# ABOUTME: Codex runtime adapter for SpacedockSolverAgent (spec §4.3.1, §8.4).
# ABOUTME: Constructs harbor's Codex agent and fails closed on unsupported controls.

import shlex
from pathlib import Path
from typing import Any

from harbor.agents.installed.codex import Codex
from harbor.environments.base import BaseEnvironment

from razorback.agents.public_lookup_guard import (
    CODEX_SHELL_GUARD_COMMANDS,
    codex_pretooluse_guard_script,
    codex_shell_guard_script,
    codex_shell_wrapper_script,
    is_forbidden_public_lookup_command,
)
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.agents.spacedock_solver import SpacedockSolverAgentError


_CODEX_SUPPORTED_KWARGS = {
    descriptor.kwarg
    for descriptor in [*Codex.CLI_FLAGS, *getattr(Codex, "ENV_VARS", [])]
}

CODEX_SPACEDOCK_REMOTE_SKILLS_DIR = "/tmp/razorback-agents/skills"
CODEX_SPACEDOCK_PLUGIN_NAMESPACE = "spacedock"
CODEX_SPACEDOCK_FIRST_OFFICER_SKILL_PATH = (
    f"{CODEX_SPACEDOCK_REMOTE_SKILLS_DIR}/"
    f"{CODEX_SPACEDOCK_PLUGIN_NAMESPACE}/skills/first-officer/SKILL.md"
)


class RazorbackCodex(Codex):
    """Codex installed agent with benchmark-safe defaults layered on top."""

    def __init__(
        self,
        *,
        enable_multi_agent: bool = False,
        spacedock_plugin_dirs: list[Path | str] | None = None,
        **kwargs: Any,
    ) -> None:
        self._enable_multi_agent = enable_multi_agent
        self._spacedock_plugin_dirs = [
            Path(p).expanduser() for p in (spacedock_plugin_dirs or [])
        ]
        super().__init__(**kwargs)

    def build_cli_flags(self) -> str:
        # Extends Codex.build_cli_flags: web search is disabled for offline benchmark solving.
        # This prevents solver answers from depending on live web access.
        base = super().build_cli_flags()
        web_search_disabled = f"-c {shlex.quote('web_search=\"disabled\"')}"
        multi_agent = "--enable multi_agent" if self._enable_multi_agent else ""
        # The adapter writes a vetted hook into the isolated CODEX_HOME at run
        # setup time. Exec mode otherwise refuses untrusted hooks interactively.
        hook_trust_bypass = "--dangerously-bypass-hook-trust"
        return " ".join(
            part
            for part in (
                base,
                web_search_disabled,
                multi_agent,
                hook_trust_bypass,
            )
            if part
        )

    async def setup(self, environment: BaseEnvironment) -> None:
        await super().setup(environment)
        await self._stage_spacedock_plugin_dirs(environment)

    async def _stage_spacedock_plugin_dirs(self, environment: BaseEnvironment) -> None:
        if not self._spacedock_plugin_dirs:
            return
        if len(self._spacedock_plugin_dirs) != 1:
            raise SpacedockSolverAgentError(
                "codex spacedock runtime expects exactly one spacedock plugin dir"
            )
        if not hasattr(environment, "upload_dir"):
            raise SpacedockSolverAgentError(
                "codex spacedock runtime requires environment.upload_dir to stage "
                "the spacedock plugin into the Harbor trial"
            )

        plugin_dir = self._spacedock_plugin_dirs[0]
        _validate_spacedock_plugin_dir(plugin_dir)
        remote_plugin_dir = (
            f"{CODEX_SPACEDOCK_REMOTE_SKILLS_DIR}/"
            f"{CODEX_SPACEDOCK_PLUGIN_NAMESPACE}"
        )
        await environment.exec(
            command=(
                f"rm -rf {shlex.quote(remote_plugin_dir)} && "
                f"mkdir -p {shlex.quote(CODEX_SPACEDOCK_REMOTE_SKILLS_DIR)}"
            )
        )
        await environment.upload_dir(str(plugin_dir), remote_plugin_dir)
        # Harbor's Codex agent copies self.skills_dir/* into
        # $HOME/.agents/skills immediately before `codex exec`, so this remote
        # tree becomes the namespaced `spacedock` skill package for the run.
        self.skills_dir = CODEX_SPACEDOCK_REMOTE_SKILLS_DIR

    async def install(self, environment: BaseEnvironment) -> None:
        # Extends Codex.install only to clear benchmark proxy variables during
        # upstream install commands; Harbor owns the install script itself.
        self._razorback_installing = True
        try:
            await super().install(environment)
        finally:
            self._razorback_installing = False

    async def exec_as_root(
        self,
        environment: BaseEnvironment,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        # Extends BaseInstalledAgent.exec_as_root for the same benchmark proxy
        # install constraint documented on RazorbackCodex.install.
        if getattr(self, "_razorback_installing", False):
            env = _without_proxy_env(env)
        else:
            _raise_if_public_lookup(command)
        return await super().exec_as_root(
            environment,
            command=command,
            env=env,
            cwd=cwd,
            timeout_sec=timeout_sec,
        )

    async def exec_as_agent(
        self,
        environment: BaseEnvironment,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        # Extends BaseInstalledAgent.exec_as_agent for the same benchmark proxy
        # install constraint documented on RazorbackCodex.install.
        if getattr(self, "_razorback_installing", False):
            env = _without_proxy_env(env)
        elif _is_codex_runtime_setup_command(command):
            command = _with_codex_lookup_guard_setup(command)
        elif _is_codex_outer_exec_command(command):
            command = _with_codex_shell_lookup_guard(command)
        else:
            _raise_if_public_lookup(command)
        return await super().exec_as_agent(
            environment,
            command=command,
            env=env,
            cwd=cwd,
            timeout_sec=timeout_sec,
        )


def build_inner_agent(
    *,
    logs_dir: Path,
    model: str,
    harbor_agent_kwargs: dict[str, Any],
    extra_env: dict[str, str],
    enable_multi_agent: bool = False,
    spacedock_plugin_dirs: list[Path | str] | None = None,
) -> Codex:
    """Construct harbor's Codex agent with Razorback's kwarg contract.

    Harbor's Codex installed agent currently exposes model_name, extra_env, and
    descriptor-backed CLI/env kwargs. It does not expose the Claude-style tool
    allow/deny or appended-system-prompt surfaces, so active restrictions fail
    closed instead of being silently dropped.
    """
    kw = _codex_kwargs(harbor_agent_kwargs)
    return RazorbackCodex(
        logs_dir=Path(logs_dir),
        model_name=model,
        extra_env=dict(extra_env),
        enable_multi_agent=enable_multi_agent,
        spacedock_plugin_dirs=spacedock_plugin_dirs,
        **kw,
    )


def _validate_spacedock_plugin_dir(plugin_dir: Path) -> None:
    required = (
        plugin_dir / ".codex-plugin" / "plugin.json",
        plugin_dir / "skills" / "first-officer" / "SKILL.md",
        plugin_dir / "skills" / "ensign" / "SKILL.md",
        plugin_dir / "agents" / "first-officer.md",
        plugin_dir / "agents" / "ensign.md",
    )
    for path in required:
        if not path.exists():
            raise SpacedockSolverAgentError(
                f"codex spacedock runtime cannot stage incomplete plugin; missing {path}"
            )


def _codex_kwargs(harbor_agent_kwargs: dict[str, Any]) -> dict[str, Any]:
    kw: dict[str, Any] = {}
    for name, value in harbor_agent_kwargs.items():
        if _is_empty_noop(name, value):
            continue
        if name not in _CODEX_SUPPORTED_KWARGS:
            raise SpacedockSolverAgentError(
                "codex runtime adapter cannot honor unsupported harbor_agent_kwargs "
                f"field {name!r}; refusing to silently drop it."
            )
        kw[name] = value
    return kw


def _without_proxy_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {key: "" for key in PROXY_BLOCK_ENV}
    if extra:
        env.update(extra)
    return env


def _raise_if_public_lookup(command: str) -> None:
    if is_forbidden_public_lookup_command(command):
        raise SpacedockSolverAgentError(
            "codex runtime blocked forbidden public lookup command before execution"
        )


def _is_codex_runtime_setup_command(command: str) -> bool:
    return '"$CODEX_HOME/auth.json"' in command or '"$CODEX_HOME/config.toml"' in command


def _is_codex_outer_exec_command(command: str) -> bool:
    return "codex exec " in command and "--enable unified_exec" in command


def _with_codex_lookup_guard_setup(command: str) -> str:
    script = codex_pretooluse_guard_script()
    shell_guard = codex_shell_guard_script()
    wrapper = codex_shell_wrapper_script()
    wrapped_commands = " ".join(shlex.quote(command) for command in CODEX_SHELL_GUARD_COMMANDS)
    return (
        command
        + "\n\n"
        + "_RAZORBACK_LOOKUP_GUARD=\"$CODEX_HOME/razorback-public-lookup-guard.py\"\n"
        + "_RAZORBACK_SHELL_GUARD=\"$CODEX_HOME/razorback-shell-guard.sh\"\n"
        + "_RAZORBACK_BIN=\"$CODEX_HOME/razorback-bin\"\n"
        + "mkdir -p \"$_RAZORBACK_BIN\"\n"
        + "cat >\"$_RAZORBACK_LOOKUP_GUARD\" <<'PY'\n"
        + script
        + "PY\n"
        + "chmod 700 \"$_RAZORBACK_LOOKUP_GUARD\"\n"
        + "cat >\"$_RAZORBACK_SHELL_GUARD\" <<'SH'\n"
        + shell_guard
        + "SH\n"
        + "chmod 700 \"$_RAZORBACK_SHELL_GUARD\"\n"
        + "cat >\"$_RAZORBACK_BIN/.razorback-wrapper\" <<'SH'\n"
        + wrapper
        + "SH\n"
        + "chmod 700 \"$_RAZORBACK_BIN/.razorback-wrapper\"\n"
        + f"for _razorback_tool in {wrapped_commands}; do\n"
        + '    cp "$_RAZORBACK_BIN/.razorback-wrapper" "$_RAZORBACK_BIN/$_razorback_tool"\n'
        + '    chmod 700 "$_RAZORBACK_BIN/$_razorback_tool"\n'
        + "done\n"
        + 'cat >>"$CODEX_HOME/config.toml" <<TOML\n'
        + "\n[[hooks.PreToolUse]]\n"
        + 'matcher = "*"\n'
        + "\n[[hooks.PreToolUse.hooks]]\n"
        + 'type = "command"\n'
        + 'command = "python3 $CODEX_HOME/razorback-public-lookup-guard.py"\n'
        + "timeout = 10\n"
        + "TOML"
    )


def _with_codex_shell_lookup_guard(command: str) -> str:
    guarded_exec = (
        'BASH_ENV="$CODEX_HOME/razorback-shell-guard.sh" '
        'RAZORBACK_ORIGINAL_PATH="$PATH" '
        'PATH="$CODEX_HOME/razorback-bin:$PATH" '
        "codex exec "
    )
    return command.replace("codex exec ", guarded_exec, 1)


def _is_empty_noop(name: str, value: Any) -> bool:
    if value is None:
        return True
    if name in {"tools_allowed", "tools_denied"} and value == []:
        return True
    # Razorback's canonical schema default is not an active user restriction for Codex.
    if name == "max_turns" and value == 200:
        return True
    return False
