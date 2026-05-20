# ABOUTME: Phase 4a running-budget gate file I/O + decision logic.
# ABOUTME: Tracks per-invocation estimates and actuals across a multi-invocation experiment.

import datetime as _dt
import fcntl
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from razorback.errors import BudgetExceededError, ConfigInvalidError


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


def read_estimate_from_spec(spec) -> float:
    """Return the spec's pre-launch cost estimate.

    AC-3: the source is the frozen spec's experiment_meta.estimated_cost_usd
    field (populated by `rk freeze` per PKG-8). Missing field is a hard error:
    the operator must re-freeze with cost-estimation logic before the gate can
    run.
    """
    meta = getattr(spec, "experiment_meta", None)
    estimate = getattr(meta, "estimated_cost_usd", None) if meta else None
    if estimate is None:
        raise ConfigInvalidError(
            "spec is missing experiment_meta.estimated_cost_usd; "
            "re-freeze with `rk freeze` (PKG-8 adds cost-estimation) before "
            "passing --max-budget-usd-running."
        )
    return float(estimate)


def decide_budget(rt: RunningTotal, *, estimate_usd: float) -> None:
    """Raise BudgetExceededError if running_total + estimate would exceed the cap.

    The condition is strictly greater; equality at the cap proceeds.
    Per AC-4 the error message names budget, running total, and estimate.
    """
    used = current_total_usd(rt)
    projected = used + estimate_usd
    if projected > rt.max_budget_usd:
        raise BudgetExceededError(
            f"budget exceeded: experiment.max_budget_usd={rt.max_budget_usd}, "
            f"running_total_usd={used:.4f}, this_invocation_estimate_usd={estimate_usd:.4f}, "
            f"projected_total_usd={projected:.4f}"
        )


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, body: dict) -> None:
    """Write JSON to path via tempfile+rename, fsync'd."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".budget-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(body, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _acquire_lock(path: Path) -> int:
    """Open + flock the lockfile alongside the running-total path. Returns lock fd."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    return lock_fd


def _release_lock(lock_fd: int) -> None:
    fcntl.flock(lock_fd, fcntl.LOCK_UN)
    os.close(lock_fd)


def _read_body(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def stamp_started(
    *,
    path: Path,
    experiment: str,
    max_budget_usd: float,
    estimate_usd: float,
    run_dir: str,
) -> None:
    """Pre-launch: append an in-flight invocation record under exclusive lock."""
    lock_fd = _acquire_lock(path)
    try:
        body = _read_body(path)
        if not body:
            body = {
                "version": SCHEMA_VERSION,
                "experiment": experiment,
                "max_budget_usd": max_budget_usd,
                "invocations": [],
            }
        else:
            if body.get("version") != SCHEMA_VERSION:
                raise ConfigInvalidError(
                    f"running-total file version mismatch: got {body.get('version')!r}, "
                    f"expected {SCHEMA_VERSION}. File: {path}"
                )
            if body.get("experiment") != experiment:
                raise ConfigInvalidError(
                    f"running-total file experiment mismatch: "
                    f"{body.get('experiment')!r} vs {experiment!r}"
                )
            if body.get("max_budget_usd") != max_budget_usd:
                raise ConfigInvalidError(
                    f"running-total file budget mismatch: "
                    f"{body.get('max_budget_usd')} vs {max_budget_usd}"
                )
        body["invocations"].append({
            "started_at": _now_iso(),
            "completed_at": None,
            "estimate_usd": estimate_usd,
            "actual_usd": None,
            "run_dir": run_dir,
            "cost_known": None,
        })
        _atomic_write(path, body)
    finally:
        _release_lock(lock_fd)


def stamp_completed(
    *,
    path: Path,
    run_dir: str,
    actual_usd: Optional[float],
    cost_known: bool,
) -> None:
    """Post-completion: locate the in-flight record by run_dir and update it."""
    lock_fd = _acquire_lock(path)
    try:
        body = _read_body(path)
        if not body:
            raise ValueError(
                f"stamp_completed called against missing running-total file: {path}"
            )
        invs = body.get("invocations", [])
        matched = None
        for inv in invs:
            if inv["run_dir"] == run_dir and inv["cost_known"] is None:
                matched = inv
                break
        if matched is None:
            raise ValueError(
                f"no in-flight invocation found for run_dir={run_dir!r} in {path}"
            )
        matched["completed_at"] = _now_iso()
        matched["actual_usd"] = actual_usd
        matched["cost_known"] = cost_known
        _atomic_write(path, body)
    finally:
        _release_lock(lock_fd)


def read_actual_cost_from_run_dir(run_dir: Path) -> tuple[Optional[float], bool]:
    """Read the actual cost from a harbor-produced run-dir.

    Returns (cost_usd, cost_known). cost_known is False when the agent runtime
    emitted null cost (subscription-auth telemetry gap per Phase 0 baseline).
    Source precedence: `summary.json` first (razorback's writer), then harbor's
    `result.json` `stats.cost_usd`. Shared convention with `rk runs cost`
    (phase4a-rk-runs-cost AC-3).
    """
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        body = json.loads(summary_path.read_text())
        if "cost_usd" in body:
            v = body["cost_usd"]
            return (float(v) if v is not None else None, v is not None)
    result_path = run_dir / "result.json"
    if result_path.exists():
        body = json.loads(result_path.read_text())
        stats = body.get("stats", {}) or {}
        if "cost_usd" in stats:
            v = stats["cost_usd"]
            return (float(v) if v is not None else None, v is not None)
    # No cost field at all: distinct from "field present but null".
    return (None, False)
