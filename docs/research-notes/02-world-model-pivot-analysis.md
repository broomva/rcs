---
title: "World-Model Pivot Analysis — LLM-as-Π₀ vs World-Model-as-Plant vs Hybrid vs Controller-Agnostic"
tags: [rcs, research-note, world-model, controllability, decision-matrix]
linear: BRO-697
created: "2026-04-17"
status: wave-1-research
related:
  - "[[rcs-definitions-ieee.tex]]"
  - "[[framework-unification]]"
  - "[[life-rcs-mapping]]"
---

# Note 02 — World-Model Pivot Analysis

**Scope.** Evaluate four candidate framings of Level 0 in the RCS hierarchy. Do **not** recommend a choice. Produce a decision matrix, enumerate what breaks in the current paper under each framing, list failure modes each framing inherits, and state what would need to be true for each framing to be the right choice.

**Framings under evaluation.**

- **A — LLM-as-Π₀.** Current paper framing. The LLM *is* the plant at the lowest level; it exposes an internal state (embeddings, KV-cache) that obeys a stochastic discrete-time dynamical system. Controllability is asserted via Bhargava et al. (2023) and Soatto et al. (2023).
- **B — World-Model-as-Plant.** Level 0 is a learned latent-dynamics model à la DreamerV3 / TD-MPC2 / R2I. The LLM is promoted to Level 1 (or higher), acting as policy/planner on the latent state.
- **C — Hybrid.** L0 is a learned latent-dynamics world model **and** L1 is an LLM policy operating over that latent. Stacked instantiations of B; the LLM never touches the physical plant directly.
- **D — Controller-Agnostic.** The RCS 7-tuple does not specify what Π is. LLM-policies, Dreamer-policies, CBF-shielded RL policies, and PID-steering controllers are all four concrete instantiations. The framework becomes a meta-template; each application paper proves its own stability conditions.

The current paper (`latex/rcs-definitions-ieee.tex`, Secs. I–II, VI) defaults to **A** in its motivation (Sec. I) and implementation narrative (Sec. VI → Life's `shell.rs` agent loop as Π₀) but the abstract framework-unification table (`docs/framework-unification.md`, Sec. 2.1) already hedges toward **D** ("LLM as implicit world model" at Eslami's L3). The framings below treat these as live alternatives rather than settled positions.

---

## 1. Decision Matrix

Each cell has a short qualitative verdict plus at least two published references per framing. References are cited inline by arXiv id; bibliographic details are in Sec. 5.

| Axis | A — LLM-as-Π₀ | B — World-Model-as-Plant | C — Hybrid (WM + LLM policy) | D — Controller-Agnostic |
|---|---|---|---|---|
| **Mathematical rigor gained** | **Low.** LLM is a shift-and-grow discrete stochastic system (Bhargava arXiv:2310.04444 Sec. 3; Soatto arXiv:2305.18449 Thms. 2–3). Khalil-style quadratic Lyapunov bounds $\underline{\alpha}\|x\|^2 \leq V(x) \leq \bar{\alpha}\|x\|^2$ (Assumption 1) do **not** literally apply to token sequences; they require a separately-stated *continuous lift* (Soatto's "meaning space" quotient, or an embedding projection). | **High.** Dreamer RSSM (Hafner arXiv:2301.04104; Nature 2025 doi:10.1038/s41586-025-08744-2) is a continuous latent stochastic dynamical system with Lipschitz transition, symlog-bounded rewards, and trained-to-stability via KL-balance + free-bits. Khalil assumptions hold *literally* on the latent. TD-MPC2 (Hansen arXiv:2310.16828) inherits this. | **High.** Inherits B's rigor on L0. Forces the paper to state time-scale separation $\gamma_0 \gg \gamma_1$ explicitly as an Assumption (currently only sketched in Thm. 1's proof). LLM-as-L1 requires a stability statement only on slower parameter dynamics, not token dynamics. | **Medium.** Theorems remain valid as-stated but become *conditional*: "if Π satisfies Assumptions 1–3, then $\lambda_i > 0$ implies stability." The burden shifts to each application to demonstrate the assumptions. Closer to control-theory norm. |
| **Narrative coherence** | **High-but-fragile.** Matches the stated motivation ("autonomous AI agents as controllers of complex systems") and matches Life's `shell.rs` mapping (`docs/life-rcs-mapping.md`, L0 row). Fragile because Bhargava/Soatto are not cited in `references.bib` yet (Note 06 will confirm), and the surrounding prose does not acknowledge the continuous-lift gap. | **Medium.** Requires rewriting Sec. I from "agents as controllers" to "agents with learned models." Strong internal coherence — Dreamer/TD-MPC2/R2I provide a mature narrative arc ("learn a model, plan in latent, act with policy"). Loses the LLM-first framing that the Abstract emphasizes. | **Low-to-medium.** Coherent to a control-theory audience but requires additional exposition (two learned components, their interaction). Paper page budget tight. Proposition (triple equivalence) becomes level-dependent in a way not currently stated. | **High.** Casts the paper as "a framework that accepts any Π" — matches the existing unification table (`docs/framework-unification.md`) and the self-referential-closure claim (`docs/self-referential-closure.md`). Loses the "LLM agents" punchline. |
| **Publishable-venue fit** | Prompt-engineering + LLM venues (ACL, NeurIPS) accept; classical-control venues (L4DC, CDC, *Automatica*) push back on the continuous-state gap. Eslami & Yu themselves (arXiv:2603.10779) publish in a neuro-symbolic outlet, a precedent but a narrow one. | **L4DC, NeurIPS (Deep RL / WM track), ICLR.** Dreamer-V3 lives in *Nature*; R2I was ICLR 2024 Oral (arXiv:2403.04253); TD-MPC2 at ICLR 2024 (arXiv:2310.16828). An RCS paper that extends these to a multi-level hierarchy has a natural home. | Strong journal fit (IEEE TCNS, *Automatica*) but needs a longer format. Conference fit awkward unless the paper is split. | IEEE TCNS, IEEE TAC surveys, *Automatica*. Best fit for a framework paper that subsumes existing approaches. Lowest competition for novelty. |
| **Life implementation cost** | **Zero.** `shell.rs` Level 0 already matches. Cost is documentation only. | **Very high.** Requires a Rust implementation of a latent-dynamics model (nothing exists today in Life), training pipeline, replay buffer, Dreamer-like actor-critic. Autonomic (`crates/autonomic/`) would need restructuring because L1 would now consume a latent state, not an event stream. | **Highest.** Combines B's cost with retaining the current LLM Π₁ integration. Realistic only as a 3–6 month engineering project. | **Low.** Add trait bounds / typed controller interface; keep existing LLM-as-Π₀ as one instantiation; optionally stub out Dreamer-instantiation for an experiment. Aligns with existing `aios-protocol::Tool` / `Provider` trait pattern. |
| **Citation alignment** | Bhargava et al. arXiv:2310.04444; Soatto et al. arXiv:2305.18449; Nguyen et al. arXiv:2510.04309 (PID-Steering). *Weak for stability — all three papers establish reachability/controllability, not Lyapunov stability.* | Hafner et al. Nature 2025 / arXiv:2301.04104 (DreamerV3); Samsami et al. arXiv:2403.04253 (R2I); Hansen et al. arXiv:2310.16828 (TD-MPC2); LeCun 2022 JEPA arXiv:2306.02572. **Strong for stability-of-training and latent-Lipschitz claims.** | UniZero arXiv:2406.10667 (transformer + latent world-model + MCTS); Yang et al. arXiv:2411.08794 (evaluating LLMs as world-models); Hao et al. 2023 (RAP / Reasoning-via-Planning); Kong et al. arXiv:2406.05954 (RE-Control). | LiSeCo arXiv:2405.15454; RE-Control arXiv:2406.05954; PID-Steering arXiv:2510.04309; Pro2Guard arXiv:2508.00500; CBF-LLM arXiv:2408.15625 — **each instantiates one Π; the RCS paper catalogs them.** |
| **Falsifiability** | **Low.** "$\gamma_0 > 0$ for LLM Π₀" is not directly falsifiable; requires proxy measurements (token-level regret curves, steering success rates). Bhargava reports controllability success rates (~97% next-token reachable) but these are not stability. | **High.** Dreamer-style world models have *measured* prediction error at horizon $H$; this directly bounds the region-of-validity of stability claims (Hafner Nature 2025 Fig. 3). Failure mode: horizon expands, error grows, claim voided. Testable. | **High.** Inherits B's falsifiability plus: time-scale separation is testable by ablating the L1 update rate. | **Conditional.** Falsifiability pushed to each application paper. The framework itself makes only existence claims ("if these assumptions hold..."). |
| **Novelty claim preserved** | "First recursive stability budget for LLM agents" — intact if you defend the continuous-lift bridge. | "First recursive stability budget for deep-model-based RL" — intact but now in a more crowded arena (Dreamer, TD-MPC2, R2I all make related but non-recursive claims). | "First framework bridging learned world models and LLM policies under a recursive stability guarantee" — **strongest distinct novelty** but also the hardest to defend because it is two claims. | "First formalism unifying LLM-steering, world-model RL, classical CBF control, and governance under a single recursive template" — lower per-claim novelty but broader coverage. |

**Count of references per framing (summary row).**

| Framing | Primary refs cited above | Secondary refs (Sec. 5) |
|---|---:|---:|
| A | 3 (Bhargava 2023, Soatto 2023, Nguyen 2025) | 2 (Eslami 2026, RE-Control 2024) |
| B | 4 (Hafner 2023/2025, Samsami 2024, Hansen 2024, LeCun 2022) | 2 (Nature Dreamer 2025, Mineault 2024) |
| C | 4 (Pu 2024 UniZero, Yang 2024, Hao 2023 RAP, Kong 2024) | 2 (Vries 2023 on MuZero, Baltieri 2019) |
| D | 5 (LiSeCo 2024, RE-Control 2024, PID-Steering 2025, Pro2Guard 2025, CBF-LLM 2024) | 1 (Ashby 1952 as framework-for-framework) |

All four framings clear the "≥ 2 published references per framing" threshold stated in the task's verification criteria.

---

## 2. What Breaks in the Current Paper Under Each Framing

This section walks each theorem/proposition/definition in `rcs-definitions-ieee.tex` and classifies it as **survives**, **needs restatement**, or **becomes void** under each framing. "Current paper" = the IEEE version at HEAD.

### 2.1 Inventory of claims audited

| # | Label | Type | Statement (paraphrased) |
|---|---|---|---|
| C1 | `def:cs` | Definition | Controlled System = 7-tuple $(\mathcal{X}, \mathcal{Y}, \mathcal{U}, f, h, S, \Pi)$ |
| C2 | `def:rcs` | Definition | RCS = Controlled System with $\Pi$ itself an RCS; fixed point $\mathrm{RCS} \cong F(\mathrm{RCS})$ |
| C3 | `def:drive` | Definition | Homeostatic drive $D_i(x) = \|x - x^*_i\|^2$ |
| C4 | `prop:triple` | Proposition | Triple equivalence: $D_i$ is simultaneously Lyapunov, reward, free-energy bound |
| C5 | `ass:per-level` | Assumption | Per-level quadratic Lyapunov bound on continuous state |
| C6 | `ass:decay` | Assumption | Frozen decay with rate $\gamma_i$ |
| C7 | `ass:coupling` | Assumption | Lipschitz coupling bounds: adaptation $L_\theta \rho$, design $L_d \eta$, delay $\beta \bar\tau$, jumps $\nu$ |
| C8 | `def:budget` | Definition | Stability budget $\lambda_i = \gamma_i - L_\theta \rho_i - L_d \eta_i - \beta_i \bar\tau_i - (\ln \nu_i)/\tau_{a,i}$ |
| C9 | `thm:recursive` | Theorem | If all $\lambda_i > 0$ and time-scale-separated, composite state converges exponentially at $\omega = \min_i \lambda_i$ |
| C10 | `sec:egri` | Proposition (EGRI coupling) | Mutation magnitude bound $\eta_1 < (\gamma_1 - \text{other costs})/L_{d,1}$ |
| C11 | `sec:observer` | Proposition (fold as sufficient statistic) | If $\Pi_1(y_0,\ldots,y_k) = \Pi_1(\hat x_k)$ then fold is sufficient |
| C12 | `sec:fleet` | Equation | Cooperative resilience $J_{jl}$ formula from Chacon-Chamorro et al. |

### 2.2 Survives / restates / voids, by framing

Legend: ✅ survives unchanged · 🔁 needs restatement · ❌ becomes void

| Claim | A (LLM-Π₀) | B (WM-plant) | C (Hybrid) | D (Π-agnostic) |
|---|---|---|---|---|
| C1 `def:cs` | ✅ | ✅ | ✅ | ✅ |
| C2 `def:rcs` | ✅ | ✅ | 🔁 (must state the recursion may be non-uniform: L0 ≠ L1 in kind) | 🔁 (becomes "RCS is a template; instantiation-uniformity is optional") |
| C3 `def:drive` | ✅ | ✅ (drive now defined on latent $z$, not raw $x$) | ✅ | ✅ |
| C4 `prop:triple` | 🔁 (must state "under continuous lift of the LLM to meaning space per Soatto arXiv:2305.18449") | ✅ (drive on latent is cleanly Lyapunov and free-energy per Hafner's ELBO) | 🔁 (level-dependent: L0 triple is B's; L1 triple is A's with the caveat) | 🔁 (conditional on chosen Π) |
| C5 `ass:per-level` | ❌ *as literally stated* — LLM state is a shift-and-grow token sequence; no fixed-dim $\|x\|^2$. Must be restated as applying to a continuous projection $\phi: \text{LLM state} \to \mathbb{R}^n$. | ✅ | ✅ at L0; 🔁 at L1 | 🔁 (per instantiation) |
| C6 `ass:decay` | ❌ unless Bhargava's reachability is upgraded to a *contraction* result (it is not; Bhargava Thm. 1 is reachability, not contraction). Restate as "in the lifted metric $d_\phi$, the closed-loop LLM is contractive with rate $\gamma$." | ✅ (Dreamer's symlog-bounded reward + KL-balance implies bounded state drift per training step; contraction measurable) | ✅ at L0; 🔁 at L1 | 🔁 |
| C7 `ass:coupling` | 🔁 — the concept applies to any Π, but the numeric values in `parameters.toml` for L0 ($L_\theta=0.3$, $\rho=0.5$) are currently unjustified for an LLM Π₀. | ✅ (Dreamer exposes learning-rate, KL-scale, and replay-refresh rate; each maps to a coupling term) | ✅ | 🔁 |
| C8 `def:budget` | ✅ algebraically; 🔁 interpretationally (what physical quantity is $L_\theta \rho$ for a frozen-weights LLM? Must be tied to in-context parameter proxies.) | ✅ | ✅ | ✅ |
| C9 `thm:recursive` | ✅ *structurally* — the singular-perturbation proof sketch is Π-agnostic — but *inapplicable* without C5, C6 restatements. | ✅ | ✅ (but time-scale separation becomes an explicit assumption, not a throwaway clause in the proof sketch) | ✅ (with "Assumptions 1–3 hold for your Π" prefix) |
| C10 EGRI coupling | ✅ (Π structure does not enter) | ✅ | ✅ | ✅ |
| C11 fold-as-sufficient | 🔁 (fold is reasonable for structured token-streams but not proven for LLM activations; needs either restricted scope or a POMDP-style argument) | ✅ for structured latent; 🔁 if the world-model observer is itself learned (loses closed-form sufficiency) | 🔁 at both levels | 🔁 |
| C12 fleet $J_{jl}$ | ✅ | ✅ | ✅ | ✅ |

**Summary of breakage.**

- **Framing A** breaks Assumptions 1 and 2 *as literally written*. The rest of the paper — the stability budget, the recursive theorem, EGRI coupling, fleet extension — is structurally fine but algebraically uninterpretable until the continuous-lift bridge is stated. The paper currently has no such bridge.
- **Framing B** touches no theorem in the claim inventory but forces Sec. I–II rewrites, Sec. VI (Life implementation) rewrites, and a new subsection defining the latent world model. The math survives verbatim.
- **Framing C** forces restatements at `def:rcs` (non-uniform recursion) and at Prop. `prop:triple` and `sec:observer` (level-dependence) and is the framing that demands the most new prose.
- **Framing D** forces the weakest restatement — adding an "if Π satisfies Assumptions 1–3 then..." prefix to every theorem — but loses the concrete "LLM agents are stable" punchline.

---

## 3. Failure Modes Each Framing Inherits

Each framing brings its own class of objections that must be defended (or scope-limited away). This section lists the failure modes a reviewer or a future paper can attack.

### 3.1 Framing A — LLM-as-Π₀

1. **LLM non-identifiability.** The same prompt can produce different outputs across temperatures, seeds, tokenizer versions, and fine-tuning snapshots. The "system" is not a fixed map $f: \mathcal{X} \times \mathcal{U} \to \mathcal{X}$ but an ensemble indexed by sampling parameters. Bhargava (arXiv:2310.04444, Sec. 4) treats this by averaging over seeds; the RCS paper currently does not.
2. **Reachability ≠ stability.** Soatto et al. (arXiv:2305.18449, Thm. 3) prove *almost-sure reachability in meaning space*, not contraction. Bhargava (Sec. 5) measures controllability as top-$k$ next-token reachability success. Neither implies a decay rate $\gamma > 0$ in the Lyapunov sense.
3. **Shift-and-grow state dynamics.** Bhargava (Sec. 3.3) explicitly identifies this as a departure from classical control: the state dimension grows monotonically with time. Quadratic Lyapunov functions $\|x - x^*\|^2$ are not well-defined without a projection to a fixed-dim state.
4. **Frozen-weights vs continual-learning gap.** The coupling assumption `ass:coupling` includes an adaptation cost $L_\theta \rho$. For a *deployed* LLM this is essentially zero (weights do not change), so the term is either trivially satisfied or re-interpreted as "in-context learning rate" — which does not correspond to any trainable parameter.
5. **Mutual exclusion on input vs output tokens.** Bhargava (Sec. 3.4) notes that the LLM cannot simultaneously be acted on and observed at the same token position. This breaks the standard simultaneous observation-control assumption underlying Def. `def:cs`.

### 3.2 Framing B — World-Model-as-Plant

1. **Prediction-error horizon.** Dreamer and TD-MPC2 both have finite-horizon validity (Hafner arXiv:2301.04104 Sec. 6.2 "imagination horizon"). Beyond that horizon, rollouts diverge from reality. This sets a hard upper bound on the time-window over which any stability claim about the learned L0 is meaningful.
2. **LLM-as-world-model degrades on long-horizon decisions.** Yang et al. (arXiv:2411.08794, Table 2) show that using an LLM *as* the world model degrades rapidly on long-horizon decision tasks. If Framing B uses an LLM-derived world model rather than a Dreamer RSSM, it inherits this degradation.
3. **Sim-to-real gap.** A world-model-based RCS is only as safe as the world model. Mineault et al. (cited in Prop. `prop:triple` as `mineault2024neuroai`) emphasize that reward-saturation is the key safety property; a world model has no such bound by default.
4. **Training stability ≠ deployment stability.** DreamerV3 guarantees training stability via symlog and KL-balance; it does not guarantee deployment stability under distribution shift. A paper citing DreamerV3 stability for $\gamma > 0$ must distinguish these.
5. **Double-level drift.** If L0 is a learned world model that is continually updated, the "frozen decay" assumption (C6) fails at L0 unless the learning rate is explicitly part of $L_d \eta$.

### 3.3 Framing C — Hybrid

1. **Double failure surface.** Inherits every failure mode of A (for the LLM L1 component) and every failure mode of B (for the world-model L0 component).
2. **Interface non-continuity.** The latent state $z \in \mathbb{R}^d$ must be tokenized to feed the LLM at L1. Discretization breaks continuity of the control law; standard singular-perturbation proofs assume smoothness across levels (Theorem 1's proof sketch).
3. **Time-scale-separation cannot be merely stated.** Currently Thm. 1 says "with time-scale separation between levels" without defining it numerically. Under C this becomes a *measurable* and *required* property: the world-model rollout horizon must be shorter than the LLM planning horizon, and both must be shorter than EGRI's update interval. Violation is a concrete failure mode.
4. **UniZero-style entanglement.** Pu et al. (arXiv:2406.10667) document that transformer-based world models entangle latent state with history, violating the Markov property assumed by Lyapunov analysis. Framing C inherits this unless it uses an RSSM-style latent.
5. **Two trained components, one paper.** A hybrid framing compresses two substantial subsystems (learned WM, LLM policy) into a single paper, weakening the empirical evaluation of each.

### 3.4 Framing D — Controller-Agnostic

1. **Conditional theorems are weaker theorems.** A reviewer will ask: "You say if Π satisfies Assumptions 1–3 then stability. Does any Π in practice satisfy them?" If the answer is "see the appendix" the paper loses punch.
2. **Novelty dilution.** Each instantiation (Dreamer-Π, LLM-Π, PID-steering-Π, CBF-QP-Π) has its own published paper. The contribution becomes "we have a taxonomy" — intellectually honest but less rewarded in top conferences.
3. **Assumption satisfiability is the hard part.** The paper pushes the hard work (showing $\gamma > 0$ for *your* Π) to downstream applications. Historically this has been the crux of stability analysis; hiding it inside "Assumption 3" is accurate but anti-climactic.
4. **Loss of the LLM-first framing.** The Linear project name is "RCS — Recursive Controlled Systems Formalization" under an MAIA initiative. The implicit audience is AI-agent-focused. Framing D makes "LLM" one of four instantiations rather than the central example.
5. **Recursion claim weakens.** If L0 can be a Dreamer, L1 can be an LLM, L2 can be EGRI, and L3 can be governance rules — the claim $\mathrm{RCS} \cong F(\mathrm{RCS})$ is structural (all levels use the 7-tuple) but not uniform (they are different *kinds* of controllers). The "same formalism at every level" narrative weakens.

---

## 4. What Would Need to Be True for Each Framing to Be the Right Choice

Preconditions and open questions whose resolution would determine which framing fits the evidence. These are *questions*, not recommendations.

### 4.1 Framing A — LLM-as-Π₀

- **Q-A1:** Is there a published continuous-lift projection $\phi: \text{LLM state} \to \mathbb{R}^n$ under which the LLM becomes a Lipschitz-continuous dynamical system with a measurable contraction rate $\gamma$? Soatto's "meaning space" (arXiv:2305.18449, Sec. 3) is the closest candidate; does it satisfy `ass:decay` quantitatively?
- **Q-A2:** Can the RCS paper adopt Bhargava's "prompt length $k$" as a proxy for the control-magnitude bound, or does that break the coupling assumptions?
- **Q-A3:** For frozen-weight deployment, what is the physical referent of $L_\theta \rho$? Is it in-context adaptation rate, KV-cache drift, or zero?
- **Q-A4:** Do published reachability results (Bhargava ≥97% next-token reachability) carry any implication for *composite-system* stability at L1+ levels, or only at L0?

### 4.2 Framing B — World-Model-as-Plant

- **Q-B1:** For Life specifically: is there appetite to build a Rust Dreamer-V3 / TD-MPC2 port as L0? (Scope of the Life repo as of 2026-04 does not include this.)
- **Q-B2:** What is the imagination horizon we can honestly defend for the world model in the RCS application target (microgrid control, codebase editing)? Short horizons invalidate the "global stability" framing.
- **Q-B3:** Does the paper want to cite DreamerV3's *training* stability as a proxy for `ass:decay`, or require a *deployment* stability result that does not yet exist in the literature?
- **Q-B4:** If the world model is itself learned online, which term of the stability budget absorbs its learning rate? If we say "it's $L_d \eta_0$" then L0 and L1 both have design-adaptation cost, which complicates the current narrative.

### 4.3 Framing C — Hybrid

- **Q-C1:** Is the paper length budget compatible with introducing two substantial subsystems (learned WM + LLM policy)? If not, is a journal-length venue available?
- **Q-C2:** Can time-scale separation be stated *numerically* in the paper — e.g., "world-model rollout horizon ≤ 10 steps; LLM planning horizon ≤ 100 steps; EGRI update interval ≥ 10³ steps" — backed by Life measurements?
- **Q-C3:** For the LLM-at-L1 component, does the paper adopt a discrete-to-continuous smoothing technique (Gumbel-softmax, straight-through, or RE-Control's value-function gradient descent) to preserve the smoothness assumption in Theorem 1's proof?
- **Q-C4:** Is the Life implementation willing to adopt a UniZero-style or TD-MPC2-style hybrid stack as the canonical reference implementation?

### 4.4 Framing D — Controller-Agnostic

- **Q-D1:** Is the paper's target venue one that values framework papers (IEEE TCNS, *Automatica*, ACM Computing Surveys) or one that values applied-to-a-specific-problem papers (L4DC, NeurIPS, ICLR)? If the former, D fits; if the latter, it is an uphill fight.
- **Q-D2:** Do we have, for each instantiation (Dreamer-Π, LLM-Π, PID-steering-Π, CBF-QP-Π), a concrete statement of Assumptions 1–3 that can be checked? If three of four fail the check, D looks less attractive.
- **Q-D3:** If the recursion $\mathrm{RCS} \cong F(\mathrm{RCS})$ is only *structural* (same 7-tuple) rather than *uniform* (same kind of Π at each level), what load-bearing role does the recursion still play? Note 04 of this research batch is evaluating exactly this question; the answer there should feed back into D's viability.
- **Q-D4:** Does the paper want to keep the EGRI-as-L2 narrative intact? EGRI (Sec. VI of the paper) currently treats Π₂ as a mutation/promotion loop — Framing D does not force a change here, but it does make EGRI *just one possible* L2.

---

## 5. Reference Digest

Each reference cited in Secs. 1–4 is listed once with arXiv / DOI and a one-line relevance to the framing(s) that invoked it. Verdicts on existence and claim-support are the subject of Note 06 of this research batch; this note takes their existence and topicality as given.

- **Hafner et al., DreamerV3**, Nature 2025, doi:10.1038/s41586-025-08744-2; arXiv:2301.04104. Latent RSSM world model; training stability via symlog + KL-balance. Refs. for B, C.
- **Hafner et al., "Dream to Control"**, ICLR 2020, arXiv:1912.01603. Original Dreamer; latent imagination. Ref. for B.
- **Hansen et al., TD-MPC2**, ICLR 2024, arXiv:2310.16828. Scalable implicit (decoder-free) latent world model with MPPI planning. Ref. for B.
- **Samsami et al., R2I ("Recall to Imagine")**, ICLR 2024 Oral, arXiv:2403.04253. S4-augmented Dreamer for long-horizon memory tasks. Ref. for B.
- **LeCun, "A Path Towards Autonomous Machine Intelligence"**, OpenReview 2022; arXiv:2306.02572. H-JEPA hierarchical world model. Ref. for B.
- **Pu / UniZero**, 2024, arXiv:2406.10667. Transformer + latent world model + MCTS; bridges MuZero and LLM-policy planning. Ref. for C.
- **Yang et al., "Evaluating World Models with LLM for Decision Making"**, 2024, arXiv:2411.08794. Evidence that LLM-as-world-model degrades on long-horizon tasks. Ref. for C, failure mode 3.3.
- **Hao et al., RAP (Reasoning via Planning)**, EMNLP 2023. LLM as explicit transition model + tree search. Ref. for C.
- **Bhargava et al., "What's the Magic Word? A Control Theory of LLM Prompting"**, 2023, arXiv:2310.04444. Discrete stochastic dynamical system formalization of LLMs; reachability (not stability) results. Ref. for A.
- **Soatto et al., "Taming AI Bots: Controllability of Neural States"**, 2023, arXiv:2305.18449. Meaning-space controllability; almost-sure reachability. Ref. for A.
- **Nguyen et al., "Activation Steering with a Feedback Controller"** (PID-Steering), 2025, arXiv:2510.04309. Maps existing activation-steering methods to P-controllers; introduces PID controller at activation level. Ref. for A, D.
- **Kong et al., RE-Control**, NeurIPS 2024, arXiv:2406.05954. LLM-as-discrete-stochastic-dynamical-system; value-function-based gradient control at test time. Ref. for A, D.
- **Ben-Kish et al., LiSeCo ("Linearly Controlled Language Generation with Performative Guarantees")**, 2024, arXiv:2405.15454. Activation-space optimal-control projection as a shield-like mechanism for LLMs. Ref. for D.
- **Wang et al., Pro2Guard (ProbGuard)**, 2025, arXiv:2508.00500. Probabilistic runtime monitoring via DTMC-abstraction; PAC-correct guardrails. Ref. for D.
- **Miyaoka & Nakamura, CBF-LLM**, 2024, arXiv:2408.15625. Control-barrier-function-based safe decoding for LLMs. Ref. for D.
- **Eslami & Yu**, 2026 (cited in paper as `eslami2026control`), arXiv:2603.10779. Stability budget for a single agent; the RCS paper extends this recursively. Contextual ref.
- **Baltieri & Buckley**, 2019 (cited in paper as `baltieri2019pid`). PID-as-active-inference. Ref. for C relationship to Prop. triple.
- **Mineault et al., 2024** (cited in paper as `mineault2024neuroai`). NeuroAI-safety argument for bounded objectives. Ref. for B failure mode.
- **Ashby**, *Design for a Brain*, 1952. Ultrastability / requisite variety. Meta-reference for D.

---

## 6. What Would Change the Decision

This note commits to no recommendation. The following is a list of *empirical* and *scoping* questions whose answers would change the balance among A, B, C, D. Each is a decision-relevant open question the user (or Wave 2 synthesis) must resolve before committing.

1. **Is the paper a control-theory paper, an AI-agents paper, or a framework paper?** This is a venue-shaping question with direct consequences for which framing fits. IEEE TCNS → D. NeurIPS RL track → B. A specialized LLM-agents workshop → A. A hybrid control+ML venue (L4DC) → B or C.
2. **Does the Life repo have capacity to build a Dreamer/TD-MPC2 component in the next six months?** If no → A or D. If yes → B or C opens up.
3. **Does Note 04 (recursion load-bearing analysis) conclude that $\mathrm{RCS} \cong F(\mathrm{RCS})$ is used in any proof?** If yes → A/B/C (uniform recursion) wins over D. If no → D becomes structurally cheaper.
4. **Does Note 01 (paper defensibility audit) conclude that Assumptions 1–3 are defensible as-written for the LLM case?** If yes → A survives. If no → the continuous-lift bridge is non-optional and A becomes a partial rewrite regardless.
5. **Does Note 05 (ESO/ADRC-around-LLM) find any value-add?** If yes, that is evidence *for* Framing A or D (LLM as the controlled thing). If no, that is evidence *for* Framing B (the LLM should be above the plant, not the plant itself).
6. **Does Note 06 (literature grounding) confirm that Bhargava and Soatto are the right citations for Assumption 1's continuous-state claim?** If their contribution is reachability-only, Framing A needs a different citation anchor (Kong / Nguyen 2025 PID-Steering might be closer to "stability" than "controllability").
7. **Is there a target application where world-model rigor is required (safety-critical microgrid control), vs an application where LLM-agent rigor is sufficient (codebase editing)?** Different applications pick different framings.
8. **Do we want the novelty statement to be "first recursive stability budget for AI agents" or "first unified framework for recursive controlled systems"?** The former favors A/B. The latter favors D.
9. **Is the paper committed to a single canonical instantiation (the `parameters.toml` numeric values for L0–L3), or can it tolerate a per-instantiation parameter table?** The former favors A/B/C. The latter favors D.
10. **Is the LLM's state the *token stream*, the *activation stream*, or the *meaning space quotient*?** Framing A's defensibility depends directly on this. Framing D absorbs the question into "your Π, your state-space definition."

These questions are unresolved. Answers are the subject of Wave 2 synthesis (`00-synthesis-decision-memo.md`). This note makes no ranking.
