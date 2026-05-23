# ABOUTME: rk score --against-constant — point-comparison verdict per stratum + stratified.
# ABOUTME: Stratum CI is null (mean-of-proportions); both stratum and stratified verdicts are point.

from __future__ import annotations

from razorback.runs.aggregate import DatasetStratum, QueryCell, StratifiedReport
from razorback.score.verdict import against_constant


def _cell(query_id: int, *, n_trials: int, n_correct: int) -> QueryCell:
    return QueryCell(
        query_id=query_id,
        n_trials=n_trials,
        n_correct=n_correct,
        pass_at_1=(n_correct / n_trials) if n_trials else 0.0,
        wilson_ci=None,
    )


def _stratum(name: str, *, dataset_mean: float) -> DatasetStratum:
    # Encode the dataset mean via a single all-pass/all-fail cell or a two-cell
    # average — for verdict tests the cell shape doesn't matter beyond the mean.
    if dataset_mean == 0.5:
        queries = [_cell(1, n_trials=2, n_correct=1)]
    elif dataset_mean in (0.0, 1.0):
        queries = [_cell(1, n_trials=1, n_correct=int(dataset_mean))]
    else:
        queries = [_cell(1, n_trials=1000, n_correct=int(dataset_mean * 1000))]
    return DatasetStratum(
        dataset=name,
        n_queries=1,
        dataset_pass_at_1=dataset_mean,
        queries=queries,
        wilson_ci=None,
    )


def _report(strata: dict[str, DatasetStratum], *, mean: float | None = 0.5) -> StratifiedReport:
    n_completed = sum(c["n_trials"] for s in strata.values() for c in s["queries"])
    return StratifiedReport(
        score_version=1,
        alpha=0.05,
        strata=strata,
        stratified_pass_at_1=mean,
        n_trials_total=n_completed,
        n_trials_completed=n_completed,
        n_trials_errored=0,
        error_reason=None,
    )


def test_stratum_matches_when_mean_equals_value() -> None:
    report = _report({"A": _stratum("A", dataset_mean=0.577)})
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["per_stratum"]["A"]["verdict"] == "matches"
    assert verdict["per_stratum"]["A"]["ci"] is None
    assert verdict["per_stratum"]["A"]["side"] is None


def test_stratum_above_when_mean_above_value() -> None:
    report = _report({"A": _stratum("A", dataset_mean=0.70)})
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["per_stratum"]["A"]["verdict"] == "above"


def test_stratum_below_when_mean_below_value() -> None:
    report = _report({"A": _stratum("A", dataset_mean=0.30)})
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["per_stratum"]["A"]["verdict"] == "below"


def test_null_stratum_pass_at_1_yields_null_verdict() -> None:
    null_stratum = DatasetStratum(
        dataset="A",
        n_queries=0,
        dataset_pass_at_1=None,  # type: ignore[typeddict-item]
        queries=[],
        wilson_ci=None,
    )
    report = _report({"A": null_stratum}, mean=None)
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["per_stratum"]["A"]["verdict"] is None


def test_stratified_row_present_with_point_comparison() -> None:
    report = _report({"A": _stratum("A", dataset_mean=0.40)}, mean=0.40)
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["stratified"]["mean"] == 0.40
    assert verdict["stratified"]["verdict"] == "below"


def test_stratified_above_when_mean_above_value() -> None:
    report = _report({"A": _stratum("A", dataset_mean=0.70)}, mean=0.70)
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["stratified"]["verdict"] == "above"


def test_stratified_matches_when_mean_equals_value() -> None:
    report = _report({"A": _stratum("A", dataset_mean=0.577)}, mean=0.577)
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["stratified"]["verdict"] == "matches"


def test_name_and_value_echoed_into_report() -> None:
    report = _report({"A": _stratum("A", dataset_mean=0.5)})
    verdict = against_constant(report, name="paper", value=0.577)
    assert verdict["name"] == "paper"
    assert verdict["value"] == 0.577
