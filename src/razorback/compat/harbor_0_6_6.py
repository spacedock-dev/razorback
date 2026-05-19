# ABOUTME: Spec → harbor 0.6.6 JobConfig translator (§6.1).
# ABOUTME: M1 supports agent.kind=nop and benchmark.kind=local only.

from pathlib import Path

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig
from harbor.models.trial.config import AgentConfig, TaskConfig, VerifierConfig

from razorback.errors import SpecError
from razorback.spec.schema import Spec


def spec_to_job_config(spec: Spec, *, job_name: str, jobs_dir: Path) -> JobConfig:
    if spec.agent.kind != "nop":
        raise SpecError(f"M1 only supports agent.kind=nop, got {spec.agent.kind!r}")
    if spec.benchmark.kind != "local":
        raise SpecError(f"M1 only supports benchmark.kind=local, got {spec.benchmark.kind!r}")

    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[AgentConfig(name=AgentName.NOP.value)],
        tasks=[TaskConfig(path=Path(p).resolve()) for p in spec.benchmark.task_paths],
        verifier=VerifierConfig(disable=False),
    )
