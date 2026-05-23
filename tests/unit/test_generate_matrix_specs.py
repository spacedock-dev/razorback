# ABOUTME: AC-5 — Goal 1 matrix specs opt into harbor-DAB batch query_mode.
# ABOUTME: Asserts build_spec() emits benchmark.query_mode: batch for every cell.

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "examples" / "drivers" / "generate-dab-paper-matrix-specs.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "_goal1_matrix_specs", str(GENERATOR)
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("_goal1_matrix_specs", module)
    spec.loader.exec_module(module)
    return module


def test_matrix_specs_carry_query_mode_batch() -> None:
    module = _load_generator()
    spec = module.build_spec("spacedock", "bookreview")
    assert spec["benchmark"]["query_mode"] == "batch"
    assert (
        spec["benchmark"]["data_root"]
        == "${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}"
    )


def test_matrix_specs_query_mode_batch_for_all_variants() -> None:
    module = _load_generator()
    for variant in ("spacedock", "direct-minimal", "direct-structured"):
        spec = module.build_spec(variant, "agnews")
        assert spec["benchmark"]["query_mode"] == "batch", (
            f"{variant}/agnews missing query_mode=batch"
        )
