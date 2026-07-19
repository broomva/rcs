# AIDE²-shape harness-evolution — Run 1 pre-registration

**Experiment:** `aide2-run1` · **Ticket:** BRO-1947 · **Date registered:** 2026-07-18
**Infra:** BRO-1943 (CliPlant + GenerationLoop, merged `2df1d4a`) · **Env fidelity:** BRO-1948 (swebench-spec sandbox, merged `15f2161`)

This document is the pre-registration gate for the run. Per BRO-1071 commitments #2/#5/#6
(the $6K budget of #1 is mooted by subscription compute), it is committed to the repo
**before any `claude -p` call**. The frozen splits + locked hypothesis below are the
anti-adaptive-overfitting mechanism the private-gate design rests on; they are not
revised post-hoc.

## The recipe

An AIDE²-shape (Weco AI, 2026) bi-level loop on our own stack:

- **Inner agent** — `claude -p` (`ClaudeCliRunner`, model `claude-sonnet-4-6`) runs one
  SWE-bench-Lite episode agentically in the instance's COW workspace. Scored *only* by the
  local pytest/`bin/test` verifier on the workspace diff (P11 — the CLI's self-report never
  sets the score). Subscription-OAuth billed (~$0 marginal; deny-by-default env filter proven
  by bogus-key dogfood).
- **Outer loop** — `GenerationLoop` proposes one `HarnessConfig` mutation per generation
  (`make_cli_proposer`, model `claude-opus-4-7`): `system_prompt_append` (coaching ≤800 chars),
  `max_turns` (20–120), `allowed_tools` (subset of the 6-whitelist). It **cannot** change the
  model or expand tools; fails closed to a no-op so the gate stays the safety boundary.
- **Private gate** — a candidate is accepted **iff** it strictly beats best-so-far on the
  held-out **holdout** split. The proposer sees only train scores + the accept bit — the raw
  holdout signal never leaks (guarded + tested in `GenerationLoop`).

## Commitment #2 — LOCKED hypothesis

> **CONFIRM** iff the evolved best `HarnessConfig` beats the genesis config on the **untouched
> `final_test` split** (scored only in `final_report()`, never by the gate) by a **paired
> positive margin** (mean `final_test` score of evolved − genesis > 0 over the n = 3
> final instances, n = 3). **DISCONFIRM** otherwise.
>
> `overfit_gap = holdout_score(best) − final_test_score(best)` is reported **regardless of
> sign**. `max_generations = 5` bounds the accept-bit adaptive-overfitting of the holdout.

The criterion is **computed mechanically** by `GenerationLoop.final_report()`, which scores
BOTH the evolved `best` and the frozen `genesis` config on `final_test` and emits
`final_test_margin` (evolved − genesis) + the `confirmed` boolean — there is no post-hoc analyst
scoring pass. `final_report()` is called once and its `final_report.json` is not re-scored on a
resume (`aide2_run` guards idempotency), so "scored once" holds under the "re-run to resume"
pacing.

**Statistical honesty (pre-committed):** n = 3 is a **directional** paired signal,
not a high-powered significance test — a sign/McNemar test at this n cannot reach significance,
and that is stated up front, not discovered after. What Run 1 establishes: (a) the full AIDE²
pipeline runs end-to-end on subscription compute against a **fidelity-correct** verifier (BRO-1948),
(b) a directional generalization estimate + `overfit_gap`, (c) whether the private gate accepts
*any* real improvement within 5 generations. A higher-powered run needs the Linux-parity /
sphinx-tox work in BRO-1949 to widen the gradeable pool.

## Commitment #5 — frozen splits

Instances are the **oracle-curated** pool from `validated_instances.json` — each proven, with no
LLM, to (a) install with pinned deps today and (b) have its FAIL_TO_PASS flip from fail@base to
pass@gold-patch (source edits genuinely exercised — the BRO-1948 property). Splits are **disjoint**
(re-checked by `GenerationLoop.__init__`) and deterministically stratified by repo
(`make_splits.py`).

Validated pool: **19** instances (18 sympy + 1 flask; all 18 sympy candidates passed the oracle,
flask-4045 excluded on install). 12 enter the splits; 7 sympy held in reserve for a future
rotation/Run-2.

| split | n | repos | instance IDs |
|---|---|---|---|
| **train** | 6 | sympy 6 | `sympy-13971`, `sympy-14774`, `sympy-14817`, `sympy-15346`, `sympy-15609`, `sympy-18057` |
| **holdout** (private gate) | 3 | sympy 3 | `sympy-13480`, `sympy-13647`, `sympy-13915` |
| **final_test** (unbiased, scored once) | 3 | flask 1 + sympy 2 | `pallets__flask-4992`, `sympy-12171`, `sympy-13471` |

Disjoint by construction (`make_splits.py`) and re-checked at `GenerationLoop.__init__`. The
one flask instance is stratified into `final_test`, giving the unbiased split a single cross-repo
generalization data point (evolved harness tuned on sympy, tested on flask + held-out sympy).

## Commitment #6 — negative-result publication

The result — **including a null or negative** — lands in `microrcs/THESIS_VALIDATION.md` within
one week of the run completing, via `final_report()` on the untouched split. No silent shelving.

## Scope & limitations (honest, pre-committed)

- **Substrate concentration.** The macOS venv sandbox (no Docker) cleanly grades only
  self-contained, deterministic repos — **sympy** (platform-independent math) is the reliable
  reservoir, plus **flask**. Instances whose PASS_TO_PASS include Linux-specific behavior
  (several pytest/requests/pylint cases) are excluded by the oracle gate because they would only
  add scoring noise. The pool is therefore **sympy-dominant**; the generalization claim is
  **within-distribution** (held-out sympy/flask), not cross-repo. Recovering Linux parity
  (container/Lima backend) + tox repos (sphinx) is BRO-1949.
- **No temperature/seed control** in the subscription CLIs → variance is via repeats, not seeds
  (same posture as temperature=1.0 API runs).
- **The "private" holdout is a 1-bit selection channel.** Because `best` only advances on
  acceptance and seeds the next proposal, the loop structurally hill-climbs the holdout over
  generations (inherent to any private-gate RSI loop, AIDE² included). `max_generations=5` bounds
  it and `final_test` is the unbiased estimate.

## Pacing (P12 + P9)

Cross-session, external-trigger, paced-over-rate-windows → **P12 persist**, not an in-context
loop. Each `aide2_run --batch N` invocation runs a bounded number of generations, atomically
checkpoints `run_state.json` (resumable across the subscription session wall), then yields.
Compose with `p9 wait-for` between batches. Low parallelism, days not hours — the subscription is
shared with live agent work.

## Reproduction

```bash
cd microrcs
# $0 — re-verify the curated pool (no LLM):
python3 -m scripts.curate_instances --candidates experiments/aide2-run1/candidates.json \
    --out experiments/aide2-run1/validated_instances.json --need 12
# $0 — wiring proof (constructs the loop, provisions workspaces, no LLM):
python3 -m scripts.aide2_run --check-only
# the paced run (subscription-billed, resumable) — spend is opt-in via --run:
python3 -m scripts.aide2_run --run --batch 2   # then re-run --run to resume; final_report ONCE at gen 5
```

## Commitments checklist

- [x] #1 Budget — mooted by subscription compute (~$0 marginal; rate-window-bound, paced).
- [x] #2 Hypothesis locked (above) — no post-hoc criterion change.
- [x] #5 Splits frozen in-repo before any LLM call (this PR).
- [x] #6 Negative-result publication path committed (THESIS_VALIDATION.md, 1 week).
- [x] #3 Model tier — sonnet inner / opus proposer (cheap to sweep on subscription).
- [x] #4 Phase-3 gating — N/A for this run (RE-Bench out of scope; AIDE²-recipe re-scope).
