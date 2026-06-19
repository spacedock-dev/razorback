# ABOUTME: Pins the single shared task-views root used by producer + both consumers.
from pathlib import Path

from razorback.harbor_tasks.manifest import task_views_root


def test_task_views_root_is_tasks_subdir_of_run_dir():
    run_dir = Path("/runs/job-123")
    # The producer materializes views under run_dir/"tasks" (tasks_root);
    # discovery + scoring must resolve the same root.
    assert task_views_root(run_dir) == run_dir / "tasks"
