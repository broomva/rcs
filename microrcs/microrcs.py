"""microRCS — single-file recursive controlled system baseline with LLM controllers.

Empirically validates the RCS thesis on real LLM reasoning across four hierarchical
levels (L0 plant + L1 autonomic + L2 meta-control + L3 governance), measuring
empirical stability margins λ̂ᵢ from Lyapunov decay traces and comparing them to
the paper's analytic values in `../data/parameters.toml`.

Run:
    pip install anthropic numpy matplotlib
    export ANTHROPIC_API_KEY=...
    python microrcs.py run --quick

See README.md and `docs/superpowers/specs/2026-05-01-microrcs-llm-baseline-design.md`.
"""

from __future__ import annotations

# === 1. Imports + module config ==============================================
import argparse
import base64
import enum
import hashlib
import io
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import tomllib
import uuid
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np

try:
    import anthropic
except ImportError:  # pragma: no cover — anthropic only needed for live runs
    anthropic = None

# Pricing (USD per 1M tokens): (input, output, cache_read, cache_create)
_PRICING: dict[str, tuple[float, float, float, float]] = {
    "claude-haiku-4-5":  (1.0,  5.0,  0.1,  1.25),
    "claude-sonnet-4-6": (3.0, 15.0,  0.3,  3.75),
    "claude-opus-4-7":  (15.0, 75.0,  1.5, 18.75),
    "mock":              (0.0,  0.0,  0.0,  0.0),
}

PARAMS_PATH = Path(__file__).resolve().parents[1] / "data" / "parameters.toml"


# === 2. Reasoner protocol + types ============================================
@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: Any  # str for plain; list[dict] for tool/thinking blocks


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class ReasoningRequest:
    messages: tuple[Message, ...]
    system: str = ""
    tools: tuple[ToolDef, ...] = ()
    max_tokens: int = 4096
    temperature: float = 1.0
    thinking_budget: int = 0
    cache_breakpoints: tuple[int, ...] = ()
    model: str = ""


@dataclass
class TokenUsage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_create: int = 0

    def cost_usd(self, model: str) -> float:
        # Anthropic returns date-pinned model strings (e.g. "claude-haiku-4-5-20251001").
        # Look up by exact match first, then by longest matching prefix.
        prices = _PRICING.get(model)
        if prices is None:
            best_key = ""
            for k in _PRICING:
                if model.startswith(k) and len(k) > len(best_key):
                    best_key = k
            prices = _PRICING.get(best_key, (0.0, 0.0, 0.0, 0.0))
        i, o, cr, cc = prices
        return (
            self.input * i
            + self.output * o
            + self.cache_read * cr
            + self.cache_create * cc
        ) / 1e6


@dataclass
class ReasoningResponse:
    text: str
    tool_calls: tuple[ToolCall, ...]
    thinking: str
    stop_reason: str
    usage: TokenUsage
    latency_ms: float
    model: str
    raw: Any = None


@runtime_checkable
class Reasoner(Protocol):
    def reason(self, req: ReasoningRequest) -> ReasoningResponse: ...


# === 3. AnthropicReasoner (full implementation) ==============================
class AnthropicReasoner:
    """Anthropic implementation of the Reasoner Protocol.

    Features: prompt caching, extended thinking, tool use, retries with
    exponential backoff + jitter, token/cost/latency accounting.
    """

    def __init__(
        self,
        client: Any | None = None,
        default_model: str = "claude-haiku-4-5",
        max_retries: int = 3,
        retry_base_seconds: float = 1.0,
    ):
        if client is None:
            if anthropic is None:
                raise ImportError("anthropic package not installed. pip install anthropic")
            client = anthropic.Anthropic()
        self.client = client
        self.default_model = default_model
        self.max_retries = max_retries
        self.retry_base = retry_base_seconds

    def reason(self, req: ReasoningRequest) -> ReasoningResponse:
        params = self._build_params(req)
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                t0 = time.perf_counter()
                raw = self.client.messages.create(**params)
                latency_ms = (time.perf_counter() - t0) * 1000
                return self._normalize(raw, latency_ms, params["model"])
            except Exception as e:  # pragma: no cover — needs network
                last_exc = e
                if anthropic is not None and isinstance(e, anthropic.RateLimitError):
                    self._backoff(attempt)
                    continue
                if anthropic is not None and isinstance(e, anthropic.APIStatusError):
                    code = getattr(e, "status_code", None)
                    if code in (500, 502, 503, 504):
                        self._backoff(attempt)
                        continue
                    if code == 400 and "context" in str(e).lower():
                        raise ContextLengthError(str(e)) from e
                    raise
                raise
        raise TransientError(
            f"max_retries={self.max_retries} exhausted; last={last_exc!r}"
        )

    def _build_params(self, req: ReasoningRequest) -> dict:
        model = req.model or self.default_model
        params: dict = {
            "model": model,
            "max_tokens": req.max_tokens,
            "messages": [self._serialize_message(m, i, req.cache_breakpoints)
                         for i, m in enumerate(req.messages)],
        }
        if req.system:
            if req.cache_breakpoints and -1 in req.cache_breakpoints:
                params["system"] = [{"type": "text", "text": req.system,
                                     "cache_control": {"type": "ephemeral"}}]
            else:
                params["system"] = req.system
        if req.tools:
            params["tools"] = [{"name": t.name, "description": t.description,
                                "input_schema": t.input_schema} for t in req.tools]
        if req.thinking_budget > 0:
            params["thinking"] = {"type": "enabled", "budget_tokens": req.thinking_budget}
            params["temperature"] = 1.0  # required when thinking enabled
        else:
            params["temperature"] = req.temperature
        return params

    def _serialize_message(self, m: Message, idx: int,
                           cache_breakpoints: tuple[int, ...]) -> dict:
        out: dict = {"role": m.role}
        content = m.content
        if isinstance(content, str):
            if idx in cache_breakpoints:
                out["content"] = [{"type": "text", "text": content,
                                   "cache_control": {"type": "ephemeral"}}]
            else:
                out["content"] = content
        else:
            out["content"] = list(content)
        return out

    def _normalize(self, raw: Any, latency_ms: float, model: str) -> ReasoningResponse:
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in getattr(raw, "content", []):
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(getattr(block, "text", ""))
            elif btype == "thinking":
                thinking_parts.append(getattr(block, "thinking", ""))
            elif btype == "tool_use":
                tool_calls.append(ToolCall(
                    id=getattr(block, "id", ""),
                    name=getattr(block, "name", ""),
                    arguments=dict(getattr(block, "input", {}) or {}),
                ))
        usage_obj = getattr(raw, "usage", None)
        usage = TokenUsage(
            input=getattr(usage_obj, "input_tokens", 0) or 0,
            output=getattr(usage_obj, "output_tokens", 0) or 0,
            cache_read=getattr(usage_obj, "cache_read_input_tokens", 0) or 0,
            cache_create=getattr(usage_obj, "cache_creation_input_tokens", 0) or 0,
        )
        return ReasoningResponse(
            text="\n".join(text_parts),
            tool_calls=tuple(tool_calls),
            thinking="\n".join(thinking_parts),
            stop_reason=getattr(raw, "stop_reason", "end_turn") or "end_turn",
            usage=usage,
            latency_ms=latency_ms,
            model=getattr(raw, "model", model) or model,
            raw=raw,
        )

    def _backoff(self, attempt: int) -> None:
        time.sleep(self.retry_base * (2 ** attempt) + random.uniform(0, self.retry_base))


# === 4. OpenAI / Ollama Reasoner stubs =======================================
class OpenAIReasoner:
    def __init__(self, **kwargs: Any) -> None:
        self._kwargs = kwargs

    def reason(self, req: ReasoningRequest) -> ReasoningResponse:
        raise NotImplementedError(
            "OpenAIReasoner is a V1 stub. Use AnthropicReasoner for V0."
        )


class OllamaReasoner:
    def __init__(self, **kwargs: Any) -> None:
        self._kwargs = kwargs

    def reason(self, req: ReasoningRequest) -> ReasoningResponse:
        raise NotImplementedError("OllamaReasoner is a V1 stub.")


def make_reasoner(model: str, **kwargs: Any) -> Reasoner:
    """Factory: 'anthropic:claude-...', 'openai:...', 'ollama:...', or bare 'claude-...'."""
    provider, name = model.split(":", 1) if ":" in model else ("anthropic", model)
    cls = {
        "anthropic": AnthropicReasoner,
        "openai": OpenAIReasoner,
        "ollama": OllamaReasoner,
    }.get(provider)
    if cls is None:
        raise ValueError(f"Unknown provider: {provider}")
    return cls(default_model=name, **kwargs)


# === 5. Typed errors =========================================================
class ReasoningError(Exception):
    """Base for all reasoning-layer errors."""


class RateLimitError(ReasoningError):
    """Provider rate-limited the request."""


class ContextLengthError(ReasoningError):
    """Request exceeds context window."""


class ContentPolicyError(ReasoningError):
    """Provider blocked the request on content policy."""


class TransientError(ReasoningError):
    """Retries exhausted; transient failure."""


# === 6. Action types (typed unions per level) ================================

# --- L0 actions ---
@dataclass(frozen=True)
class BashAction:
    command: str
    timeout_seconds: int = 30


@dataclass(frozen=True)
class SubmitAction:
    answer: str


@dataclass(frozen=True)
class NoOp:
    reason: str = ""


# --- L1 actions ---
class AgentMode(enum.Enum):
    BASE = "base"
    COT = "cot"
    SCRATCHPAD = "scratchpad"
    VERIFY = "verify"


# Concrete L0 behavior per mode. L1 mode-switching now produces measurable change,
# not just a label. Fragments are appended to the L0 system prompt by _mode_fragment().
MODE_FRAGMENTS: dict[AgentMode, str] = {}
MODE_FRAGMENTS.update({
    AgentMode.BASE: "",
    AgentMode.COT: (
        "Before calling submit(), write your step-by-step reasoning to "
        "scratch/reasoning.md. Submit only after you have written it."
    ),
    AgentMode.SCRATCHPAD: (
        "You MUST run at least one bash command to compute or verify the answer "
        "(e.g., `python3 -c '...'` or write/run a small script in scratch/) "
        "before calling submit()."
    ),
    AgentMode.VERIFY: (
        "After deriving an answer, derive it a second way (e.g., reverse the "
        "calculation, check constraints, run an alternative method). "
        "Submit only if both derivations agree; otherwise iterate."
    ),
})


@dataclass(frozen=True)
class ModeSwitch:
    target_mode: AgentMode
    reason: str


@dataclass(frozen=True)
class Retry:
    max_retries: int
    reason: str


@dataclass(frozen=True)
class Abort:
    reason: str


# --- L2 actions ---
@dataclass(frozen=True)
class PromoteHelper:
    path: str
    new_content: str
    rationale: str


@dataclass(frozen=True)
class PromoteMemory:
    path: str
    new_status: Literal["draft", "canonical"]
    rationale: str


@dataclass(frozen=True)
class AppendSystemRule:
    rule: str
    rationale: str


@dataclass(frozen=True)
class MergeMemory:
    paths: tuple[str, ...]
    merged_path: str
    rationale: str


# --- L3 actions ---
@dataclass(frozen=True)
class UpdateCap:
    target_level: int
    field: str
    new_value: Any
    reason: str


@dataclass(frozen=True)
class UpdateSchema:
    schema_diff: dict
    reason: str


@dataclass
class Decision:
    """The output of any controller — the U input for the level below."""
    action: Any
    rationale: str = ""
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)


# === 6b. Hook pipeline (Noesis-inspired veto chain) ==========================
@dataclass
class HookContext:
    """Snapshot passed to a hook. Hooks are pure functions over this."""
    level: int
    state: Any
    action: Any
    log: "EventLog"
    metadata: dict = field(default_factory=dict)


@dataclass
class HookResult:
    """Hook return value: pass-through, modified action, or veto with reason."""
    decision: Decision
    veto: bool = False
    veto_reason: str = ""


# A Hook is a pure function from context to result. Composable and testable.
# Type alias rather than Protocol because hooks are typically tiny closures.
Hook = Any  # Callable[[HookContext], HookResult] — kept loose to avoid import gymnastics


def run_hooks_chain(
    hooks: list[Hook],
    initial: Decision,
    state: Any,
    level: int,
    log: "EventLog",
) -> Decision:
    """Run hooks in order. Each may modify the action or veto. First veto wins.

    Vetoed actions become NoOp(reason=veto_reason) and emit a SHIELD event for
    visibility. This is the Noesis pattern: composable safety filters above the
    controller's built-in shield(), enabling shadow-evaluation, coherence checks,
    and other pre-commit validations without touching controller internals.
    """
    current = initial
    for hook in hooks:
        ctx = HookContext(level=level, state=state, action=current.action, log=log)
        try:
            result = hook(ctx)
        except Exception as exc:  # noqa: BLE001 — hooks must not crash the loop
            log.append(RCSEvent(
                new_event_id(), None, time.time(), level,
                EventKind.SHIELD, "hook_error",
                {"hook": getattr(hook, "__name__", repr(hook)),
                 "error": f"{type(exc).__name__}: {exc}"},
            ))
            continue
        if result.veto:
            log.append(RCSEvent(
                new_event_id(), None, time.time(), level,
                EventKind.SHIELD, "hook_veto",
                {"hook": getattr(hook, "__name__", repr(hook)),
                 "reason": result.veto_reason,
                 "blocked_action_type": type(current.action).__name__},
            ))
            return Decision(
                action=NoOp(reason=f"hook_veto:{result.veto_reason}"[:200]),
                rationale=current.rationale,
                metadata={**current.metadata, "vetoed_by": getattr(hook, "__name__", "?")},
            )
        current = result.decision
    return current


# === 7. RCSEvent + EventKind + EventLog ======================================
class EventKind(enum.Enum):
    OBSERVE = "observe"
    DECIDE = "decide"
    SHIELD = "shield"
    STEP = "step"
    LYAPUNOV = "lyapunov"
    REASONER_CALL = "reasoner_call"
    PARAM_CHANGE = "param_change"
    BREAKER = "breaker"


@dataclass(frozen=True)
class RCSEvent:
    event_id: str
    parent_id: str | None
    timestamp: float
    level: int
    kind: EventKind
    correlation_id: str
    payload: dict


def new_event_id() -> str:
    """Sortable, globally unique event id. Timestamp-prefixed UUID4 (poor man's ULID)."""
    return f"{int(time.time() * 1000):013x}-{uuid.uuid4().hex[:8]}"


class EventLog:
    """Append-only event log persisted as JSONL. The single source of truth for lineage."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[RCSEvent] = []
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        for line in self.path.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            d["kind"] = EventKind(d["kind"])
            self._events.append(RCSEvent(**d))

    def append(self, ev: RCSEvent) -> None:
        self._events.append(ev)
        with self.path.open("a") as f:
            d = {
                "event_id": ev.event_id,
                "parent_id": ev.parent_id,
                "timestamp": ev.timestamp,
                "level": ev.level,
                "kind": ev.kind.value,
                "correlation_id": ev.correlation_id,
                "payload": ev.payload,
            }
            f.write(json.dumps(d, default=str) + "\n")

    def filter(self, *, level: int | None = None, kind: EventKind | None = None,
               correlation_id: str | None = None) -> Iterator[RCSEvent]:
        for e in self._events:
            if level is not None and e.level != level:
                continue
            if kind is not None and e.kind != kind:
                continue
            if correlation_id is not None and e.correlation_id != correlation_id:
                continue
            yield e

    def trace(self, event_id: str) -> list[RCSEvent]:
        """Walk parent_id back to root. Returns events in causal order (root first)."""
        by_id = {e.event_id: e for e in self._events}
        chain: list[RCSEvent] = []
        cur: RCSEvent | None = by_id.get(event_id)
        while cur is not None:
            chain.append(cur)
            cur = by_id.get(cur.parent_id) if cur.parent_id else None
        return list(reversed(chain))


# === 8. Workspace + frontmatter parser =======================================
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-ish frontmatter. Returns (fields, body).

    Supports: scalar strings/ints/floats, list literals (single line),
    booleans, status values. No nested objects.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if len(lines) < 2:
        return {}, text
    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end < 0:
        return {}, text
    fm: dict = {}
    for ln in lines[1:end]:
        if ":" not in ln:
            continue
        k, _, v = ln.partition(":")
        k, v = k.strip(), v.strip()
        if not k:
            continue
        fm[k] = _coerce_value(v)
    body = "\n".join(lines[end + 1:]).lstrip("\n")
    return fm, body


def _coerce_value(v: str) -> Any:
    if v == "":
        return ""
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",")]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v.strip("'\"")


def render_frontmatter(fm: dict, body: str) -> str:
    """Render a frontmatter dict + body back to markdown."""
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            inner = ", ".join(repr(x) if isinstance(x, str) else str(x) for x in v)
            lines.append(f"{k}: [{inner}]")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body.lstrip("\n"))
    return "\n".join(lines)


def diff_snapshots(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    """Compute diff of two workspace snapshots."""
    bk, ak = set(before.keys()), set(after.keys())
    return {
        "added": sorted(ak - bk),
        "removed": sorted(bk - ak),
        "modified": sorted(p for p in (bk & ak) if before[p] != after[p]),
    }


_STARTER_HELPERS_PATH = Path(__file__).parent / "helpers" / "starter.py"
_STARTER_HELPERS_README = Path(__file__).parent / "helpers" / "README.md"
_STARTER_MEMORY_README = Path(__file__).parent / "memory" / "README.md"


@dataclass
class Workspace:
    path: Path
    run_id: str

    @classmethod
    def create(cls, path: Path | str, run_id: str) -> "Workspace":
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        for sub in ("helpers", "memory/concept", "memory/pattern", "memory/task",
                    "scratch", ".rcs"):
            (p / sub).mkdir(parents=True, exist_ok=True)
        # Copy starter helpers + READMEs (best-effort; missing source ok)
        if _STARTER_HELPERS_PATH.exists():
            (p / "helpers" / "starter.py").write_text(_STARTER_HELPERS_PATH.read_text())
        if _STARTER_HELPERS_README.exists():
            (p / "helpers" / "README.md").write_text(_STARTER_HELPERS_README.read_text())
        if _STARTER_MEMORY_README.exists():
            (p / "memory" / "README.md").write_text(_STARTER_MEMORY_README.read_text())
        return cls(path=p, run_id=run_id)

    def snapshot(self) -> dict[str, str]:
        """Return {relative_path: sha256} for helpers/ and memory/."""
        snap: dict[str, str] = {}
        for sub in ("helpers", "memory"):
            base = self.path / sub
            if not base.is_dir():
                continue
            for f in base.rglob("*"):
                if f.is_file() and not f.name.startswith("."):
                    rel = str(f.relative_to(self.path))
                    snap[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
        return snap


# === 9. CadenceGate + parameters loader ======================================
@dataclass
class CadenceGate:
    """Discrete-time analog of dwell-time τ_a from the paper.

    `last_fired = -inf` by default so the first call always fires.
    """
    min_interval_seconds: float
    last_fired: float = -math.inf

    def can_fire(self, now: float) -> bool:
        return (now - self.last_fired) >= self.min_interval_seconds

    def mark_fired(self, now: float) -> None:
        self.last_fired = now


def load_canonical_lambdas() -> dict[str, float]:
    """Read derived.lambda from `data/parameters.toml`."""
    with PARAMS_PATH.open("rb") as f:
        d = tomllib.load(f)
    return d.get("derived", {}).get("lambda", {})


def load_canonical_tau_a() -> dict[str, float]:
    """Read tau_a per level from `data/parameters.toml`."""
    with PARAMS_PATH.open("rb") as f:
        d = tomllib.load(f)
    return {lvl["id"]: lvl["tau_a"] for lvl in d.get("levels", [])}


# === 10. L0Plant — the bitter-lesson agent loop ==============================
@dataclass
class Caps:
    max_steps: int = 20
    max_cost_usd: float = 0.50
    max_workspace_bytes: int = 100 * 1024 * 1024
    per_command_timeout_seconds: int = 30
    max_tokens_per_call: int = 4096
    model: str = "claude-haiku-4-5"
    allowed_tools: tuple[str, ...] = ("bash", "submit")


@dataclass
class Task:
    id: str
    domain: str
    prompt: str
    verify: Any  # Callable[[str], float] returning {0.0, 1.0}
    metadata: dict = field(default_factory=dict)


@dataclass
class EpisodeTrace:
    task_id: str
    messages: list
    final_answer: str | None
    score: float
    aborted_reason: str | None
    cost_usd: float
    n_steps: int
    workspace_diff: dict


def _l0_lyapunov(cost: float, step: int, score: float, caps: "Caps") -> float:
    """Continuous V₀ ∈ [0, 1] combining capacity usage + correctness gap.

    V₀ = 0.3·(cost/budget) + 0.3·(step/max_steps) + 0.4·(1 − score)

    Continuous so the linear regression on log(V) for λ̂_0 is well-defined.
    All three terms are clamped to [0, 1] before summing.
    """
    cost_frac = min(cost / max(caps.max_cost_usd, 1e-9), 1.0)
    step_frac = min(step / max(caps.max_steps, 1), 1.0)
    return 0.3 * cost_frac + 0.3 * step_frac + 0.4 * (1.0 - score)


L0_SYSTEM_PROMPT = """\
You are an agent in a workspace. Your tools are `bash` and `submit`.

ENVIRONMENT
  cwd: {cwd}
  helpers/   - Python utilities you may use, edit, or extend.
  scratch/   - Ephemeral, wiped between tasks. Write working files here.

TASK
  See the user message.
{memory_section}{mode_fragment}{rules_addendum}
Submit your final answer with submit() when done.
"""


def _mode_fragment(mode: "AgentMode") -> str:
    frag = MODE_FRAGMENTS.get(mode, "")
    return f"\nMODE: {mode.value} — {frag}\n" if frag else ""


def _memory_section(memory_invitation: bool, has_entries: bool) -> str:
    """Memory invitation only appears when invited (L2-injected) or pre-populated.

    Default: no memory instructions (avoids forcing the agent to do unnecessary
    documentation on simple tasks — bitter-lesson alignment).
    """
    if not memory_invitation and not has_entries:
        return ""
    if has_entries and not memory_invitation:
        return ("\nMEMORY\n  memory/ contains durable knowledge from past tasks. "
                "Search it (e.g. `grep -rl <kw> memory/`) before reasoning from scratch.\n")
    return ("\nMEMORY\n  memory/ is your knowledge graph. Read existing entries; "
            "add new ones with frontmatter (see memory/README.md) when you discover "
            "something durable that future tasks could reuse.\n")


class L0Plant:
    """The agent. Solves a single Task by acting on bash + submit until done.

    This IS the f₀ dynamics function — fully transparent so L1 can observe it.
    """

    def __init__(
        self,
        reasoner: Reasoner,
        workspace: Workspace,
        log: EventLog,
        caps: Caps,
        mode: AgentMode | None = None,
        system_rules: list[str] | None = None,
        memory_invitation: bool = False,
    ):
        self.reasoner = reasoner
        self.workspace = workspace
        self.log = log
        self.caps = caps
        self.mode = mode or AgentMode.BASE
        self.system_rules: list[str] = list(system_rules or [])
        # Off by default — bitter-lesson aligned. L2 may flip it on as a rule when warranted.
        self.memory_invitation = memory_invitation

    def _has_memory_entries(self) -> bool:
        try:
            return any(
                p.is_file() and p.suffix == ".md" and p.name not in ("README.md", "SCHEMA.md")
                for p in (self.workspace.path / "memory").rglob("*.md")
            )
        except OSError:
            return False

    def run_episode(self, task: Task) -> EpisodeTrace:
        cid = f"ep_{new_event_id()}"
        snap_before = self.workspace.snapshot()
        (self.workspace.path / "TASK.md").write_text(task.prompt)
        rules = ""
        if self.system_rules:
            rules = "\nRULES YOU'VE LEARNED\n" + "\n".join(f"  - {r}" for r in self.system_rules) + "\n"
        sys_prompt = L0_SYSTEM_PROMPT.format(
            cwd=str(self.workspace.path),
            memory_section=_memory_section(self.memory_invitation, self._has_memory_entries()),
            mode_fragment=_mode_fragment(self.mode),
            rules_addendum=rules,
        )

        messages: list[dict] = [{"role": "user", "content": task.prompt}]
        cost = 0.0
        recent_actions: deque[str] = deque(maxlen=3)
        nudged = False

        for step in range(self.caps.max_steps):
            if cost >= self.caps.max_cost_usd:
                return self._abort(task, messages, cid, "cost_budget", cost, step, snap_before)

            tools = (
                ToolDef(
                    name="bash",
                    description=(
                        "Execute a shell command in the workspace. cwd is your "
                        "workspace dir. stdout/stderr is your observation."
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "timeout_seconds": {"type": "integer", "default": 30},
                        },
                        "required": ["command"],
                    },
                ),
                ToolDef(
                    name="submit",
                    description="Submit your final answer. Call exactly once when done.",
                    input_schema={
                        "type": "object",
                        "properties": {"answer": {"type": "string"}},
                        "required": ["answer"],
                    },
                ),
            )
            req_msgs = tuple(Message(role=m["role"], content=m["content"]) for m in messages)
            req = ReasoningRequest(
                messages=req_msgs, system=sys_prompt, tools=tools,
                max_tokens=self.caps.max_tokens_per_call, model=self.caps.model,
            )
            obs_event = RCSEvent(
                new_event_id(), None, time.time(), 0, EventKind.OBSERVE, cid,
                {"step": step, "n_messages": len(messages)},
            )
            self.log.append(obs_event)

            try:
                resp = self.reasoner.reason(req)
            except ContextLengthError as e:
                return self._abort(task, messages, cid, f"context_length: {e}",
                                   cost, step, snap_before)

            cost += resp.usage.cost_usd(resp.model)
            self.log.append(RCSEvent(
                new_event_id(), obs_event.event_id, time.time(), 0,
                EventKind.REASONER_CALL, cid,
                {"latency_ms": resp.latency_ms, "cost": cost,
                 "stop_reason": resp.stop_reason,
                 "input_tokens": resp.usage.input,
                 "output_tokens": resp.usage.output},
            ))

            assistant_blocks: list[dict] = []
            if resp.text:
                assistant_blocks.append({"type": "text", "text": resp.text})
            for tc in resp.tool_calls:
                assistant_blocks.append({
                    "type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments,
                })
            messages.append({
                "role": "assistant",
                "content": assistant_blocks if assistant_blocks else (resp.text or ""),
            })

            if not resp.tool_calls:
                if nudged:
                    return self._abort(task, messages, cid, "no_action", cost, step, snap_before)
                nudged = True
                messages.append({
                    "role": "user",
                    "content": "Please respond with a tool call (bash or submit).",
                })
                continue

            for tc in resp.tool_calls:
                dec_event = RCSEvent(
                    new_event_id(), obs_event.event_id, time.time(), 0,
                    EventKind.DECIDE, cid,
                    {"tool": tc.name, "arguments": tc.arguments},
                )
                self.log.append(dec_event)
                action = self._make_action(tc)
                shielded = self._shield(action, cost)
                self.log.append(RCSEvent(
                    new_event_id(), dec_event.event_id, time.time(), 0,
                    EventKind.SHIELD, cid,
                    {"action_type": type(shielded).__name__, "reason": getattr(shielded, "reason", "")},
                ))

                if isinstance(shielded, SubmitAction):
                    score = float(task.verify(shielded.answer))
                    snap_after = self.workspace.snapshot()
                    diff = diff_snapshots(snap_before, snap_after)
                    self.log.append(RCSEvent(
                        new_event_id(), dec_event.event_id, time.time(), 0,
                        EventKind.STEP, cid, {"submitted": True, "score": score},
                    ))
                    v0 = _l0_lyapunov(cost, step + 1, score, self.caps)
                    self.log.append(RCSEvent(
                        new_event_id(), None, time.time(), 0,
                        EventKind.LYAPUNOV, cid,
                        {"V": v0, "score": score, "cost": cost, "step": step + 1},
                    ))
                    return EpisodeTrace(
                        task.id, messages, shielded.answer, score, None,
                        cost, step + 1, diff,
                    )

                if isinstance(shielded, NoOp):
                    obs = f"Action blocked: {shielded.reason}"
                    is_error = True
                elif isinstance(shielded, BashAction):
                    obs, is_error = self._run_bash(shielded)
                else:
                    obs = f"Unknown action {type(shielded).__name__}"
                    is_error = True

                messages.append({"role": "user", "content": [{
                    "type": "tool_result", "tool_use_id": tc.id,
                    "content": obs, "is_error": is_error,
                }]})
                self.log.append(RCSEvent(
                    new_event_id(), dec_event.event_id, time.time(), 0,
                    EventKind.STEP, cid,
                    {"action_type": type(shielded).__name__,
                     "is_error": is_error, "obs_len": len(obs)},
                ))
                recent_actions.append(self._action_hash(shielded))

            if len(recent_actions) == 3 and len(set(recent_actions)) == 1:
                return self._abort(task, messages, cid, "repeat_loop_detected",
                                   cost, step, snap_before)

        return self._abort(task, messages, cid, "step_budget",
                           cost, self.caps.max_steps, snap_before)

    def _make_action(self, tc: ToolCall):
        if tc.name == "bash":
            return BashAction(
                command=tc.arguments.get("command", ""),
                timeout_seconds=int(tc.arguments.get(
                    "timeout_seconds", self.caps.per_command_timeout_seconds)),
            )
        if tc.name == "submit":
            return SubmitAction(answer=str(tc.arguments.get("answer", "")))
        return NoOp(reason=f"unknown_tool:{tc.name}")

    def _shield(self, dec: Any, cost: float) -> Any:
        if cost >= self.caps.max_cost_usd:
            return NoOp(reason="cost_cap_exceeded")
        if isinstance(dec, BashAction):
            if "bash" not in self.caps.allowed_tools:
                return NoOp(reason="tool_not_whitelisted")
            return BashAction(
                command=dec.command,
                timeout_seconds=min(dec.timeout_seconds, self.caps.per_command_timeout_seconds),
            )
        if isinstance(dec, SubmitAction) and "submit" not in self.caps.allowed_tools:
            return NoOp(reason="submit_not_whitelisted")
        return dec

    def _run_bash(self, act: BashAction) -> tuple[str, bool]:
        try:
            r = subprocess.run(
                act.command, shell=True, cwd=str(self.workspace.path),
                capture_output=True, text=True, timeout=act.timeout_seconds,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "HOME": str(self.workspace.path),
                    "LANG": "C.UTF-8",
                    "PYTHONPATH": str(self.workspace.path),
                },
            )
            out = (r.stdout + r.stderr).strip()
            if len(out) > 8000:
                out = out[:4000] + "\n...[truncated]...\n" + out[-2000:]
            return out, r.returncode != 0
        except subprocess.TimeoutExpired:
            return f"command timed out after {act.timeout_seconds}s", True
        except Exception as e:
            return f"{type(e).__name__}: {e}", True

    def _action_hash(self, act: Any) -> str:
        return hashlib.sha256(repr(act).encode()).hexdigest()[:16]

    def _abort(self, task: Task, messages: list, cid: str, reason: str,
               cost: float, step: int, snap_before: dict) -> EpisodeTrace:
        snap_after = self.workspace.snapshot()
        diff = diff_snapshots(snap_before, snap_after)
        v0 = _l0_lyapunov(cost, step, 0.0, self.caps)
        self.log.append(RCSEvent(
            new_event_id(), None, time.time(), 0,
            EventKind.LYAPUNOV, cid,
            {"V": v0, "score": 0.0, "cost": cost, "step": step, "aborted": reason},
        ))
        return EpisodeTrace(task.id, messages, None, 0.0, reason, cost, step, diff)


# === 11. L1Autonomic — homeostatic gating ====================================
@dataclass
class HysteresisThreshold:
    low: float
    high: float


@dataclass
class HomeostaticState:
    rolling_fail_rate: float
    rolling_latency_ms: float
    rolling_cost_usd: float
    current_mode: AgentMode = AgentMode.BASE
    memory_mutation_rate: float = 0.0


class L1Autonomic:
    """Watches L0 outcome history. Gates retry vs mode-switch vs abort."""

    def __init__(
        self,
        reasoner: Reasoner,
        log: EventLog,
        threshold: HysteresisThreshold,
        dwell_seconds: float = 30.0,
        window_size: int = 5,
    ):
        self.reasoner = reasoner
        self.log = log
        self.threshold = threshold
        self.dwell_seconds = dwell_seconds
        self.window_size = window_size
        self.last_switch_t = 0.0

    def observe(self, history: list[RCSEvent]) -> HomeostaticState:
        l0_lyap = [e for e in history
                   if e.level == 0 and e.kind == EventKind.LYAPUNOV][-self.window_size:]
        fail_rate = (
            float(np.mean([e.payload.get("V", 1.0) for e in l0_lyap]))
            if l0_lyap else 0.0
        )
        latencies = [e.payload.get("latency_ms", 0.0) for e in history
                     if e.kind == EventKind.REASONER_CALL][-self.window_size * 4:]
        avg_lat = float(np.mean(latencies)) if latencies else 0.0
        param_changes_recent = [e for e in history
                                if e.kind == EventKind.PARAM_CHANGE][-10:]
        mut_rate = len(param_changes_recent) / max(1.0, len(history))
        return HomeostaticState(
            rolling_fail_rate=fail_rate, rolling_latency_ms=avg_lat,
            rolling_cost_usd=0.0, memory_mutation_rate=mut_rate,
        )

    def decide(self, obs: HomeostaticState) -> Decision:
        prompt = (
            f"Rolling fail rate (V₁): {obs.rolling_fail_rate:.3f}\n"
            f"Current mode: {obs.current_mode.value}\n"
            f"Avg latency ms: {obs.rolling_latency_ms:.0f}\n"
            f"Memory mutation rate: {obs.memory_mutation_rate:.3f}\n\n"
            f"Pick exactly ONE: base | cot | scratchpad | verify | retry | abort | noop\n"
            f"Reply with the word, then a brief reason. No other text."
        )
        try:
            resp = self.reasoner.reason(ReasoningRequest(
                messages=(Message("user", prompt),), max_tokens=80, model="claude-haiku-4-5",
            ))
            txt = resp.text or ""
        except Exception:
            txt = "noop default"
        return self._parse_decision(txt)

    def _parse_decision(self, text: str) -> Decision:
        first = text.strip().split()[0].lower() if text.strip() else "noop"
        first = first.strip(".:,")
        if first in ("base", "cot", "scratchpad", "verify"):
            return Decision(
                action=ModeSwitch(target_mode=AgentMode(first), reason=text[:200]),
                rationale=text,
            )
        if first == "retry":
            return Decision(action=Retry(max_retries=2, reason=text[:200]), rationale=text)
        if first == "abort":
            return Decision(action=Abort(reason=text[:200]), rationale=text)
        return Decision(action=NoOp(reason="unparsed_or_noop"), rationale=text)

    def shield(self, dec: Decision, state: HomeostaticState) -> Decision:
        if isinstance(dec.action, ModeSwitch):
            if (time.time() - self.last_switch_t) < self.dwell_seconds:
                return Decision(
                    action=NoOp(reason="dwell_time_active"), rationale=dec.rationale,
                )
        return dec

    def lyapunov(self, state: HomeostaticState) -> float:
        return state.rolling_fail_rate ** 2 + state.memory_mutation_rate ** 2


# === 12. L2Meta — strategy mutator ===========================================
@dataclass
class FailureSummary:
    """Compact view of a single L0 episode failure for L2 to reason over."""
    task_id: str
    domain: str
    score: float
    aborted_reason: str | None
    n_steps: int
    submitted_answer: str | None


@dataclass
class MetaState:
    l1_decisions: list
    l1_lyapunov_trend: float
    helper_diffs: list
    memory_snapshot: dict
    epoch: int = 0
    recent_failures: list = field(default_factory=list)

    @classmethod
    def from_log(cls, log: EventLog, epoch: int = 0,
                 recent_failures: list | None = None) -> "MetaState":
        l1_decs = [e for e in log.filter(level=1, kind=EventKind.DECIDE)]
        l0_lyap = list(log.filter(level=0, kind=EventKind.LYAPUNOV))
        if len(l0_lyap) >= 4:
            ts = np.array([e.timestamp for e in l0_lyap])
            vs = np.array([e.payload.get("V", 1.0) for e in l0_lyap])
            ts = ts - ts[0]
            slope, _ = np.polyfit(ts, vs, 1)
            trend = float(slope)
        else:
            trend = 0.0
        return cls(l1_decisions=l1_decs, l1_lyapunov_trend=trend,
                    helper_diffs=[], memory_snapshot={}, epoch=epoch,
                    recent_failures=list(recent_failures or []))


class L2Meta:
    """Watches L1 history. Proposes mutations to L0's prompt template, helpers, memory.

    `hooks` is an optional list of post-shield validators (Noesis-pattern). The
    canonical use case is a shadow-eval hook that tests a candidate mutation
    on a small task set before commit, vetoing if it doesn't measurably help.
    """

    def __init__(self, reasoner: Reasoner, log: EventLog,
                 mutation_budget: int = 5,
                 hooks: list[Hook] | None = None):
        self.reasoner = reasoner
        self.log = log
        self.mutation_budget = mutation_budget
        self.mutations_this_epoch = 0
        self.accepted_mutations: list = []
        self.hooks: list[Hook] = list(hooks or [])

    def run_hooks(self, dec: Decision, state: Any) -> Decision:
        """Apply registered post-shield hooks. See `run_hooks_chain` docstring."""
        if not self.hooks:
            return dec
        return run_hooks_chain(self.hooks, dec, state, level=2, log=self.log)

    def observe(self, history: list[RCSEvent]) -> "MetaState":
        return MetaState.from_log(self.log)

    def decide(self, state: "MetaState") -> Decision:
        if state.l1_lyapunov_trend < -0.001 and not state.recent_failures:
            return Decision(action=NoOp(reason="V₁ already decaying, no failures"),
                              rationale="ok")
        # Build a compact failure-context block. Previous version gave L2 only
        # metrics, no idea WHAT was failing — so its rules were generic
        # platitudes. Now L2 sees the actual failure pattern.
        if state.recent_failures:
            fails_block = "RECENT L0 FAILURES (last few):\n"
            for f in state.recent_failures[-5:]:
                ans = (f.submitted_answer or "")[:80]
                if f.aborted_reason:
                    fails_block += (
                        f"  - [{f.domain}/{f.task_id}] aborted: {f.aborted_reason} "
                        f"after {f.n_steps} steps\n"
                    )
                else:
                    fails_block += (
                        f"  - [{f.domain}/{f.task_id}] wrong: submitted {ans!r} "
                        f"in {f.n_steps} steps\n"
                    )
        else:
            fails_block = "RECENT L0 FAILURES: none\n"

        prompt = (
            f"You are the L2 meta-controller of a recursive agent system. "
            f"L0 is the agent solving tasks; L1 gates retries/mode. Your job: "
            f"propose ONE small mutation that addresses a recurring failure pattern.\n\n"
            f"{fails_block}\n"
            f"L1 Lyapunov trend (slope of V₁): {state.l1_lyapunov_trend:+.4f}  "
            f"(positive = L0 not improving)\n"
            f"L1 decisions this epoch: {len(state.l1_decisions)}\n"
            f"Past accepted mutations: {len(self.accepted_mutations)}/"
            f"{self.mutation_budget}\n\n"
            "Action grammar (pick exactly one, single line):\n"
            "  RULE: When <trigger>, <action>.\n"
            "    — append an actionable rule to L0's system prompt\n"
            "    — must be specific and address a failure mode above\n"
            "  HELPER <relative/path.py>=<python source>\n"
            "    — promote a helper module (e.g. helpers/parse_logic.py=def parse(...): ...)\n"
            "  PROMOTE_MEMORY <relative/path.md>=<canonical|draft>\n"
            "  NOOP\n\n"
            "Prefer NOOP if no failures or no clear pattern. Avoid generic "
            "rules like 'be careful' — they hurt more than help.\n"
            "Reply with exactly one action on a single line."
        )
        try:
            resp = self.reasoner.reason(ReasoningRequest(
                messages=(Message("user", prompt),), max_tokens=300,
                model="claude-sonnet-4-6",
            ))
            txt = (resp.text or "").strip()
        except Exception:
            txt = "NOOP default"
        return self._parse_decision(txt)

    def _parse_decision(self, text: str) -> Decision:
        first_line = text.strip().split("\n", 1)[0]
        upper = first_line.upper()
        if upper.startswith("RULE:") or upper.startswith("RULE "):
            sep_idx = first_line.find(":") if upper.startswith("RULE:") else 4
            rule_text = first_line[sep_idx + 1:].strip().strip("'\"")[:300]
            if len(rule_text) < 10 or rule_text.lower() in (
                "be careful", "verify", "be precise", "think step by step",
            ):
                return Decision(action=NoOp(reason="rule_too_generic"),
                                  rationale=text)
            return Decision(
                action=AppendSystemRule(rule=rule_text,
                                          rationale=text[:300]),
                rationale=text,
            )
        if upper.startswith("HELPER "):
            rest = first_line[7:]
            path, _, content = rest.partition("=")
            return Decision(
                action=PromoteHelper(path=path.strip()[:120],
                                      new_content=content.strip()[:2000],
                                      rationale=text[:300]),
                rationale=text,
            )
        if upper.startswith("PROMOTE_MEMORY "):
            rest = first_line[len("PROMOTE_MEMORY "):]
            path, _, status = rest.partition("=")
            status = status.strip()
            if status not in ("canonical", "draft"):
                status = "canonical"
            return Decision(
                action=PromoteMemory(path=path.strip()[:120], new_status=status,
                                      rationale=text[:300]),
                rationale=text,
            )
        return Decision(action=NoOp(reason="unparsed_or_noop"), rationale=text)

    def shield(self, dec: Decision, state: "MetaState") -> Decision:
        if self.mutations_this_epoch >= self.mutation_budget:
            return Decision(
                action=NoOp(reason="mutation_budget_exhausted"),
                rationale=dec.rationale,
            )
        a = dec.action
        if isinstance(a, PromoteHelper):
            unsafe = ("rm -rf", "subprocess", "os.system", "eval(input")
            if any(u in a.new_content for u in unsafe):
                return Decision(
                    action=NoOp(reason="safety_field_protected"),
                    rationale=dec.rationale,
                )
        return dec

    def lyapunov(self, state: "MetaState") -> float:
        # V₂ = max(0, -dV₁/dt)² — bigger when V₁ is NOT decaying
        positive_slope = max(0.0, state.l1_lyapunov_trend)
        return positive_slope ** 2


# --- Shadow-evaluation hook for L2 (EGRI selector pattern) -------------------
@dataclass
class ShadowEvalConfig:
    """Configures the shadow-evaluation hook for L2 mutations.

    Default thresholds: 2 trials × 3 tasks = 6 shadow episodes per mutation
    candidate. At Haiku rates that's ~$0.20-0.40 per candidate.

    threshold_delta=2.0: shadow must beat baseline by ≥2 trials out of 6.
    A 1-trial improvement at n=6 is within sampling variance (temperature=1.0)
    and produces false positives — the live PR #23 run showed all 3 candidate
    rules accepted at delta=1, accumulated, and degraded `full` to 0.935. With
    delta=2 the threshold is ~33% relative improvement, well above noise floor.
    """
    enabled: bool = True
    n_eval_tasks: int = 3       # at most this many tasks per shadow eval
    n_trials_per_task: int = 2  # repeats per task for noise robustness
    threshold_delta: float = 2.0  # require ≥2 trial improvement vs baseline
    max_steps_per_shadow: int = 10
    max_cost_usd_per_shadow: float = 0.10


def _select_shadow_tasks(
    state: "MetaState", suite: list["Task"], n_eval: int,
) -> list["Task"]:
    """Pick tasks to shadow-evaluate the mutation against.

    Strategy: at most 2 recent failure tasks (the rule should fix what it
    claimed to fix) + at most 1 healthy task (rule must not regress healthy
    behavior). Truncates to `n_eval`.
    """
    suite_by_id = {t.id: t for t in suite}
    failed_ids: list[str] = []
    for f in state.recent_failures[-5:]:
        if f.task_id in suite_by_id and f.task_id not in failed_ids:
            failed_ids.append(f.task_id)
    failed = [suite_by_id[i] for i in failed_ids[:2]]
    healthy = [t for t in suite if t.id not in failed_ids][:max(0, n_eval - len(failed))]
    return (failed + healthy)[:n_eval]


def _baseline_pass_count(
    state: "MetaState", eval_tasks: list["Task"], n_trials: int,
) -> int:
    """Baseline successes across the eval tasks from `recent_failures` evidence.

    A failed episode contributes 0; the absence of recent failure for that
    task implies it has been passing — contributes n_trials per missing task.
    Lower bound on the true baseline (we count present-failures fully against,
    absent-tasks fully for). The shadow needs to clearly beat this floor.
    """
    failed_by_task: dict[str, int] = {}
    for f in state.recent_failures[-20:]:
        failed_by_task[f.task_id] = failed_by_task.get(f.task_id, 0) + 1
    total_passes = 0
    for t in eval_tasks:
        # If we've seen recent failures for this task, count them; cap at n_trials
        fails = min(failed_by_task.get(t.id, 0), n_trials)
        total_passes += (n_trials - fails)
    return total_passes


def make_shadow_eval_hook(
    config: ShadowEvalConfig,
    plant_template: "L0Plant",
    suite: list["Task"],
    workspace_root: Path,
) -> Hook:
    """Build a hook that shadow-evaluates AppendSystemRule / PromoteHelper actions.

    The hook is a closure capturing the eval config + read-only references to
    the plant template + suite. Each invocation:
      1. Skips NoOps and non-mutation actions.
      2. Builds an isolated shadow `Workspace` that mirrors helpers/ + memory/.
      3. Spawns a shadow `L0Plant` with the candidate mutation applied.
      4. Runs n_trials × n_eval_tasks shadow episodes (cheap caps).
      5. Vetoes the mutation if shadow pass-count <= baseline + threshold_delta.

    Cost: ≤ n_eval_tasks × n_trials_per_task × max_cost_usd_per_shadow per call.
    With defaults: 3 × 2 × $0.10 = $0.60 per shadow invocation worst-case.
    """
    def shadow_eval_hook(ctx: HookContext) -> HookResult:
        action = ctx.action
        # Pass-through for non-mutating actions
        if not config.enabled or isinstance(action, (NoOp, Retry, Abort)):
            return HookResult(decision=Decision(action=action,
                                                 rationale="shadow_eval:skip"))
        if not isinstance(action, (AppendSystemRule, PromoteHelper)):
            return HookResult(decision=Decision(action=action,
                                                 rationale="shadow_eval:not-applicable"))
        state = ctx.state
        if not isinstance(state, MetaState) or not state.recent_failures:
            # No evidence to evaluate against — let it pass (the mutation
            # budget shield still bounds rate; absent failures we trust L2).
            return HookResult(decision=Decision(action=action,
                                                 rationale="shadow_eval:no-failures"))

        eval_tasks = _select_shadow_tasks(state, suite, config.n_eval_tasks)
        if not eval_tasks:
            return HookResult(decision=Decision(action=action,
                                                 rationale="shadow_eval:no-tasks"))
        n_trials = config.n_trials_per_task

        # Build an isolated shadow workspace (sibling of the real one)
        shadow_root = workspace_root / f"shadow-{new_event_id()}"
        shadow_ws = Workspace.create(shadow_root, run_id=plant_template.workspace.run_id)
        # Mirror helpers/ + memory/ from the real workspace before applying mutation
        for sub in ("helpers", "memory"):
            src = plant_template.workspace.path / sub
            if src.is_dir():
                for f in src.rglob("*"):
                    if f.is_file():
                        rel = f.relative_to(src)
                        dst = shadow_ws.path / sub / rel
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(f.read_bytes())

        # Apply the candidate mutation in the shadow workspace ONLY
        shadow_rules = list(plant_template.system_rules)
        if isinstance(action, AppendSystemRule):
            shadow_rules.append(action.rule)
        elif isinstance(action, PromoteHelper):
            target = shadow_ws.path / action.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(action.new_content)

        # Tight caps for shadow episodes
        shadow_caps = Caps(
            max_steps=config.max_steps_per_shadow,
            max_cost_usd=config.max_cost_usd_per_shadow,
            model=plant_template.caps.model,
            allowed_tools=plant_template.caps.allowed_tools,
        )
        # Separate event log so shadow events don't pollute the main run.
        shadow_log = EventLog(shadow_ws.path / ".rcs" / "events.jsonl")
        shadow_plant = L0Plant(
            reasoner=plant_template.reasoner,
            workspace=shadow_ws, log=shadow_log,
            caps=shadow_caps, system_rules=shadow_rules,
            memory_invitation=plant_template.memory_invitation,
        )

        shadow_passes = 0
        shadow_total_cost = 0.0
        for task in eval_tasks:
            for _ in range(n_trials):
                trace = shadow_plant.run_episode(task)
                shadow_total_cost += trace.cost_usd
                if trace.score >= 1.0:
                    shadow_passes += 1

        baseline = _baseline_pass_count(state, eval_tasks, n_trials)
        passed = shadow_passes >= (baseline + config.threshold_delta)

        ctx.log.append(RCSEvent(
            new_event_id(), None, time.time(), 2,
            EventKind.SHIELD, "shadow_eval",
            {
                "n_eval_tasks": len(eval_tasks),
                "n_trials_per_task": n_trials,
                "shadow_passes": shadow_passes,
                "baseline_passes": baseline,
                "threshold_delta": config.threshold_delta,
                "decision": "accept" if passed else "veto",
                "shadow_cost_usd": round(shadow_total_cost, 4),
                "action_type": type(action).__name__,
            },
        ))
        if passed:
            return HookResult(decision=Decision(action=action,
                                                 rationale=f"shadow_eval:{shadow_passes}/{n_trials*len(eval_tasks)} > baseline {baseline}"))
        return HookResult(
            decision=Decision(action=action),
            veto=True,
            veto_reason=f"shadow_eval failed: {shadow_passes}/{n_trials*len(eval_tasks)} ≤ baseline {baseline} + {config.threshold_delta}",
        )

    shadow_eval_hook.__name__ = "shadow_eval_hook"
    return shadow_eval_hook


# === 13. L3Governance — policy gate ==========================================
@dataclass
class GovernancePolicy:
    mutation_budget_l2: int = 5
    dwell_seconds_l1: float = 30.0
    max_steps_l0: int = 20
    max_cost_usd_l0: float = 0.50


@dataclass
class GovernanceState:
    mutation_rate: float
    mutation_drift: float
    policy_age: float
    current_policy: GovernancePolicy
    memory_size: int = 0

    @classmethod
    def from_log(cls, log: EventLog, policy: GovernancePolicy | None = None) -> "GovernanceState":
        l2 = list(log.filter(level=2, kind=EventKind.DECIDE))
        if len(l2) < 2:
            mut_rate = 0.0
        else:
            duration = max(1.0, l2[-1].timestamp - l2[0].timestamp)
            mut_rate = len(l2) / (duration / 60)  # mutations/minute
        return cls(
            mutation_rate=mut_rate, mutation_drift=0.0,
            policy_age=0.0, current_policy=policy or GovernancePolicy(),
        )


MIN_POLICY_INTERVAL = 60.0  # seconds — at most one policy change per minute


class L3Governance:
    """Watches L2 mutation history. Tightens or loosens caps. Rare, deliberate."""

    def __init__(self, reasoner: Reasoner, log: EventLog):
        self.reasoner = reasoner
        self.log = log
        self.last_change_t = 0.0
        self.policy = GovernancePolicy()

    def _should_fire(self, log_or_state: Any) -> bool:
        if isinstance(log_or_state, EventLog):
            l2 = list(log_or_state.filter(level=2, kind=EventKind.DECIDE))
            return len(l2) >= 3 and (time.time() - self.last_change_t) > MIN_POLICY_INTERVAL
        return True

    def observe(self, history: list[RCSEvent]) -> GovernanceState:
        return GovernanceState.from_log(self.log, self.policy)

    def decide(self, state: GovernanceState) -> Decision:
        prompt = (
            f"L2 mutation rate: {state.mutation_rate:.3f} mut/min\n"
            f"Current policy: budget={state.current_policy.mutation_budget_l2} "
            f"dwell={state.current_policy.dwell_seconds_l1}\n\n"
            "Pick ONE:\n"
            "  TIGHTEN_BUDGET <n>   — lower L2 mutation budget to n\n"
            "  LOOSEN_BUDGET <n>    — raise L2 mutation budget to n\n"
            "  NOOP\n\n"
            "Reply on one line."
        )
        try:
            resp = self.reasoner.reason(ReasoningRequest(
                messages=(Message("user", prompt),), max_tokens=80,
                model="claude-sonnet-4-6",
            ))
            txt = (resp.text or "").strip()
        except Exception:
            txt = "NOOP default"
        return self._parse_decision(txt)

    def _parse_decision(self, text: str) -> Decision:
        first = text.strip().split("\n", 1)[0]
        upper = first.upper()
        if upper.startswith("TIGHTEN_BUDGET ") or upper.startswith("LOOSEN_BUDGET "):
            parts = first.split(maxsplit=1)
            if len(parts) >= 2:
                try:
                    n = int(re.sub(r"[^\d-]", "", parts[1]))
                    return Decision(
                        action=UpdateCap(target_level=2, field="mutation_budget",
                                          new_value=n, reason=text[:200]),
                        rationale=text,
                    )
                except ValueError:
                    pass
        return Decision(action=NoOp(reason="unparsed_or_noop"), rationale=text)

    def shield(self, dec: Decision, state: GovernanceState) -> Decision:
        if isinstance(dec.action, UpdateCap):
            if (time.time() - self.last_change_t) < MIN_POLICY_INTERVAL:
                return Decision(
                    action=NoOp(reason="policy_cooldown"), rationale=dec.rationale,
                )
            # Safety floor: don't disable the budget entirely
            if dec.action.field == "mutation_budget" and dec.action.new_value < 1:
                return Decision(
                    action=NoOp(reason="safety_floor_protected"),
                    rationale=dec.rationale,
                )
        return dec

    def lyapunov(self, state: GovernanceState) -> float:
        return (state.mutation_rate - 0.5) ** 2  # setpoint = 0.5 mut/min


# === 14. apply_decision_downward — single mutation point =====================
def apply_decision_downward(
    level: int, dec: Decision, plant: L0Plant | None,
    l1: L1Autonomic | None, l2: L2Meta | None, log: EventLog,
) -> None:
    """The ONLY place state mutates. Every change emits PARAM_CHANGE."""
    parent = log._events[-1].event_id if log._events else None
    a = dec.action
    cid = "control"
    now = time.time()

    if isinstance(a, ModeSwitch):
        if plant is not None:
            old = plant.mode
            plant.mode = a.target_mode
            if l1 is not None:
                l1.last_switch_t = now
            log.append(RCSEvent(
                new_event_id(), parent, now, level, EventKind.PARAM_CHANGE, cid,
                {"target_level": 0, "field": "mode", "old": old.value,
                 "new": a.target_mode.value, "reason": a.reason},
            ))
    elif isinstance(a, AppendSystemRule):
        if plant is not None:
            plant.system_rules.append(a.rule)
            if l2 is not None:
                l2.mutations_this_epoch += 1
                l2.accepted_mutations.append(a)
            log.append(RCSEvent(
                new_event_id(), parent, now, level, EventKind.PARAM_CHANGE, cid,
                {"target_level": 0, "field": "system_rules", "added": a.rule,
                 "rationale": a.rationale},
            ))
    elif isinstance(a, PromoteHelper):
        if plant is not None:
            target = plant.workspace.path / a.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(a.new_content)
            if l2 is not None:
                l2.mutations_this_epoch += 1
                l2.accepted_mutations.append(a)
            log.append(RCSEvent(
                new_event_id(), parent, now, level, EventKind.PARAM_CHANGE, cid,
                {"target_level": 0, "field": a.path, "rationale": a.rationale},
            ))
    elif isinstance(a, PromoteMemory):
        if plant is not None:
            target = plant.workspace.path / a.path
            if target.exists():
                fm, body = parse_frontmatter(target.read_text())
                fm["status"] = a.new_status
                target.write_text(render_frontmatter(fm, body))
                if l2 is not None:
                    l2.mutations_this_epoch += 1
                log.append(RCSEvent(
                    new_event_id(), parent, now, level, EventKind.PARAM_CHANGE, cid,
                    {"target_level": 0, "field": f"memory:{a.path}",
                     "new_status": a.new_status, "rationale": a.rationale},
                ))
    elif isinstance(a, MergeMemory):
        if plant is not None:
            bodies: list[str] = []
            for p in a.paths:
                t = plant.workspace.path / p
                if t.exists():
                    _, body = parse_frontmatter(t.read_text())
                    bodies.append(body)
                    t.unlink()
            (plant.workspace.path / a.merged_path).write_text(
                render_frontmatter(
                    {"name": Path(a.merged_path).stem, "type": "concept",
                     "score": 8, "status": "canonical"},
                    "\n\n".join(bodies),
                )
            )
    elif isinstance(a, UpdateCap):
        target_level = a.target_level
        if target_level == 0 and plant is not None and hasattr(plant.caps, a.field):
            old = getattr(plant.caps, a.field)
            setattr(plant.caps, a.field, a.new_value)
            log.append(RCSEvent(
                new_event_id(), parent, now, level, EventKind.PARAM_CHANGE, cid,
                {"target_level": 0, "field": a.field, "old": str(old),
                 "new": str(a.new_value), "reason": a.reason},
            ))
        elif target_level == 1 and l1 is not None and hasattr(l1, a.field):
            old = getattr(l1, a.field)
            setattr(l1, a.field, a.new_value)
            log.append(RCSEvent(
                new_event_id(), parent, now, level, EventKind.PARAM_CHANGE, cid,
                {"target_level": 1, "field": a.field, "old": str(old),
                 "new": str(a.new_value), "reason": a.reason},
            ))
        elif target_level == 2 and l2 is not None and hasattr(l2, a.field):
            old = getattr(l2, a.field)
            setattr(l2, a.field, a.new_value)
            log.append(RCSEvent(
                new_event_id(), parent, now, level, EventKind.PARAM_CHANGE, cid,
                {"target_level": 2, "field": a.field, "old": str(old),
                 "new": str(a.new_value), "reason": a.reason},
            ))
    elif isinstance(a, UpdateSchema):
        if plant is not None:
            schema_path = plant.workspace.path / "memory" / "SCHEMA.md"
            schema_path.write_text(
                "\n".join(f"{k}: {v}" for k, v in a.schema_diff.items())
            )
            log.append(RCSEvent(
                new_event_id(), parent, now, level, EventKind.PARAM_CHANGE, cid,
                {"target_level": 2, "field": "schema",
                 "diff": a.schema_diff, "reason": a.reason},
            ))
    # NoOp / Retry / Abort — no state mutation


def _emit_lyapunov(log: EventLog, level: int, controller: Any, state: Any,
                    correlation_id: str = "control") -> float:
    """Compute V_k(state) via controller.lyapunov() and emit a LYAPUNOV event.

    Centralized so every level emits the same shape, and so the run loop
    has a single point to hook for instrumentation. Returns the V value
    that was emitted for caller convenience.
    """
    try:
        v = float(controller.lyapunov(state))
    except Exception:  # noqa: BLE001 — defensive: lyapunov fns shouldn't raise
        v = float("nan")
    if not math.isnan(v):
        log.append(RCSEvent(
            new_event_id(), None, time.time(), level,
            EventKind.LYAPUNOV, correlation_id, {"V": v},
        ))
    return v


# === 15. REFERENCE_SUITE + verifiers =========================================
def _verify_approx_time(target: str, tolerance_minutes: int):
    target_minutes = _hhmm_to_minutes(target)

    def fn(answer: str) -> float:
        if target_minutes is None:
            return 0.0
        m = re.search(r"(\d{1,2}):(\d{2})", answer or "")
        if not m:
            return 0.0
        h, mm = int(m.group(1)), int(m.group(2))
        if not (0 <= h < 24 and 0 <= mm < 60):
            return 0.0
        ans_minutes = h * 60 + mm
        return 1.0 if abs(ans_minutes - target_minutes) <= tolerance_minutes else 0.0
    return fn


def _hhmm_to_minutes(s: str) -> int | None:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s.strip())
    if not m:
        return None
    h, mm = int(m.group(1)), int(m.group(2))
    if not (0 <= h < 24 and 0 <= mm < 60):
        return None
    return h * 60 + mm


def _verify_python_assertions(answer: str) -> float:
    """Try to define `fizzbuzz` from answer; run the canonical asserts."""
    if not answer:
        return 0.0
    try:
        ns: dict = {}
        exec(answer, ns, ns)  # noqa: S102 — guarded eval, eval'd code must define fizzbuzz
        fb = ns.get("fizzbuzz")
        if fb is None:
            return 0.0
        if fb(15) != "FizzBuzz":
            return 0.0
        r7 = fb(7)
        if r7 != "7" and r7 != 7:
            return 0.0
        if fb(0) != "FizzBuzz":
            return 0.0
        return 1.0
    except Exception:
        return 0.0


def _make_normalize_match(target: str):
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower())

    def fn(answer: str) -> float:
        return 1.0 if norm(answer or "") == norm(target) else 0.0
    return fn


def _make_assignment_verifier(expected: dict[str, str]):
    """Verify person→item mappings tolerantly across phrasings.

    Accepts answers like:
      'Alice: water, Bob: coffee, Carol: tea'
      'alice has water; bob = coffee; carol = tea'
      'Alice ordered water. Bob ordered coffee. Carol ordered tea.'

    Extracts (name → item) pairs case-insensitively from the answer and
    checks all expected mappings are present.
    """
    expected_norm = {k.lower(): v.lower() for k, v in expected.items()}
    items_pattern = "|".join(re.escape(v) for v in set(expected_norm.values()))
    names_pattern = "|".join(re.escape(k) for k in expected_norm)

    def fn(answer: str) -> float:
        if not answer:
            return 0.0
        text = answer.lower()
        # Patterns: "<name> ... <item>" with various separators within ~40 chars
        found: dict[str, str] = {}
        for m in re.finditer(
            rf"({names_pattern})\s*[:=]?\s*[\w\s]{{0,40}}?\b({items_pattern})",
            text,
        ):
            name, item = m.group(1), m.group(2)
            if name not in found:
                found[name] = item
        return 1.0 if found == expected_norm else 0.0

    return fn


_DECL_AND_CONST_SIGNERS = (
    "franklin", "sherman", "morris", "wilson", "clymer", "fitzsimons", "read",
)


def _verify_qa_yes_with_two_names(answer: str) -> float:
    a = (answer or "").lower()
    if not a:
        return 0.0
    if "no" in a.split() and "yes" not in a.split():
        return 0.0
    if not ("yes" in a or "indeed" in a or "they did" in a):
        return 0.0
    matched = sum(1 for name in _DECL_AND_CONST_SIGNERS if name in a)
    return 1.0 if matched >= 2 else 0.0


def _verify_hanoi_sequence(answer: str) -> float:
    """Validate a Tower-of-Hanoi move sequence: A→C with 4 disks via B."""
    if not answer:
        return 0.0
    pegs: dict[str, list[int]] = {"A": [4, 3, 2, 1], "B": [], "C": []}
    moves = re.findall(r"([ABC])\s*->\s*([ABC])", answer)
    if not moves:
        return 0.0
    for src, dst in moves:
        if src == dst or not pegs[src]:
            return 0.0
        d = pegs[src][-1]
        if pegs[dst] and pegs[dst][-1] < d:
            return 0.0
        pegs[src].pop()
        pegs[dst].append(d)
    return 1.0 if pegs["C"] == [4, 3, 2, 1] and not pegs["A"] and not pegs["B"] else 0.0


REFERENCE_SUITE: list[Task] = [
    Task(
        id="math-multi-step",
        domain="math",
        prompt=(
            "A train leaves Town A at 9:47 going 73 mph toward Town B. "
            "A second train leaves Town B at 11:23 going 81 mph toward Town A. "
            "The towns are 412 miles apart. "
            "At what time do they meet? Answer as HH:MM (24h)."
        ),
        # Correct answer: 13:18.
        # Derivation: at 11:23, T1 has covered 73·(11:23−9:47) ≈ 116.83 mi.
        # Remaining gap 295.17 mi closes at 73+81 = 154 mph in 1h54.99 min.
        # Meeting time = 11:23 + 1:54:59 = 13:17:59 ≈ 13:18.
        verify=_verify_approx_time("13:18", tolerance_minutes=4),
    ),
    Task(
        id="code-bugfix",
        domain="code",
        prompt=(
            "Define a Python function `fizzbuzz(n)` that satisfies all of these:\n"
            "  fizzbuzz(15) == 'FizzBuzz'\n"
            "  fizzbuzz(7)  == '7'    (note: STRING, not int)\n"
            "  fizzbuzz(0)  == 'FizzBuzz'\n"
            "Submit the complete `def fizzbuzz(n): ...` source code."
        ),
        verify=_verify_python_assertions,
    ),
    Task(
        id="logic-zebra",
        domain="logic",
        prompt=(
            "Three friends each ordered a different drink (one each, no repeats) "
            "from {coffee, tea, water}. Use these clues:\n"
            "  - Alice did not order coffee.\n"
            "  - Bob ordered the alphabetically-first drink in the set (i.e., coffee).\n"
            "  - Carol did not order water.\n"
            "Who ordered what? State each person's drink in your answer."
        ),
        # Solution: Alice=water (only remaining for her), Bob=coffee (given),
        # Carol=tea (not water, coffee taken).
        verify=_make_assignment_verifier(
            {"Alice": "water", "Bob": "coffee", "Carol": "tea"},
        ),
    ),
    Task(
        id="closed-book-qa",
        domain="qa",
        prompt=(
            "Did the same person sign both the United States Declaration of "
            "Independence and the United States Constitution? "
            "Answer yes or no, and name two such people if yes."
        ),
        verify=_verify_qa_yes_with_two_names,
    ),
    Task(
        id="planning-hanoi",
        domain="planning",
        prompt=(
            "Solve Tower of Hanoi for 4 disks moving from peg A to peg C using peg B "
            "as auxiliary. Output one move per line as 'A->B' or 'B->C' etc. "
            "Submit only the moves, one per line, no other text."
        ),
        verify=_verify_hanoi_sequence,
    ),
]


# --- Numeric verifier for harder math tasks ---------------------------------
def _verify_numeric(expected: float, tolerance: float = 0.01):
    """Extract the last numeric token from the answer; compare with tolerance.
    Uses an epsilon (1e-9) to absorb float-precision boundary effects."""
    def fn(answer: str) -> float:
        if not answer:
            return 0.0
        nums = re.findall(r"-?\d+(?:\.\d+)?", answer.replace(",", ""))
        if not nums:
            return 0.0
        try:
            diff = abs(float(nums[-1]) - expected)
            return 1.0 if diff <= tolerance + 1e-9 else 0.0
        except ValueError:
            return 0.0
    return fn


def _verify_integer_in_range(expected: int):
    """Strict integer match — expected value must appear as an int token."""
    def fn(answer: str) -> float:
        if not answer:
            return 0.0
        ints = [int(n) for n in re.findall(r"-?\d+", answer.replace(",", ""))]
        return 1.0 if expected in ints else 0.0
    return fn


def _verify_5disk_hanoi(answer: str) -> float:
    """Validate 5-disk Hanoi solution: A→C with 5 disks via B."""
    if not answer:
        return 0.0
    pegs: dict[str, list[int]] = {"A": [5, 4, 3, 2, 1], "B": [], "C": []}
    moves = re.findall(r"([ABC])\s*->\s*([ABC])", answer)
    if not moves:
        return 0.0
    for src, dst in moves:
        if src == dst or not pegs[src]:
            return 0.0
        d = pegs[src][-1]
        if pegs[dst] and pegs[dst][-1] < d:
            return 0.0
        pegs[src].pop()
        pegs[dst].append(d)
    return 1.0 if pegs["C"] == [5, 4, 3, 2, 1] and not pegs["A"] and not pegs["B"] else 0.0


def _verify_n_queens_4(answer: str) -> float:
    """Validate a 4-queens solution. Accept any valid placement.

    Expected format: 4 numbers in 1..4, each in a different row/col with no
    two on same diagonal. Examples of valid answers:
      '2,4,1,3' or 'col 2, col 4, col 1, col 3'.
    """
    if not answer:
        return 0.0
    nums = [int(n) for n in re.findall(r"\d+", answer) if n.isdigit()]
    # First 4 numbers form the placement (col index per row)
    if len(nums) < 4:
        return 0.0
    placement = nums[:4]
    if any(c < 1 or c > 4 for c in placement):
        return 0.0
    if len(set(placement)) != 4:
        return 0.0  # columns must differ
    # No two queens on same diagonal: |r1-r2| != |c1-c2|
    for i in range(4):
        for j in range(i + 1, 4):
            if abs(i - j) == abs(placement[i] - placement[j]):
                return 0.0
    return 1.0


# Cross-suite verifiers (forward-declared so HARDER_SUITE below can reference them).
def _verify_bsearch_assertions(answer: str) -> float:
    if not answer:
        return 0.0
    try:
        ns: dict = {}
        exec(answer, ns, ns)  # noqa: S102 — guarded
        bs = ns.get("bsearch")
        if bs is None:
            return 0.0
        cases = [
            ([1, 3, 5, 7, 9], 5, 2),
            ([1, 3, 5, 7, 9], 1, 0),
            ([1, 3, 5, 7, 9], 9, 4),
            ([1, 3, 5, 7, 9], 4, -1),
            ([], 5, -1),
        ]
        for arr, target, expected in cases:
            if bs(arr, target) != expected:
                return 0.0
        return 1.0
    except Exception:
        return 0.0


def _verify_fib_assertions(answer: str) -> float:
    if not answer:
        return 0.0
    try:
        ns: dict = {}
        exec(answer, ns, ns)  # noqa: S102 — guarded
        fib = ns.get("fib")
        if fib is None:
            return 0.0
        for n, expected in [(0, 0), (1, 1), (10, 55), (20, 6765)]:
            if fib(n) != expected:
                return 0.0
        return 1.0
    except Exception:
        return 0.0


def _verify_qa_three_dual_role(answer: str) -> float:
    """Need any 3 names from the set of people who held both roles."""
    a = (answer or "").lower()
    if not a:
        return 0.0
    candidates = (
        "marshall", "hughes", "jackson", "taft", "chase", "day",
        "goldberg", "byrnes", "mcreynolds",
    )
    matched = sum(1 for c in candidates if c in a)
    return 1.0 if matched >= 3 else 0.0


# --- HARDER_SUITE: 10 problems calibrated to Haiku ~50% pass rate -----------
# Each problem chosen so the base model (Haiku) succeeds roughly half the time
# with no scaffolding, leaving headroom for L1/L2/L3 to demonstrate value.
# This is the suite where H1 (full > flat) becomes a real, testable claim.
HARDER_SUITE: list[Task] = [
    # Math: multi-step word problems with non-trivial arithmetic
    Task(
        id="harder-math-mixture",
        domain="math",
        prompt=(
            "A solution is 12% acid by volume. How many liters of pure water "
            "must be added to 8 liters of this solution to make it 5% acid? "
            "Answer with the number of liters (one number)."
        ),
        # 0.12 * 8 = 0.96 L acid; need 0.96 / 0.05 = 19.2 L total; add 11.2 L water.
        verify=_verify_numeric(11.2, tolerance=0.2),
    ),
    Task(
        id="harder-math-rate",
        domain="math",
        prompt=(
            "Three workers paint a wall together. Worker A alone takes 6 hours, "
            "Worker B alone takes 8 hours, Worker C alone takes 12 hours. "
            "How many hours do they take working together? Answer with one number."
        ),
        # Combined rate = 1/6 + 1/8 + 1/12 = 4/24 + 3/24 + 2/24 = 9/24 = 3/8 walls/hr
        # Time = 8/3 ≈ 2.67 hr.
        verify=_verify_numeric(8/3, tolerance=0.05),
    ),
    Task(
        id="harder-math-combinatorics",
        domain="math",
        prompt=(
            "How many distinct ways can you arrange the letters of MISSISSIPPI? "
            "Answer with the number."
        ),
        # 11! / (4! * 4! * 2!) = 39916800 / (24*24*2) = 34650
        verify=_verify_integer_in_range(34650),
    ),
    # Code: subtle bugs requiring careful reading
    Task(
        id="harder-code-binsearch",
        domain="code",
        prompt=(
            "Define a Python function `bsearch(arr, target)` that returns the index "
            "of `target` in the sorted list `arr`, or -1 if not found. It must satisfy:\n"
            "  bsearch([1,3,5,7,9], 5) == 2\n"
            "  bsearch([1,3,5,7,9], 1) == 0\n"
            "  bsearch([1,3,5,7,9], 9) == 4\n"
            "  bsearch([1,3,5,7,9], 4) == -1\n"
            "  bsearch([], 5) == -1\n"
            "Submit the complete function source."
        ),
        verify=_verify_bsearch_assertions,
    ),
    Task(
        id="harder-code-fibonacci",
        domain="code",
        prompt=(
            "Define a Python function `fib(n)` that returns the n-th Fibonacci number "
            "with fib(0)=0, fib(1)=1. It must satisfy:\n"
            "  fib(0) == 0\n"
            "  fib(1) == 1\n"
            "  fib(10) == 55\n"
            "  fib(20) == 6765\n"
            "Submit the complete function source."
        ),
        verify=_verify_fib_assertions,
    ),
    # Logic: 4-person constraint puzzles
    Task(
        id="harder-logic-houses",
        domain="logic",
        prompt=(
            "Four houses in a row (1=leftmost, 4=rightmost) painted red, blue, "
            "green, yellow (one each). Clues:\n"
            "  - The red house is immediately left of the blue house.\n"
            "  - The green house is at position 1 or 4.\n"
            "  - The yellow house is at position 2.\n"
            "What color is each house? List them in order from position 1 to 4."
        ),
        # Yellow=2. Red+Blue adjacent (red left). Possible: Red=3,Blue=4 (then 1=green).
        # Final: green, yellow, red, blue.
        verify=_make_assignment_verifier({
            "1": "green", "2": "yellow", "3": "red", "4": "blue",
        }),
    ),
    Task(
        id="harder-logic-meeting",
        domain="logic",
        prompt=(
            "Four people (Alex, Beth, Carl, Dana) meet on different days "
            "(Mon, Tue, Wed, Thu — one person per day). Constraints:\n"
            "  - Alex meets the day after Beth.\n"
            "  - Carl does not meet on Monday or Thursday.\n"
            "  - Dana meets on Monday.\n"
            "Who meets each day? State each person's day."
        ),
        # Dana=Mon. Carl ∉ {Mon,Thu} → Carl ∈ {Tue,Wed}. Alex = Beth+1 day.
        # If Beth=Tue then Alex=Wed → Carl=Thu (no, Carl ≠ Thu)... try Beth=Wed→Alex=Thu→Carl=Tue. ✓
        verify=_make_assignment_verifier({
            "Alex": "thursday", "Beth": "wednesday",
            "Carl": "tuesday", "Dana": "monday",
        }),
    ),
    # Closed-book QA: multi-fact synthesis
    Task(
        id="harder-qa-multifact",
        domain="qa",
        prompt=(
            "Name three distinct people who served as both a U.S. Supreme Court "
            "justice and a U.S. Cabinet Secretary (in any cabinet position) at "
            "different points in their careers. List all three names."
        ),
        verify=_verify_qa_three_dual_role,
    ),
    # Planning: bigger Hanoi, n-queens
    Task(
        id="harder-planning-hanoi5",
        domain="planning",
        prompt=(
            "Solve Tower of Hanoi for 5 disks from peg A to peg C using peg B. "
            "Output one move per line as 'A->B' or 'B->C' etc. "
            "Submit only the moves (no other text)."
        ),
        verify=_verify_5disk_hanoi,
    ),
    Task(
        id="harder-planning-queens4",
        domain="planning",
        prompt=(
            "Solve the 4-queens problem: place 4 queens on a 4x4 chessboard so "
            "no two attack each other. State the column (1..4) of the queen in "
            "each row, in order rows 1..4. Example format: '2,4,1,3'."
        ),
        verify=_verify_n_queens_4,
    ),
]


# === 16. Run loop with 4-condition ablation ==================================
@dataclass
class RunConfig:
    suite: list = field(default_factory=lambda: REFERENCE_SUITE)
    n_epochs: int = 3
    n_repeats: int = 3
    n_runs: int = 4
    max_steps_per_episode: int = 20
    max_cost_usd_per_episode: float = 0.50
    model_l0_l1: str = "claude-haiku-4-5"
    model_l2_l3: str = "claude-sonnet-4-6"
    workspace_root: Path = field(default_factory=lambda: Path("/tmp"))
    seed: int | None = None
    break_budgets: bool = False  # H4: force λ_2 < 0 by removing mutation budget
    # Shadow-evaluation config for L2 mutations (Noesis-pattern hook).
    # Default: enabled — L2 candidates must beat baseline on a small task set
    # before commit. The bad-mutation injection that hurt PR #22's `full`
    # condition is exactly what this prevents.
    shadow_eval: ShadowEvalConfig = field(default_factory=ShadowEvalConfig)


@dataclass
class RunResult:
    run_id: str
    config: RunConfig
    metrics: dict
    workspace_paths: dict
    report_path: Path | None = None


def _emit_progress(quiet: bool, message: str) -> None:
    """Per-episode progress to stderr. Goes to stderr (not stdout) so the
    headline JSON/HTML capture from stdout-redirected scripts stays clean.
    Gated by `quiet=True` so CI / batch scripts can suppress."""
    if not quiet:
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {message}", file=sys.stderr, flush=True)


def run(
    cfg: RunConfig,
    out_dir: Path | str,
    conditions: tuple[str, ...] = ("flat", "+autonomic", "+meta", "full"),
    quiet: bool = False,
) -> RunResult:
    if cfg.seed is not None:
        random.seed(cfg.seed)
        np.random.seed(cfg.seed)
    run_id = new_event_id()
    out_dir = Path(out_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    _emit_progress(quiet, f"run_id={run_id} conditions={list(conditions)} "
                            f"epochs={cfg.n_epochs} repeats={cfg.n_repeats} "
                            f"tasks={len(cfg.suite)}")
    metrics: dict = {}
    workspace_paths: dict = {}

    for cond in conditions:
        ws_path = cfg.workspace_root / f"microrcs-{run_id}-{cond.replace('+','plus_')}"
        ws = Workspace.create(ws_path, run_id)
        log = EventLog(ws.path / ".rcs" / "events.jsonl")

        l0_reasoner = make_reasoner(cfg.model_l0_l1)
        l1_reasoner = make_reasoner(cfg.model_l0_l1) if cond != "flat" else None
        l2_reasoner = make_reasoner(cfg.model_l2_l3) if cond in ("+meta", "full") else None
        l3_reasoner = make_reasoner(cfg.model_l2_l3) if cond == "full" else None

        plant = L0Plant(
            l0_reasoner, ws, log,
            Caps(max_steps=cfg.max_steps_per_episode,
                 max_cost_usd=cfg.max_cost_usd_per_episode,
                 model=cfg.model_l0_l1),
        )
        l1 = L1Autonomic(l1_reasoner, log, HysteresisThreshold(0.2, 0.6)) \
            if l1_reasoner is not None else None
        # Break budgets test (H4): infinite mutation budget
        l2_budget = 10**6 if cfg.break_budgets else 5
        # L2 hooks: shadow eval (PR #23) — gated on shadow_eval.enabled.
        # H4 mode disables shadow eval to allow free mutation flow (the whole
        # point is to demonstrate that without budget shields, λ_2 < 0).
        l2_hooks: list[Hook] = []
        if cfg.shadow_eval.enabled and not cfg.break_budgets:
            l2_hooks.append(make_shadow_eval_hook(
                cfg.shadow_eval, plant, cfg.suite,
                workspace_root=cfg.workspace_root,
            ))
        l2 = L2Meta(l2_reasoner, log,
                      mutation_budget=l2_budget, hooks=l2_hooks) \
            if l2_reasoner is not None else None
        l3 = L3Governance(l3_reasoner, log) if l3_reasoner is not None else None

        cond_results: dict = {"episodes": [], "lambda": {}}
        recent_failures: list[FailureSummary] = []
        _emit_progress(quiet, f"  ╭─ {cond} (workspace={ws.path.name})")

        for epoch in range(cfg.n_epochs):
            if l2 is not None:
                l2.mutations_this_epoch = 0
            for repeat in range(cfg.n_repeats):
                for task in cfg.suite:
                    trace = plant.run_episode(task)
                    cond_results["episodes"].append({
                        "task": task.id, "epoch": epoch, "repeat": repeat,
                        "score": trace.score, "aborted": trace.aborted_reason,
                        "cost": trace.cost_usd, "n_steps": trace.n_steps,
                    })
                    # Live per-episode signal: the most useful update granularity.
                    glyph = "✓" if trace.score >= 1.0 else (
                        "✗" if trace.aborted_reason else "·"
                    )
                    _emit_progress(quiet,
                        f"  │  {cond:<12} e{epoch}/r{repeat} "
                        f"{task.id:<20} {glyph} "
                        f"score={trace.score:.2f} steps={trace.n_steps:<2} "
                        f"${trace.cost_usd:.4f}"
                        + (f" abort={trace.aborted_reason}" if trace.aborted_reason else "")
                    )
                    if trace.score < 1.0:
                        recent_failures.append(FailureSummary(
                            task_id=task.id, domain=task.domain,
                            score=trace.score, aborted_reason=trace.aborted_reason,
                            n_steps=trace.n_steps,
                            submitted_answer=trace.final_answer,
                        ))
                        recent_failures = recent_failures[-20:]
                    if l1 is not None:
                        history = list(log._events)
                        obs = l1.observe(history)
                        dec = l1.decide(obs)
                        safe = l1.shield(dec, obs)
                        apply_decision_downward(1, safe, plant, l1, l2, log)
                        _emit_lyapunov(log, level=1, controller=l1, state=obs,
                                        correlation_id=f"task_{task.id}_e{epoch}_r{repeat}")
                        if isinstance(safe.action, ModeSwitch):
                            _emit_progress(quiet,
                                f"  │  {cond:<12} L1 mode → {safe.action.target_mode.value}")
            if l2 is not None:
                state = MetaState.from_log(log, epoch=epoch,
                                              recent_failures=recent_failures)
                dec = l2.decide(state)
                safe = l2.shield(dec, state)
                safe = l2.run_hooks(safe, state)
                apply_decision_downward(2, safe, plant, l1, l2, log)
                _emit_lyapunov(log, level=2, controller=l2, state=state,
                                correlation_id=f"epoch_{epoch}")
                action_name = type(safe.action).__name__
                _emit_progress(quiet,
                    f"  │  {cond:<12} L2 epoch {epoch} → {action_name}"
                    + (f" ({getattr(safe.action, 'reason', '')[:40]})"
                       if hasattr(safe.action, 'reason') else "")
                )
            if l3 is not None and l3._should_fire(log):
                state = GovernanceState.from_log(log)
                dec = l3.decide(state)
                safe = l3.shield(dec, state)
                if not isinstance(safe.action, NoOp):
                    l3.last_change_t = time.time()
                apply_decision_downward(3, safe, plant, l1, l2, log)
                _emit_lyapunov(log, level=3, controller=l3, state=state,
                                correlation_id=f"gov_e{epoch}")
                _emit_progress(quiet,
                    f"  │  {cond:<12} L3 fired → {type(safe.action).__name__}")
            # Even when L3 doesn't fire, sample its V over time so we get a
            # stream of L3 lyapunov samples for fitting (rare events otherwise
            # produce nan from LambdaMonitor).
            elif l3 is not None:
                state = GovernanceState.from_log(log)
                _emit_lyapunov(log, level=3, controller=l3, state=state,
                                correlation_id=f"gov_e{epoch}_passive")

        # Compute lambdas for all 4 levels
        for level in (0, 1, 2, 3):
            mon = LambdaMonitor(log, level)
            lam, std = mon.lambda_hat()
            cond_results["lambda"][f"L{level}"] = (
                None if math.isnan(lam) else float(lam),
                None if math.isnan(std) else float(std),
            )
        scores = [e["score"] for e in cond_results["episodes"]]
        if scores:
            cond_results["pass_pow_k"] = pass_pow_k(scores, k=3)
            cond_results["pass_at_k"] = pass_at_k(scores, k=3)
            cond_results["bootstrap_std"] = bootstrap_std(scores)
            cond_results["bootstrap_ci"] = bootstrap_ci(scores)
        else:
            cond_results.update({
                "pass_pow_k": 0.0, "pass_at_k": 0.0,
                "bootstrap_std": 0.0, "bootstrap_ci": (0.0, 0.0),
            })
        metrics[cond] = cond_results
        workspace_paths[cond] = str(ws.path)
        _emit_progress(quiet,
            f"  ╰─ {cond} done: pass^3={cond_results.get('pass_pow_k', 0):.3f}  "
            f"cost=${sum(e['cost'] for e in cond_results['episodes']):.4f}  "
            f"n={len(cond_results['episodes'])}"
        )

    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    paper_lams = load_canonical_lambdas() if PARAMS_PATH.exists() else {}
    (out_dir / "lambda_comparison.json").write_text(json.dumps({
        "paper": paper_lams,
        "measured": {c: r["lambda"] for c, r in metrics.items()},
    }, indent=2, default=str))
    return RunResult(
        run_id=run_id, config=cfg, metrics=metrics,
        workspace_paths=workspace_paths,
    )


# === 17. Statistics: pass_at_k, pass_pow_k, bootstrap ========================
from math import prod


def pass_at_k(scores: list[float], k: int) -> float:
    """Chen et al. unbiased estimator for pass@k. score >= 1.0 = pass."""
    n = len(scores)
    c = sum(1 for s in scores if s >= 1.0)
    if n - c < k:
        return 1.0
    return float(1.0 - prod((n - c - i) / (n - i) for i in range(k)))


def pass_pow_k(scores: list[float], k: int) -> float:
    """All-k-succeed: (mean pass rate)^k. The Lyapunov-stability proxy."""
    if not scores:
        return 0.0
    return float(np.mean([1.0 if s >= 1.0 else 0.0 for s in scores]) ** k)


def bootstrap_std(values: list[float], n_resamples: int = 1000) -> float:
    if len(values) < 2:
        return 0.0
    arr = np.asarray(values, dtype=float)
    means = [
        float(np.mean(np.random.choice(arr, len(arr), replace=True)))
        for _ in range(n_resamples)
    ]
    return float(np.std(means))


def bootstrap_ci(
    values: list[float], alpha: float = 0.05, n: int = 1000
) -> tuple[float, float]:
    if len(values) < 2:
        m = float(np.mean(values)) if values else 0.0
        return (m, m)
    arr = np.asarray(values, dtype=float)
    means = [
        float(np.mean(np.random.choice(arr, len(arr), replace=True)))
        for _ in range(n)
    ]
    lo = float(np.percentile(means, 100 * alpha / 2))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return (lo, hi)


# === 18. LambdaMonitor + StabilityCircuitBreaker =============================
class LambdaMonitor:
    """Polls the event log, fits exp(-λt) to V_k(t), reports (λ̂, std)."""

    def __init__(self, log: EventLog, level: int):
        self.log = log
        self.level = level

    def lambda_hat(self, window_seconds: float | None = None) -> tuple[float, float]:
        events = list(self.log.filter(level=self.level, kind=EventKind.LYAPUNOV))
        if window_seconds is not None:
            cutoff = time.time() - window_seconds
            events = [e for e in events if e.timestamp >= cutoff]
        if len(events) < 3:
            return float("nan"), float("nan")
        events.sort(key=lambda e: e.timestamp)
        ts = np.array([e.timestamp - events[0].timestamp for e in events])
        vs = np.array([
            max(float(e.payload.get("V", 1.0)), 1e-9) for e in events
        ])
        if len(set(vs.tolist())) == 1 or ts[-1] == 0:
            return 0.0, 0.0
        log_v = np.log(vs)
        try:
            slope, _ = np.polyfit(ts, log_v, 1)
        except (np.linalg.LinAlgError, ValueError):
            return float("nan"), float("nan")
        lam = float(-slope)
        n = len(ts)
        boots: list[float] = []
        for _ in range(200):
            idx = np.random.choice(n, n, replace=True)
            try:
                if len(set(ts[idx].tolist())) < 2:
                    continue
                s, _ = np.polyfit(ts[idx], log_v[idx], 1)
                boots.append(-s)
            except Exception:  # noqa: BLE001
                continue
        std = float(np.std(boots)) if boots else 0.0
        return lam, std


@dataclass
class BreakerAction:
    freeze_level: int
    reason: str


class StabilityCircuitBreaker:
    """Last-resort meta-shield: freezes L_{k+1} mutations if λ̂_k + 2σ < 0."""

    def __init__(self, monitors: dict[int, LambdaMonitor]):
        self.monitors = monitors

    def check(self, window_seconds: float = 300.0) -> list[BreakerAction]:
        out: list[BreakerAction] = []
        for level, mon in self.monitors.items():
            lam, std = mon.lambda_hat(window_seconds=window_seconds)
            if not math.isnan(lam) and (lam + 2 * std) < 0:
                out.append(BreakerAction(
                    freeze_level=level + 1,
                    reason=f"λ̂_{level} = {lam:.4f} ± {std:.4f} < 0 (2σ floor breached)",
                ))
        return out


# === 19. HTML report + matplotlib plots ======================================
def render_report(metrics: dict, out_html: Path) -> None:
    out_html = Path(out_html)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    figs: list = []
    for fn in (_plot_pass_pow_k, _plot_lambda_comparison, _plot_ablation_heatmap):
        try:
            fig = fn(metrics)
            if fig is not None:
                figs.append(fig)
        except Exception as e:  # noqa: BLE001
            print(f"plot {fn.__name__} failed: {e}", file=sys.stderr)
    encoded = [_fig_to_base64(f) for f in figs]
    out_html.write_text(_render_html_template(metrics, encoded))


def _plot_pass_pow_k(metrics: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 3.5))
    conds = list(metrics.keys())
    vals = [metrics[c].get("pass_pow_k", 0.0) for c in conds]
    cis = [metrics[c].get("bootstrap_ci", (0.0, 0.0)) for c in conds]
    err_lo = [max(0.0, v - lo) for v, (lo, _) in zip(vals, cis)]
    err_hi = [max(0.0, hi - v) for v, (_, hi) in zip(vals, cis)]
    ax.bar(conds, vals, yerr=[err_lo, err_hi], capsize=4)
    ax.set_ylabel("pass^3")
    ax.set_ylim(0, 1)
    ax.set_title("Headline: pass^3 by condition (95% CI)")
    fig.tight_layout()
    return fig


def _plot_lambda_comparison(metrics: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    paper = load_canonical_lambdas() if PARAMS_PATH.exists() else {}
    if not paper:
        return None
    levels = ["L0", "L1", "L2", "L3"]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    width = 0.18
    xs = np.arange(len(levels))
    for i, cond in enumerate(metrics.keys()):
        lam_dict = metrics[cond].get("lambda", {})
        ys = []
        for lvl in levels:
            lam_pair = lam_dict.get(lvl)
            if lam_pair is None or lam_pair[0] is None:
                ys.append(0.0)
            else:
                ys.append(lam_pair[0])
        ax.bar(xs + i * width, ys, width, label=cond)
    paper_ys = [paper.get(lvl, 0.0) for lvl in levels]
    ax.plot(xs + width * (len(metrics) / 2), paper_ys, "kx", markersize=10,
            label="paper analytic")
    ax.set_xticks(xs + width * (len(metrics) / 2))
    ax.set_xticklabels(levels)
    ax.set_ylabel("λ̂")
    ax.set_title("Empirical λ̂ vs paper analytic")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def _plot_ablation_heatmap(metrics: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    conds = list(metrics.keys())
    tasks: list = []
    for c in conds:
        for ep in metrics[c].get("episodes", []):
            if ep["task"] not in tasks:
                tasks.append(ep["task"])
    if not tasks:
        return None
    grid = np.zeros((len(conds), len(tasks)))
    for ci, c in enumerate(conds):
        for ti, t in enumerate(tasks):
            scores = [ep["score"] for ep in metrics[c].get("episodes", [])
                      if ep["task"] == t]
            grid[ci, ti] = float(np.mean(scores)) if scores else 0.0
    fig, ax = plt.subplots(figsize=(8, 3.5))
    im = ax.imshow(grid, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(tasks))); ax.set_xticklabels(tasks, rotation=30, ha="right")
    ax.set_yticks(range(len(conds))); ax.set_yticklabels(conds)
    fig.colorbar(im, ax=ax, label="pass rate")
    ax.set_title("Ablation: pass rate by (condition, task)")
    fig.tight_layout()
    return fig


def _fig_to_base64(fig) -> str:
    import matplotlib.pyplot as plt
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _render_html_template(metrics: dict, encoded_imgs: list[str]) -> str:
    paper_lams = load_canonical_lambdas() if PARAMS_PATH.exists() else {}
    rows: list[str] = []
    for cond, r in metrics.items():
        lams = r.get("lambda", {})
        lo, hi = r.get("bootstrap_ci", (0.0, 0.0))
        lam_strs = []
        for lvl in ("L0", "L1", "L2", "L3"):
            pair = lams.get(lvl)
            if pair is None or pair[0] is None:
                lam_strs.append(f"{lvl}=–")
            else:
                lam_strs.append(f"{lvl}={pair[0]:.4f}")
        rows.append(
            f"<tr><td>{cond}</td>"
            f"<td>{r.get('pass_pow_k', 0):.3f}</td>"
            f"<td>{lo:.3f}–{hi:.3f}</td>"
            f"<td>{' '.join(lam_strs)}</td></tr>"
        )
    imgs = "\n".join(
        f'<img src="data:image/png;base64,{e}" style="max-width:900px;margin:8px 0"/>'
        for e in encoded_imgs
    )
    return f"""<!doctype html>
<html><head><title>microRCS Run Report</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; max-width: 1024px; }}
table {{ border-collapse: collapse; margin: 12px 0; }}
td, th {{ border: 1px solid #ccc; padding: 6px 12px; }}
pre {{ background: #f5f5f5; padding: 8px; }}
</style></head><body>
<h1>microRCS — Run Report</h1>
<h2>Headline metrics</h2>
<table>
<tr><th>Condition</th><th>pass^3</th><th>95% CI</th><th>λ̂ per level</th></tr>
{''.join(rows)}
</table>
<h2>Paper analytic λᵢ (target)</h2>
<pre>{json.dumps(paper_lams, indent=2)}</pre>
<h2>Plots</h2>
{imgs}
</body></html>"""


# === 20. CLI subcommands =====================================================
def _print_headline(metrics: dict) -> None:
    print("\n=== microRCS HEADLINE ===")
    paper = load_canonical_lambdas() if PARAMS_PATH.exists() else {}
    for cond, r in metrics.items():
        lo, hi = r.get("bootstrap_ci", (0.0, 0.0))
        print(f"  {cond:>12s}: pass^3 = {r.get('pass_pow_k', 0):.3f}  "
              f"CI=[{lo:.3f}, {hi:.3f}]  pass@3={r.get('pass_at_k', 0):.3f}")
    print(f"  paper λ analytic: {paper}")
    print("=========================\n")


def cli_trace(args: argparse.Namespace) -> int:
    log = EventLog(Path(args.log))
    chain = log.trace(args.event_id)
    if not chain:
        print(f"No event {args.event_id} found.", file=sys.stderr)
        return 1
    for e in chain:
        print(f"[{e.timestamp:.3f}] L{e.level} {e.kind.value:14s} {e.event_id}  "
              f"<- {e.parent_id or '-'}  {e.payload}")
    return 0


def cli_lambda(args: argparse.Namespace) -> int:
    log_path = Path(args.run_dir) / "events.jsonl"
    if not log_path.exists():
        # Fall back to first events.jsonl under the run dir
        candidates = list(Path(args.run_dir).rglob("events.jsonl"))
        if not candidates:
            print(f"No events.jsonl under {args.run_dir}", file=sys.stderr)
            return 1
        log_path = candidates[0]
    log = EventLog(log_path)
    mon = LambdaMonitor(log, level=args.level)
    lam, std = mon.lambda_hat()
    print(f"L{args.level}: λ̂ = {lam:.4f} ± {std:.4f}")
    return 0


def cli_replay(args: argparse.Namespace) -> int:
    print(f"Replay not yet implemented (stub). Episode: {args.episode_jsonl}")
    return 0


def cli_watch(args: argparse.Namespace) -> int:
    """Tail one or more events.jsonl files and stream formatted progress.

    Usage:
        microrcs watch /tmp/microrcs-RUN-flat
        microrcs watch /tmp/microrcs-RUN-*    # via shell glob expansion
        microrcs watch reports/RUN_ID         # auto-discovers all events.jsonl

    Polls every `--interval` seconds (default 1.0); reports new events with the
    same formatting as live --live runs. Exits when no activity for `--idle`
    seconds (default 30) or on Ctrl-C. Designed to be safe against partial
    JSONL writes (skips malformed lines).
    """
    paths_to_watch: list[Path] = []
    for arg_path in args.paths:
        p = Path(arg_path)
        if p.is_file():
            paths_to_watch.append(p)
        elif p.is_dir():
            paths_to_watch.extend(p.rglob("events.jsonl"))
        else:
            print(f"watch: skipping non-existent {arg_path}", file=sys.stderr)
    if not paths_to_watch:
        print("watch: no events.jsonl found in provided paths.", file=sys.stderr)
        return 1

    print(f"watch: tailing {len(paths_to_watch)} log(s); idle timeout={args.idle}s; "
          f"poll={args.interval}s. Ctrl-C to stop.", file=sys.stderr)

    offsets: dict[Path, int] = {p: 0 for p in paths_to_watch}
    last_activity = time.time()
    pass_counts: dict[str, dict[str, int]] = {}  # cond → {"passes": x, "n": y}

    try:
        while True:
            had_event = False
            for p in paths_to_watch:
                if not p.exists():
                    continue
                try:
                    with p.open("r") as f:
                        f.seek(offsets[p])
                        chunk = f.read()
                        offsets[p] = f.tell()
                except OSError:
                    continue
                if not chunk:
                    continue
                cond_name = _condition_from_workspace_path(p)
                for line in chunk.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    formatted = _format_event_for_watch(e, cond_name, pass_counts)
                    if formatted:
                        print(formatted, flush=True)
                        had_event = True
            if had_event:
                last_activity = time.time()
            elif (time.time() - last_activity) > args.idle:
                print(f"watch: no activity for {args.idle}s — exiting.",
                      file=sys.stderr)
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nwatch: interrupted.", file=sys.stderr)
    return 0


def _condition_from_workspace_path(events_jsonl: Path) -> str:
    """Extract the condition name from a workspace path like
    /tmp/microrcs-<runid>-<cond>/.rcs/events.jsonl

    Conditions never contain a hyphen, so splitting on the LAST hyphen of the
    workspace dir name reliably isolates the condition regardless of how many
    hyphens the run-id has.
    """
    p = events_jsonl
    for _ in range(3):
        p = p.parent
        name = p.name
        if name.startswith("microrcs-"):
            last_dash = name.rfind("-")
            if last_dash > len("microrcs"):
                return name[last_dash + 1:].replace("plus_", "+")
            return name
    return events_jsonl.parent.name


def _format_event_for_watch(event: dict, cond: str,
                              pass_counts: dict) -> str | None:
    """Render a JSONL event as a one-line live-feed summary. None to skip."""
    kind = event.get("kind", "?")
    level = event.get("level", "?")
    payload = event.get("payload", {}) or {}
    ts = time.strftime("%H:%M:%S", time.localtime(event.get("timestamp", 0)))
    # Episode end (LYAPUNOV at level 0 with score in payload)
    if kind == "lyapunov" and level == 0 and "score" in payload:
        score = payload.get("score", 0)
        cost = payload.get("cost", 0)
        steps = payload.get("step", 0)
        cond_pass = pass_counts.setdefault(cond, {"passes": 0, "n": 0})
        cond_pass["n"] += 1
        if score >= 1.0:
            cond_pass["passes"] += 1
        glyph = "✓" if score >= 1.0 else "✗"
        rate = f"{cond_pass['passes']}/{cond_pass['n']}"
        return (f"[{ts}] {cond:<14} {glyph} score={score:.2f} steps={steps:<2} "
                f"${cost:.4f}  cumulative pass={rate}")
    if kind == "param_change":
        field = payload.get("field", "?")
        target = payload.get("target_level", "?")
        if field == "system_rules":
            added = payload.get("added", "")[:80]
            return f"[{ts}] {cond:<14} L→L{target} RULE+ {added}"
        if field == "mode":
            return (f"[{ts}] {cond:<14} L→L{target} MODE "
                    f"{payload.get('old')}→{payload.get('new')}")
        return f"[{ts}] {cond:<14} L→L{target} {field}={payload.get('new', '?')}"
    if kind == "shield" and event.get("correlation_id") == "shadow_eval":
        d = payload.get("decision", "?")
        sp = payload.get("shadow_passes", 0)
        bp = payload.get("baseline_passes", 0)
        return (f"[{ts}] {cond:<14} L2 shadow_eval {d.upper()} "
                f"({sp}/baseline {bp})")
    if kind == "breaker":
        return f"[{ts}] {cond:<14} ⚠️  CIRCUIT_BREAKER {payload}"
    return None


def cli_run(args: argparse.Namespace) -> int:
    cfg = _build_run_config(args.quick, args.paper, getattr(args, "suite", "reference"))
    cfg = replace(cfg, break_budgets=getattr(args, "break_budgets", False))
    seed = getattr(args, "seed", None)
    if seed is not None:
        cfg = replace(cfg, seed=int(seed))
    out = getattr(args, "out", Path("reports"))
    conditions = ("flat", "+autonomic", "+meta", "full")
    if args.quick:
        conditions = ("flat", "full")
    quiet = getattr(args, "quiet", False)
    result = run(cfg, out, conditions=conditions, quiet=quiet)
    report_path = out / result.run_id / "report.html"
    render_report(result.metrics, report_path)
    print(f"Report: {report_path}")
    _print_headline(result.metrics)
    return 0


# === Bench: multi-seed runs for noise-floor + statistical-significance ======
def cli_bench(args: argparse.Namespace) -> int:
    """Run the same configuration N times with different seeds; aggregate
    pass^k across seeds with proper bootstrap CIs.

    This is the noise-floor measurement: repeated `flat`-only runs tell us the
    intra-condition variance from temperature=1.0 sampling. Then we know what
    Δpass^k counts as signal vs noise.

    Usage:
        microrcs bench --suite harder --n-seeds 3 --conditions flat
        microrcs bench --suite harder --n-seeds 3 --conditions flat,full
    """
    cfg = _build_run_config(args.quick, args.paper, args.suite)
    out_root = Path(args.out) / f"bench-{new_event_id()}"
    out_root.mkdir(parents=True, exist_ok=True)

    conditions = tuple(c.strip() for c in args.conditions.split(",") if c.strip())
    n_seeds = int(args.n_seeds)
    quiet = getattr(args, "quiet", False)

    _emit_progress(quiet, f"BENCH: {n_seeds} seeds × {conditions} on suite={args.suite}")

    aggregate: dict[str, list] = {c: [] for c in conditions}
    seed_run_ids: list[str] = []
    for s in range(n_seeds):
        seed = (args.base_seed or 0) + s * 1009  # spread seeds; coprime spacing
        cfg_s = replace(cfg, seed=seed)
        _emit_progress(quiet, f"BENCH seed[{s+1}/{n_seeds}] = {seed}")
        result = run(cfg_s, out_root, conditions=conditions, quiet=quiet)
        seed_run_ids.append(result.run_id)
        for cond in conditions:
            aggregate[cond].append(result.metrics[cond])

    # Cross-seed aggregate: each seed produces one pass^k per condition.
    # Bootstrap that distribution to get noise-floor + cross-seed CI.
    summary: dict = {}
    for cond, runs_metrics in aggregate.items():
        pass_powks = [r["pass_pow_k"] for r in runs_metrics]
        means = [
            float(np.mean([e["score"] for e in r["episodes"]])) for r in runs_metrics
        ]
        costs = [sum(e["cost"] for e in r["episodes"]) for r in runs_metrics]
        # Bootstrap over seed-level pass^k values
        if len(pass_powks) >= 2:
            ci = bootstrap_ci(pass_powks, alpha=0.05, n=2000)
            std = bootstrap_std(pass_powks, n_resamples=2000)
        else:
            ci = (pass_powks[0], pass_powks[0]) if pass_powks else (0.0, 0.0)
            std = 0.0
        summary[cond] = {
            "n_seeds": len(pass_powks),
            "pass_pow_k_per_seed": pass_powks,
            "pass_pow_k_mean": float(np.mean(pass_powks)) if pass_powks else 0.0,
            "pass_pow_k_std": float(np.std(pass_powks)) if pass_powks else 0.0,
            "pass_pow_k_bootstrap_ci": ci,
            "pass_pow_k_bootstrap_std": std,
            "mean_score_per_seed": means,
            "cost_per_seed": costs,
            "total_cost": sum(costs),
        }

    bench_summary = {
        "bench_id": out_root.name,
        "n_seeds": n_seeds,
        "conditions": list(conditions),
        "suite": args.suite,
        "seed_run_ids": seed_run_ids,
        "per_condition": summary,
    }
    (out_root / "bench_summary.json").write_text(
        json.dumps(bench_summary, indent=2, default=str)
    )

    print(f"\nBENCH report: {out_root / 'bench_summary.json'}")
    print("\n=== BENCH HEADLINE ===")
    print(f"{'cond':>14}  {'seeds':>5}  {'mean':>6}  {'std':>6}  {'95% CI':>17}  {'cost':>7}")
    for cond, s in summary.items():
        lo, hi = s["pass_pow_k_bootstrap_ci"]
        print(f"{cond:>14}  {s['n_seeds']:>5}  "
              f"{s['pass_pow_k_mean']:>6.3f}  "
              f"{s['pass_pow_k_std']:>6.3f}  "
              f"{lo:>6.3f}-{hi:>6.3f}    "
              f"${s['total_cost']:>6.4f}")
    # Cross-condition Δ comparison
    if len(conditions) >= 2:
        baseline_cond = conditions[0]
        baseline_mean = summary[baseline_cond]["pass_pow_k_mean"]
        baseline_std = summary[baseline_cond]["pass_pow_k_std"]
        print(f"\nΔ vs '{baseline_cond}' (significant if |Δ| > 2σ_baseline):")
        for cond in conditions[1:]:
            d = summary[cond]["pass_pow_k_mean"] - baseline_mean
            sig = "✓ above noise" if abs(d) > 2 * baseline_std else "noise-level"
            print(f"  {cond:>14}: Δ = {d:+.3f}  ({sig})")
    print("=======================\n")
    return 0


def _resolve_suite(name: str) -> list:
    """Map a `--suite` flag value to a concrete task list."""
    if name == "harder":
        return list(HARDER_SUITE)
    if name == "both":
        return list(REFERENCE_SUITE) + list(HARDER_SUITE)
    return list(REFERENCE_SUITE)  # default


def _build_run_config(quick: bool, paper: bool,
                       suite: str = "reference") -> RunConfig:
    base_suite = _resolve_suite(suite)
    if quick:
        return RunConfig(
            suite=base_suite[:2], n_epochs=1, n_repeats=1,
            n_runs=2, max_steps_per_episode=10,
            max_cost_usd_per_episode=0.20,
        )
    if paper:
        return RunConfig(
            suite=base_suite, n_epochs=5, n_repeats=20,
            n_runs=4, max_steps_per_episode=25,
            max_cost_usd_per_episode=0.75,
        )
    return RunConfig(suite=base_suite)


# === 21. main() + argparse ===================================================
def main() -> int:
    p = argparse.ArgumentParser(
        prog="microrcs",
        description="microRCS — single-file recursive controlled system baseline",
    )
    sub = p.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="Execute a benchmark run (default)")
    p_run.add_argument("--quick", action="store_true", help="~3 min smoke run")
    p_run.add_argument("--paper", action="store_true", help="~3 hr paper-grade run")
    p_run.add_argument(
        "--break-budgets", action="store_true",
        help="Force λ_2 < 0 by removing L2 mutation budget (H4 test)",
    )
    p_run.add_argument("--out", default=Path("reports"), type=Path)
    p_run.add_argument(
        "--quiet", action="store_true",
        help="Suppress live per-episode progress to stderr (default: live)",
    )
    p_run.add_argument(
        "--suite", choices=("reference", "harder", "both"), default="reference",
        help="Task suite: 'reference' (5 mostly-easy tasks, default), "
             "'harder' (10 problems calibrated to ~50%% pass rate), "
             "or 'both' (15 tasks)",
    )
    p_run.add_argument(
        "--seed", type=int, default=None,
        help="Optional fixed seed for reproducible runs (default: stochastic)",
    )

    p_bench = sub.add_parser(
        "bench",
        help="Multi-seed benchmark for noise-floor + statistical-significance",
    )
    p_bench.add_argument("--suite", choices=("reference", "harder", "both"),
                          default="harder")
    p_bench.add_argument("--conditions", default="flat",
                          help="Comma-separated conditions, e.g. 'flat' or 'flat,+meta,full'")
    p_bench.add_argument("--n-seeds", type=int, default=3,
                          help="Number of seeds to run (default 3)")
    p_bench.add_argument("--base-seed", type=int, default=42,
                          help="Starting seed (subsequent seeds spaced by 1009)")
    p_bench.add_argument("--out", default=Path("reports"), type=Path)
    p_bench.add_argument("--quick", action="store_true")
    p_bench.add_argument("--paper", action="store_true")
    p_bench.add_argument("--quiet", action="store_true")

    p_trace = sub.add_parser("trace", help="Walk parent chain from event_id")
    p_trace.add_argument("event_id")
    p_trace.add_argument("--log", required=True, help="Path to events.jsonl")

    p_lam = sub.add_parser("lambda", help="Print λ̂ for a level from a run dir")
    p_lam.add_argument("run_dir")
    p_lam.add_argument("--level", type=int, required=True)

    p_replay = sub.add_parser("replay", help="Re-execute episode from JSONL (stub)")
    p_replay.add_argument("episode_jsonl")

    p_watch = sub.add_parser(
        "watch",
        help="Tail events.jsonl from one or more workspaces and stream live progress",
    )
    p_watch.add_argument(
        "paths", nargs="+",
        help="Workspace dirs or events.jsonl files (shell glob OK)",
    )
    p_watch.add_argument("--interval", type=float, default=1.0,
                          help="Poll interval seconds (default 1.0)")
    p_watch.add_argument("--idle", type=float, default=30.0,
                          help="Exit after this many seconds of no new events (default 30)")

    args = p.parse_args()
    if args.cmd is None or args.cmd == "run":
        if args.cmd is None:
            args.quick = False
            args.paper = False
            args.break_budgets = False
            args.out = Path("reports")
            args.quiet = False
            args.suite = "reference"
            args.seed = None
        return cli_run(args)
    if args.cmd == "trace":
        return cli_trace(args)
    if args.cmd == "lambda":
        return cli_lambda(args)
    if args.cmd == "replay":
        return cli_replay(args)
    if args.cmd == "watch":
        return cli_watch(args)
    if args.cmd == "bench":
        return cli_bench(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
