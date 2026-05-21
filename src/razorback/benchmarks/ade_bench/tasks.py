# ABOUTME: ade-bench harbor-task loader. Resolves spec.benchmark.tasks entries
# ABOUTME: (legacy slugs or FU-1 git-task entries) into TaskConfig-ready records.

import asyncio
import fnmatch
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Literal

import shortuuid
from harbor.models.task.id import GitTaskId

from razorback.benchmarks.dab.prepare import _DEFAULT_DOCKER_IMAGE
from razorback.spec.schema import AdeBenchLocalTaskEntry, AdeBenchTaskEntry


_SOLUTION_FILE_GLOB = "seeds/solution__*.csv"

_DEFAULT_COMPOSE_FILENAME = "docker-compose.yaml"


def _select_compose_variant(
    task_yaml: dict,
    *,
    db_type: str | None,
    project_type: str | None,
) -> str:
    """Return the bare compose filename to pull from `shared/defaults/`.

    Mirrors ade_bench upstream's `docker_compose_path` property
    (`ade_bench/handlers/trial_handler.py:292-314`): the (db_type,
    project_type) pair on the selected variant entry resolves to one of four
    filenames under `shared/defaults/`. When `task.yaml` has no `variants:`
    block, or when the resolved entry doesn't carry a db_type/project_type
    pair that matches the rule, falls through to the default compose.

    Selection of WHICH `variants[]` entry uses `variants[0]` as the baseline
    when callers don't pin (db_type, project_type). When both filter fields
    are supplied, picks the first matching entry; raises ValueError if no
    entry matches.
    """
    variants = task_yaml.get("variants") or []
    if not variants:
        return _DEFAULT_COMPOSE_FILENAME

    if db_type is not None and project_type is not None:
        chosen = next(
            (
                v for v in variants
                if v.get("db_type") == db_type
                and v.get("project_type") == project_type
            ),
            None,
        )
        if chosen is None:
            raise ValueError(
                f"ade-bench task has no variant matching "
                f"db_type={db_type!r}, project_type={project_type!r}; "
                f"available={[(v.get('db_type'), v.get('project_type')) for v in variants]}"
            )
    else:
        chosen = variants[0]

    v_db = chosen.get("db_type")
    v_project = chosen.get("project_type")
    if v_db == "snowflake" and v_project == "dbt-fusion":
        return "docker-compose-snowflake-dbtf.yaml"
    if v_db == "snowflake" and v_project == "dbt":
        return "docker-compose-snowflake-dbt.yaml"
    if v_db == "duckdb":
        return "docker-compose-duckdb-dbt.yaml"
    return _DEFAULT_COMPOSE_FILENAME


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
    tasks_root). FU-1 git-task entries set `path`, `git_url`, `git_commit_id`
    so harbor's GitTaskId materializes on demand. PKG-19 local entries set
    `local_slug` to opt into the `materialize_local_task` path.
    """
    path: Path
    git_url: str | None = None
    git_commit_id: str | None = None
    local_slug: str | None = None


def resolve_task_dirs(
    *,
    tasks_root: Path,
    tasks: list[str | AdeBenchTaskEntry | AdeBenchLocalTaskEntry],
) -> list[ResolvedTask]:
    """Resolve each task entry to a TaskConfig-ready record.

    Legacy slug entries are checked for `<tasks_root>/<slug>/task.toml`
    existence (raises FileNotFoundError on miss). Git-task entries are
    forwarded as-is — harbor's GitTaskId.get_local_path() handles fetch +
    materialization at run-time. PKG-19 `AdeBenchLocalTaskEntry` entries
    defer to the translator, which calls `materialize_local_task` against
    `spec.benchmark.ade_bench_root`.
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
        elif isinstance(entry, AdeBenchLocalTaskEntry):
            resolved.append(
                ResolvedTask(path=root, local_slug=entry.slug)
            )
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


def _compute_t_bench_env(
    *,
    ade_bench_root: Path,
    view_dir: Path,
    task_slug: str,
) -> dict[str, str]:
    """Compute the six T_BENCH_* env vars ade-bench's upstream compose template
    references.

    Called only from materialize_local_task → invoked only on
    AdeBenchLocalTaskEntry by translate._build_ade_bench. Harbor-DAB and other
    benchmark kinds never reach this function (AC-2 gating is structural).

    Mirrors upstream ``ade_bench/terminal/docker_compose_manager.py:74-87``'s
    ``DockerComposeEnvVars`` construction with razorback-side substitutions:

    - ``T_BENCH_REPO_ROOT`` — ``ade_bench_root`` absolute path. Upstream sets
      this to the ade-bench checkout root because the compose template's
      ``dockerfile: docker/base/Dockerfile.duckdb-dbt`` (and sibling variants)
      resolves relative to it. The materialized view-dir does NOT contain
      ``docker/`` (PKG-19 only reflects per-task contents), so this MUST stay
      at ``ade_bench_root`` not ``view_dir``.
    - ``T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME`` — deterministic per-slug
      ``ade-bench-client-{task_slug}:latest``. The image is NOT built by
      PKG-23 (see entity §Out of scope).
    - ``T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME`` — deterministic per-slug
      ``{task_slug}-client``. Harbor's compose project-name (the session id)
      enforces per-trial uniqueness on the container layer.
    - ``T_BENCH_TEST_DIR`` — absolute path to the materialized ``tests/`` under
      the view-dir.
    - ``T_BENCH_TASK_LOGS_PATH`` — host-side per-task logs directory under
      ``view_dir / "logs"`` (created so docker compose up does not fail on a
      missing bind-mount source).
    - ``T_BENCH_CONTAINER_LOGS_PATH`` — container-side mount target ``/logs``
      per upstream convention (``DockerComposeManager.CONTAINER_LOGS_PATH``).
    """
    logs_path = view_dir / "logs"
    logs_path.mkdir(exist_ok=True)
    return {
        "T_BENCH_REPO_ROOT": str(ade_bench_root),
        "T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME": (
            f"ade-bench-client-{task_slug}:latest"
        ),
        "T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME": f"{task_slug}-client",
        "T_BENCH_TEST_DIR": str(view_dir / "tests"),
        "T_BENCH_TASK_LOGS_PATH": str(logs_path),
        "T_BENCH_CONTAINER_LOGS_PATH": "/logs",
    }


def _build_task_toml_from_yaml(
    *,
    task_yaml: dict,
    docker_image: str,
    t_bench_env: dict[str, str] | None = None,
) -> str:
    """Synthesize a harbor-shaped task.toml from an upstream ade-bench task.yaml.

    The shim consumes prompts[0].prompt (or the `key=base` entry if present) as
    the harbor `instruction` field (written to `instruction.md` alongside the
    task.toml). The rest of the upstream task.yaml (tags, solution_seeds,
    test_setup, etc.) is dropped — harbor's TaskConfig does not consume those.

    When ``t_bench_env`` is provided, an ``[environment.env]`` sub-table is
    emitted so harbor's ``DockerEnvironment._compose_task_env`` forwards the
    six ``T_BENCH_*`` vars into ``docker compose up``'s environment.
    """
    prompts = task_yaml.get("prompts") or []
    base_prompt = next(
        (p for p in prompts if p.get("key") == "base"), prompts[0] if prompts else None
    )
    if base_prompt is None:
        raise ValueError(
            "ade-bench task.yaml has no 'prompts' entries; cannot synthesize task.toml"
        )
    lines = [
        'instruction = "instruction.md"',
        '',
        '[environment]',
        f'docker_image = "{docker_image}"',
    ]
    if t_bench_env:
        lines.append('')
        lines.append('[environment.env]')
        for k, v in t_bench_env.items():
            v_escaped = v.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'{k} = "{v_escaped}"')
    return '\n'.join(lines) + '\n'


def materialize_local_task(
    *,
    ade_bench_root: Path,
    task_slug: str,
    docker_image: str = _DEFAULT_DOCKER_IMAGE,
    cache_root: Path,
    exclude_globs: tuple[str, ...] = (_SOLUTION_FILE_GLOB,),
    materialize_mode: Literal["bind", "copy"] = "bind",
    db_type: str | None = None,
    project_type: str | None = None,
) -> Path:
    """Build a view-dir for an ade-bench task that re-uses ade_bench_root data.

    Output directory layout under cache_root/<task_slug>/:
        task.toml          (synthesized — harbor-shaped)
        instruction.md     (synthesized from prompts[0].prompt)
        setup.sh           (symlink → ade_bench_root/tasks/<task_slug>/setup.sh)
        solution.sh        (symlink, if present)
        tests/             (symlink — bulk dir; copy if `materialize_mode="copy"`)
        seeds/             (real directory with selective symlinks — every file
                            EXCEPT entries matching `exclude_globs`)

    `materialize_mode="bind"` (default) reflects upstream files as symlinks
    (per-task footprint stays in MB). `materialize_mode="copy"` performs a
    full content copy for provenance-strict / self-contained-tarball runs.
    The exclusion is enforced in BOTH modes — solution__*.csv never appears
    in the view-dir.
    """
    import yaml

    ade_bench_root = Path(ade_bench_root).resolve()
    source_task_dir = ade_bench_root / "tasks" / task_slug
    if not source_task_dir.is_dir():
        raise FileNotFoundError(
            f"materialize_local_task: ade_bench_root has no tasks/{task_slug}/ "
            f"directory (ade_bench_root={ade_bench_root}); "
            f"hydrate ~/git/ade-bench checkout or pass a different slug"
        )
    source_task_yaml = source_task_dir / "task.yaml"
    if not source_task_yaml.exists():
        raise FileNotFoundError(
            f"materialize_local_task: missing task.yaml at {source_task_yaml}"
        )

    target_dir = cache_root / task_slug
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    task_yaml = yaml.safe_load(source_task_yaml.read_text())
    t_bench_env = _compute_t_bench_env(
        ade_bench_root=ade_bench_root,
        view_dir=target_dir,
        task_slug=task_slug,
    )
    (target_dir / "task.toml").write_text(
        _build_task_toml_from_yaml(
            task_yaml=task_yaml,
            docker_image=docker_image,
            t_bench_env=t_bench_env,
        )
    )
    prompts = task_yaml.get("prompts") or []
    base_prompt = next(
        (p for p in prompts if p.get("key") == "base"), prompts[0] if prompts else None
    )
    (target_dir / "instruction.md").write_text(base_prompt["prompt"])

    def _reflect(src: Path, dst: Path) -> None:
        if materialize_mode == "bind":
            os.symlink(src, dst)
        else:
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    for entry in source_task_dir.iterdir():
        if entry.name == "task.yaml":
            continue  # consumed into task.toml + instruction.md
        rel = entry.relative_to(source_task_dir)
        if entry.is_dir():
            has_excluded = any(
                fnmatch.fnmatch(str(p.relative_to(source_task_dir)), g)
                for p in entry.rglob("*")
                for g in exclude_globs
            )
            if not has_excluded:
                _reflect(entry, target_dir / rel)
            else:
                (target_dir / rel).mkdir(parents=True)
                for sub in entry.iterdir():
                    sub_rel = sub.relative_to(source_task_dir)
                    if any(
                        fnmatch.fnmatch(str(sub_rel), g) for g in exclude_globs
                    ):
                        continue
                    _reflect(sub, target_dir / sub_rel)
        else:
            _reflect(entry, target_dir / rel)

    compose_filename = _select_compose_variant(
        task_yaml, db_type=db_type, project_type=project_type
    )
    env_rel = f"environment/{compose_filename}"
    if not any(fnmatch.fnmatch(env_rel, g) for g in exclude_globs):
        source_compose = (
            ade_bench_root / "shared" / "defaults" / compose_filename
        )
        if not source_compose.exists():
            raise FileNotFoundError(
                f"materialize_local_task: shared/defaults/{compose_filename} "
                f"missing under ade_bench_root={ade_bench_root}; ade_bench_root "
                f"may be a stale or shallow checkout"
            )
        env_dir = target_dir / "environment"
        env_dir.mkdir()
        _reflect(source_compose, env_dir / "docker-compose.yaml")

    return target_dir
