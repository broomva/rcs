"""swe_specs — thin adapter over the canonical `swebench` package specs.

BRO-1948. Gives the venv sandbox *environment fidelity*: per-instance pinned
dependencies, the correct per-repo test command + directives, and repo-specific
log parsing — instead of the floating `pip install -e .[test]` that silently
rots (Werkzeug 3.x removing `url_quote` broke flask-4992) and the
pytest-node-ID assumption that can't run sympy's bare-name tests (`bin/test`).

The `swebench` import is guarded so unit tests (which mock this module or use
fixtures) and CI don't require swebench installed. Live curation / verification
DO require it — `require()` raises a clear error if it's missing.

Verified live (oracle check, BRO-1948): with these specs the venv recipe
correctly exercises SOURCE edits — the gold patch flips FAIL_TO_PASS from
FAILED/ERROR at base to PASSED, for both flask (src-layout, requirements.txt +
pinned Werkzeug==2.3.7) and sympy (flat-layout, `bin/test`, bare-name IDs).
"""
from __future__ import annotations

import json

try:  # pragma: no cover - import guard
    from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
    from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
    from swebench.harness.test_spec.python import (
        get_requirements as _sb_get_requirements,
        get_test_directives as _sb_get_test_directives,
    )

    HAS_SWEBENCH = True
except Exception:  # pragma: no cover - exercised only when swebench absent
    MAP_REPO_VERSION_TO_SPECS = {}
    MAP_REPO_TO_PARSER = {}
    HAS_SWEBENCH = False

    def _sb_get_requirements(*_a, **_k):
        raise RuntimeError("swebench not installed")

    def _sb_get_test_directives(*_a, **_k):
        raise RuntimeError("swebench not installed")


class SwebenchUnavailable(RuntimeError):
    """swebench is not installed but a spec-dependent call was made."""


def require() -> None:
    if not HAS_SWEBENCH:
        raise SwebenchUnavailable(
            "swebench is required for SWE-bench environment fidelity — "
            "`pip install swebench` (BRO-1948)."
        )


def spec_for(instance) -> dict | None:
    """Return the canonical install/test spec for an instance, or None."""
    return MAP_REPO_VERSION_TO_SPECS.get(instance.repo, {}).get(instance.version)


def venv_support(instance) -> tuple[bool, str]:
    """Is this instance supported by the uv-venv backend (no Docker/conda)?

    Excludes conda-`environment.yml` instances (need conda, e.g. matplotlib,
    scikit-learn, xarray) and tox-driven test commands (deferred: sphinx).
    """
    if not HAS_SWEBENCH:
        return False, "swebench not installed"
    spec = spec_for(instance)
    if not spec:
        return False, f"no swebench spec for {instance.repo}@{instance.version}"
    if spec.get("packages") == "environment.yml":
        return False, "conda environment.yml instance (needs conda, not venv)"
    test_cmd = spec.get("test_cmd", "")
    if "tox" in test_cmd:
        return False, "tox-based test_cmd (deferred — needs tox + pre_install seds)"
    if not test_cmd:
        return False, "spec has no test_cmd"
    return True, "supported"


def _instance_dict(instance) -> dict:
    """swebench's helpers expect a dict-like SWEbenchInstance."""
    return {
        "repo": instance.repo,
        "version": instance.version,
        "instance_id": instance.instance_id,
        "base_commit": instance.base_commit,
        "environment_setup_commit": (
            instance.environment_setup_commit or instance.base_commit
        ),
        "test_patch": instance.test_patch,
        "patch": instance.patch,
        "FAIL_TO_PASS": json.dumps(list(instance.fail_to_pass)),
        "PASS_TO_PASS": json.dumps(list(instance.pass_to_pass)),
    }


def test_directives(instance) -> list[str]:
    """Test files (from test_patch) the test command runs against."""
    require()
    return list(_sb_get_test_directives(_instance_dict(instance)))


def test_command(instance) -> str:
    """The canonical per-repo test command PREFIX (e.g. `pytest -rA`,
    `... bin/test -C --verbose`). Directives are appended by the caller."""
    require()
    spec = spec_for(instance)
    if not spec or "test_cmd" not in spec:
        raise SwebenchUnavailable(f"no test_cmd for {instance.repo}@{instance.version}")
    return spec["test_cmd"]


def requirements_text(instance) -> str:
    """The pinned requirements.txt for a `packages == 'requirements.txt'` repo
    (fetched from the repo at the environment-setup commit, then cleaned)."""
    require()
    return _sb_get_requirements(_instance_dict(instance))


def parse_test_log(instance, log: str) -> dict[str, str]:
    """Parse a raw test-run log into {test_name: STATUS} via the repo's
    canonical swebench log parser. STATUS is a plain string ("PASSED",
    "FAILED", "ERROR", "SKIPPED"). Returns {} if no parser for the repo."""
    fn = MAP_REPO_TO_PARSER.get(instance.repo)
    if fn is None:
        return {}
    try:
        result = fn(log, None)  # newer swebench signature: (log, test_spec)
    except TypeError:  # pragma: no cover - older signature
        result = fn(log)
    # Normalize TestStatus enum -> its string value where applicable.
    return {k: (getattr(v, "value", None) or str(v)) for k, v in result.items()}
