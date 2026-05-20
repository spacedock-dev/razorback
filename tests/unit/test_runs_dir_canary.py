# ABOUTME: AC-8: rk run aborts with ExitCode.CONFIG_INVALID when --runs-dir is not visible
# ABOUTME: to the harbor-orchestrated docker containers (e.g., /tmp on macOS+Colima).

from pathlib import Path

import pytest

from razorback.errors import ConfigInvalidError, ExitCode
from razorback.runs_dir_canary import check_runs_dir_visible


def test_canary_returns_silently_for_visible_runs_dir(tmp_path: Path):
    runs_dir = tmp_path / "_runs"
    runs_dir.mkdir()
    # No exception means canary passed.
    check_runs_dir_visible(runs_dir, container_probe=lambda canary_path: True)


def test_canary_raises_config_invalid_when_container_cannot_see(tmp_path: Path):
    runs_dir = tmp_path / "_runs"
    runs_dir.mkdir()
    with pytest.raises(ConfigInvalidError) as exc_info:
        check_runs_dir_visible(runs_dir, container_probe=lambda canary_path: False)
    assert exc_info.value.exit_code == ExitCode.CONFIG_INVALID
    msg = str(exc_info.value)
    assert str(runs_dir) in msg
    # AC-8 diagnostic names the fix.
    assert "/Users/" in msg or "virtiofs" in msg


def test_canary_writes_and_removes_canary_file(tmp_path: Path):
    runs_dir = tmp_path / "_runs"
    runs_dir.mkdir()
    seen_paths: list[Path] = []

    def probe(canary_path: Path) -> bool:
        seen_paths.append(canary_path)
        # Canary file must exist on disk when the probe is invoked.
        assert canary_path.exists(), f"canary {canary_path} not written before probe"
        return True

    check_runs_dir_visible(runs_dir, container_probe=probe)
    assert len(seen_paths) == 1
    # Canary file is removed after probe (positive or negative).
    assert not seen_paths[0].exists()


def test_canary_cleans_up_on_negative_probe(tmp_path: Path):
    runs_dir = tmp_path / "_runs"
    runs_dir.mkdir()
    seen_paths: list[Path] = []

    def probe(canary_path: Path) -> bool:
        seen_paths.append(canary_path)
        return False

    with pytest.raises(ConfigInvalidError):
        check_runs_dir_visible(runs_dir, container_probe=probe)
    assert len(seen_paths) == 1
    assert not seen_paths[0].exists()
