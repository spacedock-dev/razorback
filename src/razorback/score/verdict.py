# ABOUTME: rk score --against-constant — inside/outside-CI verdict per stratum + stratified point.
# ABOUTME: Spec §3.2 + §8.3a paper-reproduction line.

from __future__ import annotations

from typing import Literal, TypedDict

from razorback.score.reduce import ScoreReport


class StratumVerdict(TypedDict, total=False):
    verdict: Literal["matches", "outside-CI"] | None
    ci: tuple[float, float] | None
    side: Literal["above", "below"] | None


class StratifiedVerdict(TypedDict):
    mean: float | None
    verdict: Literal["matches", "above", "below"] | None


class AgainstConstantReport(TypedDict):
    name: str
    value: float
    per_stratum: dict[str, StratumVerdict]
    stratified: StratifiedVerdict


def against_constant(
    report: ScoreReport, *, name: str, value: float
) -> AgainstConstantReport:
    """For each stratum + the stratified mean, emit matches / outside-CI verdict.

    A stratum verdict is "matches" when ci_lo <= value <= ci_hi, else "outside-CI"
    with a side ("above" if value > ci_hi; "below" if value < ci_lo). Strata with
    null pass_at_1 (all-errored) get verdict=None.

    The stratified row is a point comparison: no run-level CI lives here (that's
    `rk diff`'s territory); verdict is "matches" iff mean == value, "above" if
    mean > value, "below" if mean < value, None if mean is null.
    """
    per_stratum: dict[str, StratumVerdict] = {}
    for stratum_name, stats in report["strata"].items():
        per_stratum[stratum_name] = _stratum_verdict(stats["wilson_ci"], value)

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


def _stratum_verdict(ci: tuple[float, float] | None, value: float) -> StratumVerdict:
    if ci is None:
        return StratumVerdict(verdict=None, ci=None, side=None)
    lo, hi = ci
    if lo <= value <= hi:
        return StratumVerdict(verdict="matches", ci=(lo, hi), side=None)
    side: Literal["above", "below"] = "above" if value > hi else "below"
    return StratumVerdict(verdict="outside-CI", ci=(lo, hi), side=side)


def _point_verdict(
    mean: float | None, value: float
) -> Literal["matches", "above", "below"] | None:
    if mean is None:
        return None
    if mean == value:
        return "matches"
    return "above" if mean > value else "below"
