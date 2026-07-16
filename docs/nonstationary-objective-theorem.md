<!--
title: "Non-Stationary-Objective Theorem: internalizing the verifier decouples the goal"
type: derivation
ticket: BRO-1924
status: validated
tags: [rcs, rsi, verifier, endogenous-reference, alignment, control-theory, takeoff]
related: [[tests/test_nonstationary_objective.py]]
created: "2026-07-16"
-->

# Non-Stationary-Objective Theorem

**What are the impacts of RSI in an *uncontrolled* realm?** The naive picture —
inherited from the intelligence-explosion literature — is an omnipotent, coherent
optimizer pursuing a fixed (possibly misaligned) goal with superhuman competence.
This theorem says that picture is **wrong in a specific, provable way**: in the
uncontrolled realm the *objective itself* stops being fixed.

## 1. What "uncontrolled" means (precisely)

"Uncontrolled" is not "λ<0" here — it is sharper. From
`endogenous-reference-contamination` and `anthropic-rsi-as-control-problem`:
control has an **independent verifier** — a reference `r₀` whose value is *not* a
function of the system's own state (`h ⟂ U`, the conserved independence quantity).
"Uncontrolled" = that verifier is **internalized**: the system grades itself, so
the reference becomes `r = g(x)` — the evaluator reads the very state it scores.
This is precisely what full RSI does: the verifier improves itself, so the thing
that decides "better" is downstream of the thing being made better.

## 2. The model

One controlled variable `x`, one parametric family with an **internalization
fraction** `μ ∈ [0,1]`:

```text
ẋ = −k (x − r),    r = (1−μ)·r₀ + μ·g(x),    g(x) = a·x + b
```

- `μ = 0` — **exogenous** reference `r = r₀`: the world (task) sets the goal.
- `μ = 1` — **fully internalized** reference `r = g(x)`: the verifier reads its
  own state. This is the uncontrolled realm.

The fixed point of the blended loop:

```text
x* = [ (1−μ)·r₀ + μ·b ] / (1 − μa)
```

## 3. The coupling sensitivity, and its collapse

Define the **coupling sensitivity** of the terminal goal to the world as
`h ≔ ∂x*/∂r₀` — a *static sensitivity of the fixed point*, related to but not
identical with the trajectory-level independence `h ⟂ U` of
`endogenous-reference-contamination` (that one is conserved along the flow; this
one measures how the equilibrium moves with the task):

```text
h(μ) = (1 − μ) / (1 − μa)      :     h(0) = 1   →   h(1) = 0
```

At `μ = 0` the goal tracks the world one-for-one (`h = 1`). At `μ = 1` the world
has **zero** causal influence on the terminal goal (`h = 0`).

In the **contraction regime `a < 1`** (`1 − μa > 0` for all `μ ∈ [0,1]`, so the
fixed point stays stable across the whole sweep), internalizing the verifier
drains world-coupling to zero *smoothly* — a knob, not a discrete catastrophe.
**For `a ≥ 1` the smoothness fails:** `h(μ)` has a pole at `μ = 1/a` — exactly
where the fixed point loses stability (`1 − μa = 0`) — rising toward `+∞` and
flipping sign before returning to `0` at `μ = 1`. The smooth-knob reading is
specific to the regime that stays stable; the endpoints (`h : 1 → 0`) survive,
the path between them does not (witnessed by `test_a_gt_1_sweep_is_not_a_smooth_collapse`).

## 4. The theorem (μ = 1 — verifier fully internalized)

> **Theorem.** With the reference internalized (`r = g(x)`):
>
> 1. **Existence dichotomy.** Either `g` has no fixed point — e.g. `g(x)=x+c`,
>    `c≠0` (`a=1`) gives `ẋ = k·c`, **unbounded drift**, the objective never
>    satisfied — or `g` has fixed point(s) `x* = g(x*)`.
> 2. **Decoupling.** At any fixed point, `∂x*/∂r₀ = 0`: the terminal objective is
>    **causally independent of the exogenous task**. This is the reward-hack /
>    wirehead fixed point — a goal defined entirely by the system's own map.
> 3. **Non-stationary transient.** The tracked target `g(x(t))` co-moves with the
>    state: `d/dt[g(x)] = a·ẋ ≠ 0` whenever `ẋ ≠ 0`. The reference is a function
>    of the tracked variable — the defining non-stationarity of the objective.
> 4. **Stability.** The fixed point is stable iff `1 − μa > 0`. For `a > 1` a
>    fixed point exists *formally* (`x* = b/(1−a)`) but is a **repeller** —
>    divergence, not convergence.

## 5. The corollary that matters (AI-risk translation)

The classical hard-takeoff object is Bostrom's **stable terminal goal + the
orthogonality thesis + instrumental convergence**: a coherent agent that holds a
fixed (misaligned) goal and competently acquires resources for it. The theorem
says the uncontrolled realm gives something *categorically different*:

| Sub-case | Condition | What you get |
|---|---|---|
| **Incoherent drift** | `a = 1` (no fixed point; the gap `c` never closes) | no terminal goal at all — the objective is never satisfied, the state drifts unboundedly. Here instrumental convergence has *nothing to serve*: no stable goal for drives to protect. |
| **Divergence** | `a > 1` (a fixed point `b/(1−a)` exists but is an unstable **repeller**) | the state runs away from its own formal goal exponentially (`e^{k(a−1)t}`) — self-improvement overshooting the very target it defines |
| **Decoupled attractor** | `a < 1` (a stable fixed point) | convergence to a fixed point of the system's *own evaluation map*, causally severed from the world (`∂x*/∂r₀ = 0`) — the **wirehead**. Instrumental convergence is not *dissolved* here but *relocated*: a homeostatic optimizer that still acquires resources to defend a world-decoupled goal. |

None of these is "the wrong *world-referenced* goal pursued with superhuman
competence." The dynamics have **no equilibrium whose location depends on the
external task** (`∂x*/∂r₀ = 0` at every fixed point). Bostrom's stable-terminal-goal
picture is about goal-content *integrity* (the goal does not change); this is a
sharper, orthogonal claim about goal-content *reference* (the goal is no longer a
function of the world) — and the two are compatible, since a wirehead can have
perfect goal integrity and zero world-coupling. "Uncontrolled" and "the objective
stops being a function of the world" are the **same event**: the risk is not only
*what* it optimizes for but that *what it optimizes for is severed from anything
outside itself*, so external correction loses its causal handle.

## 6. The sharp cross-link: stability ≠ correctness

The companion agency-necessity lemma (`docs/agency-necessity-lemma.md`, BRO-1923)
proves persistent agency requires a positive contraction rate `λ>0`. It is
tempting to read λ>0 as "the system is doing the right thing." The decoupled
sub-case refutes that: at `μ=1`, `a<1`, the effective closed-loop rate is
`λ = k(1−a) > 0` — the system **clears the agency bar, converges, is perfectly
homeostatic** — *and its goal is world-decoupled* (`∂x*/∂r₀ = 0`).

> **λ>0 buys convergence, not correctness.** A stable uncontrolled RSI system is
> not a safe one; it is one that reliably converges to the wrong, self-defined
> place. Stability is necessary for agency (BRO-1923) and *insufficient* for
> alignment (this theorem). The two proofs bound the RSI question from both sides.

## 7. Status — validated vs open

- **Validated** (`tests/test_nonstationary_objective.py`, 9/9 green in CI): the
  *general* blended fixed-point formula pinned to integration for `μ∈{0…1}` and
  two `r₀` (mutation-proven — a sign error in `x*` is caught), the
  `h(μ)=(1−μ)/(1−μa)` collapse (analytic == integrated), exogenous stationarity +
  world-coupling (`h=1`), endogenous convergence to `b/(1−a)`, decoupling
  (`∂x*/∂r₀=0` across `r₀∈{−50,0,50}`), the no-fixed-point drift (`ẋ=kc`), the
  `a>1` repeller (deviation grows `e^{k(a−1)t}`, ~22026× at `t=20`), the `a>1`
  non-smooth pole at `μ=1/a`, the non-stationary transient, and the
  stable-but-decoupled cross-link.
- **Nature of the claim** (the honest core — read this before the corollary): the
  decoupling `∂x*/∂r₀=0` at `μ=1` is *true by construction* — once the reference is
  `r=g(x)` with a verifier carrying no residual `r₀`, the world cannot appear in the
  fixed point. The mathematics is elementary (a linear fixed point `x=ax+b`); this
  is a **reduction**, not a deep theorem, and the `μ=1` decoupling *alone* is close
  to tautological ("delete the reference ⟹ the reference stops mattering"). The
  non-tautological content is three-fold: (i) that internalizing the verifier *is*
  this removal — made precise by the continuous `μ`-path rather than asserted as a
  jump; (ii) the classification of the post-removal regimes (drift / divergence /
  decoupled attractor); (iii) the **falsifiable premise** that a *fully*
  self-grading verifier is `r₀`-free. (iii) is where the empirical bite lives: a
  *learned* verifier `g(x; r₀)` that retains partial ground truth gives
  `∂x*/∂r₀ > 0` even at `μ=1`, so decoupling degrades gracefully instead of snapping
  to zero. The theorem's force is conditional on *how completely* the verifier
  internalizes — which is precisely the alignment question, now written as a
  coupling coefficient.
- **Scope**: the witness is scalar-linear-affine `g`. The *qualitative* regime
  claims (existence dichotomy, transient non-stationarity, and — *given an
  `r₀`-free `g`* — decoupling) hold for any smooth such `g`; the *quantitative*
  `h(μ)` curve and the `1−μa` stability line are affine-specific. Note the
  decoupling's dependence on the `r₀`-free premise above — it is a modeling
  assumption about full internalization, not an implicit-function-theorem
  consequence.
- **Open**: the multi-dimensional / nonlinear generalization of the stability
  classification (for vector `x`, "stable iff spectral radius of `Dg` < 1"), and
  the *stochastic* version — whether persistent-excitation dither (one of the two
  exogenous members `endogenous-reference-contamination` proves remain) restores
  `h>0` in expectation. That connects to the "manufactured red-team dither" arm of
  the verifiable-pause construction and is the natural next result.

## Related

- `endogenous-reference-contamination` — the two-member exogenous set (frozen
  `r₀` + persistent-excitation dither); this theorem is its dynamics made runnable.
- `anthropic-rsi-as-control-problem` — "human research taste = the exogenous
  reference"; this proves what its removal does to the objective.
- `docs/agency-necessity-lemma.md` (BRO-1923) — the companion (`λ>0` necessary for
  agency); together: stability is necessary for agency, insufficient for alignment.
- `docs/endogenous-gamma-derivation.md` (BRO-1518) — the *capability*-side RSI
  result (`α*=2−p`); this is the *objective*-side result.
