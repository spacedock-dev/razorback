# ABOUTME: Pydantic schema for the razorback spec.
# ABOUTME: Top-level forbids unknown keys; agent and benchmark are discriminated unions.

from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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

    @field_validator("stages")
    @classmethod
    def _stages_exact(cls, v: list[str]) -> list[str]:
        if v != ["model", "analyze", "verify"]:
            raise ValueError(
                f"stages must be ['model', 'analyze', 'verify']; got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _prompts_cover_stages(self) -> "SpacedockSolverAgentBlock":
        missing = set(self.stages) - set(self.prompts.keys())
        if missing:
            raise ValueError(f"prompts missing for stages: {sorted(missing)}")
        extra = set(self.prompts.keys()) - set(self.stages)
        if extra:
            raise ValueError(f"prompts has keys not in stages: {sorted(extra)}")
        return self


class SpacedockSolverV2AgentBlock(BaseModel):
    """Spec-level agent block for v2 (spec §6.2 + §4).

    Unfrozen specs carry the path `solver_workflow:`; freeze resolves the
    directory content hash and writes `solver_workflow_content_hash` into the
    frozen spec. `sealed_hash` is populated by freeze.
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["spacedock_solver_v2"]
    runtime: Literal["claude", "codex", "pi"] = "claude"
    model: str = "claude-opus-4-5"
    sampling: SamplingBlock = Field(default_factory=SamplingBlock)
    solver_workflow: Path
    solver_workflow_content_hash: str | None = None
    max_turns: int = 200
    max_budget_usd: float | None = None
    tools_allowed: list[str] = Field(default_factory=list)
    tools_denied: list[str] = Field(default_factory=list)
    append_system_prompt: str | None = None
    resume_from_freeze: Path | None = None
    sealed_hash: str | None = None
    spacedock_skill_version: str | None = None
    prompt_content_hashes: dict[str, str] = Field(default_factory=dict)


AgentBlock = Annotated[
    Union[
        NopAgentBlock,
        ClaudeCliAgentBlock,
        SpacedockSolverAgentBlock,
        SpacedockSolverV2AgentBlock,
    ],
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


class HarborDabBenchmarkBlock(BaseModel):
    """Phase 2 — DAB harbor adapter (sibling-package task generator).

    Translates in `rk run` to a subprocess invocation of
    `razorback-plugin-dab generate`, then a harbor `JobConfig` whose
    `tasks:` references the emitted task directories. Razorback core
    never imports from the plugin at runtime.
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["harbor_dab"]
    data_root: Path
    datasets: list[str] = Field(min_length=1)
    workspace_variant: Literal["direct-minimal", "direct-structured", "spacedock"] = "direct-minimal"
    hints: bool = False


class AdeBenchTaskEntry(BaseModel):
    """FU-1 AC-3 — git-task entry matching harbor's TaskConfig git-task shape.

    All three fields are required; partial entries reject with a ValidationError
    naming the missing field. `path` is the in-repo relative path to the harbor
    task directory; harbor's GitTaskId materializes it on demand.
    """
    model_config = ConfigDict(extra="forbid")
    path: str
    git_url: str
    git_commit_id: str


class AdeBenchLocalTaskEntry(BaseModel):
    """PKG-19 — local upstream-checkout task entry.

    Opts the entry into the `ade_bench_root` materialization path: the
    translator dispatches to `materialize_local_task`, which builds a view-
    dir from the captain's `~/git/ade-bench` checkout instead of cloning
    `harbor-datasets` per task.
    """
    model_config = ConfigDict(extra="forbid")
    slug: str


class AdeBenchBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["ade-bench"]
    tasks_root: Path
    tasks: list[str | AdeBenchTaskEntry | AdeBenchLocalTaskEntry] = Field(min_length=1)
    docker_image_override: str | None = None
    ade_bench_root: Path | None = None
    db_type: Literal["duckdb", "snowflake"] | None = None
    project_type: Literal["dbt", "dbt-fusion"] | None = None


BenchmarkBlock = Annotated[
    Union[LocalBenchmarkBlock, DabBenchmarkBlock, HarborDabBenchmarkBlock, AdeBenchBenchmarkBlock],
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
    # PKG-8 v2 (spec §3.2 + §8.2): plugin inventory + solver_workflow content hash.
    plugins: list[dict[str, str]] | None = None
    solver_workflow_hash: str | None = None


class ExperimentMetaBlock(BaseModel):
    """Phase 4a — experiment-level budget metadata.

    `max_budget_usd` is the per-experiment cap the `rk run` budget gate
    (`--max-budget-usd-running`) refuses against. `estimated_cost_usd`
    is populated by `rk freeze` (PKG-8) and consumed by the gate as the
    pre-launch cost estimate.
    """
    model_config = ConfigDict(extra="forbid")
    max_budget_usd: float | None = None
    estimated_cost_usd: float | None = None


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    experiment: str
    agent: AgentBlock
    benchmark: BenchmarkBlock
    trials: int = 1
    observers: list[ObserverBlock] = Field(default_factory=list)
    provenance: ProvenanceBlock = Field(default_factory=ProvenanceBlock)
    experiment_meta: ExperimentMetaBlock | None = None
