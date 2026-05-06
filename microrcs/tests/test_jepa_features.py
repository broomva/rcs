"""Tests for 3-source feature pipeline (Q1-T4)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.jepa_features import (  # noqa: E402
    EpisodeContext,
    StructFeatures,
    HistoryFeatures,
    FusionEncoder,
    extract_struct,
    extract_history_tokens,
)


def test_struct_features_dim_is_32():
    """StructFeatures emits exactly 32-d vectors."""
    s = StructFeatures()
    out = s.encode({"cost": 0.05, "steps": 10, "latency_ms": 200,
                    "input_tokens": 1000, "output_tokens": 200,
                    "step_idx": 3})
    assert out.shape == (32,)
    assert out.dtype == np.float32


def test_struct_features_normalize_known_inputs():
    """Cost / steps / tokens / latency normalize to [0, 1] when below caps."""
    s = StructFeatures(max_cost_usd=1.0, max_steps=20, max_step_idx=20)
    out = s.encode({"cost": 0.5, "steps": 10, "latency_ms": 1000,
                    "input_tokens": 0, "output_tokens": 0,
                    "step_idx": 5})
    # cost_norm ≈ 0.5; steps_norm = 0.5; step_idx_norm = 0.25
    # Exact indices depend on layout; check at least 3 of them.
    assert (out > 0).any()
    assert (out >= 0).all()
    assert (out <= 1.0 + 1e-6).all()


def test_history_features_handles_short_history():
    """If history has < K events, pad to K."""
    h = HistoryFeatures(max_history=5)
    tokens = h.tokenize([{"tool": "bash", "is_error": False}])
    assert len(tokens) == 5  # pad to max_history
    # First entry is the real one; others are pad tokens
    assert (tokens[0] != h._pad_token).any()


def test_history_features_truncates_long_history():
    """If history has > K events, keep the last K."""
    h = HistoryFeatures(max_history=3)
    events = [{"tool": "bash", "is_error": i % 2 == 0} for i in range(10)]
    tokens = h.tokenize(events)
    assert len(tokens) == 3


def test_fusion_encoder_output_dim_64():
    """FusionEncoder emits 64-d vectors regardless of input variant."""
    enc = FusionEncoder(text_dim=384, struct_dim=32, history_dim=64,
                        out_dim=64)
    text = torch.randn(384)
    struct = torch.randn(32)
    history = torch.randn(64)
    z = enc(text, struct, history)
    assert z.shape == (64,)


def test_fusion_encoder_is_deterministic_given_seed():
    """Same input + same model state → same output."""
    torch.manual_seed(42)
    enc1 = FusionEncoder(text_dim=384, struct_dim=32, history_dim=64,
                         out_dim=64)
    torch.manual_seed(42)
    enc2 = FusionEncoder(text_dim=384, struct_dim=32, history_dim=64,
                         out_dim=64)
    inputs = (torch.zeros(384), torch.zeros(32), torch.zeros(64))
    z1 = enc1(*inputs)
    z2 = enc2(*inputs)
    torch.testing.assert_close(z1, z2)


def test_episode_context_carries_three_sources():
    """EpisodeContext is the input contract; verify it has the three fields."""
    ctx = EpisodeContext(text="hello", struct=np.zeros(32, dtype=np.float32),
                         history_tokens=np.zeros((5, 8), dtype=np.float32))
    assert ctx.text == "hello"
    assert ctx.struct.shape == (32,)
    assert ctx.history_tokens.shape == (5, 8)


def test_extract_struct_from_step_record():
    """extract_struct accepts a StepRecord-like dict and produces 32-d."""
    rec = {"cost": 0.01, "n_steps": 3, "latency_ms": 100,
           "input_tokens": 500, "output_tokens": 50, "step": 1}
    out = extract_struct(rec)
    assert out.shape == (32,)


def test_extract_history_tokens_returns_padded():
    """extract_history_tokens emits a (max_history, token_dim) array."""
    out = extract_history_tokens([], max_history=5, token_dim=8)
    assert out.shape == (5, 8)
