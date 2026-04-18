---
title: "ISS Small-Gain Reformulation of Theorem VI.5 — Analysis"
date: 2026-04-17
author: RCS research
status: working note
scope: N=2 only (per task brief)
tags: [rcs, stability, iss, small-gain, theorem-6.5, assumption-audit]
---

# ISS Small-Gain Reformulation of Theorem VI.5 — Analysis

## 0. Question

Is replacing the composite-Lyapunov Theorem VI.5 with an ISS small-gain
formulation (Dashkovskiy–Rüffer–Wirth 2010; for N=2, Jiang–Teel–Praly 1994)
a **strict generalization**, a **reformulation**, or a **change of
assumptions**?

**Verdict (up front):** it is a **change of assumptions**. ISS small-gain
drops two hypotheses the current theorem silently uses (time-scale
separation and quadratic Lyapunov bounds), but **introduces a new
modelling requirement** the paper does not currently satisfy — explicit
inter-level gain functions γ<sub>ij</sub>. The two stability conditions
(σ<sub>i</sub> > 0 per level vs γ<sub>01</sub> ∘ γ<sub>10</sub> < id)
are formally incomparable in general; they coincide only under
linear-quadratic dynamics with a specific identification.

The rest of this note shows the symbolic work.

---

## 1. Current formulation (Theorem VI.5, composite Lyapunov)

From `latex/rcs-definitions-ieee.tex` §VI.

**Assumption VI.1 (per-level Lyapunov).** For each level ℒ<sub>i</sub>
there exists V<sub>i</sub> : 𝒳<sub>i</sub> → ℝ<sub>≥0</sub> with

> α<sub>i</sub>‖x‖² ≤ V<sub>i</sub>(x) ≤ ᾱ<sub>i</sub>‖x‖².

**Assumption VI.2 (frozen decay).** Holding higher-level variables
constant,

> V<sub>i</sub>(x<sub>k+1</sub>) − V<sub>i</sub>(x<sub>k</sub>) ≤ − γ<sub>i</sub> V<sub>i</sub>(x<sub>k</sub>).

**Assumption VI.3 (coupling bounds).** With V<sub>i</sub> itself
bounding every cross-term:

> |∂V<sub>i</sub>/∂θ · θ̇<sub>i</sub>| ≤ L<sub>θ,i</sub> ρ<sub>i</sub> V<sub>i</sub>
> |∂V<sub>i</sub>/∂d · ḋ<sub>i</sub>| ≤ L<sub>d,i</sub> η<sub>i</sub> V<sub>i</sub>
> Δ<sub>τ</sub> V<sub>i</sub> ≤ β<sub>i</sub> τ̄<sub>i</sub> V<sub>i</sub>
> V<sub>i</sub>(x<sup>+</sup>) ≤ ν<sub>i</sub> V<sub>i</sub>(x<sup>−</sup>)

**Implicit Assumption VI.⋆ (time-scale separation).** Cited in the proof
sketch: "By singular perturbation, each level sees higher levels as
quasi-static." This is what makes "frozen decay" a well-defined
quantity — if levels evolve on commensurable time-scales, γ<sub>i</sub>
is not a clean number.

**Budget & conclusion.**

> σ<sub>i</sub> = γ<sub>i</sub> − L<sub>θ,i</sub>ρ<sub>i</sub> − L<sub>d,i</sub>η<sub>i</sub> − β<sub>i</sub>τ̄<sub>i</sub> − ln(ν<sub>i</sub>)/τ<sub>a,i</sub>

> If σ<sub>i</sub> > 0 for all i, composite χ = (x<sub>0</sub>, …, x<sub>N</sub>) decays
> exponentially at rate ω = min<sub>i</sub> σ<sub>i</sub> with
> V = Σ<sub>i</sub> α<sub>i</sub> V<sub>i</sub>.

**Structural observation.** Every term in σ<sub>i</sub> is bounded by
V<sub>i</sub> (not by V<sub>j</sub> for j ≠ i). This is only
possible because time-scale separation eliminates direct V<sub>j</sub>
→ V<sub>i</sub> gradients, so all inter-level effects have been folded
into the Lipschitz-rate products (L<sub>θ,i</sub>ρ<sub>i</sub>, etc.).

---

## 2. ISS small-gain formulation (reference frame)

### 2.1 Canonical statement

**Dashkovskiy, Rüffer, Wirth (2010):** *Small Gain Theorems for Large
Scale Systems and Construction of ISS Lyapunov Functions.*
*SIAM J. Control Optim.* **48**(6), 4089–4118.
[DOI 10.1137/090746483](https://doi.org/10.1137/090746483).

Key theorems used here:

- **Theorem 5.3** (pp. 4106–4107): construction of a composite
  ISS-Lyapunov function V(x) = max<sub>i</sub> σ<sub>i</sub><sup>−1</sup>(V<sub>i</sub>(x<sub>i</sub>))
  from per-subsystem ISS-Lyapunov functions via an Ω-path of the gain
  operator Γ.
- **Theorem 6.1** (p. 4110, max-form small-gain): if Γ is the gain
  operator (Γ(s))<sub>i</sub> = max<sub>j</sub> γ<sub>ij</sub>(s<sub>j</sub>)
  and id − Γ is positive on ℝ<sub>≥0</sub><sup>n</sup>\{0} (the "cyclic"
  small-gain condition), the interconnection is GAS / ISS.
- **Theorem 8.1** (summation form): analogue with
  (Γ(s))<sub>i</sub> = Σ<sub>j</sub> γ<sub>ij</sub>(s<sub>j</sub>) and a
  matching cyclic condition.

For N = 2 the result collapses to the textbook small-gain theorem
**Jiang, Teel, Praly (1994)**, *Math. Control Signals Systems* **7**(2),
95–120: the composition γ<sub>01</sub> ∘ γ<sub>10</sub> < id on ℝ<sub>>0</sub>
is necessary and sufficient (modulo technicalities) for GAS of the
feedback interconnection.

### 2.2 Per-subsystem ISS-Lyapunov

Each subsystem i admits V<sub>i</sub> satisfying:

> **K<sub>∞</sub> bounds.** α<sub>i</sub>(‖x<sub>i</sub>‖) ≤ V<sub>i</sub>(x<sub>i</sub>) ≤ ᾱ<sub>i</sub>(‖x<sub>i</sub>‖), α<sub>i</sub>, ᾱ<sub>i</sub> ∈ 𝒦<sub>∞</sub>.
> **Max-form dissipation.** V<sub>i</sub>(x<sub>i</sub>) ≥ max<sub>j≠i</sub> γ<sub>ij</sub>(V<sub>j</sub>(x<sub>j</sub>)) ⟹ V̇<sub>i</sub> ≤ −α<sub>i</sub>(V<sub>i</sub>).

or equivalently the **summation form**

> V̇<sub>i</sub> ≤ −α<sub>i</sub>(V<sub>i</sub>) + Σ<sub>j≠i</sub> σ<sub>ij</sub>(V<sub>j</sub>).

### 2.3 Small-gain condition (N = 2)

> γ<sub>01</sub> ∘ γ<sub>10</sub>(s) < s for all s > 0.

Equivalently (symmetric under cyclic rotation): γ<sub>10</sub> ∘ γ<sub>01</sub>(s) < s.

---

## 3. N = 2 symbolic derivation, side by side

Fix a minimal RCS with

- ℒ<sub>0</sub> plant, state x<sub>0</sub> ∈ ℝ
- ℒ<sub>1</sub> controller / adapter, state x<sub>1</sub> ∈ ℝ

Continuous linear coupled dynamics (chosen because it admits both
formulations cleanly; the nonlinear case is where the two genuinely
diverge):

> ẋ<sub>0</sub> = −γ<sub>0</sub> x<sub>0</sub> + L<sub>01</sub> x<sub>1</sub>
> ẋ<sub>1</sub> = −γ<sub>1</sub> x<sub>1</sub> + L<sub>10</sub> x<sub>0</sub>

No jumps, no delay, no external input — this isolates the
adaptation/design coupling. (Delay and jumps are discussed separately
in §4.)

Per-level Lyapunov: V<sub>i</sub>(x<sub>i</sub>) = (1/2) x<sub>i</sub>², so 2V<sub>i</sub> = x<sub>i</sub>².

### 3.1 Formulation A — composite Lyapunov (current)

**Frozen decay (VI.2).** Holding x<sub>1</sub> constant:
V̇<sub>0</sub>|<sub>x<sub>1</sub> frozen</sub> = x<sub>0</sub>(−γ<sub>0</sub> x<sub>0</sub>) = −γ<sub>0</sub> x<sub>0</sub>² = −2γ<sub>0</sub> V<sub>0</sub>.
Budget decay rate: γ̃<sub>0</sub> = 2γ<sub>0</sub>.
Symmetrically, γ̃<sub>1</sub> = 2γ<sub>1</sub>.

**Coupling absorbed into VI.3.** The true ẋ<sub>0</sub> has a cross-term
L<sub>01</sub> x<sub>1</sub>. Writing it as an "adaptation"-style
perturbation to V<sub>0</sub> via Young's inequality with weight ε > 0:

> V̇<sub>0</sub> = −γ<sub>0</sub> x<sub>0</sub>² + L<sub>01</sub> x<sub>0</sub> x<sub>1</sub>
>      ≤ −γ<sub>0</sub> x<sub>0</sub>² + (ε/2) x<sub>0</sub>² + (L<sub>01</sub>²/(2ε)) x<sub>1</sub>²

This is **not** a bound of the form ≤ (L<sub>θ,0</sub>ρ<sub>0</sub>) V<sub>0</sub>: the second term is
V<sub>1</sub>, not V<sub>0</sub>. Getting VI.3 requires **time-scale
separation** — assume ẋ<sub>1</sub> is slow, so x<sub>1</sub> is quasi-static on the
x<sub>0</sub>-timescale, and then the cross-term is absorbed into the
"frozen" drift as a *parameter perturbation*:

> L<sub>01</sub> x<sub>0</sub> x<sub>1</sub> = L<sub>01</sub> x<sub>0</sub> · (x<sub>1</sub> seen as θ) ≤ L<sub>θ,0</sub> ρ<sub>0</sub> · V<sub>0</sub>

with the identification

> **L<sub>θ,0</sub> ρ<sub>0</sub> ≡ L<sub>01</sub> · (sup of x<sub>1</sub> on the slow window) · √(2/ V<sub>0</sub>) / quasi-static bound**

i.e. a heuristic bounding specific to the time-scale-separated regime.
The coupling L<sub>01</sub> x<sub>0</sub> x<sub>1</sub> is **not generically**
≤ c · V<sub>0</sub> without such an assumption — it is ≤ c · √(V<sub>0</sub>V<sub>1</sub>).

**Budget.** Under that (tacit) identification, the current theorem
gives

> σ<sub>0</sub> = 2γ<sub>0</sub> − L<sub>θ,0</sub>ρ<sub>0</sub> (no other costs in this minimal setup)
> σ<sub>1</sub> = 2γ<sub>1</sub> − L<sub>θ,1</sub>ρ<sub>1</sub>

**Composite.** V = α<sub>0</sub> V<sub>0</sub> + α<sub>1</sub> V<sub>1</sub>. Decay rate ω = min(σ<sub>0</sub>, σ<sub>1</sub>).

### 3.2 Formulation B — ISS small-gain

**Per-subsystem ISS-Lyapunov** (summation form, via Young with ε = γ<sub>0</sub>):

> V̇<sub>0</sub> = −γ<sub>0</sub> x<sub>0</sub>² + L<sub>01</sub> x<sub>0</sub> x<sub>1</sub>
>      ≤ −γ<sub>0</sub> x<sub>0</sub>² + (γ<sub>0</sub>/2) x<sub>0</sub>² + (L<sub>01</sub>²/(2γ<sub>0</sub>)) x<sub>1</sub>²
>      = −γ<sub>0</sub> V<sub>0</sub> + (L<sub>01</sub>²/γ<sub>0</sub>) V<sub>1</sub>

So

> α<sub>0</sub>(s) = γ<sub>0</sub> s,   σ<sub>01</sub>(s) = (L<sub>01</sub>²/γ<sub>0</sub>) s.

Symmetrically

> α<sub>1</sub>(s) = γ<sub>1</sub> s,   σ<sub>10</sub>(s) = (L<sub>10</sub>²/γ<sub>1</sub>) s.

Converting summation form → max-form gains (DRW 2010 §3):
γ<sub>ij</sub> := (1+ε) · α<sub>i</sub><sup>−1</sup> ∘ σ<sub>ij</sub>. With α<sub>i</sub> linear this is just

> γ<sub>01</sub>(s) = ((1+ε) L<sub>01</sub>² / γ<sub>0</sub>²) s
> γ<sub>10</sub>(s) = ((1+ε) L<sub>10</sub>² / γ<sub>1</sub>²) s.

**Small-gain condition:**

> γ<sub>01</sub> ∘ γ<sub>10</sub>(s) = (1+ε)² · L<sub>01</sub>² L<sub>10</sub>² / (γ<sub>0</sub>² γ<sub>1</sub>²) · s < s

⟺ in the limit ε → 0:

> **L<sub>01</sub> L<sub>10</sub> < γ<sub>0</sub> γ<sub>1</sub>.**

### 3.3 When do the two conditions coincide?

| Regime | Condition A (both σ<sub>i</sub> > 0) | Condition B (small-gain) |
|---|---|---|
| L<sub>01</sub> = L<sub>10</sub> = L, γ<sub>0</sub> = γ<sub>1</sub> = γ, identifications L<sub>θ,i</sub>ρ<sub>i</sub> = L²/γ | 2γ > L²/γ ⟺ L² < 2γ² | L² < γ² |
| Asymmetric: γ<sub>0</sub> = 0.1, γ<sub>1</sub> = 10, L<sub>01</sub> = 0.5, L<sub>10</sub> = 0.5, identifications as above | σ<sub>0</sub> = 0.2 − 2.5 = −2.3 ❌, σ<sub>1</sub> = 20 − 0.025 > 0 ✅ — **composite fails** | 0.25 < 1 ✅ — **small-gain holds** |
| Asymmetric: γ<sub>0</sub> = γ<sub>1</sub> = 1, L<sub>01</sub> = 5, L<sub>10</sub> = 0.1 | σ<sub>0</sub> = 2 − 25 = −23 ❌ | 0.5 < 1 ✅ — **small-gain holds** |

So small-gain is **strictly more permissive** in the asymmetric-linear
case: it recognises that a fast, heavily damped ℒ<sub>1</sub>
absorbing slow ℒ<sub>0</sub> perturbations still yields a stable
interconnection, whereas the per-level budget fails to detect the
stabilising asymmetry.

Conversely, the per-level budget can pass when small-gain fails if
γ<sub>i</sub> is large but the gain operator has a cycle with ∏γ<sub>ij</sub>
close to 1 — but in the N = 2 linear case this does not occur (any
configuration making σ<sub>i</sub> > 0 for both i also gives
γ<sub>01</sub>γ<sub>10</sub> < 1 under the natural identification above).
**For N = 2 linear, composite ⊊ small-gain.** For N > 2 or nonlinear
gains the relationship is not even a subset relation.

---

## 4. Assumption mapping table

| # | Current (Thm VI.5) | ISS small-gain (DRW 2010 / JTP 1994) | Relationship |
|---|---|---|---|
| 1 | **VI.1** — quadratic bounds α‖x‖² ≤ V ≤ ᾱ‖x‖² | 𝒦<sub>∞</sub> bounds α(‖x‖) ≤ V ≤ ᾱ(‖x‖) | **Strictly stronger (current)**: quadratic ⊂ 𝒦<sub>∞</sub>. Reformulating drops the quadratic restriction. |
| 2 | **VI.2** — frozen decay γ<sub>i</sub> (higher levels held constant) | Per-level ISS: V<sub>i</sub> ≥ max<sub>j</sub> γ<sub>ij</sub>(V<sub>j</sub>) ⟹ V̇<sub>i</sub> ≤ −α<sub>i</sub>(V<sub>i</sub>) | **Incomparable**: "frozen" is conditional on time-scale separation; "ISS dissipation" is conditional on neighbours being small. Neither implies the other. |
| 3 | **VI.3 (adapt)** — \|∂V/∂θ·θ̇\| ≤ L<sub>θ</sub>ρ V | Gain γ<sub>i,i+1</sub>(V<sub>i+1</sub>) encoding "higher-level-commanded adaptation" | **Change of representation**: if θ̇ at level i is commanded by level i+1, the coupling is an explicit gain. If θ̇ is intrinsic (level i's own adaptation loop), it belongs in α<sub>i</sub>. Current paper does not disentangle. |
| 4 | **VI.3 (design)** — \|∂V/∂d·ḋ\| ≤ L<sub>d</sub>η V | Gain γ<sub>i,i+2</sub>(V<sub>i+2</sub>) (design typically lives two levels up) | **Change of representation**: same issue, scoped to the design-level. |
| 5 | **VI.3 (delay)** — Δ<sub>τ</sub>V ≤ βτ̄ V | Delay-ISS via Pepe–Jiang 2006 (*Automatica* 42:1761) or hybrid ISS with τ̄ as dwell-time input | **Strictly weaker (ISS)** for bounded τ̄; **incomparable** for time-varying delays. Current lumps; ISS separates. |
| 6 | **VI.3 (jumps)** — V(x<sup>+</sup>) ≤ ν V(x<sup>−</sup>) | Hybrid ISS small-gain (Cai–Teel 2009, *IEEE TAC* 54:2917; DRW 2010 extends to hybrid networks) | **Same framework**: both use ν with ADT; hybrid ISS small-gain is the direct generalisation. |
| 7 | **Implicit VI.⋆** — time-scale separation / singular perturbation | Not required | **Strictly weaker (ISS)**: ISS small-gain works for levels on commensurable timescales. |
| 8 | **Jump-growth** ν<sub>i</sub> ≥ 1, ADT τ<sub>a,i</sub> | Hybrid ADT small-gain (Cai–Teel) | **Same**: both use Hespanha–Morse ADT. |

**Summary of the mapping.** ISS removes #1 and #7 (strict weakening),
matches #5, #6, #8 (framework-identical), and **reshuffles** #3 and #4
— they are not dropped but they change form. The reshuffling
(assumptions 3–4) is what makes this a change of assumptions rather
than a pure generalisation.

---

## 5. What each formulation needs from the system

| | Composite (current) | ISS small-gain |
|---|---|---|
| **Lyapunov structure** | Quadratic per level, linear combination V = Σα<sub>i</sub>V<sub>i</sub> | Per-level 𝒦<sub>∞</sub>, composite V = max<sub>i</sub> ρ<sub>i</sub>(V<sub>i</sub>) via Ω-path |
| **Dynamics regularity** | Time-scale separation so "higher held constant" is meaningful | None: arbitrary coupled dynamics |
| **Coupling** | Intra-level perturbations: each cross-term bounded by the *same* V<sub>i</sub> it perturbs | Inter-level gains γ<sub>ij</sub> : V<sub>j</sub> → V<sub>i</sub>, with γ<sub>ii</sub> absent |
| **Stability witness** | Scalar σ<sub>i</sub> > 0 per level | Cyclic composition of gains: id − Γ positive definite (N > 2) or γ<sub>01</sub>∘γ<sub>10</sub> < id (N = 2) |
| **Delay handling** | Folded into σ<sub>i</sub> via βτ̄ | Separate: ISS-w.r.t.-delay subsystem + small-gain |
| **Jump handling** | Folded into σ<sub>i</sub> via ln(ν)/τ<sub>a</sub> | Separate: hybrid ISS-Lyapunov + ADT |
| **What gets proven** | Exponential convergence at rate ω = min σ<sub>i</sub> | GAS in general; exponential iff all α<sub>i</sub>, γ<sub>ij</sub> linear |
| **What disappears** | — | Time-scale separation, quadratic bound, explicit composite weights α<sub>i</sub> |
| **What appears** | — | Explicit gain-graph structure Γ = (γ<sub>ij</sub>) |

---

## 6. What is easier, harder, or vanishes under ISS

### Easier under ISS

- **Nonlinear Lyapunov functions.** 𝒦<sub>∞</sub> bounds admit e.g.
  V<sub>i</sub> = log(1+‖x<sub>i</sub>‖²) which the current theorem cannot accommodate.
- **Non-separated timescales.** The homeostatic drive and adapter
  can evolve on comparable time-scales — currently forbidden by
  Assumption VI.⋆.
- **External disturbances.** ISS is *by construction* about
  input-to-state stability. The current theorem is autonomous only.
- **Composition theorems.** DRW 2010 gives a clean way to compose a
  sub-RCS with the rest of the system — the cyclic condition extends
  modularly. Composite Lyapunov doesn't compose without re-tuning the
  α<sub>i</sub> weights.

### Harder under ISS

- **Modelling effort.** Every inter-level coupling must be cast as an
  explicit gain γ<sub>ij</sub>. In the current paper, L<sub>θ,i</sub>ρ<sub>i</sub>
  and L<sub>d,i</sub>η<sub>i</sub> are aggregate Lipschitz constants — who
  perturbs whom is buried.
- **Runtime instrumentation.** The F2 Rust harness observes
  homeostatic state directly and produces a per-level σ<sub>i</sub>
  ≥ 0 gauge. ISS small-gain would require observing the gain operator
  empirically, which is much harder to ground-truth.
- **Proof-by-simulation tests.** The Lyapunov simulation test
  (`tests/test_lyapunov_simulation.py`) integrates the composite V and
  asserts exponential decay. Under ISS, simulation would need to
  verify "whenever V<sub>i</sub> is above the gain of its neighbours,
  V<sub>i</sub> decays" — a conditional statement that is more subtle to
  test.

### Vanishes under ISS

- **The min-over-levels aggregation** ω = min<sub>i</sub> σ<sub>i</sub>.
  Under ISS, the composite rate comes from the spectral-like properties
  of Γ (DRW 2010 Theorem 5.3), not from a pointwise minimum.
  The headline number in the paper (λ<sub>3</sub> = 0.0064) has no direct ISS analogue.
- **The interpretation "L<sub>3</sub> is delay-dominated"** based on
  comparing products in σ<sub>i</sub>. Under ISS there is no per-level
  budget decomposition; instead "what dominates" means "which gain
  γ<sub>ij</sub> is closest to saturating the small-gain condition."
- **The convenient additivity of costs** (adapt + design + delay + switch).
  ISS does not sum these; it composes them through the gain structure.

---

## 7. Verdict (restated with the settling step)

ISS small-gain is a **change of assumptions**, not a strict
generalisation or pure reformulation.

The step that settles this is §3.3: in the asymmetric case γ<sub>0</sub> = 0.1,
γ<sub>1</sub> = 10, L<sub>01</sub> = L<sub>10</sub> = 0.5 (with the natural
identification L<sub>θ,i</sub>ρ<sub>i</sub> ≡ L²<sub>ji</sub>/γ<sub>i</sub>):

- Composite budget: σ<sub>0</sub> = −2.3 → Thm VI.5 **fails**.
- Small-gain: L<sub>01</sub>L<sub>10</sub> = 0.25 < 1 = γ<sub>0</sub>γ<sub>1</sub> → **holds**.

So there exist systems stable under ISS that the composite theorem
rejects → the composite theorem is **not weaker** than ISS. Together
with the fact that ISS requires inter-level gain structure the current
paper does not supply → the two are **incomparable as hypotheses**.

This is exactly "change of assumptions," cell 2 of the question's
classification. (A strict generalisation would require every
composite-stable system to also be ISS-stable under the same
assumptions; a pure reformulation would require logical equivalence.
Neither holds.)

---

## 8. Open questions (to settle before committing)

1. **Inter-level gain extraction.** Given the current Arcan /
   Autonomic / Haima stack, can the adaptation coupling L<sub>θ,i</sub>ρ<sub>i</sub>
   be genuinely decomposed into (a) a gain γ<sub>i,i+1</sub>
   from level i+1 (commanded adaptation) and (b) a self-loop absorbed
   into α<sub>i</sub> (intrinsic adaptation)? The paper currently
   aggregates both. Without this decomposition there is no honest ISS
   statement to make.

2. **Graph topology.** Is the RCS hierarchy a chain (level i
   affects level i+1 only, no back-edge)? If yes, ISS small-gain
   collapses to **cascade stability** (trivial: each level stable in
   isolation + bounded cross-gain ⟹ cascade stable). The small-gain
   condition is vacuous and the whole machinery is overkill. The
   paper's EGRI→L<sub>2</sub> vs homeostatic-drive-back-to-L<sub>1</sub>
   pathway strongly suggests there *are* back-edges — but this needs
   to be established formally before invoking DRW 2010.

3. **Hybrid ADT compatibility.** DRW 2010 is continuous-time.
   Cai–Teel 2009 extend to hybrid systems. Verify that the paper's
   (ν<sub>i</sub>, τ<sub>a,i</sub>) framing maps cleanly onto
   Cai–Teel's hybrid ADT small-gain, specifically whether the
   jump-growth condition ν<sub>i</sub> ≥ 1 with
   ln(ν<sub>i</sub>)/τ<sub>a,i</sub> < (some margin) is compatible with
   the flow-map gain structure ISS requires.

4. **Delay handling.** The current β<sub>i</sub>τ̄<sub>i</sub> term lumps a
   delay-induced Lyapunov growth. The ISS-with-delay literature
   (Pepe–Jiang 2006; Teel 1998) is standard for bounded constant
   delays, but the paper's τ̄<sub>i</sub> appears to be a *supremal*
   delay over a family — this may need iISS or integral-ISS instead.

5. **Runtime instrumentation cost.** Currently `autonomic-core/src/rcs_budget.rs`
   computes σ<sub>i</sub> from homeostatic state with a few arithmetic
   ops. Estimating a gain γ<sub>ij</sub> empirically from trajectories
   is a regression problem (fit γ<sub>ij</sub>(V<sub>j</sub>) s.t.
   V̇<sub>i</sub> ≤ −α<sub>i</sub>(V<sub>i</sub>) whenever V<sub>i</sub> ≥
   γ<sub>ij</sub>(V<sub>j</sub>)). This is both more expensive to run and
   weaker as evidence.

6. **What do we lose in the headline narrative?** The paper's story
   ("λ<sub>3</sub> = 0.0064, delay-dominated") depends on per-level
   budget decomposition. ISS has no analogue. Before reformulating,
   decide whether to keep the budget as a *sufficient condition for
   ISS* (i.e., σ<sub>i</sub> > 0 implies per-level ISS-Lyapunov with
   linear gains, which is honest but demotes VI.5 from theorem to
   corollary) or to replace the narrative entirely.

7. **Which DRW 2010 theorem?** For N = 2, Jiang–Teel–Praly 1994
   suffices and is substantially simpler. For N > 2, DRW 2010 Theorem
   5.3 is needed because 2-system small-gain does not compose into
   network small-gain without the Ω-path construction. If the paper
   stays at N = 2 (plant + meta-controller), cite JTP 1994 and skip
   DRW.

---

## 9. References

- Dashkovskiy, S., Rüffer, B.S., Wirth, F.R. (2010). Small Gain
  Theorems for Large Scale Systems and Construction of ISS Lyapunov
  Functions. *SIAM J. Control Optim.* **48**(6), 4089–4118.
  Theorems 5.3 (Ω-path Lyapunov construction), 6.1 (max-form
  small-gain), 8.1 (summation-form small-gain).
- Jiang, Z.-P., Teel, A.R., Praly, L. (1994). Small-gain theorem for
  ISS systems and applications. *Math. Control Signals Systems*
  **7**(2), 95–120. (Canonical N = 2 result.)
- Sontag, E.D., Wang, Y. (1995). On characterizations of the
  input-to-state stability property. *Systems & Control Letters*
  **24**(5), 351–359. (ISS-Lyapunov definition used here.)
- Cai, C., Teel, A.R. (2009). Characterizations of input-to-state
  stability for hybrid systems. *IEEE TAC* **54**(12), 2917–2927.
  (Hybrid ISS; relevant to the ν<sub>i</sub>, τ<sub>a,i</sub> mapping.)
- Pepe, P., Jiang, Z.-P. (2006). A Lyapunov–Krasovskii methodology for
  ISS and iISS of time-delay systems. *Automatica* **42**(10),
  1761–1766. (Delay-ISS; relevant to βτ̄ term.)
- Hespanha, J.P., Morse, A.S. (1999). Stability of switched systems
  with average dwell-time. *Proc. 38th IEEE CDC*. (Already cited in
  the paper for jump-ADT.)
- Eslami, A., Yu, T. (2026). Control-Theoretic Foundations for Agentic
  AI. arXiv:2603.10779. (Source of the 5-level stability budget the
  current theorem extends.)

---

## 10. Recommendation

Do not reformulate Theorem VI.5 as ISS small-gain unless we first
decompose L<sub>θ,i</sub>ρ<sub>i</sub> and L<sub>d,i</sub>η<sub>i</sub> into
genuine inter-level gain functions (Open Question 1). The path that
preserves the paper's headline narrative and gains ISS machinery only
where it helps is:

- **Keep Thm VI.5** as the primary result for RCS hierarchies with
  time-scale-separated levels.
- **Add a corollary**: if the paper's hypotheses hold, the
  per-subsystem bound V̇<sub>i</sub> ≤ −σ<sub>i</sub>V<sub>i</sub> + (cross-level gain)
  yields a linear ISS-Lyapunov function, and Jiang–Teel–Praly 1994
  small-gain recovers GAS with a cleaner hypothesis set.
- **Flag as future work**: N > 2 networks (e.g., L<sub>0</sub>–L<sub>1</sub>–L<sub>2</sub>
  with homeostatic back-edges) require DRW 2010, which requires the
  decomposition in Open Question 1.

This preserves the budget as a sufficient condition for a textbook
ISS result, without the paper having to commit to the stronger ISS
modelling hypotheses up front.
