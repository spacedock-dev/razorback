# ABOUTME: AC-1 + AC-4: budget-gate pre-launch decision logic.

import pytest

from razorback.budget import RunningTotal, Invocation, decide_budget
from razorback.errors import BudgetExceededError, ExitCode


def test_decide_allows_when_estimate_fits():
    rt = RunningTotal(experiment="exp-1", max_budget_usd=100.0, invocations=[
        Invocation(started_at="", completed_at="", estimate_usd=20.0,
                   actual_usd=20.0, run_dir="", cost_known=True),
    ])
    # 20 (used) + 30 (estimate) = 50, well under 100. No raise.
    decide_budget(rt, estimate_usd=30.0)


def test_decide_refuses_when_estimate_pushes_over():
    rt = RunningTotal(experiment="exp-1", max_budget_usd=100.0, invocations=[
        Invocation(started_at="", completed_at="", estimate_usd=80.0,
                   actual_usd=80.0, run_dir="", cost_known=True),
    ])
    with pytest.raises(BudgetExceededError) as exc_info:
        decide_budget(rt, estimate_usd=30.0)
    assert exc_info.value.exit_code == ExitCode.BUDGET_EXCEEDED == 22
    msg = str(exc_info.value)
    # AC-4: message names budget, running total, and estimate.
    assert "100" in msg
    assert "80" in msg
    assert "30" in msg


def test_decide_at_exact_boundary_proceeds():
    rt = RunningTotal(experiment="exp-1", max_budget_usd=100.0, invocations=[
        Invocation(started_at="", completed_at="", estimate_usd=70.0,
                   actual_usd=70.0, run_dir="", cost_known=True),
    ])
    # 70 + 30 = 100, exactly at budget. The condition is "would exceed",
    # so equality proceeds; only strictly greater refuses.
    decide_budget(rt, estimate_usd=30.0)


def test_decide_with_subscription_auth_estimates_counted():
    # cost_known=False invocations contribute their estimate.
    rt = RunningTotal(experiment="exp-1", max_budget_usd=100.0, invocations=[
        Invocation(started_at="", completed_at="", estimate_usd=80.0,
                   actual_usd=None, run_dir="", cost_known=False),
    ])
    with pytest.raises(BudgetExceededError):
        decide_budget(rt, estimate_usd=30.0)
