# Adapters — agent-facing harness doc

You are reading this because you're going to run the SWE-bench-Lite adapter,
extend it, or curate new instances. Compact + actionable per Practice 2 of
the Harness Engineering playbook.

## What lives here

| Path | Purpose |
|---|---|
| `swe_types.py` | `SweInstance` / `SweCandidate` / `SweScore` boundary dataclasses with `__post_init__` validation. |
| `swe_bench.py` | HF dataset loader, prompt builder, verifier closure, `curated_pilot_instances()`. |
| `sandbox/backend.py` | `SandboxBackend` Protocol (Flue-pattern pluggable backend). |
| `sandbox/uv_venv.py` | `UvVenvBackend` — only impl shipped. Caches repo clones + venvs; uses APFS `clonefile()` for per-episode copies on Mac. |
| `../scripts/swe_smoke.py` | Smoke driver. Invoke via `make swe-smoke`. |

## How to run the smoke

```bash
# Dry-run first — provisions cache, no LLM call (~5 min cold, free):
make swe-smoke-dry

# Real run — Haiku × flat × 2 curated instances (~$1–5):
ANTHROPIC_API_KEY=... make swe-smoke

# Full reset:
make swe-clean
```

Outputs land in `reports/swe-smoke/`:
- `<run_id>-events.jsonl` — microRCS event log (one line per agent event)
- `<run_id>-summary.json` — per-instance scores + total cost + wall time
- `~/.cache/microrcs-swe/workspaces/<run_id>/<instance_id>/swe_scores.jsonl` —
   verifier breakdown per instance (FAIL_TO_PASS / PASS_TO_PASS counts)

## Sandbox model

Three-layer cache under `~/.cache/microrcs-swe/`:
- `repos/<owner>--<repo>--<sha>/` — immutable RO clone, shared across runs
- `venvs/<repo>--<sha>/` — immutable RO Python env, built once via `uv venv`
- `workspaces/<run_id>/<instance_id>/` — writable per-episode (APFS `clonefile`
  if Mac, else `cp -r`)

The verifier creates a sibling workspace under suffix `--verify` so the
agent's mid-run state isn't disturbed. Both workspaces start with the
instance's `test_patch` applied (failing tests present).

**Isolation level:** process-level only. The agent's bash actions inherit
the host filesystem. The threat model is "agent gets confused" not
"adversarial agent." For a real isolation layer (e.g. for the BRO-946 full
bench against untrusted patches), add a new `SandboxBackend` impl —
candidates: `sandbox-exec` (macOS-native), Lima VM, Daytona.

## Instance curation

`curated_pilot_instances()` returns 2 hard-coded SWE-bench-Lite IDs proven
to install + test cleanly in venv-without-Docker. To re-curate:

1. Browse https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite
2. Pick instances satisfying:
   - Pure Python (no C extensions, no system libs)
   - `pip install -e .` works without flags or system deps
   - Test suite total runtime < 60s
   - FAIL_TO_PASS = 1–3 tests
   - Repo clone < 200 MB
3. Verify by running `make swe-smoke-dry` against the candidate
4. Replace the IDs in `curated_pilot_instances()`

## Adding a new sandbox backend

1. Create `sandbox/<name>.py` implementing the `SandboxBackend` Protocol from
   `sandbox/backend.py` (3 methods: `setup`, `teardown`, `run_in_workspace`)
2. Re-export it from `sandbox/__init__.py`
3. Ensure your `setup()` writes a `.microrcs_venv` marker so
   `run_in_workspace` can locate the venv from a workspace path
4. Add an integration test in `microrcs/tests/test_swe_bench_adapter.py`

## Adding a new conditions sweep

Out of scope for the smoke (which is `flat`-only). For the BRO-946 full
bench, the driver script will iterate over `("flat", "+autonomic", "+meta",
"full")` × seeds and dispatch to `m.L0Plant` / L1 / L2 / L3 wrappers — same
pattern as `microrcs.cli_bench` but with SWE tasks. That driver belongs in
its own module, not `swe_smoke.py`.

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `SetupError: failed to apply test_patch` | dataset row's `test_patch` doesn't apply on top of `base_commit` | curate a different instance, or check HF row freshness |
| `pytest: command not found` after setup | `uv venv` succeeded but `pytest` extra wasn't picked up | check `_ensure_venv` extras list; some repos use `[testing]` not `[test]` |
| All tests fail with `ImportError` | repo's Python version != venv default | pass `--python` to `uv venv` (TODO: extend backend) |
| `cp -c -R` fails | non-APFS volume (Linux, USB drive, network FS) | set `prefer_clonefile=False` on the backend |
| Network timeout cloning | GitHub rate limit | use a GH token via `git config --global url.https://...` |

## See also

- Spec: `docs/superpowers/specs/2026-05-03-microrcs-swe-bench-smoke-design.md`
- Linear: BRO-946 (full bench parent ticket)
- Validation log: `microrcs/THESIS_VALIDATION.md` (smoke result lands here once Phase 8 completes)
