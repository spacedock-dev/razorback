# ABOUTME: ade-bench harbor-task loader. Resolves spec.benchmark.tasks entries
# ABOUTME: (legacy slugs or FU-1 git-task entries) into TaskConfig-ready records.

import asyncio
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable

import shortuuid
from harbor.models.task.id import GitTaskId

from razorback.benchmarks.dab.prepare import _DEFAULT_DOCKER_IMAGE
from razorback.spec.schema import AdeBenchTaskEntry


def _run_async(coro: Awaitable[Any]) -> Any:
    """Run ``coro`` to completion whether or not we're inside an event loop.

    The translator is invoked both from sync entrypoints (CLI freeze, unit
    tests) and from inside ``_execute_run_async``'s running loop. When no loop
    is running, ``asyncio.run`` is correct. When a loop IS running on this
    thread, ``asyncio.run`` raises; we fall back to running the coroutine on
    a dedicated worker thread with its own loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import threading

    result: dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001
            result["error"] = exc

    t = threading.Thread(target=runner)
    t.start()
    t.join()
    if "error" in result:
        raise result["error"]
    return result["value"]


@dataclass(frozen=True)
class ResolvedTask:
    """A task entry resolved for harbor.TaskConfig construction.

    Legacy slug entries set only `path` (the absolute task directory under
    tasks_root). FU-1 git-task entries set all three fields; `path` is the
    in-repo relative path that harbor's GitTaskId materializes on demand.
    """
    path: Path
    git_url: str | None = None
    git_commit_id: str | None = None


def resolve_task_dirs(
    *,
    tasks_root: Path,
    tasks: list[str | AdeBenchTaskEntry],
) -> list[ResolvedTask]:
    """Resolve each task entry to a TaskConfig-ready record.

    Legacy slug entries are checked for `<tasks_root>/<slug>/task.toml`
    existence (raises FileNotFoundError on miss). Git-task entries are
    forwarded as-is — harbor's GitTaskId.get_local_path() handles fetch +
    materialization at run-time.
    """
    resolved: list[ResolvedTask] = []
    root = Path(tasks_root).resolve()
    for entry in tasks:
        if isinstance(entry, str):
            task_dir = root / entry
            config = task_dir / "task.toml"
            if not config.exists():
                raise FileNotFoundError(
                    f"ade-bench task '{entry}' not found at {task_dir} "
                    f"(missing task.toml); tasks_root={root}"
                )
            resolved.append(ResolvedTask(path=task_dir))
        else:
            resolved.append(
                ResolvedTask(
                    path=Path(entry.path),
                    git_url=entry.git_url,
                    git_commit_id=entry.git_commit_id,
                )
            )
    return resolved


def rewrite_docker_image(task_toml_path: Path, docker_image: str) -> None:
    """Add or replace [environment].docker_image in task.toml.

    Preserves every other field and the existing TOML structure. Operates as a
    string transform (not a TOML round-trip) so authored field order and inline
    comments survive verbatim.
    """
    text = task_toml_path.read_text()
    pattern = re.compile(r'^docker_image\s*=\s*"[^"]*"\s*$', re.MULTILINE)
    replacement = f'docker_image = "{docker_image}"'
    if pattern.search(text):
        new_text = pattern.sub(replacement, text)
    else:
        new_text = _insert_into_environment_block(text, replacement)
    task_toml_path.write_text(new_text)


def _insert_into_environment_block(text: str, line_to_insert: str) -> str:
    """Insert ``line_to_insert`` as the last line of the ``[environment]`` block.

    Matches ``[environment]`` only as a top-level table header (not
    ``[environment.env]`` or any sub-table). Raises ``ValueError`` if the
    block is absent.
    """
    header_re = re.compile(r'^\[environment\]\s*$', re.MULTILINE)
    m = header_re.search(text)
    if m is None:
        raise ValueError(
            "task.toml has no [environment] block; cannot insert docker_image"
        )
    next_header_re = re.compile(r'^\[[^\]]+\]\s*$', re.MULTILINE)
    next_m = next_header_re.search(text, m.end())
    tail_idx = len(text) if next_m is None else next_m.start()
    insert_idx = tail_idx
    while insert_idx > m.end() and text[insert_idx - 1] in (" ", "\t", "\n"):
        insert_idx -= 1
    prefix = "" if insert_idx == 0 or text[insert_idx - 1] == "\n" else "\n"
    return text[:insert_idx] + prefix + line_to_insert + "\n" + text[insert_idx:]


def materialize_git_task(
    *,
    git_url: str,
    git_commit_id: str,
    source_path: Path,
    docker_image: str = _DEFAULT_DOCKER_IMAGE,
    cache_root: Path,
    _fake_git_source: Path | None = None,
) -> Path:
    """Fetch a git-shaped harbor task, rewrite docker_image, return the local dir.

    The rewrite happens AFTER fetch, BEFORE harbor's environment reads task.toml.
    The original source-of-truth at the git ref is untouched — only the
    materialized copy under ``cache_root`` carries the rewrite.

    ``cache_root`` is razorback-owned (NOT harbor's ``~/.cache/harbor/tasks``);
    keeping the materialization separate prevents harbor's later fetch from
    rmtree-clobbering our rewrite (per
    ``harbor.tasks.client._copy_task_source_to_target``).

    ``_fake_git_source`` is a test-only escape hatch that bypasses harbor's
    ``TaskClient`` and copytree's a local dir to the materialized target.
    Production code paths MUST pass ``_fake_git_source=None``.
    """
    task_id = GitTaskId(
        git_url=git_url, git_commit_id=git_commit_id, path=source_path
    )
    target_dir = cache_root / shortuuid.uuid(str(task_id)) / source_path.name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    if _fake_git_source is not None:
        shutil.copytree(_fake_git_source, target_dir)
    else:
        from harbor.tasks.client import TaskClient

        client = TaskClient()
        _run_async(
            client.download_tasks(
                task_ids=[task_id],
                overwrite=True,
                output_dir=cache_root,
            )
        )
        # Harbor lands the task at cache_root / shortuuid.uuid(str(task_id)) /
        # source_path.name (see harbor.tasks.client._download_git_tasks).
        # target_dir already matches that path.
        if not (target_dir / "task.toml").exists():
            raise FileNotFoundError(
                f"materialize_git_task: harbor fetched but no task.toml at {target_dir}"
            )

    rewrite_docker_image(target_dir / "task.toml", docker_image)
    return target_dir
