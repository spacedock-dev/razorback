# ABOUTME: Exact-set JSON-key snapshot for rk runs list/show under spec §3.3 semver.
# ABOUTME: Field rename or removal within a major version fails this test by design.

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir

LIST_KEYS = {
    "path",
    "experiment",
    "job_name",
    "created_at",
    "run_dir_version",
    "stratified_pass_at_1",
}
SHOW_KEYS = {"manifest", "summary", "path"}


def test_runs_list_json_keys_stable(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j")
    result = CliRunner().invoke(app, ["runs", "list", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0
    entries = json.loads(result.stdout)
    assert set(entries[0]) == LIST_KEYS, (
        f"runs list field set changed (semver violation under §3.3). "
        f"Got: {set(entries[0])}. Expected: {LIST_KEYS}. "
        f"Adding fields requires extending LIST_KEYS; removing or renaming "
        f"requires a major-version bump."
    )


def test_runs_show_json_keys_stable(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j")
    result = CliRunner().invoke(app, ["runs", "show", str(run_dir)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload) == SHOW_KEYS, (
        f"runs show field set changed (semver violation under §3.3). "
        f"Got: {set(payload)}. Expected: {SHOW_KEYS}."
    )
