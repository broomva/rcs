"""CliPlant — subscription-CLI L0 plant + AIDE²-shape generation loop.

BRO-1943 (re-scope of BRO-1071). Runs SWE episodes through the Claude Code
CLI (`claude -p`) on subscription OAuth instead of API billing, and evolves
the inner agent's *harness config* via an outer loop gated on a held-out
private split — the AIDE² recipe (weco.ai, 2026-07) on our own stack:

- inner agent  = `claude -p` running one SWE episode agentically in the
  instance's COW workspace (adapter + verifier from `swe_bench.py` reused)
- outer loop   = `GenerationLoop` proposing HarnessConfig mutations
- private gate = candidate accepted ONLY if it beats best-so-far on a
  held-out instance split the evolution never optimizes against
  (expected acceptance ~1/10 — the selection gate is load-bearing,
  cf. microgrid 69/69 vetoes + H4)

Security (maestro BRO-1912 lessons, replicated for Python):
- deny-by-default env allowlist (`filter_env`) — the child NEVER inherits
  ANTHROPIC_API_KEY (forces subscription OAuth; bogus-key dogfood proves it),
  AWS_*, GH_TOKEN, or anything else not explicitly allowed
- USER + LOGNAME forwarded (macOS keychain OAuth lookup needs them)
- prompt via stdin (claude's `--disallowed-tools`-style variadic flags are
  greedy and would swallow a trailing positional prompt)
- SIGTERM-first termination with a bounded SIGKILL fallback

Pure stdlib. Unit tests in `tests/test_cli_plant.py` mock the subprocess —
CI never invokes the real CLI.
"""
from __future__ import annotations

import dataclasses
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

_MICROCRS_DIR = Path(__file__).resolve().parents[1]
if str(_MICROCRS_DIR) not in sys.path:
    sys.path.insert(0, str(_MICROCRS_DIR))
import microrcs as m  # noqa: E402

# === Env hardening =======================================================
#: Only these vars cross into the CLI child. Everything else — most
#: critically ANTHROPIC_API_KEY — is dropped (deny-by-default).
ENV_ALLOWLIST: tuple[str, ...] = (
    "HOME", "USER", "LOGNAME", "TERM", "LANG", "LC_ALL", "TMPDIR", "SHELL",
)
#: Minimal PATH for the child: system bins + the CLI's install dir.
DEFAULT_CHILD_PATH = "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin"


def filter_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Deny-by-default env filter (maestro BRO-1912 `filterPassthroughEnv`).

    Returns a fresh dict containing ONLY the allowlisted vars plus a minimal
    PATH extended with `~/.local/bin` (where the claude CLI lives). The
    returned env NEVER contains ANTHROPIC_API_KEY — even if the parent holds
    one — so a successful child run is proof of subscription-OAuth billing.
    """
    src = dict(base if base is not None else os.environ)
    out: dict[str, str] = {}
    for key in ENV_ALLOWLIST:
        if key in src:
            out[key] = src[key]
    home = out.get("HOME", str(Path.home()))
    out["PATH"] = f"{DEFAULT_CHILD_PATH}:{home}/.local/bin"
    # Belt over braces: even a hostile allowlist edit must not leak the key.
    out.pop("ANTHROPIC_API_KEY", None)
    return out


# === Harness DNA =========================================================
@dataclass(frozen=True)
class HarnessConfig:
    """The inner agent's mutable harness — what the outer loop evolves.

    This is deliberately *config*, not code: the CLI's system-prompt append,
    turn budget, tool policy, and model choice are the four knobs AIDE²'s
    "rewrites the inner agent's harness" reduces to on a hosted CLI.
    """

    model: str = "claude-sonnet-4-6"
    max_turns: int = 60
    allowed_tools: tuple[str, ...] = ("Bash", "Read", "Edit", "Write", "Grep", "Glob")
    system_prompt_append: str = ""
    generation: int = 0
    parent: str | None = None
    notes: str = "genesis"

    @property
    def config_id(self) -> str:
        return f"gen{self.generation}"

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "HarnessConfig":
        raw = json.loads(text)
        raw["allowed_tools"] = tuple(raw.get("allowed_tools", ()))
        return cls(**raw)


@dataclass
class EpisodeResult:
    instance_id: str
    score: float
    is_error: bool
    duration_s: float
    num_turns: int | None
    cost_usd_reported: float | None
    result_text: str
    config_id: str
    aborted: str | None = None  # None | "timeout" | "spawn_error" | "parse_error"


# === The CLI plant =======================================================
class ClaudeCliRunner:
    """Runs one SWE episode through `claude -p` and scores it via the task's
    verifier closure. The CLI *is* the L0 plant: it owns the agentic loop
    (bash/edit in the workspace); we own setup, scoring, and the harness DNA.
    """

    def __init__(
        self,
        claude_bin: str | None = None,
        *,
        timeout_s: float = 900.0,
        env_base: Mapping[str, str] | None = None,
        spawn: Callable[..., subprocess.Popen] | None = None,
    ) -> None:
        self.claude_bin = claude_bin or str(Path.home() / ".local/bin/claude")
        self.timeout_s = timeout_s
        self._env = filter_env(env_base)
        self._spawn = spawn or subprocess.Popen

    # -- envelope parsing (separate for unit-testability) -----------------
    @staticmethod
    def parse_envelope(stdout: str) -> dict:
        """Parse the `--output-format json` envelope. Raises ValueError on
        malformed output so the caller can classify it as parse_error."""
        text = stdout.strip()
        if not text:
            raise ValueError("empty CLI stdout")
        # The envelope is the last JSON object on stdout (warnings may precede).
        start = text.find("{")
        if start < 0:
            raise ValueError(f"no JSON in CLI stdout: {text[:120]!r}")
        return json.loads(text[start:])

    def run_episode(self, task: m.Task, config: HarnessConfig) -> EpisodeResult:
        workspace = task.metadata.get("swe_agent_workspace")
        if not workspace:
            return EpisodeResult(
                instance_id=task.id, score=0.0, is_error=True, duration_s=0.0,
                num_turns=None, cost_usd_reported=None,
                result_text="task has no swe_agent_workspace metadata",
                config_id=config.config_id, aborted="spawn_error",
            )
        argv = [
            self.claude_bin, "-p",
            "--model", config.model,
            "--output-format", "json",
            "--max-turns", str(config.max_turns),
            "--allowed-tools", ",".join(config.allowed_tools),
        ]
        if config.system_prompt_append:
            argv += ["--append-system-prompt", config.system_prompt_append]

        t0 = time.monotonic()
        aborted: str | None = None
        stdout = ""
        try:
            proc = self._spawn(
                argv, cwd=workspace, env=self._env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            try:
                stdout, _ = proc.communicate(task.prompt, timeout=self.timeout_s)
            except subprocess.TimeoutExpired:
                aborted = "timeout"
                proc.send_signal(signal.SIGTERM)  # SIGTERM-first (BRO-1912)
                try:
                    proc.wait(timeout=10.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                stdout = ""
        except OSError as exc:
            return EpisodeResult(
                instance_id=task.id, score=0.0, is_error=True,
                duration_s=time.monotonic() - t0, num_turns=None,
                cost_usd_reported=None, result_text=f"spawn failed: {exc}",
                config_id=config.config_id, aborted="spawn_error",
            )
        duration = time.monotonic() - t0

        envelope: dict = {}
        if aborted is None:
            try:
                envelope = self.parse_envelope(stdout)
            except (ValueError, json.JSONDecodeError) as exc:
                aborted = "parse_error"
                envelope = {"is_error": True, "result": f"parse error: {exc}"}

        # Score by *interacting with the artifact*: the verifier applies the
        # workspace's `git diff HEAD` to a fresh sibling and runs pytest.
        # The CLI's own claims are never the score (P11).
        score = float(task.verify(str(envelope.get("result", ""))))
        return EpisodeResult(
            instance_id=task.id,
            score=score,
            is_error=bool(envelope.get("is_error", aborted is not None)),
            duration_s=duration,
            num_turns=envelope.get("num_turns"),
            cost_usd_reported=envelope.get("total_cost_usd"),
            result_text=str(envelope.get("result", ""))[:2000],
            config_id=config.config_id,
            aborted=aborted,
        )


# === AIDE²-shape generation loop ========================================
ProposeFn = Callable[[HarnessConfig, list[dict]], HarnessConfig]


@dataclass
class GenerationRecord:
    config: HarnessConfig
    train_score: float
    holdout_score: float
    accepted: bool
    reason: str


class GenerationLoop:
    """Outer loop: propose harness mutation → evaluate on train split →
    gate on the held-out private split vs best-so-far → accept/reject.

    The private gate is the load-bearing element (AIDE²: ~9/10 rejected;
    microrcs H4/microgrid: shields load-bearing). `holdout_tasks` must be
    disjoint from `train_tasks` and are NEVER shown to the proposer.
    """

    def __init__(
        self,
        runner: ClaudeCliRunner,
        train_tasks: Sequence[m.Task],
        holdout_tasks: Sequence[m.Task],
        propose_fn: ProposeFn,
        out_dir: Path,
        *,
        genesis: HarnessConfig | None = None,
    ) -> None:
        train_ids = {t.id for t in train_tasks}
        overlap = train_ids & {t.id for t in holdout_tasks}
        if overlap:
            raise ValueError(f"train/holdout overlap breaks the private gate: {sorted(overlap)}")
        self.runner = runner
        self.train_tasks = list(train_tasks)
        self.holdout_tasks = list(holdout_tasks)
        self.propose_fn = propose_fn
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.best = genesis or HarnessConfig()
        self.best_holdout: float | None = None  # lazily scored on first step
        self.history: list[dict] = []  # proposer-visible: PUBLIC info only

    def _mean_score(self, config: HarnessConfig, tasks: Sequence[m.Task]) -> float:
        results = [self.runner.run_episode(t, config) for t in tasks]
        self._log_episodes(config, results)
        return sum(r.score for r in results) / max(len(results), 1)

    def _log_episodes(self, config: HarnessConfig, results: list[EpisodeResult]) -> None:
        with (self.out_dir / "episodes.jsonl").open("a") as fh:
            for r in results:
                fh.write(json.dumps({"config": config.to_json(), **dataclasses.asdict(r)}) + "\n")

    def step(self) -> GenerationRecord:
        if self.best_holdout is None:
            self.best_holdout = self._mean_score(self.best, self.holdout_tasks)

        candidate = self.propose_fn(self.best, self.history)
        candidate = dataclasses.replace(
            candidate,
            generation=self.best.generation + 1,
            parent=self.best.config_id,
        )
        train_score = self._mean_score(candidate, self.train_tasks)
        holdout_score = self._mean_score(candidate, self.holdout_tasks)

        # THE GATE: strict improvement on the private split, nothing else.
        accepted = holdout_score > self.best_holdout
        reason = (
            f"holdout {holdout_score:.3f} > best {self.best_holdout:.3f}"
            if accepted
            else f"holdout {holdout_score:.3f} <= best {self.best_holdout:.3f}"
        )
        record = GenerationRecord(candidate, train_score, holdout_score, accepted, reason)
        # Proposer sees train (public) scores + accept/reject only — never
        # the holdout numbers (they'd leak the private signal into g(x)).
        self.history.append(
            {"config": candidate.to_json(), "train_score": train_score, "accepted": accepted}
        )
        with (self.out_dir / "lineage.jsonl").open("a") as fh:
            fh.write(json.dumps({
                "config": candidate.to_json(), "train_score": train_score,
                "holdout_score": holdout_score, "accepted": accepted, "reason": reason,
            }) + "\n")
        if accepted:
            self.best = candidate
            self.best_holdout = holdout_score
            (self.out_dir / "best_config.json").write_text(candidate.to_json())
        return record


# === Default mutation proposer (outer model via the same CLI) ============
PROPOSER_PROMPT = """You are the outer loop of a harness-evolution experiment.
Current inner-agent harness config (JSON): {config}
History of prior attempts (train scores + accept/reject): {history}

Propose ONE mutation to the harness that might improve the inner agent's
SWE-bench performance. You may change: system_prompt_append (coaching text,
<= 800 chars), max_turns (20..120), allowed_tools (subset of
Bash,Read,Edit,Write,Grep,Glob). Do NOT change model.

Reply with ONLY a JSON object: {{"system_prompt_append": "...",
"max_turns": N, "allowed_tools": ["..."], "notes": "one-line rationale"}}"""


def make_cli_proposer(
    claude_bin: str | None = None,
    *,
    model: str = "claude-opus-4-7",
    timeout_s: float = 120.0,
) -> ProposeFn:
    """Outer-loop proposer running on the same subscription CLI (frontier
    model — the capacity-sweep found the meta-controller tier is what
    matters). Falls back to a no-op mutation on any failure so the loop's
    gate (not the proposer) stays the safety boundary."""
    bin_ = claude_bin or str(Path.home() / ".local/bin/claude")
    env = filter_env()

    def propose(best: HarnessConfig, history: list[dict]) -> HarnessConfig:
        prompt = PROPOSER_PROMPT.format(
            config=best.to_json(), history=json.dumps(history[-8:]),
        )
        try:
            proc = subprocess.run(
                [bin_, "-p", "--model", model, "--output-format", "json",
                 "--max-turns", "1", "--disallowed-tools", "*"],
                input=prompt, env=env, text=True, capture_output=True,
                timeout=timeout_s, check=False,
            )
            envelope = ClaudeCliRunner.parse_envelope(proc.stdout)
            raw = str(envelope.get("result", ""))
            mutation = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            tools = tuple(
                t for t in mutation.get("allowed_tools", best.allowed_tools)
                if t in ("Bash", "Read", "Edit", "Write", "Grep", "Glob")
            ) or best.allowed_tools
            return dataclasses.replace(
                best,
                system_prompt_append=str(mutation.get("system_prompt_append", best.system_prompt_append))[:800],
                max_turns=max(20, min(120, int(mutation.get("max_turns", best.max_turns)))),
                allowed_tools=tools,
                notes=str(mutation.get("notes", "proposer"))[:200],
            )
        except Exception as exc:  # noqa: BLE001 — proposer must never kill the loop
            return dataclasses.replace(best, notes=f"proposer failed ({exc}); no-op mutation")

    return propose
