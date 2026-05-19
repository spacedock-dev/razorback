# ABOUTME: ade-bench tasks loader — accepts a tasks_root + slugs; validates harbor task layout.

from pathlib import Path

import pytest

from razorback.benchmarks.ade_bench.tasks import resolve_task_dirs

FIXTURE_TASKS = Path(__file__).parent.parent / "fixtures" / "ade_bench" / "tasks"


def test_resolves_known_slug_to_absolute_path():
    paths = resolve_task_dirs(
        tasks_root=FIXTURE_TASKS, tasks=["adebench-fixture-001"]
    )
    assert len(paths) == 1
    assert paths[0].is_absolute()
    assert paths[0].name == "adebench-fixture-001"
    assert (paths[0] / "task.toml").exists()


def test_raises_filenotfound_on_unknown_slug():
    with pytest.raises(FileNotFoundError) as exc:
        resolve_task_dirs(tasks_root=FIXTURE_TASKS, tasks=["does-not-exist"])
    assert "does-not-exist" in str(exc.value)
    assert "task.toml" in str(exc.value)


def test_raises_when_task_toml_missing(tmp_path):
    bad = tmp_path / "broken-task"
    bad.mkdir()
    (bad / "README.md").write_text("no task.toml here")
    with pytest.raises(FileNotFoundError) as exc:
        resolve_task_dirs(tasks_root=tmp_path, tasks=["broken-task"])
    assert "broken-task" in str(exc.value)


def test_resolves_multiple_slugs_in_order():
    paths = resolve_task_dirs(
        tasks_root=FIXTURE_TASKS,
        tasks=["adebench-fixture-001", "adebench-fixture-001"],
    )
    assert len(paths) == 2
    assert paths[0] == paths[1]
