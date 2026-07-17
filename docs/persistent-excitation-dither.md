<!--
title: "Persistent-Excitation Dither: identifiability restores world-coupling"
type: derivation
ticket: BRO-1930
status: validated
tags: [rcs, rsi, verifier, persistent-excitation, adaptive-control, alignment, control-theory]
related: [[tests/test_pe_dither_identifiability.py]]
created: "2026-07-16"
-->

# Persistent-Excitation Dither restores identifiability

The open thread from the non-stationary-objective theorem (BRO-1924). That result
showed an internalized verifier (`r = g(x)`, `μ→1`) drives the goal's world-coupling
`∂x*/∂r₀` to zero. `endogenous-reference-contamination` proves the set of things
that can hold coupling *positive* has exactly **two members**: a frozen `r₀` (the
`μ<1` fraction BRO-1924 already covered) and a manufactured **persistent-excitation
(PE) dither**. This is the dither arm — the stochastic/identifiability half of the
"verifiable pause."

## 1. The honest crux (what PE dither does and does not do)

At `μ=1` the mean fixed point of `ẋ = −k(x − g(x))` is `g`'s fixed point, and a
zero-mean dither you add and average out **cannot move it**. So:

> **PE dither does not restore coupling by itself.** For any zero-mean probe,
> `∂x*/∂r₀` is still 0.

What PE dither restores is **identifiability** — it makes the hidden world-target
`r₀` *separately recoverable* from the dithered response. A measure-only corrector
(the "second Boss" of `anthropic-rsi-as-control-problem`) can then estimate `r̂₀`
and re-inject it, and *that* restores **separable** control of the world-target
(`∂x*/∂ν → 0` under PE; see §4 — without PE the corrector still moves `x` but drags
the internal nuisance in with it). So the dither is:

- **necessary** — without a persistently-exciting probe the corrector cannot
  steer the world-target *separably*: with no probe at all `r₀` is unobservable
  (`α=0`), and with a merely *collinear* probe the estimate collapses to the blend
  `r̂₀=½(r₀+ν)`, so steering "toward `r₀`" drags the nuisance `ν` in with equal
  weight (§4) — a nonzero-but-inseparable handle, not a blind one, and
- **insufficient** — you also need the corrector that uses the identified `r₀`.

This is exactly why the verifiable pause requires *both* exogenous members: the
frozen `r₀` is the setpoint, the PE dither is what keeps that setpoint *observable*
as the verifier internalizes.

## 2. The classical fact doing the work

**Persistent excitation ⟺ parameter identifiability** (Åström–Wittenmark, adaptive
control). A probe is persistently exciting of order `n` iff its windowed
information matrix is bounded below,

```text
∫_t^{t+T} φ(s) φ(s)ᵀ ds  ≥  α I,   α > 0,
```

and then a least-squares / RLS estimator recovers the true parameters, with
estimator **variance** scaling like `1/α` (so error *magnitude* `∝ 1/√α`). A
rank-deficient (non-PE) probe leaves the parameters unidentifiable. We *apply* this
theorem; we do not reprove it.

*What the witness measures.* §2 states the **windowed** bound `∫_t^{t+T} φφᵀ ≥ αI`;
the runnable witness (§3) instead computes the **full-run averaged** Gram
`(1/n)Σφφᵀ`. For the stationary, periodic probes used here the two agree up to
constants — over an integer number of periods the time-average equals the windowed
integral divided by the window length — so the reported `α` is the windowed PE
bound up to that normalization, not a different quantity.

## 3. The identification model

Two hidden parameters `θ* = [r₀, ν]` (a world-target and a nuisance), so PE **of
order 2** is required:

```text
y(t) = φ(t)·θ* = w₁(t)·r₀ + w₂(t)·ν,     θ̂ = (Σ φφᵀ)⁻¹ (Σ φ y)
```

| Probe | `w₁, w₂` | `Σφφᵀ` | Result |
|---|---|---|---|
| **PE** | `sin t`, `sin 2t` (distinct freqs) | full rank, `α>0` | `θ̂ = θ*` exactly — `r₀` recovered |
| collinear (constant) | `1`, `1` | rank 1, `α≈0` | `r₀` not separable from `ν` |
| collinear (shared sinusoid) | `sin t`, `sin t` | rank 1, `α≈0` | identical channels (linearly dependent) |
| no probe | `0`, `0` | zero | `r₀` fully hidden (the BRO-1924 baseline) |

Not *any* dither works — but the failure mode is regressor-channel **collinearity**
(`w₁=w₂`), not spectral poverty per se: a single sinusoid sampled into two *distinct*
lagged regressors is already persistently exciting of order 2 (Åström–Wittenmark).
What the two failing rows share is `w₁=w₂` (identical channels ⟹ rank-1 Gram), which
is exactly why they cannot separate two unknowns. (Witnessed: `α = 0.47 > 0` for the
PE probe; `α = 0` for both collinear probes and the no-probe baseline.)

## 4. Restored coupling — *separability* is the switch

Add the corrector `ẋ = −k(x − g(x)) − k_c(x − r̂₀)`. Its fixed point:

```text
x* = (k·b + k_c·r̂₀) / (k(1−a) + k_c),
∂x*/∂θ* = [ k_c / (k(1−a) + k_c) ] · (∂r̂₀/∂θ*),   θ* = (r₀, ν).
```

Re-injecting the estimate `r̂₀` restores coupling to `r₀` in **both** cases — the
non-PE estimator is *not* zero. Least squares on a rank-deficient probe returns the
minimum-norm blend `r̂₀ = ½(r₀ + ν)`, so `∂r̂₀/∂r₀ = 0.5`, not `0`. What PE buys is
**separability**:

| Probe | `∂r̂₀/∂r₀` | `∂r̂₀/∂ν` | corrected `∂x*/∂r₀` | corrected `∂x*/∂ν` (contamination) |
|---|---|---|---|---|
| **PE** | `1` | `0` | `0.583` | **`0`** — steers `r₀` alone (clean) |
| non-PE | `0.5` | `0.5` | `0.292` | `0.292` — drags `ν` in equally |

The switch is therefore **not** zero-vs-nonzero coupling; it is whether the
world-target can be steered *without contaminating it* with the internal nuisance
`ν`. Under PE, `∂x*/∂ν = 0` — the corrector moves the goal along the world axis
alone. Without PE, `∂x*/∂ν = ∂x*/∂r₀` — "correcting toward the world" drags the
nuisance in with equal weight. That is the `endogenous-reference-contamination`
failure made precise: **inseparability, not decoupling**.

Witnessed against an **integrated** corrector, not the closed form:
`test_integrated_corrector_pins_correction_fraction` RK-integrates
`ẋ = −k(x−g(x)) − k_c(x−r̂₀)` to its fixed point, confirms it equals the closed form
`(kb+k_c r̂₀)/(k(1−a)+k_c)`, checks `∂x*/∂r̂₀ = 0.583 = correction_fraction()` by
finite difference *through* that integration, and then finite-differences the
end-to-end world sensitivities through the REAL least-squares estimator composed
with the integrated fixed point: `∂x*/∂r₀ = 0.583` (PE) vs `0.292` (non-PE), and
`∂x*/∂ν = 0.000` (PE) vs `0.292` (non-PE). Every `0.583`/`0.292` in this table is
*reproduced* by integrating the ODE and running the estimator, then checked against
these values — not obtained by evaluating the closed-form gain alone.

## 5. The excitation threshold

Reduce to the dynamics of the coupling coefficient itself. Two effects compete,
each independently grounded:

```text
ḣ = −ρ·h  +  β·σ²·(h_max − h)
     └ depletion ┘   └ correction that identification enables ┘
```

- `−ρ·h` — the verifier absorbing its own reference
  (`verifier-independence-depletes-under-optimization`: using a verifier as a
  selection signal erodes it toward zero).
- `+β·σ²·(h_max − h)` — the corrector re-injecting world-coupling, at a rate set by
  the excitation level `σ²` (the PE bound `α`), *because* identification succeeds.

Steady state:

```text
h* = β σ² h_max / (ρ + β σ²).
```

(The `+βσ²` rate is continuous in the excitation because identification *quality*
scales with the conditioning `α ∝ σ²`: §4's clean binary separation is the
high-excitation idealization; finite `σ²` gives partial, noisy separation, hence a
rate rather than a switch.)

- `σ² = 0` ⟹ `h* = 0` — no dither, decoupled: **recovers BRO-1924**.
- `h* ≥ h_min` ⟺ `σ² ≥ ρ h_min / (β(h_max − h_min))` — a **minimum excitation** to
  hold a target coupling: the identification-vs-internalization race, and the PE
  analog of the capability-side threshold `α* = 2 − p` (BRO-1518). Below it the
  dither is absorbed before it identifies (`h* → 0` as `ρ → ∞`); above it coupling
  is sustained.

The threshold is **well-posed only for `0 < h_min < h_max` and `β, ρ > 0`**. Since
`h* = βσ²h_max/(ρ+βσ²) < h_max` for every finite `σ²`, a target `h_min ≥ h_max` is
unreachable at *any* excitation and the formula divides by a non-positive
`(h_max − h_min)` — undefined. (`excitation_threshold` enforces this precondition.)

## 6. Where it sits in the RSI account

This closes the four-corner picture. BRO-1924 said internalizing the verifier
decouples the goal; this says the decoupling is **reversible** — but only by
paying a *specific, quantified* price: an exogenous PE probe strong enough to win
the race against internalization, *plus* a measure-only corrector to use it.
"Keep the system aligned" becomes, in control terms, **keep the world-target
separably steerable** (`∂x*/∂ν = 0`, not merely `∂x*/∂r₀ > 0` — a decoupled
wirehead can have `∂x*/∂r₀ > 0` and still be contaminated). This gives the two
mechanisms that can — frozen `r₀` (BRO-1924) and PE dither (here) — and proves there
are no others (`endogenous-reference-contamination`, two-member exogenous set).
Alignment is engineerable, and this is its cost function.

## 7. Status — validated vs classical vs open

- **Validated** (`tests/test_pe_dither_identifiability.py`, 9/9 green in CI): PE
  probe identifies `[r₀, ν]` exactly (`α>0`); constant / collinear / no probe all
  fail (`α≈0` — rank-deficient, `r₀` inseparable from `ν`); the PE bound `α` governs
  estimation error (a deterministic projection *bias* of magnitude `∝ 1/√α ∝ 1/amp`,
  genuinely nonzero — exponent pinned, not merely monotone); restored steering is
  **separable** (`∂x*/∂ν≈0`) iff PE while non-PE contaminates (`∂x*/∂ν = ∂x*/∂r₀`,
  both `0.292`); the `0.583`/`0.292` sensitivities and `correction_fraction()=0.583`
  are finite-differenced **through the RK-integrated corrector fixed point**
  `ẋ=−k(x−g(x))−k_c(x−r̂₀)` (`test_integrated_corrector_pins_correction_fraction`) —
  witnessed against the ODE, not hardcoded or asserted; the threshold
  `σ*² = ρ h_min/(β(h_max−h_min))` (well-posed for `0<h_min<h_max`; `σ²=0` recovers
  BRO-1924, analytic == integrated); dither absorbed as `ρ→∞`.
- **Classical** (cited, not re-proved): PE ⟺ identifiability and the estimator
  variance bound `∝ 1/α` (⟹ error magnitude `∝ 1/√α`) (Åström–Wittenmark). This
  derivation *applies* it to the alignment framing.
- **Framed contribution**: PE dither as the *separability* (not coupling) rescue —
  the necessary-not-sufficient distinction and the two-Bosses requirement it forces;
  the excitation threshold as the PE analog of `α*=2−p`; the reduction of "stay
  aligned" to "keep the world-target separably steerable (`∂x*/∂ν=0`)."
- **Honest scope**: the coupling macro-dynamics (§5) is a *reduced-order* model —
  `ρ, β` are effective coefficients, each grounded (depletion / identification) but
  not derived from the micro-estimator. The identification witness (§3–4) is the
  micro-grounding of *why* the `+βσ²` term exists.
- **Open**: deriving `β` from the estimator gain and the PE bound `α` (full
  stochastic averaging rigor); coupling the estimator's excitation budget to the
  capability threshold `α*=2−p` (does self-improvement that spends compute on
  capability starve the dither?); the multi-dimensional / nonlinear-`g` case.

## Related

- `uncontrolled-rsi-nonstationary-objective` (BRO-1924) — the decoupling this arm
  reverses.
- `endogenous-reference-contamination` — the two-member exogenous set (frozen `r₀`
  + PE dither); this is the second member made runnable.
- `anthropic-rsi-as-control-problem` — the two-Bosses split (learn-from vs
  measure-only); the corrector here is the measure-only Boss.
- `verifier-independence-depletes-under-optimization` — the `−ρh` depletion term.
- `docs/agency-necessity-lemma.md`, `docs/nonstationary-objective-theorem.md`,
  `docs/endogenous-gamma-derivation.md` — the rest of the RSI account.
