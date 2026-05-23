# ABOUTME: Codex runtime adapter for SpacedockSolverAgent (spec §4.3.1, §8.4).
# ABOUTME: Constructs harbor's Codex agent and fails closed on unsupported controls.

import shlex
from pathlib import Path
from typing import Any

from harbor.agents.installed.codex import Codex
from harbor.environments.base import BaseEnvironment

from razorback.agents.public_lookup_guard import (
    codex_pretooluse_guard_script,
    is_forbidden_public_lookup_command,
)
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.agents.spacedock_solver import SpacedockSolverAgentError


_CODEX_SUPPORTED_KWARGS = {
    descriptor.kwarg
    for descriptor in [*Codex.CLI_FLAGS, *getattr(Codex, "ENV_VARS", [])]
}


class RazorbackCodex(Codex):
    """Codex installed agent with benchmark-safe defaults layered on top."""

    def build_cli_flags(self) -> str:
        # Extends Codex.build_cli_flags: web search is disabled for offline benchmark solving.
        # This prevents solver answers from depending on live web access.
        base = super().build_cli_flags()
        web_search_disabled = f"-c {shlex.quote('web_search=\"disabled\"')}"
        # The adapter writes a vetted hook into the isolated CODEX_HOME at run
        # setup time. Exec mode otherwise refuses untrusted hooks interactively.
        hook_trust_bypass = "--dangerously-bypass-hook-trust"
        return " ".join(
            part for part in (base, web_search_disabled, hook_trust_bypass) if part
        )

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
        elif not _is_codex_outer_exec_command(command):
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
        **kw,
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
    return (
        command
        + "\n\n"
        + "_RAZORBACK_LOOKUP_GUARD=\"$CODEX_HOME/razorback-public-lookup-guard.py\"\n"
        + "cat >\"$_RAZORBACK_LOOKUP_GUARD\" <<'PY'\n"
        + script
        + "PY\n"
        + "chmod 700 \"$_RAZORBACK_LOOKUP_GUARD\"\n"
        + 'cat >>"$CODEX_HOME/config.toml" <<TOML\n'
        + "\n[[hooks.PreToolUse]]\n"
        + 'matcher = "*"\n'
        + 'command = "python3 $_RAZORBACK_LOOKUP_GUARD"\n'
        + "TOML"
    )


def _is_empty_noop(name: str, value: Any) -> bool:
    if value is None:
        return True
    if name in {"tools_allowed", "tools_denied"} and value == []:
        return True
    # Razorback's canonical schema default is not an active user restriction for Codex.
    if name == "max_turns" and value == 200:
        return True
    return False
