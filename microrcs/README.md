# microRCS — Single-File Recursive Controlled System Baseline

Karpathy-style minimal Python artifact that empirically validates the RCS thesis
on real LLM reasoning. One file, four levels of recursive control, four
falsifiable hypotheses, paper-grade headline result.

**Spec:** `docs/superpowers/specs/2026-05-01-microrcs-llm-baseline-design.md`
**Plan:** `docs/superpowers/plans/2026-05-01-microrcs-llm-baseline.md`

## Quick start

```bash
pip install anthropic numpy matplotlib
export ANTHROPIC_API_KEY=...

# Smoke run (~3 min, ~$0.30):
python microrcs.py run --quick

# Default run (~30 min, ~$3-5):
python microrcs.py run

# Paper-grade run (~3 hr, ~$30):
python microrcs.py run --paper

# Inspect lineage:
python microrcs.py trace <event_id> --log reports/<run_id>/.../events.jsonl

# H4 test (force λ_2 < 0):
python microrcs.py run --break-budgets
```

## What it does

For four ablation conditions (`flat / +autonomic / +meta / full`):

1. Spins up a workspace with `helpers/`, `memory/`, `scratch/`, `TASK.md`.
2. Runs each task in `REFERENCE_SUITE` (5 tasks: math, code, logic, QA, planning).
3. The L0 plant is an LLM with `bash` and `submit` tools. It reads `memory/`,
   writes new entries with frontmatter, edits `helpers/`, ultimately submits.
4. After each task L1 (homeostatic gate) inspects rolling failure rate and may
   switch L0's mode (BASE/COT/SCRATCHPAD/VERIFY).
5. After each epoch L2 (meta-controller) reads the memory graph and helper
   diffs and proposes mutations: promote helpers to next epoch's starter,
   promote memory `draft → canonical`, append learned rules to L0's prompt.
6. L3 (governance) fires rarely, adjusts caps and the frontmatter schema.
7. Computes `pass^k`, bootstrap CI, and `λ̂ᵢ` per level via Lyapunov decay fit.
8. Generates `reports/<run_id>/report.html` with four plots and headline result.

## Output structure

```
reports/<run_id>/
├── report.html           # human-readable
├── metrics.json          # all numbers
├── lambda_comparison.json
├── episodes/             # per-episode trace JSONL
└── workspace_diffs/      # before/after of helpers + memory
```

## What it validates (4 falsifiable hypotheses)

- **H1:** Full L0+L1+L2+L3 outperforms L0-only on `pass^k` (paired bootstrap, p<0.05)
- **H2:** Empirical `λ̂ᵢ > 0` for every level (95% CI excludes 0)
- **H3:** Each level contributes — removing one degrades `pass^k`
- **H4:** Forcing `λᵢ < 0` (e.g., `--break-budgets`) breaks Lyapunov decay

## Architecture (one paragraph)

The agent at L0 is a bitter-lesson-shaped bash loop with an editable
frontmatter-graph workspace; L1/L2/L3 are typed RCS controllers above it,
each with its own Lyapunov function, shield, and cadence gate (loaded from
`../data/parameters.toml`). All level mutations flow through one
`apply_decision_downward()` function and emit `PARAM_CHANGE` events into an
append-only event log; lineage is by construction. A `LambdaMonitor` polls
the log to fit `exp(−λt)` to V_k(t) live; a `StabilityCircuitBreaker`
freezes mutations at level k+1 if `λ̂ᵢ + 2σ < 0` (last-resort meta-shield).
Reasoner is a Protocol — Anthropic implementation full, OpenAI/Ollama stubs.

## Citing

If you cite this artifact in a paper, please reference the underlying
formalism in P0 Foundations:

> Escobar-Valbuena, C. D. (2026). *Recursive Controlled Systems: A Formal
> Framework for AI Agent Stability.* `research/rcs/papers/p0-foundations/`

## License

See repo root.
