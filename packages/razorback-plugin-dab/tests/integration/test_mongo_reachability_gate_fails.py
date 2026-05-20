# ABOUTME: PKG-15 AC-2 negative path — mongo content-presence probe exits non-zero
# ABOUTME: when dab-mongo is unreachable (closes Bug 2 fail-fast contract).

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


_AGNEWS_LIKE = {
    "db_clients": {
        "articles_database": {
            "db_type": "mongo",
            "db_name": "articles_db",
            "dump_folder": "query_dataset/agnews_articles",
        },
        "metadata_database": {
            "db_type": "sqlite",
            "db_path": "query_dataset/metadata.db",
        },
    }
}


def _scaffold(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_agnews"
    qdir.mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump(_AGNEWS_LIKE))
    (qdir / "db_description.txt").write_text("schema")
    qd = qdir / "query_dataset"
    qd.mkdir()
    dump_dir = qd / "agnews_articles" / "articles_db"
    dump_dir.mkdir(parents=True)
    (dump_dir / "articles.bson").write_bytes(b"\x00")
    (dump_dir / "articles.metadata.json").write_text("{}")
    (qd / "metadata.db").write_bytes(b"SQLite format 3\x00")
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "q"}')
    (q1 / "validate.py").write_text("def validate(a):\n    return (True, 'ok')\n")
    return data_root


def test_mongo_reachability_gate_fails_when_dab_mongo_unreachable(tmp_path: Path):
    """AC-2 negative path: gate exits non-zero when mongosh can't reach dab-mongo.

    Run from the host where `dab-mongo` doesn't resolve to model the
    "compose not loaded / mongorestore did not run" failure mode.
    Skipped if mongosh is not on PATH (it lives in dab-agent:latest; the
    host CI runner may not have it).
    """
    if shutil.which("mongosh") is None:
        pytest.skip("mongosh not on host PATH (it lives in container only)")

    data_root = _scaffold(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="agnews", tasks_root=out)
    task_toml = tomllib.loads((manifest[0]["task_dir"] / "task.toml").read_text())
    command = task_toml["steps"][0]["healthcheck"]["command"].replace('\\"', '"')

    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode != 0, (
        f"gate unexpectedly succeeded: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert re.search(
        r"(nodename nor servname|name or service not known|getaddrinfo|connection refused|server selection|host)",
        combined,
    ), f"expected connection-failure text; got: {combined!r}"
