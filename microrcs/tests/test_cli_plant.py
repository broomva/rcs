"""Unit tests for adapters/cli_plant.py (BRO-1943).

Pure stdlib; the claude CLI is NEVER invoked — subprocess is faked at the
seam (`spawn=` injection). Run: python3 -m pytest tests/test_cli_plant.py -q
or python3 tests/test_cli_plant.py (self-runner, CI style).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_MICROCRS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_MICROCRS_DIR))

import microrcs as m  # noqa: E402
from adapters.cli_plant import (  # noqa: E402
    ClaudeCliRunner,
    EpisodeResult,
    GenerationLoop,
    HarnessConfig,
    filter_env,
)


# === helpers =============================================================
class FakeProc:
    """Stands in for subprocess.Popen — records env/argv, returns a canned
    envelope, and counts signals for the SIGTERM-first assertion."""

    def __init__(self, argv, canned_stdout="", hang=False, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        self._stdout = canned_stdout
        self._hang = hang
        self.signals: list[int] = []
        self.killed = False

    def communicate(self, _input=None, timeout=None):
        if self._hang:
            import subprocess
            raise subprocess.TimeoutExpired(cmd=self.argv, timeout=timeout or 0)
        return self._stdout, ""

    def send_signal(self, sig):
        self.signals.append(sig)

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.killed = True


def make_task(tmp: Path, task_id="fake-instance", score=1.0) -> m.Task:
    ws = tmp / task_id
    ws.mkdir(parents=True, exist_ok=True)
    return m.Task(
        id=task_id, domain="swe-bench-lite", prompt="fix the bug",
        verify=lambda _answer: score,
        metadata={"swe_agent_workspace": str(ws)},
    )


ENVELOPE = json.dumps({
    "type": "result", "is_error": False, "result": "done",
    "num_turns": 7, "total_cost_usd": 0.42,
})


def make_runner(tmp: Path, canned=ENVELOPE, hang=False):
    procs: list[FakeProc] = []

    def spawn(argv, **kwargs):
        p = FakeProc(argv, canned_stdout=canned, hang=hang, **kwargs)
        procs.append(p)
        return p

    runner = ClaudeCliRunner(
        claude_bin="/fake/claude", timeout_s=5.0,
        env_base={"HOME": str(tmp), "USER": "u", "LOGNAME": "u", "TERM": "x",
                  "ANTHROPIC_API_KEY": "sk-ant-SHOULD-NOT-LEAK",
                  "AWS_SECRET_ACCESS_KEY": "leaky", "GH_TOKEN": "leaky"},
        spawn=spawn,
    )
    return runner, procs


# === tests ===============================================================
def test_filter_env_denies_by_default():
    env = filter_env({
        "HOME": "/h", "USER": "u", "LOGNAME": "u", "TERM": "t",
        "ANTHROPIC_API_KEY": "sk-ant-secret", "AWS_SECRET_ACCESS_KEY": "s",
        "GH_TOKEN": "g", "GITHUB_TOKEN": "g", "OPENAI_API_KEY": "o",
        "PATH": "/evil/path",
    })
    assert "ANTHROPIC_API_KEY" not in env, "API key leaked — subscription-billing proof broken"
    for bad in ("AWS_SECRET_ACCESS_KEY", "GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY"):
        assert bad not in env
    assert env["HOME"] == "/h" and env["USER"] == "u" and env["LOGNAME"] == "u"
    assert "/evil/path" not in env["PATH"], "parent PATH must not pass through"
    assert env["PATH"].endswith("/h/.local/bin"), "child PATH must reach the CLI"


def test_run_episode_success_and_child_env():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        runner, procs = make_runner(tmp)
        task = make_task(tmp, score=1.0)
        res = runner.run_episode(task, HarnessConfig(max_turns=33))
        assert isinstance(res, EpisodeResult)
        assert res.score == 1.0 and res.is_error is False and res.aborted is None
        assert res.num_turns == 7 and res.cost_usd_reported == 0.42
        child_env = procs[0].kwargs["env"]
        assert "ANTHROPIC_API_KEY" not in child_env
        argv = procs[0].argv
        assert argv[:2] == ["/fake/claude", "-p"]
        assert "--max-turns" in argv and argv[argv.index("--max-turns") + 1] == "33"
        assert procs[0].kwargs["cwd"] == task.metadata["swe_agent_workspace"]


def test_run_episode_score_comes_from_verifier_not_cli():
    """The CLI may claim success; the verifier is the only score source (P11)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        runner, _ = make_runner(tmp)  # envelope says is_error=False, "done"
        task = make_task(tmp, score=0.0)  # but pytest verification fails
        res = runner.run_episode(task, HarnessConfig())
        assert res.score == 0.0, "CLI self-report must never override the verifier"


def test_run_episode_timeout_sigterm_first():
    import signal as sig
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        runner, procs = make_runner(tmp, hang=True)
        task = make_task(tmp, score=0.0)
        res = runner.run_episode(task, HarnessConfig())
        assert res.aborted == "timeout" and res.is_error
        assert procs[0].signals == [sig.SIGTERM], "must SIGTERM before any kill"


def test_run_episode_malformed_envelope_is_parse_error_not_crash():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        runner, _ = make_runner(tmp, canned="not json at all")
        task = make_task(tmp, score=0.0)
        res = runner.run_episode(task, HarnessConfig())
        assert res.aborted == "parse_error" and res.is_error and res.score == 0.0


def test_harness_config_roundtrip():
    cfg = HarnessConfig(
        model="claude-sonnet-4-6", max_turns=45,
        allowed_tools=("Bash", "Read"), system_prompt_append="think first",
        generation=3, parent="gen2", notes="test",
    )
    assert HarnessConfig.from_json(cfg.to_json()) == cfg


def test_generation_loop_gate_accepts_on_holdout_improvement():
    """Gate logic with a scripted runner: candidate beats best on holdout."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        train = [make_task(tmp, "train-1")]
        holdout = [make_task(tmp, "hold-1")]
        scores = {("gen0", "hold-1"): 0.2, ("gen1", "hold-1"): 0.6,
                  ("gen1", "train-1"): 0.5}

        class ScriptedRunner:
            def run_episode(self, task, config):
                s = scores.get((config.config_id, task.id), 0.0)
                return EpisodeResult(task.id, s, False, 0.1, 1, None, "", config.config_id)

        loop = GenerationLoop(
            ScriptedRunner(), train, holdout,
            propose_fn=lambda best, hist: best,  # no-op mutation
            out_dir=tmp / "out",
        )
        rec = loop.step()
        assert rec.accepted and loop.best.generation == 1
        assert loop.best_holdout == 0.6
        lineage = (tmp / "out" / "lineage.jsonl").read_text().strip().splitlines()
        assert len(lineage) == 1 and json.loads(lineage[0])["accepted"] is True
        assert (tmp / "out" / "best_config.json").exists()


def test_generation_loop_gate_rejects_on_holdout_regression():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        train = [make_task(tmp, "train-1")]
        holdout = [make_task(tmp, "hold-1")]
        scores = {("gen0", "hold-1"): 0.6, ("gen1", "hold-1"): 0.4,
                  ("gen1", "train-1"): 0.9}  # train up, holdout DOWN → reject

        class ScriptedRunner:
            def run_episode(self, task, config):
                s = scores.get((config.config_id, task.id), 0.0)
                return EpisodeResult(task.id, s, False, 0.1, 1, None, "", config.config_id)

        loop = GenerationLoop(
            ScriptedRunner(), train, holdout,
            propose_fn=lambda best, hist: best, out_dir=tmp / "out",
        )
        rec = loop.step()
        assert not rec.accepted, "train improvement must NOT bypass the private gate"
        assert loop.best.generation == 0 and loop.best_holdout == 0.6


def test_generation_loop_history_never_leaks_holdout():
    """The proposer-visible history must carry train scores only — leaking
    the private signal would re-endogenize the reference (BRO-1924)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        class ZeroRunner:
            def run_episode(self, task, config):
                return EpisodeResult(task.id, 0.0, False, 0.1, 1, None, "", config.config_id)

        loop = GenerationLoop(
            ZeroRunner(), [make_task(tmp, "t")], [make_task(tmp, "h")],
            propose_fn=lambda best, hist: best, out_dir=tmp / "out",
        )
        loop.step()
        assert loop.history, "history must record the attempt"
        for entry in loop.history:
            assert "holdout_score" not in entry, "private signal leaked to proposer"


def test_generation_loop_rejects_train_holdout_overlap():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        t = make_task(tmp, "same-id")
        try:
            GenerationLoop(
                None, [t], [make_task(tmp, "same-id")],
                propose_fn=lambda b, h: b, out_dir=tmp / "out",
            )
        except ValueError as exc:
            assert "overlap" in str(exc)
        else:
            raise AssertionError("overlapping splits must be rejected at construction")


# === self-runner (CI style) =============================================
if __name__ == "__main__":
    tests = [
        test_filter_env_denies_by_default,
        test_run_episode_success_and_child_env,
        test_run_episode_score_comes_from_verifier_not_cli,
        test_run_episode_timeout_sigterm_first,
        test_run_episode_malformed_envelope_is_parse_error_not_crash,
        test_harness_config_roundtrip,
        test_generation_loop_gate_accepts_on_holdout_improvement,
        test_generation_loop_gate_rejects_on_holdout_regression,
        test_generation_loop_history_never_leaks_holdout,
        test_generation_loop_rejects_train_holdout_overlap,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  {t.__name__}: OK")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  {t.__name__}: FAIL — {exc}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
