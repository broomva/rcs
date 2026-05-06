---
title: "Paper 5 — Theorem Protocol (Online JEPA Composite Stability)"
tags:
  - rcs
  - paper
  - protocol
  - theorem
  - jepa
  - stability
aliases:
  - P5-PROTOCOL
created: "2026-05-05"
updated: "2026-05-05"
status: scaffold
related:
  - "[[p5-online-jepa-stability/README]]"
  - "[[p0-foundations]]"
  - "[[2026-05-05-jepa-as-substrate-design]]"
  - "[[jepa-as-substrate]]"
---

# Paper 5 — Theorem Protocol: Online JEPA Composite Stability

This document is the theoretical equivalent of Paper 1's `PROTOCOL.md`. Paper 1
specifies the empirical-capture contract; this document specifies the
**proof-development contract** — the locked theorem statement, the assumptions
to discharge, the proof skeleton, and the sub-results each leaf ticket
(BRO-989..993) must prove.

> **Status:** scaffold. The theorem statement and assumptions are locked
> verbatim from the JEPA-as-substrate research-program spec
> (`docs/superpowers/specs/2026-05-05-jepa-as-substrate-design.md` §4.4).
> Each sub-result is `TBC-T*` until the corresponding ticket lands.

---

## 1. Locked theorem statement

**Theorem (Online JEPA Composite Stability — Generalized).** Let $\Sigma$ be
an RCS instantiated with:

- L0 head $H \in \{\text{LLM}, \text{world-model}, \text{state-space}, \text{hybrid}, \text{behavior-cloning}\}$;
- L1 controller $\pi_1 = \mathrm{L1ForwardRollout}(s_\theta, P_\varphi, z_{\text{target}})$;
- JEPA substrate $(s_\theta, P_\varphi, s'_\theta)$ with Q3 online updates;
- Stability monitor and canary gate as specified in spec §4.3.

Suppose:

| Assumption | Statement | Discharged by |
| ---------- | --------- | ------------- |
| **(H8a)** Encoder Lipschitz       | $\|s_\theta(x) - s_\theta(x')\| \le L_\theta\,\|x - x'\|$                                  | Empirical (§4) — frozen sentence-transformer + small fusion head |
| **(H8b)** Predictor Lipschitz     | $\|P_\varphi(z, a) - P_\varphi(z', a)\| \le L_P\,\|z - z'\|$                               | Empirical (§4) — MLP predictor with bounded weights              |
| **(H8c)** Deployment lag          | weights update every $\Delta \ge \Delta_{\min}$ steps                                       | Architectural — substrate `deploy()` interval                     |
| **(H8d)** KL-bounded drift        | $\mu \ge \mu_{\min} \;\Longrightarrow\; \mathrm{KL}\!\left[s_\theta(t+\Delta) \,\|\, s_{\theta_{\text{anchor}}}\right] \le \varepsilon(\mu)$ | **T2** (Lemma; this paper) |
| **(H8e)** Stability monitor       | $\hat\lambda < \lambda_{\text{freeze}}$ for $K$ steps $\Longrightarrow$ rollback             | Architectural — `StabilityCircuitBreaker` pattern                 |
| **(H9)** Head Lipschitz emission  | $\|\varphi_H(\text{payload}) - \varphi_H(\text{payload}')\| \le L_H\,\|\text{payload} - \text{payload}'\|$ | **T3** (Definition + cross-head Theorem; this paper)            |

**Then** the composite stability budget at level $k$ satisfies:

$$
\lambda_{\text{composite}}^{(k)}
\;=\;
\underbrace{\gamma_k}_{\text{frozen-decay (P0)}}
- \underbrace{L_\theta\,\rho_k}_{\text{adaptation (P0)}}
- \underbrace{L_d\,\eta_k}_{\text{design (P0)}}
- \underbrace{\beta_k\,\bar\tau_k}_{\text{delay (P0)}}
- \underbrace{L_{o\theta}(\Delta, \mu)}_{\text{online encoder (\textbf{NEW})}}
- \underbrace{L_H\,\kappa_k}_{\text{head (\textbf{NEW})}}
- \underbrace{\frac{\ln \nu_k}{\tau_a}}_{\text{jump (P0)}}
\;>\; 0.
$$

Two new terms vs Paper 0:

- $L_{o\theta}(\Delta, \mu)$ — **online encoder cost**. Captures latent
  drift between canary deployments. Closed form derived by extending Borkar
  (2008) Ch. 6 (two-time-scale stochastic approximation) to the
  deployment-lag setting. Decreasing in $\Delta$; increasing in $1/\mu$.
  **Vanishes ($\to 0$) as $\Delta \to \infty$** (frozen substrate; Q1+Q2
  case).
- $L_H\,\kappa_k$ — **head cost**. Captures substrate sensitivity to
  head-specific payload variations. With $L_H \le 1$ (head non-amplifying),
  the head cost is **bounded by $\kappa_k$** ($L_H \kappa_k \le \kappa_k$),
  meaning the head does not amplify per-level payload variance; with
  $L_H > 1$ the head amplifies it. The term **vanishes only when no L0
  head is engaged at level $k$** (i.e., $\kappa_k = 0$, the Paper 0
  setting). Penalizes heads whose payloads vary wildly (e.g.,
  poorly-prompted LLM at temperature 1.0).

The theorem **reduces to Paper 0's Theorem VI** in the Paper 0 regime
$(\Delta \to \infty,\;\kappa_k = 0)$: the encoder cost vanishes
asymptotically, the head cost is identically zero (no head engaged at
level $k$ in P0's formalism), and the residual bound is exactly P0's
Theorem VI. This is the formal sense in which Paper 5 is *additive* to
Paper 0: the new terms are zero in the regime Paper 0 covers, and the
bound is strictly tighter than Paper 0 in any regime where they are not.
Under an engaged head with $L_H \le 1$, Paper 5's bound is non-trivial
(strictly tighter than P0) but the head cost is at worst $\kappa_k$ —
the level-$k$ head-payload variance proxy is exposed as the load-bearing
quantity to bound empirically.

---

## 2. Proof skeleton

The proof is a five-step argument. Each step is a sub-result with its own
ticket.

### Step 1 — Lyapunov decomposition

Decompose the level-$k$ Lyapunov function into a stable component (the P0
quantity) and a drift component induced by online substrate updates:

$$
V_k(x) \;=\; V_k^{\text{stable}}(x) \;+\; V_k^{\text{drift}}(x).
$$

$V_k^{\text{stable}}$ is the standard P0 Lyapunov function from
`papers/p0-foundations/main.tex` §V. $V_k^{\text{drift}}$ is new and
captures the contribution of latent-state drift between canary deployments.

> **Status:** straightforward decomposition; no new technical content.
> Belongs to **T4** (full writeup).

### Step 2 — Bound $V_k^{\text{drift}}$ via (H8c) + (H8d)

*Lemma (Discrete-deployment two-time-scale convergence).* Under (H8c)
deployment lag $\Delta$ and (H8d) KL-bounded drift $\mu$,

$$
\|s_\theta(t + \Delta) - s_\theta(t)\| \;\le\; \varepsilon(\Delta, \mu)
$$

for an explicit $\varepsilon$ that is decreasing in $\Delta$ and increasing
in $1/\mu$.

This **extends Borkar (2008) Ch. 6's two-time-scale stochastic-approximation
result to discrete deployment events** (rather than continuous-time slow
flow). The key technical move is replacing Borkar's continuous slow ODE
with a step-function update that fires every $\Delta$ trainer steps and is
KL-anchored to a frozen reference $s_{\theta_{\text{anchor}}}$.

> **Status: TBC-T1** (BRO-989). One week of theory work. References:
> Borkar (2008) Ch. 6; Tsitsiklis & Van Roy (1997) for the discounted-MDP
> two-time-scale bound; Konda & Tsitsiklis (2003) for actor-critic
> two-time-scale convergence (the closest precedent for discrete updates).

### Step 3 — Apply (H8a)–(H8b) to bound predictor residual

By (H8a) encoder Lipschitz and (H8b) predictor Lipschitz, under bounded
encoder drift,

$$
\|P_\varphi(z, a) - \hat z_{\text{target}}\|
\;\le\;
L_P \cdot \varepsilon(\Delta, \mu) + \text{base}_{\text{err}}.
$$

> **Status:** mechanical; uses standard Lipschitz composition. Belongs
> to **T4** (full writeup).

### Step 4 — Apply (H9) for head-kind generalization

*Theorem (Head-Lipschitz cross-generalization).* If $\varphi_H$ satisfies
(H9) with constant $L_H$, then encoder features under any head $H$ are
head-Lipschitz with composed constant $L_\theta \cdot L_H$. Substituting
into Step 3 yields a head-aware predictor bound.

> **Status: TBC-T3** (BRO-991). Three days. Includes the cross-head
> formalization that Q4 multi-head A/B (BRO-952) consumes.

### Step 5 — Sum bounds; require P0 exponential-decay condition

Summing Steps 1–4 and substituting into Paper 0's exponential-decay
inequality yields the seven-term bound stated in §1. The result is the
formal definition of $L_{o\theta}(\Delta, \mu)$:

$$
L_{o\theta}(\Delta, \mu) \;\equiv\; L_P \cdot \varepsilon(\Delta, \mu) \cdot c(P_0\text{-constants}),
$$

where $c$ is a level-$k$-dependent constant absorbing P0's standing
hypotheses (H1)–(H7). Note $L_{o\theta} \to 0$ as $\Delta \to \infty$
because $\varepsilon$ does. The reduction to P0 exactly requires
additionally that no L0 head is engaged at level $k$
($\kappa_k = 0$), making the head cost $L_H \kappa_k = 0$ identically;
under those two conditions the seven-term bound collapses to P0's
five-term bound.

> **Status: TBC-T4** (BRO-992). Two weeks. The full proof is the
> integrated writeup; T1–T3 supply the load-bearing lemmas.

---

## 3. Sub-task mapping (Linear)

The five leaf tickets under BRO-955 each prove a specific sub-result:

| Ticket    | Sub-result                                                   | Status  | Estimate | Dependencies                        |
| --------- | ------------------------------------------------------------ | ------- | -------- | ----------------------------------- |
| BRO-989   | **T1** — Borkar 2008 extension to discrete deployment (Step 2 lemma) | Backlog | 1w       | none (load-bearing for T2, T4)      |
| BRO-990   | **T2** — KL-bound lemma + variational-inference citation (H8d) | Backlog | 3d       | T1 informs constant tightness       |
| BRO-991   | **T3** — (H9) head-Lipschitz formalization + cross-head theorem | Backlog | 3d       | independent of T1/T2                |
| BRO-992   | **T4** — Full proof writeup (5-step from §2 expanded)         | Backlog | 2w       | T1, T2, T3                          |
| BRO-993   | **T5** — Paper 5 LaTeX draft + experimental figures            | Backlog | 1w       | T4 + Q3 substrate measurements (BRO-983, the constants table) |

Critical path: T1 → T2 → T4 → T5 (~5 weeks). T3 runs in parallel with T1
+ T2 (independent assumption). Q3 substrate measurements (constants table)
must be in hand for T5's empirical figures, so T5 cannot land before
**Wave 3** of the JEPA-as-substrate plan (~weeks 8–12).

The scaffold this document accompanies (paper directory + Makefile targets +
this protocol document) is the **T0** entry-point — it is not a leaf
ticket; it is the prerequisite for any of T1–T5 to land.

---

## 4. Empirical-constants estimation (cross-reference)

The theorem makes seven empirical predictions. Each constant is
**measurable and CI-gated**. The protocol for measurement lives in spec
§4.5 and will be implemented under a Q3 ticket (BRO-983):

```python
# scripts/measure_constants.py  -- Q3 deliverable
def measure_all(substrate, head, holdout_data) -> dict:
    return {
        "L_theta":   measure_lipschitz(substrate.encode,  holdout_data),
        "L_P":       measure_lipschitz(substrate.predict, holdout_data),
        "L_H":       measure_head_lipschitz(head,         holdout_data),
        "delta":     substrate.deployment_interval,
        "mu":        substrate.kl_coefficient,
        "L_otheta":  measure_drift(substrate, holdout_data),
        "lambda_composite_lower_bound": compute_lambda_composite(...),
    }
```

| Constant | Measurement                                                          | Acceptable range            |
| -------- | -------------------------------------------------------------------- | --------------------------- |
| $L_\theta$         | Sample $N=1000$ $(x, x')$ pairs; max ratio $\|s(x)-s(x')\|/\|x-x'\|$ | 1.0 – 3.0                   |
| $L_P$              | Same in latent space                                                  | 0.8 – 1.2                   |
| $L_H$              | Per-head; payload-pair sampling                                       | per-head table (spec §4.4)  |
| $\Delta$           | Set explicitly; default $\Delta = 100$ trainer steps                  | $\ge \Delta_{\min} = 50$    |
| $\mu$              | Set explicitly; tune against training stability                       | 0.01 – 0.1                  |
| $L_{o\theta}$      | Empirical KL drift between deployments                                | $< 0.05$                    |
| $\lambda_{\text{composite}}$ (lower bound) | Computed from above; **CI-gated $> 0$**                  | **must be $> 0$**           |

CI gates a Q3 deployment on $\lambda_{\text{composite}}^{\text{lower}} > 0$.
**Mathematical proof of stability before any production rollout.** If a
future change violates the bound, CI fails — the system never sees an
unstable substrate.

---

## 5. Verification path

The proof is a **hand-written argument**. No Lean/Coq formalization is
planned for the initial paper. If a future trigger fires (cf.
`papers/p5-categorical-foundations/SCOPE.md` §6 for the formalization
trigger framework), a Lean 4 mechanization of Steps 1–5 would be a natural
follow-on artifact, but it is explicitly out-of-scope here.

Internal consistency of the hand-written proof is checked by:

1. **Self-citation.** Every numbered constant ($L_\theta$, $L_P$,
   $\Delta$, $\mu$, $L_{o\theta}$, $L_H$, $\kappa_k$) appears in
   §1, §2, §4, and the LaTeX body, with identical names.
2. **Reduction-to-P0 sanity check.** Setting $\Delta \to \infty$ and
   $\kappa_k = 0$ (no head engaged at level $k$) in the final bound must
   reduce to Paper 0's Theorem VI exactly. The first condition makes
   $L_{o\theta} \to 0$ asymptotically; the second makes $L_H \kappa_k = 0$
   identically. This is asserted at the end of T4 with both substitutions
   shown explicitly.
3. **Empirical bound check.** The Q3 constants-measurement protocol
   produces a numeric lower bound $\hat\lambda_{\text{composite}}$ that
   must agree with the theorem's prediction (within a confidence
   interval). T5 reports this comparison.

---

## 6. References (load-bearing)

Full bibliographic detail in [`latex/references.bib`](../../latex/references.bib).
Entries added in the scaffold PR are marked **(scaffold)**; later entries are
added by the corresponding ticket.

- **(scaffold) Borkar, V. S. (2008).** *Stochastic Approximation: A Dynamical
  Systems Viewpoint.* Cambridge University Press / Hindustan Book Agency.
  → Step 2 lemma (T1); Ch. 6 two-time-scale.
- **(scaffold) Bishop, C. M. (2006).** *Pattern Recognition and Machine
  Learning.* Springer. → KL-bound lemma (T2); §10 on variational
  inference.
- **(scaffold) Tsitsiklis, J. N. & Van Roy, B. (1997).** "An analysis of
  temporal-difference learning with function approximation."
  *IEEE Transactions on Automatic Control* 42(5), 674–690. → discounted-MDP
  two-time-scale precedent (T1).
- **(T1) Konda, V. R. & Tsitsiklis, J. N. (2003).** "On actor-critic
  algorithms." *SIAM J. Control Optim.* 42(4), 1143–1166. → discrete-update
  two-time-scale convergence (closest precedent to T1's setting).
- **(T3) Bardes, A., Ponce, J., LeCun, Y. (2022).** "VICReg:
  Variance-Invariance-Covariance Regularization for Self-Supervised
  Learning." *ICLR 2022.* → variance term used in head-Lipschitz proof.
- **(T5) LeCun, Y. (2022).** "A Path Towards Autonomous Machine
  Intelligence." Open Review note. → JEPA framework (already cited in P0
  via `lecun2022path`).
- **(T5) Assran, M. et al. (2023).** "Self-Supervised Learning from Images
  with a Joint-Embedding Predictive Architecture." *CVPR 2023.* → I-JEPA;
  empirical baseline.

---

## 7. Non-goals (to prevent scope creep)

- **No revision of Paper 0.** Paper 0's Theorem VI stands; Paper 5 is
  additive. The reduction-to-P0 check (§5.2) is a *requirement* of the
  proof, not a subject of revision.
- **No new RCS framework.** Paper 5 uses Paper 0's 7-tuple
  $\Sigma = (X, Y, U, f, h, S, \Pi)$ unchanged. No new state-space, no new
  shield semantics, no new controller signature.
- **No mechanized proof.** Hand-written argument only. Lean/Coq
  formalization is a separate research program (cf.
  `papers/p5-categorical-foundations/SCOPE.md`).
- **No empirical paper-body claims about Q1+Q2 substrates.** Those are
  frozen-substrate cases ($\Delta = \infty$) where the new terms vanish;
  Paper 1 is the empirical paper for the frozen regime. Paper 5's empirical
  figures (T5) are exclusively about Q3+ online substrates where
  $L_{o\theta}$ and $L_H \kappa_k$ are non-trivial.
- **No bisimulation theory.** That is the
  `papers/p5-categorical-foundations/` track, dormant pending §6 triggers.

---

## 8. Naming reconciliation

The directory `papers/p5-online-jepa-stability/` is a sibling of the
existing dormant `papers/p5-categorical-foundations/`. Both target the
"Paper 5" slot of the RCS series, but they are mathematically and
methodologically disjoint:

|                          | `p5-online-jepa-stability` (this paper)                              | `p5-categorical-foundations` (dormant)                            |
| ------------------------ | -------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Status                   | scaffold (active; sub-epic BRO-955 In Progress)                      | dormant (no Linear ticket; annual review)                          |
| Mathematical machinery   | Two-time-scale stochastic approximation, Lipschitz analysis, Lyapunov | Bicategories, terminal coalgebras, approximate bisimulation       |
| Proof technique          | Hand-written analytic                                                | Coalgebraic / categorical                                          |
| Empirical content        | Q3+ substrate constants measured + CI-gated                          | None (purely theoretical)                                          |
| Trigger to write         | Q1 PASS (or even FAIL — theorem applies regardless)                  | One of six triggers in `p5-categorical-foundations/SCOPE.md` §6   |
| Target venue             | CDC / NeurIPS theory track / TAC                                     | LICS / LMCS / ACT                                                  |
| Estimated effort         | ~5 weeks (T1+T2+T4+T5; T3 parallel)                                  | 6–18 months                                                       |

A future renumbering decision is deferred. Once `p5-online-jepa-stability/`
is on track to publication, the categorical-foundations document may be
renumbered (e.g., `p8-categorical-foundations`) or retired per its own
dormancy policy.

---

## 9. Reproducibility commands

From the root of this repo:

```bash
# 1. Build the scaffold PDFs (sanity; does not run the proof)
make build-p5-jepa

# 2. Build a single format
make build-p5-jepa-article    # one-column article
make build-p5-jepa-ieee       # IEEE conference

# 3. Build all papers
make build                    # P0 + P1 + P5-jepa

# 4. Test (no test changes; verifies 306 microRCS baseline + drift checks)
make test
```

Each PDF that lands at publication time MUST be reproducible by running
`make build-p5-jepa` from a clean checkout of the commit SHA recorded in
the paper's metadata block. Any quoted constants ($L_\theta$, $L_P$, etc.)
in the paper body are pinned to the Q3 measurement run that produced them;
the run ID is recorded in `papers/p5-online-jepa-stability/data/` (T5
deliverable).
