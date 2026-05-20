# ABOUTME: Tests that the make_run_dir fixture builder synthesizes the run-dir layout.
# ABOUTME: Pins manifest.json + summary.json shape used by pkg1-v2 tests.

from pathlib import Path

from tests.unit.conftest import make_run_dir


def test_make_run_dir_writes_manifest_and_summary(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path,
        root="runs",
        experiment="exp-a",
        job_name="abcd1234",
    )
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "summary.json").exists()
    assert run_dir.parent.name == "exp-a"
    assert run_dir.parent.parent.name == "runs"


def test_make_run_dir_omit_skips_artifact(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path, root="runs", experiment="exp", job_name="j", omit=("summary.json",)
    )
    assert (run_dir / "manifest.json").exists()
    assert not (run_dir / "summary.json").exists()
