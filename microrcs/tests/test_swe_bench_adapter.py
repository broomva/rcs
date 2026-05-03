"""Unit tests for the SWE-bench-Lite adapter (BRO-946 smoke).

No network, no live API. Mocks subprocess + HF dataset where needed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.sandbox import UvVenvBackend  # noqa: E402
from adapters.sandbox.backend import SetupError  # noqa: E402
from adapters.swe_bench import (  # noqa: E402
    _apply_patch,
    _build_swe_prompt,
    _extract_failing_test_files,
    _extract_failing_test_names,
    _git_diff_head,
    _make_swe_verifier,
    curated_pilot_instances,
)
from adapters.swe_types import (  # noqa: E402
    SweCandidate,
    SweInstance,
    SweInstanceError,
    SweScore,
)


# === Fixture: a canonical SweInstance row ===========================================

VALID_HF_ROW = {
    "instance_id": "owner__repo-12345",
    "repo": "owner/repo",
    "base_commit": "0123456789abcdef0123456789abcdef01234567",
    "problem_statement": "The widget should not crash on empty input.",
    "hints_text": "Look at widget.py line 42.",
    "test_patch": (
        "diff --git a/tests/test_widget.py b/tests/test_widget.py\n"
        "+++ b/tests/test_widget.py\n"
        "+def test_widget_handles_empty():\n"
        "+    assert Widget().run('') is None\n"
    ),
    "patch": "diff --git a/widget.py b/widget.py\n",  # ground truth
    "FAIL_TO_PASS": json.dumps(["tests/test_widget.py::test_widget_handles_empty"]),
    "PASS_TO_PASS": json.dumps(["tests/test_widget.py::test_widget_basic"]),
    "version": "1.0",
    "environment_setup_commit": "fedcba9876543210fedcba9876543210fedcba98",
}


@pytest.fixture
def valid_instance() -> SweInstance:
    return SweInstance.from_hf_row(VALID_HF_ROW)


# === SweInstance validation =======================================================

class TestSweInstanceValidation:
    def test_round_trip_valid_row(self, valid_instance: SweInstance) -> None:
        assert valid_instance.instance_id == "owner__repo-12345"
        assert valid_instance.repo == "owner/repo"
        assert valid_instance.repo_slug == "owner--repo"
        assert valid_instance.fail_to_pass == (
            "tests/test_widget.py::test_widget_handles_empty",
        )

    def test_rejects_short_sha(self) -> None:
        row = dict(VALID_HF_ROW, base_commit="abc123")
        with pytest.raises(SweInstanceError, match="40-char hex SHA"):
            SweInstance.from_hf_row(row)

    def test_rejects_uppercase_sha(self) -> None:
        row = dict(VALID_HF_ROW, base_commit="A" * 40)
        with pytest.raises(SweInstanceError, match="40-char hex SHA"):
            SweInstance.from_hf_row(row)

    def test_rejects_repo_without_slash(self) -> None:
        row = dict(VALID_HF_ROW, repo="onlyowner")
        with pytest.raises(SweInstanceError, match="owner/name"):
            SweInstance.from_hf_row(row)

    def test_rejects_empty_problem_statement(self) -> None:
        row = dict(VALID_HF_ROW, problem_statement="   ")
        with pytest.raises(SweInstanceError, match="problem_statement is empty"):
            SweInstance.from_hf_row(row)

    def test_rejects_empty_test_patch(self) -> None:
        row = dict(VALID_HF_ROW, test_patch="")
        with pytest.raises(SweInstanceError, match="test_patch is empty"):
            SweInstance.from_hf_row(row)

    def test_rejects_empty_fail_to_pass(self) -> None:
        row = dict(VALID_HF_ROW, FAIL_TO_PASS="[]")
        with pytest.raises(SweInstanceError, match="fail_to_pass must be non-empty"):
            SweInstance.from_hf_row(row)

    def test_accepts_empty_pass_to_pass(self) -> None:
        # Some instances don't track regression tests.
        row = dict(VALID_HF_ROW, PASS_TO_PASS="[]")
        inst = SweInstance.from_hf_row(row)
        assert inst.pass_to_pass == ()

    def test_handles_pass_to_pass_as_list(self) -> None:
        row = dict(VALID_HF_ROW, PASS_TO_PASS=["test_a", "test_b"])
        inst = SweInstance.from_hf_row(row)
        assert inst.pass_to_pass == ("test_a", "test_b")

    def test_normalizes_empty_environment_setup_commit(self) -> None:
        row = dict(VALID_HF_ROW, environment_setup_commit="")
        inst = SweInstance.from_hf_row(row)
        assert inst.environment_setup_commit is None

    def test_rejects_invalid_environment_setup_commit(self) -> None:
        row = dict(VALID_HF_ROW, environment_setup_commit="badsha")
        with pytest.raises(SweInstanceError):
            SweInstance.from_hf_row(row)

    def test_rejects_instance_id_format(self) -> None:
        row = dict(VALID_HF_ROW, instance_id="not-the-right-shape")
        with pytest.raises(SweInstanceError, match="instance_id"):
            SweInstance.from_hf_row(row)


# === SweCandidate / SweScore validation ==========================================

class TestSweCandidate:
    def test_accepts_valid(self) -> None:
        c = SweCandidate(
            instance_id="owner__repo-1",
            patch_text="diff ...",
            final_message="done",
            n_steps=5,
            cost_usd=0.12,
        )
        assert c.n_steps == 5

    def test_rejects_negative_steps(self) -> None:
        with pytest.raises(ValueError, match="n_steps"):
            SweCandidate(
                instance_id="x__y-1",
                patch_text="",
                final_message="",
                n_steps=-1,
                cost_usd=0.0,
            )

    def test_rejects_negative_cost(self) -> None:
        with pytest.raises(ValueError, match="cost_usd"):
            SweCandidate(
                instance_id="x__y-1",
                patch_text="",
                final_message="",
                n_steps=0,
                cost_usd=-0.01,
            )


class TestSweScore:
    def test_accepts_full_pass(self) -> None:
        s = SweScore(
            instance_id="x__y-1",
            score=1.0,
            fail_to_pass_passing=2,
            fail_to_pass_total=2,
            pass_to_pass_passing=3,
            pass_to_pass_total=3,
            pytest_duration_s=4.5,
        )
        assert s.fully_passed is True

    def test_rejects_passing_gt_total(self) -> None:
        with pytest.raises(ValueError, match="pass.*passing.*total"):
            SweScore(
                instance_id="x__y-1",
                score=1.0,
                fail_to_pass_passing=3,
                fail_to_pass_total=2,
                pass_to_pass_passing=0,
                pass_to_pass_total=0,
                pytest_duration_s=0.0,
            )

    def test_rejects_score_other_than_0_or_1(self) -> None:
        with pytest.raises(ValueError, match="score"):
            SweScore(
                instance_id="x__y-1",
                score=0.5,
                fail_to_pass_passing=1,
                fail_to_pass_total=2,
                pass_to_pass_passing=0,
                pass_to_pass_total=0,
                pytest_duration_s=0.0,
            )

    def test_score_is_serializable(self) -> None:
        s = SweScore(
            instance_id="x__y-1",
            score=0.0,
            fail_to_pass_passing=0,
            fail_to_pass_total=2,
            pass_to_pass_passing=0,
            pass_to_pass_total=0,
            pytest_duration_s=0.0,
        )
        serialized = json.dumps(asdict(s))
        roundtrip = json.loads(serialized)
        assert roundtrip["instance_id"] == "x__y-1"


# === Prompt building =============================================================

class TestPromptBuilder:
    def test_extract_test_files(self, valid_instance: SweInstance) -> None:
        files = _extract_failing_test_files(valid_instance.test_patch)
        assert files == ["tests/test_widget.py"]

    def test_extract_test_names(self, valid_instance: SweInstance) -> None:
        names = _extract_failing_test_names(valid_instance.test_patch)
        assert names == ["test_widget_handles_empty"]

    def test_prompt_includes_failing_test_names(
        self, valid_instance: SweInstance, tmp_path: Path
    ) -> None:
        prompt = _build_swe_prompt(valid_instance, tmp_path / "ws")
        assert "test_widget_handles_empty" in prompt
        assert "tests/test_widget.py" in prompt

    def test_prompt_includes_problem_statement(
        self, valid_instance: SweInstance, tmp_path: Path
    ) -> None:
        prompt = _build_swe_prompt(valid_instance, tmp_path / "ws")
        assert "should not crash on empty input" in prompt

    def test_prompt_includes_hints_when_present(
        self, valid_instance: SweInstance, tmp_path: Path
    ) -> None:
        prompt = _build_swe_prompt(valid_instance, tmp_path / "ws")
        assert "Look at widget.py line 42" in prompt

    def test_prompt_omits_hints_when_empty(self, tmp_path: Path) -> None:
        row = dict(VALID_HF_ROW, hints_text="")
        inst = SweInstance.from_hf_row(row)
        prompt = _build_swe_prompt(inst, tmp_path / "ws")
        assert "## Hints" not in prompt


# === UvVenvBackend pure-logic tests ==============================================

class TestUvVenvBackendPaths:
    def test_path_derivation(self, tmp_path: Path, valid_instance: SweInstance) -> None:
        backend = UvVenvBackend(cache_root=tmp_path)
        assert backend.repo_dir(valid_instance) == (
            tmp_path
            / "repos"
            / f"owner--repo--{valid_instance.base_commit}"
        )
        assert backend.venv_dir(valid_instance) == (
            tmp_path
            / "venvs"
            / f"owner--repo--{valid_instance.base_commit}--py311"
        )
        assert backend.workspace_dir(valid_instance, "smoke-1") == (
            tmp_path / "workspaces" / "smoke-1" / "owner__repo-12345"
        )
        assert backend.workspace_dir(valid_instance, "smoke-1", suffix="verify") == (
            tmp_path / "workspaces" / "smoke-1" / "owner__repo-12345--verify"
        )

    def test_post_init_creates_cache_dirs(self, tmp_path: Path) -> None:
        backend = UvVenvBackend(cache_root=tmp_path / "fresh")
        assert (backend.cache_root / "repos").is_dir()
        assert (backend.cache_root / "venvs").is_dir()
        assert (backend.cache_root / "workspaces").is_dir()

    def test_teardown_only_removes_within_workspaces(
        self, tmp_path: Path
    ) -> None:
        backend = UvVenvBackend(cache_root=tmp_path)
        outside = tmp_path / "elsewhere"
        outside.mkdir()
        # teardown should be a no-op for paths outside the workspaces tree.
        backend.teardown(outside)
        assert outside.exists(), "teardown shouldn't remove non-workspace dirs"

        ws = backend.workspace_dir(
            SweInstance.from_hf_row(VALID_HF_ROW), "smoke-1"
        )
        ws.mkdir(parents=True)
        (ws / "marker.txt").write_text("hi")
        backend.teardown(ws)
        assert not ws.exists()


# === Verifier ===================================================================

class StubBackend:
    """Minimal SandboxBackend stub that records calls and runs no real subprocess."""

    def __init__(
        self,
        f2p_pass: int = 1,
        f2p_total: int = 1,
        p2p_pass: int = 0,
        p2p_total: int = 0,
        setup_raises: bool = False,
    ):
        self.f2p_pass = f2p_pass
        self.f2p_total = f2p_total
        self.p2p_pass = p2p_pass
        self.p2p_total = p2p_total
        self.setup_raises = setup_raises
        self.setups: list[tuple] = []
        self.teardowns: list[Path] = []

    def setup(self, instance, run_id, suffix=""):  # type: ignore[no-untyped-def]
        self.setups.append((instance.instance_id, run_id, suffix))
        if self.setup_raises:
            raise SetupError("stub setup error")
        # Provision a real tempdir so the verifier can record scores.
        import tempfile

        path = Path(tempfile.mkdtemp(prefix=f"stub-{suffix or 'agent'}-"))
        return path

    def teardown(self, workspace_path):  # type: ignore[no-untyped-def]
        self.teardowns.append(workspace_path)
        import shutil

        shutil.rmtree(workspace_path, ignore_errors=True)

    def run_in_workspace(self, workspace_path, cmd, timeout_s):  # type: ignore[no-untyped-def]
        # Mock a pytest output string. We feed the verifier a string with
        # the right number of "PASSED" markers via _parse_pytest_summary's
        # last-line check.
        if cmd[0] == "pytest":
            args = cmd[3:] if len(cmd) > 3 else []  # `pytest --tb=short -x -q --no-header`
            # We can't tell here whether this is f2p or p2p call without
            # context; the verifier calls f2p first, then p2p.
            # Use a counter on self to alternate.
            n_tests = max(len(args) - 4, 0)  # filter out flags
            return self._make_pytest_result(n_tests, is_first_call=not hasattr(self, "_called_once"))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    def _make_pytest_result(self, n_tests, is_first_call):
        import subprocess as sp

        if is_first_call:
            self._called_once = True
            n_pass = self.f2p_pass
            n_total = self.f2p_total
        else:
            n_pass = self.p2p_pass
            n_total = self.p2p_total
        # Build PASSED markers + summary line consistent with our parser.
        passed_lines = "\n".join(["PASSED"] * n_pass)
        n_fail = max(n_total - n_pass, 0)
        if n_fail:
            summary = f"\n{n_pass} passed, {n_fail} failed in 0.1s"
        else:
            summary = f"\n{n_pass} passed in 0.1s"
        out = f"{passed_lines}{summary}"
        return sp.CompletedProcess(["pytest"], 0, stdout=out, stderr="")


class TestVerifier:
    def test_verifier_returns_1_when_all_pass(
        self, tmp_path: Path, valid_instance: SweInstance
    ) -> None:
        agent_ws = tmp_path / "agent-ws"
        agent_ws.mkdir()
        # Simulate a no-op git repo so _git_diff_head returns ""
        (agent_ws / ".git").mkdir()
        backend = StubBackend(f2p_pass=1, f2p_total=1, p2p_pass=0, p2p_total=0)
        with mock.patch("adapters.swe_bench._git_diff_head", return_value=""):
            with mock.patch(
                "adapters.swe_bench._apply_patch", return_value=(True, "")
            ):
                verify = _make_swe_verifier(
                    valid_instance, agent_ws, backend, "test-run"
                )
                # Empty pass_to_pass list → only fail_to_pass matters.
                inst_no_p2p = SweInstance.from_hf_row(
                    dict(VALID_HF_ROW, PASS_TO_PASS="[]")
                )
                verify_no_p2p = _make_swe_verifier(
                    inst_no_p2p, agent_ws, backend, "test-run"
                )
                score = verify_no_p2p("done")
                assert score == 1.0

    def test_verifier_returns_0_when_setup_fails(
        self, tmp_path: Path, valid_instance: SweInstance
    ) -> None:
        agent_ws = tmp_path / "agent-ws"
        agent_ws.mkdir()
        (agent_ws / ".git").mkdir()
        backend = StubBackend(setup_raises=True)
        with mock.patch("adapters.swe_bench._git_diff_head", return_value=""):
            verify = _make_swe_verifier(
                valid_instance, agent_ws, backend, "test-run"
            )
            score = verify("done")
        assert score == 0.0

    def test_verifier_returns_0_when_patch_doesnt_apply(
        self, tmp_path: Path, valid_instance: SweInstance
    ) -> None:
        agent_ws = tmp_path / "agent-ws"
        agent_ws.mkdir()
        (agent_ws / ".git").mkdir()
        backend = StubBackend()
        with mock.patch(
            "adapters.swe_bench._git_diff_head", return_value="bogus diff"
        ):
            with mock.patch(
                "adapters.swe_bench._apply_patch",
                return_value=(False, "patch malformed"),
            ):
                verify = _make_swe_verifier(
                    valid_instance, agent_ws, backend, "test-run"
                )
                score = verify("done")
        assert score == 0.0


# === apply_patch / git_diff_head with no-op inputs ==============================

class TestPatchHelpers:
    def test_apply_empty_patch_succeeds(self, tmp_path: Path) -> None:
        ok, err = _apply_patch(tmp_path, "")
        assert ok is True
        assert err == ""

    def test_apply_patch_invokes_git_apply(self, tmp_path: Path) -> None:
        with mock.patch("subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            ok, err = _apply_patch(tmp_path, "diff stuff\n")
        assert ok is True
        assert run.called
        cmd = run.call_args[0][0]
        assert "git" in cmd[0]
        assert "apply" in cmd

    def test_git_diff_head_returns_empty_on_failure(self, tmp_path: Path) -> None:
        # Real git invocation in a non-repo dir will fail; expect empty string.
        # (No need to mock — this exercises the actual `git diff` error path.)
        result = _git_diff_head(tmp_path)
        assert result == ""


# === Curated pilot instances ====================================================

class TestCuratedPilotInstances:
    def test_returns_two_distinct_ids(self) -> None:
        ids = curated_pilot_instances()
        assert len(ids) >= 2
        assert len(set(ids)) == len(ids)

    def test_ids_match_canonical_format(self) -> None:
        ids = curated_pilot_instances()
        for iid in ids:
            # The validator regex asserts the format; constructing a partial
            # SweInstance with the iid alone isn't possible (other fields are
            # required), so we re-derive the regex check inline.
            from adapters.swe_types import _INSTANCE_ID_PATTERN

            assert _INSTANCE_ID_PATTERN.match(iid), iid
