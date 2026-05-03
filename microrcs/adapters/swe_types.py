"""Typed boundary dataclasses for the SWE-bench-Lite adapter.

Pattern lifted from Flue's runtime-validated I/O: validate at the seam between
the HF dataset and microRCS, between the agent and the verifier, between the
verifier and the report. Catches dataset drift cheaply.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping

_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_INSTANCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+__[A-Za-z0-9._-]+-[0-9]+$")


class SweInstanceError(ValueError):
    """Raised when an HF row cannot be coerced into a valid SweInstance."""


@dataclass(frozen=True)
class SweInstance:
    """A SWE-bench-Lite test instance, validated at construction.

    Source: HuggingFace dataset `princeton-nlp/SWE-bench_Lite`, split=test.
    Each row describes a real-world bug: target repo + base commit + failing
    tests + ground-truth fix. We never expose `patch` (the ground truth) to
    the agent — it's kept only for analytics and oracle comparisons.
    """

    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    hints_text: str
    test_patch: str
    patch: str
    fail_to_pass: tuple[str, ...]
    pass_to_pass: tuple[str, ...]
    version: str
    environment_setup_commit: str | None = None

    def __post_init__(self) -> None:
        if not _INSTANCE_ID_PATTERN.match(self.instance_id):
            raise SweInstanceError(
                f"instance_id={self.instance_id!r} doesn't match "
                f"<owner>__<repo>-<number> pattern"
            )
        if not _REPO_PATTERN.match(self.repo):
            raise SweInstanceError(
                f"repo={self.repo!r} must be 'owner/name' format"
            )
        if not _SHA_PATTERN.match(self.base_commit):
            raise SweInstanceError(
                f"base_commit={self.base_commit!r} is not a 40-char hex SHA"
            )
        if self.environment_setup_commit is not None and not _SHA_PATTERN.match(
            self.environment_setup_commit
        ):
            raise SweInstanceError(
                f"environment_setup_commit={self.environment_setup_commit!r} "
                f"is not a 40-char hex SHA"
            )
        if not self.problem_statement.strip():
            raise SweInstanceError("problem_statement is empty")
        if not self.test_patch.strip():
            raise SweInstanceError("test_patch is empty (no failing tests defined)")
        if not self.fail_to_pass:
            raise SweInstanceError("fail_to_pass must be non-empty")
        # pass_to_pass MAY be empty; some instances don't track regressions.

    @classmethod
    def from_hf_row(cls, row: Mapping) -> "SweInstance":
        """Coerce a raw HF dataset row into a SweInstance, validating en route.

        HF rows contain `FAIL_TO_PASS` and `PASS_TO_PASS` as JSON strings of
        list[str]; we parse and tuple-ify them here.
        """
        import json

        def _as_str_tuple(value: object) -> tuple[str, ...]:
            if isinstance(value, str):
                if not value.strip():
                    parsed = []
                else:
                    try:
                        parsed = json.loads(value)
                    except json.JSONDecodeError as exc:
                        raise SweInstanceError(
                            f"test list value is not valid JSON: {exc.msg}"
                        ) from exc
            elif isinstance(value, (list, tuple)):
                parsed = list(value)
            elif value is None:
                parsed = []
            else:
                raise SweInstanceError(
                    f"Cannot coerce value of type {type(value).__name__} into list[str]"
                )
            if not all(isinstance(x, str) for x in parsed):
                raise SweInstanceError("test list contains non-string entries")
            return tuple(parsed)

        env_commit = row.get("environment_setup_commit")
        if isinstance(env_commit, str) and not env_commit.strip():
            env_commit = None

        return cls(
            instance_id=str(row["instance_id"]),
            repo=str(row["repo"]),
            base_commit=str(row["base_commit"]),
            problem_statement=str(row["problem_statement"]),
            hints_text=str(row.get("hints_text") or ""),
            test_patch=str(row["test_patch"]),
            patch=str(row.get("patch") or ""),
            fail_to_pass=_as_str_tuple(row.get("FAIL_TO_PASS")),
            pass_to_pass=_as_str_tuple(row.get("PASS_TO_PASS")),
            version=str(row.get("version") or ""),
            environment_setup_commit=env_commit,
        )

    @property
    def repo_slug(self) -> str:
        """`owner--repo` for filesystem paths (no `/`)."""
        return self.repo.replace("/", "--")


@dataclass(frozen=True)
class SweCandidate:
    """Result of running an agent against a SweInstance.

    The agent edits files in its workspace via bash; at the end of an episode
    we extract `git diff HEAD` from the workspace as `patch_text`. The agent's
    `submit` action message is captured in `final_message` for audit, but the
    score depends only on the diff actually applied.
    """

    instance_id: str
    patch_text: str
    final_message: str
    n_steps: int
    cost_usd: float

    def __post_init__(self) -> None:
        if not self.instance_id:
            raise ValueError("instance_id required")
        if self.n_steps < 0:
            raise ValueError(f"n_steps must be >= 0, got {self.n_steps}")
        if self.cost_usd < 0:
            raise ValueError(f"cost_usd must be >= 0, got {self.cost_usd}")


@dataclass(frozen=True)
class SweScore:
    """Output of the verifier for one (instance, candidate) pair."""

    instance_id: str
    score: float
    fail_to_pass_passing: int
    fail_to_pass_total: int
    pass_to_pass_passing: int
    pass_to_pass_total: int
    pytest_duration_s: float
    error: str | None = None
    pytest_stderr_tail: str = ""

    def __post_init__(self) -> None:
        if self.score not in (0.0, 1.0):
            raise ValueError(f"score must be 0.0 or 1.0, got {self.score}")
        if self.fail_to_pass_passing > self.fail_to_pass_total:
            raise ValueError(
                f"fail_to_pass_passing={self.fail_to_pass_passing} > "
                f"total={self.fail_to_pass_total}"
            )
        if self.pass_to_pass_passing > self.pass_to_pass_total:
            raise ValueError(
                f"pass_to_pass_passing={self.pass_to_pass_passing} > "
                f"total={self.pass_to_pass_total}"
            )
        if self.pytest_duration_s < 0:
            raise ValueError("pytest_duration_s must be >= 0")

    @property
    def fully_passed(self) -> bool:
        """True iff all FAIL_TO_PASS now pass and all PASS_TO_PASS still pass."""
        return (
            self.fail_to_pass_total > 0
            and self.fail_to_pass_passing == self.fail_to_pass_total
            and self.pass_to_pass_passing == self.pass_to_pass_total
        )
