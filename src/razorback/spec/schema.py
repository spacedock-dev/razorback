# ABOUTME: Pydantic schema for the M1 subset of the razorback spec.
# ABOUTME: Top-level forbids unknown keys; future milestones extend agent/benchmark blocks.

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str


class BenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    task_paths: list[Path] = Field(default_factory=list)


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
