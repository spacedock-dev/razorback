# ABOUTME: Claude runtime adapter for SpacedockSolverAgent v2 (spec §4.3.1, §8.4).
# ABOUTME: Builds razorback's ClaudeCliAgent (a ClaudeCode subclass) so the inner
# ABOUTME: agent emits cost_usd + claude-output.jsonl via PKG-26's surface.

from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode

from razorback.agents.claude_cli import ClaudeCliAgent
from razorback.agents.spacedock_solver import SpacedockSolverAgentError


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
) -> ClaudeCliAgent:
    """Construct razorback's ClaudeCliAgent (ClaudeCode subclass) for spacedock v2.

    Routing through ClaudeCliAgent (rather than harbor's ClaudeCode directly)
    inherits PKG-26's cost-emit + claude-output.jsonl audit sentinel. The earlier
    path returned harbor.ClaudeCode directly and silently dropped cost telemetry
    even when paid-API auth was in use.

    tools_allowed flows through ClaudeCliAgent's own param (not harbor's
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
            # ClaudeCliAgent applies its DISALLOWED_TOOLS list by default; v2 callers
            # that need to widen the block list pass through harbor's disallowed_tools.
            kw["disallowed_tools"] = ",".join(value)
            continue
        kw[name] = value
    return ClaudeCliAgent(
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
