---
title: "Life Agent OS → RCS Mapping Table"
tags:
  - rcs
  - life-agent-os
  - mapping
  - control-theory
aliases:
  - RCS Mapping Table
  - Life RCS Mapping
created: "2026-04-16"
updated: "2026-04-16"
status: draft
linear: BRO-704
related:
  - "[[RCS Index]]"
  - "[[2026-04-16-rcs-formalization-design]]"
---

# Life Agent OS → RCS Mapping Table

**Linear:** BRO-704 (parent: BRO-697)
**Purpose:** Concrete mapping of every Life Agent OS Rust type to its RCS formal component, with file paths and line numbers.

## Notation

Each row maps an RCS 7-tuple component to its Life implementation:

| Symbol | RCS Role |
|--------|----------|
| X | State space |
| Y | Observation space |
| U | Control input space |
| f | Dynamics (state transition) |
| h | Observation map |
| S | Safety shield |
| Π | Controller |
| D | Homeostatic drive (Lyapunov candidate) |

**Base paths:**
- Life monorepo: `core/life/`
- Autoany: `core/autoany/`
- Workspace root: `~/broomva/`

---

## Level 0: External Plant

The agent controls an external system (codebase, microgrid, conversation).

| RCS | Name | Rust Type / Implementation | File (relative to `core/life/`) | Line |
|-----|------|---------------------------|--------------------------------|------|
| X₀ | Plant state | Application-dependent (e.g., microgrid SoC, PV output, load; or codebase file tree) | — | — |
| Y₀ | Sensor readings | Application-dependent (e.g., CT clamps, irradiance; or tool output, file contents) | — | — |
| U₀ | Actuation commands | Tool calls: `ToolDirective` / tool execution results | `crates/arcan-harness/src/` | — |
| f₀ | Plant dynamics | External physics / system behavior (not modeled in Rust) | — | — |
| h₀ | Sensor model | Tool output parsing, file reads, API responses | — | — |
| S₀ | Safety limits | Budget gates in agent loop (USD hard stop at limit) | `crates/arcan/arcan/src/shell.rs` | 1911–1929 |
| Π₀ | Agent | `run_agent_loop()` — 8-phase cycle, max 24 iterations | `crates/arcan/arcan/src/shell.rs` | 1873 |
| D₀ | Task metric | Task completion: `‖load_served − load_demanded‖²` or tool success rate | — | — |

**Agent loop phases (shell.rs):**
1. Reconstruct session state from Lago journal
2. Call LLM provider via `Provider` trait (`crates/arcan-core/src/provider.rs`)
3. Execute tool directives
4. Apply state patches (`AppState` — `crates/arcan-core/src/state.rs`, JSON Patch-based)
5. Stream responses via multi-format SSE (OpenAI, Anthropic, Vercel)
6. Persist all events to redb via Lago
7. Check budget constraints
8. Loop or exit

**Time scale:** Seconds to minutes (dispatch decisions every agent iteration).

---

## Level 1: Agent as Plant (Autonomic)

The agent's own internal state is the system being regulated.

| RCS | Name | Rust Type | File (relative to `core/life/`) | Line |
|-----|------|-----------|--------------------------------|------|
| X₁ | Homeostatic state | `HomeostaticState` | `crates/autonomic/autonomic-core/src/gating.rs` | 271 |
| | — operational pillar | `OperationalState` | `crates/autonomic/autonomic-core/src/gating.rs` | 60 |
| | — cognitive pillar | `CognitiveState` | `crates/autonomic/autonomic-core/src/gating.rs` | 87 |
| | — economic pillar | `EconomicState` | `crates/autonomic/autonomic-core/src/economic.rs` | 42 |
| | Agent state vector | `AgentStateVector` (8 fields: progress, uncertainty, risk, budget, error_streak, context_pressure, side_effect_pressure, human_dependency) | `crates/aios/aios-protocol/src/state.rs` | 399 |
| Y₁ | Event stream | `EventKind` (55+ variants: session lifecycle, tool execution, text streaming, knowledge ops, custom events) | `crates/aios/aios-protocol/src/event.rs` | 206 |
| U₁ | Gating profile | `GatingProfile` (side_effects, approval_risk, tool_calls, file_mutations, network, shell) | `crates/aios/aios-protocol/src/mode.rs` | 37 |
| | — combined output | `AutonomicGatingProfile` (operational + economic gates + rationale + advisory_events) | `crates/autonomic/autonomic-core/src/gating.rs` | 46 |
| | — economic gates | `EconomicGates` (economic_mode, max_tokens_next_turn, preferred_model, expensive_tools, replication) | `crates/autonomic/autonomic-core/src/gating.rs` | 16 |
| | — operating mode | `OperatingMode` (Explore, Execute, Verify, Recover, AskHuman, Sleep) | `crates/aios/aios-protocol/src/mode.rs` | 15 |
| | — economic mode | `EconomicMode` (Sovereign, Conserving, Hustle, Hibernate) | `crates/autonomic/autonomic-core/src/economic.rs` | 15 |
| f₁ | State transition (fold) | `fold()` — pure deterministic reducer: `(X₁, Y₁, seq, ts) → X₁'`, 40+ event handlers | `crates/autonomic/autonomic-controller/src/projection.rs` | 23 |
| h₁ | Event observation | Event → state update mapping (Mealy machine, implicit in fold) | `crates/autonomic/autonomic-controller/src/projection.rs` | 23 |
| S₁ | Hysteresis gate | `HysteresisGate` (enter/exit thresholds + `min_hold_ms` cooldown) | `crates/autonomic/autonomic-core/src/hysteresis.rs` | 16 |
| Π₁ | Autonomic rule engine | `evaluate()` — evaluates 7 rule sets, produces gating profile | `crates/autonomic/autonomic-controller/src/engine.rs` | 17 |
| | — decision merge | `merge_decisions()` — most-restrictive-wins per field | `crates/autonomic/autonomic-controller/src/engine.rs` | 39 |

**Rule modules (7 files in `crates/autonomic/autonomic-controller/src/`):**

| Rule Set | File | Governs |
|----------|------|---------|
| Operational | `operational_rules.rs` | Error streak, success tracking |
| Cognitive | `cognitive_rules.rs` | Context pressure, token exhaustion |
| Economic | `economic_rules.rs` | Balance-to-burn ratio |
| Knowledge | `knowledge_rules.rs` | Knowledge health, promotion monitoring |
| Strategy | `strategy_rules.rs` | Drift alerts, decision logging |
| Evaluation | `eval_rules.rs` | Evaluation quality tracking |
| Belief | `belief_rules.rs` | Anima belief violations |

**Lyapunov D₁:** Homeostatic drive across three pillars:
```
D₁ = α_op·‖op − op*‖² + α_cog·‖cog − cog*‖² + α_econ·‖econ − econ*‖²
```

**Key insight — fold-as-observer:** `fold()` is a degenerate Luenberger observer with `A = I` (state persists between events) and full gain on measurements. `HomeostaticState` is a sufficient statistic for regulation — all 7 rule sets consume `&HomeostaticState`, never raw events.

**Time scale:** Per-turn (every agent iteration, ~seconds).

---

## Level 2: Meta-Control (EGRI)

The EGRI loop optimizes the controller's parameters and architecture.

| RCS | Name | Rust Type | File (relative to `core/autoany/`) | Line |
|-----|------|-----------|-----------------------------------|------|
| X₂ | Controller config | Generic `A` (artifact) in `EgriLoop<A, P, X, E, S>` | `autoany-core/src/loop_engine.rs` | 28 |
| Y₂ | Evaluation scores | `Outcome` { score: `Score`, constraints_passed, constraint_violations, evaluator_metadata } | `autoany-core/src/types.rs` | 103 |
| | — score type | `Score` enum: `Scalar(f64)` or `Vector(HashMap<String, f64>)` | `autoany-core/src/types.rs` | 54 |
| | — comparison outcome | `ComparisonOutcome` { winner, confidence, round } (for debate protocol) | `autoany-core/src/types.rs` | 322 |
| U₂ | Mutations | `Mutation` { operator, description, diff, hypothesis } | `autoany-core/src/types.rs` | 80 |
| f₂ | Trial execution | `EgriLoop::run()` → propose → execute → evaluate → select → promote | `autoany-core/src/loop_engine.rs` | 28 |
| | — execution result | `ExecutionResult` { duration_secs, exit_code, error, output } | `autoany-core/src/types.rs` | 91 |
| h₂ | Evaluator scoring | `Evaluator` trait: `evaluate(artifact, execution) → Outcome` | `autoany-core/src/evaluator.rs` | 9 |
| | — comparative eval | `ComparativeEvaluator` trait: `compare(task, incumbent, candidate) → ComparisonOutcome` | `autoany-core/src/comparative_evaluator.rs` | 25 |
| S₂ | Safety shield (3 laws) | Budget closure + rollback + immutable evaluator | (see below) |
| | — budget controller | `BudgetController` { max_trials, total_time, trials_used, start_time } | `autoany-core/src/budget.rs` | 7 |
| | — budget spec | `Budget` { max_trials, time_per_trial_s, total_time_s, token_budget, cost_budget } | `autoany-core/src/spec.rs` | 76 |
| | — constraint checker | `ConstraintChecker` trait: `check(execution) → Vec<String>` | `autoany-core/src/constraint.rs` | 7 |
| | — runtime constraint | `RuntimeConstraint` { max_duration_secs } | `autoany-core/src/constraint.rs` | 13 |
| | — promotion controller | `PromotionController<A>` { best_artifact, best_state_id, current } | `autoany-core/src/promotion.rs` | 5 |
| Π₂ | Proposer + selector | (see below) | | |
| | — proposer | `Proposer` trait: `propose(artifact, ledger) → (Mutation, Artifact)` | `autoany-core/src/proposer.rs` | 9 |
| | — selector | `Selector` trait: `select(candidate_score, best_score) → Decision` | `autoany-core/src/selector.rs` | 6 |
| | — default selector | `DefaultSelector` { policy: `PromotionPolicy`, direction: `Direction`, threshold } | `autoany-core/src/selector.rs` | 11 |
| | — decision | `Decision` { action: `Action`, reason, new_state_id } | `autoany-core/src/types.rs` | 135 |
| | — action | `Action` enum: Promoted, Discarded, Branched, Escalated | `autoany-core/src/types.rs` | 115 |

**Supporting types:**

| Type | File | Line | Purpose |
|------|------|------|---------|
| `TrialRecord` | `autoany-core/src/types.rs` | 144 | trial_id, timestamp, parent_state, mutation, execution, outcome, decision |
| `Ledger` | `autoany-core/src/ledger.rs` | 12 | Append-only trial log with replay, state history |
| `LoopSummary` | `autoany-core/src/loop_engine.rs` | 48 | total_trials, promoted/discarded/escalated counts, baseline/final scores |
| `ProblemSpec` | `autoany-core/src/spec.rs` | 7 | Full problem configuration: objective, constraints, artifacts, budget, promotion |
| `PromotionPolicy` | `autoany-core/src/spec.rs` | 98 | KeepIfImproves, Pareto, Threshold, HumanGate, Comparative |
| `Direction` | `autoany-core/src/types.rs` | 160 | Minimize or Maximize |
| `AutonomyMode` | `autoany-core/src/types.rs` | 168 | Suggestion, Sandbox, AutoPromote, Portfolio |
| `StrategyReport` | `autoany-core/src/strategy.rs` | 10 | successful_operators, failure_patterns, recommended_order |
| `DeadEndTracker` | `autoany-core/src/dead_ends.rs` | 29 | Tracks mutation signatures that repeatedly fail |
| `StagnationDetector` | `autoany-core/src/stagnation.rs` | 26 | Detects improvement stagnation |
| `InheritedKnowledge` | `autoany-core/src/inheritance.rs` | 13 | Cross-loop knowledge transfer |
| `EgriError` | `autoany-core/src/error.rs` | 4 | BudgetExhausted, ConstraintViolation, RollbackFailed, etc. |

**EGRI 9-tuple → Rust mapping:**

| Symbol | EGRI Role | Rust Type | File |
|--------|-----------|-----------|------|
| X | Artifact state space | Generic `A` | `loop_engine.rs:28` |
| M | Mutation operators | `Proposer` trait | `proposer.rs:9` |
| H | Immutable harness | `Execution` in `ProblemSpec` | `spec.rs:57` |
| E | Execution backend | `Executor` trait | `executor.rs:11` |
| J | Evaluator | `Evaluator` trait | `evaluator.rs:9` |
| C | Hard constraints | `ConstraintChecker` trait | `constraint.rs:7` |
| B | Budget policy | `BudgetController` | `budget.rs:7` |
| P | Promotion policy | `Selector` trait | `selector.rs:6` |
| L | Ledger | `Ledger` | `ledger.rs:12` |

**Five Laws enforcement in code:**

| Law | Enforcement Point | Mechanism |
|-----|-------------------|-----------|
| 1. Evaluator Supremacy | `Evaluator` trait design | Evaluator quality bounds loop safety by construction |
| 2. Mutation-Evaluation Proportionality | `ProblemSpec` configuration | Search space bounded by evaluator capacity |
| 3. Immutability of Evaluator | Loop architecture | Evaluator is `&self` (immutable borrow) during trials |
| 4. Budget Closure | `BudgetController::check()` | Returns `EgriError::BudgetExhausted`, never "one more try" |
| 5. Rollback Guarantee | `PromotionController::rollback()` | Best artifact always recoverable |

**Lyapunov D₂:** Budget remaining is a Lyapunov function:
```
D₂ = budget_remaining(t)    [monotonically decreasing → terminates]
```

**Debate protocol types (adversarial evaluation):**

| Type | File | Line | Purpose |
|------|------|------|---------|
| `DebateConfig` | `types.rs` | 181 | judge_count, convergence_threshold, label_randomization |
| `DebateRound` | `types.rs` | 299 | Full round: critique → revision → synthesis → votes |
| `Winner` | `types.rs` | 230 | Incumbent, Revision, Synthesis |
| `CritiqueResult` | `types.rs` | 277 | Issues with severity (Critical, Major, Minor) |
| `JudgeVote` | `types.rs` | 286 | Per-judge ranking with justification |

**Time scale:** Minutes to days (each trial is an Arcan session).

---

## Level 3: Governance (bstack Policy)

Policy constraints on what EGRI can mutate and how the workspace evolves.

| RCS | Name | Implementation | File (relative to workspace root) | Details |
|-----|------|---------------|-----------------------------------|---------|
| X₃ | Policy state | `policy.yaml` (YAML, version 2, agentic-control-kernel/v1 schema) | `core/life/.life/control/policy.yaml` | 3 profiles, 11 gates, 15 setpoints |
| Y₃ | Audit metrics | `make control-audit` output | `Makefile` | Setpoint tracking, gate pass rates |
| U₃ | Policy updates | Setpoint changes, new gates, profile switches | `policy.yaml` | Manual or self-evolution |
| f₃ | Self-evolution | Pattern → conversation log → architecture doc → policy gate → invariant | `CLAUDE.md` | 5-step crystallization protocol |
| h₃ | Compliance check | `make bstack-check` — 27 skills + hooks + bridge + policy | `Makefile` | Full metalayer validation |
| S₃ | Hard gates | G1-G4 blocking gates (force push, destructive reset, rm -rf, secrets) | `policy.yaml` | Lines 88–127 |
| Π₃ | Governance rules | `CLAUDE.md` invariants + `AGENTS.md` operational rules | Workspace root | Human-authored, agent-enforced |

**Governance profiles (policy.yaml lines 8–30):**

| Profile | Description | Gates |
|---------|-------------|-------|
| `baseline` | Smoke/check/test only | Minimal |
| `governed` | All gates + EGRI sandbox | Full gate sequence |
| `autonomous` | Auto-promote + reduced approval | Relaxed approval gates |

**Gate types (policy.yaml lines 88–127):**

| Category | Count | Examples |
|----------|-------|---------|
| Hard gates | 5 | no-merge-with-failing-checks, no-unsafe-without-justification |
| Soft gates | 2 | Budget awareness warnings |
| Budget gates | 2 | Token/cost limit enforcement |
| Approval gates | 2 | Human-in-the-loop for high-risk ops |

**Setpoints (policy.yaml lines 47–83):**
S1: gate_pass_rate, S2: audit_pass_rate, S3: constraint_violation_rate, S4: shield_intervention_rate, S5: pass_at_1, S6: merge_cycle_time, S7: revert_rate, S8: human_intervention_rate (+ more through S15).

**Shield configuration (policy.yaml lines 131–139):** 4-layer composite shield:
1. Policy gate
2. Capability gate
3. Budget gate
4. Sandbox boundary

**Lyapunov D₃:** Setpoint tracking:
```
D₃ = Σⱼ wⱼ·(metricⱼ − setpointⱼ)²
```

**Time scale:** Days to weeks (policy changes are rare, deliberate).

---

## Cross-Level Data Flow

```
Level 0: run_agent_loop()  [shell.rs:1873]
  │
  │  emits EventKind events to Lago journal
  ▼
Level 1: fold()  [projection.rs:23]
  │  consumes EventKind → produces HomeostaticState
  │
  ├─ evaluate()  [engine.rs:17]
  │  consumes HomeostaticState → produces AutonomicGatingProfile
  │
  └─ HysteresisGate  [hysteresis.rs:16]
     prevents mode flapping (deadband + dwell time)
  │
  │  publishes gating decisions back to Arcan
  ▼
Level 2: EgriLoop::run()  [loop_engine.rs:28]
  │  Proposer → Executor → Evaluator → Selector
  │  manages recursive improvement of L1 parameters
  │
  └─ Ledger  [ledger.rs:12]
     records all trials to persistent storage
  │
  │  policy-driven selection and approval
  ▼
Level 3: policy.yaml
  │  gate_sequence: smoke → check → test → audit
  │  setpoints define target operating ranges
  │  hard gates block unsafe operations
  │
  └─ CLAUDE.md invariants
     self-evolution: pattern → log → doc → gate → invariant
```

## Coupling Terms Between Levels

| Coupling | Stability Budget Term | Mechanism |
|----------|----------------------|-----------|
| L2 → L1 | `L_θ₁·ρ₁` (adaptation cost) | EGRI tunes autonomic rule thresholds |
| L2 → L1 | `L_d₁·η₁` (design cost) | EGRI mutates rule architecture |
| L3 → L2 | `L_θ₂·ρ₂` (adaptation cost) | Policy changes EGRI budget/promotion parameters |
| L3 → L2 | `L_d₂·η₂` (design cost) | Policy changes which mutations are permitted |
| L1 → L0 | `L_θ₀·ρ₀` (adaptation cost) | Autonomic changes gating profile → agent behavior changes |
| Self-observation | `β_self·τ̄_self` | Agent measuring its own state consumes tokens/context |

## Time-Scale Separation

| Level | Time Scale | Characteristic Period | Justification |
|-------|------------|----------------------|---------------|
| L0 | Seconds | 1–15s per tool call | Agent loop iteration |
| L1 | Per-turn | ~seconds per evaluation | fold + evaluate on every event |
| L2 | Minutes–days | 1 trial = 1 Arcan session | EGRI trials are expensive |
| L3 | Days–weeks | Policy review cadence | Human deliberation required |

Each level operates ≥10× slower than the level below, satisfying the singular perturbation condition for Theorem 1 (recursive stability).
