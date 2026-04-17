---
title: "Framework Unification Table: Eslami / Ashby / Beer / Active Inference → RCS"
tags:
  - rcs
  - control-theory
  - framework-comparison
  - unification
aliases:
  - RCS Framework Unification
  - Framework Comparison Table
created: "2026-04-16"
updated: "2026-04-16"
status: draft
linear: BRO-705
related:
  - "[[RCS Index]]"
  - "[[2026-04-16-rcs-formalization-design]]"
  - "[[life-rcs-mapping]]"
---

# Framework Unification Table

**Linear:** BRO-705 (parent: BRO-697)
**Purpose:** Show that four major frameworks each instantiate the RCS 7-tuple `Σ = (X, Y, U, f, h, S, Π)` as special cases, and identify what RCS adds beyond each.

---

## 1. Master Comparison Table

| RCS Component | Eslami & Yu (2026) | Ashby (1952) | Beer (1972) VSM | Active Inference |
|---------------|-------------------|--------------|-----------------|------------------|
| **X** — State | Augmented state `ξ = (x, θ, σ, c, ζ, m)` distributed across L0–L2 | Essential variables (must stay in bounds) | S1 Operations state | Generative model hidden states `μ` |
| **Y** — Observation | Sensor outputs `y`, reward `r`, tool outputs `z` | Step function outputs (random triggers) | S4 Intelligence (environmental monitoring) | Sensory observations `o` |
| **U** — Control | Control law `u = π_σ(I; θ, ζ)` parameterized by mode, params, goal | Homeostat dial settings (continuous parameters) | S3 Optimization directives | Actions `a = argmin_a G(π, a)` minimizing expected free energy |
| **f** — Dynamics | `ẋ = f(x, u, w)` augmented with `θ̇, σ̇, ṁ` | Step function (state jump when essential variables leave bounds) | S1 primary activities (operational dynamics) | Generative process: `x_{t+1} = f(x_t, a_t) + w` |
| **h** — Observer | Observation `y = h(x)` + memory `ṁ = Φ_m(m, y, z, r)` | Identity (direct observation of essential variables) | S4 Intelligence + S2 Coordination (info aggregation) | Perception: `μ* = argmin_μ F(o, μ)` (minimize prediction error) |
| **S** — Shield | CBF-QP: `S(u) = argmin ‖u − ũ‖²` s.t. barrier constraints | Implicit: essential variables define viable region (homeostatic bounds) | S5 Policy (identity constraints, purpose) | Prior preferences `p(o)` constrain action space |
| **Π** — Controller | 5-level hierarchy (L1 reflex → L5 design) | Two-loop: homeostat (inner) + ultrastability (outer) | S3 + S5 recursive viable system | Active inference agent: perception + action loop |
| **D** — Lyapunov | Theorem 2 stability budget `λ > 0` | Stability = essential variables in bounds (qualitative) | Viability = recursive autonomy (organizational) | Free energy `F = D_{KL}[q(x) ‖ p(x|o)] − ln p(o)` |
| **Recursion** | Single agent, 5 levels within one entity | Two loops (inner/outer), not explicitly recursive | Explicit: each S1 is itself a viable system | Single level (perception-action at one scale) |

---

## 2. Detailed Framework Analyses

### 2.1 Eslami & Yu (2026) → RCS

**Source:** "A Control-Theoretic Foundation for Agentic Systems," arXiv:2603.10779

**State decomposition:**

| Eslami Variable | RCS Level | RCS Component | Life Implementation |
|-----------------|-----------|---------------|---------------------|
| `x` — plant state | L0 | X₀ | External system (microgrid, codebase) |
| `θ` — controller parameters | L1 | X₁ (part) | Autonomic rule thresholds |
| `σ` — operating mode | L1 | U₁ (part) | `OperatingMode` enum |
| `c` — context/goal | L0–L1 | X₁ (part) | Task context, `AgentStateVector.progress` |
| `ζ` — meta-parameters | L2 | X₂ | EGRI artifact state |
| `m` — memory | L1 | X₁ | `HomeostaticState` (fold output) |

**Agency hierarchy mapping:**

| Eslami Level | Name | RCS Mapping | Key Mechanism |
|-------------|------|-------------|---------------|
| L1 | Reflex | L0 controller (direct response) | Tool call → immediate output |
| L2 | Modulated reflex | L0 + L1 shield | Autonomic gating constrains reflexes |
| L3 | Model-based planning | L0 with internal model | LLM as implicit world model |
| L4 | Parameter adaptation | L1 → L2 boundary | EGRI tunes autonomic parameters |
| L5 | Architecture design | L2 | EGRI mutates controller structure |

**Stability budget isomorphism:**

| Eslami (Theorem 2, Eq. 51) | RCS (Definition 6, Eq. 8) |
|---------------------------|--------------------------|
| `γ` (nominal decay) | `γᵢ` at each level |
| `L_θ·ρ` (adaptation penalty) | `L_θᵢ·ρᵢ` (L{i+1} tuning Lᵢ) |
| `L_d·η` (design penalty) | `L_dᵢ·ηᵢ` (L{i+1} redesigning Lᵢ) |
| `β·τ̄` (delay penalty) | `βᵢ·τ̄ᵢ` (inference/tool/communication) |
| `(ln ν)/τ_a` (switching penalty) | `(ln νᵢ)/τ_{a,i}` (mode transitions) |

**Hysteresis (Eslami Proposition 2):**

| Eslami | RCS | Life Rust |
|--------|-----|-----------|
| State-dependent hysteresis with deadband `h̲` and bound `M̄` | Shield S₁ at Level 1 | `HysteresisGate` { enter_threshold, exit_threshold, min_hold_ms } |
| Dwell time `τ_h ≥ 2h̲/M̄` | Switching constraint in budget | `min_hold_ms` parameter |

**What RCS adds beyond Eslami:**
1. **Recursion.** Eslami analyzes a single agent with 5 internal levels. RCS shows the *same* stability budget applies at every level of a recursive hierarchy, including meta-control (EGRI) and governance (bstack) — levels Eslami doesn't model.
2. **Algebraic vocabulary.** Eslami uses differential equations. RCS adds categorical primitives (Mealy coalgebra, lens, trace, decorated cospan, fixed point) that formalize composition and self-similarity.
3. **Executable types.** Eslami is purely mathematical. RCS maps every component to Rust types, making the formalism machine-checkable.

---

### 2.2 Ashby (1952) → RCS

**Source:** *Design for a Brain*, Chapman & Hall.

| Ashby Concept | RCS Equivalent | Formalization Gain |
|---------------|---------------|-------------------|
| Essential variables | Y₁ (observation at L1) — the variables that must stay in bounds for the organism to survive | Typed as `HomeostaticState` with explicit bounds |
| Homeostat (inner loop) | Π₁ (L1 controller) — the autonomic rule engine that adjusts behavior to keep essential variables in range | 7 rule modules with formal merge policy |
| Ultrastability (outer loop) | Π₂ (L2 controller) — EGRI performs random search in parameter space until a stable configuration is found | Budget-bounded with Lyapunov guarantee |
| Step function | S₁ (L1 shield) — HysteresisGate triggers mode change when essential variables leave bounds | Explicit deadband + dwell time |
| Requisite Variety | At each level: `|Πᵢ| ≥ |disturbance variety|` — controller variety must match disturbance variety | Formalizable as `Score::Vector` dimensionality vs mutation operator count |
| Good Regulator Theorem | At each level: Πᵢ contains a model of Xᵢ (the observer) | fold() as sufficient statistic; Proposition 3 (sufficiency) |

**Ashby's two-loop architecture mapped to RCS:**

```
Ashby                          RCS
┌─────────────────┐           ┌─────────────────┐
│ Inner loop:     │           │ Level 1:        │
│ Homeostat       │──────────▶│ Autonomic Π₁    │
│ (fast, reflex)  │           │ (evaluate + fold)│
└────────┬────────┘           └────────┬────────┘
         │ failure                     │ D₁ not decreasing
         ▼                             ▼
┌─────────────────┐           ┌─────────────────┐
│ Outer loop:     │           │ Level 2:        │
│ Ultrastability  │──────────▶│ EGRI Π₂         │
│ (slow, random)  │           │ (propose+select) │
└─────────────────┘           └─────────────────┘
```

**What RCS adds beyond Ashby:**
1. **Quantitative stability conditions.** Ashby's formalism is purely qualitative ("essential variables stay in bounds"). RCS provides the stability budget `λᵢ > 0` with explicit coupling terms.
2. **Typed interfaces.** Ashby's 7-tuple equivalent is implicit. RCS makes state/observation/control spaces explicit and typed.
3. **More than two loops.** Ashby has inner (homeostat) and outer (ultrastability). RCS supports arbitrary nesting depth — L0 through L3 in practice, with coupling analysis at each boundary.
4. **Composition.** Ashby considers single organisms. RCS provides fleet composition via decorated cospans (Section 7 of the design spec).

---

### 2.3 Beer (1972) → RCS

**Source:** *Brain of the Firm*, Allen Lane. Viable System Model (VSM).

| Beer VSM System | RCS Equivalent | Mapping Detail |
|-----------------|---------------|----------------|
| **S1** Operations | L0 plant | Primary activities (the work being done) |
| **S2** Coordination | S₁ shield at L1 | Anti-flapping, conflict resolution between S1 units → `HysteresisGate` |
| **S3** Optimization | Π₁ controller at L1 | Internal regulation, resource allocation → `evaluate()` + `merge_decisions()` |
| **S3*** Audit | h₁ observer at L1 | Sporadic investigation → `fold()` with evaluation events |
| **S4** Intelligence | h₁ + h₃ observers | Environmental monitoring → event stream + audit metrics |
| **S5** Policy | Π₃ controller at L3 | Identity, purpose, existential rules → `CLAUDE.md` invariants |

**Recursive viability → RCS self-similarity:**

Beer's key insight: each S1 operation is itself a viable system with its own S1–S5. This maps directly to the RCS fixed-point property:

```
Beer: VSM ≅ {S1: VSM, S2, S3, S4, S5}
RCS:  RCS ≅ F(RCS) = (X, Y, U, f, h, S, RCS)
```

Both are recursive structures. The difference is formalization: Beer describes organizational functions, RCS defines mathematical objects with stability guarantees.

**VSM channel mapping:**

| Beer Channel | RCS Data Flow | Life Implementation |
|-------------|---------------|---------------------|
| S3–S1 command | U₁ → L0 | `AutonomicGatingProfile` constraining agent behavior |
| S1–S3 reporting | Y₁ from L0 | `EventKind` stream from agent loop to autonomic |
| S4–S3 intelligence | Y₃ → Π₂ | Audit metrics informing EGRI mutation strategy |
| S5–S3 policy | U₃ → L2 | `policy.yaml` setpoints constraining EGRI |
| S2–S1 coordination | S₁ at L1 | `HysteresisGate` preventing mode flapping between S1 units |
| Algedonic signal | Emergency escalation | `EgriError::EscalationRequired`, `OperatingMode::AskHuman` |

**What RCS adds beyond Beer:**
1. **Mathematical formalism.** Beer's model is organizational, not mathematical. RCS provides state-space formalism amenable to stability analysis (`λᵢ > 0`).
2. **Typed implementation.** VSM is a conceptual model. RCS maps to Rust types, making viability machine-checkable.
3. **Stability coupling analysis.** Beer doesn't quantify how S3 optimization perturbs S1 operations. RCS captures this via `L_θ₁·ρ₁` (adaptation cost from L2 tuning L1).
4. **Shield formalization.** Beer's S2 coordination is loosely defined. RCS formalizes it as the safety shield `S` with CBF-QP semantics.

---

### 2.4 Active Inference → RCS

**Sources:** Friston (2009), Baltieri & Buckley (2019), Mineault et al. (2024)

| Active Inference | RCS Equivalent | Mapping Detail |
|-----------------|---------------|----------------|
| Free energy `F` | Lyapunov function `D` at each level | Both are scalar functions that decrease → stability |
| Perception `μ* = argmin_μ F` | Observer `h` | Minimize prediction error → estimate state |
| Action `a* = argmin_a G(π, a)` | Controller `Π` | Minimize expected free energy → select action |
| Prior preferences `p(o)` | Setpoints `x*` | Desired observations = desired equilibrium |
| Generative model `p(o, x)` | System model in `Π` | Internal model of plant dynamics |
| Prediction error | Homeostatic drive deviation | `D(x) = ‖x − x*‖² > 0` means prediction violated |

**PID-as-Active-Inference (Baltieri & Buckley 2019):**

| PID Component | Active Inference | RCS Level 1 |
|--------------|-----------------|--------------|
| Proportional gain `Kp` | Precision on sensory prediction error | Rule threshold magnitude |
| Integral gain `Ki` | Precision on accumulated error | Economic burn-rate tracking |
| Derivative gain `Kd` | Precision on rate of change | Error streak rate detection |
| Setpoint `r` | Prior preference `p(o)` | `x*` in homeostatic drive |

**Triple equivalence (Proposition 1 in LaTeX):**

```
                    Lyapunov function
                   ╱
D(x) = ‖x − x*‖²  ── Reward signal (r = D(xₜ) − D(xₜ₊₁))
                   ╲
                    Free energy bound
```

This is a mathematical identity, not an analogy:
- **Lyapunov:** `dD/dt < 0 ⟹ stability` (control theory)
- **Reward:** `r = ΔD > 0 ⟹ reinforcement` (RL, Keramati & Gutkin 2014)
- **Free energy:** `D ≥ F ⟹ surprise bound` (active inference, Friston 2009)

**Allostasis (predictive regulation):**

| Active Inference | RCS | Life Implementation |
|-----------------|-----|---------------------|
| Allostasis: predict future needs, pre-adjust | MPC at L0: receding-horizon optimization | LLM as implicit planner (multi-step reasoning) |
| Interoceptive inference | L1 self-observation | `fold()` processing internal events |
| Expected free energy `G` | Anticipated drive reduction | Agent planning to reduce future `D₁` |

**What RCS adds beyond Active Inference:**
1. **Recursion across levels.** Active inference is fundamentally a single-level framework (perception-action at one scale). RCS shows the same free-energy-minimization structure recurses across L0–L3, with explicit coupling analysis between levels.
2. **Switched-system stability.** Active inference lacks analysis for mode-switching agents. RCS inherits Eslami's stability budget with switching cost `(ln ν)/τ_a`, covering `OperatingMode` and `EconomicMode` transitions.
3. **Safety shields.** Active inference has no explicit safety mechanism. RCS formalizes the shield `S` as a CBF-QP that projects unsafe actions to the safe set, with `HysteresisGate` preventing oscillation.
4. **Meta-control.** Active inference doesn't address who tunes the precision parameters. RCS Level 2 (EGRI) fills this role, with budget-bounded optimization of Level 1 parameters.
5. **Governance.** Active inference has no governance layer. RCS Level 3 (bstack) constrains what the meta-controller can mutate.

---

### 2.5 Context Engineering Lineage → RCS

**Sources:** Reflexion (Shinn et al. 2023), Self-Refine (Madaan et al. 2023), Voyager (Wang et al. 2023), Generative Agents (Park et al. 2023), Dynamic Cheatsheet, Agentic Context Engineering (Zhang et al. 2025, ICLR 2026).

A distinct research lineage has emerged around *adapting LLM agents through structured, evolving context rather than weight updates*. These systems instantiate RCS at Level 1, with the agent's context as the state space `X₁` and the controller `Π₁` realized as a pipeline that distills execution traces into context deltas. ACE is the most recent and most structured of these; it makes explicit what earlier systems did implicitly.

#### 2.5.1 ACE (Zhang et al. 2025) as RCS at L1

ACE's three-role architecture maps to the RCS 7-tuple at Level 1:

| RCS Component | ACE Component | Notes |
|---------------|---------------|-------|
| `X₁` — state | Playbook: set of scored bullets `[id] helpful=X harmful=Y :: content`, grouped by section | Plain text file in the reference implementation; typed in principle |
| `Y₁` — observation | Reasoning trace, bullet IDs used, environment feedback | Input to the Reflector |
| `U₁` — control | `ADD` operations + counter increments (`helpful/harmful += 1`) | Only `ADD` is operational; `UPDATE`/`MERGE`/`DELETE`/`CREATE_META` are stubbed in the reference code |
| `f₁` — dynamics | `apply_curator_operations(playbook, ops)` — deterministic text splice | Append-only **by omission**, not by invariant |
| `h₁` — observer | Reflector LLM call extracting bullet tags | Runs on both correct **and** incorrect traces — key design choice |
| `S₁` — shield | Token budget passed as Curator prompt text | Advisory only; not enforced in code |
| `Π₁` — controller | Generator + Reflector + Curator pipeline | Three roles; default config runs all three with the same model (DeepSeek-V3.1) |
| `D₁` — Lyapunov | Implicit in helpful − harmful counters | No formal drive function defined |

**Implementation finding (from code inspection, `playbook_utils.py`, `ace/core/curator.py`, `ace/core/bulletpoint_analyzer.py`):** the paper's claim of *deterministic curation with de-duplication and pruning* is partially aspirational. Only `ADD` is implemented in the curator merge function. Semantic de-duplication (`BulletpointAnalyzer`) is behind an optional flag (`use_bulletpoint_analyzer`, default `False`) requiring `sentence-transformers` + `faiss-cpu`, and when enabled it performs merges via an LLM call (temperature 0.3) rather than deterministic logic. The token budget is supplied as prompt text (`"Total token budget: {token_budget}"`) but not enforced anywhere in the update path. The invariant that prevents context collapse in ACE is therefore **structural by omission** — the runtime simply lacks the operations that would violate append-only monotonicity.

#### 2.5.2 Lineage mapping

| System | Year | RCS Contribution | RCS Gap |
|--------|------|------------------|---------|
| Reflexion (Shinn et al.) | 2023 | Reflector-as-observer; verbal self-critique closes feedback loop | No structured playbook; reflection is ephemeral |
| Self-Refine (Madaan et al.) | 2023 | Iterative refinement realizes observer → controller → plant trace | Single-task refinement; no cross-sample retained state |
| Voyager (Wang et al.) | 2023 | Skill library as retained `X₁` with execution-feedback admission | Binary admission (works/doesn't); no helpful/harmful counters |
| Generative Agents (Park et al.) | 2023 | Memory stream + importance scoring + scheduled reflection | Reflection rewrites are monolithic — vulnerable to collapse |
| Dynamic Cheatsheet | 2024/25 | Scored playbook entries with monolithic rewrite | The collapse event in ACE Fig. 2 is observed in this class of system |
| ACE (Zhang et al.) | 2025 | Append-only delta operations; Reflector always runs; separate Curator role | No formal stability guarantee; budget is advisory |

#### 2.5.3 What RCS contributes to this lineage

None of these systems has a formal state-space model, typed controller interface, or stability condition. RCS provides:

1. **Formal characterization of the collapse-avoidance mechanism.** ACE's empirical finding that monolithic rewrites degrade performance below the no-context baseline (Zhang et al. 2025, Fig. 2) is an instance of violating Assumption 4 (design evolution sensitivity) in the stability budget: a single step with `η₁ ≫ (γ₁ − other costs) / L_d₁` is outside the stability region. Append-only updates preserve `λ₁ > 0` by keeping `η₁` bounded at the per-sample admission rate.
2. **Quantitative bound on admissible rewrite magnitude.** The maximum per-step context mutation admitted by the stability budget is `η₁ < (γ₁ − L_θ·ρ − β·τ̄ − ln(ν)/τ_a) / L_d₁`. ACE's append-only design automatically satisfies this; systems with `UPDATE`/`MERGE`/`DELETE` would need explicit admission control.
3. **Recursive extension.** Context engineering as described in this lineage is a single-level phenomenon (L1). RCS makes the L2 meta-controller explicit — one that tunes the Reflector's admission policy, the Curator's prompt, or the helpful/harmful threshold for bullet eviction. None of the cited systems addresses this.
4. **Observer-as-sufficient-statistic.** The helpful/harmful counters are a degenerate Luenberger observer on entry utility: `h(entry) = helpful/(helpful + harmful + 1)` with running-average gain `L = 1/(n+1)`. This extends the fold-as-observer sufficiency theorem (Proposition 3 of the design spec) from unstructured `HomeostaticState` to structured enumerable state.
5. **Safety shield for context updates.** RCS defines `S₁` as a CBF-QP that projects unsafe controls to the safe set. Applied to context engineering, this becomes an enforced (not advisory) cap on per-step entry churn and a minimum dwell time on admitted entries before eviction.

#### 2.5.4 What this lineage contributes to RCS

The contribution is **empirical validation**, not formalism:

1. Large-scale evidence that incremental context updates preserve knowledge better than monolithic rewrites, across agent tasks (AppWorld) and domain-specific tasks (finance).
2. Measured latency and cost reductions (ACE: 82.3% latency, 75.1% rollouts vs GEPA) that quantify the cost of violating the stability budget through aggressive rewrites.
3. An open-source reference implementation that instantiates L1 of an RCS hierarchy — usable as a worked example and reproducibility baseline.
4. The observation that the Reflector should run on **both** successful and unsuccessful traces, providing a continuous stream of bullet-level feedback rather than only failure-triggered updates. This is a design choice RCS adopts for its L1 observer.

#### 2.5.5 Design choices this lineage motivates avoiding

Inspection of the ACE reference implementation reveals choices that RCS-grounded designs should **not** import:

- Plain-text regex-parsed playbook (use typed state with event-sourcing).
- LLM-as-curator as the default merge operator (start with deterministic append; introduce an LLM curator only behind an enforced shield).
- Advisory token budgets stated in prompts (enforce budgets at the context-compiler level).
- Single-model-three-prompts default (retain the option of genuinely separate Reflector/Evaluator to preserve Evaluator Supremacy — EGRI Law 1, Section 7 of the design spec).

---

## 3. Unified Vocabulary Table

A single RCS concept expressed in each framework's language:

| RCS Concept | Eslami | Ashby | Beer | Active Inference |
|-------------|--------|-------|------|------------------|
| Setpoint `x*` | Desired state/goal `ζ` | Essential variable bounds | Policy (S5 purpose) | Prior preference `p(o)` |
| Homeostatic drive `D` | (implicit in Lyapunov `V`) | Distance from essential bounds | Distance from viability | Free energy `F` |
| Stability budget `λ` | Theorem 2, Eq. 51 | (qualitative: "stable or not") | (qualitative: "viable or not") | (no equivalent) |
| Mode switching | Operating mode `σ` with dwell time | Step function trigger | Algedonic signal | (not modeled) |
| Shield `S` | CBF-QP (Remark 1) | Essential variable bounds (implicit) | S2 Coordination | Prior preferences (soft) |
| Observer `h` | Memory `ṁ = Φ_m(·)` | Direct observation | S4 Intelligence | Perception `argmin_μ F` |
| Recursion | 5 levels within one agent | 2 loops (homeostat + ultrastability) | Recursive viable system | Single level |
| Composition | (single agent) | (single organism) | VSM nesting | (single agent) |
| Meta-control | L4–L5 (adaptation + design) | Ultrastability (outer loop) | S3 Optimization + S3* Audit | (not modeled) |

---

## 4. What Each Framework Contributes to RCS

| Framework | Key Contribution to RCS | Citation |
|-----------|------------------------|----------|
| **Eslami & Yu** | Stability budget equation, switched-system analysis, CBF-QP shields, hysteresis dwell time | arXiv:2603.10779, Theorem 2 |
| **Ashby** | Requisite variety (controller must match disturbance complexity), ultrastability pattern, good regulator theorem | Design for a Brain (1952) |
| **Beer** | Recursive viability (each subsystem is itself viable), organizational function decomposition (S1–S5) | Brain of the Firm (1972) |
| **Active Inference** | Free energy = Lyapunov = reward identity, perception-action duality, precision as gain, allostasis as MPC | Friston (2009), Baltieri & Buckley (2019) |
| **Keramati & Gutkin** | Homeostatic drive as Lyapunov function that simultaneously serves as reward signal | eLife (2014) |
| **Quijano et al.** | Population dynamics for multi-agent coordination, passivity-based stability of evolutionary games | IEEE CSM (2017) |
| **Chacon-Chamorro et al.** | Cooperative resilience metric for fleet performance under disruption | IEEE Trans. AI (2025) |
| **Zhang et al. (ACE) + lineage** | Empirical validation of append-only context updates; collapse event as stability-budget violation; reflector-always-runs as continuous `h₁`; scored bullets as observer of entry utility | ICLR 2026 (ACE); NeurIPS 2023 (Reflexion, Self-Refine); UIST 2023 (Generative Agents) |

---

## 5. Gaps and Open Questions

| Gap | Which Frameworks Address It | RCS Status |
|-----|---------------------------|------------|
| Self-observation cost | None directly (reflexive monitoring is implicit) | Modeled as `β_self·τ̄_self` in stability budget (Remark 7 in LaTeX) |
| Compaction bounds | ACE (append-only empirical), Generative Agents (reflection triggers) | Identified (MHE connection, Section 6.2 of design spec). ACE Fig. 2 provides an empirical anchor; formal bound still needed — see Remark on context collapse in `rcs-definitions.tex` |
| Admission control for context | ACE (implicit via ADD-only), Voyager (binary skill admission) | Shield `S₁` formalization for playbook mutations — enforced per-step entry-churn cap with minimum dwell time (proposed, not yet implemented) |
| Fleet stability | Quijano (passivity), Chacon-Chamorro (resilience metric) | Paper 4 target — RCS composition via decorated cospans |
| Learning dynamics | Eslami (parameter adaptation), Active Inference (belief updating) | Needs formal treatment of `ρ` dynamics (how fast should L2 adapt?) |
| Observer design | Active Inference (variational inference), Eslami (memory update) | Current: fold-as-sufficient-statistic. Future: learned observers with uncertainty |
| Bounded objectives | Mineault et al. (NeuroAI safety), Keramati (homeostatic saturation) | D saturates at 0 — inherent safety against unbounded optimization |
