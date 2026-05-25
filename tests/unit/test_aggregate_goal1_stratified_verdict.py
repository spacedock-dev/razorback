# ABOUTME: AC-1/AC-2/AC-4 — Goal 1 aggregator emits stratified_verdict against paper_baseline.
# ABOUTME: 7q-shape fixture (per-cell per_query_pass_at_1 from archived evidence) drives the verdict.

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


AGGREGATOR = (
    Path(__file__).resolve().parents[2]
    / "examples" / "drivers" / "aggregate-goal1-scores.py"
)


def _load_aggregator_module():
    spec = importlib.util.spec_from_file_location("_aggregate_goal1", AGGREGATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Per-cell stats from the 7q archived evidence at
# docs/razorback-implementation/_evidence/goal1-direct-structured-v2/matrix-aggregate/aggregate-score.json
# Stratified mean over 12 cells = 0.6719017094017095; paper_baseline (direct_baseline) = 0.4376.
SEVEN_Q_PER_CELL = {
    "DEPS_DEV_V1": {"per_query_pass_at_1": 0.0, "n_query_trials": 2, "n_query_correct": 0, "n_total": 1, "n_pass": 0},
    "GITHUB_REPOS": {"per_query_pass_at_1": 0.5, "n_query_trials": 4, "n_query_correct": 2, "n_total": 1, "n_pass": 0},
    "PANCANCER_ATLAS": {"per_query_pass_at_1": 2 / 3, "n_query_trials": 3, "n_query_correct": 2, "n_total": 1, "n_pass": 0},
    "PATENTS": {"per_query_pass_at_1": 0.0, "n_query_trials": 3, "n_query_correct": 0, "n_total": 1, "n_pass": 0},
    "agnews": {"per_query_pass_at_1": 0.5, "n_query_trials": 4, "n_query_correct": 2, "n_total": 1, "n_pass": 0},
    "bookreview": {"per_query_pass_at_1": 1.0, "n_query_trials": 3, "n_query_correct": 3, "n_total": 1, "n_pass": 1},
    "crmarenapro": {"per_query_pass_at_1": 11 / 13, "n_query_trials": 13, "n_query_correct": 11, "n_total": 1, "n_pass": 0},
    "googlelocal": {"per_query_pass_at_1": 0.75, "n_query_trials": 4, "n_query_correct": 3, "n_total": 1, "n_pass": 0},
    "music_brainz_20k": {"per_query_pass_at_1": 1.0, "n_query_trials": 3, "n_query_correct": 3, "n_total": 1, "n_pass": 1},
    "stockindex": {"per_query_pass_at_1": 1.0, "n_query_trials": 3, "n_query_correct": 3, "n_total": 1, "n_pass": 1},
    "stockmarket": {"per_query_pass_at_1": 0.8, "n_query_trials": 5, "n_query_correct": 4, "n_total": 1, "n_pass": 0},
    "yelp": {"per_query_pass_at_1": 1.0, "n_query_trials": 7, "n_query_correct": 7, "n_total": 1, "n_pass": 1},
}


def _plant_seven_q_fixture(matrix_root: Path, variant: str, module) -> None:
    """Create stub cell result.json files; monkeypatch `extract_cell_stats` to return canned stats.

    The aggregator's `find_result_json` requires a real result.json on disk
    (it globs `*/*/result.json` under each cell). The actual content is then
    overridden by the patched `extract_cell_stats` returning 7q per-cell numbers.
    """
    variant_dir = matrix_root / variant
    variant_dir.mkdir(parents=True, exist_ok=True)
    for ds_name in SEVEN_Q_PER_CELL:
        cell = variant_dir / ds_name / "trial0" / "step0"
        cell.mkdir(parents=True, exist_ok=True)
        (cell / "result.json").write_text(json.dumps({"stats": {"evals": {}}}))

    def _stub_extract(result_json: Path) -> dict:
        ds_name = result_json.parent.parent.parent.name
        cell = SEVEN_Q_PER_CELL[ds_name]
        return {
            "n_total": cell["n_total"],
            "n_pass": cell["n_pass"],
            "n_errored": 0,
            "rewards": {},
            "result_json": str(result_json),
            "per_query_pass_at_1": cell["per_query_pass_at_1"],
            "n_query_trials": cell["n_query_trials"],
            "n_query_correct": cell["n_query_correct"],
            "per_query_strata": {},
        }

    module.extract_cell_stats = _stub_extract


def test_stratified_verdict_against_direct_baseline_seven_q(tmp_path, monkeypatch):
    """AC-1: stratified_verdict computed from per_query_pass_at_1_mean_over_strata."""
    module = _load_aggregator_module()
    matrix_root = tmp_path / "matrix"
    _plant_seven_q_fixture(matrix_root, "direct-structured", module)

    agg = module.aggregate_variant(matrix_root, "direct-structured")

    # Stratified mean check (sanity).
    assert abs(agg["per_query_pass_at_1_mean_over_strata"] - 0.6719017094017095) < 1e-3

    # Against-constant block targets direct_baseline = 0.4376.
    assert agg["against_constant"]["name"] == "direct_baseline"
    assert agg["against_constant"]["value"] == 0.4376

    # AC-1: canonical paper-comparison verdict from the stratified mean.
    sv = agg["against_constant"]["stratified_verdict"]
    assert sv["verdict"] == "above"
    assert abs(sv["stratified_mean"] - 0.6719017094017095) < 1e-3
    assert sv["value"] == 0.4376

    # AC-2 (choice b): null CI, captain decision.
    assert sv["ci"] is None


def test_stratified_verdict_backward_compat_fields_preserved(tmp_path):
    """AC-4: existing `verdict` (binary) and `per_query_verdict` (pooled) fields remain."""
    module = _load_aggregator_module()
    matrix_root = tmp_path / "matrix"
    _plant_seven_q_fixture(matrix_root, "direct-structured", module)

    agg = module.aggregate_variant(matrix_root, "direct-structured")

    # Backward-compat lenses still emit per their original logic.
    assert "verdict" in agg["against_constant"]
    assert "per_query_verdict" in agg["against_constant"]
    # Pooled per-query (40/54 = 0.7407) is above 0.4376 — pooled verdict stays "above".
    assert agg["against_constant"]["per_query_verdict"] == "above"
