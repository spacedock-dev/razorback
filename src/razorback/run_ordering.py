from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from harbor.models.trial.config import TaskConfig


ORDERING_MODE = "longest-known-first"


@dataclass
class OrderingHintSummary:
    source_path: str
    mode: str = ORDERING_MODE
    durations_by_task_key: dict[str, float] = field(default_factory=dict)
    usable_timing_count: int = 0
    ignored_timing_count: int = 0
    warnings: list[str] = field(default_factory=list)


def load_wallclock_hints(path: Path) -> OrderingHintSummary:
    """Load historical per-task elapsed seconds from a run dir or result JSON."""
    source = Path(path).expanduser()
    summary = OrderingHintSummary(source_path=str(source))
    result_paths = _discover_result_paths(source)
    if not result_paths:
        if not source.is_dir():
            _warn(summary, f"{source}: no trial result.json files found")
        return summary

    for result_path in result_paths:
        payload = _read_result_json(result_path, summary)
        if payload is None:
            continue
        rows = list(_iter_trial_like_records(payload))
        if not rows:
            rows = [payload]
        if source.is_file() and rows == [payload] and _task_key_from_result(payload) is None:
            _warn(summary, f"{result_path}: no usable per-task timing")
            continue
        usable_before = summary.usable_timing_count
        for row in rows:
            _record_timing(summary, result_path, row)
        if source.is_file() and summary.usable_timing_count == usable_before:
            _warn(summary, f"{result_path}: no usable per-task timing")
    return summary


def apply_wallclock_ordering(
    tasks: Sequence[TaskConfig], summary: OrderingHintSummary
) -> tuple[list[TaskConfig], dict[str, Any]]:
    """Return tasks sorted longest-known-first, with stable ties and unknowns."""
    indexed: list[tuple[int, TaskConfig, str, float | None]] = []
    for index, task in enumerate(tasks):
        key = _task_key_from_task_config(task)
        indexed.append((index, task, key, summary.durations_by_task_key.get(key)))

    def sort_key(item: tuple[int, TaskConfig, str, float | None]) -> tuple[int, float, int]:
        index, _task, _key, duration = item
        if duration is None:
            return (1, 0.0, index)
        return (0, -duration, index)

    ordered = [task for _index, task, _key, _duration in sorted(indexed, key=sort_key)]
    matched = sum(1 for _index, _task, _key, duration in indexed if duration is not None)
    metadata = {
        "mode": ORDERING_MODE,
        "source_path": summary.source_path,
        "usable_timing_count": summary.usable_timing_count,
        "matched_task_count": matched,
        "unmatched_task_count": len(indexed) - matched,
        "ignored_timing_count": summary.ignored_timing_count,
    }
    return ordered, metadata


def _discover_result_paths(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if not source.is_dir():
        return []
    out: list[Path] = []
    for child in sorted(source.iterdir()):
        if not child.is_dir():
            continue
        result_path = child / "result.json"
        if result_path.exists():
            out.append(result_path)
    return out


def _read_result_json(path: Path, summary: OrderingHintSummary) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        _warn(summary, f"{path}: malformed result JSON ({exc})")
        return None
    if not isinstance(payload, dict):
        _warn(summary, f"{path}: result JSON is not an object")
        return None
    return payload


def _iter_trial_like_records(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("trials", "trial_results", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield item


def _record_timing(summary: OrderingHintSummary, path: Path, row: dict[str, Any]) -> None:
    task_key = _task_key_from_result(row)
    if task_key is None:
        _warn(summary, f"{path}: missing task identity")
        return
    started_raw = row.get("started_at")
    finished_raw = row.get("finished_at")
    if started_raw is None:
        _warn(summary, f"{path}: missing started_at")
        return
    if finished_raw is None:
        _warn(summary, f"{path}: missing finished_at")
        return
    started = _parse_timestamp(started_raw)
    if started is None:
        _warn(summary, f"{path}: malformed started_at")
        return
    finished = _parse_timestamp(finished_raw)
    if finished is None:
        _warn(summary, f"{path}: malformed finished_at")
        return
    elapsed = (finished - started).total_seconds()
    if elapsed <= 0:
        _warn(summary, f"{path}: non-positive elapsed wallclock")
        return
    summary.usable_timing_count += 1
    previous = summary.durations_by_task_key.get(task_key)
    if previous is None or elapsed > previous:
        summary.durations_by_task_key[task_key] = elapsed


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _task_key_from_result(row: dict[str, Any]) -> str | None:
    task_name = row.get("task_name")
    if isinstance(task_name, str) and task_name:
        return task_name
    task_id = row.get("task_id")
    if isinstance(task_id, dict):
        path_value = task_id.get("path")
        if isinstance(path_value, str) and path_value:
            return Path(path_value).name
    trial_name = row.get("trial_name")
    if isinstance(trial_name, str) and trial_name:
        return trial_name.split("__", 1)[0]
    return None


def _task_key_from_task_config(task: TaskConfig) -> str:
    return Path(task.path).name


def _warn(summary: OrderingHintSummary, warning: str) -> None:
    summary.ignored_timing_count += 1
    summary.warnings.append(warning)
