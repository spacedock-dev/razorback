# ABOUTME: Unit tests for src/razorback/runs/aggregate.py (PKG-17).
# ABOUTME: AC-1: manifest.json schema; AC-2: summary aggregator; AC-3: events concat.

import json
import shutil
from pathlib import Path

import pytest

from razorback.runs.aggregate import (
    MANIFEST_SCHEMA_VERSION,
    write_manifest,
)


FIXTURE_RUN = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runs"
    / "post_harbor_skeleton"
)


def test_write_manifest_schema_fields_present(tmp_path: Path):
    run_dir = tmp_path / "exp" / "job_abc"
    run_dir.mkdir(parents=True)
    write_manifest(
        run_dir,
        spec_path=Path("examples/specs/pkg13-bookreview-claude-harbor-dab-n3.yaml"),
        frozen_spec_hash="deadbeef" * 8,
        provenance_hash="cafef00d" * 8,
        harbor_job_name="job_abc",
        n_trials_total=3,
        n_trials_completed=3,
        n_trials_errored=0,
        per_trial_paths=["bookreview-q1__a", "bookreview-q2__b", "bookreview-q3__c"],
        benchmark_kind="harbor_dab",
    )
    payload = json.loads((run_dir / "manifest.json").read_text())
    assert payload["run_dir_version"] == MANIFEST_SCHEMA_VERSION
    assert payload["experiment"] == "exp"
    assert payload["job_name"] == "job_abc"
    assert payload["spec_path"].endswith("pkg13-bookreview-claude-harbor-dab-n3.yaml")
    assert payload["frozen_spec_hash"] == "deadbeef" * 8
    assert payload["provenance_hash"] == "cafef00d" * 8
    assert payload["harbor_job_name"] == "job_abc"
    assert payload["n_trials_total"] == 3
    assert payload["n_trials_completed"] == 3
    assert payload["n_trials_errored"] == 0
    assert payload["per_trial_paths"] == [
        "bookreview-q1__a",
        "bookreview-q2__b",
        "bookreview-q3__c",
    ]
    assert payload["benchmark_kind"] == "harbor_dab"
    assert payload["created_at"].endswith("Z") or "+" in payload["created_at"]


def test_write_manifest_validates_against_schema(tmp_path: Path):
    """The written manifest validates against manifest_schema.json (AC-1 verified-by)."""
    import jsonschema

    schema_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "razorback"
        / "runs"
        / "manifest_schema.json"
    )
    schema = json.loads(schema_path.read_text())

    run_dir = tmp_path / "exp" / "job_abc"
    run_dir.mkdir(parents=True)
    write_manifest(
        run_dir,
        spec_path=Path("/spec.yaml"),
        frozen_spec_hash="a" * 64,
        provenance_hash="b" * 64,
        harbor_job_name="job_abc",
        n_trials_total=1,
        n_trials_completed=1,
        n_trials_errored=0,
        per_trial_paths=["t1"],
        benchmark_kind="nop",
    )
    payload = json.loads((run_dir / "manifest.json").read_text())
    jsonschema.validate(payload, schema)


def _copy_fixture(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copy(child, target)


def test_aggregate_summary_per_trial_rewards_and_stratified(tmp_path: Path):
    from razorback.runs.aggregate import aggregate_summary

    work = tmp_path / "exp" / "job"
    _copy_fixture(FIXTURE_RUN, work)

    aggregate_summary(work)
    summary = json.loads((work / "summary.json").read_text())

    trial_ids = {t["trial_id"] for t in summary["trials"]}
    assert trial_ids == {"bookreview-q1__a", "bookreview-q2__b", "bookreview-q3__c"}
    by_id = {t["trial_id"]: t for t in summary["trials"]}
    assert by_id["bookreview-q1__a"]["reward"] == 1.0
    assert by_id["bookreview-q2__b"]["reward"] == 0.0
    assert by_id["bookreview-q3__c"]["reward"] is None
    assert by_id["bookreview-q3__c"]["error_reason"] == "AgentTimeoutError"

    assert summary["n_trials_total"] == 3
    assert summary["n_trials_completed"] == 2
    assert summary["n_trials_errored"] == 1

    assert summary["datasets"]["bookreview"]["dataset_pass_at_1"] == 0.5
    assert summary["stratified_pass_at_1"] == 0.5

    assert summary["cost_usd"] is None
    assert summary["summary_version"] == 1
