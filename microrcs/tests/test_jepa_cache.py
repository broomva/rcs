"""Tests for sentence-transformer cache layer (Q1-T3)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.jepa_cache import STCache, st_cache_key  # noqa: E402


def test_cache_key_deterministic():
    """Same text + model → same key, byte-equal."""
    k1 = st_cache_key("hello world", "all-MiniLM-L6-v2")
    k2 = st_cache_key("hello world", "all-MiniLM-L6-v2")
    assert k1 == k2
    assert len(k1) == 64  # sha256 hex


def test_cache_key_text_sensitive():
    """Different text → different keys."""
    assert st_cache_key("a", "m1") != st_cache_key("b", "m1")


def test_cache_key_model_sensitive():
    """Different model → different keys."""
    assert st_cache_key("a", "m1") != st_cache_key("a", "m2")


def test_cache_get_returns_none_on_miss(tmp_path):
    """Empty cache returns None for any key."""
    cache = STCache(cache_dir=tmp_path)
    assert cache.get("nonexistent-key") is None


def test_cache_set_and_get_round_trip(tmp_path):
    """Stored embedding round-trips byte-equal."""
    cache = STCache(cache_dir=tmp_path)
    emb = np.random.randn(384).astype(np.float32)
    cache.set("test-key", emb)
    retrieved = cache.get("test-key")
    assert retrieved is not None
    np.testing.assert_array_equal(emb, retrieved)


def test_cache_persists_across_instances(tmp_path):
    """Two STCache instances with same cache_dir share storage."""
    cache_a = STCache(cache_dir=tmp_path)
    emb = np.zeros(384, dtype=np.float32)
    cache_a.set("k", emb)
    cache_b = STCache(cache_dir=tmp_path)
    np.testing.assert_array_equal(cache_b.get("k"), emb)


def test_cache_size_grows_with_inserts(tmp_path):
    """size() reflects the number of cached entries."""
    cache = STCache(cache_dir=tmp_path)
    assert cache.size() == 0
    cache.set("k1", np.zeros(384, dtype=np.float32))
    cache.set("k2", np.ones(384, dtype=np.float32))
    assert cache.size() == 2
