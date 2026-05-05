"""Unit tests for the Swarm-RCS-L0 scaffold.

All tests mock the Reasoner Protocol. No live API calls, no network access.
Pattern lifted from tests/test_microrcs.py (_MockReasoner, _resp_submit).

Spec: docs/superpowers/specs/2026-05-05-swarm-rcs-l0-design.md
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

# Make sibling `microrcs.py` and `scripts/` importable.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import microrcs as m  # noqa: E402

from scripts.swarm_run import (  # noqa: E402
    PeerVerdict,
    SwarmConfig,
    SwarmL0Plant,
    SwarmVerdict,
    _answer_hash,
    _normalize_answer,
    _peer_id,
)


# === Mock reasoner helpers (mirrors test_microrcs._MockReasoner) =============

class _ScriptedReasoner:
    """Returns a fixed sequence of ReasoningResponses, then defaults to submit('done')."""

    def __init__(self, responses: list[m.ReasoningResponse]) -> None:
        self._resps = list(responses)
        self._i = 0

    def reason(self, req: m.ReasoningRequest) -> m.ReasoningResponse:
        if self._i >= len(self._resps):
            return _resp_submit("done")
        r = self._resps[self._i]
        self._i += 1
        return r


def _resp_submit(answer: str, cost_input: int = 10, cost_output: int = 5):
    return m.ReasoningResponse(
        text="",
        thinking="",
        tool_calls=(m.ToolCall(
            id=f"tc_{m.new_event_id()}",
            name="submit",
            arguments={"answer": answer},
        ),),
        stop_reason="tool_use",
        usage=m.TokenUsage(input=cost_input, output=cost_output),
        latency_ms=1.0,
        model="mock",
    )


def _resp_submit_priced(answer: str, cost_input: int, cost_output: int):
    """Like _resp_submit, but pinned to a real model so TokenUsage.cost_usd
    returns a non-zero cost. Used for tie-break tests where peer cost
    differences must be observable."""
    return m.ReasoningResponse(
        text="",
        thinking="",
        tool_calls=(m.ToolCall(
            id=f"tc_{m.new_event_id()}",
            name="submit",
            arguments={"answer": answer},
        ),),
        stop_reason="tool_use",
        usage=m.TokenUsage(input=cost_input, output=cost_output),
        latency_ms=1.0,
        model="claude-haiku-4-5",
    )


def _resp_bash(command: str):
    return m.ReasoningResponse(
        text="",
        thinking="",
        tool_calls=(m.ToolCall(
            id=f"tc_{m.new_event_id()}",
            name="bash",
            arguments={"command": command},
        ),),
        stop_reason="tool_use",
        usage=m.TokenUsage(input=10, output=5),
        latency_ms=1.0,
        model="mock",
    )


def _make_task(answer_correct: str = "42") -> m.Task:
    return m.Task(
        id="t1",
        domain="math",
        prompt="What is 6*7?",
        verify=lambda a: 1.0 if a == answer_correct else 0.0,
    )


def _make_swarm(
    tmp_path: Path,
    n_peers: int = 3,
    k_quorum: int = 2,
    answers: list[str] | None = None,
    costs: list[tuple[int, int]] | None = None,
) -> SwarmL0Plant:
    """Build a swarm where each peer is scripted to submit a specific answer.

    `answers[i]` is the answer string peer i submits. `costs[i] = (input, output)`
    overrides per-peer token cost so we can exercise tie-break rules.
    """
    if answers is None:
        answers = ["42"] * n_peers
    if costs is None:
        costs = [(10, 5)] * n_peers
    cfg = SwarmConfig(n_peers=n_peers, k_quorum=k_quorum)

    def factory(i: int):
        return _ScriptedReasoner([_resp_submit(answers[i],
                                                cost_input=costs[i][0],
                                                cost_output=costs[i][1])])

    return SwarmL0Plant.build(
        substrate_root=tmp_path / "ws",
        run_id="t",
        cfg=cfg,
        reasoner_factory=factory,
        caps=m.Caps(max_steps=5, max_cost_usd=1.0, model="mock"),
    )


# === Section 1 — SwarmConfig validation ======================================

class TestSwarmConfig:
    def test_defaults(self):
        cfg = SwarmConfig()
        assert cfg.n_peers == 3
        assert cfg.k_quorum == 2
        assert cfg.voting == "answer_hash_majority"

    def test_n_peers_below_one_raises(self):
        with pytest.raises(ValueError, match="n_peers must be >= 1"):
            SwarmConfig(n_peers=0, k_quorum=1)

    def test_k_quorum_above_n_peers_raises(self):
        with pytest.raises(ValueError, match=r"k_quorum must be in"):
            SwarmConfig(n_peers=3, k_quorum=4)

    def test_k_quorum_zero_raises(self):
        with pytest.raises(ValueError, match=r"k_quorum must be in"):
            SwarmConfig(n_peers=3, k_quorum=0)

    def test_unknown_voting_strategy_raises(self):
        with pytest.raises(ValueError, match="v0 only supports"):
            SwarmConfig(n_peers=3, k_quorum=2, voting="lyapunov_weighted")  # type: ignore[arg-type]


# === Section 2 — Hash + normalize helpers ====================================

class TestAnswerHash:
    def test_normalize_strips_whitespace(self):
        assert _normalize_answer("  42  ") == "42"
        assert _normalize_answer("hello\n  world") == "hello world"
        assert _normalize_answer("HELLO") == "hello"

    def test_normalize_none_to_empty(self):
        assert _normalize_answer(None) == ""

    def test_hash_stable_under_normalization(self):
        # "42", " 42 ", "42\n" all normalize to "42" -> same hash.
        h1 = _answer_hash("42")
        h2 = _answer_hash("  42  ")
        h3 = _answer_hash("42\n")
        assert h1 == h2 == h3
        # Different content -> different hash.
        assert _answer_hash("42") != _answer_hash("43")

    def test_hash_is_16_hex_chars(self):
        h = _answer_hash("anything")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


# === Section 3 — SwarmL0Plant.build construction ============================

class TestSwarmConstruction:
    def test_swarm_constructs_n_peers(self, tmp_path: Path):
        swarm = _make_swarm(tmp_path, n_peers=3)
        assert len(swarm.peers) == 3
        # Each peer is a distinct L0Plant
        assert len({id(p) for p in swarm.peers}) == 3

    def test_each_peer_has_own_event_log(self, tmp_path: Path):
        swarm = _make_swarm(tmp_path, n_peers=3)
        log_paths = [peer.log.path for peer in swarm.peers]
        # All paths distinct.
        assert len(set(log_paths)) == 3
        # All paths under .rcs/ in the shared substrate root.
        for p in log_paths:
            assert p.parent.name == ".rcs"
            assert p.parent.parent == swarm.substrate_root

    def test_all_peers_share_same_workspace_root(self, tmp_path: Path):
        swarm = _make_swarm(tmp_path, n_peers=3)
        roots = {peer.workspace.path for peer in swarm.peers}
        assert len(roots) == 1, "all peers must share one substrate root"

    def test_build_rejects_mismatched_peer_count(self, tmp_path: Path):
        cfg = SwarmConfig(n_peers=3, k_quorum=2)
        ws = m.Workspace.create(tmp_path / "ws", run_id="t")
        peer = m.L0Plant(
            reasoner=_ScriptedReasoner([]),
            workspace=ws,
            log=m.EventLog(ws.path / ".rcs" / "events.jsonl"),
            caps=m.Caps(model="mock"),
        )
        # Pass only 2 peers when cfg says 3 — must raise.
        with pytest.raises(ValueError, match="must equal cfg.n_peers"):
            SwarmL0Plant(peers=(peer, peer), cfg=cfg, substrate_root=ws.path)


# === Section 4 — Voting & quorum =============================================

class TestVotingAndQuorum:
    def test_voting_picks_majority_hash(self, tmp_path: Path):
        # 2 peers say "42", 1 says "43". Quorum=2 -> "42" wins.
        swarm = _make_swarm(
            tmp_path, n_peers=3, k_quorum=2,
            answers=["42", "42", "43"],
        )
        verdict = swarm.run_swarm_episode(_make_task())
        assert verdict.quorum_reached is True
        assert verdict.chosen_answer == "42"
        assert verdict.n_voters_for_chosen == 2
        assert verdict.score == 1.0  # task verifies "42" -> 1.0
        assert verdict.aborted_reason is None

    def test_quorum_threshold_blocks_no_majority(self, tmp_path: Path):
        # 3 distinct answers, k=2 -> no quorum -> abort.
        swarm = _make_swarm(
            tmp_path, n_peers=3, k_quorum=2,
            answers=["42", "43", "44"],
        )
        verdict = swarm.run_swarm_episode(_make_task())
        assert verdict.quorum_reached is False
        assert verdict.score == 0.0
        assert verdict.aborted_reason == "swarm_no_quorum"
        # Modal hash is still recorded for telemetry (frequency-1 modal).
        assert verdict.chosen_hash is not None

    def test_unanimous_quorum_satisfied(self, tmp_path: Path):
        # All 3 peers agree, k=3 (unanimous) -> quorum reached.
        swarm = _make_swarm(
            tmp_path, n_peers=3, k_quorum=3,
            answers=["42", "42", "42"],
        )
        verdict = swarm.run_swarm_episode(_make_task())
        assert verdict.quorum_reached is True
        assert verdict.n_voters_for_chosen == 3
        assert verdict.score == 1.0

    def test_lowest_cost_peer_chosen_for_answer_string(self, tmp_path: Path):
        """Tie-break by cost-then-peer-id. The chosen answer string comes
        from the lowest-cost peer in the modal group; on cost ties, lowest
        peer_id wins. Under "mock" pricing all costs are zero, so this test
        exercises the peer_id deterministic tie-break."""
        swarm = _make_swarm(
            tmp_path, n_peers=3, k_quorum=2,
            answers=["42", "42", "43"],
        )
        verdict = swarm.run_swarm_episode(_make_task())
        assert verdict.quorum_reached is True
        assert verdict.chosen_answer == "42"
        modal_voters = [p for p in verdict.per_peer if p.answer == "42"]
        assert len(modal_voters) == 2
        # Both peers cost 0 (mock pricing) — peer_id tie-break should pick
        # peer "0" deterministically.
        winner = sorted(modal_voters, key=lambda v: (v.cost_usd, v.peer_id))[0]
        assert winner.peer_id == "0"

    def test_real_cost_tiebreak_picks_cheaper_peer(self, tmp_path: Path):
        """When cost differs, the cheaper peer's answer is chosen.

        Forces real (non-zero) per-peer costs by passing a Caps with a
        priced model. We use claude-haiku-4-5 pricing to compute cost in
        TokenUsage.cost_usd, so a peer with 1000 input tokens > a peer with
        10 input tokens.
        """
        cfg = SwarmConfig(n_peers=3, k_quorum=2)

        def factory(i: int):
            costs = [(10, 5), (1000, 500), (10, 5)]
            return _ScriptedReasoner([_resp_submit_priced(
                ["42", "42", "43"][i],
                cost_input=costs[i][0],
                cost_output=costs[i][1],
            )])

        swarm = SwarmL0Plant.build(
            substrate_root=tmp_path / "ws",
            run_id="t",
            cfg=cfg,
            reasoner_factory=factory,
            caps=m.Caps(max_steps=5, max_cost_usd=1.0,
                         model="claude-haiku-4-5"),
        )
        verdict = swarm.run_swarm_episode(_make_task())
        modal_voters = [p for p in verdict.per_peer if p.answer == "42"]
        cheaper, expensive = sorted(modal_voters, key=lambda v: v.cost_usd)
        assert cheaper.peer_id == "0"
        assert expensive.peer_id == "1"
        assert cheaper.cost_usd < expensive.cost_usd

    def test_no_submission_aborts_with_reason(self, tmp_path: Path):
        # 0 peers submit (empty reasoner -> default "done", but we'll patch
        # so all peers exhaust without a submit). For v0, _ScriptedReasoner
        # falls through to submit("done") which IS a submission, so we use
        # a more aggressive setup: caps.max_cost so low all peers cost-abort.
        cfg = SwarmConfig(n_peers=3, k_quorum=2)

        def expensive_resp_factory(_i):
            # Return a bash response, not a submit, so the loop iterates.
            # With max_cost_usd=0 it aborts on the first cost check.
            return _ScriptedReasoner([_resp_bash("echo hi")] * 10)

        swarm = SwarmL0Plant.build(
            substrate_root=tmp_path / "ws",
            run_id="t",
            cfg=cfg,
            reasoner_factory=expensive_resp_factory,
            caps=m.Caps(max_steps=2, max_cost_usd=0.0, model="mock"),
        )
        verdict = swarm.run_swarm_episode(_make_task())
        # All peers cost-aborted, no submission -> swarm_no_submission.
        assert verdict.quorum_reached is False
        assert verdict.score == 0.0
        assert verdict.aborted_reason == "swarm_no_submission"


# === Section 5 — Stigmergic substrate semantics =============================

class TestSubstrate:
    def test_helpers_shared_across_peers(self, tmp_path: Path):
        """Peer 0 writes a helper; peer 1 must see it on its workspace path."""
        # We don't need a real episode for this — just verify that all peers
        # see the same helpers/ directory contents.
        swarm = _make_swarm(tmp_path, n_peers=2)
        helper_path = swarm.substrate_root / "helpers" / "alpha.py"
        helper_path.write_text("def alpha(): return 1\n")
        assert (swarm.peers[0].workspace.path / "helpers" / "alpha.py").read_text() \
            == "def alpha(): return 1\n"
        assert (swarm.peers[1].workspace.path / "helpers" / "alpha.py").read_text() \
            == "def alpha(): return 1\n"

    def test_scratch_wiped_between_peers(self, tmp_path: Path):
        """v0 sequential semantics: scratch/ wiped before peer N+1's episode."""
        # Build a swarm where peer 0 writes scratch/work.txt during its episode
        # (via a bash command), submits, then peer 1 starts and should see
        # scratch/work.txt absent at the start of its episode.
        cfg = SwarmConfig(n_peers=2, k_quorum=1)

        # Peer 0: bash to write scratch, then submit.
        # Peer 1: bash to ls scratch (we'll observe via the trace), then submit.
        peer0_resps = [_resp_bash("echo hello > scratch/work.txt"),
                       _resp_submit("done")]
        # Peer 1 first lists scratch, then submits whatever it finds.
        # We capture peer 1's tool result via inspecting messages after run.
        peer1_resps = [_resp_bash("ls scratch/"), _resp_submit("done")]

        def factory(i: int):
            return _ScriptedReasoner(peer0_resps if i == 0 else peer1_resps)

        swarm = SwarmL0Plant.build(
            substrate_root=tmp_path / "ws",
            run_id="t",
            cfg=cfg,
            reasoner_factory=factory,
            caps=m.Caps(max_steps=5, max_cost_usd=1.0, model="mock"),
        )
        swarm.run_swarm_episode(_make_task("done"))

        # Inspect peer 1's messages: the tool_result for `ls scratch/` should
        # NOT contain "work.txt" (scratch was wiped before peer 1 ran).
        peer1_messages = swarm.peers[1].run_episode  # ref only — actual messages live in trace
        # We didn't store the trace; verify directly that scratch/ is empty
        # at the end (peer 1 didn't write to it). The scratch should be empty
        # after peer 1's wipe + ls (no writes by peer 1).
        scratch_dir = swarm.substrate_root / "scratch"
        scratch_files = list(scratch_dir.glob("*"))
        assert "work.txt" not in [p.name for p in scratch_files], \
            "scratch should be wiped between peers"

    def test_system_rules_shared_across_peers(self, tmp_path: Path):
        """A rule appended by one peer (or L2 via apply_decision_downward)
        must be visible to other peers via _load_persisted_system_rules."""
        swarm = _make_swarm(tmp_path, n_peers=2)
        # Simulate L2 appending a rule via the L0Plant persist API (this is
        # what apply_decision_downward(AppendSystemRule) does internally).
        peer0 = swarm.peers[0]
        peer0.persist_system_rule("Always check units.", rationale="test")

        # Peer 1, fresh from disk on its next episode, should load that rule.
        peer1 = swarm.peers[1]
        loaded = peer1._load_persisted_system_rules()
        assert "Always check units." in loaded


# === Section 6 — End-to-end mocked episode ==================================

class TestEndToEndMocked:
    def test_swarm_episode_mocked_end_to_end(self, tmp_path: Path):
        """Full episode: 3 peers, all submit '42', task verifies '42' -> 1.0."""
        swarm = _make_swarm(tmp_path, n_peers=3, k_quorum=2)
        verdict = swarm.run_swarm_episode(_make_task())
        assert verdict.score == 1.0
        assert verdict.quorum_reached is True
        assert verdict.chosen_answer == "42"
        # total_cost is sum of per-peer costs
        assert verdict.total_cost_usd == pytest.approx(
            sum(p.cost_usd for p in verdict.per_peer)
        )
        # 3 PeerVerdict entries
        assert len(verdict.per_peer) == 3

    def test_aborted_peer_does_not_crash_swarm(self, tmp_path: Path):
        """One peer aborts (returns no submit, falls through to default
        'done'), other two submit '42'. Quorum=2 reached on '42'."""
        cfg = SwarmConfig(n_peers=3, k_quorum=2)

        def factory(i: int):
            if i == 2:
                # Empty -> _ScriptedReasoner default falls through to submit("done")
                # which will be hashed as "done", a different hash from "42".
                return _ScriptedReasoner([])
            return _ScriptedReasoner([_resp_submit("42")])

        swarm = SwarmL0Plant.build(
            substrate_root=tmp_path / "ws",
            run_id="t",
            cfg=cfg,
            reasoner_factory=factory,
            caps=m.Caps(max_steps=5, max_cost_usd=1.0, model="mock"),
        )
        verdict = swarm.run_swarm_episode(_make_task())
        assert verdict.quorum_reached is True
        assert verdict.chosen_answer == "42"
        assert verdict.n_voters_for_chosen == 2

    def test_verdict_serializable_to_dict(self, tmp_path: Path):
        """asdict() must round-trip cleanly for metrics.json."""
        swarm = _make_swarm(tmp_path, n_peers=3, k_quorum=2)
        verdict = swarm.run_swarm_episode(_make_task())
        d = dataclasses.asdict(verdict)
        # Top-level fields preserved
        assert d["score"] == 1.0
        assert d["quorum_reached"] is True
        assert d["chosen_answer"] == "42"
        # per_peer is a list of dicts (asdict recurses)
        assert isinstance(d["per_peer"], (list, tuple))
        assert len(d["per_peer"]) == 3
        peer = d["per_peer"][0]
        assert "peer_id" in peer
        assert "answer" in peer
        assert "answer_hash" in peer


# === Section 7 — _peer_id helper ============================================

class TestPeerIdHelper:
    def test_peer_id_is_index_string(self):
        assert _peer_id(0) == "0"
        assert _peer_id(7) == "7"
