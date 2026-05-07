"""Joint phase gate evaluator (Q1-T7).

Reads pre-registration TOML, computes G1-G3 (math gate) + P1 (production
gate) on a trained substrate + holdout trajectories, emits a structured
gate report with PASS/FAIL decision.

Spec ref: Section 5.1 (joint gate definition).

Pre-registered thresholds live in `data/q1_pre_registration.toml`. This
script must NEVER hardcode thresholds — they come from the TOML AND the
analysis run cites the commit hash in the report.

Usage:
    python -m scripts.jepa_validate \\
        --substrate reports/q1-substrate/substrate.pt \\
        --workspaces reports/q1-substrate/raw/ \\
        --pre-registration data/q1_pre_registration.toml \\
        --out reports/q1-substrate/q1_gate_report.json
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


# === Per-gate evaluators ====================================================

def evaluate_g1_var_ratio(
    jepa_var_per_cell: dict[str, float | None],
    heur_var_per_cell: dict[str, float | None],
    threshold: float = 1.0,
    min_conditions: int = 3,
) -> dict:
    """G1: median Var[λ̂_0]_JEPA / Var[λ̂_0]_heuristic < threshold across
    ≥min_conditions conditions."""
    ratios = []
    for cond in jepa_var_per_cell:
        j = jepa_var_per_cell[cond]
        h = heur_var_per_cell.get(cond)
        if j is None or h is None or h == 0:
            continue
        if not (math.isfinite(j) and math.isfinite(h)):
            continue
        ratios.append(j / h)
    if len(ratios) < min_conditions:
        return {"pass": False,
                "reason": f"insufficient_conditions ({len(ratios)} < {min_conditions})",
                "n_conditions": len(ratios)}
    median = float(np.median(ratios))
    return {"pass": median < threshold,
            "median_ratio": median,
            "n_conditions": len(ratios),
            "all_ratios": ratios}


def evaluate_g2_pearson(
    lambdas: np.ndarray,
    scores: np.ndarray,
    threshold: float = -0.2,
) -> dict:
    """G2: Pearson r(λ̂, episode_score) ≤ threshold (predictor surprise
    tracks failure → negative r)."""
    finite = np.isfinite(lambdas) & np.isfinite(scores)
    lambdas, scores = lambdas[finite], scores[finite]
    if len(lambdas) < 3 or lambdas.std() == 0 or scores.std() == 0:
        return {"pass": False, "reason": "insufficient_data_or_zero_variance"}
    r = float(np.corrcoef(lambdas, scores)[0, 1])
    return {"pass": r <= threshold, "pearson_r": r, "n": len(lambdas)}


def evaluate_g3_training_health(
    history: list[dict],
    min_std_mean: float = 0.5,
    max_consecutive_increases: int = 3,
    epoch_for_std_check: int = 100,
) -> dict:
    """G3: training health — std_mean ≥ threshold, no NaN, ≤max consecutive
    loss-increases."""
    if not history:
        return {"pass": False, "reason": "empty_history"}
    if any(not math.isfinite(h.get("loss", float("inf"))) for h in history):
        return {"pass": False, "reason": "nan_in_loss"}
    # std_mean check at later of (epoch_for_std_check, last_epoch)
    last_idx = min(epoch_for_std_check, len(history) - 1)
    std_mean_at_check = history[last_idx].get("std_mean", 0.0)
    if std_mean_at_check < min_std_mean:
        return {"pass": False,
                "reason": f"low_std_mean ({std_mean_at_check} < {min_std_mean})",
                "std_mean_at_check": std_mean_at_check}
    # Monotone-ish: count consecutive epoch-over-epoch increases
    losses = [h.get("loss", 0.0) for h in history]
    consec = 0
    max_consec = 0
    for i in range(1, len(losses)):
        if losses[i] > losses[i - 1]:
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0
    if max_consec > max_consecutive_increases:
        return {"pass": False,
                "reason": f"non_monotone (max consec increases {max_consec})",
                "max_consecutive_increases": max_consec}
    return {"pass": True,
            "std_mean_at_check": std_mean_at_check,
            "max_consecutive_increases": max_consec}


def evaluate_p1_spearman(
    lambdas: np.ndarray,
    pass_bool: np.ndarray,
    threshold: float = -0.15,
    significance: float = 0.05,
) -> dict:
    """P1: Spearman ρ(λ̂, pass) ≤ threshold with p<significance."""
    try:
        from scipy import stats
    except ImportError:
        return {"pass": False, "reason": "scipy_not_installed"}
    finite = np.isfinite(lambdas)
    lambdas, pass_bool = lambdas[finite], pass_bool[finite]
    if len(lambdas) < 3 or lambdas.std() == 0:
        return {"pass": False, "reason": "insufficient_data_or_zero_variance"}
    rho, p = stats.spearmanr(lambdas, pass_bool)
    return {"pass": bool((rho <= threshold) and (p < significance)),
            "spearman_rho": float(rho),
            "p_value": float(p),
            "n": len(lambdas)}


# === Joint gate decision ====================================================

def joint_gate_decision(
    g1: dict, g2: dict, g3: dict, p1: dict,
    math_pass_threshold: int = 2,
) -> dict:
    """Joint gate: math 2-of-3 + P1 both must pass."""
    math_passes = sum(int(bool(g.get("pass", False))) for g in (g1, g2, g3))
    p1_pass = bool(p1.get("pass", False))
    failed_gates = []
    if not g1.get("pass"):
        failed_gates.append("g1")
    if not g2.get("pass"):
        failed_gates.append("g2")
    if not g3.get("pass"):
        failed_gates.append("g3")
    if not p1_pass:
        failed_gates.append("p1")
    overall = ("PASS" if (math_passes >= math_pass_threshold and p1_pass)
                else "FAIL")
    return {
        "overall": overall,
        "math_gate_passes": math_passes,
        "math_gate_threshold": math_pass_threshold,
        "p1_pass": p1_pass,
        "failed_gates": failed_gates,
    }


# === Report =================================================================

@dataclass
class GateReport:
    commit_hash: str
    q_phase: str
    gates: dict
    decision: str
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "commit_hash": self.commit_hash,
            "q_phase": self.q_phase,
            "gates": self.gates,
            "decision": self.decision,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def save(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2,
                                          default=str))

    def render_markdown(self) -> str:
        out = [f"# Q-Phase Gate Report — {self.q_phase}",
               "",
               f"**Commit:** {self.commit_hash}",
               f"**Timestamp:** {self.timestamp}",
               f"**Decision:** **{self.decision}**",
               ""]
        for gate_name, gate in self.gates.items():
            status = "✓" if gate.get("pass") else "✗"
            out.append(f"## {gate_name.upper()} — {status}")
            for k, v in gate.items():
                if k == "pass":
                    continue
                out.append(f"- `{k}`: {v}")
            out.append("")
        return "\n".join(out)


def _git_commit_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()[:8]
    except subprocess.CalledProcessError:
        return "unknown"


# === CLI ====================================================================

# === Q1-T8 wiring: load substrate artifacts + per-trajectory data ===========
#
# Q1-T7 (PR #54) shipped the per-gate evaluator functions but left main() as
# a documented stub ("Task 8 wires the actual evaluation"). This block fills
# that in. Inputs:
#
#   --substrate           reports/q1-substrate/jepa-substrate-q1/jepa_a_step.pt
#   --workspaces          reports/q1-substrate/all-episodes/  (84 ep_* dirs)
#   --pre-registration    data/q1_pre_registration.toml
#
# We derive the substrate dir from the .pt path and load three artifacts
# emitted by `python -m scripts.jepa_a per-step --out <dir>`:
#
#   training_history.json  — list of {epoch, loss, pred_loss, std_mean}; G3
#   cohort_lambdas.json    — {namespaced_cid: {lambda_hat, n_pairs, ...}};
#                            per-trajectory JEPA λ̂; G1+G2+P1
#   jepa_a_step.pt         — model state dict (loaded for sanity; unused
#                            for gate evaluation since cohort_lambdas.json
#                            already cached the per-trajectory slopes)
#
# Per-trajectory λ̂_heuristic is computed locally by replaying events.jsonl
# with the same V_step formula microrcs uses internally
# (cost_frac + step_frac + (1 - score)).

# Per-instance budgets used to normalize V_heuristic. Match swe_pilot's
# `--max-cost 2.0 --max-steps 100` (the values used during Q1-T2 collection).
# Misaligned norms saturate the heuristic prematurely and bias G1.
HEUR_MAX_COST_USD = 2.0
HEUR_MAX_STEPS = 100


def _heuristic_v_per_step(cumulative_cost: float, step: int,
                           score: float = 0.0,
                           max_cost: float = HEUR_MAX_COST_USD,
                           max_steps: int = HEUR_MAX_STEPS) -> float:
    """V_step heuristic mirroring microrcs._compute_v0 at step granularity."""
    cost_frac = min(cumulative_cost / max(max_cost, 1e-9), 1.0)
    step_frac = min(step / max(max_steps, 1), 1.0)
    return 0.3 * cost_frac + 0.3 * step_frac + 0.4 * (1.0 - score)


def _ols_slope(values: list[float]) -> float | None:
    """Same OLS-slope helper as jepa_a._ols_slope. Reproduced to avoid a
    cross-module import that pulls torch into the validator's startup."""
    n = len(values)
    if n < 2:
        return None
    xs = np.arange(n, dtype=np.float64)
    ys = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(ys)):
        return None
    x_mean = xs.mean()
    y_mean = ys.mean()
    denom = float(((xs - x_mean) ** 2).sum())
    if denom <= 0:
        return None
    return float(((xs - x_mean) * (ys - y_mean)).sum() / denom)


def _parse_episode_events(events_path: Path
                          ) -> tuple[list[float], float | None]:
    """Replay one episode's events.jsonl. Returns:
        - per-step V_heuristic values (one per OBSERVE event)
        - terminal score (if a `step` event with `submitted=true` exists,
          else None — the agent didn't finalize an answer).
    """
    if not events_path.exists():
        return [], None
    cumulative_cost = 0.0
    step_idx = 0
    v_per_step: list[float] = []
    final_score: float | None = None
    seen_observe_for_step = False
    with events_path.open() as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            kind = e.get("kind", "")
            payload = e.get("payload", {})
            if kind == "reasoner_call":
                # Cumulative cost is tracked as the latest reasoner cost.
                c = payload.get("cost")
                if isinstance(c, (int, float)):
                    cumulative_cost = float(c)
            elif kind == "observe":
                # New step boundary — emit V for the prior step (if any),
                # then bump step counter.
                if seen_observe_for_step:
                    v_per_step.append(_heuristic_v_per_step(
                        cumulative_cost, step_idx,
                        score=final_score or 0.0,
                    ))
                    step_idx += 1
                seen_observe_for_step = True
            elif kind == "step":
                # Terminal step carries the score on submission.
                if payload.get("submitted"):
                    s = payload.get("score")
                    if isinstance(s, (int, float)):
                        final_score = float(s)
            elif kind == "lyapunov":
                # Final lyapunov event also carries score; if we missed
                # it on the step event, capture here.
                s = payload.get("score")
                if isinstance(s, (int, float)) and final_score is None:
                    final_score = float(s)
    # Emit the last step's V (if any).
    if seen_observe_for_step:
        v_per_step.append(_heuristic_v_per_step(
            cumulative_cost, step_idx, score=final_score or 0.0,
        ))
    return v_per_step, final_score


def _condition_from_namespace(name: str) -> str | None:
    """Map a namespaced-cid like `flat-seed1--ep_0019...` or
    `plus_meta-seed1009--ep_0019...` back to its condition label.
    The pre-reg uses condition labels {flat, +autonomic, +meta, full};
    workspace dirs use POSIX-safe names {flat, plus_autonomic, plus_meta,
    full}. We normalize back to pre-reg labels so G1's per-condition
    grouping aligns with the TOML's q1.conditions.values list."""
    m = name.split("--", 1)
    if not m:
        return None
    head = m[0]  # e.g. "flat-seed1" or "plus_meta-seed1009"
    parts = head.rsplit("-", 1)  # split off "-seed<N>"
    if len(parts) != 2 or not parts[1].startswith("seed"):
        return None
    raw_cond = parts[0]
    return {
        "flat": "flat",
        "plus_autonomic": "+autonomic",
        "plus_meta": "+meta",
        "full": "full",
    }.get(raw_cond, raw_cond)


def _aggregator_name_to_cohort_key(name: str) -> str:
    """Translate aggregator dir name (POSIX-safe `plus_meta-...`) to the
    cohort_lambdas.json key emitted by jepa_a (`+meta-...`).

    Bug history: the aggregator builder uses `plus_meta` / `plus_autonomic`
    in directory names because `+` is reserved in some shells; the
    `jepa_a per-step` trainer normalizes condition labels via CONDITION_VOCAB
    (which contains `+meta`, `+autonomic`) when emitting cohort keys. Without
    this translation `cohort_lambdas.get(ep_dir.name)` misses on 44 of 84
    trajectories (every `+meta` and `+autonomic` workspace), and G1 fails
    "insufficient_conditions" because only `flat` and `full` survive.
    """
    if name.startswith("plus_autonomic-"):
        return "+autonomic-" + name[len("plus_autonomic-"):]
    if name.startswith("plus_meta-"):
        return "+meta-" + name[len("plus_meta-"):]
    return name


def _evaluate_q1(
    substrate_path: Path,
    workspaces_root: Path,
    q1_cfg: dict,
) -> tuple[dict, dict, dict, dict, dict]:
    """Run all four gates (G1/G2/G3/P1) and return their dicts plus a
    metadata dict summarising the data shape that fed them."""
    substrate_dir = substrate_path.parent

    # Load training history (for G3) and cached cohort λ̂_JEPA values.
    training_history = json.loads(
        (substrate_dir / "training_history.json").read_text()
    )
    cohort_lambdas = json.loads(
        (substrate_dir / "cohort_lambdas.json").read_text()
    )

    # Walk workspaces, build per-trajectory records.
    per_traj: list[dict] = []
    for ep_dir in sorted(p for p in workspaces_root.iterdir() if p.is_dir()):
        events_path = ep_dir / ".rcs" / "events.jsonl"
        if not events_path.exists():
            continue
        v_steps, score = _parse_episode_events(events_path)
        if len(v_steps) < 2:
            continue
        cohort_key = _aggregator_name_to_cohort_key(ep_dir.name)
        cohort_entry = cohort_lambdas.get(cohort_key) or {}
        lam_jepa = cohort_entry.get("lambda_hat")
        if lam_jepa is None:
            continue
        lam_heur = _ols_slope(v_steps)
        cond = _condition_from_namespace(ep_dir.name)
        per_traj.append({
            "name": ep_dir.name,
            "condition": cond,
            "lambda_jepa": float(lam_jepa) if math.isfinite(float(lam_jepa)) else float("nan"),
            "lambda_heur": float(lam_heur) if (lam_heur is not None and math.isfinite(lam_heur)) else float("nan"),
            "score": float(score) if score is not None else 0.0,
            "submitted": score is not None,
        })

    # Group λ̂ values per condition for G1.
    by_cond_jepa: dict[str, list[float]] = {}
    by_cond_heur: dict[str, list[float]] = {}
    for r in per_traj:
        c = r["condition"]
        if c is None:
            continue
        if math.isfinite(r["lambda_jepa"]):
            by_cond_jepa.setdefault(c, []).append(r["lambda_jepa"])
        if math.isfinite(r["lambda_heur"]):
            by_cond_heur.setdefault(c, []).append(r["lambda_heur"])

    jepa_var_per_cell = {
        c: float(np.var(v, ddof=1)) if len(v) >= 2 else None
        for c, v in by_cond_jepa.items()
    }
    heur_var_per_cell = {
        c: float(np.var(v, ddof=1)) if len(v) >= 2 else None
        for c, v in by_cond_heur.items()
    }

    g1 = evaluate_g1_var_ratio(
        jepa_var_per_cell, heur_var_per_cell,
        threshold=float(q1_cfg["gate"]["math"]["g1_var_ratio_threshold"]),
        min_conditions=int(q1_cfg["gate"]["math"]["g1_min_conditions_with_data"]),
    )

    # Stack arrays for G2 and P1.
    lambdas_arr = np.array([r["lambda_jepa"] for r in per_traj], dtype=np.float64)
    scores_arr = np.array([r["score"] for r in per_traj], dtype=np.float64)
    pass_bool_arr = np.array([1.0 if r["score"] > 0 else 0.0 for r in per_traj],
                              dtype=np.float64)

    g2 = evaluate_g2_pearson(
        lambdas_arr, scores_arr,
        threshold=float(q1_cfg["gate"]["math"]["g2_pearson_threshold"]),
    )
    p1 = evaluate_p1_spearman(
        lambdas_arr, pass_bool_arr,
        threshold=float(q1_cfg["gate"]["production"]["p1_spearman_threshold"]),
        significance=float(q1_cfg["gate"]["production"]["p1_significance_level"]),
    )

    g3 = evaluate_g3_training_health(
        training_history,
        min_std_mean=float(q1_cfg["gate"]["math"]["g3_min_std_mean_at_epoch_100"]),
        max_consecutive_increases=int(q1_cfg["gate"]["math"]["g3_max_loss_increase_consecutive_epochs"]),
    )

    metadata = {
        "n_trajectories_total": len(per_traj),
        "n_trajectories_per_condition": {c: len(v) for c, v in by_cond_jepa.items()},
        "n_pass_total": int(pass_bool_arr.sum()),
        "jepa_var_per_condition": jepa_var_per_cell,
        "heuristic_var_per_condition": heur_var_per_cell,
        "training_history_epochs": len(training_history),
        "substrate_dir": str(substrate_dir),
    }
    return g1, g2, g3, p1, metadata


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--substrate", required=True,
                    help="Path to trained substrate .pt")
    ap.add_argument("--workspaces", required=True,
                    help="Directory with raw events.jsonl per workspace")
    ap.add_argument("--pre-registration", required=True,
                    help="Path to q1_pre_registration.toml")
    ap.add_argument("--out", default="reports/q1_gate_report.json")
    args = ap.parse_args(argv)

    import tomllib
    cfg = tomllib.loads(Path(args.pre_registration).read_text())
    q1 = cfg["q1"]

    substrate_path = Path(args.substrate)
    workspaces_root = Path(args.workspaces)
    g1, g2, g3, p1, metadata = _evaluate_q1(substrate_path, workspaces_root, q1)

    decision = joint_gate_decision(g1, g2, g3, p1)
    rep = GateReport(
        commit_hash=_git_commit_hash(),
        q_phase="Q1",
        gates={"g1": g1, "g2": g2, "g3": g3, "p1": p1},
        decision=decision["overall"],
        metadata={**metadata, "joint_gate_decision": decision},
    )
    rep.save(args.out)

    # Also emit the markdown rendering next to the JSON for quick review.
    md_path = Path(args.out).with_suffix(".md")
    md_path.write_text(rep.render_markdown())

    print(f"[jepa-validate] wrote {args.out}: {rep.decision}")
    print(f"[jepa-validate] wrote {md_path}")
    print(f"[jepa-validate] math_passes={decision['math_gate_passes']}/3 "
          f"p1_pass={decision['p1_pass']} "
          f"failed={decision['failed_gates']}")
    return 0 if rep.decision == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
