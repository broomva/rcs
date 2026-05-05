# Eclectic Systems: Communication Strategies, Knowledge Substrate Articulation, and Infrastructure Audit

**Date:** 2026-05-05
**Trigger:** PR #42 swarm live result revealed that aggregation strategy dominates substrate sharing by ~75× in effective performance. User asked us to research the broader space and audit infrastructure constraints.

## Executive summary

Three things are true after this research pass:

1. **The 2025-2026 literature converges on a clear answer** to our PR #42 finding: simple majority voting is the wrong default for heterogeneous LLM ensembles. Verifier-weighted, confidence-weighted, and second-order-correlation-aware aggregation strategies dominate by 4-15% absolute. Our SwarmL0Plant should be upgraded.

2. **Our knowledge substrate has the right shape but lacks formal stigmergic properties.** The blackboard pattern (Hayes-Roth 1985), Linda tuplespaces (Gelernter 1985), and CRDT-backed stigmergy (Oct 2025) all require *observable updates*, *deterministic convergence*, and *monotonic progress*. Our substrate has none of these formally — it has shared filesystem and best-effort semantics.

3. **The infrastructure binding constraint is RAM, not disk or compute.** 24 GB Apple M4 Pro caps us at ~14B local models. Disk at 48 GB free is tight but adequate. To test heterogeneous-model swarms locally we either need smaller models that fit together or hosted-API access for diversity.

## Section 1: Communication strategies in the 2025-2026 literature

### 1.1 Mixture-of-Agents (MoA) — ICLR 2025 Spotlight

Wang et al. ([arXiv:2406.04692](https://arxiv.org/abs/2406.04692)). Layered architecture where each layer's LLMs receive prior layer's outputs as auxiliary context. Operates entirely through prompt interface — no weight surgery. Open-source MoA achieved 65.1% on AlpacaEval 2.0 vs GPT-4 Omni's 57.5%.

**Two selection criteria identified as load-bearing:**
- **Performance metrics** — pick demonstrably-strong models per layer
- **Diversity considerations** — heterogeneous models contribute more than copies

**Mapping to microRCS:** the 4-level hierarchy (L0/L1/L2/L3) is a degenerate MoA where each "layer" has exactly one model, and the inter-layer contract is meta-control rather than answer refinement. We have the diversity dial via `--model-l0-l1` vs `--model-l2-l3`, but we don't iterate refinement.

### 1.2 Graph-of-Agents (GoA) — 2026

[arXiv:2604.17148](https://arxiv.org/abs/2604.17148). Critique of MoA's heavy intra-layer communication overhead and lack of model-relationship structure. Proposes **relevance-aware bidirectional message-passing** — source-to-target plus target-to-source feedback. Removing the feedback direction drops MMLU-Pro by 1.12 and GPQA by 1.95.

**Mapping to microRCS:** PR #40's SwarmL0Plant has *no* peer-to-peer communication — peers run independently, output gets aggregated. GoA suggests adding inter-peer message passing in v1.

### 1.3 Static DAG approaches: MacNet, GPTSwarm

Agents as nodes in fixed DAGs. Communication topology is part of the experimental design rather than a runtime decision. **microRCS is exactly this** — vertical static DAG with depth=4.

### 1.4 Dynamic activation: DyLAN

Computes Agent Importance Score via forward-backward peer-rating propagation; coordinates agents through a temporal feed-forward communication network. **The shadow-eval hook in PR #23 is a primitive form of this** — it scores candidate L2 mutations before commit. But we don't propagate scores backward to influence future agent selection.

### 1.5 Blackboard architectures — revival in 2025

Three concurrent papers in 2025:

- [arXiv:2507.01701](https://arxiv.org/abs/2507.01701) "Exploring Advanced LLM Multi-Agent Systems Based on Blackboard Architecture" (July 2025) — blackboard-based MAS competitive with SOTA static and dynamic MASs while spending fewer tokens.
- [arXiv:2510.01285](https://arxiv.org/abs/2510.01285) "LLM-Based Multi-Agent Blackboard System for Information Discovery in Data Science" (Sept 2025) — central agent posts requests; subordinates volunteer based on their capabilities. **Outperforms RAG and master-slave by 13–57% relative**.
- [arXiv:2510.18893](https://arxiv.org/html/2510.18893) "CodeCRDT" (Oct 2025) — CRDT-based stigmergic coordination for LLM agents.

**Critical formalization from CodeCRDT:** the substrate must satisfy three properties for indirect coordination to converge:
1. **Observable updates** — agents can subscribe to state changes
2. **Deterministic convergence** — all agents eventually observe consistent state
3. **Monotonic progress** — no rollbacks invalidating completed work

CodeCRDT's contribution is bringing CRDT semantics to LLM agents because traditional stigmergy is "best-effort" with no concurrent-write guarantees.

### 1.6 Beyond Majority Voting — Oct 2025

[arXiv:2510.01499](https://arxiv.org/abs/2510.01499). Standard majority voting "fails to consider latent heterogeneity and correlation across models." Authors propose:
- **Optimal Weight (OW)** — weight by accuracy priors (first-order info)
- **Inverse Surprising Popularity (ISP)** — weight by inverse of expected agreement (second-order info, captures correlation)

Provably mitigates inherent limitations of majority voting under mild assumptions.

### 1.7 Optimal LLM + PRM aggregation — Oct 2025

[arXiv:2510.13918](https://arxiv.org/html/2510.13918). Process Reward Model (PRM) verifier-weighted Best-of-N is suboptimal: pure majority voting (ignoring the PRM) often beats PRM-guided BoN. Authors derive principled weights combining LLM consensus signal **and** external verifier scores. Confidence-Informed Self-Consistency (CISC) variant uses model self-confidence as weight.

**This is directly applicable to PR #42.** We have a verifier (`task.verify`) — we can weight peer submissions by their score. The literature predicts this beats both strict-majority and best-of-N.

### 1.8 Adaptive Heterogeneous Multi-Agent Debate (A-HMAD) — Nov 2025

[Springer, J King Saud Univ](https://link.springer.com/article/10.1007/s44443-025-00353-3). Critiques homogeneous-agent simple-majority debate; introduces **consensus optimizer that learns to weight each agent's vote according to its reliability and the confidence of its arguments**. Reports 4-6% absolute accuracy gain and >30% reduction in factual errors.

### 1.9 The Consensus Trap

[arXiv:2604.17139](https://arxiv.org/html/2604.17139). Response-level consensus mathematically collapses when corrupted agents form a local majority. Suggests token-level collaboration. **Not directly relevant to our H1 thesis test (no adversarial scenario), but worth flagging for future work.**

### 1.10 Debate or Vote?

[arXiv:2508.17536](https://arxiv.org/pdf/2508.17536). Empirical finding: in many tasks, simple majority voting accounts for most of the gain from multi-agent debate. Debate adds value mainly when agents have *task-specific personas*. **Suggests our future swarm experiments should bake in persona/role differentiation, not just temperature noise.**

## Section 2: Audit of microRCS knowledge substrate

### 2.1 What we have today

The substrate at `Workspace.path` consists of:

| Component | Path | Persistence | Sharing in swarm |
|---|---|---|---|
| `helpers/` | `<ws>/helpers/*.py` | Cross-run via `persist=True` | Shared across peers (PR #40 D3) |
| `memory/` (frontmatter graph) | `<ws>/memory/{concept,pattern,task}/*.md` | Cross-run via `persist=True` | Shared across peers (PR #40 D3) |
| `system_rules.jsonl` | `<ws>/memory/system_rules.jsonl` | Cross-run, disk-persisted (PR #28) | Shared across peers (PR #40 D3) |
| `scratch/` | `<ws>/scratch/` | Wiped per-task | Functionally isolated by sequential-execution wipe (PR #40 D3) |
| Event log | `<ws>/.rcs/events.jsonl` | Per-run, append-only | Per-peer (event log isolation) |

### 2.2 Stigmergy-property audit

Per CodeCRDT's three required properties:

| Property | Status | Gap |
|---|---|---|
| **Observable updates** | ❌ missing | Filesystem doesn't push notifications. A peer can write a helper but its siblings don't know unless they re-scan. Currently moot since peers run sequentially in PR #40 v0; bites if peers run concurrently. |
| **Deterministic convergence** | ⚠️ partial | Sequential execution gives trivial convergence. Concurrent writes would race (no CRDT, no locking). |
| **Monotonic progress** | ⚠️ partial | `scratch/` wipes break monotonicity by design. `helpers/` and `memory/` are append-mostly but L2's `AppendSystemRule` overwrites; rollbacks possible if shadow-eval rejects. Not formally monotone. |

### 2.3 Stigmergic primitives we don't have

From the bio/swarm-intelligence literature, mature stigmergy includes:

| Primitive | What it does | Have it? |
|---|---|---|
| **Pheromone deposition** | Agent leaves a typed marker | ✓ via `helpers/` + `memory/` |
| **Pheromone evaporation** | Markers decay over time | ❌ missing — rules persist forever |
| **Pheromone strength** | Signal magnitude | ❌ missing — rules are boolean (present/absent) |
| **Provenance** | Which agent wrote what | ❌ missing — no per-rule attribution |
| **Signal types** | Different markers for different purposes | ⚠️ implicit via dir structure (concept/pattern/task) |
| **Quorum sensing** | Behavior change above density threshold | ❌ missing |
| **Field gradients** | Local intensity varies | ❌ missing |

The ASI:BUILD project ([Phase 5.2 issue](https://github.com/web3guru888/asi-build/issues/185)) is concurrently building exactly this for LLM agents — typed signals with `strength: 0.0–1.0`, `decay: float`, `ttl: seconds`, `agent_id` attribution. This is a sensible reference shape.

### 2.4 Articulation gaps

The substrate's *content* is well-specified (frontmatter schema, JSONL rules, Python helpers). The *protocol around it* is under-specified:

- No formal write-conflict resolution
- No subscription mechanism
- No staleness/freshness tracking
- No quality gating beyond shadow-eval at L2 (and that's a one-shot pre-commit check, not an ongoing fitness signal)
- No way to retire bad rules post-commit

## Section 3: Infrastructure audit — what's actually limiting us

### 3.1 Hardware

```text
RAM:    24 GB (Apple M4 Pro, Mac16,7)
Disk:   460 GB total, 48 GB free (89% full)
Models: gemma4:8b only (9.6 GB) — single Ollama model loaded at a time
```

**Binding constraint: RAM.** macOS baseline ~6-10 GB, gemma4-8B loaded ~13 GB → ~1-5 GB headroom. Implications:

- ✗ **32B local models** (qwen2.5-coder:32b ~20 GB) won't fit alongside macOS without thrashing. Even at Q4 quantization, marginal.
- ✓ **14B local models** (qwen2.5:14b ~9 GB Q4, qwen3:14b ~10 GB) fit fine but only *one at a time* in Ollama.
- ✗ **Heterogeneous local swarm** (multiple models loaded simultaneously) is impractical without unloading/loading between calls — adds 30-60s overhead per swap.
- ✓ **Heterogeneous swarm via API** is fine — Anthropic + OpenAI + Ollama can be mixed in a single run; budget-bound rather than RAM-bound.

### 3.2 Disk

48 GB free of 460 GB. Pulling another model uses 5-9 GB. Should clean up before pulling more:
- `~/.cache/microrcs-swe/` (SWE adapter caches) — could be GBs
- `~/.cache/uv/` — uv build cache
- `/tmp/microrcs-*` workspaces from prior runs

### 3.3 Memory (agent context window)

- gemma4 default 8K context, extends to 128K. Adequate.
- Anthropic models 200K. Plenty.
- Per-peer event log size grows with episode length. Currently 5-task episodes are fine.

### 3.4 Persistent state

✓ Cross-run persistence works (PR #28). Rules survive across runs at file level. Compounding mechanism is functional even if it didn't show measurable score effect (PR #28 result was null).

### 3.5 Environment / tool surface

- ✓ Bash + submit on agent side (mini-swe-agent style)
- ✓ Reasoner provider abstraction (Anthropic, OpenAI stub, Ollama working — PR #36)
- ✓ Workspace isolation via `Workspace.path` (per-run /tmp dirs)
- ✓ APFS COW for SWE adapter workspaces
- ✗ No first-class subscription mechanism on substrate writes
- ✗ No tool primitives beyond bash (no `python_eval`, `vector_search`, `web_search` as separate tools)
- ✗ No process-level isolation in the smoke (acceptable per spec; real isolation deferred to BRO-947 / sandbox-exec / Lima)

### 3.6 Verdict on constraints

| | Constraint | Severity |
|---|---|---|
| **Hardware** | 24 GB RAM caps local model size at ~14B | Medium — heterogeneous local swarm is hard |
| **Disk** | 48 GB free is tight | Low — cleanup buys headroom |
| **Memory (context)** | None | None — current models adequate |
| **Persistent state** | Mechanism works; no decay/provenance | Medium — substrate quality lever, not a blocker |
| **Environment** | No native subscription primitive on substrate | Medium — required for concurrent peer coordination |
| **Tool surface** | Bash-only (no first-class python/vector/web) | Low — bash composes everything; explicit tools would help capability ceiling |
| **API budget** | Exhausted | High — blocks frontier-tier experiments |

**The two real constraints are: (1) API budget for frontier-tier swarm experiments, and (2) absence of stigmergic protocol primitives (decay, provenance, observability) on the substrate.** Neither is fatal. Both are addressable.

## Section 4: Concrete next-step plan, priority-ordered

### 4.1 Tier 1 — cheapest, highest-leverage ($0, hours-of-work)

**A. Verifier-weighted aggregation upgrade for SwarmL0Plant.** Add a third aggregation strategy to `swarm_run.py`: run `task.verify(answer)` on each peer's submission, pick highest-scoring. ~30 LOC patch. Direct test of the literature claim ([arXiv:2510.13918](https://arxiv.org/html/2510.13918)) that verifier-weighted Best-of-N + consensus dominates both pure strict-majority and pure BoN.

**Predicted outcome:** at gemma4 × REFERENCE × N=3, verifier-weighted swarm should yield ≥0.60 (matching `pass@k=0.60` from PR #42) and likely higher, because tasks where multiple peers submit but only one is correct (e.g., code-bugfix with valid-but-buggy implementations) get correctly disambiguated by the verifier.

**B. Run swarm × k=1 (best-of-N) live to confirm `pass@k = 0.60` prospectively.** ~10 min wall, $0. Same driver, just `--k-quorum 1`. Confirms PR #42's retroactive observation as a real result.

**C. Add stigmergic primitives to substrate.** Three ASI-BUILD-style additions:
- `system_rules.jsonl` entries get `strength: float`, `ttl_episodes: int`, `peer_id: str`
- L2 hook reads strengths; rules below threshold are functionally muted
- A new "decay" pass at end of each epoch reduces `strength` by configurable factor

~80 LOC. Doesn't change behavior unless explicitly enabled (default rules use `strength=1.0, ttl=∞`).

### 4.2 Tier 2 — moderate cost, real signal ($0-50, days-of-work)

**D. Heterogeneous swarm via API mixing.** Mix `gemma4-local + claude-haiku-4-5 + claude-sonnet-4-6` as N=3 peers (or 2 local + 1 API) for the same task. Tests A-HMAD's claim that diversity > N copies of same model. Cost ≈ \$3-10 per condition.

**E. Pull a 14B model that fits alongside gemma4** — e.g., `qwen2.5-coder:14b` (~9 GB). Run swarm with one heterogeneous local pair (gemma4 + qwen2.5-coder), Ollama swapping models per peer call. Slow (~60s per swap) but free.

**F. Implement subscription/observability on substrate.** Use `watchdog` or filesystem event hooks to make writes to `helpers/` / `memory/` / `system_rules.jsonl` notify subscribed peers. Required for concurrent-peer coordination beyond v0's sequential-execution model.

### 4.3 Tier 3 — frontier-grade ($50+ or RAM-constrained, weeks)

**G. Multi-tier swarm bench.** swarm_flat × {Haiku, Sonnet, Opus} × verifier-weighted aggregation × 3 seeds × 4 instances. ~$60-200 depending on tier.

**H. Graph-of-Agents (GoA) implementation.** Add explicit peer-to-peer message-passing in `swarm_run.py` v2. Source→target plus target→source feedback per the 2026 paper. ~200 LOC. Tests whether feedback adds value beyond pure aggregation.

**I. CRDT-backed substrate.** Replace the filesystem-as-substrate with a Y.js/Automerge-equivalent CRDT (Python: `pycrdt`, `automerge-py`). Gives formal eventual consistency for concurrent peer writes. Required for true parallel swarm execution. ~1 week.

**J. BRO-947 v0.5 — extend perturbation to L1, L2.** Same shape as life PR #1090's L0 work. Closes construct-validity gap with paper's λᵢ.

## Section 5: The unifying picture

Three orthogonal axes of agent-control intervention now exist as testable code in this codebase:

1. **Vertical RCS** (microRCS today, PR #30+): hierarchical L0 ← L1 ← L2 ← L3. Verdict at proper power: null at the tails, hurts at Sonnet, directional+inconclusive at Opus.
2. **Horizontal Plexus** (PR #40 + #42): N peer agents at L0 sharing stigmergic substrate. Verdict from one live run: aggregation strategy dominates substrate sharing by ~75×.
3. **Modal Eywa** (PR #37 + #39): bash → python tool nudge for modality-native compute. Mechanism confirmed; magnitude unverified.

A future 2³ factorial — `{single, swarm} × {flat, full} × {language-only, +eywa-python}` × {Haiku, Sonnet, Opus} — would test all three axes against capacity. Cost: ~\$300-500 at Anthropic tier; ~\$0 at gemma4 with the caveats noted.

The literature suggests two more axes worth building:
4. **Aggregation strategy** (verifier-weighted, CISC, OW/ISP) — Tier 1 work item A
5. **Substrate protocol** (stigmergic primitives) — Tier 1 work item C

Adding axes 4 and 5 would give us the cleanest possible characterization of *which architectural choice actually pays off and under what conditions*.

## Sources

- [Mixture-of-Agents (arXiv:2406.04692, ICLR 2025 Spotlight)](https://arxiv.org/abs/2406.04692)
- [Graph-of-Agents (arXiv:2604.17148, 2026)](https://arxiv.org/abs/2604.17148)
- [Blackboard Architecture for LLM MAS (arXiv:2507.01701, July 2025)](https://arxiv.org/abs/2507.01701)
- [Multi-Agent Blackboard for Data Science (arXiv:2510.01285, Sept 2025)](https://arxiv.org/abs/2510.01285)
- [CodeCRDT — Stigmergic CRDT Coordination (arXiv:2510.18893, Oct 2025)](https://arxiv.org/html/2510.18893)
- [Beyond Majority Voting (arXiv:2510.01499, Oct 2025)](https://arxiv.org/abs/2510.01499)
- [Optimal LLM + PRM Aggregation (arXiv:2510.13918, Oct 2025)](https://arxiv.org/html/2510.13918)
- [A-HMAD (J King Saud Univ, Nov 2025)](https://link.springer.com/article/10.1007/s44443-025-00353-3)
- [The Consensus Trap (arXiv:2604.17139)](https://arxiv.org/html/2604.17139)
- [Debate or Vote? (arXiv:2508.17536)](https://arxiv.org/pdf/2508.17536)
- [Consensus Protocols Guide (Fastio, Feb 2026)](https://fast.io/resources/consensus-protocols-multi-agent-systems/)
- [ASI:BUILD Phase 5.2 stigmergic blackboard (GitHub)](https://github.com/web3guru888/asi-build/issues/185)
