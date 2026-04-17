---
title: "Paper 0: RCS Foundations"
tags:
  - rcs
  - paper
  - control-theory
  - category-theory
aliases:
  - P0
  - RCS Foundations Paper
created: "2026-04-16"
updated: "2026-04-16"
status: drafting
linear: BRO-697
target_venue: "Workshop (CDC or NeurIPS, Dec 2026)"
related:
  - "[[RCS Index]]"
  - "[[2026-04-16-rcs-formalization-design]]"
  - "[[eslami-2026-control-theoretic-agentic]]"
---

# Paper 0: Recursive Controlled Systems — A Self-Similar Formalization for Autonomous AI Agents

## Working Title

"Recursive Controlled Systems: A Self-Similar Control-Theoretic Foundation for Autonomous AI Agents"

## Contribution

Define the RCS 7-tuple `Sigma = (X, Y, U, f, h, S, Pi)` with self-similar recursion. Establish algebraic vocabulary (Mealy coalgebra, lens, trace, decorated cospan, fixed point). Map the Life Agent OS codebase onto this formalism. Show that Eslami's 5-level agency hierarchy, Ashby's ultrastability, Beer's VSM, Active Inference, and the context-engineering lineage (Reflexion / Self-Refine / Voyager / Generative Agents / ACE) all instantiate the same recursive structure.

**Not a proof paper** — a definitions-and-mapping paper. The "Rosetta stone" that connects the literatures.

## Outline

1. Introduction: The agent-as-plant thesis
2. Preliminaries: State-space control, switched systems, Lyapunov stability
3. The RCS Definition: 7-tuple, recursion, fixed-point property
4. Algebraic Vocabulary: 5 categorical primitives
5. Mapping to Life Agent OS: L0-L3 concrete instantiation
6. Unification: Eslami / Ashby / Beer / Active Inference / Context Engineering -> RCS
7. Worked example: Context collapse as design-evolution violation (ACE Fig. 2)
8. Discussion: What the formalism buys us

## Sub-Issues (Linear)

- [x] BRO-702 — Design spec document
- [ ] BRO-703 — LaTeX formal definitions
- [ ] BRO-704 — Life -> RCS mapping table
- [ ] BRO-705 — Framework unification table
- [ ] BRO-706 — `PlantInterface<L>` trait in aios-protocol

## Key References

- Eslami & Yu (2026), arXiv:2603.10779
- Ashby (1952), *Design for a Brain*
- Beer (1972), *Brain of the Firm*
- Baez & Erbele (2015), "Categories in Control"
- Keramati & Gutkin (2014), "Homeostatic reinforcement learning"
- Baltieri & Buckley (2019), "PID Control as Active Inference"
- Zhang et al. (2025), "Agentic Context Engineering" (ICLR 2026) — arXiv:2510.04618
- Shinn et al. (2023), "Reflexion" (NeurIPS)
- Madaan et al. (2023), "Self-Refine" (NeurIPS)
- Wang et al. (2023), "Voyager" — arXiv:2305.16291
- Park et al. (2023), "Generative Agents" (UIST)
