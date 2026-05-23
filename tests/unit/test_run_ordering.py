import json
from pathlib import Path

from harbor.models.trial.config import TaskConfig

from razorback.run_ordering import apply_wallclock_ordering, load_wallclock_hints


def _write_trial_result(
    run_dir: Path,
    name: str,
    *,
    task_name: str | None = None,
    started_at: str | None = "2026-05-23T00:00:00Z",
    finished_at: str | None = "2026-05-23T00:02:00Z",
) -> Path:
    trial_dir = run_dir / name
    trial_dir.mkdir(parents=True)
    payload: dict = {
        "trial_name": name,
        "task_id": {"path": f"/tmp/tasks/{name.split('__', 1)[0]}"},
    }
    if task_name is not None:
        payload["task_name"] = task_name
    if started_at is not None:
        payload["started_at"] = started_at
    if finished_at is not None:
        payload["finished_at"] = finished_at
    (trial_dir / "result.json").write_text(json.dumps(payload))
    return trial_dir / "result.json"


def test_load_wallclock_hints_uses_max_elapsed_and_ignores_bad_rows(tmp_path: Path) -> None:
    run_dir = tmp_path / "historical"
    run_dir.mkdir()
    (run_dir / "result.json").write_text("{}")
    _write_trial_result(run_dir, "task-a__first", task_name="task-a")
    _write_trial_result(
        run_dir,
        "task-a__second",
        task_name="task-a",
        started_at="2026-05-23T00:00:00Z",
        finished_at="2026-05-23T00:04:00Z",
    )
    missing_path = _write_trial_result(
        run_dir,
        "task-b__missing",
        task_name="task-b",
        finished_at=None,
    )
    malformed_path = _write_trial_result(
        run_dir,
        "task-c__malformed",
        task_name="task-c",
        started_at="not-a-date",
    )

    summary = load_wallclock_hints(run_dir)

    assert summary.durations_by_task_key == {"task-a": 240.0}
    assert summary.usable_timing_count == 2
    assert summary.ignored_timing_count == 2
    warnings = "\n".join(summary.warnings)
    assert str(missing_path) in warnings
    assert "missing finished_at" in warnings
    assert str(malformed_path) in warnings
    assert "malformed started_at" in warnings


def test_load_wallclock_hints_can_parse_single_result_file_by_trial_name(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "trial_name": "task-from-trial__abcdef",
                "started_at": "2026-05-23T00:00:00Z",
                "finished_at": "2026-05-23T00:00:30Z",
            }
        )
    )

    summary = load_wallclock_hints(result_path)

    assert summary.durations_by_task_key == {"task-from-trial": 30.0}
    assert summary.usable_timing_count == 1
    assert summary.ignored_timing_count == 0


def test_load_wallclock_hints_warns_for_unusable_single_result_file(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({"started_at": "2026-05-23T00:00:00Z"}))

    summary = load_wallclock_hints(result_path)

    assert summary.durations_by_task_key == {}
    assert summary.usable_timing_count == 0
    assert summary.ignored_timing_count == 1
    assert any("no usable per-task timing" in warning for warning in summary.warnings)


def test_apply_wallclock_ordering_sorts_known_tasks_longest_first(tmp_path: Path) -> None:
    tasks = [TaskConfig(path=tmp_path / name) for name in ("a", "b", "c", "d")]
    summary = load_wallclock_hints(tmp_path)
    summary.durations_by_task_key.update({"b": 30.0, "d": 90.0})

    ordered, metadata = apply_wallclock_ordering(tasks, summary)

    assert [task.path.name for task in ordered] == ["d", "b", "a", "c"]
    assert metadata == {
        "mode": "longest-known-first",
        "source_path": str(tmp_path),
        "usable_timing_count": 0,
        "matched_task_count": 2,
        "unmatched_task_count": 2,
        "ignored_timing_count": 0,
    }


def test_apply_wallclock_ordering_preserves_ties_and_empty_summary(tmp_path: Path) -> None:
    tasks = [TaskConfig(path=tmp_path / name) for name in ("a", "b", "c")]
    summary = load_wallclock_hints(tmp_path)
    summary.durations_by_task_key.update({"a": 10.0, "b": 10.0})

    ordered, _metadata = apply_wallclock_ordering(tasks, summary)

    assert [task.path.name for task in ordered] == ["a", "b", "c"]

    empty = load_wallclock_hints(tmp_path)
    same_order, _metadata = apply_wallclock_ordering(tasks, empty)
    assert same_order == tasks
