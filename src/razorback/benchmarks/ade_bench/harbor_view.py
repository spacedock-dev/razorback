from __future__ import annotations

import shlex
from pathlib import Path
from typing import Literal

from razorback.benchmarks.ade_bench.preflight import (
    contract_for_task_id,
    preflight_script_text,
)
from razorback.harbor_tasks.leakage import DEFAULT_SOLUTION_DENY_GLOBS
from razorback.harbor_tasks.materialize import materialize_harbor_task_view


ADE_BENCH_DENY_GLOBS = DEFAULT_SOLUTION_DENY_GLOBS + (
    "seeds/solution__*.csv",
)

_DBT_DEPS_LAYER_MARKER = (
    "# Razorback: install declared dbt packages before agent runtime."
)
_DBT_DEPS_TEST_SETUP_MARKER = (
    "# Razorback: reuse image-installed dbt packages when available."
)
_ADE_WORKSPACE_PREFLIGHT_MARKER = (
    "# Razorback: validate ADE task-specific DuckDB before agent runtime."
)


def materialize_ade_harbor_task_view(
    *,
    source_task_dir: Path,
    view_root: Path,
    task_slug: str,
    docker_image: str | None = None,
    view_mode: Literal["copy", "link"] = "copy",
    dataset_ref: str | None = None,
    dataset_content_hash: str | None = None,
    task_content_hash: str | None = None,
) -> Path:
    view = materialize_harbor_task_view(
        source_task_dir=source_task_dir,
        view_root=view_root,
        benchmark_kind="ade-bench",
        benchmark_task_id=task_slug,
        transform_name="ade-bench-harbor-task-view",
        docker_image=docker_image,
        environment_env={
            "RAZORBACK_BENCHMARK_KIND": "ade-bench",
            "RAZORBACK_BENCHMARK_TASK_ID": task_slug,
        },
        exclude_globs=ADE_BENCH_DENY_GLOBS,
        view_mode=view_mode,
        dataset_ref=dataset_ref,
        dataset_content_hash=dataset_content_hash,
        task_content_hash=task_content_hash,
    )
    _ensure_dbt_deps_image_layer(view)
    _ensure_workspace_preflight_image_layer(view, task_slug=task_slug)
    _ensure_dbt_deps_test_setup_uses_preinstalled_packages(view)
    return view


def _has_dbt_packages_manifest(view_dir: Path) -> bool:
    return (
        (view_dir / "project" / "packages.yml").is_file()
        or (view_dir / "environment" / "project" / "packages.yml").is_file()
    )


def _ensure_dbt_deps_image_layer(view_dir: Path) -> None:
    """Install declared dbt packages during image build for dbt ADE tasks."""
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
    dockerfile.write_text(_insert_before_final_cmd(text, block))


def _ensure_dbt_deps_test_setup_uses_preinstalled_packages(view_dir: Path) -> None:
    """Avoid verifier-time registry access when the image already has packages."""
    if not _has_dbt_packages_manifest(view_dir):
        return

    test_setup = view_dir / "tests" / "test-setup.sh"
    if not test_setup.is_file():
        return

    text = test_setup.read_text()
    if _DBT_DEPS_TEST_SETUP_MARKER in text:
        return

    patched = _replace_standalone_dbt_deps(text)
    if patched != text:
        test_setup.write_text(patched)


def _ensure_workspace_preflight_image_layer(view_dir: Path, *, task_slug: str) -> None:
    contract = contract_for_task_id(task_slug)
    if contract is None:
        return

    environment_dir = view_dir / "environment"
    dockerfile = environment_dir / "Dockerfile"
    if not dockerfile.is_file():
        return

    script_path = environment_dir / "razorback_ade_preflight.py"
    script_path.write_text(preflight_script_text())

    text = dockerfile.read_text()
    if _ADE_WORKSPACE_PREFLIGHT_MARKER in text:
        return

    db_name = _read_db_name(environment_dir) or contract.expected_db_name
    command = " ".join(
        [
            "python",
            "/tmp/razorback_ade_preflight.py",
            "--task-id",
            shlex.quote(task_slug),
            "--workspace",
            "/app",
            "--db-name",
            shlex.quote(db_name),
        ]
    )
    block = "\n".join(
        [
            _ADE_WORKSPACE_PREFLIGHT_MARKER,
            "COPY razorback_ade_preflight.py /tmp/razorback_ade_preflight.py",
            f"RUN {command}",
        ]
    )
    dockerfile.write_text(_insert_before_final_cmd(text, block))


def _read_db_name(environment_dir: Path) -> str | None:
    db_name_path = environment_dir / "db_name.txt"
    if not db_name_path.is_file():
        return None
    db_name = db_name_path.read_text().strip()
    return db_name or None


def _replace_standalone_dbt_deps(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    changed = False
    for line in lines:
        stripped = line.strip()
        if stripped == "dbt deps":
            indent = line[: len(line) - len(line.lstrip())]
            output.extend(
                [
                    f"{indent}{_DBT_DEPS_TEST_SETUP_MARKER}",
                    (
                        f'{indent}if [ ! -d "dbt_packages" ] '
                        f'|| [ -z "$(ls -A dbt_packages 2>/dev/null)" ]; then'
                    ),
                    f"{indent}    dbt deps",
                    f"{indent}else",
                    (
                        f'{indent}    echo "Skipping dbt deps; '
                        'dbt_packages already present."'
                    ),
                    f"{indent}fi",
                ]
            )
            changed = True
        else:
            output.append(line)

    if not changed:
        return text
    return "\n".join(output) + "\n"


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
