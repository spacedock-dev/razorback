# ABOUTME: Runs-dir mount-visibility canary (Phase 1 AC-8).
# ABOUTME: Probes harbor docker bind-mount visibility before any agent invocation.

import subprocess
import uuid
from pathlib import Path
from typing import Callable

from razorback.errors import ConfigInvalidError


def check_runs_dir_visible(
    runs_dir: Path,
    *,
    container_probe: Callable[[Path], bool],
) -> None:
    """Write a canary file under runs_dir and probe whether the container can see it.

    Raises `ConfigInvalidError` (exit code 24) with a diagnostic naming the
    runs-dir, its resolved path, and the fix if the canary is not visible.
    """
    resolved = Path(runs_dir).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    canary = resolved / f".rk-canary-{uuid.uuid4().hex[:8]}"
    canary.write_text("rk-canary\n")
    try:
        visible = container_probe(canary)
    finally:
        canary.unlink(missing_ok=True)
    if not visible:
        raise ConfigInvalidError(
            f"runs-dir not visible to harbor docker containers: "
            f"runs_dir={runs_dir} resolved={resolved}. "
            f"On macOS+Colima, use --runs-dir under /Users/... or a "
            f"virtiofs-mounted volume (configurable via colima.yaml)."
        )


def default_container_probe_factory(
    agent_image: str = "alpine:3.20",
) -> Callable[[Path], bool]:
    """Return a container_probe that execs `ls <canary>` inside a throwaway docker container.

    Returns True iff `ls` succeeds inside a container started with `runs-dir`
    bind-mounted to the same in-container path.
    """

    def _probe(canary_path: Path) -> bool:
        mount_root = canary_path.parent
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{mount_root}:{mount_root}",
                agent_image,
                "ls",
                str(canary_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode == 0

    return _probe
