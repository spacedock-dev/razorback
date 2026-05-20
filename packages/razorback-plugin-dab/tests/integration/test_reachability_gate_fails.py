# ABOUTME: PKG-13 T6 — reachability gate exits non-zero when dab-postgres is unreachable.
# ABOUTME: AC-3 verified-by: validates the gate's failure shape without pulling postgres.

import re
import shutil
import subprocess
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


def _scaffold(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    qdir.mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump(_BOOKREVIEW_DB_CONFIG))
    (qdir / "db_description.txt").write_text("schema")
    qd = qdir / "query_dataset"
    qd.mkdir()
    (qd / "books_info.sql").write_text("-- sql\n")
    (qd / "review_query.db").write_bytes(b"SQLite format 3\x00")
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "q"}')
    (q1 / "validate.py").write_text("def validate(a):\n    return (True, 'ok')\n")
    return data_root


def test_psql_gate_fails_when_dab_postgres_unreachable(tmp_path: Path):
    """AC-3 negative path: when dab-postgres can't be resolved (postgres
    container not running or compose stack not loaded), the healthcheck
    command exits non-zero with a psql / hostname-resolution error.

    We exercise the failure shape directly with `psql` rather than
    bringing up a deliberately broken compose stack — pulling postgres:17
    is expensive and the failure shape is what AC-3 actually verifies.
    """
    if shutil.which("psql") is None:
        pytest.skip("psql client not installed on host")

    data_root = _scaffold(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="bookreview", tasks_root=out)
    task_toml = tomllib.loads((manifest[0]["task_dir"] / "task.toml").read_text())
    command = task_toml["steps"][0]["healthcheck"]["command"]

    # Run the command as the host would — `dab-postgres` does not resolve from
    # outside the compose network, so this models the "compose not loaded /
    # postgres not running" failure mode AC-3 fails fast on.
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=15,
        env={"PGCONNECT_TIMEOUT": "3"},
    )
    assert result.returncode != 0, (
        f"psql gate unexpectedly succeeded: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert re.search(r"(could not translate host name|connection refused|could not connect|name or service not known|name resolution|unknown host)", combined), (
        f"expected connection-failure text in psql output; got: {combined!r}"
    )
