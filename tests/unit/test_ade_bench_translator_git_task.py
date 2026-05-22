# ABOUTME: FU-2 — translator materializes git-task entries via materialize_git_task,
# ABOUTME: emitting a LOCAL TaskConfig (no git fields). Slug entries use PKG-40 task views.

import tomllib
from pathlib import Path

from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    AdeBenchTaskEntry,
    NopAgentBlock,
    Spec,
)
from razorback.translate import spec_to_job_config

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


def _stub_materialize(monkeypatch, target_root: Path):
    """Replace materialize_git_task with a copytree of the with-image fixture."""
    import shutil

    fixture = (
        Path(__file__).parent.parent
        / "fixtures"
        / "ade_bench"
        / "fixture_git_task_with_image"
    ).resolve()

    def fake_materialize(*, git_url, git_commit_id, source_path, docker_image, cache_root, _fake_git_source=None):
        target = cache_root / source_path.name
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(fixture, target)
        return target

    monkeypatch.setattr(
        "razorback.benchmarks.ade_bench.tasks.materialize_git_task",
        fake_materialize,
    )


def test_spec_to_job_config_with_git_task(tmp_path, monkeypatch):
    _stub_materialize(monkeypatch, tmp_path)
    spec = _spec_with_tasks([
        AdeBenchTaskEntry(
            path="datasets/ade-bench/ade-bench-airbnb001",
            git_url=GIT_URL,
            git_commit_id=COMMIT,
        )
    ])
    cfg, _ = spec_to_job_config(
        spec, job_name="testjob", jobs_dir=tmp_path, home=tmp_path
    )
    [task] = cfg.tasks
    # FU-2: git entries materialize to LOCAL TaskConfig; git fields are dropped.
    assert task.git_url is None
    assert task.git_commit_id is None
    assert task.is_git_task() is False
    assert task.path is not None
    assert task.path.is_absolute()
    assert (task.path / "task.toml").exists()


def test_spec_to_job_config_with_legacy_slug(tmp_path, monkeypatch):
    _stub_materialize(monkeypatch, tmp_path)
    spec = _spec_with_tasks(["adebench-fixture-001"])
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path, home=tmp_path)
    [task] = cfg.tasks
    assert task.path == (
        tmp_path / "testjob" / "_razorback" / "task_views"
        / "ade-bench-adebench-fixture-001"
    )
    assert (task.path / "view_manifest.json").exists()
    assert task.git_url is None
    assert task.git_commit_id is None
    assert task.is_git_task() is False


def test_spec_to_job_config_with_harbor_task_view_preserves_dockerfile_build(tmp_path):
    tasks_root = tmp_path / "tasks"
    task_dir = tasks_root / "ade-bench-custom001"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        "\n".join(
            [
                'schema_version = "1.0"',
                "[environment]",
                'os = "linux"',
                "cpus = 1",
                "memory_mb = 1024",
                "storage_mb = 1024",
                "[agent]",
                "timeout_sec = 60.0",
                "[verifier]",
                "timeout_sec = 60.0",
                "",
            ]
        )
    )
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.11-slim\n")

    spec = Spec(
        version=1,
        experiment="ade-bench-task-view-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark=AdeBenchBenchmarkBlock(
            kind="ade-bench",
            tasks_root=tasks_root,
            tasks=["ade-bench-custom001"],
        ),
        trials=1,
        observers=[],
    )

    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path, home=tmp_path)
    [task] = cfg.tasks
    task_toml = tomllib.loads((task.path / "task.toml").read_text())

    assert "docker_image" not in task_toml["environment"]


def test_spec_to_job_config_mixed_list(tmp_path, monkeypatch):
    _stub_materialize(monkeypatch, tmp_path)
    spec = _spec_with_tasks([
        "adebench-fixture-001",
        AdeBenchTaskEntry(
            path="datasets/ade-bench/ade-bench-airbnb001",
            git_url=GIT_URL,
            git_commit_id=COMMIT,
        ),
    ])
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path, home=tmp_path)
    assert len(cfg.tasks) == 2
    legacy, git = cfg.tasks
    assert legacy.is_git_task() is False
    assert legacy.path == (
        tmp_path / "testjob" / "_razorback" / "task_views"
        / "ade-bench-adebench-fixture-001"
    )
    # FU-2: git entry is now LOCAL after materialization.
    assert git.is_git_task() is False
    assert git.path is not None
    assert git.path.is_absolute()
