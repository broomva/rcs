"""Sentence-transformer cache layer (Q1-T3).

Frozen sentence-transformer encoder calls dominate substrate-training
forward passes. This module caches (text, model) → embedding pairs,
keyed by sha256(text + model_version), persisted as a directory of
.npy files. Deterministic + thread-safe (file-locking via os.replace).

Usage:
    cache = STCache(cache_dir=Path('reports/.st_cache'))
    key = st_cache_key("hello", "all-MiniLM-L6-v2")
    emb = cache.get(key)
    if emb is None:
        emb = model.encode("hello")
        cache.set(key, emb)
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np


def st_cache_key(text: str, model_id: str) -> str:
    """Cache key = sha256(text + model_id). 64-char hex string."""
    h = hashlib.sha256()
    h.update(model_id.encode("utf-8"))
    h.update(b"\x00")  # separator to prevent collision (text + model collisions)
    h.update(text.encode("utf-8"))
    return h.hexdigest()


class STCache:
    """File-backed embedding cache. One .npy file per key.

    Atomicity: writes go to .tmp + os.replace (atomic on POSIX).
    """

    def __init__(self, cache_dir: Path | str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Shard by first 2 chars to avoid one giant directory.
        return self.cache_dir / key[:2] / f"{key}.npy"

    def get(self, key: str) -> np.ndarray | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return np.load(p, allow_pickle=False)
        except (OSError, ValueError):
            # Corrupted file — pretend it's a miss; caller will re-compute
            return None

    def set(self, key: str, emb: np.ndarray) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".npy.tmp")
        # Open explicitly so np.save does not auto-append ".npy" to the .tmp path.
        with open(tmp, "wb") as f:
            np.save(f, emb.astype(np.float32))
        tmp.replace(p)  # atomic

    def size(self) -> int:
        return sum(1 for _ in self.cache_dir.rglob("*.npy"))
