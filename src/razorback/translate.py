# ABOUTME: Spec to harbor JobConfig translator (Phase 1 AC-6: emits AgentConfig.import_path).
# ABOUTME: Replaces the v1 compat translator. Auth flows via AgentConfig.env per FU-1 AC-1.

from pathlib import Path
from typing import Any, Literal

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig, RetryConfig
from harbor.models.trial.config import (
    AgentConfig,
    EnvironmentConfig,
    TaskConfig,
    VerifierConfig,
)

from razorback.agents.auth import resolve_claude_auth, resolve_codex_auth
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.errors import SpecError
from razorback.spec.agent_kwargs import build_spacedock_harbor_agent_kwargs
from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    HarborDabBenchmarkBlock,
    LocalBenchmarkBlock,
    NopAgentBlock,
    Spider2DbtBenchmarkBlock,
    SpacedockSolverAgentBlock,
    Spec,
)


SPACEDOCK_SOLVER_IMPORT_PATH = (
    "razorback.agents.spacedock_solver:SpacedockSolverAgent"
)
SPACEDOCK_SOLVER_ENVIRONMENT_IMPORT_PATH = (
    "razorback.environments.docker:ProxySeparatedDockerEnvironment"
)
RAZORBACK_CLAUDE_CODE_IMPORT_PATH = (
    "razorback.agents._runtime.claude:RazorbackClaudeCode"
)
SPACEDOCK_SOLVER_CONTAINER_FREEZE_ROOT = "/razorback-freeze"


def spec_to_job_config(
    spec: Spec,
    *,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path | None = None,
    project_root: Path | None = None,
    home: Path | None = None,
    prior_frozen_spec_path: Path | None = None,
    materialize_mode: Literal["bind", "copy"] = "bind",
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    """Translate a parsed (frozen) spec into a harbor JobConfig.

    Returns (JobConfig, trial_name_map). The map is empty for non-DAB benchmarks.
    Phase 1 emits `AgentConfig.import_path` for spacedock_solver per AC-6.
    """
    agent_cfg, _task_env = _build_agent_config(
        spec,
        project_root=project_root,
        home=home,
        prior_frozen_spec_path=prior_frozen_spec_path,
    )

    if isinstance(spec.benchmark, LocalBenchmarkBlock):
        return _build_local(
            spec=spec, job_name=job_name, jobs_dir=jobs_dir, agent_cfg=agent_cfg
        ), {}
    if isinstance(spec.benchmark, HarborDabBenchmarkBlock):
        if tasks_root is None:
            raise SpecError(
                "harbor_dab specs require tasks_root (the run orchestrator passes it)."
            )
        return _build_harbor_dab(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            tasks_root=Path(tasks_root),
            agent_cfg=agent_cfg,
        )
    if isinstance(spec.benchmark, AdeBenchBenchmarkBlock):
        return _build_ade_bench(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            agent_cfg=agent_cfg,
            home=home,
            materialize_mode=materialize_mode,
        ), {}
    if isinstance(spec.benchmark, Spider2DbtBenchmarkBlock):
        return _build_spider2_dbt(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            agent_cfg=agent_cfg,
        ), {}
    raise SpecError(f"unsupported benchmark block: {type(spec.benchmark).__name__}")


def _build_agent_config(
    spec: Spec,
    *,
    project_root: Path | None,
    home: Path | None,
    prior_frozen_spec_path: Path | None = None,
) -> tuple[AgentConfig, dict[str, str]]:
    if isinstance(spec.agent, NopAgentBlock):
        return AgentConfig(name=AgentName.NOP.value), {}

    if isinstance(spec.agent, SpacedockSolverAgentBlock):
        if project_root is None:
            raise SpecError(
                "spacedock_solver requires project_root for .env auth discovery."
            )
        if spec.agent.sealed_hash is None:
            raise SpecError(
                "spacedock_solver spec must be frozen (agent.sealed_hash missing)."
            )
        if spec.agent.runtime == "codex":
            resolution = resolve_codex_auth(project_root=project_root, home=home)
        else:
            resolution = resolve_claude_auth(project_root=project_root, home=home)
        harbor_agent_kwargs = build_spacedock_harbor_agent_kwargs(
            max_turns=spec.agent.max_turns,
            tools_allowed=spec.agent.tools_allowed,
            tools_denied=spec.agent.tools_denied,
            append_system_prompt=spec.agent.append_system_prompt,
            reasoning_effort=spec.agent.reasoning_effort,
            reasoning_summary=spec.agent.reasoning_summary,
        )
        kwargs: dict[str, Any] = {
            "runtime": spec.agent.runtime,
            "model": spec.agent.model,
            "sampling": {
                "temperature": spec.agent.sampling.temperature,
                "top_p": spec.agent.sampling.top_p,
                "seed": spec.agent.sampling.seed,
            },
            "solver_workflow": str(spec.agent.solver_workflow),
            "solver_workflow_content_hash": spec.agent.solver_workflow_content_hash,
            "prompt_content_hashes": dict(spec.agent.prompt_content_hashes),
            "spacedock_skill_version": spec.agent.spacedock_skill_version,
            "harbor_agent_kwargs": harbor_agent_kwargs,
            "max_turns": spec.agent.max_turns,
            "tools_allowed": list(spec.agent.tools_allowed),
            "tools_denied": list(spec.agent.tools_denied),
            "resume_from_freeze": (
                str(spec.agent.resume_from_freeze)
                if spec.agent.resume_from_freeze
                else None
            ),
        }
        agent_cfg = AgentConfig(
            import_path=SPACEDOCK_SOLVER_IMPORT_PATH,
            model_name=spec.agent.model,
            kwargs=kwargs,
            env=dict(resolution.env),
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env

    if getattr(spec.agent, "kind", None) == "claude-cli":
        if project_root is None:
            raise SpecError(
                "claude-cli agent requires project_root for .env auth discovery."
            )
        if spec.agent.sampling.temperature not in (None, 0.0):
            raise SpecError(
                "legacy agent.kind: claude-cli now routes to Harbor ClaudeCode, "
                "which has no temperature kwarg; keep sampling.temperature at "
                "its default no-op value."
            )
        resolution = resolve_claude_auth(project_root=project_root, home=home)
        kwargs: dict[str, Any] = {}
        if spec.agent.tools_allowed:
            kwargs["allowed_tools"] = ",".join(spec.agent.tools_allowed)
        agent_cfg = AgentConfig(
            import_path=RAZORBACK_CLAUDE_CODE_IMPORT_PATH,
            model_name=spec.agent.model,
            kwargs=kwargs,
            env=dict(resolution.env),
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env

    raise SpecError(f"unsupported agent block: {type(spec.agent).__name__}")


def _build_local(
    *, spec: Spec, job_name: str, jobs_dir: Path, agent_cfg: AgentConfig
) -> JobConfig:
    assert isinstance(spec.benchmark, LocalBenchmarkBlock)
    run_dir = jobs_dir / job_name
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=spec.concurrency.trials,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=[TaskConfig(path=Path(p).resolve()) for p in spec.benchmark.task_paths],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=_environment_config(agent_cfg, run_dir),
    )


def _build_ade_bench(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    agent_cfg: AgentConfig,
    home: Path | None = None,
    materialize_mode: Literal["bind", "copy"] = "bind",
) -> JobConfig:
    from razorback.benchmarks.ade_bench.harbor_view import (
        materialize_ade_harbor_task_view,
    )
    from razorback.benchmarks.ade_bench.tasks import (
        DEFAULT_ADE_BENCH_DOCKER_IMAGE,
        materialize_git_task,
        resolve_task_dirs,
    )

    assert isinstance(spec.benchmark, AdeBenchBenchmarkBlock)
    if spec.benchmark.batch_mode == "shared-context":
        raise SpecError(
            "ade-bench batch_mode='shared-context' is explicit but not yet "
            "supported for Harbor dispatch; use batch_mode='per-task'."
        )
    home_dir = Path(home) if home is not None else Path.home()
    cache_root = home_dir / ".cache" / "razorback" / "ade-bench"
    view_root = jobs_dir / job_name / "_razorback" / "task_views"
    tasks: list[TaskConfig] = []

    if spec.benchmark.dataset is not None:
        from razorback.benchmarks.ade_bench.dataset_ref import (
            resolve_dataset_tasks,
        )

        dataset_cache_root = cache_root / "datasets"
        # Spec-side task subset entries must be plain strings on the dataset-ref
        # path; AdeBenchTaskEntry (git tasks) is local-only.
        requested_subset: list[str] | None = None
        if spec.benchmark.tasks:
            requested_subset = [
                t for t in spec.benchmark.tasks if isinstance(t, str)
            ]
        resolved_dataset = resolve_dataset_tasks(
            dataset_ref=spec.benchmark.dataset,
            tasks=requested_subset,
            cache_root=dataset_cache_root,
        )
        for r in resolved_dataset:
            materialized = materialize_ade_harbor_task_view(
                source_task_dir=r.path,
                view_root=view_root,
                task_slug=r.requested_slug,
                docker_image=spec.benchmark.docker_image_override,
                view_mode="copy",
                dataset_ref=spec.benchmark.dataset,
                dataset_content_hash=r.dataset_content_hash,
                task_content_hash=r.content_hash,
            )
            tasks.append(TaskConfig(path=materialized))
    else:
        resolved = resolve_task_dirs(
            tasks_root=spec.benchmark.tasks_root,
            tasks=spec.benchmark.tasks,
        )
        docker_image = (
            spec.benchmark.docker_image_override or DEFAULT_ADE_BENCH_DOCKER_IMAGE
        )
        for r in resolved:
            if r.git_url is not None and r.git_commit_id is not None:
                materialized = materialize_git_task(
                    git_url=r.git_url,
                    git_commit_id=r.git_commit_id,
                    source_path=r.path,
                    docker_image=docker_image,
                    cache_root=cache_root,
                )
                tasks.append(TaskConfig(path=materialized))
            else:
                materialized = materialize_ade_harbor_task_view(
                    source_task_dir=r.path,
                    view_root=view_root,
                    task_slug=r.path.name,
                    docker_image=spec.benchmark.docker_image_override,
                    view_mode="copy",
                )
                tasks.append(TaskConfig(path=materialized))

    run_dir = jobs_dir / job_name
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=spec.concurrency.trials,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=_environment_config(agent_cfg, run_dir),
    )


def _build_harbor_dab(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path,
    agent_cfg: AgentConfig,
) -> tuple[JobConfig, dict[str, tuple[str, int] | tuple[str, list[int]]]]:
    """Translate harbor_dab block by invoking the sibling plugin.

    Calls `razorback-plugin-dab generate` as a subprocess, collects emitted
    task directories under `tasks_root`, and builds a harbor JobConfig that
    points `tasks:` at each emitted (dataset, query) directory. Razorback
    core never imports from the plugin.

    Under `query_mode: batch`, the plugin emits one task per dataset and the
    trial_name_map carries `(dataset, list[int])` so the aggregator can fan
    that single trial out into N per-query outcomes.
    """
    import subprocess

    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)

    # AC-2: dataset ref resolution. If `dataset:` is set, the definition supplies
    # the dataset inventory; `benchmark.datasets` (if present) is a subset selector.
    # `data_root` falls back to env default — local data is still needed at
    # materialize time (per entity Notes).
    if spec.benchmark.dataset is not None:
        from razorback_plugin_dab.dataset_def import load_default_definition

        definition = load_default_definition()
        if definition.ref != spec.benchmark.dataset:
            raise SpecError(
                f"benchmark.dataset {spec.benchmark.dataset!r} does not match "
                f"the plugin's shipped definition {definition.ref!r}; "
                f"upgrade razorback-plugin-dab or pin the matching version."
            )
        if spec.benchmark.datasets:
            known = {d.name for d in definition.datasets}
            unknown = [d for d in spec.benchmark.datasets if d not in known]
            if unknown:
                raise SpecError(
                    f"benchmark.datasets subset references unknown DAB datasets "
                    f"{unknown!r}; definition {definition.ref} knows {sorted(known)}"
                )
            resolved_datasets = list(spec.benchmark.datasets)
        else:
            resolved_datasets = [d.name for d in definition.datasets]
        if spec.benchmark.data_root is not None:
            data_root = Path(spec.benchmark.data_root).resolve()
        else:
            import os
            env_default = os.environ.get(
                "DATAAGENTBENCH_DATA_ROOT",
                str(Path.home() / "dataagentbench" / "data"),
            )
            data_root = Path(env_default).expanduser().resolve()
    else:
        resolved_datasets = list(spec.benchmark.datasets)
        data_root = Path(spec.benchmark.data_root).resolve()

    query_mode = spec.benchmark.query_mode
    task_dirs: list[Path] = []
    trial_name_map: dict[str, tuple[str, int] | tuple[str, list[int]]] = {}
    for dataset in resolved_datasets:
        out_dir = tasks_root / dataset
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            "uv", "run", "razorback-plugin-dab", "generate",
            "--datasets", dataset,
            "--data-root", str(data_root),
            "--out", str(out_dir.resolve()),
            "--workspace-variant", spec.benchmark.workspace_variant,
            "--query-mode", query_mode,
        ]
        if spec.benchmark.hints:
            cmd.append("--hints")
        else:
            cmd.append("--no-hints")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise SpecError(
                f"razorback-plugin-dab generate failed for dataset {dataset!r} "
                f"(exit {result.returncode}): {result.stderr.strip()}"
            )
        emitted_dirs = sorted(p for p in out_dir.iterdir() if p.is_dir())
        if query_mode == "batch":
            for entry in emitted_dirs:
                task_name = entry.name
                if task_name != dataset:
                    continue
                task_dirs.append(entry)
                workdir = entry / "steps" / "main" / "workdir"
                query_ids: list[int] = []
                if workdir.is_dir():
                    for p in workdir.iterdir():
                        if not (p.is_dir() and p.name.startswith("query")):
                            continue
                        suffix = p.name[len("query"):]
                        if suffix.isdigit():
                            query_ids.append(int(suffix))
                query_ids.sort()
                trial_name_map[task_name] = (dataset, query_ids)
        else:
            for entry in emitted_dirs:
                task_name = entry.name
                task_dirs.append(entry)
                if "-q" in task_name:
                    ds, qpart = task_name.rsplit("-q", 1)
                    try:
                        trial_name_map[task_name] = (ds, int(qpart))
                    except ValueError:
                        pass

    tasks = [TaskConfig(path=p) for p in task_dirs]
    run_dir = jobs_dir / job_name
    cfg = JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=spec.concurrency.trials,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=_environment_config(agent_cfg, run_dir),
    )
    return cfg, trial_name_map


def _build_spider2_dbt(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    agent_cfg: AgentConfig,
) -> JobConfig:
    from razorback.benchmarks.spider2_dbt.harbor_view import (
        materialize_spider2_harbor_task_view,
    )

    assert isinstance(spec.benchmark, Spider2DbtBenchmarkBlock)
    if spec.benchmark.batch_mode == "shared-context":
        raise SpecError(
            "spider2-dbt batch_mode='shared-context' is explicit but not yet "
            "supported for Harbor dispatch; use batch_mode='per-task'."
        )

    view_root = jobs_dir / job_name / "_razorback" / "task_views"
    source_root = Path(spec.benchmark.tasks_root).resolve()
    task_configs: list[TaskConfig] = []
    for slug in spec.benchmark.tasks:
        source_task_dir = source_root / slug
        if not (source_task_dir / "task.toml").is_file():
            raise FileNotFoundError(
                f"spider2-dbt task '{slug}' not found at {source_task_dir} "
                f"(missing task.toml); tasks_root={source_root}"
            )
        materialized = materialize_spider2_harbor_task_view(
            source_task_dir=source_task_dir,
            view_root=view_root,
            task_slug=slug,
            docker_image=spec.benchmark.docker_image_override,
            view_mode="copy",
        )
        task_configs.append(TaskConfig(path=materialized))

    run_dir = jobs_dir / job_name
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=spec.concurrency.trials,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=task_configs,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=_environment_config(agent_cfg, run_dir),
    )


def _environment_config(agent_cfg: AgentConfig, run_dir: Path) -> EnvironmentConfig:
    if agent_cfg.import_path != SPACEDOCK_SOLVER_IMPORT_PATH:
        return EnvironmentConfig(delete=False)

    host_freeze_root = run_dir / "_razorback" / "freeze"
    host_freeze_root.mkdir(parents=True, exist_ok=True)
    return EnvironmentConfig(
        import_path=SPACEDOCK_SOLVER_ENVIRONMENT_IMPORT_PATH,
        delete=False,
        env=dict(PROXY_BLOCK_ENV),
        mounts_json=[
            {
                "type": "bind",
                "source": str(host_freeze_root.resolve()),
                "target": SPACEDOCK_SOLVER_CONTAINER_FREEZE_ROOT,
            }
        ],
    )
