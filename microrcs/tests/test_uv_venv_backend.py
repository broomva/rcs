"""Unit tests for UvVenvBackend robustness fixes (BRO-1949).

Two deferred-robustness follow-ups from the BRO-1948 P20 review:
- Half-init completion sentinel: a venv is reused only if it carries the
  `.microrcs_spec_ok` marker written at the very end of construction, so a
  build that failed mid-install is rebuilt instead of silently reused.
- Parallel same-instance repoint-race guard: the shared venv records which
  workspace its editable pointer aims at; the scoring path asserts it still
  points at THIS workspace before running tests.

All tests are pure filesystem — no `uv`, no `swebench`, no network — so they
run in CI (which installs neither).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402

from adapters import swe_specs  # noqa: E402
from adapters.sandbox.backend import SetupError  # noqa: E402
from adapters.sandbox.uv_venv import (  # noqa: E402
    _EDITABLE_MARKER,
    _SENTINEL_NAME,
    UvVenvBackend,
)
from adapters.swe_types import SweInstance  # noqa: E402


def _inst(**over) -> SweInstance:
    base = dict(
        instance_id="pallets__flask-4992",
        repo="pallets/flask",
        base_commit="0" * 40,
        problem_statement="fix the bug",
        hints_text="",
        test_patch="diff --git a/t.py b/t.py\n",
        patch="",
        fail_to_pass=("t1",),
        pass_to_pass=(),
        version="2.3",
    )
    base.update(over)
    return SweInstance(**base)


def _fake_bin_python(venv_dir: Path) -> None:
    (venv_dir / "bin").mkdir(parents=True, exist_ok=True)
    (venv_dir / "bin" / "python").write_text("#!/bin/sh\n")


# ---- #1 half-init completion sentinel -------------------------------------
def test_ensure_venv_reuses_when_sentinel_present(tmp_path, monkeypatch):
    # A venv with bin/python AND the sentinel is fully built => reuse, no
    # subprocess (rebuild) at all.
    backend = UvVenvBackend(cache_root=tmp_path)
    inst = _inst()
    venv_dir = backend.venv_dir(inst)
    _fake_bin_python(venv_dir)
    (venv_dir / _SENTINEL_NAME).write_text("spec")

    def _boom(*a, **k):  # any subprocess call means we tried to rebuild
        raise AssertionError(f"unexpected rebuild subprocess: {a!r}")

    monkeypatch.setattr("adapters.sandbox.uv_venv.subprocess.run", _boom)
    backend._ensure_venv(inst)  # must return without raising


def test_ensure_venv_rebuilds_when_sentinel_absent(tmp_path, monkeypatch):
    # bin/python present but NO sentinel => half-init: nuke and rebuild, then
    # write the sentinel once the (mocked) install succeeds.
    monkeypatch.setattr(swe_specs, "HAS_SWEBENCH", False)
    monkeypatch.setattr(swe_specs, "MAP_REPO_VERSION_TO_SPECS", {})
    backend = UvVenvBackend(cache_root=tmp_path)
    inst = _inst()
    venv_dir = backend.venv_dir(inst)
    _fake_bin_python(venv_dir)
    (venv_dir / "stale-artifact").write_text("from the broken build")

    def _fake_run(cmd, *a, **k):  # the `uv venv --seed` call: recreate bin
        _fake_bin_python(venv_dir)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    installs: list = []
    monkeypatch.setattr("adapters.sandbox.uv_venv.subprocess.run", _fake_run)
    monkeypatch.setattr(backend, "_install_floating", lambda *a, **k: installs.append(1))

    backend._ensure_venv(inst)

    assert installs == [1], "install path must run on rebuild"
    assert (venv_dir / _SENTINEL_NAME).exists(), "sentinel written after build"
    assert not (venv_dir / "stale-artifact").exists(), "stale venv was removed"


def test_sentinel_not_written_when_install_fails(tmp_path, monkeypatch):
    # A failing install must leave the venv WITHOUT the sentinel, so the next
    # setup() rebuilds it rather than reusing a half-init env.
    monkeypatch.setattr(swe_specs, "HAS_SWEBENCH", False)
    monkeypatch.setattr(swe_specs, "MAP_REPO_VERSION_TO_SPECS", {})
    backend = UvVenvBackend(cache_root=tmp_path)
    inst = _inst()
    venv_dir = backend.venv_dir(inst)

    def _fake_run(cmd, *a, **k):
        _fake_bin_python(venv_dir)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def _boom_install(*a, **k):
        raise SetupError("install exploded at the target package")

    monkeypatch.setattr("adapters.sandbox.uv_venv.subprocess.run", _fake_run)
    monkeypatch.setattr(backend, "_install_floating", _boom_install)

    with pytest.raises(SetupError):
        backend._ensure_venv(inst)
    assert not (venv_dir / _SENTINEL_NAME).exists(), "no sentinel on failed build"


# ---- #2 parallel same-instance repoint-race guard -------------------------
def _workspace_pointing_at(tmp_path: Path, venv_dir: Path, name: str) -> Path:
    ws = tmp_path / name
    ws.mkdir(parents=True, exist_ok=True)
    venv_dir.mkdir(parents=True, exist_ok=True)
    (ws / ".microrcs_venv").write_text(str(venv_dir))
    return ws


def test_editable_marker_path_resolves_from_workspace(tmp_path):
    backend = UvVenvBackend(cache_root=tmp_path)
    venv_dir = tmp_path / "venv"
    ws = _workspace_pointing_at(tmp_path, venv_dir, "ws")
    assert backend._editable_marker_path(ws) == venv_dir / _EDITABLE_MARKER


def test_assert_editable_pointer_absent_marker_is_ok(tmp_path):
    # No marker => no repoint happened through this backend; stay silent.
    backend = UvVenvBackend(cache_root=tmp_path)
    venv_dir = tmp_path / "venv"
    ws = _workspace_pointing_at(tmp_path, venv_dir, "ws")
    backend._assert_editable_pointer(ws)  # no raise


def test_assert_editable_pointer_match_is_ok(tmp_path):
    backend = UvVenvBackend(cache_root=tmp_path)
    venv_dir = tmp_path / "venv"
    ws = _workspace_pointing_at(tmp_path, venv_dir, "ws")
    (venv_dir / _EDITABLE_MARKER).write_text(str(ws))
    backend._assert_editable_pointer(ws)  # pointer is ours => no raise


def test_assert_editable_pointer_mismatch_raises(tmp_path):
    backend = UvVenvBackend(cache_root=tmp_path)
    venv_dir = tmp_path / "venv"
    ws = _workspace_pointing_at(tmp_path, venv_dir, "ws")
    (venv_dir / _EDITABLE_MARKER).write_text(str(tmp_path / "other-worker-ws"))
    with pytest.raises(SetupError, match="parallel repoint race"):
        backend._assert_editable_pointer(ws)


def test_repoint_editable_records_pointer(tmp_path, monkeypatch):
    backend = UvVenvBackend(cache_root=tmp_path)
    venv_dir = tmp_path / "venv"
    ws = _workspace_pointing_at(tmp_path, venv_dir, "ws")

    def _fake_run(cmd, *a, **k):
        return subprocess.CompletedProcess(cmd, 0, "installed", "")

    monkeypatch.setattr("adapters.sandbox.uv_venv.subprocess.run", _fake_run)
    backend.repoint_editable(ws)
    assert (venv_dir / _EDITABLE_MARKER).read_text().strip() == str(ws)


def test_run_test_command_trips_guard_before_running(tmp_path):
    # The scoring path must refuse to run when the shared pointer has been
    # re-aimed at another workspace (simulated parallel same-instance repoint).
    backend = UvVenvBackend(cache_root=tmp_path)
    venv_dir = tmp_path / "venv"
    ws = _workspace_pointing_at(tmp_path, venv_dir, "ws")
    (venv_dir / _EDITABLE_MARKER).write_text(str(tmp_path / "other-worker-ws"))
    with pytest.raises(SetupError, match="parallel repoint race"):
        backend.run_test_command(ws, "echo should-not-run", timeout_s=5)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
