# ABOUTME: Per-(dataset, query) task-dir materializer — emits harbor task tree under tasks_root.
# ABOUTME: AC-2 forbids ground_truth.csv / validate.py inside workdir; only safe inputs are copied.

from __future__ import annotations

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

    task_toml_text = _task_toml(
        task_name=task_name,
        docker_image=docker_image,
        container_workdir=container_workdir,
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

    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    from razorback_plugin_dab.verify import verify as verify_module
    shutil.copy2(Path(verify_module.__file__), tests_dir / "verify.py")
    upstream_validate = query_dir / "validate.py"
    if upstream_validate.exists():
        shutil.copy2(upstream_validate, tests_dir / "validate.py")

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


def _task_toml(
    *,
    task_name: str,
    docker_image: str,
    container_workdir: str,
) -> str:
    # PKG-13 T1: harbor's EnvironmentConfig has no docker_compose field;
    # any [environment].docker_compose value is silently dropped by pydantic.
    # Compose discovery is purely positional: environment_dir / docker-compose.yaml.
    return (
        'schema_version = "1.2"\n\n'
        f'[task]\nname = "razorback-plugin-dab/{task_name}"\n'
        f'description = "DAB {task_name} as a harbor task."\n\n'
        "[environment]\n"
        f'docker_image = "{_toml_escape(docker_image)}"\n'
        f'workdir = "{_toml_escape(container_workdir)}"\n'
        f'\n[[steps]]\nname = "{_STEP_NAME}"\n'
    )


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
