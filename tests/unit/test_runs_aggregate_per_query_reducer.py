# ABOUTME: AC-1/AC-2/AC-3 — canonical reducer consumes reward_per_query.json for DAB batch trials.
# ABOUTME: Run-dir-driven; exercises read_trial_outcomes + reduce_per_query_stratified end-to-end.

from __future__ import annotations

import json
import shutil
from pathlib import Path

from razorback.runs.aggregate import (
    aggregate_summary,
    read_trial_outcomes,
    reduce_per_query_stratified,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "score"
DAB_BATCH_FIXTURE = FIXTURE_ROOT / "dab_batch_run_dir"
DAB_PER_QUERY_FIXTURE = FIXTURE_ROOT / "mixed_trial_run_dir"
ADE_FIXTURE = FIXTURE_ROOT / "ade_bench_run_dir"


def _copy_trial_subdirs(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        if child.is_dir():
            shutil.copytree(child, dst / child.name)


def test_batch_mode_reads_reward_per_query_sidecar() -> None:
    """A DAB batch trial with composite reward 0.857 and a sidecar of six 1.0s
    and one 0.0 must reduce to pass_at_1 == 6/7, not 0.0."""
    outcomes = read_trial_outcomes(DAB_BATCH_FIXTURE)
    report = reduce_per_query_stratified(outcomes, alpha=0.05)

    cells = report["strata"]["yelp"]["queries"]
    by_qid = {c["query_id"]: c["n_correct"] for c in cells}
    assert by_qid == {1: 1, 2: 1, 3: 1, 4: 0, 5: 1, 6: 1, 7: 1}
    assert report["strata"]["yelp"]["dataset_pass_at_1"] == 6 / 7
    assert report["stratified_pass_at_1"] == 6 / 7


def test_batch_mode_summary_json_renders_per_query_datasets_block(tmp_path: Path) -> None:
    """AC-2: summary.json's datasets block carries seven entries for the yelp
    stratum with dataset_pass_at_1 == 6/7. Render adapter preserves the legacy
    field layout (no per-cell wilson_ci, no stratum-level metadata)."""
    work = tmp_path / "exp" / "job"
    _copy_trial_subdirs(DAB_BATCH_FIXTURE, work)

    aggregate_summary(work)
    summary = json.loads((work / "summary.json").read_text())

    yelp = summary["datasets"]["yelp"]
    assert set(yelp.keys()) == {"dataset_pass_at_1", "n_queries", "queries"}
    assert yelp["n_queries"] == 7
    assert yelp["dataset_pass_at_1"] == 6 / 7
    cell_keys = {frozenset(c.keys()) for c in yelp["queries"]}
    assert cell_keys == {frozenset({"query_id", "n_trials", "n_correct", "pass_at_1"})}
    by_qid = {c["query_id"]: c["n_correct"] for c in yelp["queries"]}
    assert by_qid == {1: 1, 2: 1, 3: 1, 4: 0, 5: 1, 6: 1, 7: 1}

    assert summary["stratified_pass_at_1"] == 6 / 7
    assert summary["n_trials_total"] == 1
    assert summary["n_trials_completed"] == 1
    assert summary["n_trials_errored"] == 0


def test_dab_per_query_fixture_still_falls_through(tmp_path: Path) -> None:
    """AC-3: a DAB per-query run-dir (no reward_per_query.json sidecar)
    keeps the one-row-per-trial behavior end-to-end."""
    work = tmp_path / "exp" / "job"
    _copy_trial_subdirs(DAB_PER_QUERY_FIXTURE, work)

    outcomes = read_trial_outcomes(work)
    assert len(outcomes) == 3
    trial_ids = {o["trial_id"] for o in outcomes}
    assert trial_ids == {
        "trial-completed-pass",
        "trial-completed-fail",
        "trial-errored",
    }


def test_ade_bench_round_trip_runs_clean() -> None:
    """AC-3: ADE/Spider fixture (no `dataset` key in stratum, no sidecar)
    round-trips through the canonical reducer without crashing or fanning."""
    outcomes = read_trial_outcomes(ADE_FIXTURE)
    assert len(outcomes) == 3
    report = reduce_per_query_stratified(outcomes)
    assert report["strata"], "ADE fixture must produce at least one stratum"
