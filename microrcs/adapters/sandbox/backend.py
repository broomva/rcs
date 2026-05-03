"""SandboxBackend protocol — the seam between SWE-bench and the host.

Pattern from Flue: pluggable sandbox backends. Smoke test ships one impl
(`UvVenvBackend`); future Docker / sandbox-exec / Lima / Daytona slots in
without rewriting `swe_bench.py`. The Protocol is intentionally tiny: just
enough surface for setup, teardown, and running a subprocess in the box.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from ..swe_types import SweInstance


class SandboxBackend(Protocol):
    """Provisions per-episode workspaces and runs commands inside them.

    Implementations are responsible for: cloning the target repo (cached),
    building the Python venv (cached), creating a writable per-episode
    workspace, and applying the instance's `test_patch` so failing tests
    are present at episode start.
    """

    def setup(self, instance: SweInstance, run_id: str, suffix: str = "") -> Path:
        """Provision a writable workspace for `instance` under `run_id`.

        `suffix` lets the verifier create a sibling workspace (suffix='verify')
        without colliding with the agent's mid-run workspace.

        Returns the absolute path to the writable workspace, with `test_patch`
        already applied (so the failing tests exist on disk).

        Raises:
            SetupError: if the canonical clone or venv build failed.
        """
        ...

    def teardown(self, workspace_path: Path) -> None:
        """Remove a per-episode workspace. Cache layers are preserved."""
        ...

    def run_in_workspace(
        self,
        workspace_path: Path,
        cmd: list[str],
        timeout_s: float,
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess inside `workspace_path` with the venv activated.

        Captures stdout + stderr as text. Caller is responsible for handling
        non-zero return codes; this method does not raise on test failures.

        Raises:
            subprocess.TimeoutExpired: if the command exceeds `timeout_s`.
        """
        ...


class SetupError(RuntimeError):
    """Raised when a sandbox backend cannot provision a workspace."""
