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
# (captain decision). `matches_denied_path` uses `fnmatch.fnmatch` (see that
# function below) where `*` CROSSES `/`, so the default's broad cross-`/` globs
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
    "gold.diff",
    "test_patch*",
    "FAIL_TO_PASS*",
    "PASS_TO_PASS*",
    "patch",
    "patch.diff",
    "solution.patch",
)


# Fail-closed deep-scan backstop (cycle 2). The root-anchored
# SWE_BENCH_PRO_DENY_GLOBS strip answers at the TASK ROOT (the assumed
# sibling-file layout, captain-decision #1). But if harbor NESTS the answer
# artifacts under a checkout/metadata dir (`repo/test_patch.diff`,
# `meta/gold_patch.diff`), the root-only globs MISS them and the answers would
# silently leak to the agent — scores invalid, no signal. This guard
# DEEP-scans the materialized view at ALL depths and raises `LeakageError` if
# any file is a swe ANSWER ARTIFACT by PRECISE signature, so a wrong layout
# fails LOUD instead of leaking.
#
# Precise signatures only (NOT broad token globs) so legitimate nested repo
# files (`tests/test_patch_helpers.py`, `src/answer_engine.py`, `lib/patch.py`,
# `docs/gold_notes.md`, `a/test_patch/file.py`) do NOT trip it:
#   - exact basenames (compared case-insensitively; SWE-bench canonical names
#     are lowercase, so normalizing the basename to lower is a safe superset),
#   - a `gold_patch.*` basename glob (covers `gold_patch.diff`/`gold_patch.patch`),
#   - any file located DIRECTLY under a directory named exactly `gold` at any depth.
_SWE_ANSWER_BASENAMES = frozenset(
    {
        "gold.patch",
        "gold.diff",
        "gold_patch.diff",
        "test_patch.diff",
        "test_patch",
        "fail_to_pass.json",
        "pass_to_pass.json",
        "solution.patch",
        # `patch` / `patch.diff` are answer artifacts the deny-glob set strips at
        # the root; the deep guard MUST cover them too or it is weaker than the
        # front-line strip (a nested `repo/patch.diff` would leak). Exact-basename
        # match keeps `lib/patch.py`, `src/patches/apply.py`, `mypatch.diff` clean.
        "patch",
        "patch.diff",
    }
)
# Keep the `gold_patch.*` glob alongside the `gold_patch.diff` literal: it is NOT
# redundant — it also covers `gold_patch.patch` / `gold_patch.json` variants.
_SWE_ANSWER_BASENAME_GLOBS = ("gold_patch.*",)
_SWE_ANSWER_PARENT_DIR = "gold"


def is_swe_answer_artifact(rel_path: str | Path) -> bool:
    """True if `rel_path` is a swe-bench-pro ANSWER artifact by precise signature.

    Matches by exact basename (case-insensitive), the `gold_patch.*` basename
    glob, or membership directly under a `gold/` directory at any depth. Does
    NOT use broad token globs, so legitimate nested repo files are not matched.
    """
    parts = Path(rel_path).as_posix().split("/")
    base = parts[-1].lower()
    if base in _SWE_ANSWER_BASENAMES:
        return True
    if any(fnmatch.fnmatch(base, glob) for glob in _SWE_ANSWER_BASENAME_GLOBS):
        return True
    # case-fold the parent-dir compare too, so files under `Gold/`/`GOLD/` are
    # caught (the basenames are already case-folded above).
    if len(parts) >= 2 and parts[-2].lower() == _SWE_ANSWER_PARENT_DIR:
        return True
    return False


def assert_no_swe_answer_leak(view_dir: Path) -> None:
    """Fail closed if a materialized swe-bench-pro view leaks ANY answer artifact.

    Deep-scans the view at all depths (the root-anchored deny-globs are
    best-effort copy-time stripping; this is the fail-closed backstop). Raises
    `LeakageError` listing every leaked answer artifact found.
    """
    root = Path(view_dir)
    leaked: list[str] = []
    # NOTE: `rglob` does not descend INTO directory-level symlinks; a view that
    # symlinked a whole answer dir in would not be walked through. Latent and
    # non-reachable for the copy-mode materializer (view_mode="copy"); flagged,
    # not re-architected.
    for path in sorted(root.rglob("*")):
        if not path.is_file() and not path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if is_swe_answer_artifact(rel):
            leaked.append(rel)
    if leaked:
        raise LeakageError(
            "materialized swe-bench-pro task view leaks answer artifacts "
            "(wrong layout — answers nested below the task root, root deny-globs "
            "missed them): " + ", ".join(leaked)
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
