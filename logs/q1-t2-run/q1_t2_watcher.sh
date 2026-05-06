#!/usr/bin/env bash
# Q1-T2 watcher — sibling primitive to P9 (CI watcher), adapted to a
# long-running compute job rather than a CI run.
#
# Polls Q1-T2-RUN's PID, episode count, cost, and wall-clock; writes
# structured state events to state.jsonl; exits on terminal state with
# a classifier code.
#
# Terminal-state exit codes (mirroring P9 conventions):
#   0   SUCCESS         — PID dead AND >= MIN_EPISODES events.jsonl present
#   10  COST_CAPPED     — accumulated cost >= MAX_USD
#   11  TIME_CAPPED     — elapsed >= MAX_HOURS * 3600 seconds
#   12  ABANDONED       — PID dead with < MIN_EPISODES events
#   13  PROCESS_GONE    — PID dead before any episodes (early failure)
#   99  UNRECOVERABLE   — cannot write state.jsonl (P9 cardinal invariant)
#
# Usage:
#   q1_t2_watcher.sh <pid> <state_dir> <reports_dir>

set -euo pipefail

PID="${1:?usage: q1_t2_watcher.sh <pid> <state_dir> <reports_dir>}"
STATE_DIR="${2:?missing state_dir}"
REPORTS_DIR="${3:?missing reports_dir}"

STATE_FILE="${STATE_DIR}/state.jsonl"
POLL_INTERVAL="${POLL_INTERVAL:-60}"   # seconds between polls
MIN_EPISODES="${MIN_EPISODES:-100}"    # 120 expected; allow 100 for partial-success classification
MAX_USD="${MAX_USD:-10.0}"             # pre-reg budget cap (data/q1_pre_registration.toml)
MAX_HOURS="${MAX_HOURS:-24}"           # pre-reg wall-clock cap
MAX_SECONDS=$(( MAX_HOURS * 3600 ))

emit_event() {
    # emit_event <event_type> <extras_json>
    local etype="$1"
    local extras="${2:-{\}}"
    local ts
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    if ! printf '{"ts":"%s","event":"%s","pid":%d,"extras":%s}\n' \
            "$ts" "$etype" "$PID" "$extras" >> "$STATE_FILE" 2>/dev/null; then
        # Cardinal invariant: cannot silently drop state.
        echo "[q1-t2-watcher] FATAL: cannot write state.jsonl" >&2
        exit 99
    fi
}

is_alive() {
    kill -0 "$PID" 2>/dev/null
}

count_events() {
    # Returns the number of events.jsonl files under reports/q1-substrate/
    find "$REPORTS_DIR" -name events.jsonl 2>/dev/null | wc -l | tr -d ' '
}

estimate_cost_usd() {
    # Sum cost from per-instance lines in seed-*.log (the tee'd swe_pilot output).
    # Format: "[pilot] │  <instance>  · score=X steps=N cost=$Y.YYYY  wall=Zs"
    # or:     "[pilot] │  <instance>  ✗ ... cost=$Y.YYYY ... abort=cost_budget"
    # We exclude per-condition aggregate lines ("done: pass^1=") to avoid double-counting.
    # NOTE: events.jsonl files do NOT carry cost; the .log per-instance lines are
    # the only authoritative source. Initial implementation tried events.jsonl and
    # always returned 0.0; that bug let a 3x budget breach slip through (see
    # state.jsonl event "cost_cap_breached" 2026-05-06).
    if [ ! -d "$REPORTS_DIR" ]; then
        echo "0.00"
        return
    fi
    grep -h "score=" "$REPORTS_DIR"/seed-*.log 2>/dev/null | \
        grep -v "done: pass" | \
        grep -oE 'cost=\$[0-9]+\.[0-9]+' | \
        grep -oE '[0-9]+\.[0-9]+' | \
        python3 -c "import sys; vals=[float(l) for l in sys.stdin]; print(f'{sum(vals):.4f}')" 2>/dev/null || echo "0.00"
}

count_episodes_completed() {
    # Count per-instance result lines (· or ✗ markers) in seed-*.log.
    # This is more accurate than events.jsonl file count because some instances
    # that hit per-instance --max-cost still log a result line but may not have
    # a finalized events.jsonl. Same bug-fix lineage as estimate_cost_usd().
    if [ ! -d "$REPORTS_DIR" ]; then
        echo "0"
        return
    fi
    grep -h "score=" "$REPORTS_DIR"/seed-*.log 2>/dev/null | \
        grep -v "done: pass" | wc -l | tr -d ' '
}

START_TS=$(date +%s)
mkdir -p "$STATE_DIR"
emit_event "watcher_started" "{\"poll_interval_s\":${POLL_INTERVAL},\"min_episodes\":${MIN_EPISODES},\"max_usd\":${MAX_USD},\"max_hours\":${MAX_HOURS}}"

while true; do
    NOW=$(date +%s)
    ELAPSED=$(( NOW - START_TS ))
    # Authoritative episode count: per-instance result lines in seed-*.log.
    # Prefer this over events.jsonl because partial/cost-capped episodes
    # have a result line but may not finalize events.jsonl.
    EPISODES=$(count_episodes_completed)
    EVENTS_JSONL=$(count_events)
    COST=$(estimate_cost_usd)
    ALIVE=$(is_alive && echo true || echo false)

    POLL_JSON="{\"alive\":${ALIVE},\"episodes\":${EPISODES},\"events_jsonl\":${EVENTS_JSONL},\"cost_usd\":${COST},\"elapsed_s\":${ELAPSED}}"

    # Cost cap (pre-registered)
    if (( $(echo "$COST >= $MAX_USD" | bc -l 2>/dev/null || echo 0) )); then
        emit_event "terminal_cost_capped" "$POLL_JSON"
        kill -TERM "$PID" 2>/dev/null || true
        exit 10
    fi

    # Wall-clock cap (pre-registered)
    if (( ELAPSED >= MAX_SECONDS )); then
        emit_event "terminal_time_capped" "$POLL_JSON"
        kill -TERM "$PID" 2>/dev/null || true
        exit 11
    fi

    # Process gone
    if [ "$ALIVE" = "false" ]; then
        if (( EPISODES >= MIN_EPISODES )); then
            emit_event "terminal_success" "$POLL_JSON"
            exit 0
        elif (( EPISODES > 0 )); then
            emit_event "terminal_abandoned" "$POLL_JSON"
            exit 12
        else
            emit_event "terminal_process_gone" "$POLL_JSON"
            exit 13
        fi
    fi

    # Heartbeat
    emit_event "poll" "$POLL_JSON"

    sleep "$POLL_INTERVAL"
done
