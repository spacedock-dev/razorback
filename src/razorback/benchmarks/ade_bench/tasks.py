# ABOUTME: ade-bench harbor-task loader (§M7 AC-3).
# ABOUTME: Resolves spec.benchmark.tasks slugs to absolute task directories under tasks_root.

from pathlib import Path


def resolve_task_dirs(*, tasks_root: Path, tasks: list[str]) -> list[Path]:
    """Resolve each slug to an absolute harbor task directory.

    Raises FileNotFoundError if any slug does not resolve to a directory containing
    a `task.toml` file at `<tasks_root>/<slug>/task.toml`.
    """
    resolved: list[Path] = []
    root = Path(tasks_root).resolve()
    for slug in tasks:
        task_dir = root / slug
        config = task_dir / "task.toml"
        if not config.exists():
            raise FileNotFoundError(
                f"ade-bench task '{slug}' not found at {task_dir} "
                f"(missing task.toml); tasks_root={root}"
            )
        resolved.append(task_dir)
    return resolved
