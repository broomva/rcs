# microRCS — Swarm-RCS-L0 Experiment Design

**Status:** scaffold (spec + driver + tests; no live run)  •  **Date:** 2026-05-05
**Author:** Carlos Escobar (operator), Claude Opus 4.7 (implementing)
**Linear:** parent epic BRO-944 (this is a follow-up scaffold sub-issue)
**Predecessors:**
- `microrcs/THESIS_VALIDATION.md` — capacity sweep (PR #31), Eywa flag (PR #37), gemma4 bench (PR #36)
- `papers/p0-foundations/main.tex` — RCS 7-tuple Σ; vertical hierarchy L0..L3
- `research/entities/concept/` — Plexus / Pneuma horizontal substrate (concept, not yet implemented)

## TL;DR

Today, microRCS implements vertical recursion: a single L0 plant + one L1 + one L2 + one
L3. The H1 verdict is **non-monotone in capacity** (Haiku within noise, Sonnet hurts,
Opus directionally helps). Distinct from the vertical axis is the **horizontal axis** —
N peer agents sharing a stigmergic substrate, the architecture our `Plexus` design
targets but which has never been integrated with vertical recursion.

This spec scaffolds the **Swarm-RCS-L0** experiment: L0 is replaced with a swarm of
N=3 peer agents that share a workspace (`helpers/`, `memory/`, `system_rules`). The
experiment is a 2×2 factorial — `{single, swarm} × {flat, full}` — that asks whether
vertical recursion (L1+L2+L3) helps, hurts, or is neutral on top of a swarm-flat
baseline that already captures stigmergic learning.

**This PR ships only the spec + driver scaffold + unit tests.** It does NOT execute the
bench. Live runs are deferred to a follow-up so the design is reviewable and committable
before any spend.

## Why this question matters

The 4-tier H1 verdict (PR #31) demonstrated that vertical recursion's effect on
single-agent L0 is **tier-dependent and non-monotone**. The synthesis question now is
about the *shape* of L0 itself:

> Does vertical recursion (L1/L2/L3) help, hurt, or stay neutral when L0 is replaced
> with a swarm of N peers sharing the same workspace?

Three a-priori plausible outcomes, each scientifically informative:

| Outcome | What it would mean |
|---|---|
| **Swarm-flat ≈ swarm-full** (recursion neutral over swarm) | Stigmergy already captures most of recursion's value. Vertical recursion is *redundant* given a horizontal substrate. Plexus alone suffices; RCS Π hierarchy is the wrong abstraction at L0. |
| **Swarm-full > swarm-flat by Δ ≥ single-full−single-flat** (recursion amplifies on swarm) | Vertical and horizontal recursion are *complementary*. RCS hierarchy compounds with stigmergy. Strongest case for the full Plexus⊕Π architecture. |
| **Swarm-full < swarm-flat** (recursion hurts on swarm) | Vertical control over a horizontal substrate is *destabilizing*. The swarm's emergent consensus is brittle under L1/L2 mutation pressure — peers diverge, voting collapses. Important negative result. |

A fourth outcome is sociologically possible but theoretically uninteresting: both swarm
conditions ≈ single-flat, meaning N=3 doesn't change the floor either. The benchmark
choice (HARDER_SUITE) and N=3 are calibrated to make this last outcome unlikely; if it
happens, the experiment is reportable as a calibration miss, not a thesis test.

## Scope (IN this PR)

- **Spec doc** at `docs/superpowers/specs/2026-05-05-swarm-rcs-l0-design.md` (this file)
- **Driver scaffold** at `microrcs/scripts/swarm_run.py` (~200 LOC)
  - `SwarmL0Plant` wrapper around N independent `L0Plant` instances
  - `run_swarm_episode(task, peers)` — sequential peer execution + voting
  - 4-condition argument scaffold: `single_flat`, `single_full`, `swarm_flat`, `swarm_full`
  - Mock-driver mode for tests; live-driver path stubbed but not exercised
- **Unit tests** at `microrcs/tests/test_swarm_l0.py` (~180 LOC)
  - All mocked; pytest must stay green alongside the existing 202 tests
- **Makefile target** `make swarm-smoke` (skeleton; defers to live PR)

## Scope (OUT — follow-up PRs)

- The full bench (4 conditions × 3 seeds × HARDER_SUITE; ~$60 Opus, ~$15 Sonnet, ~$0 gemma4)
- Swarm-aware L1/L2/L3 controllers (this PR keeps them naïve — they observe the union
  of peer event streams as if it were one stream; cross-peer correlation is a v2 feature)
- Multi-process / true-parallel peer execution (sequential peer execution is sufficient
  for v0; threading is opt-in and gated behind a flag)
- Voting strategies beyond `answer_hash_majority` (Lyapunov-weighted, Borda count,
  cost-discounted majority — defer to follow-up if v0 results warrant)
- A `--swarm-n` flag on `microrcs.py` mainline (the swarm driver lives in `scripts/`,
  not the mainline CLI, by the same convention as `swe_smoke.py`)

## Architectural decisions (locked in this PR)

### D1. Voting strategy: simple `answer_hash_majority` with `k_quorum` config knob

**Decision:** v0 votes by `sha256(normalize(answer))`, picks the modal hash, and emits
the answer of the lowest-cost peer that voted for the modal hash. A `k_quorum` integer
≥ 1 controls how many peers must agree before the swarm submits; if no answer hash
reaches `k_quorum`, the swarm aborts with reason `swarm_no_quorum` and score 0.

**Default:** `k_quorum = ceil(N/2) + 1 = 2` for N=3 (strict majority).

**Considered and rejected for v0:**
- `lyapunov_weighted` — weight votes by `1 − V₀` of each peer's trace. Theoretically
  cleaner (peers that converged faster carry more weight) but requires V₀ extraction
  per-peer and adds a free parameter (the weighting curve). Defer to v1.
- `cost_discounted` — penalize expensive peers. Conflates economic and epistemic
  signals; harder to interpret. Defer.
- `defer_to_user_config` — overengineered for v0 and forces operators to make a choice
  before any signal exists.

**Tradeoff:** simple majority is the strongest, most interpretable null model. If
swarm-flat already beats single-flat under simple majority, that's the cleanest signal.
The cost: at N=3 with `k_quorum=2`, ties are impossible (3 hashes ≠ majority is the
only no-quorum case), but at higher N the parameter matters; we expose it for future use.

**Normalization function:** strip leading/trailing whitespace, collapse internal
whitespace, lowercase. Numeric answers ("13:18", "42", "7") are case-insensitive but
otherwise byte-equal across peers; this is sufficient for HARDER_SUITE.

### D2. L1 over a swarm: union-of-peer-streams, naïve aggregation

**Decision:** v0 L1Autonomic observes the **union** of all peer event streams (all
events from all peers in chronological order, treated as one stream). It does not
distinguish per-peer state. Mode switches it emits via `apply_decision_downward` are
applied **uniformly** to all peers (every peer gets the same mode at every L1 fire).

**Rationale:** the existing `L1Autonomic.observe(history)` consumes a flat list of
`RCSEvent`s. Making L1 swarm-aware (per-peer hysteresis, mode diversity, peer-specific
mode assignment) is a v2 feature that requires:
- a new state type (`SwarmAutonomicState` carrying per-peer V₀, modes, abort streaks);
- per-peer mode tracking inside `SwarmL0Plant`;
- a vote-on-modes decision rule (do peers vote on their next mode? does L1 unilaterally
  diverge them?).

That's a non-trivial design choice in its own right. v0 picks the simplest faithful
behavior: L1 sees more events (≈ N× the volume), thresholds may fire sooner, and
when they do, every peer switches mode in lockstep. This is the **null hypothesis** for
swarm-aware L1 — if v0 swarm-full helps, v2 per-peer L1 should help more; if v0 is
neutral, the design budget for v2 is justified.

**Tradeoff:** v0 may underestimate the upside of recursion-over-swarm because the
controller is not exploiting peer diversity. We accept this. The v0 result is a
**lower bound** on swarm-full's benefit.

### D3. Stigmergic substrate scope: shared `helpers/`, isolated `scratch/`, replicated `system_rules`

**Decision:** Each `SwarmL0Plant` constructs N peer plants whose `Workspace` instances
share the **same root directory** for `helpers/` and `memory/`, but each peer gets its
own `scratch/<peer_id>/` namespace. `system_rules.jsonl` is **shared** (all peers read
the same file at startup); rules appended by L2 (via `apply_decision_downward`) are
written once and visible to all peers on their next episode.

**The substrate (shared across peers):**
- `helpers/` — promoted Python helpers; if peer A writes one, peer B sees it next
  episode. This is the canonical "blackboard": peers leave traces in code, future peers
  build on them. **Read-write to all.**
- `memory/concept/`, `memory/pattern/`, `memory/task/` — durable knowledge graph;
  shared. **Read-write to all.**
- `memory/system_rules.jsonl` — system rules from L2's `AppendSystemRule` action;
  shared. **Read-write to all** (all peers persist; race-condition risk is bounded by
  sequential peer execution in v0).

**The peer-private state (effectively isolated by sequential execution):**
- `scratch/` — wiped between peers by the existing `Workspace.create()` semantics.
  In v0 (sequential peer execution), this gives **functional isolation**: peer N+1
  starts with clean scratch, so peer N's intermediate files never leak. Equivalent to
  per-peer namespacing for the v0 experiment. (For v2 true-parallel peers, scratch
  must be relocated to per-peer subdirs; gated under a `parallel=True` flag.)
- `TASK.md` — written per-peer at the start of each peer's `run_episode`. Sequential
  execution means there is never a race; the shared root's `TASK.md` reflects the
  current peer's task at all times during that peer's episode.
- `.rcs/events_peer_<id>.jsonl` — each peer has its own `EventLog` at a per-peer path
  under `.rcs/`. This preserves the existing per-correlation-id semantics and lets
  L1/L2/L3 (D2) merge them into one stream.

**Rationale:** this scope is the minimum that makes "swarm" meaningful — peers learn
from each other's helpers and memory. Sharing `scratch/` would create destructive
interference (peer A's `solution.py` overwritten by peer B mid-derivation), defeating
the experiment. Sharing `system_rules` is essential because rules ARE the L2 → L0
communication channel; if rules were per-peer, L2's `AppendSystemRule` would only
affect one peer, making `swarm_full` indistinguishable from `single_full × N`.

**Tradeoff:** sequential peer execution avoids race conditions in v0. If v2 introduces
true parallelism, `system_rules.jsonl` writes need a file lock or copy-on-write rotation
(e.g., `system_rules.jsonl.lock` flock, or numbered append-only segments). Not an issue
for the scaffold.

## File layout

```text
research/rcs/
├── docs/superpowers/specs/
│   └── 2026-05-05-swarm-rcs-l0-design.md    # NEW (this file)
├── microrcs/
│   ├── microrcs.py                           # UNCHANGED — existing L0Plant reused as-is
│   ├── scripts/
│   │   └── swarm_run.py                      # NEW (~200 LOC)
│   ├── tests/
│   │   └── test_swarm_l0.py                  # NEW (~180 LOC)
│   └── ...
└── Makefile                                  # ADD make swarm-smoke target
```

**Total new code:** ~480 LOC (~200 driver + ~180 test + ~100 spec excerpts in code comments).

## Component contracts

### `SwarmL0Plant` (in `scripts/swarm_run.py`)

Typed dataclass wrapping N peer `L0Plant`s + a shared workspace root:

```python
@dataclass
class SwarmConfig:
    n_peers: int = 3
    k_quorum: int = 2                       # must be ≤ n_peers
    voting: Literal["answer_hash_majority"] = "answer_hash_majority"
    seed_base: int = 0                      # peer i seeded with seed_base + i

    def __post_init__(self) -> None:
        if self.n_peers < 1:
            raise ValueError("n_peers must be ≥ 1")
        if not (1 <= self.k_quorum <= self.n_peers):
            raise ValueError("k_quorum must be in [1, n_peers]")


@dataclass
class PeerVerdict:
    peer_id: str
    answer: str | None
    answer_hash: str | None
    score: float
    cost_usd: float
    n_steps: int
    aborted_reason: str | None


@dataclass
class SwarmVerdict:
    chosen_answer: str | None
    chosen_hash: str | None
    quorum_reached: bool
    score: float                            # of the chosen answer (or 0.0 if no quorum)
    n_voters_for_chosen: int
    total_cost_usd: float
    per_peer: tuple[PeerVerdict, ...]
    aborted_reason: str | None              # "swarm_no_quorum" if !quorum_reached


class SwarmL0Plant:
    """A swarm of N L0 peers sharing a stigmergic substrate.

    Each peer has its own EventLog and scratch/ namespace, but helpers/ and
    memory/ (including system_rules.jsonl) are shared. Peers run sequentially
    in v0; voting picks the modal answer-hash with k_quorum threshold.
    """

    def __init__(
        self,
        peers: tuple[L0Plant, ...],
        cfg: SwarmConfig,
        substrate_root: Path,
    ): ...

    def run_swarm_episode(self, task: Task) -> SwarmVerdict: ...
```

### `run_swarm_episode` semantics

1. For each peer i in `[0, N)`, in deterministic order seeded by `cfg.seed_base + i`:
   a. Call `peer.run_episode(task)` → `EpisodeTrace`
   b. Capture `(peer.id, trace.final_answer, hash, score, cost, n_steps, aborted)`
2. Tally `answer_hash` frequencies across the N traces.
3. The modal hash with frequency ≥ `cfg.k_quorum` wins. Tie-break: highest summed score
   among the tied hashes. Second tie-break: lowest summed cost. Third tie-break:
   stable sort by hash bytes.
4. If no hash reaches `k_quorum`: emit `SwarmVerdict(quorum_reached=False, score=0.0,
   aborted_reason="swarm_no_quorum")`. Choose the modal hash anyway for telemetry but
   score it 0.0.
5. The chosen answer is the answer string of the **lowest-cost peer** voting for the
   chosen hash. Score is `task.verify(chosen_answer)` (re-verified, not mean of peer
   scores) — guarantees swarm score is a single deterministic verifier call.

### Driver `swarm_run.py` CLI

```text
python -m scripts.swarm_run \
    --condition swarm_full \                 # single_flat | single_full | swarm_flat | swarm_full
    --suite reference \                       # reference | harder
    --n-peers 3 \
    --k-quorum 2 \
    --model-l0-l1 claude-haiku-4-5 \         # uses microrcs reasoner factory
    --model-l2-l3 claude-opus-4-7 \
    --seed 42 \
    --out reports/swarm/                     # default reports/swarm-<run_id>/
    --dry-run                                 # mock reasoner, no API calls
```

The driver:
1. Loads the suite via existing `microrcs.SUITES[suite]`.
2. Builds peer plants (1 for `single_*`, N for `swarm_*`) with shared substrate.
3. Wraps in `L1`/`L2`/`L3` per condition (matching `microrcs.run`'s wiring) when
   condition is `*_full`.
4. Runs episodes, tallies pass^k, writes `metrics.json` matching the existing format
   so downstream analysis tools are unchanged.
5. Print live progress in the same `_emit_progress` style as `microrcs.run`.

### Hooks into existing iteration

The driver does NOT modify `microrcs.run()`. It builds a parallel iteration loop that
calls `SwarmL0Plant.run_swarm_episode(task)` instead of `L0Plant.run_episode(task)`.
The episode-trace shape is widened to `SwarmVerdict`, but downstream metrics (pass^3,
bootstrap CI) consume only `score` — a scalar — so the existing stat helpers
(`pass_pow_k`, `bootstrap_ci`) work unchanged.

## Testing strategy

All tests mock the `Reasoner` Protocol (no live API). Pattern lifted from existing
`tests/test_microrcs.py` (`_MockReasoner`, `_resp_submit`, `_resp_bash`).

**Required test cases** (in `tests/test_swarm_l0.py`):

1. `test_swarm_constructs_n_peers` — `SwarmL0Plant` with `n_peers=3` produces 3
   distinct peer `L0Plant` instances, each with its own `EventLog` and
   `scratch/<peer_id>/` namespace, all sharing the same `helpers/` + `memory/`
   directory tree.
2. `test_swarm_voting_picks_majority_hash` — 3 peers return answers `"42"`, `"42"`,
   `"43"`. Modal hash is `hash("42")` (count 2 ≥ k_quorum=2). Verdict's
   `chosen_answer == "42"`.
3. `test_swarm_quorum_threshold_honored` — 3 peers return all-different answers.
   With `k_quorum=2`, no hash reaches quorum → `quorum_reached=False`,
   `aborted_reason="swarm_no_quorum"`, `score=0.0`.
4. `test_swarm_quorum_unanimous` — 3 peers return all `"42"`. With `k_quorum=3`
   (unanimous), `quorum_reached=True`, score derived from verifier on `"42"`.
5. `test_swarm_lowest_cost_peer_breaks_tie_for_chosen_answer` — 2 peers tie on hash,
   peer A spent $0.05 and peer B spent $0.10 (both answered `"42"`). The chosen
   answer string is taken from peer A's trace.
6. `test_swarm_substrate_helpers_shared_across_peers` — peer 0 writes
   `helpers/foo.py`, peer 1 sees it via `helper_count() == 1` after peer 0's episode
   ends.
7. `test_swarm_scratch_wiped_between_peers` — peer 0 writes `scratch/work.txt` during
   its episode; before peer 1's episode begins, the swarm calls `Workspace.create()`
   again (or equivalently wipes `scratch/`), so peer 1 starts with clean scratch.
   (Sequential-execution functional isolation; for v0 the workspace is re-prepared
   per-peer rather than namespaced per-peer.)
8. `test_swarm_system_rules_shared` — `system_rules.jsonl` written by L2 via peer 0's
   `apply_decision_downward` is visible to peer 1's `_load_persisted_system_rules` on
   construction.
9. `test_swarm_config_validates_inputs` — `n_peers < 1` and `k_quorum > n_peers` both
   raise `ValueError`.
10. `test_swarm_episode_mocked_end_to_end` — full mocked episode: 3 peers, each with a
    `_MockReasoner` returning `_resp_submit("42")`, task verifies `"42"` to 1.0.
    Verdict score == 1.0, total cost is sum of per-peer costs.
11. `test_swarm_aborted_peer_does_not_crash_swarm` — 1 peer aborts (e.g., empty
    reasoner queue → fallback "done" answer); other 2 peers submit `"42"`. Swarm
    chooses `"42"` because it's the modal hash and quorum=2 reached.
12. `test_peer_verdict_serializable_to_dict` — `PeerVerdict` and `SwarmVerdict`
    round-trip through `dataclasses.asdict()` cleanly (used for `metrics.json`).

**Total expected test additions:** 12 tests, ~180 LOC. Combined with existing 202
tests = 214 tests passing.

## Open scoping decisions (NOT locked in this PR — recorded for follow-up)

- **OD1. Per-peer reasoner diversity.** Should peer i use a different model than peer
  j? (e.g., 2× Haiku + 1× Opus.) v0 uses identical reasoner config across peers. v2
  could test "weak swarm with one strong peer" — analogous to ensembles in classical
  ML. Cost-effective if cheap-peer agreement gates expensive-peer call.
- **OD2. Per-peer Eywa flag diversity.** Some peers with `eywa_python_hint=True`,
  others without. Tests whether modality-native compute hints diffuse via the shared
  substrate (peer A computes via python, peer B copies the helper, peer C learns).
- **OD3. Voting strategy v1.** Lyapunov-weighted voting if v0 results show high
  per-peer V₀ variance.
- **OD4. Swarm-aware L1.** Per-peer mode switching (D2 v2). Likely the single biggest
  v1 lever if v0 swarm-full ≈ swarm-flat.
- **OD5. Cross-condition seed reuse.** v0 reuses seeds across `single_*` and `swarm_*`
  conditions for paired-difference statistics. If swarm peers share a seed_base, peer
  0 of the swarm gets the same seed as the single agent — making `single_flat` a
  sub-trial of `swarm_flat` (peer 0 alone). This is desirable for paired analysis but
  introduces a confound: swarm performance with peer 0 randomized across seeds may
  differ from peer 0 fixed at seed_base. Document the chosen pairing in the live-run
  spec.

## Reproduction (live-run, deferred to follow-up PR)

```bash
# Smoke (mocked, no API):
make swarm-smoke

# Live (single seed, ~$5 Haiku, ~$30 Opus):
cd microrcs
python -m scripts.swarm_run \
    --condition swarm_flat,swarm_full,single_flat,single_full \
    --suite harder --n-peers 3 --k-quorum 2 \
    --seed 42 \
    --model-l0-l1 claude-haiku-4-5 --model-l2-l3 claude-opus-4-7

# Bench (3 seeds × 4 conditions, follow-up):
python -m scripts.swarm_run \
    --condition all --suite harder --n-peers 3 --k-quorum 2 \
    --seeds 42,1051,2060 \
    --model-l0-l1 claude-opus-4-7 --model-l2-l3 claude-opus-4-7
```

## Acceptance criteria (this PR)

- [ ] Spec doc lands at `docs/superpowers/specs/2026-05-05-swarm-rcs-l0-design.md`
- [ ] Driver scaffold lands at `microrcs/scripts/swarm_run.py`
- [ ] Tests land at `microrcs/tests/test_swarm_l0.py`, all 12 pass
- [ ] Existing 202 tests still pass alongside (214 total)
- [ ] `make swarm-smoke` target exists in root `Makefile` (skeleton; live behind a
      `--dry-run` arg by default to avoid accidental spend)
- [ ] No edit to `microrcs.py` mainline (existing L0Plant is reused via composition)
- [ ] Linear comment posted on BRO-944 with spec link + scaffold summary + open
      decisions

## Acceptance criteria (live-run follow-up, NOT this PR)

- [ ] Live `make swarm-smoke --no-dry-run` runs end-to-end on Haiku × 1 seed × 1 task
- [ ] Bench runs `swarm_flat`, `swarm_full`, `single_flat`, `single_full` × 3 seeds
      × HARDER_SUITE
- [ ] `metrics.json` schema matches existing format (downstream analysis unchanged)
- [ ] Headline result appended to `microrcs/THESIS_VALIDATION.md` with paired-Δ CI

## References

- Vertical RCS: `papers/p0-foundations/main.tex` § Definition 1, § Theorem 1
- Capacity sweep: `microrcs/THESIS_VALIDATION.md` § "Three-tier × 3 seeds × HARDER_SUITE"
- Eywa modality flag: PR #37, `microrcs/THESIS_VALIDATION.md` § "Eywa-style modality"
- gemma4 local L0: PR #36 (cost-zero swarm experiments are feasible)
- Plexus / Pneuma: `~/broomva/research/entities/concept/` (horizontal substrate concept)
- Stigmergy primer: Beer (1972), VSM; Quijano (2017) population dynamics; Ashby (1952)
  ultrastability via shared environment
