# ABOUTME: Phase 4a t2 — precedence walk for read_run_cost (summary → result.stats → per-trial).
# ABOUTME: Pins the cross-plan contract with phase4a-rk-run-budget-gate.read_actual_cost_from_run_dir.

from pathlib import Path

import pytest

from razorback.runs.cost import read_run_cost
from tests.unit.conftest import make_run_dir, make_trial_dir


def test_summary_cost_wins(tmp_path: Path):
    run = make_run_dir(
        tmp_path, root="r", experiment="e", job_name="j",
        cost_in_summary=2.25, cost_in_result_stats=999.0,
    )
    assert read_run_cost(run) == (2.25, True, "summary")


def test_result_stats_used_when_summary_lacks_cost(tmp_path: Path):
    run = make_run_dir(
        tmp_path, root="r", experiment="e", job_name="j",
        cost_in_result_stats=1.50,
    )
    assert read_run_cost(run) == (1.50, True, "result_stats")


def test_result_stats_null_does_not_fall_through(tmp_path: Path):
    run = make_run_dir(
        tmp_path, root="r", experiment="e", job_name="j",
        cost_in_result_stats=None, write_result_stats=True,
    )
    assert read_run_cost(run) == (None, False, "result_stats")


def test_per_trial_agent_result_used_when_higher_sources_absent(tmp_path: Path):
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j")
    make_trial_dir(run, trial_name="t1__abc", agent_cost_usd=0.30)
    make_trial_dir(run, trial_name="t2__def", agent_cost_usd=0.45)
    cost, known, source = read_run_cost(run)
    assert known is True
    assert source == "result_step_agent"
    assert cost == pytest.approx(0.75)


def test_all_null_per_trial_returns_unknown_subscription_auth(tmp_path: Path):
    # Phase 0 baseline-rerun finding: subscription auth → all per-trial nulls.
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j")
    make_trial_dir(run, trial_name="t1__abc", agent_cost_usd=None)
    make_trial_dir(run, trial_name="t2__def", agent_cost_usd=None)
    assert read_run_cost(run) == (None, False, "result_step_agent")


def test_no_cost_field_anywhere(tmp_path: Path):
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j")
    assert read_run_cost(run) == (None, False, None)


def test_missing_run_dir_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_run_cost(tmp_path / "nope")


def test_partial_null_per_trial_sums_non_null(tmp_path: Path):
    """Mixed-null trial costs: sum only the non-null contributions."""
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j")
    make_trial_dir(run, trial_name="t1__a", agent_cost_usd=0.20)
    make_trial_dir(run, trial_name="t2__b", agent_cost_usd=None)
    make_trial_dir(run, trial_name="t3__c", agent_cost_usd=0.10)
    cost, known, source = read_run_cost(run)
    assert known is True
    assert source == "result_step_agent"
    assert cost == pytest.approx(0.30)
