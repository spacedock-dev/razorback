# ABOUTME: AC-2 + AC-6: atomic running-total appender survives concurrent writes and crashes.

from pathlib import Path

import pytest

from razorback.budget import (
    read_running_total,
    stamp_started,
    stamp_completed,
    current_total_usd,
)


def test_stamp_started_creates_in_flight_record(tmp_path: Path):
    p = tmp_path / "budget.json"
    stamp_started(
        path=p, experiment="exp-1", max_budget_usd=100.0,
        estimate_usd=10.0, run_dir="/runs/job-1",
    )
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert len(rt.invocations) == 1
    inv = rt.invocations[0]
    assert inv.estimate_usd == 10.0
    assert inv.run_dir == "/runs/job-1"
    assert inv.cost_known is None
    assert inv.actual_usd is None
    assert inv.completed_at is None
    # AC-6: in-flight record excludes from running total.
    assert current_total_usd(rt) == 0.0


def test_stamp_completed_updates_in_flight_record(tmp_path: Path):
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    stamp_completed(path=p, run_dir="/runs/job-1",
                    actual_usd=9.5, cost_known=True)
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    inv = rt.invocations[0]
    assert inv.actual_usd == 9.5
    assert inv.cost_known is True
    assert inv.completed_at is not None
    assert current_total_usd(rt) == 9.5


def test_stamp_completed_subscription_auth_null_cost(tmp_path: Path):
    """Phase 0 baseline-rerun finding: agent_result.cost_usd is null on subscription auth."""
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    stamp_completed(path=p, run_dir="/runs/job-1",
                    actual_usd=None, cost_known=False)
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    inv = rt.invocations[0]
    assert inv.actual_usd is None
    assert inv.cost_known is False
    # The estimate counts toward the running total since telemetry is absent.
    assert current_total_usd(rt) == 10.0


def test_concurrent_appends_see_consistent_total(tmp_path: Path):
    """Two stamp_started + stamp_completed pairs interleave without losing data."""
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=20.0, run_dir="/runs/job-2")
    stamp_completed(path=p, run_dir="/runs/job-2", actual_usd=18.0, cost_known=True)
    stamp_completed(path=p, run_dir="/runs/job-1", actual_usd=9.5, cost_known=True)
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert len(rt.invocations) == 2
    assert current_total_usd(rt) == pytest.approx(27.5)


def test_crash_between_start_and_complete_leaves_in_flight(tmp_path: Path):
    """AC-6: crash mid-invocation does NOT corrupt the file.

    Simulates a crash by calling stamp_started but never calling stamp_completed.
    The next read sees the in-flight record and excludes it from the total.
    """
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    # Simulated crash: process dies; no stamp_completed.

    # Subsequent read: in-flight record present, excluded from total.
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert len(rt.invocations) == 1
    assert rt.invocations[0].cost_known is None
    assert current_total_usd(rt) == 0.0  # AC-6 invariant


def test_stamp_completed_for_unknown_run_dir_raises(tmp_path: Path):
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    with pytest.raises(ValueError):
        stamp_completed(path=p, run_dir="/runs/no-such",
                        actual_usd=9.5, cost_known=True)
