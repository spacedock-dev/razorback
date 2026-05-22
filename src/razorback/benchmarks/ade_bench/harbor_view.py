from __future__ import annotations

from pathlib import Path
from typing import Literal

from razorback.harbor_tasks.leakage import DEFAULT_SOLUTION_DENY_GLOBS
from razorback.harbor_tasks.materialize import materialize_harbor_task_view


ADE_BENCH_DENY_GLOBS = DEFAULT_SOLUTION_DENY_GLOBS + (
    "seeds/solution__*.csv",
)


def materialize_ade_harbor_task_view(
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
    )
