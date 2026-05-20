# ABOUTME: AC-2 — CLI exposes exactly three commands: generate, list, validate.
# ABOUTME: list prints a 12-entry JSON catalog; hello-fixture generate produces a harbor task tree.

import json
import subprocess
from pathlib import Path


def _uv_run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["uv", "run", "razorback-plugin-dab"] + args
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def test_help_lists_three_commands():
    result = _uv_run(["--help"])
    assert result.returncode == 0
    text = result.stdout
    assert "generate" in text
    assert "list" in text
    assert "validate" in text


def test_list_returns_12_entries():
    result = _uv_run(["list"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload) == 12
    names = {entry["name"] for entry in payload}
    assert "bookreview" in names
    assert "yelp" in names


def test_generate_hello_fixture_emits_harbor_shape(tmp_path: Path):
    out = tmp_path / "out"
    result = _uv_run(["generate", "--datasets", "hello-fixture", "--out", str(out)])
    assert result.returncode == 0, result.stderr
    task_dir = out / "hello-fixture"
    assert (task_dir / "task.toml").exists()
    assert (task_dir / "instruction.md").exists()
    assert (task_dir / "tests" / "test.sh").exists()
    assert (task_dir / "environment" / "Dockerfile").exists()


def test_generate_unknown_dataset_exits_2(tmp_path: Path):
    out = tmp_path / "out"
    result = _uv_run(["generate", "--datasets", "bogus", "--data-root", str(tmp_path), "--out", str(out)])
    assert result.returncode == 2
    assert "unknown dataset" in result.stderr


def test_validate_passes_on_hello_fixture(tmp_path: Path):
    out = tmp_path / "out"
    _uv_run(["generate", "--datasets", "hello-fixture", "--out", str(out)])
    result = _uv_run(["validate", str(out)])
    assert result.returncode == 0
    assert "1 tasks validated" in result.stdout
