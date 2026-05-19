# ABOUTME: Spec → harbor 0.6.6 JobConfig translator (§6.1).
# ABOUTME: Supports agent.kind=nop and benchmark.kind ∈ {local, dab}.

from pathlib import Path

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig, RetryConfig
from harbor.models.trial.config import AgentConfig, TaskConfig, VerifierConfig

from razorback.benchmarks.dab.prepare import prepare_dataset_tasks
from razorback.errors import SpecError
from razorback.spec.schema import DabBenchmarkBlock, LocalBenchmarkBlock, Spec


def spec_to_job_config(
    spec: Spec,
    *,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path | None = None,
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    """Translate a parsed spec into a harbor JobConfig and a trial_name_map.

    Returns a 2-tuple: (JobConfig, trial_name_map). The map keys are the trial_name
    prefixes harbor will assign (`<task_name>__<uuid7>`); values are (dataset, query_id).
    For non-DAB benchmarks the map is empty.

    `tasks_root` is required for DAB specs (where prepared task dirs land). The run
    orchestrator passes `run_dir / "tasks"`. Local-benchmark specs may omit it.
    """
    if spec.agent.kind != "nop":
        raise SpecError(
            f"agent.kind=nop only (got {spec.agent.kind!r}); ClaudeCliAgent lands in M3."
        )

    if isinstance(spec.benchmark, LocalBenchmarkBlock):
        return _build_local(spec=spec, job_name=job_name, jobs_dir=jobs_dir), {}

    if isinstance(spec.benchmark, DabBenchmarkBlock):
        if tasks_root is None:
            raise SpecError("DAB specs require tasks_root (the run orchestrator passes it).")
        return _build_dab(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            tasks_root=Path(tasks_root),
        )

    raise SpecError(f"unsupported benchmark block: {type(spec.benchmark).__name__}")


def _build_local(*, spec: Spec, job_name: str, jobs_dir: Path) -> JobConfig:
    assert isinstance(spec.benchmark, LocalBenchmarkBlock)
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[AgentConfig(name=AgentName.NOP.value)],
        tasks=[TaskConfig(path=Path(p).resolve()) for p in spec.benchmark.task_paths],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
    )


def _build_dab(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path,
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    assert isinstance(spec.benchmark, DabBenchmarkBlock)
    manifest_all: list[dict] = []
    for dataset in spec.benchmark.datasets:
        manifest_all.extend(
            prepare_dataset_tasks(
                data_root=Path(spec.benchmark.data_root),
                dataset=dataset,
                tasks_root=tasks_root / dataset,
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
        agents=[AgentConfig(name=AgentName.NOP.value)],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
    )
    return cfg, trial_name_map
