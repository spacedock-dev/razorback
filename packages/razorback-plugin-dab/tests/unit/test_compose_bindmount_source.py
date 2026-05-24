# ABOUTME: PKG-14 AC-1 — compose bind-mount source for dab-postgres / dab-mongo
# ABOUTME: resolves to the absolute data_root path, not a per-task workdir copy.

from __future__ import annotations

from pathlib import Path

import yaml

from razorback_plugin_dab.generate.compose import generate_compose


def _bookreview_cfg(data_root: Path) -> dict:
    qdir = data_root / "query_bookreview"
    (qdir / "query_dataset").mkdir(parents=True)
    (qdir / "query_dataset" / "books_info.sql").write_text("SELECT 1;\n")
    return {
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": "query_dataset/books_info.sql",
            }
        }
    }


def _mixed_cfg(data_root: Path) -> dict:
    qdir = data_root / "query_mixed" / "query_dataset"
    qdir.mkdir(parents=True)
    (qdir / "books_info.sql").write_text("SELECT 1;\n")
    (qdir / "review_query.db").write_bytes(b"SQLite format 3\x00")
    (qdir / "analytics.duckdb").write_bytes(b"DUCK")
    mongo_dump = qdir / "events_dump" / "events_db"
    mongo_dump.mkdir(parents=True)
    (mongo_dump / "events.bson").write_bytes(b"\x00" * 64)
    return {
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": "query_dataset/books_info.sql",
            },
            "events_database": {
                "db_type": "mongo",
                "db_name": "events_db",
                "dump_folder": "query_dataset/events_dump",
            },
            "review_database": {
                "db_type": "sqlite",
                "db_path": "query_dataset/review_query.db",
            },
            "analytics_database": {
                "db_type": "duckdb",
                "db_path": "query_dataset/analytics.duckdb",
            },
        }
    }


def test_postgres_source_is_data_root_absolute(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="bookreview",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    pg_volumes = compose["services"]["dab-postgres"]["volumes"]
    init_mounts = [v for v in pg_volumes if "/docker-entrypoint-initdb.d/" in v]
    assert init_mounts, "expected at least one postgres init volume"
    src = init_mounts[0].split(":", 1)[0]
    expected = str((data_root / "query_bookreview" / "query_dataset" / "books_info.sql").resolve())
    assert src == expected, (
        f"AC-1: postgres init source must be absolute data_root path; got {src!r}"
    )
    assert Path(src).exists()


def test_postgres_source_is_not_per_task_workdir(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="bookreview",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    pg_volumes = compose["services"]["dab-postgres"]["volumes"]
    init_mounts = [v for v in pg_volumes if "/docker-entrypoint-initdb.d/" in v]
    src = init_mounts[0].split(":", 1)[0]
    assert "_initdb" not in src, (
        f"AC-1: PKG-14 supersedes PKG-16's _initdb/ staging — source must be data_root: {src}"
    )
    assert "steps/main/workdir" not in src, (
        f"AC-1: source must not be the agent workdir: {src}"
    )


def test_postgres_init_volume_is_read_only(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="bookreview",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    pg_volumes = compose["services"]["dab-postgres"]["volumes"]
    init_mounts = [v for v in pg_volumes if "/docker-entrypoint-initdb.d/" in v]
    assert init_mounts, "expected init volume for AC-3 :ro assertion"
    for entry in init_mounts:
        assert entry.endswith(":ro"), (
            f"AC-3: postgres init bind-mount must be read-only; got {entry!r}"
        )


def test_mongo_init_volume_is_read_only(tmp_path: Path):
    data_root = tmp_path / "data"
    qdir = data_root / "query_agnews" / "query_dataset" / "agnews_articles"
    qdir.mkdir(parents=True)
    (qdir / "metadata.bson").write_bytes(b"\x00" * 64)
    cfg = {
        "db_clients": {
            "articles": {
                "db_type": "mongo",
                "db_name": "agnews_db",
                "dump_folder": "query_dataset/agnews_articles",
            }
        }
    }
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="agnews",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    mongo_volumes = compose["services"]["dab-mongo"]["volumes"]
    init_mounts = [v for v in mongo_volumes if "/docker-entrypoint-initdb.d/" in v]
    assert init_mounts, "expected init volume for AC-3 :ro assertion"
    for entry in init_mounts:
        assert entry.endswith(":ro"), (
            f"AC-3: mongo dump bind-mount must be read-only; got {entry!r}"
        )


def test_file_backed_dbs_are_read_only_main_mounts(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _mixed_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="mixed",
        data_root=data_root,
        container_workdir="/workspace",
    )
    compose = yaml.safe_load(yaml_text)

    main_volumes = compose["services"]["main"]["volumes"]
    expected = {
        (
            str((data_root / "query_mixed" / "query_dataset" / "review_query.db").resolve()),
            "/workspace/query_dataset/review_query.db",
        ),
        (
            str((data_root / "query_mixed" / "query_dataset" / "analytics.duckdb").resolve()),
            "/workspace/query_dataset/analytics.duckdb",
        ),
    }
    observed = {tuple(entry.rsplit(":", 2)[:2]) for entry in main_volumes}

    assert observed == expected
    for entry in main_volumes:
        assert entry.endswith(":ro"), (
            f"AC-3: file-backed DB mount must be read-only; got {entry!r}"
        )
        assert Path(entry.split(":", 1)[0]).is_absolute()


def test_postgres_and_mongo_dumps_are_not_main_mounts(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _mixed_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="mixed",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)

    main_volumes = compose["services"]["main"]["volumes"]
    assert all("books_info.sql" not in entry for entry in main_volumes)
    assert all("events_dump" not in entry for entry in main_volumes)
