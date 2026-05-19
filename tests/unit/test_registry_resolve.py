# ABOUTME: AC-6 — registry add / resolve / list / remove roundtrip.

import os
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def reg_env(tmp_path: Path) -> Path:
    return tmp_path / "registry.yaml"


def _rk(*args: str, registry_path: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "RAZORBACK_REGISTRY": str(registry_path)}
    return subprocess.run(
        ["uv", "run", "rk", *args],
        capture_output=True, text=True, env=env, cwd=_REPO_ROOT,
    )


def test_registry_add_then_resolve_prints_path(reg_env: Path) -> None:
    target = "/some/path/to/baseline"
    cp = _rk("registry", "add", "baseline", "@codex-direct-baseline", target,
             registry_path=reg_env)
    assert cp.returncode == 0, cp.stderr
    cp2 = _rk("registry", "resolve", "baseline", "@codex-direct-baseline",
              registry_path=reg_env)
    assert cp2.returncode == 0, cp2.stderr
    assert cp2.stdout.strip() == target


def test_registry_resolve_unknown_name_exits_nonzero(reg_env: Path) -> None:
    cp = _rk("registry", "resolve", "baseline", "@no-such-name",
             registry_path=reg_env)
    assert cp.returncode != 0


def test_registry_list_then_remove_then_resolve(reg_env: Path) -> None:
    _rk("registry", "add", "constraints", "@cd", "/tmp/c.yaml",
        registry_path=reg_env)
    cp_list = _rk("registry", "list", registry_path=reg_env)
    assert "cd" in cp_list.stdout
    _rk("registry", "remove", "constraints", "@cd", registry_path=reg_env)
    cp_resolve = _rk("registry", "resolve", "constraints", "@cd",
                     registry_path=reg_env)
    assert cp_resolve.returncode != 0


def test_registry_resolve_with_bare_name_no_at(reg_env: Path) -> None:
    """@-prefix is optional on the resolve side too."""
    _rk("registry", "add", "baseline", "@plain", "/p", registry_path=reg_env)
    cp = _rk("registry", "resolve", "baseline", "plain", registry_path=reg_env)
    assert cp.returncode == 0, cp.stderr
    assert cp.stdout.strip() == "/p"


def test_registry_add_replaces_existing(reg_env: Path) -> None:
    """add of the same (kind, name) replaces the previous entry."""
    _rk("registry", "add", "baseline", "@x", "/old", registry_path=reg_env)
    _rk("registry", "add", "baseline", "@x", "/new", registry_path=reg_env)
    cp = _rk("registry", "resolve", "baseline", "@x", registry_path=reg_env)
    assert cp.returncode == 0
    assert cp.stdout.strip() == "/new"
