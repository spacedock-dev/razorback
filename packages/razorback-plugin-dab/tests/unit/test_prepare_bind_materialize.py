# ABOUTME: PKG-14 AC-2 + AC-4 — bind mode skips per-task SQL dump copy (≤10MB);
# ABOUTME: copy mode restores the dump alongside other dataset payload in workdir.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


def _build_bookreview_data_root(root: Path, dump_size_mb: int = 50) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    (qdir / "query_dataset").mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump({
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": "query_dataset/books_info.sql",
            },
            "review_database": {
                "db_type": "sqlite",
                "db_path": "query_dataset/review_query.db",
            },
        }
    }))
    (qdir / "db_description.txt").write_text("Bookreview schema.")
    # Large synthetic dump — the file PKG-14 must NOT copy under bind mode.
    (qdir / "query_dataset" / "books_info.sql").write_bytes(b"X" * (dump_size_mb * 1024 * 1024))
    (qdir / "query_dataset" / "review_query.db").write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "How many books?"}')
    return data_root


def _du_bytes(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def test_bind_mode_task_dir_under_10mb(tmp_path: Path):
    """AC-2: under bind mode, the per-task dir contains no dataset SQL dump."""
    data_root = _build_bookreview_data_root(tmp_path, dump_size_mb=50)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    task_dir = manifest[0]["task_dir"]
    size = _du_bytes(task_dir)
    # 10MB allowance covers task.toml + instruction.md + compose + sqlite live DB
    # (the .db file IS copied; it's the live DB, not a dump). The 50MB dump
    # must not be copied.
    assert size <= 10 * 1024 * 1024, (
        f"AC-2: bind-mode task-dir is {size / (1024*1024):.1f}MB, expected ≤10MB"
    )


def test_bind_mode_no_sql_dump_in_workdir(tmp_path: Path):
    """AC-1: bind mode must not copy the postgres SQL dump into the agent workdir."""
    data_root = _build_bookreview_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    task_dir = manifest[0]["task_dir"]
    workdir = task_dir / "steps" / "main" / "workdir"
    assert not (workdir / "query_dataset" / "books_info.sql").exists(), (
        "AC-1: bind mode must not stage the SQL dump in the agent workdir"
    )


def test_copy_mode_keeps_sql_dump_in_workdir(tmp_path: Path):
    """AC-4: --materialize=copy restores the pre-PKG-14 copy behavior."""
    data_root = _build_bookreview_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="copy",
    )
    task_dir = manifest[0]["task_dir"]
    workdir = task_dir / "steps" / "main" / "workdir"
    assert (workdir / "query_dataset" / "books_info.sql").exists(), (
        "AC-4: copy mode must keep the SQL dump in the agent workdir"
    )


def test_bind_mode_keeps_sqlite_live_db_in_workdir(tmp_path: Path):
    """PKG-14 leaves sqlite/duckdb live-DB files in workdir — only dumps are excluded."""
    data_root = _build_bookreview_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    assert (workdir / "query_dataset" / "review_query.db").exists(), (
        "sqlite is a file-backed live DB — must remain in workdir"
    )


def test_invalid_materialize_mode_rejected(tmp_path: Path):
    data_root = _build_bookreview_data_root(tmp_path)
    with pytest.raises(ValueError, match="materialize_mode"):
        prepare_dataset_tasks(
            data_root=data_root,
            dataset="bookreview",
            tasks_root=tmp_path / "tasks",
            materialize_mode="symlink",
        )
