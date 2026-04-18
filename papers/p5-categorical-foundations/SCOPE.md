---
title: "Paper 5 (Hypothetical): Categorical Foundations — Scope & Option-Preservation Document"
tags:
  - rcs
  - paper
  - scope
  - category-theory
  - bisimulation
  - coalgebra
aliases:
  - P5-SCOPE
  - RCS Categorical Foundations Scope
created: "2026-04-18"
updated: "2026-04-18"
status: dormant
linear: (unassigned — no ticket until a trigger fires)
target_venue: "(hypothetical) LICS / POPL / ACT / Logical Methods in CS"
related:
  - "[[RCS Index]]"
  - "[[p0-foundations]]"
  - "[[p6-horizontal-composition]]"
  - "[[p7-thermodynamic-limits]]"
  - "[[horizontal-vs-vertical-recursion]]"
  - "[[2026-04-18-pneuma-plexus-recursion-synthesis]]"
---

# Paper 5 (Hypothetical): Categorical Foundations for Recursive Controlled Systems

> **Document status: DORMANT preservation-of-option.** This is not a paper draft.
> It scopes what a future Paper 5 would cover, what machinery it would need, and
> what conditions would justify writing it. P0's finite-depth induction is and
> remains the authoritative foundation. Paper 5 is purely additive.

---

## 1. Purpose and Relationship to P0

Paper 0 (Foundations) establishes the RCS framework using **finite-depth
induction** — a predicate $P(N)$ proved by base case and inductive step
(`main.tex` §V, `thm:recursive`, lines 492–597). This is the correct proof
strategy: it gives a rigorous composite stability guarantee $\omega_N > 0$ for
any finite depth $N$, covers every Life deployment that will ever be built, and
does not require categorical machinery the paper does not earn.

During the D2 refactor (PRs #9 and #10 in `research/rcs/CLAUDE.md`), two
decorative definitions were removed from P0:

1. `def:rcs-endofunctor` — the "$F : \mathsf{RCS} \to \mathsf{RCS}$" endofunctor claim
2. `def:mealy-coalgebra` — the Mealy-coalgebra/fixed-point framing "$F(\mathrm{RCS}) \cong \mathrm{RCS}$"

Both were **decoration that the math did not earn**. The deletions were correct.
P0 is now tighter, more honest, and every result it states is rigorously proved
within finite-depth induction. `remark:finite-depth` in P0 (line 263–270) makes
this explicit: "recursion is notational convenience, and Theorem~\ref{thm:recursive}
proves composite stability by induction on this finite depth, without invoking a
categorical fixed point."

### What Paper 5 would be

Paper 5 would be an **additive, standalone** contribution that introduces
coinductive/categorical machinery **only to frame specific research results that
cannot be stated rigorously in the P0 framework**. Concretely:

- Paper 5 does **not** revise P0.
- Paper 5 does **not** retract `remark:finite-depth`.
- Paper 5 does **not** claim finite-depth induction is insufficient for what P0
  proves.
- Paper 5 **does** argue that certain *different* theorems — theorems P0 does
  not attempt — require moving to a categorical/coinductive setting.
- Paper 5 **does** preserve bit-for-bit compatibility with P0's stability
  theorem: every finite-depth hierarchy that P0 proves stable, Paper 5 proves
  stable as a corollary via the categorical-to-inductive projection.

Think of Paper 5 as bolting on an optional categorical layer above P0, like
adding a functor library on top of a well-tested imperative codebase.

---

## 2. What Paper 5 Would Prove

Candidate theorems. Each entry states: **(a) mathematical content, (b) research
problem it solves, (c) why finite induction alone cannot reach it.**

### T1 — Approximate bisimulation preservation under $F$

**Content.** Let $\Sigma_1, \Sigma_2$ be RCS instantiations at level $i$, and
let $\equiv_\varepsilon$ denote the $\varepsilon$-approximate bisimulation
relation (Girard–Pappas style) with respect to a chosen observation metric $d$.
Let $F$ be the "lift one level" endofunctor on the RCS category. Then:
$$
\Sigma_1 \equiv_\varepsilon \Sigma_2 \;\;\Longrightarrow\;\;
F(\Sigma_1) \equiv_{\varepsilon'} F(\Sigma_2)
$$
for some $\varepsilon' = \varepsilon' (\varepsilon, L_f, L_h, L_\Pi)$ depending
only on the Lipschitz constants of the dynamics, observation, and controller.

**Problem solved.** Answers: *"when two L0 world-model systems (e.g., Dreamer,
V-JEPA) are approximately equivalent, are the L1 agents built on top of them
approximately equivalent?"* This is a compositional transport question.

**Why finite induction can't prove it.** $P(N)$ quantifies over depth, not over
*architectures at a fixed depth*. Finite induction has no language for
"different $\Sigma$'s at the same level" or for a preservation law holding
across a morphism between them.

### T2 — Universal RCS up to $\varepsilon$-bisimulation

**Content.** There exists a canonical minimal RCS instantiation $\Sigma^*$
such that any RCS $\Sigma$ satisfying the standing hypotheses H1–H7 is
$\varepsilon$-bisimilar to $\Sigma^*$ for some $\varepsilon$ determined by
the parameter gap between $\Sigma$ and $\Sigma^*$.

**Problem solved.** Provides a single object to prove theorems *about* (rather
than proving them for every architecture separately). Dual-use as a
specification device.

**Why finite induction can't prove it.** "There exists" quantifies over the
proper class of RCS instantiations. Finite induction builds up from base cases;
it cannot universally quantify over all possible $\Sigma$'s.

### T3 — Cross-architecture transport of stability margins

**Content.** If $\Sigma_1 \equiv_\varepsilon \Sigma_2$ at level $i$ under the
bisimulation relation $R$, and $\Sigma_1$ has per-level margin $\lambda_i > 0$,
then $\Sigma_2$ has margin $\lambda_i' \geq \lambda_i - \phi(\varepsilon)$ for
a computable degradation function $\phi$.

**Problem solved.** Prove a stability result *once* on a reference architecture,
inherit approximate guarantees on every $\varepsilon$-equivalent architecture
without re-deriving the Lyapunov analysis. Deploys compositionally.

**Why finite induction can't prove it.** Requires the notion of "stability of a
relation between systems," which is a bisimulation-metric concept, not a
state-space trajectory concept.

### T4 — Infinite-depth fixed point $\mathrm{RCS}^\infty$

**Content.** Formal construction of $\mathrm{RCS}^\infty$ as the terminal
coalgebra of a suitable endofunctor $F$ on a category of metric transition
systems. Each finite-depth RCS is realized as an initial-segment projection
$\pi_N : \mathrm{RCS}^\infty \to \mathrm{RCS}_N$, with projection-preserving
$\omega_N \to \omega_\infty$ (possibly zero) in the limit.

**Problem solved.** Gives a single mathematical object to analyze
depth-invariant properties of the hierarchy. Enables reasoning about "any
depth" rather than "all finite depths" — these are different.

**Why finite induction can't prove it.** The object literally does not exist in
the finite-depth framework. Its construction requires terminal-coalgebra
theorems (Rutten, Jacobs).

### T5 — Functorial composition (vertical × horizontal)

**Content.** The vertical stability theorem (P0 Theorem VI) and horizontal
stability theorem (P6, outlined) are both functorial: there exist endofunctors
$V, H$ on the RCS category such that
$$
V \circ H \;\;\cong\;\; H \circ V
$$
up to $\varepsilon$-bisimulation. Composing vertical and horizontal recursion
in either order yields $\varepsilon$-equivalent systems, with $\varepsilon$
bounded by coupling constants between the axes.

**Problem solved.** Gives a categorical statement of the "two orthogonal axes"
claim in `research/entities/pattern/horizontal-vs-vertical-recursion.md`.
Establishes that the axes genuinely commute rather than being accidentally
consistent at the instances we have checked.

**Why finite induction can't prove it.** Commutativity of functors is not a
state-trajectory property. It lives in the 2-category of categories.

### T6 — Coinductive refinement of governance invariance

**Content.** The L3 self-referential closure described in
`research/rcs/docs/self-referential-closure.md` is a coinductive fixed point:
the governance layer that governs the system is itself a sub-object of the
system under its own governance. Paper 5 formalizes this as
$$
G \;=\; \nu X . \, \mathrm{Governs}(X, X)
$$
for a suitable type/endofunctor $\mathrm{Governs}$, and proves that this
coinductive definition is consistent with P0's finite-depth treatment at every
depth $N$.

**Problem solved.** Gives the self-referential closure described in the P0
governance section (lines 823+) its proper formal status. Removes the
hand-wave in "Level~3 (governance) includes the formalization itself."

**Why finite induction can't prove it.** Induction terminates; self-reference
does not. The only coherent formalization of "governs itself" is coinductive.

### T7 — Impossibility bounds quantifying over architectures

**Content.** Theorem schema:
> For no RCS $\Sigma$ at depth $D$ with compute budget $C$, horizon bound $H$,
> and latency bound $L$ can conditions $(P_1, \ldots, P_k)$ simultaneously
> hold.

**Problem solved.** Establishes *fundamental limits* on what any recursive
agent system can achieve, not just what a specific one does achieve. Required
for regulatory and certification work (see trigger T1, T6 in §6).

**Why finite induction can't prove it.** Negative universal claims quantifying
over architectures require a category of architectures over which to
quantify. Finite induction gives no such structure.

### T8 — Categorical probability bridge

**Content.** Probabilistic RCSs (where $f, h$ are Markov kernels) embed
faithfully into the Kleisli category of a suitable probability monad (Giry,
quasi-Borel, or Markov-category-style à la Baez–Fritz–Perrone). Under this
embedding, per-level KL divergences between bisimilar probabilistic RCSs bound
the $\varepsilon$ in approximate bisimulation.

**Problem solved.** Links RCS to mainstream categorical probability, opening
cross-pollination with categorical approaches to MDPs, POMDPs, and active
inference. Makes information-theoretic bounds directly applicable.

**Why finite induction can't prove it.** Monad/Kleisli structure is not a
trajectory-level concept.

---

## 3. Required Mathematical Machinery

What Paper 5 would have to build (or import and apply):

### 3.1 The category $\mathbf{RCS}$

**Objects.** RCS 7-tuples $\Sigma = (X, Y, U, f, h, S, \Pi)$ satisfying
standing hypotheses H1–H7 (from P0 §IV).

**Morphisms.** $\phi : \Sigma_1 \to \Sigma_2$ as a triple
$(\phi_X, \phi_Y, \phi_U)$ of maps between state/output/input spaces that
commute with $f, h$ up to $\varepsilon$-bounded error on trajectories. Morphisms
preserve shields $S$ and recursively lift through the controller $\Pi$.

**Key design question (deferred).** Whether morphisms preserve *exactly* or
*up to $\varepsilon$* is a foundational choice. $\varepsilon$-morphisms form a
bicategory / 2-category structure (the 2-cells measure approximation slack).

Reference: Baez–Erbele (2015) for categories in control (cited in P0);
Abramsky–Coecke categorical quantum mechanics for the bicategorical template.

### 3.2 Approximate bisimulation (Girard–Pappas)

**Definition.** A relation $R \subseteq X_1 \times X_2$ is an
$\varepsilon$-approximate bisimulation between $\Sigma_1, \Sigma_2$ with
observation metric $d$ iff for all $(x_1, x_2) \in R$:
1. $d(h_1(x_1), h_2(x_2)) \leq \varepsilon$,
2. for every $u \in U$, if $x_1' = f_1(x_1, u)$ then there exists $x_2'$ with
   $(x_1', x_2') \in R$ and $x_2' \approx f_2(x_2, u)$ modulo the metric, and
   symmetrically.

$\Sigma_1 \equiv_\varepsilon \Sigma_2$ iff such an $R$ exists from every pair
of initial states.

Reference: Girard & Pappas (2007), "Approximation metrics for discrete and
continuous systems," IEEE TAC 52(5).

### 3.3 Endofunctor $F$ on $\mathbf{RCS}$

**Candidate definition.** $F(\Sigma) := \Sigma^+$ where $\Sigma^+$ is obtained
by treating $\Sigma$'s behavior as a single component of a new higher-level
plant. Formally:
- $X_{F(\Sigma)}$ := space of trajectories of $\Sigma$ modulo the shield $S$,
- $Y_{F(\Sigma)}$ := aggregation of $Y_\Sigma$ over a time window,
- $U_{F(\Sigma)}$ := meta-controls selecting among setpoints for $\Pi_\Sigma$,
- $f_{F(\Sigma)}, h_{F(\Sigma)}$ induced by the above,
- $S_{F(\Sigma)}$, $\Pi_{F(\Sigma)}$ inherited recursively.

Functoriality requires this construction to extend to morphisms (it does, by
pointwise lifting) and to preserve identity and composition (it does up to
$\varepsilon$, giving a lax functor at minimum).

### 3.4 Terminal coalgebras and coinduction

To construct $\mathrm{RCS}^\infty$ (Theorem T4), Paper 5 applies Adámek's
terminal coalgebra theorem (or its metric-space variant). The final sequence
$$
1 \leftarrow F(1) \leftarrow F^2(1) \leftarrow \cdots
$$
converges in the category of metric transition systems under mild
size/accessibility conditions to the terminal coalgebra. Each $F^N(1)$ is
(essentially) the depth-$N$ RCS realized by P0's finite-depth induction; the
limit is $\mathrm{RCS}^\infty$.

Reference: Rutten (2000), "Universal coalgebra: a theory of systems," TCS 249;
Jacobs (2017), "Introduction to Coalgebra"; Adámek (1974) on terminal
coalgebras.

### 3.5 Functorial stability-budget transport

Given the commutativity of $V$ and $H$ (Theorem T5), Paper 5 would define
**budget-preserving functors**: functors on $\mathbf{RCS}$ that bound the
degradation in $\lambda_i$ across objects. Formally, a functor $F$ is
$\delta$-budget-preserving iff for every $\Sigma$, $F$ maps margin $\lambda_i$
to margin $\geq \lambda_i - \delta$.

### 3.6 Symmetric monoidal structure (optional, for composition)

Horizontal composition is a monoidal product; vertical composition is a
different monoidal product. Whether $\mathbf{RCS}$ is symmetric-monoidal,
closed, compact-closed, etc., determines which composition laws hold
automatically and which require proof.

Reference: Fong & Spivak, "Seven Sketches in Compositionality"; Baez–Stay,
"Physics, topology, logic and computation: a Rosetta Stone."

### 3.7 Higher structure — only if needed

If the $\varepsilon$-morphism 2-cells turn out to be load-bearing, Paper 5
would need to work in a 2-category or bicategory setting. This is the single
biggest cost multiplier in the paper; it should only be invoked if a target
theorem (T5 in particular) genuinely requires it.

---

## 4. Prerequisites (Papers That Must Come First)

Paper 5 cannot precede the following; it *builds on* their results by adding a
categorical framing.

### 4.1 P0 (Foundations) — **must stay unchanged**

P0 is the authoritative finite-induction framework. Every theorem P0 proves
about depth-$N$ hierarchies must remain provable from the P0 predicate $P(N)$,
without reference to any Paper 5 machinery. Paper 5 is additive; P0 is load-
bearing for every downstream paper and every Life implementation.

### 4.2 P6 (Horizontal Composition)

Paper 5 would formalize "vertical × horizontal functorial composition"
(Theorem T5). P6 must exist first so that the horizontal stability theorem has
a concrete statement to categorify. Until P6 is written, T5 has no subject.

### 4.3 P7 (Thermodynamic Limits) — *possibly*

Some Paper 5 theorems (T7 impossibility bounds tied to physical resources)
require P7's physical grounding. If Paper 5 only pursues T1–T5, P7 is not a
strict prerequisite; if T7 is a central result, P7 must be in place.

### 4.4 P2 (EGRI) / P3 (Observers) / P4 (Fleet)

These provide the instantiation catalogue Paper 5 would reason categorically
*about*. They must be fleshed out beyond their current state if Paper 5 is to
transport stability margins across them (T3).

---

## 5. Example: Bisimulation of Dreamer vs V-JEPA as L0 World Models

Concrete walkthrough of how Paper 5 machinery would apply. This example is
chosen because Dreamer and V-JEPA are both widely-cited L0 world-model
architectures, they are not obviously equivalent, and a rigorous bisimulation
statement about them would be a genuinely useful research result.

### 5.1 What we want to state

$$
\mathrm{Dreamer}_{\text{L0}} \;\equiv_\varepsilon\; \mathrm{V\text{-}JEPA}_{\text{L0}}
\quad\text{under observation metric } d \text{ at task distribution } \mathcal{T}.
$$

### 5.2 The bisimulation relation $R$

Both systems maintain a latent state $z$ predicting future observations.
$R \subseteq Z_{\text{Dreamer}} \times Z_{\text{V-JEPA}}$ would relate latent
states whose decoded predictions over a horizon $H$ agree within $\varepsilon$
on a fixed distribution of observation sequences $\mathcal{T}$.

Concretely: $(z_1, z_2) \in R$ iff for every sample trajectory $\tau \in \mathcal{T}$,
$$
\mathbb{E}_\tau \big[\, d\big(\mathrm{Decode}_{\text{Dreamer}}(z_1, \tau),\, \mathrm{Predict}_{\text{V-JEPA}}(z_2, \tau)\big) \,\big] \leq \varepsilon.
$$

### 5.3 Observation metric

Task-dependent. For video-prediction tasks, $d$ is feature-space L2 distance on
a frozen encoder (LPIPS-style). For planning tasks, $d$ is a reward-distance
proxy (max over same-observation reward gap).

### 5.4 Realistic $\varepsilon$

On standard benchmarks, probably **task-dependent and non-trivial**. Existing
empirical comparisons put Dreamer-V3 and V-JEPA within 10–25% on most
out-of-distribution video prediction tasks. A realistic $\varepsilon$ statement
might be: "equivalent to within 0.18 LPIPS on BAIR-pushing, within 0.32 on
Something-Something-v2, and not equivalent on tasks requiring contact
dynamics."

### 5.5 Tractable verification path today

Empirical: measure $\mathbb{E}_\tau[d(\cdots)]$ on held-out test trajectories.
This is what benchmark papers already do informally. Paper 5 would frame it as
a bisimulation-estimation problem, with confidence bounds from finite-sample
concentration.

Symbolic: out of reach today. Neither Dreamer nor V-JEPA has a clean closed-form
latent dynamics; both are deep networks. Symbolic bisimulation would require
either (a) neural-network abstraction to a symbolic form, or (b) sound
interval-based analysis à la Marabou/α,β-CROWN — currently intractable at the
relevant scale.

### 5.6 What Paper 5 would contribute

Paper 5 would **not** run the empirical benchmark (that's engineering work).
What Paper 5 would do is:
1. Formalize the statement "$\mathrm{Dreamer} \equiv_\varepsilon \mathrm{V\text{-}JEPA}$" as a well-typed theorem in the RCS category.
2. Prove that *if* the statement holds at L0, *then* any L1 RCS built on top of either world model inherits $\varepsilon' = g(\varepsilon, L_\Pi)$-equivalence.
3. Give rigorous content to the intuition that "these two are basically the same architecture."

The verification remains empirical; the semantics become rigorous. That is the
point of Paper 5: not to replace empirical science with proofs, but to give
empirical claims a formal framework they can live in.

---

## 6. Trigger Conditions for Writing Paper 5

Six concrete scenarios. Until at least one fires, the paper stays dormant.

### T1 — Fundamental limits need proving

**What it looks like.** Someone (you, a collaborator, a reviewer) needs to
prove a statement of the form: *"no RCS at depth $D$ with compute budget $C$
can simultaneously achieve horizon $H$, latency $L$, and stability margin
$\lambda$."* Universal quantification over architectures is non-optional for
this class of claim.

**How to recognize.** A research question whose honest answer is "we don't
know if this is a property of our specific design or a fundamental limit" and
whose resolution would change a deployment decision.

**Decision criterion.** Would the answer actually affect what you build? If a
"no" answer would cancel a development path worth $>\$50k$ of engineering,
Paper 5 pays for itself.

### T2 — Formal verification at scale (regulated deployment)

**What it looks like.** Life or a derivative needs deployment in a regulated
domain — medicine (FDA, MHRA), aviation (FAA, EASA), financial oversight
(SEC), critical infrastructure, or military applications. Regulators require
*semantic* correctness proofs, not just engineering tests.

**How to recognize.** A concrete regulator asks: "show me the formal semantics
of your control stack." Paper 5 + a Lean/Coq formalization is what you hand
them.

**Decision criterion.** Is there a $>\$10M$ market contingent on passing
certification? If yes, Paper 5 is infrastructure investment, not research.

### T3 — Bridge to adjacent physics / quantum / thermodynamics fires

**What it looks like.** Categorical agent theory starts producing predictions
that touch Bekenstein bounds, Landauer's principle, or quantum-advantage
regimes. This is adjacent to P7's agenda but sharper: if the categorical
framing *enables* a prediction P7 cannot make alone, Paper 5 is earning its
keep.

**How to recognize.** A specific claim of the form "quantum RCSs admit
compression factor $\alpha$ that classical RCSs do not" emerges from the
category-theoretic analysis.

**Decision criterion.** Is the prediction testable with forthcoming (5–10yr)
hardware? If yes, Paper 5 is first-mover positioning.

### T4 — Academic trajectory commits to RCS as foundational theory

**What it looks like.** You (or a derivative researcher) pursue RCS as a core
contribution to AI theory — PhD thesis, senior research role, long-term lab
affiliation. Paper 5 becomes the natural apex paper that grounds the series.

**How to recognize.** A hiring committee, thesis committee, or grant panel
asks: "what is the mathematical foundation of this research program?" The
answer "finite-depth induction in a 7-tuple framework" is correct but does not
position RCS as a foundational contribution. Paper 5 does.

**Decision criterion.** Is RCS the terminal contribution of your research
career, or one project among many? If terminal, Paper 5 is the capstone.

### T5 — Competing framework publishes categorical foundations

**What it looks like.** A group (DeepMind, FAIR, MIRI, Anthropic research,
academic lab) publishes a rival categorical framework for autonomous AI agents
— e.g., "Categorical Agents" or "A Functor Semantics for World Models." RCS
now either responds or concedes the theoretical ground.

**How to recognize.** A paper citing Baez, Fong–Spivak, or Rutten *together
with* agent-architecture case studies appears on arXiv.

**Decision criterion.** Does the competing framework make RCS look
ad-hoc by comparison on concrete case studies? If yes, Paper 5 becomes
defensive necessity, and response-time matters (6–12 months maximum).

### T6 — Industrial equivalence requirements (certification)

**What it looks like.** A standards body (ISO, IEEE, NIST) or industrial
consortium requires provable equivalence between agent architectures as a
certification prerequisite. "Architecture A is $\varepsilon$-equivalent to
reference architecture R" becomes a contractual / regulatory statement.

**How to recognize.** A draft standard (e.g., ISO/IEC DIS ... on AI agent
safety) references bisimulation or formal equivalence in its requirements.

**Decision criterion.** Is RCS positioned to be one of the reference
architectures in such a standard? If yes, Paper 5 is regulatory
infrastructure.

---

## 7. Verification Hierarchy (What Is Provable Today at Each Level)

Five levels of equivalence claim about agent architectures, each stronger than
the last. For each: **what's verifiable today**, **what Paper 5 machinery would
add**, and **cost–benefit**.

### L1 — Benchmark equivalence

**Today.** Run both architectures on a shared benchmark suite (ARC-AGI,
BabyAI, MuJoCo, HumanEval, SWE-Bench), compare aggregate scores. Standard
empirical ML practice.

**What Paper 5 adds.** Nothing directly. L1 is empirical; Paper 5 is formal.

**Cost–benefit.** High value, low cost. Already done by benchmark leaderboards.
Paper 5 adds no value here.

### L2 — Ablation decomposition

**Today.** For each architecture, systematically ablate components (remove L3,
replace $h$ with identity, etc.) and measure performance delta. Produces a
component-importance profile.

**What Paper 5 adds.** A categorical framework for comparing ablation profiles:
"architecture $A$'s ablation-response functor is $\varepsilon$-equivalent to
architecture $B$'s." Would let you say *which components do the same work*
across architectures.

**Cost–benefit.** Medium value, medium cost. Worth it if systematic ablation
becomes a standard research output.

### L3 — Functional equivalence (input–output)

**Today.** Feed both architectures the same input stream, measure output
divergence over a task distribution. Equivalent to a black-box bisimulation
test under a chosen metric.

**What Paper 5 adds.** Rigorous bisimulation semantics (§5.2–5.4 above),
concentration bounds on the empirical $\hat\varepsilon$, transfer to
downstream RCS layers (T3).

**Cost–benefit.** High value, high cost. This is the level where Paper 5
machinery genuinely earns its keep: it upgrades what is currently an informal
engineering comparison into a theorem.

### L4 — Empirical bisimulation (relation identification)

**Today.** Hard. Requires identifying a witness relation $R$ between state
spaces, then certifying the bisimulation conditions empirically. A few
specialized cases exist (linear-Gaussian systems, finite MDPs); general neural
systems are out of reach.

**What Paper 5 adds.** The definition and existence conditions for $R$;
sample-complexity bounds on verifying $R$ from trajectory data; the projection
theorem showing $R$ at L0 lifts to $R^+$ at L1.

**Cost–benefit.** High value *for specific architectures* (those with
tractable latent structure), low value for black-box deep networks.

### L5 — Symbolic bisimulation (sound verification)

**Today.** Out of reach for non-trivial agent systems. Marabou-style
abstraction verification works for bounded properties of small networks;
bisimulation of two large networks is far beyond current tooling.

**What Paper 5 adds.** The formal semantics that a future symbolic verifier
would target. The Lean/Coq formalization of Paper 5's definitions *is* the
specification a symbolic verification tool would need to satisfy.

**Cost–benefit.** High long-term value (this is the only level that survives
in regulated deployment), extremely high short-term cost. Paper 5 writes the
spec; actually building an L5 verifier is a multi-year project in its own
right.

---

## 8. Estimated Cost and Deliverables

Realistic (not promotional) estimate for writing Paper 5.

### 8.1 Technical depth required

- **PhD-level category theory.** Specifically: bicategories, terminal
  coalgebras, approximate bisimulation, categorical probability, symmetric
  monoidal categories. This is beyond the typical ML/control researcher.
- **Control theory.** Lyapunov analysis, switched systems, singular
  perturbation, robust control. Already present in P0–P6.
- **Computer science.** Coalgebraic logic, metric semantics, denotational vs
  operational semantics. Touched in P2 (EGRI); Paper 5 would deepen.
- **Honest statement.** If no coauthor brings the category-theoretic
  expertise, the paper will take 2–3× longer and risk technical errors that
  referees will catch.

### 8.2 Page count

~30–40 pages (double-column IEEE) or ~50–60 pages (single-column LMCS/LICS).
This is substantially longer than P0–P4 (~12–20 pages each) because of
categorical overhead: every definition requires setup, every theorem requires
stating morphism-preservation properties, every example requires constructing
the witness functor.

### 8.3 Timeline

**6–18 months of focused research**, depending on:
- coauthor availability (category theorist + control theorist, see below)
- whether the Lean/Coq formalization is attempted (adds 3–6 months)
- how many of T1–T8 are attempted (T1+T3+T5 is a minimum viable paper; all
  eight is a thesis-scale effort)

### 8.4 Possible coauthors

People whose research trajectory overlaps Paper 5's scope (names illustrative,
not endorsements or commitments):
- **Category-theoretic control.** John Baez (UCR), Brendan Fong (Topos),
  David Spivak (MIT), Paolo Perrone (Oxford).
- **Bisimulation / approximate bisimulation.** Antoine Girard (CentraleSupélec),
  George Pappas (Penn), Prasad Sistla (UIC).
- **Categorical probability / coalgebra.** Tobias Fritz (Innsbruck),
  Bart Jacobs (Nijmegen), Jan Rutten (CWI, emeritus).
- **Agent-theoretic contact.** Rao (Purdue, on active inference), Kaelbling
  (MIT, on planning). More of a sanity check than a primary coauthor.

Best-case team: 1 senior category theorist + 1 senior control theorist +
1 primary author (you or a PhD student) driving the RCS-specific content.

### 8.5 Venue

Primary candidates:
- **LICS** (Logic in Computer Science) — top theoretical venue, good fit for
  coalgebraic / bisimulation content.
- **POPL** (Principles of Programming Languages) — less obvious fit but has
  published agent-semantics papers (Voevodsky, Jacobs).
- **Applied Category Theory (ACT)** — perfect topical fit, smaller audience.
- **Logical Methods in Computer Science (LMCS)** — full-journal option,
  longer format acceptable, open-access.
- **CDC** (Conference on Decision and Control) — control-theory audience, but
  would require repositioning the paper toward the control-side contributions.

Secondary (survey / tutorial): SIGACT News, Notices of the AMS.

Honest assessment: LICS or LMCS is the right target. CDC audience will not
engage with coalgebraic content; ACT audience will appreciate it but the
paper's scope is broader than typical ACT submissions.

### 8.6 Required artifacts

Beyond the paper:
- **Lean 4 or Rocq (Coq) formalization** of the core definitions (RCS
  category, $F$ endofunctor, bisimulation relation, main theorems T1 and T3
  minimum). Without this, Paper 5 reads as "proof sketches that nobody
  machine-checked"; with it, Paper 5 reads as a specification.
- **Python/Rust harness** extending the P0 proof tests to verify the
  categorical-to-inductive projection at $N = 1, 2, 3, 4$.
- **Case-study repository** working out §5 (Dreamer vs V-JEPA) and at least
  one more pair empirically, with confidence intervals on $\varepsilon$.
- **Updated `data/parameters.toml`** if new categorical-margin parameters are
  introduced.

### 8.7 Go / no-go budget estimate

Assuming a senior researcher at ~$300k all-in and a PhD student at ~$75k:
- Minimum viable paper (T1, T3, T5 only; no Lean): ~$150k researcher-time.
- Full paper (T1–T6 + Lean formalization): ~$500k researcher-time, 18 months.
- Thesis-scale treatment (T1–T8 + Lean + case studies): ~$1.5M, 3 years.

These are direct labor; add infrastructure, conference travel, referee review
cycles.

---

## 9. What NOT to Include

Scope guardrails. Paper 5 is **not**:

1. **A revision of P0.** P0's finite-depth induction is the authoritative
   foundation. Paper 5 adds categorical machinery on top; it does not touch
   P0's proof structure or claims. The D2 refactor (dropping
   `def:rcs-endofunctor`) was correct and stays.
2. **A survey.** Not "the state of category-theoretic approaches to agent
   systems." Paper 5 is a specific original contribution defining the RCS
   category, proving T1–T8 (or some subset), and connecting RCS to existing
   categorical probability / coalgebra.
3. **A complete category-theoretic framework for all of agent theory.** Scope
   is RCS bisimulation, composition, and approximate equivalence. Active
   inference, LLM semantics, tool-use formalisms, embodied cognition — all
   out of scope.
4. **Engineering-focused.** Paper 5 is pure theory. Implementation work
   (improving Life, new Rust crates, new benchmarks) is explicitly downstream
   and gated on specific theorem statements.
5. **A unification with P6/P7.** Paper 5 *consumes* P6/P7 results to
   categorify them. It does not re-derive horizontal composition or
   thermodynamic limits.
6. **An attempt to re-prove Theorem VI via coinduction.** That would be
   technically possible but gains nothing and duplicates work. Finite
   induction is the right tool for Theorem VI.

If Paper 5 starts drifting into any of these, scope-cut aggressively.

---

## 10. Dormancy Policy

Until a trigger in §6 fires, this document stays dormant. Maintenance cadence:

**Annual review (next: 2027-04-18).** Update:
- Any new RCS research (P6, P7, L2/L0 estimators, Life integration tests) that
  would change the paper's preconditions or open new theorem candidates.
- Any new triggers that emerged in the ambient research landscape.
- Any new results from adjacent fields that would reduce Paper 5's cost
  (e.g., a new Lean library for bisimulation; a new categorical-probability
  textbook; a competing paper that does part of the work).
- Status of each trigger in §6: fired / not fired / near-fire / decisively
  inapplicable.

**Event-driven updates.** When any of the following happen outside the annual
cadence:
- A rival group publishes categorical foundations for agent systems (trigger
  T5): update this document within 2 weeks with their approach and how Paper 5
  would differentiate.
- A regulator or standards body cites bisimulation for AI certification
  (trigger T6): update scope section with their specific requirements.
- A P6 or P7 draft lands: update §4 prerequisites and §2 theorem catalog
  accordingly.

**Retirement.** If by 2030 no trigger has fired and the research program has
moved elsewhere, mark this document `status: retired` and archive. The option
has expired; the artifact remains as historical record of what was considered.

---

## 11. Related Adjacent Work

Reading list for anyone reactivating this scope document. Organized by
category. Not exhaustive; focused on the most load-bearing references.

### 11.1 Approximate bisimulation (core for T1, T3, §5)

- **Girard, A. & Pappas, G. J. (2007).** "Approximation metrics for discrete
  and continuous systems." *IEEE Trans. Automatic Control* 52(5), 782–798.
  *The foundational paper. If you read only one reference, read this.*
- **Girard, A. (2008).** "Synthesis using approximately bisimilar abstractions."
  HSCC.
- **Pola, G., Girard, A., Tabuada, P. (2008).** "Approximately bisimilar
  symbolic models for nonlinear control systems." *Automatica* 44(10).
- **Tabuada, P. (2009).** *Verification and Control of Hybrid Systems: A
  Symbolic Approach.* Springer. *Standard textbook on symbolic bisimulation.*

### 11.2 Categorical probability (core for T8)

- **Fritz, T. (2020).** "A synthetic approach to Markov kernels, conditional
  independence and theorems on sufficient statistics." *Advances in Mathematics* 370.
- **Baez, J. C. & Fritz, T. (2014).** "A Bayesian characterization of relative
  entropy." *Theory and Applications of Categories* 29.
- **Perrone, P. (2024).** *Starting Category Theory.* Textbook (World Scientific).
- **Cho, K. & Jacobs, B. (2019).** "Disintegration and Bayesian inversion via
  string diagrams." *Mathematical Structures in Computer Science* 29(7).

### 11.3 Categorical control (core for category of RCSs)

- **Baez, J. C. & Erbele, J. (2015).** "Categories in Control." *Theory and
  Applications of Categories* 30. *Already cited in P0; re-read for Paper 5.*
- **Fong, B. (2015).** "Decorated cospans." *Theory and Applications of
  Categories* 30.
- **Libkind, S. et al. (2022).** "Operadic modeling of dynamical systems."
  *Applied Category Theory* proceedings.

### 11.4 Coalgebra and coinduction (core for T4, T6)

- **Rutten, J. J. M. M. (2000).** "Universal coalgebra: a theory of systems."
  *Theoretical Computer Science* 249(1). *The coalgebraic foundation.*
- **Jacobs, B. (2017).** *Introduction to Coalgebra: Towards Mathematics of
  States and Observations.* Cambridge. *Textbook treatment.*
- **Cîrstea, C., Kurz, A., Pattinson, D., Schröder, L., Venema, Y. (2011).**
  "Modal logics are coalgebraic." *Computer Journal* 54(1).
- **Hasuo, I., Jacobs, B., Sokolova, A. (2007).** "Generic trace semantics via
  coinduction." *Logical Methods in Computer Science* 3.

### 11.5 Symmetric monoidal / compositional (supporting §3.6)

- **Abramsky, S. & Coecke, B. (2004).** "A categorical semantics of quantum
  protocols." *LICS 2004.* *Template for bicategorical semantics.*
- **Fong, B. & Spivak, D. I. (2019).** *An Invitation to Applied Category
  Theory: Seven Sketches in Compositionality.* Cambridge. *Accessible entry
  point.*
- **Spivak, D. I. (2014).** *Category Theory for the Sciences.* MIT Press.
- **Selinger, P. (2011).** "A survey of graphical languages for monoidal
  categories." In *New Structures for Physics,* Springer LNP 813.

### 11.6 Agent-adjacent categorical work

- **Smithe, T. S. C. (2023).** "Compositional active inference."
  *Compositionality* journal. *Category-theoretic active inference — directly
  relevant to any bridge with FEP/AIF communities.*
- **Capucci, M., Gavranović, B., Hedges, J., Rischel, E. F. (2021).**
  "Towards foundations of categorical cybernetics." *ACT 2021.*
- **St Clere Smithe, T. (2024).** "Open dynamical systems as coalgebras for
  polynomial functors." Various recent work.

### 11.7 Foundational (just so they're on the list)

- **Mac Lane, S. (1998).** *Categories for the Working Mathematician.*
  Springer, 2nd ed. *The standard reference.*
- **Riehl, E. (2017).** *Category Theory in Context.* Dover. *Good modern
  alternative to Mac Lane.*
- **Lurie, J. (2009).** *Higher Topos Theory.* *Only if higher/∞-category
  material becomes load-bearing — probably not, but listed for completeness.*

---

## Appendix A — Checklist for future self

Before writing Paper 5, confirm:

- [ ] At least one §6 trigger has fired, documented, and the decision
      criterion satisfied.
- [ ] P6 has a complete draft (not just README outline).
- [ ] (If T3-style theorems are in scope) P7 has at least an outline-level
      draft with defined quantities.
- [ ] A category-theorist coauthor is committed (not just "interested").
- [ ] Budget for 6–18 months of focused work is secured.
- [ ] Annual review section §10 has been updated within the last 90 days.
- [ ] This document has been re-read end-to-end for drift against current P0.

If any of the above is unchecked, the paper is not ready to start. Update this
document with what's missing and stop.

---

## Appendix B — One-line summary

> **Paper 5 would bolt an optional categorical layer onto P0, enabling
> bisimulation-based equivalence statements, cross-architecture transport of
> stability margins, and coinductive self-reference — none of which P0 attempts
> or needs. It is dormant until a trigger in §6 makes the investment worth it.**
