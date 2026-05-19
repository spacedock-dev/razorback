# ABOUTME: FU-1 AC-3 — translator emits a harbor TaskConfig with git_url + git_commit_id
# ABOUTME: + relative path populated when the spec entry is a git-task entry.

from pathlib import Path

from harbor.models.task.id import GitTaskId

from razorback.compat import spec_to_job_config
from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    AdeBenchTaskEntry,
    NopAgentBlock,
    Spec,
)

FIXTURE_TASKS = Path(__file__).parent.parent / "fixtures" / "ade_bench" / "tasks"
GIT_URL = "https://github.com/laude-institute/harbor-datasets.git"
COMMIT = "b4e82debfdd2aba9d91c41cd96a997dd549fcbb3"


def _spec_with_tasks(tasks: list) -> Spec:
    return Spec(
        version=1,
        experiment="ade-bench-git-task-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark=AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=FIXTURE_TASKS,
            tasks=tasks,
        ),
        trials=1,
        observers=[],
    )


def test_spec_to_job_config_with_git_task(tmp_path):
    spec = _spec_with_tasks([
        AdeBenchTaskEntry(
            path="datasets/ade-bench/ade-bench-airbnb001",
            git_url=GIT_URL,
            git_commit_id=COMMIT,
        )
    ])
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    [task] = cfg.tasks
    assert task.path == Path("datasets/ade-bench/ade-bench-airbnb001")
    assert task.git_url == GIT_URL
    assert task.git_commit_id == COMMIT
    assert task.is_git_task() is True
    task_id = task.get_task_id()
    assert isinstance(task_id, GitTaskId)


def test_spec_to_job_config_with_legacy_slug(tmp_path):
    spec = _spec_with_tasks(["adebench-fixture-001"])
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    [task] = cfg.tasks
    assert task.path == (FIXTURE_TASKS / "adebench-fixture-001").resolve()
    assert task.git_url is None
    assert task.git_commit_id is None
    assert task.is_git_task() is False


def test_spec_to_job_config_mixed_list(tmp_path):
    spec = _spec_with_tasks([
        "adebench-fixture-001",
        AdeBenchTaskEntry(
            path="datasets/ade-bench/ade-bench-airbnb001",
            git_url=GIT_URL,
            git_commit_id=COMMIT,
        ),
    ])
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert len(cfg.tasks) == 2
    legacy, git = cfg.tasks
    assert legacy.is_git_task() is False
    assert legacy.path == (FIXTURE_TASKS / "adebench-fixture-001").resolve()
    assert git.is_git_task() is True
    assert git.git_url == GIT_URL
    assert git.git_commit_id == COMMIT
