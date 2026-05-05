# JEPA Experiment A — Results

**Date**: 2026-05-05
**Trajectories**: 24
**Training pairs**: 2136
**Final training loss**: 3.5668

## Variance ratio per (model_size, condition)

| model_size | condition | JEPA mean λ̂ | JEPA Var | Heur mean λ̂ | Heur Var | Var ratio J/H |
|---|---|---|---|---|---|---|
| opus | +autonomic | -0.0059 | 0.0000 | -0.0032 | 0.0000 | 1.9315 |
| opus | +meta | -0.0007 | 0.0000 | 0.0004 | 0.0000 | 1.4115 |
| opus | flat | -0.0030 | 0.0000 | -0.0027 | 0.0000 | 0.7168 |
| opus | full | 0.0016 | 0.0000 | -0.0037 | 0.0000 | 0.5233 |
| sonnet | +autonomic | -0.0117 | 0.0000 | -0.0030 | 0.0000 | 0.4874 |
| sonnet | +meta | -0.0095 | 0.0000 | -0.0029 | 0.0000 | 3.2246 |
| sonnet | flat | -0.0054 | 0.0000 | 0.0003 | 0.0000 | 21.2967 |
| sonnet | full | 0.0038 | 0.0000 | 0.0013 | 0.0000 | 6.9208 |

**JEPA wins (lower Var) in 3 / 8 cells**
**Median Var ratio (JEPA / heuristic)**: 1.6715

## Verdict

- **Heuristic V_0 = 0.3*cost + 0.3*step + 0.4*(1-score) remains the better estimator**: JEPA does not reduce Var[λ̂_0] across capacity tiers.

## Training curve (final 5 epochs)

| epoch | loss | pred_loss | std_mean |
|---|---|---|---|
| 45 | 3.6984 | 0.4263 | 1.007 |
| 46 | 3.7080 | 0.4347 | 1.007 |
| 47 | 3.5749 | 0.4295 | 1.009 |
| 48 | 3.5924 | 0.4334 | 1.009 |
| 49 | 3.5668 | 0.4068 | 1.010 |
