# ABOUTME: Claude runtime adapter for SpacedockSolverAgent v2 (spec §4.3.1, §8.4).
# ABOUTME: Constructs harbor's ClaudeCode agent with the kwarg shape razorback's spec requires.

from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode

from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgentError


_CLAUDE_SUPPORTED_KWARGS = {
    descriptor.kwarg
    for descriptor in [*ClaudeCode.CLI_FLAGS, *getattr(ClaudeCode, "ENV_VARS", [])]
} | {"skills_dir"}

_RAZORBACK_TO_HARBOR_KWARGS = {
    "tools_allowed": "allowed_tools",
    "tools_denied": "disallowed_tools",
}


class RazorbackClaudeCode(ClaudeCode):
    """Harbor ClaudeCode subclass for live Razorback benchmark solving."""


def build_inner_agent(
    *,
    logs_dir: Path,
    model: str,
    harbor_agent_kwargs: dict[str, Any],
    extra_env: dict[str, str],
) -> ClaudeCode:
    """Construct harbor's ClaudeCode agent with razorback's kwarg shape.

    Maps razorback field names to harbor's CLI flags:
    tools_allowed -> allowed_tools; tools_denied -> disallowed_tools.
    Drops no-op values so harbor uses its own defaults.
    """
    kw = _claude_kwargs(harbor_agent_kwargs)
    return RazorbackClaudeCode(
        logs_dir=Path(logs_dir),
        model_name=model,
        extra_env=dict(extra_env),
        **kw,
    )


def _claude_kwargs(harbor_agent_kwargs: dict[str, Any]) -> dict[str, Any]:
    kw: dict[str, Any] = {}
    for name, value in harbor_agent_kwargs.items():
        if _is_empty_noop(name, value):
            continue
        harbor_name = _RAZORBACK_TO_HARBOR_KWARGS.get(name, name)
        if harbor_name not in _CLAUDE_SUPPORTED_KWARGS:
            raise SpacedockSolverAgentError(
                "claude runtime adapter cannot honor unsupported harbor_agent_kwargs "
                f"field {name!r}; refusing to silently drop it."
            )
        if name in {"tools_allowed", "tools_denied"}:
            value = ",".join(value)
        kw[harbor_name] = value
    return kw


def _is_empty_noop(name: str, value: Any) -> bool:
    if value is None:
        return True
    if name in {"tools_allowed", "tools_denied"} and value == []:
        return True
    return False
