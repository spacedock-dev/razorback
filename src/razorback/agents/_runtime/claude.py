# ABOUTME: Claude runtime adapter for SpacedockSolverAgent v2 (spec §4.3.1, §8.4).
# ABOUTME: Constructs harbor's ClaudeCode agent with the kwarg shape razorback's spec requires.

from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode


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
    Drops None values so harbor uses its own defaults.
    """
    kw: dict[str, Any] = {
        "max_turns": harbor_agent_kwargs.get("max_turns"),
    }
    if "tools_allowed" in harbor_agent_kwargs and harbor_agent_kwargs["tools_allowed"]:
        kw["allowed_tools"] = ",".join(harbor_agent_kwargs["tools_allowed"])
    if "tools_denied" in harbor_agent_kwargs and harbor_agent_kwargs["tools_denied"]:
        kw["disallowed_tools"] = ",".join(harbor_agent_kwargs["tools_denied"])
    if "append_system_prompt" in harbor_agent_kwargs:
        kw["append_system_prompt"] = harbor_agent_kwargs["append_system_prompt"]
    if "skills_dir" in harbor_agent_kwargs:
        kw["skills_dir"] = harbor_agent_kwargs["skills_dir"]
    kw = {k: v for k, v in kw.items() if v is not None}
    return ClaudeCode(logs_dir=Path(logs_dir), model_name=model, **kw)
