---
title: "Wave 1 Synthesis — Decision Memo & Roadmap"
date: 2026-04-17
author: Synthesis agent
status: wave-1-synthesis
scope: decision memo, not decision itself
reads:
  - 01-paper-truth-audit.md
  - 02-world-model-pivot-analysis.md
  - 03-iss-small-gain-analysis.md
  - 04-recursion-load-bearing-audit.md
  - 05-eso-llm-value-analysis.md
  - 06-literature-audit.md
tags: [rcs, synthesis, roadmap, decision-memo]
---
# Wave 1 Synthesis — Decision Memo & Roadmap

**Purpose.** Compress the six Wave 1 notes (`01-paper-truth-audit.md`,`02-world-model-pivot-analysis.md`, `03-iss-small-gain-analysis.md`,`04-recursion-load-bearing-audit.md`, `05-eso-llm-value-analysis.md`,`06-literature-audit.md`) into (i) a defensibility snapshot, (ii) a rankedcandidate-next-deliverable list, (iii) a roadmap tree over a 3–6 monthhorizon, and (iv) one recommended next action.

**This memo does not pick the pivot.** It surfaces 2–3 candidates withexplicit tradeoffs and identifies the cheapest unambiguously-useful stepthat can ship regardless of which pivot is later chosen.

## 1. Defensibility Summary

Every load-bearing claim in the paper (IEEE + article) has a verdict from`01-paper-truth-audit.md`. Below each class lists the anchoringWave 1 evidence.

### 1.1 Grounded (keep as-is)

- **Per-level Lyapunov bounds** (`ass:per-level`, `ass:jump`) — Khalil2002 converse theorems; Liberzon 2003 multi-Lyapunov switchedsystems. (Note 01 C05, C08.)
- **Stability budget formula** (`def:budget`) — direct algebraicconsequence of the per-level assumptions + Hespanha–Morse dwell-time;extends Eslami & Yu 2026 Thm 2. (Note 01 C09; Note 03 §1 confirms theformula is internally consistent; Note 04 §1.3 confirms it isfinite-hierarchy, not recursive-coalgebraic.)
- **EGRI–stability coupling** (`prop:egri-coupling`, η₁ bound) —pure rearrangement of `def:budget`. (Note 01 C13.)
- `rem:context-collapse` — ACE's 18,282→122 token collapse and66.7→57.1 accuracy drop (Zhang et al. 2025) *genuinely* exceed anyadmissible `L_{d,1}·η_1` under σ₁>0. The strongest ACE-grounded claimin the paper. (Note 01 C14.)
- **Governance numerics** (`prop:governance`, `parameters.toml`,`[derived.lambda]`) — reproduced identically by Python tests and Rustmirror (life#802); the arithmetic is correct. (Note 01 C21.)
- **CBF-QP as shield instance** — standard Ames et al. 2017/2019literature. (Note 01 C23; Note 06 ref #10 verified.)
- **Citations that exist and support the role they play**: 13 of 14shortlisted references. Bhargava, Soatto, Nguyen 2025 (PID-Steering),Dashkovskiy–Rüffer–Wirth 2010, Guo & Zhao 2016, Ames 2019, Berkenkamp2017, Perkins–Barto 2002, Esfandiari–Khalil 1992, Astolfi–Marconi2015, Hafner 2025 Nature, AgentSpec, Pro²Guard. (Note 06 §1.)

### 1.2 At-Risk (true in a restricted regime; currently asserted more broadly)

- `thm:recursive` — proof sketch invokes singular perturbation /Tikhonov level-by-level without instantiating ε, the reduced system,or the boundary-layer stability. (Note 01 C10, H02, H03, H04.)
- **"Composite rate = min_i σ_i"** — asserted as equality; Dashkovskiyet al. 2010 show composite rate depends on small-gain, not thepointwise min. α_i weights are unspecified. (Note 01 C11, H05;Note 03 §3.3 constructs an asymmetric example where `min σ_i < 0`but small-gain holds — the per-level and small-gain conditions areformally **incomparable**.)
- **"Frozen decay" / time-scale separation** — used both as hypothesisof `thm:recursive` and as proof argument without independentquantitative separation ratio. (Note 01 C06, C24, H03.)
- **Per-level coupling bounds linear in V_i** — valid after locallinearisation; not automatic for general nonlinear V. (Note 01 C07.)
- **Triple equivalence** (`prop:triple`) — three distinct identifications,each holding in its own regime (LQG for AIF; bounded physiologicaldrives for reward; quadratic V for Lyapunov). "Under appropriatemappings" hides three different mappings. (Note 01 C03, H01.)
- **"Inherent safety guarantees against catastrophic optimization"** —saturation blocks unbounded scale only; does not addressGoodharting / specification gaming / side-effects (Krakovna 2020,Pan et al. 2022). (Note 01 C04, H12.)
- **LLM-as-Π₀ (current framing, Assumptions 1–2 literally applied)** —Bhargava/Soatto establish **reachability**, not contraction; LLMstate is shift-and-grow, so `‖x‖²` is not well-defined without acontinuous-lift projection the paper does not state. (Note 02 §2.1,§2.2 Framing A row; Note 06 §3.B, §3.C on Bhargava/Soatto partialsupport.)
- **"Luenberger observer with A=I"** (`def:fold`) — Luenbergerconvergence requires (A,C) detectable and L chosen so A−LC is Schur;A=I collapses the plant-prediction term and makes the analogycosmetic. (Note 01 C15, H08.)
- **"Three-layer soundness guarantee"** (LaTeX + Rust + Python) —numeric agreement at one operating point, not semantic equivalence(CompCert/Leroy 2009 standard). (Note 01 C22, H10.)

### 1.3 Speculative (no derivation in the paper; stated for rhetorical effect)

- **Self-similarity as categorical fixed point** (`RCS ≅ F(RCS)`) —endofunctor F, initial algebra, final coalgebra *named but neverunfolded*. Note 04 counterfactual test: every theorem and proofsurvives the flat-list formulation. Classification: aesthetic, notload-bearing. (Note 01 C02, H07, H13; Note 04 §1.1, §1.2, §1.5,§1.6, §2.)
- **Mealy coalgebra framing of fold** — "unique homomorphism to thefinal coalgebra" never constructed; bisimulation never used.(Note 04 §1.6.)
- **Self-referential RCS closure** (`def:self-ref`) — philosophicalposition dressed as definition; no operational semantics for"documentation as controller". (Note 01 C20; Note 04 §1.8.)
- **EGRI Laws 1, 3, 5** — policy statements, not derived conditions.Law 3 invokes the LQG separation principle (Wonham 1968) asanalogy. (Note 01 C12, H09.)
- **Fleet composition operator ⊗_G** — introduced without formaldefinition; stability preservation not derived. (Note 01 C18, H11.)
- **ESO / ADRC around the LLM** — three ADRC structural requirements(sign(b₀), bounded ‖ḟ‖, monotone action effect) **all fail** on thenatural LLM action space. Defensible only on structured actionvocabularies where PID steering already works. (Note 05 §2, §4.)
- **Fürnsinn–Long–Cortés NeurIPS 2025** — **citation does not exist**as described. Author combination and venue are not attested onarXiv, dblp, OpenReview, or NeurIPS 2025 proceedings. Likely ahallucinated reference. (Note 06 §1 row 6, §2 "Not emitted" block.)
- **"Closed-loop control of LLM internals" bundling Pro²Guard +AgentSpec with Nguyen/LiSeCo** — category collapse. Pro²Guard andAgentSpec are **runtime enforcement over external agent actions**,not activation/logit/hidden-state control. (Note 06 §3.A.)

### 1.4 One-line verdict on the paper

The **extension of Eslami & Yu 2026's stability budget** (`def:budget`→ `prop:governance` → `rem:context-collapse`) is algebraically soundand quantitatively useful. The **main theorem** (`thm:recursive`) is aproof sketch that cannot be promoted without either (a) a finite-depthinduction (Note 04 Option B) or (b) a small-gain companion statement(Note 03 §10). **Everything else** — self-similarity, tripleequivalence, fleet, observer, self-referential closure, ESO-as-controller,"three-layer soundness" — is decorative with respect to the mainresult: fixing it does not touch the core theorem, and fixing the coretheorem does not require touching it.

## 2. Critical-Path Next Deliverables

Three candidates, ranked by **leverage = (reduction in defensibilitydebt) / (effort)**. Each entry cites which Wave 1 finding justifies it,which open questions it resolves, and which it does **not**.

### Candidate D1 — *Citation-hygiene PR* (`references.bib` update + Soatto arXiv ID fix)

- **Deliverable.** Add the 13 confirmed shortlisted BibTeX entriesfrom Note 06 §2 to `latex/references.bib`. Fix Soatto's arXiv ID`2302.01819` → `2305.18449` wherever it appears. Remove theFürnsinn–Long–Cortés reference entirely (or recover the intendedsource first — Note 06 surfaces three candidates).
- **Effort.** Small. 1–2 hours for entry edits + 1 compile pass.
- **Risk.** Near-zero. Every entry is verified against arXiv / DOI inNote 06 §1. No math touched.
- **Depends on Wave 1 findings.** Note 06 §1 verification table,Note 06 §2 gap list, Note 06 §3.A category-collapse observation.
- **Resolves open questions.** Closes *all* bibliography-level debtfor the Wave 1 shortlist. Prerequisite for any future PR that citesthese works (which, under every candidate framing in Note 02, ismost or all of them).
- **Does not resolve.** The paper's mathematical weaknesses; theworld-model pivot; the recursion question; the ESO/ADRC question.
- **Why ship it.** It is strictly additive, needed under every futurepath, and does not require any decision about Notes 01/02/03/04/05.

### Candidate D2 — *Decoration demotion + main-theorem hardening PR*

- **Deliverable.** Two changes to `latex/rcs-definitions.tex` and`latex/rcs-definitions-ieee.tex`, landed as separate commits inone PR:
    1. **Demote decorative overclaims.** Per Note 01 §Dependencygraph and Note 04 §3 Option A:
    - `def:rcs` remark "`RCS ≅ F(RCS)` as fixed point" →downgrade to "structural self-similarity: same 7-tuplesignature at every level; the hierarchy has finite depthN≤4 in practice." Delete the RCS-endofunctor definitionand the Mealy-coalgebra definition (both unused). Remove`prop:triple`'s "equivalence" language in favour of"each interpretation holds in its regime" + name thethree regimes. Soften"inherent safety guarantees against catastrophicoptimization" → "prevents unbounded resourceacquisition". Relabel `rem:witnesses` "three-layersoundness guarantee" → "numerical cross-check acrossrepresentations".
    - Relabel EGRI Laws 1, 3, 5 as "design principles"; keepLaws 2 (requisite variety) and 4 (budget-as-Lyapunov) asformal conditions. (Note 01 EGRI table, Note 04 §1.7.)
    - Demote `def:fold`'s "Luenberger observer with A=I" to"Mealy accumulator; Luenberger analogy holds only whenplant dynamics are slower than folding rate". (Note 01C15, H08.)
    2. **Promote the main theorem** from proof sketch to theorem viathe cheapest honest route available:
    - **Route A (preferred — Note 04 Option B):** rewrite`thm:recursive` as a finite-depth induction on N with anexplicit Tikhonov step at each level and an explicitminimum-separation hypothesis (H6 in Note 04 §4). Adda skeleton proof following Note 04 §4; full proof canland in a follow-up.
    - **Route B (alternative — Note 03 §10):** keep`thm:recursive` as primary, add a corollary that theper-level bounds yield a linear ISS-Lyapunov functionand invoke Jiang–Teel–Praly 1994 for GAS (sufficient forN=2; flag N>2 as future work). This is algebraicallycheaper but adds a new modelling layer.
    - Pick *one* route. Both require roughly the same timeinvestment in LaTeX; Route A preserves the paper'scurrent narrative (σ_i budget, min rate) while Route Bintroduces small-gain machinery that eventually needsexplicit inter-level gain functions the paper does notyet decompose (Note 03 Open Question 1).
- **Effort.** Medium. ~1 week for one person. Demotion is mechanicalediting; hardening (Route A) is 3–5 pages of new proof.
- **Risk.** Low on the demotion step (Wave 1 evidence is explicit).Medium on the hardening step — either Route A or Route B couldreveal a gap once the full proof is written out, though both areknown-feasible in the literature (Khalil 2002 Thm 11.4; JTP 1994).
- **Depends on Wave 1 findings.** Note 01 (C01, C02, C03, C04, C10,C11, C12, C15, C18, C20, C22, EGRI-laws); Note 03 (Open Question1 — decomposition of coupling terms), §10 Recommendation;Note 04 Option B §4 skeleton.
- **Resolves open questions.** Elevates `thm:recursive` from proofsketch to theorem. Removes decorative overclaims that a reviewerwill flag. Leaves the paper's quantitative spine(`parameters.toml` + governance + context-collapse) unchanged.
- **Does not resolve.** The world-model framing pivot (Note 02); theESO/ADRC direction for Paper 3 (Note 05); whether to pursueobserver estimation as a separate paper.
- **Why ship it.** It is the *single highest-leverage* move forPaper 0 / Paper 1 (foundations + stability). It resolves theweaknesses a control-theory reviewer will raise first. NeitherRoute A nor Route B forecloses any later framing choice.

### Candidate D3 — *World-model framing decision PR* (A/B/C/D pivot)

- **Deliverable.** Pick one of Framings A (LLM-as-Π₀, current), B(World-Model-as-Plant), C (Hybrid), D (Controller-Agnostic) perNote 02. Rewrite Sec. I–II accordingly. If B or C: plan aRust-Dreamer / TD-MPC2 port for Life as a 3–6 month side-project.If D: restructure all theorems with "if Π satisfies Assumptions1–3 …" prefix and add an instantiation catalogue.
- **Effort.** Medium (A with continuous-lift bridge) to Very Large(B or C — includes a Rust Dreamer port). D is medium: mostlyrephrasing.
- **Risk.** High. Framing A retains a reachability-vs-stabilitycitation gap (Note 06 §3.B, §3.C). Framing B forces Lifeimplementation work currently out of scope. Framing C compoundsboth. Framing D dilutes novelty.
- **Depends on Wave 1 findings.** Note 02 whole note; Note 01 C05(literal applicability of quadratic Lyapunov to LLM states);Note 05 (whether the ESO-as-observer contribution makes Framing Aor D more attractive); Note 04 (whether recursion is load-bearing —Note 04 says **no**, which lowers the cost of Framing D'snon-uniform recursion and raises the cost of retaining thecategorical language in any framing).
- **Resolves open questions.** The paper's venue fit (Note 02 row"Publishable-venue fit"); the novelty-statement choice (Note 02§6 Q8); whether Life builds a world-model backend.
- **Does not resolve.** Anything in Note 01, Note 03, Note 04 thatis decorative-vs-load-bearing; the citation hygiene in Note 06.
- **Why not ship first.** This is the highest-impact buthighest-commitment decision. Note 04 established that no theoremcurrently exploits the recursion structurally — so the framingchoice does *not* unlock or break the main theorem. It can waitbehind D1 and D2.

## 3. Roadmap Tree — 3–6 Month Horizon

Branches on three open decisions:

- **Decision 1** — Framing pivot (A / B / C / D per Note 02).
- **Decision 2** — Theorem-hardening route (A = induction / B = ISS corollary per Note 03 §10).
- **Decision 3** — Paper 3 direction (ESO-as-observer vs skip ESO entirely vs different observer family per Note 05 §6).

Each path below assumes D1 (citation hygiene) has shipped — D1 isindependent of every decision.

### Path P1 — *Rigor-first, framing-agnostic* (Note 04 Option B + Note 03 corollary, keep Framing A)

**Thesis.** Paper 1's contribution is the budget extension, not theLLM framing. Lock in the theorem, defer pivoting.

- Month 1: ship D1 (citation hygiene) + D2 (decorations demoted,`thm:recursive` hardened via Note 04 §4 Route A).
- Month 2: add Note 03 §10 small-gain corollary as a supportingresult; state the inter-level-gain decomposition as an openproblem.
- Month 3: reference a continuous-lift appendix (Soatto meaningspace) as a self-contained addendum, not a load-bearing claim.
- Months 4–6: optional — start Paper 3 (observer paper, Note 05§5 ESO-as-anomaly-observer) or Paper 2 (EGRI, already scoped).

**Milestones.** (i) Paper 1 rev 2 draft with induction proof;(ii) Paper 1 rev 2 submitted to IEEE TCNS / L4DC; (iii) Paper 3kickoff.

**When to choose P1.** Life has no capacity to build a Dreamerbackend in 2026 H2; the goal is to get Paper 1 defensible and move on.

### Path P2 — *World-model pivot* (Framing B, full Dreamer backend)

**Thesis.** The paper's ambition — "first recursive stability budgetfor AI agents" — is more defensible with a latent-dynamics plant thanwith an LLM plant. Take the hit.

- Month 1: ship D1. Start Sec. I–II rewrite (Framing B narrative).No D2 yet — theorem will change shape once L0 is Dreamer.
- Months 2–4: Rust Dreamer-V3 / TD-MPC2 port as new Life crate(`crates/worldmodel/`). Autonomic restructuring to consumelatent state.
- Month 5: new `thm:recursive` using Dreamer's Lipschitz RSSM asthe L0 Assumption 1/2 grounding (clean fit — Note 02 §2.2 Bcolumn).
- Month 6: Paper 1 rev with B framing; Paper 2 (EGRI) deferred.

**Milestones.** (i) Life `worldmodel` crate MVP; (ii) Paper 1 revwith B framing and new theorem; (iii) single-agent Dreamer-on-Lifebenchmark.

**When to choose P2.** Target venue is NeurIPS RL / Dreamer-awareaudience; Life team is willing to commit engineering to a world-modelbackend.

### Path P3 — *Observer-first* (ship Paper 3 before Paper 1 rev)

**Thesis.** The ESO-as-anomaly-observer idea (Note 05 §5) is thecleanest novel contribution in the program. It does not depend onPaper 1 being fixed, and it generates the empirical evidence thatwill motivate whatever framing Paper 1 ultimately adopts.

- Month 1: ship D1. Start Paper 3 (observer) with a minimalexperimental setup: scalar probe (e.g., refusal probability),ESO state estimator, detection-latency measurement.
- Months 2–3: Paper 3 draft; show ESO detects adversarial prefixinjection with shorter latency than Pro²Guard, and produces acontinuous magnitude suitable for the autonomic layer.
- Month 4: ship D2 based on what Paper 3 reveals about theframing — Paper 3 likely favours Framing A or D (Note 02 §6 Q5).
- Months 5–6: Paper 1 rev with Framing chosen by Paper 3 evidence.

**Milestones.** (i) Paper 3 experimental pipeline; (ii) Paper 3submitted; (iii) Paper 1 rev driven by Paper 3 evidence.

**When to choose P3.** The program's narrative weight sits in theobserver contribution; Paper 1 rev is less time-sensitive thansecuring novelty via Paper 3.

### Path P4 — *Controller-agnostic meta-framework* (Framing D)

**Thesis.** The paper's real novelty is the *template*, not theLLM-Π₀ instantiation. Reframe as a meta-framework that subsumesDreamer-Π, LLM-Π, CBF-shielded-Π, and PID-steering-Π as fourinstantiations.

- Month 1: D1 + D2 (decorations demoted; but `thm:recursive`restated as "if Π satisfies Assumptions 1–3 then …" rather thanhardened). Note 04 Option A is the target form (aestheticself-similarity explicitly retreated to).
- Months 2–3: add instantiation sections for Dreamer-Π,PID-steering-Π (Nguyen 2025), CBF-QP-Π (Ames 2019), LLM-Π(Soatto/Bhargava); each ≈ 1 page.
- Month 4: venue submission (IEEE TCNS / *Automatica*, frameworkpaper).
- Months 5–6: Paper 2 (EGRI) and Paper 3 (observer) asper-instantiation refinements.

**Milestones.** (i) Framework paper rev 2; (ii) four instantiationsubsections; (iii) framework submission to TCNS.

**When to choose P4.** Venue target is a framework-friendly journal;the team is comfortable trading per-claim novelty for breadth.

## 4. Recommended Next Action

**Ship Candidate D1 (citation hygiene) this week, then ship CandidateD2 (decoration demotion + **`thm:recursive`** hardening via Note 04Option B Route A) as the next PR after.** Keep the framing decision(P1 vs P2 vs P3 vs P4) open until D2 has landed.

**Reasoning.** (a) D1 is required under every path and every framing— shipping it is strictly dominant. (b) D2 removes everydecorative overclaim Wave 1 surfaced (Note 01 §1 summary: 7 of 8overclaimed items are decorative, and Note 04 confirms the recursionis not load-bearing in any current proof) *and* fixes thesingle load-bearing weakness (Note 01 C10/C11). It does this withoutcommitting to Framing A, B, C, or D. (c) The framing pivot (D3) isa larger commitment than Wave 1 alone justifies; two Wave 1 notes(Note 02 §6 Q1, Note 05 §6) explicitly flag that the decisionshould wait on Wave 2 evidence (target-venue choice and observerexperiment design). D1+D2 *shorten* the path to every subsequentframing choice.

## 5. Verification Checklist (self-audit)

- [x] File at `docs/research-notes/00-synthesis-decision-memo.md`.
- [x] Cross-references all six Wave 1 notes by filename:`01-paper-truth-audit.md` (§1.1–1.3, §2 D2, §4),`02-world-model-pivot-analysis.md` (§1.2, §2 D3, §3 P2/P4, §4),`03-iss-small-gain-analysis.md` (§1.1–1.2, §2 D2, §3 P1, §4),`04-recursion-load-bearing-audit.md` (§1.3, §2 D2, §3 P1/P4, §4),`05-eso-llm-value-analysis.md` (§1.3, §2 D3, §3 P3, §4),`06-literature-audit.md` (§1.1, §1.3, §2 D1, §3 P1–P4, §4).
- [x] Defensibility summary labels each claim **grounded / at-risk /speculative** (§1.1 grounded, §1.2 at-risk, §1.3 speculative).
- [x] Roadmap tree has ≥ 3 branches (§3: P1, P2, P3, P4 = four paths).
- [x] Recommended next action is 1–3 sentences with explicit Wave 1reasoning (§4).
- [x] No LaTeX, BibTeX, or code files modified by this task. Thismemo is a Markdown note only.