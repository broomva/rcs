---
title: "Paper 1: RCS Stability — Empirical Budget Validation"
tags:
  - rcs
  - paper
  - control-theory
  - stability
  - empirical
aliases:
  - P1
  - RCS Stability Paper
created: "2026-04-23"
updated: "2026-04-23"
status: scaffold
linear: BRO-698
target_venue: "Workshop (CDC or NeurIPS, Dec 2026)"
related:
  - "[[RCS Index]]"
  - "[[p0-foundations]]"
  - "[[2026-04-16-rcs-formalization-design]]"
---

# Paper 1: Measuring the Recursive Stability Budget in a Production Agent Operating System

## Working Title

"Measuring the Recursive Stability Budget in a Production Agent Operating System"

## Contribution

Runtime validation of the per-level stability margin $\hat{\lambda}_i$ and
composite rate $\hat{\omega}_N = \min_i \hat{\lambda}_i$ from Paper 0, using
the Life Agent OS as the experimental plant. Paper 0's theorem is inductive
and assumption-discharged; Paper 1 closes the loop empirically — it shows
that the canonical parameters in `data/parameters.toml` match observed
runtime behaviour (or characterises where they don't).

**Not a theory paper.** All proofs live in Paper 0. This paper is a
measurement study: instrumentation, capture protocol, dataset, and
regression-style analysis of the four cost components
($L_\theta\rho,\ L_d\eta,\ \beta\bar\tau,\ \ln\nu / \tau_a$) predicted by
Paper 0.

## Outline

1. Introduction: why empirical validation is non-trivial for recursive plants
2. Related Work: Eslami & Yu's original budget, observability of switched
   systems, production ML-safety monitoring
3. RCS Recap (short): 7-tuple, budget decomposition, composite rate
   (forwarded to Paper 0)
4. Experimental Methodology: daemon configuration, OTel instrumentation,
   capture windows, dataset layout (see `PROTOCOL.md`)
5. Results: per-level margin traces, cost-component breakdown, violation
   incidents
6. Discussion: where the theory fits, where it doesn't, dominant cost term
7. Conclusion: limitations; threads to Papers 2–4

## Experimental Protocol

See [`PROTOCOL.md`](./PROTOCOL.md) for the full specification of daemon
configuration, capture-window length, $\hat{\lambda}_i$ sampling rate,
OpenTelemetry metric names, dataset layout under `data/p1-runs/`, plot
specification, and reproducibility commands.

## Sub-Issues (Linear)

- [ ] BRO-698 — Paper 1 parent epic
- [ ] P1-scaffold — paper skeleton, Makefile targets, protocol document (this PR)
- [ ] P1d — data-capture harness (under `data/p1-runs/`) following PROTOCOL.md
- [ ] P1e — analysis notebooks (cost-component attribution, regime transitions)
- [ ] P1f — paper body and figures

## Key References

- Eslami & Yu (2026), arXiv:2603.10779 — original 5-level stability budget
- Keramati & Gutkin (2014) — homeostatic drive = Lyapunov = reward
- Hespanha & Morse (1999) — average dwell time for switched systems
- Ioannou & Sun (1996) — adaptive-control sensitivity bounds
- Paper 0 of this series — formal inductive theorem for $\omega_N$

## Relationship to the Life Agent OS

Paper 1 depends on the `StabilityBudget` / `MarginEstimator` / `RcsObserver`
instrumentation landed in life#802 and life#804 (see `CLAUDE.md` §Landed
infrastructure). The `data/parameters.toml` mirror is the shared contract
between this paper's measurements and Paper 0's theory.
