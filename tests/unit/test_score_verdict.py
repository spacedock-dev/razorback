# ABOUTME: rk score --against-constant — matches / outside-CI verdict per stratum.
# ABOUTME: AC-4.

from __future__ import annotations

from razorback.score.reduce import ScoreReport, StratumStats
from razorback.score.verdict import against_constant


def _stratum(*, lo: float, hi: float, mean: float = 0.5) -> StratumStats:
    return StratumStats(
        n_total=10,
        n_completed=10,
        n_errored=0,
        n_pass=int(mean * 10),
        pass_at_1=mean,
        wilson_ci=(lo, hi),
        error_reason=None,
    )


def _report(strata: dict[str, StratumStats], *, mean: float | None = 0.5) -> ScoreReport:
    return ScoreReport(
        score_version=1,
        alpha=0.05,
        strata=strata,
        stratified_pass_at_1=mean,
        stratified_n_completed=sum(s["n_completed"] for s in strata.values()),
        stratified_n_errored=sum(s["n_errored"] for s in strata.values()),
        error_reason=None,
    )


def test_value_inside_ci_yields_matches() -> None:
    report = _report({"A": _stratum(lo=0.50, hi=0.65)})
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["per_stratum"]["A"]["verdict"] == "matches"
    assert verdict["per_stratum"]["A"]["ci"] == (0.50, 0.65)


def test_value_above_ci_yields_outside_ci_above() -> None:
    report = _report({"A": _stratum(lo=0.50, hi=0.65)})
    verdict = against_constant(report, name="paper", value=0.70)
    assert verdict["per_stratum"]["A"]["verdict"] == "outside-CI"
    assert verdict["per_stratum"]["A"]["side"] == "above"


def test_value_below_ci_yields_outside_ci_below() -> None:
    report = _report({"A": _stratum(lo=0.50, hi=0.65)})
    verdict = against_constant(report, name="paper", value=0.30)
    assert verdict["per_stratum"]["A"]["verdict"] == "outside-CI"
    assert verdict["per_stratum"]["A"]["side"] == "below"


def test_null_score_stratum_yields_null_verdict() -> None:
    null_stratum = StratumStats(
        n_total=3, n_completed=0, n_errored=3, n_pass=0,
        pass_at_1=None, wilson_ci=None, error_reason="SubprocessError",
    )
    report = _report({"A": null_stratum}, mean=None)
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["per_stratum"]["A"]["verdict"] is None


def test_stratified_row_present_with_point_comparison() -> None:
    report = _report({"A": _stratum(lo=0.50, hi=0.65)}, mean=0.4)
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["stratified"]["mean"] == 0.4
    assert verdict["stratified"]["verdict"] == "below"


def test_stratified_above_when_mean_above_value() -> None:
    report = _report({"A": _stratum(lo=0.50, hi=0.65)}, mean=0.7)
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["stratified"]["verdict"] == "above"


def test_stratified_matches_when_mean_equals_value() -> None:
    report = _report({"A": _stratum(lo=0.50, hi=0.65)}, mean=0.577)
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["stratified"]["verdict"] == "matches"


def test_name_and_value_echoed_into_report() -> None:
    report = _report({"A": _stratum(lo=0.50, hi=0.65)})
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["name"] == "paper"
    assert verdict["value"] == 0.577
