"""Unit tests for the oracle validity classifier (BRO-1948).

Pure — no network, no subprocess, no swebench. Exercises `classify_oracle`,
the decision surface that gates which SWE-bench-Lite instances enter the
pre-registered splits: empty-diff fails-at-base + p2p healthy, AND gold patch
makes f2p all pass (source edits genuinely exercised). Run by CI.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.curate_instances import classify_oracle  # noqa: E402


def _empty(**kw) -> dict:
    base = {
        "error": None, "fail_to_pass_total": 1, "fail_to_pass_passing": 0,
        "pass_to_pass_total": 10, "pass_to_pass_passing": 10,
    }
    base.update(kw)
    return base


def _gold(**kw) -> dict:
    base = {"error": None, "fail_to_pass_total": 1, "fail_to_pass_passing": 1}
    base.update(kw)
    return base


def test_valid_oracle():
    ok, reason = classify_oracle(_empty(), _gold())
    assert ok is True and "ORACLE ok" in reason


def test_empty_missing():
    ok, reason = classify_oracle(None, _gold())
    assert ok is False and reason == "empty_not_scored"


def test_empty_error():
    ok, reason = classify_oracle(_empty(error="boom"), _gold())
    assert ok is False and reason.startswith("empty_verifier_error")


def test_no_f2p():
    ok, reason = classify_oracle(_empty(fail_to_pass_total=0), _gold())
    assert ok is False and reason == "no_fail_to_pass_tests"


def test_f2p_passes_at_base():
    ok, reason = classify_oracle(_empty(fail_to_pass_passing=1), _gold())
    assert ok is False and "f2p_passes_at_base" in reason


def test_p2p_fails_at_base_broken_env():
    ok, reason = classify_oracle(_empty(pass_to_pass_passing=8), _gold())
    assert ok is False and "p2p_fails_at_base" in reason


def test_gold_missing():
    ok, reason = classify_oracle(_empty(), None)
    assert ok is False and reason == "gold_not_scored"


def test_gold_error():
    ok, reason = classify_oracle(_empty(), _gold(error="kaboom"))
    assert ok is False and reason.startswith("gold_verifier_error")


def test_gold_f2p_not_all_pass_edits_not_exercised():
    # The load-bearing BRO-1948 case: gold applied but F2P still fails =>
    # source edits are NOT being exercised (the fidelity bug).
    ok, reason = classify_oracle(_empty(), _gold(fail_to_pass_passing=0))
    assert ok is False and "edits not exercised" in reason


def test_multi_f2p_oracle():
    ok, _ = classify_oracle(
        _empty(fail_to_pass_total=2, fail_to_pass_passing=1),
        _gold(fail_to_pass_total=2, fail_to_pass_passing=2),
    )
    assert ok is True


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
