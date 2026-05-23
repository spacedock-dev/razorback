# ABOUTME: AC-4 — Goal 1 aggregator enumerates strata from the dataset definition.
# ABOUTME: Plants stub result.json under each cell; verifies aggregate_variant visits every def-listed dataset.

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


def test_aggregator_strata_match_definition(tmp_path: Path) -> None:
    from razorback_plugin_dab.dataset_def import load_default_definition

    definition = load_default_definition()
    matrix_root = tmp_path / "matrix"
    variant_dir = matrix_root / "spacedock"
    variant_dir.mkdir(parents=True)
    for ds_entry in definition.datasets:
        cell = variant_dir / ds_entry.name / "trial0" / "step0"
        cell.mkdir(parents=True)
        (cell / "result.json").write_text(json.dumps({"stats": {"evals": {}}}))

    module = _load_aggregator_module()
    agg = module.aggregate_variant(matrix_root, "spacedock")

    assert set(agg["strata"].keys()) == {d.name for d in definition.datasets}
    assert agg["n_strata_total"] == len(definition.datasets)


def test_aggregator_strata_count_explicitly_sourced_from_definition(tmp_path: Path) -> None:
    """AC-4 Verified by: aggregator's stratum enumeration matches definition cardinality."""
    from razorback_plugin_dab.dataset_def import load_default_definition

    definition = load_default_definition()
    module = _load_aggregator_module()
    matrix_root = tmp_path / "matrix"
    variant_dir = matrix_root / "spacedock"
    variant_dir.mkdir(parents=True)

    agg = module.aggregate_variant(matrix_root, "spacedock")
    assert agg["n_strata_total"] == len(definition.datasets) == 12
