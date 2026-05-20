# ABOUTME: Live-DB compose stack generator — postgres / mongo / hybrid (AC-4, PKG-3 carry-forward).
# ABOUTME: Emits docker-compose.yaml with services.{main,dab-postgres,dab-mongo} on networks.dab-net.

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


POSTGRES_IMAGE = "postgres:17"
MONGO_IMAGE = "mongo:8"
DEFAULT_AGENT_IMAGE = "dab-agent:latest"
DEFAULT_CONTAINER_WORKDIR = "/workspace"

# PKG-13 T10 finding: upstream DAB SQL dumps assume the default `postgres`
# superuser (ALTER TABLE ... OWNER TO postgres in books_info.sql). Configuring
# a different POSTGRES_USER makes the init SQL fail with role-not-found and
# the container exits with code 3 before becoming healthy. Use the default
# superuser name to match the dump's role references.
POSTGRES_USER = "postgres"
POSTGRES_PASSWORD = "postgres"


class ComposeError(RuntimeError):
    """Compose generation refused (e.g. unsupported db_type)."""


def generate_compose(
    *,
    db_config: dict,
    dataset_name: str,
    data_root: Path,
    docker_image: str = DEFAULT_AGENT_IMAGE,
    container_workdir: str = DEFAULT_CONTAINER_WORKDIR,
) -> str:
    """Emit the docker-compose.yaml text for one (dataset, query) task.

    Returns YAML text. Caller writes it next to task.toml.
    """
    services: dict[str, Any] = {}
    networks_used: set[str] = set()
    init_volumes_pg: list[dict[str, str]] = []
    init_volumes_mongo: list[dict[str, str]] = []

    clients = (db_config or {}).get("db_clients") or {}
    pg_dbs: list[str] = []
    mongo_dbs: list[str] = []
    for _client, cfg in clients.items():
        if not isinstance(cfg, dict):
            continue
        kind = cfg.get("db_type")
        if kind == "postgres":
            db_name = cfg.get("db_name") or f"{dataset_name}_db"
            pg_dbs.append(db_name)
            sql_file = cfg.get("sql_file")
            if sql_file:
                # PKG-14 AC-1: bind-mount the dump from data_root directly,
                # read-only. No per-task copy. Compose accepts absolute host
                # paths in volume sources.
                src = (data_root / f"query_{dataset_name}" / sql_file).resolve()
                init_volumes_pg.append(
                    {"src": str(src), "dst": f"/docker-entrypoint-initdb.d/{Path(sql_file).name}"}
                )
        elif kind == "mongo":
            db_name = cfg.get("db_name") or f"{dataset_name}_db"
            mongo_dbs.append(db_name)
            dump_folder = cfg.get("dump_folder")
            if dump_folder:
                src = (data_root / f"query_{dataset_name}" / dump_folder).resolve()
                init_volumes_mongo.append(
                    {"src": str(src), "dst": f"/docker-entrypoint-initdb.d/{Path(dump_folder).name}"}
                )
        elif kind in (None, "sqlite", "duckdb"):
            # File-backed engines need no service; bind mount handled by workdir copy.
            continue
        else:
            raise ComposeError(f"unsupported db_type {kind!r} for dataset {dataset_name!r}")

    if pg_dbs:
        services["dab-postgres"] = {
            "image": POSTGRES_IMAGE,
            "environment": {
                "POSTGRES_USER": POSTGRES_USER,
                "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
                "POSTGRES_DB": pg_dbs[0],
            },
            "healthcheck": {
                "test": ["CMD-SHELL", f"pg_isready -U {POSTGRES_USER} -d {pg_dbs[0]}"],
                "interval": "5s",
                "timeout": "5s",
                "retries": 20,
            },
            "networks": ["dab-net"],
            "volumes": [f"{v['src']}:{v['dst']}:ro" for v in init_volumes_pg],
        }
        networks_used.add("dab-net")

    if mongo_dbs:
        services["dab-mongo"] = {
            "image": MONGO_IMAGE,
            "healthcheck": {
                "test": ["CMD", "mongosh", "--quiet", "--eval", "db.runCommand({ping:1})"],
                "interval": "5s",
                "timeout": "5s",
                "retries": 20,
            },
            "networks": ["dab-net"],
            "volumes": [f"{v['src']}:{v['dst']}:ro" for v in init_volumes_mongo],
        }
        networks_used.add("dab-net")

    main_depends_on: dict[str, dict[str, str]] = {}
    if "dab-postgres" in services:
        main_depends_on["dab-postgres"] = {"condition": "service_healthy"}
    if "dab-mongo" in services:
        main_depends_on["dab-mongo"] = {"condition": "service_healthy"}

    main_service: dict[str, Any] = {
        "image": docker_image,
        "working_dir": container_workdir,
        "networks": ["dab-net"] if networks_used else [],
    }
    if main_depends_on:
        main_service["depends_on"] = main_depends_on
    services["main"] = main_service
    networks_used.add("dab-net")

    compose: dict[str, Any] = {
        "services": services,
        "networks": {n: {"name": f"{n}-{dataset_name}"} for n in sorted(networks_used)},
    }

    return yaml.safe_dump(compose, sort_keys=False, default_flow_style=False)
