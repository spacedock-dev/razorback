# ABOUTME: ClaudeCliAgent (§6.2) — wraps `claude -p`. setup() validates auth & CLI presence;
# ABOUTME: run() emits one claude invocation per trial; version() parses `claude --version`.

import subprocess
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from razorback.agents.claude_invoke import DEFAULT_ALLOWED_TOOLS, build_claude_argv
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.errors import RazorbackError


class ClaudeCliAgentError(RazorbackError):
    """Raised on ClaudeCliAgent contract violations (e.g. co-mingled auth)."""


class ClaudeCliAgent(BaseAgent):
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
        tools_allowed: list[str] | None = None,
        sampling_temperature: float | None = None,
        extra_env: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name,
            logger=logger,
            mcp_servers=mcp_servers,
            skills_dir=skills_dir,
            **kwargs,
        )
        # FU-1 AC-1/AC-2: auth arrives via harbor's `extra_env` kwarg (resolved from
        # AgentConfig.env at agent-factory time — see harbor.agents.factory). The
        # env field is serialized to disk via templatize_sensitive_env, so the
        # literal value never persists. The constructor still validates that at
        # most one credential is forwarded (refusing co-mingled auth).
        env = dict(extra_env or {})
        if "ANTHROPIC_API_KEY" in env and "CLAUDE_CODE_OAUTH_TOKEN" in env:
            raise ClaudeCliAgentError(
                "ANTHROPIC_API_KEY and CLAUDE_CODE_OAUTH_TOKEN cannot both be set."
            )
        self._extra_env = env
        self._tools_allowed = (
            list(tools_allowed) if tools_allowed else list(DEFAULT_ALLOWED_TOOLS)
        )
        self._sampling_temperature = sampling_temperature
        self._exec_env: dict[str, str] = {}
        self._version_cache: str | None = None

    @staticmethod
    def name() -> str:
        return "claude-cli"

    def version(self) -> str | None:
        """AC-4: parse `claude --version`'s stdout. Cached on the instance."""
        if self._version_cache is not None:
            return self._version_cache
        try:
            result = subprocess.run(
                ["claude", "--version"], capture_output=True, text=True, timeout=10
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        self._version_cache = result.stdout.strip()
        return self._version_cache

    @classmethod
    def required_env(cls) -> dict:
        """AC-1: alternation declaration — ANTHROPIC_API_KEY OR CLAUDE_CODE_OAUTH_TOKEN."""
        return {
            "mode": "alternation",
            "names": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"],
        }

    @staticmethod
    def supported_sampling() -> set[str]:
        """AC-5: Anthropic models honor temperature only. No seed, no top_p."""
        return {"temperature"}

    async def setup(self, environment: BaseEnvironment) -> None:
        """AC-2 — build the exec env dict (auth + proxy block); validate `claude` binary."""
        result = await environment.exec("claude --version")
        if result.return_code != 0:
            raise ClaudeCliAgentError(
                "claude CLI not available inside the container "
                f"(exit={result.return_code}, stderr={getattr(result, 'stderr', '')!r})"
            )
        self._exec_env = {**PROXY_BLOCK_ENV, **self._extra_env}

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        """One `claude -p <instruction>` per trial."""
        cmd = build_claude_argv(
            prompt=instruction,
            model=self.model_name,
            tools_allowed=self._tools_allowed,
        )
        await environment.exec(cmd, env=self._exec_env, timeout_sec=600)
