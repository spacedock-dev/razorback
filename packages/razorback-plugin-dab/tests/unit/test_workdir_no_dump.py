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


def test_postgres_dump_bind_mounted_from_data_root(tmp_path: Path):
    # PKG-14 superseded PKG-16's environment/_initdb/ staging: dumps are
    # now bind-mounted from data_root directly (absolute path), no per-task
    # copy. The PKG-16 contract ("dump not in agent workdir") still holds
    # because the bind-mount source is an absolute path under data_root,
    # not under the task's workdir.
    data_root = _build_bookreview(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
    )
    expected_source = (data_root / "query_bookreview" / "query_dataset" / "books_info.sql").resolve()
    assert expected_source.exists(), "data_root must contain the canonical dump"


def test_compose_bind_mount_resolves_to_data_root_dump(tmp_path: Path):
    data_root = _build_bookreview(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
    )
    compose_path = manifest[0]["task_dir"] / "environment" / "docker-compose.yaml"
    compose = yaml.safe_load(compose_path.read_text())
    pg_vols = compose["services"]["dab-postgres"]["volumes"]
    named_volumes = set((compose.get("volumes") or {}).keys())
    init_vols = [v for v in pg_vols if v.split(":", 1)[0] not in named_volumes]
    assert init_vols, "expected at least one postgres init bind-mount"
    for entry in init_vols:
        src = entry.split(":", 1)[0]
        resolved = Path(src).resolve() if Path(src).is_absolute() else (compose_path.parent / src).resolve()
        assert resolved.exists(), f"bind-mount source missing: {resolved}"
        # PKG-16 AC-1 + AC-2 (preserved under PKG-14): source must NOT be the agent workdir copy.
        assert "steps/main/workdir" not in str(resolved), (
            f"AC-1: postgres bind-mount source still resolves into agent workdir: {resolved}"
        )


# AC-4: walk the 12-dataset catalog and confirm the workdir-absence contract
# holds for every dataset using a synthetic per-dataset fixture (no LFS deps).

_PG_DUMP_NAMES = {
    "bookreview": "books_info.sql",
    "crmarenapro": "support.sql",
    "googlelocal": "googlelocal.sql",
    "PANCANCER_ATLAS": "pancancer_atlas.sql",
    "PATENTS": "patents.sql",
}
_MONGO_DUMP_NAMES = {
    "agnews": "agnews_articles",
    "yelp": "yelp_business",
}


def _backend_to_client_cfg(dataset_name: str, backend: str) -> dict:
    """Return a synthetic db_clients entry for one backend on one dataset."""
    if backend == "postgres":
        return {
            "db_type": "postgres",
            "db_name": f"{dataset_name.lower()}_db",
            "sql_file": f"query_dataset/{_PG_DUMP_NAMES.get(dataset_name, dataset_name.lower() + '.sql')}",
        }
    if backend == "mongo":
        return {
            "db_type": "mongo",
            "db_name": f"{dataset_name.lower()}_db",
            "dump_folder": f"query_dataset/{_MONGO_DUMP_NAMES.get(dataset_name, dataset_name.lower())}",
        }
    if backend == "sqlite":
        return {"db_type": "sqlite", "db_path": f"query_dataset/{dataset_name.lower()}.db"}
    if backend == "duckdb":
        return {"db_type": "duckdb", "db_path": f"query_dataset/{dataset_name.lower()}.duckdb"}
    raise AssertionError(f"unknown backend: {backend}")


def _build_synthetic_dataset(root: Path, dataset: catalog.DabDataset) -> Path:
    data_root = root / "data"
    qdir = data_root / f"query_{dataset.name}"
    qdir.mkdir(parents=True, exist_ok=True)
    clients = {
        f"{backend}_client": _backend_to_client_cfg(dataset.name, backend)
        for backend in dataset.backends
    }
    (qdir / "db_config.yaml").write_text(yaml.safe_dump({"db_clients": clients}))
    (qdir / "db_description.txt").write_text(f"{dataset.name} schema.")
    qd = qdir / "query_dataset"
    qd.mkdir(exist_ok=True)
    for cfg in clients.values():
        for key in ("sql_file", "dump_folder", "db_path"):
            rel = cfg.get(key)
            if not rel:
                continue
            target = qdir / rel
            if key == "dump_folder":
                # PKG-15 mongo gate: <dump_folder>/<db_name>/<collection>.bson
                # so collection derivation can find the bson file.
                target.mkdir(parents=True, exist_ok=True)
                db_subdir = target / cfg["db_name"]
                db_subdir.mkdir(exist_ok=True)
                (db_subdir / "items.bson").write_bytes(b"\x00" * 64)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                if key == "db_path":
                    target.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
                else:
                    target.write_text("INSERT INTO t VALUES (1);\n" * 10)
    q1 = qdir / "query1"
    q1.mkdir(exist_ok=True)
    (q1 / "query.json").write_text('{"question": "synthetic"}')
    return data_root


@pytest.mark.parametrize("dataset", catalog.DAB_DATASETS, ids=lambda d: d.name)
def test_workdir_excludes_all_dump_artifacts_for_each_dataset(
    tmp_path: Path, dataset: catalog.DabDataset
):
    data_root = _build_synthetic_dataset(tmp_path, dataset)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset=dataset.name, tasks_root=tmp_path / "tasks"
    )
    assert manifest, f"{dataset.name}: expected at least one task"
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    # AC-1 + AC-4: no .sql under the workdir for any dataset.
    leaked_sql = list(workdir.rglob("*.sql"))
    assert leaked_sql == [], f"{dataset.name}: .sql leaked into workdir: {leaked_sql}"
    # AC-1 + AC-4: no mongo BSON dump under the workdir for any mongo dataset.
    leaked_bson = list(workdir.rglob("*.bson"))
    assert leaked_bson == [], f"{dataset.name}: BSON dump leaked into workdir: {leaked_bson}"
