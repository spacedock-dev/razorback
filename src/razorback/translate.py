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
from razorback.spec.agent_kwargs import build_v2_harbor_agent_kwargs
from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    ClaudeCliAgentBlock,
    DabBenchmarkBlock,
    HarborDabBenchmarkBlock,
    LocalBenchmarkBlock,
    NopAgentBlock,
    SpacedockSolverAgentBlock,
    SpacedockSolverV2AgentBlock,
    Spec,
)


SPACEDOCK_SOLVER_IMPORT_PATH = (
    "razorback.agents.spacedock_solver:SpacedockSolverAgent"
)
SPACEDOCK_SOLVER_V2_IMPORT_PATH = (
    "razorback.agents.spacedock_solver_v2:SpacedockSolverAgent"
)
SPACEDOCK_SOLVER_V2_ENVIRONMENT_IMPORT_PATH = (
    "razorback.environments.docker:ProxySeparatedDockerEnvironment"
)
RAZORBACK_CLAUDE_CODE_IMPORT_PATH = (
    "razorback.agents._runtime.claude:RazorbackClaudeCode"
)
SPACEDOCK_SOLVER_V2_CONTAINER_FREEZE_ROOT = "/razorback-freeze"


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
    agent_cfg, task_env = _build_agent_config(
        spec,
        project_root=project_root,
        home=home,
        prior_frozen_spec_path=prior_frozen_spec_path,
    )

    if isinstance(spec.benchmark, LocalBenchmarkBlock):
        return _build_local(
            spec=spec, job_name=job_name, jobs_dir=jobs_dir, agent_cfg=agent_cfg
        ), {}
    if isinstance(spec.benchmark, DabBenchmarkBlock):
        if tasks_root is None:
            raise SpecError("DAB specs require tasks_root.")
        return _build_dab(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            tasks_root=Path(tasks_root),
            agent_cfg=agent_cfg,
            task_env=task_env,
        )
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
                "spacedock-solver requires project_root for .env auth discovery."
            )
        if spec.agent.sealed_hash is None:
            raise SpecError(
                "spacedock-solver spec must be frozen (agent.sealed_hash missing)."
            )
        if spec.agent.prompt_contents is None:
            raise SpecError(
                "spacedock-solver spec must be frozen (agent.prompt_contents missing)."
            )
        resolution = resolve_claude_auth(project_root=project_root, home=home)
        kwargs: dict[str, Any] = {
            "model": spec.agent.model,
            "sampling": {
                "temperature": spec.agent.sampling.temperature,
                "top_p": spec.agent.sampling.top_p,
                "seed": spec.agent.sampling.seed,
            },
            "stages": list(spec.agent.stages),
            "tools_allowed": list(spec.agent.tools_allowed),
            "prompts": dict(spec.agent.prompts),
            "prompt_contents": dict(spec.agent.prompt_contents),
            "sealed_hash": spec.agent.sealed_hash,
            "prior_frozen_spec_path": (
                str(prior_frozen_spec_path) if prior_frozen_spec_path else None
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

    if isinstance(spec.agent, SpacedockSolverV2AgentBlock):
        if project_root is None:
            raise SpecError(
                "spacedock_solver_v2 requires project_root for .env auth discovery."
            )
        if spec.agent.sealed_hash is None:
            raise SpecError(
                "spacedock_solver_v2 spec must be frozen (agent.sealed_hash missing)."
            )
        if spec.agent.runtime == "codex":
            resolution = resolve_codex_auth(project_root=project_root, home=home)
        else:
            resolution = resolve_claude_auth(project_root=project_root, home=home)
        harbor_agent_kwargs = build_v2_harbor_agent_kwargs(
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
            import_path=SPACEDOCK_SOLVER_V2_IMPORT_PATH,
            model_name=spec.agent.model,
            kwargs=kwargs,
            env=dict(resolution.env),
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env

    if isinstance(spec.agent, ClaudeCliAgentBlock):
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
        n_concurrent_trials=1,
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
    # Phase 1 keeps the in-tree ade-bench path until Phase 8's port-out.
    from razorback.benchmarks.ade_bench.tasks import (
        materialize_git_task,
        materialize_local_task,
        resolve_task_dirs,
    )
    from razorback.benchmarks.dab.prepare import _DEFAULT_DOCKER_IMAGE

    assert isinstance(spec.benchmark, AdeBenchBenchmarkBlock)
    resolved = resolve_task_dirs(
        tasks_root=spec.benchmark.tasks_root,
        tasks=spec.benchmark.tasks,
    )
    docker_image = (
        spec.benchmark.docker_image_override or _DEFAULT_DOCKER_IMAGE
    )
    home_dir = Path(home) if home is not None else Path.home()
    cache_root = home_dir / ".cache" / "razorback" / "ade-bench"

    tasks: list[TaskConfig] = []
    for r in resolved:
        if r.local_slug is not None:
            if spec.benchmark.ade_bench_root is None:
                raise SpecError(
                    "ade-bench local task entry requires ade_bench_root on the "
                    "benchmark block (PKG-19)"
                )
            materialized = materialize_local_task(
                ade_bench_root=Path(spec.benchmark.ade_bench_root).expanduser(),
                task_slug=r.local_slug,
                docker_image=docker_image,
                cache_root=cache_root,
                materialize_mode=materialize_mode,
                db_type=spec.benchmark.db_type,
                project_type=spec.benchmark.project_type,
            )
            tasks.append(TaskConfig(path=materialized))
        elif r.git_url is not None and r.git_commit_id is not None:
            materialized = materialize_git_task(
                git_url=r.git_url,
                git_commit_id=r.git_commit_id,
                source_path=r.path,
                docker_image=docker_image,
                cache_root=cache_root,
            )
            tasks.append(TaskConfig(path=materialized))
        else:
            tasks.append(TaskConfig(path=r.path))
    run_dir = jobs_dir / job_name
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=_environment_config(agent_cfg, run_dir),
    )


def _build_dab(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path,
    agent_cfg: AgentConfig,
    task_env: dict[str, str],
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    # Phase 1 keeps the in-tree DAB prepare path until Phase 2's port-out.
    from razorback.benchmarks.dab.prepare import prepare_dataset_tasks

    assert isinstance(spec.benchmark, DabBenchmarkBlock)
    manifest_all: list[dict] = []
    for dataset in spec.benchmark.datasets:
        manifest_all.extend(
            prepare_dataset_tasks(
                data_root=Path(spec.benchmark.data_root),
                dataset=dataset,
                tasks_root=tasks_root / dataset,
                task_env=task_env,
            )
    )
    tasks = [TaskConfig(path=entry["task_dir"]) for entry in manifest_all]
    trial_name_map = {
        entry["task_name"]: (entry["dataset"], entry["query_id"])
        for entry in manifest_all
    }
    run_dir = jobs_dir / job_name
    cfg = JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=_environment_config(agent_cfg, run_dir),
    )
    return cfg, trial_name_map


def _build_harbor_dab(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path,
    agent_cfg: AgentConfig,
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    """Translate harbor_dab block by invoking the sibling plugin.

    Calls `razorback-plugin-dab generate` as a subprocess, collects emitted
    task directories under `tasks_root`, and builds a harbor JobConfig that
    points `tasks:` at each emitted (dataset, query) directory. Razorback
    core never imports from the plugin.
    """
    import subprocess

    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)

    task_dirs: list[Path] = []
    trial_name_map: dict[str, tuple[str, int]] = {}
    for dataset in spec.benchmark.datasets:
        out_dir = tasks_root / dataset
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            "uv", "run", "razorback-plugin-dab", "generate",
            "--datasets", dataset,
            "--data-root", str(Path(spec.benchmark.data_root).resolve()),
            "--out", str(out_dir.resolve()),
            "--workspace-variant", spec.benchmark.workspace_variant,
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
        for entry in sorted(out_dir.iterdir()):
            if not entry.is_dir():
                continue
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
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=_environment_config(agent_cfg, run_dir),
    )
    return cfg, trial_name_map


def _environment_config(agent_cfg: AgentConfig, run_dir: Path) -> EnvironmentConfig:
    if agent_cfg.import_path != SPACEDOCK_SOLVER_V2_IMPORT_PATH:
        return EnvironmentConfig(delete=False)

    host_freeze_root = run_dir / "_razorback" / "freeze"
    host_freeze_root.mkdir(parents=True, exist_ok=True)
    return EnvironmentConfig(
        import_path=SPACEDOCK_SOLVER_V2_ENVIRONMENT_IMPORT_PATH,
        delete=False,
        env=dict(PROXY_BLOCK_ENV),
        mounts_json=[
            {
                "type": "bind",
                "source": str(host_freeze_root.resolve()),
                "target": SPACEDOCK_SOLVER_V2_CONTAINER_FREEZE_ROOT,
            }
        ],
    )
