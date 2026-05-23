# ABOUTME: AC-1 resolver for the default freeze-tree CAS root.
# ABOUTME: Precedence: $RAZORBACK_FREEZE_DIR > $XDG_DATA_HOME/razorback/freeze > ~/.local/share/razorback/freeze.

import os
from pathlib import Path


def resolve_default_freeze_dir() -> Path:
    """Return the default freeze-tree CAS root as an absolute, expanded path.

    Precedence:
    1. `$RAZORBACK_FREEZE_DIR` if set and non-empty.
    2. `$XDG_DATA_HOME/razorback/freeze` if `$XDG_DATA_HOME` is set and non-empty.
    3. `~/.local/share/razorback/freeze`.

    The returned path is NOT created on disk; callers `mkdir(parents=True,
    exist_ok=True)` when they materialize a freeze tree at
    `<root>/<sealed_hash>/`.
    """
    explicit = os.environ.get("RAZORBACK_FREEZE_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return (Path(xdg).expanduser() / "razorback" / "freeze").resolve()
    return (Path.home() / ".local" / "share" / "razorback" / "freeze").resolve()
