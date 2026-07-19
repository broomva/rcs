"""make_splits — deterministic stratified train/holdout/final_test splits.

BRO-1947 pre-registration step 1 (commitment #5). Consumes the curated
`validated_instances.json` (only instances proven install+gradeable+fail-at-base
TODAY) and deterministically partitions them into DISJOINT train / holdout /
final_test splits, spreading repos so the small holdout/final splits are as
repo-diverse as the surviving pool allows.

Determinism: no RNG. Repos sorted alphabetically; instances sorted within repo;
round-robin interleave; slice. Re-running on the same validated_instances.json
yields byte-identical splits — the pre-registration must be reproducible.

The private-gate integrity (disjointness) is enforced here AND re-checked by
GenerationLoop.__init__ at run time (belt + braces).

Usage:
    cd microrcs && python3 -m scripts.make_splits \
        --validated experiments/aide2-run1/validated_instances.json \
        --out       experiments/aide2-run1/splits.json \
        --train 6 --holdout 3 --final 3
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_of(instance_id: str) -> str:
    # "pallets__flask-4992" -> "pallets__flask"
    return instance_id.rsplit("-", 1)[0]


def interleave_by_repo(instance_ids: list[str]) -> list[str]:
    """Round-robin across repos (sorted) so consecutive picks vary the repo.

    Deterministic: repos alphabetical, ids sorted within repo.
    """
    by_repo: dict[str, list[str]] = {}
    for iid in sorted(instance_ids):
        by_repo.setdefault(_repo_of(iid), []).append(iid)
    for repo in by_repo:
        by_repo[repo].sort()
    repos = sorted(by_repo)
    out: list[str] = []
    i = 0
    while len(out) < len(instance_ids):
        repo = repos[i % len(repos)]
        if by_repo[repo]:
            out.append(by_repo[repo].pop(0))
        i += 1
    return out


def stratified_split(
    instance_ids: list[str], n_train: int, n_holdout: int, n_final: int
) -> tuple[list[str], list[str], list[str]]:
    """Partition into disjoint splits, spreading repos into the small splits.

    final_test and holdout are drawn FIRST from the repo-interleaved order so
    they are as repo-diverse as the pool permits; train takes the remainder.
    Raises ValueError if the pool is too small.
    """
    need = n_train + n_holdout + n_final
    uniq = sorted(set(instance_ids))
    if len(uniq) < need:
        raise ValueError(
            f"validated pool has {len(uniq)} instances but splits need {need} "
            f"({n_train} train + {n_holdout} holdout + {n_final} final)"
        )
    ordered = interleave_by_repo(uniq)
    final = sorted(ordered[:n_final])
    holdout = sorted(ordered[n_final : n_final + n_holdout])
    train = sorted(ordered[n_final + n_holdout : n_final + n_holdout + n_train])
    # Disjointness invariant (private gate rests on it).
    assert not (set(train) & set(holdout)), "train/holdout overlap"
    assert not (set(final) & (set(train) | set(holdout))), "final overlap"
    return train, holdout, final


def _repo_hist(ids: list[str]) -> dict[str, int]:
    h: dict[str, int] = {}
    for iid in ids:
        h[_repo_of(iid)] = h.get(_repo_of(iid), 0) + 1
    return h


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="make_splits", description=__doc__)
    p.add_argument("--validated", type=Path, default=Path("experiments/aide2-run1/validated_instances.json"))
    p.add_argument("--out", type=Path, default=Path("experiments/aide2-run1/splits.json"))
    p.add_argument("--train", type=int, default=6)
    p.add_argument("--holdout", type=int, default=3)
    p.add_argument("--final", type=int, default=3)
    args = p.parse_args(argv)

    report = json.loads(args.validated.read_text())
    valid_ids = report.get("valid_instance_ids", [])
    if not valid_ids:
        print(f"ERROR: no valid_instance_ids in {args.validated}", file=sys.stderr)
        return 2
    try:
        train, holdout, final = stratified_split(valid_ids, args.train, args.holdout, args.final)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    splits = {
        "experiment": "aide2-run1",
        "ticket": "BRO-1947",
        "source": str(args.validated),
        "n_validated_pool": len(valid_ids),
        "sizes": {"train": len(train), "holdout": len(holdout), "final_test": len(final)},
        "repo_histogram": {
            "train": _repo_hist(train),
            "holdout": _repo_hist(holdout),
            "final_test": _repo_hist(final),
        },
        "train": train,
        "holdout": holdout,
        "final_test": final,
    }
    args.out.write_text(json.dumps(splits, indent=2))
    print(f"[splits] train={train}")
    print(f"[splits] holdout={holdout}")
    print(f"[splits] final_test={final}")
    print(f"[splits] repo spread: {splits['repo_histogram']}")
    print(f"[splits] -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
