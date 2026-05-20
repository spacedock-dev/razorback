# ABOUTME: Per-(dataset, query) task-dir materializer — emits harbor task tree under tasks_root.
# ABOUTME: AC-2 forbids ground_truth.csv / validate.py inside workdir; only safe inputs are copied.

from __future__ import annotations

import json
import shutil
import stat
import tomllib
from pathlib import Path
from typing import TypedDict

import yaml

from razorback_plugin_dab import datasets as catalog
from razorback_plugin_dab.generate.compose import (
    DEFAULT_AGENT_IMAGE,
    DEFAULT_CONTAINER_WORKDIR,
    POSTGRES_USER,
    ComposeError,
    generate_compose,
)
from razorback_plugin_dab.generate.stratum import write_stratum_file
from razorback_plugin_dab.generate.tools_denied import write_settings_json
from razorback_plugin_dab.generate.workspace_readme import render_workspace_readme


class TaskTomlError(RuntimeError):
    """Generated task.toml has keys harbor will silently drop (schema drift)."""


class TaskManifestEntry(TypedDict):
    dataset: str
    query_id: int
    task_name: str
    task_dir: Path


_QUERY_SAFE = ("query.json",)
_QUERY_FORBIDDEN = ("ground_truth.csv", "validate.py", "__pycache__")
_DATASET_SAFE = (
    "db_config.yaml",
    "db_description.txt",
    "db_description_withhint.txt",
    "query_dataset",
)
_STEP_NAME = "main"


def prepare_dataset_tasks(
    *,
    data_root: Path,
    dataset: str,
    tasks_root: Path,
    workspace_variant: str = "direct-minimal",
    hints: bool = False,
    docker_image: str = DEFAULT_AGENT_IMAGE,
    container_workdir: str = DEFAULT_CONTAINER_WORKDIR,
) -> list[TaskManifestEntry]:
    """Materialize one harbor task dir per query under tasks_root/<dataset>-q<n>/.

    Returns one TaskManifestEntry per emitted task.
    """
    data_root = Path(data_root)
    dataset_dir = data_root / f"query_{dataset}"
    if not dataset_dir.exists():
        raise FileNotFoundError(f"DAB dataset dir not found: {dataset_dir}")

    tasks_root = Path(tasks_root)
    tasks_root.mkdir(parents=True, exist_ok=True)

    dataset_meta = catalog.by_name(dataset)
    db_config_path = dataset_dir / "db_config.yaml"
    db_config = yaml.safe_load(db_config_path.read_text()) if db_config_path.exists() else {}

    manifest: list[TaskManifestEntry] = []
    query_dirs = sorted(
        p for p in dataset_dir.iterdir()
        if p.is_dir() and p.name.startswith("query") and p.name != "query_dataset"
    )
    for query_dir in query_dirs:
        try:
            query_id = int(query_dir.name.removeprefix("query"))
        except ValueError:
            continue
        task_name = f"{dataset}-q{query_id}"
        task_dir = tasks_root / task_name
        if task_dir.exists():
            shutil.rmtree(task_dir)
        _materialize_task_dir(
            task_name=task_name,
            dataset_dir=dataset_dir,
            query_dir=query_dir,
            task_dir=task_dir,
            workspace_variant=workspace_variant,
            hints=hints,
            docker_image=docker_image,
            container_workdir=container_workdir,
            db_config=db_config,
            dataset_meta=dataset_meta,
            query_id=query_id,
        )
        manifest.append({
            "dataset": dataset,
            "query_id": query_id,
            "task_name": task_name,
            "task_dir": task_dir,
        })
    return manifest


def _materialize_task_dir(
    *,
    task_name: str,
    dataset_dir: Path,
    query_dir: Path,
    task_dir: Path,
    workspace_variant: str,
    hints: bool,
    docker_image: str,
    container_workdir: str,
    db_config: dict,
    dataset_meta: catalog.DabDataset,
    query_id: int,
) -> None:
    task_dir.mkdir(parents=True)

    postgres_db = _postgres_db_name(db_config, dataset_name=dataset_meta.name)
    mongo_probes = _mongo_probe_targets(
        db_config, dataset_dir=dataset_dir, dataset_name=dataset_meta.name,
    )
    task_toml_text = _task_toml(
        task_name=task_name,
        docker_image=docker_image,
        container_workdir=container_workdir,
        postgres_db=postgres_db,
        mongo_probes=mongo_probes,
    )
    _check_task_toml_environment_keys(task_toml_text, task_name=task_name)
    (task_dir / "task.toml").write_text(task_toml_text)

    instruction = _instruction(
        query_dir=query_dir,
        dataset_dir=dataset_dir,
        container_workdir=container_workdir,
        hints=hints,
    )
    (task_dir / "instruction.md").write_text(instruction)

    env_dir = task_dir / "environment"
    env_dir.mkdir()
    (env_dir / "Dockerfile").write_text(
        "# Unused — [environment].docker_image selects the prebuilt image.\n"
    )
    write_settings_json(env_dir / "settings.json", task_name=task_name)

    if db_config:
        # PKG-13 T1: harbor's compose discovery hard-codes
        # environment_dir / docker-compose.yaml as the task-author override
        # slot. Writing anywhere else means harbor never loads the file.
        compose_text = generate_compose(
            db_config=db_config,
            dataset_name=dataset_meta.name,
            data_root=dataset_dir.parent,
            docker_image=docker_image,
            container_workdir=container_workdir,
        )
        (env_dir / "docker-compose.yaml").write_text(compose_text)
        _write_compose_services_sidecar(env_dir / "docker-compose.yaml")

    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    from razorback_plugin_dab.verify import verify as verify_module
    shutil.copy2(Path(verify_module.__file__), tests_dir / "verify.py")
    upstream_validate = query_dir / "validate.py"
    if upstream_validate.exists():
        _install_validator(
            tests_dir=tests_dir,
            upstream=upstream_validate,
            dataset=dataset_meta.name,
            query_id=query_id,
        )

    write_stratum_file(
        tests_dir=tests_dir,
        dataset=dataset_meta.name,
        query_id=query_id,
        backends=dataset_meta.backends,
    )

    test_sh = tests_dir / "test.sh"
    test_sh.write_text(_test_sh(container_workdir=container_workdir))
    test_sh.chmod(test_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    step_dir = task_dir / "steps" / _STEP_NAME
    step_dir.mkdir(parents=True)
    (step_dir / "instruction.md").write_text(instruction)
    workdir = step_dir / "workdir"
    workdir.mkdir()

    workdir_readme = workdir / "README.md"
    workdir_readme.write_text(
        render_workspace_readme(variant=workspace_variant, container_workdir=container_workdir)
    )

    for name in _DATASET_SAFE:
        src = dataset_dir / name
        if not src.exists():
            continue
        dst = workdir / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    for name in _QUERY_SAFE:
        src = query_dir / name
        if src.exists():
            shutil.copy2(src, workdir / name)

    # AC-2 belt-and-braces: any forbidden file under workdir is removed.
    for forbidden in _QUERY_FORBIDDEN:
        for stray in workdir.rglob(forbidden):
            if stray.is_dir():
                shutil.rmtree(stray)
            else:
                stray.unlink()

    # PKG-13 T7 / AC-4: now that workdir is populated, every compose bind-mount
    # src must resolve to a real path on disk. Caught here so the failure lands
    # at generation time rather than during compose-up.
    compose_path = env_dir / "docker-compose.yaml"
    if compose_path.exists():
        _check_compose_volumes(compose_path)


def _task_toml(
    *,
    task_name: str,
    docker_image: str,
    container_workdir: str,
    postgres_db: str | None = None,
    mongo_probes: list[tuple[str, str]] | None = None,
) -> str:
    # PKG-13 T1: harbor's EnvironmentConfig has no docker_compose field;
    # any [environment].docker_compose value is silently dropped by pydantic.
    # Compose discovery is purely positional: environment_dir / docker-compose.yaml.
    body = (
        'schema_version = "1.2"\n\n'
        f'[task]\nname = "razorback-plugin-dab/{task_name}"\n'
        f'description = "DAB {task_name} as a harbor task."\n\n'
        "[environment]\n"
        f'docker_image = "{_toml_escape(docker_image)}"\n'
        f'workdir = "{_toml_escape(container_workdir)}"\n'
        f'\n[[steps]]\nname = "{_STEP_NAME}"\n'
    )
    if postgres_db:
        # PKG-13 T5 / AC-3: bookreview reachability gate. Harbor runs the
        # per-step healthcheck after setup and before the agent; on failure
        # it aborts the step with a typed error, which is the fail-fast
        # shape AC-3 requires. The command exits non-zero if dab-postgres
        # is unreachable.
        #
        # Implementation note: dab-agent:latest does not ship a postgres
        # client (no psql / pg_isready), so the probe is a python3 TCP
        # connect against the dab-postgres service. Postgres-protocol
        # readiness is already guaranteed by compose's depends_on:
        # condition: service_healthy + dab-postgres's container-level
        # pg_isready healthcheck, so this TCP probe is the right shape for
        # fail-fast detection of compose-not-loaded / network-broken paths.
        probe = (
            "python3 -c \\\"import socket; s=socket.create_connection(('dab-postgres', 5432), timeout=5); s.close()\\\""
        )
        body += (
            "\n[steps.healthcheck]\n"
            f'command = "{probe}"\n'
            "interval_sec = 5\n"
            "timeout_sec = 10\n"
            "start_period_sec = 30\n"
            "retries = 6\n"
        )
    elif mongo_probes:
        # PKG-15 AC-2: content-presence probe, NOT TCP-only. TCP would have
        # missed Bug 1 from the dab-mongo-probe (mongo ignored .bson and
        # started healthy with an empty DB). countDocuments() > 0 fails fast
        # if mongorestore did not run or produced no documents.
        # start_period_sec=60 + retries=12 gives 2m post-init budget on top
        # of mongo's container start; mongorestore of agnews/yelp (~120-150k
        # docs) empirically completes in ~30s but the headroom is cheap.
        db_name, collection = mongo_probes[0]
        eval_js = (
            f"db.getSiblingDB('{db_name}').getCollection('{collection}').countDocuments() > 0"
        )
        probe = (
            f"mongosh --quiet --host dab-mongo --eval \\\"{eval_js}\\\" | grep -q true"
        )
        body += (
            "\n[steps.healthcheck]\n"
            f'command = "{probe}"\n'
            "interval_sec = 5\n"
            "timeout_sec = 10\n"
            "start_period_sec = 60\n"
            "retries = 12\n"
        )
    return body


def _postgres_db_name(db_config: dict | None, *, dataset_name: str) -> str | None:
    """Return the first postgres db_name in the db_config, or None.

    The reachability gate (T5) is emitted only when at least one postgres
    client is declared; sqlite/duckdb/mongo datasets get no gate.
    """
    clients = (db_config or {}).get("db_clients") or {}
    for cfg in clients.values():
        if isinstance(cfg, dict) and cfg.get("db_type") == "postgres":
            return cfg.get("db_name") or f"{dataset_name}_db"
    return None


def _mongo_probe_targets(
    db_config: dict | None,
    *,
    dataset_dir: Path,
    dataset_name: str,
) -> list[tuple[str, str]]:
    """Return (db_name, collection_name) pairs for every mongo client.

    Collection name is derived from the .bson file basename under
    <dataset_dir>/<dump_folder>/<db_name>/ (mongo's standard dump layout).
    Returns [] when no mongo client is declared.
    """
    pairs: list[tuple[str, str]] = []
    clients = (db_config or {}).get("db_clients") or {}
    for cfg in clients.values():
        if not isinstance(cfg, dict) or cfg.get("db_type") != "mongo":
            continue
        db_name = cfg.get("db_name") or f"{dataset_name}_db"
        dump_folder = cfg.get("dump_folder")
        collection = _derive_mongo_collection(
            dataset_dir=dataset_dir, dump_folder=dump_folder, db_name=db_name,
        )
        if collection is None:
            raise ComposeError(
                f"could not derive mongo probe collection for dataset {dataset_name!r} "
                f"(db_name={db_name!r}, dump_folder={dump_folder!r}). "
                "Expected <dump_folder>/<db_name>/<collection>.bson under data_root."
            )
        pairs.append((db_name, collection))
    return pairs


def _derive_mongo_collection(
    *, dataset_dir: Path, dump_folder: str | None, db_name: str,
) -> str | None:
    if not dump_folder:
        return None
    base = dataset_dir / dump_folder / db_name
    if not base.is_dir():
        return None
    bsons = [p for p in base.iterdir() if p.suffix == ".bson"]
    if not bsons:
        return None
    # The largest .bson is the primary collection; ties broken by lexicographic
    # name for determinism. Probing any one collection > 0 documents is enough
    # to certify the restore actually loaded data.
    bsons.sort(key=lambda p: (-p.stat().st_size, p.name))
    return bsons[0].stem


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _check_task_toml_environment_keys(text: str, *, task_name: str) -> None:
    """Reject any [environment].* key harbor's EnvironmentConfig doesn't honour.

    Harbor parses task.toml via pydantic with the default `extra='ignore'`
    policy, which silently drops unknown keys. That bit us once already
    (`[environment].docker_compose`, dropped, compose never loaded). This
    helper fails fast at generation time so future schema drift surfaces
    where it can be fixed instead of as a silent runtime no-op.
    """
    from harbor.models.task.config import EnvironmentConfig

    parsed = tomllib.loads(text)
    env = parsed.get("environment", {}) or {}
    extras = sorted(set(env) - set(EnvironmentConfig.model_fields))
    if extras:
        raise TaskTomlError(
            f"task.toml for {task_name!r} has [environment] keys harbor does "
            f"not honour and will silently drop: {extras}. "
            "Either remove the key or upgrade harbor."
        )


def _install_validator(
    *,
    tests_dir: Path,
    upstream: Path,
    dataset: str,
    query_id: int,
) -> None:
    """Copy the upstream validate.py, optionally wrapping it with a hardened
    template for known bookreview substring-leak queries (T14 finding).

    For bookreview-q1/q2/q3 the upstream substring check is necessary but
    not sufficient; we install a template that loads upstream as
    `_upstream_validate.py` and adds a bounded-answer check on top.
    """
    from razorback_plugin_dab.verify import validators as hardened

    template_name = _hardened_template(dataset=dataset, query_id=query_id)
    if template_name is None:
        shutil.copy2(upstream, tests_dir / "validate.py")
        return

    shutil.copy2(upstream, tests_dir / "_upstream_validate.py")
    template_path = Path(hardened.__file__).parent / template_name
    shutil.copy2(template_path, tests_dir / "validate.py")


def _hardened_template(*, dataset: str, query_id: int) -> str | None:
    if dataset != "bookreview":
        return None
    return {
        1: "bookreview_q1.py",
        2: "bookreview_q2_q3.py",
        3: "bookreview_q2_q3.py",
    }.get(query_id)


def _write_compose_services_sidecar(compose_path: Path) -> None:
    """Record the compose services emitted for this task.

    The bookreview reachability gate (T5/T6) and the AC-6 re-run validator
    read this sidecar to confirm what was supposed to be running. It is a
    cheap structural check that does not depend on a docker daemon.
    """
    compose = yaml.safe_load(compose_path.read_text()) or {}
    services = sorted((compose.get("services") or {}).keys())
    sidecar = {"compose_file": compose_path.name, "services": services}
    (compose_path.parent / ".compose-services.json").write_text(
        json.dumps(sidecar, indent=2) + "\n"
    )


def _check_compose_volumes(compose_path: Path) -> None:
    """Resolve every bind-mount src against the compose file's parent.

    Raises ComposeError if any source resolves to a missing host path.
    Closes AC-4: catches future regressions where the compose bind-mount
    source path resolves to a missing host file at compose-up time.
    """
    compose = yaml.safe_load(compose_path.read_text()) or {}
    base = compose_path.parent
    missing: list[str] = []
    for svc_name, svc in (compose.get("services") or {}).items():
        for entry in svc.get("volumes") or []:
            if not isinstance(entry, str):
                continue
            src = entry.split(":", 1)[0]
            if src.startswith("/"):
                resolved = Path(src)
            else:
                resolved = (base / src).resolve()
            if not resolved.exists():
                missing.append(f"{svc_name}:{src} -> {resolved}")
    if missing:
        raise ComposeError(
            "compose bind-mount source(s) do not exist on host: "
            + "; ".join(missing)
        )


def _instruction(
    *,
    query_dir: Path,
    dataset_dir: Path,
    container_workdir: str,
    hints: bool,
) -> str:
    query_text = (query_dir / "query.json").read_text() if (query_dir / "query.json").exists() else "{}"
    desc_file = "db_description_withhint.txt" if hints else "db_description.txt"
    desc_path = dataset_dir / desc_file
    if not desc_path.exists():
        desc_path = dataset_dir / "db_description.txt"
    db_description = desc_path.read_text() if desc_path.exists() else ""
    return (
        "# Task\n\n"
        "Answer the following query using the databases described below.\n\n"
        f"## Query\n\n{query_text}\n\n"
        f"## Databases\n\n{db_description}\n\n"
        "## Output contract\n\n"
        f"Write your final answer to `{container_workdir}/answers.json` as a JSON object of the form\n"
        '`{"answer": "<your answer as a single string>"}`. The verifier reads this file.\n'
    )


def _test_sh(*, container_workdir: str) -> str:
    return (
        '#!/bin/sh\n'
        'set -eu\n'
        'mkdir -p /logs/verifier\n'
        'cp /tests/stratum.json /logs/verifier/stratum.json 2>/dev/null || true\n'
        'python /tests/verify.py \\\n'
        '  --validate-py /tests/validate.py \\\n'
        f'  --answers {container_workdir}/answers.json \\\n'
        '  --reward-out /logs/verifier/reward.json\n'
    )
