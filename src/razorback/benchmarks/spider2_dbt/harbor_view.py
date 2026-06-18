from __future__ import annotations

import shlex
import shutil
import stat
from pathlib import Path
from typing import Literal

from razorback.benchmarks.spider2_dbt import duckdb_match as _duckdb_match_mod
from razorback.benchmarks.spider2_dbt import eval_spec as _eval_spec_mod
from razorback.benchmarks.spider2_dbt import verify as _verify_mod
from razorback.benchmarks.spider2_dbt.preflight import (
    preflight_script_text,
    resolve_spider2_db_name,
)
from razorback.harbor_tasks.leakage import DEFAULT_SOLUTION_DENY_GLOBS
from razorback.harbor_tasks.materialize import materialize_harbor_task_view


SPIDER2_DBT_DENY_GLOBS = DEFAULT_SOLUTION_DENY_GLOBS + (
    # Both the top-level and nested forms: fnmatch's `**/` prefix requires a
    # leading path segment, so `**/gold/**` alone misses a top-level `gold/`
    # dir. The bare `gold/**` variants close that leakage hole (surfaced by
    # the plan-gate cycle-1 negative-leakage rider).
    "expected/**",
    "**/expected/**",
    "gold/**",
    "**/gold/**",
    "golden/**",
    "**/golden/**",
)

# The dbt project root inside the running container. The r5 verifier
# (spider2-dbt-duckdb-match-verifier) and run-wiring entity read this same
# path; do not let later layers drift from it (Task 0 contract).
_APP_ROOT = "/app"

# Source-side directory (inside the materialized view) holding the dbt
# project. spider2-dbt nests the dbt project under `dbt_project/` — the one
# structural divergence from ade-bench's `project/`.
_DBT_PROJECT_DIRNAME = "dbt_project"

_BUILD_CONTEXT_MARKER = (
    "# Razorback: land spider2-dbt project + source DuckDB at /app before agent runtime."
)
_DBT_DEPS_LAYER_MARKER = (
    "# Razorback: install declared dbt packages before agent runtime."
)
_SPIDER2_WORKSPACE_PREFLIGHT_MARKER = (
    "# Razorback: validate spider2-dbt source DuckDB before agent runtime."
)

# Emitted into the view's tests/ — Harbor uploads tests/ to the container only
# at verify time, so the gold .duckdb + eval spec reach the verifier but never
# the agent. `{predicted_db}` is filled from `resolve_spider2_db_name` (the
# SHARED `/app/<db_name>.duckdb` contract) so the verifier scores the SAME
# DuckDB the build-time preflight validated — NOT a hardcoded /app/spider2.duckdb.
_TEST_SH_TEMPLATE = """#!/bin/sh
set -eu
mkdir -p /logs/verifier
python /tests/verify.py \\
  --predicted-db {predicted_db} \\
  --gold-db {gold_db} \\
  --eval-spec /tests/spider2_eval.jsonl \\
  --reward-out /logs/verifier/reward.json
"""


def materialize_spider2_harbor_task_view(
    *,
    source_task_dir: Path,
    view_root: Path,
    task_slug: str,
    docker_image: str | None = None,
    view_mode: Literal["copy", "link"] = "copy",
) -> Path:
    view = materialize_harbor_task_view(
        source_task_dir=source_task_dir,
        view_root=view_root,
        benchmark_kind="spider2-dbt",
        benchmark_task_id=task_slug,
        transform_name="spider2-dbt-harbor-task-view",
        docker_image=docker_image,
        environment_env={
            "RAZORBACK_BENCHMARK_KIND": "spider2-dbt",
            "RAZORBACK_BENCHMARK_TASK_ID": task_slug,
        },
        exclude_globs=SPIDER2_DBT_DENY_GLOBS,
        view_mode=view_mode,
    )
    # RIDER (Codex finding 2): stage dbt_project/ (incl. the source .duckdb)
    # into the build context and COPY it to /app BEFORE the preflight RUN, so
    # the preflight `--workspace /app` can never fail on a missing project.
    _ensure_spider2_build_context_layer(view)
    _ensure_dbt_deps_image_layer(view)
    _ensure_workspace_preflight_image_layer(view, task_slug=task_slug)
    _ensure_verifier_assets(
        view, source_task_dir=Path(source_task_dir), task_slug=task_slug
    )
    return view


def _copy_into_view(src: Path, dst: Path) -> None:
    """copy2 src->dst, first replacing any symlink dst with a view-owned file.

    In link mode the generic materializer reflects allowed source files as
    symlinks, so a view path that collides with a source-provided name (e.g. a
    source `tests/verify.py` or top-level `tests/<gold>.duckdb`) is a symlink
    back to the source; a bare copy2 would follow it and overwrite the source
    task. Same write-through class the Dockerfile/preflight/test.sh writes guard.
    """
    if dst.is_symlink():
        dst.unlink()
    shutil.copy2(src, dst)


def _ensure_verifier_assets(
    view_dir: Path, *, source_task_dir: Path, task_slug: str
) -> None:
    """Copy the comparator + gold data + test.sh into the view's tests/ dir.

    Gold assets are read from the SOURCE task's tests/gold/ (the reflected view
    stripped them via the **/gold/** deny-glob) and written WITHOUT a `gold/`
    path segment so `assert_no_denied_paths` stays green while the
    verifier-uploaded tests/ dir still carries them. The emitted test.sh's
    `--predicted-db` is `/app/<db_name>.duckdb` where `<db_name>` comes from the
    SHARED `resolve_spider2_db_name` resolver (RIDER, Codex r5-plan finding) —
    never a hardcoded `/app/spider2.duckdb`.

    The GOLD DB basename is driven by the eval spec's
    ``evaluation.parameters.gold`` (real Spider2 tasks name the gold per task,
    e.g. ``playbook.duckdb``) — the EXACT named file is copied and
    ``--gold-db /tests/<basename>`` is emitted. Fails closed (raises) if the
    spec names a gold file that does not exist under ``tests/gold/``, so the
    verifier never scores against a missing/wrong gold.
    """
    # Every spider2-dbt task is duckdb_match-scored, so its source MUST ship
    # tests/gold/spider2_eval.jsonl (+ the named gold DB). A missing gold dir is
    # NOT a "skip scoring" signal — silently returning would leave the source
    # test.sh in place (e.g. a stub `exit 0`), materializing an unscored /
    # trivially-passing task under dataset skew or a resolver bug. Fail closed.
    source_gold = Path(source_task_dir) / "tests" / "gold"
    source_spec = source_gold / "spider2_eval.jsonl"
    if not source_spec.is_file():
        raise FileNotFoundError(
            f"spider2-dbt task {task_slug!r} is missing its gold eval spec "
            f"{source_spec} — every spider2-dbt task is duckdb_match-scored and "
            "must ship tests/gold/spider2_eval.jsonl + its named gold DB; "
            "refusing to materialize an unscored task (fail-closed)"
        )

    tests = view_dir / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    for mod in (_duckdb_match_mod, _eval_spec_mod, _verify_mod):
        src = Path(mod.__file__)
        _copy_into_view(src, tests / src.name)

    # Resolve the gold DB basename from the spec (NOT hardcoded gold.duckdb).
    # Real Spider2 tasks name the gold per task; scoring the wrong/missing file
    # is a benchmark-correctness defect. A wrapped spec without parameters.gold
    # fails closed inside load_eval_spec.
    spec = _eval_spec_mod.load_eval_spec(source_spec)
    gold_basename = spec.gold or "gold.duckdb"
    source_gold_db = source_gold / gold_basename
    if not source_gold_db.is_file():
        raise FileNotFoundError(
            f"spider2-dbt gold spec names gold DB {gold_basename!r} but "
            f"{source_gold_db} does not exist; refusing to emit a verifier that "
            "would score against a missing gold (fail-closed)"
        )
    _copy_into_view(source_gold_db, tests / gold_basename)
    _copy_into_view(source_spec, tests / "spider2_eval.jsonl")

    # Resolve the agent-facing DuckDB stem from the dbt project (or the slug
    # fallback) so the verifier compares the SAME `/app/<db_name>.duckdb` the
    # preflight validated and the agent operates against.
    project_dir = _dbt_project_dir(view_dir)
    db_name = resolve_spider2_db_name(
        project_dir if project_dir is not None else view_dir,
        task_slug=task_slug,
    )
    test_sh = tests / "test.sh"
    if test_sh.is_symlink():
        test_sh.unlink()
    # shlex.quote BOTH args: db_name is resolved from the task's profiles.yml
    # path (external input) and gold_basename from the eval spec; emitting either
    # unquoted into the verifier shell script is a command-injection boundary.
    # gold_basename is also allowlisted in load_eval_spec (traversal defense);
    # quoting closes the injection half for both arguments at the emission point.
    test_sh.write_text(
        _TEST_SH_TEMPLATE.format(
            predicted_db=shlex.quote(f"{_APP_ROOT}/{db_name}.duckdb"),
            gold_db=shlex.quote(f"/tests/{gold_basename}"),
        )
    )
    test_sh.chmod(
        test_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )

    # The deny-glob reflection strips gold FILES but leaves the now-empty
    # `gold/` directory behind. Prune empty `gold/`-named dirs so no `gold/`
    # path segment survives anywhere in the agent-facing view.
    for gold_dir in sorted(
        (p for p in view_dir.rglob("gold") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        if not any(gold_dir.iterdir()):
            gold_dir.rmdir()


def _has_dbt_project(view_dir: Path) -> bool:
    """spider2-dbt nests the dbt project under `dbt_project/` (or under
    `environment/dbt_project/`)."""
    return _dbt_project_dir(view_dir) is not None


def _dbt_project_dir(view_dir: Path) -> Path | None:
    """The dbt project root inside the view (`dbt_project/` or
    `environment/dbt_project/`), if present.

    This is the on-disk stand-in for the container's `/app` dbt root: the
    source `.duckdb` and any `profiles.yml` live here, so it is the workspace
    `resolve_spider2_db_name` reads to pin `/app/<db_name>.duckdb`.
    """
    direct = view_dir / _DBT_PROJECT_DIRNAME
    if direct.is_dir():
        return direct
    nested = view_dir / "environment" / _DBT_PROJECT_DIRNAME
    if nested.is_dir():
        return nested
    return None


def _has_dbt_packages_manifest(view_dir: Path) -> bool:
    return (
        (view_dir / _DBT_PROJECT_DIRNAME / "packages.yml").is_file()
        or (
            view_dir / "environment" / _DBT_PROJECT_DIRNAME / "packages.yml"
        ).is_file()
    )


def _ensure_spider2_build_context_layer(view_dir: Path) -> None:
    """Land the dbt project + source DuckDB at /app inside the image build.

    The Docker build context is the view's `environment/` directory, so the
    dbt project (which the materializer reflects to `<view>/dbt_project/`)
    must be staged *inside* `environment/` for a COPY to reach it. This makes
    the entity own the minimal COPY/context the preflight RUN depends on,
    rather than assuming run-wiring already placed the project at /app.
    """
    if not _has_dbt_project(view_dir):
        return

    dockerfile = view_dir / "environment" / "Dockerfile"
    if not dockerfile.is_file():
        return

    text = dockerfile.read_text()
    if _BUILD_CONTEXT_MARKER in text:
        return

    environment_dir = view_dir / "environment"
    source_project = view_dir / _DBT_PROJECT_DIRNAME
    staged_project = environment_dir / _DBT_PROJECT_DIRNAME
    if source_project.is_dir() and not staged_project.exists():
        # Stage into the build context so the COPY source resolves. Copy
        # (not move) so the view's own dbt_project/ remains intact for
        # downstream consumers/tests.
        shutil.copytree(source_project, staged_project)

    block = "\n".join(
        [
            _BUILD_CONTEXT_MARKER,
            f"COPY {_DBT_PROJECT_DIRNAME}/ {_APP_ROOT}/",
        ]
    )
    # In `view_mode="link"` the reflected Dockerfile is a symlink back into the
    # shared source tree; writing through it would follow the link and corrupt
    # the version-controlled source. Replace the symlink with a real,
    # view-owned file so the layer injection stays inside the view.
    if dockerfile.is_symlink():
        dockerfile.unlink()
    dockerfile.write_text(_insert_before_final_cmd(text, block))


def _ensure_dbt_deps_image_layer(view_dir: Path) -> None:
    """Install declared dbt packages during image build for dbt spider2 tasks."""
    if not _has_dbt_packages_manifest(view_dir):
        return

    dockerfile = view_dir / "environment" / "Dockerfile"
    if not dockerfile.is_file():
        return

    text = dockerfile.read_text()
    if _DBT_DEPS_LAYER_MARKER in text:
        return

    block = "\n".join(
        [
            _DBT_DEPS_LAYER_MARKER,
            "RUN if [ -f /app/packages.yml ]; then cd /app && dbt deps; fi",
        ]
    )
    # In `view_mode="link"` the reflected Dockerfile is a symlink back into the
    # shared source tree; writing through it would follow the link and corrupt
    # the version-controlled source. Replace the symlink with a real,
    # view-owned file so the layer injection stays inside the view.
    if dockerfile.is_symlink():
        dockerfile.unlink()
    dockerfile.write_text(_insert_before_final_cmd(text, block))


def _ensure_workspace_preflight_image_layer(
    view_dir: Path, *, task_slug: str
) -> None:
    """Validate the source DuckDB at build time, before the agent runs.

    Gated on `_has_dbt_project`: spider2-dbt has no task families, so the
    preflight is injected whenever the task is a dbt project. By the time this
    RUN executes, the build-context layer has already COPY'd dbt_project/ (and
    its .duckdb) to /app, so `--workspace /app` cannot fail on a missing
    project.
    """
    if not _has_dbt_project(view_dir):
        return

    environment_dir = view_dir / "environment"
    dockerfile = environment_dir / "Dockerfile"
    if not dockerfile.is_file():
        return

    script_path = environment_dir / "razorback_spider2_preflight.py"
    # In `view_mode="link"` a source task that ships a file with this exact name
    # is reflected as a symlink back into the shared source tree; writing through
    # it would follow the link and corrupt the version-controlled source. Replace
    # the symlink with a real, view-owned file so the write stays inside the view
    # (mirrors the Dockerfile/task.toml unlink-then-write guards).
    if script_path.is_symlink():
        script_path.unlink()
    script_path.write_text(preflight_script_text())

    text = dockerfile.read_text()
    if _SPIDER2_WORKSPACE_PREFLIGHT_MARKER in text:
        return

    # Pin the agent-facing DuckDB via the SHARED resolver so the build-time
    # preflight validates the SAME `/app/<db_name>.duckdb` the agent (and the
    # r5 verifier) operate against — never a glob-first under multi/stale-DB
    # drift. Resolution fails CLOSED (raises) when >1 *.duckdb exists and none
    # is pinned; that aborts the materialize, the correct fail-closed point.
    project_dir = _dbt_project_dir(view_dir)
    db_name = resolve_spider2_db_name(
        project_dir if project_dir is not None else view_dir,
        task_slug=task_slug,
    )
    command = " ".join(
        [
            "python",
            "/tmp/razorback_spider2_preflight.py",
            "--task-id",
            shlex.quote(task_slug),
            "--workspace",
            _APP_ROOT,
            "--db-name",
            shlex.quote(db_name),
        ]
    )
    block = "\n".join(
        [
            _SPIDER2_WORKSPACE_PREFLIGHT_MARKER,
            "COPY razorback_spider2_preflight.py /tmp/razorback_spider2_preflight.py",
            f"RUN {command}",
        ]
    )
    # In `view_mode="link"` the reflected Dockerfile is a symlink back into the
    # shared source tree; writing through it would follow the link and corrupt
    # the version-controlled source. Replace the symlink with a real,
    # view-owned file so the layer injection stays inside the view.
    if dockerfile.is_symlink():
        dockerfile.unlink()
    dockerfile.write_text(_insert_before_final_cmd(text, block))


def _insert_before_final_cmd(text: str, block: str) -> str:
    lines = text.rstrip().splitlines()
    insert_at = None
    for idx, line in enumerate(lines):
        if line.lstrip().startswith("CMD "):
            insert_at = idx
    block_lines = ["", *block.splitlines()]
    if insert_at is None:
        lines.extend(block_lines)
    else:
        lines[insert_at:insert_at] = block_lines
    return "\n".join(lines) + "\n"
