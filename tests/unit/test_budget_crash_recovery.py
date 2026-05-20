# ABOUTME: AC-6: crash-recovery atomicity; AC-2 cost-telemetry-gap end-to-end.

import json
from pathlib import Path

import pytest

from razorback.budget import (
    read_running_total,
    stamp_started,
    stamp_completed,
    current_total_usd,
    read_actual_cost_from_run_dir,
)


def test_crash_invariant_holds_for_rk_runs_cost_consumer(tmp_path: Path):
    """Phase 0 baseline cited finding: rk runs cost must see consistent totals."""
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    stamp_completed(path=p, run_dir="/runs/job-1",
                    actual_usd=9.5, cost_known=True)

    # Second invocation crashes: stamp_started only.
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-2")
    # Simulated crash here.

    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert len(rt.invocations) == 2
    # AC-6 invariant: only completed invocations contribute.
    assert current_total_usd(rt) == 9.5


def test_subscription_auth_null_cost_reader(tmp_path: Path):
    """Phase 0 baseline-rerun item C: agent_result.cost_usd is null on subscription auth."""
    run_dir = tmp_path / "run-x"
    run_dir.mkdir()
    # Harbor emits result.json with stats.cost_usd: null (subscription-billed).
    (run_dir / "result.json").write_text(json.dumps({
        "stats": {"n_completed_trials": 3, "cost_usd": None}
    }))
    # No summary.json, or summary.json without cost field.

    cost, known = read_actual_cost_from_run_dir(run_dir)
    assert cost is None
    assert known is False


def test_api_key_auth_present_cost_reader(tmp_path: Path):
    run_dir = tmp_path / "run-y"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(json.dumps({"cost_usd": 12.50}))

    cost, known = read_actual_cost_from_run_dir(run_dir)
    assert cost == 12.50
    assert known is True


def test_summary_takes_precedence_over_result_json(tmp_path: Path):
    run_dir = tmp_path / "run-z"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(json.dumps({"cost_usd": 12.50}))
    (run_dir / "result.json").write_text(json.dumps({"stats": {"cost_usd": 99.0}}))

    cost, known = read_actual_cost_from_run_dir(run_dir)
    assert cost == 12.50
    assert known is True


def test_mixed_mode_experiment_total(tmp_path: Path):
    """API-key invocation + subscription invocation + API-key invocation."""
    p = tmp_path / "budget.json"
    # Invocation 1: API-key, actual 9.5.
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    stamp_completed(path=p, run_dir="/runs/job-1", actual_usd=9.5, cost_known=True)
    # Invocation 2: subscription, cost null; estimate 10 counts.
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-2")
    stamp_completed(path=p, run_dir="/runs/job-2", actual_usd=None, cost_known=False)
    # Invocation 3: API-key, actual 11.2.
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-3")
    stamp_completed(path=p, run_dir="/runs/job-3", actual_usd=11.2, cost_known=True)

    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    # 9.5 (known) + 10.0 (subscription estimate fallback) + 11.2 (known) = 30.7
    assert current_total_usd(rt) == pytest.approx(30.7)
