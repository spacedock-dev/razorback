# ABOUTME: Pydantic schema for the razorback spec.
# ABOUTME: Top-level forbids unknown keys; agent and benchmark are discriminated unions.

from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class SamplingBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature: float = 0.0
    top_p: float | None = None
    seed: int | None = None


class NopAgentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["nop"]


class ClaudeCliAgentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["claude-cli"]
    model: str = "claude-opus-4-5"
    sampling: SamplingBlock = Field(default_factory=SamplingBlock)
    tools_allowed: list[str] = Field(default_factory=list)
    prompt_file: Path | None = None


class SpacedockSolverAgentBlock(BaseModel):
    """Spec-level agent block (§6.2 third bullet).

    Unfrozen specs carry prompt FILE PATHS in `prompts`; freeze resolves them to
    `sha256:<hex>` strings and pins the body under `prompt_contents`. `sealed_hash`
    is populated by freeze; absent in unfrozen specs.
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["spacedock-solver"]
    model: str = "claude-opus-4-5"
    sampling: SamplingBlock = Field(default_factory=SamplingBlock)
    stages: list[str] = Field(default_factory=lambda: ["model", "analyze", "verify"])
    tools_allowed: list[str] = Field(default_factory=list)
    prompts: dict[str, str] = Field(default_factory=dict)
    prompt_contents: dict[str, str] | None = None
    sealed_hash: str | None = None


AgentBlock = Annotated[
    Union[NopAgentBlock, ClaudeCliAgentBlock, SpacedockSolverAgentBlock],
    Field(discriminator="kind"),
]


class LocalBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["local"] = "local"
    task_paths: list[Path] = Field(default_factory=list)


class DabBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["dab"]
    data_root: Path
    datasets: list[str] = Field(min_length=1)


BenchmarkBlock = Annotated[
    Union[LocalBenchmarkBlock, DabBenchmarkBlock],
    Field(discriminator="kind"),
]


class ObserverBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["jsonl", "stdout"]
    path: str | None = None


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    experiment: str
    agent: AgentBlock
    benchmark: BenchmarkBlock
    trials: int = 1
    observers: list[ObserverBlock] = Field(default_factory=list)
