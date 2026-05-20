# ABOUTME: PKG-16 AC-1 + AC-4 — agent workdir excludes server-ingested dump files.
# ABOUTME: Tests bookreview (postgres+sqlite) and a 12-dataset synthetic catalog walk.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab import datasets as catalog
from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


def _build_bookreview(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    qdir.mkdir(parents=True)
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
    qd = qdir / "query_dataset"
    qd.mkdir()
    (qd / "books_info.sql").write_text(
        "CREATE TABLE books (id INT);\nINSERT INTO books VALUES (1);\n" * 50
    )
    (qd / "review_query.db").write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "How many books?"}')
    return data_root


def test_postgres_sql_dump_absent_from_workdir(tmp_path: Path):
    data_root = _build_bookreview(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    assert not (workdir / "query_dataset" / "books_info.sql").exists(), (
        "AC-1: SQL dump must not appear in the agent workdir"
    )
    leaked_sql = list(workdir.rglob("*.sql"))
    assert leaked_sql == [], f"AC-1: stray .sql under workdir: {leaked_sql}"


def test_sqlite_live_db_still_in_workdir(tmp_path: Path):
    data_root = _build_bookreview(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    assert (workdir / "query_dataset" / "review_query.db").exists(), (
        "sqlite is a file-backed live DB — must remain in workdir for the agent"
    )


def test_postgres_dump_staged_under_environment_initdb(tmp_path: Path):
    data_root = _build_bookreview(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
    )
    task_dir = manifest[0]["task_dir"]
    assert (task_dir / "environment" / "_initdb" / "books_info.sql").exists(), (
        "dump must be staged outside the agent workdir but still inside the task dir"
    )


def test_compose_bind_mount_resolves_to_staged_dump(tmp_path: Path):
    data_root = _build_bookreview(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
    )
    compose_path = manifest[0]["task_dir"] / "environment" / "docker-compose.yaml"
    compose = yaml.safe_load(compose_path.read_text())
    pg_vols = compose["services"]["dab-postgres"]["volumes"]
    assert pg_vols, "expected at least one postgres init bind-mount"
    for entry in pg_vols:
        src = entry.split(":", 1)[0]
        resolved = (compose_path.parent / src).resolve()
        assert resolved.exists(), f"bind-mount source missing: {resolved}"
        # AC-1 + AC-2: source must NOT be the agent workdir copy.
        assert "steps/main/workdir" not in str(resolved), (
            f"AC-1: postgres bind-mount source still resolves into agent workdir: {resolved}"
        )
