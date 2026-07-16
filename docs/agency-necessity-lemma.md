<!--
title: "Agency-Necessity Lemma: persistent goal-directed behavior requires λ>0"
type: derivation
ticket: BRO-1923
status: validated
tags: [rcs, agency, stability, iss, converse-lyapunov, control-theory]
related: [[tests/test_agency_necessity.py]]
created: "2026-07-16"
-->

# Agency-Necessity Lemma

**Does intelligence *need* control/stability?** The question is ambiguous until
you split *capability* from *agency*, and once split it has a clean two-part
answer — one half a theorem we already hold, the other half this lemma.

## 1. The split (why the question is ambiguous)

| Reading | Object | Needs λ>0? | Source |
|---|---|---|---|
| **Capability** | raw function-power: a forward pass, a predictor, an oracle | **No** | `compute-stability-budget-orthogonality` (9/9) |
| **Agency** | capability harnessed to a *persistent goal under disturbance* | **Yes** | this lemma |

Capability rides the **compute** axis; λ fixes the **time-scale ratios** between
control levels. The stability budget is invariant to uniform time-scaling — you
can buy tempo (compute) without buying any stability, and you can have unbounded
stability at a crawl. The two budgets are orthogonal. A frozen oracle has
unbounded capability and needs no λ: it never acts, so nothing can drift.

So "intelligence needs stability" is **false of the adjective** (*intelligent* =
capable) and **true of the noun** (*an intelligence* = a thing that persists and
acts toward a goal). This lemma proves the second half.

## 2. Setup

State `x ∈ ℝ`, goal `x* = 0`, disturbance `d(t)` with `|d(t)| ≤ D̄`. The plant is
the single integrator — deliberately the *neutrally stable* case, because a
naturally-contracting plant needs no controller and a naturally-diverging one
makes the point even faster:

```text
ẋ = u + d
```

Define **agency** as *ultimate boundedness of the goal error to an ε-ball, for
every admissible disturbance, over the horizon H*:

```text
∃ T ≤ H such that |x(t)| ≤ ε   for all t ∈ [T, H], for all d(·) with |d| ≤ D̄
```

This is the operational content of "keeps pursuing its goal despite the world
pushing back." It is exactly the *input-to-state stability* (ISS) property with
respect to the disturbance.

## 3. The two control laws

**Open-loop** — `u = r(t) = 0` (the reference says "stay at 0"; no term reads the
state):

```text
ẋ = d   ⟹   x(t) = x0 + ∫₀ᵗ d(s) ds
```

Worst-case constant `d = D̄` gives `x(t) = x0 + D̄·t` — **linear, unbounded**
growth. The error leaves the ε-ball at

```text
H* = (ε − |x0|) / D̄
```

and never returns. Open-loop persistence fails past a finite horizon `H*`.

**Closed-loop** — `u = −k·x`, contraction rate `λ = k > 0`:

```text
ẋ = −k x + d   ⟹   x(t) = (x0 − D̄/k) e^{−kt} + D̄/k  →  D̄/k
```

The error contracts into the **ISS ball of radius `D̄/k`**, and this bound holds
for *every* `|d| ≤ D̄` — the constant, sign-aligned disturbance is extremal (it
alone achieves `D̄/k`; the witness confirms a genuinely time-varying square-wave
disturbance lands strictly inside it, and that a sign-aligned adversary
degenerates to constant `+D̄` once the state settles at the edge). Ultimate bound
`ε` is achievable **iff**

```text
k ≥ D̄/ε
```

So a strictly positive contraction rate is **necessary**, and its magnitude is
**bounded below by `D̄/ε`**. As `k → 0⁺`, the ball `D̄/k → ∞` — no feedback is
literally the open-loop case, unbounded.

## 4. The lemma

> **Lemma (agency ⟹ λ>0).** If a system maintains its goal error within an
> ε-ball for *all* disturbances bounded by `D̄ > 0` over an unbounded horizon
> (`H → ∞`), then its **total closed-loop contraction rate must be positive**,
> `λ > 0`. Persistent goal-directed behavior under disturbance is impossible with
> `λ ≤ 0`.
>
> For the drift-dominated plant used here — the integrator, whose *natural*
> contraction is `0` — the whole rate must come from feedback, so `λ = k` and the
> quantitative floor is `k ≥ D̄/ε`. A naturally-contracting plant
> `ẋ = −a x + u + d` (`a > 0`) already supplies `λ = a` and can clear the bar with
> `k = 0`: the lemma requires *some* positive rate, not that it come from the
> controller. The integrator is chosen precisely because it isolates the feedback
> contribution.

The forward direction (λ>0 ⟹ bounded error) is Lyapunov/ISS sufficiency. The
necessity direction (bounded error ∀d ⟹ the system is ISS) is the **converse
ISS-Lyapunov theorem** (Sontag–Wang) — classical; in general it yields a
class-𝒦𝓛 decay bound, which in the linear/scalar case *specializes* to a uniform
exponential rate `λ > 0`. What this lemma *adds* is the sharp boundary that makes
the necessity conditional, below.

## 5. The open-loop escape clause (the contribution)

Necessity holds only for **persistent** agency. Open-loop suffices exactly when
the horizon is short enough relative to the disturbance:

> **Escape clause.** Open-loop (`λ = 0`) keeps the error inside the (closed)
> ε-ball iff `H · D̄ ≤ ε` (with `x0 = 0`, unit disturbance gain; the boundary
> point `H = ε/D̄` sits exactly on the ball). One-shot / short-horizon capability
> is under the threshold; persistent agency (`H → ∞`, any `D̄ > 0`) is over it,
> and only `λ ≥ D̄/ε` closes the gap.

This is why the everyday "intelligence" of a single sharp answer needs no control
theory, while an agent that must *hold* a goal across a long, disturbed horizon
does. The crossover is a concrete inequality, not a vibe: `H* = ε/D̄`.

## 6. Connection to the RCS budget

Here `λ = k` (the integrator contributes no natural contraction, so the whole
rate is the feedback gain) is precisely the **L0/L1 contraction rate** of the RCS
stability budget. Every stable level `i` has `λ_i > 0` (Theorem 1) and therefore a
finite agency ISS ball `D̄/λ_i`. The witness grounds this against the canonical
per-level values in `data/parameters.toml`: the tightest is **L3** (governance,
`λ₃ ≈ 0.006398`), giving the largest ball `D̄/λ₃ ≈ 78` — the level with the least
agency margin, exactly as the narrowest-stability-margin layer should be. The
budget's `λ_i > 0` requirement *is* the per-level agency-necessity condition.

## 7. Status — validated vs classical vs open

- **Validated** (`tests/test_agency_necessity.py`, 9/9 green in CI): the ISS ball
  `D̄/k` (steady state *and* transient, checked against the closed form to 1e-13),
  the necessity threshold `k* = D̄/ε`, the linear open-loop growth and its
  crossover `H* = (ε−|x0|)/D̄`, the `λ→0 ⟹ ball→∞` divergence, that a genuinely
  time-varying (square-wave) disturbance stays strictly inside the extremal `D̄/k`
  ball while the constant aligned disturbance achieves it, and the escape-clause
  boundary `H·D̄ ≤ ε`.
- **Classical** (cited, not re-proved): the converse ISS-Lyapunov theorem
  (Sontag–Wang 1995) — bounded response to all bounded disturbances ⟺ existence
  of an ISS-Lyapunov function (a class-𝒦𝓛 bound). This lemma *applies* it and
  *specializes* it to the linear/scalar case, where the bound becomes a uniform
  exponential `λ>0`; it does not claim the theorem as new.
- **Framed contribution**: the capability-vs-agency split (only agency inherits
  the necessity), the explicit escape-clause inequality `H·D̄ < ε` locating the
  one-shot/persistent boundary, and the identification `λ = ` the RCS per-level
  contraction rate.
- **Open**: the multi-dimensional / nonlinear-plant generalization (the witness
  uses the scalar integrator; the ISS machinery extends but the tightness of
  `k ≥ D̄/ε` is plant-specific). Not required for the qualitative lemma.

## Related

- `compute-stability-budget-orthogonality` — the other half (capability ⟂ λ).
- `open-loop-reference-vs-control-law` — the predictor-vs-feedback distinction
  this lemma quantifies.
- `docs/endogenous-gamma-derivation.md` — the companion result on *self-improving*
  capability (α*=2−p); together they bound what RCS articulates about RSI.
