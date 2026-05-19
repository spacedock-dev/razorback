# ABOUTME: ade-bench harbor-task loader. Resolves spec.benchmark.tasks entries
# ABOUTME: (legacy slugs or FU-1 git-task entries) into TaskConfig-ready records.

from dataclasses import dataclass
from pathlib import Path

from razorback.spec.schema import AdeBenchTaskEntry


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
