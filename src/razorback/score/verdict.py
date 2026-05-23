# ABOUTME: rk score --against-constant — verdict per stratum + stratified point comparison.
# ABOUTME: Stratum CI is always null (mean-of-proportions), so the stratum verdict is a point comparison.

from __future__ import annotations

from typing import Literal, TypedDict

from razorback.runs.aggregate import DatasetStratum, StratifiedReport


class StratumView(TypedDict):
    dataset: str
    n_total: int
    n_completed: int
    n_errored: int
    n_pass: int
    pass_at_1: float | None
    wilson_ci: None
    error_reason: str | None


class StratumVerdict(TypedDict, total=False):
    verdict: Literal["matches", "above", "below"] | None
    ci: None
    side: None


class StratifiedVerdict(TypedDict):
    mean: float | None
    verdict: Literal["matches", "above", "below"] | None


class AgainstConstantReport(TypedDict):
    name: str
    value: float
    per_stratum: dict[str, StratumVerdict]
    stratified: StratifiedVerdict


def build_stratum_view(stratum: DatasetStratum) -> StratumView:
    """Project a DatasetStratum into the legacy rk score stratum surface.

    `n_completed` is the sum of `n_trials` across query cells (only completed
    trials enter cells). `n_errored` is not present in DatasetStratum (errored
    trials never land in any cell), so it surfaces as 0; the run-level
    n_errored remains the authoritative count via `stratified_n_errored`.
    `wilson_ci` is always None because mean-of-proportions across queries is
    not a binomial.
    """
    n_completed = sum(q["n_trials"] for q in stratum["queries"])
    n_pass = sum(q["n_correct"] for q in stratum["queries"])
    return StratumView(
        dataset=stratum["dataset"],
        n_total=n_completed,
        n_completed=n_completed,
        n_errored=0,
        n_pass=n_pass,
        pass_at_1=stratum["dataset_pass_at_1"],
        wilson_ci=None,
        error_reason=None,
    )


def against_constant(
    report: StratifiedReport, *, name: str, value: float
) -> AgainstConstantReport:
    """For each stratum + the stratified mean, emit a point-comparison verdict.

    The stratum CI is always null (mean-of-proportions is not binomial), so the
    stratum verdict is the same point comparison used at the run level: matches
    iff dataset_pass_at_1 == value, else above/below.
    """
    per_stratum: dict[str, StratumVerdict] = {}
    for stratum_name, stratum in report["strata"].items():
        per_stratum[stratum_name] = _stratum_verdict(stratum["dataset_pass_at_1"], value)

    stratified_mean = report["stratified_pass_at_1"]
    stratified: StratifiedVerdict = StratifiedVerdict(
        mean=stratified_mean,
        verdict=_point_verdict(stratified_mean, value),
    )

    return AgainstConstantReport(
        name=name,
        value=value,
        per_stratum=per_stratum,
        stratified=stratified,
    )


def _stratum_verdict(mean: float | None, value: float) -> StratumVerdict:
    return StratumVerdict(verdict=_point_verdict(mean, value), ci=None, side=None)


def _point_verdict(
    mean: float | None, value: float
) -> Literal["matches", "above", "below"] | None:
    if mean is None:
        return None
    if mean == value:
        return "matches"
    return "above" if mean > value else "below"
