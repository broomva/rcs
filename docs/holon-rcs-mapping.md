---
title: "holon → RCS Mapping Table"
tags:
  - rcs
  - holon
  - mapping
  - control-theory
  - horizontal-composition
aliases:
  - holon RCS mapping
  - RCS holon instantiation
created: "2026-09-06"
updated: "2026-09-06"
status: draft
linear: BRO-2441
related:
  - "[[RCS Index]]"
  - "[[life-rcs-mapping]]"
  - "[[recursive-controlled-system]]"
  - "[[self-referential-closure]]"
  - "[[p6-horizontal-composition/README]]"
  - "[[harness-axis-self-improvement]]"
  - "[[self-improvement-verifier-ceiling]]"
---

# holon → RCS Mapping Table

**Linear:** BRO-2441 (arc ticket)
**Purpose:** Map the holon harness (`apps/holon`, `github.com/broomva/holon`) onto the RCS
7-tuple slot by slot, the factory onto Paper 6's horizontal composition, and the planned
training loop onto the EGRI 9-tuple; state where the code diverges from the formalism and
what the formalism then forces. Companion to [[life-rcs-mapping]], which does the same for
Life. Human-read narrative with the figure: `docs/specs/2026-09-06-holon-system-map.html` §8.

**Status, stated first.** RCS is *not represented in holon's code today.* Nothing in the crate
implements `RecursiveControlledSystem<L>` from
`core/life/crates/aios/aios-protocol/src/rcs.rs`, `research/rcs/data/parameters.toml` has no
holon block, and no stability margin has been measured. What this document records is that
holon's types line up with the tuple almost slot for slot, so the instantiation is
mechanical once someone chooses to do it, and that three places disagree with the formalism
on purpose.

## Notation

| Symbol | RCS role |
|--------|----------|
| X | state space |
| Y | observation space |
| U | control input space |
| f | dynamics X × U → X |
| h | observation map X → Y |
| S | safety shield U × X → U |
| Π | controller, itself an RCS one level up |
| D | homeostatic drive (Lyapunov candidate) |

Paths are relative to `apps/holon/` unless stated. Symbols are cited instead of line numbers,
because line numbers in this repo drift on every merge (seven P20 rounds moved most of them).

## The recursion applied to holon

Definition (RCS), items 2–4: X_{i+1} includes the parameters of L_i's controller; Y_{i+1} is
derived from L_i's performance; U_{i+1} modifies L_i's behaviour. Applied to holon:

- **The weights are X₂ by definition.** Context blocks (`trait Context`, `src/traits.rs`) and
  tool schemas (`Tool::schema`) are the parameters of Π₀ (the model call). They are therefore
  the *state of the level above the unit*, and editing them is U₂. This is why the
  self-improvement loop is L2 and never part of the unit — the perceptron framing and the RCS
  recursion agree on where the weights live.
- **A unit spans L0 fully and L1 thinly.** L1 has no setpoint and no D₁; a run does not regulate
  toward an equilibrium, it runs to a stop. The one L1 regulator with a dwell time is the
  factory's quota breaker.
- **L3 is the CLAUDE.md invariants plus the seam registry.** The system map itself is a model
  of the hierarchy inside Π₃, which is the self-referential closure condition
  (Def. Self-referential RCS).

## Level 0: the unit acting on the workspace

| RCS | Name | holon implementation | File |
|-----|------|----------------------|------|
| X₀ | Plant state | `Workspace { root, session_id }` + the run's transcript `Vec<Message>` | `src/types.rs`, `src/unit.rs` |
| Y₀ | Observation | tool results, the model's content `Block`s | `src/types.rs` |
| U₀ | Actuation | `ToolCall { id, name, input }` | `src/types.rs` |
| f₀ | Plant dynamics | the tool handler's effect on the root (`Tool::call`); bash · fs · workspace plugins | `src/plugins/{bash,fs}.rs` |
| h₀ | Sensor model | all tool results of a batch in **one** user message; `is_error` carried | `src/unit.rs` (the batch push in `run_cancellable`) |
| S₀ | Shield | the PreToolUse gate over Claude Code's own surfaces, fail-closed; `ask` and `updatedInput` are denials | `src/gate/{dispatch,verdict,surfaces}.rs`, `trait Gate` |
| Π₀ | Controller | the model call, framed by Context blocks and Tool schemas (= Σ₁) | `src/claude_direct/provider.rs`, `trait Provider` |
| D₀ | Task metric | none built in; the exogenous verifier of the training loop is its planned instance | — |

**Lens laws read as invariants.** get-put (a no-op control preserves state) is a run with no
tool calls leaving the root unchanged. put-get (an effect is observable) is CLAUDE.md's
"Tools fail with `Err`; a returned string reads to the model as success" — a failure
disguised as prose makes the observation stop reflecting the effect.

## Level 1: the unit regulating itself (thin)

| RCS | Name | holon implementation | File |
|-----|------|----------------------|------|
| X₁ | Internal state | `turn`, accumulated `Usage`, `Outcome`, the `CancellationToken` | `src/unit.rs` |
| Y₁ | Event stream | `Event { ts_ms, seq, session_id, kind }` through every `Sink`; per-unit `seq` totally orders one unit | `src/event.rs`, `trait Sink` |
| U₁ | Regulation | `UnitConfig { max_turns, max_tokens, effort }`, `RetryPolicy` backoff, the factory's pause and re-queue | `src/unit.rs`, `src/claude_direct/provider.rs`, `src/factory.rs` |
| f₁ | Transition | the step loop: build → post → dispatch on the stop-reason allowlist → gate → tools → repeat | `Unit::run_cancellable` |
| h₁ | Fold observer | `usage += resp.usage`, the turn counter — a trivial Mealy fold, no homeostatic state | `src/unit.rs` |
| S₁ | Shield | completion allowlist (unknown stop reason → exit 5), refusal checked before content, `check_assistant` transcript validator, budget exhaustion → 5 | `src/unit.rs` |
| Π₁ | Controller | the factory's quota classifier: a 429 with rate-limit headers is capacity and is backed off; without them it is the identity refusal and never retried (= Σ₂ slot) | `src/claude_direct/provider.rs`, `src/factory.rs` |
| D₁ | Drive | **none** — no setpoint at L1 | — |

**Self-observation cost, measured.** The paper's remark that self-measurement enters λ₁ as a
delay term has a holon number: the skills index was ~7k of a 9.8k-token tool run, so it
became an opt-in context (`--context skills`). That is a reduction of τ̄_self.

**Dwell time.** The quota breaker's pause (server `Retry-After`, capped by `--max-pause`,
else 30 s doubling per re-queue) is an average dwell time in the sense of
Def. (Average dwell time) — the only τ_a holon has today.

## Horizontal composition: the factory (Paper 6)

Paper 6 composes N depth-k instances into a depth-(k+1) RCS whose plant is ∏ X^(i), with an
aggregation operator h_H, a distribution operator d_H, and a coupling layer (δ, τ_p, α, σ, N).

| P6 object | The factory | File |
|-----------|-------------|------|
| X^(k+1) = ∏ X^(i) | N workers, each a `Unit` serving its own `MpscChannel` inbox | `Factory::run`, `serve` in `src/factory.rs` |
| h_H | the collector: results keyed by task position, `TaskFinished` events with the factory's own `seq` | `src/factory.rs`, `src/event.rs` |
| d_H | pull dispatch — one task per idle worker (`dispatch_idle!`) | `src/factory.rs` |
| S^(k+1) | one `CancellationToken`; the quota breaker holds the *queue*, not the collector; results always complete and in task order; stdout loss cancels | `src/factory.rs` |
| Π^(k+1) | the collector; above it, whatever chains factories (results → tasks, same `Envelope`) | `Task::envelope`, `TaskResult::from_envelope` |

| Coupling parameter | holon value | Consequence |
|--------------------|-------------|-------------|
| N | `--workers` | — |
| τ_p propagation delay | ≈ 0 in-process (mpsc); real once the socket `Channel` exists | enters β_H·τ̄_H |
| α directive authority | **total** for cancel (the token stops a worker inside a model call); partial for tasks | C2: α·L_d < min λ₀ — cancel must not destabilise a unit's own shield, which is why a cancelled run still returns its partial transcript |
| σ cross-instance observation | **0 through channels** (workers never observe each other); **> 0 through the shared workspace** — the implicit second medium | C4: N·σ < reserve. `--isolate worktree` is the act of setting σ to zero; without it two workers on one root race |
| δ signal decay | **undefined** — envelopes do not decay | safe in a star with one collector and no cycles; **a backward pass of critique envelopes on reversed edges creates a cycle**, so C3 (δ > 1/τ_p) forces a hop count or a budget on critiques (EGRI Law 2 applied laterally) |

**The fleet exception.** Def. (Fleet RCS) composes *full* L0–L3 hierarchies. Factory workers
share one provider, one gate and one set of weights: they are L0 instances under one L1, one
L2 and one L3. So the factory is horizontal composition **at L0 only** — one RCS with a
product plant, not a fleet. It becomes a fleet, and λ_H becomes live, only when workers carry
their own weights and their own training loops.

**Lemma (aggregation consistency) obligation.** P6 requires (h_H, d_H) to form a lens on the
composed system. For the factory: h_H is the position-keyed result vector (surjective onto the
result space by construction — every task has exactly one row); d_H right-inverts it on its
range because a dispatched task's result lands at that task's position. The commuting square
holds for the star; it is *not* established for a general graph runner with routing by
envelope kind, and must be re-checked there.

## Level 2: the training loop as the EGRI 9-tuple (planned)

Def. (EGRI 9-tuple as Σ₂), instantiated by the loop designed in this arc. None of the right
column exists yet; the file names are where each piece would land.

| RCS | EGRI | holon (planned) | File (would be) |
|-----|------|-----------------|-----------------|
| X₂ | artifact state | `weights.json` — Context blocks + tool descriptions, content-hashed | `src/plugins/weights.rs` |
| Y₂ | outcome (score, C) | held-out pass rate, tokens, regression count | `src/train.rs` |
| U₂ | mutation operators | one localized edit by the proposer holon | `src/train.rs` |
| f₂ | trial execution | propose → `Factory::run(train)` → verify → select | `src/train.rs` |
| h₂ | evaluator | the exogenous verifier: exit code · regex · file state · a command that exits 0 — **never a model** | `src/train.rs` (verify module) |
| S₂ | immutable evaluator + budget + rollback | verifier never imports the proposer (module boundary + a test that fails on a cross-import); token and iteration budget; incumbent restored by hash | `src/train.rs`, `tests/train.rs` |
| Π₂ | proposer + selector | proposer holon jailed to the weights file; keep rule = more passes ∧ 0 regressions ∧ tokens ≤ 1.2× | `src/train.rs` |

**Two EGRI laws land directly.**

- *Law 1 (mutation–evaluation proportionality)*, |M| ≤ capacity(σ): this is Ashby's requisite
  variety and the same statement as [[self-improvement-verifier-ceiling]] — the loop only
  amplifies what the verifier can judge.
- *Law 2 (budget closure)*: the token budget is a Lyapunov function on the loop; it must
  decrease per trial and the loop halts at zero.

## Level 3: governance

| RCS | holon implementation | File |
|-----|----------------------|------|
| X₃ | the invariants; the seam registry; the conformance documents | `CLAUDE.md`, `conformance/{cases,cases.holon,contract}.json` |
| Y₃ | `make check` · `make conformance` · the P20 round ledgers on each PR | `Makefile`, PR comments |
| U₃ | an invariant added or removed; a seam bound to a standard | `CLAUDE.md` |
| f₃ | the workspace self-evolution protocol (pattern → log → doc → invariant) | workspace `CLAUDE.md` |
| S₃ | the workspace G1–G4 gates via the real `control-gate-hook.sh`, which holon's gate itself consults | `tests/fixtures/real-gate/` |
| Π₃ | `CLAUDE.md` + the seam registry + the system map (closure: a model of the hierarchy inside the controller) | `docs/specs/2026-09-06-holon-system-map.html` |

## Where the code disagrees with the formalism (deliberate)

1. **The shield is a restriction, not a projection.** Def. (Controlled System) defines S as the
   argmin projection onto the safe set — the *nearest safe input*. Holon's gate returns
   allow or deny and treats a hook's `updatedInput` as a denial, because no human is present
   to audit a rewrite. Formally S_holon(ũ, x) ∈ {ũ, ∅}. Implementing the witness trait would
   return an empty control on deny rather than a nearest-safe one. This should stay a
   divergence.
2. **No homeostatic drive at L1.** A unit has no setpoint. The Lyapunov candidate the
   formalism wants at L1 has no holon instance; the first candidate is the exogenous
   verifier of the loop, which is L2's h₂, not L1's D₁.
3. **The factory is not a fleet.** See above: horizontal composition at L0 only, because the
   weights are shared.

## What the stability budget forces

- **H6 time-scale dilation.** τ_a(i+1) ≥ c·τ_a(i), c ≈ 10. Weight acceptance must be at least
  an order of magnitude rarer than forward passes. A ~90 % rejection rate *is* that ratio —
  the figure AIDE² reported ([[aide2-recursive-self-improvement]]) and the reason the loop
  design expects most proposals to fail. Updates apply only at run boundaries because
  weights are gathered once per run.
- **C3 for the backward pass.** Critique envelopes on reversed edges introduce a cycle;
  without decay or a hop budget they are a standing wave. Any graph runner that routes
  critiques must carry δ.
- **C4 for the shared workspace.** N·σ < reserve. Worktree isolation is the σ = 0 setting;
  it is not optional once N > 1 units write to one root.
- **Self-observation cost.** Every context block the unit loads about itself is τ̄_self; keep
  the skills index opt-in and measure any new context block's token share before it is
  default-on.

## Dependency chain to instantiate

Upstream (interfaces): `core/life/crates/aios/aios-protocol/src/rcs.rs`
(`RecursiveControlledSystem<L>`, `LyapunovCandidate<L>`, `StabilityBudget`);
`research/rcs/data/parameters.toml` (canonical parameters; a `[[levels]]` block per holon level
would go here, regenerated into `latex/parameters.tex` by `scripts/gen_parameters_tex.py`).

Implementors (holon): `src/unit.rs` (L0 and thin L1), `src/factory.rs` (the composed level),
`src/train.rs` (L2, planned). A fold over the factory's trace into the five budget terms per
level is the missing observer — the same shape as `core/life/crates/arcan/arcand/src/rcs_observer.rs`.

Downstream: `research/rcs/tests/test_stability_budget.py` (would gain holon rows),
`docs/specs/2026-09-06-holon-system-map.html` §8 (the figure), this document. The
conformance files do not move: the wire is untouched.

## Cross-level data flow (holon)

```
tool result  ──h₀──▶  one user message ──▶ model call (Π₀ = Σ₁)
                                            │ ToolCall (U₀)
                                            ▼
                                     Gate S₀ (allow | deny)
                                            │
                                     handler f₀ → workspace X₀
Event stream Y₁ ──▶ Sink (trace) ──▶ usage fold h₁ ──▶ max_turns / allowlist / exit codes (S₁, U₁)
                                            │
                        factory: results h_H ──▶ TaskResult ──▶ next factory's Task (d_H)
                                            │
training loop (planned): Factory::run(train) ──▶ verifier h₂ ──▶ proposer U₂ ──▶ weights X₂ ──▶ next run's Context
governance: CLAUDE.md invariants + seam registry (Π₃) ──▶ what the loop may mutate
```
