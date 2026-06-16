# ABOUTME: AC-4 — postgres-backed dataset emits services.dab-postgres with image postgres:17.
# ABOUTME: Bookreview-shaped fixture (postgres + sqlite).

from pathlib import Path

import yaml

from razorback_plugin_dab.generate.compose import generate_compose


_BOOKREVIEW_LIKE = {
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


def test_postgres_service_emitted(tmp_path: Path):
    compose_text = generate_compose(
        db_config=_BOOKREVIEW_LIKE,
        dataset_name="bookreview",
        data_root=tmp_path,
    )
    compose = yaml.safe_load(compose_text)
    services = compose["services"]
    assert "dab-postgres" in services
    pg = services["dab-postgres"]
    assert pg["image"] == "postgres:17"
    assert pg["environment"]["POSTGRES_DB"] == "bookreview_db"
    assert pg["environment"]["POSTGRES_USER"] == "postgres"
    assert "pg_isready" in pg["healthcheck"]["test"][1]
    assert "dab-net" in pg["networks"]


def test_postgres_has_restart_policy(tmp_path: Path):
    # postgres:17 can die mid-run (crash/OOM). Without restart-on-failure the
    # container leaves dab-net and `dab-postgres` stops resolving for the rest of
    # the trial, so clinical data becomes unreachable and the agent can only
    # abstain (observed on PANCANCER_ATLAS q2/q3). Mirror the dab-mongo fix.
    compose_text = generate_compose(
        db_config=_BOOKREVIEW_LIKE,
        dataset_name="bookreview",
        data_root=tmp_path,
    )
    pg = yaml.safe_load(compose_text)["services"]["dab-postgres"]
    assert pg["restart"] == "on-failure"


def test_main_service_depends_on_postgres(tmp_path: Path):
    compose_text = generate_compose(
        db_config=_BOOKREVIEW_LIKE,
        dataset_name="bookreview",
        data_root=tmp_path,
    )
    compose = yaml.safe_load(compose_text)
    main = compose["services"]["main"]
    assert "dab-postgres" in main["depends_on"]
    assert main["depends_on"]["dab-postgres"]["condition"] == "service_healthy"
    assert "dab-net" in main["networks"]


def test_sqlite_does_not_spawn_service(tmp_path: Path):
    compose_text = generate_compose(
        db_config=_BOOKREVIEW_LIKE,
        dataset_name="bookreview",
        data_root=tmp_path,
    )
    compose = yaml.safe_load(compose_text)
    assert "dab-sqlite" not in compose["services"]


def test_main_service_runs_as_root(tmp_path: Path):
    # The codex runtime's setup (run as root) pre-creates root-owned
    # /logs/agent and $CODEX_HOME, then harbor runs the agent as the image's
    # default USER. dab-agent:latest is USER exedev (non-root), so the agent
    # cannot write those dirs -> codex aborts with "Permission denied
    # (os error 13)". Pin the main service to root so it can write them,
    # matching the root images ade-bench runs successfully.
    compose_text = generate_compose(
        db_config=_BOOKREVIEW_LIKE,
        dataset_name="bookreview",
        data_root=tmp_path,
    )
    compose = yaml.safe_load(compose_text)
    assert compose["services"]["main"]["user"] == "0:0"


def test_dab_net_declared(tmp_path: Path):
    compose_text = generate_compose(
        db_config=_BOOKREVIEW_LIKE,
        dataset_name="bookreview",
        data_root=tmp_path,
    )
    compose = yaml.safe_load(compose_text)
    assert "dab-net" in compose["networks"]
