# ABOUTME: Phase 4a running-budget gate file I/O + decision logic.
# ABOUTME: Tracks per-invocation estimates and actuals across a multi-invocation experiment.

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from razorback.errors import ConfigInvalidError


SCHEMA_VERSION = 1


@dataclass
class Invocation:
    started_at: Optional[str]
    completed_at: Optional[str]
    estimate_usd: float
    actual_usd: Optional[float]
    run_dir: Optional[str]
    cost_known: Optional[bool]


@dataclass
class RunningTotal:
    experiment: str
    max_budget_usd: float
    invocations: list[Invocation] = field(default_factory=list)


def read_running_total(
    path: Path,
    *,
    experiment: str,
    max_budget_usd: float,
) -> RunningTotal:
    """Read the running-total JSON file. Returns an empty RunningTotal if absent.

    Raises ConfigInvalidError on schema version mismatch, experiment-name mismatch,
    or max_budget_usd mismatch (the operator pointed at the wrong file or the spec
    changed mid-experiment).
    """
    if not path.exists():
        return RunningTotal(experiment=experiment, max_budget_usd=max_budget_usd)
    body = json.loads(path.read_text())
    if body.get("version") != SCHEMA_VERSION:
        raise ConfigInvalidError(
            f"running-total file version mismatch: got {body.get('version')!r}, "
            f"expected {SCHEMA_VERSION}. File: {path}"
        )
    if body.get("experiment") != experiment:
        raise ConfigInvalidError(
            f"running-total file experiment name {body.get('experiment')!r} "
            f"does not match spec.experiment {experiment!r}. File: {path}"
        )
    if body.get("max_budget_usd") != max_budget_usd:
        raise ConfigInvalidError(
            f"running-total file max_budget_usd {body.get('max_budget_usd')} "
            f"does not match spec.experiment_meta.max_budget_usd {max_budget_usd}. "
            f"The spec's budget changed; resolve before re-running. File: {path}"
        )
    invocations = [Invocation(**inv) for inv in body.get("invocations", [])]
    return RunningTotal(
        experiment=experiment,
        max_budget_usd=max_budget_usd,
        invocations=invocations,
    )


def current_total_usd(rt: RunningTotal) -> float:
    """Sum of completed-invocation costs.

    - cost_known is True: use actual_usd (telemetry available).
    - cost_known is False: use estimate_usd (subscription-auth: telemetry null;
      the pre-launch belief is the conservative proxy).
    - cost_known is None: exclude (in-flight or crashed before completion).
    """
    total = 0.0
    for inv in rt.invocations:
        if inv.cost_known is True:
            total += inv.actual_usd or 0.0
        elif inv.cost_known is False:
            total += inv.estimate_usd
        # cost_known is None: skip
    return total
