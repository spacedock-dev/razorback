# ABOUTME: AC-2 — HarborDabBenchmarkBlock accepts dataset: <name>@<version> in place of data_root+datasets.
# ABOUTME: Old-shape specs still parse (compat). Mixed shapes raise.

from pathlib import Path

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text
from razorback.spec.schema import HarborDabBenchmarkBlock


def _spec(benchmark_yaml: str) -> str:
    return (
        "version: 1\n"
        "experiment: ac2-test\n"
        "agent:\n"
        "  kind: nop\n"
        f"benchmark:\n{benchmark_yaml}\n"
        "trials: 1\n"
    )


def test_harbor_dab_accepts_dataset_ref_without_data_root() -> None:
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        "  dataset: dab@1.0\n"
        "  workspace_variant: spacedock\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.dataset == "dab@1.0"
    assert spec.benchmark.datasets == []
    assert spec.benchmark.data_root is None


def test_harbor_dab_dataset_ref_with_subset() -> None:
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        "  dataset: dab@1.0\n"
        "  datasets: [bookreview, agnews]\n"
        "  workspace_variant: spacedock\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.dataset == "dab@1.0"
    assert spec.benchmark.datasets == ["bookreview", "agnews"]


def test_harbor_dab_legacy_shape_still_parses(tmp_path: Path) -> None:
    """AC-2 compat: old harbor_dab specs (no `dataset:`) keep working."""
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        f"  data_root: {tmp_path}\n"
        "  datasets: [bookreview]\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.dataset is None
    assert spec.benchmark.data_root == tmp_path


def test_harbor_dab_legacy_shape_requires_data_root_when_no_dataset_ref(
    tmp_path: Path,
) -> None:
    with pytest.raises(SpecError, match="(?i)data_root.*required"):
        parse_spec_text(_spec(
            "  kind: harbor_dab\n"
            "  datasets: [bookreview]\n"
        ))


def test_harbor_dab_rejects_unknown_dataset_ref_format() -> None:
    with pytest.raises(SpecError, match="(?i)dataset.*format"):
        parse_spec_text(_spec(
            "  kind: harbor_dab\n"
            "  dataset: dab-no-version\n"
        ))
