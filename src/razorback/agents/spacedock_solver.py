# ABOUTME: SpacedockSolverAgent (§6.2 third bullet) — staged solver with halt-resume.
# ABOUTME: __init__ recomputes sealed_hash and refuses on mismatch BEFORE any harbor I/O.

from pathlib import Path
from typing import Any

import yaml

from harbor.agents.base import BaseAgent

from razorback.agents.seal import compute_sealed_hash
from razorback.errors import RazorbackError, SeedMismatchError


class SpacedockSolverAgentError(RazorbackError):
    """Raised on SpacedockSolverAgent contract violations."""


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
        model: str,
        sampling: dict[str, Any],
        stages: list[str],
        tools_allowed: list[str],
        prompts: dict[str, str],
        sealed_hash: str,
        resolved_auth_env: dict[str, str],
        prompt_contents: dict[str, str] | None = None,
        prior_frozen_spec_path: Path | str | None = None,
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
        self._model = model
        self._sampling = dict(sampling)
        self._stages = list(stages)
        self._tools_allowed = list(tools_allowed)
        self._prompts = dict(prompts)
        self.sealed_hash = sealed_hash
        self._resolved_auth_env = dict(resolved_auth_env)
        self._prompt_contents = dict(prompt_contents) if prompt_contents else {}
        self._exec_env: dict[str, str] = {}
        self._phase_stats: dict[str, dict] = {}

        # AC-1: BEFORE harbor I/O — refuse on sealed-hash mismatch.
        self._refuse_on_resume_mismatch(
            Path(prior_frozen_spec_path) if prior_frozen_spec_path else None
        )

    def _refuse_on_resume_mismatch(self, prior_frozen_spec_path: Path | None) -> None:
        if prior_frozen_spec_path is None:
            return
        prior = yaml.safe_load(Path(prior_frozen_spec_path).read_text())
        prior_agent = prior.get("agent", {})
        prior_sealed = prior_agent.get("sealed_hash")
        if prior_sealed is None:
            raise SpacedockSolverAgentError(
                f"prior frozen spec at {prior_frozen_spec_path} has no agent.sealed_hash — "
                "cannot validate resume."
            )
        # Recompute the sealed_hash from kwargs to detect tampered (sealed_hash, prompts) pairs.
        recomputed = compute_sealed_hash(
            model=self._model,
            sampling=self._sampling,
            stages=self._stages,
            prompt_hashes={
                k: v for k, v in self._prompts.items() if v.startswith("sha256:")
            },
        )
        if recomputed != self.sealed_hash:
            raise SeedMismatchError(
                f"resume spec's recomputed sealed_hash ({recomputed}) does not match "
                f"its declared sealed_hash ({self.sealed_hash}). "
                "Tampered or stale frozen spec."
            )
        if self.sealed_hash != prior_sealed:
            drifted = self._find_drifted_field(prior_agent)
            raise SeedMismatchError(
                f"resume sealed_hash ({self.sealed_hash}) does not match prior seed run "
                f"sealed_hash ({prior_sealed}). Drifted field: {drifted}. "
                f"Prior frozen spec: {prior_frozen_spec_path}"
            )

    def _find_drifted_field(self, prior_agent: dict[str, Any]) -> str:
        if prior_agent.get("model") != self._model:
            return f"model (seed={prior_agent.get('model')!r}, resume={self._model!r})"
        if prior_agent.get("sampling") != self._sampling:
            return "sampling"
        if list(prior_agent.get("stages", [])) != self._stages:
            return "stages"
        prior_prompts = prior_agent.get("prompts", {})
        for name, my_hash in self._prompts.items():
            if not my_hash.startswith("sha256:"):
                continue
            if prior_prompts.get(name) != my_hash:
                return f"prompts.{name}"
        return "sealed_hash"

    @staticmethod
    def name() -> str:
        return "spacedock-solver"

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

    async def setup(self, environment) -> None:
        raise NotImplementedError("Task 4 implements setup()")

    async def run(self, instruction, environment, context) -> None:
        raise NotImplementedError("Task 5 implements run()")
