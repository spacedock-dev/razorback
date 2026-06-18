from __future__ import annotations

from pathlib import Path
from typing import Literal

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


def materialize_spider2_harbor_task_view(
    *,
    source_task_dir: Path,
    view_root: Path,
    task_slug: str,
    docker_image: str | None = None,
    view_mode: Literal["copy", "link"] = "copy",
) -> Path:
    return materialize_harbor_task_view(
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
