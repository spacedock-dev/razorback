# ABOUTME: Spec → harbor 0.6.6 JobConfig translator (§6.1).
# ABOUTME: Supports agent.kind ∈ {nop, claude-cli}, benchmark.kind ∈ {local, dab}.

from pathlib import Path
from typing import Any

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig, RetryConfig
from harbor.models.trial.config import (
    AgentConfig,
    EnvironmentConfig,
    TaskConfig,
    VerifierConfig,
)

from razorback.agents.auth import resolve_claude_auth
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.benchmarks.ade_bench.tasks import (
    materialize_git_task,
    resolve_task_dirs,
)
from razorback._legacy.benchmarks.dab.prepare import (
    _DEFAULT_DOCKER_IMAGE,
    prepare_dataset_tasks,
)
from razorback.errors import SpecError
from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    ClaudeCliAgentBlock,
    DabBenchmarkBlock,
    HarborDabBenchmarkBlock,
    LocalBenchmarkBlock,
    NopAgentBlock,
    SpacedockSolverAgentBlock,
    Spec,
)


def spec_to_job_config(
    spec: Spec,
    *,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path | None = None,
    project_root: Path | None = None,
    home: Path | None = None,
    prior_frozen_spec_path: Path | None = None,
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    """Translate a parsed spec into a harbor JobConfig and a trial_name_map.

    Returns (JobConfig, trial_name_map). For non-DAB benchmarks the map is
    empty. `tasks_root` is required for DAB specs. `project_root` is required
    for claude-cli agents (.env-driven auth discovery — AC-3). `prior_frozen_spec_path`
    threads through to spacedock-solver agent kwargs for AC-1 sealed-hash refusal.
    """
    agent_cfg, task_env = _build_agent_config(
        spec,
        project_root=project_root,
        home=home,
        prior_frozen_spec_path=prior_frozen_spec_path,
    )

    if isinstance(spec.benchmark, LocalBenchmarkBlock):
        return _build_local(spec=spec, job_name=job_name, jobs_dir=jobs_dir, agent_cfg=agent_cfg), {}
    if isinstance(spec.benchmark, DabBenchmarkBlock):
        if tasks_root is None:
            raise SpecError("DAB specs require tasks_root (the run orchestrator passes it).")
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
        return (
            _build_ade_bench(
                spec=spec,
                job_name=job_name,
                jobs_dir=jobs_dir,
                agent_cfg=agent_cfg,
                home=home,
            ),
            {},
        )
    raise SpecError(f"unsupported benchmark block: {type(spec.benchmark).__name__}")


def _build_agent_config(
    spec: Spec,
    *,
    project_root: Path | None,
    home: Path | None,
    prior_frozen_spec_path: Path | None = None,
) -> tuple[AgentConfig, dict[str, str]]:
    """Returns (agent_config, task_env_to_stamp_into_task_toml)."""
    if isinstance(spec.agent, NopAgentBlock):
        return AgentConfig(name=AgentName.NOP.value), {}
    if isinstance(spec.agent, SpacedockSolverAgentBlock):
        if project_root is None:
            raise SpecError(
                "spacedock-solver agent requires project_root for .env auth discovery."
            )
        if spec.agent.sealed_hash is None:
            raise SpecError(
                "spacedock-solver spec must be frozen (agent.sealed_hash missing). "
                "Run freeze before run."
            )
        if spec.agent.prompt_contents is None:
            raise SpecError(
                "spacedock-solver spec must be frozen (agent.prompt_contents missing)."
            )
        resolution = resolve_claude_auth(project_root=project_root, home=home)
        # FU-1 AC-1: auth forwarded ONLY via AgentConfig.env (redacted on disk).
        # kwargs is plaintext-on-disk and must not carry credentials.
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
            import_path="razorback.agents.spacedock_solver:SpacedockSolverAgent",
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
        resolution = resolve_claude_auth(project_root=project_root, home=home)
        # FU-1 AC-1: forward auth ONLY via AgentConfig.env (harbor redacts on disk
        # via templatize_sensitive_env). kwargs is plaintext-on-disk and must not
        # carry credentials.
        kwargs: dict[str, Any] = {
            "tools_allowed": list(spec.agent.tools_allowed),
            "sampling_temperature": spec.agent.sampling.temperature,
        }
        agent_cfg = AgentConfig(
            import_path="razorback.agents.claude_cli:ClaudeCliAgent",
            model_name=spec.agent.model,
            kwargs=kwargs,
            env=dict(resolution.env),
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env
    raise SpecError(f"unsupported agent block: {type(spec.agent).__name__}")


def _build_local(*, spec: Spec, job_name: str, jobs_dir: Path, agent_cfg: AgentConfig) -> JobConfig:
    assert isinstance(spec.benchmark, LocalBenchmarkBlock)
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=[TaskConfig(path=Path(p).resolve()) for p in spec.benchmark.task_paths],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        # delete=False preserves the prebuilt dab-agent:latest image across runs.
        # Default delete=True invokes `docker compose down --rmi all`, which removes
        # the prebuilt image and forces a rebuild before every subsequent run.
        environment=EnvironmentConfig(delete=False),
    )


def _build_ade_bench(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    agent_cfg: AgentConfig,
    home: Path | None = None,
) -> JobConfig:
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
        if r.git_url is not None and r.git_commit_id is not None:
            # FU-2: rewrite docker_image at materialization, emit a LOCAL
            # TaskConfig so harbor skips its own git fetch.
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
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=EnvironmentConfig(delete=False),
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
        entry["task_name"]: (entry["dataset"], entry["query_id"]) for entry in manifest_all
    }
    cfg = JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        # delete=False preserves the prebuilt dab-agent:latest image across runs.
        # Default delete=True invokes `docker compose down --rmi all`, which removes
        # the prebuilt image and forces a rebuild before every subsequent run.
        environment=EnvironmentConfig(delete=False),
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
    """Phase 2 — translate harbor_dab block by invoking the sibling plugin.

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
            # Parse "<dataset>-q<n>" → (dataset, n) for the trial-name map.
            if "-q" in task_name:
                ds, qpart = task_name.rsplit("-q", 1)
                try:
                    trial_name_map[task_name] = (ds, int(qpart))
                except ValueError:
                    pass

    tasks = [TaskConfig(path=p) for p in task_dirs]
    cfg = JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=EnvironmentConfig(delete=False),
    )
    return cfg, trial_name_map
