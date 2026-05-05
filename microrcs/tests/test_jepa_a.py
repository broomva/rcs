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
