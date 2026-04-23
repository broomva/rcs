---
title: RCS Research Index
tags:
  - research
  - index
  - MOC
  - rcs
  - control-theory
aliases:
  - Recursive Controlled Systems
  - RCS
created: "2026-04-16"
updated: "2026-04-23"
---

# RCS — Recursive Controlled Systems

Formal control-theoretic foundation for autonomous AI agents, where the agent itself is a plant operated upon by nested controllers at multiple time scales.

## Design Spec

- [[2026-04-16-rcs-formalization-design]] — Full design specification (BRO-702)

## Working Documents

- [[life-rcs-mapping]] — Life Agent OS → RCS mapping table with Rust types, file paths, line numbers (BRO-704)
- [[framework-unification]] — Framework unification: Eslami/Ashby/Beer/Active Inference → RCS (BRO-705)
- [[self-referential-closure]] — Self-referential closure: the RCS paper IS a Level 3 artifact (Proposition 4)

## Papers

| # | Title | Status | Linear | Target Venue |
|---|-------|--------|--------|-------------|
| P0 | [[p0-foundations/README\|RCS Foundations]] | Drafting (12 PRs landed, π₀-family instantiation added) | BRO-697 | Workshop (Dec 2026) |
| P1 | [[p1-stability/README\|Empirical Budget Validation]] | Scaffold (PROTOCOL + root-Makefile p1 build targets landed PR #14) | BRO-698 | CDC/L4DC (May 2027) |
| P2 | [[p2-egri/README\|EGRI as Meta-Controller]] | Planned | BRO-699 | ICML/AAMAS (May 2027) |
| P3 | [[p3-observers/README\|Self-Referential Observers]] | Planned | BRO-700 | AAAI (Sep 2027) |
| P4 | [[p4-fleet/README\|Fleet Cooperative Resilience]] | Planned | BRO-701 | IEEE TAI (Mar 2028) |
| P5 | [[p5-categorical-foundations/SCOPE\|Categorical Foundations]] | Dormant (annual review; retire 2030 if no trigger) | TBD | TBD |
| P6 | [[p6-horizontal-composition/README\|Horizontal Composition]] | Outline (171-line README; closes horizontal-scaling gap) | TBD | Workshop (CDC or NeurIPS, 2027) |
| P7 | [[p7-thermodynamic-limits/README\|Thermodynamic Limits & Depth-Kardashev]] | Outline (197-line README; substrate-warp data in) | TBD | Physics of Life Reviews / Entropy / AI-TDSP workshop |

## Core Concepts

```
RCS 7-Tuple: Σ = (X, Y, U, f, h, S, Π)

Level 0: External plant → Arcan agent
Level 1: Agent internal → Autonomic controller
Level 2: Meta-control → EGRI loop
Level 3: Governance → bstack policy

Stability Budget: λᵢ = γᵢ - L_θᵢ·ρᵢ - L_dᵢ·ηᵢ - βᵢ·τ̄ᵢ - (ln νᵢ)/τₐ,ᵢ > 0
```

## Entity Pages

Concepts promoted to the knowledge graph:

- [[autonomic-homeostasis]] — Three-pillar regulation
- [[cooperative-resilience-mas]] — Measurement framework for MAS disruption
- [[agent-economic-pillar]] — Economic mode switching
- [[hysteresis]] — Anti-flapping deadband + dwell time

## Key References

- [[eslami-2026-control-theoretic-agentic]] — 5-level agency hierarchy
- [[keramati-gutkin-2014]] — Homeostatic drive = Lyapunov = reward
- [[ashby-1952-design-for-a-brain]] — Ultrastability
- [[beer-1972-brain-of-the-firm]] — Viable System Model
- [[quijano-2017-population-games]] — Evolutionary dynamics for distributed control
- [[chacon-chamorro-2025-cooperative-resilience]] — Cooperative resilience in AI MAS

## Related

- [[MAIA Index]] — Masters program administration
- [[Life Agent OS]] — Code implementation
- [[Becas para el Cambio]] — Scholarship application
