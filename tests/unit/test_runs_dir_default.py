# ABOUTME: AC-1 unit tests for the default runs-dir resolver.
# ABOUTME: Asserts env-var precedence and that the default is never under cwd.

import os
from pathlib import Path

import pytest


def test_env_var_takes_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.setenv("RAZORBACK_RUNS_DIR", str(tmp_path / "explicit"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert resolve_default_runs_dir() == (tmp_path / "explicit").resolve()


def test_xdg_fallback_when_no_razorback_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.delenv("RAZORBACK_RUNS_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    expected = (tmp_path / "xdg" / "razorback" / "runs").resolve()
    assert resolve_default_runs_dir() == expected


def test_home_local_share_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.delenv("RAZORBACK_RUNS_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    expected = (tmp_path / "home" / ".local" / "share" / "razorback" / "runs").resolve()
    assert resolve_default_runs_dir() == expected


def test_expands_tilde_in_razorback_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("RAZORBACK_RUNS_DIR", "~/custom-runs")
    expected = (tmp_path / "home" / "custom-runs").resolve()
    assert resolve_default_runs_dir() == expected


def test_default_is_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.delenv("RAZORBACK_RUNS_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert resolve_default_runs_dir().is_absolute()


def test_default_not_under_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1 verification clause: resolved default is not a sub-path of cwd."""
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.delenv("RAZORBACK_RUNS_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "fake_cwd_worktree").mkdir()
    monkeypatch.chdir(tmp_path / "fake_cwd_worktree")
    resolved = resolve_default_runs_dir()
    cwd = Path.cwd().resolve()
    assert cwd not in resolved.parents, (
        f"default runs_dir {resolved} is under cwd {cwd}; AC-1 violated"
    )
