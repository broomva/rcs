"""SWE-bench-Lite adapter for microRCS.

Translates HuggingFace SWE-bench-Lite instances into microRCS `Task`s with
custom verifiers. Smoke test ships with 2 hand-picked instances curated for
venv-without-Docker compatibility.

Convention for the agent: edit files in the workspace via bash; the verifier
reads `git diff HEAD` from the workspace at episode end. The agent's `submit`
message is informational. Final score is 1.0 iff every test in
`FAIL_TO_PASS` now passes AND every test in `PASS_TO_PASS` still passes.

Public surface:
- `load_swe_bench_lite_subset(instance_ids, backend)` -> list[m.Task]
- `curated_pilot_instances()` -> list[str]
- `make_swe_task(instance, backend, run_id)` -> m.Task
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Callable

# Allow `from .. import microrcs` style import via `microrcs/microrcs.py`
_MICROCRS_DIR = Path(__file__).resolve().parents[1]
if str(_MICROCRS_DIR) not in sys.path:
    sys.path.insert(0, str(_MICROCRS_DIR))
import microrcs as m  # noqa: E402

from .sandbox import SandboxBackend, SetupError, UvVenvBackend  # noqa: E402
from .swe_types import SweInstance, SweScore  # noqa: E402


# === Curated pilot instances ============================================
def curated_pilot_instances() -> list[str]:
    """Two hand-picked instances proven to install + test in venv-no-Docker.

    Selection criteria:
    - Pure Python (no C extensions, no system libs)
    - `pip install -e .` works without flags
    - FAIL_TO_PASS = small handful of tests
    - Repo clone < 200 MB

    These IDs are locked here after live HF verification (see Phase 7 of
    the implementation plan). To re-curate, follow the workflow in
    `microrcs/adapters/AGENTS.md` § "Instance curation".
    """
    return [
        # Flask — add file-mode param to Config.from_file (Python 3.11 TOML).
        # 1 FAIL_TO_PASS, 18 PASS_TO_PASS, 42-line patch, pure Python, ships
        # without C extensions; `pip install -e .` works on a clean venv.
        "pallets__flask-4992",
        # Pylint — `--recursive=y` should respect `ignore-paths`. 1 FAIL_TO_PASS,
        # 11-line patch, pure Python, modern (2022-vintage). Note: requests-863
        # was originally chosen but its 2014-vintage urllib3 imports
        # `collections.MutableMapping` which doesn't exist in Python ≥3.10.
        "pylint-dev__pylint-7080",
    ]


# === Prompt builder =====================================================
_FAILING_TEST_RE = re.compile(r"^\+\+\+ b/(.+\.py)\b", re.MULTILINE)
_TEST_FUNC_RE = re.compile(r"^\+\s*def (test_\w+)\(", re.MULTILINE)


def _extract_failing_test_files(test_patch: str) -> list[str]:
    """Return relative paths of test files added/modified by `test_patch`."""
    files = sorted(set(_FAILING_TEST_RE.findall(test_patch)))
    return [f for f in files if "test" in f.lower()]


def _extract_failing_test_names(test_patch: str) -> list[str]:
    """Return names of test_ functions added by `test_patch`."""
    return sorted(set(_TEST_FUNC_RE.findall(test_patch)))


def _build_swe_prompt(instance: SweInstance, workspace_path: Path) -> str:
    """Front-loaded prompt: agent doesn't need to grep for test names.

    Per harness-engineering Practice 5 (optimize for agent flow), we include
    durable context up front: the failing test names parsed from `test_patch`,
    the file the failing test lives in, and the problem statement. The agent
    can spend its budget on the actual fix instead of re-discovering context.
    """
    failing_files = _extract_failing_test_files(instance.test_patch) or [
        "(could not parse from test_patch — search for the failing test)",
    ]
    failing_names = _extract_failing_test_names(instance.test_patch) or list(
        instance.fail_to_pass
    )

    lines = [
        f"# SWE-bench-Lite task: {instance.instance_id}",
        "",
        "You are debugging a real GitHub issue. The repository is checked out",
        f"in your current working directory ({workspace_path}). A test_patch",
        "has already been applied to your workspace, so the failing tests are",
        "present on disk and currently FAIL.",
        "",
        "## Goal",
        "",
        "Edit the source code so that the failing tests pass. The grading",
        "checks two things:",
        "1. Every test in FAIL_TO_PASS must now pass.",
        "2. Every test in PASS_TO_PASS must still pass (no regressions).",
        "",
        "## Repository",
        "",
        f"- Repo: `{instance.repo}` at base commit `{instance.base_commit[:12]}`",
        f"- Workspace: `{workspace_path}` (you are already cd'd here)",
        f"- Python venv: pre-built; `python` and `pytest` are on PATH",
        "",
        "## Failing tests (already present in your workspace)",
        "",
        f"- Files modified by test_patch: {', '.join(failing_files)}",
        f"- Test names: {', '.join(failing_names[:8]) or '(see FAIL_TO_PASS below)'}",
        "",
        "FAIL_TO_PASS (must pass after your fix):",
    ]
    for t in instance.fail_to_pass[:20]:
        lines.append(f"  - {t}")
    if len(instance.pass_to_pass) > 0:
        lines.append("")
        lines.append("PASS_TO_PASS (sample — must remain passing):")
        for t in instance.pass_to_pass[:5]:
            lines.append(f"  - {t}")
    lines += [
        "",
        "## Issue / problem statement",
        "",
        instance.problem_statement.strip(),
    ]
    if instance.hints_text.strip():
        lines += [
            "",
            "## Hints",
            "",
            instance.hints_text.strip(),
        ]
    lines += [
        "",
        "## How to work",
        "",
        "Use bash to read source files (`cat`, `rg`, `grep`, `find`).",
        "Edit files in place (`sed -i ''`, or `cat > file` with full content).",
        "Run the failing test directly: `pytest -x <path/to/test_file.py::test_name>`",
        "Iterate until the failing tests pass.",
        "",
        "When done, call `submit` with a one-line summary of your fix. The",
        "verifier reads `git diff HEAD` from your workspace — your edits ARE",
        "your submission; the submit-message is just informational.",
    ]
    return "\n".join(lines)


# === Verifier ============================================================
def _git_diff_head(workspace: Path) -> str:
    """Return the agent's accumulated edits as a unified diff."""
    result = subprocess.run(
        ["git", "-C", str(workspace), "diff", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def _apply_patch(workspace: Path, patch_text: str) -> tuple[bool, str]:
    """Apply `patch_text` to `workspace`; return (success, error_msg)."""
    if not patch_text.strip():
        return True, ""  # nothing to apply
    proc = subprocess.run(
        ["git", "-C", str(workspace), "apply", "--whitespace=nowarn", "-"],
        input=patch_text,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return False, proc.stderr.strip()[:500]
    return True, ""


def _count_pytest_passes(
    backend: SandboxBackend,
    workspace: Path,
    test_ids: tuple[str, ...],
    timeout_s: float,
) -> tuple[int, int, str]:
    """Run pytest on `test_ids`; return (passing, total, stderr_tail)."""
    if not test_ids:
        return 0, 0, ""
    cmd = ["pytest", "--tb=short", "-x", "-q", "--no-header", *test_ids]
    try:
        proc = backend.run_in_workspace(workspace, cmd, timeout_s=timeout_s)
    except subprocess.TimeoutExpired as exc:
        return 0, len(test_ids), f"pytest timeout after {timeout_s}s: {exc}"
    out = proc.stdout + "\n" + proc.stderr
    passed = len(re.findall(r"PASSED", out)) or _parse_pytest_summary(out, "passed")
    total = len(test_ids)
    if passed > total:
        passed = total
    stderr_tail = (proc.stderr or "")[-1000:]
    return passed, total, stderr_tail


_SUMMARY_RE = re.compile(r"(\d+) (passed|failed|error|skipped)")


def _parse_pytest_summary(output: str, want: str) -> int:
    """Parse `pytest -q` summary line for a count of `want` outcomes."""
    last_line = output.strip().splitlines()[-1] if output.strip() else ""
    matches = _SUMMARY_RE.findall(last_line)
    for n, kind in matches:
        if kind == want:
            return int(n)
    return 0


def _make_swe_verifier(
    instance: SweInstance,
    agent_workspace: Path,
    backend: SandboxBackend,
    run_id: str,
    pytest_timeout_s: float = 120.0,
) -> Callable[[str], float]:
    """Build a verifier closure. Returns 1.0 iff FAIL_TO_PASS all pass and
    PASS_TO_PASS all still pass; 0.0 otherwise.

    Signature is single-arg `(answer: str) -> float` to match microRCS's
    `task.verify(shielded.answer)` call site. The agent's workspace path is
    captured in the closure (it was provisioned at task-construction time).

    The verifier runs in a SIBLING workspace under suffix='verify' so the
    agent's mid-run state isn't disturbed. Agent edits are extracted via
    `git diff HEAD` from `agent_workspace`, then applied to the sibling
    workspace before pytest runs.
    """

    def verify(answer: str) -> float:  # noqa: ARG001 — `answer` is informational
        # Extract agent's edits.
        patch_text = _git_diff_head(agent_workspace)
        # Provision sibling workspace for verification.
        try:
            verify_ws = backend.setup(instance, run_id, suffix="verify")
        except SetupError as exc:
            _record_score(
                agent_workspace,
                instance,
                score=0.0,
                error=f"verify-workspace setup failed: {exc}",
            )
            return 0.0
        try:
            applied, apply_err = _apply_patch(verify_ws, patch_text)
            if not applied:
                _record_score(
                    agent_workspace,
                    instance,
                    score=0.0,
                    error=f"agent patch did not apply: {apply_err}",
                    pytest_stderr_tail="",
                )
                return 0.0
            t0 = time.monotonic()
            f2p_pass, f2p_total, f2p_err = _count_pytest_passes(
                backend, verify_ws, instance.fail_to_pass, pytest_timeout_s
            )
            p2p_pass, p2p_total, p2p_err = _count_pytest_passes(
                backend, verify_ws, instance.pass_to_pass[:10], pytest_timeout_s
            )
            duration = time.monotonic() - t0
            score_value = (
                1.0
                if f2p_total > 0
                and f2p_pass == f2p_total
                and p2p_pass == p2p_total
                else 0.0
            )
            _record_score(
                agent_workspace,
                instance,
                score=score_value,
                f2p_pass=f2p_pass,
                f2p_total=f2p_total,
                p2p_pass=p2p_pass,
                p2p_total=p2p_total,
                duration_s=duration,
                error=None,
                pytest_stderr_tail=(f2p_err or p2p_err)[-1000:],
            )
            return score_value
        finally:
            backend.teardown(verify_ws)

    return verify


def _record_score(
    agent_workspace: Path,
    instance: SweInstance,
    *,
    score: float,
    f2p_pass: int = 0,
    f2p_total: int = 0,
    p2p_pass: int = 0,
    p2p_total: int = 0,
    duration_s: float = 0.0,
    error: str | None = None,
    pytest_stderr_tail: str = "",
) -> None:
    """Append a SweScore JSON line to <run_root>/swe_scores.jsonl.

    `agent_workspace` is the per-instance workspace under
    `<cache_root>/workspaces/<run_id>/<instance_id>/`. We climb two levels to
    reach the run root and write a shared scores log there.
    """
    score_obj = SweScore(
        instance_id=instance.instance_id,
        score=float(score),
        fail_to_pass_passing=int(f2p_pass),
        fail_to_pass_total=max(int(f2p_total), int(f2p_pass)),
        pass_to_pass_passing=int(p2p_pass),
        pass_to_pass_total=max(int(p2p_total), int(p2p_pass)),
        pytest_duration_s=max(float(duration_s), 0.0),
        error=error,
        pytest_stderr_tail=pytest_stderr_tail,
    )
    out_path = agent_workspace.parent / "swe_scores.jsonl"
    try:
        import dataclasses
        import json

        with out_path.open("a") as fh:
            fh.write(json.dumps(dataclasses.asdict(score_obj)) + "\n")
    except Exception:  # noqa: BLE001
        # Score-recording failures must never fail the verifier — the
        # in-memory float is what the run loop reads.
        traceback.print_exc()


# === Loader ==============================================================
def make_swe_task(
    instance: SweInstance,
    backend: SandboxBackend,
    run_id: str,
    *,
    pytest_timeout_s: float = 120.0,
) -> m.Task:
    """Build a microRCS Task for one SweInstance.

    The task's prompt is built lazily from the workspace path that the run
    loop will create, but L0Plant's run_episode signature passes `workspace`
    after construction. So we build the prompt with the canonical workspace
    path that `backend.setup()` returns, and pre-provision the workspace
    here at task-construction time.
    """
    # Pre-provision so the prompt can reference the actual path AND the
    # verifier closure can capture it. The smoke driver constructs an
    # `m.Workspace(path=agent_ws, run_id=run_id)` from the path in metadata
    # and passes it to L0Plant — keeping the agent's bash cwd inside the
    # SWE repo.
    agent_ws = backend.setup(instance, run_id)
    prompt = _build_swe_prompt(instance, agent_ws)
    verifier = _make_swe_verifier(
        instance, agent_ws, backend, run_id, pytest_timeout_s=pytest_timeout_s
    )
    return m.Task(
        id=instance.instance_id,
        domain="swe-bench-lite",
        prompt=prompt,
        verify=verifier,
        metadata={
            "swe_repo": instance.repo,
            "swe_base_commit": instance.base_commit,
            "swe_agent_workspace": str(agent_ws),
        },
    )


def load_swe_bench_lite_subset(
    instance_ids: list[str],
    backend: SandboxBackend,
    run_id: str,
    *,
    pytest_timeout_s: float = 120.0,
) -> list[m.Task]:
    """Load the requested SWE-bench-Lite instances and return microRCS Tasks.

    Requires `datasets` (HuggingFace). Fails fast with a clear message if the
    HF Hub is unreachable or any requested ID is missing from the dataset.
    """
    from datasets import load_dataset  # type: ignore[import-untyped]

    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    by_id = {row["instance_id"]: row for row in ds}
    missing = [iid for iid in instance_ids if iid not in by_id]
    if missing:
        sample = list(by_id.keys())[:3]
        raise KeyError(
            f"instance_id(s) {missing!r} not in SWE-bench_Lite split=test "
            f"({len(by_id)} total; sample IDs: {sample!r})"
        )
    instances = [SweInstance.from_hf_row(by_id[iid]) for iid in instance_ids]
    tasks = []
    for inst in instances:
        try:
            tasks.append(
                make_swe_task(
                    inst, backend, run_id, pytest_timeout_s=pytest_timeout_s
                )
            )
        except SetupError as exc:
            # Build a "broken task" that scores 0 with the setup error so the
            # smoke driver still produces a report row.
            tasks.append(_broken_task(inst, str(exc)))
    return tasks


def _broken_task(instance: SweInstance, error: str) -> m.Task:
    """Stand-in Task for instances that failed sandbox setup.

    Verifier signature must match `task.verify(answer)` — the call site in
    L0Plant.run_episode passes a single argument. (CodeRabbit caught this:
    a 2-arg lambda would have raised TypeError on first invocation.)
    """
    return m.Task(
        id=instance.instance_id,
        domain="swe-bench-lite",
        prompt=f"Task setup failed: {error}\n\nReturn an empty submission.",
        verify=lambda answer: 0.0,
        metadata={
            "swe_repo": instance.repo,
            "swe_setup_error": error,
        },
    )


__all__ = [
    "curated_pilot_instances",
    "make_swe_task",
    "load_swe_bench_lite_subset",
    "_build_swe_prompt",
    "_extract_failing_test_files",
    "_extract_failing_test_names",
    "_apply_patch",
    "_git_diff_head",
    "_make_swe_verifier",
]
