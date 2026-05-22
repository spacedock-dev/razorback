# ABOUTME: rk score renderers — JSON (canonical) + markdown (human-readable).
# ABOUTME: AC-7 + AC-8 prep.

from __future__ import annotations

import json

from razorback.score.reduce import ScoreReport, StratumStats
from razorback.score.render import render_json, render_markdown
from razorback.score.verdict import AgainstConstantReport, against_constant


def _stratum(*, lo: float, hi: float, n_completed: int = 10, n_pass: int = 5) -> StratumStats:
    return StratumStats(
        n_total=n_completed,
        n_completed=n_completed,
        n_errored=0,
        n_pass=n_pass,
        pass_at_1=n_pass / n_completed,
        wilson_ci=(lo, hi),
        error_reason=None,
    )


def _report(strata: dict[str, StratumStats], *, mean: float = 0.5) -> ScoreReport:
    return ScoreReport(
        score_version=1,
        alpha=0.05,
        strata=strata,
        stratified_pass_at_1=mean,
        stratified_n_completed=sum(s["n_completed"] for s in strata.values()),
        stratified_n_errored=sum(s["n_errored"] for s in strata.values()),
        error_reason=None,
    )


def test_json_keys_present_and_stable() -> None:
    report = _report({"A": _stratum(lo=0.30, hi=0.70), "B": _stratum(lo=0.20, hi=0.80)})
    output = render_json(report, None)
    parsed = json.loads(output)
    assert set(parsed.keys()) >= {
        "score_version",
        "alpha",
        "strata",
        "stratified_pass_at_1",
        "stratified_n_completed",
        "stratified_n_errored",
        "error_reason",
    }
    assert set(parsed["strata"]["A"].keys()) >= {
        "n_total",
        "n_completed",
        "n_errored",
        "n_pass",
        "pass_at_1",
        "wilson_ci",
        "error_reason",
    }


def test_json_includes_against_constant_when_present() -> None:
    report = _report({"A": _stratum(lo=0.30, hi=0.70)})
    verdict = against_constant(report, name="paper", value=0.577)
    output = render_json(report, verdict)
    parsed = json.loads(output)
    assert "against_constant" in parsed
    assert parsed["against_constant"]["name"] == "paper"
    assert parsed["against_constant"]["value"] == 0.577


def test_json_omits_against_constant_when_none() -> None:
    report = _report({"A": _stratum(lo=0.30, hi=0.70)})
    parsed = json.loads(render_json(report, None))
    assert "against_constant" not in parsed


def test_markdown_has_one_row_per_stratum_plus_stratified() -> None:
    report = _report({"A": _stratum(lo=0.30, hi=0.70), "B": _stratum(lo=0.20, hi=0.80)})
    output = render_markdown(report, None)
    assert "| stratum" in output
    assert "| A " in output or "| A|" in output or "| A\t" in output or "A " in output
    assert "B" in output
    assert "stratified" in output.lower()


def test_markdown_carries_verdict_column_when_against_constant_set() -> None:
    report = _report({"A": _stratum(lo=0.30, hi=0.70)})
    verdict = against_constant(report, name="paper", value=0.577)
    output = render_markdown(report, verdict)
    assert "paper=0.577" in output
    assert "matches" in output


def test_markdown_shows_outside_ci_when_value_outside() -> None:
    report = _report({"A": _stratum(lo=0.30, hi=0.40)})
    verdict = against_constant(report, name="paper", value=0.90)
    output = render_markdown(report, verdict)
    assert "outside-CI" in output


def test_json_canonical_shape_with_tuple_serialized_as_list() -> None:
    """wilson_ci tuples must serialize to JSON lists, not tuples."""
    report = _report({"A": _stratum(lo=0.30, hi=0.70)})
    parsed = json.loads(render_json(report, None))
    assert parsed["strata"]["A"]["wilson_ci"] == [0.30, 0.70]


def test_json_includes_task_view_identity_metadata() -> None:
    report = _report(
        {
            "ade-bench": StratumStats(
                dataset="ade-bench",
                query_id="adebench-fixture-001",
                benchmark_kind="ade-bench",
                benchmark_task_id="adebench-fixture-001",
                n_total=1,
                n_completed=1,
                n_errored=0,
                n_pass=1,
                pass_at_1=1.0,
                wilson_ci=(0.21, 1.0),
                error_reason=None,
            )
        },
        mean=1.0,
    )

    parsed = json.loads(render_json(report, None))

    assert parsed["strata"]["ade-bench"]["dataset"] == "ade-bench"
    assert parsed["strata"]["ade-bench"]["query_id"] == "adebench-fixture-001"
    assert parsed["strata"]["ade-bench"]["benchmark_kind"] == "ade-bench"
    assert (
        parsed["strata"]["ade-bench"]["benchmark_task_id"]
        == "adebench-fixture-001"
    )
