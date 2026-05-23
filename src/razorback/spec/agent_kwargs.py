# ABOUTME: Shared spec-to-Harbor agent kwarg builders for sealed v2 inputs.
# ABOUTME: Keeps freeze-time sealed hashes aligned with runtime translation kwargs.

from __future__ import annotations

from typing import Any


def build_v2_harbor_agent_kwargs(
    *,
    max_turns: int | None,
    tools_allowed: list[str] | None,
    tools_denied: list[str] | None,
    append_system_prompt: str | None = None,
    reasoning_effort: str | None = None,
    reasoning_summary: str | None = None,
) -> dict[str, Any]:
    harbor_agent_kwargs: dict[str, Any] = {
        "max_turns": max_turns,
        "tools_allowed": list(tools_allowed or []),
        "tools_denied": list(tools_denied or []),
    }
    if append_system_prompt is not None:
        harbor_agent_kwargs["append_system_prompt"] = append_system_prompt
    if reasoning_effort is not None:
        harbor_agent_kwargs["reasoning_effort"] = reasoning_effort
    if reasoning_summary is not None:
        harbor_agent_kwargs["reasoning_summary"] = reasoning_summary
    return harbor_agent_kwargs
