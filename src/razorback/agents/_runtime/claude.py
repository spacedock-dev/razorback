# ABOUTME: Claude runtime adapter for SpacedockSolverAgent (spec §4.3.1, §8.4).
# ABOUTME: Builds RazorbackClaudeCode (a ClaudeCode subclass) so the inner agent
# ABOUTME: emits cost_usd + claude-output.jsonl via PKG-26's surface.

import shlex
from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.models.agent.context import AgentContext

from razorback.agents.claude_invoke import DEFAULT_ALLOWED_TOOLS, DISALLOWED_TOOLS
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.agents.spacedock_solver import SpacedockSolverAgentError
from razorback.errors import RazorbackError


class RazorbackClaudeCodeError(RazorbackError):
    """Raised on RazorbackClaudeCode contract violations."""


class RazorbackClaudeCode(ClaudeCode):
    """ClaudeCode runtime helper with Razorback auth, tool policy, and telemetry."""

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
        plugin_dirs: list[Path | str] | None = None,
        sub_agent: str | None = None,
        **kwargs: Any,
    ) -> None:
        env = dict(extra_env or {})
        if "ANTHROPIC_API_KEY" in env and "CLAUDE_CODE_OAUTH_TOKEN" in env:
            raise RazorbackClaudeCodeError(
                "ANTHROPIC_API_KEY and CLAUDE_CODE_OAUTH_TOKEN cannot both be set."
            )

        self._tools_allowed = (
            list(tools_allowed) if tools_allowed else list(DEFAULT_ALLOWED_TOOLS)
        )
        self._sampling_temperature = sampling_temperature
        self._plugin_dirs = [str(p) for p in (plugin_dirs or [])]
        self._sub_agent = sub_agent

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

        self._razorback_extra_env = env
        self._exec_env: dict[str, str] = {}

    def build_cli_flags(self) -> str:
        base = super().build_cli_flags()
        extras: list[str] = []
        for path in self._plugin_dirs:
            extras.append(f"--plugin-dir {path}")
        if self._sub_agent:
            extras.append(f"--agent {self._sub_agent}")
        if not extras:
            return base
        return f"{base} {' '.join(extras)}" if base else " ".join(extras)

    @staticmethod
    def name() -> str:
        return "claude-cli"

    @classmethod
    def required_env(cls) -> dict:
        return {
            "mode": "alternation",
            "names": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"],
        }

    @staticmethod
    def supported_sampling() -> set[str]:
        return {"temperature"}

    async def run(self, instruction: str, environment, context):
        import os

        saved: dict[str, str | None] = {}
        try:
            for key, value in self._razorback_extra_env.items():
                saved[key] = os.environ.get(key)
                os.environ[key] = value
            await super().run(instruction, environment, context)
        finally:
            for key, old in saved.items():
                if old is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old

    async def setup(self, environment) -> None:
        result = await environment.exec("claude --version")
        if result.return_code != 0:
            raise RazorbackClaudeCodeError(
                "claude CLI not available inside the container "
                f"(exit={result.return_code}, stderr={getattr(result, 'stderr', '')!r})"
            )
        self._exec_env = {**PROXY_BLOCK_ENV, **self._razorback_extra_env}
        try:
            self._version = result.stdout.strip() if hasattr(result, "stdout") else None
        except Exception:
            self._version = None
        await self._stage_plugin_dirs(environment)

    async def _stage_plugin_dirs(self, environment) -> None:
        """Upload each host-side plugin_dir into the agent container.

        `--plugin-dir <path>` must resolve INSIDE the trial environment where
        `claude` runs. The constructor accepts host paths; setup stages them to
        an in-container path that is then substituted on every flag render.
        Without this step the host path leaks into a docker container that
        cannot see it, and claude refuses to load the plugin.
        """
        if not self._plugin_dirs or not hasattr(environment, "upload_dir"):
            return
        staged: list[str] = []
        for host_path in self._plugin_dirs:
            host = Path(host_path)
            if not host.is_dir():
                raise RazorbackClaudeCodeError(
                    f"plugin_dir {host} is not a host directory; cannot stage."
                )
            container_path = f"/tmp/razorback-plugins/{host.name}"
            await environment.exec(f"mkdir -p /tmp/razorback-plugins")
            await environment.upload_dir(str(host), container_path)
            staged.append(container_path)
        self._plugin_dirs = staged

    def populate_context_post_run(self, context: AgentContext) -> None:
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


_CLAUDE_SUPPORTED_KWARGS = {
    descriptor.kwarg
    for descriptor in [*ClaudeCode.CLI_FLAGS, *getattr(ClaudeCode, "ENV_VARS", [])]
} | {"skills_dir", "tools_allowed", "tools_denied"}


def build_inner_agent(
    *,
    logs_dir: Path,
    model: str,
    harbor_agent_kwargs: dict[str, Any],
    extra_env: dict[str, str],
    plugin_dirs: list[Path | str] | None = None,
    sub_agent: str | None = None,
) -> RazorbackClaudeCode:
    """Construct razorback's ClaudeCode runtime helper for spacedock_solver.

    Routing through RazorbackClaudeCode (rather than harbor's ClaudeCode directly)
    inherits PKG-26's cost-emit + claude-output.jsonl audit sentinel. The earlier
    path returned harbor.ClaudeCode directly and silently dropped cost telemetry
    even when paid-API auth was in use.

    tools_allowed flows through RazorbackClaudeCode's own param (not harbor's
    allowed_tools kwarg) so the subclass applies its DEFAULT_ALLOWED_TOOLS/
    DISALLOWED_TOOLS policy consistently. Drops None values so harbor uses its
    own defaults.
    """
    kw: dict[str, Any] = {}
    for name, value in harbor_agent_kwargs.items():
        if _is_empty_noop(name, value):
            continue
        if name not in _CLAUDE_SUPPORTED_KWARGS:
            raise SpacedockSolverAgentError(
                "claude runtime adapter cannot honor unsupported harbor_agent_kwargs "
                f"field {name!r}; refusing to silently drop it."
            )
        if name == "tools_allowed":
            kw["tools_allowed"] = list(value)
            continue
        if name == "tools_denied":
            # RazorbackClaudeCode applies DISALLOWED_TOOLS by default; callers
            # that need a wider block list pass through harbor's disallowed_tools.
            kw["disallowed_tools"] = ",".join(value)
            continue
        kw[name] = value
    if plugin_dirs:
        kw["plugin_dirs"] = list(plugin_dirs)
    if sub_agent:
        kw["sub_agent"] = sub_agent
    return RazorbackClaudeCode(
        logs_dir=Path(logs_dir),
        model_name=model,
        extra_env=dict(extra_env or {}),
        **kw,
    )


def _is_empty_noop(name: str, value: Any) -> bool:
    if value is None:
        return True
    if name in {"tools_allowed", "tools_denied"} and value == []:
        return True
    return False
