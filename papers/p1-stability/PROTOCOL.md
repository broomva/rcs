---
title: "Paper 1 — Experimental Protocol"
tags:
  - rcs
  - paper
  - protocol
  - experimental-design
aliases:
  - P1-PROTOCOL
created: "2026-04-23"
updated: "2026-04-23"
status: draft
related:
  - "[[p1-stability/README]]"
  - "[[p0-foundations]]"
---

# Paper 1 — Experimental Protocol

Specification of the data-capture procedure that produces the dataset under
[`data/p1-runs/`](../../data/p1-runs/) analysed by Paper 1. Everything here
is the contract between Paper 1's *methodology* section and the Life Agent
OS runtime; the paper's numbers must be reproducible by re-running exactly
this protocol.

> **Status:** draft (scaffold). Fields marked **TBC-P1d** are placeholders
> to be finalised by the P1d data-capture task; the canonical names are
> recorded here first so that the paper's methodology section, the harness,
> and the analysis notebooks agree from day 1.

---

## 1. System under test

- **Runtime:** Life Agent OS (mirror of `parameters.toml` at
  `~/broomva/core/life/crates/autonomic/autonomic-core/data/rcs-parameters.toml`).
- **Required daemons:** `arcand`, `autonomicd`, `lagod`, `vigil` exporter.
- **Rust toolchain:** pinned by the life repo's `rust-toolchain.toml` (≥ 1.95
  at time of writing; see `CLAUDE.md` in the life repo for the current pin).
- **Architecture:** single host, x86_64 or aarch64. Container host MUST have
  at least 2 logical cores available to the `autonomicd` tick loop.
- **Branch:** life `main`; commit SHA MUST be recorded with every run (see
  §5 below).

### 1.1 Daemon configuration

The following knobs are fixed for Paper 1 runs and MUST be recorded in
`config.toml` for each run (see §5):

| Daemon        | Knob                      | Default for P1 runs | Rationale                                                        |
| ------------- | ------------------------- | ------------------- | ---------------------------------------------------------------- |
| `arcand`      | tick interval             | 100 ms              | `decay_0 = 2.0` units/s in `parameters.toml` assumes ~10 Hz L0.  |
| `autonomicd`  | tick interval             | 500 ms              | L1 homeostasis check; matches `tau_a = 0.5` default.             |
| `autonomicd`  | hysteresis profile        | `default`           | Anti-flapping; see `life-autonomic` skill.                       |
| `autonomicd`  | economic mode             | `Sovereign`         | Baseline; mode sweeps are a separate run matrix row.             |
| `lagod`       | journal flush             | every event         | Never lose events during capture (sync fsync).                   |
| `vigil`       | OTLP endpoint             | local collector     | Metrics scraped by `otel-collector` → NDJSON (see §3).           |

Any deviation from these defaults is a separate run-matrix row and MUST be
reflected in `config.toml` (§5).

### 1.2 Canonical parameters

Paper 1 runs use the canonical parameters from
[`data/parameters.toml`](../../data/parameters.toml) unmodified. The
runtime's `StabilityBudget` consumes the mirror at the path in §1; the
Rust test `rcs_canonical_parameters_reproduce_paper_lambdas` (landed in
life#802) guarantees the mirror matches the paper's `[derived.lambda]`
cache to <1e-3. Any drift is a pre-capture blocker — re-run
`bash ~/broomva/core/life/scripts/sync-rcs-parameters.sh` before starting
a run.

---

## 2. Capture windows and sampling

| Quantity                               | Value                       |
| -------------------------------------- | --------------------------- |
| Nominal capture-window length          | **30 min per run**          |
| Warm-up discarded at window start      | **60 s**                    |
| Run matrix entries per configuration   | **3** (seeded 0, 1, 2)      |
| $\hat{\lambda}_i$ sampling rate        | **per `autonomicd` tick**   |
|   → effective at default tick          | ≈ 2 Hz (500 ms)             |
| L0 state samples (`HomeostaticState`)  | per `arcand` tick (≈ 10 Hz) |
| L2/L3 margin samples                   | **TBC-P1d** (L2/L3 estimators not yet landed — see `CLAUDE.md` §Forthcoming) |

The 30-minute window is long enough to observe multiple economic-mode
transitions and several adaptation events (`L_\theta \rho` activations) at
the default autonomic tick rate, and short enough to bound disk use at
~50 MB NDJSON per run at expected event rates.

Runs MUST be at least 3× seeded repeats to let the analysis separate
intrinsic $\hat{\lambda}_i$ variance from the seed-dependent jitter of the
controller's LLM calls. Seeds live in `config.toml`.

---

## 3. OpenTelemetry metric names

The `vigil` crate emits the metrics below; they are the ground truth for
every number in Paper 1. Names are stable and versioned with the life
repo. If a name in this table does not resolve against
`crates/vigil/life-vigil/src/metrics.rs` at capture time, **the capture is
invalid** — stop, reconcile the name, and restart.

### 3.1 Per-level margins and composite rate

| Metric name (OTel)                          | Kind       | Labels                        | Meaning                                                                 |
| ------------------------------------------- | ---------- | ----------------------------- | ----------------------------------------------------------------------- |
| `rcs.lambda_hat`                            | Gauge      | `level ∈ {L0,L1,L2,L3}`       | Per-level stability margin $\hat{\lambda}_i$ as reported by `MarginEstimator` (may be EMA-smoothed; smoothing window is a `MarginEstimator` config recorded in `config.toml`). |
| `rcs.lambda_hat.budget`                     | Gauge      | `level`                       | Instantaneous algebraic decomposition $\hat{\gamma}_i - \hat{L_\theta\rho}_i - \hat{L_d\eta}_i - \hat{\beta\bar\tau}_i - \hat{\ln\nu / \tau_a}_i$, recomputed per tick from the five component gauges below. Equals `rcs.lambda_hat` exactly when the estimator's smoothing window has elapsed; during warm-up or a rapid perturbation the two may diverge by up to the smoothing response. **Invariant the P1d harness MUST assert on each run:** after the §2 warm-up, `|rcs.lambda_hat − rcs.lambda_hat.budget| ≤ ε` for all samples, with `ε = 5e-3` by default (≥ one display digit of precision in the paper's tables; override in `config.toml` if the run intentionally uses a longer smoothing window). Violations of this invariant fail the capture and are logged to `events.ndjson` as `kind = "violation"` with `detail.reason = "lambda_hat_budget_divergence"`. |
| `rcs.lambda_hat.decay`                      | Gauge      | `level`                       | Nominal decay $\hat{\gamma}_i$.                                         |
| `rcs.lambda_hat.adapt_cost`                 | Gauge      | `level`                       | $\hat{L}_{\theta,i}\hat{\rho}_i$ adaptation cost.                       |
| `rcs.lambda_hat.design_cost`                | Gauge      | `level`                       | $\hat{L}_{d,i}\hat{\eta}_i$ design-evolution cost.                      |
| `rcs.lambda_hat.delay_cost`                 | Gauge      | `level`                       | $\hat{\beta}_i \hat{\bar\tau}_i$ delay cost.                            |
| `rcs.lambda_hat.switch_cost`                | Gauge      | `level`                       | $\hat{\ln \nu}_i / \hat{\tau}_{a,i}$ switching cost.                    |
| `rcs.omega_hat`                             | Gauge      | (none)                        | $\hat{\omega}_N = \min_i \hat{\lambda}_i$ across active levels.         |
| `rcs.omega_hat.bottleneck_level`            | Gauge      | (none)                        | Integer 0…3 identifying which level currently realises the min.         |

### 3.2 Violation and regime events

| Metric name (OTel)                          | Kind       | Labels                        | Meaning                                                                 |
| ------------------------------------------- | ---------- | ----------------------------- | ----------------------------------------------------------------------- |
| `rcs.budget.violation.total`                | Counter    | `level`, `component`          | Increments when `rcs.lambda_hat{level}` dips ≤ 0. `component ∈ {decay, adapt, design, delay, switch, unknown}` records which term pushed it negative. |
| `rcs.regime.transition.total`               | Counter    | `from`, `to`                  | Economic-mode transitions in autonomicd (`Sovereign ↔ Conserving ↔ Hustle ↔ Hibernate`). |
| `rcs.switch.count`                          | Counter    | `level`                       | Raw mode-switching count, for $\tau_{a,i}$ empirical fit.               |

### 3.3 Supporting cadence metrics

| Metric name (OTel)                          | Kind       | Labels                        | Meaning                                                                 |
| ------------------------------------------- | ---------- | ----------------------------- | ----------------------------------------------------------------------- |
| `rcs.tick.duration_ms`                      | Histogram  | `daemon ∈ {arcand, autonomicd}` | Tick-loop wall-clock duration, needed for $\bar\tau_i$ attribution.   |
| `rcs.observer.observe_duration_ms`          | Histogram  | `level`                       | Cost of the `RcsObserver` itself; should be ≪ tick interval.            |
| `rcs.homeostatic.state.norm`                | Gauge      | (none)                        | $\|\xi\|_2$ of the observed homeostatic state; proxy for the Lyapunov value. |

> **Naming drift check.** The P1d harness MUST assert each name above against
> the life repo's `metrics.rs` at capture time and abort on mismatch. The
> assertion list lives alongside the harness.

---

## 4. Run matrix

Each row is executed 3× (seeds 0, 1, 2) for a total of 30 min × 3 × |rows|
of capture. Rows are crossed, not nested; add rows by appending, never by
reinterpreting existing rows.

| Row | Label            | Load / perturbation                                      | Purpose                                                                 |
| --- | ---------------- | -------------------------------------------------------- | ----------------------------------------------------------------------- |
| A   | `baseline`       | idle agent, no external prompts                          | Establish $\hat{\lambda}_i$ floor under nominal conditions.             |
| B   | `steady-task`    | repeated benign task stream, 1 task / 30 s                | Activate L0 tick loop without triggering L1 adaptation.                 |
| C   | `adaptation`     | task stream that forces `L_\theta \rho_1` activation     | Measure the adaptation-cost term in production.                         |
| D   | `delay-injected` | artificial tool-call delay $\bar\tau_0 \approx 2\times$  | Probe sensitivity of $\hat{\lambda}_0$ to the delay term.               |
| E   | `mode-sweep`     | cycle autonomicd through all 4 economic modes            | Measure $\ln\nu / \tau_a$ empirically and observe regime transitions.   |

Rows C, D, E must also record the perturbation schedule in
`events.ndjson` (§5) so the analysis can align cause and effect.

---

## 5. Dataset layout

All runs are written to `data/p1-runs/` at the repo root.

```text
data/p1-runs/
├── manifest.ndjson                  # one JSON object per run (metadata)
└── runs/
    └── <run-id>/                    # run-id = "<ISO-date>_<row-label>_seed<N>"
        ├── config.toml              # full daemon/runtime config for this run
        ├── git-sha.txt              # life-repo HEAD SHA at capture time
        ├── rcs-parameters.toml      # copy of the mirror used by the run
        ├── metrics.ndjson           # OTel metrics stream (schema §5.1)
        ├── events.ndjson            # perturbation + regime-transition log
        └── README.md                # human-readable summary of the run
```

- `<run-id>` example: `2026-04-30_adaptation_seed1`.
- `manifest.ndjson` is append-only; one line per run. Fields: `run_id`,
  `row_label`, `seed`, `start_ts`, `end_ts`, `life_sha`, `rcs_sha`
  (this repo), `host`, `notes`.
- `rcs-parameters.toml` is copied *from the mirror actually used by the
  live process*, not from this repo, so that a mid-run sync mismatch would
  be caught by the post-hoc drift check.

### 5.1 `metrics.ndjson` record schema

One record per metric sample. Schema (JSON Lines):

```json
{
  "ts":     "2026-04-30T13:42:05.123Z",
  "metric": "rcs.lambda_hat",
  "value":  0.4115,
  "labels": {"level": "L1"},
  "run_id": "2026-04-30_adaptation_seed1"
}
```

All timestamps UTC; all floats double-precision.

### 5.2 `events.ndjson` record schema

One record per perturbation injection or regime transition. Fields:
`ts`, `kind ∈ {perturbation, regime_transition, violation}`, `detail`
(free-form object), `run_id`.

---

## 6. Plot specification

The figures in Paper 1 are generated from the dataset in §5. Each figure's
input is a pair `(row_label, seed)` or a set thereof, named so the figure
and its generating command remain tightly coupled.

| Figure | Name                         | Content                                                                                              | Source rows |
| ------ | ---------------------------- | ---------------------------------------------------------------------------------------------------- | ----------- |
| F1     | `margin-trace-per-level.pdf` | $\hat{\lambda}_0\ldots\hat{\lambda}_3$ vs. wall-clock; one panel per level; 4 panels stacked         | A           |
| F2     | `omega-vs-regime.pdf`        | $\hat{\omega}_N$ vs. time with economic-mode stripes overlayed                                       | E           |
| F3     | `cost-breakdown.pdf`         | Stacked bar per level: median contribution of decay / adapt / design / delay / switch components    | A+B+C+D+E   |
| F4     | `violation-histogram.pdf`    | Histogram of violation counts by `(level, component)`                                                | All         |
| F5     | `delay-sensitivity.pdf`      | $\hat{\lambda}_0$ vs. injected $\bar\tau_0$ scaling factor                                           | D           |

Each figure's generating script reads only from
`data/p1-runs/runs/<run-id>/metrics.ndjson`; no intermediate SQLite or
Parquet stage. The analysis scripts live under a P1e task (separate PR).

Plots use the same colour convention as Paper 0 (Section VII tables): L0
darkest → L3 lightest; violations in red.

---

## 7. Reproducibility commands

From the root of this repo (`~/broomva/research/rcs/`):

```bash
# 1. Canonical-parameter drift check (must pass before starting a run)
make params-check

# 2. Sync the mirror into life (if parameters.toml changed since last run)
bash ~/broomva/core/life/scripts/sync-rcs-parameters.sh

# 3. Build & test the paper skeleton (sanity; does not run the experiment)
make build-p1
make test

# 4. Launch a capture run (harness lives in life-repo; landed in P1d)
#    <row> ∈ {baseline, steady-task, adaptation, delay-injected, mode-sweep}
#    <seed> ∈ {0, 1, 2}
RCS_RUN_ROOT="$PWD/data/p1-runs" \
  bash ~/broomva/core/life/scripts/p1-capture.sh <row> <seed>  # TBC-P1d

# 5. Regenerate figures from captured data
python3 papers/p1-stability/figures/make_figures.py            # TBC-P1e

# 6. Rebuild the PDFs with new figures
make build-p1
```

Every published plot, table, and quoted number in Paper 1 MUST be
reproducible by running steps 4–6 from a clean checkout of the pinned
commit SHAs recorded in `manifest.ndjson`. The paper's appendix will
include the exact command set used for the camera-ready dataset.

---

## 8. Non-goals (to prevent scope creep)

- **No theoretical extensions** of Paper 0. All proofs stay in Paper 0.
- **No new parameters** — Paper 1 consumes `data/parameters.toml` read-only.
- **No controller-improvement claims.** Measurement only. Changes to the
  controller belong in Paper 2 (EGRI) or the life repo.
- **No multi-host or fleet topology.** That is Paper 4's remit.
