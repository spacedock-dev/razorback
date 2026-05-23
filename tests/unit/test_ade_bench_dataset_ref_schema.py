# ABOUTME: RED schema tests for AdeBenchBenchmarkBlock.dataset (Harbor dataset ref).
# ABOUTME: Tests AC-1 — accept dataset-only, dataset+subset, keep tasks_root compat, reject conflicts/bare names.

import pytest
from pydantic import ValidationError

from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    NopAgentBlock,
    Spec,
)


def test_schema_accepts_dataset_only():
    block = AdeBenchBenchmarkBlock(
        kind="ade-bench",
        dataset="dbt-labs/ade-bench@latest",
    )
    assert block.dataset == "dbt-labs/ade-bench@latest"
    assert block.tasks_root is None
    assert block.tasks is None


def test_schema_accepts_dataset_with_subset():
    block = AdeBenchBenchmarkBlock(
        kind="ade-bench",
        dataset="dbt-labs/ade-bench@latest",
        tasks=["airbnb001", "airbnb002"],
    )
    assert block.dataset == "dbt-labs/ade-bench@latest"
    assert block.tasks == ["airbnb001", "airbnb002"]
    assert block.tasks_root is None


def test_schema_keeps_local_tasks_root_compat():
    block = AdeBenchBenchmarkBlock(
        kind="ade-bench",
        tasks_root="/tmp/ade-bench-tasks",
        tasks=["ade-bench-airbnb001"],
    )
    assert block.tasks_root is not None
    assert block.tasks == ["ade-bench-airbnb001"]
    assert block.dataset is None


def test_schema_rejects_dataset_plus_tasks_root():
    with pytest.raises(ValidationError) as exc:
        AdeBenchBenchmarkBlock(
            kind="ade-bench",
            dataset="dbt-labs/ade-bench@latest",
            tasks_root="/tmp/local",
            tasks=["a"],
        )
    msg = str(exc.value)
    assert "dataset" in msg
    assert "tasks_root" in msg


def test_schema_rejects_neither_dataset_nor_tasks_root():
    with pytest.raises(ValidationError) as exc:
        AdeBenchBenchmarkBlock(kind="ade-bench")
    msg = str(exc.value)
    assert "dataset" in msg
    assert "tasks_root" in msg


def test_schema_rejects_bare_dataset_name_with_canonical_example_in_error():
    """AC-1 captain guardrail: bad input -> good guidance.

    Bare names (no `<org>/`) must reject with a message that names BOTH a
    working canonical example AND the rule.
    """
    with pytest.raises(ValidationError) as exc:
        AdeBenchBenchmarkBlock(
            kind="ade-bench",
            dataset="ade-bench@1.0",
        )
    msg = str(exc.value)
    assert "<org>/<name>@<ref>" in msg
    assert "dbt-labs/ade-bench@latest" in msg


def test_schema_rejects_dataset_missing_ref_with_canonical_example_in_error():
    with pytest.raises(ValidationError) as exc:
        AdeBenchBenchmarkBlock(
            kind="ade-bench",
            dataset="dbt-labs/ade-bench",
        )
    msg = str(exc.value)
    assert "<org>/<name>@<ref>" in msg
    assert "dbt-labs/ade-bench@latest" in msg


def test_spec_dispatches_to_ade_bench_dataset_via_discriminator():
    spec = Spec(
        version=1,
        experiment="x",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "ade-bench",
            "dataset": "dbt-labs/ade-bench@latest",
        },
    )
    assert isinstance(spec.benchmark, AdeBenchBenchmarkBlock)
    assert spec.benchmark.dataset == "dbt-labs/ade-bench@latest"
