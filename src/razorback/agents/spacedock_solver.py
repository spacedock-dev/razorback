# ABOUTME: SpacedockSolverAgent canonical runtime adapter for claude|codex|pi.
# ABOUTME: __init__ computes sealed_hash from six inputs; refuses on resume mismatch BEFORE harbor I/O.

import asyncio
import json
import os
import shlex
from pathlib import Path
from typing import Any, Literal

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment

from razorback.agents.seal import compute_sealed_hash, prompt_sha256  # noqa: F401
from razorback.benchmarks.ade_bench.preflight import preflight_script_text
from razorback.errors import RazorbackError, SeedMismatchError
from razorback.freeze_dir_default import resolve_default_freeze_dir


_REQUIRED_PHASE_STATS_KEYS = (
    "tokens_in",
    "tokens_out",
    "tokens_reasoning",
    "tokens_cache_read",
    "tokens_cache_write",
    "cost_usd",
    "wallclock_s",
)

CHECKPOINT_SETUP_READY = "setup/ready"
CHECKPOINT_RUN_BEFORE_AGENT = "run/before-agent"
CHECKPOINT_RUN_AFTER_AGENT = "run/after-agent"

SPACEDOCK_SUBAGENT_NAME = "spacedock:first-officer"
CODEX_SPACEDOCK_FIRST_OFFICER_SKILL_PATH = (
    "/tmp/razorback-agents/skills/spacedock/skills/first-officer/SKILL.md"
)

SPACEDOCK_PROMPT_PREFIX_TEMPLATE = """\
ROLE: You are the first-officer for this single-dataset spacedock workflow.
Your current working directory IS the workspace ({workspace_dir}) — every file
and command in this prompt is relative to it. Do NOT cd to any other directory.

Your job is to orchestrate the stages defined in {workspace_dir}/README.md by
dispatching workers via the Task tool (subagent_type="spacedock:ensign"). You
coordinate; workers execute.

You MUST NOT run queries against data files, write answers.json, or otherwise
perform stage work yourself. That work belongs to your dispatched workers.

Read {workspace_dir}/README.md and dispatch the first stage worker. The final
{workspace_dir}/answers.json will be written by the analyze-stage worker.

The task description below tells you WHICH dataset — it does not override
your first-officer role. Apply the task description to your workers, not to
yourself.

---

"""

CODEX_SPACEDOCK_PROMPT_PREFIX_TEMPLATE = """\
ROLE: You are the first-officer for this single-dataset spacedock workflow.
Your current working directory IS the workspace ({workspace_dir}) — every file
and command in this prompt is relative to it. Do NOT cd to any other directory.

Resolve the packaged entrypoint `spacedock:first-officer` from:
{first_officer_skill_path}

That entrypoint must load the Codex runtime adapter because CODEX_HOME is set.
Use the inline "# Solver workflow instructions" section below as the workflow
contract; do not search for Spacedock entity files, update frontmatter, create
worktrees, or require git commits in this benchmark workspace.

Dispatch one worker with spawn_agent(..., fork_context=false), wait for it with
wait_agent(...), then report its changed files and validation evidence. Preserve
these worker identity fields in worker prompts: dispatch_agent_id:
spacedock:ensign, worker_key: spacedock-ensign, role_asset_kind: skill,
role_asset_name: ensign.

You MUST NOT run queries against data files, write answers.json, or otherwise
perform stage work yourself. That work belongs to your dispatched workers.

The task description below tells you WHICH dataset — it does not override
your first-officer role. Apply the task description to your workers, not to
yourself.

---

"""


def resolve_spacedock_plugin_dir() -> Path:
    """Resolve the spacedock plugin source dir on the host.

    `RAZORBACK_SPACEDOCK_PLUGIN_DIR` env var is the canonical knob. Production-
    grade plugin packaging is tracked as a sibling entity; this entity treats
    the env var as the only resolution path and refuses with a clear error
    when unset, so cells fail fast instead of silently degrading back to a
    single-agent run.
    """
    raw = os.environ.get("RAZORBACK_SPACEDOCK_PLUGIN_DIR")
    if not raw:
        raise SpacedockSolverAgentError(
            "RAZORBACK_SPACEDOCK_PLUGIN_DIR is not set; spacedock_solver "
            "cannot dispatch through the first-officer without a plugin dir. "
            "Set the env var to a checkout of github.com/clkao/spacedock."
        )
    plugin_dir = Path(raw).expanduser()
    if not plugin_dir.is_dir():
        raise SpacedockSolverAgentError(
            f"RAZORBACK_SPACEDOCK_PLUGIN_DIR={plugin_dir} is not a directory."
        )
    return plugin_dir


class SpacedockSolverAgentError(RazorbackError):
    """Raised on SpacedockSolverAgent contract violations."""


def assert_phase_stats_schema(path: Path, *, stages: list[str]) -> None:
    """Per §7.2, phase_stats.json carries five token fields + cost + wallclock per stage."""
    data = json.loads(Path(path).read_text())
    assert isinstance(data, dict)
    for stage in stages:
        assert stage in data, f"missing stage: {stage}"
        for k in _REQUIRED_PHASE_STATS_KEYS:
            assert k in data[stage], f"missing key {k!r} in stage {stage!r}"


class SpacedockSolverAgent(BaseAgent):
    SUPPORTS_WINDOWS = False
    SUPPORTS_ATIF = False

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        logger=None,
        mcp_servers=None,
        skills_dir=None,
        *,
        runtime: Literal["claude", "codex", "pi"],
        model: str,
        sampling: dict[str, Any],
        solver_workflow: Path | str,
        solver_workflow_content_hash: str,
        prompt_content_hashes: dict[str, str],
        spacedock_skill_version: str,
        harbor_agent_kwargs: dict[str, Any],
        max_turns: int = 200,
        tools_allowed: list[str] | None = None,
        tools_denied: list[str] | None = None,
        benchmark_kind: str | None = None,
        benchmark_task_id: str | None = None,
        batch_mode: str | None = None,
        child_task_ids_hash: str | None = None,
        resume_from_freeze: Path | str | None = None,
        extra_env: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name or model,
            logger=logger,
            mcp_servers=mcp_servers,
            skills_dir=skills_dir,
            **kwargs,
        )
        # FU-1: auth via extra_env (sourced from AgentConfig.env; redacted on disk).
        # KEEP-VERBATIM from spacedock_solver.py:76-86 (co-mingled auth refusal).
        self._extra_env = dict(extra_env or {})
        if (
            "ANTHROPIC_API_KEY" in self._extra_env
            and "CLAUDE_CODE_OAUTH_TOKEN" in self._extra_env
        ):
            raise SpacedockSolverAgentError(
                "ANTHROPIC_API_KEY and CLAUDE_CODE_OAUTH_TOKEN cannot both be set."
            )

        self._runtime = runtime
        self._model = model
        self._sampling = dict(sampling)
        self._solver_workflow = Path(solver_workflow)
        self._solver_workflow_content_hash = solver_workflow_content_hash
        self._prompt_content_hashes = dict(prompt_content_hashes)
        self._spacedock_skill_version = spacedock_skill_version
        self._harbor_agent_kwargs = dict(harbor_agent_kwargs)
        self._max_turns = max_turns
        self._tools_allowed = list(tools_allowed or [])
        self._tools_denied = list(tools_denied or [])
        discovered_identity = self._discover_task_identity_from_manifest()
        self._benchmark_kind = benchmark_kind or discovered_identity.get("benchmark_kind")
        self._benchmark_task_id = benchmark_task_id or discovered_identity.get(
            "benchmark_task_id"
        )
        self._batch_mode = batch_mode or discovered_identity.get("batch_mode")
        self._child_task_ids_hash = child_task_ids_hash or discovered_identity.get(
            "child_task_ids_hash"
        )

        # AC-2 + b5 contract point 1: compute sealed_hash from canonical inputs.
        self.sealed_hash = compute_sealed_hash(
            model=self._model,
            sampling=self._sampling,
            solver_workflow_content_hash=self._solver_workflow_content_hash,
            prompt_content_hashes=self._prompt_content_hashes,
            spacedock_skill_version=self._spacedock_skill_version,
            harbor_agent_kwargs=self._harbor_agent_kwargs,
            benchmark_kind=self._benchmark_kind,
            benchmark_task_id=self._benchmark_task_id,
            batch_mode=self._batch_mode,
            child_task_ids_hash=self._child_task_ids_hash,
        )

        # AC-2 + b5 contract point 4: refuse on cross-job resume mismatch
        # BEFORE harbor I/O. In-place harbor jobs resume mismatch is caught
        # in setup() against the per-run freeze dir.
        self._resume_from_freeze = (
            Path(resume_from_freeze) if resume_from_freeze else None
        )
        if self._resume_from_freeze is not None:
            self._refuse_on_resume_mismatch(self._resume_from_freeze)

        self._inner: BaseAgent | None = None
        self._freeze_checkpointing_ready = False

    def __repr__(self) -> str:
        # FU-1: never surface secrets in repr.
        return (
            f"SpacedockSolverAgent(runtime={self._runtime!r}, model={self._model!r}, "
            f"sealed_hash={self.sealed_hash!r})"
        )

    __str__ = __repr__

    def _refuse_on_resume_mismatch(self, freeze_dir: Path) -> None:
        """Per b5 contract point 4: read sealed_hash.txt; SeedMismatchError on mismatch."""
        sealed_file = freeze_dir / "sealed_hash.txt"
        if not sealed_file.exists():
            raise SpacedockSolverAgentError(
                f"resume_from_freeze {freeze_dir} has no sealed_hash.txt; "
                "cannot validate resume."
            )
        prior = sealed_file.read_text().strip()
        if prior != self.sealed_hash:
            raise SeedMismatchError(
                f"resume sealed_hash ({self.sealed_hash}) does not match prior "
                f"sealed_hash ({prior}). Prior freeze dir: {freeze_dir}."
            )

    @staticmethod
    def name() -> str:
        return "spacedock_solver"

    def version(self) -> str | None:
        return None

    @classmethod
    def required_env(cls) -> dict:
        return {
            "mode": "alternation",
            "names": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"],
        }

    @staticmethod
    def supported_sampling() -> set[str]:
        return {"temperature"}

    def resolve_freeze_dir(self) -> Path:
        """Per spec §4.3.4 + AC-1: sealed_hash-keyed external freeze in a CAS.

        The freeze tree lives at `<cas-root>/<sealed_hash>/` where `<cas-root>`
        resolves via `$RAZORBACK_FREEZE_DIR` → `$XDG_DATA_HOME/razorback/freeze`
        → `~/.local/share/razorback/freeze`. This is independent of any
        worktree, so:
        - `git worktree remove --force` cannot destroy freeze trees.
        - Any worktree can discover any prior freeze by sealed_hash (AC-2).
        - Re-running the same spec resumes from the existing freeze without
          re-invoking the agent (AC-5).
        """
        return resolve_default_freeze_dir() / self.sealed_hash

    @staticmethod
    def _resolve_run_dir_from_logs_dir(logs_dir: Path) -> Path:
        """Back out from harbor's per-trial logs_dir to the run-dir root."""
        p = logs_dir.resolve()
        for _ in range(6):
            p = p.parent
            if (
                (p / "_job_config.yaml").exists()
                or (p / "trials").exists()
                or (p / "spec.frozen.yaml").exists()
            ):
                return p
        # Fallback to b5 line 61's stated default (three .parent calls).
        return logs_dir.resolve().parent.parent.parent

    def _discover_task_identity_from_manifest(self) -> dict[str, str]:
        try:
            run_dir = self._resolve_run_dir_from_logs_dir(Path(self.logs_dir))
            rel = Path(self.logs_dir).resolve().relative_to(run_dir.resolve())
        except Exception:
            return {}
        if not rel.parts:
            return {}
        if rel.parts[0] == "trials" and len(rel.parts) >= 2:
            trial_name = rel.parts[1]
        else:
            trial_name = rel.parts[0]
        trial_prefix = trial_name.split("__", 1)[0]
        views_root = run_dir / "_razorback" / "task_views"
        if not views_root.is_dir():
            return {}
        for manifest_path in sorted(views_root.glob("*/view_manifest.json")):
            view_prefix = manifest_path.parent.name[:32].rstrip("_-")
            if view_prefix != trial_prefix:
                continue
            try:
                payload = json.loads(manifest_path.read_text())
            except (OSError, json.JSONDecodeError):
                return {}
            out: dict[str, str] = {}
            for key in ("benchmark_kind", "benchmark_task_id", "child_task_ids_hash"):
                value = payload.get(key)
                if value is not None:
                    out[key] = str(value)
            out.setdefault("batch_mode", str(payload.get("batch_mode") or "per-task"))
            return out
        return {}

    async def _host_git(self, *args: str) -> None:
        # freeze tree is host-side bookkeeping; git runs on host
        freeze_dir = self.resolve_freeze_dir()
        argv = ("git", "-C", str(freeze_dir), *args)
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise SpacedockSolverAgentError(
                f"freeze repo git failed at: {' '.join(argv)} "
                f"(rc={proc.returncode}); stderr={stderr.decode(errors='replace')!r}"
            )

    async def _commit_stage(
        self, environment: BaseEnvironment, stage: str
    ) -> None:
        """Per-stage commit helper exposed for the workflow's freeze mod."""
        # freeze tree is host-side bookkeeping; git runs on host
        await self._host_git("add", "-A")
        await self._host_git(
            "commit", "-q", "--allow-empty", "-m", f"stage: {stage}"
        )

    def _build_inner_agent(self) -> BaseAgent:
        """Dispatch to the per-runtime adapter sub-module (spec §8.4).

        For runtime=claude the spacedock variant threads `sub_agent` +
        `plugin_dirs` so the inner `claude` CLI loads the spacedock plugin
        and enters first-officer mode. For runtime=codex the adapter stages the
        same plugin into Codex's skills surface and enables multi_agent; Codex
        enters FO mode from the prompt because it has no Claude-style --agent
        flag. Pi is unchanged.
        """
        from razorback.agents._runtime import claude as _claude
        from razorback.agents._runtime import codex as _codex
        from razorback.agents._runtime import pi as _pi

        if self._runtime == "claude":
            plugin_dir = resolve_spacedock_plugin_dir()
            return _claude.build_inner_agent(
                logs_dir=self.logs_dir,
                model=self._model,
                harbor_agent_kwargs=self._harbor_agent_kwargs,
                extra_env=self._extra_env,
                plugin_dirs=[plugin_dir],
                sub_agent=SPACEDOCK_SUBAGENT_NAME,
            )

        if self._runtime == "codex":
            plugin_dir = resolve_spacedock_plugin_dir()
            return _codex.build_inner_agent(
                logs_dir=self.logs_dir,
                model=self._model,
                harbor_agent_kwargs=self._harbor_agent_kwargs,
                extra_env=self._extra_env,
                enable_multi_agent=True,
                spacedock_plugin_dirs=[plugin_dir],
            )

        builders = {
            "pi": _pi.build_inner_agent,
        }
        builder = builders[self._runtime]
        return builder(
            logs_dir=self.logs_dir,
            model=self._model,
            harbor_agent_kwargs=self._harbor_agent_kwargs,
            extra_env=self._extra_env,
        )

    def _solver_workflow_readme_text(self) -> str:
        readme = self._solver_workflow / "README.md"
        if not readme.is_file():
            raise SpacedockSolverAgentError(
                f"solver workflow README.md not found: {readme}"
            )
        return readme.read_text()

    def _compose_run_instruction(self, instruction: str) -> str:
        workflow_text = self._solver_workflow_readme_text().strip()
        # Workspace path inside harbor's trial environment. Harbor's claude_code
        # adapter reports /workspace; harbor's Codex path runs in /app.
        workspace_dir = "/app" if self._runtime == "codex" else "/workspace"
        role_prefix = ""
        if self._runtime == "claude":
            role_prefix = SPACEDOCK_PROMPT_PREFIX_TEMPLATE.format(
                workspace_dir=workspace_dir
            )
        elif self._runtime == "codex":
            role_prefix = CODEX_SPACEDOCK_PROMPT_PREFIX_TEMPLATE.format(
                workspace_dir=workspace_dir,
                first_officer_skill_path=CODEX_SPACEDOCK_FIRST_OFFICER_SKILL_PATH,
            )
        return (
            f"{role_prefix}"
            "# Solver workflow instructions\n\n"
            f"{workflow_text}\n\n"
            "# Task instruction\n\n"
            f"{instruction}"
        )

    async def setup(self, environment: BaseEnvironment) -> None:
        """Per spec §8.4: bootstrap workspace; write sealed_hash.txt; delegate to inner.

        First-stage path: create freeze dir, git init, write sealed_hash.txt.
        Resume path (sealed_hash.txt exists with matching hash): restore from .git.
        Resume mismatch: SeedMismatchError (exit 20).
        """
        freeze_dir = self.resolve_freeze_dir()
        sealed_file = freeze_dir / "sealed_hash.txt"

        # freeze tree is host-side bookkeeping; git runs on host
        if sealed_file.exists():
            prior = sealed_file.read_text().strip()
            if prior != self.sealed_hash:
                raise SeedMismatchError(
                    f"freeze dir {freeze_dir} sealed_hash ({prior}) does not match "
                    f"this agent's sealed_hash ({self.sealed_hash})."
                )
            await self._host_git("checkout", "--", ".")
        else:
            freeze_dir.mkdir(parents=True, exist_ok=True)
            sealed_file.write_text(self.sealed_hash)
            await self._host_git("init", "-q")
            await self._host_git("config", "user.email", "razorback@local")
            await self._host_git("config", "user.name", "razorback")
            await self._host_git("config", "commit.gpgsign", "false")
            await self._host_git("add", "-A")
            await self._host_git("commit", "-q", "--allow-empty", "-m", "seed")

        self._freeze_checkpointing_ready = True
        await self._commit_stage(environment, CHECKPOINT_SETUP_READY)
        await self._run_ade_workspace_preflight(environment)

        if self._inner is None:
            self._inner = self._build_inner_agent()
        await self._inner.setup(environment)

    async def _run_ade_workspace_preflight(self, environment: BaseEnvironment) -> None:
        if self._benchmark_kind != "ade-bench" or not self._benchmark_task_id:
            return

        delimiter = "RAZORBACK_ADE_PREFLIGHT_PY"
        command = (
            f"cat >/tmp/razorback_ade_preflight.py <<'{delimiter}'\n"
            f"{preflight_script_text()}\n"
            f"{delimiter}\n"
            "python /tmp/razorback_ade_preflight.py "
            f"--task-id {shlex.quote(self._benchmark_task_id)} --workspace /app"
        )
        result = await environment.exec(command, timeout_sec=120)
        if result.return_code == 0:
            return

        output = "\n".join(
            part.strip()
            for part in (
                getattr(result, "stdout", None),
                getattr(result, "stderr", None),
            )
            if part and part.strip()
        )
        raise SpacedockSolverAgentError(
            "ADE workspace preflight failed before codex exec/agent runtime "
            f"for task {self._benchmark_task_id}: {output}"
        )

    async def run(self, instruction, environment, context):
        if self._inner is None:
            raise SpacedockSolverAgentError("run() called before setup()")
        if self._freeze_checkpointing_ready:
            await self._commit_stage(environment, CHECKPOINT_RUN_BEFORE_AGENT)
        try:
            await self._inner.run(
                self._compose_run_instruction(instruction), environment, context
            )
        finally:
            # Emit dispatch evidence even when the inner runtime times out while
            # waiting on a worker. Harbor still runs the verifier after agent
            # timeout, and the smoke gate needs the parent JSONL dispatch trace.
            if self._runtime in {"claude", "codex"}:
                self._maybe_write_subagent_trace_manifest()
        if self._freeze_checkpointing_ready:
            await self._commit_stage(environment, CHECKPOINT_RUN_AFTER_AGENT)
        # AC-2 manifest write lives in the finally block above because harbor's
        # trial runner invokes only `setup` and `run` on `BaseAgent` subclasses;
        # `populate_context_post_run` is gated to `BaseInstalledAgent`
        # (harbor/trial/trial.py:466-471) and `cleanup` is not part of the
        # BaseAgent lifecycle at all. Follow-up `m2
        # spacedock-solver-base-installed-agent-feasibility` may relocate
        # this hook once SpacedockSolverAgent graduates to BaseInstalledAgent.

    async def cleanup(self, environment):
        # `cleanup()` is NOT part of harbor's BaseAgent lifecycle (the trial
        # runner never calls it on the outer agent). Kept only as an inner-
        # agent delegate for any other path that might call it; do NOT add
        # post-run side effects here — they belong in `run()`.
        if self._inner is not None and hasattr(self._inner, "cleanup"):
            await self._inner.cleanup(environment)

    def _maybe_write_subagent_trace_manifest(self) -> None:
        """Emit a per-cell subagent-trace-manifest.json next to provenance.yaml.

        AC-2: every spacedock-variant cell writes a manifest carrying the count
        of dispatch events from the inner runtime session.

        Resolution: harbor's `TrialPaths.agent_dir` is `<trial-dir>/agent`,
        and during run() the contents are still at that pre-relocation
        location (the trial runner relocates into `steps/<step>/agent/`
        after our `run()` returns — harbor/trial/trial.py:673). The
        trials-job dir (where `provenance.yaml` lives and where the matrix
        dispatcher's smoke validator expects the manifest) is one level
        above the per-trial dir, i.e. `logs_dir.parents[1]`.
        """
        from razorback.agents.subagent_traces import (
            write_subagent_trace_manifest,
        )

        try:
            logs_dir = Path(self.logs_dir).resolve()
            cell_run_dir = logs_dir.parents[1]
            write_subagent_trace_manifest(cell_run_dir)
        except (FileNotFoundError, IndexError, OSError) as exc:
            self.logger.debug(
                f"subagent-trace-manifest write skipped: {exc}"
            )

    def populate_context_post_run(self, context):
        """Delegate context-population to the inner agent.

        Harbor's trial runner gates this hook on
        `isinstance(self._agent, BaseInstalledAgent)`
        (harbor/trial/trial.py:466-471), so it is NOT called on
        `SpacedockSolverAgent` (which subclasses `BaseAgent` directly).
        Kept as an inner-agent delegate for any path that does invoke it;
        the AC-2 manifest write lives in `run()` instead.
        """
        if self._inner is not None and hasattr(
            self._inner, "populate_context_post_run"
        ):
            self._inner.populate_context_post_run(context)
