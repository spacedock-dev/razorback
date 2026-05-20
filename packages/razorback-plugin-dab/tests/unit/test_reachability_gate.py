# ABOUTME: PKG-13 T5 — bookreview reachability gate emits per-step healthcheck (AC-3).
# ABOUTME: psql probe lands as [steps.healthcheck]; sqlite-only datasets get no gate.

import tomllib
from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


_BOOKREVIEW_DB_CONFIG = {
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
}


def _scaffold(root: Path, *, dataset: str, db_config: dict, sql_present: bool = True) -> Path:
    data_root = root / "data"
    qdir = data_root / f"query_{dataset}"
    qdir.mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump(db_config))
    (qdir / "db_description.txt").write_text("schema")
    qd = qdir / "query_dataset"
    qd.mkdir()
    if sql_present:
        (qd / "books_info.sql").write_text("-- sql\n")
    (qd / "review_query.db").write_bytes(b"SQLite format 3\x00")
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "q"}')
    (q1 / "validate.py").write_text("def validate(a):\n    return (True, 'ok')\n")
    return data_root


def test_bookreview_emits_postgres_reachability_healthcheck(tmp_path: Path):
    """PKG-13 T5 / T10: the gate is a python3 TCP probe against dab-postgres.

    dab-agent:latest does not ship a postgres client; the probe is a python
    socket.create_connection. Postgres-protocol readiness is enforced by
    compose's depends_on: condition: service_healthy + dab-postgres's
    pg_isready healthcheck, so the TCP probe is the right shape for
    fail-fast detection.
    """
    data_root = _scaffold(tmp_path, dataset="bookreview", db_config=_BOOKREVIEW_DB_CONFIG)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="bookreview", tasks_root=out)
    task_toml = tomllib.loads((manifest[0]["task_dir"] / "task.toml").read_text())
    steps = task_toml["steps"]
    assert len(steps) == 1
    hc = steps[0]["healthcheck"]
    assert "python3" in hc["command"]
    assert "dab-postgres" in hc["command"]
    assert "5432" in hc["command"]
    assert hc["retries"] == 6
    assert hc["start_period_sec"] == 30


def test_sqlite_only_dataset_emits_no_healthcheck(tmp_path: Path):
    sqlite_only = {
        "db_clients": {
            "review_database": {
                "db_type": "sqlite",
                "db_path": "query_dataset/review_query.db",
            }
        }
    }
    # Reuse bookreview's catalog entry, but with a sqlite-only db_config; the
    # postgres-conditional gate must not fire.
    data_root = _scaffold(tmp_path, dataset="bookreview", db_config=sqlite_only)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="bookreview", tasks_root=out)
    task_toml = tomllib.loads((manifest[0]["task_dir"] / "task.toml").read_text())
    steps = task_toml["steps"]
    assert "healthcheck" not in steps[0]
