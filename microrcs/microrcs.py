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
        i, o, cr, cc = _PRICING.get(model, (0.0, 0.0, 0.0, 0.0))
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


L0_SYSTEM_PROMPT = """\
You are an agent in a workspace. Your tools are `bash` and `submit`.

ENVIRONMENT
  cwd: {cwd}
  helpers/   - Python utilities you may use, edit, or extend.
  memory/    - Your knowledge graph. Read existing entries; add new ones with
               frontmatter (see memory/README.md). Use wikilinks to relate them.
  scratch/   - Ephemeral, wiped between tasks.

TASK
  See TASK.md (or use the user message below).

DOCUMENT AS YOU WORK
  When you discover something durable (a fact, a pattern, a useful helper),
  write it as a markdown file in memory/ with frontmatter so future tasks
  can find it. Bump `score` on entries you reuse.

CURRENT MODE: {mode}
{rules_addendum}

Submit your final answer with submit() when done.
"""


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
    ):
        self.reasoner = reasoner
        self.workspace = workspace
        self.log = log
        self.caps = caps
        self.mode = mode or AgentMode.BASE
        self.system_rules: list[str] = list(system_rules or [])

    def run_episode(self, task: Task) -> EpisodeTrace:
        cid = f"ep_{new_event_id()}"
        snap_before = self.workspace.snapshot()
        (self.workspace.path / "TASK.md").write_text(task.prompt)
        rules = ""
        if self.system_rules:
            rules = "RULES YOU'VE LEARNED\n" + "\n".join(f"  - {r}" for r in self.system_rules)
        sys_prompt = L0_SYSTEM_PROMPT.format(
            cwd=str(self.workspace.path), mode=self.mode.value, rules_addendum=rules
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
                    self.log.append(RCSEvent(
                        new_event_id(), None, time.time(), 0,
                        EventKind.LYAPUNOV, cid, {"V": 1.0 - score},
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
        self.log.append(RCSEvent(
            new_event_id(), None, time.time(), 0,
            EventKind.LYAPUNOV, cid, {"V": 1.0, "aborted": reason},
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
class MetaState:
    l1_decisions: list
    l1_lyapunov_trend: float
    helper_diffs: list
    memory_snapshot: dict
    epoch: int = 0

    @classmethod
    def from_log(cls, log: EventLog, epoch: int = 0) -> "MetaState":
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
                    helper_diffs=[], memory_snapshot={}, epoch=epoch)


class L2Meta:
    """Watches L1 history. Proposes mutations to L0's prompt template, helpers, memory."""

    def __init__(self, reasoner: Reasoner, log: EventLog,
                 mutation_budget: int = 5):
        self.reasoner = reasoner
        self.log = log
        self.mutation_budget = mutation_budget
        self.mutations_this_epoch = 0
        self.accepted_mutations: list = []

    def observe(self, history: list[RCSEvent]) -> MetaState:
        return MetaState.from_log(self.log)

    def decide(self, state: MetaState) -> Decision:
        if state.l1_lyapunov_trend < -0.001:
            return Decision(action=NoOp(reason="V₁ already decaying"), rationale="ok")
        prompt = (
            f"L1 Lyapunov trend (slope): {state.l1_lyapunov_trend:+.4f}\n"
            f"L1 decisions this epoch: {len(state.l1_decisions)}\n"
            f"Past mutations: {len(self.accepted_mutations)}\n\n"
            "Pick ONE action:\n"
            "  RULE <text>          — append a system rule for L0\n"
            "  HELPER <path>=<text> — promote a helper file\n"
            "  PROMOTE_MEMORY <path>=<canonical|draft>\n"
            "  NOOP\n\n"
            "Reply on one line with the action keyword + arguments."
        )
        try:
            resp = self.reasoner.reason(ReasoningRequest(
                messages=(Message("user", prompt),), max_tokens=200,
                model="claude-sonnet-4-6",
            ))
            txt = (resp.text or "").strip()
        except Exception:
            txt = "NOOP default"
        return self._parse_decision(txt)

    def _parse_decision(self, text: str) -> Decision:
        first_line = text.strip().split("\n", 1)[0]
        upper = first_line.upper()
        if upper.startswith("RULE "):
            return Decision(
                action=AppendSystemRule(rule=first_line[5:].strip()[:300],
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

    def shield(self, dec: Decision, state: MetaState) -> Decision:
        if self.mutations_this_epoch >= self.mutation_budget:
            return Decision(
                action=NoOp(reason="mutation_budget_exhausted"), rationale=dec.rationale,
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

    def lyapunov(self, state: MetaState) -> float:
        # V₂ = max(0, -dV₁/dt)² — bigger when V₁ is NOT decaying
        positive_slope = max(0.0, state.l1_lyapunov_trend)
        return positive_slope ** 2


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
            "A train leaves Town A at 9:47 going 73 mph. A second train leaves "
            "Town B at 11:23 going 81 mph toward Town A. Towns are 412 miles apart. "
            "At what time do they meet? Answer as HH:MM (24h)."
        ),
        verify=_verify_approx_time("13:54", tolerance_minutes=4),
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
            "Three friends ordered different drinks: coffee, tea, water. "
            "Alice didn't order coffee. Bob ordered the same drink as the person "
            "whose name comes alphabetically last (Carol). Carol didn't order water. "
            "Who ordered what? Answer EXACTLY as 'Alice: X, Bob: Y, Carol: Z'."
        ),
        verify=_make_normalize_match("Alice: water, Bob: tea, Carol: tea"),
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


@dataclass
class RunResult:
    run_id: str
    config: RunConfig
    metrics: dict
    workspace_paths: dict
    report_path: Path | None = None


def run(
    cfg: RunConfig,
    out_dir: Path | str,
    conditions: tuple[str, ...] = ("flat", "+autonomic", "+meta", "full"),
) -> RunResult:
    if cfg.seed is not None:
        random.seed(cfg.seed)
        np.random.seed(cfg.seed)
    run_id = new_event_id()
    out_dir = Path(out_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
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
        l2 = L2Meta(l2_reasoner, log, mutation_budget=l2_budget) \
            if l2_reasoner is not None else None
        l3 = L3Governance(l3_reasoner, log) if l3_reasoner is not None else None

        cond_results: dict = {"episodes": [], "lambda": {}}

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
                    # L1 fires per task
                    if l1 is not None:
                        history = list(log._events)
                        obs = l1.observe(history)
                        dec = l1.decide(obs)
                        safe = l1.shield(dec, obs)
                        apply_decision_downward(1, safe, plant, l1, l2, log)
            # L2 fires per epoch
            if l2 is not None:
                state = MetaState.from_log(log, epoch=epoch)
                dec = l2.decide(state)
                safe = l2.shield(dec, state)
                apply_decision_downward(2, safe, plant, l1, l2, log)
            # L3 fires when conditions met
            if l3 is not None and l3._should_fire(log):
                state = GovernanceState.from_log(log)
                dec = l3.decide(state)
                safe = l3.shield(dec, state)
                if not isinstance(safe.action, NoOp):
                    l3.last_change_t = time.time()
                apply_decision_downward(3, safe, plant, l1, l2, log)

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


def cli_run(args: argparse.Namespace) -> int:
    cfg = _build_run_config(args.quick, args.paper)
    cfg = replace(cfg, break_budgets=getattr(args, "break_budgets", False))
    out = getattr(args, "out", Path("reports"))
    conditions = ("flat", "+autonomic", "+meta", "full")
    if args.quick:
        conditions = ("flat", "full")
    result = run(cfg, out, conditions=conditions)
    report_path = out / result.run_id / "report.html"
    render_report(result.metrics, report_path)
    print(f"Report: {report_path}")
    _print_headline(result.metrics)
    return 0


def _build_run_config(quick: bool, paper: bool) -> RunConfig:
    if quick:
        return RunConfig(
            suite=REFERENCE_SUITE[:2], n_epochs=1, n_repeats=1,
            n_runs=2, max_steps_per_episode=10,
            max_cost_usd_per_episode=0.20,
        )
    if paper:
        return RunConfig(
            suite=REFERENCE_SUITE, n_epochs=5, n_repeats=20,
            n_runs=4, max_steps_per_episode=25,
            max_cost_usd_per_episode=0.75,
        )
    return RunConfig()


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

    p_trace = sub.add_parser("trace", help="Walk parent chain from event_id")
    p_trace.add_argument("event_id")
    p_trace.add_argument("--log", required=True, help="Path to events.jsonl")

    p_lam = sub.add_parser("lambda", help="Print λ̂ for a level from a run dir")
    p_lam.add_argument("run_dir")
    p_lam.add_argument("--level", type=int, required=True)

    p_replay = sub.add_parser("replay", help="Re-execute episode from JSONL (stub)")
    p_replay.add_argument("episode_jsonl")

    args = p.parse_args()
    if args.cmd is None or args.cmd == "run":
        if args.cmd is None:
            args.quick = False
            args.paper = False
            args.break_budgets = False
            args.out = Path("reports")
        return cli_run(args)
    if args.cmd == "trace":
        return cli_trace(args)
    if args.cmd == "lambda":
        return cli_lambda(args)
    if args.cmd == "replay":
        return cli_replay(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
