# ABOUTME: Per-(dataset, query) task-dir materializer — emits harbor task tree under tasks_root.
# ABOUTME: AC-2 forbids ground_truth.csv / validate.py inside workdir; only safe inputs are copied.

from __future__ import annotations

import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
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
from razorback_plugin_dab.generate.stratum import (
    write_batch_stratum_file,
    write_stratum_file,
)
from razorback_plugin_dab.generate.tools_denied import write_settings_json
from razorback_plugin_dab.generate.workspace_readme import render_workspace_readme


class TaskTomlError(RuntimeError):
    """Generated task.toml has keys harbor will silently drop (schema drift)."""


class TaskManifestEntry(TypedDict, total=False):
    dataset: str
    query_id: int | None
    query_ids: list[int]
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
    materialize_mode: str = "bind",
    postgres_volume_mode: str = "fresh",
    query_mode: str = "per-query",
) -> list[TaskManifestEntry]:
    """Materialize one harbor task dir per query under tasks_root/<dataset>-q<n>/.

    Returns one TaskManifestEntry per emitted task.

    materialize_mode:
        "bind" (default) — postgres/mongo dump files stay at data_root and are
            bind-mounted read-only into the dab-postgres / dab-mongo container.
            The per-task workdir excludes those dump files (≤10MB task-dir).
        "copy" — dump files are copied into the per-task workdir alongside
            the other dataset payload. Preserved for provenance-strict runs.

    postgres_volume_mode:
        "fresh" (default) — per-task unique postgres data volume (keyed on
            task_id). CONCURRENCY-SAFE: under concurrency.trials>1, two cells
            of the same dataset must NOT share one writable PGDATA dir —
            postgres locks the data dir, so the second container can't start,
            goes unhealthy, and the cell errors. Per-task volumes also avoid
            stale cross-run data (the volume does not survive across runs as a
            dataset-keyed one would). Cost: init.d (DB restore) runs per cell
            instead of once per dataset; DAB postgres dumps are small
            (≤8.5MB / ~90k lines for crmarenapro, the worst concurrent case;
            PATENTS is 129MB but only 3 queries) and restore well within the
            healthcheck budget.
        "reuse" — postgres data volume keyed on (dataset, schema_version) so
            init.d runs ONCE per dataset. Restore-once optimization, but NOT
            concurrency-safe (see above). Only safe for serial single-trial
            runs.
    """
    if materialize_mode not in ("bind", "copy"):
        raise ValueError(
            f"materialize_mode must be 'bind' or 'copy'; got {materialize_mode!r}"
        )
    if postgres_volume_mode not in ("reuse", "fresh"):
        raise ValueError(
            f"postgres_volume_mode must be 'reuse' or 'fresh'; got {postgres_volume_mode!r}"
        )
    if query_mode not in ("batch", "per-query"):
        raise ValueError(
            f"query_mode must be 'batch' or 'per-query'; got {query_mode!r}"
        )
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
    if query_mode == "batch":
        ordered: list[tuple[int, Path]] = []
        for query_dir in query_dirs:
            try:
                qid = int(query_dir.name.removeprefix("query"))
            except ValueError:
                continue
            ordered.append((qid, query_dir))
        ordered.sort(key=lambda pair: pair[0])
        task_name = dataset
        task_dir = tasks_root / task_name
        if task_dir.exists():
            shutil.rmtree(task_dir)
        _materialize_batch_task_dir(
            task_name=task_name,
            dataset_dir=dataset_dir,
            ordered_queries=ordered,
            task_dir=task_dir,
            workspace_variant=workspace_variant,
            hints=hints,
            docker_image=docker_image,
            container_workdir=container_workdir,
            db_config=db_config,
            dataset_meta=dataset_meta,
            materialize_mode=materialize_mode,
            postgres_volume_mode=postgres_volume_mode,
        )
        manifest.append({
            "dataset": dataset,
            "query_id": None,
            "query_ids": [qid for qid, _ in ordered],
            "task_name": task_name,
            "task_dir": task_dir,
        })
        return manifest

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
            materialize_mode=materialize_mode,
            postgres_volume_mode=postgres_volume_mode,
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
    materialize_mode: str = "bind",
    postgres_volume_mode: str = "reuse",
) -> None:
    task_dir.mkdir(parents=True)

    postgres_db = _postgres_db_name(db_config, dataset_name=dataset_meta.name)
    mongo_probes = _mongo_probe_targets(
        db_config, dataset_dir=dataset_dir, dataset_name=dataset_meta.name,
    )
    mongo_healthcheck_retries = _mongo_healthcheck_retries(db_config)
    task_toml_text = _task_toml(
        task_name=task_name,
        docker_image=docker_image,
        container_workdir=container_workdir,
        postgres_db=postgres_db,
        mongo_probes=mongo_probes,
        mongo_healthcheck_retries=mongo_healthcheck_retries,
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
            schema_version=getattr(dataset_meta, "schema_version", "v1"),
            postgres_volume_mode=postgres_volume_mode,
            task_id=task_name,
        )
        (env_dir / "docker-compose.yaml").write_text(compose_text)
        _write_compose_services_sidecar(env_dir / "docker-compose.yaml")
        _write_mongo_restore_shims(env_dir=env_dir, db_config=db_config, dataset_name=dataset_meta.name)

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
    # Some upstream validators do `from common_scaffold.validate.levenshtein
    # import levenshtein`. verify.py exec_module's validate.py inside the
    # dab-agent container, which has no common_scaffold installed, so the
    # import raises, verify.py exits non-zero under `set -eu`, no reward.json
    # is written, and harbor reports RewardFileNotFoundError (verifier appears
    # to never run). Vendor common_scaffold next to verify.py — /tests is
    # sys.path[0] — so the import resolves. The batch path already does this.
    _install_common_scaffold(tests_dir=tests_dir, data_root=dataset_dir.parent)

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

    if materialize_mode == "bind":
        excluded_workdir_names = _dump_basenames(db_config)
        excluded_workdir_paths = _bind_mode_excluded_paths(db_config)
    else:
        excluded_workdir_names = set()
        excluded_workdir_paths = set()

    for name in _DATASET_SAFE:
        src = dataset_dir / name
        if not src.exists():
            continue
        dst = workdir / name
        if src.is_dir():
            if materialize_mode == "bind":
                _clone_or_copy_tree(
                    src,
                    dst,
                    ignore_names=excluded_workdir_names,
                    ignore_paths={
                        path.relative_to(name)
                        for path in excluded_workdir_paths
                        if path.parts and path.parts[0] == name
                    },
                )
            else:
                shutil.copytree(
                    src,
                    dst,
                    ignore=lambda _dir, names: [
                        n for n in names if n in excluded_workdir_names
                    ],
                )
        else:
            if src.name in excluded_workdir_names:
                continue
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


def _materialize_batch_task_dir(
    *,
    task_name: str,
    dataset_dir: Path,
    ordered_queries: list[tuple[int, Path]],
    task_dir: Path,
    workspace_variant: str,
    hints: bool,
    docker_image: str,
    container_workdir: str,
    db_config: dict,
    dataset_meta: catalog.DabDataset,
    materialize_mode: str = "bind",
    postgres_volume_mode: str = "reuse",
) -> None:
    task_dir.mkdir(parents=True)

    postgres_db = _postgres_db_name(db_config, dataset_name=dataset_meta.name)
    mongo_probes = _mongo_probe_targets(
        db_config, dataset_dir=dataset_dir, dataset_name=dataset_meta.name,
    )
    mongo_healthcheck_retries = _mongo_healthcheck_retries(db_config)
    task_toml_text = _task_toml(
        task_name=task_name,
        docker_image=docker_image,
        container_workdir=container_workdir,
        postgres_db=postgres_db,
        mongo_probes=mongo_probes,
        mongo_healthcheck_retries=mongo_healthcheck_retries,
    )
    _check_task_toml_environment_keys(task_toml_text, task_name=task_name)
    (task_dir / "task.toml").write_text(task_toml_text)

    query_ids = [qid for qid, _ in ordered_queries]
    instruction = _batch_instruction(
        ordered_queries=ordered_queries,
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
        compose_text = generate_compose(
            db_config=db_config,
            dataset_name=dataset_meta.name,
            data_root=dataset_dir.parent,
            docker_image=docker_image,
            container_workdir=container_workdir,
            schema_version=getattr(dataset_meta, "schema_version", "v1"),
            postgres_volume_mode=postgres_volume_mode,
            task_id=task_name,
        )
        (env_dir / "docker-compose.yaml").write_text(compose_text)
        _write_compose_services_sidecar(env_dir / "docker-compose.yaml")
        _write_mongo_restore_shims(env_dir=env_dir, db_config=db_config, dataset_name=dataset_meta.name)

    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    from razorback_plugin_dab.verify import verify_batch as verify_batch_module
    shutil.copy2(Path(verify_batch_module.__file__), tests_dir / "verify_batch.py")
    _install_common_scaffold(tests_dir=tests_dir, data_root=dataset_dir.parent)
    for query_id, query_dir in ordered_queries:
        upstream_validate = query_dir / "validate.py"
        if upstream_validate.exists():
            _install_batch_validator(
                tests_dir=tests_dir,
                upstream=upstream_validate,
                dataset=dataset_meta.name,
                query_id=query_id,
            )

    write_batch_stratum_file(
        tests_dir=tests_dir,
        dataset=dataset_meta.name,
        query_ids=query_ids,
        backends=dataset_meta.backends,
    )

    test_sh = tests_dir / "test.sh"
    test_sh.write_text(_batch_test_sh(container_workdir=container_workdir))
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

    if materialize_mode == "bind":
        excluded_workdir_names = _dump_basenames(db_config)
        excluded_workdir_paths = _bind_mode_excluded_paths(db_config)
    else:
        excluded_workdir_names = set()
        excluded_workdir_paths = set()

    for name in _DATASET_SAFE:
        src = dataset_dir / name
        if not src.exists():
            continue
        dst = workdir / name
        if src.is_dir():
            if materialize_mode == "bind":
                _clone_or_copy_tree(
                    src,
                    dst,
                    ignore_names=excluded_workdir_names,
                    ignore_paths={
                        path.relative_to(name)
                        for path in excluded_workdir_paths
                        if path.parts and path.parts[0] == name
                    },
                )
            else:
                shutil.copytree(
                    src,
                    dst,
                    ignore=lambda _dir, names: [
                        n for n in names if n in excluded_workdir_names
                    ],
                )
        else:
            if src.name in excluded_workdir_names:
                continue
            shutil.copy2(src, dst)

    for query_id, query_dir in ordered_queries:
        q_workspace = workdir / f"query{query_id}"
        q_workspace.mkdir()
        for name in _QUERY_SAFE:
            src = query_dir / name
            if src.exists():
                shutil.copy2(src, q_workspace / name)

    for forbidden in _QUERY_FORBIDDEN:
        for stray in workdir.rglob(forbidden):
            if stray.is_dir():
                shutil.rmtree(stray)
            else:
                stray.unlink()

    compose_path = env_dir / "docker-compose.yaml"
    if compose_path.exists():
        _check_compose_volumes(compose_path)


def _batch_instruction(
    *,
    ordered_queries: list[tuple[int, Path]],
    dataset_dir: Path,
    container_workdir: str,
    hints: bool,
) -> str:
    desc_file = "db_description_withhint.txt" if hints else "db_description.txt"
    desc_path = dataset_dir / desc_file
    if not desc_path.exists():
        desc_path = dataset_dir / "db_description.txt"
    db_description = desc_path.read_text() if desc_path.exists() else ""
    lines = [
        "# Task",
        "",
        "Answer ALL of the following queries using the databases described below.",
        "Solve every query in this single agent turn.",
        "",
        "## Queries",
        "",
    ]
    answer_keys: list[str] = []
    for query_id, query_dir in ordered_queries:
        query_text = (
            (query_dir / "query.json").read_text()
            if (query_dir / "query.json").exists()
            else "{}"
        )
        lines.append(f"### query{query_id}")
        lines.append("")
        lines.append(
            f"Located under `{container_workdir}/query{query_id}/query.json`:"
        )
        lines.append("")
        lines.append(query_text)
        lines.append("")
        answer_keys.append(f'"q{query_id}"')
    lines.extend([
        "## Databases",
        "",
        db_description,
        "",
        "## Output contract",
        "",
        (
            f"Write your final answers to `{container_workdir}/answers.json` as a "
            "JSON object where each key is the query directory name (e.g. "
            f"{', '.join(answer_keys)}) and each value is the answer string. For "
            "example:"
        ),
        "",
        "```json",
        "{",
    ])
    for query_id, _ in ordered_queries:
        lines.append(f'  "q{query_id}": "<your answer for query{query_id}>",')
    if ordered_queries:
        lines[-1] = lines[-1].rstrip(",")
    lines.extend([
        "}",
        "```",
        "",
        "The verifier reads this file and scores each query independently.",
        "",
    ])
    return "\n".join(lines)


def _install_batch_validator(
    *,
    tests_dir: Path,
    upstream: Path,
    dataset: str,
    query_id: int,
) -> None:
    """Install a per-query validator under tests/validate_q{N}.py.

    Bookreview's hardened templates (PKG-13 T14) are applied per-query; the
    hardened body loads the upstream alongside it under
    `_upstream_validate_q{N}.py` to avoid colliding with sibling queries'
    upstream copies.
    """
    from razorback_plugin_dab.verify import validators as hardened

    template_name = _hardened_template(dataset=dataset, query_id=query_id)
    if template_name is None:
        shutil.copy2(upstream, tests_dir / f"validate_q{query_id}.py")
        return

    upstream_dst = tests_dir / f"_upstream_validate_q{query_id}.py"
    shutil.copy2(upstream, upstream_dst)
    template_path = Path(hardened.__file__).parent / template_name
    body = template_path.read_text()
    # Hardened templates load their sibling as `_upstream_validate.py`; under
    # batch we keep per-query siblings to avoid name collisions. Rewrite the
    # loader to point at the per-query upstream copy we just wrote.
    body = body.replace(
        '"_upstream_validate.py"', f'"_upstream_validate_q{query_id}.py"'
    )
    body = body.replace(
        '"_upstream_validate"', f'"_upstream_validate_q{query_id}"'
    )
    (tests_dir / f"validate_q{query_id}.py").write_text(body)


def _install_common_scaffold(*, tests_dir: Path, data_root: Path) -> None:
    upstream = data_root / "common_scaffold"
    if not upstream.exists():
        return
    shutil.copytree(
        upstream,
        tests_dir / "common_scaffold",
        ignore=shutil.ignore_patterns("__pycache__"),
    )


def _batch_test_sh(*, container_workdir: str) -> str:
    return (
        '#!/bin/sh\n'
        'set -eu\n'
        'mkdir -p /logs/verifier\n'
        'cp /tests/stratum.json /logs/verifier/stratum.json 2>/dev/null || true\n'
        'python /tests/verify_batch.py \\\n'
        '  --tests-dir /tests \\\n'
        f'  --answers {container_workdir}/answers.json \\\n'
        '  --reward-out /logs/verifier/reward.json \\\n'
        '  --per-query-out /logs/verifier/reward_per_query.json\n'
    )


_MONGO_HEALTHCHECK_DEFAULT_RETRIES = 90


def _task_toml(
    *,
    task_name: str,
    docker_image: str,
    container_workdir: str,
    postgres_db: str | None = None,
    mongo_probes: list[tuple[str, str]] | None = None,
    mongo_healthcheck_retries: int | None = None,
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
        # started healthy with an empty DB). count_documents() > 0 fails fast
        # if mongorestore did not run or produced no documents.
        #
        # Probe runs from the agent's `main` step container (dab-agent:latest),
        # which ships python3 + pymongo but NOT mongosh. The probe must use
        # python3/pymongo for the call to succeed; an earlier mongosh-based
        # probe was unrunnable from `main` (command-not-found) and burned the
        # retry budget without ever testing mongo content presence.
        #
        # retries default = 90 × interval 5s = 7.5min budget covers
        # mongorestore wall time for agnews/yelp (~120-150k docs). Per-dataset
        # override via db_config[<client>].healthcheck_retries handles outliers.
        db_name, collection = mongo_probes[0]
        # Harbor runs this per-step healthcheck inside the `main` agent
        # container. `dab-agent:latest` carries pymongo but not mongosh, so use
        # Python here and leave mongosh to the mongo sidecar's own healthcheck.
        probe_py = (
            "import sys; "
            "from pymongo import MongoClient; "
            "client = MongoClient("
            "'mongodb://dab-mongo:27017', "
            "serverSelectionTimeoutMS=5000, connectTimeoutMS=5000"
            "); "
            f"count = client[{db_name!r}][{collection!r}].count_documents({{}}, limit=1); "
            "sys.exit(0 if count > 0 else 1)"
        )
        retries = (
            mongo_healthcheck_retries
            if mongo_healthcheck_retries is not None
            else _MONGO_HEALTHCHECK_DEFAULT_RETRIES
        )
        probe = f"python3 -c {shlex.quote(probe_py)}"
        body += (
            "\n[steps.healthcheck]\n"
            f'command = "{_toml_escape(probe)}"\n'
            "interval_sec = 5\n"
            "timeout_sec = 10\n"
            "start_period_sec = 60\n"
            f"retries = {retries}\n"
        )
    return body


def _clone_or_copy_tree(
    src: Path,
    dst: Path,
    *,
    ignore_names: set[str] | None = None,
    ignore_paths: set[Path] | None = None,
    _relative_root: Path = Path(),
) -> None:
    """Materialize src into dst via a reflink-capable copy primitive.

    Bind-mode workdir materializer for safe dataset files that still need a
    physical workdir copy. Multi-GB SQLite/DuckDB live DB files are excluded
    by relative path and mounted read-only into the main container instead.

    Per-platform primitive:
        - darwin: ``cp -c`` → APFS clonefile (true copy-on-write).
        - linux:  ``cp --reflink=auto`` → reflink (true copy-on-write) on
          filesystems that support it (btrfs, xfs with reflinks, ext4 with
          reflinks); falls back to a full physical copy on filesystems that
          do not (tmpfs, ext4-without-reflinks, cross-device, etc.). The
          fallback is safe — distinct inodes — so writes through the dst
          never mutate the src. Disk-savings are lost on the fallback path
          but data integrity is preserved.
        - other:  raises NotImplementedError naming sys.platform — callers
          can opt into ``materialize_mode="copy"`` for ``shutil.copytree``.

    Files whose basename is in ignore_names are skipped for legacy dump
    exclusion. Files or directories whose path relative to src is in
    ignore_paths are skipped for path-aware DB-file exclusion.

    Caveats:
        - ``cp -c`` exits non-zero (EOPNOTSUPP) on a darwin volume that is
          not APFS; the CalledProcessError surfaces to the caller.
        - ``cp --reflink=auto`` is a GNU coreutils flag. Busybox ``cp`` does
          not implement it. Target environments (harbor-DAB containers,
          Debian/Ubuntu hosts) ship GNU coreutils.
    """
    ignore_names = ignore_names or set()
    ignore_paths = ignore_paths or set()
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        child_rel = _relative_root / child.name
        if child.name in ignore_names or child_rel in ignore_paths:
            continue
        dst_child = dst / child.name
        if child.is_dir():
            _clone_or_copy_tree(
                child,
                dst_child,
                ignore_names=ignore_names,
                ignore_paths=ignore_paths,
                _relative_root=child_rel,
            )
            continue
        if sys.platform == "darwin":
            subprocess.run(
                ["cp", "-c", str(child), str(dst_child)], check=True,
            )
        elif sys.platform == "linux":
            subprocess.run(
                ["cp", "--reflink=auto", str(child), str(dst_child)],
                check=True,
            )
        else:
            raise NotImplementedError(
                f"bind-mode workdir materialization not supported on {sys.platform!r}; "
                "use materialize_mode='copy' for full-copy semantics"
            )


def _bind_mode_excluded_paths(db_config: dict | None) -> set[Path]:
    """Return dataset-relative payload paths omitted from bind-mode workdirs."""
    excluded = _dump_relative_paths(db_config)
    excluded.update(_file_backed_db_paths(db_config))
    return excluded


def _dump_basenames(db_config: dict | None) -> set[str]:
    """Return basenames of every postgres sql_file / mongo dump_folder in db_config.

    Used under materialize_mode='bind' to skip copying dump files into the
    per-task agent workdir — they are bind-mounted into the dab-postgres /
    dab-mongo container directly from data_root instead (PKG-14 AC-1, AC-2).
    Sqlite (db_path) and duckdb (db_path) live-DB files are NOT in this set —
    they stay in the workdir for the agent to read.
    """
    names: set[str] = set()
    clients = (db_config or {}).get("db_clients") or {}
    for cfg in clients.values():
        if not isinstance(cfg, dict):
            continue
        kind = cfg.get("db_type")
        if kind == "postgres":
            sql_file = cfg.get("sql_file")
            if sql_file:
                names.add(Path(sql_file).name)
        elif kind == "mongo":
            dump_folder = cfg.get("dump_folder")
            if dump_folder:
                names.add(Path(dump_folder).name)
    return names


def _dump_relative_paths(db_config: dict | None) -> set[Path]:
    """Return dataset-relative postgres/mongo dump payload paths."""
    paths: set[Path] = set()
    clients = (db_config or {}).get("db_clients") or {}
    for cfg in clients.values():
        if not isinstance(cfg, dict):
            continue
        kind = cfg.get("db_type")
        if kind == "postgres":
            sql_file = cfg.get("sql_file")
            if sql_file:
                paths.add(Path(sql_file))
        elif kind == "mongo":
            dump_folder = cfg.get("dump_folder")
            if dump_folder:
                paths.add(Path(dump_folder))
    return paths


def _file_backed_db_paths(db_config: dict | None) -> set[Path]:
    """Return dataset-relative SQLite/DuckDB db_path entries."""
    paths: set[Path] = set()
    clients = (db_config or {}).get("db_clients") or {}
    for cfg in clients.values():
        if not isinstance(cfg, dict):
            continue
        if cfg.get("db_type") not in {"sqlite", "duckdb"}:
            continue
        db_path = cfg.get("db_path")
        if db_path:
            paths.add(Path(db_path))
    return paths


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


def _mongo_healthcheck_retries(db_config: dict | None) -> int | None:
    """Return the first mongo client's healthcheck_retries override, or None.

    The override widens or narrows the mongo content-presence healthcheck's
    retries budget on a per-dataset basis. Datasets whose mongorestore wall
    time exceeds the default 5-minute budget set the override higher; tiny
    datasets that restore in seconds can set it lower. Returning None leaves
    `_task_toml` on its built-in default.
    """
    clients = (db_config or {}).get("db_clients") or {}
    for cfg in clients.values():
        if not isinstance(cfg, dict) or cfg.get("db_type") != "mongo":
            continue
        override = cfg.get("healthcheck_retries")
        if isinstance(override, int) and not isinstance(override, bool):
            return override
    return None


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


def _write_mongo_restore_shims(
    *, env_dir: Path, db_config: dict, dataset_name: str,
) -> None:
    """Emit one restore.sh per mongo client alongside the compose file.

    PKG-15 AC-1: compose.py mounts these into the mongo container's
    /docker-entrypoint-initdb.d/. Shim text comes from mongo_init; we
    chmod +x so mongo's init.d phase actually executes it.
    """
    from razorback_plugin_dab.generate.mongo_init import render_mongo_restore_sh

    for cfg in (db_config.get("db_clients") or {}).values():
        if not isinstance(cfg, dict) or cfg.get("db_type") != "mongo":
            continue
        db_name = cfg.get("db_name") or f"{dataset_name}_db"
        dump_folder = cfg.get("dump_folder")
        if not dump_folder:
            continue
        shim_path = env_dir / f"restore-{db_name}.sh"
        shim_path.write_text(
            render_mongo_restore_sh(
                db_name=db_name,
                dump_folder_basename=Path(dump_folder).name,
            )
        )
        shim_path.chmod(shim_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


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

    NAMED volumes declared in the top-level `volumes:` section are skipped —
    docker creates them on demand and they have no host-path semantics.
    """
    compose = yaml.safe_load(compose_path.read_text()) or {}
    named_volumes = set((compose.get("volumes") or {}).keys())
    base = compose_path.parent
    missing: list[str] = []
    for svc_name, svc in (compose.get("services") or {}).items():
        for entry in svc.get("volumes") or []:
            if not isinstance(entry, str):
                continue
            src = entry.split(":", 1)[0]
            if src in named_volumes:
                continue
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
