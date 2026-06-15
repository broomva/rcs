---
title: "Endogenous-γ: controllability of recursive capability growth"
type: derivation
ticket: BRO-1518
status: conjecture
tags: [rcs, rsi, intelligence-explosion, stability, endogenous-gamma, controllability]
related:
  - "[[tests/test_endogenous_gamma.py]]"
  - "[[data/parameters.toml]]"
created: 2026-06-14
---

# Endogenous-γ: controllability of recursive capability growth (BRO-1518)

The formal model of recursive self-improvement / "intelligence explosion" *within*
the RCS stability budget. Companion to the runnable witness
[[tests/test_endogenous_gamma.py]]. Graduation target: a P2-EGRI section or a short
standalone paper, *Controllability of Recursive Capability Growth*.

## 1. The coupled system

In P0, `γ` (the nominal decay rate, Assumption `ass:decay`) is a **constant** — the
substrate's contraction capability. To model self-improvement, promote it to a state
variable that grows by self-modification (spending design effort `η`):

```text
dγ/dt = κ · η · γ^α          (RSI kernel; α = returns-to-self-improvement exponent)
```

`α` is the inverse of Bostrom's *recalcitrance*: α<1 diminishing returns, α=1 constant
returns, α>1 increasing returns.

## 2. The cost of tracking a self-improving plant

A controller exploiting capability `γ` must **re-tune as γ grows**, to keep H6
(time-scale separation, `τ_a < c·τ_γ`) valid against an accelerating plant. Both P0
cost channels scale with capability:

- **Switching** (`ass:jump` + dwell): re-tune rate `1/τ_a ~ 1/τ_γ = (dγ/dt)/γ = κη γ^{α−1}`, so switching cost `= ln(ν)·c·κη · γ^{α−1} =: B_s γ^{α−1}`.
- **Adaptation** (`ass:adapt`): if control effort scales as `γ^p` (p = how the cost of *wielding* capability scales with capability), the effort-drift rate is `d(γ^p)/dt = p κη γ^{α+p−1}`, so adaptation cost `= L_θ p κη γ^{α+p−1} =: B_a p γ^{α+p−1}`.

Closed-loop, the homeostatic Lyapunov function `V_p` therefore obeys
`dV_p/dt ≤ −γ_eff(γ) V_p` with the **effective decay**

```text
γ_eff(γ) = γ − B_s γ^{α−1} − B_a p γ^{α+p−1}.
```

`V_p` contracts (homeostasis maintained) iff `γ_eff > 0`.

## 3. The theorem

Factor: `γ_eff/γ = 1 − B_s γ^{α−2} − B_a p γ^{α+p−2}`. As `γ → ∞` the binding term is
the **largest exponent**, `max(α−2, α+p−2) = α+p−2` (since p ≥ 0). Hence

> **Controllability threshold.** The contraction certificate `γ_eff` stays positive
> for all large γ iff
> ```text
>     α  <  α*  =  2 − p .
> ```
> α > α*: `γ_eff` flips negative at `γ_crit = (…)^{1/(α+p−2)}` (finite) — **control lost**.
> α < α*: `γ_eff → γ` — **homeostatic control maintained even as capability → ∞**.

**What "iff" means here (necessary-asymptotic, not full closed-loop).** The result is a
statement about the *contraction certificate* `γ_eff`, which is **necessary** for
closed-loop homeostatic stability under growing γ. It is not yet the full closed-loop
theorem — that needs the singular-perturbation argument re-derived for non-stationary γ
(§7, OPEN). So the bold "control maintained / lost" below should be read as "the
certificate holds / fails," which is the asymptotic boundary, not a proof of full
stability. **Marginal line** α = 2−p exactly (measure-zero): there the adaptation term
→ the constant `B_a·p`, so positivity hinges on `B_a·p < 1`; the strict inequality
α < 2−p is what the theorem asserts.

Two endpoints:
- **p = 0** (capability free to wield) → **α\* = 2** — recovers the switching-only budget (the result before adaptation cost is added).
- **p = 1** (verification cost scales with capability) → **α\* = 1**.

## 4. Two thresholds, three regimes

| Line | Value | Meaning |
|---|---|---|
| **Blowup** | α = 1 | α≤1: infinite-horizon growth. α>1: finite-time singularity `t* = γ₀^{1−α}/((α−1)κη)`. |
| **Control-loss** | α = 2−p | below: certificate positive (homeostasis survives). above: certificate flips before the singularity. |

1. **α < 1 — soft / sub-critical:** unbounded growth, infinite horizon, controlled indefinitely. (≈ Christiano slow-takeoff.)
2. **1 ≤ α < 2−p — controlled hard takeoff:** finite-time singularity, **yet `γ_eff → ∞`** — control holds to the end; the binding ceiling is **thermodynamic** (P7 depth-Kardashev), not control. A *controlled singularity*.
3. **α ≥ 2−p — uncontrollable:** `γ_eff` flips negative before the singularity; the cost of control overtakes capability. (≈ Yudkowsky hard-takeoff.)

(For p ≥ 1 the controlled-hard-takeoff window `[1, 2−p)` is empty — control survives only the soft regime.)

## 5. Which p? — the verifier-ceiling argument

`p` is the capability-scaling of control/verification cost. The verifier-ceiling
literature (`self-improvement-verifier-ceiling`: verification ability must keep pace
with generation ability; Meta-Rewarding) implies **verification cost scales with
capability, p ≈ 1**, hence **α\* ≈ 1**:

> Under the verifier-ceiling premise, **only sub-critical (diminishing-returns)
> recursive self-improvement is controllable.** Constant- or increasing-returns
> self-improvement (α ≥ 1) eventually outruns any bounded-rate controller.

This is the formal version of the verifier-evolution frontier: `dγ/dt = κη γ^α` *is*
the verifier self-improvement law, and α<1 is exactly "the verifier can't improve
itself fast enough to outrun its own control cost."

## 6. Why this is a contribution

The takeoff literature (Good 1965, Bostrom, Yudkowsky/Christiano) has only the **α=1**
line (soft vs hard). RCS's budget reveals a **second line at α=2−p** — the exponent at
which the *cost of controlling* a self-improving plant equals the capability gained —
and characterizes the middle regime as control-stable-but-thermodynamically-bounded.
It **unifies the RCS papers**: P0 (the budget) + this (the thresholds) + P7 (the
thermodynamic ceiling that binds regime 2).

## 7. Status — what is proven vs open

**Proven / validated** (this PR):
- The effective-decay certificate `γ_eff` and the threshold `α* = 2−p` — symbolically (binding exponent `α+p−2`) and numerically (`tests/test_endogenous_gamma.py`: certificate flips iff α>2−p across p∈{0,0.5,1}; blowup `t*` matches analytic; p=0→α*=2, p=1→α*=1).

**Open** (the genuine remaining theorem):
- A first-principles plant+controller from which the cost-scaling `p` *emerges* rather than is posited.
- The full **singular-perturbation (Tikhonov) validity** of the budget decomposition under **non-stationary γ** — P0's `thm:recursive` assumes frozen decay per flow-interval; a growing γ violates that, so the composite-Lyapunov argument must be re-derived for the time-varying-γ case. This is the publishable theorem; the present result is its asymptotic certificate.

**Caveat (honest):** the control-loss threshold is **asymptotic in γ** — `γ_crit → ∞`
as `α → (2−p)⁺`, so near-threshold super-critical growth stays controlled up to
*enormous* capability; loss manifests only when α exceeds 2−p enough that `γ_crit` is
reached (at the finite-time singularity for α>1).
