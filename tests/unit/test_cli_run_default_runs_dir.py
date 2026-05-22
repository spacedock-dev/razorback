# ABOUTME: AC-1+AC-2 CLI integration: `rk run` honors $RAZORBACK_RUNS_DIR when --runs-dir omitted.
# ABOUTME: Explicit --runs-dir still wins (AC-2).

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from razorback.cli import app


def _make_minimal_frozen_spec(tmp_path: Path) -> Path:
    # Reuse the smallest fixture from existing CLI tests: the deterministic-smoke
    # spec is the canonical "won't actually call any model" shape.
    src = Path("examples/specs/_deterministic-smoke.yaml")
    dst = tmp_path / "smoke.frozen.yaml"
    dst.write_bytes(src.read_bytes())
    return dst


@patch("razorback.cli.run._run_canary", return_value=None)
@patch("razorback.cli.run._invoke_harbor", return_value=0)
def test_default_runs_dir_lands_under_razorback_runs_dir_env(
    _harbor, _canary, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAZORBACK_RUNS_DIR", str(tmp_path / "runs"))
    spec = _make_minimal_frozen_spec(tmp_path)
    result = CliRunner().invoke(
        app, ["run", str(spec), "--allow-plugin-drift", "--allow-alias-drift"]
    )
    # Tolerate non-zero exit on downstream contract issues; what matters is
    # that the run-dir got CREATED under the env-var location.
    assert (tmp_path / "runs").exists(), (
        f"expected $RAZORBACK_RUNS_DIR/runs to be created; stdout={result.stdout}"
    )


@patch("razorback.cli.run._run_canary", return_value=None)
@patch("razorback.cli.run._invoke_harbor", return_value=0)
def test_explicit_runs_dir_wins_over_env(
    _harbor, _canary, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-2: explicit --runs-dir is still honored verbatim."""
    monkeypatch.setenv("RAZORBACK_RUNS_DIR", str(tmp_path / "should-not-be-used"))
    spec = _make_minimal_frozen_spec(tmp_path)
    explicit = tmp_path / "explicit-runs"
    CliRunner().invoke(
        app,
        ["run", str(spec), "--runs-dir", str(explicit),
         "--allow-plugin-drift", "--allow-alias-drift"],
    )
    assert explicit.exists(), "explicit --runs-dir was not honored"
    assert not (tmp_path / "should-not-be-used").exists(), (
        "env var took precedence over explicit flag — AC-2 violated"
    )
