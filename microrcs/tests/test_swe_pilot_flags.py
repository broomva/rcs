"""Tests for swe_pilot CLI flags (Q1-T1).

The --save-events flag enables per-workspace events.jsonl mirroring so
collect_step_trajectories (jepa_a.py) can consume the data for substrate
training. Without it, swe_pilot only writes a consolidated log per
condition that does not match the per-workspace structure jepa_a expects.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import swe_pilot as sp  # noqa: E402


def test_build_parser_exposes_save_events_flag():
    """The --save-events flag is wired into the CLI."""
    parser = sp.build_parser()
    args = parser.parse_args(["--save-events"])
    assert args.save_events is True


def test_build_parser_save_events_default_off():
    """Default behavior: --save-events is False (backward compat)."""
    parser = sp.build_parser()
    args = parser.parse_args([])
    assert args.save_events is False


def test_split_log_to_workspaces_round_trip(tmp_path):
    """Splitting a consolidated events.jsonl produces per-(cond, cid) files."""
    consolidated = tmp_path / "consolidated.jsonl"
    cond_safe = "flat"

    # Two episodes, three events each. Distinct correlation_ids.
    events = [
        {"event_id": "e1", "parent_id": None, "timestamp": 1.0, "level": 0,
         "kind": "observe", "correlation_id": "ep_alpha",
         "payload": {"step": 0}},
        {"event_id": "e2", "parent_id": "e1", "timestamp": 1.1, "level": 0,
         "kind": "decide", "correlation_id": "ep_alpha",
         "payload": {"tool": "bash"}},
        {"event_id": "e3", "parent_id": "e2", "timestamp": 1.2, "level": 0,
         "kind": "step", "correlation_id": "ep_alpha",
         "payload": {"is_error": False}},
        {"event_id": "e4", "parent_id": None, "timestamp": 2.0, "level": 0,
         "kind": "observe", "correlation_id": "ep_beta",
         "payload": {"step": 0}},
        {"event_id": "e5", "parent_id": "e4", "timestamp": 2.1, "level": 0,
         "kind": "decide", "correlation_id": "ep_beta",
         "payload": {"tool": "submit"}},
        {"event_id": "e6", "parent_id": "e5", "timestamp": 2.2, "level": 0,
         "kind": "lyapunov", "correlation_id": "ep_beta",
         "payload": {"V": 0.1, "score": 1.0, "step": 1, "cost": 0.01}},
    ]
    consolidated.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    output_root = tmp_path / "workspaces"
    n_split = sp._split_log_to_workspaces(consolidated, output_root, cond_safe)
    assert n_split == 2

    # Per-cid workspaces created
    alpha_log = output_root / cond_safe / "ep_alpha" / ".rcs" / "events.jsonl"
    beta_log = output_root / cond_safe / "ep_beta" / ".rcs" / "events.jsonl"
    assert alpha_log.exists()
    assert beta_log.exists()

    # Round-trip: each per-cid file contains exactly its events
    alpha_events = [json.loads(l) for l in alpha_log.read_text().splitlines()
                    if l.strip()]
    assert len(alpha_events) == 3
    assert all(e["correlation_id"] == "ep_alpha" for e in alpha_events)

    beta_events = [json.loads(l) for l in beta_log.read_text().splitlines()
                   if l.strip()]
    assert len(beta_events) == 3
    assert all(e["correlation_id"] == "ep_beta" for e in beta_events)


def test_split_log_skips_non_episode_correlation_ids(tmp_path):
    """Only events with correlation_id starting 'ep_' get split out."""
    consolidated = tmp_path / "consolidated.jsonl"
    events = [
        {"event_id": "e1", "parent_id": None, "timestamp": 1.0, "level": 0,
         "kind": "observe", "correlation_id": "ep_real",
         "payload": {"step": 0}},
        {"event_id": "e2", "parent_id": None, "timestamp": 2.0, "level": 1,
         "kind": "decide", "correlation_id": "control",
         "payload": {"action": "noop"}},
        {"event_id": "e3", "parent_id": None, "timestamp": 3.0, "level": 2,
         "kind": "lyapunov", "correlation_id": "epoch_5",
         "payload": {"V": 0.5}},
    ]
    consolidated.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    output_root = tmp_path / "workspaces"
    n_split = sp._split_log_to_workspaces(consolidated, output_root, "flat")
    assert n_split == 1
    assert (output_root / "flat" / "ep_real" / ".rcs" / "events.jsonl").exists()
    assert not (output_root / "flat" / "control").exists()
    assert not (output_root / "flat" / "epoch_5").exists()


def test_split_log_handles_missing_consolidated_file(tmp_path):
    """If the consolidated log doesn't exist, return 0 (no error)."""
    n_split = sp._split_log_to_workspaces(
        tmp_path / "missing.jsonl", tmp_path / "out", "flat"
    )
    assert n_split == 0


def test_split_log_skips_malformed_jsonl_lines(tmp_path):
    """Malformed lines are skipped; valid lines processed."""
    consolidated = tmp_path / "consolidated.jsonl"
    consolidated.write_text(
        '{"correlation_id": "ep_a", "event_id": "e1", "level": 0}\n'
        'not-json-at-all\n'
        '{"correlation_id": "ep_a", "event_id": "e2", "level": 0}\n'
    )
    output_root = tmp_path / "workspaces"
    n_split = sp._split_log_to_workspaces(consolidated, output_root, "flat")
    assert n_split == 1
    log = output_root / "flat" / "ep_a" / ".rcs" / "events.jsonl"
    valid = [l for l in log.read_text().splitlines() if l.strip()]
    assert len(valid) == 2


def test_split_log_handles_empty_log(tmp_path):
    """Empty or whitespace-only log produces zero workspaces."""
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n\n  \n")
    output_root = tmp_path / "workspaces"
    n_split = sp._split_log_to_workspaces(empty, output_root, "flat")
    assert n_split == 0
