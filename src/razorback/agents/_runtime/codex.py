# ABOUTME: Codex runtime adapter for SpacedockSolverAgent v2 (spec §4.3.1, §8.4).
# ABOUTME: Constructs harbor's Codex agent and fails closed on unsupported controls.

import shlex
from pathlib import Path
from typing import Any

from harbor.agents.installed.codex import Codex
from harbor.environments.base import BaseEnvironment

from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgentError


_CODEX_SUPPORTED_KWARGS = {
    descriptor.kwarg
    for descriptor in [*Codex.CLI_FLAGS, *getattr(Codex, "ENV_VARS", [])]
}


class RazorbackCodex(Codex):
    """Codex installed agent with benchmark-safe defaults layered on top."""

    def build_cli_flags(self) -> str:
        base = super().build_cli_flags()
        web_search_disabled = f"-c {shlex.quote('web_search=\"disabled\"')}"
        return " ".join(part for part in (base, web_search_disabled) if part)

    async def install(self, environment: BaseEnvironment) -> None:
        install_env = _without_proxy_env({"DEBIAN_FRONTEND": "noninteractive"})
        await self.exec_as_root(
            environment,
            command=(
                "if ldd --version 2>&1 | grep -qi musl || [ -f /etc/alpine-release ]; then"
                "  apk add --no-cache curl bash nodejs npm ripgrep;"
                " elif command -v apt-get &>/dev/null; then"
                "  apt-get update && apt-get install -y curl ripgrep;"
                " elif command -v yum &>/dev/null; then"
                "  yum install -y curl ripgrep;"
                " else"
                '  echo "Warning: No known package manager found, assuming curl is available" >&2;'
                " fi"
            ),
            env=install_env,
        )

        version_spec = f"@{self._version}" if self._version else "@latest"
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                "if ldd --version 2>&1 | grep -qi musl || [ -f /etc/alpine-release ]; then"
                f"  npm install -g @openai/codex{version_spec};"
                " else"
                "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.2/install.sh | bash &&"
                '  export NVM_DIR="$HOME/.nvm" &&'
                '  \\. "$NVM_DIR/nvm.sh" || true &&'
                "  command -v nvm &>/dev/null || { echo 'Error: NVM failed to load' >&2; exit 1; } &&"
                "  nvm install 22 && nvm alias default 22 && npm -v &&"
                f"  npm install -g @openai/codex{version_spec};"
                " fi && "
                "codex --version"
            ),
            env=_without_proxy_env(),
        )

        await self.exec_as_root(
            environment,
            command=(
                "for bin in node codex; do"
                '  BIN_PATH="$(which "$bin" 2>/dev/null || true)";'
                '  if [ -n "$BIN_PATH" ] && [ "$BIN_PATH" != "/usr/local/bin/$bin" ]; then'
                '    ln -sf "$BIN_PATH" "/usr/local/bin/$bin";'
                "  fi;"
                " done"
            ),
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


def _is_empty_noop(name: str, value: Any) -> bool:
    if value is None:
        return True
    if name in {"tools_allowed", "tools_denied"} and value == []:
        return True
    # Razorback's v2 schema default is not an active user restriction for Codex.
    if name == "max_turns" and value == 200:
        return True
    return False
