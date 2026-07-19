"""Unit tests for deterministic stratified splitting (BRO-1947).

Pure — no network. The disjointness invariant is load-bearing: the private
gate is vacuous if train/holdout/final overlap. Run by CI `test-microrcs`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402

from scripts.make_splits import (  # noqa: E402
    _repo_of,
    interleave_by_repo,
    stratified_split,
)


def test_repo_of():
    assert _repo_of("pallets__flask-4992") == "pallets__flask"
    assert _repo_of("sympy__sympy-13480") == "sympy__sympy"
    assert _repo_of("pytest-dev__pytest-11143") == "pytest-dev__pytest"


def test_disjoint_and_sized():
    pool = [f"sympy__sympy-{i}" for i in range(8)] + [f"pytest-dev__pytest-{i}" for i in range(4)]
    train, holdout, final = stratified_split(pool, 6, 3, 3)
    assert len(train) == 6 and len(holdout) == 3 and len(final) == 3
    s_tr, s_ho, s_fi = set(train), set(holdout), set(final)
    assert not (s_tr & s_ho)
    assert not (s_tr & s_fi)
    assert not (s_ho & s_fi)
    assert len(s_tr | s_ho | s_fi) == 12


def test_deterministic():
    pool = [f"sympy__sympy-{i}" for i in range(20)] + [f"pytest-dev__pytest-{i}" for i in range(6)]
    a = stratified_split(pool, 6, 3, 3)
    b = stratified_split(list(reversed(pool)), 6, 3, 3)
    assert a == b  # order-independent, deterministic


def test_small_pool_raises():
    with pytest.raises(ValueError):
        stratified_split([f"sympy__sympy-{i}" for i in range(5)], 6, 3, 3)


def test_interleave_spreads_repos():
    pool = ["sympy__sympy-1", "sympy__sympy-2", "sympy__sympy-3", "pytest-dev__pytest-9"]
    order = interleave_by_repo(pool)
    # Round-robin => the single pytest appears within the first 2 positions,
    # not last (repos are spread, not concatenated).
    assert order.index("pytest-dev__pytest-9") <= 1


def test_multi_repo_final_is_diverse_when_pool_allows():
    # 3 repos, plenty each => final_test (n=3) should pull one from each repo.
    pool = (
        [f"sympy__sympy-{i}" for i in range(4)]
        + [f"pytest-dev__pytest-{i}" for i in range(4)]
        + [f"sphinx-doc__sphinx-{i}" for i in range(4)]
    )
    _, _, final = stratified_split(pool, 6, 3, 3)
    repos = {_repo_of(x) for x in final}
    assert len(repos) == 3  # one from each repo


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
