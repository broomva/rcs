"""Joint phase gate evaluator (Q1-T7).

Reads pre-registration TOML, computes G1-G3 (math gate) + P1 (production
gate) on a trained substrate + holdout trajectories, emits a structured
gate report with PASS/FAIL decision.

Spec ref: Section 5.1 (joint gate definition).

Pre-registered thresholds live in `data/q1_pre_registration.toml`. This
script must NEVER hardcode thresholds — they come from the TOML AND the
analysis run cites the commit hash in the report.

Usage:
    python -m scripts.jepa_validate \\
        --substrate reports/q1-substrate/substrate.pt \\
        --workspaces reports/q1-substrate/raw/ \\
        --pre-registration data/q1_pre_registration.toml \\
        --out reports/q1-substrate/q1_gate_report.json
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


# === Per-gate evaluators ====================================================

def evaluate_g1_var_ratio(
    jepa_var_per_cell: dict[str, float | None],
    heur_var_per_cell: dict[str, float | None],
    threshold: float = 1.0,
    min_conditions: int = 3,
) -> dict:
    """G1: median Var[λ̂_0]_JEPA / Var[λ̂_0]_heuristic < threshold across
    ≥min_conditions conditions."""
    ratios = []
    for cond in jepa_var_per_cell:
        j = jepa_var_per_cell[cond]
        h = heur_var_per_cell.get(cond)
        if j is None or h is None or h == 0:
            continue
        if not (math.isfinite(j) and math.isfinite(h)):
            continue
        ratios.append(j / h)
    if len(ratios) < min_conditions:
        return {"pass": False,
                "reason": f"insufficient_conditions ({len(ratios)} < {min_conditions})",
                "n_conditions": len(ratios)}
    median = float(np.median(ratios))
    return {"pass": median < threshold,
            "median_ratio": median,
            "n_conditions": len(ratios),
            "all_ratios": ratios}


def evaluate_g2_pearson(
    lambdas: np.ndarray,
    scores: np.ndarray,
    threshold: float = -0.2,
) -> dict:
    """G2: Pearson r(λ̂, episode_score) ≤ threshold (predictor surprise
    tracks failure → negative r)."""
    finite = np.isfinite(lambdas) & np.isfinite(scores)
    lambdas, scores = lambdas[finite], scores[finite]
    if len(lambdas) < 3 or lambdas.std() == 0 or scores.std() == 0:
        return {"pass": False, "reason": "insufficient_data_or_zero_variance"}
    r = float(np.corrcoef(lambdas, scores)[0, 1])
    return {"pass": r <= threshold, "pearson_r": r, "n": len(lambdas)}


def evaluate_g3_training_health(
    history: list[dict],
    min_std_mean: float = 0.5,
    max_consecutive_increases: int = 3,
    epoch_for_std_check: int = 100,
) -> dict:
    """G3: training health — std_mean ≥ threshold, no NaN, ≤max consecutive
    loss-increases."""
    if not history:
        return {"pass": False, "reason": "empty_history"}
    if any(not math.isfinite(h.get("loss", float("inf"))) for h in history):
        return {"pass": False, "reason": "nan_in_loss"}
    # std_mean check at later of (epoch_for_std_check, last_epoch)
    last_idx = min(epoch_for_std_check, len(history) - 1)
    std_mean_at_check = history[last_idx].get("std_mean", 0.0)
    if std_mean_at_check < min_std_mean:
        return {"pass": False,
                "reason": f"low_std_mean ({std_mean_at_check} < {min_std_mean})",
                "std_mean_at_check": std_mean_at_check}
    # Monotone-ish: count consecutive epoch-over-epoch increases
    losses = [h.get("loss", 0.0) for h in history]
    consec = 0
    max_consec = 0
    for i in range(1, len(losses)):
        if losses[i] > losses[i - 1]:
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0
    if max_consec > max_consecutive_increases:
        return {"pass": False,
                "reason": f"non_monotone (max consec increases {max_consec})",
                "max_consecutive_increases": max_consec}
    return {"pass": True,
            "std_mean_at_check": std_mean_at_check,
            "max_consecutive_increases": max_consec}


def evaluate_p1_spearman(
    lambdas: np.ndarray,
    pass_bool: np.ndarray,
    threshold: float = -0.15,
    significance: float = 0.05,
) -> dict:
    """P1: Spearman ρ(λ̂, pass) ≤ threshold with p<significance."""
    try:
        from scipy import stats
    except ImportError:
        return {"pass": False, "reason": "scipy_not_installed"}
    finite = np.isfinite(lambdas)
    lambdas, pass_bool = lambdas[finite], pass_bool[finite]
    if len(lambdas) < 3 or lambdas.std() == 0:
        return {"pass": False, "reason": "insufficient_data_or_zero_variance"}
    rho, p = stats.spearmanr(lambdas, pass_bool)
    return {"pass": bool((rho <= threshold) and (p < significance)),
            "spearman_rho": float(rho),
            "p_value": float(p),
            "n": len(lambdas)}


# === Joint gate decision ====================================================

def joint_gate_decision(
    g1: dict, g2: dict, g3: dict, p1: dict,
    math_pass_threshold: int = 2,
) -> dict:
    """Joint gate: math 2-of-3 + P1 both must pass."""
    math_passes = sum(int(bool(g.get("pass", False))) for g in (g1, g2, g3))
    p1_pass = bool(p1.get("pass", False))
    failed_gates = []
    if not g1.get("pass"):
        failed_gates.append("g1")
    if not g2.get("pass"):
        failed_gates.append("g2")
    if not g3.get("pass"):
        failed_gates.append("g3")
    if not p1_pass:
        failed_gates.append("p1")
    overall = ("PASS" if (math_passes >= math_pass_threshold and p1_pass)
                else "FAIL")
    return {
        "overall": overall,
        "math_gate_passes": math_passes,
        "math_gate_threshold": math_pass_threshold,
        "p1_pass": p1_pass,
        "failed_gates": failed_gates,
    }


# === Report =================================================================

@dataclass
class GateReport:
    commit_hash: str
    q_phase: str
    gates: dict
    decision: str
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "commit_hash": self.commit_hash,
            "q_phase": self.q_phase,
            "gates": self.gates,
            "decision": self.decision,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def save(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2,
                                          default=str))

    def render_markdown(self) -> str:
        out = [f"# Q-Phase Gate Report — {self.q_phase}",
               "",
               f"**Commit:** {self.commit_hash}",
               f"**Timestamp:** {self.timestamp}",
               f"**Decision:** **{self.decision}**",
               ""]
        for gate_name, gate in self.gates.items():
            status = "✓" if gate.get("pass") else "✗"
            out.append(f"## {gate_name.upper()} — {status}")
            for k, v in gate.items():
                if k == "pass":
                    continue
                out.append(f"- `{k}`: {v}")
            out.append("")
        return "\n".join(out)


def _git_commit_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()[:8]
    except subprocess.CalledProcessError:
        return "unknown"


# === CLI ====================================================================

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--substrate", required=True,
                    help="Path to trained substrate .pt")
    ap.add_argument("--workspaces", required=True,
                    help="Directory with raw events.jsonl per workspace")
    ap.add_argument("--pre-registration", required=True,
                    help="Path to q1_pre_registration.toml")
    ap.add_argument("--out", default="reports/q1_gate_report.json")
    args = ap.parse_args(argv)

    import tomllib
    cfg = tomllib.loads(Path(args["pre_registration"]).read_text() if isinstance(
        args, dict) else Path(args.pre_registration).read_text())
    q1 = cfg["q1"]

    # Load substrate (skipped here — Task 8 wires the actual evaluation)
    # Compute G1-G3 + P1 from holdout trajectories (skipped here; placeholder)

    decision = joint_gate_decision(
        g1={"pass": False, "reason": "stub"},
        g2={"pass": False, "reason": "stub"},
        g3={"pass": False, "reason": "stub"},
        p1={"pass": False, "reason": "stub"},
    )
    rep = GateReport(
        commit_hash=_git_commit_hash(), q_phase="Q1",
        gates={"g1": {}, "g2": {}, "g3": {}, "p1": {}},
        decision=decision["overall"],
    )
    rep.save(args.out)
    print(f"[jepa-validate] wrote {args.out}: {rep.decision}")
    return 0 if rep.decision == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
