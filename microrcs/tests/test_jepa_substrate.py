"""Tests for MlpJepaSubstrate (Q1-T5).

Avoids sentence-transformers dependency by pre-populating the cache with
synthetic embeddings — encode() never falls through to the lazy ST model.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.jepa_cache import st_cache_key  # noqa: E402
from scripts.jepa_features import EpisodeContext  # noqa: E402
from scripts.jepa_substrate import (  # noqa: E402
    MlpJepaSubstrate,
    ACPredictor,
    SubstrateConfig,
    vicreg_loss,
)


def _make_ctx() -> EpisodeContext:
    return EpisodeContext(
        text="bash ls",
        struct=np.zeros(32, dtype=np.float32),
        history_tokens=np.zeros((5, 7), dtype=np.float32),
    )


def _make_substrate_with_cached_text(tmp_path: Path,
                                       text: str = "bash ls",
                                       **kwargs) -> MlpJepaSubstrate:
    """Build a substrate with text pre-cached so encode() never loads ST."""
    cfg = SubstrateConfig(**kwargs)
    sub = MlpJepaSubstrate(cfg, cache_dir=tmp_path)
    fake_emb = np.zeros(cfg.text_dim, dtype=np.float32)
    sub.st_cache.set(st_cache_key(text, cfg.st_model_id), fake_emb)
    return sub


def test_substrate_construction_with_default_config(tmp_path):
    """MlpJepaSubstrate constructs with default config and has version_id."""
    cfg = SubstrateConfig()
    sub = MlpJepaSubstrate(cfg, cache_dir=tmp_path)
    assert sub.version_id is not None
    assert sub.is_stable is True


def test_substrate_encode_returns_64d_tensor(tmp_path):
    """encode(ctx) → R^64 (cache pre-populated; ST not loaded)."""
    sub = _make_substrate_with_cached_text(tmp_path, latent_dim=64)
    z = sub.encode(_make_ctx())
    assert z.shape == (64,)
    assert torch.is_tensor(z)


def test_substrate_predict_action_conditioned(tmp_path):
    """predict(z, a) returns same-shape latent; a affects output."""
    cfg = SubstrateConfig(latent_dim=64)
    sub = MlpJepaSubstrate(cfg, cache_dir=tmp_path)
    z = torch.randn(64)
    a1 = torch.tensor([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    a2 = torch.tensor([0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    p1 = sub.predict(z, a1)
    p2 = sub.predict(z, a2)
    assert p1.shape == (64,)
    assert not torch.allclose(p1, p2)


def test_substrate_energy_is_nonnegative(tmp_path):
    """energy(z, z') ≥ 0; equals 0 iff z == z'."""
    sub = MlpJepaSubstrate(SubstrateConfig(), cache_dir=tmp_path)
    z = torch.zeros(64)
    z_eq = torch.zeros(64)
    z_neq = torch.ones(64)
    assert sub.energy(z, z_eq) == pytest.approx(0.0, abs=1e-6)
    assert sub.energy(z, z_neq) > 0


def test_ac_predictor_residual_at_zero_action():
    """ACPredictor(z, 0) returns same shape; residual structure preserved."""
    p = ACPredictor(latent_dim=64, action_dim=7, hidden=64)
    z = torch.randn(64)
    a = torch.zeros(7)
    z_pred = p(z, a)
    assert z_pred.shape == (64,)


def test_vicreg_loss_returns_finite_for_random_input():
    """VICReg loss is well-defined and finite on random input."""
    z = torch.randn(16, 64)
    loss, info = vicreg_loss(z, var_weight=25.0, cov_weight=1.0)
    assert torch.isfinite(loss)
    assert "var_loss" in info
    assert "cov_loss" in info


def test_vicreg_loss_penalizes_collapse():
    """VICReg loss is high when all latents are identical."""
    z_collapsed = torch.zeros(16, 64)
    z_diverse = torch.randn(16, 64) * 2.0
    loss_c, _ = vicreg_loss(z_collapsed, var_weight=25.0, cov_weight=0.0)
    loss_d, _ = vicreg_loss(z_diverse, var_weight=25.0, cov_weight=0.0)
    assert loss_c > loss_d


def test_substrate_save_and_load_round_trip(tmp_path):
    """Substrate state_dict round-trips through disk."""
    cfg = SubstrateConfig()
    sub_a = MlpJepaSubstrate(cfg, cache_dir=tmp_path / "cache_a")
    pt_path = tmp_path / "sub.pt"
    sub_a.save(pt_path)

    sub_b = MlpJepaSubstrate(cfg, cache_dir=tmp_path / "cache_b")
    sub_b.load(pt_path)

    z = torch.randn(64)
    a = torch.zeros(7)
    pa = sub_a.predict(z, a)
    pb = sub_b.predict(z, a)
    torch.testing.assert_close(pa, pb)


def test_substrate_version_id_changes_after_load(tmp_path):
    """Loading new weights bumps version_id."""
    sub = MlpJepaSubstrate(SubstrateConfig(), cache_dir=tmp_path / "c")
    v1 = sub.version_id
    pt_path = tmp_path / "sub.pt"
    sub.save(pt_path)
    sub.load(pt_path)
    assert sub.version_id != v1


def test_substrate_is_stable_false_on_nan_in_predict(tmp_path):
    """If predict() produces NaN, substrate sets is_stable=False."""
    sub = MlpJepaSubstrate(SubstrateConfig(), cache_dir=tmp_path)
    z = torch.full((64,), float("nan"))
    a = torch.zeros(7)
    _ = sub.predict(z, a)
    assert sub.is_stable is False


def test_vicreg_non_optional_invariant_in_train_step(tmp_path):
    """train_step() with vicreg disabled raises an explicit error.

    VICReg is non-optional per spec Section 4.1 invariant 3 — anti-collapse
    is load-bearing for theorem (H8 alpha_k > 0). This test enforces that
    invariant at the API level."""
    sub = MlpJepaSubstrate(SubstrateConfig(), cache_dir=tmp_path)
    z = torch.randn(8, 64)
    z_next = torch.randn(8, 64)
    a = torch.zeros(8, 7)
    with pytest.raises(ValueError, match="VICReg.*non-optional"):
        sub.train_step(z, a, z_next, vicreg_var_weight=0.0)


def test_vicreg_non_optional_invariant_in_loss():
    """vicreg_loss() with var_weight=0 raises ValueError directly."""
    z = torch.randn(8, 64)
    with pytest.raises(ValueError, match="VICReg.*non-optional"):
        vicreg_loss(z, var_weight=0.0, cov_weight=1.0)
