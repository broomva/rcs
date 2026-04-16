---
title: "Design Spec: Recursive Controlled Systems (RCS)"
tags:
  - rcs
  - design-spec
  - control-theory
  - life-agent-os
aliases:
  - RCS Design Spec
  - RCS Formalization
created: "2026-04-16"
updated: "2026-04-16"
status: approved
linear: BRO-702
related:
  - "[[RCS Index]]"
  - "[[autonomic-homeostasis]]"
  - "[[cooperative-resilience-mas]]"
  - "[[MAIA Index]]"
---

# Design Spec: Recursive Controlled Systems (RCS)

**Date:** 2026-04-16
**Status:** Approved
**Linear:** BRO-702 (parent: BRO-697)
**Author:** Carlos Escobar

## 1. Problem Statement

The Life Agent OS implements a rich implicit control architecture — `AgentStateVector`, `HomeostaticState`, `HysteresisGate`, 10+ autonomic rules, EGRI optimization loops, bstack governance — but no formal model unifies these as a single control-theoretic system. Meanwhile, the agent needs a self-model for metacognitive optimization, and the MAIA trabajo de grado needs a publishable mathematical contribution.

Three things are missing:

1. **A definition** that captures the agent-as-plant at every level of the hierarchy
2. **Stability guarantees** that the nested controllers don't destabilize each other
3. **Executable types** in Rust that make the formalism machine-checkable

## 2. Core Definition

### 2.1 Controlled System (Base Case)

A **Controlled System** is a 7-tuple:

```
Σ = (X, Y, U, f, h, S, Π)
```

where:

| Symbol | Name | Type | Meaning |
|--------|------|------|---------|
| `X` | State space | Set | The system's internal state |
| `Y` | Observation space | Set | What can be measured |
| `U` | Control input space | Set | What can be changed |
| `f: X × U → X` | Dynamics | Function | How the system evolves |
| `h: X → Y` | Observation map | Function | How state becomes measurement |
| `S: U × X → U` | Safety shield | Function | How unsafe actions are filtered to safe ones |
| `Π: Y* → U` | Controller | Function | How observation history becomes control action |

**Notation.** `Y*` denotes the set of finite observation sequences (the controller has memory). In practice, `Π` maintains internal state — this is where the recursion enters.

### 2.2 Recursive Controlled System

A **Recursive Controlled System (RCS)** is a Controlled System `Σ = (X, Y, U, f, h, S, Π)` where the controller `Π` is itself a Controlled System at the next level:

```
Π = Σ' = (X', Y', U', f', h', S', Π')
```

This produces a hierarchy of levels `L₀, L₁, L₂, ...` where:

- Level `Lᵢ` is a Controlled System whose controller is `Lᵢ₊₁`
- The state of `Lᵢ₊₁` includes the parameters and configuration of `Lᵢ`'s controller
- The observation of `Lᵢ₊₁` is derived from the performance metrics of `Lᵢ`
- The control output of `Lᵢ₊₁` modifies the behavior of `Lᵢ`

**Self-similarity.** The same 7-tuple structure applies at every level. This is the fixed-point property: `RCS ≅ (X, Y, U, f, h, S, RCS)`.

### 2.3 Homeostatic Drive as Lyapunov Function

At each level `Lᵢ`, define the **homeostatic drive**:

```
Dᵢ(x) = ||x - x*ᵢ||²
```

where `x*ᵢ` is the setpoint (desired equilibrium) at level `i`. This serves simultaneously as:

1. **Lyapunov function** — if `dDᵢ/dt < 0`, the system converges to the setpoint (stability)
2. **Reward signal** — reward = drive reduction `r = Dᵢ(xₜ) - Dᵢ(xₜ₊₁)` (Keramati & Gutkin 2014)
3. **Free energy bound** — `Dᵢ` upper-bounds surprise under the generative model (Active Inference)

This triple equivalence is not an analogy — it is a mathematical identity under the appropriate mappings. The homeostatic drive unifies control theory, reinforcement learning, and Bayesian inference at each level.

### 2.4 Recursive Stability Budget

Extending Eslami & Yu (2026, Theorem 2), the **stability budget** at level `Lᵢ` is:

```
λᵢ = γᵢ - L_θᵢ·ρᵢ - L_dᵢ·ηᵢ - βᵢ·τ̄ᵢ - (ln νᵢ)/τₐ,ᵢ > 0
```

where:

| Term | Meaning | Source |
|------|---------|--------|
| `γᵢ` | Nominal decay rate of `Dᵢ` | Plant dynamics at level `i` |
| `L_θᵢ·ρᵢ` | Adaptation cost | Level `i+1` tuning level `i` parameters |
| `L_dᵢ·ηᵢ` | Design evolution cost | Level `i+1` changing level `i` architecture |
| `βᵢ·τ̄ᵢ` | Delay cost | Inference/tool/communication latency |
| `(ln νᵢ)/τₐ,ᵢ` | Switching cost | Mode changes (e.g., OperatingMode transitions) |

**The recursive constraint:** For the composite system to be stable, `λᵢ > 0` must hold at **every** level simultaneously. The coupling terms capture how higher levels affect lower levels:

- Level 1 adaptation (`ρ₁`) consumes stability margin at Level 0
- Level 2 mutations (`η₂`) consume stability margin at Level 1
- Level 3 policy changes consume stability margin at Level 2

**Time-scale separation** makes this tractable. If Level `i+1` operates much slower than Level `i`, the singular perturbation argument applies: each level sees the levels above it as quasi-static, and the levels below it as fast inner loops that have already converged.

## 3. The Four-Level Hierarchy in Life Agent OS

### Level 0: External Plant

The agent controls an external system (microgrid, codebase, conversation).

| Component | RCS Symbol | Life Implementation |
|-----------|-----------|-------------------|
| State `X₀` | Physical/digital state | Microgrid: SoC, PV output, load, diesel level |
| Observation `Y₀` | Sensor readings | CT clamps, irradiance sensor, SoC monitor |
| Control `U₀` | Actuation commands | Battery charge/discharge setpoints, genset start/stop |
| Dynamics `f₀` | Plant physics | Microgrid power flow equations |
| Observation `h₀` | Sensor model | ADC readings → physical units |
| Shield `S₀` | Safety limits | SoC bounds [20%, 95%], overcurrent protection, CBF-QP |
| Controller `Π₀` | Agent | Arcan agent session (`run_agent_loop` in `shell.rs`) |

**Lyapunov `D₀`:** Task completion metric — e.g., minimize `||load_served - load_demanded||²` subject to battery health constraints.

**Time scale:** Seconds to minutes (dispatch decisions every 1-15 seconds).

### Level 1: Agent as Plant

The agent's own internal state is the system being regulated.

| Component | RCS Symbol | Life Implementation |
|-----------|-----------|-------------------|
| State `X₁` | Agent health | `HomeostaticState` — operational, cognitive, economic pillars |
| Observation `Y₁` | Event stream | `EventKind` variants (55+): tool calls, errors, tokens, costs |
| Control `U₁` | Behavioral constraints | `GatingProfile` + `OperatingMode` + `EconomicMode` |
| Dynamics `f₁` | State evolution | `fold()` in `projection.rs` — deterministic reducer |
| Observation `h₁` | Event processing | Event → state update mapping (Mealy machine) |
| Shield `S₁` | Anti-flapping | `HysteresisGate` (deadband + 30s dwell time) |
| Controller `Π₁` | Autonomic engine | `engine.rs::evaluate()` → `merge_decisions()` (most-restrictive-wins) |

**Lyapunov `D₁`:** Homeostatic drive across three pillars:
```
D₁ = α_op·||op - op*||² + α_cog·||cog - cog*||² + α_econ·||econ - econ*||²
```
where `op*`, `cog*`, `econ*` are the healthy setpoints (low error rate, moderate context pressure, sovereign economic mode).

**Time scale:** Per-turn (every agent iteration, ~seconds).

**Key insight — fold-as-observer:** The `fold()` function is a degenerate Luenberger observer with `A = I` (state persists between events) and full gain on measurements. It is a sufficient statistic for regulation decisions — the rule engine sees only `HomeostaticState`, never raw events. The `HysteresisGate` is precisely Eslami's Proposition 2: a state-dependent hysteresis mechanism that guarantees minimum dwell time `τ_h ≥ 2h̲/M̄`, satisfying the switching constraint in the stability budget.

### Level 2: Meta-Control (EGRI)

The EGRI loop optimizes the controller's parameters and architecture.

| Component | RCS Symbol | Life Implementation |
|-----------|-----------|-------------------|
| State `X₂` | Controller config | Weights, thresholds, model structure, policy code |
| Observation `Y₂` | Evaluation scores | `Outcome { score, constraints_passed }` |
| Control `U₂` | Mutations | `Mutation { operator, description, diff, hypothesis }` |
| Dynamics `f₂` | Trial execution | `EgriLoop::run()` — propose → execute → evaluate → select |
| Observation `h₂` | Evaluator scoring | `Evaluator::score(traces) → ScoreVector` |
| Shield `S₂` | Safety laws | Budget closure (Law 4) + rollback guarantee (Law 5) + immutable evaluator (Law 3) |
| Controller `Π₂` | EGRI proposer + selector | `Proposer::propose()` + `Selector::select()` |

**Lyapunov `D₂`:** Score improvement bounded by budget:
```
D₂ = budget_remaining(t)    [monotonically decreasing → terminates]
```

The budget is a Lyapunov function: `dD₂/dt < 0` strictly (each trial consumes budget), ensuring termination. This is a formal guarantee, not a heuristic.

**EGRI's Five Laws as stability conditions:**

| Law | Statement | Stability condition |
|-----|-----------|-------------------|
| 1. Evaluator Supremacy | Evaluator quality bounds loop safety | `λ₂` is only meaningful if `J` is trustworthy |
| 2. Mutation-Evaluation Proportionality | Don't mutate beyond evaluator capacity | Ashby's Requisite Variety: `|M| ≤ |J|` capacity |
| 3. Immutable Evaluator | Never mutate evaluator and artifact in same trial | Prevents feedback corruption (separation principle) |
| 4. Budget Closure | Loop terminates when budget exhausted | `D₂` is a valid Lyapunov function |
| 5. Rollback Guarantee | Every promoted state is recoverable | System can always return to known-good (invariant set) |

**Time scale:** Minutes to days (each trial is an Arcan session).

### Level 3: Governance (bstack)

Policy constraints on what EGRI can mutate and how the workspace evolves.

| Component | RCS Symbol | Life Implementation |
|-----------|-----------|-------------------|
| State `X₃` | Policy configuration | `.control/policy.yaml` — setpoints S1-S15, gates G1-G11 |
| Observation `Y₃` | Audit metrics | `make control-audit` output, setpoint tracking |
| Control `U₃` | Policy updates | Setpoint changes, new gates, profile switches |
| Dynamics `f₃` | Self-evolution protocol | Pattern → conversation log → architecture doc → policy gate → invariant |
| Observation `h₃` | Compliance checking | `make bstack-check` — 27 skills + hooks + bridge + policy |
| Shield `S₃` | Hard gates | G1-G4 blocking (force push, destructive reset, rm -rf, secrets) |
| Controller `Π₃` | Governance rules | `CLAUDE.md` invariants + `AGENTS.md` operational rules |

**Lyapunov `D₃`:** Setpoint tracking:
```
D₃ = Σⱼ wⱼ·(metric_j - setpoint_j)²
```
where `j` ranges over S1-S15 (gate pass rate, audit pass rate, constraint violation rate, etc.).

**Time scale:** Days to weeks (policy changes are rare, deliberate).

## 4. Algebraic Vocabulary

Five categorical primitives provide the compositional vocabulary for RCS:

### 4.1 Mealy Coalgebra — The Agent

An agent is a **Mealy coalgebra**: a state machine `S → (I → O × S)` that, given a current state `s` and input `i`, produces an output `o` and a next state `s'`.

**Life mapping:** The `fold()` function in `projection.rs` is precisely this:
```
fold: HomeostaticState × EventKind → HomeostaticState
```
The coalgebraic perspective provides: behavioral equivalence (two agents are equivalent iff they produce the same output sequences — bisimulation), and the final coalgebra classifies all possible agent behaviors.

### 4.2 Lens — The Observer-Controller Interface

A **lens** `(get: S → V, put: V × S → S)` formalizes bidirectional state access:
- `get` = observation (extract a view from the full state)
- `put` = control (update the state through the view)

**Life mapping:**
- `get`: `HomeostaticState → GatingProfile` (the rule engine extracts a control decision from the state)
- `put`: `GatingProfile × AgentState → AgentState` (the gating profile modifies the agent's behavior)

The lens laws (get-put, put-get) formalize the requirement that observation and control are consistent.

### 4.3 Trace — Feedback

**Trace** is the categorical operation that turns an open system into a closed-loop system by connecting an output back to an input. In string diagram notation, it's a wire that loops back.

**Life mapping:** The Arcan agent loop is a trace: tool results (outputs) feed back as context for the next LLM call (input). The Autonomic advisory loop is a trace: gating decisions (outputs) constrain the agent (inputs), whose behavior generates events that update the homeostatic state that drives future gating decisions.

### 4.4 Decorated Cospan — Composition of Open Systems

A **decorated cospan** (Fong 2015) formalizes how open systems compose by matching their interfaces. Two systems share a boundary (the cospan's apex), and composition is pushout.

**Life mapping:** Arcan sessions compose with Lago journals by sharing the `EventKind` boundary. Autonomic composes with Arcan by sharing the `GatingProfile` interface. The decorated cospan formalizes what "plugging subsystems together" means — and guarantees that the composition is well-defined.

### 4.5 Fixed Point of Endofunctor — Self-Similar Hierarchy

The RCS hierarchy is a **fixed point** of the endofunctor `F(Π) = (X, Y, U, f, h, S, Π)`:
```
RCS ≅ F(RCS)
```

The initial algebra gives a finite hierarchy (L0-L3 as implemented). The final coalgebra gives the infinite hierarchy (the limit of all possible levels). In practice, we use the initial algebra — four levels suffice.

**Life mapping:** The Life codebase has exactly four levels. The fixed-point property means the same Rust traits (`RecursiveControlledSystem<L>`) parameterized by level type work at every level. The type system enforces self-similarity.

## 5. Framework Unification

The RCS definition subsumes four major frameworks. Each is an instantiation of the same recursive structure:

### 5.1 Eslami & Yu (2026) → RCS

| Eslami | RCS |
|--------|-----|
| Augmented state `ξ = (x, θ, σ, c, ζ, m)` | Composite state across L0-L2: `x` at L0, `(θ, m)` at L1, `(σ, c, ζ)` at L2 |
| Control law `u = π_σ(I; θ, ζ)` | L0 controller parameterized by L1 state (θ) and L2 goal (ζ) |
| Agency levels L1-L5 | L1-L2 map to RCS L0-L1; L3-L5 map to RCS L2 (increasing mutation authority) |
| Stability budget (Eq. 51) | RCS recursive `λᵢ > 0` — same equation applied per level |
| Hysteresis (Prop. 2) | `HysteresisGate` at L1 — dwell time guarantees switching constraint |
| Memory `ṁ = Φ_m(m, y, z, r)` | L1 dynamics: `fold()` as memory evolution |

**What RCS adds:** Eslami analyzes a single agent. RCS shows the same stability budget applies recursively across levels, with coupling terms between levels. The EGRI meta-controller (L2) and governance (L3) are outside Eslami's scope.

### 5.2 Ashby (1952) → RCS

| Ashby | RCS |
|-------|-----|
| Essential variables | L1 observation `Y₁` (the variables that must stay in bounds) |
| Homeostat (inner loop) | L1 controller `Π₁` (Autonomic rule engine) |
| Ultrastability (outer loop) | L2 controller `Π₂` (EGRI — random search in parameter space until stable) |
| Requisite Variety | At each level: `|Π_i|` variety ≥ disturbance variety |
| Good Regulator Theorem | At each level: `Π_i` must contain a model of `X_i` (the observer) |

**What RCS adds:** Ashby's formalism is qualitative. RCS provides quantitative stability conditions (the budget) and typed interfaces (the 7-tuple).

### 5.3 Beer (1972) → RCS

| Beer VSM | RCS |
|----------|-----|
| S1 Operations | L0 plant (primary activities) |
| S2 Coordination | L1 shield `S₁` (anti-flapping, conflict resolution) |
| S3 Optimization | L1 controller `Π₁` (Autonomic — resource allocation) |
| S4 Intelligence | L1 observer `h₁` (fold — environmental monitoring) |
| S5 Policy | L3 controller `Π₃` (governance — identity, purpose) |
| Recursive viability | RCS self-similarity: each S1 is itself a viable system |

**What RCS adds:** Beer's model is organizational, not mathematical. RCS provides the state-space formalism that makes VSM amenable to stability analysis.

### 5.4 Active Inference → RCS

| Active Inference | RCS |
|-----------------|-----|
| Free energy `F` | Lyapunov function `D` at each level |
| Perception `argmin_μ F` | Observer `h` (minimize prediction error → estimate state) |
| Action `argmin_a F` | Controller `Π` (minimize expected free energy → select action) |
| Prior preferences `p(o)` | Setpoints `x*` (desired observations) |
| PID gains = precision parameters | L1 rule thresholds as precision weights (Baltieri & Buckley 2019) |
| Expected free energy (planning) | L0 MPC cost function (receding-horizon optimization) |
| Allostasis (predictive regulation) | MPC: predict future states, pre-adjust controls |

**What RCS adds:** Active inference is a single-level framework (perception-action at one scale). RCS shows the same structure recurses across levels, and provides the switched-system stability analysis that active inference lacks.

## 6. Observer Theory

### 6.1 The Fold as Observer

The `fold()` function in `projection.rs` computes `HomeostaticState` from an event stream:

```
state_{k+1} = fold(state_k, event_k)
```

This is a **Mealy machine** (deterministic, no prediction between events). It is equivalent to a Luenberger observer with:
- `A = I` (state persists unchanged between events)
- `L = I` on observable components (full trust in measurements)
- No process model (no prediction of what will happen next)

**Sufficiency theorem:** `HomeostaticState` is a sufficient statistic for regulation decisions. Proof: all Autonomic rules take `&HomeostaticState` as sole input; no rule accesses raw events. Therefore, by construction, the fold output contains all information needed for regulation.

### 6.2 Context Window as Finite-Horizon Observer

The agent's context window is a finite observation buffer of `N` tokens. This maps to **Moving Horizon Estimation (MHE)**:

| MHE | Agent |
|-----|-------|
| Sliding window `[t-T, t]` | Context window (finite token budget) |
| Arrival cost | Compacted summaries (`ReflectionCompacted` events) |
| Measurement sequence | Event stream within the window |
| Optimization over window | The fold (deterministic, not optimized) |

**Information-theoretic bound:** Compaction is lossy compression. By rate-distortion theory, the summary has minimum achievable distortion given its size. Better compaction strategies (higher mutual information between summary and history) directly improve state estimation quality.

### 6.3 Self-Observation Cost

The agent measuring its own state consumes resources (tokens for evaluation, context space for introspection). This creates a **reflexive observation cost** that enters the stability budget:

```
β_self·τ̄_self
```

where `τ̄_self` is the delay introduced by self-measurement. The `HysteresisGate` prevents this self-referential loop from causing oscillation — the deadband creates a zone where small perturbations from self-observation don't trigger state transitions.

### 6.4 Multi-Rate Observation

Different state variables are observable at different rates:

| Variable | Rate | Source |
|----------|------|--------|
| Token count | Every turn | `TokenUsage` events |
| Error streak | Every tool call | `ToolCallCompleted/Failed` |
| Context pressure | Every turn | Computed ratio |
| Economic state | Per API call | `CostCharged` events |
| Knowledge health | Minutes-hours | `KnowledgeEvaluated` events |
| Quality score | Sporadic | `eval.InlineCompleted` events |

Staleness timestamps (`knowledge_last_indexed_ms`, `last_eval_ms`) enable discount of stale observations. A Kalman-style uncertainty growth model would formalize: confidence in slow-rate variables decays between measurements proportional to their process noise.

## 7. Multi-Agent Extension (Paper 4 Preview)

### 7.1 Fleet as Composed RCS

A fleet of `N` agents is a composition of RCS instances sharing a communication boundary:

```
Σ_fleet = Σ₁ ⊗_G Σ₂ ⊗_G ... ⊗_G Σ_N
```

where `⊗_G` denotes composition over communication graph `G` (the MQTT topology). Each agent is a full RCS (L0-L3); the fleet adds a coordination layer.

### 7.2 Population Dynamics for Coordination

Following Quijano's framework, fleet coordination uses **evolutionary game dynamics** where each agent selects from a strategy set (e.g., charge, discharge, curtail, idle). The population distribution evolves via replicator dynamics:

```
ẋᵢ = xᵢ(fᵢ(x) - x·f(x))
```

where `xᵢ` is the proportion of agents playing strategy `i` and `fᵢ` is the fitness (payoff) of strategy `i`. Convergence to Nash equilibrium is guaranteed under passivity conditions on the plant-controller interconnection.

### 7.3 Cooperative Resilience as Performance Metric

Following Chacon-Chamorro et al. (2025), fleet performance under disruption is measured by the **cooperative resilience score**:

```
J_jl = (t_i + F_jl·Δt_f + G_jl·Δt_r) / (t_i + Δt_f + Δt_r)
```

This is structurally a disturbance-rejection quality measure — analogous to H∞ bounds in robust control. The harmonic mean across variables penalizes worst-case degradation.

## 8. Paper Series

| # | Title | Contribution | Venue | Milestone |
|---|-------|-------------|-------|-----------|
| P0 | RCS Foundations | Definition, algebraic vocabulary, codebase mapping, framework unification | Workshop (CDC/NeurIPS) | S1 Dec 2026 |
| P1 | Homeostatic Stability | Composite Lyapunov, time-scale separation, drive=Lyapunov=reward=free-energy | CDC or L4DC | S2 May 2027 |
| P2 | EGRI as Meta-Controller | Budget-as-Lyapunov, Five Laws as stability conditions, Requisite Variety bridge | ICML or AAMAS | S2 May 2027 |
| P3 | Self-Referential Observers | Fold sufficiency, compaction bounds, self-observation cost, MHE connection | AAAI or JAIR | S3 Sep 2027 |
| P4 | Fleet Cooperative Resilience | Multi-agent RCS, population dynamics, cooperative resilience, ZNI microgrids | IEEE TAI | S4 Mar 2028 |

## 9. Code Artifact Specifications

### 9.1 `RecursiveControlledSystem<L>` trait (aios-protocol)

```rust
/// Marker trait for RCS hierarchy levels
pub trait Level: Send + Sync + 'static {}

pub struct L0; // External plant
pub struct L1; // Agent internal
pub struct L2; // Meta-control (EGRI)
pub struct L3; // Governance

impl Level for L0 {}
impl Level for L1 {}
impl Level for L2 {}
impl Level for L3 {}

/// The RCS 7-tuple as a Rust trait
pub trait RecursiveControlledSystem<L: Level> {
    type State;
    type Observation;
    type Control;

    /// h: X → Y — observe the current state
    fn observe(&self) -> Self::Observation;

    /// f: X × U → X — compute next state given control input
    fn step(&mut self, u: &Self::Control);

    /// S: U × X → U — filter unsafe control to safe control
    fn shield(&self, proposed: Self::Control) -> Self::Control;
}
```

### 9.2 `LyapunovCandidate` trait (autonomic-core)

```rust
/// A candidate Lyapunov function for stability analysis
pub trait LyapunovCandidate<L: Level> {
    type State;

    /// V(x) — evaluate the Lyapunov function at state x
    fn evaluate(&self, state: &Self::State) -> f64;

    /// dV/dt estimate — negative means converging
    fn decrease_rate(&self, state: &Self::State) -> f64;

    /// ν — jump bound at switching instants (V_new ≤ ν·V_old)
    fn jump_bound(&self) -> f64;
}
```

### 9.3 `StabilityBudget` struct (autonomic-controller)

```rust
/// The recursive stability budget: λ = γ - Σ costs > 0
pub struct StabilityBudget {
    /// γ — nominal decay rate of the Lyapunov function
    pub decay_rate: f64,
    /// L_θ·ρ — adaptation cost from higher level
    pub adaptation_cost: f64,
    /// L_d·η — design evolution cost
    pub design_cost: f64,
    /// β·τ̄ — delay cost from inference/tool latency
    pub delay_cost: f64,
    /// (ln ν)/τ_a — switching cost from mode changes
    pub switching_cost: f64,
}

impl StabilityBudget {
    /// λ = γ - Σ costs
    pub fn margin(&self) -> f64 {
        self.decay_rate
            - self.adaptation_cost
            - self.design_cost
            - self.delay_cost
            - self.switching_cost
    }

    /// Is the system stable at this level?
    pub fn is_stable(&self) -> bool {
        self.margin() > 0.0
    }
}
```

## 10. Key References

### Control Theory
- Eslami & Yu (2026). "A Control-Theoretic Foundation for Agentic Systems." arXiv:2603.10779
- Liberzon (2003). *Switching in Systems and Control*. Springer.
- Hespanha & Morse (1999). "Stability of switched systems with average dwell-time." CDC.
- Goebel, Sanfelice & Teel (2009). "Hybrid Dynamical Systems." IEEE CSM.
- Khalil & Grizzle (2002). *Nonlinear Systems*. Prentice Hall.

### Bio-Inspired Control
- Keramati & Gutkin (2014). "Homeostatic reinforcement learning for integrating reward collection and physiological stability." eLife.
- Baltieri & Buckley (2019). "PID Control as a Process of Active Inference with Linear Generative Models." Entropy.
- Mineault et al. (2024). "NeuroAI for AI Safety." arXiv:2411.18526.
- Yoshida et al. (2024). "Emergence of integrated behaviors through direct optimization for homeostasis." Neural Networks.
- Sterling (2012). "Allostasis: A model of predictive regulation." Physiology & Behavior.

### Cybernetics
- Ashby (1952). *Design for a Brain*. Chapman & Hall.
- Conant & Ashby (1970). "Every good regulator of a system must be a model of that system." Int. J. Systems Science.
- Beer (1972). *Brain of the Firm*. Allen Lane.

### Category Theory for Control
- Baez & Erbele (2015). "Categories in Control." Theory and Applications of Categories.
- Fong (2015). "Decorated Cospans." Theory and Applications of Categories.
- Spivak & Niu (2021). "Polynomial Functors: A Mathematical Theory of Interaction."

### Multi-Agent Systems
- Quijano et al. (2017). "The Role of Population Games and Evolutionary Dynamics in Distributed Control Systems." IEEE CSM.
- Chacon-Chamorro et al. (2025). "Cooperative Resilience in AI Multiagent Systems." IEEE Trans. AI.
- Chacon-Chamorro, Giraldo & Quijano (2026). "Learning Reward Functions for Cooperative Resilience." arXiv:2601.22292.
- Giraldo & Passino (2016). "Dynamic Task Performance, Cohesion, and Communications in Human Groups." IEEE Trans. Cybernetics.

### EGRI
- Autoany REFERENCE.md — Formal 9-tuple model: Π = (X, M, H, E, J, C, B, P, L).
- Autoany META-LOOP.md — Nested loops, strategy distillation.
