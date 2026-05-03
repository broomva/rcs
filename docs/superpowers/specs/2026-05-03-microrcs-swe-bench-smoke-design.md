# microRCS — SWE-bench-Lite Smoke Adapter

**Status:** approved 2026-05-03
**Author:** Carlos Escobar (operator), Claude Opus 4.7 (implementing)
**Linear:** BRO-946 parent (full bench scope); this spec covers the smoke-test slice only
**Predecessor:** `microrcs/THESIS_VALIDATION.md` § Capacity-tier sweep (PR #31)

## Why this exists

The H1 thesis verdict is currently **tier-dependent on HARDER_SUITE** (refuted at Sonnet, directionally supported at Opus). HARDER_SUITE is a single-shot independent reasoning benchmark — it doesn't probe long-horizon multi-step agent regimes where the original RCS thesis is strongest. SWE-bench-Lite is the canonical long-horizon test: real GitHub issues, real codebases, multi-step bash + edit + run-tests trajectories.

Before committing to BRO-946's full bench (~$240, ~1 week, 20 instances × 4 conditions × 3 seeds), we de-risk the pipeline with a smoke test on 2 hand-picked instances at `flat` only on Haiku. Validates: HF dataset loading, repo clone + venv setup, multi-step agent loop in `L0Plant`, FAIL_TO_PASS / PASS_TO_PASS verifier, end-to-end scoring.

## Scope (what's IN)

- New module `microrcs/adapters/swe_bench.py` returning microRCS `Task` objects
- Pluggable `SandboxBackend` protocol with one impl: `UvVenvBackend`
- Three typed boundary dataclasses with `__post_init__` validation
- 2 hand-picked instances curated for venv compatibility (no Docker, no compilation)
- Driver script `scripts/swe_smoke.py` runnable as `make swe-smoke`
- Compact `AGENTS.md` inside `adapters/` directory
- Unit tests for adapter logic (no live API, no network)
- Live smoke run on Haiku × 2 instances × `flat` only (~$1–5)

## Scope (what's OUT — these belong in BRO-946 proper)

- The 20-instance × 4-condition × 3-seed bench
- `+autonomic` / `+meta` / `full` conditions on SWE-bench
- Sonnet / Opus tier sweeps on SWE-bench
- A `--suite swe-lite` flag on `microrcs.py` mainline
- Additional sandbox backends (`SandboxExecBackend`, `LimaBackend`, `DaytonaBackend`)
- HF dataset auto-update / mirror handling

## Architectural decisions (locked)

1. **Minimal edits to `microrcs.py`.** Adapter consumes the existing public surface (`Task`, `Caps`, `Workspace`, `L0Plant`, `EpisodeTrace`, `Reasoner`). The smoke surfaced one mainline bug (empty `tool_result` content with `is_error=true` rejected by Anthropic API) which is fixed in this PR — the only mainline change. Future BRO-946 work may need a `--suite swe-lite` flag; out of scope for the smoke.
2. **Bash-only L0** (mini-swe-agent style). Agent uses `cat`, `sed`, `pytest`, `git diff` via existing `BashAction` + `submit`. No new tools, no `read_file`/`edit_file` surface. Bitter-lesson aligned.
3. **Three-layer sandbox cache:** immutable RO repo clone + immutable RO venv + COW per-episode workspace via APFS `clonefile()`. Pattern lifted from Flue's MountableFs.
4. **Pluggable `SandboxBackend` protocol.** One implementation now (`UvVenvBackend`); future Docker / sandbox-exec / Lima / Daytona slots in unchanged.
5. **Runtime schema validation at boundaries.** `SweInstance.__post_init__` validates the HF row shape (lifted from Flue's Valibot pattern). Catches dataset drift cheaply.
6. **Verifier scoring mirrors official SWE-bench:** `score = 1.0` iff every test in `FAIL_TO_PASS` now passes AND every test in `PASS_TO_PASS` still passes. `0.0` otherwise. No partial credit.
7. **Per-instance budget:** `Caps(max_steps=50, max_cost_usd=5.0, per_command_timeout_seconds=120)` per BRO-946 caps adjustment.
8. **Smoke uses Haiku + `flat` only.** Recursion conditions belong in BRO-946 proper. The smoke is engineering de-risk, not science.

## File layout

```text
research/rcs/microrcs/
├── microrcs.py                          # unchanged
├── adapters/
│   ├── __init__.py                      # NEW (empty)
│   ├── AGENTS.md                        # NEW — ~40 lines, harness doc
│   ├── swe_types.py                     # NEW — ~80 LOC, dataclasses
│   ├── swe_bench.py                     # NEW — ~220 LOC, Tasks + verifier
│   └── sandbox/
│       ├── __init__.py                  # NEW (re-exports)
│       ├── backend.py                   # NEW — ~40 LOC, Protocol
│       └── uv_venv.py                   # NEW — ~110 LOC, only impl
├── scripts/
│   └── swe_smoke.py                     # NEW — ~80 LOC driver
└── tests/
    └── test_swe_bench_adapter.py        # NEW — ~150 LOC unit tests

# Outside the repo (host-local cache, not committed)
~/.cache/microrcs-swe/
├── repos/<owner>--<repo>--<base_sha>/   # immutable RO clone
├── venvs/<repo>--<base_sha>/            # immutable RO venv (built once via uv)
└── workspaces/<run_id>/<inst>/          # COW per-episode (APFS clonefile)
```

**Total new code: ~720 LOC** (~470 source + ~150 test + ~40 docs + ~60 scaffolding).

## Component contracts

### `swe_types.py`

```python
@dataclass(frozen=True)
class SweInstance:
    """Validated HF SWE-bench-Lite row. Validated at construction."""
    instance_id: str            # e.g. "django__django-11099"
    repo: str                   # "owner/repo"
    base_commit: str            # 40-char SHA
    problem_statement: str      # the issue text
    hints_text: str             # may be ""
    test_patch: str             # diff that introduces the failing tests
    patch: str                  # ground-truth fix (used for analytics, never shown to agent)
    fail_to_pass: tuple[str, ...]  # tests that must pass after agent's fix
    pass_to_pass: tuple[str, ...]  # tests that must remain passing
    version: str
    environment_setup_commit: str | None  # may be None for some instances

    def __post_init__(self) -> None:
        # Validate base_commit is 40-char SHA, repo has "owner/name" shape,
        # fail_to_pass non-empty, etc. Raise ValueError on bad data.
        ...

@dataclass(frozen=True)
class SweCandidate:
    """Agent's submitted fix."""
    instance_id: str
    patch_text: str             # unified diff
    final_message: str          # agent's last submit message
    n_steps: int
    cost_usd: float

@dataclass(frozen=True)
class SweScore:
    """Verifier output."""
    instance_id: str
    score: float                # 1.0 or 0.0
    fail_to_pass_passing: int
    fail_to_pass_total: int
    pass_to_pass_passing: int
    pass_to_pass_total: int
    pytest_duration_s: float
    error: str | None           # populated if patch didn't apply, pytest crashed, etc.
```

### `sandbox/backend.py`

```python
class SandboxBackend(Protocol):
    def setup(self, instance: SweInstance, run_id: str) -> Path:
        """Provision a workspace for this instance under run_id.
        Returns the absolute path to the writable workspace."""

    def teardown(self, workspace_path: Path) -> None:
        """Clean up the workspace. Cache layers are NOT torn down."""

    def run_in_workspace(
        self, workspace_path: Path, cmd: list[str], timeout_s: float
    ) -> subprocess.CompletedProcess:
        """Run a subprocess inside the workspace's venv. Used by verifier."""
```

### `sandbox/uv_venv.py` — `UvVenvBackend`

- `setup`: ensure canonical clone at `repos/<owner>--<repo>--<base_sha>/` exists; ensure venv at `venvs/<repo>--<base_sha>/` exists (build via `uv venv` + `uv pip install -e .` if missing); APFS-clone canonical clone into `workspaces/<run_id>/<inst>/`; apply `instance.test_patch` so failing tests are present; return workspace path.
- `teardown`: `rm -rf workspaces/<run_id>/<inst>/` (cache layers preserved).
- `run_in_workspace`: `subprocess.run` with `cwd=workspace_path`, `env={"VIRTUAL_ENV": venv_path, "PATH": venv_bin + os.environ["PATH"]}`, capture stdout/stderr, enforce timeout.

### `swe_bench.py`

- `load_swe_bench_lite_subset(instance_ids: list[str], backend: SandboxBackend) -> list[Task]`
   Loads HF dataset, filters to requested IDs, returns one `microrcs.Task` per instance.
- `_build_swe_prompt(inst: SweInstance) -> str`: front-loaded prompt — repo path, problem statement, **failing test names** (parsed from `test_patch`), hint text. The agent doesn't have to grep for the test name.
- `_make_swe_verifier(inst: SweInstance, backend: SandboxBackend) -> Callable`: closure that takes `(answer: str, workspace: m.Workspace)` and returns `float`. Steps:
  1. Determine candidate patch: if `answer` is a unified diff, use it; otherwise run `git -C <ws> diff` to extract the agent's edits.
  2. Apply candidate patch on a *fresh* sibling workspace (so we don't pollute the agent's mid-run state).
  3. Run `pytest -x <fail_to_pass tests>` then `pytest -x <pass_to_pass sample>`.
  4. Return 1.0 iff both pass; 0.0 otherwise. Wrap in try/except and return 0.0 with logged error on any failure.
- `curated_pilot_instances() -> list[str]`: returns 2 hardcoded instance IDs proven to install + test cleanly in venv-no-Docker.

### `scripts/swe_smoke.py`

```python
# pseudo
def main() -> int:
    backend = UvVenvBackend(cache_root=Path("~/.cache/microrcs-swe").expanduser())
    tasks = load_swe_bench_lite_subset(curated_pilot_instances(), backend)
    cfg = RunConfig(
        suite=tasks, n_epochs=1, n_repeats=1, n_runs=1,
        max_steps_per_episode=50,
        max_cost_usd_per_episode=5.0,
        model_l0_l1="claude-haiku-4-5",
    )
    out = Path("reports/swe-smoke")
    result = m.run(cfg, out, conditions=("flat",))
    _print_smoke_summary(result.metrics, tasks)
    return 0
```

## Data flow

```text
[HF Hub: SWE-bench_Lite] ──load──> SweInstance(s) ──validate──>
[curated_pilot_instances] ──filter──> 2 instances
   │
   └─> for each instance:
        ├─ SandboxBackend.setup(instance, run_id) → workspace_path
        │   └─ ensure repos/<sha>/ + venvs/<sha>/, clonefile→workspace, apply test_patch
        ├─ Task(verify=make_swe_verifier(instance, backend))
        ├─ L0Plant.run_episode(task) → 0..50 bash actions + final submit
        ├─ Verifier reads agent's diff, applies to sibling, pytests
        └─ SweScore(instance_id, score=1.0 or 0.0, ...)
   │
   └──> aggregate: pass^1, total cost, total steps
```

## Error handling

| Failure mode | Behavior |
|---|---|
| HF dataset unreachable | smoke aborts with clear error; document network requirement in AGENTS.md |
| `instance_id` not in dataset | `load_swe_bench_lite_subset` raises with available IDs printed |
| Schema mismatch in HF row | `SweInstance.__post_init__` raises `ValueError` with offending field |
| `git clone` fails | backend's `setup` returns informative error; smoke records score=0.0 with error string |
| `uv venv` / `uv pip install` fails | same — score=0.0 with error |
| APFS `clonefile()` unavailable (non-Mac) | fallback to `cp -r`; tested via env var override |
| Agent runs out of `max_steps` | episode ends; verifier reads whatever's in workspace; usually 0.0 |
| Agent's patch doesn't apply | verifier returns 0.0 with `error="patch did not apply"` |
| Pytest hangs | per-test timeout (120s) trips, verifier returns 0.0 |
| Pytest crashes (collection error) | verifier returns 0.0 with stderr captured |

**Observability:** every failure mode emits a structured event with `instance_id`, `base_sha`, `run_id`, `phase` (setup/agent/verify), `error_class`. Goes through microRCS's existing `EventLog`.

## Testing strategy

### Unit tests (CI-runnable, no network)

- `test_swe_instance_validates_base_commit_sha` — bad SHA raises ValueError
- `test_swe_instance_validates_repo_format` — missing `/` raises
- `test_swe_instance_accepts_canonical_fixture` — full HF row dict round-trips
- `test_build_swe_prompt_includes_failing_test_names` — front-loaded context check
- `test_make_swe_verifier_handles_unappliable_patch` — score=0.0 + error string
- `test_make_swe_verifier_handles_missing_workspace` — graceful failure
- `test_uv_venv_backend_paths` — pure path-derivation logic, no FS calls
- `test_curated_pilot_instances_are_real_ids` — checks against a frozen fixture (not live HF)
- `test_score_aggregation` — given 2 mock SweScore, computes pass^1 correctly
- `test_load_subset_filters_correctly` — uses a tiny mocked dataset

### Manual / live (out of CI)

- `make swe-smoke` runs end-to-end against 2 real instances, captures output to `reports/swe-smoke/run.log`, expected cost ~$1–5

### What we explicitly do NOT test in CI

- No real HF download
- No real git clone
- No real uv invocation
- No live API calls

## Curated instances for smoke

Two instances must satisfy ALL of:
- Pure Python (no C extensions, no system libs, no compilation)
- `pip install -e .` works without flags or system deps
- Test suite total runtime < 60s
- FAIL_TO_PASS = 1–3 tests
- Repo clone < 200MB

**Initial picks** (subject to live-verification in implementation phase):
1. **`pydicom__pydicom-XXXX`** — pure-Python DICOM library, fast tests, well-isolated
2. **`pylint-dev__astroid-XXXX`** — pure-Python AST library, decoupled tests

The actual instance IDs will be locked in during implementation by inspecting the HF dataset and confirming `pip install -e . && pytest` works on each candidate. Locked IDs go into `curated_pilot_instances()`.

## Cost / timing budget

- HF download: one-time ~50 MB (cached after first run)
- Per-instance setup: ~3-5 min first time (clone + uv pip install), <5s subsequent
- Per-instance agent run: 30–120s wall, ~$0.10–$0.50 on Haiku at max_steps=50
- Per-instance verify: 5–30s
- **Total smoke (2 instances cold): ~10–15 min wall, $0.50–$2 API**
- **Total smoke (2 instances warm): ~3–5 min wall, $0.50–$2 API**

## Implementation order (sequential — parallelism not valuable here)

1. `swe_types.py` + tests
2. `sandbox/backend.py` + tests
3. `sandbox/uv_venv.py` + tests (with mocked subprocess where pure-logic; one integration test that actually makes a tiny venv)
4. `swe_bench.py` (skeleton: prompt, verifier, loader) + tests with mock data
5. `curated_pilot_instances()` — pick 2 candidates by live HF inspection
6. `scripts/swe_smoke.py` driver + Makefile target
7. `adapters/AGENTS.md`
8. Live smoke run, capture results
9. Append findings to `THESIS_VALIDATION.md`
10. Branch + PR + CI green + merge

## Definition of done

- [ ] All unit tests pass locally and in CI
- [ ] `make swe-smoke` runs end-to-end on this Mac without intervention
- [ ] Both curated instances scored (whether 0.0 or 1.0 — what matters is the pipeline produced a verdict)
- [ ] `THESIS_VALIDATION.md` has a `## SWE-bench-Lite smoke result` subsection with: instance IDs, scores, costs, wall time, observed agent step counts
- [ ] PR merged on `broomva/rcs:main`
- [ ] BRO-946 has a comment with smoke results and a recommendation: ready for full bench, or blocked on X

## Out of band

- The full BRO-946 bench (20 instances × 4 conditions × 3 seeds) is intentionally out of scope. After the smoke succeeds, the next ticket scopes the full run with the now-validated cost-per-instance from the smoke as input.
- If the smoke reveals that the L0Plant abstraction can't sustain 50-step trajectories cleanly (e.g., context overflow, retry-loop pathology), this becomes a microrcs.py mainline change ticket, NOT a smoke iteration.
