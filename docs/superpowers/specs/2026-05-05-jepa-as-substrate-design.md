# microRCS — JEPA as Substrate: Architecture, Theory, Validation

**Status:** design (this PR)  •  **Date:** 2026-05-05
**Author:** Carlos Escobar (operator), Claude Opus 4.7 (specifying)
**Linear epic:** parent `BRO-XXX JEPA Substrate Research Program` *(Linear ticket IDs marked `BRO-XXX` in this spec are intentional placeholders — assigned during writing-plans phase when tickets are actually created)*
**Predecessors:**
- `microrcs/THESIS_VALIDATION.md` — capacity sweep (PR #31), Eywa flag (PR #37), gemma4 multi-seed (PR #41), swarm L0 (PR #42), JEPA Experiment A v1 (PR #45), JEPA v2 per-step (PR #47)
- `docs/research-notes/2026-05-05-jepa-as-rcs-frame.md` — design framing
- `docs/research-notes/2026-05-05-jepa-experiment-a-results.md` — v1 null result
- `docs/research-notes/2026-05-05-jepa-experiment-a-perstep-results.md` — v2 data-shape limit
- `docs/research-notes/2026-05-05-eclectic-systems-knowledge-substrate.md` — sibling research note
- `papers/p0-foundations/main.tex` — RCS 7-tuple Σ; vertical L0..L3 hierarchy; Lyapunov decomposition (Asm. 1-2)
- `data/parameters.toml` — canonical λᵢ values

## TL;DR

This spec scopes a research program that turns JEPA (Joint Embedding Predictive Architecture) from a sensor signal into the **substrate** for the RCS controller hierarchy — a learned latent space `Z` and a learned dynamics function `P_φ` that L1 (and eventually L0/L2/L3) act in. The thesis is that **P0's hand-set Lyapunov `V_k` can be replaced by JEPA's predictor energy `E_θ = ‖P_φ(z, a) − z'‖²`**, with stability constants (`α_k, ᾱ_k, γ_k`) becoming learned outputs of VICReg + EMA-target regularization rather than hand-set design parameters.

Five phases — Q1 (substrate + AC-Trajectory-JEPA), Q2 (L1-in-z-space, the empirical anchor), Q3 (online substrate with replay-buffer + canary deployment), Q4 (multi-head L0 — WorldModel/Hybrid/SSC), Q5 (sketched embodied extension). Theorem track in parallel scopes Paper 5 of the RCS series. Validation is **production-like**: SWE-bench-Lite real GitHub bugs as the validation surface; pass^1 on real tasks is the gate, not just λ̂ statistics.

**Status of locked decisions:** seven design decisions taken in brainstorming round (full table below). All locked.

## 0. Locked decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Spec scope | Full Q1+Q2 architectural research note with phased decommit; single document |
| 2 | Theory depth | Engineering + theoretical scaffolding + full theorem (locked Theorem statement; proofs scoped to Paper 5) |
| 3 | Q2 empirical scope | L1 only; L0/L2/L3 architecturally scoped with interfaces, not implemented |
| 4 | Deployment target | microRCS as proving ground; Life Rust integration deferred to its own future spec |
| 5 | Phase gate | Multi-signal pragmatic gate: math (2-of-3) + production (both-of-2 on SWE) + kill criteria |
| 6 | Validation surface | SWE-bench-Lite as primary; real bugs + pytest verification + paired A/B |
| 7 | Encoder cadence | Phase Q3 = online (replay buffer + canary deployment + circuit breaker); Q1+Q2 = frozen |

Three follow-on commitments locked during architecture review:

- **L0Head abstraction** (Section A.3): L0 is a `Protocol` with concrete impls `LlmL0Head`, `WorldModelL0Head`, `StateSpaceL0Head`, `HybridL0Head`, `BehaviorCloningL0Head`. Q2.0 is the mechanical refactor that introduces the protocol; Q4 is multi-head empirical validation.
- **Online JEPA Composite Stability Theorem** (Section B.4): formal statement with assumptions (H8a-e + H9), proof sketch, paper-grade target.
- **Pre-registration discipline** (Section C.5): every phase commits gate thresholds, instance lists, and seeds in a separate PR before data collection. Same protocol as PR #25 noise-floor that buried PR #24's optimistic single-seed signal.

## 1. Why this matters

Current state of the H1 thesis ("recursive control improves agent performance"):

- v1 episode-level JEPA (PR #45): null on capacity-sweep traces. Median Var ratio 1.67. Inconclusive.
- v2 per-step JEPA (PR #47): null on gemma4+REFERENCE due to short-episode data shape. Pipeline shipped; data inadequate.
- Capacity sweep across 4 tiers: H1 is **non-monotone in capacity** — null at gemma4-8B, statistically negative at Sonnet, directional at Opus. Both naive bitter-lesson interpretations refuted.

The unaddressed structural question: are we measuring the right `V_k`? The current heuristic `V_0 = 0.3·cost + 0.3·step + 0.4·(1−score)` is hand-engineered and degenerate within episodes (monotone-increasing per step). JEPA's predictor energy is a **learned alternative** that:

1. Captures within-episode dynamics (predictor surprise tracks divergence-from-success);
2. Generalizes across heads (LLM, world-model, classical controller) via the L0Head abstraction;
3. Provides controllers (L1, eventually L0/L2/L3) with a forward-rollout primitive `argmin_a ‖P_φ(z, a) − z_target‖²` — replacing hand-coded mode logic with learned mode logic;
4. Maps cleanly onto P0's `Π_k = Σ_{k+1}` recursion clause: the predictor IS the dynamics function `f_k` the recursion theorem requires.

Outcomes worth distinguishing:

| Outcome | What it means |
|---|---|
| Q2 z-L1 ≥ hand-L1 on SWE pass^1 | JEPA-as-substrate works; recursion theorem applies in production; Paper 5 ships |
| Q2 z-L1 ≈ hand-L1 (within noise) | JEPA-as-sensor only; substrate is real but no production gain; spec preserved as research |
| Q2 z-L1 < hand-L1 (degradation) | Kill criterion K2; architectural rollback; substrate stays observability-only |
| Q1 fails math gate twice | Kill criterion K1; JEPA downgrades to "fifth instantiation row" in P0 |

Each of these is publishable. The kill criteria force a clean, honest stop.

## 2. Scope

### 2.1 In scope

- **Q1**: Action-Conditioned Trajectory-JEPA substrate (encoder + predictor + EMA target + VICReg-non-optional anti-collapse). Frozen-after-bootstrap.
- **Q2.0**: L0Head protocol introduction. Mechanical refactor of `L0Plant` → `LlmL0Head`. Zero behavior change. ~30 LOC diff.
- **Q2.1**: `L1ForwardRollout` controller — the empirical anchor. 7-mode forward rollout, argmin-energy mode selection, StabilityMonitor circuit breaker.
- **Q3**: `OnlineJepaSubstrate` — replay buffer, KL-regularized online training, canary deployment with shadow-eval gating, atomic deploy + rollback.
- **Q4**: Multi-head L0 — `WorldModelL0Head` and `HybridL0Head` validated against `LlmL0Head` on SWE-bench-Lite.
- **Q5**: Sketched embodied extension — `StateSpaceL0Head` + sensor encoder. Architectural protocol only; implementation deferred to first embodied use case.
- **Theorem track (Paper 5)**: Online JEPA Composite Stability Theorem with assumptions (H8a-e + H9), proof sketched in this spec, full proof scoped to Paper 5.

### 2.2 Out of scope

- Per-tenant substrate isolation (deferred to Life Rust migration spec).
- Vigil/life-spaces production observability integration (deferred).
- Co-training of L1 + substrate (rejected during brainstorm — non-gradient controllers + jointly-trained encoder has no published stability theorem; would solve an orthogonal research problem).
- Re-training cadence variants beyond MVP-frozen and Q3-online (e.g., periodic offline retrain). Deferred to Q3 follow-up if stale-latent symptoms emerge.
- Cross-task transfer studies (open question OQ-3; ablation in Q4 if Q2 passes with margin).

### 2.3 Phase decomposition (overview)

```
Q1   — Substrate + AC-Trajectory-JEPA + Q1 SWE-bench-Lite data collection
Q2.0 — L0Head protocol introduced; L0Plant → LlmL0Head rename
Q2.1 — L1ForwardRollout shipped against frozen substrate; A/B on SWE
Q3   — OnlineJepaSubstrate (replay + canary + circuit breaker)
Q4   — WorldModelL0Head + HybridL0Head; A/B on SWE
Q5   — StateSpaceL0Head architectural sketch (deferred implementation)

Paper 5 — runs in parallel weeks 1-3 (T1-T3), 8-12 (T4-T5)
```

Critical-path duration: ~11-12 weeks. Parallelizable with up to 3 concurrent agents.

## 3. Architecture (Section A)

### 3.1 High-level system

```
┌─────────────────────────────────────────────────────────────────────┐
│                     microRCS RCS Stack                              │
├─────────────────────────────────────────────────────────────────────┤
│  L3 Governance        — hand-feature (unchanged)                    │
│  L2 Meta              — hand-feature (Q2); architecturally scoped Q4│
│  L1 Autonomic         — z-space forward-rollout (NEW in Q2)         │
│      ↑   ↓  z_t, forward rollouts ẑ_{t+1}^{(m)} per mode m         │
│  ╔════════════════════════════════════════════════════════════╗    │
│  ║              JEPA Substrate (NEW)                          ║    │
│  ║  Encoder s_θ : text(frozen 384d) + struct(32d)             ║    │
│  ║                + history(64d) → fusion(64d)                ║    │
│  ║  Predictor P_φ: residual MLP, action-conditioned           ║    │
│  ║  Target s'_θ : EMA of s_θ, momentum 0.99                   ║    │
│  ║  StabilityMonitor: watches λ̂ trends, triggers fallback     ║    │
│  ║  ReplayBuffer (Q3): rolling ~10K (z_t, a_t, z_{t+1})       ║    │
│  ╚════════════════════════════════════════════════════════════╝    │
│      ↑ events.jsonl                                                 │
│  L0 Plant (LlmL0Head|WorldModelL0Head|...) — head abstraction       │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Three-trait family

The architecture is anchored on three Python `Protocol` definitions. These are the load-bearing interfaces; everything else composes via them. The trait split mirrors `AnimaCustody` from Spec D — proven across Wave 2A/B/3 with 6 backends.

```python
class L0Head(Protocol):
    """Abstract L0 plant. The agent loop. Different implementations represent
    different *modalities of action selection* — LLM-driven, world-model-driven,
    classical-controller-driven, hybrid.

    Contract: emit identical RCSEvent kinds (OBSERVE/REASONER_CALL/DECIDE/
    SHIELD/STEP/LYAPUNOV) to the shared EventLog so L1+ observe identically
    across heads. Payloads differ; events shape stays normalized.
    """
    def run_episode(self, task: Task) -> EpisodeTrace: ...
    @property
    def head_kind(self) -> Literal["llm", "world-model", "ssc",
                                    "hybrid", "bc"]: ...
    @property
    def caps(self) -> Caps: ...
    @property
    def system_rules(self) -> list[str]: ...
    @property
    def workspace(self) -> Workspace: ...


class JepaSubstrate(Protocol):
    """The learned latent space + dynamics. L1ForwardRollout depends on THIS,
    not on a specific encoder/predictor. Choice of encoder backbone (custom MLP
    fusion vs V-JEPA-2-vitl) and update cadence (frozen vs online) swap behind
    this trait without touching any controller."""
    def encode(self, ctx: EpisodeContext) -> Tensor: ...
    def predict(self, z: Tensor, action: ActionEmbedding) -> Tensor: ...
    def energy(self, z: Tensor, z_next: Tensor) -> float: ...
    @property
    def is_stable(self) -> bool: ...
    @property
    def version_id(self) -> str: ...


class L1Controller(Protocol):
    """Same surface as existing L1Autonomic. Implementations differ only in
    how decide() forms a Decision."""
    def observe(self, history: list[RCSEvent]) -> HomeostaticState: ...
    def decide(self, obs: HomeostaticState) -> Decision: ...
    def shield(self, dec: Decision, state: HomeostaticState) -> Decision: ...
```

Concrete implementations and their phase:

| Class | Implements | Phase | Role |
|---|---|---|---|
| `LlmL0Head` (rename of L0Plant) | `L0Head` | Q2.0 mechanical | Today's default; cost ~$0.01–1/episode; rate ~0.1–0.5 Hz |
| `WorldModelL0Head` | `L0Head` | Q4 | $0/episode; ~10–100 Hz; needs trained substrate |
| `StateSpaceL0Head` | `L0Head` | Q5 (sketched) | Sensor-driven; 100–500 Hz; gateway to physical control |
| `HybridL0Head` | `L0Head` | Q4 | LLM by default; falls back to WM on rate-limit |
| `BehaviorCloningL0Head` | `L0Head` | Future | Imitation-learn from past successful episodes |
| `MlpJepaSubstrate` | `JepaSubstrate` | Q1 | Frozen-after-bootstrap encoder + predictor |
| `OnlineJepaSubstrate` | `JepaSubstrate` | Q3 | Replay buffer + canary + circuit breaker |
| `L1Autonomic` *(existing)* | `L1Controller` | already | Hand-feature; preserved as fallback |
| `L1ForwardRollout` | `L1Controller` | Q2.1 | New z-space controller via forward rollouts |
| `StabilityMonitor` | (new) | Q2.1 | Watches λ̂; triggers fallback when unstable |

### 3.3 L0Head abstraction rationale

Five reasons this is the right move under the locked decisions:

1. **RCS theoretical alignment**. P0's `Π_k = Σ_{k+1}` clause says controllers are themselves RCS systems. L0Head makes the symmetric statement: *plants* can be parameterized by anything that produces actions. Together: any X_k or Π_k slot accepts a recursive instantiation. Cleanest possible categorical statement of the theory.
2. **Doesn't violate Q2 = L1-only**. Q2.0 introduces the protocol and renames the existing concrete impl. Empirical Q2 still validates only `L1ForwardRollout` against `L1Autonomic`, with `LlmL0Head` as the L0. World-model and friends deferred to Q4.
3. **Composes with the JEPA substrate**. Encoder consumes RCSEvent streams — same shape regardless of which head produced them. Encoder learns features robust across head kinds.
4. **Gateway to control-rate hierarchy**. Different heads occupy different Hz bands (Section J). Substrate becomes the unifying object: same encoder, same predictor, fed by different L0 heads operating at their natural rates. Path to embodied physical control.
5. **Per-episode head selection**. Composition is at the run-loop level; HybridL0Head implements per-step head-switching internally with its own state. Mid-episode head swaps at the run-loop level are forbidden — they create state-tracking pathologies.

### 3.4 Forward-compatibility with Life Rust

The three protocols map directly onto Rust traits with identical semantics. Future Life integration follows the Spec D pattern: trait shipped in microRCS-style first, then Life crate provides Rust implementations. Concrete Rust trait sketches in Section E.6.

## 4. Data Flow + Theoretical Contribution (Section B)

### 4.1 Q1 substrate training data flow

```
   SWE-bench-Lite task instance
            │
            ▼
   ┌──────────────────┐
   │  LlmL0Head       │  emits per agent step:
   │  .run_episode()  │  OBSERVE / REASONER_CALL / DECIDE /
   └──────┬───────────┘  SHIELD / STEP / LYAPUNOV
          │
          ▼
   ┌──────────────────┐
   │  EventLog        │  append-only events.jsonl
   │  (workspace .rcs)│  ← single source of truth
   └──────┬───────────┘
          │ replayed offline
          ▼
   ┌─────────────────────┐
   │ parse_workspace_    │  groups by correlation_id (cid)
   │   events()          │  (one cid = one episode)
   └──────┬──────────────┘
          │
          ▼
   ┌────────────────────┐
   │ StepTrajectory[]   │  ordered (z_t, a_t) per episode
   └──────┬─────────────┘
          │
          ▼
   ┌──────────────────────────────────────────────────┐
   │           EncoderInput pipeline (Q1)             │
   │                                                  │
   │  text_features  : sentence-transformer (frozen,  │
   │                   cached) → R^384                │
   │  struct_features: cost/tokens/latency/step_norm  │
   │                   → R^32                         │
   │  history_features: last K events as token seq    │
   │                    → 1-layer transformer → R^64  │
   │                                                  │
   │  fusion_proj([text; struct; history]) → R^64     │
   │     = z_t                                        │
   └──────┬───────────────────────────────────────────┘
          │
          │  + action_embed(tool_choice) ∈ R^8
          ▼
   ┌──────────────────┐
   │  P_φ predictor   │  ẑ_{t+1} = z_t + MLP([z_t; a_t])
   └──────┬───────────┘  (residual; 3-layer MLP)
          │
          ▼
   loss = ‖ẑ_{t+1} − sg(s'_θ(x_{t+1}))‖² + VICReg(z_t)
          │
          ▼
   Adam(lr=1e-3); EMA target update post-step
          │
          ▼
   substrate.pt (encoder + predictor + EMA target weights)
```

Three load-bearing invariants:

1. **Sentence-transformer is frozen + cached**. No fine-tune. Encoder gradients pass only through fusion + struct + history modules. Means encoder Lipschitz `L_θ` is dominated by ~150K trainable params, not the 22M-param sentence-transformer. Critical for theorem (H8a).
2. **EMA target gets stop-gradient on every forward pass**. Trivially enforces the asymmetry that prevents collapse.
3. **VICReg variance term is non-optional**. Enforces `α_k > 0` (H8 anti-collapse). Cov term may be dropped on small batches; var term never.

### 4.2 Q2 L1 inference data flow

```
   Episode boundary (L0 episode just completed)
          │
          ▼
   ┌─────────────────────────┐
   │ L1ForwardRollout        │
   │  .observe(history)      │  build EpisodeContext from
   │                         │  last N L0 events
   └────────┬────────────────┘
            │
            ▼
   ┌─────────────────────────┐
   │ StabilityMonitor        │  if substrate.is_stable == False:
   │  (circuit breaker)      │     fallback → L1Autonomic.decide()
   └────────┬────────────────┘
            │ stable path
            ▼
   ┌─────────────────────────┐
   │ substrate.encode(ctx)   │
   │   → z_t ∈ R^64          │  ~3-5 ms (sentence-transformer cached)
   └────────┬────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ for m ∈ {base, cot, scratchpad,      │
   │           verify, retry, abort, noop}│
   │   a_m = action_embed(m)              │
   │   ẑ^(m) = substrate.predict(z_t, a_m)│  ~10 µs each
   │   E^(m) = ‖ẑ^(m) − z_target‖²        │
   └────────┬─────────────────────────────┘
            │
            ▼
   chosen = argmin_m E^(m)
   rationale = f"argmin energy={E[chosen]:.3f}"
            │
            ▼
   ┌─────────────────────────┐
   │ shield(Decision)        │  dwell-time hysteresis
   │ (existing pattern)      │  + safety filter
   └────────┬────────────────┘
            │
            ▼
   apply_decision_downward(level=1, ...)
   → emits PARAM_CHANGE event for L0 mode swap
   → emits LYAPUNOV event with V_1 = E[chosen]
```

**z_target lifecycle.** Computed lazily from EMA of latents emitted by past-successful episodes (score ≥ 1.0). Stored persistently at `<workspace>/memory/jepa_z_target.npy`. Updated end-of-epoch alongside stigmergy decay. Defaults to centroid-of-z-space if no successes have occurred (cold-start safety).

**Total per-decision cost.** ~3-5 ms encoder + 7 × ~10 µs predictor = ~5 ms. Compared to L0's LLM call (1-10 sec/step), L1 inference is essentially free.

### 4.3 Q3 online update data flow

```
   Live agent system running (Q2 production)
          │
          ▼ each L0 step emits substrate inputs
   ┌──────────────────────────────────────┐
   │ ReplayBuffer.append(z_t, a_t, z_{t+1})│  rolling window ~10K
   │  - bounded memory: ~50-100 MB         │  - thread-safe write
   │  - LRU eviction at episode boundary   │  - per-(z,a,z') tuple
   └────────┬─────────────────────────────┘
            │
            ▼ background trainer (separate thread)
   ┌─────────────────────────────────────────────┐
   │ Online trainer loop (every K=10 steps):     │
   │  1. sample minibatch from buffer            │
   │  2. compute loss = pred + VICReg + KL_drift │
   │      (KL term = μ · KL[s_θ_t ‖ s_θ_anchor]) │
   │  3. step optimizer; EMA update              │
   └────────┬────────────────────────────────────┘
            │ every Δ=100 trainer steps
            ▼
   ┌─────────────────────────────────────────┐
   │ CanaryGate                              │
   │  - hold candidate weights aside         │
   │  - shadow-eval on N=20 held-out trajs   │
   │    measure: pred_loss, std_mean, λ̂_h    │
   │  - if all within tolerance of baseline: │
   │      substrate.deploy(weights, ver_id)  │   ← atomic swap
   │      anchor ← previous baseline         │   for KL regularizer
   │  - else:                                │
   │      emit RCSEvent(SHIELD,"canary_veto")│
   └────────┬────────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ StabilityMonitor (per-episode check) │
   │  observes λ̂_1 over last K episodes:  │
   │    if λ̂_1 < λ_freeze for J consec:   │
   │      substrate.deploy(last_known_good)│ ← rollback
   │      emit BREAKER event              │
   └──────────────────────────────────────┘
```

Three concurrency invariants:

1. **Atomic deployment**. `substrate.deploy(state_dict, version_id)` is one Python attribute swap; reads see consistent (weights, version_id). No torn reads.
2. **Bounded buffer**. Rolling window keeps memory bounded irrespective of run duration. Eviction is FIFO at episode boundary (not mid-episode) to avoid trajectory fragmentation.
3. **Read-mostly substrate**. L1 inference path holds no locks. Trainer thread holds a coarse-grained lock only during `deploy()` (microseconds). L1 latency stays at ~5 ms even during trainer activity.

### 4.4 Theorem statement: Online JEPA Composite Stability

**Theorem (Online JEPA Composite Stability — Generalized).** Let Σ be an RCS instantiated with:
- L0 head H ∈ {LLM, world-model, SSC, hybrid, BC};
- L1 controller π₁ = `L1ForwardRollout(s_θ, P_φ, z_target)`;
- JEPA substrate `(s_θ, P_φ, s'_θ)` with Q3 online updates;
- Stability monitor and canary gate as specified in Section 4.3.

Suppose:

```
(H8a) Encoder Lipschitz:        ‖s_θ(x) − s_θ(x')‖ ≤ L_θ ‖x − x'‖
(H8b) Predictor Lipschitz:      ‖P_φ(z,a) − P_φ(z',a)‖ ≤ L_P ‖z − z'‖
(H8c) Deployment lag:           weights update every Δ ≥ Δ_min steps
(H8d) KL-bounded drift:         μ ≥ μ_min ⟹ KL[s_θ(t+Δ) ‖ s_θ_anchor] ≤ ε(μ)
(H8e) Stability monitor:        λ̂ < λ_freeze for K steps ⟹ rollback
(H9)  Head Lipschitz emission:  ‖φ_H(payload) − φ_H(payload')‖
                                ≤ L_H ‖payload − payload'‖
```

Then the composite stability budget at level k satisfies:

```
λ_composite^(k) = γ_k                ← frozen-decay (P0 Asm 2; unchanged)
                − L_θ ρ_k             ← adaptation cost (P0; unchanged)
                − L_d η_k             ← design cost (P0; unchanged)
                − β_k τ̄_k            ← delay cost (P0; unchanged)
                − L_oθ(Δ, μ)         ← online encoder cost (NEW)
                − L_H κ_k             ← head cost (NEW)
                − ln(ν_k)/τ_a        ← jump cost (P0; unchanged)
                > 0
```

Where:

- `L_oθ(Δ, μ)` is the **online encoder cost** — captures latent drift between canary deployments. Closed form derived by extending Borkar 2008 Ch. 6 (two-time-scale stochastic approximation) to the deployment-lag setting. Decreasing in Δ; increasing in 1/μ. Vanishes when Δ → ∞ (frozen substrate; Q1+Q2 case).
- `L_H κ_k` is the **head cost** — captures substrate sensitivity to head-specific payload variations. Vanishes when L_H ≤ 1 (head non-amplifying). Penalizes heads whose payloads vary wildly (e.g., poorly-prompted LLM).

**Expected empirical L_H (per head kind).**

| Head | Expected L_H | Why |
|---|---|---|
| LLM (sampling temp 1.0) | 1.5–2.5 | Token sampling stochastic |
| WorldModel | 0.8–1.2 | Deterministic forward rollout |
| StateSpace | 0.5–1.0 | Linear control, low variance |
| Hybrid | max(constituent L_H) | Worst-case constituent |
| BehaviorCloning | 1.0–1.5 | Sampled from policy |

**Proof sketch (5 steps; full proof scoped to Paper 5).**

1. **Lyapunov decomposition**. `V_k(x) = V_k^stable(x) + V_k^drift(x)` — standard P0 quantity + new drift term.
2. **Bound `V_k^drift` via H8c+H8d**. KL regularizer + canary deployment lag ⟹ ‖s_θ(t+Δ) − s_θ(t)‖ ≤ ε(Δ, μ) for explicit ε. Extends Borkar 2008's two-time-scale convergence to discrete deployment events.
3. **Apply (H8a-b)** to bound predictor residual under bounded encoder drift: ‖P_φ(z, a) − ẑ_target‖ ≤ L_P · ε + base error.
4. **Apply (H9)** for head-kind generalization: payload Lipschitz ⟹ encoder features are head-Lipschitz with composed constant L_θ · L_H.
5. **Sum bounds**. Require result satisfies P0's exponential decay condition. Yields the λ_composite formula above.

Paper-5 dependencies:
- Extending Borkar 2008 Ch. 6 to discrete-deployment (Δ-step) updates instead of continuous. Tractable; ~3-4 weeks of theory work.
- New (H8d) KL-bound lemma. Standard result from variational inference literature; cite Bishop 2006.
- Empirical validation that real systems satisfy (H8a-e + H9) — done via the constants-estimation protocol in Section 4.5.

### 4.5 Empirical-constants estimation protocol

Each constant in the theorem is **measurable and CI-gated**.

```python
# scripts/measure_constants.py
def measure_all(substrate: JepaSubstrate, head: L0Head,
                 holdout_data: list[Trajectory]) -> dict:
    return {
        "L_theta": measure_lipschitz(substrate.encode, holdout_data),
        "L_P":     measure_lipschitz(substrate.predict, holdout_data),
        "L_H":     measure_head_lipschitz(head, holdout_data),
        "delta":   substrate.deployment_interval,
        "mu":      substrate.kl_coefficient,
        "L_otheta": measure_drift(substrate, holdout_data),
        "lambda_composite_lower_bound": compute_lambda_composite(...)
    }
```

| Constant | Measurement | Acceptable |
|---|---|---|
| L_θ | Sample N=1000 (x, x') pairs; max ratio ‖s(x)−s(x')‖/‖x−x'‖ | 1.0–3.0 |
| L_P | Same in latent space | 0.8–1.2 |
| L_H | Per-head; payload-pair sampling | per table above |
| Δ | Set explicitly; default Δ=100 trainer steps | ≥ Δ_min = 50 |
| μ | Set explicitly; tune against training stability | 0.01–0.1 |
| L_oθ | Empirical KL drift between deployments | < 0.05 |
| **λ_composite (lower bound)** | **Computed from above; CI-gated > 0** | **must be > 0** |

CI gates a Q3 deployment on `λ_composite_lower_bound > 0`. **Mathematical proof of stability before any production rollout.** If a future change violates the bound, CI fails — system never sees an unstable substrate.

### 4.6 Design patterns deployed

| Pattern | Where | Why |
|---|---|---|
| **Strategy** | L0Head, L1Controller, JepaSubstrate as protocols | Algorithm selection at runtime; clean A/B testing |
| **Observer** | EventLog as broadcast channel | Decouples L0 emission from L1+ consumption; same data drives training and inference |
| **Template Method** | Common parent for substrate impls (init/encode/predict shared, update virtual) | Avoids duplication MlpJepaSubstrate vs OnlineJepaSubstrate |
| **Circuit Breaker** | StabilityMonitor wrapping substrate | Auto-fallback when substrate destabilizes; matches existing StabilityCircuitBreaker pattern |
| **Decorator** | OnlineJepaSubstrate composes Frozen + replay + canary | Adds online behavior atop frozen baseline; removable without touching L1 |
| **Repository** | ReplayBuffer | Encapsulates persistence/sampling; testable in isolation |
| **Adapter** | parse_workspace_events: events.jsonl → StepRecord | Bridges existing storage to new feature pipeline; reusable Q1/Q2/Q3 |
| **Atomic Swap** | substrate.deploy() | Lock-free version updates; readers see consistent state |
| **Single Source of Truth** | EventLog | All training and inference flows through identical event stream |

Explicitly NOT used:

- ❌ **Singleton** — substrate always passed by reference, never global
- ❌ **Builder** — RunConfig dataclass sufficient for construction
- ❌ **Factory** — provider strings ("ollama:gemma4") already work; no abstract factory needed
- ❌ **Active Object** — trainer thread is bounded; no need for command queue indirection

## 5. Empirical Validation Protocol (Section C)

### 5.1 Joint phase gate

A phase Q(N+1) starts iff phase Q(N) passes BOTH the math gate AND the production gate.

```
MATH GATE — any 2 of 3 must pass (noise tolerance by design)
  G1. Median Var[λ̂_0]_JEPA / Var[λ̂_0]_heuristic < 1.0 across ≥3 conditions
  G2. Pearson r(λ̂, episode_score) ≤ −0.2
        (predictor surprise tracks failure)
  G3. Training health: std_mean ≥ 0.5, no NaN, monotone loss

PRODUCTION GATE — both must pass (no degradation tolerance)
  P1. Spearman ρ(λ̂, pass-bool) ≤ −0.15, p<0.05 on holdout trajectories
  P2. z-L1 pass^1 ≥ hand-L1 pass^1 on the SAME task batch
        (McNemar p>0.05 if z-L1 < hand-L1; or z-L1 ≥ hand-L1)

KILL CRITERIA
  K1. Q1 fails math gate AND follow-up data run also fails
        → JEPA downgrades to "P0 instantiation row"; spec preserved
  K2. Q2 fails P2 (z-L1 strictly worse than hand-L1)
        → architectural rollback; substrate stays as sensor only
```

The 2-of-3 on math gate is **deliberate noise tolerance**. Both-of-2 on production gate is **strict** — no regression shipped. Pre-registration (Section 5.5) prevents post-hoc threshold tuning.

### 5.2 Q1 validation

Data collection (locked instances pre-registered):

```
SWE-bench-Lite × 10 instances × 4 conditions × 3 seeds
  Model: Haiku (cost ~$0.10/instance) — cheap, signal sufficient at this tier
  Persistent workspace: ON (--save-events flag)
  Output: ~120 episodes; 50-100 step pairs each = 6K-12K pairs
```

Training:

```
Substrate: 64-d latent, 3-layer fusion encoder
Optimizer: Adam(lr=1e-3), batch 64, 200 epochs
Loss: predictor MSE + VICReg(var=25, cov=1)
Wall-clock: ~30-60 sec on M4 Pro CPU
```

Sanity checks (must pass BEFORE gate evaluation):

- Training loss monotone decreasing
- VICReg std_mean ∈ [0.9, 1.1] by epoch 100
- No NaN in any forward pass
- λ̂_holdout finite for ≥80% of held-out trajectories

### 5.3 Q2 validation (paired A/B on SWE-bench-Lite)

```
arm_A: LlmL0Head + L1Autonomic         (baseline)
arm_B: LlmL0Head + L1ForwardRollout    (treatment)

20 instances × 2 arms × 3 seeds = 120 episodes
Model: Sonnet (real test of architectural value)
Cost: ~$1.10/episode × 120 = $132
Wall-clock: ~12-24 hours
```

Statistical tests (in priority order):

```
Primary:   McNemar's exact test on paired pass/fail
           Power: 80% to detect Cohen's h = 0.3 with n=60 pairs
Secondary: Paired bootstrap on Δpass^1
Tertiary:  Spearman ρ between λ̂ and pass-bool (validates P1)
```

P2 evaluation logic:

```
if z-L1.pass^1 ≥ hand-L1.pass^1:                    PASS  (improvement, any p)
elif McNemar p > 0.05:                              PASS  (no sig. degradation)
else:                                               FAIL P2 → kill criterion K2
```

### 5.4 Q3 validation (online + canary + circuit breaker)

```
arm_C: frozen substrate         (Q2 baseline)
arm_D: online substrate         (Q3 treatment)
Both run L1ForwardRollout. Same instances. Differs only in cadence.
100-episode SWE-bench-Lite continuous run.
Cost: ~$200; wall-clock ~7-14 days.
```

Success criteria (all must pass):

| Check | Threshold | Why |
|---|---|---|
| Successful canary deployments | ≥1 during run | Demonstrates online updates work |
| Emergency rollbacks | ≤1 over 100 episodes | Online stability holds |
| λ̂_1 stability | σ(λ̂_1)/μ(λ̂_1) < 0.5 | Coefficient of variation bounded |
| Performance degradation | arm_D ≥ arm_C - 0.05 pass^1 | Online doesn't hurt production |
| Empirical λ_composite | > 0 throughout | Theorem holds in practice |

### 5.5 Statistical methodology + pre-registration

**Pre-registration discipline.** Before each phase's data collection:

```
Lock in spec doc, committed to git BEFORE any runs:
  - All gate thresholds (G1, G2, G3, P1, P2)
  - All instance IDs (SWE-bench-Lite specific instances)
  - All seeds (e.g., 1, 1009, 2018)
  - All sample sizes
  - All statistical tests + their p-thresholds
```

Same discipline as PR #25 noise-floor protocol. Without pre-registration, "the substrate works" becomes a moving target.

**Power analysis (a priori).**

```
α = 0.05 (Type I error)
β = 0.20 (80% power)
Effect size: Cohen's h = 0.3 (small but practically meaningful)
Required n_paired ≥ 60
Allocated: 20 instances × 3 seeds = 60 paired observations ✓
```

**Reproducibility commitments.**

```
After each phase run:
  - Commit raw events.jsonl + summary metrics
  - Commit analysis script invocation
  - Re-running scripts/jepa_validate.py on committed data must
    reproduce gate decisions to byte equivalence (deterministic CPU)
```

CI smoke test runs validate-script on a tiny synthetic fixture, asserts deterministic output.

### 5.6 Failure mode catalog

| ID | Failure | Detection | Recovery | Prevention |
|---|---|---|---|---|
| FM-1 | Encoder collapse (std_mean → 0) | Training-loop sentry per epoch | Increase VICReg var_weight | VICReg-non-optional invariant; CI gate `std_mean ≥ 0.5` |
| FM-2 | Predictor diverges (NaN in inference) | `substrate.is_stable` returns False | StabilityMonitor falls back to L1Autonomic | Lipschitz regularization + grad clipping |
| FM-3 | z-L1 picks dwell-time-violating mode | `shield()` refuses ModeSwitch | NoOp; episode proceeds with previous mode | Existing dwell-time logic from L1Autonomic, reused |
| FM-4 | Canary thrashing (veto/deploy oscillation) | Trainer log: success < 50% over 10 candidates | Increase Δ; trainer auto-pause | Hysteresis: 3-of-5 windows must succeed |
| FM-5 | Catastrophic forgetting (rollback storms) | Rollback count > 3 over 50 episodes | Increase μ; persistent freeze flag | Pre-deployment shadow eval on holdout |
| FM-6 | Cross-head latent drift (Q4) | Per-head λ̂ diverges over time | Per-head encoder fine-tuning | (H9) head-Lipschitz validation pre-deploy |
| FM-7 | OOM on M4 Pro 24 GB | PyTorch OOM exception | Reduce batch size | Training peak <500 MB; well under limit |
| FM-8 | Test data contamination (Q1 trains on Q2 holdout) | CI gate: instance ID intersection check | Refuse to run | Deterministic train/holdout split per phase |
| FM-9 | Sentence-transformer cache stale | Hash mismatch on model+input | Recompute and update cache | Cache key = sha256(text + model_version) |
| FM-10 | Race condition in online deployment | Stale read from L1 during atomic swap | Atomic single-attribute write | Lock-free read; ~µs deploy critical section |

Each FM has a unit test in `tests/test_failure_modes.py`. CI gates the spec on all 10 having passing tests.

### 5.7 Cost projection + budget

```
PHASE                  | DATA COLLECTION | INFER+TRAIN | TOTAL
-----------------------+-----------------+-------------+--------
Q1 (Haiku data)        |        $4       |  $0 (CPU)   |   $4
Q2 A/B (Sonnet)        |      $132       |  $0 (CPU)   | $132
Q3 online demo         |      $200       |  $0 (CPU)   | $200
Constants measurement  |        $0 (Q1+Q2 reuse)       |   $0
Failure recovery buffer|       $50       |  $0         |  $50
-----------------------+-----------------+-------------+--------
TOTAL DOLLAR COST                                      | $386

Wall-clock (continuous):
  Q1   ~1 day
  Q2   ~3 days
  Q3   ~7-14 days
  Constants  ~2 hours

Engineering time (focused):
  Q1 substrate + encoder pipeline:         2 weeks
  Q2.0 + Q2.1 L1ForwardRollout:           2 weeks
  Q3 OnlineJepaSubstrate + canary:         4 weeks
  Theory (Theorem proof, parallel):        3-4 weeks
  Q4 + Q5 sketches:                        already covered

  Total focused engineering:               ~3 months calendar
  Total dollar cost:                       <$400
```

## 6. Phase Decomposition + Linear Tickets + PR Sequencing (Section D)

### 6.1 Linear epic structure

```
BRO-XXX  JEPA Substrate Research Program (parent epic)
   ├── BRO-XXX  JEPA-Q1: Substrate + AC-Trajectory-JEPA       (8 tickets)
   ├── BRO-XXX  JEPA-Q2.0: L0Head Protocol Refactor           (3 tickets)
   ├── BRO-XXX  JEPA-Q2.1: L1ForwardRollout + Validation      (8 tickets)
   ├── BRO-XXX  JEPA-Q3: OnlineJepaSubstrate                  (8 tickets)
   ├── BRO-XXX  JEPA-Q4: Multi-head L0 (post-Q3)              (3 tickets)
   ├── BRO-XXX  JEPA-Q5: Embodied Extension (sketched)        (1 ticket)
   └── BRO-XXX  PAPER-5: Online JEPA Stability Theorem        (5 tickets)
```

Each sub-epic is **independently shippable**.

### 6.2 Phase Q1 tickets

```
ID      Subject                                            Effort   Blocks
─────────────────────────────────────────────────────────────────────────
Q1-T1   swe_pilot --save-events flag                       1d      Q1-T2
Q1-T2   Collect Q1 SWE-bench-Lite training data            1d      Q1-T8
        (locked instance set, pre-registered seeds)
Q1-T3   Sentence-transformer cache layer                   2d      Q1-T4
Q1-T4   3-source feature pipeline                          2d      Q1-T5
        (text + struct + history → 64-d via fusion)
Q1-T5   AC-Trajectory-JEPA: action-conditioned P_φ         2d      Q1-T7
Q1-T6   VICReg-non-optional + std_mean CI gate             1d      Q1-T8
Q1-T7   scripts/jepa_validate.py (gate evaluator)          2d      Q1-T8
Q1-T8   Run Q1 validation; emit gate report                1d      —
```

### 6.3 Phase Q2.0 + Q2.1 tickets

Q2.0 — Mechanical refactor (introduces protocol; zero behavior change):

```
Q2.0-T1    Define L0Head protocol (Protocol class)         1d      Q2.0-T2
Q2.0-T2    Rename L0Plant → LlmL0Head; implement protocol  2d      Q2.0-T3
Q2.0-T3    Update all call sites + tests                   1d      Q2.1-T1
```

Q2.0 is a single PR with 3 commits; not 3 PRs. Pattern matches Spec C M0 daemon-rename.

Q2.1 — L1ForwardRollout + validation:

```
Q2.1-T1    Define JepaSubstrate protocol;                  1d      Q2.1-T3
           refactor MlpJepaSubstrate to implement
Q2.1-T2    Define L1Controller protocol;                   1d      Q2.1-T3
           refactor L1Autonomic to implement
           (PARALLEL with Q2.1-T1 — different files)
Q2.1-T3    Implement L1ForwardRollout                      3d      Q2.1-T6
           (load-bearing; the 7-mode forward rollout)
Q2.1-T4    Implement StabilityMonitor circuit breaker      2d      Q2.1-T6
           (PARALLEL with Q2.1-T3)
Q2.1-T5    z_target persistence + lazy refresh             1d      Q2.1-T6
Q2.1-T6    Add --substrate flag to swe_pilot               1d      Q2.1-T7
Q2.1-T7    Implement scripts/swe_compare.py                2d      Q2.1-T8
Q2.1-T8    Run Q2 A/B benchmark + analysis                 3d      —
```

Two-stage review on Q2.1-T3 (load-bearing). Following Spec D pattern: spec-compliance review + code-quality review.

### 6.4 Phase Q3 tickets

```
Q3-T1    ReplayBuffer (thread-safe, rolling window)        3d      Q3-T2
Q3-T2    Background trainer thread                         4d      Q3-T3
Q3-T3    CanaryGate + shadow eval                          3d      Q3-T4
Q3-T4    Atomic deployment + version_id                    2d      Q3-T5
Q3-T5    Wire StabilityMonitor → rollback                  2d      Q3-T6
Q3-T6    scripts/measure_constants.py                      3d      Q3-T7
Q3-T7    CI gate: λ_composite_lower_bound > 0              1d      Q3-T8
Q3-T8    Q3 online demo run + analysis                     2w      —
```

Two-stage review on Q3-T2 (concurrency), Q3-T3 (safety), Q3-T6 (theorem-side).

### 6.5 Phase Q4 + Q5 tickets

```
Q4 (Multi-head L0; post-Q3):
  Q4-T1   WorldModelL0Head (forward-rollout for tools)     3d
  Q4-T2   HybridL0Head (LLM default + WM fallback)         2d
  Q4-T3   L0Head A/B benchmark on SWE (3-way)              1w

Q5 (Embodied; sketched):
  Q5-T1   Sensor encoder for SSC head (architectural       3d
          sketch only; full implementation deferred)
```

### 6.6 Theorem track (Paper 5; parallel)

```
Theorem-T1   Borkar 2008 extension to discrete deployment  1w
Theorem-T2   KL-bound lemma + variational-inference cite   3d
Theorem-T3   (H9) head-Lipschitz formalization             3d
Theorem-T4   Full proof writeup                            2w
Theorem-T5   Paper 5 LaTeX draft + experimental figures    1w
```

Theorem-T1 + T2 + T3 run in parallel with Q1 + Q2 implementation. T4 + T5 depend on Q3 measurements for empirical figures.

### 6.7 Critical path + parallelization

```
WEEK  1    2    3    4    5    6    7    8    9   10   11   12   13   14
─────────────────────────────────────────────────────────────────────────
Q1   ████████ ▒▒▒
Q2.0     ▓▓▓
Q2.1          ████████  ▒▒
Q3                              ████████████████  ▒▒▒
Q4                                                          ████████
Theorem ████████████  ▓▓▓▓▓▓▓▓                              (T4-T5)

█ = engineering         ▒ = run + analysis    ▓ = mechanical/parallel
```

Critical path: ~11-12 weeks. Max 3 concurrent agents.

### 6.8 PR sequencing + stack discipline

Stacked-PR pattern proven across the JEPA work this session (PR #44 → #45 → #47):

```
main
 ├── feat/jepa-q1-save-events           (Q1-T1)
 ├── feat/jepa-q1-data-collection        (Q1-T2; depends on T1 in main)
 ├── feat/jepa-q1-st-cache               (Q1-T3)
 ├── feat/jepa-q1-feature-pipeline       (Q1-T4)
 ├── feat/jepa-q1-action-conditioned-jepa (Q1-T5)
 ├── feat/jepa-q1-vicreg-required        (Q1-T6)
 ├── feat/jepa-q1-validate-script        (Q1-T7)
 └── feat/jepa-q1-validation-run         (Q1-T8)
```

Each PR is rebased onto main once dependencies merge. Branch lifecycle: ~1-3 days from create to merge.

CI requirements per PR:

- `pytest microrcs/tests/` (must pass; current 246+ baseline)
- `pytest microrcs/tests/test_failure_modes.py` (each FM detected)
- `ruff/black` format check
- `mypy --strict` type check on substrate + L1 modules
- `λ_composite > 0` gate (Q3 only; CI smoke uses synthetic substrate)
- Reproducibility: re-run validate script produces byte-identical output

### 6.9 Pre-registration commits

Before each phase begins, the spec doc is updated AND committed in a separate PR with locked thresholds.

```
PHASE  PR title                                  Lock contents
─────────────────────────────────────────────────────────────────
Q1     docs(microrcs): pre-register Q1 thresholds    Instance set, seeds,
                                                  G1-G3 thresholds, P1 ρ
Q2     docs(microrcs): pre-register Q2 thresholds    Instance set, seeds,
                                                  McNemar α, n_pairs
Q3     docs(microrcs): pre-register Q3 thresholds    Constants ranges,
                                                  λ_composite floor,
                                                  rollback hysteresis
```

These pre-registration PRs are committed BEFORE any data run. Downstream analysis scripts cite the specific commit hash.

## 7. Risk Analysis + Open Questions + Migration Path (Section E)

### 7.1 Theoretical risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| TR-1 | Constants violate ranges → theorem inapplicable | Medium | High | Empirical fallback; spec updated with measured ranges |
| TR-2 | Borkar 2008 extension stalls | Medium | High | Fall back to "empirical λ_composite > 0" without closed-form |
| TR-3 | (H9) fails for stochastic LLM heads | Medium-High | Medium | Narrow theorem to deterministic heads if L_H > 3.0 |
| TR-4 | KL drift bound violated under tenant load | Low-Medium | High | μ tunable; canary catches violations |
| TR-5 | Forward-rollout on 7-mode action space too small for theorem generality | Low | Low | Action space size doesn't appear in λ_composite formula |
| TR-6 | Theorem proves stability but not optimality | Certain | Low | Optimality is explicit non-goal |

Every theorem-side risk has an empirical fallback. If theory fails, engineering still works.

### 7.2 Implementation risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| IR-1 | Sentence-transformer library churn | Medium | Low | Cache key includes model version |
| IR-2 | PyTorch MPS nondeterminism breaks reproducibility CI | High | Medium | CI uses CPU only |
| IR-3 | Background trainer GIL contention | Medium | Medium | Trainer uses tensor ops (releases GIL) |
| IR-4 | ReplayBuffer memory growth unbounded | Low | High | Bounded rolling window (10K = ~100 MB) |
| IR-5 | Atomic deployment race during canary | Low | High | Single Python attribute write atomic |
| IR-6 | Encoder version_id mismatch in saved logs | Low | Medium | All RCSEvent payloads include `substrate_version_id` |
| IR-7 | Q1-T2 SWE data collection times out | Medium | Medium | Per-instance checkpointing; 2× expected time |
| IR-8 | Q3 trainer thread crashes silently | Low | High | Exceptions propagated to main thread; CI smoke test |
| IR-9 | sentence-transformer + torch version conflicts | Medium | Low | requirements-jepa.txt pinned; Docker image (deferred) |

### 7.3 Empirical risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| ER-1 | SWE traces too short to distinguish L1 modes | Low | High | Pilot data shows 35-98 step episodes |
| ER-2 | Haiku data quality insufficient | Medium | Medium | Q1 success threshold = "predictor learns ANY signal" |
| ER-3 | Sonnet A/B too noisy with n=20 instances | Medium | Medium | n=60 paired sufficient for h=0.3; expand to n=40 if needed ($264) |
| ER-4 | z_target cold-start with 0 successes | Medium | Medium | Centroid-of-z-space initialization; lazy refresh |
| ER-5 | Pearson r on G2 doesn't reach -0.2 | Medium | Low | 2-of-3 rule absorbs single-gate failure |
| ER-6 | Joint gate fails for non-architectural reasons | Low | High | Pre-registration; root-cause analysis required |
| ER-7 | Q3 demo encounters API outage | Medium | Low | Resumable; demo period extends |
| ER-8 | A/B treatment effect lost in within-task variance | Low | Medium | Paired design eliminates this |

### 7.4 Production risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| PR-1 | Online substrate destabilizes mid-deployment | Low (with canary) | Catastrophic | StabilityMonitor + rollback |
| PR-2 | Canary passes but regression surfaces 100+ episodes later | Low-Medium | High | Per-deployment λ̂ tracking + J-of-K hysteresis |
| PR-3 | Cost overrun on Q3 demo | Medium | Low | Per-day cost cap |
| PR-4 | Multi-tenant data leaks (Life-scale) | N/A yet | High | Deferred to Life migration spec |
| PR-5 | LLM API outage during Q3 | Medium | Low | Resumable; checkpoint per episode |
| PR-6 | Substrate file corruption during atomic save | Low | Medium | .tmp + atomic rename + checksum |

### 7.5 Open questions

| ID | Question | Why open | Revisit trigger |
|---|---|---|---|
| OQ-1 | z_target: EMA / median / learned? | EMA is MVP | Post-Q2 if pass^1 improvement <2% |
| OQ-2 | Optimal Δ deployment lag | Δ=100 heuristic | Post-Q3 if canary thrashes (FM-4) |
| OQ-3 | Cross-task substrate transfer | Untested | Post-Q2; smoke test on REFERENCE |
| OQ-4 | Forward-rollout horizon (1-step vs k-step) | 1-step MVP | Post-Q2 if L1 underperforms |
| OQ-5 | VICReg vs Barlow Twins vs BYOL-style | VICReg for clean theory | Post-Q1 if std_mean slow |
| OQ-6 | Action embedding (one-hot / learned / TextEmb) | One-hot MVP | Q4 only |
| OQ-7 | Encoder gradient flow (ST top layer unfreeze?) | Frozen MVP | Post-Q1 if quality insufficient |
| OQ-8 | Shared substrate vs per-level | Shared MVP | Q4 if controllers diverge |

Each OQ has a specific revisit trigger; none are punted indefinitely.

### 7.6 Migration path to Life Rust

Locked decision: **microRCS as proving ground; Life integration deferred** (Section 0, decision #4). This subsection scopes the interface contract that makes future Life migration mechanical.

Rust trait correspondence (target):

```rust
// core/life/crates/autonomic/jepa-substrate/src/lib.rs

pub trait JepaSubstrate: Send + Sync {
    fn encode(&self, ctx: &EpisodeContext) -> Result<Embedding>;
    fn predict(&self, z: &Embedding, action: &ActionEmbedding) -> Result<Embedding>;
    fn energy(&self, z: &Embedding, z_next: &Embedding) -> Result<f64>;
    fn is_stable(&self) -> bool;
    fn version_id(&self) -> &VersionId;
}

pub trait L0Head: Send + Sync {
    type Task;
    fn run_episode(&self, task: Self::Task) -> Result<EpisodeTrace>;
    fn head_kind(&self) -> HeadKind;
    fn caps(&self) -> &Caps;
}

pub trait L1Controller: Send + Sync {
    fn observe(&self, history: &[RcsEvent]) -> HomeostaticState;
    fn decide(&self, obs: &HomeostaticState) -> Decision;
    fn shield(&self, dec: Decision, state: &HomeostaticState) -> Decision;
}
```

Concrete crate breakdown (target Life monorepo):

```
core/life/crates/autonomic/
  jepa-substrate/                   # NEW
    src/{lib.rs, mlp_jepa.rs, online_jepa.rs, stability_monitor.rs}
  l0-heads/                         # NEW
    src/{lib.rs, llm_head.rs, world_model_head.rs, hybrid_head.rs}
  l1-controllers/                   # NEW
    src/{lib.rs, autonomic_l1.rs, forward_rollout_l1.rs}
  autonomic-core/                   # EXISTING
    src/rcs_observer.rs             # adds JepaSubstrate observability hooks
```

ML framework choice:

| Framework | Pros | Cons |
|---|---|---|
| `candle-core` (HF) | Pure Rust; lightweight | Smaller ecosystem |
| `tch-rs` | Full PyTorch; weight interchange | libtorch dependency (200+ MB) |

Default recommendation: **candle-core**. Reconsider if Q3 online updates demand ops not in candle.

Vigil integration (production observability):

```
substrate_lambda_composite_lower_bound  : Gauge<f64>
substrate_canary_deploys_total          : Counter
substrate_canary_vetoes_total           : Counter
substrate_rollbacks_total               : Counter
substrate_version_active                : Gauge<u64>
jepa_energy_per_episode                 : Histogram<f64>
l1_forward_rollout_decision_latency_ms  : Histogram<f64>
```

life-spaces integration: substrate version_id broadcast to peer agents; rollback events broadcast as alerts.

Production hardening additions: TLS-mTLS for substrate weight sync; KMS-signed weights (canary trust); per-tenant substrate isolation; circuit-breaker integration with `autonomic-core::HomeostaticState`.

Linear ticket sketches (future Life migration spec):

```
LIFE-Q1   Crate jepa-substrate with traits + candle MlpJepaSubstrate
LIFE-Q2   Crate l0-heads with LlmL0Head bridging existing arcand
LIFE-Q3   Crate l1-controllers + L1ForwardRollout
LIFE-Q4   OnlineJepaSubstrate + canary + StabilityMonitor in Rust
LIFE-Q5   Vigil metrics (7 series)
LIFE-Q6   life-spaces broadcast integration
LIFE-Q7   Multi-tenant isolation + KMS-signed weight sync
LIFE-Q8   E2E integration test against arcand + autonomic-core
```

Migration trigger. Life migration begins when ALL of:

1. microRCS Q3 passes empirically
2. Paper 5 theorem ships
3. A tenant requests the substrate (or Life-runtime production needs explicit per-tenant stability budgets)
4. Engineering capacity exists for ~6-week Rust port

Until trigger fires, microRCS stays canonical. Same model as Spec D — Anima trait shipped in microRCS-style first, then Life got 6 backends across Wave 2A/B/3.

## 8. Section J — Control-Rate Profile and Embodied Extension

### 8.1 Per-component Hz budget

| Layer | Per-decision cost | Achievable Hz |
|---|---|---|
| **Predictor `P_φ`** (forward-rollout core) | ~5-10 µs (3-layer MLP, 64-d, M4 Pro CPU) | ~100-200 kHz raw |
| **Encoder `s_θ`** (text→latent, sentence-transformer cached) | ~50 µs cached / ~3-5 ms first call | ~10 kHz cached |
| **L1 forward-rollout decision** (7 modes × predict + argmin) | ~50-100 µs | **~10-20 kHz** |
| **L1 + LLM call** (current production loop) | ~2-10 s | ~0.1-0.5 Hz |

Substrate intrinsic control rate: **~10 kHz**. The LLM in the agent loop is the binding constraint, slowing the system by 4-5 orders of magnitude.

### 8.2 What this enables for genuine dynamic control

If the LLM-driven L0 is replaced with a non-LLM head, the substrate becomes a high-rate controller. Sufficient for:

| Domain | Required rate | Substrate verdict |
|---|---|---|
| Industrial process control (PLC) | 10–100 Hz | ✅ over-sampled |
| UAV / drone attitude | 200–1000 Hz | ✅ comfortable |
| Locomotion / quadruped MPC | 50–500 Hz | ✅ |
| Real-time audio synthesis | 44.1 kHz | ⚠️ marginal |
| Robotic arm trajectory | 100–1000 Hz | ✅ |

Substrate is the right computational class for **physical embodied control** when the encoder's input modality is appropriate (vision/sensor encoder rather than text+history).

### 8.3 Q5 embodied extension

Q5 implements `StateSpaceL0Head` with a sensor encoder variant of `s_θ`. Use case: classical control of a dynamical system. **Architectural sketch only in this spec; full implementation deferred to first concrete embodied use case.**

This bridges the JEPA-as-substrate research program to the physical-intelligence direction without committing to it. Mirrors π₀ family (P0 instantiation row #5) — same architectural template (encoder + predictor + action conditioning) operating at 50 Hz robot control. Substrate-as-L0 is structurally equivalent; only the encoder's input modality differs.

## 9. Section K — L0Head Abstraction (cross-reference)

L0Head abstraction and its rationale are covered in Section 3 (Architecture). This section exists for cross-reference and to anchor future docs that will need to point at the L0Head concept independent of the broader spec.

Key surface (re-stated for cross-reference):

```python
class L0Head(Protocol):
    def run_episode(self, task: Task) -> EpisodeTrace: ...
    @property
    def head_kind(self) -> Literal[...]: ...
```

Concrete heads per phase:

```
Q2.0 — LlmL0Head (rename of L0Plant)
Q4   — WorldModelL0Head, HybridL0Head
Q5   — StateSpaceL0Head (sketched)
Future — BehaviorCloningL0Head
```

Theory: (H9) head-Lipschitz formalization in Section 4.4 (Theorem (H9)) generalizes the Online JEPA Stability Theorem across heads.

Forward compatibility with Life Rust: Section 7.6.

## 10. Closing — pre-registration discipline + reproducibility

### 10.1 Reproducibility commitments

After each phase run:

- Commit raw events.jsonl + summary metrics
- Commit analysis script invocation
- Re-running scripts/jepa_validate.py on committed data must reproduce gate decisions to byte equivalence (deterministic CPU)
- CI smoke test runs validate-script on a tiny synthetic fixture and asserts deterministic output

### 10.2 Cross-references

Predecessors (this spec depends on, cites, and extends):

- `papers/p0-foundations/main.tex` — RCS theory base; instantiation #5 (π₀)
- `microrcs/THESIS_VALIDATION.md` — empirical baseline state across capacity tiers
- `microrcs/scripts/jepa_a.py` — v1 + v2 implementation; foundation for Q1
- `docs/research-notes/2026-05-05-jepa-as-rcs-frame.md` — design-question framing
- `docs/research-notes/2026-05-05-jepa-experiment-a-results.md` — v1 null result
- `docs/research-notes/2026-05-05-jepa-experiment-a-perstep-results.md` — v2 data-shape limit
- `docs/research-notes/2026-05-05-eclectic-systems-knowledge-substrate.md` — sibling research note
- `docs/superpowers/specs/2026-05-05-swarm-rcs-l0-design.md` — sibling design pattern (horizontal axis)

Successors (this spec scopes; future docs will extend):

- `papers/p5-online-jepa-stability/` — Paper 5 LaTeX (parallel theorem track)
- Future Life-migration spec (post-Q3 + post-Paper-5)
- Future microrcs Q4/Q5 specs (if/when Q4 empirical work begins)

### 10.3 Definition of done for this spec

This spec is "done" when:

1. ✅ All seven locked decisions explicitly stated and traceable to brainstorm
2. ✅ Three-trait architecture defined with concrete impls per phase
3. ✅ Theorem statement (H8a-e + H9) committed with proof sketch
4. ✅ Empirical-constants estimation protocol with CI gate definition
5. ✅ Phase decomposition with Linear ticket sketches and dependency graph
6. ✅ Cost projection ($386 + ~3 months engineering)
7. ✅ Risk/OQ/migration sections complete with mitigations
8. ✅ Section J control-rate profile + Section K L0Head cross-reference

The spec is NOT a buildable plan. The buildable plan comes next via the writing-plans skill (Step 9 in the brainstorming flow). This spec is the architecture, theory, and validation contract.
