# ABOUTME: Pydantic schema for the razorback spec.
# ABOUTME: Top-level forbids unknown keys; agent and benchmark are discriminated unions.

import os
import re
from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_ENV_DEFAULT_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):-([^}]*)\}")


def _expand_path(value: object) -> object:
    """Expand local path conveniences accepted by benchmark data-root fields."""
    if isinstance(value, (str, Path)):
        text = str(value)
        text = _ENV_DEFAULT_RE.sub(
            lambda match: os.environ.get(match.group(1)) or match.group(2),
            text,
        )
        return Path(os.path.expandvars(text)).expanduser()
    return value


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
    """Spec-level agent block for canonical spacedock_solver (spec §6.2 + §4).

    Unfrozen specs carry the path `solver_workflow:`; freeze resolves the
    directory content hash and writes `solver_workflow_content_hash` into the
    frozen spec. `sealed_hash` is populated by freeze.
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["spacedock_solver"]
    runtime: Literal["claude", "codex", "pi"] = "claude"
    model: str = "claude-opus-4-5"
    sampling: SamplingBlock = Field(default_factory=SamplingBlock)
    solver_workflow: Path
    solver_workflow_content_hash: str | None = None
    max_turns: int = 200
    max_budget_usd: float | None = None
    override_timeout_sec: float | None = Field(default=None, gt=0)
    override_setup_timeout_sec: float | None = Field(default=None, gt=0)
    max_timeout_sec: float | None = Field(default=None, gt=0)
    tools_allowed: list[str] = Field(default_factory=list)
    tools_denied: list[str] = Field(default_factory=list)
    append_system_prompt: str | None = None
    reasoning_effort: str | None = None
    reasoning_summary: str | None = None
    resume_from_freeze: Path | None = None
    sealed_hash: str | None = None
    spacedock_skill_version: str | None = None
    prompt_content_hashes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _timeout_cap_allows_override(self) -> "SpacedockSolverAgentBlock":
        if (
            self.override_timeout_sec is not None
            and self.max_timeout_sec is not None
            and self.max_timeout_sec < self.override_timeout_sec
        ):
            raise ValueError(
                "agent.max_timeout_sec must be greater than or equal to "
                "agent.override_timeout_sec"
            )
        return self


AgentBlock = Annotated[
    Union[
        NopAgentBlock,
        ClaudeCliAgentBlock,
        SpacedockSolverAgentBlock,
    ],
    Field(discriminator="kind"),
]


class LocalBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["local"] = "local"
    task_paths: list[Path] = Field(default_factory=list)


class DabBenchmarkBlock(BaseModel):
    """Legacy-only schema block retained for `_legacy` imports.

    Active specs no longer include this class in `BenchmarkBlock`; use
    `benchmark.kind: harbor_dab`.
    """

    model_config = ConfigDict(extra="forbid")
    kind: Literal["dab"]
    data_root: Path
    datasets: list[str] = Field(min_length=1)

    @field_validator("data_root", mode="before")
    @classmethod
    def _expand_data_root(cls, value: object) -> object:
        return _expand_path(value)


class HarborDabBenchmarkBlock(BaseModel):
    """Phase 2 — DAB harbor adapter (sibling-package task generator).

    Translates in `rk run` to a subprocess invocation of
    `razorback-plugin-dab generate`, then a harbor `JobConfig` whose
    `tasks:` references the emitted task directories. Razorback core
    never imports from the plugin at runtime.

    `dataset:` (AC-2) names a Harbor-style dataset definition ref of the form
    `<name>@<version>`. When set, `data_root` becomes optional and falls back
    to the env-default at materialization time; `datasets:` is treated as a
    task-subset selector over the definition (empty = all datasets in the def).
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["harbor_dab"]
    dataset: str | None = None
    data_root: Path | None = None
    datasets: list[str] = Field(default_factory=list)
    workspace_variant: Literal["direct-minimal", "direct-structured", "spacedock"] = "direct-minimal"
    hints: bool = False
    query_mode: Literal["batch", "per-query"] = "per-query"

    @field_validator("data_root", mode="before")
    @classmethod
    def _expand_data_root(cls, value: object) -> object:
        if value is None:
            return None
        return _expand_path(value)

    @field_validator("dataset")
    @classmethod
    def _validate_dataset_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "@" not in value:
            raise ValueError(
                f"benchmark.dataset must be in the form '<name>@<version>'; "
                f"got dataset format {value!r}"
            )
        name, version = value.split("@", 1)
        if not name or not version:
            raise ValueError(
                f"benchmark.dataset must be '<name>@<version>' with non-empty parts; "
                f"got dataset format {value!r}"
            )
        return value

    @model_validator(mode="after")
    def _dataset_or_data_root(self) -> "HarborDabBenchmarkBlock":
        if self.dataset is None:
            if self.data_root is None:
                raise ValueError(
                    "benchmark.data_root is required when benchmark.dataset is not set"
                )
            if not self.datasets:
                raise ValueError(
                    "benchmark.datasets must be non-empty when benchmark.dataset is not set"
                )
        return self


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


_ADE_BENCH_DATASET_REF_SHAPE = "<org>/<name>@<ref>"
_ADE_BENCH_DATASET_REF_EXAMPLE = "dbt-labs/ade-bench@latest"


class AdeBenchBenchmarkBlock(BaseModel):
    """ADE-Bench benchmark block.

    Source selection is exclusive: either `dataset` (Harbor published dataset
    ref, fully qualified as `<org>/<name>@<ref>`) or `tasks_root` (local
    Harbor-shaped directory, the dev/fixture escape hatch).

    Three Harbor ref tiers are accepted (all three round-trip through
    `harbor.models.package.reference.PackageReference.parse`):

    - `@<tag>` (e.g. `@latest`): dev/smoke convenience; re-resolves on each
      `rk run`.
    - `@<rev_number>` (e.g. `@1`): stable-ish citation; a published revision
      number does not change once Harbor assigns it.
    - `@sha256:<digest>` (e.g. `@sha256:2c1f9e69...`): paper-grade pin; the
      resolver itself refuses mismatched content, not just a downstream
      manifest check.

    The canonical example spec demonstrates the digest tier (paper-grade pin).
    `@latest` stays valid for daily smoke runs.

    `tasks` is the spec-side task subset; on the dataset-ref path each entry
    is matched against per-task package names with the dataset prefix
    stripped (e.g. spec `tasks: [airbnb001]` matches the resolved
    `ade-bench-airbnb001`).
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["ade-bench"]
    dataset: str | None = None
    tasks_root: Path | None = None
    tasks: list[str | AdeBenchTaskEntry] | None = None
    docker_image_override: str | None = None
    batch_mode: Literal["per-task", "shared-context"] = "per-task"
    db_type: Literal["duckdb", "snowflake"] | None = None
    project_type: Literal["dbt", "dbt-fusion"] | None = None

    @model_validator(mode="after")
    def _validate_source_selection(self) -> "AdeBenchBenchmarkBlock":
        if self.dataset is not None and self.tasks_root is not None:
            raise ValueError(
                "exactly one of `dataset` (Harbor dataset ref) or `tasks_root` "
                "(local task directory) may be set; both were provided"
            )
        if self.dataset is None and self.tasks_root is None:
            raise ValueError(
                "ade-bench benchmark requires exactly one of `dataset` "
                f"(Harbor dataset ref, e.g. {_ADE_BENCH_DATASET_REF_EXAMPLE!r}) "
                "or `tasks_root` (local Harbor-shaped task directory); "
                "neither was provided"
            )
        if self.dataset is not None:
            from harbor.models.package.reference import PackageReference

            try:
                parsed = PackageReference.parse(self.dataset)
            except Exception as exc:
                raise ValueError(
                    f"invalid Harbor dataset ref {self.dataset!r}: "
                    f"required shape is {_ADE_BENCH_DATASET_REF_SHAPE} "
                    f"(e.g. {_ADE_BENCH_DATASET_REF_EXAMPLE!r}); "
                    f"Harbor parser rejected it: {exc}"
                ) from exc
            # PackageReference.parse accepts bare names (no org, no ref); the
            # captain's AC-1 guardrail still requires fully-qualified refs.
            if "/" not in self.dataset or "@" not in self.dataset:
                raise ValueError(
                    f"invalid Harbor dataset ref {self.dataset!r}: "
                    f"required shape is {_ADE_BENCH_DATASET_REF_SHAPE} "
                    f"(e.g. {_ADE_BENCH_DATASET_REF_EXAMPLE!r})"
                )
            if not parsed.org or not parsed.short_name or not parsed.ref:
                raise ValueError(
                    f"invalid Harbor dataset ref {self.dataset!r}: "
                    f"required shape is {_ADE_BENCH_DATASET_REF_SHAPE} "
                    f"(e.g. {_ADE_BENCH_DATASET_REF_EXAMPLE!r})"
                )
        if self.tasks_root is not None:
            if not self.tasks:
                raise ValueError(
                    "`tasks_root` (local task directory) requires a non-empty "
                    "`tasks` list naming task subdirectories"
                )
        return self


class Spider2DbtBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["spider2-dbt"]
    tasks_root: Path
    tasks: list[str] = Field(min_length=1)
    docker_image_override: str | None = None
    batch_mode: Literal["per-task", "shared-context"] = "per-task"


BenchmarkBlock = Annotated[
    Union[
        LocalBenchmarkBlock,
        HarborDabBenchmarkBlock,
        AdeBenchBenchmarkBlock,
        Spider2DbtBenchmarkBlock,
    ],
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
    # PKG-8 (spec §3.2 + §8.2): plugin inventory + solver_workflow content hash.
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


class ConcurrencyBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trials: int = Field(default=1, ge=1, le=4)


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    experiment: str
    agent: AgentBlock
    benchmark: BenchmarkBlock
    trials: int = 1
    concurrency: ConcurrencyBlock = Field(default_factory=ConcurrencyBlock)
    observers: list[ObserverBlock] = Field(default_factory=list)
    provenance: ProvenanceBlock = Field(default_factory=ProvenanceBlock)
    experiment_meta: ExperimentMetaBlock | None = None
