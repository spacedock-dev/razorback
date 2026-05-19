# ABOUTME: Unit tests for spec → harbor JobConfig translation (§6.1).
# ABOUTME: Pins the M1-supported subset; future milestones extend the translator.

from pathlib import Path

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig

from razorback.compat.harbor_0_6_6 import spec_to_job_config
from razorback.spec.parse import parse_spec_text


SPEC = """\
version: 1
experiment: m1-nop
agent:
  kind: nop
benchmark:
  kind: local
  task_paths:
    - examples/tasks/hello-world
trials: 1
observers: []
"""


def test_translator_produces_runnable_job_config(colima_safe_tmp_path):
    spec = parse_spec_text(SPEC)
    cfg = spec_to_job_config(
        spec,
        job_name="abc1234567890def",
        jobs_dir=colima_safe_tmp_path / "jobs",
    )
    assert isinstance(cfg, JobConfig)
    assert cfg.job_name == "abc1234567890def"
    assert cfg.jobs_dir == colima_safe_tmp_path / "jobs"
    assert cfg.n_concurrent_trials == 1
    assert cfg.n_attempts == 1
    assert len(cfg.agents) == 1
    assert cfg.agents[0].name == AgentName.NOP.value
    assert len(cfg.tasks) == 1
    assert Path(cfg.tasks[0].path).name == "hello-world"
    # M1 wants the verifier on (Task 1 proved the contract).
    assert cfg.verifier.disable is False
