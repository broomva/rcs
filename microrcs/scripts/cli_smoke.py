"""cli_smoke — one SWE-bench-Lite instance through ClaudeCliRunner (BRO-1943).

Live smoke for the subscription-CLI plant: cold-provisions the instance
workspace (UvVenvBackend), runs `claude -p` agentically inside it with the
genesis HarnessConfig, scores via the standard SWE verifier (pytest on a
fresh sibling), and writes a verdict JSON.

Usage:
    python3 -m scripts.cli_smoke                       # flask-4992, haiku
    python3 -m scripts.cli_smoke --instance <id> --model claude-sonnet-4-6

Cost: subscription-billed (no API key crosses into the child — cli_plant
filter_env). Verifier is local pytest, $0.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

_MICROCRS_DIR = Path(__file__).resolve().parents[1]
if str(_MICROCRS_DIR) not in sys.path:
    sys.path.insert(0, str(_MICROCRS_DIR))

from adapters.cli_plant import ClaudeCliRunner, HarnessConfig  # noqa: E402
from adapters.sandbox import UvVenvBackend  # noqa: E402
from adapters.swe_bench import load_swe_bench_lite_subset  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cli_smoke", description=__doc__)
    p.add_argument("--instance", default="pallets__flask-4992")
    p.add_argument("--model", default="claude-haiku-4-5")
    p.add_argument("--max-turns", type=int, default=30)
    p.add_argument("--timeout-s", type=float, default=600.0)
    p.add_argument("--out", default="../reports/cli-smoke")
    args = p.parse_args(argv)

    run_id = f"cli-smoke-{int(time.time())}"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[cli_smoke] provisioning {args.instance} (run_id={run_id})...", flush=True)
    backend = UvVenvBackend()
    tasks = load_swe_bench_lite_subset([args.instance], backend, run_id)
    task = tasks[0]
    ws = task.metadata.get("swe_agent_workspace", "<none — setup failed>")
    print(f"[cli_smoke] workspace: {ws}", flush=True)

    config = HarnessConfig(model=args.model, max_turns=args.max_turns)
    runner = ClaudeCliRunner(timeout_s=args.timeout_s)
    print(f"[cli_smoke] running claude -p ({args.model}, max_turns={args.max_turns})...", flush=True)
    t0 = time.monotonic()
    result = runner.run_episode(task, config)
    verdict = {
        "run_id": run_id,
        "instance": args.instance,
        "config": config.to_json(),
        **dataclasses.asdict(result),
        "wall_s": round(time.monotonic() - t0, 1),
    }
    verdict_path = out_dir / f"{run_id}-verdict.json"
    verdict_path.write_text(json.dumps(verdict, indent=2))
    print(json.dumps(verdict, indent=2))
    print(f"[cli_smoke] verdict -> {verdict_path}", flush=True)
    # Smoke success = pipeline validity: episode ran, envelope parsed OR
    # classified abort, verifier produced a float. Solving is not required.
    ok = result.aborted in (None, "timeout") or result.score >= 0.0
    print(f"[cli_smoke] PIPELINE {'OK' if ok else 'FAIL'} (score={result.score})", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
