"""Starter helpers — stdlib-only utilities the agent may use, edit, or replace.

Available as `from helpers.starter import *` after adding helpers/ to sys.path.
"""

import json
import re
from pathlib import Path


def parse_int(s: str) -> int | None:
    """Parse an integer from messy input. Returns None if not a clean int."""
    s = s.strip().replace(",", "")
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def parse_float(s: str) -> float | None:
    """Parse a float from messy input."""
    s = s.strip().replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def normalize_text(s: str) -> str:
    """Lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", s.strip().lower())


def safe_eval_arith(expr: str) -> float | None:
    """Evaluate a pure arithmetic expression. None on any non-arithmetic input."""
    if not re.fullmatch(r"[\d\s+\-*/().]+", expr):
        return None
    try:
        return float(eval(expr, {"__builtins__": {}}))  # noqa: S307 — guarded
    except Exception:
        return None


def time_to_minutes(hhmm: str) -> int | None:
    """'HH:MM' → minutes since midnight."""
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", hhmm.strip())
    if not m:
        return None
    h, mm = int(m.group(1)), int(m.group(2))
    if not (0 <= h < 24 and 0 <= mm < 60):
        return None
    return h * 60 + mm


def find_in_memory(memory_dir: Path, keyword: str) -> list[Path]:
    """Search memory/*.md for files containing keyword. Case-insensitive."""
    if not memory_dir.exists():
        return []
    out = []
    kw = keyword.lower()
    for p in memory_dir.rglob("*.md"):
        try:
            if kw in p.read_text().lower():
                out.append(p)
        except OSError:
            continue
    return out
