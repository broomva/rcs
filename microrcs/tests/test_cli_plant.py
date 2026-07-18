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

    def __init__(self, argv, canned_stdout="", hang=False, hang_forever=False, **kwargs):
        self.argv = argv
        self.kwargs = kwargs
        self._stdout = canned_stdout
        self._hang = hang
        self._hang_forever = hang_forever  # never drains, even after SIGTERM
        self.signals: list[int] = []
        self.killed = False
        self.stdin_received: str | None = None
        self._communicate_calls = 0

    def communicate(self, _input=None, timeout=None):
        self._communicate_calls += 1
        if _input is not None:
            self.stdin_received = _input
        # First call hangs if hang; post-signal reap call succeeds unless
        # hang_forever (which forces the SIGKILL fallback path).
        import subprocess
        if self._hang and self._communicate_calls == 1:
            raise subprocess.TimeoutExpired(cmd=self.argv, timeout=timeout or 0)
        if self._hang_forever:
            raise subprocess.TimeoutExpired(cmd=self.argv, timeout=timeout or 0)
        return self._stdout, ""

    def send_signal(self, sig):
        self.signals.append(sig)

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.killed = True


def _git_init(ws: Path) -> None:
    """Minimal committed git repo so `_reset_workspace` (which now hard-fails
    on a non-git tree, P20 NEW-2) has a valid HEAD to reset to. Idempotent —
    overlap tests reuse the same task-id (same dir)."""
    import subprocess as sp
    if (ws / ".git").exists():
        return
    run = lambda *a: sp.run(list(a), cwd=ws, capture_output=True, text=True, check=True)  # noqa: E731
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t"); run("git", "config", "user.name", "t")
    (ws / ".seed").write_text("seed\n")
    run("git", "add", "-A"); run("git", "commit", "-qm", "seed")


def make_task(tmp: Path, task_id="fake-instance", score=1.0) -> m.Task:
    ws = tmp / task_id
    ws.mkdir(parents=True, exist_ok=True)
    _git_init(ws)
    return m.Task(
        id=task_id, domain="swe-bench-lite", prompt="fix the bug",
        verify=lambda _answer: score,
        metadata={"swe_agent_workspace": str(ws)},
    )


def make_git_task(tmp: Path, task_id="git-instance", venv=True) -> m.Task:
    """Real git workspace (committed base) + optional .microrcs_venv marker,
    with a verifier that scores from the CURRENT `git diff HEAD` line count —
    so it detects whether the workspace was reset between episodes (B1)."""
    import subprocess as sp
    ws = tmp / task_id
    ws.mkdir(parents=True, exist_ok=True)
    run = lambda *a: sp.run(list(a), cwd=ws, capture_output=True, text=True, check=True)  # noqa: E731
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t"); run("git", "config", "user.name", "t")
    (ws / "code.py").write_text("base\n")
    run("git", "add", "-A"); run("git", "commit", "-qm", "base")
    if venv:
        (ws / ".microrcs_venv").write_text(str(tmp / "venv-cache"))
    (tmp / "venv-cache" / "bin").mkdir(parents=True, exist_ok=True)

    def verify(_answer: str) -> float:
        d = sp.run(["git", "diff", "HEAD"], cwd=ws, capture_output=True, text=True)
        return float(d.stdout.count("\n"))  # grows if edits accumulate

    return m.Task(id=task_id, domain="swe-bench-lite", prompt="fix", verify=verify,
                  metadata={"swe_agent_workspace": str(ws)})


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


def test_run_episode_resets_workspace_between_episodes():
    """B1: two episodes on the SAME task must NOT accumulate edits — the
    workspace is git-reset before each run so measurements are independent."""
    import subprocess as sig  # noqa: F401 (kept parallel to sibling tests)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        task = make_git_task(tmp)

        # A 'fake agent' that appends a line to code.py each episode.
        def spawn(argv, **kwargs):
            ws = Path(kwargs["cwd"])
            with (ws / "code.py").open("a") as fh:
                fh.write("edit\n")
            return FakeProc(argv, canned_stdout=ENVELOPE, **kwargs)

        runner = ClaudeCliRunner(
            claude_bin="/fake/claude", timeout_s=5.0,
            env_base={"HOME": str(tmp), "USER": "u", "LOGNAME": "u", "TERM": "x"},
            spawn=spawn,
        )
        r1 = runner.run_episode(task, HarnessConfig())
        r2 = runner.run_episode(task, HarnessConfig())
        # Each episode's diff reflects exactly ONE appended line, not two —
        # proving the prior episode's edit was reset. Without the reset r2
        # would score strictly greater than r1 (accumulation).
        assert r1.score == r2.score, f"workspace not reset: r1={r1.score} r2={r2.score}"
        assert r2.score > 0, "verifier should see the single fresh edit"


def test_reset_workspace_does_not_exfil_env_secret_via_planted_git_filter():
    """P20 round-2 NEW-1 regression: an agent-planted git smudge filter must
    NOT capture ANTHROPIC_API_KEY (or any parent secret) when it fires during
    the next episode's reset. The reset git spawns run under the filtered env
    AND with filters/hooks/fsmonitor neutralized."""
    import subprocess as sp
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        task = make_git_task(tmp)
        ws = Path(task.metadata["swe_agent_workspace"])
        loot = tmp / "loot.txt"
        # The 'agent' plants a smudge filter + attributes that would run on
        # the next `git reset --hard` checkout of code.py.
        run = lambda *a: sp.run(list(a), cwd=ws, capture_output=True, text=True)  # noqa: E731
        run("git", "config", "filter.evil.smudge", f"sh -c 'echo $ANTHROPIC_API_KEY > {loot}; cat'")
        (ws / ".gitattributes").write_text("code.py filter=evil\n")
        run("git", "add", ".gitattributes"); run("git", "commit", "-qm", "attrs")
        (ws / "code.py").write_text("dirty\n")  # make reset actually re-checkout

        runner = ClaudeCliRunner(
            claude_bin="/fake/claude", timeout_s=5.0,
            env_base={"HOME": str(tmp), "USER": "u", "LOGNAME": "u", "TERM": "x",
                      "ANTHROPIC_API_KEY": "sk-ant-SECRET-PARENT"},
            spawn=lambda argv, **kw: FakeProc(argv, canned_stdout=ENVELOPE, **kw),
        )
        runner._reset_workspace(str(ws))
        captured = loot.read_text().strip() if loot.exists() else ""
        assert "sk-ant-SECRET-PARENT" not in captured, f"SECRET EXFILTRATED: {captured!r}"


def test_reset_workspace_failure_is_classified_reset_error():
    """NEW-2: a non-git (or otherwise failing) workspace must classify as
    reset_error, never silently proceed on an unreset tree."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ws = tmp / "not-a-git-repo"; ws.mkdir()
        (ws / ".microrcs_venv").write_text(str(tmp / "vc"))
        (tmp / "vc" / "bin").mkdir(parents=True)
        task = m.Task(id="nogit", domain="swe-bench-lite", prompt="x",
                      verify=lambda _a: 1.0, metadata={"swe_agent_workspace": str(ws)})
        runner = ClaudeCliRunner(
            claude_bin="/fake/claude", timeout_s=5.0,
            env_base={"HOME": str(tmp), "USER": "u", "LOGNAME": "u", "TERM": "x"},
            spawn=lambda argv, **kw: FakeProc(argv, canned_stdout=ENVELOPE, **kw),
        )
        res = runner.run_episode(task, HarnessConfig())
        assert res.aborted == "reset_error" and res.is_error and res.score == 0.0


def test_run_episode_prepends_venv_to_child_path():
    """M1: the instance venv bin must be on the child PATH (the SWE prompt
    promises pytest/python there)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        task = make_git_task(tmp, venv=True)
        captured = {}

        def spawn(argv, **kwargs):
            captured["env"] = kwargs["env"]
            return FakeProc(argv, canned_stdout=ENVELOPE, **kwargs)

        runner = ClaudeCliRunner(
            claude_bin="/fake/claude", timeout_s=5.0,
            env_base={"HOME": str(tmp), "USER": "u", "LOGNAME": "u", "TERM": "x"},
            spawn=spawn,
        )
        runner.run_episode(task, HarnessConfig())
        venv_bin = str(tmp / "venv-cache" / "bin")
        assert captured["env"]["PATH"].startswith(venv_bin), "venv bin not prepended to child PATH"
        assert captured["env"]["VIRTUAL_ENV"] == str(tmp / "venv-cache")


def test_run_episode_delivers_prompt_via_stdin():
    """m4: the prompt must reach the child via stdin (not argv — greedy flags)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        runner, procs = make_runner(tmp)
        task = make_task(tmp, score=1.0)
        runner.run_episode(task, HarnessConfig())
        assert procs[0].stdin_received == task.prompt
        assert task.prompt not in procs[0].argv, "prompt must not be a positional arg"


def test_run_episode_sigkill_fallback_when_sigterm_ignored():
    """m4: if the child ignores SIGTERM (reap hangs), kill() is the fallback."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        procs: list[FakeProc] = []

        def spawn(argv, **kwargs):
            p = FakeProc(argv, hang=True, hang_forever=True, **kwargs)
            procs.append(p)
            return p

        runner = ClaudeCliRunner(
            claude_bin="/fake/claude", timeout_s=5.0,
            env_base={"HOME": str(tmp), "USER": "u", "LOGNAME": "u", "TERM": "x"},
            spawn=spawn,
        )
        res = runner.run_episode(make_task(tmp, score=0.0), HarnessConfig())
        assert res.aborted == "timeout"
        assert procs[0].killed, "SIGKILL fallback must fire when reap hangs"


def test_run_episode_verify_exception_is_classified_not_raised():
    """A verifier that raises must not kill the loop — classify verify_error."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        runner, _ = make_runner(tmp)
        ws = tmp / "boom"; ws.mkdir()
        _git_init(ws)  # reach the verify path (reset must succeed first)
        def boom(_a): raise RuntimeError("pytest exploded")
        task = m.Task(id="boom", domain="swe-bench-lite", prompt="x",
                      verify=boom, metadata={"swe_agent_workspace": str(ws)})
        res = runner.run_episode(task, HarnessConfig())
        assert res.aborted == "verify_error" and res.is_error and res.score == 0.0


def test_parse_envelope_tolerates_warning_prefix_and_trailing_text():
    """m2: a brace-bearing warning before, or text after, the JSON must parse."""
    noisy = 'WARNING: config at {/home/u} missing\n' + ENVELOPE + '\nBYE'
    env = ClaudeCliRunner.parse_envelope(noisy)
    assert env["result"] == "done" and env["num_turns"] == 7


def test_generation_loop_gate_rejects_ties():
    """The strict `>` gate must reject holdout == best (docstring stresses this)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        train = [make_task(tmp, "train-1")]
        holdout = [make_task(tmp, "hold-1")]
        scores = {("gen0", "hold-1"): 0.5, ("gen1", "hold-1"): 0.5,  # exact tie
                  ("gen1", "train-1"): 0.9}

        class ScriptedRunner:
            def run_episode(self, task, config):
                s = scores.get((config.config_id, task.id), 0.0)
                return EpisodeResult(task.id, s, False, 0.1, 1, None, "", config.config_id)

        loop = GenerationLoop(ScriptedRunner(), train, holdout,
                              propose_fn=lambda b, h: b, out_dir=tmp / "out")
        rec = loop.step()
        assert not rec.accepted, "a tie must be rejected by strict >"


def test_generation_loop_history_leak_is_semantic_not_key_named():
    """m5: strengthen the leak guard — NO value in any history entry may
    equal a holdout score, regardless of key name (renamed-key raw leak)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        holdout_val = 0.37

        class HoldoutRunner:
            def run_episode(self, task, config):
                s = holdout_val if task.id == "h" else 0.1
                return EpisodeResult(task.id, s, False, 0.1, 1, None, "", config.config_id)

        loop = GenerationLoop(HoldoutRunner(), [make_task(tmp, "t")], [make_task(tmp, "h")],
                              propose_fn=lambda b, h: b, out_dir=tmp / "out")
        loop.step()
        for entry in loop.history:
            for v in entry.values():
                assert v != holdout_val, f"holdout score {holdout_val} leaked as {entry}"


def test_generation_loop_rejects_empty_splits():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for train, hold, why in [([], [make_task(tmp, "h")], "empty train"),
                                 ([make_task(tmp, "t")], [], "empty holdout")]:
            try:
                GenerationLoop(None, train, hold, propose_fn=lambda b, h: b, out_dir=tmp / "o")
            except ValueError:
                pass
            else:
                raise AssertionError(f"{why} must raise")


def test_final_report_uses_untouched_split_and_reports_overfit_gap():
    """M2 mitigation: final_test split is scored only in final_report, never
    by the gate; overfit_gap = holdout - final surfaces the accept-bit bias."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        scores = {"h": 0.8, "f": 0.5}

        class SplitRunner:
            def run_episode(self, task, config):
                base = scores.get(task.id, 0.3)
                return EpisodeResult(task.id, base, False, 0.1, 1, None, "", config.config_id)

        loop = GenerationLoop(
            SplitRunner(), [make_task(tmp, "t")], [make_task(tmp, "h")],
            propose_fn=lambda b, h: b, out_dir=tmp / "out",
            final_test_tasks=[make_task(tmp, "f")],
        )
        loop.step()
        rep = loop.final_report()
        assert rep["final_test_score"] == 0.5 and rep["holdout_score"] == 0.8
        assert abs(rep["overfit_gap"] - 0.3) < 1e-9
        assert (tmp / "out" / "final_report.json").exists()


def test_generation_loop_rejects_final_overlap():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        try:
            GenerationLoop(None, [make_task(tmp, "t")], [make_task(tmp, "h")],
                           propose_fn=lambda b, h: b, out_dir=tmp / "o",
                           final_test_tasks=[make_task(tmp, "h")])  # overlaps holdout
        except ValueError as exc:
            assert "final_test" in str(exc)
        else:
            raise AssertionError("final/holdout overlap must raise")


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
        test_run_episode_resets_workspace_between_episodes,
        test_reset_workspace_does_not_exfil_env_secret_via_planted_git_filter,
        test_reset_workspace_failure_is_classified_reset_error,
        test_run_episode_prepends_venv_to_child_path,
        test_run_episode_delivers_prompt_via_stdin,
        test_run_episode_sigkill_fallback_when_sigterm_ignored,
        test_run_episode_verify_exception_is_classified_not_raised,
        test_parse_envelope_tolerates_warning_prefix_and_trailing_text,
        test_generation_loop_gate_rejects_ties,
        test_generation_loop_history_leak_is_semantic_not_key_named,
        test_generation_loop_rejects_empty_splits,
        test_final_report_uses_untouched_split_and_reports_overfit_gap,
        test_generation_loop_rejects_final_overlap,
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
