from __future__ import annotations

import fnmatch
from pathlib import Path


DEFAULT_SOLUTION_DENY_GLOBS = (
    "solution/**",
    "solutions/**",
    "**/solution.*",
    "**/answer*",
    "**/*answers*",
    "tests/expected/**",
)


class LeakageError(ValueError):
    """Raised when an agent-visible task view contains denied solution data."""


def matches_denied_path(path: str | Path, deny_globs: tuple[str, ...]) -> bool:
    rel = Path(path).as_posix()
    return any(fnmatch.fnmatch(rel, pattern) for pattern in deny_globs)


def assert_no_denied_paths(
    view_dir: Path,
    *,
    deny_globs: tuple[str, ...] = DEFAULT_SOLUTION_DENY_GLOBS,
) -> None:
    """Fail closed if a materialized task view exposes known answer paths."""
    root = Path(view_dir)
    leaked: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() and not path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if matches_denied_path(rel, deny_globs):
            leaked.append(rel)
    if leaked:
        raise LeakageError(
            "materialized Harbor task view contains denied paths: "
            + ", ".join(leaked)
        )
