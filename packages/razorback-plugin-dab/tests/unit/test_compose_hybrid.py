# ABOUTME: AC-4 — hybrid (postgres + mongo + main agent) compose triple.
# ABOUTME: Synthetic fixture that exercises both database services on dab-net.

from pathlib import Path

import yaml

from razorback_plugin_dab.generate.compose import generate_compose


_HYBRID = {
    "db_clients": {
        "pg_db": {"db_type": "postgres", "db_name": "hybrid_db", "sql_file": "query_dataset/init.sql"},
        "mongo_db": {"db_type": "mongo", "db_name": "events_db", "dump_folder": "query_dataset/dump"},
        "lite_db": {"db_type": "sqlite", "db_path": "query_dataset/lite.db"},
    }
}


def test_all_three_services_emitted(tmp_path: Path):
    text = generate_compose(db_config=_HYBRID, dataset_name="hybrid", data_root=tmp_path)
    compose = yaml.safe_load(text)
    services = compose["services"]
    assert "main" in services
    assert "dab-postgres" in services
    assert "dab-mongo" in services


def test_main_depends_on_both(tmp_path: Path):
    text = generate_compose(db_config=_HYBRID, dataset_name="hybrid", data_root=tmp_path)
    compose = yaml.safe_load(text)
    main = compose["services"]["main"]
    assert "dab-postgres" in main["depends_on"]
    assert "dab-mongo" in main["depends_on"]


def test_all_services_on_dab_net(tmp_path: Path):
    text = generate_compose(db_config=_HYBRID, dataset_name="hybrid", data_root=tmp_path)
    compose = yaml.safe_load(text)
    for service_name, service in compose["services"].items():
        assert "dab-net" in service["networks"], f"{service_name} not on dab-net"
