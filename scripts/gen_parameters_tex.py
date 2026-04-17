#!/usr/bin/env python3
"""
Regenerate latex/parameters.tex from latex/parameters.toml.

The TOML file is the single source of truth for the RCS stability budget
parameters. This script emits a LaTeX file defining \\newcommand macros for
every parameter and derived quantity (lambda_i per level, composite omega),
so the paper can reference them symbolically and the paper/code cannot drift.

Invariants:
  - Every [[levels]] entry produces macros for gamma, L_theta, rho, L_d, eta,
    beta, tau_bar, nu, tau_a, the five costs, and the stability margin lambda.
  - The computed lambda_i values are cross-checked against [derived.lambda]
    in the TOML; the script exits 1 if any cached value differs by more than
    1e-6 from the recomputed value.
  - Composite omega = min_i lambda_i is verified against [derived.omega].

Usage:
  python3 scripts/gen_parameters_tex.py
      reads  latex/parameters.toml
      writes latex/parameters.tex (overwrite)

  python3 scripts/gen_parameters_tex.py --check
      reads  latex/parameters.toml
      writes nothing; exits 1 if latex/parameters.tex would change

The --check mode is used by CI to catch hand-edits to parameters.tex.
"""

from __future__ import annotations

import argparse
import math
import sys
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
TOML_PATH = REPO_ROOT / "latex" / "parameters.toml"
TEX_PATH = REPO_ROOT / "latex" / "parameters.tex"

LAMBDA_TOLERANCE = 1e-6


def compute_level_costs(level: dict[str, Any]) -> dict[str, float]:
    """Compute the four per-level costs and the stability margin."""
    gamma = level["gamma"]
    adapt = level["L_theta"] * level["rho"]
    design = level["L_d"] * level["eta"]
    delay = level["beta"] * level["tau_bar"]
    switch = math.log(level["nu"]) / level["tau_a"]
    lam = gamma - adapt - design - delay - switch
    return {
        "adapt_cost": adapt,
        "design_cost": design,
        "delay_cost": delay,
        "switch_cost": switch,
        "lambda": lam,
    }


def fmt(x: float) -> str:
    """Format a float for LaTeX — compact but lossless within 6 decimals.

    Used for the authoritative \\rcs<name> macros. Readers see ugly forms
    like 1.000000e-06 for very small values; paper body should use the
    \\rcs<name>Disp companion macros emitted by ``fmt_display``.
    """
    if x == 0:
        return "0"
    if abs(x) >= 1e-3 and abs(x) < 1e6:
        s = f"{x:.6f}".rstrip("0").rstrip(".")
        return s if s else "0"
    return f"{x:.6e}"


def fmt_display(x: float, digits: int) -> str:
    """Format a float for paper display. Returns LaTeX math-mode content.

    Rules:
      - |x| within [10^-digits, 10^4): decimal with ``digits`` places,
        trailing zeros stripped. E.g. 1.455357 with digits=3 -> "1.455".
      - Smaller or larger: scientific notation "a \\times 10^{b}" with
        mantissa to 1 decimal place. E.g. 1e-6 -> "1 \\times 10^{-6}".

    Companion macros using this function (\\rcs...Disp) MUST be used
    inside math mode in the paper body. Callers that need both a numeric
    value (for comparison) and a displayable form should use the raw
    \\rcs<name> macro for the former and \\rcs<name>Disp for the latter.
    """
    if x == 0:
        return "0"
    abs_x = abs(x)
    threshold = 10 ** (-digits)
    if threshold <= abs_x < 1e4:
        s = f"{x:.{digits}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s if s else "0"
    # Scientific notation: a \times 10^{b} with 1-decimal mantissa
    exp = int(math.floor(math.log10(abs_x)))
    mantissa = x / (10 ** exp)
    m_str = f"{mantissa:.1f}"
    if m_str.endswith(".0"):
        m_str = m_str[:-2]
    return f"{m_str} \\times 10^{{{exp}}}"


def level_macro_suffix(level_id: str) -> str:
    """Map 'L0' -> 'Lzero', 'L1' -> 'Lone', etc., since LaTeX macros can't have digits."""
    mapping = {"L0": "Lzero", "L1": "Lone", "L2": "Ltwo", "L3": "Lthree"}
    if level_id not in mapping:
        raise ValueError(
            f"Unsupported level id {level_id!r}: expected one of {list(mapping)}"
        )
    return mapping[level_id]


def generate_tex(config: dict[str, Any]) -> str:
    lines = [
        "% =============================================================================",
        "% RCS — Canonical Parameters (auto-generated — do NOT edit by hand)",
        "% =============================================================================",
        "%",
        "% This file is regenerated from latex/parameters.toml by",
        "% scripts/gen_parameters_tex.py. CI verifies the two stay in sync.",
        "% Edit parameters.toml and re-run the generator instead.",
        "",
    ]

    # Validate derived values against computed ones.
    derived_lambda = config.get("derived", {}).get("lambda", {})
    derived_omega = config.get("derived", {}).get("omega", {})

    min_lambda = math.inf
    min_level = None
    for level in config["levels"]:
        suffix = level_macro_suffix(level["id"])
        costs = compute_level_costs(level)
        lam = costs["lambda"]

        cached = derived_lambda.get(level["id"])
        if cached is not None and abs(cached - lam) > LAMBDA_TOLERANCE:
            raise SystemExit(
                f"drift: [derived.lambda].{level['id']} = {cached} in TOML but "
                f"recomputed = {lam:.9f} (|diff| > {LAMBDA_TOLERANCE}). "
                f"Update the [derived.lambda] cache in parameters.toml."
            )

        if lam < min_lambda:
            min_lambda = lam
            min_level = level["id"]

        digits = level.get("display_digits", 4)
        for field in ("gamma", "L_theta", "rho", "L_d", "eta", "beta", "tau_bar", "nu", "tau_a"):
            macro = f"rcs{field.replace('_', '')}{suffix}"
            lines.append(f"\\newcommand{{\\{macro}}}{{{fmt(level[field])}}}")
            lines.append(f"\\newcommand{{\\{macro}Disp}}{{{fmt_display(level[field], digits)}}}")
        for cost in ("adapt_cost", "design_cost", "delay_cost", "switch_cost"):
            macro = f"rcs{cost.replace('_', '')}{suffix}"
            lines.append(f"\\newcommand{{\\{macro}}}{{{fmt(costs[cost])}}}")
            lines.append(f"\\newcommand{{\\{macro}Disp}}{{{fmt_display(costs[cost], digits)}}}")
        lines.append(f"\\newcommand{{\\rcsmargin{suffix}}}{{{fmt(lam)}}}")
        lines.append(f"\\newcommand{{\\rcsmargin{suffix}Disp}}{{{fmt_display(lam, digits)}}}")
        lines.append("")

    cached_omega = derived_omega.get("value")
    if cached_omega is not None and abs(cached_omega - min_lambda) > LAMBDA_TOLERANCE:
        raise SystemExit(
            f"drift: [derived.omega].value = {cached_omega} in TOML but "
            f"recomputed = {min_lambda:.9f} (|diff| > {LAMBDA_TOLERANCE}). "
            f"Update the [derived.omega] cache in parameters.toml."
        )
    cached_omega_level = derived_omega.get("level")
    if cached_omega_level is not None and cached_omega_level != min_level:
        raise SystemExit(
            f"drift: [derived.omega].level = {cached_omega_level!r} in TOML but "
            f"argmin is {min_level!r}."
        )

    lines.append(f"\\newcommand{{\\rcsomega}}{{{fmt(min_lambda)}}}")
    lines.append(f"\\newcommand{{\\rcsomegalevel}}{{{min_level}}}")
    lines.append("")

    # Eslami reference parameters (as macros so the paper can cite exact values).
    eslami = config.get("eslami_2026", {})
    for case_name in ("stable", "unstable"):
        case = eslami.get(case_name)
        if not case:
            continue
        lines.append(f"% Eslami & Yu (2026), Section V — {case_name} case")
        for field in ("gamma", "L_theta", "rho", "L_d", "eta", "beta", "tau_bar", "nu", "tau_a", "expected_lambda"):
            if field not in case:
                continue
            name = field.replace("_", "")
            lines.append(
                f"\\newcommand{{\\rcsEslami{case_name.capitalize()}{name}}}{{{fmt(case[field])}}}"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit 1 if the file on disk would change.",
    )
    args = parser.parse_args()

    with TOML_PATH.open("rb") as f:
        config = tomllib.load(f)

    try:
        new_content = generate_tex(config)
    except SystemExit as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.check:
        if not TEX_PATH.exists():
            print(f"error: {TEX_PATH} does not exist — run without --check", file=sys.stderr)
            return 1
        current = TEX_PATH.read_text()
        if current != new_content:
            print(
                f"error: {TEX_PATH} is out of sync with {TOML_PATH}. "
                f"Run: python3 scripts/gen_parameters_tex.py",
                file=sys.stderr,
            )
            return 1
        print(f"ok: {TEX_PATH} matches {TOML_PATH}")
        return 0

    TEX_PATH.write_text(new_content)
    print(f"wrote {TEX_PATH} ({len(new_content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
