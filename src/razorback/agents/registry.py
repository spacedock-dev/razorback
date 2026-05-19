# ABOUTME: Agent-kind registry (§6.2) — maps agent.kind to (config schema, import path).
# ABOUTME: The spec parser validates kwargs against the schema before harbor sees them.

from pathlib import Path
from typing import Type

from pydantic import BaseModel, ConfigDict, Field

from razorback.errors import RazorbackError


class AgentKindError(RazorbackError):
    """Raised when agent.kind is not registered."""


class NopAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaudeCliAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(default="claude-opus-4-5")
    tools_allowed: list[str] = Field(default_factory=list)
    prompt_file: Path | None = None


class AgentKindEntry:
    """Config schema + import path. import_path=None means harbor-bundled."""

    def __init__(self, config_schema: Type[BaseModel], import_path: str | None) -> None:
        self.config_schema = config_schema
        self.import_path = import_path


_REGISTRY: dict[str, AgentKindEntry] = {
    "nop": AgentKindEntry(NopAgentConfig, None),
    "claude-cli": AgentKindEntry(
        ClaudeCliAgentConfig,
        "razorback.agents.claude_cli:ClaudeCliAgent",
    ),
}


def resolve_agent_kind(kind: str) -> AgentKindEntry:
    try:
        return _REGISTRY[kind]
    except KeyError:
        raise AgentKindError(
            f"unknown agent.kind: {kind!r} (registered: {sorted(_REGISTRY)})"
        )
