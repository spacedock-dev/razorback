# ABOUTME: PKG-14 AC-7 + AC-8 + AC-9 + AC-10 + AC-11 — dataset-keyed NAMED postgres volume.

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
