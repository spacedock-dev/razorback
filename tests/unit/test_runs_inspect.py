# ABOUTME: Tests for razorback.runs.inspect primitives (list_run_dirs, read_run_dir).
# ABOUTME: Pins the wire shapes that rk runs list/show surface to JSON output.

from pathlib import Path

import pytest

from razorback.runs.inspect import list_run_dirs, read_run_dir
from tests.unit.conftest import make_run_dir


def test_list_run_dirs_returns_all_under_root(tmp_path: Path):
    root = tmp_path / "runs"
    make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    make_run_dir(tmp_path, root="runs", experiment="exp-b", job_name="j2")
    entries = list_run_dirs(root)
    assert len(entries) == 2
    assert {e["experiment"] for e in entries} == {"exp-a", "exp-b"}


def test_list_run_dirs_filters_by_experiment(tmp_path: Path):
    root = tmp_path / "runs"
    make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    make_run_dir(tmp_path, root="runs", experiment="exp-b", job_name="j2")
    entries = list_run_dirs(root, experiment="exp-a")
    assert len(entries) == 1
    assert entries[0]["experiment"] == "exp-a"


def test_list_run_dirs_emits_required_keys(tmp_path: Path):
    root = tmp_path / "runs"
    make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    entries = list_run_dirs(root)
    required = {
        "path",
        "experiment",
        "job_name",
        "created_at",
        "run_dir_version",
        "stratified_pass_at_1",
    }
    assert required.issubset(entries[0])


def test_list_run_dirs_handles_missing_summary(tmp_path: Path):
    root = tmp_path / "runs"
    make_run_dir(
        tmp_path, root="runs", experiment="exp", job_name="j", omit=("summary.json",)
    )
    entries = list_run_dirs(root)
    assert entries[0]["stratified_pass_at_1"] is None


def test_list_run_dirs_empty_root(tmp_path: Path):
    root = tmp_path / "runs"
    root.mkdir()
    assert list_run_dirs(root) == []


def test_list_run_dirs_root_override(tmp_path: Path):
    make_run_dir(tmp_path, root="runs-a", experiment="exp", job_name="j")
    make_run_dir(tmp_path, root="runs-b", experiment="exp", job_name="j")
    assert len(list_run_dirs(tmp_path / "runs-a")) == 1
    assert len(list_run_dirs(tmp_path / "runs-b")) == 1


def test_read_run_dir_returns_manifest_and_summary(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j")
    payload = read_run_dir(run_dir)
    assert payload["manifest"]["experiment"] == "exp"
    assert payload["summary"]["summary_version"] == 1
    assert payload["path"] == str(run_dir)


def test_read_run_dir_raises_on_missing_run_dir(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_run_dir(tmp_path / "does-not-exist")


def test_read_run_dir_raises_on_missing_manifest(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path, root="runs", experiment="exp", job_name="j", omit=("manifest.json",)
    )
    with pytest.raises(FileNotFoundError):
        read_run_dir(run_dir)


def test_read_run_dir_raises_on_missing_summary(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path, root="runs", experiment="exp", job_name="j", omit=("summary.json",)
    )
    with pytest.raises(FileNotFoundError):
        read_run_dir(run_dir)
