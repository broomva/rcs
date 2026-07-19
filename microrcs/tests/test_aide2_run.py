"""Unit tests for the aide2_run checkpoint/resume state (BRO-1947).

Pure — no network, no CLI, no HF. The resume path is load-bearing: a run
interrupted at the subscription rate wall must restart WITHOUT re-scoring the
genesis holdout (wasted episodes) and with the incumbent private-gate bar
(best_holdout) intact. Run by CI `test-microrcs`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from adapters.cli_plant import HarnessConfig  # noqa: E402
from scripts.aide2_run import apply_state_dict, loop_state_dict  # noqa: E402


class _StubLoop:
    """Duck-typed stand-in for GenerationLoop's resumable surface."""

    def __init__(self):
        self.n_steps: int = 0
        self.best: HarnessConfig = HarnessConfig()
        self.best_holdout: float | None = None
        self.history: list = []


def test_state_roundtrip_preserves_fields():
    src = _StubLoop()
    src.n_steps = 3
    src.best = HarnessConfig(
        model="claude-sonnet-4-6", max_turns=80,
        system_prompt_append="coach", generation=3, parent="gen2", notes="p",
    )
    src.best_holdout = 0.6667
    src.history = [
        {"config": "{}", "train_score": 0.5, "accepted": False},
        {"config": "{}", "train_score": 0.75, "accepted": True},
    ]
    state = loop_state_dict(src)

    dst = _StubLoop()
    apply_state_dict(dst, state)

    assert dst.n_steps == 3
    assert dst.best_holdout == 0.6667
    assert dst.history == src.history
    assert dst.best.max_turns == 80
    assert dst.best.system_prompt_append == "coach"
    assert dst.best.generation == 3
    assert dst.best.model == "claude-sonnet-4-6"


def test_restore_keeps_best_holdout_non_none():
    # The whole point: a resumed loop must NOT re-score genesis (best_holdout
    # is None only on a truly fresh start).
    src = _StubLoop()
    src.n_steps = 1
    src.best_holdout = 0.0  # genesis scored 0 on holdout — must survive as 0.0, not None
    state = loop_state_dict(src)
    dst = _StubLoop()
    apply_state_dict(dst, state)
    assert dst.best_holdout is not None
    assert dst.best_holdout == 0.0


def test_history_defaults_empty_when_absent():
    dst = _StubLoop()
    apply_state_dict(dst, {"n_steps": 2, "best_config": HarnessConfig().to_json(), "best_holdout": 0.5})
    assert dst.history == []


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
