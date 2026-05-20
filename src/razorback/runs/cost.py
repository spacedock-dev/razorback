# ABOUTME: Phase 4a — cost-summary primitives for `rk runs cost`.
# ABOUTME: Precedence: summary.json → result.json.stats → per-trial agent_result. JSON shape semver-stable per §3.3.

import json
from pathlib import Path

from razorback.runs.inspect import list_run_dirs


# Cross-plan contract: read_run_cost shares its first two precedence levels with
# phase4a-rk-run-budget-gate.read_actual_cost_from_run_dir (summary.json, then
# result.json.stats.cost_usd). This module extends with a third per-trial fallback
# observed in the real subscription-auth run-dir; the budget-gate reader stops at
# the second level. If either reader changes the shared levels, the other tracks.
# See docs/razorback-implementation/plans/phase4a-rk-runs-cost.md.


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def read_run_cost(run_dir: Path) -> tuple[float | None, bool, str | None]:
    """Return (cost_usd, cost_known, cost_source) for one run-dir.

    Precedence walk:
      1. summary.json["cost_usd"] — present non-null wins; present null is authoritative.
      2. result.json["stats"]["cost_usd"] — same shape.
      3. per-trial */result.json step_results[].agent_result.cost_usd — sum non-null.
      4. Nothing found: (None, False, None).

    Raises FileNotFoundError if run_dir itself does not exist.
    """
    if not run_dir.exists():
        raise FileNotFoundError(f"run-dir does not exist: {run_dir}")

    summary = _read_json(run_dir / "summary.json")
    if summary is not None and "cost_usd" in summary:
        value = summary["cost_usd"]
        if value is None:
            return (None, False, "summary")
        return (float(value), True, "summary")

    result = _read_json(run_dir / "result.json")
    if result is not None:
        stats = result.get("stats")
        if isinstance(stats, dict) and "cost_usd" in stats:
            value = stats["cost_usd"]
            if value is None:
                return (None, False, "result_stats")
            return (float(value), True, "result_stats")

    trial_costs: list[float] = []
    any_trial_seen = False
    for child in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        trial_result = _read_json(child / "result.json")
        if trial_result is None:
            continue
        steps = trial_result.get("step_results")
        if not isinstance(steps, list):
            continue
        any_trial_seen = True
        for step in steps:
            agent = step.get("agent_result") if isinstance(step, dict) else None
            if not isinstance(agent, dict):
                continue
            value = agent.get("cost_usd")
            if value is not None:
                trial_costs.append(float(value))

    if any_trial_seen:
        if trial_costs:
            return (sum(trial_costs), True, "result_step_agent")
        return (None, False, "result_step_agent")

    return (None, False, None)
