# ABOUTME: AC-4 — mongo-backed dataset emits services.dab-mongo with image mongo:8.
# ABOUTME: agnews-shaped fixture (mongo + sqlite).

from pathlib import Path

import yaml

from razorback_plugin_dab.generate.compose import generate_compose


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


def test_mongo_service_emitted(tmp_path: Path):
    text = generate_compose(db_config=_AGNEWS_LIKE, dataset_name="agnews", data_root=tmp_path)
    compose = yaml.safe_load(text)
    services = compose["services"]
    assert "dab-mongo" in services
    assert services["dab-mongo"]["image"] == "mongo:8"
    assert "mongosh" in services["dab-mongo"]["healthcheck"]["test"]


def test_main_depends_on_mongo(tmp_path: Path):
    text = generate_compose(db_config=_AGNEWS_LIKE, dataset_name="agnews", data_root=tmp_path)
    compose = yaml.safe_load(text)
    assert "dab-mongo" in compose["services"]["main"]["depends_on"]


def test_no_postgres_for_mongo_only(tmp_path: Path):
    text = generate_compose(db_config=_AGNEWS_LIKE, dataset_name="agnews", data_root=tmp_path)
    compose = yaml.safe_load(text)
    assert "dab-postgres" not in compose["services"]
