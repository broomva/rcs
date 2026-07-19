"""aide2_run — paced AIDE²-shape harness-evolution run driver (BRO-1947).

Loads the PRE-REGISTERED splits (train / holdout / final_test), wires the
subscription-CLI plant (`ClaudeCliRunner`) + frontier proposer
(`make_cli_proposer`) into a `GenerationLoop`, and runs a BOUNDED batch of
generations, checkpointing after each so the run is RESTARTABLE across
subscription rate windows (the P12-persist substrate — the handoff notes the
session wall was hit twice during the build).

Pre-registration is enforced upstream: this driver refuses to run unless a
`validated_instances.json` (commitment #5) and the splits file exist, and
`GenerationLoop.__init__` rejects any train/holdout/final overlap. The proposer
never sees holdout/final scores (guarded in GenerationLoop).

Billing: inner + proposer both bill subscription OAuth via cli_plant.filter_env
(ANTHROPIC_API_KEY is stripped; confirm with a bogus-key smoke before a run).
Scoring is local pytest ($0). Spending is opt-in: WITHOUT `--run` the driver
defaults to the $0 wiring check — a bare invocation never bills.

Usage:
    # $0 wiring check (no LLM) — the default when --run is absent:
    python3 -m scripts.aide2_run --check-only        # (or bare: safety-defaults here too)

    # one paced batch of generations (subscription-billed), then checkpoint + yield:
    python3 -m scripts.aide2_run --run --batch 2

    # resume: re-run `--run` — picks up from run_state.json automatically; when
    # n_steps reaches max_generations it writes final_report.json ONCE (idempotent:
    # a completed run's final_report is not re-scored / re-billed).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from adapters.cli_plant import (  # noqa: E402
    ClaudeCliRunner,
    GenerationLoop,
    HarnessConfig,
    make_cli_proposer,
)
from adapters.sandbox import UvVenvBackend  # noqa: E402
from adapters.swe_bench import load_swe_bench_lite_subset  # noqa: E402


# === checkpoint state (pure — unit-tested mock-only) =====================
def loop_state_dict(loop) -> dict:
    """Serialize the resumable state of a GenerationLoop.

    best_holdout is the load-bearing field: restoring it prevents the resumed
    run from re-scoring the genesis holdout (wasted subscription episodes) AND
    keeps the private gate's incumbent bar consistent across restarts.
    """
    return {
        "n_steps": loop.n_steps,
        "best_config": loop.best.to_json(),
        "best_holdout": loop.best_holdout,
        "history": loop.history,
    }


def apply_state_dict(loop, state: dict) -> None:
    """Restore a GenerationLoop's resumable state from a checkpoint dict."""
    loop.n_steps = int(state["n_steps"])
    loop.best = HarnessConfig.from_json(state["best_config"])
    loop.best_holdout = state["best_holdout"]
    loop.history = list(state.get("history", []))


def _write_atomic(path: Path, text: str) -> None:
    """Atomic write (temp + rename) — a resume must never read a half-written
    checkpoint if the process is killed at the rate wall mid-write."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


# === run wiring ==========================================================
def _load_split_ids(splits_path: Path) -> tuple[list[str], list[str], list[str]]:
    obj = json.loads(splits_path.read_text())
    for key in ("train", "holdout", "final_test"):
        if not obj.get(key):
            raise ValueError(f"splits file {splits_path} missing/empty '{key}'")
    return obj["train"], obj["holdout"], obj["final_test"]


def build_loop(
    splits_path: Path,
    out_dir: Path,
    *,
    cache_root: Path,
    inner_model: str,
    proposer_model: str,
    max_generations: int,
    timeout_s: float,
    proposer_timeout_s: float,
) -> GenerationLoop:
    train_ids, hold_ids, final_ids = _load_split_ids(splits_path)
    run_id = f"aide2-run1-{int(time.time())}"
    backend = UvVenvBackend(cache_root=cache_root)
    # Provision task workspaces (clone+venv cached from curation; $0).
    train = load_swe_bench_lite_subset(train_ids, backend, run_id + "-train")
    holdout = load_swe_bench_lite_subset(hold_ids, backend, run_id + "-hold")
    final = load_swe_bench_lite_subset(final_ids, backend, run_id + "-final")
    runner = ClaudeCliRunner(timeout_s=timeout_s)
    proposer = make_cli_proposer(model=proposer_model, timeout_s=proposer_timeout_s)
    genesis = HarnessConfig(model=inner_model)  # primary arm inner model
    # GenerationLoop enforces disjoint train/holdout/final at construction.
    return GenerationLoop(
        runner, train, holdout, proposer, out_dir,
        genesis=genesis, final_test_tasks=final, max_generations=max_generations,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aide2_run", description=__doc__)
    p.add_argument("--splits", type=Path, default=Path("experiments/aide2-run1/splits.json"))
    p.add_argument("--out", type=Path, default=Path("experiments/aide2-run1"))
    p.add_argument("--validated", type=Path, default=Path("experiments/aide2-run1/validated_instances.json"))
    p.add_argument("--cache-root", type=Path, default=Path("~/.cache/microrcs-swe").expanduser())
    p.add_argument("--inner-model", default="claude-sonnet-4-6")
    p.add_argument("--proposer-model", default="claude-opus-4-7")
    p.add_argument("--max-generations", type=int, default=5)
    p.add_argument("--batch", type=int, default=1, help="Generations to run this invocation, then checkpoint + exit.")
    p.add_argument("--timeout-s", type=float, default=900.0, help="Per inner episode.")
    p.add_argument("--proposer-timeout-s", type=float, default=120.0)
    p.add_argument("--check-only", action="store_true", help="$0: build loop + provision workspaces, then exit (no LLM).")
    p.add_argument("--run", action="store_true", help="Opt in to the subscription-billed run. Without it (or with --check-only) the driver only does the $0 wiring check — a bare invocation never bills.")
    args = p.parse_args(argv)

    # Pre-registration integrity: the curated/validated list must exist BEFORE
    # any LLM call (commitment #5). The splits must be frozen in the repo.
    if not args.validated.exists():
        print(f"ERROR: {args.validated} missing — run curate_instances first (commitment #5).", file=sys.stderr)
        return 2
    if not args.splits.exists():
        print(f"ERROR: {args.splits} missing — freeze the pre-registered splits first.", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    loop = build_loop(
        args.splits, args.out, cache_root=args.cache_root,
        inner_model=args.inner_model, proposer_model=args.proposer_model,
        max_generations=args.max_generations, timeout_s=args.timeout_s,
        proposer_timeout_s=args.proposer_timeout_s,
    )
    print(
        f"[aide2] loop built: train={len(loop.train_tasks)} "
        f"holdout={len(loop.holdout_tasks)} final={len(loop.final_test_tasks)} "
        f"max_gen={loop.max_generations} inner={args.inner_model} "
        f"proposer={args.proposer_model}",
        flush=True,
    )
    # Spend is opt-in: --check-only OR the absence of --run both stop here at
    # $0 (a bare `aide2_run` must never silently bill the subscription).
    if args.check_only or not args.run:
        why = "--check-only" if args.check_only else "no --run flag (safety default)"
        print(f"[aide2] {why}: wiring OK (disjoint splits enforced, workspaces provisioned). No LLM called. Pass --run to spend.", flush=True)
        return 0

    # Resume from checkpoint if present.
    state_path = args.out / "run_state.json"
    if state_path.exists():
        apply_state_dict(loop, json.loads(state_path.read_text()))
        print(f"[aide2] resumed: n_steps={loop.n_steps} best_holdout={loop.best_holdout} best={loop.best.config_id}", flush=True)

    ran = 0
    max_gen = args.max_generations  # always an int (argparse default 5)
    while loop.n_steps < max_gen and ran < args.batch:
        t0 = time.monotonic()
        rec = loop.step()
        _write_atomic(state_path, json.dumps(loop_state_dict(loop), indent=2))
        ran += 1
        print(
            f"[aide2] gen {loop.n_steps}/{max_gen}: "
            f"train={rec.train_score:.3f} holdout={rec.holdout_score:.3f} "
            f"accepted={rec.accepted} ({rec.reason}) [{time.monotonic() - t0:.0f}s]",
            flush=True,
        )

    if loop.n_steps >= max_gen:
        # Idempotency guard (commitment #2/#6 "scored once"): pacing is
        # "re-run to resume", so a re-invocation after completion must NOT
        # re-score / re-bill the final_test split. If final_report.json already
        # exists, load and report it instead of recomputing.
        report_path = args.out / "final_report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text())
            print("[aide2] final_report.json already present — run complete; not re-scoring (idempotent, no re-bill).", flush=True)
        else:
            report = loop.final_report()
        print(f"[aide2] DONE — final_report: {json.dumps(report, indent=2)}", flush=True)
        print("[aide2] next: fill the THESIS_VALIDATION.md ledger row (commitment #6).", flush=True)
    else:
        print(
            f"[aide2] batch done ({ran} gen this run, {loop.n_steps}/{loop.max_generations} total). "
            f"Yield to the rate window; re-run to resume.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
