"""SWE-bench-Lite pilot driver — 4 conditions × 5 instances × 1 seed.

Mirrors `microrcs.run()`'s controller-stack composition (L0/L1/L2/L3 per
condition with shadow-eval hooks for L2) but uses SWE workspaces instead
of microRCS scratch dirs. Each (condition, instance) pair gets its own
fresh SWE workspace so state doesn't bleed across conditions.

Not a benchmark-grade run (n=1 seed, n_epochs=1, n_repeats=1). The pilot's
purpose is to surface a directional signal:

- Does any recursion condition beat `flat` on SWE-bench-Lite?
- Per-condition cost overhead at the smallest defensible N.

If a directional signal exists, scope a full bench at re-calibrated cost.
If null, the H1 thesis is empirically refuted on the canonical agent
benchmark and the next move is structural (BRO-947 life-perturb) or
theoretical (revise the paper).

Usage:
    make swe-pilot
    # or directly:
    cd microrcs && python -m scripts.swe_pilot
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
import microrcs as m  # noqa: E402

from adapters.sandbox import UvVenvBackend  # noqa: E402
from adapters.swe_bench import (  # noqa: E402
    curated_pilot5_instances,
    load_swe_bench_lite_subset,
)


CONDITIONS = ("flat", "+autonomic", "+meta", "full")


def _maybe_enable_langsmith_tracing() -> bool:
    """If `LANGSMITH_API_KEY` (or legacy `LANGCHAIN_API_KEY`) is set, wrap
    the anthropic SDK so every reason() call publishes to LangSmith.

    Returns True if tracing was enabled, False otherwise (no-op when no key).
    Lightest-touch integration — patches the SDK module, not microRCS internals.
    """
    if not (os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")):
        return False
    try:
        import anthropic  # noqa: F401  — needed before wrapping
        from langsmith.wrappers import wrap_anthropic
    except ImportError:
        print(
            "[pilot] WARN: LANGSMITH_API_KEY set but `langsmith` package "
            "not importable — skipping tracing.",
            file=sys.stderr,
        )
        return False
    # Monkey-patch the constructor so every AnthropicReasoner.client is wrapped.
    import anthropic  # noqa: E402

    original_init = anthropic.Anthropic.__init__

    def wrapped_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        original_init(self, *args, **kwargs)
        # Re-wrap self in-place — wrap_anthropic returns a wrapper around the
        # client; rebind core attrs so the existing instance becomes traced.
        traced = wrap_anthropic(self)
        # The wrapper exposes .messages, .completions, etc. Replace these.
        for attr in ("messages", "completions", "models"):
            if hasattr(traced, attr):
                object.__setattr__(self, attr, getattr(traced, attr))

    anthropic.Anthropic.__init__ = wrapped_init  # type: ignore[method-assign]
    return True


def _build_controller_stack(
    cond: str,
    l0_reasoner,
    l2_reasoner,
    l3_reasoner,
    log: m.EventLog,
    suite: list[m.Task],
    workspace_root: Path,
):
    """Construct the per-condition L1/L2/L3 controllers (or None for `flat`).

    The L0Plant is constructed per-instance (once per task) since each
    instance has its own SWE workspace. Returns (l1, l2, l3) tuple where
    elements are None if the condition doesn't include them.
    """
    l1 = (
        m.L1Autonomic(l0_reasoner, log, m.HysteresisThreshold(0.2, 0.6))
        if cond in ("+autonomic", "+meta", "full")
        else None
    )
    # L2: needs a reasoner + shadow-eval hook (matches microrcs.run() defaults).
    l2 = None
    if cond in ("+meta", "full") and l2_reasoner is not None:
        l2_hooks: list[m.Hook] = []
        # Shadow eval hook needs a "plant" reference; we'll re-bind it later
        # at task time. For now we construct L2 with empty hooks and add the
        # hook lazily after we have the first plant.
        l2 = m.L2Meta(l2_reasoner, log, mutation_budget=5, hooks=l2_hooks)
    l3 = m.L3Governance(l3_reasoner, log) if cond == "full" and l3_reasoner else None
    return l1, l2, l3


def _maybe_install_shadow_hook(
    l2: m.L2Meta | None,
    plant: m.L0Plant,
    suite: list[m.Task],
    cfg: m.RunConfig,
    workspace_root: Path,
) -> None:
    """Install the shadow-eval hook on L2 if not already installed.

    The hook needs a concrete plant reference — we wait until the first task
    materializes the plant, then install. Subsequent tasks reuse the same
    plant for the duration of one condition pass (matches microRCS run()
    semantics), so the hook stays valid.
    """
    if l2 is None:
        return
    if l2.hooks:
        return  # already installed
    l2.hooks.append(
        m.make_shadow_eval_hook(
            cfg.shadow_eval, plant, suite, workspace_root=workspace_root
        )
    )


def _run_condition(
    cond: str,
    instance_ids: list[str],
    backend: UvVenvBackend,
    pilot_run_id: str,
    cfg: m.RunConfig,
    out_dir: Path,
    pytest_timeout_s: float,
    quiet: bool = False,
) -> dict:
    """Run one condition's pass over all instances. Returns aggregated metrics."""
    log = m.EventLog(out_dir / f"{pilot_run_id}-{cond}-events.jsonl")

    # Provision SWE Tasks for THIS condition (each gets its own workspace).
    cond_run_id = f"{pilot_run_id}-{cond.lstrip('+')}"
    tasks = load_swe_bench_lite_subset(
        instance_ids,
        backend,
        cond_run_id,
        pytest_timeout_s=pytest_timeout_s,
    )

    # Construct per-condition reasoners + controllers.
    l0_reasoner = m.make_reasoner(cfg.model_l0_l1)
    l2_reasoner = (
        m.make_reasoner(cfg.model_l2_l3) if cond in ("+meta", "full") else None
    )
    l3_reasoner = (
        m.make_reasoner(cfg.model_l2_l3) if cond == "full" else None
    )
    l1, l2, l3 = _build_controller_stack(
        cond, l0_reasoner, l2_reasoner, l3_reasoner, log,
        suite=tasks, workspace_root=backend.cache_root / "workspaces",
    )

    if not quiet:
        print(f"\n[pilot] ╭─ {cond} (n={len(tasks)})", flush=True)

    cond_results: list[dict] = []
    plant_for_hook_binding: m.L0Plant | None = None
    recent_failures: list[m.FailureSummary] = []

    for task in tasks:
        agent_ws_path = Path(task.metadata["swe_agent_workspace"])
        workspace = m.Workspace(path=agent_ws_path, run_id=cond_run_id)
        plant = m.L0Plant(
            reasoner=l0_reasoner,
            workspace=workspace,
            log=log,
            caps=m.Caps(
                max_steps=cfg.max_steps_per_episode,
                max_cost_usd=cfg.max_cost_usd_per_episode,
                model=cfg.model_l0_l1,
            ),
            mode=m.AgentMode.BASE,
            system_rules=[],  # no cross-instance compounding in the pilot
            memory_invitation=False,
        )

        # Install the shadow-eval hook lazily (needs a plant reference).
        if plant_for_hook_binding is None:
            plant_for_hook_binding = plant
            _maybe_install_shadow_hook(
                l2, plant, tasks, cfg,
                workspace_root=backend.cache_root / "workspaces",
            )

        if not quiet:
            print(f"[pilot] │  {task.id} ...", flush=True)

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
            trace = None
        wall = time.monotonic() - t_task
        cond_results.append({
            "instance_id": task.id,
            "score": score,
            "n_steps": n_steps,
            "cost_usd": cost,
            "wall_s": wall,
            "aborted": aborted,
        })
        glyph = "✓" if score >= 1.0 else ("✗" if aborted else "·")
        if not quiet:
            print(
                f"[pilot] │  {task.id:<35} {glyph} "
                f"score={score:.2f} steps={n_steps:<2} "
                f"cost=${cost:<7.4f} wall={wall:.0f}s "
                + (f"abort={aborted}" if aborted else ""),
                flush=True,
            )
        if score < 1.0:
            recent_failures.append(m.FailureSummary(
                task_id=task.id, domain=task.domain,
                score=score, aborted_reason=aborted,
                n_steps=n_steps,
                submitted_answer=trace.final_answer if trace else None,
            ))
            recent_failures = recent_failures[-20:]

        # L1 observe + decide per task — matches m.run() semantics.
        if l1 is not None:
            history = list(log._events)
            obs = l1.observe(history)
            dec = l1.decide(obs)
            safe = l1.shield(dec, obs)
            m.apply_decision_downward(1, safe, plant, l1, l2, log)
            m._emit_lyapunov(  # type: ignore[attr-defined]
                log, level=1, controller=l1, state=obs,
                correlation_id=f"task_{task.id}",
            )

    # L2 fires once at end of "epoch" (we do 1 epoch in the pilot).
    if l2 is not None and plant_for_hook_binding is not None:
        l2.mutations_this_epoch = 0  # explicit reset
        state = m.MetaState.from_log(log, epoch=0, recent_failures=recent_failures)
        dec = l2.decide(state)
        safe = l2.shield(dec, state)
        safe = l2.run_hooks(safe, state)
        m.apply_decision_downward(
            2, safe, plant_for_hook_binding, l1, l2, log,
        )
        m._emit_lyapunov(  # type: ignore[attr-defined]
            log, level=2, controller=l2, state=state, correlation_id="epoch_0",
        )
        if not quiet:
            action_name = type(safe.action).__name__
            print(f"[pilot] │  L2 epoch 0 → {action_name}", flush=True)

    # L3 fires once if conditions met.
    if l3 is not None and l3._should_fire(log):
        state = m.GovernanceState.from_log(log)
        dec = l3.decide(state)
        m.apply_decision_downward(
            3, m.Decision(action=dec.action, reason=dec.reason), None, l1, l2, log,
        )
        if not quiet:
            print(f"[pilot] │  L3 fire → {type(dec.action).__name__}", flush=True)

    pass_at_1 = sum(r["score"] for r in cond_results) / max(len(cond_results), 1)
    total_cost = sum(r["cost_usd"] for r in cond_results)
    if not quiet:
        print(
            f"[pilot] ╰─ {cond} done: pass^1={pass_at_1:.2f} "
            f"cost=${total_cost:.2f} n={len(cond_results)}",
            flush=True,
        )
    return {
        "condition": cond,
        "pass_at_1": pass_at_1,
        "total_cost_usd": total_cost,
        "results": cond_results,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="swe_pilot", description=__doc__)
    p.add_argument(
        "--cache-root", type=Path,
        default=Path("~/.cache/microrcs-swe").expanduser(),
    )
    p.add_argument("--out", type=Path, default=Path("reports/swe-pilot"))
    p.add_argument(
        "--model-l0-l1", default="claude-haiku-4-5",
        help="L0/L1 reasoner model (default: Haiku, cheapest for pilot).",
    )
    p.add_argument(
        "--model-l2-l3", default="claude-sonnet-4-6",
        help="L2/L3 reasoner model (default: Sonnet, modest meta-controller).",
    )
    p.add_argument("--max-steps", type=int, default=50)
    p.add_argument("--max-cost", type=float, default=5.0)
    p.add_argument("--pytest-timeout", type=float, default=120.0)
    p.add_argument(
        "--conditions",
        default=",".join(CONDITIONS),
        help=f"Comma-separated subset of {CONDITIONS}. Default: all 4.",
    )
    p.add_argument("--instance", action="append", default=None,
                   help="Override instance IDs. Repeatable.")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY required", file=sys.stderr)
        return 2

    if _maybe_enable_langsmith_tracing():
        project = os.getenv("LANGSMITH_PROJECT", "microrcs-swe-pilot")
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", project)
        print(f"[pilot] LangSmith tracing enabled, project={project}", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    pilot_run_id = f"pilot-{int(time.time())}"
    backend = UvVenvBackend(cache_root=args.cache_root)
    instance_ids = args.instance or curated_pilot5_instances()
    conditions = tuple(c.strip() for c in args.conditions.split(",") if c.strip())
    invalid = [c for c in conditions if c not in CONDITIONS]
    if invalid:
        print(f"ERROR: unknown condition(s): {invalid}", file=sys.stderr)
        return 2

    cfg = m.RunConfig(
        suite=[],  # we provide tasks per-condition in _run_condition
        n_epochs=1,
        n_repeats=1,
        n_runs=1,
        max_steps_per_episode=args.max_steps,
        max_cost_usd_per_episode=args.max_cost,
        model_l0_l1=args.model_l0_l1,
        model_l2_l3=args.model_l2_l3,
    )

    print(f"[pilot] run_id={pilot_run_id}", flush=True)
    print(f"[pilot] instances ({len(instance_ids)}): {instance_ids}", flush=True)
    print(f"[pilot] conditions: {conditions}", flush=True)
    print(f"[pilot] L0/L1={cfg.model_l0_l1}  L2/L3={cfg.model_l2_l3}", flush=True)
    print(f"[pilot] max_steps={cfg.max_steps_per_episode}  "
          f"max_cost=${cfg.max_cost_usd_per_episode}", flush=True)

    t_total = time.monotonic()
    by_condition: list[dict] = []
    for cond in conditions:
        cond_summary = _run_condition(
            cond, instance_ids, backend, pilot_run_id, cfg,
            out_dir=args.out, pytest_timeout_s=args.pytest_timeout,
            quiet=args.quiet,
        )
        by_condition.append(cond_summary)

    summary = {
        "pilot_run_id": pilot_run_id,
        "model_l0_l1": cfg.model_l0_l1,
        "model_l2_l3": cfg.model_l2_l3,
        "instance_ids": list(instance_ids),
        "conditions": list(conditions),
        "by_condition": by_condition,
        "total_cost_usd": sum(c["total_cost_usd"] for c in by_condition),
        "total_wall_s": time.monotonic() - t_total,
    }
    summary_path = args.out / f"{pilot_run_id}-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))

    print(f"\n[pilot] === HEADLINE ===", flush=True)
    print(f"{'cond':>14}  {'pass^1':>7}  {'cost':>7}", flush=True)
    for c in by_condition:
        print(
            f"{c['condition']:>14}  "
            f"{c['pass_at_1']:>7.3f}  "
            f"${c['total_cost_usd']:>6.4f}",
            flush=True,
        )
    if len(by_condition) >= 2:
        flat_summary = next((c for c in by_condition if c["condition"] == "flat"), None)
        if flat_summary:
            flat_p1 = flat_summary["pass_at_1"]
            print(f"\nΔ vs flat (pass^1):", flush=True)
            for c in by_condition:
                if c["condition"] == "flat":
                    continue
                d = c["pass_at_1"] - flat_p1
                print(f"  {c['condition']:>14}: Δ = {d:+.3f}", flush=True)
    print(
        f"\n[pilot] total_cost=${summary['total_cost_usd']:.4f}  "
        f"wall={summary['total_wall_s']:.0f}s  "
        f"summary → {summary_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
