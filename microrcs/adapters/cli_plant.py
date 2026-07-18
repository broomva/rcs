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

Billing hardening (maestro BRO-1912 lessons, replicated for Python):
- deny-by-default env allowlist (`filter_env`) — the child NEVER inherits
  ANTHROPIC_API_KEY (forces subscription OAuth; bogus-key dogfood proves it),
  AWS_*, GH_TOKEN, or anything else not explicitly allowed
- USER + LOGNAME forwarded (macOS keychain OAuth lookup needs them)
- prompt via stdin (claude's `--disallowed-tools`-style variadic flags are
  greedy and would swallow a trailing positional prompt)
- SIGTERM-first termination with a bounded SIGKILL fallback + reap

SECURITY SCOPE (do not over-read `filter_env`): env filtering closes the
*environment-variable* exfil channel and forces subscription billing. It is
NOT an exfil sandbox. The child is `claude -p` with auto-approved Bash + a
forwarded HOME, so it can still READ `~/.aws/credentials`, `~/.config/gh/*`,
`~/.codex/auth.json`, the Claude OAuth credential itself, and workspace
`.env` files, and can `curl` them out. Only run TRUSTED tasks (curated
SWE-bench instances) this way; untrusted-task runs require a real filesystem
+ network sandbox (container/VM/`sandbox-exec`, or a scratch HOME holding
only an isolated OAuth cred). See `filter_env` docstring.

Stdlib only in this module (the `microrcs` import pulls numpy transitively via
the parent). Unit tests in `tests/test_cli_plant.py` mock the subprocess —
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

    SCOPE: this closes the environment-variable channel only. It does NOT
    prevent a Bash-capable child from reading on-disk secrets under the
    forwarded HOME (see module docstring). Env filtering ⇒ correct billing +
    no env-resident secret leak; it is not an exfil sandbox.
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
        malformed output so the caller can classify it as parse_error.

        Robust to warning lines before the JSON AND trailing text after it:
        scans each `{` and uses raw_decode to take the first balanced object,
        so a warning containing a brace or a `...}\\nBYE` tail no longer wastes
        a (subscription-billed) episode (m2)."""
        text = stdout.strip()
        if not text:
            raise ValueError("empty CLI stdout")
        decoder = json.JSONDecoder()
        idx = text.find("{")
        while idx >= 0:
            try:
                obj, _ = decoder.raw_decode(text, idx)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
            idx = text.find("{", idx + 1)
        raise ValueError(f"no JSON object in CLI stdout: {text[:120]!r}")

    def _episode_env(self, workspace: str) -> dict[str, str]:
        """Child env = filtered base + the instance venv bin prepended to PATH
        (M1: the SWE prompt promises `python`/`pytest` on PATH; the venv lives
        in a separate cache dir, discoverable via the workspace marker)."""
        env = dict(self._env)
        marker = Path(workspace) / ".microrcs_venv"
        if marker.exists():
            try:
                venv_bin = Path(marker.read_text().strip()) / "bin"
                env["VIRTUAL_ENV"] = str(venv_bin.parent)
                env["PATH"] = f"{venv_bin}{os.pathsep}{env['PATH']}"
            except OSError:
                pass  # fall back to bare PATH; verifier still scores git diff
        return env

    @staticmethod
    def _reset_workspace(workspace: str) -> None:
        """B1: restore the workspace to its post-setup git state so every
        episode is INDEPENDENT. Setup commits test_patch as HEAD, so
        `reset --hard HEAD` reverts the previous agent's edits and `clean -fd`
        removes its untracked files — while `-e .microrcs_venv` preserves the
        venv-locator marker (the venv itself lives in a separate cache dir).
        Without this, agent edits + `git diff HEAD` accumulate across
        generations and the private gate measures cumulative state, not the
        candidate's marginal effect (the load-bearing correctness property)."""
        subprocess.run(
            ["git", "reset", "--hard", "HEAD"], cwd=workspace,
            capture_output=True, text=True, timeout=60, check=False,
        )
        subprocess.run(
            ["git", "clean", "-fd", "-e", ".microrcs_venv"], cwd=workspace,
            capture_output=True, text=True, timeout=60, check=False,
        )

    def run_episode(self, task: m.Task, config: HarnessConfig) -> EpisodeResult:
        workspace = task.metadata.get("swe_agent_workspace")
        if not workspace:
            return EpisodeResult(
                instance_id=task.id, score=0.0, is_error=True, duration_s=0.0,
                num_turns=None, cost_usd_reported=None,
                result_text="task has no swe_agent_workspace metadata",
                config_id=config.config_id, aborted="spawn_error",
            )
        # Independence gate: reset before the agent touches the workspace.
        try:
            self._reset_workspace(workspace)
        except (OSError, subprocess.SubprocessError) as exc:
            return EpisodeResult(
                instance_id=task.id, score=0.0, is_error=True, duration_s=0.0,
                num_turns=None, cost_usd_reported=None,
                result_text=f"workspace reset failed: {exc}",
                config_id=config.config_id, aborted="reset_error",
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

        episode_env = self._episode_env(workspace)
        t0 = time.monotonic()
        aborted: str | None = None
        stdout = ""
        try:
            proc = self._spawn(
                argv, cwd=workspace, env=episode_env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace",  # m4: non-ASCII SWE text
            )
            try:
                stdout, _ = proc.communicate(task.prompt, timeout=self.timeout_s)
            except subprocess.TimeoutExpired:
                aborted = "timeout"
                proc.send_signal(signal.SIGTERM)  # SIGTERM-first (BRO-1912)
                try:
                    proc.communicate(timeout=10.0)  # reap + drain pipes
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.communicate(timeout=10.0)  # final reap (m1: no zombie/FD leak)
                    except subprocess.TimeoutExpired:
                        pass
                stdout = ""
        except (OSError, UnicodeError) as exc:
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
        # The CLI's own claims are never the score (P11). Guard the verify
        # call so a verifier exception can't kill an unattended long run.
        try:
            score = float(task.verify(str(envelope.get("result", ""))))
        except Exception as exc:  # noqa: BLE001 — verifier robustness boundary
            return EpisodeResult(
                instance_id=task.id, score=0.0, is_error=True,
                duration_s=duration, num_turns=envelope.get("num_turns"),
                cost_usd_reported=envelope.get("total_cost_usd"),
                result_text=f"verify error: {exc}",
                config_id=config.config_id, aborted="verify_error",
            )
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
    disjoint from `train_tasks`; their raw scores are never shown to the
    proposer.

    HONEST LIMIT on "private" (P20 caught this — the adaptive-data-analysis
    channel): the accept/reject decision IS a 1-bit thresholded projection
    of the holdout signal, and because `best` only advances on acceptance and
    seeds the next proposal, the loop *structurally* hill-climbs `best`
    against the holdout over many generations. So the holdout degrades into a
    selection set (this is inherent to any private-gate RSI loop, AIDE²
    included). Two guards ship here: (1) `max_generations` bounds how much the
    selection channel can overfit; (2) an OPTIONAL `final_test_tasks` split is
    scored only in `final_report()` and NEVER touched by the gate — the
    unbiased generalization estimate. Rotate the holdout for long runs.
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
        final_test_tasks: Sequence[m.Task] | None = None,
        max_generations: int | None = None,
    ) -> None:
        if not train_tasks:
            raise ValueError("train_tasks is empty — the loop can never learn")
        if not holdout_tasks:
            raise ValueError("holdout_tasks is empty — the gate is vacuous (0>0 always False)")
        train_ids = {t.id for t in train_tasks}
        hold_ids = {t.id for t in holdout_tasks}
        final_ids = {t.id for t in (final_test_tasks or [])}
        overlap = train_ids & hold_ids
        if overlap:
            raise ValueError(f"train/holdout overlap breaks the private gate: {sorted(overlap)}")
        final_overlap = final_ids & (train_ids | hold_ids)
        if final_overlap:
            raise ValueError(f"final_test overlaps train/holdout — biases the unbiased estimate: {sorted(final_overlap)}")
        self.runner = runner
        self.train_tasks = list(train_tasks)
        self.holdout_tasks = list(holdout_tasks)
        self.final_test_tasks = list(final_test_tasks or [])
        self.propose_fn = propose_fn
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.best = genesis or HarnessConfig()
        self.best_holdout: float | None = None  # lazily scored on first step
        self.max_generations = max_generations
        self.n_steps = 0
        self.history: list[dict] = []  # proposer-visible: train scores + accept-bit only

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

        if self.max_generations is not None and self.n_steps >= self.max_generations:
            raise RuntimeError(
                f"max_generations={self.max_generations} reached — stop to bound "
                f"adaptive-data-analysis overfitting of the holdout via the accept bit"
            )
        self.n_steps += 1
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

    def final_report(self) -> dict:
        """Unbiased generalization estimate: score `best` on the final-test
        split, which the gate NEVER touched (M2 mitigation for the accept-bit
        adaptive-overfitting channel). Returns {} if no final split was given.
        Call once, after the loop; never inside `step`."""
        if not self.final_test_tasks:
            return {"final_test": None, "note": "no final_test_tasks — holdout is the only estimate (accept-bit overfitting uncorrected)"}
        final_score = self._mean_score(self.best, self.final_test_tasks)
        report = {
            "best_config": self.best.to_json(),
            "generations": self.n_steps,
            "holdout_score": self.best_holdout,
            "final_test_score": final_score,
            "overfit_gap": (self.best_holdout - final_score) if self.best_holdout is not None else None,
        }
        (self.out_dir / "final_report.json").write_text(json.dumps(report, indent=2))
        return report


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
