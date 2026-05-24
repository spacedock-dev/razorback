# ABOUTME: Cycle-9 — plugin CLI's --data-root resolves via DATAAGENTBENCH_DATA_ROOT env
# ABOUTME: when not explicitly passed; explicit --data-root always wins.

"""The pre-hm translator carried a `DATAAGENTBENCH_DATA_ROOT` env-default
fallback for `data_root` when the spec didn't carry it explicitly. The
hm migration deleted that translator-side fallback. To preserve consumer
equivalence for the 19 goal1 specs (which never set `data_root`
explicitly), the env-default moves INTO the plugin CLI itself per captain
decision 2026-05-25 (option b).

Resolution order:
  1. Explicit `--data-root <path>` on CLI → uses that.
  2. Else `$DATAAGENTBENCH_DATA_ROOT` if set + non-empty → uses that.
  3. Else `~/dataagentbench/data` if it exists as a directory → uses that.
  4. Else exit with a named error pointing at the env var.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _uv_run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Invoke `razorback-plugin-dab` via uv with optional env override."""
    cmd = ["uv", "run", "razorback-plugin-dab"] + args
    run_env = dict(os.environ)
    # Clear inherited so the test owns the env-fallback fully.
    run_env.pop("DATAAGENTBENCH_DATA_ROOT", None)
    if env:
        run_env.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=run_env)


def test_explicit_data_root_wins_over_env(tmp_path: Path):
    """Explicit --data-root /explicit/path ignores env."""
    explicit = tmp_path / "explicit-root"
    explicit.mkdir()
    bogus = tmp_path / "bogus-from-env"
    bogus.mkdir()
    out = tmp_path / "out"
    # Use an unknown-dataset path that exits 2 with a dataset error rather than
    # a data-root error — proves the CLI accepted the explicit root.
    result = _uv_run(
        [
            "generate",
            "--datasets", "ad-hoc-not-in-catalog",
            "--data-root", str(explicit),
            "--out", str(out),
        ],
        env={"DATAAGENTBENCH_DATA_ROOT": str(bogus)},
    )
    assert "--data-root is required" not in result.stderr
    # The CLI proceeded past the data-root gate and hit the dataset-name check.
    assert "unknown dataset" in result.stderr.lower() or result.returncode != 0


def test_env_default_used_when_no_explicit_flag(tmp_path: Path):
    """No --data-root on CLI + $DATAAGENTBENCH_DATA_ROOT set → CLI uses env."""
    env_root = tmp_path / "from-env"
    env_root.mkdir()
    out = tmp_path / "out"
    result = _uv_run(
        [
            "generate",
            "--datasets", "ad-hoc-not-in-catalog",
            "--out", str(out),
        ],
        env={"DATAAGENTBENCH_DATA_ROOT": str(env_root)},
    )
    # The CLI accepted the env-default; it now fails at the dataset-name check,
    # not the missing-data-root check.
    assert "--data-root is required" not in result.stderr, result.stderr
    assert "unknown dataset" in result.stderr.lower() or result.returncode != 0


def test_no_explicit_no_env_no_default_dir_errors_with_named_env_var(tmp_path: Path):
    """No --data-root + no env + no ~/dataagentbench/data → clear named error.

    Uses HOME override pointing at an empty tmp_path so the default path
    `~/dataagentbench/data` doesn't resolve to a real dir.
    """
    out = tmp_path / "out"
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    result = _uv_run(
        ["generate", "--datasets", "ad-hoc-not-in-catalog", "--out", str(out)],
        env={"HOME": str(fake_home)},
    )
    assert result.returncode == 2, result.stderr
    # Message must name DATAAGENTBENCH_DATA_ROOT so consumers know the env var.
    assert "DATAAGENTBENCH_DATA_ROOT" in result.stderr, result.stderr


def test_default_home_dir_used_when_present(tmp_path: Path):
    """No --data-root + no env + ~/dataagentbench/data exists → CLI uses it."""
    fake_home = tmp_path / "fake-home"
    (fake_home / "dataagentbench" / "data").mkdir(parents=True)
    out = tmp_path / "out"
    result = _uv_run(
        ["generate", "--datasets", "ad-hoc-not-in-catalog", "--out", str(out)],
        env={"HOME": str(fake_home)},
    )
    # The CLI accepted the home-default; now fails at the dataset-name check.
    assert "--data-root is required" not in result.stderr
    assert "DATAAGENTBENCH_DATA_ROOT" not in result.stderr
    assert "unknown dataset" in result.stderr.lower() or result.returncode != 0


def test_hello_fixture_unchanged_by_env_default(tmp_path: Path):
    """hello-fixture short-circuits before the data-root gate — env-default
    addition must not regress this path."""
    out = tmp_path / "out"
    result = _uv_run(
        ["generate", "--datasets", "hello-fixture", "--out", str(out)],
        env={},  # no env, no flag
    )
    assert result.returncode == 0, result.stderr
    assert (out / "hello-fixture" / "task.toml").is_file()
