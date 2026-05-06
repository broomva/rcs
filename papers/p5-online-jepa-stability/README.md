---
title: "Paper 5: Online JEPA Composite Stability — A Two-Time-Scale Extension of Borkar (2008)"
tags:
  - rcs
  - paper
  - control-theory
  - stability
  - jepa
  - two-time-scale
aliases:
  - P5
  - P5-JEPA
  - RCS Online JEPA Stability Paper
created: "2026-05-05"
updated: "2026-05-05"
status: scaffold
linear: BRO-955
target_venue: "CDC 2027 / IEEE TAC / NeurIPS 2026 (theory track)"
related:
  - "[[RCS Index]]"
  - "[[p0-foundations]]"
  - "[[2026-05-05-jepa-as-substrate-design]]"
  - "[[jepa-as-substrate]]"
  - "[[joint-phase-gate]]"
---

# Paper 5: Online JEPA Composite Stability — A Two-Time-Scale Extension of Borkar (2008)

## Working Title

"Online JEPA Composite Stability: A Two-Time-Scale Extension of Borkar (2008)
for Recursive Controlled Systems with Learned Substrates."

## Contribution

Generalizes Paper 0's per-level stability budget
$\stab_k = \decay_k - \adapt_k - \design_k - \delay_k - \switch_k$ to the
setting where the substrate $V_k$ itself is **learned online** by a
Joint-Embedding Predictive Architecture (JEPA) rather than hand-set. Paper 0
treats $V_k$ as a fixed Lyapunov function with hand-set constants
$(\alpha_k, \bar\alpha_k, \gamma_k)$; Paper 5 treats them as **learned
outputs** of an encoder–predictor pair under VICReg + EMA-target
regularization, and derives the new bound:

$$
\lambda_{\text{composite}}^{(k)}
\;=\;
\gamma_k
- L_\theta\,\rho_k
- L_d\,\eta_k
- \beta_k\,\bar\tau_k
- L_{o\theta}(\Delta, \mu)
- L_H\,\kappa_k
- \frac{\ln \nu_k}{\tau_a}
\;>\; 0.
$$

Two new terms vs Paper 0:

- $L_{o\theta}(\Delta, \mu)$ — **online encoder cost**, bounding the
  contribution of latent-state drift between canary deployments. Closed form
  derived by extending Borkar (2008) Ch. 6 to discrete deployment events.
- $L_H \kappa_k$ — **head cost**, bounding the contribution of head-specific
  payload variations to the encoder's effective Lipschitz constant.

When $\Delta \to \infty$ (frozen substrate) and $L_H \le 1$ (non-amplifying
head), the new terms vanish and the bound reduces exactly to Paper 0
Theorem VI. Paper 5 is therefore **strictly additive** to Paper 0: it
covers every regime Paper 0 covers and extends to the new online + head-aware
regime that Paper 0 does not address.

**Not a measurement paper.** Paper 1 is the empirical paper for frozen-substrate
runtime measurements. Paper 5 is a theory paper: theorem statement, proof,
and the **CI-gated empirical-constants protocol** that future Q3+ substrate
deployments must pass before any production rollout.

## Outline

1. Introduction: motivation for moving from hand-set $V_k$ to learned-substrate
   $V_k$; positioning relative to Paper 0
2. Related Work: Borkar (2008) two-time-scale stochastic approximation;
   Tsitsiklis & Van Roy (1997) discounted-MDP TD-learning; LeCun (2022) JEPA
   framework; Bardes et al. (2022) VICReg; Assran et al. (2023) I-JEPA
3. RCS Recap (short): 7-tuple, P0 Theorem VI, the four hand-set constants
   that Paper 5 will replace with learned analogues (forwarded to Paper 0)
4. Theorem Statement: the seven-term bound; six assumptions (H8a–e + H9);
   reduction-to-P0 corollary
5. Proof: five-step argument (Lyapunov decomposition; Borkar extension;
   Lipschitz composition; head-Lipschitz cross-generalization; sum bounds)
6. Empirical Validation Protocol: the CI-gated constants-estimation
   protocol; per-head expected $L_H$ table; the
   $\hat\lambda_{\text{composite}}^{\text{lower}} > 0$ deployment gate
7. Discussion: where the new terms dominate; sensitivity to $\Delta$ and
   $\mu$; relationship to the JEPA-as-substrate research program (Q1–Q5)
8. Conclusion: limitations; open questions; threads to mechanized proof
   (Lean/Coq) and to the dormant categorical-foundations paper

## Theoretical Protocol

See [`PROTOCOL.md`](./PROTOCOL.md) for the locked theorem statement, the six
assumptions and how each is discharged, the five-step proof skeleton, the
sub-task mapping (T1–T5), the empirical-constants estimation protocol, and
the verification path (hand-written; no Lean/Coq mechanization for the
initial paper).

## Sub-Issues (Linear)

Parent sub-epic: **BRO-955** (PAPER-5: Online JEPA Composite Stability Theorem
— parallel track). Status: **In Progress** as of 2026-05-05.

- **T0** — paper scaffold, Makefile targets, theorem protocol document (this PR)
- **T1** — Borkar 2008 extension to discrete deployment (Lemma) — `BRO-989`
- **T2** — KL-bound lemma + variational-inference citation — `BRO-990`
- **T3** — (H9) head-Lipschitz formalization + cross-head generalization — `BRO-991`
- **T4** — Full proof writeup (5-step from PROTOCOL §2 expanded) — `BRO-992`
- **T5** — Paper 5 LaTeX draft + experimental figures from Q1–Q3 — `BRO-993`

Critical path: **T1 → T2 → T4 → T5** (~5 weeks). T3 in parallel with T1+T2.
T5 cannot land before Q3 substrate measurements are available.

The scaffold (T0) does not have a leaf ticket; it lands under BRO-955
directly because it is the prerequisite that any T* needs.

## Key References

Bibliographic entries marked **(scaffold)** are added in this PR;
others are added by the corresponding leaf ticket.

- **(scaffold) Borkar, V. S. (2008).** *Stochastic Approximation: A Dynamical
  Systems Viewpoint.* Cambridge University Press / Hindustan Book Agency.
  → Step 2 lemma (T1); Ch. 6 two-time-scale.
- **(scaffold) Bishop, C. M. (2006).** *Pattern Recognition and Machine
  Learning.* Springer. → KL-bound lemma (T2); §10 on variational inference.
- **(scaffold) Tsitsiklis, J. N. & Van Roy, B. (1997).** "An analysis of
  temporal-difference learning with function approximation."
  *IEEE Trans. Automatic Control* 42(5).
- Paper 0 of this series — Theorem VI (Composite Stability)
- LeCun (2022) — `lecun2022path`, already in `latex/references.bib`

## Relationship to the JEPA-as-Substrate Research Program

Paper 5 is the **theorem track** of the JEPA-as-substrate research program
specified at `docs/superpowers/specs/2026-05-05-jepa-as-substrate-design.md`.
The program has six phases (Q1, Q2.0, Q2.1, Q3, Q4, Q5) and a parallel
theorem track:

```
                      Q1 (substrate + AC-Trajectory-JEPA)
                           │
                           │ joint phase gate (G1/G2/G3 + P1/P2)
                           ▼
                      Q2.0 (L0Head refactor)
                           │
                           ▼
                      Q2.1 (L1ForwardRollout + SWE A/B)
                           │
                           ▼
                      Q3 (OnlineJepaSubstrate)
                           │
                           │ measures constants L_θ, L_P, L_H, Δ, μ, L_oθ
                           │ for Paper 5's empirical figures
                           ▼
                      Q4 (multi-head L0)
                           │
                           ▼
                      Q5 (embodied; sketched)

  parallel:           Paper 5 theorem track  ─────────────────►
                      T1 → T2 → T3 → T4 → T5
                      (T1+T2+T3 unblocked NOW; T4 needs all three;
                       T5 needs Q3 constants table)
```

Paper 5's theorem is **a-priori valid** under the six assumptions; the
empirical portions of the program are about *measuring the constants*, not
about validating the theorem itself. If Q1 fails its joint phase gate
(`research/entities/concept/joint-phase-gate.md`), the theorem still
applies — it just bounds the failure in terms of $L_\theta, L_P, \Delta, \mu$.

## Naming reconciliation

This directory (`p5-online-jepa-stability/`) sits next to the existing
dormant `p5-categorical-foundations/`. Both target the Paper 5 slot of the
RCS series, but they are methodologically disjoint:

- `p5-online-jepa-stability` — this paper. Two-time-scale stochastic
  approximation; Lyapunov / Lipschitz analysis; hand-written proof.
  Active (sub-epic BRO-955 In Progress).
- `p5-categorical-foundations` — dormant. Categorical / coalgebraic
  framework for cross-architecture bisimulation. No Linear ticket.
  Annual review per its own `SCOPE.md` §10; retirement 2030 if no
  trigger fires.

The two directories may coexist indefinitely. A future renumbering decision
is deferred to the user; see `PROTOCOL.md` §8 for the comparison table.
