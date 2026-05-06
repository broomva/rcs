# Thesis Validation — empirical state

> **Purpose:** Pin the cumulative findings from microRCS empirical runs so future
> contributors don't relearn what we already know. Each section is dated and
> traceable to a specific PR + run.

## Headline state (as of PR #31 — POST capacity sweep result)

The RCS thesis exists in three forms; current evidence by form:

| Form | Claim | Status | Evidence |
|---|---|---|---|
| **Performance (weak)** | "some recursive control improves agent pass-rate when there's headroom" | ⚠️ **TIER-DEPENDENT** | Refuted at Haiku × HARDER (PR #25), Sonnet × HARDER (NEW PR #31); **directionally supported at Opus × HARDER (NEW PR #31)** with 3/3 seeds showing +meta and +full > flat. Refuted on microgrid (PR #2) and cross-run compounding (PR #28). |
| **Performance (statistical)** | `pass^k_recursive > pass^k_flat` with `p<0.05` | ❌ **rejected at Haiku, Sonnet (negative)**, ⚠️ **inconclusive at Opus** | Sonnet bench: Δ=−0.07 to −0.09, all above 2σ_flat=0.020 → recursion *significantly hurts*. Opus bench: Δ=+0.13 to +0.14 but 2σ_flat=0.16 → effect within noise band but consistently positive directionally (n=3). |
| **Stability (λᵢ > 0)** | empirical λ̂ᵢ positive at every level | ⚠️ **partial** | Only λ̂_2 numerically positive on microRCS; microgrid hourly sim cannot resolve sub-second decay |
| **Stability (paper-magnitude)** | λ̂ᵢ ≈ paper analytic λᵢ within bootstrap CI | ❌ **3 orders off** | Construct gap — see §"Why λ̂ doesn't match paper" |
| **Strong (monotone-by-level)** | `full > +meta > +autonomic > flat`, with λᵢ matching paper | ❌ **refuted at every tested tier** | At Opus, surprisingly +meta ≈ full (both help) > +autonomic (≈ flat) — the +autonomic step does NOT add value when L1 mode-switching acts alone. |
| **Shadow-eval load-bearing** | "without budget shields, recursion hurts" | ✅ **SUPPORTED on TWO testbeds** | microRCS H4: +meta=0.282 < flat=0.327 without shadow eval; microgrid: shadow eval correctly vetoes 69/69 candidate mutations on both +meta AND full |
| **Bitter-lesson interpretation** | "scaffolding helps weak / hurts strong models" | ❌ **partially refuted by capacity sweep** | Haiku→Sonnet: scaffolding hurts more (consistent with bitter lesson). Sonnet→Opus: scaffolding REVERSES from hurting to helping (anti-bitter-lesson). The relationship is non-monotone in capacity. |

**The defensible claim today (after gemma4 multi-seed at n=3, post-PR #40):** _the relationship between recursive control and pass^k across 4 tiers tested (gemma4-8B, Haiku, Sonnet, Opus) is **null at proper power except in one direction at Sonnet**. At gemma4-8B (REFERENCE × 3 seeds, 540 ep): all Δ within ±0.005, well inside 2σ_flat=0.026. At Haiku (HARDER × 3 seeds): noise dominates. At Sonnet (HARDER × 3 seeds, σ=0.010): recursion **statistically hurts** (Δ=−0.07 to −0.09, all above 2σ band). At Opus (HARDER × 3 seeds, σ=0.079): +meta and full beat flat by Δ=+0.13 / +0.14 directionally but the wide CI makes n=3 inconclusive. The shadow eval safety mechanism is reliably load-bearing across testbeds. **Pattern: recursion is null at the tails (very weak / very strong L0) and actively harmful in the middle (Sonnet).** Both naive interpretations of the bitter lesson (monotone-helps-weak; monotone-hurts-strong) are empirically dead._

**The weak-form thesis is now empirically null at most tiers and negative at one** — refuted at gemma4-8B and Haiku within noise, statistically refuted at Sonnet (recursion hurts), directionally supported at Opus but n=3 inconclusive. A `--paper` mode run (n=20) at Opus tier remains the cleanest path to either confirming or burying the directional Opus signal. Beyond that: long time scales (Life multi-day runs via BRO-947 perturbation, life PR #1090), harder benchmarks (SWE-bench at higher max_steps), or **horizontal-recursion variants** (Swarm-RCS-L0, PR #40) are the remaining open paths.

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
| **microgrid #2** | TestVillage × 3 seeds × 720h | **flat ≈ all** | n/a (diesel L: 1124) | n/a (1123 ± 39) | recursion **identical** to flat (Δ=−0.1%) | ~$0 (no LLM) | **H1 REFUTED on a SECOND testbed** — real physics, hard physical metrics, same null result. 69/69 L2 mutations correctly vetoed by shadow eval. |
| **#27 cross-run v1** | HARDER × 5 iter × full × Opus L2 (--quick) | n/a | mean ~1.0 (saturated) | flat trend | suite ceiling masked compounding signal | ~$0.05 | inconclusive — `--quick` gave only 2 tasks per iter; canonical=0 (compounding mechanism wired but not exercised because L2 NoOp'd) |
| **#27 cross-run v2** | HARDER × 5 iter × full × Opus L2 (full suite) | n/a | n/a | Δ = -0.061 (declining) | **structural gap discovered**: AppendSystemRule mutates in-memory list only, doesn't persist | ~$3 | revealed that PR #27's persistence mechanism wasn't being exercised by the L2 actions Opus chose; led to PR #28 |
| **#28 cross-run final** | HARDER × 5 iter × full × Opus L2 + disk-persisted rules | flat ≈ iter1 | ~0.36 (mean across iter) | iter1 0.360 → iter5 0.431 (+0.072) | within-iter σ=0.045, 2σ=0.09 — **NOT significant** | ~$3.4 | 4 high-quality Opus rules accumulated to disk and loaded across iterations. Mechanism works perfectly. **Compounding still doesn't measurably improve pass^k**. |
| **#31 Sonnet bench** | HARDER × 3 seeds × Sonnet L0/L1 + Opus L2/L3 | **flat** | **0.505 ± 0.010** | full=0.431 (Δ=−0.074) | recursion **significantly HURTS** (3/3 conditions Δ > 2σ_flat=0.020) | $17.78 | first regime where recursion is measurably bad. Tight baseline (σ=0.010) makes effect detectable. Bitter-lesson signal at Sonnet tier. |
| **#31 Opus bench** | HARDER × 3 seeds × Opus L0/L1 + Opus L2/L3 | **+meta** | **0.495 ± 0.079** | +meta=0.636 (Δ=+0.141), full=0.626 (Δ=+0.131) | recursion **directionally HELPS** but per-seed σ=0.079 makes it inconclusive at n=3 | $63.04 | 3/3 seeds show +meta > flat AND full > flat. **The bitter-lesson reverses at Opus.** +autonomic alone (L1 mode-switching, no L2) ≈ flat. The L2 layer is what helps Opus. |
| **#32 SWE-bench-Lite smoke** | 2 instances × Haiku × flat × max_steps=50 | n/a (engineering smoke) | n/a (smoke goal: pipeline) | flask=0.0 / pylint=0.0 (both step_budget) | not statistical — pipeline validation only | ~$2 | Pipeline validated end-to-end. Verifier checked against ground-truth patch: score=1.0 on flask-4992 (FAIL_TO_PASS 1/1 + PASS_TO_PASS 10/10). Two real bugs caught + fixed: empty-tool-result API rejection in microrcs.py mainline; test_patch leaking into agent diff in adapter. Cost-per-instance baseline: ~$1 Haiku × flat. **Ready for BRO-946 full bench scoping.** |
| **#34 SWE-bench-Lite pilot** | 4 instances × 4 conditions × 1 seed × Haiku L0/L1 + Sonnet L2/L3 × max_steps=50 | none (all 0.000) | flat=0.000 | all conditions = 0.000 | recursion overhead negligible (~$0.50/condition); recursion benefit also zero — **L0 capacity is the binding constraint** | $13.46 | Pilot confirms smoke: Haiku × 50 steps below the SWE-bench floor. All 16 episodes step-budget abort or no_action abort. Recursion wraps a flat that scores 0/4 → still 0/4. The recursion question is NOT testable in this regime. To probe H1 productively on SWE-bench, need either (a) higher tier (Sonnet/Opus L0), (b) higher max_steps (≥100), or (c) easier instances (SWE-bench Verified subset). |
| **Path 1: Haiku × max_steps=150 SWE** | 4 instances × 4 conditions × 1 seed × Haiku L0/L1 + Sonnet L2/L3 × max_steps=150 | flat ≈ full | flat=0.250, full=0.250 | +autonomic=0.000 (Δ=−0.25), +meta=0.000 (Δ=−0.25), full=0.250 (Δ=0.00) | step-budget bump unlocked one solve; recursion at L1-only and L1+L2 LOSES the solve, full re-finds it | $24.36 (Path 1 only) | First non-zero SWE-bench result. `psf__requests-3362` solved by flat AND full but NOT +autonomic / +meta. Could be real "L1 mode-switch noise breaks the solve, L3 governance recovers" OR per-instance variance at n=1 paired (only 1 of 4 instances solvable). Need ≥3 seeds to disambiguate. |
| **Path 2: Sonnet × max_steps=50 SWE** | 4 instances × 4 conditions × 1 seed × Sonnet L0/L1 + Opus L2/L3 × max_steps=50 | flat partial only | n/a (incomplete) | invalid (credit balance + connectivity) | inconclusive — API credits ran out mid-flat condition, all recursion conditions aborted on the next call | ~$3 | flat got 2/4 instances run (flask: 0.00 in 10 steps, pylint: 0.00 in 43 steps); requests-3362 + sphinx not run; +autonomic/+meta/full all aborted with API errors. **Re-run pending budget refresh.** |
| **gemma4 bench (PR #36)** | REFERENCE_SUITE × 4 conditions × 3 epochs × 3 repeats × gemma4:8b local L0+L2 × max_steps=20 = 180 episodes | **full** | flat=0.054 | +autonomic=0.054 (Δ=0.000), +meta=0.045 (Δ=−0.009), full=0.064 (Δ=+0.010) | recursion **directionally HELPS** at full, neutral at +autonomic, slightly hurts at +meta — but CIs heavily overlap; not significant at n=1 seed | $0 (local) | First end-to-end run via OllamaReasoner (PR #36). Validates that the Reasoner Protocol is provider-agnostic; confirms gemma4-8B can tool-call against the bash+submit interface. Per-task pass-rate pattern: math=0% (all no_action — modality mismatch), logic-zebra ~100%, code-bugfix ~50%, qa partial only, planning-hanoi mixed. **3 of 5 tasks are modality-mismatched** — motivates the Eywa flag (PR #37) for follow-up. |
| **Eywa A/B mechanism (post-PR #37)** | --quick × REFERENCE × flat+full × gemma4 + `--eywa-python` flag | n/a (mechanism check) | flat=0.000 (control parity) | full=0.125 (parity with smoke) | scores unchanged but **mechanism confirmed**: agent now invokes `python -c` for arithmetic instead of rambling | $0 (local) | **Eywa hypothesis empirically validated at the mechanistic level.** Without the flag, gemma4 hit `no_action` after 1 step on math-multi-step. With `--eywa-python`, gemma4 took 4 bash steps including `python -c 'print(73 * 1.6)'` and `python -c 'print(295.2 / 154)'` — modality-native compute exactly as Eywa (arXiv:2604.27351) predicts. Score still 0 because `--quick` capped max_steps=10, too few for the multi-step time calculation to complete. **Binding constraint shifted from modality-mismatch to step-budget.** Magnitude follow-up: same A/B at max_steps=50+. |
| **gemma4 multi-seed bench (post-PR #40)** | REFERENCE × 3 seeds × 4 conditions × 3 epochs × 3 repeats × gemma4:8b × max_steps=20 = 540 episodes | **flat ≈ +meta ≈ full** | flat=0.061 ± 0.013 | +meta=0.065 (Δ=+0.004), full=0.065 (Δ=+0.004), +autonomic=0.057 (Δ=−0.004) | recursion **NOISE-LEVEL** at gemma4 — all Δ within 2σ_flat=0.026 | $0 (local) | **The PR #38 directional signal does NOT survive at n=3 seeds.** +0.01 Δ shrunk to +0.004, smaller than within-condition std. Confirms the gemma4 weak-L0 result is empirically null. Combined with PR #31 capacity sweep at n=3, only Sonnet × HARDER shows statistically significant effect (negative). **The bitter-lesson is dead at proper power on every tier we've tested except Sonnet (where it inverts).** |
| **Swarm-RCS-L0 first live run (post-PR #40)** | REFERENCE × 1 seed × swarm_flat × N=3 peers × k=2 majority × gemma4 × max_steps=20 = 5 tasks × 3 peers = 15 reasoner calls | logic-zebra ✓ | n/a (different aggregation than single) | swarm_flat: pass^k=0.008 (strict majority), pass@k=0.600 (any-peer success) | **strict majority quorum HURTS, but best-of-N would HELP 10x at gemma4** | $0 (local) | Single live invocation revealed a deep finding: strict-majority answer-hash voting (k=2 of 3) requires peers to converge on the SAME answer, not just succeed independently. With gemma4 at ~33% per-peer submit rate on most tasks, majority quorum almost never reaches. BUT `pass@k=0.60` shows that at least 1 peer often succeeds — so a different aggregation (best-of-N, verifier-weighted, score-driven) would yield 10× over single_flat. **Strict-majority quorum is brittle on free-form outputs; the swarm has latent capability that the chosen aggregation throws away.** Follow-up: run with k=1 (any-peer-submits), then implement verifier-weighted aggregation. |

Total spend so far: ~$159 across ~6040 episodes (microRCS, +540 free this round) + 2160 hours (microgrid).

## Capacity-tier sweep result (PR #31 / BRO-945)

The bitter-lesson interpretation predicts that recursive scaffolding should help weaker
models more and hurt stronger ones. PR #31 tests this directly by sweeping L0/L1 across
Anthropic's full capability tier (Haiku → Sonnet → Opus), holding L2/L3 constant at Opus
(highest available meta-controller). The result refutes the simple bitter-lesson story.

**Three-tier × 3 seeds × HARDER_SUITE × 4 conditions = 1080 episodes per tier.**

| Tier (L0/L1) | flat mean ± std | +autonomic Δ | +meta Δ | full Δ | 2σ_flat | Verdict |
|---|---|---|---|---|---|---|
| Haiku-4-5 (PR #25) | 0.357 ± 0.055 | −0.014 | −0.032 | −0.080 | 0.110 | all within noise |
| **Sonnet-4-6 (NEW)** | **0.505 ± 0.010** | **−0.085 ✓** | **−0.078 ✓** | **−0.074 ✓** | **0.020** | **all 3 conditions HURT, above noise** |
| **Opus-4-7 (NEW)** | **0.495 ± 0.079** | **−0.000** | **+0.141** | **+0.131** | **0.158** | **+meta and full HELP directionally**, n=3 inconclusive |

### Per-seed paired pass^3 (the "3/3 directional consistency" pattern at Opus)

| Seed | Opus flat | Opus +autonomic | Opus +meta | Opus full | Δ_full vs flat |
|---|---|---|---|---|---|
| 42   | 0.602 | 0.394 | 0.702 | 0.651 | **+0.049** |
| 1051 | 0.413 | 0.534 | 0.451 | 0.471 | **+0.058** |
| 2060 | 0.471 | 0.556 | 0.756 | 0.756 | **+0.285** |

3/3 seeds show full > flat at Opus. 3/3 show +meta > flat at Opus. The unpaired bootstrap
CI is wide because per-seed σ_flat=0.079, but the paired-difference signal is consistent.
Sign-test on paired Δ: 3 successes / 3 trials, one-sided p = 0.125 — directional but not
formally significant at α=0.05 with this sample size.

### What changes between tiers

- **Haiku → Sonnet**: flat baseline tightens from σ=0.055 to σ=0.010 (5×), making any
  recursion effect detectable. All 3 recursion conditions cross the noise band into "hurts."
  The bitter lesson plays out as predicted at this step.
- **Sonnet → Opus**: flat baseline widens back to σ=0.079 (variance balloons because Opus
  occasionally fails individual tasks that Sonnet solves reliably, and pass^3 is unforgiving
  to single-trial failures). But the *direction* of the recursion effect REVERSES: +meta
  goes from −0.078 (hurts Sonnet) to +0.141 (helps Opus). +full goes from −0.074 to +0.131.

### Why does +autonomic stay neutral at Opus while +meta and full help?

`+autonomic` adds only L1 mode-switching (cot/scratchpad/verify); no L2 rule generation,
no shadow eval. At Opus, L1 mode-switching alone is essentially noise: per-seed Δ is
[−0.208, +0.121, +0.085] which sums to ~0.

`+meta` adds L2 (rule generation + shadow eval) on top of L1. At Opus, the L2 generates
high-quality rules (Opus is the L2 model), and the shadow-eval gate filters the bad ones.
Net effect: useful rules accumulate within a single bench condition (n=90 episodes).

This means **the L2 layer is the load-bearing element of recursion at Opus tier** — not
the L1 mode-switching. At Sonnet, L2 still doesn't beat flat because Sonnet (the L0 model)
either doesn't profit from rule injection or actively gets confused by it.

### Cost per tier

| Tier | Cost | Per-condition mean cost |
|---|---|---|
| Haiku (PR #25) | $8.65 | $2.16 |
| Sonnet (PR #31) | $17.78 | $4.45 |
| Opus (PR #31) | $63.04 | $15.76 |

Opus +meta was the most expensive condition ($20.72 across 3 seeds, ~$6.91/seed) because
the shadow-eval mechanism spawns extra Opus inference for trial episodes. Despite the cost,
this is also the condition that helps most.

### Methodological caveats (still open)

1. **n=3 at Opus is too few** to declare H1 supported with statistical confidence at α=0.05.
   A `--paper` run (n=20) at Opus tier would tighten the CI and either confirm or refute.
2. **HARDER_SUITE may be miscalibrated for Opus** — pass^3=0.495 means there's headroom,
   but math-rate and logic-meeting consistently fail (suite-specific failure modes Opus
   shares with Sonnet). A redesigned suite hitting Opus at 50% baseline would be cleaner.
3. **L2/L3 = Opus across all conditions** — we held the meta-controller constant. The
   tier-0 effect is what we measure. A sweep also varying L2 tier would test whether the
   meta-controller's capacity matters.
4. **Single-shot tasks remain the regime.** The capacity sweep doesn't address the
   long-horizon hypothesis (BRO-946 SWE-bench). The Opus result here is at most a
   directional hint that "scaffolding helps high-capacity agents on short text tasks."

### Reproduction

```bash
# Haiku baseline (already done in PR #25):
python3 microrcs.py bench --suite harder --conditions flat,+autonomic,+meta,full \
    --n-seeds 3 --base-seed 42

# Sonnet capacity test (PR #31):
python3 microrcs.py bench --suite harder --conditions flat,+autonomic,+meta,full \
    --n-seeds 3 --base-seed 42 \
    --model-l0-l1 claude-sonnet-4-6 --model-l2-l3 claude-opus-4-7

# Opus capacity test (PR #31):
python3 microrcs.py bench --suite harder --conditions flat,+autonomic,+meta,full \
    --n-seeds 3 --base-seed 42 \
    --model-l0-l1 claude-opus-4-7 --model-l2-l3 claude-opus-4-7
```

## SWE-bench-Lite smoke result (PR #32 / BRO-946 phase 1)

The capacity sweep (PR #31) tested H1 on single-shot independent reasoning
tasks. The thesis is fundamentally about long-horizon multi-step recursive
control — exactly the regime SWE-bench-Lite is built for. Before committing
to BRO-946's full bench (~$240, ~1 week, 20 instances × 4 conditions × 3
seeds), PR #32 ships an engineering smoke to validate the pipeline.

### Setup

- 2 hand-curated instances: `pallets__flask-4992`, `pylint-dev__pylint-7080`
- Both pure-Python, modern (≥2022), pass venv-no-Docker compatibility
- Haiku × `flat` only × `max_steps=50` × `max_cost_usd=5.0`
- New module: `microrcs/adapters/{swe_bench,swe_types}.py` + pluggable
  `SandboxBackend` protocol with one `UvVenvBackend` impl
- Three-layer cache: `~/.cache/microrcs-swe/{repos,venvs,workspaces}` with
  APFS `clonefile` for COW per-episode workspaces

### Live smoke results

| Instance | Score | Steps | Cost | Wall | Aborted |
|---|---|---|---|---|---|
| `pallets__flask-4992` | 0.0 | 50 | $0.77 | 190s | step_budget |
| `pylint-dev__pylint-7080` | 0.0 | 50 | $1.25 | 142s | step_budget |

Both instances exhausted their step budget without submitting. **Expected
for Haiku × flat × 50 steps on real SWE-bench bugs.** The smoke goal was
pipeline validation, not signal — both instances produced clean verdicts
through the verifier path.

### Verifier correctness

The verifier was exercised end-to-end against the **ground-truth patch**
(via `instance.patch`) for `flask-4992`. Result:

```text
score=1.0
fail_to_pass_passing=1, fail_to_pass_total=1
pass_to_pass_passing=10, pass_to_pass_total=10
pytest_duration_s=0.74
```

This proves: (1) the pipeline applies a candidate patch to a fresh sibling
workspace, (2) pytest runs in the per-repo venv with the right Python and
deps, (3) FAIL_TO_PASS and PASS_TO_PASS counts are extracted correctly,
(4) the binary scoring rule matches the official SWE-bench convention.

### Bugs found via the smoke (both fixed in PR #32)

1. **`microrcs.py`: empty `tool_result` content with `is_error=true` rejected
   by Anthropic API.** A bash command producing no stdout/stderr (e.g.
   `cd somewhere`) was crashing the agent loop after ~30 messages. Fix:
   substitute `[no stderr / no stdout]` placeholder when `obs` is empty.
   Affects all microRCS runs, not just SWE-bench.

2. **Adapter: `test_patch` leaking into agent's `git diff HEAD`.** Verifier
   reads agent edits via `git diff HEAD`, but `test_patch` was applied at
   setup time without committing — so the diff conflated test setup + agent
   edits. Applying the combined diff to the verify-sibling workspace (which
   already has `test_patch` applied) failed. Fix: commit `test_patch` as a
   new HEAD during setup so subsequent `git diff HEAD` captures only agent
   changes.

### Implications for BRO-946 full bench

| Parameter | Smoke observation | Full-bench projection |
|---|---|---|
| Cost per Haiku × flat × instance | ~$1.00 | ~$1.00/instance × 20 × 1 condition = $20 |
| Wall per instance | ~3 min agent + ~20s verify (ground-truth) | ~3 min × 20 = ~1h per condition |
| Step budget hit rate (Haiku × flat) | 2/2 (100%) | suggests Haiku alone can't solve real SWE-bench at flat |
| Cold-cache setup | ~14s for 2 instances | ~3-5 min for 20 instances first run |
| Verifier correctness | confirmed against ground-truth | no further calibration needed |

**Projected BRO-946 full bench cost** (20 instances × 4 conditions × 3 seeds):
- flat × 20 × 3 = 60 episodes × $1 = $60
- +autonomic / +meta / full × 20 × 3 = 180 episodes; recursion overhead via
  PR #31 calibration is ~1.5–4× per condition, so ~$90–$180 × 3 conditions
- **Total: $300–$600 at Haiku** (above the $240 ticket estimate; the ticket
  underestimated the recursion overhead from the HARDER bench)
- Sonnet/Opus full benches would be 3×–15× this (proportional to PR #31)

The full bench is feasible. Recommendation: re-scope BRO-946 with the
observed costs before kicking off, or start with a tighter pilot (5
instances × 4 conditions × 1 seed at Haiku ≈ $30) to confirm the recursion
ablation produces a directional signal before the full N=3 seeds run.

## JEPA Experiment A — null on existing capacity-sweep traces (PR #44+)

PR #44 shipped the design note `docs/research-notes/2026-05-05-jepa-as-rcs-frame.md` proposing JEPA's predictor energy `E_θ = ‖P_φ(z) − z'‖²` as an alternative Lyapunov substrate to the current `V_0 = 0.3·cost + 0.3·steps + 0.4·(1−score)` heuristic. Experiment A — train a small MLP-JEPA on existing per-episode capacity-sweep traces and check whether `Var[λ̂_0]_JEPA < Var[λ̂_0]_heuristic` — has now been run.

### Setup

- **Code**: `microrcs/scripts/jepa_a.py` (~430 LOC, 9 unit tests passing)
- **Data**: 2,160 per-episode records from `reports/bro945-{sonnet,opus}/` (2 capacities × 3 seeds × 4 conditions × 90 episodes)
- **Trajectories**: 24 ordered per-(model, seed, condition) sequences
- **Model**: encoder R²⁰ → R³² (5K params), residual predictor, EMA target encoder, VICReg-lite collapse prevention
- **Training**: 50 epochs, ~2s wall-clock CPU, no collapse (final std=1.01, pred_loss=0.41)

### Result — heuristic wins

**Median `Var[λ̂_0]_JEPA / Var[λ̂_0]_heuristic = 1.67`** across 8 (capacity × condition) cells. JEPA achieves lower variance in 3/8 cells, heuristic in 5/8. The two estimators **disagree on the sign of `λ̂_0` in 4/8 cells** — they measure different dynamic properties of the trajectory, not noisier vs less noisy versions of the same property.

| capacity | condition | JEPA λ̂ | heur λ̂ | Var ratio J/H |
|---|---|---|---|---|
| opus   | flat | −0.0030 | −0.0027 | **0.72** ✓ |
| opus   | full | +0.0016 | −0.0037 | **0.52** ✓ |
| sonnet | +autonomic | −0.0117 | −0.0030 | **0.49** ✓ |
| (5 other cells) | | | | 1.4× to 21.3× |

(✓ = JEPA wins. Full table at `docs/research-notes/2026-05-05-jepa-experiment-a-results.md`.)

### Why this is interpretable, not refutational

1. **Episode-level granularity ≠ design-spec step-level.** The note's Experiment A specified per-step `(z_t, z_{t+1})` pairs from `events.jsonl` streams. Those streams are wiped from `/tmp` workspaces; this run substituted per-episode aggregates from existing reports — fewer pairs, coarser dynamics.
2. **Pass-rate ceiling on Opus compresses both estimators** symmetrically into the e-3/e-4 band, where ratios are dominated by sampling noise (the 21× outlier on `sonnet flat` is one near-zero seed cell pinching).
3. **n=3 seeds per cell is below statistical power** for second-order statistics like Var[λ̂].

### Implications

- **Experiment A null does NOT refute the design-note thesis.** It refutes the path "use existing capacity-sweep aggregates → JEPA graduates immediately." The thesis test (Experiment B: two-level H-JEPA U-shape recovery) remains scoped at the original priority.
- **Productive next data run is per-step.** Run a small fresh bench with `--persistent-workspace` on gemma4 (free), retain `events.jsonl`, parse to `(z_t, z_{t+1})` pairs at >100K resolution. At step level, ceiling effects on episode score don't matter — within-episode dynamics are richer than the score boolean.
- **JEPA frame stays alive but downgraded** from "ship Tier-1 immediately" to "needs step-level data first."

### Reproduction

```bash
cd microrcs
python3 -m scripts.jepa_a --reports ../reports --out ../reports/jepa-a \
    --epochs 50 --seed 42
# wall-clock: ~2 s on Apple M4 Pro CPU
```

Full results note: `docs/research-notes/2026-05-05-jepa-experiment-a-results.md`.

## JEPA Experiment A v2 — per-step pipeline shipped, data-shape limit identified (PR #45+)

PR #45 (per-step) shipped the `jepa_a per-step` subcommand with full per-step extraction (events.jsonl → StepRecord → StepTrajectory), training (`train_step_jepa`), and two estimators (per-trajectory `lambda_hat_step` + cohort `lambda_hat_step_cohort`). 9 new tests, **246/246 passing** in the full suite.

### Setup

- **Code**: `microrcs/scripts/jepa_a.py` per-step subcommand; 14-d step features
- **Data run**: gemma4-8B + REFERENCE suite × 1 epoch × 3 repeats × {flat, full}, persistent workspace, 15.9 min wall-clock, $0 cost
- **Training**: 100 epochs, ~3 s on M4 Pro CPU, no collapse

### Result — data-shape limitation, not a JEPA refutation

After parsing 30 episodes' events.jsonl: **19 trajectories ≥2 steps, 20 step pairs total**. Most gemma4 episodes are 2-step (bash → submit), so per-trajectory λ̂ is undefined for all 19 (need ≥3 positive energy values per trajectory; we have ≤1).

| Cohort λ̂ | n_pairs | unique step_idx | Verdict |
|---|---|---|---|
| flat | 10 | 1 | n/a (xs all at 0 → degenerate) |
| full | 10 | ≥2 | −1.37 (single point, statistically uninformative) |

### What this changes

- **Pipeline**: shipped + validated. Will consume any per-step events.jsonl stream.
- **JEPA frame**: still alive. Was not given a fair empirical test on this data.
- **Productive next data run**: SWE-bench-Lite pilot with `--persistent-workspace` (gemma4 + REFERENCE produces 1–2 step episodes; SWE produces 35–98 step episodes per `reports/swe-pilot-step150/pilot-*-summary.json`).
- **Cohort λ̂ as second-line estimator**: implemented as fallback when per-trajectory λ̂ is undefined, with documented survival-bias caveat.

Full results note: `docs/research-notes/2026-05-05-jepa-experiment-a-perstep-results.md`.

### Reproduction

```bash
# Generate the data
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

# Train per-step JEPA (~3 s)
python3 -m scripts.jepa_a per-step \
    --workspaces ../reports/jepa-a-perstep/raw \
    --out ../reports/jepa-a-perstep \
    --epochs 100 --seed 42
```

## JEPA-as-substrate research-program spec (PR #48)

PR #48 ships the 1,105-line spec at `docs/superpowers/specs/2026-05-05-jepa-as-substrate-design.md` scoping a phased research program (Q1-Q5 + Paper 5) that turns JEPA from a sensor signal into the **substrate** for the RCS controller hierarchy. Synthesizes v1 + v2 null/limit results into a coherent next-step program.

### Architecture commitment

Three-trait family (mirrors Spec D AnimaCustody pattern):

- `L0Head` — agent loop abstraction (LLM/world-model/SSC/hybrid/BC)
- `JepaSubstrate` — encoder + predictor + EMA target + stability monitor
- `L1Controller` — existing L1Autonomic + new L1ForwardRollout

L0Head abstraction enables Q4 multi-head A/B and Q5 embodied extension. Substrate intrinsic control rate ~10 kHz; LLM is the binding constraint.

### Theoretical contribution

**Online JEPA Composite Stability Theorem** with 6 assumptions (H8a-e Lipschitz/deployment-lag/KL-drift/monitor + H9 head-Lipschitz):

```
λ_composite = γ_k − L_θρ_k − L_dη_k − β_kτ̄_k − L_oθ(Δ,μ) − L_Hκ_k
              − ln(ν_k)/τ_a > 0
```

Two new terms vs P0: online encoder cost L_oθ(Δ,μ) and head cost L_H κ_k. Closed form derived by extending Borkar 2008 two-time-scale stochastic approximation to discrete-deployment setting. Full proof scoped to Paper 5; CI-gated empirical lower bound > 0 before any production rollout.

### Validation surface

SWE-bench-Lite paired A/B as primary validation surface — real GitHub bugs, pytest verification, paired McNemar test. Joint phase gate: math (G1 Var ratio + G2 Pearson r + G3 training health, 2-of-3) + production (P1 Spearman ρ ≤ -0.15, P2 z-L1 pass^1 ≥ hand-L1 pass^1, both-of-2). Kill criteria K1/K2 force clean stop on persistent failure.

### Phase decomposition

7 sub-epics under parent JEPA Substrate Research Program:
- Q1 (8 tickets, ~2 weeks): substrate + AC-Trajectory-JEPA + Q1 SWE data
- Q2.0 (3 tickets, mechanical): L0Head protocol introduction
- Q2.1 (8 tickets, ~2 weeks): L1ForwardRollout + SWE A/B benchmark
- Q3 (8 tickets, ~4 weeks): OnlineJepaSubstrate + canary + circuit breaker
- Q4 (3 tickets, post-Q3): WorldModelL0Head + HybridL0Head + 3-way A/B
- Q5 (1 sketched ticket): StateSpaceL0Head + sensor encoder
- Paper 5 (5 tickets, parallel weeks 1-3 + 8-12): theorem track

Critical path 11-12 weeks. Cost ~$386 ($4 Q1 Haiku + $132 Q2 Sonnet + $200 Q3 demo + $50 buffer). 3-month focused engineering.

### Locked decisions

7 decisions from brainstorm explicitly locked:
1. Spec scope full Q1+Q2 with phased decommit
2. Theory depth = full theorem (proofs in Paper 5)
3. Q2 empirical scope L1 only; L0/L2/L3 architecturally scoped
4. microRCS as proving ground; Life Rust deferred
5. Phase gate = math 2-of-3 + production both-of-2 + kill criteria
6. SWE-bench-Lite as primary validation surface
7. Q3 encoder cadence = online (replay + canary + circuit breaker)

### Status

Design complete. Next: implementation plan via writing-plans skill (separate PR), then Q1 implementation begins.

Full spec: `docs/superpowers/specs/2026-05-05-jepa-as-substrate-design.md`.

## Swarm-RCS-L0 first live run — quorum aggregation matters more than expected

PR #40 shipped the SwarmL0Plant scaffold (3 architectural decisions: strict-majority answer-hash voting, union-of-peer-streams L1, helpers+memory+rules shared). PR #43 ran the first live invocation against gemma4 to test "does horizontal recursion (peer swarm + stigmergic substrate) help at the weakest tier?"

### Result

`swarm_flat × gemma4 × REFERENCE × N=3 × k=2 × 1 seed`:

| Task | Per-peer voters | Quorum | Score |
|---|---|---|---|
| math-multi-step | 0/3 | ❌ | 0.00 |
| code-bugfix | 1/3 | ❌ | 0.00 |
| logic-zebra | 3/3 | ✅ | **1.00** |
| closed-book-qa | 1/3 | ❌ | 0.00 |
| planning-hanoi | 0/3 | ❌ | 0.00 |

Headline metrics from the structured output:
- `pass_pow_k = 0.008` (strict 2/3 majority quorum)
- `pass@k    = 0.600` (any-peer-success — **best-of-N**)

**Same data, two aggregation strategies, ~75× different effective performance.**

### What this reveals

Strict-majority answer-hash voting requires peers to:
1. Successfully submit (vs hit `no_action`) — gemma4 fails this on 3 of 5 REFERENCE tasks
2. Submit the **same answer hash** — fails on free-form outputs like code or hanoi sequences (multiple correct forms)

The `pass@k = 0.60` — meaning at least one peer succeeded on 3 of 5 tasks — shows the swarm has real latent capability. The aggregation strategy throws it away. Concretely:

- Single-flat × gemma4 (PR #41 multi-seed): mean = 0.061 ± 0.013
- Swarm-flat × gemma4 × strict-majority: pass_pow_k = 0.008 (worse than single)
- Swarm-flat × gemma4 × best-of-N: pass@k = 0.60 (~10× single)

### What this changes about the H1 picture

The vertical-RCS verdict (recursion null at the tails, hurts at Sonnet) is unchanged — that bench is multi-seed at proper power.

But for **horizontal recursion** (PR #40's contribution): the answer depends almost entirely on the aggregation strategy. The structural choice "what does the swarm output as its consensus answer?" turns out to matter more than the structural choice "should peers share helpers/memory/?". This wasn't anticipated in the spec's D1 decision — that decision treated voting as a parameter to tune, but the live run shows it's the dominant variable.

### Three follow-up experiments enabled

1. **Swarm × k=1 (best-of-N)** at gemma4 (~10 min, $0): verify that pass^1 actually reaches 0.60 with k=1 quorum — this would be the cleanest "swarm beats single" result we've gotten in any condition.
2. **Verifier-weighted aggregation**: instead of voting on answer hash, run each peer's submission through `task.verify` and pick the highest-scoring. Requires a small driver change (~30 LOC). Likely dominates both strict-majority and best-of-N.
3. **Single-tier comparison** at proper N (3 seeds × N peers): does the swarm advantage replicate at Haiku, Sonnet, Opus? If yes, swarm's value scales across tiers in a way vertical RCS doesn't.

The PR #40 spec D1 (voting strategy) needs revisiting in light of this — strict majority shouldn't be the v0 default for free-form output domains.

## Eywa modality-nudge mechanism confirmed (post-PR #37)

After the gemma4 bench landed (PR #38), we ran a single-variable A/B at
gemma4 × REFERENCE × `--quick` × flat+full to test whether the
`--eywa-python` flag changes agent behavior. The flag injects a system-
prompt block telling the agent to offload arithmetic to `python -c` via
bash (Eywa-style modality-native compute, arXiv:2604.27351).

### Result

| Cond | pass^3 control (PR #38 smoke) | pass^3 treatment (--eywa-python) |
|---|---|---|
| flat | 0.000 | 0.000 |
| full | 0.125 | 0.125 |

**Scores unchanged.** But the underlying agent behavior is materially
different. Reading the events.jsonl for the treatment run:

```text
flat × math-multi-step:
  step 1: bash: # Calculate time difference (11:23 - 9:47)...
  step 2: bash: python -c 'print(73 * 1.6)'         ← modality-native!
  step 3: bash: python -c 'print(295.2 / 154)'      ← Eywa cure firing
  step 4: bash: [more arithmetic]
  abort:  step_budget at max_steps=10 (--quick cap)
```

Compare to the control (PR #38 bench, no flag):

```text
flat × math-multi-step:
  step 1: [model rambled in tokens about time math]
  abort:  no_action at step 1
```

**The Eywa hypothesis is empirically validated at the mechanism level.**
Without the flag, gemma4 doesn't even attempt to compute — it generates
plain-text reasoning and hits `no_action` because the model never emits
a tool call. With `--eywa-python`, the same model on the same task
correctly identifies that arithmetic is needed and routes it through
Python. The binding constraint shifts from "modality mismatch" to
"step budget" — a different problem entirely.

### What this means for the thesis

The Eywa lens reframes the H1 picture once more:
- Recursion (vertical RCS) tests: does scaffolding ABOVE L0 help?
- Eywa tests: does L0 ITSELF need to be heterogeneous (language + non-LLM compute)?

Per-task data from the gemma4 bench showed 3 of 5 REFERENCE tasks were
modality-mismatched. The Eywa hint addresses this without any recursion
change — and at gemma4 it does change agent behavior on math. A
follow-up A/B with `max_steps=50` will tell us if the math task actually
solves under the Eywa hint, which would be the cleanest empirical
confirmation that **modality choice at L0 is a binding constraint that
recursion cannot bypass.**

If the magnitude test confirms (math hit rate goes from 0/N to >0/N
with the Eywa hint at full step budget), the practical claim becomes:

> Vertical recursion is a useful scaffold ONLY for language-native tasks.
> For non-language-native tasks (math, planning, retrieval, structured
> search), no amount of recursion compensates for the L0's modality
> mismatch — only Tsaheylu-bond access to non-LLM compute does.

This is an entirely separate axis of intervention from RCS recursion,
and it's testable cheaply ($0, ~30 min wall) right now.

## gemma4-8B local-bench result (BRO-945 weak-L0 closure)

After Path 2 hit API credit exhaustion, PR #36 shipped a real `OllamaReasoner`
to enable $0 local runs on any tool-call-capable model. PR #37 added the
Eywa-style `--eywa-python` modality hint flag. PR #38 ran the first
local-only bench: **REFERENCE_SUITE × 4 conditions × 3 epochs × 3 repeats
× gemma4:8b × max_steps=20 = 180 episodes, ~8h wall, $0**.

### Result

| Condition | pass^3 | pass@3 | bootstrap CI |
|---|---|---|---|
| flat | 0.054 | 0.769 | [0.244, 0.511] |
| +autonomic | 0.054 | 0.769 | [0.244, 0.533] |
| +meta | 0.045 | 0.742 | [0.222, 0.511] |
| **full** | **0.064** | **0.794** | [0.267, 0.533] |

Per-condition Δ vs flat (pass^3): [+0.000, −0.009, **+0.010**] for
[+autonomic, +meta, full]. The signal is tiny and the CIs heavily overlap
— **not statistically significant at n=1 seed.** But the directional
ordering matches what we'd expect if gemma4 were the "weak L0" the
bitter-lesson interpretation predicts:

- **full > flat** by +0.010 pass^3 / +0.025 pass@3 — recursion provides a
  small positive nudge
- **+autonomic = flat** — L1 mode-switching alone doesn't move the needle
- **+meta < flat** by −0.009 — L2's rule injection at this small N is
  marginally hurting (shadow eval correctly NoOp'd most candidates per the
  log: "L2 epoch 0 → NoOp (unparsed_or_noop)")

### Per-task pattern (qualitative observation from the live log)

| Task | Per-task hit rate | Diagnostic |
|---|---|---|
| `math-multi-step` | 0% across all conditions | **Modality mismatch** — gemma4 rambles in tokens about time arithmetic, hits no_action abort. Recursion can't fix this. |
| `code-bugfix` | ~50% | language-native; fluctuates with temperature |
| `logic-zebra` | ~100% | language-native constraint puzzle gemma4 nails reliably |
| `closed-book-qa` | partial only | retrieval modality |
| `planning-hanoi` | mixed | structured-search modality; long episodes |

**Three of five tasks are modality-mismatched.** Recursion (vertical or
horizontal) sits on top of an L0 that fundamentally cannot solve them
without offloading to non-language compute. This is exactly Eywa's claim
(arXiv:2604.27351): language-only L0 is the binding constraint, not the
control structure.

### What this changes about the H1 verdict

The H1 verdict in this document so far has been:
- ❌ Refuted at Haiku × HARDER
- ❌ Refuted at Sonnet × HARDER (recursion HURTS, statistically)
- ⚠️ Directionally supported at Opus × HARDER (3/3 seeds, n=3 inconclusive)
- 🚫 Untestable at Haiku × SWE × max_steps=50 (capacity floor)

Adding gemma4-8B × REFERENCE × 1 seed:
- ⚠️ **Directionally supported, smallest measured tier** (+0.010 pass^3)

**The 4-tier picture (Haiku → Sonnet → Opus → gemma4-8B local):** the
relationship between recursion and capacity is NOT monotone. Sonnet hurts.
Opus and gemma4-local both nudge positive but at different magnitudes
(Opus: +0.13 large; gemma4: +0.01 small). The most charitable reading: at
the tails (very strong or very weak L0), recursion provides marginal
help. In the middle (Sonnet), it actively hurts.

### Open follow-ups directly enabled by this bench

1. **Multi-seed gemma4 bench** (3 seeds × 4 conditions × 180 ep = 540
   episodes, ~24h wall, $0). Tightens CIs and either confirms or refutes
   the gemma4 directional signal at proper power.
2. **`--eywa-python` A/B at gemma4 × math-multi-step** (~30 min wall, $0).
   Tests Eywa's claim directly: does the Python-tool nudge cure the 0%
   math hit rate? Hypothesis: control = 0/N, treatment > 0.
3. **gemma4 × HARDER suite** (10 tasks × 4 conditions × 1 seed = 40
   episodes, ~3h wall, $0). HARDER's calibration vs gemma4 capacity is
   unknown; expected to be HARDER below the floor (math/planning), but
   could surface different patterns.

## Step-budget step-up + Sonnet attempt (BRO-946 phase 3 — partial)

After PR #34's pilot showed Haiku × max_steps=50 below the floor, this phase
tested two separate hypotheses in parallel: (a) step-up to max_steps=150 at
Haiku (Path 1), and (b) tier-up to Sonnet at max_steps=50 (Path 2). A
parallel agent simultaneously scaffolded the BRO-947 `life-perturb` Rust
crate (life PR #1088) — the only path to closing the construct-validity
gap with the paper.

### Path 1: Haiku × max_steps=150 — first non-zero SWE-bench result

| Condition | pass^1 | Cost | Notes |
|---|---|---|---|
| flat | **0.250** (1/4) | $6.08 | `psf__requests-3362` solved in 83 steps |
| +autonomic | 0.000 (0/4) | $5.19 | Lost the solve flat had |
| +meta | 0.000 (0/4) | $6.21 | Lost the solve too; L2 → NoOp (shadow eval gated) |
| full | **0.250** (1/4) | $6.88 | Re-found the solve in 54 steps (faster than flat) |

**Headline**: Per-condition Δ vs flat = [−0.25, −0.25, 0.00] for [+autonomic,
+meta, full]. **Recursion at intermediate stacks (L1-only, L1+L2) hurts;
full stack matches flat.** The "U-shape" is striking but n=1 paired observation
per condition can't distinguish signal from per-instance variance.

Cost: $24.36 (initial $11.28 + retry $13.09 because the first attempt's
+meta/full died on a transient API connection error).

#### What's confirmed by Path 1

- The PR #34 pilot null was a step-budget artifact, not a hard floor.
  Haiku CAN solve some SWE-bench-Lite instances given enough bash room.
- Step budget more than tripled (50 → 150) to unlock 1 solve out of 4.
  Marginal returns from more steps are real but limited at Haiku tier.
- The recursion overhead pattern from PR #34 holds: ~$5–$7 per condition,
  spread is small relative to total cost.

#### What's NOT confirmed (small-N caveats)

- The flat-and-full-but-not-recursion-middle pattern at n=1 paired could
  be: (a) real "L1 mode-switch noise + L3 recovery" dynamics, (b) random
  task-level variance (only requests-3362 is solvable in this configuration
  for Haiku), or (c) noise from temperature=1.0 sampling.
- A faithful test needs ≥3 seeds × the same 4 instances. Cost projection:
  ~3× this run = ~$70 at Haiku × 150 steps.

### Path 2: Sonnet × max_steps=50 — INCOMPLETE (credit exhaustion)

The Anthropic API credit balance ran out mid-`flat` condition:

| Condition | Status | Notes |
|---|---|---|
| flat | partial (2/4 episodes ran) | flask=0.00 (10 steps), pylint=0.00 (43 steps), then credit error |
| +autonomic | invalid | API connection errors on all 4 episodes |
| +meta | invalid | API connection errors on all 4 episodes |
| full | invalid | API connection errors on all 4 episodes |

Total Path 2 spend: $3.19 (essentially wasted). **Path 2 needs full re-run
once credits refresh.**

### Parallel workstream: BRO-947 life-perturb scaffold (life PR #1088)

While the live runs were executing, a worktree-isolated agent scaffolded
the `life-perturb` Rust crate. Deliverables:

- 340-line design spec at `core/life/docs/superpowers/specs/2026-05-04-life-perturb-design.md`
- New crate at `core/life/crates/life-perturb/` with: `Cargo.toml`, public
  trait surface (`Perturbation`, `Injector`, `LambdaEstimator`), data
  structs, error types, smoke test
- 12/12 unit tests pass; `cargo check`, `cargo clippy --tests -- -D warnings`,
  full workspace check all green
- Bonus: working OLS log-linear `fit_recovery` (recovers λ=0.5 from synthetic
  exp(−0.5·t) trace to <1e-6) — not just a stub
- Linear comment posted on BRO-947 (id `2aa9d347-7b66-48ac-8553-4328e5693268`)

Implementation phasing per the spec:
- v0.1: sandbox-only L0 + L1 + L2 perturbations (1 week impl)
- v0.5: single-level closed-loop validation (~3 weeks)
- v1.0: all 4 levels + cross-validation against paper analytic λᵢ (~3 months)

The crate compiles + tests cleanly. The next agent can pick up v0.1
implementation cleanly with the spec and trait surface as guide.

### Open follow-ups

1. **Path 2 full re-run** at Sonnet × max_steps=50 once credit refreshed
   (~$50, ~2h). Tests whether the PR #31 Sonnet "recursion hurts" pattern
   replicates on SWE-bench long-horizon.
2. **Path 1 N=3 seeds** at Haiku × max_steps=150 to disambiguate the
   "+autonomic loses solve, full recovers" pattern from per-instance
   variance (~$70, ~3h).
3. **BRO-947 v0.1 implementation** — first level (L0) of perturbation
   injection on the autonomic daemon. Spec + scaffold ready in life
   PR #1088.

## SWE-bench-Lite pilot result (PR #34 / BRO-946 phase 2)

The smoke (PR #32) validated the adapter pipeline. The pilot tests the actual
recursion thesis: **does any recursion condition beat `flat` on SWE-bench
when the L0 model is real-world-deployable but capacity-limited?** Run with
the cheapest defensible scope: 4 hand-curated instances × 4 conditions
(flat / +autonomic / +meta / full) × 1 seed × Haiku L0/L1 × Sonnet L2/L3 ×
`max_steps=50` × `max_cost_usd=5.0`.

### Headline

| Condition | pass^1 | Total cost | Mean steps | Mean wall |
|---|---|---|---|---|
| flat | **0.000** | $3.67 | 48 | 150s |
| +autonomic | 0.000 | $3.10 | 44 | 114s |
| +meta | 0.000 | $3.29 | 45 | 136s |
| full | 0.000 | $3.41 | 46 | 124s |

**Total: $13.46, 2218s wall (~37 min). All 16 episodes scored 0.0.**

Per-condition Δ vs flat: +0.000 across the board — there's nothing to
interpret because **none of the 16 episodes solved any instance**.

### What this tells us

1. **The bottleneck is L0 capacity, not strategy.** Haiku at `max_steps=50`
   on real SWE-bench-Lite bugs is below the floor — the model can't
   generate a passing patch within the bash-step budget regardless of L1
   mode-switching, L2 rule injection, or L3 governance. The recursion
   stack sits on top of an L0 that simply can't get there.
2. **Recursion overhead at SWE-bench scale is negligible.** Cross-condition
   cost spread is ~$0.50 (within ~15% of flat). Sonnet L2 + shadow eval
   adds little on top of Haiku L0 because the L0 plant aborts before L2
   has anything substantive to react to.
3. **The smoke result generalizes.** PR #32's 0/2 on Haiku × flat × 50
   steps wasn't a sample fluke — it's a robust ceiling. Pilot saw 0/4 at
   flat AND 0/4 at full. n=4 paired observations with Δ=0 is informative,
   not noise.

### What the pilot does NOT tell us

- **Whether recursion helps when L0 can sometimes solve.** Need a regime
  where flat scores ≥1 to test if recursion adds. Three paths:
  - **Tier-up L0**: Sonnet × max_steps=50 likely solves 30–50% based on
    public reports. Cost projection: ~3× pilot ≈ $40.
  - **Step-up budget**: Haiku × max_steps=150 gives the agent ~3× more
    bash trajectory. Cost ~3× pilot ≈ $40.
  - **Easier benchmark**: SWE-bench Verified has very-easy instances
    (~80%+ baseline). Cost similar.
- **Whether the directional Opus result from PR #31 (recursion HELPS at
  Opus on HARDER) replicates on SWE-bench.** Opus L0 × SWE-bench would be
  the cleanest test but cost ~15× pilot ≈ $200.

### Recommendation

**Don't scale this configuration.** A Haiku × 50-step bench with N>4 won't
generate signal — just more 0.0s at higher cost. The pilot is a complete
result for this setup.

Three viable next experiments, ordered by ROI:

1. **Step-budget step-up (lowest cost, most direct)**: Haiku × max_steps=
   150 × same 4 conditions × same 4 instances. ~$40, ~2h. Tests "does
   recursion help when the L0 has more bash room?"
2. **Tier sweep on SWE**: Sonnet × max_steps=50 × 4 conditions × 5
   instances. ~$50, ~2h. Tests whether the PR #31 Sonnet "recursion
   hurts" pattern replicates on the long-horizon regime.
3. **BRO-947 (`life-perturb`)**: structural — different testbed, real
   perturbation telemetry, paper-magnitude λᵢ measurement. Weeks of work
   but the only path to closing the construct-validity gap with the paper.

The pilot data justifies parking BRO-946 as currently scoped. The full
bench (20 instances × 4 conditions × 3 seeds at Haiku) would cost
$300–$600 and produce 240 zeros. Re-scoping is required before any
further SWE-bench investment.

## Cross-run compounding result (PR #28 / final test)

Closed the structural gap exposed by PR #27's first cross-run experiment: `AppendSystemRule` now writes through to `memory/system_rules.jsonl`. New `L0Plant` instances load these rules on construct. Cross-run iterations now actually compound knowledge.

**5 iterations on the same workspace, full HARDER_SUITE, Opus 4.7 at L2:**

| iter | pass^3 | mean pass rate | rules accumulated |
|---|---|---|---|
| 1 | 0.360 | 0.722 | 0 (cold start) |
| 2 | 0.394 | 0.733 | 1 |
| 3 | 0.343 | 0.711 | 2 |
| 4 | 0.296 | 0.667 | 3 |
| 5 | 0.431 | 0.756 | 4 |

**Δ = +0.072 — within within-iteration variance** (σ_iter ≈ 0.045 → 2σ ≈ 0.09). Bootstrap CIs heavily overlap. **Not statistically significant.**

The 4 accumulated rules are *high quality* — specific, actionable, addressing real failure patterns:
- "Enumerate all required facts before submitting"
- "Cross-check each fact before finalizing"
- "Enumerate ALL constraints as numbered list, verify each"
- "Re-verify each slot satisfies ALL stated constraints"

The mechanism works. Opus generates thoughtful rules. The rules persist correctly and load on the next iteration. Yet pass^k doesn't measurably improve.

**This is the cleanest refutation we can produce at this scale.** No structural excuses remain. The thesis weak form is empirically refuted across:

1. Single-run × 3 seeds (PR #25)
2. Real physics (microgrid PR #2)
3. **Compounding × Opus L2 × disk persistence (PR #28)**

## Cross-testbed validation (microgrid #2 — broomva/microgrid-agent)

The strongest possible test: validate the same hypothesis on a *completely
different* testbed with completely different physics, completely different
metrics, and completely different time scales.

**Microgrid simulation — 3 seeds × 4 conditions × 720h (1 month):**

| condition | diesel_L | unserved_kWh | cycles | l2_acc | l2_vet |
|---|---|---|---|---|---|
| flat | 1124.1 ± 39.2 | 4300.81 ± 25.66 | 1.89 | 0 | 0 |
| +autonomic | 1123.0 ± 38.7 | 4304.40 ± 25.99 | 1.89 | 0 | 0 |
| +meta | 1123.0 ± 38.7 | 4304.40 ± 25.99 | 1.89 | 0 | **69** |
| full | 1123.0 ± 38.7 | 4304.40 ± 25.99 | 1.89 | 0 | **69** |

**Same null result on a completely different physics testbed.** All Δ within 0.1% of flat. Shadow eval correctly vetoed 69/69 candidate mutations on each of `+meta` and `full`. The recursive structure provides safety (via shadow eval) but no measurable performance gain — this time on a real physical control problem with hard-currency metrics.

**This is dual-testbed convergence on the H1 refutation.** The thesis isn't merely refuted on text-task pass rate — it's refuted on diesel liters, CO2, and battery cycles. Different testbed, different physics, same answer.

### Construct-validity finding from microgrid

The cloud-burst perturbation experiment for λ̂_0 produced ≈0 instead of the paper's 1.45/s. **Reason: the simulation's 1-hour timestep cannot resolve sub-second recovery dynamics.** To validate paper-magnitude λᵢ values, we'd need either:
1. Sub-second simulation (not currently available; would require simulation rewrite)
2. Real-hardware kernel telemetry from the deployed Rust controller in Inirida/Choco/Vaupes pilot sites
3. Workstream A (`life-perturb`) on Life runtime — the right testbed for paper-magnitude λᵢ measurement

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

**Status: TIER-DEPENDENT.** Refuted at Haiku and Sonnet. Inconclusive (directionally supported) at Opus.

**Haiku baseline — PR #25 bench (3 seeds × 4 conditions × 90 eps × HARDER_SUITE):**

```text
flat       mean=0.357 ± 0.055    [0.282, 0.413]
+autonomic mean=0.343 ± 0.013    Δ=−0.014  (within 2σ_flat = 0.110)
+meta      mean=0.325 ± 0.052    Δ=−0.032  (within noise)
full       mean=0.277 ± 0.018    Δ=−0.080  (within noise but trending HURTS)
```

At Haiku, the noise floor is too wide to declare any conclusion — recursion neither
significantly helps nor hurts.

**Sonnet — PR #31 bench (3 seeds × 4 conditions × 90 eps × HARDER_SUITE), L0/L1=Sonnet, L2/L3=Opus:**

```text
flat       mean=0.505 ± 0.010    [0.491, 0.512]   ← strikingly tight σ
+autonomic mean=0.420 ± 0.039    Δ=−0.085  (✓ above 2σ_flat = 0.020 — significantly HURTS)
+meta      mean=0.427 ± 0.046    Δ=−0.078  (✓ above noise — HURTS)
full       mean=0.431 ± 0.086    Δ=−0.074  (✓ above noise — HURTS)
```

The Sonnet flat baseline is unusually tight (σ=0.010, 5× narrower than Haiku). All three
recursion conditions cross the 2σ noise band. **At Sonnet, recursion measurably hurts.**
This is the bitter lesson holding cleanly.

**Opus — PR #31 bench (3 seeds × 4 conditions × 90 eps × HARDER_SUITE), L0/L1=Opus, L2/L3=Opus:**

```text
flat       mean=0.495 ± 0.079    [0.413, 0.602]   ← variance balloons
+autonomic mean=0.495 ± 0.071    Δ=−0.000  (within noise; L1 mode-switching = neutral)
+meta      mean=0.636 ± 0.133    Δ=+0.141  (within 2σ_flat=0.158 but 3/3 seeds positive)
full       mean=0.626 ± 0.118    Δ=+0.131  (within 2σ_flat=0.158 but 3/3 seeds positive)
```

At Opus, the per-seed variance is high (σ=0.079) because Opus is at the edge of
HARDER_SUITE's task distribution — it solves most tasks but occasionally fails one
unrecoverably, and pass^3 is binary-per-task. **Despite the wide CI, +meta and +full
both consistently beat flat across 3/3 seeds.** Sign test: p=0.125 (not formally
significant at α=0.05 with n=3).

The directional reversal between Sonnet and Opus is the key finding. The bitter-lesson
prediction "scaffolding helps weak / hurts strong" is REFUTED — recursion hurts at the
"intermediate" tier (Sonnet) and helps at the "strong" tier (Opus).

**Implication for the original H1:** The thesis is not a single binary claim — it's
tier-conditional. At Opus tier, *the apparatus tested is at the edge of supporting
recursion*. The next clean test would be `--paper` mode (n=20 seeds) at Opus to lock in
a paired-bootstrap p-value.

H1 remains untested under:
- Longer time scales (Life multi-day runs)
- Harder benchmarks where L0 alone fails most of the time (SWE-bench Lite — BRO-946)
- Different L2 surface (helper promotion only, no rule injection)
- A `--paper` mode run at Opus tier (n=20, ~$420 — would convert directional to formal)

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
```text
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

**Update from PR #31 capacity sweep:**

Sonnet cross-seed means (3 seeds, HARDER):
```text
flat       = 0.505 (best)
+meta      = 0.427
full       = 0.431
+autonomic = 0.420 (worst)
```

Opus cross-seed means (3 seeds, HARDER):
```text
+meta      = 0.636 (best)
full       = 0.626
flat       = 0.495
+autonomic = 0.495 (tied with flat)
```

The strong-form prediction `full > +meta > +autonomic > flat` does NOT hold at any tier.
At every tier `+autonomic` is among the worst — L1 mode-switching alone is consistently
neutral or harmful. At Opus, `full ≈ +meta` and both > flat, suggesting L3 governance
adds nothing detectable beyond L2 at the 90-episode scale (L3 only fires 1× per epoch).
The empirical ordering is more like `[+meta ≈ full] > flat > +autonomic` at Opus and
`flat > [+meta ≈ full ≈ +autonomic]` at Sonnet.

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

```text
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
