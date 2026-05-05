---
title: "JEPA Experiment A v2 — Per-step pipeline + data-shape limit on gemma4 REFERENCE"
date: 2026-05-05
tags: [jepa, rcs, experiment-result, data-limitation]
relates_to:
  - "[[2026-05-05-jepa-experiment-a-results]]"
  - "[[2026-05-05-jepa-as-rcs-frame]]"
  - "[[../../microrcs/THESIS_VALIDATION.md]]"
  - "[[../../microrcs/scripts/jepa_a.py]]"
---

# JEPA Experiment A v2 — Per-step pipeline + data-shape limit on gemma4 REFERENCE

**Date:** 2026-05-05
**Code:** `microrcs/scripts/jepa_a.py` (per-step subcommand)
**Outputs:** `reports/jepa-a-perstep/{results.md, lambdas.json, cohort_lambdas.json, training_history.json, jepa_a_step.pt}`
**Predecessor:** [[2026-05-05-jepa-experiment-a-results]] (v1, episode-level null)
**Design note:** [[2026-05-05-jepa-as-rcs-frame]]

## Headline

> The per-step pipeline ships, parses real `events.jsonl` streams, trains
> without collapse, and is unit-tested across 9 new test cases. Running it
> against a fresh gemma4 + REFERENCE bench reveals **the binding constraint
> for per-step Experiment A is episode length, not the JEPA framework**:
> gemma4 produces 1–2 step episodes (most: bash → submit), so the dataset
> contains 20 step pairs across 19 trajectories. Per-trajectory `λ̂_0` is
> undefined (need ≥3 positive energy values per trajectory; we have ≤1).
> Cohort λ̂ aggregated across trajectories is degenerate for `flat` (all pairs
> at step_idx=0) and produces a single point estimate `λ̂[full] = −1.37` from
> 10 pairs across only a handful of step indices — too few to be informative.

The shipped infrastructure unblocks the productive next data run (SWE-bench-Lite pilot with `--persistent-workspace`); the gemma4 + REFERENCE configuration tested here is **inappropriate as a per-step JEPA validation surface**.

## What shipped

- `scripts/jepa_a.py` — refactored into `episode-level` (v1, default) and `per-step` (v2) subcommands. Backward compatible with prior CLI invocations.
- New per-step extraction primitives:
  - `StepRecord` — one agent step reconstructed from L0 RCSEvent stream
  - `parse_workspace_events(workspace_dir)` — reads `<dir>/.rcs/events.jsonl`, groups by episode `cid`, reduces to `StepRecord` list per episode
  - `featurize_step(rec)` — 14-dim state vector (step_norm, tool one-hot, is_error, log obs/tokens/latency, cost_norm, condition one-hot)
  - `build_step_trajectories(by_cid)` — drops episodes < 2 steps; precomputes feature stack
  - `collect_step_trajectories(workspaces_root)` — namespaces cids by workspace name to prevent cross-workspace cid collision
- New training entry point: `train_step_jepa(...)` — same JEPA model architecture as v1, different in_dim
- New estimators:
  - `lambda_hat_step(model, trajectories)` — per-trajectory OLS slope (returns None for short trajectories)
  - `lambda_hat_step_cohort(model, trajectories)` — pooled-pairs slope per condition (sidesteps short-trajectory limit but introduces survival bias)
- 9 new tests in `tests/test_jepa_a.py` (synthetic events.jsonl fixture, round-trip parser, cohort degeneracy guards, CLI dispatch). **Total 246/246 passing**.

## Data collected

```
gemma4-8B + REFERENCE × 1 epoch × 3 repeats × {flat, full}
└── 30 episodes total
    ├── flat: 15 episodes — pass^3 = 0.064
    └── full: 15 episodes — pass^3 = 0.037

Wall-clock: 15.9 min on M4 Pro local ollama
Cost: $0
Persistent workspaces retained at: reports/jepa-a-perstep/raw/{flat,full}/
```

After parsing: 19 trajectories with ≥2 steps, **20 step pairs total**.

| Condition | Episodes | Trajectories ≥2 steps | Step pairs | Unique step indices in cohort |
|---|---|---|---|---|
| flat | 15 | 9 | 10 | 1 (all at step_idx=0) |
| full | 15 | 10 | 10 | ≥2 |

## Training health

| Epoch | loss | pred_loss | std_mean |
|---|---|---|---|
| 0 | 24.39 | 0.20 | 0.03 |
| 49 | 18.39 | 0.12 | 0.28 |
| 99 | 12.80 | 0.09 | 0.62 |

- Pred loss decreases monotonically (no degenerate fit)
- VICReg variance term tracks toward 1.0 but only reaches 0.62 in 100 epochs — undertrained, consistent with 20 step pairs being far below the data volume the regularizer needs
- No collapse, no NaN, monotone loss curve — pipeline is healthy; **the issue is data, not training**

## Estimator outputs

**Per-trajectory λ̂**: 0/19 finite. All trajectories have ≤1 step pair (most are 2-step bash → submit, yielding 1 energy at step_idx=0). OLS requires ≥3 positive log-energy values to fit a line.

**Cohort λ̂** (pooled across trajectories per condition):

| Condition | n_pairs | unique step_idx | λ̂ (cohort) | Verdict |
|---|---|---|---|---|
| flat | 10 | 1 | n/a | xs all at 0 → undefined |
| full | 10 | ≥2 | −1.3747 | Negative; degenerate due to tiny support |

The single `λ̂[full] = −1.37` point estimate is from a regression with too few unique x-values to be statistically informative. It is reported only as a sanity-check witness that the pipeline can produce numbers.

## Why this is meaningful (not a refutation)

The v1 episode-level null result identified two diagnostic possibilities:

1. JEPA energy is genuinely no better than `cost+steps+score` as a Lyapunov surrogate.
2. JEPA energy is better but episode-level data is too coarse to reveal it.

This v2 run was designed to disambiguate by going to per-step granularity. **It was inadvertently sabotaged by the choice of (model, suite)**: gemma4-8B on REFERENCE produces episodes too short for per-trajectory dynamics to exist at all. The framework is not refuted; the experimental surface chosen for this run was wrong.

The clean conclusion: **per-step Experiment A requires a (model × suite) combination that produces ≥5-step episodes**. Specifically:

- ❌ gemma4 + REFERENCE → 1–2 step episodes (this run)
- ❌ Sonnet/Opus + HARDER → 1–2 step episodes (per `bro945-*` reports)
- ✅ Sonnet/Haiku + SWE-bench-Lite → 35–98 step episodes (per `reports/swe-pilot-*/pilot-*-summary.json`)

## What this changes

- **Pipeline status**: shipped, validated, 18/18 own tests + 246/246 full suite.
- **Per-step JEPA frame**: still alive; not yet given a fair empirical test.
- **Productive next data run**: SWE-bench-Lite pilot with `--persistent-workspace` and `events.jsonl` retention. Estimated cost: $5–20 for a small pilot (3–4 instances × 2 conditions × Haiku). The per-step pipeline is ready to consume the data the moment it lands.
- **Episode-level v1 null result**: unchanged. v1 and v2 are complementary; v1 lacked granularity, v2 lacked episode length.

## Concrete next step

```bash
# Pilot 1 — SWE-bench-Lite × Haiku × {flat, full} × persistent workspace
python3 -m microrcs swe-pilot \
    --instances 3 \
    --conditions flat,full \
    --max-steps 100 \
    --max-cost-usd 2.0 \
    --model anthropic:claude-haiku-4-5 \
    --workspace reports/jepa-a-swe-pilot/raw/ \
    --out reports/jepa-a-swe-pilot/runs/

# Pilot 2 — feed events.jsonl into per-step JEPA
python3 -m scripts.jepa_a per-step \
    --workspaces reports/jepa-a-swe-pilot/raw/ \
    --out reports/jepa-a-swe-pilot/jepa/ \
    --epochs 200 --seed 42
```

If SWE-bench-Lite events show per-trajectory λ̂ that *correlate with episode score* (Pearson r > 0.3 negative — predictor surprise tracks failure), the JEPA frame is empirically validated and graduates to v0.4 production estimator candidate. If not, JEPA downgrades to "fifth instantiation row" in P0.

## Open follow-ups

- The `swe-pilot` CLI command was not implemented as part of this PR. Next PR scopes that, then runs Pilot 1 above.
- Add a `--save-events` flag to `cli_bench` so future capacity sweeps automatically retain `events.jsonl` (currently requires direct Python API invocation as in this run's collect script).
- Address the 1.0 → 0.62 std_mean undertraining when more data arrives by extending epochs or dropping VICReg cov term on tiny batches.

## Reproducing this run

```bash
# 1. Collect data (15.9 min, $0)
cd microrcs
python3 -c "
import sys; sys.path.insert(0, '.')
import microrcs as m
from pathlib import Path
cfg = m.RunConfig(
    suite=m.REFERENCE_SUITE, n_epochs=1, n_repeats=3, n_runs=1,
    max_steps_per_episode=15, max_cost_usd_per_episode=1e9,
    model_l0_l1='ollama:gemma4', model_l2_l3='ollama:gemma4',
    persistent_workspace=Path('../reports/jepa-a-perstep/raw'), seed=42,
)
m.run(cfg, '../reports/jepa-a-perstep/runs', conditions=('flat', 'full'))
"

# 2. Train per-step JEPA (~2 s)
python3 -m scripts.jepa_a per-step \
    --workspaces ../reports/jepa-a-perstep/raw \
    --out ../reports/jepa-a-perstep \
    --epochs 100 --seed 42
```

## Sources

- Per-step JEPA pipeline (this PR): `microrcs/scripts/jepa_a.py` (subcommand `per-step`)
- v1 episode-level null result: `docs/research-notes/2026-05-05-jepa-experiment-a-results.md`
- Design note that scoped Experiment A as per-step originally: `docs/research-notes/2026-05-05-jepa-as-rcs-frame.md` §3.
- Existing SWE-bench-Lite pilot data (no events.jsonl retained): `reports/swe-pilot-step150/pilot-1777903738-summary.json`.
