# JEPA Experiment A — Per-Step Results

**Date**: 2026-05-05
**Step trajectories** (≥2 steps): 19
**Step pairs trained on**: 20
**Final pred_loss**: 0.0928
**Final std_mean**: 0.620

## λ̂ distribution per condition

| condition | n | mean λ̂ | std | min | max |
|---|---|---|---|---|---|

## Cohort-aggregate λ̂ per condition

(Pools every (step_idx, energy) pair across trajectories per condition; one OLS fit per condition. Sidesteps short-trajectory limit of per-trajectory λ̂.)

| condition | n_pairs | λ̂ (cohort) | intercept |
|---|---|---|---|
| flat | 10 | n/a | n/a |
| full | 10 | -1.3747 | -2.7519 |

## λ̂ vs final episode score (correlation)

| condition | n | Pearson r |
|---|---|---|

## Training curve (final 5 epochs)

| epoch | loss | pred_loss | std_mean |
|---|---|---|---|
| 95 | 13.0461 | 0.0852 | 0.618 |
| 96 | 12.9834 | 0.0871 | 0.618 |
| 97 | 12.9208 | 0.0889 | 0.619 |
| 98 | 12.8583 | 0.0908 | 0.619 |
| 99 | 12.7957 | 0.0928 | 0.620 |
