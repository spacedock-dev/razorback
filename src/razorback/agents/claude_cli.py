# ABOUTME: ClaudeCliAgent (§6.2) — subclasses harbor's ClaudeCode so razorback's
# ABOUTME: claude-cli kind inherits stream-json invocation, cost parsing, and ATIF.

import shlex
from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.models.agent.context import AgentContext

from razorback.agents.claude_invoke import DEFAULT_ALLOWED_TOOLS, DISALLOWED_TOOLS
from razorback.errors import RazorbackError


class ClaudeCliAgentError(RazorbackError):
    """Raised on ClaudeCliAgent contract violations (e.g. co-mingled auth)."""


class ClaudeCliAgent(ClaudeCode):
    SUPPORTS_WINDOWS = False

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
        env = dict(extra_env or {})
        if "ANTHROPIC_API_KEY" in env and "CLAUDE_CODE_OAUTH_TOKEN" in env:
            raise ClaudeCliAgentError(
                "ANTHROPIC_API_KEY and CLAUDE_CODE_OAUTH_TOKEN cannot both be set."
            )

        self._tools_allowed = (
            list(tools_allowed) if tools_allowed else list(DEFAULT_ALLOWED_TOOLS)
        )
        self._sampling_temperature = sampling_temperature

        kwargs.setdefault("allowed_tools", ",".join(self._tools_allowed))
        # Harbor's build_cli_flags emits CLI flag values UNQUOTED. The razorback
        # block list contains shell-active parens (e.g. `Bash(curl *)`); pre-
        # shell-quote the whole CSV so the rendered command parses correctly.
        kwargs.setdefault(
            "disallowed_tools", shlex.quote(",".join(DISALLOWED_TOOLS))
        )

        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name,
            logger=logger,
            mcp_servers=mcp_servers,
            skills_dir=skills_dir,
            extra_env=env,
            **kwargs,
        )

        # Razorback-side mirror of extra_env (harbor stores it on _extra_env;
        # tests inspect agent._exec_env after setup() — see setup() override).
        self._razorback_extra_env = env
        self._exec_env: dict[str, str] = {}

    @staticmethod
    def name() -> str:
        return "claude-cli"

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

    async def run(self, instruction: str, environment, context):
        """Stamp the razorback-resolved auth env into os.environ before delegating
        to harbor's ClaudeCode.run(). Harbor reads ANTHROPIC_API_KEY etc. directly
        from os.environ at line 1024 of claude_code.py; razorback's contract puts
        the resolved auth on the agent via extra_env, so we bridge.
        """
        import os

        saved: dict[str, str | None] = {}
        try:
            for k, v in self._razorback_extra_env.items():
                saved[k] = os.environ.get(k)
                os.environ[k] = v
            await super().run(instruction, environment, context)
        finally:
            for k, old in saved.items():
                if old is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = old

    async def setup(self, environment) -> None:
        """Validate the `claude` binary, then materialize razorback's exec env.

        Harbor's BaseInstalledAgent.setup() does an install + auto-detect via
        get_version_command(). For razorback's claude-cli historical contract
        we just need `claude --version` to succeed inside the environment plus
        the proxy block stamped onto _exec_env for the legacy test surface.
        """
        from razorback.agents.proxy import PROXY_BLOCK_ENV

        result = await environment.exec("claude --version")
        if result.return_code != 0:
            raise ClaudeCliAgentError(
                "claude CLI not available inside the container "
                f"(exit={result.return_code}, stderr={getattr(result, 'stderr', '')!r})"
            )
        self._exec_env = {**PROXY_BLOCK_ENV, **self._razorback_extra_env}
        try:
            self._version = result.stdout.strip() if hasattr(result, "stdout") else None
        except Exception:
            self._version = None

    def populate_context_post_run(self, context: AgentContext) -> None:
        """Inherit harbor's trajectory + cost flow; then publish razorback's
        ``claude-output.jsonl`` audit sentinel by symlinking harbor's
        ``claude-code.txt`` (the stream-json tee from claude_code.py:1144-1155).

        See ``src/razorback/audit/taint.py:46`` for the sentinel contract.
        """
        super().populate_context_post_run(context)
        claude_code_txt = self.logs_dir / "claude-code.txt"
        claude_output_jsonl = self.logs_dir / "claude-output.jsonl"
        if claude_code_txt.exists() and not claude_output_jsonl.exists():
            try:
                claude_output_jsonl.symlink_to(claude_code_txt.name)
            except OSError:
                try:
                    import shutil

                    shutil.copyfile(claude_code_txt, claude_output_jsonl)
                except OSError as exc:
                    self.logger.debug(
                        f"Failed to publish claude-output.jsonl sentinel: {exc}"
                    )
