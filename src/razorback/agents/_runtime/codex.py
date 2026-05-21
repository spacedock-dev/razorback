# ABOUTME: Codex runtime adapter for SpacedockSolverAgent v2 (spec §4.3.1, §8.4).
# ABOUTME: Constructs harbor's Codex agent and fails closed on unsupported controls.

from pathlib import Path
from typing import Any

from harbor.agents.installed.codex import Codex

from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgentError


_CODEX_SUPPORTED_KWARGS = {
    descriptor.kwarg
    for descriptor in [*Codex.CLI_FLAGS, *getattr(Codex, "ENV_VARS", [])]
}


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
    return Codex(
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


def _is_empty_noop(name: str, value: Any) -> bool:
    if value is None:
        return True
    if name in {"tools_allowed", "tools_denied"} and value == []:
        return True
    # Razorback's v2 schema default is not an active user restriction for Codex.
    if name == "max_turns" and value == 200:
        return True
    return False
