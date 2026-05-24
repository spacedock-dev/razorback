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
    reasoning_effort: str | None = None


class CodexAgentBlock(BaseModel):
    """Direct Codex agent block.

    This is the minimal Codex path: it translates straight to RazorbackCodex
    without solver workflow prompting or sealed/checkpoint semantics.
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["codex"]
    model: str = "gpt-5.5"
    sampling: SamplingBlock = Field(default_factory=SamplingBlock)
    reasoning_effort: str | None = None
    reasoning_summary: str | None = None
    override_timeout_sec: float | None = Field(default=None, gt=0)
    override_setup_timeout_sec: float | None = Field(default=None, gt=0)
    max_timeout_sec: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _only_noop_sampling(self) -> "CodexAgentBlock":
        if (
            self.sampling.temperature not in (None, 0.0)
            or self.sampling.top_p is not None
            or self.sampling.seed is not None
        ):
            raise ValueError(
                "agent.kind: codex does not support sampling controls; keep "
                "sampling at temperature=0.0, top_p=null, seed=null."
            )
        return self

    @model_validator(mode="after")
    def _timeout_cap_allows_override(self) -> "CodexAgentBlock":
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
        CodexAgentBlock,
        SpacedockSolverAgentBlock,
    ],
    Field(discriminator="kind"),
]


class LocalBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["local"] = "local"
    task_paths: list[Path] = Field(default_factory=list)


class AdeBenchTaskEntry(BaseModel):
    """Git-task entry retained for in-tree ade-bench helper APIs.

    Not on any active `BenchmarkBlock` union — accessed only via
    `razorback.benchmarks.ade_bench.tasks.resolve_task_dirs` for local
    fixture/dev work.
    """
    model_config = ConfigDict(extra="forbid")
    path: str
    git_url: str
    git_commit_id: str


_HARBOR_DATASET_REF_SHAPE = "<org>/<name>@<ref>"
_HARBOR_DATASET_REF_EXAMPLE = "adyen/dabstep@latest"


class HarborBenchmarkBlock(BaseModel):
    """Generic Harbor-resolved benchmark block (`kind: harbor`).

    `dataset:` resolves via `harbor.registry.client.PackageDatasetClient`;
    optional `tasks` / `exclude_tasks` / `n_tasks` selectors apply spec-side
    with the same semantics as harbor's `-i` / `-x` / `-l` flags. Spec-side
    `tasks:` entries match `PackageTaskId.name` verbatim — no per-dataset
    prefix stripping (heterogeneous: dabstep uses bare ints,
    swe-bench-verified uses project-prefixed slugs).

    For benchmarks that need razorback-side prep (currently only DAB), set
    `plugin:` to the plugin's registered name. The plugin's typed args go
    in `plugin_args`; they are validated at parse time against the plugin's
    Pydantic model discovered via the `razorback.plugin_args` entry-point
    group. When `plugin:` is set, `dataset:` may use the short
    `<name>@<version>` form (the plugin owns the registry lookup); when
    `plugin:` is None, `dataset:` must be fully qualified
    `<org>/<name>@<ref>` for PackageDatasetClient resolution.
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["harbor"]
    dataset: str | None = None
    tasks: list[str] | None = None
    exclude_tasks: list[str] | None = None
    n_tasks: int | None = None
    plugin: str | None = None
    plugin_args: dict[str, object] | None = None

    @model_validator(mode="after")
    def _validate_source_and_ref(self) -> "HarborBenchmarkBlock":
        if self.dataset is None:
            raise ValueError(
                "harbor benchmark requires `dataset` "
                f"(e.g. {_HARBOR_DATASET_REF_EXAMPLE!r})"
            )
        if self.plugin_args is not None and self.plugin is None:
            raise ValueError(
                "`plugin_args` requires `plugin` to name the registered plugin "
                "the args belong to"
            )
        if self.plugin is None:
            from harbor.models.package.reference import PackageReference

            try:
                parsed = PackageReference.parse(self.dataset)
            except Exception as exc:
                raise ValueError(
                    f"invalid Harbor dataset ref {self.dataset!r}: "
                    f"required shape is {_HARBOR_DATASET_REF_SHAPE} "
                    f"(e.g. {_HARBOR_DATASET_REF_EXAMPLE!r}); "
                    f"Harbor parser rejected it: {exc}"
                ) from exc
            if "/" not in self.dataset or "@" not in self.dataset:
                raise ValueError(
                    f"invalid Harbor dataset ref {self.dataset!r}: "
                    f"required shape is {_HARBOR_DATASET_REF_SHAPE} "
                    f"(e.g. {_HARBOR_DATASET_REF_EXAMPLE!r})"
                )
            if not parsed.org or not parsed.short_name or not parsed.ref:
                raise ValueError(
                    f"invalid Harbor dataset ref {self.dataset!r}: "
                    f"required shape is {_HARBOR_DATASET_REF_SHAPE} "
                    f"(e.g. {_HARBOR_DATASET_REF_EXAMPLE!r})"
                )
        else:
            if "@" not in self.dataset:
                raise ValueError(
                    f"plugin-resolved dataset {self.dataset!r} must include `@<ref>`"
                )
            from razorback.spec.plugin_args import (
                PluginNotFoundError,
                get_plugin_args_model,
            )

            try:
                args_model = get_plugin_args_model(self.plugin)
            except PluginNotFoundError as exc:
                raise ValueError(str(exc)) from exc
            args = self.plugin_args or {}
            args_model(**args)
        return self


class HarborLocalBenchmarkBlock(BaseModel):
    """Local Harbor-shaped task directory — dev-escape (`kind: harbor-local`).

    Used when iterating on a Harbor adapter before publishing it. The
    `tasks_root` directory must contain the canonical Harbor task layout
    (`<slug>/task.toml` + sibling files). Once the adapter publishes,
    migrate to `kind: harbor` + `dataset: <org>/<name>@<ref>`.
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["harbor-local"]
    tasks_root: Path
    tasks: list[str] = Field(min_length=1)

    @field_validator("tasks_root", mode="before")
    @classmethod
    def _expand_tasks_root(cls, value: object) -> object:
        return _expand_path(value)


BenchmarkBlock = Annotated[
    Union[
        LocalBenchmarkBlock,
        HarborBenchmarkBlock,
        HarborLocalBenchmarkBlock,
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


class PaperBaselineBlock(BaseModel):
    """Published baseline a researcher targets — `rk score` auto-applies
    this as `--against-constant <name>=<value>` when set."""
    model_config = ConfigDict(extra="forbid")
    name: str
    value: float


class ExperimentMetaBlock(BaseModel):
    """Phase 4a — experiment-level budget metadata + paper baseline ref.

    `max_budget_usd` is the per-experiment cap the `rk run` budget gate
    (`--max-budget-usd-running`) refuses against. `estimated_cost_usd`
    is populated by `rk freeze` (PKG-8) and consumed by the gate as the
    pre-launch cost estimate. `paper_baseline` carries the published
    baseline `rk score` auto-applies when present.
    """
    model_config = ConfigDict(extra="forbid")
    max_budget_usd: float | None = None
    estimated_cost_usd: float | None = None
    paper_baseline: PaperBaselineBlock | None = None


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
