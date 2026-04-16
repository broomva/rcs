# RCS — Recursive Controlled Systems

## Purpose

Research program formalizing autonomous AI agents as recursive control-theoretic plants.
5-paper series + executable Rust witnesses in the Life Agent OS.

## Linear

- **Initiative:** MAIA — Maestria en Inteligencia Artificial
- **Project:** RCS — Recursive Controlled Systems Formalization
- **Epic:** BRO-697 (Paper 0), BRO-698 (Paper 1), BRO-699 (Paper 2), BRO-700 (Paper 3), BRO-701 (Paper 4)

## Structure

```
rcs/
├── papers/           # Paper drafts (one folder per paper)
│   ├── p0-foundations/
│   ├── p1-stability/
│   ├── p2-egri/
│   ├── p3-observers/
│   └── p4-fleet/
├── latex/            # Formal definitions, proofs, shared macros
├── specs/            # Design specifications
├── references/       # PDFs + reading notes for cited works
├── docs/             # Mapping tables, comparison tables, working docs
│   └── conversations/  # Session logs for this project
└── CLAUDE.md         # This file
```

## Core Definition

A Recursive Controlled System is a 7-tuple `Sigma = (X, Y, U, f, h, S, Pi)` where the controller `Pi` is itself an RCS at the next level.

## Key References

- Eslami & Yu (2026), arXiv:2603.10779 — 5-level agency, stability budget
- Keramati & Gutkin (2014) — homeostatic drive = Lyapunov = reward
- Ashby (1952) — ultrastability, requisite variety
- Beer (1972) — viable system model, recursive viability
- Quijano (2017, 2026) — population dynamics for distributed control
- Chacon-Chamorro et al. (2025) — cooperative resilience in MAS

## Conventions

- Language: English for papers and code, Spanish for MAIA capstone deliverables
- LaTeX: One shared preamble in `latex/preamble.tex`, per-paper main files
- Citations: BibTeX in `latex/references.bib`
- Obsidian: All docs use YAML frontmatter with wikilinks for cross-referencing
- Entity pages: Concepts surfaced here promote to `research/entities/concept/`
