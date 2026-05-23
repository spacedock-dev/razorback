# ABOUTME: DAB prepare — materialize one harbor task dir per (dataset, query_id) under tasks_root.
# ABOUTME: AC-2: ground_truth.csv (and validate.py) are NEVER copied into the agent's workdir.

import shutil
import stat
import warnings
from pathlib import Path
from typing import TypedDict


class TaskManifestEntry(TypedDict):
    dataset: str
    query_id: int
    task_name: str
    task_dir: Path


# Files inside a query dir that are SAFE to copy to the agent's workdir.
_QUERY_SAFE = ("query.json",)
# Files inside a query dir that must NEVER be copied to the agent's workdir.
_QUERY_FORBIDDEN = ("ground_truth.csv", "validate.py", "__pycache__")
# Top-level safe entries inside the dataset dir.
_DATASET_SAFE = (
    "db_config.yaml",
    "db_description.txt",
    "db_description_withhint.txt",
    "query_dataset",
)

# Default image + workdir. dab-agent:latest is the DAB-built image (built by
# benchmark/setup.sh) that ships claude + /workspace. M3's smoke validated this
# triangle; production runs assume the image is pre-baked.
_DEFAULT_DOCKER_IMAGE = "dab-agent:latest"
_DEFAULT_CONTAINER_WORKDIR = "/workspace"
_STEP_NAME = "main"


def prepare_dataset_tasks(
    *,
    data_root: Path,
    dataset: str,
    tasks_root: Path,
    task_env: dict[str, str] | None = None,
    docker_image: str = _DEFAULT_DOCKER_IMAGE,
    container_workdir: str = _DEFAULT_CONTAINER_WORKDIR,
) -> list[TaskManifestEntry]:
    """Materialize harbor task dirs for every query in `dataset`.

    data_root: the DAB data root (e.g. `/path/to/dataagentbench/data`).
    dataset:   short name, e.g. "bookreview" (resolved as `data_root / f"query_{dataset}"`).
    tasks_root: razorback-owned dir (must live under /Users/... for Colima); deleted and re-created.
    task_env: optional environment variables to stamp into task.toml's
        [environment.env] block. M3's translator threads the proxy lock-down
        through here so harbor's docker env carries it into every trial.
    docker_image: container image referenced by task.toml's [environment].docker_image.
        Defaults to dab-agent:latest (the DAB-built image that ships claude).
    container_workdir: container path harbor lands the workdir/ contents and uses
        as cwd for the agent. Defaults to /workspace (the dab-agent WORKDIR).

    Returns one entry per query directory found.
    """
    warnings.warn(
        "in-tree DAB adapter (kind: dab) is dev-only; "
        "use kind: harbor_dab + dataset: dab@1.0 for canonical runs.",
        DeprecationWarning,
        stacklevel=2,
    )
    data_root = Path(data_root)
    dataset_dir = data_root / f"query_{dataset}"
    if not dataset_dir.exists():
        raise FileNotFoundError(f"DAB dataset dir not found: {dataset_dir}")

    tasks_root = Path(tasks_root)
    if tasks_root.exists():
        shutil.rmtree(tasks_root)
    tasks_root.mkdir(parents=True)

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
        _materialize_task_dir(
            task_name=task_name,
            dataset_dir=dataset_dir,
            query_dir=query_dir,
            task_dir=task_dir,
            task_env=task_env or {},
            docker_image=docker_image,
            container_workdir=container_workdir,
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
    task_env: dict[str, str],
    docker_image: str,
    container_workdir: str,
) -> None:
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        _task_toml(
            task_name=task_name,
            task_env=task_env,
            docker_image=docker_image,
            container_workdir=container_workdir,
        )
    )

    instruction = _instruction(
        query_dir=query_dir,
        dataset_dir=dataset_dir,
        container_workdir=container_workdir,
    )
    (task_dir / "instruction.md").write_text(instruction)

    env_dir = task_dir / "environment"
    env_dir.mkdir()
    # Dockerfile is unused when [environment].docker_image is set (harbor uses
    # the prebuilt compose path). Keep an empty placeholder so harbor's task
    # validator (which checks environment/ exists) is satisfied.
    (env_dir / "Dockerfile").write_text(_placeholder_dockerfile())

    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    import razorback.benchmarks.dab.verify as verify_module
    shutil.copy2(Path(verify_module.__file__), tests_dir / "verify.py")
    shutil.copy2(query_dir / "validate.py", tests_dir / "validate.py")

    test_sh = tests_dir / "test.sh"
    test_sh.write_text(_test_sh(container_workdir=container_workdir))
    test_sh.chmod(test_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Harbor 0.6.6's single-step trial path does NOT auto-upload task_dir/workdir;
    # only steps/<step>/workdir is uploaded (trial.py:482-496). Use a one-step
    # task with name="main" so the dataset reaches the container.
    step_dir = task_dir / "steps" / _STEP_NAME
    step_dir.mkdir(parents=True)
    (step_dir / "instruction.md").write_text(instruction)
    workdir = step_dir / "workdir"
    workdir.mkdir()
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

    # AC-2 belt-and-braces: any forbidden file that somehow landed under workdir is removed.
    for forbidden in _QUERY_FORBIDDEN:
        for stray in workdir.rglob(forbidden):
            if stray.is_dir():
                shutil.rmtree(stray)
            else:
                stray.unlink()


def _task_toml(
    *,
    task_name: str,
    task_env: dict[str, str],
    docker_image: str,
    container_workdir: str,
) -> str:
    body = (
        'schema_version = "1.2"\n\n'
        f'[task]\nname = "razorback/{task_name}"\n'
        f'description = "DAB {task_name} as a harbor task."\n\n'
        "[environment]\n"
        f'docker_image = "{_toml_escape(docker_image)}"\n'
        f'workdir = "{_toml_escape(container_workdir)}"\n'
    )
    if task_env:
        body += "\n[environment.env]\n"
        for k, v in task_env.items():
            body += f'{k} = "{_toml_escape(v)}"\n'
    body += f'\n[[steps]]\nname = "{_STEP_NAME}"\n'
    return body


def _toml_escape(value: str) -> str:
    """Escape backslashes and double-quotes for TOML basic strings."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _instruction(*, query_dir: Path, dataset_dir: Path, container_workdir: str) -> str:
    query_text = (query_dir / "query.json").read_text()
    db_description = (dataset_dir / "db_description.txt").read_text()
    return (
        "# Task\n\n"
        "Answer the following query using the databases described below.\n\n"
        f"## Query\n\n{query_text}\n\n"
        f"## Databases\n\n{db_description}\n\n"
        "## Output contract\n\n"
        f"Write your final answer to `{container_workdir}/answers.json` as a JSON object of the form\n"
        '`{"answer": "<your answer as a single string>"}`. The verifier reads this file.\n'
    )


def _placeholder_dockerfile() -> str:
    """Empty placeholder so harbor's task validator sees an environment/ dir.

    The actual image is selected via [environment].docker_image in task.toml,
    so this Dockerfile is never built when the prebuilt image is configured.
    """
    return "# Unused — [environment].docker_image selects a prebuilt image.\n"


def _test_sh(*, container_workdir: str) -> str:
    return (
        '#!/bin/sh\n'
        'set -eu\n'
        'mkdir -p /logs/verifier\n'
        'python /tests/verify.py \\\n'
        '  --validate-py /tests/validate.py \\\n'
        f'  --answers {container_workdir}/answers.json \\\n'
        '  --reward-out /logs/verifier/reward.json\n'
    )
