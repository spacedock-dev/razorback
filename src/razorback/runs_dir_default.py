# ABOUTME: AC-1 resolver for the default runs-dir when --runs-dir is omitted.
# ABOUTME: Precedence: $RAZORBACK_RUNS_DIR > $XDG_DATA_HOME/razorback/runs > ~/.local/share/razorback/runs.

import os
from pathlib import Path


def resolve_default_runs_dir() -> Path:
    """Return the default runs-dir as an absolute, expanded, resolved path.

    Precedence:
    1. `$RAZORBACK_RUNS_DIR` if set and non-empty.
    2. `$XDG_DATA_HOME/razorback/runs` if `$XDG_DATA_HOME` is set and non-empty.
    3. `~/.local/share/razorback/runs`.

    The returned path is NOT created on disk; callers `mkdir(parents=True,
    exist_ok=True)` after the canary check (see `cli/run.py`).
    """
    explicit = os.environ.get("RAZORBACK_RUNS_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return (Path(xdg).expanduser() / "razorback" / "runs").resolve()
    return (Path.home() / ".local" / "share" / "razorback" / "runs").resolve()
