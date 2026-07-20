"""Unit tests for the swebench spec adapter (BRO-1948).

Two layers:
- Pure/monkeypatched tests (always run): venv_support branch logic, log-parse
  normalization, instance-dict shape.
- Real-swebench integration (skipif not installed): directives from a test
  patch, real spec support — network-free (uses the bundled spec tables +
  regex directive extraction).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402

from adapters import swe_specs  # noqa: E402


def _stub(**over):
    base = dict(
        repo="pallets/flask", version="2.3", instance_id="pallets__flask-4992",
        base_commit="0" * 40, environment_setup_commit=None,
        test_patch="diff --git a/tests/test_x.py b/tests/test_x.py\n",
        patch="", fail_to_pass=("t1",), pass_to_pass=("t2", "t3"),
    )
    base.update(over)
    return SimpleNamespace(**base)


# ---- pure / monkeypatched -------------------------------------------------
def test_instance_dict_shape():
    d = swe_specs._instance_dict(_stub())
    assert d["repo"] == "pallets/flask"
    assert d["FAIL_TO_PASS"] == json.dumps(["t1"])
    assert d["PASS_TO_PASS"] == json.dumps(["t2", "t3"])
    # environment_setup_commit falls back to base_commit when None
    assert d["environment_setup_commit"] == "0" * 40


def test_parse_test_log_normalizes_enum(monkeypatch):
    class _Status:
        def __init__(self, v):
            self.value = v

    monkeypatch.setattr(
        swe_specs, "MAP_REPO_TO_PARSER",
        {"x/y": lambda log, ts=None: {"a": _Status("PASSED"), "b": _Status("FAILED")}},
    )
    out = swe_specs.parse_test_log(_stub(repo="x/y"), "irrelevant")
    assert out == {"a": "PASSED", "b": "FAILED"}


def test_parse_test_log_plain_string(monkeypatch):
    monkeypatch.setattr(
        swe_specs, "MAP_REPO_TO_PARSER", {"x/y": lambda log, ts=None: {"a": "ERROR"}}
    )
    assert swe_specs.parse_test_log(_stub(repo="x/y"), "log") == {"a": "ERROR"}


def test_parse_test_log_unknown_repo(monkeypatch):
    monkeypatch.setattr(swe_specs, "MAP_REPO_TO_PARSER", {})
    assert swe_specs.parse_test_log(_stub(repo="no/parser"), "log") == {}


def test_venv_support_env_yml_excluded(monkeypatch):
    monkeypatch.setattr(swe_specs, "HAS_SWEBENCH", True)
    monkeypatch.setattr(
        swe_specs, "MAP_REPO_VERSION_TO_SPECS",
        {"m/m": {"1": {"packages": "environment.yml", "test_cmd": "pytest"}}},
    )
    ok, why = swe_specs.venv_support(_stub(repo="m/m", version="1"))
    assert ok is False and "conda" in why


def test_venv_support_bare_tox_excluded(monkeypatch):
    # Bare `tox` (no --current-env) still needs tox-managed isolated envs.
    monkeypatch.setattr(swe_specs, "HAS_SWEBENCH", True)
    monkeypatch.setattr(
        swe_specs, "MAP_REPO_VERSION_TO_SPECS",
        {"s/s": {"1": {"test_cmd": "tox -epy39 -v"}}},
    )
    monkeypatch.setattr(swe_specs, "MAP_REPO_TO_PARSER", {"s/s": lambda log, ts=None: {}})
    ok, why = swe_specs.venv_support(_stub(repo="s/s", version="1"))
    assert ok is False and "bare tox" in why


def test_venv_support_tox_current_env_supported(monkeypatch):
    # `tox --current-env` runs in THIS venv (tox-current-env plugin) — the
    # sphinx form. Supported now (BRO-1949).
    monkeypatch.setattr(swe_specs, "HAS_SWEBENCH", True)
    monkeypatch.setattr(
        swe_specs, "MAP_REPO_VERSION_TO_SPECS",
        {"s/s": {"1": {
            "test_cmd": "tox --current-env -epy39 -v --",
            "pip_packages": ["tox==4.16.0", "tox-current-env==0.0.11"],
        }}},
    )
    monkeypatch.setattr(swe_specs, "MAP_REPO_TO_PARSER", {"s/s": lambda log, ts=None: {}})
    ok, why = swe_specs.venv_support(_stub(repo="s/s", version="1"))
    assert ok is True and why == "supported"


def test_venv_support_no_spec(monkeypatch):
    monkeypatch.setattr(swe_specs, "HAS_SWEBENCH", True)
    monkeypatch.setattr(swe_specs, "MAP_REPO_VERSION_TO_SPECS", {})
    ok, why = swe_specs.venv_support(_stub(repo="ghost/repo", version="9"))
    assert ok is False and "no swebench spec" in why


def test_venv_support_list_test_cmd_excluded(monkeypatch):
    # swebench 4.x non-Lite specs (e.g. redis) carry a list test_cmd.
    monkeypatch.setattr(swe_specs, "HAS_SWEBENCH", True)
    monkeypatch.setattr(
        swe_specs, "MAP_REPO_VERSION_TO_SPECS",
        {"r/r": {"1": {"test_cmd": ["make test", "cat out"]}}},
    )
    ok, why = swe_specs.venv_support(_stub(repo="r/r", version="1"))
    assert ok is False and "string test_cmd" in why


def test_venv_support_no_parser_excluded(monkeypatch):
    # spec + string test_cmd but no log parser => would score 0 every episode.
    monkeypatch.setattr(swe_specs, "HAS_SWEBENCH", True)
    monkeypatch.setattr(
        swe_specs, "MAP_REPO_VERSION_TO_SPECS",
        {"a/b": {"1": {"packages": "pytest", "test_cmd": "pytest -rA"}}},
    )
    monkeypatch.setattr(swe_specs, "MAP_REPO_TO_PARSER", {})
    ok, why = swe_specs.venv_support(_stub(repo="a/b", version="1"))
    assert ok is False and "log parser" in why


def test_venv_support_ok(monkeypatch):
    monkeypatch.setattr(swe_specs, "HAS_SWEBENCH", True)
    monkeypatch.setattr(
        swe_specs, "MAP_REPO_VERSION_TO_SPECS",
        {"a/b": {"1": {"packages": "pytest", "test_cmd": "pytest -rA"}}},
    )
    monkeypatch.setattr(swe_specs, "MAP_REPO_TO_PARSER", {"a/b": lambda log, ts=None: {}})
    ok, why = swe_specs.venv_support(_stub(repo="a/b", version="1"))
    assert ok is True and why == "supported"


# ---- real swebench integration (network-free) -----------------------------
@pytest.mark.skipif(not swe_specs.HAS_SWEBENCH, reason="swebench not installed")
def test_real_flask_supported():
    ok, _ = swe_specs.venv_support(_stub(repo="pallets/flask", version="2.3"))
    assert ok is True
    assert swe_specs.test_command(_stub(repo="pallets/flask", version="2.3")) == "pytest -rA"


@pytest.mark.skipif(not swe_specs.HAS_SWEBENCH, reason="swebench not installed")
def test_real_sphinx_tox_current_env_supported():
    # BRO-1949: sphinx uses `tox --current-env` with tox + tox-current-env
    # pinned in the spec's pip_packages, so the venv backend supports it.
    ok, why = swe_specs.venv_support(_stub(repo="sphinx-doc/sphinx", version="3.5"))
    assert ok is True, why
    assert "--current-env" in swe_specs.test_command(
        _stub(repo="sphinx-doc/sphinx", version="3.5")
    )


@pytest.mark.skipif(not swe_specs.HAS_SWEBENCH, reason="swebench not installed")
def test_real_directives_from_test_patch():
    tp = (
        "diff --git a/tests/test_config.py b/tests/test_config.py\n"
        "--- a/tests/test_config.py\n+++ b/tests/test_config.py\n"
    )
    directives = swe_specs.test_directives(_stub(repo="pallets/flask", test_patch=tp))
    assert "tests/test_config.py" in directives


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
