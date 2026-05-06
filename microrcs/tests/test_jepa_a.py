"""Smoke tests for `scripts/jepa_a.py` (JEPA Experiment A pipeline).

Heavy ML deps (torch) are optional; tests skip cleanly when torch is
absent, mirroring the convention used in the swarm-run smoke tests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")  # skip whole module if torch missing
np = pytest.importorskip("numpy")

# Make `scripts.jepa_a` importable under the same root as `microrcs.py`.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import jepa_a as ja  # noqa: E402


def _write_synthetic_metrics(out_dir: Path) -> None:
    """Build a minimal metrics.json fixture under bro945-test/bench-X/seed-Y/.

    Path components honor the default `load_episodes` glob:
    `bro945-*/bench-*/0019*/metrics.json`.
    """
    base = out_dir / "bro945-test" / "bench-mock" / "0019deadbeef-test"
    base.mkdir(parents=True, exist_ok=True)
    metrics = {
        "flat": {
            "episodes": [
                {"task": "harder-math-rate", "epoch": 0, "repeat": r,
                 "score": float(s), "aborted": None,
                 "cost": 0.01 * (r + 1), "n_steps": 2 + r}
                for r, s in enumerate([1.0, 0.0, 1.0, 0.5])
            ],
        },
        "full": {
            "episodes": [
                {"task": "harder-code-fibonacci", "epoch": 0, "repeat": r,
                 "score": float(s), "aborted": None,
                 "cost": 0.02, "n_steps": 5}
                for r, s in enumerate([0.0, 1.0, 0.5, 0.5])
            ],
        },
    }
    (base / "metrics.json").write_text(json.dumps(metrics))


def test_load_episodes_round_trip(tmp_path):
    _write_synthetic_metrics(tmp_path)
    # Reset module-level vocab so this test is order-independent.
    ja.TASK_VOCAB.clear()
    records = ja.load_episodes(tmp_path)
    assert len(records) == 8
    sizes = {r.model_size for r in records}
    assert sizes == {"test"}
    assert all(r.condition in ("flat", "full") for r in records)
    # v_heuristic computed and finite for every record.
    assert all(0.0 <= r.v_heuristic <= 1.0 for r in records)


def test_featurize_dim_matches_helper(tmp_path):
    _write_synthetic_metrics(tmp_path)
    ja.TASK_VOCAB.clear()
    records = ja.load_episodes(tmp_path)
    feat = ja.featurize(records[0])
    assert feat.shape == (ja._feature_dim(),)
    assert feat.dtype == np.float32


def test_build_trajectories_groups_by_size_seed_condition(tmp_path):
    _write_synthetic_metrics(tmp_path)
    ja.TASK_VOCAB.clear()
    records = ja.load_episodes(tmp_path)
    trajectories = ja.build_trajectories(records)
    # 1 size × 1 seed × 2 conditions = 2 trajectories
    assert len(trajectories) == 2
    keys = {t.key for t in trajectories}
    assert keys == {("test", "0019deadbeef-test", "flat"),
                    ("test", "0019deadbeef-test", "full")}


def test_jepa_a_vicreg_non_optional_in_train_jepa(tmp_path):
    """train_jepa() with var_weight=0 raises ValueError (Q1-T6 invariant).

    Anti-collapse (H8) requires var_weight > 0. The API must never permit
    a degenerate configuration that ships an unstable substrate.
    """
    _write_synthetic_metrics(tmp_path)
    ja.TASK_VOCAB.clear()
    records = ja.load_episodes(tmp_path)
    trajectories = ja.build_trajectories(records)
    cfg = ja.TrainConfig(epochs=1, batch_size=4, latent_dim=8, hidden=16,
                          seed=0, vicreg_var_weight=0.0)
    with pytest.raises(ValueError, match="VICReg.*non-optional"):
        ja.train_jepa(trajectories, cfg, device="cpu", verbose=False)


def test_train_jepa_smoke_runs_without_collapse(tmp_path):
    """A 2-epoch training pass on the synthetic fixture must:
    1) terminate without error,
    2) leave the latent std > 0 (i.e. encoder didn't collapse),
    3) emit a finite final loss.
    """
    _write_synthetic_metrics(tmp_path)
    ja.TASK_VOCAB.clear()
    records = ja.load_episodes(tmp_path)
    trajectories = ja.build_trajectories(records)
    cfg = ja.TrainConfig(epochs=2, batch_size=4, latent_dim=8, hidden=16,
                         seed=0)
    model, history = ja.train_jepa(trajectories, cfg, device="cpu",
                                     verbose=False)
    assert len(history) == 2
    assert all(np.isfinite(h["loss"]) for h in history)
    # No-collapse witness: per-dim std should be strictly positive after
    # 2 epochs (training hasn't fully converged yet, so we don't require
    # std ≥ 1.0 — just non-trivial). The 50-epoch run reaches 1.01.
    assert history[-1]["std_mean"] > 1e-3


def test_lambda_hat_jepa_returns_value_per_trajectory(tmp_path):
    _write_synthetic_metrics(tmp_path)
    ja.TASK_VOCAB.clear()
    records = ja.load_episodes(tmp_path)
    trajectories = ja.build_trajectories(records)
    cfg = ja.TrainConfig(epochs=2, batch_size=4, latent_dim=8, hidden=16,
                         seed=0)
    model, _ = ja.train_jepa(trajectories, cfg, device="cpu", verbose=False)
    out = ja.lambda_hat_jepa(model, trajectories, device="cpu")
    assert set(out.keys()) == {t.key for t in trajectories}


def test_lambda_hat_heuristic_returns_value_per_trajectory(tmp_path):
    _write_synthetic_metrics(tmp_path)
    ja.TASK_VOCAB.clear()
    records = ja.load_episodes(tmp_path)
    trajectories = ja.build_trajectories(records)
    out = ja.lambda_hat_heuristic(trajectories)
    assert set(out.keys()) == {t.key for t in trajectories}


def test_compare_estimators_aggregates(tmp_path):
    """compare_estimators must produce one row per (size, condition) and
    a finite median ratio when both estimators have ≥1 cell each."""
    _write_synthetic_metrics(tmp_path)
    ja.TASK_VOCAB.clear()
    records = ja.load_episodes(tmp_path)
    trajectories = ja.build_trajectories(records)
    cfg = ja.TrainConfig(epochs=2, batch_size=4, latent_dim=8, hidden=16,
                         seed=0)
    model, _ = ja.train_jepa(trajectories, cfg, device="cpu", verbose=False)
    jl = ja.lambda_hat_jepa(model, trajectories, device="cpu")
    hl = ja.lambda_hat_heuristic(trajectories)
    cmp = ja.compare_estimators(jl, hl)
    assert cmp["n_cells"] >= 1
    # On synthetic data with 1 seed per cell, no variance is computable —
    # so n_finite_ratios may be 0. Just check structural integrity.
    assert "rows" in cmp
    assert all("model_size" in r for r in cmp["rows"])


def test_ols_slope_handles_degenerate_inputs():
    assert ja._ols_slope([]) is None
    assert ja._ols_slope([0.0, 0.0, 0.0]) is None  # all non-positive
    assert ja._ols_slope([1.0, 1.0, 1.0]) is None  # zero variance in log
    out = ja._ols_slope([1.0, 0.5, 0.25, 0.125])  # halving
    assert out is not None and out > 0  # decay → positive λ


# =====================================================================
# Per-step pipeline (Experiment A v2 — events.jsonl → step trajectories)
# =====================================================================
def _write_synthetic_workspace(out_dir: Path, n_episodes: int = 3,
                                steps_per_episode: int = 4,
                                condition: str = "flat") -> Path:
    """Write a minimal events.jsonl mimicking microrcs' L0 event stream.

    Layout: <out_dir>/<condition>/.rcs/events.jsonl
    Each episode has steps_per_episode OBSERVE/REASONER/DECIDE/STEP cycles,
    plus a terminal LYAPUNOV emitting a synthetic score.
    """
    ws = out_dir / condition
    rcs_dir = ws / ".rcs"
    rcs_dir.mkdir(parents=True, exist_ok=True)
    events_path = rcs_dir / "events.jsonl"
    ts = [1_000_000.0]

    def emit(level, kind, cid, payload, parent=None):
        ts[0] += 0.001
        return {
            "event_id": f"ev-{ts[0]:.3f}",
            "parent_id": parent,
            "timestamp": ts[0],
            "level": level,
            "kind": kind,
            "correlation_id": cid,
            "payload": payload,
        }

    lines: list[dict] = []
    for ep_idx in range(n_episodes):
        cid = f"ep_{ep_idx:04d}"
        cumulative_cost = 0.0
        for s in range(steps_per_episode):
            obs = emit(0, "observe", cid,
                        {"step": s, "n_messages": s + 1})
            cumulative_cost += 0.001
            lines.append(obs)
            lines.append(emit(0, "reasoner_call", cid, {
                "latency_ms": 100.0, "cost": cumulative_cost,
                "stop_reason": "tool_use",
                "input_tokens": 10 * (s + 1), "output_tokens": 5 * (s + 1),
            }, parent=obs["event_id"]))
            decide = emit(0, "decide", cid,
                            {"tool": "bash", "arguments": {"command": "ls"}},
                            parent=obs["event_id"])
            lines.append(decide)
            lines.append(emit(0, "shield", cid,
                                {"action_type": "BashAction", "reason": ""},
                                parent=decide["event_id"]))
            lines.append(emit(0, "step", cid,
                                {"action_type": "BashAction",
                                 "is_error": (s % 2 == 1),
                                 "obs_len": 50 + s * 10},
                                parent=decide["event_id"]))
        score = 1.0 if (ep_idx % 2 == 0) else 0.0
        lines.append(emit(0, "lyapunov", cid, {
            "V": 0.5, "score": score,
            "cost": cumulative_cost, "step": steps_per_episode,
        }))
    events_path.write_text("\n".join(json.dumps(d) for d in lines) + "\n")
    return ws


def test_parse_workspace_events_round_trip(tmp_path):
    ja.TASK_VOCAB.clear()
    ws = _write_synthetic_workspace(tmp_path, n_episodes=3,
                                      steps_per_episode=4)
    by_cid = ja.parse_workspace_events(ws)
    assert len(by_cid) == 3
    for _cid, recs in by_cid.items():
        assert len(recs) == 4
        assert [r.step for r in recs] == [0, 1, 2, 3]
        costs = [r.cost for r in recs]
        assert all(b >= a - 1e-9 for a, b in zip(costs, costs[1:]))
        assert recs[-1].score is not None
        assert all(r.score is None for r in recs[:-1])


def test_featurize_step_dim_and_dtype(tmp_path):
    ws = _write_synthetic_workspace(tmp_path, n_episodes=1)
    by_cid = ja.parse_workspace_events(ws)
    rec = next(iter(by_cid.values()))[0]
    feat = ja.featurize_step(rec)
    assert feat.shape == (ja._step_feature_dim(),)
    assert feat.dtype == np.float32


def test_collect_step_trajectories_aggregates_workspaces(tmp_path):
    """Each subdir is one workspace; trajectories aggregate across conditions
    with namespaced cids so cid collisions across workspaces can't merge."""
    _write_synthetic_workspace(tmp_path, n_episodes=2, condition="flat")
    _write_synthetic_workspace(tmp_path, n_episodes=2, condition="full")
    trajectories = ja.collect_step_trajectories(tmp_path)
    assert len(trajectories) == 4  # 2 episodes × 2 conditions
    conds = sorted({t.key[0] for t in trajectories})
    assert conds == ["flat", "full"]


def test_build_step_trajectories_drops_too_short(tmp_path):
    """Episodes with < 2 steps must be filtered out (no z_t→z_{t+1})."""
    ja.TASK_VOCAB.clear()
    ws = _write_synthetic_workspace(tmp_path, n_episodes=2,
                                      steps_per_episode=1)
    by_cid = ja.parse_workspace_events(ws)
    trajectories = ja.build_step_trajectories(by_cid)
    assert trajectories == []


def test_jepa_a_vicreg_non_optional_in_train_step_jepa(tmp_path):
    """train_step_jepa() with var_weight=0 raises ValueError.

    Same Q1-T6 invariant as train_jepa, applied to the per-step training
    entry point. Anti-collapse (H8) requires var_weight > 0.
    """
    _write_synthetic_workspace(tmp_path, n_episodes=4, steps_per_episode=5,
                                 condition="flat")
    trajectories = ja.collect_step_trajectories(tmp_path)
    cfg = ja.TrainConfig(epochs=1, batch_size=4, latent_dim=8, hidden=16,
                          seed=0, vicreg_var_weight=0.0)
    with pytest.raises(ValueError, match="VICReg.*non-optional"):
        ja.train_step_jepa(trajectories, cfg, device="cpu", verbose=False)


def test_train_step_jepa_smoke_runs_without_collapse(tmp_path):
    _write_synthetic_workspace(tmp_path, n_episodes=4, steps_per_episode=5,
                                condition="flat")
    _write_synthetic_workspace(tmp_path, n_episodes=4, steps_per_episode=5,
                                condition="full")
    trajectories = ja.collect_step_trajectories(tmp_path)
    assert len(trajectories) >= 4
    cfg = ja.TrainConfig(epochs=2, batch_size=4, latent_dim=8, hidden=16,
                          seed=0)
    model, history = ja.train_step_jepa(trajectories, cfg, device="cpu",
                                          verbose=False)
    assert len(history) == 2
    assert all(np.isfinite(h["loss"]) for h in history)
    assert history[-1]["std_mean"] > 1e-3


def test_lambda_hat_step_returns_value_per_trajectory(tmp_path):
    _write_synthetic_workspace(tmp_path, n_episodes=4, steps_per_episode=5,
                                condition="flat")
    trajectories = ja.collect_step_trajectories(tmp_path)
    cfg = ja.TrainConfig(epochs=2, batch_size=4, latent_dim=8, hidden=16,
                          seed=0)
    model, _ = ja.train_step_jepa(trajectories, cfg, device="cpu",
                                    verbose=False)
    out = ja.lambda_hat_step(model, trajectories, device="cpu")
    assert set(out.keys()) == {t.key for t in trajectories}


def test_lambda_hat_step_cohort_handles_single_step_trajectories(tmp_path):
    """Cohort fit must gracefully degrade when every trajectory contributes
    only one step pair (all xs collapsed to step_idx=0 → undefined slope)."""
    _write_synthetic_workspace(tmp_path, n_episodes=6, steps_per_episode=2,
                                condition="flat")
    trajectories = ja.collect_step_trajectories(tmp_path)
    cfg = ja.TrainConfig(epochs=2, batch_size=4, latent_dim=8, hidden=16,
                          seed=0)
    model, _ = ja.train_step_jepa(trajectories, cfg, device="cpu",
                                    verbose=False)
    cohort = ja.lambda_hat_step_cohort(model, trajectories, device="cpu")
    assert "flat" in cohort
    # All 2-step trajectories → all pairs at step_idx=0 → no slope possible
    assert cohort["flat"]["lambda_hat"] is None
    assert cohort["flat"]["n_unique_steps"] == 1
    assert cohort["flat"]["n_pairs"] == 6


def test_lambda_hat_step_cohort_fits_when_steps_vary(tmp_path):
    """When trajectories span multiple step indices, cohort fit succeeds."""
    _write_synthetic_workspace(tmp_path, n_episodes=4, steps_per_episode=5,
                                condition="full")
    trajectories = ja.collect_step_trajectories(tmp_path)
    cfg = ja.TrainConfig(epochs=2, batch_size=4, latent_dim=8, hidden=16,
                          seed=0)
    model, _ = ja.train_step_jepa(trajectories, cfg, device="cpu",
                                    verbose=False)
    cohort = ja.lambda_hat_step_cohort(model, trajectories, device="cpu")
    assert "full" in cohort
    assert cohort["full"]["n_unique_steps"] >= 2
    # Slope may be either sign on synthetic data — just check it's finite.
    lh = cohort["full"]["lambda_hat"]
    assert lh is None or np.isfinite(lh)


def test_perstep_cli_subcommand_dispatch(tmp_path):
    """Smoke: per-step subcommand wires up parsing → training → reporting."""
    _write_synthetic_workspace(tmp_path / "raw", n_episodes=4,
                                 steps_per_episode=5, condition="flat")
    _write_synthetic_workspace(tmp_path / "raw", n_episodes=4,
                                 steps_per_episode=5, condition="full")
    rc = ja.main([
        "per-step",
        "--workspaces", str(tmp_path / "raw"),
        "--out", str(tmp_path / "out"),
        "--epochs", "2",
        "--latent-dim", "8",
        "--hidden", "16",
    ])
    assert rc == 0
    assert (tmp_path / "out" / "results.md").exists()
    assert (tmp_path / "out" / "lambdas.json").exists()
    assert (tmp_path / "out" / "jepa_a_step.pt").exists()


def test_vicreg_loss_penalizes_collapse():
    """When all latents are identical, var_loss should be high."""
    # Disable cov term: identical points have NO off-diagonal covariance,
    # so cov_loss is ~0. Variance-only signal is the relevant one.
    z_collapsed = torch.zeros(8, 4)
    loss_c, info_c = ja.vicreg_loss(z_collapsed, var_weight=25.0,
                                       cov_weight=0.0)
    z_diverse = torch.randn(8, 4) * 2.0
    loss_d, info_d = ja.vicreg_loss(z_diverse, var_weight=25.0,
                                       cov_weight=0.0)
    assert info_c["std_mean"] < info_d["std_mean"]
    assert loss_c > loss_d
