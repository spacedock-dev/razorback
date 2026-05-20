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
    schema_version: str = "v1",
    postgres_volume_mode: str = "reuse",
    task_id: str | None = None,
) -> str:
    """Emit the docker-compose.yaml text for one (dataset, query) task.

    Returns YAML text. Caller writes it next to task.toml.

    PKG-14 AC-7..AC-11: postgres data lives on a NAMED volume keyed on
    (dataset_name, schema_version) so init.d runs ONCE per dataset across
    variants/trials. postgres_volume_mode='fresh' appends task_id for a
    per-task unique volume (clean-DB-init override).
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
                # PKG-14 AC-1: bind-mount the dump folder from data_root absolute path
                # (no per-task copy); read-only.
                src = (data_root / f"query_{dataset_name}" / dump_folder).resolve()
                init_volumes_mongo.append(
                    {"src": str(src), "dst": f"/docker-entrypoint-initdb.d/{Path(dump_folder).name}"}
                )
                # PKG-15 AC-1: mongo:8 ignores .bson under /docker-entrypoint-initdb.d/
                # but auto-runs .sh files. The shim mongorestore's the dump folder
                # on first start. prepare.py writes the shim text alongside the
                # compose file; the 00- prefix orders it ahead of any future .sh.
                init_volumes_mongo.append(
                    {"src": f"./restore-{db_name}.sh", "dst": f"/docker-entrypoint-initdb.d/00-restore-{db_name}.sh"}
                )
        elif kind in (None, "sqlite", "duckdb"):
            # File-backed engines need no service; bind mount handled by workdir copy.
            continue
        else:
            raise ComposeError(f"unsupported db_type {kind!r} for dataset {dataset_name!r}")

    pg_volume_name: str | None = None
    if pg_dbs:
        pg_volume_name = _postgres_volume_name(
            dataset_name=dataset_name,
            schema_version=schema_version,
            mode=postgres_volume_mode,
            task_id=task_id,
        )
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
            "volumes": (
                [f"{pg_volume_name}:/var/lib/postgresql/data"]
                + [f"{v['src']}:{v['dst']}:ro" for v in init_volumes_pg]
            ),
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

    # PKG-14 AC-7: emit the NAMED postgres data volume in the top-level
    # `volumes:` section with an explicit `name:` so docker compose does NOT
    # prepend the project name. The volume is shared across different harbor
    # compose projects (different variants / trials / task_ids).
    if pg_volume_name:
        compose["volumes"] = {pg_volume_name: {"name": pg_volume_name}}

    return yaml.safe_dump(compose, sort_keys=False, default_flow_style=False)


def _postgres_volume_name(
    *,
    dataset_name: str,
    schema_version: str,
    mode: str,
    task_id: str | None,
) -> str:
    """PKG-14 AC-7 / AC-9 / AC-11: deterministic postgres-data volume name.

    'reuse' (default): `dab-postgres-data-{dataset_name.lower()}-{schema_version}`
        — shared across variants / trials / task_ids on the same dataset.
    'fresh': append `-{task_id}` for a per-task unique volume (clean DB init).
    """
    base = f"dab-postgres-data-{dataset_name.lower()}-{schema_version}"
    if mode == "fresh":
        suffix = task_id or "anon"
        return f"{base}-{suffix}"
    return base
