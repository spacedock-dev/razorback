# ABOUTME: rk score reducer — per-stratum Wilson CI + macro-average stratified mean.
# ABOUTME: AC-1 + AC-2 + AC-3 + AC-6 — counting honesty pinned by errored-vs-completed denominator.

from __future__ import annotations

import pytest

from razorback.score.load import TrialRecord
from razorback.score.reduce import reduce_trials


def _completed(name: str, stratum: str, passed: bool) -> TrialRecord:
    return TrialRecord(
        trial_name=name,
        stratum=stratum,
        state="completed",
        passed=passed,
        reward=1.0 if passed else 0.0,
        error_class=None,
    )


def _errored(name: str, stratum: str, error_class: str = "SubprocessError") -> TrialRecord:
    return TrialRecord(
        trial_name=name,
        stratum=stratum,
        state="errored",
        passed=None,
        reward=None,
        error_class=error_class,
    )


# AC-2: Wilson CI literature reference values.


def test_wilson_ci_n_20_k_10_alpha_05_matches_literature() -> None:
    """n=20, k=10, alpha=0.05 → Wilson CI = [0.299, 0.701] (Newcombe 1998 Table 1)."""
    records = [_completed(f"t{i}", "A", i < 10) for i in range(20)]
    report = reduce_trials(records, alpha=0.05)
    lo, hi = report["strata"]["A"]["wilson_ci"]
    assert lo == pytest.approx(0.299, abs=1e-3)
    assert hi == pytest.approx(0.701, abs=1e-3)


def test_alpha_10_half_width_shrinks_vs_alpha_05() -> None:
    """z=1.645 (α=0.10) narrows the interval vs z=1.96 (α=0.05)."""
    records = [_completed(f"t{i}", "A", i < 10) for i in range(20)]
    report_05 = reduce_trials(records, alpha=0.05)
    report_10 = reduce_trials(records, alpha=0.10)
    lo05, hi05 = report_05["strata"]["A"]["wilson_ci"]
    lo10, hi10 = report_10["strata"]["A"]["wilson_ci"]
    half_05 = (hi05 - lo05) / 2
    half_10 = (hi10 - lo10) / 2
    assert half_10 < half_05 * 0.9


# AC-1: macro-average stratified mean.


def test_stratified_mean_is_macro_average() -> None:
    """A:0.6 (6/10), B:0.4 (4/10), C:0.2 (2/10) → stratified = (0.6 + 0.4 + 0.2) / 3 = 0.4."""
    records: list[TrialRecord] = []
    for i in range(10):
        records.append(_completed(f"A{i}", "A", i < 6))
    for i in range(10):
        records.append(_completed(f"B{i}", "B", i < 4))
    for i in range(10):
        records.append(_completed(f"C{i}", "C", i < 2))
    report = reduce_trials(records, alpha=0.05)
    assert report["strata"]["A"]["pass_at_1"] == pytest.approx(0.6)
    assert report["strata"]["B"]["pass_at_1"] == pytest.approx(0.4)
    assert report["strata"]["C"]["pass_at_1"] == pytest.approx(0.2)
    assert report["stratified_pass_at_1"] == pytest.approx(0.4)


# AC-3: counting honesty.


def test_denominator_is_n_completed_not_n_total() -> None:
    """1 pass + 1 fail + 1 errored → pass@1 = 1/2 (NOT 1/3)."""
    records = [
        _completed("p", "A", True),
        _completed("f", "A", False),
        _errored("e", "A"),
    ]
    report = reduce_trials(records, alpha=0.05)
    stratum = report["strata"]["A"]
    assert stratum["n_total"] == 3
    assert stratum["n_completed"] == 2
    assert stratum["n_errored"] == 1
    assert stratum["n_pass"] == 1
    assert stratum["pass_at_1"] == pytest.approx(0.5)


# Run-level rollups.


def test_run_level_counts_aggregate_across_strata() -> None:
    records = [
        _completed("p1", "A", True),
        _completed("f1", "A", False),
        _errored("e1", "A"),
        _completed("p2", "B", True),
    ]
    report = reduce_trials(records, alpha=0.05)
    assert report["stratified_n_completed"] == 3
    assert report["stratified_n_errored"] == 1


def test_score_version_is_one() -> None:
    report = reduce_trials([_completed("p", "A", True)], alpha=0.05)
    assert report["score_version"] == 1


def test_alpha_echoed_into_report() -> None:
    report = reduce_trials([_completed("p", "A", True)], alpha=0.10)
    assert report["alpha"] == 0.10


def test_empty_records_returns_empty_strata() -> None:
    report = reduce_trials([], alpha=0.05)
    assert report["strata"] == {}
    assert report["stratified_pass_at_1"] is None
