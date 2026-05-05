---
title: "JEPA as an Alternative Formalization of the RCS Recursion Thesis"
date: 2026-05-05
tags: [jepa, rcs, world-models, research-note]
relates_to:
  - "[[2026-05-05-eclectic-systems-knowledge-substrate]]"
  - "[[../../microrcs/THESIS_VALIDATION.md]]"
  - "[[../../papers/p0-foundations/main.tex]]"
---

# JEPA as an Alternative Formalization of the RCS Recursion Thesis

**Date:** 2026-05-05
**Trigger:** The capacity-sweep result (PR #31, BRO-945) left the H1 thesis empirically null at gemma4 / Haiku, statistically negative at Sonnet, and directionally positive at Opus. We need a *second formalization* of "recursive control improves agent performance" that is not bound to the 7-tuple Σ + per-level Lyapunov story — one with a learned energy and a falsifiable per-level prediction error. JEPA (LeCun's Joint Embedding Predictive Architecture) offers exactly that. P0 already cites V-JEPA-2 as Instantiation #3 in the catalogue (`papers/p0-foundations/main.tex` lines 1009–1013); this note asks whether JEPA could be promoted from "instantiation" to "alternative substrate for the entire H1 thesis."

## Executive summary

1. **JEPA's energy is structurally a Lyapunov function.** The predictor's residual `E_θ(s, s') = ||P_φ(s) - s'||²` has the correct sandwich structure for `V_k` in P0's Assumption 1, modulo a learned (not designed) sandwich constant. The collapse-prevention regularizers (VICReg, Barlow Twins) play the role of the stability-budget guarantee `λᵢ > 0`.
2. **H-JEPA is structurally an RCS hierarchy.** LeCun's 2022 "Path Toward Autonomous Machine Intelligence" already proposes a multi-level predictor stack with dwell-time separation — exactly H6 (time-scale separation) in P0.
3. **The thesis becomes empirically cleaner under JEPA.** "Recursive control helps" can be operationalized as: *"adding a hierarchical level above L_k strictly reduces L_k's marginal prediction-error budget more than a same-capacity flat baseline."* This is one regression test, not 6,040 episodes of pass^k bench.
4. **Hardware feasibility is real.** A toy MLP-JEPA on existing microRCS bench traces fits in seconds on the M4 Pro 24 GB. V-JEPA-2-vitl (0.3B) inference fits in <2 GB at fp16, well inside MPS budget. V-JEPA-2-vitg (1B) inference fits at ~4 GB fp16. Pretraining at LeCun scale does not.

## 1. JEPA architecture summary

### 1.1 Core construct

JEPA learns a representation in which **future states are predictable from present states plus action**, but the prediction is performed in a **latent space**, not pixel/token space. Three modules are jointly trained:

- **Context encoder** `s_θ : X → Z` — maps observation `x` to embedding `z`.
- **Target encoder** `s'_θ : Y → Z` — maps target observation `y` to embedding `z'`. In I-JEPA / V-JEPA the target encoder is an EMA of the context encoder (BYOL-style).
- **Predictor** `P_φ : Z × A → Z` — given context embedding and action `a` (or "future mask" in image variants), predict target embedding.

The training loss is the energy

```
E_θ,φ(x, y, a) = || P_φ(s_θ(x), a) - s'_θ(y) ||²
```

minimized over compatible `(x, y, a)` triples. The key win over generative world-models (Dreamer, GAIA-1) is that JEPA does not have to predict pixels: irrelevant detail (lighting, background motion) is allowed to be encoded away. This is what LeCun calls the *abstraction property*.

### 1.2 Variants

| Variant | Domain | Reference |
|---|---|---|
| I-JEPA | Static images | Assran et al., CVPR 2023, arXiv:2301.08243 |
| V-JEPA | Short video | Bardes et al., NeurIPS 2024, arXiv:2404.08471 |
| **V-JEPA-2** | Long video + action-conditioned planning | Assran et al., 2026, arXiv:2406.09246 (cited as `assran2025vjepa2` in P0) |
| MC-JEPA | Multi-task (motion + content) | Bardes et al., 2023, arXiv:2307.12698 |
| H-JEPA | Hierarchical, multi-time-scale | LeCun 2022, "A Path Toward Autonomous Machine Intelligence" (no arXiv ID; Open Review submission) |

### 1.3 Energy-based formulation

JEPA is an **Energy-Based Model** in Y. LeCun's strict sense: training does not produce a likelihood, only a scalar `E_θ(x, y)` whose minima coincide with compatible pairs. The pathology to avoid is **representational collapse** — the trivial solution `s_θ(·) = const` minimizes the loss with zero gradient. Three known regularizers prevent this:

- **VICReg** (Bardes et al., arXiv:2105.04906): Variance + Invariance + Covariance regularization on `z`.
- **Barlow Twins** (Zbontar et al., arXiv:2103.03230): cross-correlation matrix → identity.
- **EMA target + masking** (BYOL/JEPA-style): asymmetric encoder pair breaks the trivial solution implicitly.

These regularizers are **not optional**: without them the energy is degenerate. They are the load-bearing element of the entire framework.

### 1.4 H-JEPA — the multi-level construction

LeCun's 2022 vision paper proposes **stacking JEPAs** with progressively coarser prediction horizons:

- L0 frame-level predictor (predicts t+1 from t)
- L1 segment-level predictor (predicts segment-level latent from a segment of L0 latents)
- L2 scene-level predictor (predicts scene-latent from segments)

Each level has its own encoder, predictor, and energy. The cross-level interface is: L_{k+1} predicts the **target latent** that L_k will be operating in over the next dwell window. This is structurally the same as P0's `Π_k = Σ_{k+1}` controller-as-recursive-system clause.

## 2. Mapping JEPA primitives to RCS thesis

This is the load-bearing section. The mapping is tight enough that JEPA is plausibly an alternative substrate for P0's claims, not merely a fifth instantiation row.

### 2.1 Structural isomorphism table

| RCS 7-tuple symbol (P0 §III) | JEPA primitive | Mapping fidelity |
|---|---|---|
| State `X_k` | Latent space `Z_k` (encoder image) | **Tight** — both are continuous embedding spaces; sandwich condition (Asm. 1) maps to bounded-norm regularization on `Z_k`. |
| Output `Y_k` | Predicted future latent `ẑ' = P_φ(z, a)` | **Tight** — JEPA predicts in the same metric space it observes. |
| Action / control `U_k` | Action conditioning `a` of `P_φ` | **Tight** when JEPA is action-conditioned (V-JEPA-2 with CEM-MPC); **loose** for unconditioned I-JEPA. |
| Dynamics `f_k` | Predictor `P_φ` | **Tight** — both are learned/specified maps `(state, action) → next state`. |
| Observation `h_k` | Encoder `s_θ` | **Tight** — both go from "raw" world to "agent-internal" space. The EMA target encoder `s'_θ` introduces an asymmetry P0 doesn't currently model. |
| Shield `S_k` | Energy threshold `E_θ < ε` (intrinsic cost, V-JEPA-2 row of P0 instantiations table, line 1012) | **Medium** — P0's shield is hard-set-membership; JEPA's is a soft energy gate. The CEM-MPC action filter in V-JEPA-2 makes it concrete. |
| Controller `Π_k = Σ_{k+1}` (recursion clause) | L_{k+1} JEPA predictor over a coarser-grained latent | **Tight in spirit, hand-wavy in current literature** — H-JEPA proposes it but no public implementation has end-to-end training of three or more levels with proven dwell-time separation. |
| Lyapunov `V_k(x)` (Asm. 1) | **Energy** `E_θ(z, ẑ')` along a trajectory | **Tight modulo learned sandwich.** See §2.2. |
| Stability budget `λ_k > 0` (Eq. 1) | Bound on **per-level prediction-error growth rate** | **Tight modulo regularizer guarantees.** See §2.3. |

### 2.2 The energy-as-Lyapunov correspondence (the key claim)

P0 Assumption 1 (`papers/p0-foundations/main.tex` lines 360–371) requires a function `V_k : X_k → ℝ_{≥0}` with sandwich

```
α_k ||x||² ≤ V_k(x) ≤ ᾱ_k ||x||²
```

and Assumption 2 (lines 373–381) requires a frozen-decay rate `γ_k > 0`:

```
V_k(x_{t+1}) - V_k(x_t) ≤ -γ_k V_k(x_t).
```

JEPA's energy along a closed-loop trajectory is `E_t = ||P_φ(z_t, a_t) - z_{t+1}||²`. If we define `V_k(z) := E_t` evaluated at the realized next state, then:

- **Sandwich**: holds whenever the encoder image is bounded and the predictor is `L_P`-Lipschitz. VICReg's variance term enforces a strict positive lower bound `α_k > 0` on representation magnitude; the covariance/invariance terms enforce the upper bound. So `α_k, ᾱ_k > 0` are *learned constants* recoverable from the regularizer hyperparameters.
- **Frozen-decay**: holds along action-conditioned planning trajectories whenever the agent is closing the loop with the predictor. V-JEPA-2 reports `γ_k > 0` empirically over horizons `T ≤ 16` frames (P0 instantiations row, line 1013).

The correspondence is therefore: **`V_k = E_θ`** with the trade-off that `(α_k, ᾱ_k, γ_k)` are no longer hand-set design parameters but *outputs of the regularizer + training loop*. This is the central asymmetry of the JEPA framing.

### 2.3 Collapse-prevention as the stability-budget guarantee

P0 Eq. 1 (line 426–438) says level `k` is stable iff

```
λ_k = γ_k - L_θ ρ_k - L_d η_k - β_k τ̄_k - ln(ν_k)/τ_a > 0.
```

Under JEPA the budget terms map as:

| P0 term | JEPA analog |
|---|---|
| `γ_k` (frozen decay) | Empirical predictor-error decay rate measured on holdout trajectories. |
| `L_θ ρ_k` (adaptation) | Lipschitz of the encoder w.r.t. its weights × EMA momentum schedule. |
| `L_d η_k` (design) | Drift of the predictor head when the higher-level conditioning latent is updated. |
| `β_k τ̄_k` (delay) | Latency between action emission and target-encoder refresh. |
| `ln(ν_k)/τ_a` (jump) | KL divergence between adjacent EMA snapshots, divided by EMA half-life. |

The crucial extra constraint JEPA imposes: `λ_k > 0` is **necessary but not sufficient** — we additionally need the regularizer (VICReg / Barlow / EMA asymmetry) to bound `α_k > 0`, otherwise the trivial collapse solution gives `λ_k = ∞` for the meaningless reason that constants are perfectly predictable. This is a hypothesis P0 currently does not formalize. **Under a JEPA framing, P0 would need a new (H8) Anti-collapse:** the encoder `s_θ` satisfies `α_k > c > 0` for some training-determined constant `c`.

### 2.4 What becomes cleaner, what becomes harder

**Cleaner under JEPA:**
- `V_k` is *learned*, not hand-specified. No more "the homeostatic drive is the Lyapunov" axiom (P0 §IV) — it falls out of training.
- Per-level decay `γ_k` is *measurable* from prediction-error decay on held-out trajectories. The current λ̂ estimator on microRCS uses a heuristic `cost+steps+score` formula that has known construct issues (THESIS_VALIDATION.md "Why λ̂ doesn't match paper" section).
- The H1 thesis acquires a **single** falsifiable form: *adding L_{k+1} reduces L_k's marginal prediction-error*. One regression. No more 6,040-episode pass^k bench.

**Harder under JEPA:**
- Proving `λ_k > 0` *globally* requires a regularizer-guarantee theorem we don't have. VICReg's variance term is empirically effective but lacks a formal lower bound on `α_k`.
- The recursion clause `Π_k = Σ_{k+1}` is structurally clean in H-JEPA but has no working public implementation training all levels jointly with dwell-time separation enforced. We'd be the first.
- Cross-level coupling (the time-scale separation H6 of P0 line 500–509) becomes a *training-time invariant*, not an inference-time hypothesis. Easier to satisfy by construction; harder to verify post-hoc on a system not built for it.

### 2.5 The reframed H1 hypothesis

Under JEPA, H1 reads:

> **H1-JEPA:** Let `E_k(t)` denote per-level prediction error of L_k under closed-loop training. Adding L_{k+1} above L_k yields a lower marginal `E_k` integral than a same-capacity flat baseline trained on the same data, controlling for total compute.

This is *cleaner* than the current H1 because:
- No pass-rate ceiling effects (the gemma4 reference suite ceiling that masked PR #28's compounding signal).
- No verifier-aggregation entanglement (the "majority voting kills your swarm" finding from PR #42).
- Direct test of the level-separation principle, which is the underlying claim of P0 Theorem 1.

The empirical signature would be: a U-shaped curve in marginal prediction error vs. capacity matching the U-shape we already observe in H1 across gemma4 → Haiku → Sonnet → Opus.

## 3. Candidate experiments

Three experiments, ordered cheapest first. Each tests a distinct claim from §2.

### Experiment A — MLP-JEPA on existing microRCS traces (cheapest)

**Hypothesis.** A small MLP-JEPA trained on agent-trajectory tuples can produce a `V̂_0` (energy-based Lyapunov estimate) more stable across runs than the current `cost+steps+score` heuristic.

**Input data.** Existing microRCS bench traces. Total ~6,040 episodes. Each episode is a sequence of `(message_t, tool_call_t, observation_t)` tuples. State featurization:

```
z_t = concat([
  embed(last_2_messages),     # 384-dim sentence-transformer
  one_hot(tool_history[-3:]),  # 64-dim
  episode_step_normalized,     # 1-dim
])  # → R^449
```

Action `a_t` = one-hot encoding of next tool choice (8-dim). Target `z_{t+1}` = same encoding of next state.

**Architecture.** `s_θ: R^449 → R^128` (2-layer MLP, 256 hidden). `P_φ: R^128 × R^8 → R^128` (3-layer MLP, 256 hidden, residual). Total: ~200K params. EMA target encoder, momentum 0.99. VICReg loss with λ=25, μ=25, ν=1 (canonical settings from arXiv:2105.04906).

**Training cost.** ~5 min on M4 Pro MPS at batch size 256, 50 epochs. Trivially feasible.

**Expected output.** Trajectory of `V̂_0(t) = E_θ(z_t, ẑ_{t+1})` over each episode. Compute λ̂_0 as the slope of `log V̂_0` vs `t` over the inner-loop window.

**What it would prove.** If `Var[λ̂_0]` across runs (held-out at 4 capacity tiers gemma4 / Haiku / Sonnet / Opus) is *substantially smaller* than the current `Var[λ̂_0]` from `cost+steps+score`, the JEPA framing is empirically more reliable. If it's larger, the current heuristic is a better Lyapunov surrogate than a learned one for this data shape.

**What it would refute.** If `λ̂_0` is *negative* on every condition (including known-stable flat baselines), then the JEPA energy is not a valid Lyapunov on this data and the framing collapses to "interesting analogy, not substrate."

### Experiment B — Two-level H-JEPA trained on stacked traces (medium)

**Hypothesis.** Adding a coarser-grained L1 JEPA above L0 reduces L0's effective `λ̂_0` by absorbing slow drift into the L1 latent — the recursion-helps signal P0 Theorem 1 predicts.

**Input data.** Same traces, but episode-level stacking. L0 operates on per-step tuples (Experiment A). L1 operates on per-episode summaries: `z_episode = mean_t z_t + max_t z_t` concatenated with episode-level metadata (suite, condition, score).

**Architecture.** L0 same as Experiment A. L1: `s_θ^1: R^256 → R^64` (2-layer MLP, 128 hidden). `P_φ^1: R^64 → R^64` predicts next-episode latent from current episode latent. Cross-level coupling: L1 emits a 32-dim "context vector" that is concatenated to `z_t` at L0 (residual addition path; no gradient flow to preserve dwell-time separation, in the spirit of Driess et al. knowledge insulation, P0 lines 1050–1066).

**Training cost.** ~30 min on M4 Pro MPS. Joint training with both losses.

**Expected output.** Compare `λ̂_0` with vs. without the L1 conditioning. Predict 5–15% reduction in `Var[λ̂_0]` at Opus tier (where current empirical H1 is directionally positive), no change at gemma4 tier (where empirical H1 is null), modest *increase* at Sonnet tier (where empirical H1 is statistically negative).

**What it would prove.** If the prediction-error reduction matches the U-shape of empirical H1, JEPA recovers the tier-dependent signal *via a single continuous metric*, not via 6,040 binary pass^k outcomes. This would be a major win for the framing.

**What it would refute.** If L1 conditioning never reduces L0 prediction error, then either (a) recursion genuinely doesn't help in the JEPA sense, in which case empirical H1 is a verifier-or-aggregation artifact, or (b) the chosen L1 latent dimension is wrong and we need to sweep.

### Experiment C — V-JEPA-2 inference on Arcan tool-screen captures (expensive, future)

**Hypothesis.** A pretrained V-JEPA-2 video model can serve as the L0 perception substrate of an Arcan-running RCS hierarchy, with the L0 → L1 interface specified in JEPA energies rather than text scoring.

**Input data.** Screen captures of the Arcan agent operating (already collected via prosopon's display server, see `core/prosopon/` and the prosopon project page). ~10s clips at 256×256, 16 frames each.

**Architecture.** Frozen V-JEPA-2-vitl-fpc16-256 (`facebook/vjepa2-vitl-fpc16-256-ssv2`, 0.4B params, ~1.6 GB at fp16) as encoder. Custom predictor head fine-tuned on Arcan trajectory data. L1 = Autonomic gating model (existing Rust crate).

**Cost.** Pretraining infeasible locally; inference + small predictor finetune feasible. ~1–2 wks engineering effort. No GPU rental needed: M4 Pro MPS handles V-JEPA-2-vitl inference at ~1–2 fps which is sufficient for offline retroactive analysis.

**What it would prove.** That the JEPA-as-RCS framing is operationally usable on a real Agent OS, not just a synthetic dataset. This is the bridge from "interesting alternative formalization" to "production-grade L0 in Life."

**Defer until.** Experiments A and B yield positive signals on the U-shape recovery.

## 4. Hardware feasibility on M4 Pro 24 GB

Audit on `Apple M4 Pro, Mac16,7, 24 GB unified memory, no dedicated GPU; PyTorch MPS backend available`.

### 4.1 What fits comfortably

| Workload | Footprint | Feasibility |
|---|---|---|
| MLP-JEPA training (Experiment A) | <100 MB model + <500 MB activations at batch 256 | **Trivial.** ~5 min wall clock. |
| Two-level H-JEPA training (Experiment B) | <500 MB model + <2 GB activations | **Easy.** ~30 min wall clock. |
| V-JEPA-2-vitl inference (`facebook/vjepa2-vitl-fpc64-256`, 0.3B) at fp16 | ~1.2 GB weights + ~2 GB activations per 64-frame clip | **Comfortable.** ~1–2 fps offline. |
| V-JEPA-2-vith inference (`facebook/vjepa2-vith-fpc64-256`, 0.7B) at fp16 | ~2.8 GB weights + ~4 GB activations | **Comfortable.** ~0.5 fps offline. |
| V-JEPA-2-vitg inference (`facebook/vjepa2-vitg-fpc64-256`, 1B) at fp16 | ~4 GB weights + ~5 GB activations | **Tight but works.** Close gemma4 in Ollama first. |

### 4.2 What does not fit

| Workload | Footprint | Verdict |
|---|---|---|
| Full V-JEPA-2 pretraining (any size) | ≥80 GB activations, multi-GPU expected | **Infeasible.** Use checkpoints. |
| V-JEPA-2-vitg inference at fp32 | ~16 GB weights + ~12 GB activations | **Infeasible.** Use fp16 or smaller variant. |
| Heterogeneous in-memory ensemble (V-JEPA-2-vitg + gemma4-8B + Sonnet API client) | >24 GB combined | **RAM-bound.** Same constraint as the eclectic-systems note. Swap model loads or use API-only diversity. |

### 4.3 Pretrained checkpoints available

Verified via HuggingFace `facebook/` org search (2026-05-05):

| Model slug | Params | Use case |
|---|---|---|
| `facebook/vjepa2-vitl-fpc64-256` | 0.3B | Smallest V-JEPA-2; default for Experiment C |
| `facebook/vjepa2-vitl-fpc16-256-ssv2` | 0.4B | Action-recognition fine-tune; useful for tool-screen classification |
| `facebook/vjepa2-vith-fpc64-256` | 0.7B | Mid-tier; better for fine-grained motion |
| `facebook/vjepa2-vitg-fpc64-256` | 1B | Largest publicly released; near M4 Pro ceiling at fp16 |
| `facebook/vjepa2-vitg-fpc64-384` | 1B | Higher input resolution; same parameter count |

All checkpoints uploaded 2025-08-11. License: CC-BY-NC 4.0 (research use is fine; commercial use of derivatives in a Life-tenant deployment would need clearance).

### 4.4 The binding constraint, restated

Same as the sibling eclectic-systems note: **RAM caps the in-memory ensemble at ~14B in token-models or ~1B in V-JEPA-2 video models.** API-mediated diversity remains the cheapest path to heterogeneity, but for JEPA we don't need diversity at inference time — we need a single solid encoder + a small predictor, both of which fit. **JEPA is locally feasible to a depth the LLM-stack-as-substrate isn't.**

## Recommendation

Pursue JEPA-as-RCS as a **fourth axis** parallel to the three currently in flight (vertical RCS, horizontal Plexus, modal Eywa). Specifically:

- **Tier-1 commitment now:** ship Experiment A. Cost is hours; signal is immediate. If the learned `V̂_0` is more reliable across capacity tiers than the current heuristic, this becomes the empirical λ̂ estimator for the F2 Life-side instrumentation (`crates/autonomic/autonomic-core/src/rcs_budget.rs`) and downgrades the current cost+steps+score formula to a pre-JEPA baseline.
- **Tier-2 contingent on A:** ship Experiment B if and only if A's `λ̂_0` is well-calibrated. The U-shape recovery is the headline test.
- **Tier-3 deferred:** Experiment C (real V-JEPA-2 on Arcan) belongs in v0.4+ — it requires both A and B to work *and* a stable prosopon→V-JEPA-2 capture pipeline, neither of which exist today.

Scientific value: high. JEPA gives us a *learned* Lyapunov, a *measurable* per-level decay, and a *single* falsifiable H1. Feasibility: high at Tier 1–2, blocked by data plumbing (not compute) at Tier 3. Net verdict: **start Experiment A this week.** Open a BRO ticket as `jepa-as-rcs-experiment-a` under the RCS project.

## Sources

- LeCun, Y. (2022). "A Path Toward Autonomous Machine Intelligence." OpenReview (no arXiv).
- Assran, M. et al. (2023). "Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture" (I-JEPA). CVPR 2023, arXiv:2301.08243.
- Bardes, A. et al. (2024). "V-JEPA: Latent Video Prediction for Visual Representation Learning." NeurIPS 2024, arXiv:2404.08471.
- Assran, M. et al. (2026). "V-JEPA 2: Self-Supervised Video Models." arXiv:2406.09246. (Cited in P0 as `assran2025vjepa2`.)
- Bardes, A. et al. (2023). "MC-JEPA: A Joint-Embedding Predictive Architecture for Self-Supervised Learning of Motion and Content Features." arXiv:2307.12698.
- Bardes, A. et al. (2022). "VICReg: Variance-Invariance-Covariance Regularization for Self-Supervised Learning." ICLR 2022, arXiv:2105.04906.
- Zbontar, J. et al. (2021). "Barlow Twins: Self-Supervised Learning via Redundancy Reduction." ICML 2021, arXiv:2103.03230.
- HuggingFace `facebook/` model org, V-JEPA-2 collection (verified 2026-05-05): `facebook/vjepa2-{vitl,vith,vitg}-fpc{16,32,64}-{256,384}{,-ssv2,-diving48}`.
- P0 paper: `~/broomva/research/rcs/papers/p0-foundations/main.tex` §III–§V; instantiations Table at lines 988–1037.
- microRCS empirical state: `~/broomva/research/rcs/microrcs/THESIS_VALIDATION.md` (capacity sweep, gemma4 multi-seed, swarm-L0).
- Sibling note (same date): `2026-05-05-eclectic-systems-knowledge-substrate.md`.
