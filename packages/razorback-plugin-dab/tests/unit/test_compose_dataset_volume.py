# ABOUTME: PKG-14 AC-7 + AC-8 + AC-9 + AC-10 + AC-11 — dataset-keyed NAMED postgres volume.

from __future__ import annotations

from pathlib import Path

import yaml

from razorback_plugin_dab.generate.compose import generate_compose
from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


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


def test_postgres_data_volume_is_dataset_keyed(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="bookreview",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    assert "volumes" in compose, "AC-7: compose must declare top-level volumes section"
    vol_names = list(compose["volumes"].keys())
    assert "dab-postgres-data-bookreview-v1" in vol_names, (
        f"AC-7: expected dataset-keyed volume; got {vol_names}"
    )
    pg_volumes = compose["services"]["dab-postgres"]["volumes"]
    pgdata_mounts = [v for v in pg_volumes if "/var/lib/postgresql/data" in v]
    assert pgdata_mounts, "AC-7: dab-postgres must mount the NAMED volume at PGDATA"
    src = pgdata_mounts[0].split(":", 1)[0]
    assert src == "dab-postgres-data-bookreview-v1", (
        f"AC-7: PGDATA must mount the dataset-keyed NAMED volume; got {src!r}"
    )


def test_postgres_volume_name_stable_across_invocations(tmp_path: Path):
    """AC-7: re-running with identical inputs produces identical volume names."""
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml1 = generate_compose(db_config=cfg, dataset_name="bookreview", data_root=data_root)
    yaml2 = generate_compose(db_config=cfg, dataset_name="bookreview", data_root=data_root)
    assert "dab-postgres-data-bookreview-v1" in yaml1
    assert "dab-postgres-data-bookreview-v1" in yaml2


def test_named_volume_and_readonly_bindmount_coexist(tmp_path: Path):
    """AC-10: in one compose file, the postgres service has BOTH a NAMED data
    volume (writable) AND a read-only bind-mount for the dump."""
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg, dataset_name="bookreview", data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    pg_volumes = compose["services"]["dab-postgres"]["volumes"]
    assert len(pg_volumes) >= 2, (
        f"AC-10: expected NAMED data volume + read-only dump mount; got {pg_volumes}"
    )
    named = [v for v in pg_volumes if v.startswith("dab-postgres-data-")]
    assert len(named) == 1
    assert not named[0].endswith(":ro"), "PGDATA must be writable"
    dump_mounts = [v for v in pg_volumes if "/docker-entrypoint-initdb.d/" in v]
    assert len(dump_mounts) >= 1
    assert all(v.endswith(":ro") for v in dump_mounts)


def test_schema_version_v2_yields_distinct_volume_name(tmp_path: Path):
    """AC-9: bumping schema_version invalidates the v1 volume — new v2 name."""
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_v1 = generate_compose(
        db_config=cfg, dataset_name="bookreview", data_root=data_root,
        schema_version="v1",
    )
    yaml_v2 = generate_compose(
        db_config=cfg, dataset_name="bookreview", data_root=data_root,
        schema_version="v2",
    )
    assert "dab-postgres-data-bookreview-v1" in yaml_v1
    assert "dab-postgres-data-bookreview-v2" in yaml_v2
    assert "dab-postgres-data-bookreview-v1" not in yaml_v2


def test_fresh_mode_yields_per_task_volume_name(tmp_path: Path):
    """AC-11: fresh mode appends a per-task suffix; the volume is NOT shared."""
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg, dataset_name="bookreview", data_root=data_root,
        postgres_volume_mode="fresh", task_id="bookreview-q1",
    )
    compose = yaml.safe_load(yaml_text)
    vol_names = list(compose["volumes"].keys())
    assert vol_names == ["dab-postgres-data-bookreview-v1-bookreview-q1"], (
        f"AC-11: fresh mode must carry per-task suffix; got {vol_names}"
    )


def test_reuse_mode_default_no_per_task_suffix(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg, dataset_name="bookreview", data_root=data_root,
        task_id="bookreview-q1",
    )
    compose = yaml.safe_load(yaml_text)
    vol_names = list(compose["volumes"].keys())
    assert vol_names == ["dab-postgres-data-bookreview-v1"]


def _two_query_postgres_data_root(root: Path) -> Path:
    """Bookreview-shaped data root with TWO postgres queries of one dataset.

    Used to assert the concurrency-safety invariant: under the operator
    default, two cells of the SAME dataset get NON-colliding postgres data
    volume names so a trials:2 run never mounts one writable PGDATA twice.
    """
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
        }
    }))
    (qdir / "db_description.txt").write_text("Bookreview schema description.")
    qd = qdir / "query_dataset"
    qd.mkdir()
    (qd / "books_info.sql").write_text("CREATE TABLE books (id INT);\n")
    for qid in (1, 2):
        q = qdir / f"query{qid}"
        q.mkdir()
        (q / "query.json").write_text('{"question": "how many?"}')
    return data_root


def _pg_data_volume_name(task_dir: Path) -> str:
    compose = yaml.safe_load(
        (task_dir / "environment" / "docker-compose.yaml").read_text()
    )
    pg_volumes = compose["services"]["dab-postgres"]["volumes"]
    pgdata = [v for v in pg_volumes if "/var/lib/postgresql/data" in v]
    return pgdata[0].split(":", 1)[0]


def test_same_dataset_tasks_get_distinct_postgres_volumes(tmp_path: Path):
    """Concurrency-safety invariant (the dab0015 corruption bug): two cells of
    the SAME dataset, materialized with the operator default, must NOT key on
    the same writable postgres data volume. Under trials:2 they start
    concurrently and two containers mounting one PGDATA dir collide
    (postgres locks the dir -> second container unhealthy -> cell errors)."""
    data_root = _two_query_postgres_data_root(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=out,
        workspace_variant="direct-minimal",
        materialize_mode="copy",
    )
    assert len(manifest) == 2
    vol_names = {_pg_data_volume_name(e["task_dir"]) for e in manifest}
    assert len(vol_names) == 2, (
        f"two queries of one dataset must get distinct PGDATA volumes; got {vol_names}"
    )


def test_postgres_volume_name_lowercased_for_caps_datasets(tmp_path: Path):
    """Docker volume names should be case-stable; the catalog names like
    PANCANCER_ATLAS must lowercase to a valid volume name."""
    data_root = tmp_path / "data"
    qdir = data_root / "query_PANCANCER_ATLAS" / "query_dataset"
    qdir.mkdir(parents=True)
    (qdir / "pancancer_atlas.sql").write_text("SELECT 1;\n")
    cfg = {
        "db_clients": {
            "pc": {
                "db_type": "postgres",
                "db_name": "pancancer_atlas_db",
                "sql_file": "query_dataset/pancancer_atlas.sql",
            }
        }
    }
    yaml_text = generate_compose(
        db_config=cfg, dataset_name="PANCANCER_ATLAS", data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    assert "dab-postgres-data-pancancer_atlas-v1" in compose["volumes"]
