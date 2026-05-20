# ABOUTME: PKG-14 AC-3 — agent container cannot mutate bind-mounted source data.
# ABOUTME: docker compose up dab-postgres; exec a write attempt; assert EROFS / non-zero exit.

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="docker not available — AC-3 EROFS contract is a live test",
)


def _bookreview_data_root(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    (qdir / "query_dataset").mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump({
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": "query_dataset/books_info.sql",
            }
        }
    }))
    (qdir / "db_description.txt").write_text("Bookreview schema.")
    (qdir / "query_dataset" / "books_info.sql").write_text(
        "CREATE TABLE books (id INT);\n"
    )
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "synthetic"}')
    return data_root


def test_bind_mounted_source_is_read_only(tmp_path: Path):
    data_root = _bookreview_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    compose_dir = manifest[0]["task_dir"] / "environment"
    project = f"pkg14-readonly-{os.getpid()}"
    original_bytes = (data_root / "query_bookreview" / "query_dataset" / "books_info.sql").read_bytes()
    try:
        up = subprocess.run(
            ["docker", "compose", "-p", project, "-f", "docker-compose.yaml",
             "up", "-d", "--wait", "dab-postgres"],
            cwd=compose_dir, check=False, capture_output=True, text=True, timeout=180,
        )
        if up.returncode != 0:
            pytest.skip(f"compose up failed (likely no daemon): {up.stderr}")
        result = subprocess.run(
            ["docker", "compose", "-p", project, "-f", "docker-compose.yaml",
             "exec", "-T", "dab-postgres", "sh", "-c",
             "echo X >> /docker-entrypoint-initdb.d/books_info.sql 2>&1; echo EXIT=$?"],
            cwd=compose_dir, check=True, capture_output=True, text=True, timeout=30,
        )
        assert "EXIT=0" not in result.stdout, (
            f"AC-3: write to bind-mounted source unexpectedly succeeded:\n{result.stdout}"
        )
        # Host source file is unchanged.
        host_bytes = (data_root / "query_bookreview" / "query_dataset" / "books_info.sql").read_bytes()
        assert host_bytes == original_bytes, (
            "AC-3: host source file was modified by container write attempt"
        )
    finally:
        subprocess.run(
            ["docker", "compose", "-p", project, "-f", "docker-compose.yaml",
             "down", "-v", "--remove-orphans"],
            cwd=compose_dir, check=False, capture_output=True, timeout=60,
        )
