---
title: "Paper 6: RCS Horizontal Composition"
tags:
  - rcs
  - paper
  - control-theory
  - horizontal-composition
  - swarm
  - pneuma
aliases:
  - P6
  - RCS Horizontal Composition Paper
created: "2026-04-18"
updated: "2026-04-18"
status: outline
linear: TBD
target_venue: "Workshop (CDC or NeurIPS, 2027)"
related:
  - "[[RCS Index]]"
  - "[[p0-foundations]]"
  - "[[p4-fleet]]"
  - "[[2026-04-18-pneuma-plexus-recursion-synthesis]]"
  - "[[stability-budget]]"
  - "[[pneuma]]"
  - "[[plexus]]"
---

# Paper 6: Horizontal Composition of Recursive Controlled Systems

## Working Title

"Horizontal Composition of Recursive Controlled Systems: Stability Conditions for Populations of Nested Agents"

## Contribution

Paper 0 proves *vertical* composition: if the stability budget λᵢ > 0 at every level within one RCS instance, the composite is exponentially stable with rate min_i λᵢ. Paper 6 extends this to **horizontal composition**: populations of vertically-stable instances coordinated through an inter-instance coupling layer.

This closes a concrete gap: the Life Agent OS architecture assumes Life can run at both individual and collective scales (a harness running Life is a unit; a harness running Life over populations of those units is the collective). Without a horizontal stability result, the collective case has no formal guarantees.

**P6 establishes:** (a) conditions under which horizontal composition preserves stability, (b) an explicit horizontal margin λ_H as a function of coupling parameters, (c) the fundamental trade-off between depth-(k+1) responsiveness and depth-k governance cadence, and (d) design constraints for practical coupling-layer implementations (pneuma realizations, specifically `life-plexus`).

## Core Conjecture (to prove or disprove)

Let {Σᵢ}_{i=1..N} be a population of depth-k RCS instances each satisfying vertical stability with margins {λ₀ⁱ, λ₁ⁱ, λ₂ⁱ, λ₃ⁱ > 0}. Let P be a depth-k → depth-(k+1) pneuma implementation characterized by:

- **Signal decay rate** δ (inverse half-life of emitted signals)
- **Propagation delay** τ_p (communication latency across the coupling layer)
- **Directive authority** α (magnitude of depth-(k+1) control influence on depth-k plants)
- **Population size** N
- **Coupling strength** σ (cross-instance observation weight)

Then the horizontally composed system (a depth-(k+1) RCS with plant X^(k+1) = population of {Σᵢ}) is exponentially stable iff all four conditions hold:

**C1 — Time-scale dilation (Singular perturbation):**
```
τ₀^(k+1) ≥ κ · max_i τ₃^(k),    κ ≥ 10
```

**C2 — Bounded directive authority (Lower-level plant not destabilized):**
```
α · L_d^(k) < min_i λ₀^(k, i)
```

**C3 — Signal decay exceeds propagation (No standing waves in field):**
```
δ > 1/τ_p
```

**C4 — Sub-critical coupling (Population-level jam factor):**
```
N · σ < reserve_budget(k+1)
```

Yielding a horizontal stability margin:
```
λ_H = g(δ, τ_p, α, N, σ) = γ_H − L_θ,H·ρ_H − L_d,H·η_H − β_H·τ̄_H − ln(ν_H)/τ_{a,H}
```
with λ_H > 0 required for depth-(k+1) exponential stability.

## Outline

1. **Introduction**
   - Motivation: the collective-Life scaling question
   - Vertical vs. horizontal recursion axes (orthogonal)
   - Why Theorem 1 doesn't cover horizontal composition

2. **Preliminaries**
   - RCS 7-tuple recap from P0
   - Vertical stability theorem (restate)
   - Coupling-layer abstraction (Pneuma trait family)
   - Singular perturbation review

3. **Horizontal Composition Setup**
   - Population as a plant: X^(k+1) = Vec<Σᵢ>
   - Aggregation operator h_H: X^(k+1) → Y^(k+1) (gradient fields, quorum readings, formation state)
   - Distribution operator (inverse of h) for directives
   - Coupling-layer as explicit S_H shield (what traverses between depths)

4. **Stability Conditions (main theorem)**
   - Statement of the four conditions C1-C4
   - Proof via Lyapunov composition with switched systems (Hespanha dwell-time)
   - Horizontal margin λ_H derivation
   - Relationship to vertical composition: λ at depth-(k+1) inherits from min_i λ₃^(k)

5. **Time-scale analysis**
   - Why dilation is forced: κ must be ≥10 for singular perturbation
   - Consequence: depth-(k+1) L0 cadence ≥ κ × slowest depth-k L3 cadence
   - Corollary: for fast horizontal recursion, depth-k L3 must be compressed (agent-native Nous, not human review)
   - **Recursion structure:** P6 is finite induction at each depth (consistent with P0 Theorem VI's P(N) framework). Iterating to arbitrary depth = iterated finite induction, not coinductive/categorical fixed-point claim. Categorical composition of RCS instances is deferred to a future Paper 5 (if ever needed).

6. **Compute-budget perspective (compute-normalized time)**
   - Re-express conditions in substrate-relative time (cycles, not seconds)
   - Absolute tempo T as free parameter bounded by total compute C_total
   - Sub-linear scaling: doubling C_total approximately doubles T modulo coordination overhead η(N)
   - Connection to P7 (thermodynamic limits)

7. **Design constraints for `life-plexus`**
   - Signal half-lives bounded below by field geometry
   - Directive rates bounded above by depth-0 L3 cadence
   - Population size bounded above by coupling-strength budget
   - Choice of aggregation operator (gradient, quorum, voting) determines λ_H behavior

8. **Worked Example: depth-0→depth-1 Life plexus**
   - 10 Claude-class agents, Nous-as-L3 (compressed to seconds)
   - Substitute concrete parameters from `data/parameters.toml` into C1-C4
   - Compute λ_H numerically
   - Show feasibility regime

9. **Fleet-scale comparison (vs P4)**
   - P4 (Fleet) treats multiple agents as a control surface at L3 of one instance
   - P6 (Horizontal) treats them as L0 of a new depth-(k+1) instance
   - When to use which: P4 for supervised fleets, P6 for autonomous swarms

10. **Discussion**
    - What happens at depth ≥2? Recursive application of the same theorem
    - Asymmetric populations (heterogeneous depth-k instances)
    - Composition with non-RCS plants (e.g., human agents in the population)
    - Failure modes: what happens when C2 is violated (over-authoritative depth-(k+1) destabilizes depth-k loops)

## Sub-issues (Linear — TBD)

- [ ] BRO-TBD — Formal statement of C1-C4
- [ ] BRO-TBD — Lyapunov proof sketch
- [ ] BRO-TBD — Parameter derivation for horizontal λ_H
- [ ] BRO-TBD — Worked numerical example
- [ ] BRO-TBD — Rust traits: `Pneuma<Axis, Boundary>` + `HorizontalStabilityBudget`
- [ ] BRO-TBD — Python tests: `test_horizontal_composition.py`

## Key References

- Eslami & Yu (2026) — vertical stability budget (foundation)
- Hespanha & Morse (1999) — dwell-time stability of switched systems
- Quijano (2017, 2026) — population dynamics for distributed control
- Khalil (2002) — singular perturbation theory
- Boyd (1994) — LMI approaches to stability
- P0 (this repo) — RCS 7-tuple foundations
- P4 (this repo) — Fleet control (related but distinct axis)

## Open research questions

1. **Is λ_H tight?** What's the gap between the sufficient condition and necessary condition for horizontal stability?
2. **Heterogeneous populations:** does the theorem hold when {λ₀ⁱ, ..., λ₃ⁱ} varies significantly across i?
3. **Dynamic N:** how does λ_H behave when population size changes during operation (agents joining/leaving formations)?
4. **Non-ergodic coupling:** what if signal propagation has non-stationary statistics (e.g., burst traffic)?
5. **Depth ≥ 2 composition:** does recursive application of P6 preserve the horizontal margin structure, or does it decay?

## Status

- Outlined 2026-04-18 following pneuma/plexus architecture session
- Prerequisite for building `life-plexus` crate
- Prerequisite for horizontal-composition integration tests in Life harness
