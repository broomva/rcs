"""Swarm-RCS-L0 driver scaffold.

Executes the 2x2 factorial {single, swarm} x {flat, full} for the
Swarm-RCS-L0 experiment. v0 wraps N peer L0Plant instances around a shared
stigmergic substrate (helpers/, memory/, system_rules.jsonl) and votes by
answer-hash majority with a configurable k_quorum threshold.

This is the SCAFFOLD ONLY. The CLI's --dry-run flag (default behavior under
make swarm-smoke) exercises the wiring with a mocked Reasoner so this
module can be reviewed and committed before any live spend.

Spec: ../../docs/superpowers/specs/2026-05-05-swarm-rcs-l0-design.md
Linear: BRO-944 (parent epic)

Usage:
    make swarm-smoke
    # or directly:
    python -m scripts.swarm_run --dry-run --condition swarm_full
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# Make sibling `microrcs.py` importable.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import microrcs as m  # noqa: E402


# === 1. Boundary contracts (typed dataclasses) ==============================
# Lessons from PR #32 SWE adapter: validate at construction, fail loud.

@dataclass
class SwarmConfig:
    """Configuration for one SwarmL0Plant.

    Validates inputs at __post_init__. n_peers >= 1 (n_peers=1 reduces to a
    single-agent baseline that should be byte-identical to the existing
    L0Plant path; this is intentional — it lets the driver express
    `single_*` conditions through the same SwarmL0Plant code path).
    """

    n_peers: int = 3
    k_quorum: int = 2
    voting: Literal["answer_hash_majority"] = "answer_hash_majority"
    seed_base: int = 0

    def __post_init__(self) -> None:
        if self.n_peers < 1:
            raise ValueError(f"n_peers must be >= 1, got {self.n_peers}")
        if not (1 <= self.k_quorum <= self.n_peers):
            raise ValueError(
                f"k_quorum must be in [1, n_peers={self.n_peers}], got {self.k_quorum}"
            )
        if self.voting != "answer_hash_majority":
            raise ValueError(
                f"v0 only supports voting='answer_hash_majority', got {self.voting!r}"
            )


@dataclass
class PeerVerdict:
    """Per-peer outcome of one swarm episode."""

    peer_id: str
    answer: str | None
    answer_hash: str | None
    score: float
    cost_usd: float
    n_steps: int
    aborted_reason: str | None


@dataclass
class SwarmVerdict:
    """Aggregate outcome of one swarm episode after voting."""

    chosen_answer: str | None
    chosen_hash: str | None
    quorum_reached: bool
    score: float
    n_voters_for_chosen: int
    total_cost_usd: float
    per_peer: tuple[PeerVerdict, ...]
    aborted_reason: str | None = None


# === 2. Helpers =============================================================

def _normalize_answer(answer: str | None) -> str:
    """Normalize for hash-majority voting.

    Strip leading/trailing whitespace, collapse internal whitespace runs,
    lowercase. Sufficient for HARDER_SUITE answers (numbers, short strings).
    None -> empty string (no answer).
    """
    if answer is None:
        return ""
    return " ".join(answer.split()).lower()


def _answer_hash(answer: str | None) -> str:
    """16-byte hex prefix of sha256(normalized_answer). Stable across processes."""
    norm = _normalize_answer(answer)
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


def _peer_id(idx: int) -> str:
    """Stable peer identifier derived from index. v0: just the integer string."""
    return str(idx)


# === 3. SwarmL0Plant ========================================================

class SwarmL0Plant:
    """N L0 peers sharing a stigmergic substrate.

    All peers share the same Workspace.path (so helpers/, memory/,
    system_rules.jsonl are physically shared on disk). Each peer has its own
    EventLog at .rcs/events_peer_<id>.jsonl. Peers run sequentially in v0;
    voting picks the modal answer-hash with k_quorum threshold.

    The existing L0Plant is reused as-is (no microrcs.py edits). This class
    is composition-only: it constructs N L0Plant instances pointing at the
    shared substrate root and orchestrates run_episode + vote.
    """

    def __init__(
        self,
        peers: tuple[m.L0Plant, ...],
        cfg: SwarmConfig,
        substrate_root: Path,
    ) -> None:
        if len(peers) != cfg.n_peers:
            raise ValueError(
                f"len(peers)={len(peers)} must equal cfg.n_peers={cfg.n_peers}"
            )
        self.peers = peers
        self.cfg = cfg
        self.substrate_root = substrate_root

    @classmethod
    def build(
        cls,
        substrate_root: Path,
        run_id: str,
        cfg: SwarmConfig,
        reasoner_factory: Any,           # Callable[[int], Reasoner]
        caps: m.Caps,
        eywa_python_hint: bool = False,
    ) -> "SwarmL0Plant":
        """Construct a swarm with N peers sharing substrate_root.

        reasoner_factory(peer_idx) -> Reasoner. The factory is responsible
        for any per-peer reasoner diversity (out of scope for v0; default
        factories return identical reasoners).
        """
        # Single shared workspace — physically shared substrate on disk.
        ws = m.Workspace.create(substrate_root, run_id=run_id, persist=True)
        peers: list[m.L0Plant] = []
        for i in range(cfg.n_peers):
            pid = _peer_id(i)
            peer_log_path = ws.path / ".rcs" / f"events_peer_{pid}.jsonl"
            peer_log_path.parent.mkdir(parents=True, exist_ok=True)
            peer_log = m.EventLog(peer_log_path)
            peer = m.L0Plant(
                reasoner=reasoner_factory(i),
                workspace=ws,
                log=peer_log,
                caps=caps,
                eywa_python_hint=eywa_python_hint,
            )
            peers.append(peer)
        return cls(peers=tuple(peers), cfg=cfg, substrate_root=ws.path)

    def run_swarm_episode(self, task: m.Task) -> SwarmVerdict:
        """Run one task across all N peers and vote on the answer.

        v0: sequential peer execution. After every peer's episode, the
        shared scratch/ is wiped (existing Workspace.create semantics) so
        peer N+1 sees a clean scratch but inherits any helpers/ + memory/ +
        system_rules.jsonl mutations made by peer N. This is the
        stigmergic substrate behavior described in spec D3.
        """
        per_peer: list[PeerVerdict] = []
        for i, peer in enumerate(self.peers):
            # Re-prepare the workspace before each peer run. This wipes
            # scratch/ but preserves helpers/, memory/, and system_rules.jsonl
            # because persist=True. Functionally isolates peers' scratch
            # state without per-peer namespacing (v0 sequential model).
            if i > 0:
                m.Workspace.create(self.substrate_root, run_id=peer.workspace.run_id,
                                    persist=True)
                # Reload persisted system rules so peer i sees rules added
                # by L2 mid-episode (v1 — currently L2 fires post-episode,
                # but this is forward-compatible).
                peer.system_rules = peer._load_persisted_system_rules()

            trace = peer.run_episode(task)
            ahash = _answer_hash(trace.final_answer) if trace.final_answer else None
            per_peer.append(PeerVerdict(
                peer_id=_peer_id(i),
                answer=trace.final_answer,
                answer_hash=ahash,
                score=trace.score,
                cost_usd=trace.cost_usd,
                n_steps=trace.n_steps,
                aborted_reason=trace.aborted_reason,
            ))
        return self._vote(task, per_peer)

    def _vote(self, task: m.Task, per_peer: list[PeerVerdict]) -> SwarmVerdict:
        """Tally hashes, apply k_quorum, choose answer.

        Tie-break (when two hashes have equal frequency >= k_quorum):
        1. Highest summed score among tied peers.
        2. Lowest summed cost among tied peers.
        3. Stable sort by hash bytes.

        The chosen answer string is taken from the lowest-cost peer that
        voted for the chosen hash — guarantees determinism.
        """
        total_cost = sum(p.cost_usd for p in per_peer)

        # Filter to peers who actually submitted (None hash means no submit).
        voters_by_hash: dict[str, list[PeerVerdict]] = {}
        for p in per_peer:
            if p.answer_hash is not None:
                voters_by_hash.setdefault(p.answer_hash, []).append(p)

        if not voters_by_hash:
            # No peer submitted at all
            return SwarmVerdict(
                chosen_answer=None,
                chosen_hash=None,
                quorum_reached=False,
                score=0.0,
                n_voters_for_chosen=0,
                total_cost_usd=total_cost,
                per_peer=tuple(per_peer),
                aborted_reason="swarm_no_submission",
            )

        # Find the modal hash, breaking ties deterministically.
        ranked = sorted(
            voters_by_hash.items(),
            key=lambda kv: (
                -len(kv[1]),                           # frequency desc
                -sum(v.score for v in kv[1]),          # summed score desc
                sum(v.cost_usd for v in kv[1]),        # summed cost asc
                kv[0],                                  # hash bytes asc
            ),
        )
        modal_hash, modal_voters = ranked[0]
        n_modal = len(modal_voters)

        if n_modal < self.cfg.k_quorum:
            # No quorum reached — verdict is a no-quorum abort.
            return SwarmVerdict(
                chosen_answer=None,
                chosen_hash=modal_hash,                # for telemetry
                quorum_reached=False,
                score=0.0,
                n_voters_for_chosen=n_modal,
                total_cost_usd=total_cost,
                per_peer=tuple(per_peer),
                aborted_reason="swarm_no_quorum",
            )

        # Quorum reached. Pick the answer string from the lowest-cost peer
        # in the modal group (deterministic tie-break: lowest peer_id on cost tie).
        chosen_peer = sorted(
            modal_voters, key=lambda v: (v.cost_usd, v.peer_id)
        )[0]
        # Re-verify the chosen answer to get the swarm score (single
        # deterministic verifier call rather than mean of per-peer scores).
        # task.verify is the canonical ground truth.
        score = float(task.verify(chosen_peer.answer))
        return SwarmVerdict(
            chosen_answer=chosen_peer.answer,
            chosen_hash=modal_hash,
            quorum_reached=True,
            score=score,
            n_voters_for_chosen=n_modal,
            total_cost_usd=total_cost,
            per_peer=tuple(per_peer),
            aborted_reason=None,
        )


# === 4. CLI driver scaffold =================================================

CONDITION_NAMES = ("single_flat", "single_full", "swarm_flat", "swarm_full")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="swarm_run", description=__doc__)
    p.add_argument(
        "--condition",
        choices=CONDITION_NAMES,
        default="swarm_full",
        help="Which 2x2 cell to run.",
    )
    p.add_argument(
        "--suite",
        choices=("reference", "harder"),
        default="reference",
    )
    p.add_argument("--n-peers", type=int, default=3)
    p.add_argument("--k-quorum", type=int, default=2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--model-l0-l1",
        default="claude-haiku-4-5",
        help="Reasoner model for L0 peers and L1Autonomic.",
    )
    p.add_argument(
        "--model-l2-l3",
        default="claude-opus-4-7",
        help="Reasoner model for L2Meta and L3Governance.",
    )
    p.add_argument(
        "--workspace-root",
        type=Path,
        default=Path("/tmp/microrcs-swarm"),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("reports/swarm"),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Mocked reasoner (no API). Default for `make swarm-smoke`.",
    )
    p.add_argument(
        "--max-steps", type=int, default=20,
    )
    p.add_argument(
        "--max-cost-usd", type=float, default=0.50,
    )
    return p.parse_args(argv)


class _MockSubmitReasoner:
    """Always submits a fixed answer. Used by --dry-run to exercise wiring."""

    def __init__(self, answer: str = "42") -> None:
        self._answer = answer

    def reason(self, req: m.ReasoningRequest) -> m.ReasoningResponse:
        return m.ReasoningResponse(
            text="",
            tool_calls=(m.ToolCall(
                id=f"tc_{m.new_event_id()}",
                name="submit",
                arguments={"answer": self._answer},
            ),),
            thinking="",
            stop_reason="tool_use",
            usage=m.TokenUsage(input=10, output=5),
            latency_ms=1.0,
            model="mock",
        )


def _build_reasoner_factory(args: argparse.Namespace) -> Any:
    """Return reasoner_factory(peer_idx) -> Reasoner.

    Dry-run path uses a mock submitter so the wiring can be exercised
    without API credentials. Live path defers to microrcs.make_reasoner.
    """
    if args.dry_run:
        return lambda _i: _MockSubmitReasoner(answer="42")
    return lambda _i: m.make_reasoner(args.model_l0_l1)


def _is_swarm(condition: str) -> bool:
    return condition.startswith("swarm_")


def _is_full(condition: str) -> bool:
    return condition.endswith("_full")


def _resolve_n_peers(condition: str, n_peers: int) -> int:
    """For single_* conditions, n_peers is forced to 1. swarm_* uses configured n."""
    return n_peers if _is_swarm(condition) else 1


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    n_peers = _resolve_n_peers(args.condition, args.n_peers)
    k_quorum = min(args.k_quorum, n_peers)  # collapse to 1 for single_* conditions
    cfg = SwarmConfig(
        n_peers=n_peers,
        k_quorum=k_quorum,
        seed_base=args.seed,
    )

    suite_map: dict[str, list[m.Task]] = {
        "reference": m.REFERENCE_SUITE,
        "harder": m.HARDER_SUITE,
    }
    suite = suite_map[args.suite]

    run_id = m.new_event_id()
    out_dir = args.out / f"swarm-{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    substrate_root = args.workspace_root / f"swarm-{run_id}-{args.condition}"

    caps = m.Caps(
        max_steps=args.max_steps,
        max_cost_usd=args.max_cost_usd,
        model=args.model_l0_l1,
    )

    reasoner_factory = _build_reasoner_factory(args)
    swarm = SwarmL0Plant.build(
        substrate_root=substrate_root,
        run_id=run_id,
        cfg=cfg,
        reasoner_factory=reasoner_factory,
        caps=caps,
    )

    print(f"swarm_run condition={args.condition} n_peers={n_peers} "
          f"k_quorum={k_quorum} suite={args.suite} dry_run={args.dry_run}")

    # NOTE: v0 keeps L1/L2/L3 wiring stubbed. The "_full" conditions are
    # scaffolded for forward compatibility but the meta-controllers are
    # NOT exercised in this PR — they are deferred to the live-run
    # follow-up alongside swarm-aware controllers (spec D2 v2).
    if _is_full(args.condition):
        print("  [scaffold] L1/L2/L3 wiring deferred to live-run follow-up "
              "(see spec D2). v0 runs L0-only swarm; full conditions reduce "
              "to swarm_flat for this PR.")

    verdicts: list[SwarmVerdict] = []
    for task in suite:
        v = swarm.run_swarm_episode(task)
        verdicts.append(v)
        print(f"  task={task.id} score={v.score:.2f} "
              f"quorum={v.quorum_reached} chosen={v.chosen_answer!r} "
              f"voters={v.n_voters_for_chosen}/{n_peers} "
              f"cost=${v.total_cost_usd:.4f}")

    scores = [v.score for v in verdicts]
    metrics = {
        "run_id": run_id,
        "condition": args.condition,
        "n_peers": n_peers,
        "k_quorum": k_quorum,
        "suite": args.suite,
        "dry_run": args.dry_run,
        "pass_pow_k": m.pass_pow_k(scores, k=3) if scores else 0.0,
        "pass_at_k": m.pass_at_k(scores, k=3) if scores else 0.0,
        "total_cost_usd": sum(v.total_cost_usd for v in verdicts),
        "verdicts": [dataclasses.asdict(v) for v in verdicts],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    print(f"wrote {out_dir / 'metrics.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
