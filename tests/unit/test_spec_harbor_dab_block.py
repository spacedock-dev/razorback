# ABOUTME: Phase 2 — HarborDabBenchmarkBlock parses with defaults and rejects unknowns.
# ABOUTME: Confirms the v2 in_tree_dab alias still produces a DabBenchmarkBlock.

from pathlib import Path

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text
from razorback.spec.schema import (
    DabBenchmarkBlock,
    HarborDabBenchmarkBlock,
)


def _spec(benchmark_yaml: str) -> str:
    return (
        "version: 1\n"
        "experiment: phase2-spec-test\n"
        "agent:\n"
        "  kind: nop\n"
        f"benchmark:\n{benchmark_yaml}\n"
        "trials: 1\n"
    )


def test_harbor_dab_block_parses_with_defaults(tmp_path: Path) -> None:
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        f"  data_root: {tmp_path}\n"
        "  datasets: [bookreview]\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.workspace_variant == "direct-minimal"
    assert spec.benchmark.hints is False
    assert spec.benchmark.datasets == ["bookreview"]


def test_harbor_dab_block_accepts_overrides(tmp_path: Path) -> None:
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        f"  data_root: {tmp_path}\n"
        "  datasets: [bookreview, agnews]\n"
        "  workspace_variant: spacedock\n"
        "  hints: true\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.workspace_variant == "spacedock"
    assert spec.benchmark.hints is True


def test_harbor_dab_rejects_unknown_workspace_variant(tmp_path: Path) -> None:
    with pytest.raises(SpecError):
        parse_spec_text(_spec(
            "  kind: harbor_dab\n"
            f"  data_root: {tmp_path}\n"
            "  datasets: [bookreview]\n"
            "  workspace_variant: ad-hoc\n"
        ))


def test_harbor_dab_default_query_mode_is_per_query(tmp_path: Path) -> None:
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        f"  data_root: {tmp_path}\n"
        "  datasets: [bookreview]\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.query_mode == "per-query"


def test_harbor_dab_accepts_query_mode_batch_and_per_query(tmp_path: Path) -> None:
    for mode in ("batch", "per-query"):
        spec = parse_spec_text(_spec(
            "  kind: harbor_dab\n"
            f"  data_root: {tmp_path}\n"
            "  datasets: [bookreview]\n"
            f"  query_mode: {mode}\n"
        ))
        assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
        assert spec.benchmark.query_mode == mode


def test_harbor_dab_rejects_unknown_query_mode(tmp_path: Path) -> None:
    with pytest.raises(SpecError):
        parse_spec_text(_spec(
            "  kind: harbor_dab\n"
            f"  data_root: {tmp_path}\n"
            "  datasets: [bookreview]\n"
            "  query_mode: fresh\n"
        ))


def test_in_tree_dab_alias_resolves_to_dab(tmp_path: Path) -> None:
    spec = parse_spec_text(_spec(
        "  kind: in_tree_dab\n"
        f"  data_root: {tmp_path}\n"
        "  datasets: [bookreview]\n"
    ))
    assert isinstance(spec.benchmark, DabBenchmarkBlock)
    assert spec.benchmark.kind == "dab"


def test_legacy_dab_kind_still_parses(tmp_path: Path) -> None:
    spec = parse_spec_text(_spec(
        "  kind: dab\n"
        f"  data_root: {tmp_path}\n"
        "  datasets: [bookreview]\n"
    ))
    assert isinstance(spec.benchmark, DabBenchmarkBlock)
