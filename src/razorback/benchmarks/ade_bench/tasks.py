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


_TEST_SH_TEMPLATE = """\
#!/bin/bash
# ABOUTME: PKG-27 — synthesized harbor test.sh that bridges to ade-bench
# ABOUTME: upstream run-tests.sh via docker exec into the client container.
set -uo pipefail

# Harbor's reward file (per harbor.models.trial.paths.EnvironmentPaths).
# REWARD_DIR is honored only for unit-test stubs that cannot write under /.
REWARD_DIR="${REWARD_DIR:-/logs/verifier}"
REWARD_FILE="${REWARD_DIR}/reward.txt"
mkdir -p "${REWARD_DIR}"

CLIENT="${T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME:?T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME unset}"

# Stage test/scripts/seeds files into the client container. Upstream
# ade-bench's host-side harness (ade_bench/harness.py) does this via
# DockerComposeManager.put_archive. Our equivalent tar-streams over
# `docker exec` stdin from main → client.
#
# Harbor's verifier uploads our task's tests/ dir into main:/tests/.
# materialize_local_task packs upstream's shared/scripts + run-tests.sh
# + task seeds under tests/_ade_bench_assets/ so a single upload_dir
# delivers everything we need.
ASSETS=/tests/_ade_bench_assets

_stage_dir() {
    local src_dir="$1"
    local dest_dir="$2"
    if [ -d "${src_dir}" ] && [ -n "$(ls -A "${src_dir}" 2>/dev/null)" ]; then
        docker exec "${CLIENT}" mkdir -p "${dest_dir}"
        tar -C "${src_dir}" -cf - . \\
            | docker exec -i "${CLIENT}" tar -C "${dest_dir}" -xf -
    fi
}

_stage_file() {
    local src="$1"
    local dest_dir="$2"
    if [ -f "${src}" ]; then
        docker exec "${CLIENT}" mkdir -p "${dest_dir}"
        tar -C "$(dirname "${src}")" -cf - "$(basename "${src}")" \\
            | docker exec -i "${CLIENT}" tar -C "${dest_dir}" -xf -
    fi
}

_stage_dir "${ASSETS}/scripts" /scripts
_stage_file "${ASSETS}/run-tests.sh" /tests
_stage_dir "${ASSETS}/seeds" /seeds
# Stage the AUTO_*.sql files harbor uploaded to /tests/. Filter to .sql so
# we do not re-stage the test.sh + _ade_bench_assets subdir.
_AUTO_DIR="$(mktemp -d)"
for f in /tests/*.sql; do
    [ -f "${f}" ] && cp "${f}" "${_AUTO_DIR}/"
done
_stage_dir "${_AUTO_DIR}" /tests
rm -rf "${_AUTO_DIR}"

DBT_STDOUT="$(mktemp)"
# Invoke ade-bench upstream's run-tests.sh verbatim inside the client
# container. The host docker socket is bind-mounted into main so this exec
# reaches the sibling client container managed by the same daemon.
docker exec -w /app "${CLIENT}" bash /tests/run-tests.sh \\
    --db-type=__DB_TYPE__ --project-type=__PROJECT_TYPE__ \\
    2>&1 | tee "${DBT_STDOUT}"

# Parse dbt stdout. Logic mirrors ade_bench.parsers.dbt_parser.DbtParser +
# ade_bench.harness._is_resolved (upstream commit-pinned regex):
#   FAIL if Compilation Error
#   FAIL if zero test lines parsed
#   FAIL if expected_test_count > parsed lines
#   FAIL if any line shows FAIL or ERROR
#   PASS otherwise.
TEST_LINE_RE='[0-9]+ of [0-9]+ (PASS|FAIL|ERROR)( [0-9]+)? [^ ]+ \\.+ \\[(PASS|FAIL|ERROR)'

if grep -qE 'Compilation Error|Encountered an error' "${DBT_STDOUT}"; then
    echo 0 > "${REWARD_FILE}"
    exit 0
fi

EXPECTED="$(grep -oE '\\[ade-bench\\] expected_test_count=[0-9]+' "${DBT_STDOUT}" \\
    | tail -n1 | grep -oE '[0-9]+$' || echo 0)"

PARSED="$(grep -cE "${TEST_LINE_RE}" "${DBT_STDOUT}" || true)"

if [ "${PARSED}" -eq 0 ]; then
    echo 0 > "${REWARD_FILE}"
    exit 0
fi

if [ "${EXPECTED}" -gt "${PARSED}" ]; then
    echo 0 > "${REWARD_FILE}"
    exit 0
fi

# Any FAIL/ERROR test line is a fail.
if grep -E "${TEST_LINE_RE}" "${DBT_STDOUT}" | grep -qE '(FAIL|ERROR)'; then
    echo 0 > "${REWARD_FILE}"
    exit 0
fi

echo 1 > "${REWARD_FILE}"
"""


def _build_test_sh(
    *,
    db_type: str | None,
    project_type: str | None,
) -> str:
    """Synthesize the harbor-shaped tests/test.sh for an ade-bench task.

    The script runs in harbor's ``main`` service. It `docker exec`s into the
    sibling ``client`` container (via the bind-mounted host socket) and runs
    ade-bench upstream's ``shared/defaults/run-tests.sh`` verbatim. dbt stdout
    is parsed by the same regex shape upstream's ``DbtParser`` uses; the
    result is written as ``1`` (PASS) or ``0`` (FAIL) to harbor's
    ``/logs/verifier/reward.txt`` per ``EnvironmentPaths.reward_text_path``.

    ``db_type`` and ``project_type`` are forwarded to run-tests.sh as
    ``--db-type=...`` / ``--project-type=...`` flags so upstream's
    ``run-dbt-test.sh`` filters SQL files by db/project type. ``None`` is
    rendered as an empty string (upstream tolerates missing flags).
    """
    return (
        _TEST_SH_TEMPLATE
        .replace("__DB_TYPE__", db_type or "")
        .replace("__PROJECT_TYPE__", project_type or "")
    )


def _build_task_toml_from_yaml(
    *,
    task_yaml: dict,
    docker_image: str,
    t_bench_env: dict[str, str] | None = None,
    verifier_user: str | None = None,
) -> str:
    """Synthesize a harbor-shaped task.toml from an upstream ade-bench task.yaml.

    The shim consumes prompts[0].prompt (or the `key=base` entry if present) as
    the harbor `instruction` field (written to `instruction.md` alongside the
    task.toml). The rest of the upstream task.yaml (tags, solution_seeds,
    test_setup, etc.) is dropped — harbor's TaskConfig does not consume those.

    When ``t_bench_env`` is provided, an ``[environment.env]`` sub-table is
    emitted so harbor's ``DockerEnvironment._compose_task_env`` forwards the
    six ``T_BENCH_*`` vars into ``docker compose up``'s environment.

    When ``verifier_user`` is set, a ``[verifier]`` block emits the user the
    verifier exec should run as. PKG-27 sets this to ``"root"`` so the bridge
    test.sh has access to the bind-mounted docker socket on `main` (the
    upstream base image's default user `exedev` is in a docker group whose
    GID does not match the host socket's GID).
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
    if verifier_user is not None:
        lines.append('')
        lines.append('[verifier]')
        lines.append(f'user = "{verifier_user}"')
    if t_bench_env:
        # PKG-27: forward the T_BENCH_* keys to the verifier exec env so the
        # synthesized tests/test.sh can resolve $T_BENCH_TASK_DOCKER_CLIENT_*.
        # Harbor's verifier exec uses task.config.verifier.env (per
        # verifier.py:145), separate from compose's [environment.env].
        lines.append('')
        lines.append('[verifier.env]')
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
            verifier_user="root",
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

    # PKG-27: `tests/` becomes a real dir so we can pack the harbor test.sh +
    # upstream's shared assets (scripts + run-tests.sh + seeds) under it. A
    # single harbor upload_dir(tests/) ships them all into main:/tests/.
    _materialize_tests_dir(
        source_tests_dir=source_task_dir / "tests",
        source_seeds_dir=source_task_dir / "seeds",
        ade_bench_root=ade_bench_root,
        target_tests_dir=target_dir / "tests",
        db_type=db_type,
        project_type=project_type,
        exclude_globs=exclude_globs,
    )

    for entry in source_task_dir.iterdir():
        if entry.name == "task.yaml":
            continue  # consumed into task.toml + instruction.md
        if entry.name == "tests":
            continue  # handled above
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
        # PKG-27: harbor's `_environment_docker_compose_path` is hardcoded to
        # `environment/docker-compose.yaml` — a second YAML under env/ is
        # NOT auto-discovered. Synthesize a merged compose that includes
        # upstream's services (via `extends`) AND a socket bind on `main`
        # so the bridge test.sh can `docker exec` into client.
        (env_dir / "docker-compose.yaml").write_text(
            _build_environment_compose(source_compose=source_compose)
        )

    return target_dir


def _materialize_tests_dir(
    *,
    source_tests_dir: Path,
    source_seeds_dir: Path,
    ade_bench_root: Path,
    target_tests_dir: Path,
    db_type: str | None,
    project_type: str | None,
    exclude_globs: tuple[str, ...],
) -> None:
    """Build the per-task tests/ dir uploaded by harbor's verifier into main.

    Layout:
        tests/test.sh                         (synthesized harbor entrypoint)
        tests/AUTO_*.sql                      (copy from upstream task tests/)
        tests/_ade_bench_assets/run-tests.sh  (upstream shared/defaults/)
        tests/_ade_bench_assets/scripts/*     (upstream shared/scripts/)
        tests/_ade_bench_assets/seeds/*       (task seeds — solution__*.csv
                                                 excluded per exclude_globs)
    """
    target_tests_dir.mkdir(parents=True)
    test_sh_path = target_tests_dir / "test.sh"
    test_sh_path.write_text(_build_test_sh(db_type=db_type, project_type=project_type))
    test_sh_path.chmod(0o755)

    if source_tests_dir.is_dir():
        for sub in source_tests_dir.iterdir():
            if not sub.is_file():
                continue
            shutil.copy2(sub, target_tests_dir / sub.name)

    assets_dir = target_tests_dir / "_ade_bench_assets"
    assets_dir.mkdir()

    shared_scripts_src = ade_bench_root / "shared" / "scripts"
    if shared_scripts_src.is_dir():
        shutil.copytree(shared_scripts_src, assets_dir / "scripts")

    run_tests_src = ade_bench_root / "shared" / "defaults" / "run-tests.sh"
    if run_tests_src.is_file():
        shutil.copy2(run_tests_src, assets_dir / "run-tests.sh")

    if source_seeds_dir.is_dir():
        target_seeds = assets_dir / "seeds"
        target_seeds.mkdir()
        for entry in source_seeds_dir.iterdir():
            rel = entry.relative_to(source_seeds_dir)
            if any(
                fnmatch.fnmatch(f"seeds/{rel}", g) for g in exclude_globs
            ):
                continue
            if entry.is_file():
                shutil.copy2(entry, target_seeds / rel)


_COMPOSE_BRIDGE_HEADER = (
    "# Synthesized by razorback PKG-27 materialize_local_task.\n"
    "# Merges ade-bench upstream's compose with a docker-socket bind on main\n"
    "# so harbor's bridge test.sh can `docker exec` into the client container.\n"
)


def _build_environment_compose(*, source_compose: Path) -> str:
    """Synthesize the materialized environment/docker-compose.yaml.

    Includes upstream's compose verbatim (textually) and adds a `services.main`
    block with a host-side docker socket bind. Harbor's compose stack already
    contributes the `main` service via docker-compose-base.yaml; this file is
    layered last so the volume entries merge.

    Uses textual concatenation rather than YAML round-trip so authored comments
    + key order in the upstream compose survive (consistent with razorback's
    other compose handling).
    """
    upstream = source_compose.read_text()
    socket_block = (
        "\n"
        "services:\n"
        "  main:\n"
        "    volumes:\n"
        "      - /var/run/docker.sock:/var/run/docker.sock\n"
    )
    if upstream.lstrip().startswith("services:"):
        # Merge by appending a second top-level mapping; docker compose
        # tolerates this via YAML's multi-document merge inside one stream
        # only if expressed as separate YAML docs. To be safe we emit a
        # single docs YAML by appending the main block under services:.
        return _COMPOSE_BRIDGE_HEADER + _merge_services_block(
            upstream=upstream,
            main_volumes=["/var/run/docker.sock:/var/run/docker.sock"],
        )
    return _COMPOSE_BRIDGE_HEADER + upstream + socket_block


def _merge_services_block(
    *, upstream: str, main_volumes: list[str]
) -> str:
    """Append a `main` service block under the upstream `services:` mapping.

    Uses a YAML round-trip for the merge — preserving authored comments isn't
    a requirement once we synthesize the file (we're already replacing the
    PKG-20 symlink).
    """
    import yaml

    data = yaml.safe_load(upstream) or {}
    services = data.setdefault("services", {})
    main = services.setdefault("main", {})
    volumes = main.setdefault("volumes", [])
    for v in main_volumes:
        if v not in volumes:
            volumes.append(v)
    return yaml.safe_dump(data, sort_keys=False)
