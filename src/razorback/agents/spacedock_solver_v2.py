# ABOUTME: SpacedockSolverAgent v2 (spec §4 + §8.4), runtime adapter for claude|codex|pi.
# ABOUTME: __init__ computes sealed_hash from six inputs; refuses on resume mismatch BEFORE harbor I/O.

import json
from pathlib import Path
from typing import Any, Literal

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment

from razorback.agents.seal import compute_sealed_hash, prompt_sha256  # noqa: F401
from razorback.errors import RazorbackError, SeedMismatchError


_REQUIRED_PHASE_STATS_KEYS = (
    "tokens_in",
    "tokens_out",
    "tokens_reasoning",
    "tokens_cache_read",
    "tokens_cache_write",
    "cost_usd",
    "wallclock_s",
)

_FREEZE_REPO_GIT_REQUIREMENT = "git is required for the sealed freeze repo"


class SpacedockSolverAgentError(RazorbackError):
    """Raised on SpacedockSolverAgent v2 contract violations."""


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

        # AC-2 + b5 contract point 1: compute sealed_hash from six inputs.
        self.sealed_hash = compute_sealed_hash(
            model=self._model,
            sampling=self._sampling,
            solver_workflow_content_hash=self._solver_workflow_content_hash,
            prompt_content_hashes=self._prompt_content_hashes,
            spacedock_skill_version=self._spacedock_skill_version,
            harbor_agent_kwargs=self._harbor_agent_kwargs,
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
        return "spacedock-solver-v2"

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
        """Per b5 contract point 2 + spec §4.3.4: sealed_hash-keyed external freeze.

        Harbor's per-trial logs_dir is <run-dir>/trials/<trial_name>/logs/agent/.
        Walk up until we find the run-dir sentinel (spec.frozen.yaml or trials/).
        The freeze tree lives at <run-dir>/_razorback/freeze/<sealed_hash>/,
        outside the trial subtree that harbor jobs resume rmtree's.
        """
        run_dir = self._resolve_run_dir_from_logs_dir(Path(self.logs_dir))
        return run_dir / "_razorback" / "freeze" / self.sealed_hash

    @staticmethod
    def _resolve_run_dir_from_logs_dir(logs_dir: Path) -> Path:
        """Back out from harbor's per-trial logs_dir to the run-dir root."""
        p = logs_dir.resolve()
        for _ in range(6):
            p = p.parent
            if (p / "trials").exists() or (p / "spec.frozen.yaml").exists():
                return p
        # Fallback to b5 line 61's stated default (three .parent calls).
        return logs_dir.resolve().parent.parent.parent

    async def _commit_stage(
        self, environment: BaseEnvironment, stage: str
    ) -> None:
        """Per-stage commit helper exposed for the workflow's freeze mod."""
        freeze_dir = self.resolve_freeze_dir()
        for cmd in (
            f"git -C {freeze_dir} add -A",
            f"git -C {freeze_dir} commit -q --allow-empty -m 'stage: {stage}'",
        ):
            r = await environment.exec(cmd)
            if r.return_code != 0:
                raise SpacedockSolverAgentError(
                    f"freeze stage commit failed at: {cmd} (rc={r.return_code})"
                )

    async def _ensure_freeze_repo_git(self, environment: BaseEnvironment) -> None:
        r = await environment.exec("command -v git >/dev/null 2>&1")
        if r.return_code == 0:
            return

        installers = (
            (
                "apk",
                "command -v apk >/dev/null 2>&1",
                "apk add --no-cache git",
            ),
            (
                "apt-get",
                "command -v apt-get >/dev/null 2>&1",
                "DEBIAN_FRONTEND=noninteractive apt-get update -qq && "
                "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git",
            ),
            (
                "yum",
                "command -v yum >/dev/null 2>&1",
                "yum install -y git",
            ),
        )

        for name, probe_cmd, install_cmd in installers:
            probe = await environment.exec(probe_cmd)
            if probe.return_code != 0:
                continue
            install = await environment.exec(install_cmd)
            if install.return_code != 0:
                raise SpacedockSolverAgentError(
                    f"{_FREEZE_REPO_GIT_REQUIREMENT}; installing via {name} "
                    f"failed (rc={install.return_code})."
                )
            verify = await environment.exec("command -v git >/dev/null 2>&1")
            if verify.return_code == 0:
                return
            raise SpacedockSolverAgentError(
                f"{_FREEZE_REPO_GIT_REQUIREMENT}; installing via {name} "
                f"completed but git is still unavailable (rc={verify.return_code})."
            )

        raise SpacedockSolverAgentError(
            f"{_FREEZE_REPO_GIT_REQUIREMENT}; no supported package manager "
            "(apk, apt-get, yum) found."
        )

    def _build_inner_agent(self) -> BaseAgent:
        """Dispatch to the per-runtime adapter sub-module (spec §8.4)."""
        from razorback.agents._runtime import claude as _claude
        from razorback.agents._runtime import codex as _codex
        from razorback.agents._runtime import pi as _pi

        builders = {
            "claude": _claude.build_inner_agent,
            "codex": _codex.build_inner_agent,
            "pi": _pi.build_inner_agent,
        }
        builder = builders[self._runtime]
        return builder(
            logs_dir=self.logs_dir,
            model=self._model,
            harbor_agent_kwargs=self._harbor_agent_kwargs,
            extra_env=self._extra_env,
        )

    async def setup(self, environment: BaseEnvironment) -> None:
        """Per spec §8.4: bootstrap workspace; write sealed_hash.txt; delegate to inner.

        First-stage path: create freeze dir, git init, write sealed_hash.txt.
        Resume path (sealed_hash.txt exists with matching hash): restore from .git.
        Resume mismatch: SeedMismatchError (exit 20).
        """
        freeze_dir = self.resolve_freeze_dir()
        sealed_file = freeze_dir / "sealed_hash.txt"

        await self._ensure_freeze_repo_git(environment)

        if sealed_file.exists():
            prior = sealed_file.read_text().strip()
            if prior != self.sealed_hash:
                raise SeedMismatchError(
                    f"freeze dir {freeze_dir} sealed_hash ({prior}) does not match "
                    f"this agent's sealed_hash ({self.sealed_hash})."
                )
            r = await environment.exec(f"git -C {freeze_dir} checkout -- .")
            if r.return_code != 0:
                raise SpacedockSolverAgentError(
                    f"resume restore via git checkout failed at {freeze_dir} "
                    f"(rc={r.return_code})"
                )
        else:
            freeze_dir.mkdir(parents=True, exist_ok=True)
            sealed_file.write_text(self.sealed_hash)
            for cmd in (
                f"git -C {freeze_dir} init -q",
                f"git -C {freeze_dir} config user.email razorback@local",
                f"git -C {freeze_dir} config user.name razorback",
                f"git -C {freeze_dir} config commit.gpgsign false",
                f"git -C {freeze_dir} add -A",
                f"git -C {freeze_dir} commit -q --allow-empty -m seed",
            ):
                r = await environment.exec(cmd)
                if r.return_code != 0:
                    raise SpacedockSolverAgentError(
                        f"freeze repo init failed at: {cmd} (rc={r.return_code})"
                    )

        if self._inner is None:
            self._inner = self._build_inner_agent()
        await self._inner.setup(environment)

    async def run(self, instruction, environment, context):
        if self._inner is None:
            raise SpacedockSolverAgentError("run() called before setup()")
        await self._inner.run(instruction, environment, context)

    async def cleanup(self, environment):
        if self._inner is not None and hasattr(self._inner, "cleanup"):
            await self._inner.cleanup(environment)
