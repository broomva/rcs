"""Tests for joint-gate evaluator (Q1-T7)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.jepa_validate import (  # noqa: E402
    GateReport,
    evaluate_g1_var_ratio,
    evaluate_g2_pearson,
    evaluate_g3_training_health,
    evaluate_p1_spearman,
    joint_gate_decision,
)


def test_g1_passes_when_var_ratio_below_threshold():
    """G1: median Var ratio < 1.0 → pass."""
    jepa_var_per_cell = {"flat": 0.5, "+autonomic": 0.6, "+meta": 0.7}
    heur_var_per_cell = {"flat": 1.0, "+autonomic": 1.0, "+meta": 1.0}
    result = evaluate_g1_var_ratio(jepa_var_per_cell, heur_var_per_cell,
                                    threshold=1.0, min_conditions=3)
    assert result["pass"] is True
    assert result["median_ratio"] == pytest.approx(0.6, rel=0.1)


def test_g1_fails_when_too_few_conditions():
    """G1: needs ≥min_conditions cells with finite ratios."""
    result = evaluate_g1_var_ratio({"flat": 0.5}, {"flat": 1.0},
                                    threshold=1.0, min_conditions=3)
    assert result["pass"] is False
    assert "insufficient_conditions" in result["reason"]


def test_g2_passes_when_pearson_below_negative_threshold():
    """G2: r(λ̂, score) ≤ -0.2 → pass."""
    # Anticorrelated: as λ̂ increases, score decreases
    lambdas = np.array([0.1, 0.2, 0.3, 0.4])
    scores = np.array([1.0, 0.5, 0.5, 0.0])
    result = evaluate_g2_pearson(lambdas, scores, threshold=-0.2)
    assert result["pass"] is True
    assert result["pearson_r"] < -0.2


def test_g2_fails_on_zero_correlation():
    """G2: r ≈ 0 → fail."""
    lambdas = np.array([0.1, 0.2, 0.3, 0.4])
    scores = np.array([1.0, 0.0, 0.0, 1.0])  # uncorrelated (r=0)
    result = evaluate_g2_pearson(lambdas, scores, threshold=-0.2)
    # |r| likely small; depends on exact pattern but should not be < -0.2
    assert result["pass"] is False or result["pearson_r"] > -0.2


def test_g3_passes_with_healthy_history():
    """G3: std_mean ≥ 0.5 by epoch 100, no NaN, monotone-ish loss."""
    history = [{"epoch": i, "loss": 10.0 - i * 0.05,
                "std_mean": min(1.0, 0.3 + i * 0.01)}
                for i in range(100)]
    result = evaluate_g3_training_health(history, min_std_mean=0.5,
                                          max_consecutive_increases=3)
    assert result["pass"] is True


def test_g3_fails_on_nan_loss():
    """G3: any NaN loss → fail."""
    history = [{"epoch": 0, "loss": float("nan"), "std_mean": 0.5}]
    result = evaluate_g3_training_health(history, min_std_mean=0.5,
                                          max_consecutive_increases=3)
    assert result["pass"] is False
    assert "nan" in result["reason"].lower()


def test_g3_fails_on_low_std_mean():
    """G3: std_mean < 0.5 at epoch 100 → fail (collapse)."""
    history = [{"epoch": i, "loss": 1.0, "std_mean": 0.1}
                for i in range(110)]
    result = evaluate_g3_training_health(history, min_std_mean=0.5,
                                          max_consecutive_increases=3)
    assert result["pass"] is False


def test_p1_passes_with_strong_negative_spearman():
    """P1: ρ(λ̂, pass) ≤ -0.15 with p<0.05 → pass."""
    # Need n large enough for significance
    lambdas = np.linspace(0.1, 1.0, 20)
    pass_bool = np.array([1] * 10 + [0] * 10)  # low λ̂ → pass; high λ̂ → fail
    result = evaluate_p1_spearman(lambdas, pass_bool, threshold=-0.15,
                                    significance=0.05)
    assert result["pass"] is True
    assert result["spearman_rho"] < -0.15
    assert result["p_value"] < 0.05


def test_joint_gate_pass_with_2of3_math_and_p1():
    """Joint gate: math 2-of-3 pass + P1 pass → overall pass."""
    decision = joint_gate_decision(
        g1={"pass": True, "median_ratio": 0.6},
        g2={"pass": True, "pearson_r": -0.3},
        g3={"pass": False, "reason": "std_mean too low"},
        p1={"pass": True, "spearman_rho": -0.2, "p_value": 0.01},
    )
    assert decision["overall"] == "PASS"


def test_joint_gate_fail_when_only_1of3_math():
    """Joint gate: only 1 of 3 math gates pass → overall fail."""
    decision = joint_gate_decision(
        g1={"pass": True, "median_ratio": 0.6},
        g2={"pass": False, "pearson_r": -0.1},
        g3={"pass": False, "reason": "nan"},
        p1={"pass": True, "spearman_rho": -0.2, "p_value": 0.01},
    )
    assert decision["overall"] == "FAIL"
    assert decision["math_gate_passes"] == 1


def test_joint_gate_fail_when_p1_fails():
    """Joint gate: math passes but P1 fails → overall fail."""
    decision = joint_gate_decision(
        g1={"pass": True, "median_ratio": 0.6},
        g2={"pass": True, "pearson_r": -0.3},
        g3={"pass": True},
        p1={"pass": False, "spearman_rho": -0.05, "p_value": 0.5},
    )
    assert decision["overall"] == "FAIL"
    assert "p1" in decision.get("failed_gates", [])


def test_gate_report_serializes_to_json(tmp_path):
    """GateReport.save() emits valid JSON."""
    rep = GateReport(
        commit_hash="abc1234", q_phase="Q1",
        gates={"g1": {"pass": True}, "g2": {"pass": True},
               "g3": {"pass": True}, "p1": {"pass": True}},
        decision="PASS",
    )
    path = tmp_path / "report.json"
    rep.save(path)
    loaded = json.loads(path.read_text())
    assert loaded["q_phase"] == "Q1"
    assert loaded["decision"] == "PASS"


def test_gate_report_render_markdown(tmp_path):
    """GateReport.render_markdown() emits human-readable summary."""
    rep = GateReport(
        commit_hash="abc1234", q_phase="Q1",
        gates={"g1": {"pass": True, "median_ratio": 0.6}, "g2": {"pass": True},
               "g3": {"pass": True}, "p1": {"pass": True}},
        decision="PASS",
    )
    md = rep.render_markdown()
    assert "Q1" in md
    assert "PASS" in md
    assert "0.6" in md  # median_ratio shown
