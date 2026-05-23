# ABOUTME: rk score renderers — JSON (canonical) + markdown (human-readable).
# ABOUTME: Consumes StratifiedReport from runs/aggregate.py.

from __future__ import annotations

import json
from typing import Any

from razorback.diff.stats import wilson_ci
from razorback.runs.aggregate import DatasetStratum, QueryCell, StratifiedReport
from razorback.score.render import render_json, render_markdown
from razorback.score.verdict import against_constant


def _cell(query_id: int | str, *, n_trials: int, n_correct: int, alpha: float = 0.05) -> QueryCell:
    return QueryCell(
        query_id=query_id,
        n_trials=n_trials,
        n_correct=n_correct,
        pass_at_1=(n_correct / n_trials) if n_trials else 0.0,
        wilson_ci=wilson_ci(k=n_correct, n=n_trials, alpha=alpha) if n_trials else None,
    )


def _stratum(dataset: str, cells: list[QueryCell]) -> DatasetStratum:
    return DatasetStratum(
        dataset=dataset,
        n_queries=len(cells),
        dataset_pass_at_1=sum(c["pass_at_1"] for c in cells) / len(cells) if cells else 0.0,
        queries=cells,
        wilson_ci=None,
    )


def _report(strata: dict[str, DatasetStratum], *, mean: float = 0.5) -> StratifiedReport:
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


def test_json_keys_present_and_stable() -> None:
    report = _report(
        {
            "A": _stratum("A", [_cell(1, n_trials=10, n_correct=5)]),
            "B": _stratum("B", [_cell(1, n_trials=10, n_correct=5)]),
        }
    )
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
        "queries",
    }


def test_json_per_query_cells_carry_wilson_ci() -> None:
    """AC-3 — per-query Wilson cells ride in the JSON for analyst use."""
    report = _report({"A": _stratum("A", [_cell(1, n_trials=5, n_correct=3)])})
    parsed = json.loads(render_json(report, None))
    [cell] = parsed["strata"]["A"]["queries"]
    assert cell["query_id"] == 1
    assert cell["n_trials"] == 5
    assert cell["n_correct"] == 3
    assert cell["pass_at_1"] == 3 / 5
    assert cell["wilson_ci"] is not None
    assert len(cell["wilson_ci"]) == 2


def test_json_stratum_wilson_ci_is_null() -> None:
    """AC-3 — mean-of-proportions across queries is not binomial; stratum CI is null."""
    report = _report({"A": _stratum("A", [_cell(1, n_trials=10, n_correct=5)])})
    parsed = json.loads(render_json(report, None))
    assert parsed["strata"]["A"]["wilson_ci"] is None


def test_json_includes_against_constant_when_present() -> None:
    report = _report({"A": _stratum("A", [_cell(1, n_trials=10, n_correct=5)])})
    verdict = against_constant(report, name="paper", value=0.577)
    output = render_json(report, verdict)
    parsed = json.loads(output)
    assert "against_constant" in parsed
    assert parsed["against_constant"]["name"] == "paper"
    assert parsed["against_constant"]["value"] == 0.577


def test_json_omits_against_constant_when_none() -> None:
    report = _report({"A": _stratum("A", [_cell(1, n_trials=10, n_correct=5)])})
    parsed = json.loads(render_json(report, None))
    assert "against_constant" not in parsed


def test_markdown_has_one_row_per_stratum_plus_stratified() -> None:
    report = _report(
        {
            "A": _stratum("A", [_cell(1, n_trials=10, n_correct=5)]),
            "B": _stratum("B", [_cell(1, n_trials=10, n_correct=5)]),
        }
    )
    output = render_markdown(report, None)
    assert "| stratum" in output
    assert "A" in output
    assert "B" in output
    assert "stratified" in output.lower()


def test_markdown_carries_verdict_column_when_against_constant_set() -> None:
    report = _report({"A": _stratum("A", [_cell(1, n_trials=10, n_correct=5)])}, mean=0.577)
    verdict = against_constant(report, name="paper", value=0.577)
    output = render_markdown(report, verdict)
    assert "paper=0.577" in output
    assert "matches" in output


def test_json_cell_wilson_ci_serialized_as_list() -> None:
    """wilson_ci tuples must serialize to JSON lists, not tuples."""
    report = _report({"A": _stratum("A", [_cell(1, n_trials=10, n_correct=5)])})
    parsed = json.loads(render_json(report, None))
    cell = parsed["strata"]["A"]["queries"][0]
    assert isinstance(cell["wilson_ci"], list)
    assert len(cell["wilson_ci"]) == 2


def test_json_includes_dataset_identity_field() -> None:
    """The stratum's `dataset` slug surfaces in JSON for analyst tools."""
    report = _report({"ade-bench": _stratum("ade-bench", [_cell("adebench-fixture-001", n_trials=1, n_correct=1)])}, mean=1.0)
    parsed = json.loads(render_json(report, None))
    assert parsed["strata"]["ade-bench"]["dataset"] == "ade-bench"
    cell = parsed["strata"]["ade-bench"]["queries"][0]
    assert cell["query_id"] == "adebench-fixture-001"
