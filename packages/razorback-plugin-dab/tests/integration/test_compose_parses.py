# ABOUTME: PKG-13 T4 — `docker compose config -q` parses the generated tree.
# ABOUTME: AC-2 runtime side: catches bind-mount path resolution at compose parse time.

import shutil
import subprocess
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


def _build_synthetic_data_root(root: Path) -> Path:
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


def test_docker_compose_config_parses_generated_tree(tmp_path: Path):
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not on PATH")

    data_root = _build_synthetic_data_root(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="bookreview", tasks_root=out)
    compose_path = manifest[0]["task_dir"] / "environment" / "docker-compose.yaml"
    assert compose_path.exists()

    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "config", "-q"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"docker compose config -q failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
