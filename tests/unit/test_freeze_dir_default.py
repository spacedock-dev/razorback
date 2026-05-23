# ABOUTME: AC-1 unit tests for the default freeze-dir resolver (CAS root).
# ABOUTME: Asserts env-var precedence and that the default is never under cwd.

from pathlib import Path

import pytest


def test_env_var_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "explicit"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert resolve_default_freeze_dir() == (tmp_path / "explicit").resolve()


def test_xdg_fallback_when_no_razorback_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.delenv("RAZORBACK_FREEZE_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    expected = (tmp_path / "xdg" / "razorback" / "freeze").resolve()
    assert resolve_default_freeze_dir() == expected


def test_home_local_share_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.delenv("RAZORBACK_FREEZE_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    expected = (
        tmp_path / "home" / ".local" / "share" / "razorback" / "freeze"
    ).resolve()
    assert resolve_default_freeze_dir() == expected


def test_expands_tilde_in_razorback_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", "~/custom-freeze")
    expected = (tmp_path / "home" / "custom-freeze").resolve()
    assert resolve_default_freeze_dir() == expected


def test_default_is_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.delenv("RAZORBACK_FREEZE_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert resolve_default_freeze_dir().is_absolute()


def test_default_not_under_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1 verification clause: resolved default is not a sub-path of cwd."""
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.delenv("RAZORBACK_FREEZE_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "fake_cwd_worktree").mkdir()
    monkeypatch.chdir(tmp_path / "fake_cwd_worktree")
    resolved = resolve_default_freeze_dir()
    cwd = Path.cwd().resolve()
    assert cwd not in resolved.parents, (
        f"default freeze_dir {resolved} is under cwd {cwd}; AC-1 violated"
    )
