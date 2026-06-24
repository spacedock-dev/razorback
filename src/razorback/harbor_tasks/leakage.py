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


# swe-bench-pro ships the gold patch + test patch + FAIL_TO_PASS/PASS_TO_PASS
# answer artifacts at the TASK ROOT (siblings of the repo checkout, NOT inside
# the repo the agent edits).
#
# This is a STANDALONE curated tuple, NOT `DEFAULT_SOLUTION_DENY_GLOBS + (...)`
# (captain decision). `matches_denied_path` uses `fnmatch.fnmatch` (leakage.py:
# 21-23) where `*` CROSSES `/`, so the default's broad cross-`/` globs
# (`**/answer*`, `**/solution.*`, `**/*answers*`) would strip LEGITIMATE nested
# repo files (`src/answer_engine.py`, `lib/myanswers.py`, `pkg/solution.cfg`)
# that real SWE repos (django/astropy/sympy) ship — corrupting the task. We
# therefore curate only ROOT-ANCHORED globs (one path segment, no `**/`): they
# match the task-root answer files and CANNOT reach into the repo checkout.
#
# We add NO `**/*.patch` / `**/*.diff` for the same false-positive reason
# (design-doc `*.patch` coverage is satisfied by the root-anchored
# `patch`/`patch.diff`/`gold.patch`/`solution.patch` names).
#
# Root-token collision residual: a TOP-LEVEL repo file named `answer*`,
# `gold_patch*`, `test_patch*`, `patch`, etc. would be denied (acceptable —
# answer data lives at the task root, repo source rarely does); their NESTED
# forms are NOT denied. The shared DEFAULT is left untouched.
SWE_BENCH_PRO_DENY_GLOBS = (
    # root solution/answer family (root-anchored; NOT the default's `**/` forms)
    "solution/**",
    "solutions/**",
    "tests/expected/**",
    "solution.*",
    "answer*",
    "answers*",
    # swe answer artifacts at the task root
    "gold/**",
    "gold_patch*",
    "gold.patch",
    "test_patch*",
    "FAIL_TO_PASS*",
    "PASS_TO_PASS*",
    "patch",
    "patch.diff",
    "solution.patch",
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
