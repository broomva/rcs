---
title: "JEPA Experiment A — Null result on existing capacity-sweep traces"
date: 2026-05-05
tags: [jepa, rcs, experiment-result, null-result]
relates_to:
  - "[[2026-05-05-jepa-as-rcs-frame]]"
  - "[[../../microrcs/THESIS_VALIDATION.md]]"
  - "[[../../microrcs/scripts/jepa_a.py]]"
---

# JEPA Experiment A — Null result on existing capacity-sweep traces

**Date:** 2026-05-05
**Code:** `microrcs/scripts/jepa_a.py`
**Outputs:** `reports/jepa-a/{results.md, comparison.json, training_history.json, jepa_a.pt, lambdas_*.json}`
**Predecessor design note:** [[2026-05-05-jepa-as-rcs-frame]]

## Headline

> A small MLP-JEPA trained on the existing Sonnet + Opus capacity-sweep
> per-episode traces (n=2160 episodes, 24 trajectories) does **not** produce
> a Lyapunov estimator with lower cross-seed variance than the current
> `V_0 = 0.3·cost + 0.3·steps + 0.4·(1−score)` heuristic.
>
> **Median `Var[λ̂_0]_JEPA / Var[λ̂_0]_heuristic = 1.67`** across 8 cells
> (2 capacities × 4 conditions × 3 seeds). JEPA has lower variance in 3/8
> cells, higher in 5/8. The two estimators **disagree on the sign of λ̂_0
> in 4/8 cells** — they are not measuring the same thing more or less
> reliably; they are measuring different things.

## Setup

- **Data**: `reports/bro945-{sonnet,opus}/bench-*/0019*/metrics.json` —
  the BRO-945 capacity-sweep outputs from PR #31. Per-episode summaries
  `(task, score, cost, n_steps, aborted, epoch, repeat)`.
- **Trajectories**: 2 capacities × 3 seeds × 4 conditions = 24 ordered
  per-(model, seed, condition) sequences of 90 episodes each.
- **State features (20-d)**: `cost_norm, steps_norm, score, aborted_bin`
  + 4-d condition one-hot + 10-d task one-hot + `epoch_norm, repeat_norm`.
- **Model**: encoder R²⁰ → R³² (2-layer MLP, 64 hidden, GELU); residual
  predictor R³² → R³² (3-layer MLP); EMA target encoder (momentum 0.99);
  VICReg-lite collapse prevention (variance + covariance terms; predictor
  loss replaces invariance term, faithful to JEPA training convention).
- **Training**: 50 epochs, batch 64, lr 1e-3, seed 42. ~5K trainable
  params, <2 seconds wall-clock on M4 Pro CPU.
- **Evaluation**: per-trajectory `λ̂_0 = -slope(log V̂_0(t) vs t)` via OLS
  (mirroring `microrcs.LambdaMonitor.lambda_hat`); cross-seed variance
  per (model_size, condition) cell.

## Results

| model_size | condition  | JEPA mean λ̂ | JEPA Var | Heur mean λ̂ | Heur Var | Var ratio J/H |
|---|---|---|---|---|---|---|
| opus   | flat       | −0.0030 | tiny | −0.0027 |   ε  | **0.72** ✓ |
| opus   | +autonomic | −0.0059 | tiny | −0.0032 |   ε  |   1.93     |
| opus   | +meta      | −0.0007 | tiny |  0.0004 |   ε  |   1.41     |
| opus   | full       |  0.0016 | tiny | −0.0037 |   ε  | **0.52** ✓ |
| sonnet | flat       | −0.0054 | tiny |  0.0003 |   ε  |  21.30     |
| sonnet | +autonomic | −0.0117 | tiny | −0.0030 |   ε  | **0.49** ✓ |
| sonnet | +meta      | −0.0095 | tiny | −0.0029 |   ε  |   3.22     |
| sonnet | full       |  0.0038 | tiny |  0.0013 |   ε  |   6.92     |

(✓ = JEPA wins. Variances are all O(10⁻⁵); ratios are reliable, magnitudes are not.)

**Aggregate**: JEPA wins 3/8, heuristic wins 5/8, median ratio 1.67 (heuristic favored).

**Training health**:
- Final pred_loss = 0.41 (no degenerate fit; not zero)
- Final std_mean = 1.01 (VICReg variance term hits its target → no collapse)
- Loss decreased monotonically from 23.1 → 3.6 over 50 epochs

## Why this is a meaningful result

The design note ([[2026-05-05-jepa-as-rcs-frame]] §2.5) framed H1-JEPA as

> "Adding L_{k+1} above L_k yields a lower marginal `E_k` integral than
> a same-capacity flat baseline, controlling for total compute."

Experiment A's null is **specifically a null on the capacity-sweep dataset**.
That dataset has a known structural artifact: pass-rate near ceiling on
Opus (PR #31 finding), which compresses both heuristic and JEPA λ̂ values
into the same near-zero band. With small absolute λ̂ values, ratios become
dominated by sampling noise — the 21× outlier on `sonnet flat` is one
seed-cell pair pinching toward zero in the heuristic, not a JEPA-specific
failure.

The interpretive caveats:

1. **n=3 seeds per cell is below statistical power** for second-order
   statistics like Var[λ̂]. PR #41's gemma4 multi-seed bench (n=3) reached
   the same conclusion for first-order λ̂.
2. **Ceiling effects compress both estimators** symmetrically, so we
   can't distinguish "JEPA is no better" from "JEPA can't be better
   here because there's no signal to recover."
3. **Sign disagreement (4/8 cells)** is the substantive finding — it
   means JEPA energy and the cost+steps+score heuristic are measuring
   *different* dynamic properties of the trajectory, not noisier vs less
   noisy versions of the same property. Which is right is undetermined
   on this data.

## What this changes about the JEPA frame

- **Experiment A status**: shipped, null. Does not refute the design-note
  thesis. Does refute the "use existing capacity-sweep data and JEPA
  graduates to production immediately" path.
- **Experiment B (two-level H-JEPA)** from [[2026-05-05-jepa-as-rcs-frame]]
  §3 is unchanged in priority. The prediction "L1 conditioning reduces
  L0 Var[λ̂_0]" is what really tests the recursion-helps claim. Experiment A
  was the cheap *infrastructure* test (does the JEPA pipeline work at all);
  Experiment B is the *thesis* test.
- **A productive next data run** is the one Experiment A could not use:
  per-step trajectories with full event streams. PR #43 Tier-1 work item C
  shipped the stigmergy substrate; the remaining Tier-1 work is to capture
  per-step state in a small fresh bench (gemma4, free) so a step-level
  MLP-JEPA can be trained on >100K (z_t, z_{t+1}) pairs instead of 2,136.
  At step level, ceiling effects on any *single episode* don't matter —
  the dynamics within an episode are richer than the score boolean.

## Concrete next steps

1. **Run a small fresh bench with `--persistent-workspace`** to retain
   `events.jsonl` per workspace, so step-level features are available.
   Cost: $0 (gemma4) or ~$1 (Haiku), 30 min wall clock.
2. **Add a `--per-step` mode to `microrcs/scripts/jepa_a.py`** that loads
   events.jsonl, builds per-step `(z_t, z_{t+1})` pairs, and trains the
   same JEPA architecture on the higher-resolution data.
3. **Re-run Experiment A on per-step data**. If `Var[λ̂_0]_JEPA <
   Var[λ̂_0]_heuristic` reverses sign at step level, the JEPA frame
   stays alive. If not, downgrade JEPA from "alternative substrate" to
   "fifth instantiation row" in P0.
4. **Scope Experiment B (two-level H-JEPA)** as a follow-up only after
   per-step Experiment A signals are positive.

## Reproducing this run

```bash
cd microrcs
python3 -m scripts.jepa_a --reports ../reports --out ../reports/jepa-a \
    --epochs 50 --seed 42
# wall-clock: ~2 s on Apple M4 Pro CPU
# outputs: ../reports/jepa-a/{results.md, comparison.json, jepa_a.pt, ...}
```

Bit-identical reruns require fixing Python + PyTorch + NumPy seeds; the
script does this via `--seed`, but parallel matrix ops on MPS may
introduce nondeterminism. CPU is the determinism target.

## Sources

- Predecessor design note: `2026-05-05-jepa-as-rcs-frame.md`
- Heuristic formula: `microrcs/microrcs.py::_compute_v0` (also mirrored
  at `_compute_v_heuristic` in `scripts/jepa_a.py` for consistency).
- Lambda-fit convention: `microrcs/microrcs.py::LambdaMonitor.lambda_hat`
  (OLS slope of `-log V`).
- Capacity-sweep data: PR #31 BRO-945 (microRCS multi-tier bench).
- Null-result tradition in this project: PR #41 gemma4 multi-seed.
