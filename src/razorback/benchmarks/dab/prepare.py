# ABOUTME: DAB prepare — materialize one harbor task dir per (dataset, query_id) under tasks_root.
# ABOUTME: AC-2: ground_truth.csv (and validate.py) are NEVER copied into the agent's workdir.

import shutil
import stat
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


def prepare_dataset_tasks(
    *,
    data_root: Path,
    dataset: str,
    tasks_root: Path,
) -> list[TaskManifestEntry]:
    """Materialize harbor task dirs for every query in `dataset`.

    data_root: the DAB data root (e.g. `/Users/clkao/git/dataagentbench/data`).
    dataset:   short name, e.g. "bookreview" (resolved as `data_root / f"query_{dataset}"`).
    tasks_root: razorback-owned dir (must live under /Users/... for Colima); deleted and re-created.

    Returns one entry per query directory found.
    """
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
) -> None:
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(_task_toml(task_name))

    instruction = _instruction(query_dir=query_dir, dataset_dir=dataset_dir)
    (task_dir / "instruction.md").write_text(instruction)

    env_dir = task_dir / "environment"
    env_dir.mkdir()
    (env_dir / "Dockerfile").write_text(_dockerfile())

    tests_dir = task_dir / "tests"
    tests_dir.mkdir()

    # The verifier and the dataset's validate.py live in /tests/ inside the container.
    # /tests/ is NOT visible to the agent (which only sees /work/), so AC-2 holds.
    import razorback.benchmarks.dab.verify as verify_module
    shutil.copy2(Path(verify_module.__file__), tests_dir / "verify.py")
    shutil.copy2(query_dir / "validate.py", tests_dir / "validate.py")

    test_sh = tests_dir / "test.sh"
    test_sh.write_text(_test_sh())
    test_sh.chmod(test_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    workdir = task_dir / "workdir"
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


def _task_toml(task_name: str) -> str:
    return (
        'schema_version = "1.2"\n'
        '\n'
        '[task]\n'
        f'name = "razorback/{task_name}"\n'
        f'description = "DAB {task_name} as a harbor task."\n'
    )


def _instruction(*, query_dir: Path, dataset_dir: Path) -> str:
    query_text = (query_dir / "query.json").read_text()
    db_description = (dataset_dir / "db_description.txt").read_text()
    return (
        "# Task\n\n"
        f"Answer the following query using the databases described below.\n\n"
        f"## Query\n\n{query_text}\n\n"
        f"## Databases\n\n{db_description}\n\n"
        "## Output contract\n\n"
        "Write your final answer to `/work/answers.json` as a JSON object of the form\n"
        '`{"answer": "<your answer as a single string>"}`. The verifier reads this file.\n'
    )


def _dockerfile() -> str:
    # Minimal image: bookreview tasks read SQLite directly; postgres is out of M2 scope
    # (the nop agent never queries it). Future milestones swap in DAB's full image.
    return (
        "FROM python:3.12-slim\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends sqlite3 "
        "&& rm -rf /var/lib/apt/lists/*\n"
        "WORKDIR /work\n"
        'CMD ["sleep", "infinity"]\n'
    )


def _test_sh() -> str:
    # The verifier reads /work/answers.json, calls /tests/verify.py with the per-query
    # validate.py already copied alongside it. No env vars, no bind mounts —
    # everything the verifier needs is in /tests/ (where harbor auto-copies the task's
    # tests/ dir).
    return (
        '#!/bin/sh\n'
        'set -eu\n'
        'mkdir -p /logs/verifier\n'
        'python /tests/verify.py \\\n'
        '  --validate-py /tests/validate.py \\\n'
        '  --answers /work/answers.json \\\n'
        '  --reward-out /logs/verifier/reward.json\n'
    )
