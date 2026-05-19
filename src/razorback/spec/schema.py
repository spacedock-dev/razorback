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


AgentBlock = Annotated[
    Union[NopAgentBlock, ClaudeCliAgentBlock],
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


class ProvenanceBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pin_model_version: bool = True
    pin_image_digest: bool = True
    pin_agent_cli_hash: bool = True
    pin_git_sha: bool = True
    model_resolved_version: str | None = None
    model_resolved_at: str | None = None
    image_digest: str | None = None
    agent_cli_hash: str | None = None
    harness_git_sha: str | None = None
    harbor_version: str | None = None
    prompt_file_hashes: dict[str, str] | None = None


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    experiment: str
    agent: AgentBlock
    benchmark: BenchmarkBlock
    trials: int = 1
    observers: list[ObserverBlock] = Field(default_factory=list)
    provenance: ProvenanceBlock = Field(default_factory=ProvenanceBlock)
