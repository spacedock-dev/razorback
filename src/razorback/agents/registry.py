# ABOUTME: Agent-kind registry (§6.2) — maps agent.kind to (config schema, import path).
# ABOUTME: The spec parser validates kwargs against the schema before harbor sees them.

from pathlib import Path
from typing import Literal, Type

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


_VALID_STAGES = ("model", "analyze", "verify")


class _SamplingKwargs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature: float
    top_p: float | None = None
    seed: int | None = None


class SpacedockSolverAgentConfig(BaseModel):
    """Registry-level kwargs validated BEFORE harbor.AgentConfig is constructed."""
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1)
    sampling: _SamplingKwargs
    stages: list[str]
    tools_allowed: list[str] = Field(default_factory=list)
    prompts: dict[str, str]
    sealed_hash: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")

    @field_validator("stages")
    @classmethod
    def _stages_must_be_exact_order(cls, v: list[str]) -> list[str]:
        if v != list(_VALID_STAGES):
            raise ValueError(
                f"stages must be exactly {list(_VALID_STAGES)!r}; got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _prompts_cover_every_stage(self) -> "SpacedockSolverAgentConfig":
        missing = set(self.stages) - set(self.prompts.keys())
        if missing:
            raise ValueError(f"prompts missing for stages: {sorted(missing)}")
        extra = set(self.prompts.keys()) - set(self.stages)
        if extra:
            raise ValueError(f"prompts has keys not in stages: {sorted(extra)}")
        return self


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
    "spacedock-solver": AgentKindEntry(
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
