# ABOUTME: AC-4 — `git worktree remove --force` MUST NOT destroy runs when the
# ABOUTME: default runs-dir is honored (user-data location outside the worktree).

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from razorback.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_throwaway_worktree(repo_root: Path, base: Path) -> Path:
    """Create a git worktree under `base/wt` rooted at HEAD of `repo_root`."""
    wt = base / "wt"
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "add", "--detach", str(wt), "HEAD"],
        check=True,
        capture_output=True,
    )
    return wt


def _force_remove_worktree(repo_root: Path, wt: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(wt)],
        check=True,
        capture_output=True,
    )


@patch("razorback.cli.run._run_canary", return_value=None)
@patch("razorback.cli.run._invoke_harbor", return_value=0)
def test_worktree_remove_force_does_not_destroy_runs(
    _harbor, _canary, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_root = tmp_path / "runs"
    monkeypatch.setenv("RAZORBACK_RUNS_DIR", str(runs_root))

    wt = _make_throwaway_worktree(REPO_ROOT, tmp_path)
    try:
        # Run `rk run` from INSIDE the worktree using the worktree's copy
        # of the smoke spec. cwd = worktree to match what a real ensign
        # dispatched into a worktree would do.
        original_cwd = Path.cwd()
        os.chdir(wt)
        try:
            result = CliRunner().invoke(
                app,
                [
                    "run",
                    str(wt / "examples" / "specs" / "_deterministic-smoke.yaml"),
                    "--allow-plugin-drift",
                    "--allow-alias-drift",
                ],
            )
        finally:
            os.chdir(original_cwd)

        # Find the experiment/job dir that rk run created under runs_root.
        # rk run always creates `<runs_root>/<experiment>/<job_name>/`.
        assert runs_root.exists(), (
            f"runs_root not created; rk run output:\n{result.stdout}"
        )
        run_dirs = [
            p for p in runs_root.rglob("spec.frozen.yaml")
        ]
        assert run_dirs, (
            f"no spec.frozen.yaml written under {runs_root}; "
            f"rk run output:\n{result.stdout}"
        )
        artifact_path = run_dirs[0]
    finally:
        # The whole point: force-remove the worktree, then re-assert.
        _force_remove_worktree(REPO_ROOT, wt)

    # AC-4 assertion: artifacts are still readable after worktree teardown.
    assert artifact_path.exists(), (
        f"artifact {artifact_path} destroyed by `git worktree remove --force` — AC-4 violated"
    )
    assert artifact_path.read_bytes(), "artifact is empty after worktree teardown"
