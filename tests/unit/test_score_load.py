# ABOUTME: rk score loader walks run-dir for per-trial state + stratum.
# ABOUTME: AC-1 + AC-3 + AC-6 prerequisite — TrialRecord shape pins downstream contracts.

from pathlib import Path

import pytest

from razorback.score.load import ScoreInputError, TrialRecord, load_run_dir

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "score"
MIXED = FIXTURE_ROOT / "mixed_trial_run_dir"


def _by_name(records: list[TrialRecord]) -> dict[str, TrialRecord]:
    return {r.trial_name: r for r in records}


def test_mixed_run_dir_yields_three_records() -> None:
    records = load_run_dir(MIXED)
    assert len(records) == 3


def test_completed_pass_record_shape() -> None:
    records = _by_name(load_run_dir(MIXED))
    r = records["trial-completed-pass"]
    assert r.state == "completed"
    assert r.passed is True
    assert r.reward == 1.0
    assert r.stratum == "bookreview"
    assert r.error_class is None


def test_completed_fail_record_shape() -> None:
    records = _by_name(load_run_dir(MIXED))
    r = records["trial-completed-fail"]
    assert r.state == "completed"
    assert r.passed is False
    assert r.reward == 0.0
    assert r.stratum == "bookreview"
    assert r.error_class is None


def test_errored_record_shape() -> None:
    records = _by_name(load_run_dir(MIXED))
    r = records["trial-errored"]
    assert r.state == "errored"
    assert r.passed is None
    assert r.reward is None
    assert r.stratum == "bookreview"
    assert r.error_class == "SubprocessError"


def test_load_skips_non_trial_children(tmp_path: Path) -> None:
    """Files at run-dir root (summary.json, per_trial_outcomes.json) aren't trials."""
    records = load_run_dir(MIXED)
    names = {r.trial_name for r in records}
    assert "summary.json" not in names
    assert "per_trial_outcomes.json" not in names


def test_load_missing_run_dir_raises(tmp_path: Path) -> None:
    with pytest.raises((FileNotFoundError, ScoreInputError)):
        load_run_dir(tmp_path / "does-not-exist")


def test_load_resolves_task_view_manifest_stratum(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    view = run_dir / "_razorback" / "task_views" / "ade-bench-adebench-fixture-001"
    view.mkdir(parents=True)
    (view / "view_manifest.json").write_text(
        """{
          "benchmark_kind": "ade-bench",
          "benchmark_task_id": "adebench-fixture-001"
        }"""
    )
    trial = run_dir / "ade-bench-adebench-fixture-001__abc1234"
    trial.mkdir(parents=True)
    (trial / "result.json").write_text(
        """{"verifier_result": {"rewards": {"reward": 1.0}}}"""
    )

    [record] = load_run_dir(run_dir)

    assert record.stratum == "ade-bench"
    assert record.stratum_payload == {
        "dataset": "ade-bench",
        "query_id": "adebench-fixture-001",
        "benchmark_kind": "ade-bench",
        "benchmark_task_id": "adebench-fixture-001",
    }
    assert record.state == "completed"
    assert record.passed is True
