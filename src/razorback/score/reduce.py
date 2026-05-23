# ABOUTME: rk score reducer — per-stratum Wilson CI + macro-average stratified mean.
# ABOUTME: Counting honesty: n_completed denominator; n_errored exposed; all-errored → null.

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, NotRequired, TypedDict

from razorback.diff.stats import wilson_ci
from razorback.score.load import TrialRecord


class StratumStats(TypedDict):
    dataset: NotRequired[str | None]
    query_id: NotRequired[str | int | float | bool | None]
    benchmark_kind: NotRequired[str | None]
    benchmark_task_id: NotRequired[str | int | float | bool | None]
    n_total: int
    n_completed: int
    n_errored: int
    n_pass: int
    pass_at_1: float | None
    wilson_ci: tuple[float, float] | None
    error_reason: str | None


class ScoreReport(TypedDict):
    score_version: int
    alpha: float
    strata: dict[str, StratumStats]
    stratified_pass_at_1: float | None
    stratified_n_completed: int
    stratified_n_errored: int
    error_reason: str | None


def reduce_trials(records: list[TrialRecord], *, alpha: float) -> ScoreReport:
    """Group records by stratum, compute per-stratum stats and macro-average stratified mean.

    The score denominator is `n_completed`; errored trials are exposed via `n_errored`
    but never inflate the failure count (spec §9.2 counting honesty). When a stratum
    has zero completed trials, `pass_at_1` and `wilson_ci` are None and `error_reason`
    names the dominant exception class.
    """
    by_stratum: dict[str, list[TrialRecord]] = defaultdict(list)
    for record in records:
        by_stratum[record.stratum].append(record)

    strata: dict[str, StratumStats] = {}
    for stratum_name in sorted(by_stratum.keys()):
        strata[stratum_name] = _reduce_stratum(
            by_stratum[stratum_name], alpha=alpha
        )

    per_stratum_means = [s["pass_at_1"] for s in strata.values() if s["pass_at_1"] is not None]
    if per_stratum_means:
        stratified_mean: float | None = sum(per_stratum_means) / len(per_stratum_means)
    else:
        stratified_mean = None

    n_completed_total = sum(s["n_completed"] for s in strata.values())
    n_errored_total = sum(s["n_errored"] for s in strata.values())

    top_error_reason: str | None = None
    if stratified_mean is None and records:
        top_error_reason = _dominant_error_class(records)

    return ScoreReport(
        score_version=1,
        alpha=alpha,
        strata=strata,
        stratified_pass_at_1=stratified_mean,
        stratified_n_completed=n_completed_total,
        stratified_n_errored=n_errored_total,
        error_reason=top_error_reason,
    )


def _reduce_stratum(records: list[TrialRecord], *, alpha: float) -> StratumStats:
    n_total = len(records)
    completed = [r for r in records if r.state == "completed"]
    errored = [r for r in records if r.state == "errored"]
    n_completed = len(completed)
    n_errored = len(errored)
    n_pass = sum(1 for r in completed if r.passed)

    if n_completed == 0:
        return StratumStats(
            **_common_stratum_metadata(records),
            n_total=n_total,
            n_completed=0,
            n_errored=n_errored,
            n_pass=0,
            pass_at_1=None,
            wilson_ci=None,
            error_reason=_dominant_error_class(errored),
        )

    pass_at_1 = n_pass / n_completed
    ci = wilson_ci(k=n_pass, n=n_completed, alpha=alpha)
    return StratumStats(
        **_common_stratum_metadata(records),
        n_total=n_total,
        n_completed=n_completed,
        n_errored=n_errored,
        n_pass=n_pass,
        pass_at_1=pass_at_1,
        wilson_ci=ci,
        error_reason=None,
    )


def _common_stratum_metadata(records: list[TrialRecord]) -> dict[str, Any]:
    payloads = [r.stratum_payload or {} for r in records]
    metadata: dict[str, Any] = {}
    for key in ("dataset", "query_id", "benchmark_kind", "benchmark_task_id"):
        values = {
            payload.get(key)
            for payload in payloads
            if _metadata_scalar(payload.get(key))
        }
        if len(values) == 1:
            metadata[key] = next(iter(values))
    return metadata


def _metadata_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and not isinstance(
        value, (list, dict)
    )


def _dominant_error_class(records: list[TrialRecord]) -> str | None:
    """Return the most-frequent error_class across errored records; ties broken alphabetically."""
    classes = [r.error_class for r in records if r.state == "errored" and r.error_class]
    if not classes:
        return None
    counts = Counter(classes)
    max_count = max(counts.values())
    top = sorted(name for name, count in counts.items() if count == max_count)
    return top[0]
