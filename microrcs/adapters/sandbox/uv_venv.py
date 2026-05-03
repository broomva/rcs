"""UvVenvBackend — venv-based sandbox for the SWE-bench-Lite smoke.

Three-layer cache:
  repos/<owner>--<repo>--<sha>/    immutable canonical clone
  venvs/<repo>--<sha>/             immutable Python env (built once)
  workspaces/<run>/<inst>/         writable per-episode (APFS clonefile)

The agent gets the writable workspace; the verifier creates a sibling one
under `<run>/<inst>--verify/`. Test setup is applied to BOTH — the agent's
view starts with failing tests present.

Isolation level for the smoke test is intentionally minimal (process-level,
no syscall sandbox). The threat model is "agent gets confused and writes to
wrong path," not "adversarial agent." Real isolation belongs in a future
SandboxExecBackend / LimaBackend.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..swe_types import SweInstance
from .backend import SetupError


@dataclass
class UvVenvBackend:
    """Filesystem-cached venv-per-repo backend.

    `cache_root` is typically `~/.cache/microrcs-swe/`. Set `prefer_clonefile`
    to False to force a regular `cp -r` (useful in CI on non-APFS volumes).
    Set `uv_path` to override the discovered `uv` binary.

    `python_version` controls the venv's Python toolchain. Default 3.11 is
    the common-denominator: most 2022-vintage SWE-bench-Lite repos pin
    setuptools/wheel versions that don't survive Python 3.12 (which removed
    `pkgutil.ImpImporter`), but Python 3.11 still works with the older
    setuptools and is also recent enough for modern pyproject.toml-only
    builds. uv auto-downloads the toolchain if not installed locally.
    """

    cache_root: Path
    uv_path: str = "uv"
    git_path: str = "git"
    prefer_clonefile: bool = True
    python_version: str = "3.11"

    def __post_init__(self) -> None:
        self.cache_root = Path(self.cache_root).expanduser().resolve()
        (self.cache_root / "repos").mkdir(parents=True, exist_ok=True)
        (self.cache_root / "venvs").mkdir(parents=True, exist_ok=True)
        (self.cache_root / "workspaces").mkdir(parents=True, exist_ok=True)

    # ---- path derivation (pure, easy to unit test) ------------------------

    def repo_dir(self, instance: SweInstance) -> Path:
        return self.cache_root / "repos" / f"{instance.repo_slug}--{instance.base_commit}"

    def venv_dir(self, instance: SweInstance) -> Path:
        # CodeRabbit catch: key venv cache by python_version too — otherwise
        # changing the default Python (e.g., 3.12 → 3.11) silently reuses an
        # incompatible cached venv from a prior config.
        py = self.python_version.replace(".", "")
        return (
            self.cache_root
            / "venvs"
            / f"{instance.repo_slug}--{instance.base_commit}--py{py}"
        )

    def workspace_dir(
        self, instance: SweInstance, run_id: str, suffix: str = ""
    ) -> Path:
        leaf = instance.instance_id + (f"--{suffix}" if suffix else "")
        return self.cache_root / "workspaces" / run_id / leaf

    # ---- public Protocol surface ------------------------------------------

    def setup(
        self, instance: SweInstance, run_id: str, suffix: str = ""
    ) -> Path:
        try:
            self._ensure_canonical_clone(instance)
            self._ensure_venv(instance)
            ws = self._materialize_workspace(instance, run_id, suffix)
            self._apply_test_patch(ws, instance)
            return ws
        except subprocess.CalledProcessError as exc:
            raise SetupError(
                f"setup failed for {instance.instance_id}: "
                f"{exc.cmd!r} exited {exc.returncode}: {exc.stderr or exc.stdout}"
            ) from exc

    def teardown(self, workspace_path: Path) -> None:
        if workspace_path.is_dir() and workspace_path.is_relative_to(
            self.cache_root / "workspaces"
        ):
            shutil.rmtree(workspace_path, ignore_errors=True)

    def run_in_workspace(
        self,
        workspace_path: Path,
        cmd: list[str],
        timeout_s: float,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        venv_bin = self._venv_bin_from_workspace(workspace_path)
        env["VIRTUAL_ENV"] = str(venv_bin.parent)
        env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
        env.pop("PYTHONHOME", None)
        return subprocess.run(
            cmd,
            cwd=workspace_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )

    # ---- internals --------------------------------------------------------

    def _ensure_canonical_clone(self, instance: SweInstance) -> None:
        repo_dir = self.repo_dir(instance)
        # CodeRabbit catch: a half-initialized cache (`.git` exists but
        # checkout failed mid-way during a prior run) was being reused as
        # if it were healthy. Verify the working tree is actually at
        # base_commit before declaring the cache valid.
        if (repo_dir / ".git").is_dir():
            head = subprocess.run(
                [self.git_path, "-C", str(repo_dir), "rev-parse", "HEAD"],
                capture_output=True, text=True,
            )
            if head.returncode == 0 and head.stdout.strip() == instance.base_commit:
                return
            # Half-init: nuke and re-clone.
            shutil.rmtree(repo_dir, ignore_errors=True)
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://github.com/{instance.repo}.git"
        # Shallow clone of the base_commit only — far smaller than a full clone.
        subprocess.run(
            [self.git_path, "clone", "--quiet", url, str(repo_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [self.git_path, "-C", str(repo_dir), "checkout", "--quiet", instance.base_commit],
            check=True,
            capture_output=True,
            text=True,
        )

    def _ensure_venv(self, instance: SweInstance) -> None:
        venv_dir = self.venv_dir(instance)
        # Half-init detection: `bin/python` exists but the package wasn't
        # installed (no `.dist-info` directories). Nuke and rebuild rather
        # than silently reuse the broken venv.
        if (venv_dir / "bin" / "python").exists():
            site_packages = list(
                (venv_dir / "lib").glob("python*/site-packages")
            )
            has_install = any(
                any(sp.glob("*.dist-info")) for sp in site_packages
            )
            if has_install:
                return
            shutil.rmtree(venv_dir, ignore_errors=True)
        venv_dir.parent.mkdir(parents=True, exist_ok=True)
        # Create venv with the configured Python toolchain. uv will download
        # the toolchain if not installed. Default 3.11 maximizes compat with
        # 2022-vintage SWE-bench-Lite repos (see python_version docstring).
        subprocess.run(
            [self.uv_path, "venv", "--python", self.python_version, str(venv_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        # Install the repo + test deps. The repo's setup.py / pyproject is
        # what determines deps. `uv pip install -e .[test]` is the typical
        # incantation; we fall back to plain `-e .` if `[test]` extras don't
        # exist.
        repo_dir = self.repo_dir(instance)
        env = os.environ.copy()
        env["VIRTUAL_ENV"] = str(venv_dir)
        for spec in (".[test]", ".[testing]", ".[tests]", ".[dev]", "."):
            try:
                subprocess.run(
                    [self.uv_path, "pip", "install", "-e", spec, "pytest"],
                    cwd=repo_dir,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                return
            except subprocess.CalledProcessError:
                continue
        raise SetupError(
            f"could not install {instance.repo} into venv (tried [test], "
            f"[testing], [tests], [dev], plain '.')"
        )

    def _materialize_workspace(
        self, instance: SweInstance, run_id: str, suffix: str
    ) -> Path:
        ws = self.workspace_dir(instance, run_id, suffix)
        if ws.exists():
            shutil.rmtree(ws)
        ws.parent.mkdir(parents=True, exist_ok=True)
        repo_dir = self.repo_dir(instance)
        copied = False
        # Prefer APFS clonefile via `cp -c` on Mac (near-instant, COW).
        # Fallback: regular recursive copy.
        if self.prefer_clonefile:
            try:
                subprocess.run(
                    ["cp", "-c", "-R", str(repo_dir), str(ws)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                copied = True
            except subprocess.CalledProcessError:
                # cp -c can fail on non-APFS volumes; flip the flag off so
                # we don't pay for a doomed `cp -c` on every subsequent
                # workspace setup. (CodeRabbit perf catch.)
                self.prefer_clonefile = False
        if not copied:
            shutil.copytree(repo_dir, ws, symlinks=True)
        # Write the venv marker so run_in_workspace can locate the venv from
        # just a workspace path (the Protocol only exposes Path).
        (ws / ".microrcs_venv").write_text(str(self.venv_dir(instance)))
        return ws

    def _apply_test_patch(self, workspace: Path, instance: SweInstance) -> None:
        # Pipe the test_patch through `git apply`. Failure is treated as a
        # SetupError because without test_patch the failing tests aren't on
        # disk and the verifier has nothing to score.
        result = subprocess.run(
            [self.git_path, "-C", str(workspace), "apply", "--whitespace=nowarn", "-"],
            input=instance.test_patch,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SetupError(
                f"failed to apply test_patch for {instance.instance_id}: "
                f"{result.stderr.strip()[:500]}"
            )
        # Commit the test_patch as a new HEAD so the verifier's `git diff HEAD`
        # captures ONLY the agent's source edits, not the test_patch we just
        # applied. Without this, the verifier picks up the test_patch as part
        # of the agent's "diff" and fails to apply it cleanly to the sibling
        # workspace (which already has test_patch applied at its own setup).
        for cmd in (
            [self.git_path, "-C", str(workspace), "config", "user.email", "microrcs@local"],
            [self.git_path, "-C", str(workspace), "config", "user.name", "microrcs"],
            [self.git_path, "-C", str(workspace), "add", "-A"],
            [
                self.git_path, "-C", str(workspace), "commit",
                "--allow-empty", "-q", "--no-gpg-sign",
                "-m", f"microrcs: apply test_patch for {instance.instance_id}",
            ],
        ):
            subprocess.run(cmd, check=True, capture_output=True, text=True)

    def _venv_bin_from_workspace(self, workspace_path: Path) -> Path:
        # Workspace dir name is `<instance_id>` or `<instance_id>--<suffix>`.
        # Recover instance_id by stripping any `--<suffix>` and look up the venv.
        leaf = workspace_path.name.split("--", 1)[0]
        run_dir = workspace_path.parent
        # The venv lives at venvs/<repo_slug>--<sha>/ — we don't have direct
        # access to the SweInstance here, so we infer from the canonical
        # clone's git remote + HEAD. Cheap fallback: scan venvs/ for one
        # whose `bin/python` works and whose dir name appears in our cache.
        # Simpler: callers always know the instance, so they pass it via
        # an adjacent helper. We expose `venv_bin_for_instance` for verifier.
        # For agent-driven L0Plant calls, `run_in_workspace` is used by the
        # verifier — at that point the verifier knows the instance. So we
        # use a marker file written at setup time:
        marker = workspace_path / ".microrcs_venv"
        if marker.exists():
            return Path(marker.read_text().strip()) / "bin"
        # Last resort: walk venvs/ looking for one whose name suffix is a SHA
        # that matches a directory in this run's workspace. Rare path.
        raise SetupError(
            f"workspace {workspace_path} missing .microrcs_venv marker; "
            f"setup() must write it"
        )
