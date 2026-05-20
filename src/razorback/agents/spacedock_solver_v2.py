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

    async def setup(self, environment: BaseEnvironment) -> None:
        """Stub setup; full lifecycle wiring lands in Task 5."""
        raise NotImplementedError("setup() lands in Task 5")

    async def run(self, instruction, environment, context):
        if self._inner is None:
            raise SpacedockSolverAgentError("run() called before setup()")
        await self._inner.run(instruction, environment, context)

    async def cleanup(self, environment):
        if self._inner is not None and hasattr(self._inner, "cleanup"):
            await self._inner.cleanup(environment)
