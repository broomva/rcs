---
title: "Paper 6: Horizontal Composition — Proof Sketch"
tags:
  - rcs
  - paper
  - proof-sketch
  - horizontal-composition
  - lyapunov
  - singular-perturbation
aliases:
  - P6 Proof Sketch
created: "2026-04-18"
updated: "2026-04-18"
status: draft
related:
  - "[[p0-foundations]]"
  - "[[pneuma]]"
  - "[[plexus]]"
  - "[[stability-budget]]"
  - "[[time-scale-dilation]]"
  - "[[horizontal-vs-vertical-recursion]]"
---

# P6 — Horizontal Composition Stability: Proof Sketch

This document maps out the proof strategy for the horizontal stability theorem. It is **not** the LaTeX paper; it is a structured markdown that a mathematician (or a later drafting session) can convert into the formal proof. Notation matches the preamble of `p0-foundations/main.tex`.

## 1. Preliminaries Recap

From Paper 0 (Section 3–5, Theorem~\ref{thm:recursive}):

**RCS 7-tuple.** A Recursive Controlled System is
$$\rcs = (\X, \Y, \U, \dyn, \obs, \shield, \ctrl), \qquad \ctrl = \rcs'.$$
The controller slot at level $\Li{i}$ is itself an RCS at $\Li{i+1}$.

**Vertical stability budget** (Def.~\ref{def:budget}):
$$\stab_i = \decay_i - L_{\theta,i}\,\rho_i - L_{d,i}\,\eta_i - \beta_i\,\taubar_i - \frac{\ln \nu_i}{\taua[i]}.$$
Each term has a fixed interpretation: nominal decay, adaptation cost, design cost, delay cost, switching cost.

**Theorem 1 (P0, inductive form).** Under standing hypotheses (H1)–(H7), a finite RCS hierarchy of depth $N$ admits a composite Lyapunov function $\lyap{\leq N}$ and constants $K_N > 0$, $\omega_N > 0$ with
$$\lyap{\leq N}(\chi(t)) \leq K_N \, e^{-\omega_N t}\, \lyap{\leq N}(\chi(0)), \qquad \omega_N = \min_{0 \leq i \leq N} \stab_i.$$
The proof is by induction on $N$; Tikhonov singular perturbation (Khalil Thm.~11.4) is used at step (iv) of the inductive step to factor slow from fast subsystems.

**Singular perturbation hypothesis (H6).** There exists $c > 1$ such that $\taua[i+1] \geq c \cdot \taua[i]$ for every $i < N$. In the Life deployment this realizes as $\kappa \geq 10$ (see `data/parameters.toml`; each level $\sim 10\times$ slower than the one below).

**Canonical values** (cached in `[derived.lambda]` of `parameters.toml`, delay-dominated at the top):
$$\stab_0 = 1.455,\quad \stab_1 = 0.411,\quad \stab_2 = 0.069,\quad \stab_3 = 0.006398,\quad \omega = \min_i \stab_i = \stab_3.$$

## 2. Horizontal Composition Setup

Paper 0 extends a single instance through four vertical levels. Paper 6 extends this **laterally**: a population of depth-$k$ instances becomes the plant of a depth-$(k+1)$ instance, with a coupling layer $P$ (the pneuma realization; in Life this is `life-plexus`) carrying signals and directives across the inter-instance boundary.

### Population

Let $\{\rcs^{(i)}\}_{i=1\ldots N}$ be $N$ depth-$k$ RCS instances, each satisfying the hypotheses of Theorem~\ref{thm:recursive} with per-level margins $\{\stab_{0}^{(i)}, \ldots, \stab_{3}^{(i)}\}$ and composite rate $\omega^{(i)} = \min_{j} \stab_{j}^{(i)} > 0$.

### Coupling layer parameters

The pneuma implementation $P$ is characterized by the 5-tuple $(\delta, \tau_p, \alpha, \sigma, N)$:

| Parameter | Meaning | Analog of |
|---|---|---|
| $\delta$ | Signal decay rate (inverse half-life in field) | $\decay$ at the coupling layer |
| $\tau_p$ | Propagation delay across the coupling substrate | $\taubar$ at the coupling layer |
| $\alpha$ | Directive authority (magnitude of depth-$(k+1)$ control into per-instance inputs) | $L_d$ coupling |
| $\sigma$ | Cross-instance observation weight (how much one instance's signal affects the aggregate) | $L_\theta$ coupling |
| $N$ | Population size | bound on cumulative cross-term magnitude |

Additionally the aggregated observation satisfies its own dwell-time bound with constants $(\nu_H, \taua[H])$.

### Depth-$(k+1)$ RCS

$$\rcs^{(k+1)} = (\X^{(k+1)}, \Y^{(k+1)}, \U^{(k+1)}, \dyn^{(k+1)}, \obs^{(k+1)}, \shield^{(k+1)}, \ctrl^{(k+1)})$$

with:

- $\X^{(k+1)} \;=\; \prod_{i=1}^{N} \X^{(i)}$ — the product/sum space of the $N$ depth-$k$ instances (formally a direct sum if instances are non-interacting modulo pneuma; a product with coupling inside $\dyn^{(k+1)}$ otherwise).
- $\Y^{(k+1)} \;=\; h_H\!\left( \X^{(k+1)} \right)$ — aggregate observation via the **aggregation operator** $h_H : \X^{(k+1)} \to \Y^{(k+1)}$ (gradient fields, quorum readings, formation state; see `research/entities/concept/plexus.md`).
- $\U^{(k+1)}$ — distributed directive space. A **distribution operator** $d_H : \U^{(k+1)} \to \prod_i \U_{\text{in}}^{(i)}$ carries a single depth-$(k+1)$ directive into per-instance inputs (setpoint nudges, budget allocations).
- $\dyn^{(k+1)}$ — the population dynamics induced by the per-instance $\dyn^{(i)}$ plus the coupling layer's transport map.
- $\obs^{(k+1)} = h_H$; $\shield^{(k+1)}$ contains the pneuma admission gate (C2 bound; see below); $\ctrl^{(k+1)}$ is the depth-$(k+1)$ controller (itself an RCS at depth $k+2$ if the recursion continues).

**Commuting-square condition (to verify):** $d_H$ and $h_H$ should commute with per-instance lens structure. That is, applying an aggregate directive then observing should equal distributing, applying per-instance, and aggregating. This is the horizontal analog of the lens laws in Def.~\ref{def:lens}.

> **LEMMA (to prove) — Aggregation consistency.** The pair $(h_H, d_H)$ forms a lens on $(\X^{(k+1)}, \Y^{(k+1)}, \U^{(k+1)})$. Proof requires: (a) choice of $h_H$ is surjective onto $\Y^{(k+1)}$, (b) per-instance lens laws hold at depth $k$, (c) $d_H$ right-inverts $h_H$ on $\text{range}(d_H)$. Left as an open obligation; satisfied by stigmergic, quorum, and mean-field aggregations but not by arbitrary $h_H$.

## 3. Main Theorem (Horizontal Stability)

### Hypotheses

**(HH1) Per-instance vertical stability.** For every $i \in \{1, \ldots, N\}$, the depth-$k$ instance $\rcs^{(i)}$ satisfies hypotheses (H1)–(H7) of Theorem~\ref{thm:recursive} with composite rate $\omega^{(i)} = \min_j \stab_{j}^{(i)} > 0$.

**(HH2) Coupling-layer Lyapunov.** The pneuma layer admits a field-energy function $V_P : \Y^{(k+1)} \times \U^{(k+1)} \to \setR_{\geq 0}$ with a sandwich bound
$$\underline{\alpha}_P \|y\|^2 \leq V_P(y, u) \leq \bar{\alpha}_P \|y\|^2.$$
(This assumption is the horizontal analog of Assumption~\ref{ass:per-level} and must be discharged by the concrete pneuma implementation, e.g. `life-plexus` choosing a reaction–diffusion or consensus-Laplacian Lyapunov.)

**(HH3) Singular perturbation (C1).** $\taua[0,k+1] \geq \kappa \cdot \max_i \taua[3, i]^{(k)}$ with $\kappa > 1$. In practice $\kappa \geq 10$.

**(HH4) Bounded directive authority (C2).**
$$\alpha \cdot L_d^{(k)} \,<\, \min_i \stab_{0}^{(i, k)}.$$
(The directive perturbation enters each depth-$k$ $\Li{0}$ plant as a design-sensitivity term; keeping it below the depth-$k$ $\Li{0}$ margin preserves vertical stability per instance.)

**(HH5) Signal decay exceeds propagation (C3).** $\delta > 1/\tau_p$.

**(HH6) Sub-critical coupling (C4).**
$$N \cdot \sigma \cdot \alpha \;\leq\; \delta - \bigl( L_d^{(k)}\alpha + \beta_H \tau_p / \taua[0, k+1] + \ln \nu_H / \taua[H] \bigr).$$
Equivalently: the horizontal margin $\stab_H$ (defined in §6) is non-negative; the four terms on the right are the non-$\decay_H$ costs.

### Statement

**Theorem P6 (Horizontal stability, informal).** Under (HH1)–(HH6), the depth-$(k+1)$ composite system admits a Lyapunov function $\lyap{H}$ and constants $K_H > 0$, $\omega_H > 0$ such that
$$\lyap{H}(\chi(t)) \leq K_H\, e^{-\omega_H t}\, \lyap{H}(\chi(0)),$$
$$\omega_H \;=\; \min\!\Bigl(\, \min_{i} \omega^{(i)},\; \stab_H \,\Bigr), \qquad \stab_H > 0,$$
where $\stab_H$ is the horizontal stability margin defined in §6. In particular, the depth-$(k+1)$ state decays exponentially at rate $\omega_H$.

Cross-references: the formula for $\stab_H$ matches the shape of Def.~\ref{def:budget} applied at the coupling layer; we treat $\stab_H$ as the budget at a new "virtual level" between depth-$k$ $\Li{3}$ and depth-$(k+1)$ $\Li{0}$.

## 4. Proof Strategy

The proof is by **Lyapunov composition** with a dwell-time/singular-perturbation argument, mirroring the inductive step of Theorem~\ref{thm:recursive}. Four steps.

### Step 1 — Composite Lyapunov construction

Define
$$\lyap{H}(\chi) \;=\; \sum_{i=1}^{N} \alpha_i \, \lyap{\leq 3}^{(i)}(\chi^{(i)}) \;+\; \alpha_P \, V_P(y_{H}, u_{H}),$$
where:

- $\lyap{\leq 3}^{(i)}$ is the depth-$k$ composite Lyapunov function of instance $i$, provided by Theorem~\ref{thm:recursive} applied under (HH1).
- $V_P$ is the field-energy of the pneuma layer from (HH2).
- $\alpha_i, \alpha_P > 0$ are positive weights chosen per the Tikhonov construction (Khalil §11.4) so that cross-term contributions of $\alpha_P V_P$ into the per-instance sub-hierarchies are dominated by $\omega^{(i)} \lyap{\leq 3}^{(i)}$.

The structure mirrors the composite Lyapunov function $\lyap{\leq n+1} = \lyap{\leq n} + \alpha_{n+1} \lyap{n+1}$ from eq.~\eqref{eq:composite-construction}; the only new element is summation over the $N$ horizontal peers.

### Step 2 — Bound $\dot{V}_H \leq -\omega_H V_H$

Differentiate along the joint trajectory. Three contributions:

**Per-instance contribution.** By Theorem~\ref{thm:recursive} applied to each instance (with the quasi-static lifting discussed in Step 3), for every $i$:
$$\Delta \lyap{\leq 3}^{(i)} \;\leq\; -\omega^{(i)} \lyap{\leq 3}^{(i)} + \varepsilon_i(t),$$
where $\varepsilon_i(t)$ is the depth-$(k+1)$ directive perturbation felt by instance $i$. Under (HH4), $\|\varepsilon_i\| \leq \alpha L_d^{(k)} < \min_j \stab_{0}^{(j,k)}$, so $\varepsilon_i$ is absorbed into the already-margin'd depth-$k$ budget without flipping $\omega^{(i)}$ negative. Formally this is the same absorption argument as step (iii) of Theorem~\ref{thm:recursive}.

**Coupling contribution.** The field-energy evolves under reaction–diffusion-like dynamics with decay $\delta$ and propagation bounded by $\tau_p$:
$$\Delta V_P \;\leq\; -\delta \, V_P + \text{(cross-terms)}.$$
The cross-terms are bounded by the four sensitivity products summed over the $N$ agents; under (HH5) ($\delta > 1/\tau_p$) the Green's function of the field is $L^2$-integrable, which is required for $V_P$ to be a valid Lyapunov function (no standing-wave blowup).

**Cross terms.** Bounded using (HH4)–(HH6):
$$\sum_i \langle \nabla_{\chi^{(i)}} \lyap{\leq 3}^{(i)}, \text{directive}_i \rangle + \text{(observation flux)} \;\leq\; (\alpha L_d^{(k)} + \sigma N \alpha) \cdot (\text{bounded}).$$
(HH6) ensures this is dominated by $\delta V_P$ after absorbing weights via Young's inequality.

Combining:
$$\Delta \lyap{H} \;\leq\; -\min\!\Bigl(\min_i \omega^{(i)},\, \stab_H\Bigr) \cdot \lyap{H} \;=\; -\omega_H \, \lyap{H}.$$

### Step 3 — Dwell-time / singular perturbation

The depth-$(k+1)$ state evolves slowly (cadence $\taua[0, k+1]$) relative to depth-$k$ $\Li{3}$ (cadence $\taua[3, i]$). (HH3) with $\kappa \geq 10$ satisfies Tikhonov's time-scale hypothesis: the depth-$(k+1)$ control is the **slow** subsystem, the population of depth-$k$ hierarchies is the **fast** subsystem.

Applying Tikhonov's theorem (Khalil Thm.~11.4) and the Hespanha–Morse average-dwell-time formula \cite{hespanha1999stability}:
- Between mode-switches at the depth-$(k+1)$ level, $\lyap{H}$ decays exponentially at rate $\omega_H$.
- At mode-switches, $\lyap{H}(x^+) \leq \nu_H \lyap{H}(x^-)$.
- With $\taua[H]$ average dwell time, the cumulative growth from jumps is bounded by $\nu_H^{N_0}$ where $N_0$ is the chatter bound (Def.~\ref{def:dwell-time}, Rem.~\ref{rem:N0-standing-max}).

Error bound: the quasi-static approximation introduces an $O(\kappa^{-1})$ error, which shrinks as $\kappa \to \infty$ and is negligible for $\kappa \geq 10$.

### Step 4 — Integration

Combining the per-interval decay from Step 2 with the jump bound from Step 3:
$$\lyap{H}(t) \;\leq\; \nu_H^{N_0} \cdot \prod_i K^{(i)} \cdot e^{-\omega_H t} \cdot \lyap{H}(0) \;=\; K_H \, e^{-\omega_H t}\, \lyap{H}(0).$$
With $K_H := \nu_H^{N_0} \cdot \prod_{i=1}^{N} K^{(i)}$ (bounded because $N$ is finite) and $\omega_H > 0$ by (HH6), the theorem's conclusion follows.

$\blacksquare$ (sketch)

## 5. Derivation of Each Condition $C_i$

Each of the four conditions enters the proof at a specific step.

### C1 — Time-scale dilation: $\taua[0, k+1] \geq \kappa \cdot \max_i \taua[3, i]$, $\kappa \geq 10$

**Where used:** Step 3 (singular perturbation). (HH3) is **exactly** the Tikhonov hypothesis. Without $\kappa > 1$, the fast/slow decomposition fails, $V_H$ cannot be proved a Lyapunov function on the joint dynamics, and the argument collapses.

**Why $\kappa \geq 10$ specifically:** the Tikhonov error is $O(\kappa^{-1})$; $\kappa = 10$ gives ≤10% error, which is the conventional engineering threshold. The mathematical requirement is only $\kappa > 1$; the canonical `parameters.toml` enforces $\kappa = 10$ uniformly.

### C2 — Bounded directive authority: $\alpha \cdot L_d^{(k)} < \min_i \stab_{0}^{(i, k)}$

**Where used:** Step 2, per-instance contribution. The depth-$(k+1)$ controller reaches into each depth-$k$ $\Li{0}$ plant via a design perturbation of magnitude $\alpha L_d^{(k)}$. By Assumption~\ref{ass:design}, this contributes $\alpha L_d^{(k)}$ to the effective budget at depth-$k$ $\Li{0}$. Requiring this quantity to be strictly less than $\stab_{0}^{(i,k)}$ guarantees each per-instance margin remains positive, so $\omega^{(i)}$ stays positive.

**If violated:** per-instance $\Li{0}$ margin flips negative, instance $i$ loses vertical stability, and the horizontal composition fails at the root.

**Connection to existing results:** this is an exact analog of Prop.~\ref{prop:egri-coupling} (EGRI mutation bound), but cross-instance rather than cross-level.

### C3 — Signal decay exceeds propagation: $\delta > 1/\tau_p$

**Where used:** Step 2, coupling contribution. The pneuma field obeys (in mean-field approximation) a reaction–diffusion equation
$$\partial_t \phi \;=\; -\delta \phi + D \nabla^2 \phi + \text{sources}.$$
The Green's function decays like $e^{-\delta t}$ along characteristics that propagate at speed $\sim 1/\tau_p$. When $\delta \leq 1/\tau_p$, characteristics outrun local decay and standing waves (or traveling pulses) persist indefinitely; $V_P$ cannot be bounded by a quadratic in the aggregate state, violating (HH2).

**If violated:** the coupling Lyapunov $V_P$ is not a valid Lyapunov function (no decay along some modes). The entire composition falls back to per-instance vertical stability with no horizontal margin gained.

### C4 — Sub-critical coupling: $N \sigma \alpha \leq \delta - (\text{other costs})$

**Where used:** Step 2, cross-term bound. The cumulative observation flux from $N$ peers into the aggregate scales as $N \sigma$; multiplied by directive authority $\alpha$, the cross-term magnitude is $N \sigma \alpha$. Young's inequality absorbs this into the $-\delta V_P$ term only when $N \sigma \alpha$ does not saturate $\delta$ after the other costs are subtracted.

**Equivalent form:** $\stab_H > 0$. C4 is algebraically the requirement that the horizontal margin (formula in §6) is positive.

**If violated:** cross-terms dominate, $\Delta V_H$ is not sign-definite, and exponential decay fails. The population exhibits "jamming" — coupling overwhelms local decay.

## 6. Horizontal Margin Formula

Because the proof of Theorem P6 mirrors Theorem~\ref{thm:recursive} with an added coupling level, the horizontal margin has the **same shape** as the vertical budget (Def.~\ref{def:budget}):
$$\boxed{\;\stab_H \;=\; \decay_H - L_{\theta, H}\,\rho_H - L_{d, H}\,\eta_H - \beta_H\,\taubar_H - \frac{\ln \nu_H}{\taua[H]}\;}$$

Each term has a specific lift from the coupling-layer parameters to the Paper 0 taxonomy:

| P0 term | P6 analog | Derivation |
|---|---|---|
| $\decay_H$ | $\delta$ | Signal decay rate IS the coupling layer's nominal decay. |
| $L_{\theta, H}$ | $\sigma$ | Cross-instance observation weight is the sensitivity of the aggregate to per-instance parameter drift. |
| $\rho_H$ | $N \alpha$ | Effective adaptation rate = population-size times per-agent directive authority (cumulative across peers). |
| $L_{d, H}$ | $\alpha$ | Directive authority acts as design perturbation on each instance. |
| $\eta_H$ | $L_d^{(k)}$ | Design sensitivity inherited from depth-$k$ $\Li{0}$ (how much directive perturbation moves the plant). |
| $\beta_H$ | $\approx 1$ (normalized) | Delay sensitivity — set by the pneuma admission gate. |
| $\taubar_H$ | $\tau_p / \taua[0, k+1]$ | Propagation delay normalized by the slow-subsystem cadence. |
| $\nu_H$ | pneuma jump factor | Aggregate Lyapunov discontinuity at formation create/dissolve events. |
| $\taua[H]$ | depth-$(k+1)$ dwell time | Average dwell between aggregate-state mode switches. |

### Side derivation (adaptation-cost term)

Showing how $L_{\theta, H} \rho_H = \sigma \cdot N \alpha$ emerges.

In Step 2 the cross-term bound requires
$$\sum_{i=1}^{N} \bigl|\partial_{\theta_i} V_P \cdot \dot\theta_i\bigr| \;\leq\; \sum_{i=1}^{N} \sigma \cdot \alpha \cdot V_P \;=\; N \sigma \alpha \, V_P.$$
The first inequality uses Assumption~\ref{ass:adapt} for the coupling layer: $|\partial_\theta V_P \cdot \dot\theta| \leq L_{\theta,H} \rho_H V_P$. Matching coefficients gives $L_{\theta,H} \rho_H = N \sigma \alpha$. Setting $L_{\theta,H} = \sigma$ and $\rho_H = N\alpha$ is a canonical split that makes each factor dimensionally interpretable; other splits are mathematically equivalent.

An analogous derivation (Young's inequality applied to the delay kernel) gives $\beta_H \taubar_H = \tau_p / \taua[0,k+1]$.

## 7. Relationship to Vertical Composition (Floor Inheritance)

**Claim.** The depth-$(k+1)$ composite rate satisfies
$$\omega_H \;\leq\; \min_i \stab_{3}^{(i, k)},$$
where $\stab_{3}^{(i,k)}$ is the governance-level margin of each depth-$k$ instance. That is, the weakest depth-$k$ $\Li{3}$ margin is an **upper bound** on the depth-$(k+1)$ composite rate.

**Why.** $\omega_H = \min(\min_i \omega^{(i)}, \stab_H)$ by construction. By Theorem~\ref{thm:recursive}, $\omega^{(i)} = \min_j \stab_j^{(i)} \leq \stab_3^{(i)}$. Hence $\min_i \omega^{(i)} \leq \min_i \stab_3^{(i,k)}$, so $\omega_H \leq \min_i \stab_3^{(i,k)}$. The bound is tight when $\stab_H > \min_i \stab_3^{(i,k)}$ (the usual case: governance is narrower than horizontal coupling).

**Interpretation.** "Composite stability cannot exceed the weakest component." The depth-$(k+1)$ system is bottlenecked by whichever depth-$k$ instance has the slowest governance loop. Building a plexus on top of sluggishly-governed agents does not speed them up; at best it matches the slowest component's rate.

**Design consequence (for `life-plexus`).** Before enabling horizontal composition, the depth-0 $\Li{3}$ must be compressed to agent-native tempo (Nous-in-loop, not week-scale human review). See `research/entities/concept/plexus.md` — the "L3 compression" precondition.

## 8. Worked Numerical Example

Using canonical parameters from `data/parameters.toml` for the depth-0 instance and concrete coupling-layer values.

### Depth-0 instance (all $N$ copies identical for simplicity)

From `[[levels]]` in `parameters.toml` and `[derived.lambda]`:
$$\stab_0 = 1.455, \quad \stab_1 = 0.411, \quad \stab_2 = 0.069, \quad \stab_3 = 0.006398, \quad \omega^{(i)} = 0.006398.$$
$L_d^{(0)} = 0.1$ at the $\Li{0}$ level.

### Coupling layer ($N, \kappa, \alpha, \sigma, \delta, \tau_p, \nu_H, \taua[H]$)

| Param | Value | Rationale |
|---|---|---|
| $N$ | $10$ | small swarm |
| $\kappa$ | $10$ | canonical ratio (H6 in P0) |
| $\alpha$ | $0.1$ | directive authority — 10% of per-instance design margin |
| $\sigma$ | $0.01$ | loose cross-coupling (each peer weighs 1% in aggregate) |
| $\delta$ | $100.0 / \text{s}$ | fast field decay (half-life ~7ms) |
| $\tau_p$ | $0.1 \text{ s}$ | RPC/mesh latency |
| $\taua[0, k+1]$ | $10 \text{ days} = 864\,000$ s | depth-1 $\Li{0}$ cadence (satisfies C1) |
| $\nu_H$ | $1.1$ | aggregate jump factor |
| $\taua[H]$ | $30 \text{ days}$ | depth-1 dwell time between aggregate mode changes |

### Verify C1–C4

**C1.** $\taua[0, k+1] = 864\,000 \text{ s} \geq \kappa \cdot \taua[3]^{(0)} = 10 \cdot 86\,400 = 864\,000 \text{ s}$. $\checkmark$

**C2.** $\alpha \cdot L_d^{(0)} = 0.1 \cdot 0.1 = 0.01 < \stab_{0}^{(0)} = 1.455$. $\checkmark$

**C3.** $\delta = 100/\text{s} > 1/\tau_p = 10/\text{s}$. $\checkmark$

**C4 / $\stab_H > 0$.**
$$\decay_H = \delta = 100.0$$
$$L_{\theta,H}\rho_H = \sigma \cdot N\alpha = 0.01 \cdot 10 \cdot 0.1 = 0.01$$
$$L_{d,H}\eta_H = \alpha \cdot L_d^{(0)} = 0.1 \cdot 0.1 = 0.01$$
$$\beta_H \taubar_H = 1 \cdot (0.1 / 864\,000) \approx 1.16 \times 10^{-7}$$
$$\ln \nu_H / \taua[H] = \ln 1.1 / (30 \cdot 86\,400) \approx 3.68 \times 10^{-8}$$
$$\stab_H = 100.0 - 0.01 - 0.01 - 1.16{\times}10^{-7} - 3.68{\times}10^{-8} \approx 99.98. \;\checkmark$$

### Compute $\omega_H$

$$\omega_H = \min\!\bigl(\min_i \omega^{(i)},\, \stab_H\bigr) = \min(0.006398, 99.98) = 0.006398.$$

### Discussion

The coupling layer contributes enormous raw margin ($\stab_H \approx 100$), but the depth-1 composite rate collapses to the depth-0 floor $\stab_3 = 0.006398$ by the inheritance result of §7. In practice this means: adding a plexus on top of vertically-saturated depth-0 agents does not make the composite any faster than the slowest governance loop.

To raise the composite rate, the engineering lever is **compressing $\taubar_3^{(0)}$ at depth 0** (Nous-in-loop), which widens $\stab_3$ and raises the floor. Horizontal coupling parameters $(\delta, \sigma, \alpha, N)$ can reduce the margin if (C2)–(C4) are violated, but they cannot increase it above the vertical bottleneck.

## 9. Corollaries

### Corollary 1 — Recursion to arbitrary depth

Iterating P6 from depth $0$ to depth $M$ produces a sequence of horizontal margins $\stab_H^{(0)}, \stab_H^{(1)}, \ldots, \stab_H^{(M-1)}$. By induction on $M$ and repeated application of §7's floor-inheritance,
$$\omega^{(M)} \;=\; \min\!\bigl(\omega^{(0)},\, \stab_H^{(0)},\, \stab_H^{(1)},\, \ldots,\, \stab_H^{(M-1)}\bigr).$$
Each depth adds at most one new $\stab_H$ constraint, but adds one more time-scale dilation by factor $\kappa$. The recursion terminates (mathematically) at any finite $M$, matching P0's finite-depth induction stance (Rem.~\ref{rem:structural-self-similarity}).

### Corollary 2 — Depth-$M$ scaling

In the canonical regime where every depth saturates $\stab_H^{(k)} \gg \min_i \stab_3^{(i,k)}$ (as in §8's worked example),
$$\omega^{(M)} \approx \min_i \stab_3^{(i, 0)}.$$
The composite rate is bottlenecked by the **top of the depth-0 vertical stack**, not by horizontal couplings. Scaling $M$ upward does not improve the rate; it only adds cadence dilation.

For the Life deployment, this says: horizontally stacking many plexus layers on top of depth-0 Life instances gains nothing until depth-0 governance itself is compressed. Compression lifts the floor for every subsequent depth.

### Corollary 3 — Substrate independence

Theorem P6 depends on $(N, \kappa, \alpha, \sigma, \delta, \tau_p, \nu_H, \taua[H])$ only through the scalar inequalities (HH3)–(HH6) and the shape of (HH2)'s sandwich bound. Substrate choice — whether the pneuma is implemented via stigmergic pheromones, gradient consensus, a Laplacian gossip protocol, or field-theoretic diffusion — enters only via the concrete values of $\delta$, $\tau_p$, $\nu_H$ and the form of $V_P$.

In particular, the theorem holds on any substrate where $\dyn^{(k+1)}$ and $\obs^{(k+1)} = h_H$ are well-defined and $V_P$ satisfies (HH2). Substrate-specific stability witnesses plug into the P0 instantiation catalogue (Table~\ref{tab:instantiations}) the same way LQR, Dreamer, and LLM rows already do.

## 10. Open Research Questions

These are gaps the proof sketch leaves open; each deserves its own follow-up investigation.

1. **Is $\stab_H$ tight?** The formula in §6 is a *sufficient* condition for horizontal stability; necessity is not claimed. For $\rho_H = N \alpha$ specifically (population-scaled directive), a matching lower bound via constructive counterexample (a population where $\stab_H = 0^+$ fails to stabilize) would show tightness. Open.

2. **Heterogeneous populations.** The statement uses $\min_i$ on per-instance margins, but the proof implicitly assumes bounded *variance* across the population. If $\omega^{(i)}$ varies by orders of magnitude across $i$, the weak peers may destabilize the aggregate before the floor inheritance kicks in. Quantifying the variance tolerance (and its interaction with $\sigma$) is open.

3. **Dynamic $N$.** The theorem fixes $N$. Real deployments (swarm formations, agents joining and leaving) change $N$ adiabatically. Admission/eviction events introduce jumps in $V_H$, which need a horizontal-analog of Assumption~\ref{ass:jump}. Conjecture: if membership changes obey a dwell time compatible with $\taua[H]$, the theorem extends with a modified $\nu_H$. Proof open.

4. **Non-ergodic propagation.** The mean-field approximation used in C3's justification assumes stationary signal statistics. Bursty traffic (e.g. periodic broadcast storms) violates this and can resonate with the field's natural modes even when $\delta > 1/\tau_p$ on average. Is there a bursty-traffic version of C3 involving $L^\infty$ rather than $L^2$ bounds? Open.

5. **Tight coupling between $\sigma$ and $h_H$.** The value of $\sigma$ is not arbitrary — it is determined by the choice of aggregation operator $h_H$ (quorum, mean-field, max, Laplacian). A systematic table mapping $h_H$ choices to effective $\sigma$ values (and the corresponding admissible $N$) would make the theorem operational for practitioners designing `life-plexus` variants.

6. **Pneuma-layer Lyapunov construction.** (HH2) is an *assumption* — it must be discharged by the concrete pneuma implementation. For `life-plexus`, candidate Lyapunov functions include: the $L^2$ norm of the pheromone field; the quadratic gap between actual and consensus directive; formation-energy under a graph Laplacian. Matching a specific construction to the proof is concrete follow-up work.

---

### Style and Technical Notes

- Notation follows `p0-foundations/main.tex` preamble (`\rcs`, `\stab`, `\decay`, `\drive{i}`, `\lyap{i}`, `\taua[i]`, etc.). No new notation was introduced except the "$H$" subscript for the horizontal layer.
- All numerical values trace to `data/parameters.toml` or coupling-layer design parameters. When converted to LaTeX, the $\stab_H$ computation should be added to `scripts/gen_parameters_tex.py` and surfaced as `\rcsmarginHDisp` for the paper.
- Proof steps 1–4 follow the structure of the inductive step in P0's Theorem~1 proof (steps i–v). Reviewers familiar with P0 should find the argument shape immediately recognizable.
- Flagged gaps: Lemma (aggregation consistency) in §2, open questions 1–6 in §10, and the assumption-vs-derivation status of (HH2). These are conceptual holes the final LaTeX paper must either close or clearly defer.
- The §8 worked example is deliberately tuned so $\stab_H \gg \min_i \stab_3^{(i)}$; this surfaces the floor-inheritance effect cleanly. An alternative worked example where $\stab_H$ dominates would stress-test C1–C4 in the opposite regime — worth adding to the LaTeX paper as a companion case.
