"""Smoke-test driver for the SWE-bench-Lite adapter.

Runs `flat`-only on Haiku against the 2 curated pilot instances. Validates the
adapter pipeline end-to-end: HF dataset load → repo clone → venv build →
agent loop → patch verification → score recording.

Not a benchmark. The goal is "the pipeline produces a verdict for both
instances, the verdict file is well-formed, total cost is bounded." Whether
the verdict is 1.0 or 0.0 doesn't gate the smoke as long as the pipeline
itself doesn't break.

Usage:
    make swe-smoke
    # or directly:
    python -m microrcs.scripts.swe_smoke
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import time
from pathlib import Path

# Make sibling `microrcs.py` importable.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import microrcs as m  # noqa: E402

from adapters.sandbox import UvVenvBackend  # noqa: E402
from adapters.swe_bench import (  # noqa: E402
    curated_pilot_instances,
    load_swe_bench_lite_subset,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="swe_smoke", description=__doc__)
    p.add_argument(
        "--cache-root",
        type=Path,
        default=Path("~/.cache/microrcs-swe").expanduser(),
        help="Where to cache repo clones, venvs, and per-episode workspaces.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("reports/swe-smoke"),
        help="Where to write run artifacts (logs, scores).",
    )
    p.add_argument(
        "--model",
        default="claude-haiku-4-5",
        help="Reasoner model. Default Haiku (cheapest for smoke).",
    )
    p.add_argument(
        "--max-steps", type=int, default=50,
        help="Per-episode step ceiling (matches BRO-946 caps adjustment).",
    )
    p.add_argument(
        "--max-cost", type=float, default=5.0,
        help="Per-episode USD ceiling.",
    )
    p.add_argument(
        "--pytest-timeout", type=float, default=120.0,
        help="Per-pytest-invocation timeout seconds.",
    )
    p.add_argument(
        "--instance", action="append", default=None,
        help="Override curated instance IDs. Repeatable.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Provision workspaces and verify scoring path without calling LLM.",
    )
    args = p.parse_args(argv)

    if "ANTHROPIC_API_KEY" not in os.environ and not args.dry_run:
        print(
            "ERROR: ANTHROPIC_API_KEY is not set and --dry-run wasn't passed.\n"
            "       Set the env var or pass --dry-run to test the pipeline "
            "without LLM calls.",
            file=sys.stderr,
        )
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    run_id = f"smoke-{int(time.time())}"
    log_path = args.out / f"{run_id}.log"

    backend = UvVenvBackend(cache_root=args.cache_root)
    instance_ids = args.instance or curated_pilot_instances()

    print(f"[smoke] run_id={run_id}", flush=True)
    print(f"[smoke] cache_root={backend.cache_root}", flush=True)
    print(f"[smoke] instances: {instance_ids}", flush=True)
    print(f"[smoke] model={args.model}", flush=True)

    print("[smoke] loading HF dataset + provisioning workspaces...", flush=True)
    t_setup = time.monotonic()
    tasks = load_swe_bench_lite_subset(
        instance_ids,
        backend,
        run_id,
        pytest_timeout_s=args.pytest_timeout,
    )
    print(
        f"[smoke] provisioned {len(tasks)} task(s) in "
        f"{time.monotonic() - t_setup:.1f}s",
        flush=True,
    )

    if args.dry_run:
        print("[smoke] --dry-run: skipping agent loop")
        all_provisioned = True
        for task in tasks:
            print(f"[smoke] task={task.id} domain={task.domain}")
            ws = task.metadata.get("swe_agent_workspace")
            err = task.metadata.get("swe_setup_error")
            if ws:
                print(f"        agent_ws={ws}")
            if err:
                print(f"        SETUP_ERROR: {err}")
                all_provisioned = False
        return 0 if all_provisioned else 3

    # Build the L0 reasoner + plant per-task. We don't use `m.run()` because
    # that creates its own microRCS workspace; we want the agent to operate
    # INSIDE the SWE workspace we provisioned.
    reasoner = m.make_reasoner(args.model)
    caps = m.Caps(
        max_steps=args.max_steps,
        max_cost_usd=args.max_cost,
        per_command_timeout_seconds=args.pytest_timeout,
        max_tokens_per_call=4096,
        model=args.model,
    )

    results: list[dict] = []
    log = m.EventLog(args.out / f"{run_id}-events.jsonl")
    total_cost = 0.0
    t_total = time.monotonic()

    for task in tasks:
        agent_ws_path = Path(task.metadata["swe_agent_workspace"])
        workspace = m.Workspace(path=agent_ws_path, run_id=run_id)
        plant = m.L0Plant(
            reasoner=reasoner,
            workspace=workspace,
            log=log,
            caps=caps,
            mode=m.AgentMode.BASE,
            system_rules=[],  # explicit: no rules at L0 in smoke
            memory_invitation=False,
        )
        print(f"\n[smoke] -- {task.id} -- starting", flush=True)
        t_task = time.monotonic()
        try:
            trace = plant.run_episode(task)
            score = trace.score
            n_steps = trace.n_steps
            cost = trace.cost_usd
            aborted = trace.aborted_reason
        except Exception as exc:  # noqa: BLE001
            score = 0.0
            n_steps = 0
            cost = 0.0
            aborted = f"exception: {exc!r}"
        wall = time.monotonic() - t_task
        total_cost += cost
        result = {
            "instance_id": task.id,
            "score": score,
            "n_steps": n_steps,
            "cost_usd": cost,
            "wall_s": wall,
            "aborted": aborted,
            "agent_workspace": str(agent_ws_path),
        }
        results.append(result)
        print(
            f"[smoke] -- {task.id} -- score={score:.2f} "
            f"steps={n_steps} cost=${cost:.4f} wall={wall:.1f}s "
            f"aborted={aborted!r}",
            flush=True,
        )

    summary = {
        "run_id": run_id,
        "model": args.model,
        "instance_ids": instance_ids,
        "results": results,
        "total_cost_usd": total_cost,
        "total_wall_s": time.monotonic() - t_total,
        "pass_at_1": sum(r["score"] for r in results) / max(len(results), 1),
    }
    summary_path = args.out / f"{run_id}-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\n[smoke] summary → {summary_path}", flush=True)
    print(
        f"[smoke] pass^1={summary['pass_at_1']:.2f}  "
        f"total_cost=${total_cost:.4f}  "
        f"wall={summary['total_wall_s']:.1f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
