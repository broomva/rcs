#!/usr/bin/env bash
# Q1-T2: SWE-bench-Lite training-data collection.
#
# Pre-registered config from data/q1_pre_registration.toml:
# - 10 instances × 4 conditions × 3 seeds = 120 episodes
# - Haiku as L0/L1 model
# - Persistent workspace, --save-events flag (Q1-T1)
# - Budget cap $10, 24h wall-clock
#
# Wall-clock estimate: ~12-24h continuous.
# Cost estimate: ~$8-12 (Haiku ~$0.07-0.10/instance).
#
# Run from the rcs repo root:
#   ./scripts/launch_q1_data_collection.sh
#
# Requires:
# - ANTHROPIC_API_KEY exported in the shell
# - Pre-registration TOML committed (PR #49 / Task 0)
# - --save-events flag in swe_pilot (PR #50 / Task 1)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ERROR: ANTHROPIC_API_KEY is not set in this shell." >&2
    echo "Export it first: export ANTHROPIC_API_KEY='sk-ant-...'" >&2
    exit 2
fi

# Read pre-registered instance set + seeds + conditions from TOML
INSTANCES=$(python3 -c "
import tomllib
from pathlib import Path
cfg = tomllib.loads(Path('data/q1_pre_registration.toml').read_text())
print(','.join(cfg['q1']['instances']['ids']))
")

CONDITIONS=$(python3 -c "
import tomllib
from pathlib import Path
cfg = tomllib.loads(Path('data/q1_pre_registration.toml').read_text())
print(','.join(cfg['q1']['conditions']['values']))
")

MODEL=$(python3 -c "
import tomllib
from pathlib import Path
cfg = tomllib.loads(Path('data/q1_pre_registration.toml').read_text())
print(cfg['q1']['model']['provider'])
")

# Seeds need separate runs since swe_pilot is single-seed.
# Pre-reg TOML has [1, 1009, 2018]. We loop.
SEEDS=$(python3 -c "
import tomllib
from pathlib import Path
cfg = tomllib.loads(Path('data/q1_pre_registration.toml').read_text())
print(' '.join(str(s) for s in cfg['q1']['seeds']['values']))
")

# Strip 'anthropic:' prefix for swe_pilot CLI which takes bare model name.
MODEL_BARE="${MODEL#anthropic:}"

OUTDIR="reports/q1-substrate"
mkdir -p "${OUTDIR}"

# Build --instance flags (one per instance ID).
INSTANCE_FLAGS=""
IFS=',' read -ra INSTANCE_ARR <<< "$INSTANCES"
for inst in "${INSTANCE_ARR[@]}"; do
    INSTANCE_FLAGS="${INSTANCE_FLAGS} --instance ${inst}"
done

echo "[q1-t2] Pre-registered config:"
echo "  instances: ${INSTANCES}"
echo "  conditions: ${CONDITIONS}"
echo "  seeds: ${SEEDS}"
echo "  model: ${MODEL_BARE}"
echo ""

T_START=$(date +%s)

for SEED in $SEEDS; do
    SEED_OUT="${OUTDIR}/seed-${SEED}"
    if [ -f "${SEED_OUT}/seed-done" ]; then
        echo "[q1-t2] seed=${SEED} already done; skipping"
        continue
    fi

    echo "[q1-t2] === seed=${SEED} ==="
    cd microrcs

    # Note: swe_pilot doesn't take --seed natively (it's single-seed by design).
    # We use PYTHONHASHSEED + a separate output dir per seed for variability.
    PYTHONHASHSEED=${SEED} python3 -m scripts.swe_pilot \
        --conditions "${CONDITIONS}" \
        ${INSTANCE_FLAGS} \
        --model-l0-l1 "${MODEL_BARE}" \
        --model-l2-l3 "${MODEL_BARE}" \
        --max-steps 100 \
        --max-cost 2.0 \
        --pytest-timeout 180 \
        --save-events \
        --out "../${SEED_OUT}" \
        2>&1 | tee "../${SEED_OUT}.log"

    cd ..
    touch "${SEED_OUT}/seed-done"
done

T_END=$(date +%s)
ELAPSED=$((T_END - T_START))
echo ""
echo "[q1-t2] all seeds done in $((ELAPSED/3600))h$((ELAPSED%3600/60))m"

# Aggregate workspace structure into a single root for jepa_a.collect_step_trajectories
# Each seed has its own workspaces/<cond_safe>/<cid>/.rcs/events.jsonl;
# we aggregate by namespacing cids with seed.
mkdir -p "${OUTDIR}/raw"
for SEED in $SEEDS; do
    SEED_WS="${OUTDIR}/seed-${SEED}/workspaces"
    if [ ! -d "${SEED_WS}" ]; then
        echo "[q1-t2] WARN: ${SEED_WS} missing; --save-events may have failed for seed ${SEED}"
        continue
    fi
    for COND_DIR in "${SEED_WS}"/*; do
        COND_NAME=$(basename "${COND_DIR}")
        TARGET="${OUTDIR}/raw/${COND_NAME}-seed${SEED}"
        if [ ! -d "${TARGET}" ]; then
            ln -s "$(cd "${COND_DIR}" && pwd)" "${TARGET}"
        fi
    done
done

echo "[q1-t2] aggregated raw workspaces: ${OUTDIR}/raw/"
ls -la "${OUTDIR}/raw/" || true

# Sanity check: count events.jsonl files
N_LOGS=$(find "${OUTDIR}/raw" -name "events.jsonl" 2>/dev/null | wc -l)
echo "[q1-t2] events.jsonl count: ${N_LOGS}"
echo "[q1-t2] expected: ~120 (10 instances × 4 conds × 3 seeds = 120 episodes)"
