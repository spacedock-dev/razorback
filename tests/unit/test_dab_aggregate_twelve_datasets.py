# ABOUTME: AC-5 — DAB aggregator produces stratified macro-average across 12 datasets (§6.5).

import json
from pathlib import Path

from razorback.benchmarks.dab.aggregate import aggregate_synthetic


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "provenance"


def test_aggregator_stratifies_across_twelve_datasets(tmp_path):
    rows = json.loads((FIXTURES / "twelve_dataset_trial_results.json").read_text())
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    got = json.loads(out.read_text())
    expected = json.loads((FIXTURES / "twelve_dataset_golden_summary.json").read_text())
    assert got == expected


def test_stratified_pass_at_1_is_hand_computed_macro_average(tmp_path):
    """Independent verification: re-derive the macro-average without reading the golden."""
    rows = json.loads((FIXTURES / "twelve_dataset_trial_results.json").read_text())
    out = tmp_path / "summary.json"
    aggregate_synthetic(rows, out)
    got = json.loads(out.read_text())
    per_ds = [d["dataset_pass_at_1"] for d in got["datasets"].values()]
    assert len(per_ds) == 12
    assert abs(got["stratified_pass_at_1"] - sum(per_ds) / 12) < 1e-9
    assert abs(got["stratified_pass_at_1"] - 6.5 / 12) < 1e-9
