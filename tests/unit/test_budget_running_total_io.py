# ABOUTME: AC-1 + AC-6: budget-gate running-total file reader and shape contract.
# ABOUTME: Exercises subscription-auth cost_known=false handling per Phase 0 baseline finding.

import json
from pathlib import Path

import pytest

from razorback.budget import (
    RunningTotal,
    read_running_total,
    current_total_usd,
)
from razorback.errors import ConfigInvalidError


def _write(path: Path, body: dict) -> None:
    path.write_text(json.dumps(body))


def test_read_missing_file_returns_empty_running_total(tmp_path: Path):
    rt = read_running_total(tmp_path / "budget.json", experiment="exp-1", max_budget_usd=100.0)
    assert rt.invocations == []
    assert rt.experiment == "exp-1"
    assert rt.max_budget_usd == 100.0


def test_read_existing_file_parses_invocations(tmp_path: Path):
    p = tmp_path / "budget.json"
    _write(p, {
        "version": 1,
        "experiment": "exp-1",
        "max_budget_usd": 100.0,
        "invocations": [
            {
                "started_at": "2026-05-20T12:00:00Z",
                "completed_at": "2026-05-20T12:30:00Z",
                "estimate_usd": 10.0,
                "actual_usd": 9.5,
                "run_dir": "/runs/job-1",
                "cost_known": True,
            },
        ],
    })
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert len(rt.invocations) == 1
    assert rt.invocations[0].actual_usd == 9.5
    assert rt.invocations[0].cost_known is True


def test_current_total_excludes_in_flight_and_crashed(tmp_path: Path):
    p = tmp_path / "budget.json"
    _write(p, {
        "version": 1,
        "experiment": "exp-1",
        "max_budget_usd": 100.0,
        "invocations": [
            {"estimate_usd": 10.0, "actual_usd": 9.5, "cost_known": True,
             "started_at": "...", "completed_at": "...", "run_dir": "..."},
            # Subscription-auth: cost_known=False; estimate counts toward total.
            {"estimate_usd": 10.0, "actual_usd": None, "cost_known": False,
             "started_at": "...", "completed_at": "...", "run_dir": "..."},
            # In-flight (or crashed): cost_known=None; excluded from total.
            {"estimate_usd": 10.0, "actual_usd": None, "cost_known": None,
             "started_at": "...", "completed_at": None, "run_dir": None},
        ],
    })
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    # 9.5 (known actual) + 10.0 (subscription-auth estimate fallback)
    # = 19.5. The in-flight invocation contributes 0.
    assert current_total_usd(rt) == pytest.approx(19.5)


def test_experiment_name_mismatch_raises_config_invalid(tmp_path: Path):
    p = tmp_path / "budget.json"
    _write(p, {
        "version": 1, "experiment": "wrong", "max_budget_usd": 100.0, "invocations": []
    })
    with pytest.raises(ConfigInvalidError) as exc_info:
        read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert "wrong" in str(exc_info.value)
    assert "exp-1" in str(exc_info.value)


def test_budget_mismatch_raises_config_invalid(tmp_path: Path):
    p = tmp_path / "budget.json"
    _write(p, {
        "version": 1, "experiment": "exp-1", "max_budget_usd": 100.0, "invocations": []
    })
    with pytest.raises(ConfigInvalidError):
        read_running_total(p, experiment="exp-1", max_budget_usd=200.0)


def test_unknown_version_raises_config_invalid(tmp_path: Path):
    p = tmp_path / "budget.json"
    _write(p, {"version": 99, "experiment": "exp-1", "max_budget_usd": 100.0, "invocations": []})
    with pytest.raises(ConfigInvalidError):
        read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
