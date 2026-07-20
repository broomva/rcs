# P12-persist run prompt — AIDE²-run1 (BRO-1947)

> **SUPERSEDED (2026-07-19). DO NOT CONTINUE THIS RUN.** Generation 1 returned a
> determined outcome: genesis holdout = 1.000 (12/12 episodes) ⟹ the strict
> private gate is unsatisfiable ⟹ DISCONFIRM-by-ceiling. See the AIDE²-run1
> section of `microrcs/THESIS_VALIDATION.md`. The successor is the three-arm
> ignition experiment (workspace entity `recursion-relocates-guarantees`),
> which gets its own pre-registration + PROMPT.md. This file is retained as the
> run's P12 record only.

You are continuing the **paced** AIDE²-shape harness-evolution run. The pre-registration is
LOCKED and MERGED (`broomva/rcs` main, PRs #69 fidelity + #70 pre-registration). Splits +
hypothesis are frozen in git — **do not modify them**. Your only job is to advance the run one
bounded batch at a time until `final_report.json` exists, then record the result.

## The one command (run from `microrcs/`)

```bash
python3 -m scripts.aide2_run --run --batch 1
```

- Runs **one generation** (genesis holdout on the first step, then one candidate proposal +
  train + holdout scoring), atomically checkpoints `run_state.json`, and exits.
- **Resume is automatic** — re-running picks up from `run_state.json`. No state to paste.
- At `n_steps == 5` (`max_generations`) it writes `final_report.json` **once** (idempotent — a
  completed run is not re-scored / re-billed).

## Pacing (HARD rules — this is why it's persist, not an in-context loop)

- **One `--batch 1` per iteration.** Each generation is ~9–12 `claude -p` sonnet episodes; the
  subscription rate window is shared with live agent work (and with the agent running THIS
  loop). Running all 5 generations at once hits the session wall.
- **Between batches, yield to the rate window** — `p9 wait-for` cadence or a fresh persist
  iteration later. Days, not hours. Never `sleep`-spin.
- If episodes start aborting with rate/auth errors, STOP and wait for the window to reset;
  do not hammer.

## Completion (commitment #6)

When `final_report.json` exists:
1. Read it: `final_test_margin` (evolved − genesis), `confirmed` (bool), `overfit_gap`.
2. Append a ledger row to `microrcs/THESIS_VALIDATION.md` — the result **regardless of sign**
   (CONFIRM or DISCONFIRM), within one week. No silent shelving.
3. Commit `final_report.json` + `lineage.jsonl` + the ledger row on a branch → PR → merge.

## Guardrails

- Billing is subscription-OAuth (bogus-key smoke reconfirmed). `aide2_run` needs `--run` to
  spend; a bare invocation is a $0 wiring check.
- The proposer never sees holdout/final scores (guarded in `GenerationLoop`). Don't route
  around it.
- Do NOT re-curate or re-split — the pre-registration is committed. If a split instance
  becomes ungradeable mid-run, record it; do not swap it.

## Current resume state

- **run_state.json**: absent until the first `--batch 1` runs (fresh run) — then it carries
  `n_steps`, `best_holdout`, `best_config`, `history`.
- **max_generations**: 5. **Arm**: inner `claude-sonnet-4-6`, proposer `claude-opus-4-7`.
- **Splits**: `splits.json` (train 6 / holdout 3 / final 3; flask-4992 is the one final-test
  cross-repo point). **Pool**: `validated_instances.json` (19 valid; 7 sympy in reserve).
