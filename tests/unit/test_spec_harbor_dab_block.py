# ABOUTME: Phase 2 — HarborDabBenchmarkBlock parses with defaults and rejects unknowns.
# ABOUTME: Confirms retired in-tree DAB spellings are rejected.

from pathlib import Path

import pytest

from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text
from razorback.spec.schema import HarborDabBenchmarkBlock


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


def test_harbor_dab_data_root_expands_env_default(monkeypatch) -> None:
    monkeypatch.delenv("DATAAGENTBENCH_DATA_ROOT", raising=False)
    spec = parse_spec_text(_spec(
        "  kind: harbor_dab\n"
        '  data_root: "${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}"\n'
        "  datasets: [bookreview]\n"
    ))
    assert isinstance(spec.benchmark, HarborDabBenchmarkBlock)
    assert spec.benchmark.data_root == Path.home() / "dataagentbench" / "data"


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


def test_in_tree_dab_kind_is_retired_from_active_specs(tmp_path: Path) -> None:
    with pytest.raises(SpecError) as exc_info:
        parse_spec_text(_spec(
            "  kind: in_tree_dab\n"
            f"  data_root: {tmp_path}\n"
            "  datasets: [bookreview]\n"
        ))
    assert "harbor_dab" in str(exc_info.value) or "Input tag" in str(exc_info.value)


def test_dab_kind_is_retired_from_active_specs(tmp_path: Path) -> None:
    with pytest.raises(SpecError) as exc_info:
        parse_spec_text(_spec(
            "  kind: dab\n"
            f"  data_root: {tmp_path}\n"
            "  datasets: [bookreview]\n"
        ))
    assert "harbor_dab" in str(exc_info.value) or "Input tag" in str(exc_info.value)
