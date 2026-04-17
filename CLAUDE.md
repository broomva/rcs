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
│   ├── parameters.toml   # CANONICAL — single source of truth (see below)
│   ├── parameters.tex    # GENERATED — do NOT edit by hand
│   ├── preamble.tex      # \input{parameters} lives here
│   ├── references.bib    # BibTeX
│   ├── rcs-definitions.tex        # article-format paper
│   └── rcs-definitions-ieee.tex   # IEEE-format paper
├── scripts/          # Build tooling (gen_parameters_tex.py)
├── tests/            # Proof tests (stability budget + Lyapunov sim)
├── specs/            # Design specifications
├── references/       # PDFs + reading notes for cited works
├── docs/             # Mapping tables, comparison tables, working docs
│   └── conversations/  # Session logs for this project
├── Makefile          # make test / make build / make params
└── CLAUDE.md         # This file
```

## Core Definition

A Recursive Controlled System is a 7-tuple `Sigma = (X, Y, U, f, h, S, Pi)` where the controller `Pi` is itself an RCS at the next level.

## Canonical parameters — `latex/parameters.toml`

**`latex/parameters.toml` is the single source of truth for every numeric value that appears in the paper, the Python proof tests, and the future Rust Life harness.** Three invariants are enforced by CI:

1. Editing `parameters.toml` without regenerating `parameters.tex` → fails `params-drift-check` CI job.
2. Hand-editing `parameters.tex` → fails `params-drift-check`.
3. Bumping a parameter without updating `[derived.lambda]` cache → generator exits 1, CI fails.

### When you edit a parameter

```bash
# 1. Edit parameters.toml
$EDITOR latex/parameters.toml

# 2. Update the [derived.lambda] cache for any level whose inputs changed.
#    If you don't know the new lambda, run the generator; it will fail with
#    the exact recomputed value you need to paste in.

# 3. Regenerate parameters.tex
make params                          # shorthand
# or: python3 scripts/gen_parameters_tex.py

# 4. Validate
make test                            # runs params-check + proof tests
make build                           # rebuilds both PDFs
```

### Schema

```toml
schema_version = 1

[[levels]]
id             = "L0"                # L0..L3 supported; level_macro_suffix() in generator
name           = "plant"
system         = "Arcan agent loop (shell.rs)"
gamma          = 2.0                 # nominal decay rate
L_theta        = 0.3                 # adaptation sensitivity
rho            = 0.5                 # adaptation rate bound
L_d            = 0.1                 # design sensitivity
eta            = 0.2                 # design evolution rate bound
beta           = 1.0                 # delay sensitivity
tau_bar        = 0.01                # supremal delay (seconds)
nu             = 1.2                 # jump comparability factor (>= 1)
tau_a          = 0.5                 # average dwell time (seconds)
display_digits = 3                   # decimal places for *Disp paper macros

[eslami_2026.stable]                 # faithful reproduction of a cited external result — DO NOT EDIT
# ... same parameter fields + expected_lambda

[derived.lambda]                     # cache; regenerator verifies these
L0 = 1.455357
L1 = 0.411484
L2 = 0.069274
L3 = 0.006398

[derived.omega]                      # composite rate omega = min_i lambda_i
value = 0.006398
level = "L3"
```

To add a new level or field: bump `schema_version`, update `level_macro_suffix()` in `scripts/gen_parameters_tex.py` if adding a new level id, update `tests/test_stability_budget.py::test_recursive_all_levels_stable`'s expected-set assertion.

### Macro naming convention in `parameters.tex`

Every parameter produces two macros:

| Macro form | Value | Use in paper |
|---|---|---|
| `\rcs<name>L<suffix>`     | Full precision (up to 6 decimals or scientific) | Tables requiring precision; programmatic consumers |
| `\rcs<name>L<suffix>Disp` | Rounded per `display_digits`; math-mode scientific for tiny values | **Paper body prose and tables** — must be inside `$...$` |

Suffixes: `Lzero`, `Lone`, `Ltwo`, `Lthree` (LaTeX macros can't contain digits).

Names: `gamma`, `Ltheta`, `rho`, `Ld`, `eta`, `beta`, `taubar`, `nu`, `taua`, `adaptcost`, `designcost`, `delaycost`, `switchcost`, `margin`.

Examples:

```tex
% In paper prose:
$\stab_3 = \rcsmarginLthreeDisp$                 % -> "0.0064"
$L_{\param,3}\rho_3 = \rcsadaptcostLthreeDisp$   % -> "1 \times 10^{-6}"

% In programmatic tables / Rust harness consumers:
\rcsmarginLthree                                  % -> 0.006398 (full)
```

Eslami & Yu (2026) reference macros follow the pattern `\rcsEslami{Stable,Unstable}<name>`.

### Why this matters

Before F1, the paper's governance table hard-coded cost products (`L_theta*rho = 0.001`, `beta*tau_bar = 0.002`, etc.) that did **not** match the products computed from the Python test's parameters — even though the headline `lambda_3 = 0.0064` happened to match. Future edits to either side would silently drift. The canonical TOML + generator + CI drift check makes this class of bug impossible.

## Working with the paper

```bash
make test        # params-check + both proof test suites (9 algebraic + 4 simulation)
make build       # regenerate parameters.tex + build both PDFs
make params      # just regenerate parameters.tex
make params-check   # verify parameters.tex matches parameters.toml
make all         # build + test
make clean       # clean LaTeX intermediates
```

Python 3.11+ required (uses `tomllib` stdlib). No third-party deps. CI is Python 3.12 + tectonic 0.16.8 on `ubuntu-latest`.

## Best practices for future sessions

- **Never hand-edit `latex/parameters.tex`.** It is generated. Hand edits are caught by CI but silently lose information.
- **Never duplicate canonical values.** If you need a parameter in a new file (Python module, Rust crate, spec doc), load it from `parameters.toml`.
- **When changing headline values** (e.g., `\stab_3`), update the paper narrative, not just the number. The paper's surrounding prose is coupled to the value (e.g., "delay-dominated" only makes sense if `beta*tau_bar` is the largest term).
- **When adding a new citation** in the paper text, add the BibTeX entry to `latex/references.bib` in the same commit. CI does not auto-detect missing bib entries, but undefined references will show up as warnings in the build log.
- **Separate content changes from infrastructure changes.** PRs touching `parameters.toml` or the generator should not also be changing the paper's narrative — makes review harder and drift risk higher.
- **Preserve `schema_version`.** Bump it when adding/removing/renaming a field in the TOML. Tests check the version.
- **The paper and Python produce bit-identical `lambda_i` values** (to 1e-6 tolerance). If they diverge, one of them is wrong — the TOML's `[derived.lambda]` cache is the tiebreaker, and the generator/tests will point at which side to fix.

## Landed infrastructure (reference for future agents)

| PR | Repo | What | Key files |
|---|---|---|---|
| #1 | rcs | RK4 integrator, real assertions in Lyapunov tests | `tests/test_lyapunov_simulation.py` |
| #2 | rcs | `parameters.toml` + generator + drift check + CI job | `latex/parameters.toml`, `scripts/gen_parameters_tex.py`, `.github/workflows/ci.yml` |
| #3 | rcs | `rem:context-collapse` tying ACE to Assumption 3 | `latex/rcs-definitions.tex` |
| #4 | rcs | `*Disp` display macros + governance table reconciliation | `latex/parameters.toml`, `scripts/gen_parameters_tex.py`, `latex/rcs-definitions.tex` |
| #5 | rcs | CLAUDE.md + README workflow documentation | `CLAUDE.md`, `README.md` |
| life#802 | life | F2 Rust instrumentation: `StabilityBudget`, `MarginEstimator`, vigil OTel gauges, mirror of `parameters.toml` | `crates/autonomic/autonomic-core/src/rcs_budget.rs`, `crates/autonomic/autonomic-core/data/rcs-parameters.toml`, `crates/vigil/life-vigil/src/metrics.rs`, `scripts/sync-rcs-parameters.sh` |

## Cross-repo mirror contract (`parameters.toml`)

**Single source of truth stays in this repo** (`~/broomva/research/rcs/latex/parameters.toml`). The Life repo (`~/broomva/core/life`) needs compile-time access for its Rust `rcs_budget` module via `include_str!`, and cross-repo absolute paths break hermetic builds. The resolution:

- **Mirror location:** `~/broomva/core/life/crates/autonomic/autonomic-core/data/rcs-parameters.toml`
- **Authoritative source:** `~/broomva/research/rcs/latex/parameters.toml` (this repo)
- **Sync script:** `~/broomva/core/life/scripts/sync-rcs-parameters.sh` — rewrites the mirror header and copies the paper body verbatim
- **Drift policy:**
  - After editing this repo's `parameters.toml`, run `bash ~/broomva/core/life/scripts/sync-rcs-parameters.sh` and commit the mirror update in a separate life-repo PR.
  - The Rust test `rcs_canonical_parameters_reproduce_paper_lambdas` (in `autonomic-core`) verifies the mirror's computed λᵢ match the paper's `[derived.lambda]` values to <1e-3. Numeric drift fails that test.
  - **Structural drift** (new fields, removed levels) is NOT auto-caught — the sync script is run manually. If you add fields to the TOML schema, update `CanonicalLevel` in `rcs_budget.rs` and re-run sync in the same Life PR.

Never edit the mirror by hand. If CI in life reports canonical-parameter test failures, the fix is almost always "re-run the sync script on the life side."

## Forthcoming

- **Integration test end-to-end strengthening** (life-repo follow-up): replace the current reconstruction-style test in `rcs_validation.rs` with one that observes the actual autonomic daemon's `HomeostaticState` and asserts `lambda_1 > 0` against real runtime state. Work in progress.
- **L0 and L2 estimators** (life-repo): `MarginEstimator::for_l0` (hooking `aios_runtime` tick stats) and `MarginEstimator::for_l2` (bridging `autoany-core::loop_engine`). Not yet implemented — scope of the F2 PR was L1 only (the only level with direct `HomeostaticState` observability).

## Key References

- Eslami & Yu (2026), arXiv:2603.10779 — 5-level agency, stability budget
- Keramati & Gutkin (2014) — homeostatic drive = Lyapunov = reward
- Ashby (1952) — ultrastability, requisite variety
- Beer (1972) — viable system model, recursive viability
- Quijano (2017, 2026) — population dynamics for distributed control
- Chacon-Chamorro et al. (2025) — cooperative resilience in MAS
- Zhang et al. (2025), arXiv:2510.04618 — Agentic Context Engineering (ACE); see `rem:context-collapse`

## Conventions

- Language: English for papers and code, Spanish for MAIA capstone deliverables
- LaTeX: One shared preamble in `latex/preamble.tex`, per-paper main files
- Citations: BibTeX in `latex/references.bib`
- Obsidian: All docs use YAML frontmatter with wikilinks for cross-referencing
- Entity pages: Concepts surfaced here promote to `research/entities/concept/`
