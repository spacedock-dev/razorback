# ABOUTME: PKG-15 follow-up — mongo content-presence healthcheck retries budget.
# ABOUTME: AC-1 default 60 retries (5min), AC-2 per-dataset healthcheck_retries override.

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


def _scaffold(root: Path, *, db_config: dict) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_agnews"
    qdir.mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump(db_config))
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


def _healthcheck(manifest_entry) -> dict:
    text = (manifest_entry["task_dir"] / "task.toml").read_text()
    return tomllib.loads(text)["steps"][0]["healthcheck"]


def test_mongo_healthcheck_default_retries_is_60(tmp_path: Path):
    data_root = _scaffold(tmp_path, db_config=_AGNEWS_LIKE)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="agnews", tasks_root=out)
    hc = _healthcheck(manifest[0])
    assert hc["retries"] == 60, hc
    assert hc["interval_sec"] == 5
    assert hc["start_period_sec"] == 60


def test_mongo_healthcheck_retries_override_honored(tmp_path: Path):
    config = {
        "db_clients": {
            "articles_database": {
                "db_type": "mongo",
                "db_name": "articles_db",
                "dump_folder": "query_dataset/agnews_articles",
                "healthcheck_retries": 120,
            },
            "metadata_database": {
                "db_type": "sqlite",
                "db_path": "query_dataset/metadata.db",
            },
        }
    }
    data_root = _scaffold(tmp_path, db_config=config)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="agnews", tasks_root=out)
    hc = _healthcheck(manifest[0])
    assert hc["retries"] == 120, hc


def test_mongo_healthcheck_retries_override_absent_falls_back_to_default(tmp_path: Path):
    data_root = _scaffold(tmp_path, db_config=_AGNEWS_LIKE)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="agnews", tasks_root=out)
    hc = _healthcheck(manifest[0])
    assert hc["retries"] == 60
