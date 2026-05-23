# ABOUTME: FU-2 AC-2 — translator routes git entries through materialize_git_task
# ABOUTME: with the resolved docker_image override; emits LOCAL TaskConfig for git entries.

from pathlib import Path

import pytest

from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    AdeBenchTaskEntry,
    NopAgentBlock,
    Spec,
)
from razorback.translate import spec_to_job_config


GIT_URL = "https://github.com/laude-institute/harbor-datasets.git"
COMMIT = "b4e82debfdd2aba9d91c41cd96a997dd549fcbb3"

FIXTURE_TASKS = (
    Path(__file__).parent.parent / "fixtures" / "ade_bench" / "tasks"
).resolve()


def _spec_with_tasks(tasks: list, override: str | None = None) -> Spec:
    block_kwargs = dict(
        kind="ade-bench",
        tasks_root=FIXTURE_TASKS,
        tasks=tasks,
    )
    if override is not None:
        block_kwargs["docker_image_override"] = override
    return Spec(
        version=1,
        experiment="fu2-translator",
        agent=NopAgentBlock(kind="nop"),
        benchmark=AdeBenchBenchmarkBlock(**block_kwargs),
        trials=1,
        observers=[],
    )


def _git_entry() -> AdeBenchTaskEntry:
    return AdeBenchTaskEntry(
        path="datasets/ade-bench/ade-bench-airbnb001",
        git_url=GIT_URL,
        git_commit_id=COMMIT,
    )


def _record_materialize_calls(monkeypatch, fake_target_root: Path):
    """Replace materialize_git_task with a recording stub returning a fake dir."""
    calls: list[dict] = []

    def fake_materialize(*, git_url, git_commit_id, source_path, docker_image, cache_root, _fake_git_source=None):
        calls.append({
            "git_url": git_url,
            "git_commit_id": git_commit_id,
            "source_path": source_path,
            "docker_image": docker_image,
            "cache_root": cache_root,
        })
        target = fake_target_root / source_path.name
        target.mkdir(parents=True, exist_ok=True)
        (target / "task.toml").write_text(
            'version = "1.0"\n[environment]\ndocker_image = "%s"\n' % docker_image
        )
        return target

    monkeypatch.setattr(
        "razorback.benchmarks.ade_bench.tasks.materialize_git_task",
        fake_materialize,
    )
    return calls


def test_translator_uses_default_docker_image_when_override_omitted(monkeypatch, tmp_path):
    calls = _record_materialize_calls(monkeypatch, tmp_path / "fake-cache")
    spec = _spec_with_tasks([_git_entry()])
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert len(calls) == 1
    assert calls[0]["docker_image"] == "dab-agent:latest"


def test_translator_uses_custom_override(monkeypatch, tmp_path):
    calls = _record_materialize_calls(monkeypatch, tmp_path / "fake-cache")
    spec = _spec_with_tasks([_git_entry()], override="custom-agent:stable")
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert len(calls) == 1
    assert calls[0]["docker_image"] == "custom-agent:stable"


def test_translator_emits_local_task_config_for_git_entries(monkeypatch, tmp_path):
    _record_materialize_calls(monkeypatch, tmp_path / "fake-cache")
    spec = _spec_with_tasks([_git_entry()])
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    [task] = cfg.tasks
    assert task.git_url is None
    assert task.git_commit_id is None
    assert task.is_git_task() is False
    assert task.path is not None
    assert task.path.is_absolute()


def test_translator_passes_through_local_slug_unchanged(monkeypatch, tmp_path):
    # Build a local slug fixture inside FIXTURE_TASKS that the loader can resolve.
    slug_dir = FIXTURE_TASKS / "adebench-fixture-001"
    assert (slug_dir / "task.toml").exists(), (
        "Pre-existing FU-1 fixture missing — investigate"
    )
    calls = _record_materialize_calls(monkeypatch, tmp_path / "fake-cache")
    spec = _spec_with_tasks(["adebench-fixture-001", _git_entry()])
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert len(cfg.tasks) == 2
    legacy, git = cfg.tasks
    assert legacy.is_git_task() is False
    assert legacy.path == (
        tmp_path / "testjob" / "_razorback" / "task_views"
        / "ade-bench-adebench-fixture-001"
    )
    # materialize_git_task was called exactly once — for the git entry only.
    assert len(calls) == 1
