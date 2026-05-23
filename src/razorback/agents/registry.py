# ABOUTME: Agent-kind registry (§6.2) — canonical Spacedock solver schema helper.
# ABOUTME: Runtime dispatch itself flows through spec/schema.py and translate.py.

from pathlib import Path
from typing import Literal, Type

from pydantic import BaseModel, ConfigDict, Field

from razorback.errors import RazorbackError


class AgentKindError(RazorbackError):
    """Raised when agent.kind is not registered."""


class _SamplingKwargs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature: float = 0.0
    top_p: float | None = None
    seed: int | None = None


class SpacedockSolverAgentConfig(BaseModel):
    """Registry-level kwargs for canonical agent.kind: spacedock_solver."""
    model_config = ConfigDict(extra="forbid")
    runtime: Literal["claude", "codex", "pi"] = "claude"
    model: str = Field(default="claude-opus-4-5", min_length=1)
    sampling: _SamplingKwargs = Field(default_factory=_SamplingKwargs)
    solver_workflow: Path
    solver_workflow_content_hash: str | None = None
    max_turns: int = 200
    max_budget_usd: float | None = None
    tools_allowed: list[str] = Field(default_factory=list)
    tools_denied: list[str] = Field(default_factory=list)
    append_system_prompt: str | None = None
    reasoning_effort: str | None = None
    reasoning_summary: str | None = None
    resume_from_freeze: Path | None = None
    sealed_hash: str | None = None
    spacedock_skill_version: str | None = None
    prompt_content_hashes: dict[str, str] = Field(default_factory=dict)


class AgentKindEntry:
    """Config schema + import path. import_path=None means harbor-bundled."""

    def __init__(self, config_schema: Type[BaseModel], import_path: str | None) -> None:
        self.config_schema = config_schema
        self.import_path = import_path


_REGISTRY: dict[str, AgentKindEntry] = {
    "spacedock_solver": AgentKindEntry(
        SpacedockSolverAgentConfig,
        "razorback.agents.spacedock_solver:SpacedockSolverAgent",
    ),
}


def resolve_agent_kind(kind: str) -> AgentKindEntry:
    try:
        return _REGISTRY[kind]
    except KeyError:
        raise AgentKindError(
            f"unknown agent.kind: {kind!r} (registered: {sorted(_REGISTRY)})"
        )
