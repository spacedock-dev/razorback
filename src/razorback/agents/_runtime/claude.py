# ABOUTME: Claude runtime adapter for SpacedockSolverAgent v2 (spec §4.3.1, §8.4).
# ABOUTME: Builds razorback's ClaudeCliAgent (a ClaudeCode subclass) so the inner
# ABOUTME: agent emits cost_usd + claude-output.jsonl via PKG-26's surface.

from pathlib import Path
from typing import Any

from razorback.agents.claude_cli import ClaudeCliAgent


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
    kw: dict[str, Any] = {
        "max_turns": harbor_agent_kwargs.get("max_turns"),
    }
    if "tools_allowed" in harbor_agent_kwargs and harbor_agent_kwargs["tools_allowed"]:
        kw["tools_allowed"] = list(harbor_agent_kwargs["tools_allowed"])
    if "tools_denied" in harbor_agent_kwargs and harbor_agent_kwargs["tools_denied"]:
        # ClaudeCliAgent applies its DISALLOWED_TOOLS list by default; v2 callers
        # that need to widen the block list pass through harbor's disallowed_tools.
        kw["disallowed_tools"] = ",".join(harbor_agent_kwargs["tools_denied"])
    if "append_system_prompt" in harbor_agent_kwargs:
        kw["append_system_prompt"] = harbor_agent_kwargs["append_system_prompt"]
    if "skills_dir" in harbor_agent_kwargs:
        kw["skills_dir"] = harbor_agent_kwargs["skills_dir"]
    kw = {k: v for k, v in kw.items() if v is not None}
    return ClaudeCliAgent(
        logs_dir=Path(logs_dir),
        model_name=model,
        extra_env=dict(extra_env or {}),
        **kw,
    )
