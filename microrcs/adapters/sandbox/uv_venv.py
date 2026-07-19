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

from .. import swe_specs
from ..swe_types import SweInstance
from .backend import SetupError

# Written at the venv root ONLY after a full install completes (spec step 4
# or floating success). Presence => the venv is fully built and safe to reuse;
# `bin/python` present but this absent => half-init, rebuild (BRO-1949).
_SENTINEL_NAME = ".microrcs_spec_ok"

# Written at the venv root by `repoint_editable`, recording which workspace the
# shared venv's single editable pointer currently aims at. Lets the scoring
# path detect a parallel same-instance repoint race and fail loudly instead of
# scoring against cross-contaminated imports (BRO-1949).
_EDITABLE_MARKER = ".microrcs_editable_at"


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

    def _resolve_python(self, instance: SweInstance) -> str:
        """Python toolchain for this instance: the canonical swebench spec's
        `python` when available (per-instance fidelity — flask@2.3 wants 3.11,
        most 2022-vintage repos want 3.9), else the backend default."""
        spec = swe_specs.spec_for(instance)
        if spec and spec.get("python"):
            return str(spec["python"])
        return self.python_version

    def venv_dir(self, instance: SweInstance) -> Path:
        # CodeRabbit catch: key venv cache by python_version too — otherwise
        # changing the default Python (e.g., 3.12 → 3.11) silently reuses an
        # incompatible cached venv from a prior config. BRO-1948: the version
        # is now per-instance (from the swebench spec), so the key reflects it,
        # AND a `-sb` recipe tag when a swebench spec drives the build — so a
        # spec-pinned venv never collides with a stale floating-install venv
        # from before the fidelity fix (the exact flask stale-cache miss).
        py = self._resolve_python(instance).replace(".", "")
        tag = "-sb" if (swe_specs.HAS_SWEBENCH and swe_specs.spec_for(instance)) else ""
        return (
            self.cache_root
            / "venvs"
            / f"{instance.repo_slug}--{instance.base_commit}--py{py}{tag}"
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

    def _venv_env(self, workspace_path: Path) -> dict:
        venv_bin = self._venv_bin_from_workspace(workspace_path)
        env = os.environ.copy()
        env["VIRTUAL_ENV"] = str(venv_bin.parent)
        env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
        env.pop("PYTHONHOME", None)
        return env

    def repoint_editable(
        self, workspace_path: Path, timeout_s: float = 300.0
    ) -> None:
        """Redirect the venv's editable install to point at THIS workspace
        (BRO-1948). The venv is shared across the agent + verify workspaces, so
        its single editable pointer must be re-aimed at whichever workspace is
        about to run tests — otherwise source edits (agent fix / gold patch)
        are invisible and every episode silently scores 0 regardless of the
        harness. `--no-deps` keeps it fast (runtime deps already in the venv;
        build deps come from uv's isolated build env).

        ASSUMES SERIAL EXECUTION: the venv (keyed by repo+commit+py) is shared,
        and GenerationLoop runs episodes serially, so each consumer repoints
        immediately before use. Parallelizing episodes of the SAME instance
        (e.g. P5 multi-seed) would race on this single pointer — give each
        parallel worker its own venv/workspace first. As a backstop (BRO-1949)
        the repoint records the target workspace in the venv and
        `run_test_command` asserts the pointer is still ours before scoring, so
        a race fails loudly instead of scoring against the wrong workspace."""
        env = self._venv_env(workspace_path)
        r = subprocess.run(
            [self.uv_path, "pip", "install", "-e", ".", "--no-deps"],
            cwd=str(workspace_path), env=env,
            capture_output=True, text=True, timeout=timeout_s,
        )
        if r.returncode != 0:
            raise SetupError(
                f"repoint_editable failed in {workspace_path}: "
                f"{(r.stderr or r.stdout)[-500:]}"
            )
        # Record which workspace the shared venv's editable pointer now aims at
        # (BRO-1949 parallel-repoint-race backstop).
        self._editable_marker_path(workspace_path).write_text(str(workspace_path))

    def run_test_command(
        self, workspace_path: Path, command: str, timeout_s: float
    ) -> subprocess.CompletedProcess[str]:
        """Run a test command STRING inside the workspace with the venv
        activated. The command may carry env prefixes + a custom runner
        (e.g. sympy's `PYTHONWARNINGS='...' bin/test -C --verbose`), so it runs
        through the shell. Does not raise on test failures.

        Asserts the shared venv's editable pointer still aims at THIS workspace
        before running (BRO-1949) — a parallel same-instance repoint would
        otherwise silently score against the wrong source tree."""
        self._assert_editable_pointer(workspace_path)
        return subprocess.run(
            command, cwd=str(workspace_path), env=self._venv_env(workspace_path),
            shell=True, capture_output=True, text=True, timeout=timeout_s,
        )

    def _editable_marker_path(self, workspace_path: Path) -> Path:
        """The shared venv's editable-pointer marker for this workspace's venv.

        Resolved from the workspace's `.microrcs_venv` marker, so it names the
        SAME venv the tests will import from."""
        return self._venv_bin_from_workspace(workspace_path).parent / _EDITABLE_MARKER

    def _assert_editable_pointer(self, workspace_path: Path) -> None:
        """Fail loudly on a parallel same-instance repoint race (BRO-1949).

        The venv (keyed by repo+commit+py) is shared across the agent + verify
        workspaces and carries a SINGLE editable pointer, repointed immediately
        before each test run. Serial execution (GenerationLoop) keeps that safe.
        If a parallel worker for the same instance repoints between our repoint
        and our test run, the pointer now aims at THEIR workspace and our scores
        would be silently cross-contaminated. Convert that into a clear error.

        An absent marker means no repoint happened through this backend (older
        venv / a non-repoint code path); stay silent then, for backward
        compatibility — the guard only trips on a definite mismatch."""
        marker = self._editable_marker_path(workspace_path)
        if not marker.exists():
            return
        pointed_at = marker.read_text().strip()
        if pointed_at != str(workspace_path):
            raise SetupError(
                f"parallel repoint race: the shared venv editable pointer is "
                f"aimed at {pointed_at!r}, not this workspace "
                f"{str(workspace_path)!r}. Episodes of the same instance must "
                f"not run in parallel on one venv — give each parallel worker "
                f"its own venv/workspace."
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
        # Half-init detection (BRO-1949): reuse only a venv carrying the
        # completion sentinel, written at the very end of construction. The
        # prior `any *.dist-info` heuristic false-passed on a venv where
        # `_install_from_spec` installed deps (steps 1-2, which carry
        # dist-info) but then FAILED at step 4 (the target package) — leaving
        # a persistent score-0 for a genuinely un-installable instance until
        # the cache was cleared by hand. The sentinel is precise: present =>
        # fully built, reuse; `bin/python` present but sentinel absent =>
        # half-init (or a venv built before this fix), so nuke and rebuild.
        if (venv_dir / "bin" / "python").exists():
            if (venv_dir / _SENTINEL_NAME).exists():
                return
            shutil.rmtree(venv_dir, ignore_errors=True)
        venv_dir.parent.mkdir(parents=True, exist_ok=True)
        # Per-instance Python from the swebench spec (BRO-1948) — env fidelity.
        # `--seed` provisions pip/setuptools/wheel so the spec's install command
        # (`python -m pip install -e .`) runs verbatim (a bare uv venv has no
        # pip → "No module named pip").
        py = self._resolve_python(instance)
        subprocess.run(
            [self.uv_path, "venv", "--seed", "--python", py, str(venv_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        repo_dir = self.repo_dir(instance)
        env = os.environ.copy()
        env["VIRTUAL_ENV"] = str(venv_dir)
        env["PATH"] = f"{venv_dir / 'bin'}{os.pathsep}{env.get('PATH', '')}"
        env.pop("PYTHONHOME", None)
        spec = swe_specs.spec_for(instance) if swe_specs.HAS_SWEBENCH else None
        if spec:
            self._install_from_spec(instance, spec, repo_dir, venv_dir, env)
        else:
            self._install_floating(instance, repo_dir, env)
        # Completion sentinel (BRO-1949): reached ONLY if the install above did
        # not raise. A half-init venv (install failed mid-way) never gets this
        # marker, so the next setup() rebuilds it instead of reusing a partial
        # env. Written last, so its presence proves construction finished.
        (venv_dir / _SENTINEL_NAME).write_text("spec" if spec else "floating")

    def _install_from_spec(
        self,
        instance: SweInstance,
        spec: dict,
        repo_dir: Path,
        venv_dir: Path,
        env: dict,
    ) -> None:
        """Canonical swebench install: pinned deps + pre_install + spec install.

        Reproduces the environment the SWE-bench Docker harness builds, in a
        venv: exact dependency versions (so flask@2.3 keeps Werkzeug==2.3.7 and
        `url_quote` survives), any `pre_install` source edits, then the spec's
        install command. The target package's editable pointer is redirected to
        each per-episode workspace by `repoint_editable`; here it seeds the
        venv with the package + its test dependencies.
        """
        # 1. base packages: a requirements.txt (fetched + cleaned by swebench)
        #    or a space-separated conda/pip list. Test runner belt-and-braces
        #    for every repo EXCEPT pytest itself (which IS the package).
        pkgs = spec.get("packages", "")
        extra = [] if instance.repo == "pytest-dev/pytest" else ["pytest"]
        if pkgs == "requirements.txt":
            reqs = swe_specs.requirements_text(instance)
            reqs_file = venv_dir.parent / f"{instance.instance_id}-reqs.txt"
            reqs_file.write_text(reqs)
            try:
                self._uv_pip(["install", "-r", str(reqs_file), *extra], repo_dir, env)
            finally:
                reqs_file.unlink(missing_ok=True)
        elif pkgs and pkgs != "environment.yml":
            self._uv_pip(["install", *pkgs.split(), *extra], repo_dir, env)
        elif extra:
            self._uv_pip(["install", *extra], repo_dir, env)
        # 2. pinned pip_packages (the version lock that prevents rot).
        if spec.get("pip_packages"):
            self._uv_pip(["install", *spec["pip_packages"]], repo_dir, env)
        # 3. pre_install source edits (sed on setup.py etc.). Deferred repos
        #    (tox-based, e.g. sphinx) are excluded upstream by venv_support.
        for pre in spec.get("pre_install") or []:
            subprocess.run(
                pre, cwd=repo_dir, env=env, shell=True,
                check=True, capture_output=True, text=True,
            )
        # 4. spec install — seeds the venv with the package + its test extras.
        #    Run faithfully (it may be `-e .`, `-e .[test]`, or plain `.`);
        #    repoint_editable makes the workspace authoritative per episode.
        install_cmd = spec.get("install", "python -m pip install -e .")
        r = subprocess.run(
            install_cmd, cwd=repo_dir, env=env, shell=True,
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise SetupError(
                f"spec install failed for {instance.instance_id} "
                f"({install_cmd!r}): {(r.stderr or r.stdout)[-500:]}"
            )

    def _install_floating(
        self, instance: SweInstance, repo_dir: Path, env: dict
    ) -> None:
        """Legacy fallback (no swebench spec): floating `-e .[extras]` install.

        Kept for repos without a swebench spec and for offline unit tests. This
        is the rot-prone path BRO-1948 replaces wherever a spec exists.
        """
        for extras in (".[test]", ".[testing]", ".[tests]", ".[dev]", "."):
            try:
                subprocess.run(
                    [self.uv_path, "pip", "install", "-e", extras, "pytest"],
                    cwd=repo_dir, env=env, check=True,
                    capture_output=True, text=True,
                )
                return
            except subprocess.CalledProcessError:
                continue
        raise SetupError(
            f"could not install {instance.repo} into venv (no swebench spec; "
            f"tried [test], [testing], [tests], [dev], plain '.')"
        )

    def _uv_pip(self, args: list[str], cwd: Path, env: dict) -> None:
        r = subprocess.run(
            [self.uv_path, "pip", *args], cwd=cwd, env=env,
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise SetupError(
                f"`uv pip {' '.join(args)}` failed: {(r.stderr or r.stdout)[-500:]}"
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
        # BRO-1948: guarantee a pristine base tree regardless of any dirt in
        # the shared canonical clone (stray egg-info/build artifacts from an
        # editable install, or a patch left applied by a prior run — the flask
        # cache-pollution class that made empty-diff falsely PASS). Reset
        # tracked files to base_commit and remove untracked cruft so the
        # workspace starts at EXACTLY base, before test_patch is applied.
        for args in (
            ["reset", "--hard", instance.base_commit],
            ["clean", "-fdx"],
        ):
            subprocess.run(
                [self.git_path, "-C", str(ws), *args],
                check=True, capture_output=True, text=True,
            )
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
