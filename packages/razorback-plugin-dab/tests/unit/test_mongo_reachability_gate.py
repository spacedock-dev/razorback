# ABOUTME: PKG-15 AC-2 — mongo dataset emits [steps.healthcheck] with a content-presence probe.
# ABOUTME: TCP-only would not have caught Bug 1 from the dab-mongo-probe; we probe a doc count.

import tomllib
from pathlib import Path

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


def test_mongo_dataset_emits_content_presence_healthcheck(tmp_path: Path):
    data_root = _scaffold(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="agnews", tasks_root=out)
    task_toml = tomllib.loads((manifest[0]["task_dir"] / "task.toml").read_text())
    hc = task_toml["steps"][0]["healthcheck"]
    cmd = hc["command"]
    assert "python3 -c" in cmd
    assert "pymongo" in cmd
    assert "MongoClient" in cmd
    assert "dab-mongo" in cmd
    assert "articles_db" in cmd
    assert "articles" in cmd
    assert "count_documents" in cmd
    assert "limit=1" in cmd
    assert hc["retries"] >= 3


def test_mongo_only_dataset_no_postgres_gate(tmp_path: Path):
    data_root = _scaffold(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="agnews", tasks_root=out)
    task_toml = tomllib.loads((manifest[0]["task_dir"] / "task.toml").read_text())
    cmd = task_toml["steps"][0]["healthcheck"]["command"]
    assert "dab-postgres" not in cmd
    assert "5432" not in cmd
