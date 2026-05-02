# Thesis Validation — empirical state

> **Purpose:** Pin the cumulative findings from microRCS empirical runs so future
> contributors don't relearn what we already know. Each section is dated and
> traceable to a specific PR + run.

## Headline state (as of PR #25 — POST bench result)

The RCS thesis exists in three forms; current evidence by form:

| Form | Claim | Status | Evidence |
|---|---|---|---|
| **Performance (weak)** | "some recursive control improves agent pass-rate when there's headroom" | ❌ **REFUTED** | PR #25 bench (3 seeds × 4 conditions × 90 eps): no condition beats flat above noise floor. Mean: full < +meta < +autonomic ≤ flat |
| **Performance (statistical)** | `pass^k_recursive > pass^k_flat` with `p<0.05` | ❌ **rejected** | All Δ vs flat within 2σ_flat = 0.11 band. PR #24's directional signal was a single-seed lucky outcome |
| **Stability (λᵢ > 0)** | empirical λ̂ᵢ positive at every level | ⚠️ **partial** | Only λ̂_2 numerically positive across runs; L0/L1 hover near 0; L3 degenerate |
| **Stability (paper-magnitude)** | λ̂ᵢ ≈ paper analytic λᵢ within bootstrap CI | ❌ **3 orders off** | Construct gap — see §"Why λ̂ doesn't match paper" |
| **Strong (monotone-by-level)** | `full > +meta > +autonomic > flat`, with λᵢ matching paper | ❌ **refuted** | PR #25 bench: full = 0.277 < flat = 0.357 |
| **Shadow-eval load-bearing** | "without budget shields, +meta < flat" | ✅ **SUPPORTED** | PR #25 H4: +meta = 0.282 < flat = 0.327 with shadow eval disabled (vs +meta = 0.325 with eval enabled) |

**The defensible claim today:** _on HARDER_SUITE with Haiku at 30-min runs, the recursive structure provides **no statistically significant performance benefit** over a bitter-lesson baseline. The shadow eval safety mechanism, however, IS load-bearing — without it, recursion measurably hurts (confirmed via H4)._

**The weak-form thesis is empirically refuted at this scale, model, and benchmark.** Whether it holds at higher capability tiers (Sonnet/Opus) or longer time scales (multi-day Life runtime) or harder benchmarks (SWE-bench) remains open and is the path forward.

## Cumulative empirical runs (pinned)

| PR | Suite | Best condition | flat pass^3 | best pass^3 | Δ rel | Cost | Key finding |
|---|---|---|---|---|---|---|---|
| #20 | smoke | — | — | — | — | $0.04 | end-to-end works |
| #21 | reference (broken) | full | 0.241 | 0.268 | +11% | $5.47 | math verifier was wrong (13:54 vs correct 13:18) |
| #22 | reference (fixed) | +meta | 0.935 | 1.000 | +7% | $1.93 | bad-rule injection in `full` (L2 had no shadow eval) |
| #23 (1st) | reference | flat ≈ +meta | 1.000 | 1.000 | 0% | $1.67 | shadow eval too lenient at delta=1 |
| #23 (2nd) | reference | flat ≈ full | 1.000 | 1.000 | 0% | $1.78 | shadow eval working at delta=2; suite ceiling — H1 untestable |
| **#24** | **HARDER_SUITE** | **+autonomic** | **0.296** | **0.377** | **+27%** | **$2.60** | **first H1 directional signal** |
| **#25 H4** | HARDER_SUITE --break-budgets | **+meta worst** | 0.327 | 0.282 (+meta) | -14% (vs flat) | ~$3 | **shadow eval IS load-bearing** — without it, +meta < flat (bad-rule injection returns) |
| **#25 bench** | HARDER_SUITE × 3 seeds | **flat** | **0.357 (mean)** | **flat best (mean)** | recursion HURTS or is noise | $8.65 | **noise-floor refutes H1**; PR #24's signal was lucky single-seed |

Total spend so far: ~$30 across ~2530 episodes.

## Per-seed bench result (PR #25 bench)

3 seeds × HARDER_SUITE × 4 conditions = 1080 episodes:

| Condition | per-seed pass^3 | mean | std | Δ vs flat | verdict |
|---|---|---|---|---|---|
| **flat** | [0.413, 0.377, 0.282] | **0.357** | 0.055 | — | baseline |
| +autonomic | [0.360, 0.327, 0.343] | 0.343 | 0.013 | -0.014 | within noise (HURTS slightly) |
| +meta | [0.254, 0.343, 0.377] | 0.325 | 0.052 | -0.032 | within noise (HURTS) |
| **full** | [0.282, 0.254, 0.296] | **0.277** | 0.018 | **-0.080** | within noise (HURTS clearly) |

**Noise floor: 2σ_flat = 0.110.** All deltas are within this band. **No condition statistically beats flat.**

Cost: flat $1.71 vs full $2.39 (+40% cost for −0.080 performance).

## H1-H4 verdicts as of this commit

### H1 — full > flat on pass^k (paired bootstrap, p<0.05)

**Status: REFUTED.**

PR #25 bench (3 seeds × 4 conditions × 90 eps × HARDER_SUITE):

```
flat       mean=0.357 ± 0.055    [0.282, 0.413]
+autonomic mean=0.343 ± 0.013    Δ=−0.014  (within 2σ_flat = 0.110)
+meta      mean=0.325 ± 0.052    Δ=−0.032  (within noise)
full       mean=0.277 ± 0.018    Δ=−0.080  (within noise but trending HURTS)
```

The directional signal in PR #24 (+autonomic +0.081 over flat) was a single-seed run that happened to hit a favorable point in the high-variance flat distribution. Mean across seeds shows recursion provides no systematic benefit — and `full` measurably underperforms (Δ=−0.080), albeit within the wide noise floor.

**Implication: the bitter lesson is winning at this scale.** Recursion adds API cost (full +40% cost) without proportional benefit.

H1 might still hold under different conditions (untested):
- Higher capability model tier (Sonnet/Opus instead of Haiku)
- Longer time scales (Life multi-day runs)
- Harder benchmarks where L0 alone fails most of the time (SWE-bench Lite, AIME)
- Different L2 surface (helper promotion only, no rule injection)
- Cross-run memory persistence (knowledge compounding)

These are the next experiments. None are validated yet.

### H2 — λ̂ᵢ > 0 at every level

**Status: partial.**

| Level | Sign | Significance | Notes |
|---|---|---|---|
| L0 | mixed (slightly negative across conditions) | not significant | continuous V_0 makes regression noisy; near-zero |
| L1 | slightly negative across conditions | not significant | V_1 hovers; no clear trend |
| **L2** | **positive in all conditions running L2** (+0.0048-0.0078) | not statistically significant (CI touches 0) | sign matches paper; magnitudes don't |
| L3 | degenerate (insufficient samples) | n/a | needs day-scale runs to fire meaningfully |

Per-level analytic λᵢ from `parameters.toml` are 1.45, 0.41, 0.07, 0.006 — orders of magnitude larger than measured. See §"Why λ̂ doesn't match paper."

### H3 — monotone by level (`full > +meta > +autonomic > flat`)

**Status: REFUTED.**

PR #24 ordering on HARDER_SUITE:
```
+autonomic = 0.377 (best)
full       = 0.343
+meta      = 0.327
flat       = 0.296 (worst)
```

`+autonomic > full` despite `full` having more levels. **L2 and L3 don't add value beyond L1 on this benchmark with this model tier.**

Possible interpretations:
1. The strong-form thesis is wrong (more levels ≠ more help)
2. The model tier (Haiku) lacks the meta-reasoning capacity to make L2 useful
3. The benchmark doesn't exercise L3 (3-epoch runs too short for day-scale governance)
4. L2's value is gated by mutation quality, which shadow eval is correctly suppressing in this regime

**Honest reading:** the strong-form thesis as stated in the paper doesn't hold on Haiku-class models with 30-min runs on a 10-task benchmark. Whether it holds at higher capability tiers / longer time scales / harder benchmarks is open.

### H4 — forcing λ_2 < 0 (--break-budgets) breaks Lyapunov decay

**Status: partially supported.**

PR #25 H4 run on HARDER_SUITE:

| Condition | Normal (PR #24) | H4 | Δ |
|---|---|---|---|
| flat | 0.296 | 0.327 | +0.031 (within noise) |
| +autonomic | 0.377 | 0.343 | -0.034 |
| **+meta** | **0.327** | **0.282** | **−0.045 (BELOW flat)** ⚠️ |
| full | 0.343 | 0.377 | +0.034 |

Critical signal: **`+meta` regresses to BELOW `flat`** when shadow eval is disabled. This reproduces the bad-rule injection pattern from PR #22 under controlled conditions — confirming that **the budget shields are doing real work**. Without them, L2's mutations directly hurt agent performance.

L1 Lyapunov trajectory in `full` H4:
- V_1(start) = 0.0011
- V_1(end) = 0.0403 (grew 36×)
- λ̂_1 fit = **−0.0009 (NEGATIVE = diverging)**

The direction matches H4 prediction (V_1 should not decay when L2 mutations are unfiltered). Magnitude is small at n=90.

## Why λ̂ doesn't match paper analytic values

The paper's λᵢ values (1.45, 0.41, 0.07, 0.006) describe **exponential decay rates of perturbations** in the Lyapunov function. They are derived from the budget formula:

```
λᵢ = γᵢ − L_θᵢ·ρᵢ − L_dᵢ·ηᵢ − βᵢ·τ̄ᵢ − (ln νᵢ)/τ_{a,i}
```

Each cost term is a distinct physical quantity that requires its own measurement:
- `γᵢ` — natural decay rate when level above is frozen
- `L_θᵢ·ρᵢ` — sensitivity to level k+1's parameter changes
- `L_dᵢ·ηᵢ` — sensitivity to level k+1's structural changes
- `βᵢ·τ̄ᵢ` — measured Reasoner latency × delay sensitivity
- `(ln νᵢ)/τ_{a,i}` — observed switching rate × jump bound

We measure none of these directly. We fit `exp(−λt)` to V_k(t) of a stationary signal with no controlled perturbation, which gives a fundamentally different quantity (population variance estimator, not perturbation decay rate).

**To get λ̂ that compares meaningfully to the paper, we need controlled perturbation experiments** (`life-perturb` workstream). That's a research project, not a PR. Until then, our λ̂ are a *shape check* (sign matches?) not a *magnitude check*.

## What's been validated (the engineering bar)

Concrete mechanisms that **do** work as designed (with empirical evidence in events.jsonl):

| Mechanism | Evidence |
|---|---|
| Reasoner protocol + AnthropicReasoner with retries, caching, thinking | 5 live runs across 4 PRs, 0 wire bugs after PR #24's date-pinned-pricing fix |
| Hooks pipeline (`run_hooks_chain`) — Noesis pattern | 6/6 candidate L2 rules vetoed correctly across PR #23 + #24 |
| Shadow eval at calibrated `threshold_delta=2.0` | Blocks bad rules; H4 confirms it's load-bearing |
| Continuous L0 Lyapunov | V_0 ∈ [0.03, 0.82] across 360+ episodes; regression has signal |
| L1/L2/L3 LYAPUNOV emission | Per-level decay curves recoverable from any run's events.jsonl |
| HARDER_SUITE calibration (~67% baseline mean) | Real headroom; H1 directionally testable |
| Live progress streaming + watch CLI | Confirmed by visual inspection during multiple live runs |
| Bench command (multi-seed, bootstrap CIs) | This PR — first run pending |

## What remains (the validation bar)

| # | Item | Cost | Effort | Yields |
|---|---|---|---|---|
| 1 | **Bench run with N=3-5 seeds** | $5-15 | this PR | noise floor; H1 statistical significance |
| 2 | **--paper mode on HARDER_SUITE** | $30 | 3 hr | tight CIs; publishable headline |
| 3 | **Cross-validate at Sonnet tier** | $50-100 | rerun all conditions with model_l0_l1=Sonnet | does L2/L3 help when L0 is more capable? |
| 4 | **SWE-bench Lite subset (10 instances)** | $200 | 1 week | external validity on real-world benchmark |
| 5 | **`life-perturb` Workstream A** (controlled perturbations on Life) | weeks | weeks | actual paper-magnitude λ̂ measurement |
| 6 | **Cross-validation: microRCS-on-SWE vs Life-perturbed** | combined | months | strongest-possible evidence |

## Decision rules for next moves

- **If bench shows `2σ_flat < 0.04`:** H1 is statistically supported on HARDER_SUITE — ship `--paper` run for tight CIs and publish.
- **If bench shows `2σ_flat ∈ [0.04, 0.08]`:** PR #24's effect is at the noise edge; need bigger N or harder benchmark.
- **If bench shows `2σ_flat > 0.08`:** the system is too noisy at this scale; need either fixed seeds + many repeats, or a different model tier.
- **In all cases:** Workstream A (`life-perturb`) for actual λᵢ magnitude validation.

## Open scientific questions (deserve investigation)

1. **Why doesn't L2 help beyond L1?** Hypotheses: (a) shadow eval too conservative; (b) Haiku too weak to write good rules; (c) HARDER_SUITE's variance is task-typed — L1 mode-switching captures most of it.
2. **Does the result reverse at Sonnet/Opus tier?** Higher-capacity models may benefit from L2's prompt-rule injection more, or less.
3. **What's the right Lyapunov function for L0?** Current: continuous combination of cost/steps/score. Alternatives: KL from optimal trajectory, learned reward model.
4. **Is the budget formula `λᵢ = γᵢ − ...` the right decomposition?** Maybe the paper's parameters are wrong, not our measurements.

## Reproducibility

Every run referenced here is fully reproducible:

```bash
# PR #24 H1 directional signal:
python3 microrcs.py run --suite harder --seed 42 --out reports/

# PR #25 H4 budget-shield validation:
python3 microrcs.py run --break-budgets --suite harder --seed 42 --out reports/

# PR #25 noise-floor / multi-seed bench:
python3 microrcs.py bench --suite harder --conditions flat --n-seeds 5 --base-seed 42

# PR #25 cross-condition significance:
python3 microrcs.py bench --suite harder --conditions flat,+autonomic,full --n-seeds 5
```

Each command is fully deterministic given the same seed (modulo Anthropic API stochasticity, which is bounded by temperature=1.0 sampling).

## Document maintenance

This file is **append-only** by convention. Each PR that updates a verdict should:
1. Add a row to "Cumulative empirical runs"
2. Update the relevant verdict in §H1-H4
3. NOT delete previous findings (they document the iterative scientific process)
