"""curate_instances — $0 (no LLM) ORACLE validity gate for SWE-bench-Lite.

BRO-1948 + BRO-1947 commitment #5. Proves each candidate is a *real,
gradeable, no-Docker-installable, correctly-exercised* task by running it
through the SAME verifier the experiment uses, twice, with the swebench-spec
environment:

  1. EMPTY diff  -> FAIL_TO_PASS must FAIL at base (f2p_pass < f2p_total) and
                    PASS_TO_PASS must all pass (p2p healthy install).
  2. GOLD patch  -> applying the instance's ground-truth fix must make every
                    FAIL_TO_PASS pass (f2p_pass == f2p_total).

Passing BOTH is the oracle: it certifies the venv actually exercises SOURCE
edits (the BRO-1948 fidelity property — the editable install repoints to the
patched workspace) AND that dependencies resolve today (no rot). An instance
that only did the empty check could still be silently broken (edits invisible);
the gold check is what closes that gap.

Cost: subscription-free, API-free — wall-clock only (spec venv build cached in
~/.cache/microrcs-swe). Requires `swebench` installed for env fidelity.

Usage:
    cd microrcs && python3 -m scripts.curate_instances \
        --candidates experiments/aide2-run1/candidates.json \
        --out        experiments/aide2-run1/validated_instances.json --need 12

`classify_oracle` is pure (unit-tested mock-only, no network, in CI).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from adapters import swe_specs  # noqa: E402
from adapters.sandbox import SetupError, UvVenvBackend  # noqa: E402
from adapters.swe_bench import make_swe_task  # noqa: E402
from adapters.swe_types import SweInstance  # noqa: E402


@dataclass(frozen=True)
class Verdict:
    instance_id: str
    valid: bool
    reason: str
    repo: str = ""
    version: str = ""
    base_commit: str = ""
    empty_f2p_pass: int = 0
    empty_f2p_total: int = 0
    empty_p2p_pass: int = 0
    empty_p2p_total: int = 0
    gold_f2p_pass: int = 0
    gold_f2p_total: int = 0
    setup_s: float = 0.0
    verify_s: float = 0.0
    error: str | None = None


def classify_oracle(empty: dict | None, gold: dict | None) -> tuple[bool, str]:
    """Pure oracle classifier over two recorded SweScore dicts.

    VALID iff (empty) F2P fails at base + P2P all pass, AND (gold) F2P all pass.
    """
    if empty is None:
        return False, "empty_not_scored"
    if empty.get("error"):
        return False, f"empty_verifier_error: {str(empty['error'])[:100]}"
    ef_t = int(empty.get("fail_to_pass_total", 0))
    ef_p = int(empty.get("fail_to_pass_passing", 0))
    ep_t = int(empty.get("pass_to_pass_total", 0))
    ep_p = int(empty.get("pass_to_pass_passing", 0))
    if ef_t <= 0:
        return False, "no_fail_to_pass_tests"
    if ef_p >= ef_t:
        return False, "f2p_passes_at_base (trivial/broken instance)"
    if ep_t <= 0:
        return False, "no_pass_to_pass_sample"
    if ep_p < ep_t:
        return False, f"p2p_fails_at_base ({ep_p}/{ep_t}) — broken env"
    if gold is None:
        return False, "gold_not_scored"
    if gold.get("error"):
        return False, f"gold_verifier_error: {str(gold['error'])[:100]}"
    gf_t = int(gold.get("fail_to_pass_total", 0))
    gf_p = int(gold.get("fail_to_pass_passing", 0))
    if gf_t <= 0 or gf_p < gf_t:
        return False, f"gold_f2p_not_all_pass ({gf_p}/{gf_t}) — edits not exercised"
    return True, (
        f"ORACLE ok (empty f2p {ef_p}/{ef_t} fail, p2p {ep_p}/{ep_t} pass; "
        f"gold f2p {gf_p}/{gf_t} pass)"
    )


def _read_last_score(scores_path: Path, instance_id: str) -> dict | None:
    if not scores_path.exists():
        return None
    last = None
    for line in scores_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("instance_id") == instance_id:
            last = rec
    return last


def curate_one(
    inst: SweInstance, backend: UvVenvBackend, run_id: str, *, pytest_timeout_s: float
) -> Verdict:
    supported, why = swe_specs.venv_support(inst)
    common = dict(
        instance_id=inst.instance_id, repo=inst.repo,
        version=inst.version, base_commit=inst.base_commit,
    )
    if not supported:
        return Verdict(valid=False, reason=f"unsupported: {why}", **common)
    t0 = time.monotonic()
    try:
        task = make_swe_task(inst, backend, run_id, pytest_timeout_s=pytest_timeout_s)
    except SetupError as exc:
        return Verdict(
            valid=False, reason="install_failed", setup_s=time.monotonic() - t0,
            error=str(exc)[:300], **common,
        )
    setup_s = time.monotonic() - t0
    if task.metadata.get("swe_setup_error"):
        return Verdict(
            valid=False, reason="install_failed", setup_s=setup_s,
            error=str(task.metadata["swe_setup_error"])[:300], **common,
        )
    agent_ws = Path(task.metadata["swe_agent_workspace"])
    scores_path = agent_ws.parent / "swe_scores.jsonl"
    t1 = time.monotonic()
    # 1. EMPTY diff — agent_ws is clean at base+test_patch.
    try:
        task.verify("")
    except Exception as exc:  # noqa: BLE001
        return Verdict(
            valid=False, reason="empty_verify_raised", setup_s=setup_s,
            verify_s=time.monotonic() - t1, error=str(exc)[:300], **common,
        )
    empty = _read_last_score(scores_path, inst.instance_id)
    # 2. GOLD patch — apply the ground-truth fix to agent_ws, verify again.
    ap = subprocess.run(
        ["git", "-C", str(agent_ws), "apply", "--whitespace=nowarn", "-"],
        input=inst.patch, capture_output=True, text=True,
    )
    gold: dict | None = None
    if ap.returncode != 0:
        reason = f"gold_apply_failed: {ap.stderr.strip()[:120]}"
        valid = False
    else:
        try:
            task.verify("")
        except Exception as exc:  # noqa: BLE001
            return Verdict(
                valid=False, reason="gold_verify_raised", setup_s=setup_s,
                verify_s=time.monotonic() - t1, error=str(exc)[:300], **common,
            )
        gold = _read_last_score(scores_path, inst.instance_id)
        valid, reason = classify_oracle(empty, gold)
    verify_s = time.monotonic() - t1
    empty = empty or {}
    gold = gold or {}
    return Verdict(
        valid=valid, reason=reason, setup_s=setup_s, verify_s=verify_s,
        empty_f2p_pass=int(empty.get("fail_to_pass_passing", 0)),
        empty_f2p_total=int(empty.get("fail_to_pass_total", 0)),
        empty_p2p_pass=int(empty.get("pass_to_pass_passing", 0)),
        empty_p2p_total=int(empty.get("pass_to_pass_total", 0)),
        gold_f2p_pass=int(gold.get("fail_to_pass_passing", 0)),
        gold_f2p_total=int(gold.get("fail_to_pass_total", 0)),
        error=(empty.get("error") or gold.get("error")),
        **common,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="curate_instances", description=__doc__)
    p.add_argument("--candidates", type=Path, default=Path("experiments/aide2-run1/candidates.json"))
    p.add_argument("--out", type=Path, default=Path("experiments/aide2-run1/validated_instances.json"))
    p.add_argument("--cache-root", type=Path, default=Path("~/.cache/microrcs-swe").expanduser())
    p.add_argument("--pytest-timeout", type=float, default=300.0)
    p.add_argument("--need", type=int, default=12)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args(argv)

    if not swe_specs.HAS_SWEBENCH:
        print("ERROR: swebench not installed — `pip install swebench` (BRO-1948).", file=sys.stderr)
        return 2

    from datasets import load_dataset

    candidate_ids = json.loads(args.candidates.read_text())
    if not isinstance(candidate_ids, list) or not candidate_ids:
        print(f"ERROR: {args.candidates} must be a non-empty JSON list", file=sys.stderr)
        return 2
    if args.limit:
        candidate_ids = candidate_ids[: args.limit]

    print("[curate] loading SWE-bench_Lite (split=test)...", flush=True)
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    by_id = {row["instance_id"]: row for row in ds}

    run_id = f"curate-{int(time.time())}"
    backend = UvVenvBackend(cache_root=args.cache_root)
    verdicts: list[Verdict] = []
    n_valid = 0
    for i, iid in enumerate(candidate_ids, 1):
        if iid not in by_id:
            verdicts.append(Verdict(instance_id=iid, valid=False, reason="not_in_dataset"))
            print(f"[curate] {i:2d}/{len(candidate_ids)} {iid}: MISSING", flush=True)
            continue
        inst = SweInstance.from_hf_row(by_id[iid])
        print(f"[curate] {i:2d}/{len(candidate_ids)} {iid} ({inst.repo}@{inst.version}) ...", flush=True)
        v = curate_one(inst, backend, run_id, pytest_timeout_s=args.pytest_timeout)
        verdicts.append(v)
        n_valid += int(v.valid)
        print(
            f"[curate]     -> {'VALID  ' if v.valid else 'INVALID'} {v.reason} "
            f"(setup {v.setup_s:.0f}s, verify {v.verify_s:.0f}s) [{n_valid} valid]",
            flush=True,
        )

    valid_ids = [v.instance_id for v in verdicts if v.valid]
    report = {
        "run_id": run_id,
        "generated_by": "scripts/curate_instances.py (BRO-1948 oracle gate, $0/no-LLM)",
        "candidates_file": str(args.candidates),
        "n_candidates": len(candidate_ids),
        "n_valid": n_valid,
        "target": args.need,
        "target_met": n_valid >= args.need,
        "validity_gate": (
            "ORACLE: empty-diff f2p fails at base + p2p all pass, AND gold "
            "patch makes f2p all pass (source edits exercised via BRO-1948 "
            "editable repoint + swebench-spec env)"
        ),
        "valid_instance_ids": valid_ids,
        "verdicts": [v.__dict__ for v in verdicts],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(
        f"\n[curate] {n_valid}/{len(candidate_ids)} valid "
        f"(target {args.need}: {'MET' if report['target_met'] else 'NOT MET'})",
        flush=True,
    )
    print(f"[curate] report -> {args.out}", flush=True)
    print(f"[curate] valid: {valid_ids}", flush=True)
    return 0 if report["target_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
