"""JEPA Experiment A — MLP-JEPA Lyapunov estimator on microRCS bench traces.

Tests the central claim from `docs/research-notes/2026-05-05-jepa-as-rcs-frame.md`:

    V̂_0 = ||P_φ(s_θ(z_t)) - sg(s'_θ(z_{t+1}))||²

is a more reliable Lyapunov function than the current heuristic

    V_0 = 0.3 * cost_frac + 0.3 * step_frac + 0.4 * (1 - score)

across capacity tiers (Sonnet vs Opus).

The experiment is *episode-level* (not step-level): each capacity-sweep
report stores per-episode summaries `(task, score, cost, n_steps, ...)`,
so we treat each episode as a state and the per-(seed, condition) sequence
as a trajectory. Same temporal granularity as the current `LambdaMonitor`
(which fits λ̂ from per-episode `EventKind.LYAPUNOV` samples), so the
comparison is apples-to-apples.

If `Var[λ̂_0]_JEPA < Var[λ̂_0]_heuristic` across {Sonnet, Opus} × 4 conditions,
the JEPA energy is empirically the better Lyapunov surrogate and graduates
to the production estimator. If not, the cost+steps+score heuristic stays.

Usage:
    python -m scripts.jepa_a --reports ../reports --out ../reports/jepa-a/
    python -m scripts.jepa_a --reports ../reports --out ../reports/jepa-a/ --epochs 50

Spec: docs/research-notes/2026-05-05-jepa-as-rcs-frame.md §3 Experiment A
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Shared vocabularies — extended automatically when load_episodes encounters
# a task or condition not in the seed list. Order is fixed at first sight so
# featurization stays deterministic across reruns on the same data.
TASK_VOCAB: list[str] = []
CONDITION_VOCAB: list[str] = ["flat", "+autonomic", "+meta", "full"]


# === 1. Episode loading =====================================================
@dataclass
class EpisodeRecord:
    model_size: str       # "sonnet" / "opus" / "haiku" / "gemma4" / ...
    seed: str             # bench seed run id
    condition: str
    epoch: int
    repeat: int
    task: str
    score: float
    aborted: str | None
    cost: float
    n_steps: int
    # Heuristic Lyapunov, computed from cost+steps+score the same way
    # microrcs._compute_v0 does (caps embedded in the bench config).
    v_heuristic: float = 0.0

    @property
    def group_key(self) -> tuple[str, str, str]:
        return (self.model_size, self.seed, self.condition)


def load_episodes(reports_dir: Path,
                  glob_pattern: str = "bro945-*/bench-*/0019*/metrics.json"
                  ) -> list[EpisodeRecord]:
    """Parse all per-episode records under `reports_dir`.

    Expected layout: `<reports_dir>/bro945-<size>/bench-<id>/<seed_id>/metrics.json`.
    Each `metrics.json` is `{condition: {"episodes": [...], ...}, ...}`.
    """
    records: list[EpisodeRecord] = []
    for path in sorted(reports_dir.glob(glob_pattern)):
        # bro945-sonnet → "sonnet"
        size = path.parents[2].name.replace("bro945-", "")
        seed = path.parent.name
        data = json.loads(path.read_text())
        for cond, body in data.items():
            for ep in body.get("episodes", []):
                rec = EpisodeRecord(
                    model_size=size,
                    seed=seed,
                    condition=cond,
                    epoch=int(ep.get("epoch", 0)),
                    repeat=int(ep.get("repeat", 0)),
                    task=str(ep["task"]),
                    score=float(ep.get("score", 0.0)),
                    aborted=ep.get("aborted"),
                    cost=float(ep.get("cost", 0.0)),
                    n_steps=int(ep.get("n_steps", 0)),
                )
                rec.v_heuristic = _compute_v_heuristic(rec)
                records.append(rec)
                if rec.task not in TASK_VOCAB:
                    TASK_VOCAB.append(rec.task)
    return records


def _compute_v_heuristic(rec: EpisodeRecord,
                         max_cost_usd: float = 0.50,
                         max_steps: int = 20) -> float:
    """Mirror of `microrcs._compute_v0` formula at episode level."""
    cost_frac = min(rec.cost / max(max_cost_usd, 1e-9), 1.0)
    step_frac = min(rec.n_steps / max(max_steps, 1), 1.0)
    return 0.3 * cost_frac + 0.3 * step_frac + 0.4 * (1.0 - rec.score)


# === 2. Featurization =======================================================
def _feature_dim() -> int:
    # 4 scalars + 4 condition + len(TASK_VOCAB) tasks + 2 (epoch/repeat normalized)
    return 4 + len(CONDITION_VOCAB) + len(TASK_VOCAB) + 2


def featurize(rec: EpisodeRecord,
              max_cost_usd: float = 0.50,
              max_steps: int = 20) -> np.ndarray:
    """Build a deterministic state vector. Dim = `_feature_dim()`."""
    feat = np.zeros(_feature_dim(), dtype=np.float32)
    feat[0] = min(rec.cost / max(max_cost_usd, 1e-9), 1.0)
    feat[1] = min(rec.n_steps / max(max_steps, 1), 1.0)
    feat[2] = float(rec.score)
    feat[3] = 1.0 if rec.aborted else 0.0
    if rec.condition in CONDITION_VOCAB:
        feat[4 + CONDITION_VOCAB.index(rec.condition)] = 1.0
    if rec.task in TASK_VOCAB:
        feat[4 + len(CONDITION_VOCAB) + TASK_VOCAB.index(rec.task)] = 1.0
    feat[-2] = rec.epoch / 10.0
    feat[-1] = rec.repeat / 10.0
    return feat


# === 3. Trajectories (per-(model, seed, condition) ordered episodes) ========
@dataclass
class Trajectory:
    key: tuple[str, str, str]
    episodes: list[EpisodeRecord]

    @property
    def features(self) -> np.ndarray:
        """Stack `featurize` over the trajectory. Shape (T, D)."""
        return np.stack([featurize(e) for e in self.episodes], axis=0)


def build_trajectories(records: list[EpisodeRecord]) -> list[Trajectory]:
    """Group by (model, seed, condition), sort by (epoch, repeat, task)."""
    groups: dict[tuple, list[EpisodeRecord]] = {}
    for r in records:
        groups.setdefault(r.group_key, []).append(r)
    trajectories: list[Trajectory] = []
    for k, eps in groups.items():
        eps.sort(key=lambda e: (e.epoch, e.repeat, TASK_VOCAB.index(e.task)
                                if e.task in TASK_VOCAB else 0))
        trajectories.append(Trajectory(k, eps))
    return trajectories


# === 4. JEPA model ==========================================================
class MLPEncoder(nn.Module):
    def __init__(self, in_dim: int, hidden: int = 64, out_dim: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, out_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class MLPPredictor(nn.Module):
    """Residual predictor: ẑ' = z + MLP(z)."""

    def __init__(self, dim: int = 32, hidden: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, hidden),
            nn.GELU(),
            nn.Linear(hidden, dim),
        )

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        return z + self.net(z)


class JEPA(nn.Module):
    """Minimal MLP-JEPA: encoder + EMA target encoder + residual predictor.

    Energy along a trajectory:
        E_t = ||P_φ(s_θ(z_t)) - sg(s'_θ(z_{t+1}))||²

    where `s'_θ` is the EMA target encoder (BYOL/JEPA convention) and
    `sg` is stop-gradient.
    """

    def __init__(self, in_dim: int, latent_dim: int = 32, hidden: int = 64,
                 ema_momentum: float = 0.99):
        super().__init__()
        self.encoder = MLPEncoder(in_dim, hidden, latent_dim)
        self.target_encoder = MLPEncoder(in_dim, hidden, latent_dim)
        self.predictor = MLPPredictor(latent_dim, hidden)
        self.ema_momentum = ema_momentum
        # Initialize target = encoder; freeze its gradients.
        self.target_encoder.load_state_dict(self.encoder.state_dict())
        for p in self.target_encoder.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def update_target(self) -> None:
        m = self.ema_momentum
        for p_online, p_target in zip(self.encoder.parameters(),
                                      self.target_encoder.parameters()):
            p_target.data.mul_(m).add_(p_online.data, alpha=1 - m)

    def forward(self, x_t: torch.Tensor, x_next: torch.Tensor
                ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        z_t = self.encoder(x_t)
        z_pred = self.predictor(z_t)
        with torch.no_grad():
            z_target = self.target_encoder(x_next)
        return z_t, z_pred, z_target

    @torch.no_grad()
    def energy(self, x_t: torch.Tensor, x_next: torch.Tensor) -> torch.Tensor:
        """Compute V̂_0 = ||P(s(x_t)) - s'(x_next)||² (no grad)."""
        z_pred = self.predictor(self.encoder(x_t))
        z_target = self.target_encoder(x_next)
        return ((z_pred - z_target) ** 2).sum(dim=-1)


# === 5. Loss (VICReg-lite collapse prevention) ==============================
def vicreg_loss(z: torch.Tensor,
                sim_weight: float = 25.0,
                var_weight: float = 25.0,
                cov_weight: float = 1.0,
                eps: float = 1e-4) -> tuple[torch.Tensor, dict]:
    """Minimal VICReg regularization on a batch of latent vectors.

    Note: we ONLY compute the variance + covariance terms here. The
    invariance term is replaced by the JEPA prediction loss in the caller
    (the predictor IS the invariance constraint). This keeps the loss
    formulation faithful to JEPA-style training.
    """
    # Variance term: penalize per-dim std falling below 1.0 (Hinge).
    std = torch.sqrt(z.var(dim=0, unbiased=False) + eps)
    var_loss = F.relu(1.0 - std).mean()
    # Covariance term: off-diagonal of normalized cov matrix → 0.
    z_centered = z - z.mean(dim=0, keepdim=True)
    cov = (z_centered.T @ z_centered) / max(z.size(0) - 1, 1)
    diag_mask = torch.eye(z.size(1), dtype=torch.bool, device=z.device)
    cov_loss = (cov[~diag_mask] ** 2).sum() / z.size(1)
    total = var_weight * var_loss + cov_weight * cov_loss
    return total, {
        "var_loss": float(var_loss.detach()),
        "cov_loss": float(cov_loss.detach()),
        "std_mean": float(std.mean().detach()),
    }


# === 6. Training ============================================================
@dataclass
class TrainConfig:
    epochs: int = 50
    batch_size: int = 64
    learning_rate: float = 1e-3
    latent_dim: int = 32
    hidden: int = 64
    ema_momentum: float = 0.99
    vicreg_var_weight: float = 25.0
    vicreg_cov_weight: float = 1.0
    seed: int = 42


def _build_pairs(trajectories: list[Trajectory]
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Concatenate (z_t, z_{t+1}) within trajectories. Returns (X_t, X_next)."""
    parts_t: list[np.ndarray] = []
    parts_next: list[np.ndarray] = []
    for traj in trajectories:
        feats = traj.features
        if feats.shape[0] < 2:
            continue
        parts_t.append(feats[:-1])
        parts_next.append(feats[1:])
    if not parts_t:
        raise ValueError("No usable trajectories (all length < 2)")
    return np.concatenate(parts_t, axis=0), np.concatenate(parts_next, axis=0)


def train_jepa(trajectories: list[Trajectory],
               cfg: TrainConfig,
               device: str = "cpu",
               verbose: bool = True) -> tuple[JEPA, list[dict]]:
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    X_t, X_next = _build_pairs(trajectories)
    in_dim = X_t.shape[1]
    n = X_t.shape[0]
    if verbose:
        print(f"[jepa-a] training on {n} pairs, dim={in_dim}, "
              f"latent={cfg.latent_dim}, epochs={cfg.epochs}")

    model = JEPA(in_dim, latent_dim=cfg.latent_dim, hidden=cfg.hidden,
                 ema_momentum=cfg.ema_momentum).to(device)
    opt = Adam(list(model.encoder.parameters()) +
                list(model.predictor.parameters()),
                lr=cfg.learning_rate)
    X_t_t = torch.from_numpy(X_t).to(device)
    X_next_t = torch.from_numpy(X_next).to(device)

    history: list[dict] = []
    for epoch in range(cfg.epochs):
        perm = torch.randperm(n, device=device)
        epoch_loss = 0.0
        epoch_pred = 0.0
        epoch_var = 0.0
        n_batches = 0
        for i in range(0, n, cfg.batch_size):
            idx = perm[i: i + cfg.batch_size]
            x_t = X_t_t[idx]
            x_next = X_next_t[idx]
            z_t, z_pred, z_target = model(x_t, x_next)
            pred_loss = ((z_pred - z_target) ** 2).sum(dim=-1).mean()
            reg_loss, reg_info = vicreg_loss(
                z_t,
                var_weight=cfg.vicreg_var_weight,
                cov_weight=cfg.vicreg_cov_weight,
            )
            loss = pred_loss + reg_loss
            opt.zero_grad()
            loss.backward()
            opt.step()
            model.update_target()
            epoch_loss += float(loss.detach())
            epoch_pred += float(pred_loss.detach())
            epoch_var += reg_info["std_mean"]
            n_batches += 1
        history.append({
            "epoch": epoch,
            "loss": epoch_loss / max(n_batches, 1),
            "pred_loss": epoch_pred / max(n_batches, 1),
            "std_mean": epoch_var / max(n_batches, 1),
        })
        if verbose and (epoch == 0 or (epoch + 1) % 10 == 0
                        or epoch == cfg.epochs - 1):
            h = history[-1]
            print(f"[jepa-a] epoch {epoch:>3} loss={h['loss']:.4f} "
                  f"pred={h['pred_loss']:.4f} std={h['std_mean']:.3f}")
    return model, history


# === 7. λ̂_0 estimation =====================================================
def _ols_slope(values: list[float]) -> float | None:
    """OLS slope of log(values) vs index. Returns None if degenerate.

    Uses the same convention as `microrcs.LambdaMonitor.lambda_hat`: the
    slope of `-log V` is reported (positive λ ⟺ V decaying ⟺ stable).
    """
    if len(values) < 3:
        return None
    pos = [(i, v) for i, v in enumerate(values) if v > 0]
    if len(pos) < 3:
        return None
    xs = np.array([p[0] for p in pos], dtype=np.float64)
    ys = np.log(np.array([p[1] for p in pos], dtype=np.float64))
    if np.allclose(ys.std(), 0):
        return None
    slope, _ = np.polyfit(xs, ys, 1)
    return float(-slope)


def lambda_hat_jepa(model: JEPA,
                    trajectories: list[Trajectory],
                    device: str = "cpu") -> dict[tuple, float | None]:
    out: dict[tuple, float | None] = {}
    model.eval()
    for traj in trajectories:
        feats = traj.features
        if feats.shape[0] < 2:
            out[traj.key] = None
            continue
        x_t = torch.from_numpy(feats[:-1]).to(device)
        x_next = torch.from_numpy(feats[1:]).to(device)
        e = model.energy(x_t, x_next).cpu().numpy().tolist()
        out[traj.key] = _ols_slope(e)
    return out


def lambda_hat_heuristic(trajectories: list[Trajectory]
                         ) -> dict[tuple, float | None]:
    out: dict[tuple, float | None] = {}
    for traj in trajectories:
        v = [e.v_heuristic for e in traj.episodes]
        out[traj.key] = _ols_slope(v)
    return out


# === 8. Comparison ==========================================================
def variance_by_capacity_condition(
    lambdas: dict[tuple, float | None]
) -> dict[tuple[str, str], dict]:
    """Group λ̂ values by (model_size, condition); compute variance over seeds."""
    grouped: dict[tuple[str, str], list[float]] = {}
    for (size, _seed, cond), lam in lambdas.items():
        if lam is None or not math.isfinite(lam):
            continue
        grouped.setdefault((size, cond), []).append(lam)
    out: dict[tuple[str, str], dict] = {}
    for k, vals in grouped.items():
        if len(vals) < 2:
            out[k] = {"mean": vals[0] if vals else None, "var": None,
                      "n": len(vals)}
            continue
        out[k] = {
            "mean": float(np.mean(vals)),
            "var": float(np.var(vals, ddof=1)),
            "std": float(np.std(vals, ddof=1)),
            "n": len(vals),
        }
    return out


def compare_estimators(jepa_lambdas: dict, heur_lambdas: dict) -> dict:
    """Cross-tab Var[λ̂] for both estimators per (model_size, condition)."""
    jepa_var = variance_by_capacity_condition(jepa_lambdas)
    heur_var = variance_by_capacity_condition(heur_lambdas)
    keys = sorted(set(jepa_var.keys()) | set(heur_var.keys()))
    rows: list[dict] = []
    for k in keys:
        size, cond = k
        j = jepa_var.get(k, {})
        h = heur_var.get(k, {})
        ratio = (j.get("var") / h["var"]
                 if (j.get("var") is not None and h.get("var")
                     and h.get("var") > 0) else None)
        rows.append({
            "model_size": size, "condition": cond,
            "jepa_mean": j.get("mean"), "jepa_var": j.get("var"),
            "jepa_n": j.get("n"),
            "heuristic_mean": h.get("mean"), "heuristic_var": h.get("var"),
            "heuristic_n": h.get("n"),
            "var_ratio_jepa_over_heur": ratio,
        })
    # Aggregate: how often does JEPA have lower variance?
    finite_ratios = [r["var_ratio_jepa_over_heur"] for r in rows
                     if r["var_ratio_jepa_over_heur"] is not None]
    n_jepa_wins = sum(1 for r in finite_ratios if r < 1.0)
    return {
        "rows": rows,
        "n_cells": len(rows),
        "n_finite_ratios": len(finite_ratios),
        "n_jepa_lower_variance": n_jepa_wins,
        "median_ratio": (float(np.median(finite_ratios))
                         if finite_ratios else None),
    }


def render_markdown(comparison: dict, train_history: list[dict],
                    n_trajectories: int, n_pairs: int) -> str:
    rows = comparison["rows"]
    out = ["# JEPA Experiment A — Results",
           "",
           f"**Date**: {time.strftime('%Y-%m-%d')}",
           f"**Trajectories**: {n_trajectories}",
           f"**Training pairs**: {n_pairs}",
           f"**Final training loss**: "
           f"{train_history[-1]['loss']:.4f}" if train_history else "n/a",
           "",
           "## Variance ratio per (model_size, condition)",
           "",
           "| model_size | condition | JEPA mean λ̂ | JEPA Var | "
           "Heur mean λ̂ | Heur Var | Var ratio J/H |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        def fmt(x: float | None) -> str:
            return f"{x:.4f}" if isinstance(x, float) else "—"
        out.append(
            f"| {r['model_size']} | {r['condition']} | "
            f"{fmt(r['jepa_mean'])} | {fmt(r['jepa_var'])} | "
            f"{fmt(r['heuristic_mean'])} | {fmt(r['heuristic_var'])} | "
            f"{fmt(r['var_ratio_jepa_over_heur'])} |"
        )
    out += [
        "",
        f"**JEPA wins (lower Var) in {comparison['n_jepa_lower_variance']} / "
        f"{comparison['n_finite_ratios']} cells**",
        f"**Median Var ratio (JEPA / heuristic)**: "
        f"{comparison['median_ratio']:.4f}"
        if comparison["median_ratio"] is not None else "n/a",
        "",
        "## Verdict",
        "",
        ("- **JEPA energy is the empirically more reliable Lyapunov surrogate**"
         " — median ratio < 1 across capacity tiers."
         if (comparison["median_ratio"] is not None
             and comparison["median_ratio"] < 1.0)
         else "- **Heuristic V_0 = 0.3*cost + 0.3*step + 0.4*(1-score) "
              "remains the better estimator**: JEPA does not reduce "
              "Var[λ̂_0] across capacity tiers."),
        "",
        "## Training curve (final 5 epochs)",
        "",
        "| epoch | loss | pred_loss | std_mean |",
        "|---|---|---|---|"]
    for h in train_history[-5:]:
        out.append(f"| {h['epoch']} | {h['loss']:.4f} | "
                    f"{h['pred_loss']:.4f} | {h['std_mean']:.3f} |")
    out.append("")
    return "\n".join(out)


# === 9. Per-step extraction (Experiment A v2: step-level data) =============
# Episode-level v1 (above) hit a null result because pass-rate ceiling on
# Opus compressed both estimators into the e-3/e-4 band. Per-step data
# isn't subject to that artifact: within-episode dynamics are richer than
# the binary score outcome. This section provides the parser + featurizer
# for events.jsonl streams produced by `microrcs.run` with a persistent
# workspace.

@dataclass
class StepRecord:
    """One agent step within an episode, reconstructed from RCSEvent stream."""
    cid: str          # episode correlation id (cid="ep_<id>")
    workspace: str
    condition: str    # "flat" / "+autonomic" / "+meta" / "full"
    step: int
    tool: str         # "bash" / "submit" / "<no-decide>"
    is_error: bool
    obs_len: int
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost: float       # cumulative cost at this step
    score: float | None  # only set on terminal step (LYAPUNOV-bearing)


@dataclass
class StepTrajectory:
    """One per-episode step sequence + its precomputed feature stack."""
    key: tuple[str, str]   # (condition, cid)
    steps: list[StepRecord]
    features: np.ndarray   # shape (T, D)


STEP_TOOL_VOCAB: tuple[str, ...] = ("bash", "submit", "<no-decide>")


def _step_feature_dim() -> int:
    # 1 step_norm + 3 tool one-hot + 1 is_error + 1 obs_log + 2 token_logs
    # + 1 latency_log + 1 cost_norm + len(CONDITION_VOCAB) condition one-hot
    return 1 + len(STEP_TOOL_VOCAB) + 1 + 1 + 2 + 1 + 1 + len(CONDITION_VOCAB)


def featurize_step(rec: StepRecord, max_steps: int = 15,
                   max_cost: float = 0.50) -> np.ndarray:
    feat = np.zeros(_step_feature_dim(), dtype=np.float32)
    i = 0
    feat[i] = min(rec.step / max(max_steps, 1), 1.0); i += 1
    if rec.tool in STEP_TOOL_VOCAB:
        feat[i + STEP_TOOL_VOCAB.index(rec.tool)] = 1.0
    i += len(STEP_TOOL_VOCAB)
    feat[i] = 1.0 if rec.is_error else 0.0; i += 1
    feat[i] = math.log1p(max(rec.obs_len, 0)) / 10.0; i += 1
    feat[i] = math.log1p(max(rec.input_tokens, 0)) / 10.0; i += 1
    feat[i] = math.log1p(max(rec.output_tokens, 0)) / 10.0; i += 1
    feat[i] = math.log1p(max(rec.latency_ms, 0)) / 10.0; i += 1
    feat[i] = min(rec.cost / max(max_cost, 1e-9), 1.0); i += 1
    if rec.condition in CONDITION_VOCAB:
        feat[i + CONDITION_VOCAB.index(rec.condition)] = 1.0
    i += len(CONDITION_VOCAB)
    return feat


def _events_to_steps(cid: str, workspace: str, condition: str,
                     events: list[dict]) -> list[StepRecord]:
    """Reduce a chronologically sorted list of L0 events for one episode
    into StepRecords. Each step starts with an OBSERVE event; the
    OBSERVE → next-OBSERVE window defines one step's events."""
    step_groups: list[dict] = []
    current: dict | None = None
    for e in events:
        if e["kind"] == "observe":
            if current is not None:
                step_groups.append(current)
            current = {"step": int(e["payload"].get("step", 0)), "events": []}
        if current is not None:
            current["events"].append(e)
    if current is not None:
        step_groups.append(current)

    records: list[StepRecord] = []
    cumulative_cost = 0.0
    for sg in step_groups:
        evs = sg["events"]
        reasoner = next((e for e in evs if e["kind"] == "reasoner_call"), None)
        decide = next((e for e in evs if e["kind"] == "decide"), None)
        step_out = next((e for e in evs if e["kind"] == "step"), None)
        lyap = next((e for e in evs if e["kind"] == "lyapunov"), None)

        latency_ms = float(reasoner["payload"].get("latency_ms", 0.0)
                            if reasoner else 0.0)
        if reasoner:
            cumulative_cost = float(reasoner["payload"].get("cost",
                                                              cumulative_cost))
        input_tokens = int(reasoner["payload"].get("input_tokens", 0)
                            if reasoner else 0)
        output_tokens = int(reasoner["payload"].get("output_tokens", 0)
                             if reasoner else 0)
        tool = str(decide["payload"].get("tool", "<no-decide>")
                    if decide else "<no-decide>")
        is_error = bool(step_out["payload"].get("is_error", False)
                         if step_out else False)
        obs_len = int(step_out["payload"].get("obs_len", 0)
                       if step_out else 0)
        score = lyap["payload"].get("score") if lyap else None
        records.append(StepRecord(
            cid=cid, workspace=workspace, condition=condition,
            step=int(sg["step"]), tool=tool, is_error=is_error,
            obs_len=obs_len, input_tokens=input_tokens,
            output_tokens=output_tokens, latency_ms=latency_ms,
            cost=cumulative_cost,
            score=float(score) if score is not None else None,
        ))
    return records


def parse_workspace_events(workspace_dir: Path
                           ) -> dict[str, list[StepRecord]]:
    """Read events.jsonl from a persistent-workspace directory, group L0
    events by correlation_id (episode cid), reduce to StepRecords.

    Path convention: `<workspace_dir>/.rcs/events.jsonl`. The workspace
    directory's name encodes the condition (`flat`, `plus_meta`, `full`).
    """
    events_path = workspace_dir / ".rcs" / "events.jsonl"
    if not events_path.exists():
        return {}
    cond_raw = workspace_dir.name
    condition = cond_raw.replace("plus_", "+")

    events_by_cid: dict[str, list[dict]] = {}
    for line in events_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        cid = d.get("correlation_id", "")
        # Only L0 episode events. L1/L2/L3 events have non-"ep_" cids.
        if cid.startswith("ep_") and d.get("level") == 0:
            events_by_cid.setdefault(cid, []).append(d)

    result: dict[str, list[StepRecord]] = {}
    for cid, evs in events_by_cid.items():
        evs.sort(key=lambda e: e["timestamp"])
        steps = _events_to_steps(cid, str(workspace_dir), condition, evs)
        if steps:
            result[cid] = steps
    return result


def build_step_trajectories(steps_by_cid: dict[str, list[StepRecord]]
                             ) -> list[StepTrajectory]:
    """One StepTrajectory per cid (episode). Drops episodes with < 2 steps
    (need at least one (z_t, z_{t+1}) pair)."""
    trajectories: list[StepTrajectory] = []
    for cid, recs in steps_by_cid.items():
        if len(recs) < 2:
            continue
        recs_sorted = sorted(recs, key=lambda r: r.step)
        cond = recs_sorted[0].condition
        feats = np.stack([featurize_step(r) for r in recs_sorted], axis=0)
        trajectories.append(StepTrajectory(
            key=(cond, cid), steps=recs_sorted, features=feats,
        ))
    return trajectories


def collect_step_trajectories(workspace_root: Path) -> list[StepTrajectory]:
    """Walk every immediate subdirectory of `workspace_root`, treat each as
    one workspace, and return all step trajectories aggregated."""
    aggregate: dict[str, list[StepRecord]] = {}
    for ws_dir in sorted(p for p in workspace_root.iterdir() if p.is_dir()):
        for cid, recs in parse_workspace_events(ws_dir).items():
            # Workspace name is the unique discriminator: cids COULD collide
            # across workspaces if random uuids alias; namespace by ws name.
            namespaced_cid = f"{ws_dir.name}:{cid}"
            aggregate[namespaced_cid] = recs
    return build_step_trajectories(aggregate)


# === 10. Per-step JEPA training (reuses model from §4-§6) ===================
def train_step_jepa(trajectories: list[StepTrajectory],
                    cfg: TrainConfig,
                    device: str = "cpu",
                    verbose: bool = True) -> tuple[JEPA, list[dict]]:
    """Same model architecture as `train_jepa`; only the trajectory type
    differs. We materialize (X_t, X_next) pairs from precomputed features."""
    parts_t: list[np.ndarray] = []
    parts_next: list[np.ndarray] = []
    for traj in trajectories:
        f = traj.features
        if f.shape[0] < 2:
            continue
        parts_t.append(f[:-1])
        parts_next.append(f[1:])
    if not parts_t:
        raise ValueError("No usable step trajectories (all length < 2)")
    X_t = np.concatenate(parts_t, axis=0)
    X_next = np.concatenate(parts_next, axis=0)
    in_dim = X_t.shape[1]
    n = X_t.shape[0]
    if verbose:
        print(f"[jepa-a-step] training on {n} step-pairs, dim={in_dim}, "
              f"latent={cfg.latent_dim}, epochs={cfg.epochs}")

    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)
    model = JEPA(in_dim, latent_dim=cfg.latent_dim, hidden=cfg.hidden,
                 ema_momentum=cfg.ema_momentum).to(device)
    opt = Adam(list(model.encoder.parameters()) +
                list(model.predictor.parameters()),
                lr=cfg.learning_rate)
    X_t_t = torch.from_numpy(X_t).to(device)
    X_next_t = torch.from_numpy(X_next).to(device)

    history: list[dict] = []
    for epoch in range(cfg.epochs):
        perm = torch.randperm(n, device=device)
        epoch_loss = epoch_pred = epoch_var = 0.0
        n_batches = 0
        for i in range(0, n, cfg.batch_size):
            idx = perm[i:i + cfg.batch_size]
            x_t = X_t_t[idx]
            x_next = X_next_t[idx]
            z_t, z_pred, z_target = model(x_t, x_next)
            pred_loss = ((z_pred - z_target) ** 2).sum(dim=-1).mean()
            reg_loss, reg_info = vicreg_loss(
                z_t, var_weight=cfg.vicreg_var_weight,
                cov_weight=cfg.vicreg_cov_weight,
            )
            loss = pred_loss + reg_loss
            opt.zero_grad(); loss.backward(); opt.step()
            model.update_target()
            epoch_loss += float(loss.detach())
            epoch_pred += float(pred_loss.detach())
            epoch_var += reg_info["std_mean"]
            n_batches += 1
        history.append({
            "epoch": epoch,
            "loss": epoch_loss / max(n_batches, 1),
            "pred_loss": epoch_pred / max(n_batches, 1),
            "std_mean": epoch_var / max(n_batches, 1),
        })
        if verbose and (epoch == 0 or (epoch + 1) % 10 == 0
                        or epoch == cfg.epochs - 1):
            h = history[-1]
            print(f"[jepa-a-step] epoch {epoch:>3} loss={h['loss']:.4f} "
                  f"pred={h['pred_loss']:.4f} std={h['std_mean']:.3f}")
    return model, history


def lambda_hat_step(model: JEPA,
                    trajectories: list[StepTrajectory],
                    device: str = "cpu") -> dict[tuple, float | None]:
    """Per-trajectory λ̂ from JEPA energy along each episode's step sequence.

    Returns None when the trajectory has fewer than 3 positive energy
    samples — `_ols_slope` requires ≥3 to fit a meaningful line.
    """
    out: dict[tuple, float | None] = {}
    model.eval()
    for traj in trajectories:
        feats = traj.features
        if feats.shape[0] < 2:
            out[traj.key] = None
            continue
        x_t = torch.from_numpy(feats[:-1]).to(device)
        x_next = torch.from_numpy(feats[1:]).to(device)
        e = model.energy(x_t, x_next).cpu().numpy().tolist()
        out[traj.key] = _ols_slope(e)
    return out


def lambda_hat_step_cohort(model: JEPA,
                            trajectories: list[StepTrajectory],
                            device: str = "cpu"
                            ) -> dict[str, dict]:
    """Cohort-aggregate λ̂ per condition.

    For each condition, pool every (step_idx, energy) pair across all
    trajectories and OLS-fit `log E` vs `step_idx` once. This sidesteps
    the per-trajectory short-episode constraint: even when individual
    trajectories don't have ≥3 step pairs, the cohort might. The trade-off
    is that survival bias (only longer trajectories reach high step_idx)
    can skew the slope; we report `n_pairs` per condition so callers can
    judge.

    Returns: `{condition: {"lambda_hat": float|None, "n_pairs": int,
    "intercept": float|None}}`.
    """
    pooled: dict[str, list[tuple[int, float]]] = {}
    model.eval()
    for traj in trajectories:
        feats = traj.features
        if feats.shape[0] < 2:
            continue
        x_t = torch.from_numpy(feats[:-1]).to(device)
        x_next = torch.from_numpy(feats[1:]).to(device)
        energies = model.energy(x_t, x_next).cpu().numpy().tolist()
        cond = traj.key[0]
        # step index of the *source* state in each pair (0, 1, ..., T-2)
        for s_idx, e in enumerate(energies):
            pooled.setdefault(cond, []).append((s_idx, float(e)))

    out: dict[str, dict] = {}
    for cond, pairs in pooled.items():
        positives = [(s, e) for s, e in pairs if e > 0]
        if len(positives) < 3:
            out[cond] = {"lambda_hat": None, "n_pairs": len(pairs),
                         "intercept": None}
            continue
        xs = np.array([p[0] for p in positives], dtype=np.float64)
        ys = np.log(np.array([p[1] for p in positives], dtype=np.float64))
        # Degenerate cases: all xs identical (every trajectory contributes
        # a single pair at the same step_idx) or all ys identical
        # (constant log-energy across pairs) — both make OLS undefined.
        if np.allclose(xs.std(), 0) or np.allclose(ys.std(), 0):
            out[cond] = {"lambda_hat": None, "n_pairs": len(pairs),
                         "intercept": None,
                         "n_unique_steps": int(np.unique(xs).size)}
            continue
        slope, intercept = np.polyfit(xs, ys, 1)
        out[cond] = {"lambda_hat": float(-slope), "n_pairs": len(pairs),
                     "intercept": float(intercept),
                     "n_unique_steps": int(np.unique(xs).size)}
    return out


def render_perstep_markdown(
    trajectories: list[StepTrajectory],
    lambdas: dict[tuple, float | None],
    train_history: list[dict],
    cohort_lambdas: dict[str, dict] | None = None,
) -> str:
    # Group by condition.
    by_condition: dict[str, list[float]] = {}
    score_for_lambda: dict[str, list[tuple[float, float]]] = {}
    for traj in trajectories:
        cond = traj.key[0]
        lam = lambdas.get(traj.key)
        if lam is None or not math.isfinite(lam):
            continue
        by_condition.setdefault(cond, []).append(lam)
        # Episode score is the score on the terminal step (LYAPUNOV-bearing).
        terminal = traj.steps[-1]
        if terminal.score is not None:
            score_for_lambda.setdefault(cond, []).append(
                (lam, float(terminal.score))
            )

    out = ["# JEPA Experiment A — Per-Step Results",
           "",
           f"**Date**: {time.strftime('%Y-%m-%d')}",
           f"**Step trajectories** (≥2 steps): {len(trajectories)}",
           f"**Step pairs trained on**: "
           f"{sum(max(t.features.shape[0] - 1, 0) for t in trajectories)}",
           f"**Final pred_loss**: "
           f"{train_history[-1]['pred_loss']:.4f}" if train_history else "n/a",
           f"**Final std_mean**: "
           f"{train_history[-1]['std_mean']:.3f}" if train_history else "n/a",
           "",
           "## λ̂ distribution per condition",
           "",
           "| condition | n | mean λ̂ | std | min | max |",
           "|---|---|---|---|---|---|"]
    for cond in sorted(by_condition):
        vals = by_condition[cond]
        if not vals:
            continue
        out.append(f"| {cond} | {len(vals)} | "
                    f"{float(np.mean(vals)):+.4f} | "
                    f"{float(np.std(vals, ddof=1)) if len(vals) > 1 else 0:.4f} | "
                    f"{min(vals):+.4f} | {max(vals):+.4f} |")

    if cohort_lambdas:
        out += [
            "",
            "## Cohort-aggregate λ̂ per condition",
            "",
            "(Pools every (step_idx, energy) pair across trajectories per "
            "condition; one OLS fit per condition. Sidesteps short-trajectory "
            "limit of per-trajectory λ̂.)",
            "",
            "| condition | n_pairs | λ̂ (cohort) | intercept |",
            "|---|---|---|---|"]
        for cond in sorted(cohort_lambdas):
            entry = cohort_lambdas[cond]
            lh = entry.get("lambda_hat")
            ic = entry.get("intercept")
            out.append(f"| {cond} | {entry.get('n_pairs', 0)} | "
                        f"{lh:+.4f}" + " | " + (f"{ic:+.4f}" if ic is not None
                                                  else "—") + " |"
                        if lh is not None else
                        f"| {cond} | {entry.get('n_pairs', 0)} | n/a | n/a |")

    out += [
        "",
        "## λ̂ vs final episode score (correlation)",
        "",
        "| condition | n | Pearson r |",
        "|---|---|---|"]
    for cond, pairs in sorted(score_for_lambda.items()):
        if len(pairs) < 3:
            out.append(f"| {cond} | {len(pairs)} | n/a (n<3) |")
            continue
        xs = np.array([p[0] for p in pairs])
        ys = np.array([p[1] for p in pairs])
        if xs.std() == 0 or ys.std() == 0:
            out.append(f"| {cond} | {len(pairs)} | n/a (zero variance) |")
        else:
            r = float(np.corrcoef(xs, ys)[0, 1])
            out.append(f"| {cond} | {len(pairs)} | {r:+.3f} |")

    out += [
        "",
        "## Training curve (final 5 epochs)",
        "",
        "| epoch | loss | pred_loss | std_mean |",
        "|---|---|---|---|"]
    for h in train_history[-5:]:
        out.append(f"| {h['epoch']} | {h['loss']:.4f} | "
                    f"{h['pred_loss']:.4f} | {h['std_mean']:.3f} |")
    out.append("")
    return "\n".join(out)


# === 11. CLI ================================================================
def _cmd_episode_level(args: argparse.Namespace) -> int:
    reports_dir = Path(args.reports)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[jepa-a] loading episodes from {reports_dir}")
    records = load_episodes(reports_dir)
    if not records:
        print("[jepa-a] ERROR: no episode records found", file=sys.stderr)
        return 1
    print(f"[jepa-a] loaded {len(records)} episodes; "
          f"tasks={len(TASK_VOCAB)}; sizes="
          f"{sorted({r.model_size for r in records})}")

    trajectories = build_trajectories(records)
    print(f"[jepa-a] built {len(trajectories)} trajectories "
          f"(median len="
          f"{int(np.median([len(t.episodes) for t in trajectories]))})")

    cfg = TrainConfig(
        epochs=args.epochs, batch_size=args.batch_size,
        learning_rate=args.lr, latent_dim=args.latent_dim,
        hidden=args.hidden, ema_momentum=args.ema, seed=args.seed,
    )
    model, history = train_jepa(trajectories, cfg, device=args.device,
                                  verbose=True)
    n_pairs = sum(max(t.features.shape[0] - 1, 0) for t in trajectories)

    jepa_lambdas = lambda_hat_jepa(model, trajectories, device=args.device)
    heur_lambdas = lambda_hat_heuristic(trajectories)

    comparison = compare_estimators(jepa_lambdas, heur_lambdas)
    md = render_markdown(comparison, history, len(trajectories), n_pairs)

    (out_dir / "results.md").write_text(md)
    (out_dir / "comparison.json").write_text(json.dumps(comparison,
                                                        indent=2, default=str))
    (out_dir / "training_history.json").write_text(json.dumps(history, indent=2))
    (out_dir / "lambdas_jepa.json").write_text(json.dumps(
        {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in jepa_lambdas.items()}, indent=2))
    (out_dir / "lambdas_heuristic.json").write_text(json.dumps(
        {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in heur_lambdas.items()}, indent=2))
    torch.save(model.state_dict(), out_dir / "jepa_a.pt")

    print()
    print(f"[jepa-a] wrote {out_dir}/results.md")
    print(f"[jepa-a] median Var ratio (JEPA / heuristic): "
          f"{comparison['median_ratio']}")
    print(f"[jepa-a] JEPA wins {comparison['n_jepa_lower_variance']} / "
          f"{comparison['n_finite_ratios']} cells")
    return 0


def _cmd_per_step(args: argparse.Namespace) -> int:
    workspaces_root = Path(args.workspaces)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not workspaces_root.exists():
        print(f"[jepa-a-step] ERROR: workspaces root does not exist: "
              f"{workspaces_root}", file=sys.stderr)
        return 1

    print(f"[jepa-a-step] parsing workspaces under {workspaces_root}")
    trajectories = collect_step_trajectories(workspaces_root)
    if not trajectories:
        print("[jepa-a-step] ERROR: no step trajectories with ≥2 steps",
              file=sys.stderr)
        return 1
    n_pairs = sum(max(t.features.shape[0] - 1, 0) for t in trajectories)
    print(f"[jepa-a-step] {len(trajectories)} trajectories, "
          f"{n_pairs} step-pairs, "
          f"conditions={sorted({t.key[0] for t in trajectories})}")

    cfg = TrainConfig(
        epochs=args.epochs, batch_size=args.batch_size,
        learning_rate=args.lr, latent_dim=args.latent_dim,
        hidden=args.hidden, ema_momentum=args.ema, seed=args.seed,
    )
    model, history = train_step_jepa(trajectories, cfg, device=args.device,
                                       verbose=True)
    lambdas = lambda_hat_step(model, trajectories, device=args.device)
    cohort = lambda_hat_step_cohort(model, trajectories, device=args.device)
    md = render_perstep_markdown(trajectories, lambdas, history,
                                  cohort_lambdas=cohort)

    (out_dir / "results.md").write_text(md)
    (out_dir / "training_history.json").write_text(json.dumps(history, indent=2))
    (out_dir / "lambdas.json").write_text(json.dumps(
        {f"{k[0]}|{k[1]}": v for k, v in lambdas.items()},
        indent=2, default=str,
    ))
    (out_dir / "cohort_lambdas.json").write_text(json.dumps(cohort, indent=2))
    torch.save(model.state_dict(), out_dir / "jepa_a_step.pt")

    finite = [v for v in lambdas.values() if v is not None and math.isfinite(v)]
    print()
    print(f"[jepa-a-step] wrote {out_dir}/results.md")
    if finite:
        print(f"[jepa-a-step] per-trajectory λ̂: n={len(finite)}, "
              f"mean={float(np.mean(finite)):+.4f} "
              f"std={float(np.std(finite, ddof=1)) if len(finite) > 1 else 0:.4f}")
    else:
        print(f"[jepa-a-step] no finite per-trajectory λ̂ "
              f"(trajectories too short)")
    for cond in sorted(cohort):
        entry = cohort[cond]
        lh = entry.get("lambda_hat")
        if lh is not None:
            print(f"[jepa-a-step] cohort λ̂[{cond}] = {lh:+.4f} "
                  f"(n_pairs={entry['n_pairs']})")
        else:
            print(f"[jepa-a-step] cohort λ̂[{cond}] = n/a "
                  f"(n_pairs={entry['n_pairs']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd")

    # episode-level (default for backward compatibility — no subcommand also OK)
    ep = sub.add_parser("episode-level",
                         help="Train JEPA on per-episode bench aggregates "
                              "(v1 default).")
    ep.add_argument("--reports", default="reports",
                     help="Directory containing bro945-*/bench-*/0019*/metrics.json")
    ep.add_argument("--out", default="reports/jepa-a",
                     help="Output directory for trained model + report")
    ep.add_argument("--epochs", type=int, default=50)
    ep.add_argument("--batch-size", type=int, default=64)
    ep.add_argument("--latent-dim", type=int, default=32)
    ep.add_argument("--hidden", type=int, default=64)
    ep.add_argument("--lr", type=float, default=1e-3)
    ep.add_argument("--ema", type=float, default=0.99)
    ep.add_argument("--seed", type=int, default=42)
    ep.add_argument("--device", default="cpu")
    ep.set_defaults(func=_cmd_episode_level)

    # per-step (v2 — fresh-bench events.jsonl)
    ps = sub.add_parser("per-step",
                         help="Train JEPA on per-step trajectories from a "
                              "persistent-workspace events.jsonl bench (v2).")
    ps.add_argument("--workspaces", required=True,
                     help="Directory whose subdirs are persistent workspaces "
                          "with .rcs/events.jsonl streams.")
    ps.add_argument("--out", default="reports/jepa-a-perstep",
                     help="Output directory for trained model + report")
    ps.add_argument("--epochs", type=int, default=100)
    ps.add_argument("--batch-size", type=int, default=64)
    ps.add_argument("--latent-dim", type=int, default=32)
    ps.add_argument("--hidden", type=int, default=64)
    ps.add_argument("--lr", type=float, default=1e-3)
    ps.add_argument("--ema", type=float, default=0.99)
    ps.add_argument("--seed", type=int, default=42)
    ps.add_argument("--device", default="cpu")
    ps.set_defaults(func=_cmd_per_step)

    # Backward-compat: bare `python -m scripts.jepa_a --reports ...` (no
    # subcommand) maps to episode-level. argparse can't directly express
    # this with sub.required=False + default values, so we handle it
    # manually below.
    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        # Re-parse with episode-level defaults so old invocations keep working.
        return _cmd_episode_level(ap.parse_args(["episode-level"] + (argv or sys.argv[1:])))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
