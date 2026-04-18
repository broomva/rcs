---
title: "ESO / ADRC Around an LLM — Genuine Value vs Existing Closed-Loop LLM Control"
tags:
  - rcs
  - research-note
  - control-theory
  - eso
  - adrc
  - llm-control
aliases:
  - ESO-LLM Value Analysis
  - Research Note 05
created: "2026-04-17"
updated: "2026-04-17"
status: draft
linear: BRO-700
related:
  - "[[RCS Index]]"
  - "[[framework-unification]]"
  - "[[self-referential-closure]]"
  - Paper 3 — Observers (p3-observers)
---

# Research Note 05 — ESO / ADRC Around an LLM: Genuine Value vs Existing Closed-Loop LLM Control

**Purpose.** Decide whether wrapping an Extended State Observer (ESO) / Active Disturbance Rejection Controller (ADRC) around a large language model is a genuine research contribution or an incremental luxury. We audit four published closed-loop LLM control approaches, check ADRC's three structural prerequisites against the LLM-as-plant reality, and conclude with a verdict plus an alternative (stronger) framing.

**TL;DR.** ESO-as-controller around a raw LLM likely cannot satisfy ADRC's prerequisites (input-gain sign, bounded disturbance derivative, monotone action effect) on the natural action space. It becomes defensible only on a structured, low-gain action vocabulary — and even then its gains over PID steering and RE-Control are incremental. The stronger framing is **ESO-as-anomaly-observer**: use the extended-state estimate as a residual-based drift signal that feeds the autonomic / homeostatic layer (Level `Lᵢ₊₁`), without closing the control loop on the LLM itself. That is a real RCS contribution; ESO-as-controller on a raw LLM is not.

---

## 1. Method-Coverage Matrix

Five approaches, each a closed-loop controller (or near-controller) around an LLM. We catalog the failure mode each targets, the prerequisite it needs, its cost, and the published evidence.

| # | Approach | Failure mode addressed | Key assumption | Cost | Published evidence |
|---|---|---|---|---|---|
| 1 | **PID activation steering** (Nguyen et al. 2025) | Open-loop steering vectors over- or under-shoot target concept strength; drift as context grows | A single steering direction `v` exists s.t. concept-probe activation `p = vᵀa` is a smooth monotone function of injection magnitude in the linear regime | One probe forward per layer, per token; tuning 3 PID gains | Demonstrated on sentiment / refusal / topic tracking; closed-loop error reduced vs open-loop steering |
| 2 | **LiSeCo** — linear-constraint projection (Cheng & Amo Alonso 2024) | Activations drift into a pre-labeled "unsafe" linear half-space | Unsafe concepts are separable by a pre-trained linear classifier `wᵀa ≤ c`; projection preserves task utility locally | One projection per forward / per layer; offline classifier training | Shown to suppress refusal violations and toxicity with bounded perplexity cost |
| 3 | **ProbGuard / Pro²Guard** (Wang et al. 2026) | Unsafe outputs that appear with non-negligible probability but aren't trivially flagged by one-shot classifiers | A calibrated probabilistic monitor generalizes to held-out unsafe cases; threshold `P(unsafe)` is known | Monitor forward per step; abstention triggers a fallback policy (retry, refuse, hand-off) | Reported monitoring AUROC and escalation savings vs rule-based guards |
| 4 | **RE-Control** — residual / value-function hidden-state control (Liu, Trager, Achille, Soatto) | Output distribution is misaligned with a latent reward (harmlessness, helpfulness, factuality) | A learned value function `V(h)` on hidden states is differentiable and its gradient in `h`-space reliably increases the scalar reward | Training a value function; per-step gradient step on hidden states | Empirical improvements on harmlessness / helpfulness benchmarks over RLHF at comparable compute |
| 5 | **ESO / ADRC around the LLM** (proposed) | Time-varying, unmodeled "disturbance" — context contamination, distribution shift, adversarial injection — that drifts output from the intended trajectory | (i) input-gain sign `sign(b₀)` known; (ii) lumped disturbance has bounded derivative `‖ḟ‖ ≤ M`; (iii) control action has locally monotone effect on output; (iv) a scalar output `y(t)` of practical interest exists and is observable | One ESO state update per step + ADRC law; no retraining of the LLM | **None on LLMs.** Guo & Zhao 2016 proved nonlinear ADRC stability for smooth plants with known `b₀` sign; no equivalent result exists for LLMs |

### What each method does *not* address

- **PID steering** — has no internal model of the disturbance; if context drift shifts the steering direction itself, PID gains need re-tuning. Single scalar target only.
- **LiSeCo** — silent on *why* activations drifted; once projected, there is no residual signal to the metacontroller.
- **ProbGuard** — purely detective; does not attempt to correct in-flight, only abstain.
- **RE-Control** — adaptive in hidden-state geometry but requires a *trained* `V`; new disturbance classes need new training data.

None of the four provides an **explicit, online, model-free estimate of an aggregate time-varying disturbance acting on the LLM's observable output**. That niche is where ESO would live.

---

## 2. ADRC Structural-Requirements Check Against LLM-as-Plant

ADRC's stability proofs (Guo & Zhao 2016 and predecessors) rest on three structural facts about the plant. We audit each against an LLM.

### 2.1 Known input-gain sign `sign(b₀)`

**Natural LLM action space (prompt tokens, arbitrary steering vectors): NO.**

The "input-gain" is the partial derivative of the observable output (e.g., sentiment probe, refusal probability, a task score) with respect to the control action, evaluated around the nominal operating point. For a raw LLM, the control is high-dimensional (`≥ d_model`) and the output is task-specific. Empirically, steering-vector experiments show that the same direction can increase a probe at low magnitude, saturate at moderate magnitude, and *flip* the probe at high magnitude as the model begins to produce degenerate text. The sign of `b₀` therefore depends on both magnitude and context — it is not a fixed global property of the plant, which is what ADRC requires.

**Structured action vocabulary (single pre-validated direction in a known linear regime, bounded magnitude, one pre-chosen probe): CONDITIONAL yes.**

Within the linear regime identified by PID-steering work, a single chosen direction `v` against a single chosen probe behaves monotonically and the sign is known by construction. This is a strong restriction on the action space — effectively the same restriction PID steering already operates under — and any gain from ESO over PID in this regime is incremental.

### 2.2 Bounded disturbance derivative `‖ḟ‖ ≤ M`

**Natural LLM action space: NO.**

The "disturbance" in an ADRC framing aggregates everything that is not the nominal model: context contamination, instruction-following drift, jailbreak prefixes, tool-use interference, distribution shift. A single adversarial token can shift behavior discontinuously — an arbitrary bound `M` chosen ahead of deployment will be violated by any sufficiently engineered prompt. Unlike a mechanical plant, the LLM's disturbance spectrum is not bandwidth-limited; it is limited only by the adversary's vocabulary.

**Structured / rate-limited input stream (e.g., only system-prompt edits at a slow cadence, or activation-patch updates at a bounded rate): CONDITIONAL yes.**

If the effective input channel is rate-limited by the `Lᵢ₊₁` controller — for example, the autonomic homeostasis layer is the only entity allowed to change gating profiles and does so on a slow timescale — then the disturbance seen at `Lᵢ` *can* have a useful bound. This is exactly the multi-rate separation the RCS stability budget already exploits.

### 2.3 Monotone action effect

**Natural LLM action space: NO.**

This is the most-often violated assumption in practice. Activation steering exhibits the classic "over-steering" failure: past an optimal magnitude, output quality collapses — a non-monotone, often U-shaped curve. Temperature, top-p, and guidance scale show analogous effects. ADRC's control law implicitly assumes that once `u` is nudged in the direction `sign(b₀)`, `y` moves monotonically; in the LLM case the curve bends back.

**Structured action vocabulary with bounded magnitude: CONDITIONAL yes.**

If the action is constrained to a sub-interval in which the output is demonstrably monotone (identified, e.g., by offline probing), ADRC's proof can go through. That sub-interval must be validated per deployment; once the controller pushes outside it, guarantees vanish. This is a non-trivial safety obligation that none of the four baselines carry, and it is itself a new attack surface.

### Summary of structural checks

| Requirement | Natural action space | Structured action vocabulary | Note |
|---|---|---|---|
| `sign(b₀)` known | NO | Conditional yes | Sign depends on magnitude / context on the natural space |
| `‖ḟ‖` bounded | NO | Conditional yes (rate-limited upstream) | Adversarial prompts break any fixed `M` |
| Monotone action effect | NO | Conditional yes (bounded sub-interval) | Classic over-steering failure |

All three conditional-yes cases require the controller upstream to enforce the restriction. In RCS terms, ADRC around the LLM works only when `Lᵢ₊₁` has *already* shrunk `U` to a well-behaved sub-region — at which point PID steering also works, and ESO's marginal value shrinks.

---

## 3. Gap Analysis — What the Four Baselines Leave Uncovered

Laying the failure-mode vocabulary side-by-side:

| Failure mode | PID | LiSeCo | ProbGuard | RE-Control | Uncovered? |
|---|---|---|---|---|---|
| Scalar target tracking | ✅ | — | — | Partial | No |
| Linear-subspace safety containment | — | ✅ | — | — | No |
| Probabilistic unsafe-output abstention | — | — | ✅ | — | No |
| Latent-reward alignment | Partial | — | — | ✅ | No |
| **Online, model-free estimate of an aggregate time-varying disturbance** | — | — | — | — | **Yes** |
| **Residual-based drift signal for the metacontroller (`Lᵢ₊₁`)** | — | — | Partial (binary flag) | — | **Mostly yes** |
| **Adaptation to disturbance classes absent from training data** | Partial (via retune) | — | — | — | **Yes** |

The three "yes" rows are the ESO-shaped gap. They are real. The question is whether ESO-as-controller is the right tool to fill them.

### Why ESO-as-controller doesn't cleanly fill the gap

The gap is about **estimation and signal quality**, not about **actuation**. The four baselines already actuate in well-chosen ways (PID on a probe, LiSeCo via projection, RE-Control via hidden-state gradient). ADRC's distinctive claim — "cancel the disturbance by feeding `-f̂/b₀` into `u`" — requires `b₀` and monotonicity (§2.1, §2.3) that the LLM plant does not provide.

If the gap is estimation, ESO *can* still deliver its estimate `f̂` without the cancellation law. That estimate is a residual-based drift signal — an anomaly detector with a control-theoretic pedigree. Which is where the alternative framing below pays off.

---

## 4. Verdict

**(b) Incremental luxury on the natural action space, with one qualification: in the restricted regime where ADRC prerequisites hold (structured action vocabulary, rate-limited input, bounded-magnitude direction, single probe), ESO-around-LLM is defensible — but its incremental value over PID steering is marginal, because PID already operates in that regime.**

Equivalently: on the natural LLM action space, verdict is **(c) unlikely to work without structural LLM changes**, because all three ADRC structural requirements fail. The "structural LLM change" is essentially a safety shield `S` that restricts `U` to a monotone sub-region — which is RCS's job, not ESO's.

Justification in one line each:
- **PID steering** already handles the "restricted regime" case with lower mathematical overhead.
- **LiSeCo + ProbGuard + RE-Control** already cover the safety-containment, detection, and latent-reward failure modes.
- **ADRC's distinctive cancellation term** needs `sign(b₀)` and monotonicity the LLM does not supply.
- **ESO's distinctive estimation term** is valuable, but it does not require ADRC's actuation law. See §5.

---

## 5. Alternative Framing — ESO-as-Anomaly-Observer (the Defensible Version)

A stronger paper, and the one that fits the RCS program, frames ESO purely as an **observer**, never as a controller. The extended state estimate `f̂(t)` becomes a residual-based drift signal consumed by `Lᵢ₊₁` (the autonomic / homeostasis layer), which *is* a controller with an appropriate, low-bandwidth action vocabulary (switch gating profiles, raise refusal probability, hand-off to a safer model, trigger a restart).

### Why this framing avoids every ADRC failure

| ADRC failure (§2) | Why it doesn't apply to ESO-as-observer |
|---|---|
| `sign(b₀)` unknown | No cancellation law means no dependence on `b₀`. The observer is driven only by the output residual `y - ŷ`, not by control inversion |
| Unbounded `‖ḟ‖` | An observer with unbounded disturbance derivative loses convergence rate but still yields a usable *estimate of the current disturbance level* — which is exactly the signal the metacontroller needs. Detection does not require the observer's error dynamics to be asymptotically zero; it requires that `‖f̂‖` crosses a threshold when something abnormal happens |
| Non-monotone action effect | The observer does not act. It is a passive estimator sitting in parallel to the LLM |

### Why this is stronger than ProbGuard

ProbGuard is a learned binary monitor. ESO-as-observer is:
1. **Model-based, not learned** — no training data needed for unseen disturbance classes; the observer generalizes via its state-space structure, not via interpolation. This is where the "adaptation to novel disturbance classes" row in §3 is actually filled.
2. **Quantitative, not binary** — `f̂(t)` is a continuous magnitude that the metacontroller can use for graded responses (soft refusal at `‖f̂‖ > θ₁`, hand-off at `‖f̂‖ > θ₂`), rather than a flip.
3. **Control-theoretically grounded** — innovation-based fault detection has decades of aerospace / process-control evidence. Lyapunov bounds on observer error translate directly into detection-latency guarantees (an `Lᵢ₊₁` stability-budget term), which ProbGuard cannot express.

### Concrete RCS payoff

Within the RCS formalism, this maps as:

- **`Lᵢ`** = the raw LLM, with `Uᵢ` = output tokens, `Yᵢ` = observable scalar of interest (probe activation, task score, or a bounded functional).
- **Observer** sits beside `Lᵢ`, producing `f̂(t)` as an additional observation `yₘ` at `Lᵢ₊₁`.
- **`Lᵢ₊₁`** = autonomic layer, with `Uᵢ₊₁` restricted to safe, bounded, rate-limited actions (gating profile, model swap, refusal bias). These actions *do* satisfy ADRC-style prerequisites, so a standard controller can close the outer loop.
- **Stability budget** is cleanly additive because the observer's detection latency is a scalar, whereas closing ADRC around `Lᵢ` would couple observer and actuator error through the ill-behaved `b₀`.

### The one-sentence paper

*"We do not wrap ADRC around the LLM — we instrument it with an ESO that exports a time-varying disturbance estimate into the metacontroller's observation vector. Closing the loop happens at `Lᵢ₊₁`, where the action space is well-behaved. This preserves ADRC's key idea — that a lumped disturbance is useful even when the plant model is terrible — without inheriting ADRC's structural prerequisites on the plant."*

---

## 6. Loose Ends / Things To Validate Before Writing Paper 3

1. **Does the observer gain schedule survive when the "plant" is a function sampled stochastically (an LLM sampling token-by-token)?** Guo & Zhao 2016 assume continuous-time smooth plants; we need a discrete-time, stochastic analogue with an analytic convergence rate in expectation. If this is hopeless, the "control-theoretic pedigree" argument in §5 weakens — the observer would be one more heuristic.
2. **What is the right `y(t)` for an LLM observer?** Candidate options: (a) a probe-layer activation norm, (b) a calibrated output-level scalar (e.g., refusal probability), (c) a self-report signal from a critic model. Option (c) loops us back to ProbGuard territory.
3. **Comparison to Kalman / extended Kalman** — ESO is one of several observer families. A proper paper must justify *why ESO specifically*, not "just" a Kalman filter with a disturbance state. The likely answer is that ESO tolerates a worse nominal model than EKF does, which fits the LLM "we barely have a plant model at all" setting — but this claim needs a clear empirical or analytic comparison.
4. **Does the autonomic layer already have the action bandwidth to consume `f̂`?** In the Life Agent OS, gating profiles flip at seconds-to-minutes cadence. If `f̂` varies per-token, there is a rate mismatch that the stability-budget math must absorb.

---

## References (for future BibTeX entries in `latex/references.bib`)

- Nguyen, C., et al. (2025). *Activation Steering with a Feedback Controller.*
- Cheng, M., & Amo Alonso, C. (2024). *LiSeCo: Linear Safety Constraint Enforcement via Activation Projection.*
- Wang, X., et al. (2026). *Pro²Guard: Probabilistic Runtime Monitoring for LLM Safety.* (also referenced as *ProbGuard*)
- Liu, Y., Trager, M., Achille, A., Soatto, S. *RE-Control: Value-Function Control of LLM Hidden States.*
- Guo, B.-Z., & Zhao, Z.-L. (2016). *Active Disturbance Rejection Control for Nonlinear Systems: An Introduction.* Wiley.
- Eslami, S., & Yu, X. (2026). *A Control-Theoretic Account of Agentic LLM Systems.* arXiv:2603.10779.

---

## Changelog

- **2026-04-17** — v0.1 initial draft (Carlos Escobar + Analyst agent). Verdict (b) with the (c) qualification on the natural action space; alternative framing to ESO-as-observer recommended for Paper 3.
