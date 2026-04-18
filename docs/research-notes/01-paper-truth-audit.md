---
title: "Note 01 — Paper Truth Audit: Defensibility of RCS Claims"
date: 2026-04-17
status: wave-1-deliverable
scope: latex/rcs-definitions-ieee.tex + latex/rcs-definitions.tex
tags: [rcs, audit, defensibility, meta]
---

# Note 01 — Paper Truth Audit

## Purpose

Classify every load-bearing claim in the current RCS paper (IEEE + article
versions) by defensibility. Output is a table, a dependency graph, a
hand-wave index, and a count — no rewrites, no fixes.

## Nomenclature caveat

The spec refers to "Theorem VI.5"; the paper contains **one theorem**,
`thm:recursive` ("Recursive stability"). All other formal objects are
definitions, assumptions, propositions, remarks, or laws. Every occurrence
of "Theorem VI.5" below means `thm:recursive`.

## Corpus

- `latex/rcs-definitions-ieee.tex` (351 lines, conference format)
- `latex/rcs-definitions.tex` (711 lines, article format — superset)
- `latex/references.bib` (19 BibTeX entries)

Unless otherwise noted, line numbers refer to the article version.

## Defensibility table

Classification values: **grounded** / **weak** (proof sketch or hidden
assumption) / **overclaimed** (true in a restricted regime but asserted more
broadly) / **likely-wrong** (contradicted by literature or counterexample).

| # | Section / line | Claim (paraphrased) | Class. | Supporting / counter-evidence | Action |
|---|---|---|---|---|---|
| C01 | Abstract L51–63 | RCS "subsumes Eslami's agency hierarchy, Ashby's ultrastability, Beer's VSM, and active inference under a single recursive definition with quantitative stability conditions." | **overclaimed** | Ashby 1952 *Design for a Brain* ch.6 uses step-function homeostat, not Lyapunov; Beer 1972 *Brain of the Firm* uses information-variety + recursive management, not composite-V hierarchy; Friston 2009 PLoS ONE 4(7):e6421 treats AIF and RL as *related*, not unified. "Subsumes" overstates; "analogous to / compatible with" is accurate. | Downgrade to "unifies under a common *notation*", not a common *theorem*. |
| C02 | §3 def:rcs L148–180 + remark L171 | Self-similarity: "RCS ≅ F(RCS)", presented as a categorical fixed point of endofunctor F. | **overclaimed** | Spivak & Niu 2021 (*Polynomial Functors*, MIT Press) ch.6 treats fixed points via initial-algebra / final-coalgebra continuity (Adámek's theorem: F preserves ω-chains). Paper names the fixed point but does not verify F is actually an endofunctor on the declared category (what is a morphism in **CS**? simulation? bisimulation? these give *different* fixed points). | Either provide the categorical machinery or demote to "structural analogy / recursion pattern". |
| C03 | §4 prop:triple L198–213 | "Triple equivalence": drive V_i is *simultaneously* Lyapunov function, reward signal, and free-energy bound "under appropriate mappings". | **overclaimed** | Baltieri & Buckley 2019 *Entropy* 21(3):257, DOI 10.3390/e21030257 — PID↔AIF equivalence established **only for linear Gaussian generative models**. Keramati & Gutkin 2014 *eLife* 3:e04811 gives reward = −ΔV for physiological drives, not for arbitrary setpoint-quadratic costs. Friston 2009 explicitly frames RL vs AIF as a dichotomy, not an equivalence. The three are *compatible* in narrow regimes; "equivalence" requires more. | Weaken to "each interpretation holds under its regime" + state the three regimes. |
| C04 | §4 remark L215–220 | Saturation V_i(s_i)=0 provides "inherent safety guarantees against catastrophic optimization". | **overclaimed** | Krakovna et al. 2020 "Specification gaming: the flip side of AI ingenuity" (DeepMind) and Pan, Bhatia, Steinhardt 2022 *arXiv:2201.03544* "The Effects of Reward Misspecification" — bounded objectives still admit Goodharting, reward hacking, specification gaming, side-effects. Saturation prevents *one* failure mode (unbounded scale), not safety in the Stuart-Russell/Krakovna sense. | Narrow to "prevents unbounded resource acquisition"; drop "safety guarantees". |
| C05 | §5 ass:per-level L231–242 | Each level has Lyapunov V_i with quadratic sandwich. | **grounded** | Khalil 2002 ch.4 — standard Lyapunov converse theorems give this on exponentially stable regions. | Keep. |
| C06 | §5 ass:decay L244–252 | "Frozen decay": V_i drops at rate σ_i with higher levels held constant. | **weak** | The word "frozen" is singular-perturbation jargon; the assumption presumes the two-time-scale reduced system from Tikhonov's theorem (Kokotović, Khalil, O'Reilly 1986, *Singular Perturbation Methods in Control*, ch.2). Discrete-time version needs explicit slow-fast decomposition with a small parameter ε; paper never names ε. | State the reduced-system / boundary-layer split explicitly. |
| C07 | §5 ass:adapt, ass:design, ass:delay L254–286 | Per-level coupling bounds are linear in V_i. | **weak** | Linear-in-V bounds are valid after local linearization around the equilibrium but are *not* automatic for general nonlinear V (Khalil 2002 §4.5). Paper does not restrict attention to linearizable or quadratic V_i. | State the quadratic-V regime where the bound is tight. |
| C08 | §5 ass:jump L288–295 | Jump comparability: V(x⁺) ≤ ν V(x⁻) at mode switches. | **grounded** | Liberzon 2003 §3.2 — standard multiple-Lyapunov-function switched-systems setup. | Keep. |
| C09 | §5 def:budget L297–325 | σ_i = γ_i − L_θρ_i − L_dη_i − βτ̄_i − (ln ν_i)/τ_a. | **grounded** | Direct algebraic consequence of ass:decay + ass:adapt + ass:design + ass:delay + ass:jump + Hespanha–Morse 1999 dwell-time formula. Eslami & Yu 2026 (arXiv:2603.10779) Thm.2 has the single-level analogue. | Keep. |
| C10 | §5 thm:recursive L353–371 | If σ_i > 0 ∀i, composite state decays exponentially at rate ω = min_i σ_i. | **weak** | Proof labelled "Proof sketch" and invokes "by singular perturbation" + "Full proof via Tikhonov's theorem … level-by-level". Tikhonov (Khalil 2002 ch.11, theorem 11.2) is a *continuous-time* ODE result with small ε; discrete-time analogues exist (Kokotović et al. 1986 ch.6) but require explicit reduced/boundary-layer stability, which is not verified here. | Either produce the full proof (discrete-time Tikhonov instantiation) or weaken to "conjecture verified numerically". |
| C11 | §5 thm:recursive (composite rate) L401–404 | Composite V = Σ α_i V_i decays at rate ω = min_i σ_i. | **overclaimed** | Dashkovskiy, Rüffer, Wirth 2010 *SIAM J. Control Optim.* 48(6):4089–4118, DOI 10.1137/090746483 — for interconnected ISS systems, the composite rate depends on small-gain conditions, not min of per-system rates. Khalil §11.3 shows composite decay rate can be strictly below min when coupling is present. The paper's choice of α_i is not specified; the "inheritance" is not automatic. | Replace "= min_i σ_i" with "≥ some explicit ω depending on coupling + α_i". |
| C12 | §6 EGRI Five Laws L493–522 | Five Laws map to stability conditions. | **overclaimed** | Only Law 2 (requisite variety, Ashby 1956) and Law 4 (budget-as-Lyapunov) admit formal content. Law 1 (evaluator supremacy) is a policy statement. Law 3 (evaluator immutability) invokes "separation principle" which is a *linear-Gaussian* result (Wonham 1968 *SIAM J. Control* 6(2):312–326); EGRI operates on arbitrary artifacts, not LQG plants. Law 5 is a definitional requirement on the rollback operator, not a derived condition. | Keep Laws 2 & 4 as formal; label 1, 3, 5 as "design principles" not "conditions". |
| C13 | §6 prop:egri-coupling L524–537 | η_1 bound for σ_1 > 0. | **grounded** | Rearranges def:budget; pure algebra. | Keep. |
| C14 | §5 rem:context-collapse L327–350 | ACE monolithic rewrite (Zhang et al. 2025) violates the η_1 bound (~150× in one step). | **grounded** | Zhang et al. 2025 *arXiv:2510.04618* Fig.2 reports the 18,282→122 token collapse and the 66.7%→57.1% accuracy drop. The η_1 bound follows from def:budget. The ratio does exceed any plausible L_{d,1}·η_1 admissible under σ_1>0. | Keep. Strongest ACE-grounded claim. |
| C15 | §7 def:fold L545–556 | Fold = Mealy machine "equivalently, a Luenberger observer with A=I". | **overclaimed** | Luenberger 1966 *IEEE Trans. Mil. Electron.* 8:74–80 — observer is x̂_{k+1}=Ax̂+Bu+L(y−Cx̂); convergence requires (A,C) detectable and L chosen so A−LC Schur. A=I collapses the plant-prediction term; fold is a pure accumulator, not a plant-aware observer. Calling it a "Luenberger observer" is cosmetic, not technical. | Demote to "Mealy state accumulator; Luenberger analogy holds only when plant dynamics are slower than folding rate". |
| C16 | §7 prop:sufficient L558–567 | If π_1 depends on y-history only through h_k, then h_k is a sufficient statistic. | **grounded** | Definitional: sufficient-statistic = a function of history that screens off the rest conditional on the policy. Standard (Bertsekas 2017 *Dynamic Programming*, vol.1 §4). | Keep. |
| C17 | §7 remark on self-observation cost L569–581 | Self-measurement adds τ̄_self into the budget. | **weak** | Ad hoc additive term with no derivation of its functional form. Reflexive delay literature (Carmel & Markovitch 1998; Stone & Veloso 2000) models self-modeling cost in computation, not in a Lyapunov-decrease penalty. | Either derive τ̄_self from a self-simulation argument or label it "illustrative". |
| C18 | §8 def:fleet L589–601 | ⊗_G = graph-indexed fleet composition. | **weak** | ⊗_G symbol introduced without formal definition; information-exchange-along-edges is gestured, not defined. Preservation of stability under ⊗_G is not shown. | Provide a formal definition (tensor product of dynamical systems along an interaction graph, e.g., Lewis–Vamvoudakis 2014 *IEEE Trans. Autom. Control*). |
| C19 | §8 def:resilience L603–617 | J_{jl} formula from Chacon 2025. | **grounded** | Direct reproduction of Chacon-Chamorro et al. 2025 IEEE TAI formula. Harmonic-mean aggregation is a standard worst-case penalty. | Keep. |
| C20 | §9 def:self-ref L632–641 | "Governance rules, documentation, and this document *are* the controller π_N". | **weak** | Philosophical position framed as definition. The inclusion π_N ⊇ Model(RCS_0…N) is not given a formal operational semantics (what does it mean to *execute* documentation as a controller?). | Keep as narrative; don't advertise as formal. |
| C21 | §9 prop:governance L643–678 | L3 has σ_3 > 0 with concrete parameters delay-dominated (56%). | **grounded** | Follows from def:budget + `parameters.toml` + `[derived.lambda]` cache. Python tests verify the arithmetic. | Keep (strongest quantitative claim in the paper). |
| C22 | §9 rem:witnesses L692–702 | Rust types + Python tests constitute a "three-layer soundness guarantee". | **overclaimed** | Type-level agreement is *not* semantic-equivalence. Leroy 2009 *Commun. ACM* 52(7):107–115 (CompCert) and Pierce et al. 2015 *Software Foundations* require semantic-preservation proofs, not signature matching. The current witnesses show the *same numeric value* ω ≈ 0.006 across three representations; they do not prove the mathematical claims. | Downgrade to "numerical cross-check", not "soundness guarantee". |
| C23 | §2 remark CBF-QP L135–140 | Shield = CBF-QP when U_safe defined via barrier. | **grounded** | Standard CBF literature (Ames et al. 2017 *IEEE TAC* 62(8):3861–3876). | Keep. |
| C24 | §5 proof line L373–378 | "By time-scale separation, each level sees higher as quasi-static and lower as converged." | **weak** | Circular with ass:decay's "frozen" qualifier; this *is* the singular-perturbation assumption restated. Paper uses time-scale separation both as hypothesis of thm:recursive and as proof argument without an independent bound on the separation ratio. | State a minimum separation ratio and show it holds in the parameters. |
| C25 | §1 contributions L88–99 | Paper contributes (i) RCS def, (ii) unified drive, (iii) recursive budget extending Eslami Thm.2, (iv) EGRI at L2. | **weak** on (ii) & (iv), **grounded** on (i) & (iii) | See C01, C03, C12. Contribution (iii) — extending Eslami 2026 Thm.2 — is the strongest; it is a direct algebraic generalisation. | Recast (ii) as "unified *notation*" and (iv) as "instantiation at L2, with Laws 2 & 4 as formal conditions". |

**25 rows. ≥ 15 requirement met.**

## Dependency graph

```
                       ass:per-level --+
                       ass:decay ------+
                       ass:adapt ------+
                       ass:design -----+--> def:budget (C09) --> thm:recursive (C10, C11)
                       ass:delay ------+          |                         |
                       ass:jump -------+          |                         v
                                                  v                   prop:governance (C21)
                                       prop:egri-coupling (C13) --+         |
                                                  |               |         v
                                                  v               |   rem:narrowest
                                       rem:context-collapse (C14) +
                                                                  |
                                                                  v
                                                     EGRI Laws 1–5 (C12)
                                                     [only 2 & 4 formal]

    def:rcs (C02) ─── fixed-point claim (not used in any proof) ─── aesthetic
    def:drive ──────> prop:triple (C03) ──── overclaim, not used downstream
    def:fold (C15) ──> prop:sufficient (C16) ─── prop:sufficient is independent of the Luenberger claim
    def:fleet (C18) ─── def:resilience (C19) ─── not used in main theorem
    rem:witnesses (C22) ─── rhetorical, not a proof step
```

**Reading.** The *load-bearing* chain is `ass:* → def:budget → thm:recursive
→ prop:governance`. Everything else (self-similarity, triple equivalence,
fleet, observer, self-referential closure) is *decorative* with respect to
the main stability result. **This is good news for revision**: fixing the
weak/overclaimed decorations leaves the core theorem intact, and fixing the
core theorem (C10, C11) does not require rewriting the decorations.

**Critical load-bearing hand-waves**, in order of severity:
1. C10 — Tikhonov / singular perturbation is invoked but not instantiated.
2. C11 — "composite rate = min σ_i" without small-gain verification.
3. C06 — "frozen decay" encodes time-scale separation implicitly.
4. C24 — circular use of time-scale separation as both hypothesis and proof step.

## Hand-wave index

Exhaustive list of rhetorical hedges in the paper, with the hidden work
each conceals.

| # | Phrase | Location | What it hides |
|---|---|---|---|
| H01 | "Under appropriate mappings" | prop:triple L200 | Three distinct mappings (V→reward via finite difference; reward→free-energy via linear Gaussian model; free-energy→V via monotone transform). Each holds in a different regime. |
| H02 | "By singular perturbation" | proof of thm:recursive L374 | Invocation of Tikhonov 1952 / Kokotović et al. 1986 without specifying the small parameter ε, the reduced system, the boundary-layer system, or their stability. |
| H03 | "Time-scale separation" | thm:recursive hypothesis L357 | No quantitative separation ratio. The budget σ_i does not contain an ε term; a tighter separation should tighten the budget, but the formula doesn't reflect this. |
| H04 | "Full proof via Tikhonov's theorem … applied level-by-level" | proof L402 | *The entire proof.* Pairwise Tikhonov applications introduce cumulative approximation errors that are not bounded. |
| H05 | "inherits exponential decay with rate ω = min_i σ_i" | proof L401 | Choice of α_i weights for V = Σ α_i V_i, and the argument that composite rate equals (rather than bounds below) min σ_i. Small-gain conditions (Dashkovskiy et al. 2010) not checked. |
| H06 | "Combining with jump growth and applying the average dwell-time condition" | IEEE proof L251–253 | Algebra of piecewise-continuous V with multiplicative ν at jumps and exponential decay on flows — Hespanha–Morse 1999 gives the recipe; paper skips the step showing V_i remains well-defined across higher-level-frozen flows. |
| H07 | "RCS ≅ F(RCS)" (fixed point) | def:rcs remark L171–180 | Endofunctor structure: is F actually functorial? On what category? What are morphisms? Paper names initial/final (co)algebras without verifying the standard hypotheses (Adámek ω-continuity). |
| H08 | "Equivalently, a Luenberger observer with A=I" | def:fold L552–556 | Luenberger-observer convergence needs (A,C) detectable and L chosen so A−LC is Schur; A=I forces the observer to track accumulator dynamics, not plant dynamics. |
| H09 | "The separation principle: the observer is independent of the plant" | Law 3 L503–507 | Separation principle = LQG result (Wonham 1968). EGRI artifacts are not linear Gaussian; the analogy is motivating, not normative. |
| H10 | "Constitutes a three-layer soundness guarantee" | rem:witnesses L700 | Semantic equivalence between LaTeX, Rust, Python is not shown — only numeric agreement at one operating point. |
| H11 | "⊗_G denotes composition with information exchange along edges" | def:fleet L595 | Formal tensor-product operator on dynamical systems (Lewis–Vamvoudakis 2014; Bullo 2018 *Lectures on Network Systems*) not written out; stability preservation not derived. |
| H12 | "Inherent safety guarantees against catastrophic optimization" | remark after prop:triple L218–220 | Which safety property, against which threat model (Goodharting, specification gaming, deceptive alignment, side-effects)? Saturation answers none of these. |
| H13 | "The hierarchy is a fixed point" | def:rcs L161 | See H07; the phrase is gestural without the categorical machinery. |

**13 hand-waves identified.** H02–H05 sit on the critical proof path and
are jointly responsible for thm:recursive being a "proof sketch" rather
than a proof. H01, H07, H12 are cosmetic — they cushion claims that don't
feed the main theorem. H08, H10 are specific to the "executable witness"
rhetoric and can be softened independently.

## EGRI Five Laws — formal-content mapping

Verifying the spec's claim that only Laws 2 & 4 have direct formal links.

| Law | Content | Formal link? |
|---|---|---|
| L1 Evaluator supremacy | "Loop safety ≤ evaluator quality" | **No.** Prose claim; no inequality, no proof. |
| L2 Mutation ≤ capacity | |M| ≤ capacity(σ) | **Yes.** Ashby 1956 Law of Requisite Variety; capacity is information-theoretic. |
| L3 Evaluator immutability | No joint mutation | **No.** Invokes separation principle (LQG) — analogy, not theorem (see C12, H09). |
| L4 Budget closure | Budget is Lyapunov, halt at 0 | **Yes.** Definitional: any strictly decreasing non-negative budget halts in finite time. |
| L5 Rollback | Promoted states forward-invariant | **Partial.** The statement *defines* the rollback operator's required property; it is not derived from anything. |

**Confirmed.** Only Laws 2 & 4 have derived formal content. Laws 1, 3, 5
are design principles dressed as conditions.

## Prop V.2 "triple equivalence" — targeted audit

The spec singled this out. Verdict: **overclaimed** (C03).

The three identifications require **three different regimes**:

1. **V as Lyapunov.** Standard, requires positive-definiteness + decrease
   — given by def:drive with local convergence to s_i.
2. **V drive-reduction as reward.** Keramati & Gutkin 2014 establishes this
   for physiological drives with *pre-specified* setpoints; extending to
   arbitrary ‖x − s‖² for RL reward is stronger than the paper's own
   support (an arbitrary policy may not maximize ΔV; reward shaping
   theorems — Ng, Harada, Russell 1999 — constrain which shapings
   preserve optimal policies).
3. **V as free-energy bound.** Baltieri & Buckley 2019 prove this for
   linear Gaussian generative models with PID-structured inference. For
   non-linear or non-Gaussian generative models, the bound does not hold.

Hence "equivalence" is too strong. Each identification holds in a
restricted regime and the regimes do not universally coincide.

## Summary

**Counts**: 25 audited claims.

- **Grounded**: 10 (C05, C08, C09, C13, C14, C16, C19, C21, C23, C25-part)
- **Weak** (proof sketch, hidden assumption, missing derivation): 9 (C06,
  C07, C10, C17, C18, C20, C24, C25-part, L3+L5 of EGRI-laws)
- **Overclaimed** (true in narrow regime, asserted broadly): 7 (C01, C02,
  C03, C04, C11, C12, C15, C22) — actually 8 when we split C12; the
  Laws-mapping counts once.
- **Likely-wrong** (contradicted by literature or counterexample): 0.

**Three-line conclusion.**
The paper's **core extension of Eslami & Yu's stability budget (C09,
thm:recursive-as-definition, prop:governance, rem:context-collapse) is
algebraically sound** and directly quantitatively useful. The **main
theorem (thm:recursive) is a proof sketch**, not a proof: it invokes
singular perturbation / Tikhonov without instantiation and asserts
composite rate ω = min σ_i without small-gain verification — these are
the two load-bearing weaknesses. All other weak/overclaimed items
(self-similarity, triple equivalence, fleet, observer, self-referential
closure) are **decorative** — fixing them does not alter the stability
result, and they can be softened to match the evidence without losing
the paper's contribution.

## Pointers for follow-up notes

- **Note 03 (ISS reformulation)** should target C10, C11, H02–H05. A
  Dashkovskiy–Rüffer–Wirth formulation would replace the Tikhonov hand-wave
  with a small-gain computation that feeds directly into the existing
  parameters.toml values.
- **Note 04 (recursion F(RCS)≅RCS)** should target C02, H07, H13. Our audit
  says the fixed-point language is decorative — Note 04 should confirm or
  refute that with an induction-on-depth search.
- **Note 06 (citation gaps)** should add Krakovna 2020 & Pan 2022 (for C04),
  Dashkovskiy et al. 2010 (for C11), Kokotović et al. 1986 (for C06, C10),
  Luenberger 1966 (for C15), Wonham 1968 (for C12), CompCert/Leroy 2009
  (for C22), Spivak & Niu 2021 already cited but unused (for C02).

---

*Word count excluding the defensibility table ≈ 1,850 words. Under the
2,500-word cap.*
