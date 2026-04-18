---
title: Literature Audit — Reference Verification and Citation Gaps
author: Wave 1 / Note 06
date: 2026-04-17
status: draft
scope: verify shortlist references, cross-check against references.bib, flag overstatements, surface additional relevant works
out_of_scope: editing latex/references.bib — this note produces a gap list only
---

# Literature Audit — Wave 1 Note 06

## Summary

Verified 14 shortlisted references against arXiv, IEEE Xplore, SIAM, Taylor & Francis, Nature, JMLR, and author pages. **13 of 14 exist and are correctly attributed; 1 does not exist as cited (Fürnsinn–Long–Cortés NeurIPS 2025).** The current `latex/references.bib` contains **zero** of the 14 shortlist entries — every shortlist reference is a gap. Additionally, the shortlist's arXiv ID for Soatto et al. "Taming AI Bots" is wrong (`2302.01819` → correct is `2305.18449`).

Overstatement risk is concentrated in the claim that AgentSpec and ProbGuard/Pro²Guard constitute "closed-loop control of LLM internals." Both are **runtime enforcement / behavioral monitoring** frameworks that intercept agent actions; they do not touch hidden states, activations, or weights. Treating them as peers of Nguyen 2025 PID activation steering and LiSeCo activation projection is category-collapse.

---

## 1. Reference verification table

Legend: **claim-supported** = does the source's own content support the role it plays in the prior conversation?
  - **yes** = source directly supports the claim as stated.
  - **partial** = source supports a weaker/narrower version of the claim.
  - **no** = source contradicts or does not support the claim.
  - **unverifiable** = cannot confirm existence or content; claim cannot be evaluated.

| # | Citation (as invoked) | Exists? | arXiv / DOI | Title as published | Claim-supported |
|---|---|---|---|---|---|
| 1 | Bhargava et al. "What's the Magic Word" | yes | arXiv:2310.04444 | What's the Magic Word? A Control Theory of LLM Prompting | partial — empirical k−ε controllability with ≥97% top-1 reachability for k≤10 tokens; not a full controllability theorem. |
| 2 | Soatto et al. "Taming AI Bots" | yes | arXiv:**2305.18449** (prior conversation cited **2302.01819** — wrong) | Taming AI Bots: Controllability of Neural States in Large Language Models | partial — controllability holds only when restricted to the quotient space of "meanings"; reachability in the raw embedding space is almost-sure with small probability. |
| 3 | Nguyen et al. 2025 "Activation Steering with a Feedback Controller" | yes | arXiv:2510.04309 | Activation Steering with a Feedback Controller | yes — paper explicitly frames prior activation-steering methods (ActAdd, Mean-AcT, DIM) as proportional controllers, derives PID extension, and "connects activation steering to classical stability guarantees in control theory." |
| 4 | Dashkovskiy–Rüffer–Wirth 2010 | yes | DOI:10.1137/090746483, SIAM JCO 48(6):4089–4118 | Small Gain Theorems for Large Scale Systems and Construction of ISS Lyapunov Functions | yes — constructs a locally Lipschitz ISS Lyapunov function for an interconnected network under a small-gain condition on the monotone gain operator. Matches the role it is meant to play in Note 03's ISS small-gain analysis. |
| 5 | Guo & Zhao 2016 | yes | ISBN 9781119239925, DOI:10.1002/9781119239932 | Active Disturbance Rejection Control for Nonlinear Systems: An Introduction (Wiley) | yes — canonical book-length ADRC reference covering ESO, tracking differentiator, and stability. |
| 6 | Fürnsinn–Long–Cortés NeurIPS 2025 | **no** | — | — | **unverifiable / likely fabricated**. Annika Fürnsinn's 2024–2025 publications are co-authored with Christian Ebenbauer and Bahman Gharesifard (flexible-step MPC, arXiv:2404.07870, Automatica 2025). No paper with co-authors "Long" and/or "Cortés" (Jorge Cortés, UCSD) is indexed on arXiv, dblp, OpenReview, NeurIPS 2025 proceedings, or Gharesifard's or Cortés's publication pages. Either the names are wrong, the venue is wrong, or the citation is a hallucination. |
| 7 | AgentSpec ICSE 2026 | yes | arXiv:2503.18666 | AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents | partial — it is *runtime enforcement via DSL rules* on agent actions, not control of LLM internals (see Overstatement §3.A). |
| 8 | ProbGuard / Pro²Guard 2026 | yes | arXiv:2508.00500 (v2 posted 2026-01-06) | Pro2Guard: Proactive Runtime Enforcement of LLM Agent Safety via Probabilistic Model Checking | partial — it learns a DTMC from execution traces and applies PAC-bounded probabilistic reachability at runtime; it does *not* close a loop through the LLM's hidden states or logits (see Overstatement §3.A). |
| 9 | Dreamer-V3 Nature | yes | DOI:10.1038/s41586-025-08744-2, Nature 640:647–653 (2025-04) | Mastering diverse control tasks through world models | yes for RL/robotics benchmarks (150+ tasks, Minecraft diamonds from scratch); partial if extrapolated to "world models for LLM agents" — paper does not study language agents. |
| 10 | Ames et al. CBF tutorial | yes | arXiv:1903.11199, DOI:10.23919/ECC.2019.8796030 | Control Barrier Functions: Theory and Applications (2019 ECC, pp. 3420–3431) | yes — canonical CBF tutorial/survey; supports the "safe set forward-invariance via CBF" claim. |
| 11 | Berkenkamp et al. 2017 | yes | arXiv:1705.08551, NeurIPS 2017 pp. 908–919 | Safe Model-based Reinforcement Learning with Stability Guarantees | yes for classical control tasks under a GP prior; partial if used to justify "safe RL with stability guarantees for LLMs" — the paper's results are for Lipschitz dynamical systems, not language models. |
| 12 | Perkins & Barto JMLR 2002 | yes | JMLR 3:803–832 | Lyapunov Design for Safe Reinforcement Learning | partial — gives qualitative safety via switching among *pre-designed* Lyapunov-descending base controllers; does not synthesize Lyapunov functions from scratch. |
| 13 | Esfandiari–Khalil 1992 | yes | DOI:10.1080/00207179208934355, Int. J. Control 56(5):1007–1037 | Output feedback stabilization of fully linearizable systems | yes — canonical high-gain observer paper; correctly identified as the origin of the peaking phenomenon. |
| 14 | Astolfi–Marconi low-power observer | yes | arXiv:1501.04330, DOI:10.1109/TAC.2015.2408554, IEEE TAC 60(11):3059–3064 | A High-Gain Nonlinear Observer with Limited Gain Power | yes — replaces a gain growing as powers of n with a 2n−2-dimensional observer whose gain grows only to power 2. Supports the "low-power high-gain observer" claim. |

**Rows:** 14. **Existence verdicts:** 13 yes, 1 no. **Claim-support verdicts:** 6 yes, 7 partial, 1 no/unverifiable. Every row has a verdict.

---

## 2. Gap list — references invoked but missing from `references.bib`

Current `latex/references.bib` contains 31 entries. **None of the 14 shortlisted references is present.** The closest existing entry is `khalil2002nonlinear` (Khalil's *Nonlinear Systems* textbook), which is a different work from both Esfandiari–Khalil 1992 and Khalil's 2017 SIAM observer monograph.

Below are syntactically valid BibTeX entries ready for a future PR that updates `references.bib`. **Not pasted into `references.bib` — out of scope for this task.**

```bibtex
% --- Control of LLMs / agents ---

@article{bhargava2023magic,
  author  = {Bhargava, Aman and Witkowski, Cameron and Shah, Manav and Thomson, Matt W.},
  title   = {What's the Magic Word? {A} Control Theory of {LLM} Prompting},
  journal = {arXiv preprint arXiv:2310.04444},
  year    = {2023},
  note    = {v4, July 2024}
}

@article{soatto2023taming,
  author  = {Soatto, Stefano and Tabuada, Paulo and Chaudhari, Pratik and Liu, Tian Yu},
  title   = {Taming {AI} Bots: Controllability of Neural States in Large Language Models},
  journal = {arXiv preprint arXiv:2305.18449},
  year    = {2023}
}

@article{nguyen2025activation,
  author  = {Nguyen, Dung V. and others},
  title   = {Activation Steering with a Feedback Controller},
  journal = {arXiv preprint arXiv:2510.04309},
  year    = {2025},
  note    = {v2, March 2026}
}

@inproceedings{wang2026agentspec,
  author    = {Wang, Haoyu and Poskitt, Christopher M. and Sun, Jun},
  title     = {{AgentSpec}: Customizable Runtime Enforcement for Safe and Reliable {LLM} Agents},
  booktitle = {Proceedings of the 48th {IEEE/ACM} International Conference on Software Engineering ({ICSE} '26)},
  year      = {2026},
  note      = {arXiv:2503.18666}
}

@article{wang2026pro2guard,
  author  = {Wang, Haoyu and Poskitt, Christopher M. and Sun, Jun and Wei, Jiali},
  title   = {{Pro2Guard}: Proactive Runtime Enforcement of {LLM} Agent Safety via Probabilistic Model Checking},
  journal = {arXiv preprint arXiv:2508.00500},
  year    = {2026},
  note    = {v2, January 2026}
}

@inproceedings{kong2024liseco,
  author    = {Kong, Emily and others},
  title     = {Linearly Controlled Language Generation with Performative Guarantees},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  year      = {2024},
  note      = {LiSeCo; OpenReview id V2xBBD1Xtu. Verify first-author attribution before citing.}
}

% --- ISS / small-gain ---

@article{dashkovskiy2010smallgain,
  author  = {Dashkovskiy, Sergey N. and R{\"u}ffer, Bj{\"o}rn S. and Wirth, Fabian R.},
  title   = {Small Gain Theorems for Large Scale Systems and Construction of {ISS} {Lyapunov} Functions},
  journal = {SIAM Journal on Control and Optimization},
  volume  = {48},
  number  = {6},
  pages   = {4089--4118},
  year    = {2010},
  doi     = {10.1137/090746483}
}

% --- ADRC / ESO ---

@book{guo2016adrc,
  author    = {Guo, Bao-Zhu and Zhao, Zhi-Liang},
  title     = {Active Disturbance Rejection Control for Nonlinear Systems: An Introduction},
  publisher = {John Wiley \& Sons},
  year      = {2016},
  isbn      = {9781119239925},
  doi       = {10.1002/9781119239932}
}

% --- World models / RL ---

@article{hafner2025dreamerv3,
  author  = {Hafner, Danijar and Pasukonis, Jurgis and Ba, Jimmy and Lillicrap, Timothy},
  title   = {Mastering Diverse Control Tasks Through World Models},
  journal = {Nature},
  volume  = {640},
  pages   = {647--653},
  year    = {2025},
  doi     = {10.1038/s41586-025-08744-2}
}

% --- Safe RL / CBF / Lyapunov design ---

@inproceedings{ames2019cbf,
  author    = {Ames, Aaron D. and Coogan, Samuel and Egerstedt, Magnus and Notomista, Gennaro and Sreenath, Koushil and Tabuada, Paulo},
  title     = {Control Barrier Functions: Theory and Applications},
  booktitle = {18th European Control Conference (ECC)},
  pages     = {3420--3431},
  year      = {2019},
  doi       = {10.23919/ECC.2019.8796030}
}

@inproceedings{berkenkamp2017safe,
  author    = {Berkenkamp, Felix and Turchetta, Matteo and Schoellig, Angela P. and Krause, Andreas},
  title     = {Safe Model-based Reinforcement Learning with Stability Guarantees},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  pages     = {908--919},
  year      = {2017},
  note      = {arXiv:1705.08551}
}

@article{perkins2002lyapunov,
  author  = {Perkins, Theodore J. and Barto, Andrew G.},
  title   = {{Lyapunov} Design for Safe Reinforcement Learning},
  journal = {Journal of Machine Learning Research},
  volume  = {3},
  pages   = {803--832},
  year    = {2002}
}

% --- High-gain / low-power observers ---

@article{esfandiari1992output,
  author  = {Esfandiari, Farzad and Khalil, Hassan K.},
  title   = {Output Feedback Stabilization of Fully Linearizable Systems},
  journal = {International Journal of Control},
  volume  = {56},
  number  = {5},
  pages   = {1007--1037},
  year    = {1992},
  doi     = {10.1080/00207179208934355}
}

@article{astolfi2015lowpower,
  author  = {Astolfi, Daniele and Marconi, Lorenzo},
  title   = {A High-Gain Nonlinear Observer With Limited Gain Power},
  journal = {IEEE Transactions on Automatic Control},
  volume  = {60},
  number  = {11},
  pages   = {3059--3064},
  year    = {2015},
  doi     = {10.1109/TAC.2015.2408554}
}
```

**Not emitted** (fabricated / unverifiable):

```bibtex
% Fürnsinn--Long--Cortés NeurIPS 2025: NO matching paper found on arXiv, dblp, OpenReview,
% NeurIPS 2025 proceedings, or the publication pages of Gharesifard or Cortés. Annika Fürnsinn's
% actual 2024-2025 MPC papers are with Ebenbauer and Gharesifard (not Long/Cortés).
% Action: before citing, identify the actual intended paper. Candidates:
%   - Fürnsinn, Ebenbauer, Gharesifard, "Flexible-step MPC for Switched Linear Systems with
%     No Quadratic Common Lyapunov Function," IEEE TAC 70(9):6316-6322, 2025 (arXiv:2404.07870).
%   - Fürnsinn, Ebenbauer, Gharesifard, "Flexible-step model predictive control based on
%     generalized Lyapunov functions," Automatica 175:112215, 2025 (arXiv:2211.02780).
%   - Cherukuri, Gharesifard, Cortés, "Saddle-Point Dynamics: Conditions for Asymptotic
%     Stability of Saddle Points," SIAM JCO 55(1):486-511, 2017 — the only Gharesifard--Cortés
%     joint paper found.
```

---

## 3. Overstatement list

I do not have the full verbatim prior-conversation transcript in this workspace, only the summarized open questions in the spec. Overstatement analysis below is against the **spec-level formulations** + common usage patterns these works get subjected to in LLM-safety prose.

### 3.A Claim: "closed-loop control of LLM internals (Nguyen 2025 PID steering, LiSeCo activation projection, ProbGuard probabilistic monitoring)"

This bundles three fundamentally different intervention surfaces under one label. Exact quotes:

- **Nguyen et al. 2025** (verified, arXiv:2510.04309): Does intervene on LLM internals. Paper says:
  > "we develop a control-theoretic foundation for activation steering by showing that popular steering methods correspond to the proportional (P) controllers, with the steering vector serving as the feedback signal... the proportional (P) term aligns activations with target semantic directions, the integral (I) term accumulates errors to enforce persistent corrections across layers."
  **Verdict: claim supported.** This is genuine closed-loop intervention on residual-stream activations.

- **LiSeCo** (verified, NeurIPS 2024 OpenReview id V2xBBD1Xtu): Does intervene on LLM internals via an optimization-based projection. Paper says:
  > "[LiSeCo] derives from a theoretical formulation of controlled text generation... they formally pose LM control as a constrained optimization problem and provide its closed-form solution with guarantees... the steering variable is added to the intermediate representations."
  **Verdict: claim supported** — though "activation projection" is a fair characterization, the method is specifically **constrained-optimization-based linear projection**, with performative guarantees conditional on linear probes being well-calibrated.

- **ProbGuard / Pro²Guard** (verified, arXiv:2508.00500): Does **not** intervene on LLM internals. Paper says:
  > "Pro2Guard performs probabilistic model checking [...] by abstracting agent behaviors into symbolic states and learning a Discrete-Time Markov Chain (DTMC) from execution traces. At runtime, if [reach-probability of an unsafe state] exceeds the threshold, the system proactively triggers an intervention strategy, such as halting execution, prompting user verification, or invoking an LLM-based self-assessment."
  **Verdict: overstatement.** Pro²Guard is **runtime enforcement over *external* agent actions**, not control of hidden states, logits, or activations. Classing it with Nguyen 2025 and LiSeCo is category-collapse (runtime monitoring ≠ activation control).

- **AgentSpec** (verified, arXiv:2503.18666) — same category as ProbGuard:
  > "AgentSpec is a lightweight domain-specific language (DSL) for specifying and enforcing runtime constraints on LLM agents... the framework is designed to integrate seamlessly with LLM agent platforms like LangChain, intercepting key execution stages to enforce user-defined constraints."
  **Verdict: overstatement if used to support an "internals control" claim.**

**Remediation suggestion (for Note 05 / a future paper rev):** Split the triple into two rows:
| Intervention surface | Papers |
|---|---|
| Activation-space closed-loop control (internals) | Nguyen 2025 (PID steering), LiSeCo (linear projection) |
| Behavior-space runtime enforcement (externals) | AgentSpec, ProbGuard/Pro²Guard |

### 3.B Claim: "Bhargava et al. shows LLMs are controllable by prompts"

What the paper actually shows (direct quote):
> "Given initial state x₀ from Wikitext and prompts of length k ≤ 10 tokens, the 'correct' next token is reachable at least 97% of the time, and the top 75 most likely next tokens are reachable at least 85% of the time."

**Verdict: partial.** The result is a k−ε statistical controllability (short prompt → high probability of reaching a target *next token*, not a full sequence). Claiming full controllability of LLM behavior or of trajectories beyond next-token is an overstatement of the empirical result.

### 3.C Claim: "Soatto et al. proves LLM bots are controllable"

What the paper actually shows (direct quote):
> "a well-trained bot can reach any meaning albeit with small probability. [...] when restricted to the space of meanings, an AI bot is controllable."

**Verdict: partial.** Controllability is **conditional on restricting to the quotient space of meanings**, and the "any meaning is reachable" part is only almost-sure with possibly-small probability in the raw embedding. This does not imply strong / deterministic / uniform controllability.

### 3.D Claim: "Berkenkamp 2017 gives safe-RL stability guarantees applicable to LLMs"

What the paper actually shows:
> "We extend control-theoretic results on Lyapunov stability verification and show how to use statistical models of the dynamics to obtain high-performance control policies with provable stability certificates. [...] under additional regularity assumptions in terms of a Gaussian process prior, [...] one can effectively and safely collect data in order to learn about the dynamics."

**Verdict: overstatement if transferred to LLMs.** Results require a Gaussian-process prior over a Lipschitz dynamics $x_{t+1} = f(x_t, u_t)$ with reachable-set estimation. LLM token dynamics are 50k-way discrete, non-Lipschitz in embedding, and do not admit an analogous GP prior without modeling surgery. The method shape (Lyapunov verification + safe exploration) is transferable; the stability guarantees are not.

### 3.E Claim: "Perkins–Barto 2002 is a Lyapunov-RL method we can apply to agents"

What the paper actually shows (direct quote):
> "an agent learns to control a system by switching among a number of given, base-level controllers. These controllers are designed using Lyapunov domain knowledge so that any switching policy is safe and enjoys basic performance guarantees."

**Verdict: partial.** The method requires **externally-designed Lyapunov-descending base controllers**; the RL agent only chooses *which one to switch to*. It does not itself learn Lyapunov functions. Applying this to LLM-as-policy requires a set of provably-Lyapunov-descending base policies, which is exactly the hard part for LLMs.

### 3.F Claim: "Ames 2019 CBF tutorial provides safety certificates we can use on LLM agents"

The CBF tutorial assumes a continuous-time affine control system $\dot x = f(x) + g(x)u$ with a smooth safe set $\{x : h(x) \ge 0\}$. **Verdict: partial.** Transferable to hybrid / embodied agent plants (robots, vehicles). Not directly transferable to discrete-token LLM generation without first specifying $h$ over latent/output space — which is itself an open research question.

### 3.G Claim: "Dreamer-V3 proves world-model RL outperforms everything"

What the paper actually shows (direct quote):
> "we present the third generation of Dreamer, a general algorithm that outperforms specialized methods across over 150 diverse tasks, with a single configuration."

**Verdict: partial.** Scoped to RL benchmarks (Atari, DMC, Crafter, Minecraft). The paper does not study language agents, nor claim world models replace LLMs for linguistic reasoning. Invoking Dreamer-V3 to justify "LLM = world model" pivots is a *conceptual analogy* at best, not empirical support.

---

## 4. Additional relevant references discovered

These were not in the shortlist but surfaced during verification and deserve consideration for later citation (with human review — do not auto-cite).

1. **Khalil, *High-Gain Observers in Nonlinear Feedback Control*, SIAM, 2017** (ISBN 9781611974850, DOI 10.1137/1.9781611974867). Book-length synthesis of refs #13–#14 + low-power + measurement-noise extensions. **Suggested role:** replace or supplement Esfandiari–Khalil 1992 and Astolfi–Marconi 2015 when a single canonical citation is preferred. BibTeX:
   ```bibtex
   @book{khalil2017highgain,
     author    = {Khalil, Hassan K.},
     title     = {High-Gain Observers in Nonlinear Feedback Control},
     series    = {Advances in Design and Control},
     publisher = {SIAM},
     year      = {2017},
     isbn      = {9781611974850},
     doi       = {10.1137/1.9781611974867}
   }
   ```

2. **Cherukuri, Gharesifard, Cortés, "Saddle-Point Dynamics: Conditions for Asymptotic Stability of Saddle Points,"** SIAM J. Control Optim. 55(1):486–511 (2017). The only Gharesifard–Cortés joint paper surfaced. If the "Fürnsinn–Long–Cortés NeurIPS 2025" citation was a memory-collapse of this work or of Fürnsinn–Ebenbauer–Gharesifard, this is a candidate replacement. BibTeX:
   ```bibtex
   @article{cherukuri2017saddle,
     author  = {Cherukuri, Ashish and Gharesifard, Bahman and Cort{\'e}s, Jorge},
     title   = {Saddle-Point Dynamics: Conditions for Asymptotic Stability of Saddle Points},
     journal = {SIAM Journal on Control and Optimization},
     volume  = {55}, number = {1}, pages = {486--511}, year = {2017}
   }
   ```

3. **Fürnsinn, Ebenbauer, Gharesifard, "Flexible-step MPC for Switched Linear Systems with No Quadratic Common Lyapunov Function,"** IEEE TAC 70(9):6316–6322 (2025), arXiv:2404.07870. Relevant to Note 03's ISS analysis because it constructs generalized (non-quadratic, finite-window-averaged) Lyapunov functions for switched systems — directly comparable to Hespanha–Morse dwell-time averaging already in `references.bib`.

4. **Ames, Tabuada, co-authors of Soatto 2023 *and* Ames 2019 CBF tutorial.** Paulo Tabuada is a co-author on both controllability-of-LLMs (ref #2) and the CBF tutorial (ref #10). There may be newer Tabuada-led work bridging LLM controllability and CBFs; worth a targeted search if Note 05 pursues the ESO/ADRC-around-LLM direction. Not cited here — flagged as follow-up.

5. **"Linear Feedback Control Systems for Iterative Prompt Optimization in Large Language Models,"** arXiv:2501.11979 (Jan 2025). PID-style loop *around* the LLM (prompt-level, not activation-level). Useful as a **negative-of-internals** reference to balance Nguyen 2025: shows that prompt-level PID already exists in the literature, which weakens a "novelty" claim for ESO/ADRC *around* an LLM.

6. **Eslami & Yu (2026), arXiv:2603.10779** — already in `references.bib` as `eslami2026control`. Verified: exists, title matches, eess.SY, v4 2026-03-24. The bib entry's current `journal = {arXiv preprint arXiv:2603.10779}` is acceptable; consider adding `archivePrefix = {arXiv}, eprint = {2603.10779}` for tools that parse those fields.

7. **Zhang et al. (2025) ACE, arXiv:2510.04618** — already in `references.bib` as `zhang2025ace`. Verified: exists. BibTeX looks correct; note says ICLR 2026, which tracks with v3 timing (March 2026).

---

## 5. Self-check against Verification criteria

- [x] File exists at `docs/research-notes/06-literature-audit.md`.
- [x] Reference table has 14 rows covering the shortlist (§1 above).
- [x] Every row has a verdict on claim-support (yes / partial / no / unverifiable).
- [x] Suggested BibTeX entries in §2 are syntactically valid (`@type{key, field = {value}, ...}` shape with author/title/year/venue or DOI).
- [x] No edits to `latex/references.bib` have been made (verified via `git status`).

---

## 6. Open questions for the synthesis memo (Note 00)

- Should the paper adopt the ICSE 2026 / Pro²Guard runtime-enforcement frame as a *separate* layer from activation-space control, and cite them for the L3 governance layer rather than the L0/L1 control layer? (Relates to the split proposed in §3.A.)
- The Fürnsinn–Long–Cortés citation was evidently load-bearing in at least one prior-conversation argument (otherwise it wouldn't be on the shortlist). Before committing to that argument, we need to recover the actual intended source — recommend the user confirm which paper they meant.
- Is the Soatto 2023 arXiv ID fix (`2302.01819` → `2305.18449`) already in any draft? If so, it's a silent error that should be corrected in the same PR that lands the rest of these entries.
