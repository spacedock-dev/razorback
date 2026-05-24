# ABOUTME: Schema tests for the generic HarborBenchmarkBlock (kind: harbor).
# ABOUTME: Validates dataset-ref shape, selectors, dispatch via discriminator.

import pytest
from pydantic import ValidationError

from razorback.spec.schema import (
    HarborBenchmarkBlock,
    NopAgentBlock,
    Spec,
)


def test_schema_accepts_dataset_only():
    block = HarborBenchmarkBlock(
        kind="harbor",
        dataset="adyen/dabstep@latest",
    )
    assert block.dataset == "adyen/dabstep@latest"
    assert block.tasks is None
    assert block.exclude_tasks is None
    assert block.n_tasks is None
    assert block.plugin is None
    assert block.plugin_args is None


def test_schema_accepts_dataset_with_task_subset():
    block = HarborBenchmarkBlock(
        kind="harbor",
        dataset="adyen/dabstep@latest",
        tasks=["35", "2712"],
    )
    assert block.tasks == ["35", "2712"]


def test_schema_accepts_dataset_with_exclude_tasks_and_n_tasks():
    block = HarborBenchmarkBlock(
        kind="harbor",
        dataset="swe-bench/swe-bench-verified@latest",
        exclude_tasks=["matplotlib__matplotlib-14623"],
        n_tasks=10,
    )
    assert block.exclude_tasks == ["matplotlib__matplotlib-14623"]
    assert block.n_tasks == 10


def test_schema_rejects_dataset_missing():
    with pytest.raises(ValidationError) as exc:
        HarborBenchmarkBlock(kind="harbor")
    msg = str(exc.value)
    assert "dataset" in msg


def test_schema_rejects_bare_dataset_name_with_canonical_example_in_error():
    """Bad input -> good guidance: error names BOTH the required shape AND a
    working canonical example."""
    with pytest.raises(ValidationError) as exc:
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="dabstep@1.0",
        )
    msg = str(exc.value)
    assert "<org>/<name>@<ref>" in msg
    assert "adyen/dabstep@latest" in msg


def test_schema_rejects_dataset_missing_ref_with_canonical_example_in_error():
    with pytest.raises(ValidationError) as exc:
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="adyen/dabstep",
        )
    msg = str(exc.value)
    assert "<org>/<name>@<ref>" in msg
    assert "adyen/dabstep@latest" in msg


def test_schema_rejects_extra_fields():
    with pytest.raises(ValidationError) as exc:
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="adyen/dabstep@latest",
            datasets=["a"],  # ← typo / leftover from harbor_dab; must reject
        )
    assert "datasets" in str(exc.value).lower()


def test_spec_dispatches_to_harbor_via_discriminator():
    spec = Spec(
        version=1,
        experiment="x",
        agent=NopAgentBlock(kind="nop"),
        benchmark={
            "kind": "harbor",
            "dataset": "adyen/dabstep@latest",
        },
    )
    assert isinstance(spec.benchmark, HarborBenchmarkBlock)
    assert spec.benchmark.dataset == "adyen/dabstep@latest"


def test_schema_accepts_tag_revision_and_digest_refs():
    digest_ref = (
        "adyen/dabstep@sha256:"
        "0edf62c0bdf7003b1d1f934f1547df1c051877e076d5b6f6a2d99caf8b6432b3"
    )
    for ref in ("adyen/dabstep@latest", "adyen/dabstep@1", digest_ref):
        block = HarborBenchmarkBlock(kind="harbor", dataset=ref)
        assert block.dataset == ref


def test_schema_validation_uses_harbor_package_reference_parser():
    """Pin the validator to Harbor's own ref grammar rather than a parallel regex."""
    from harbor.models.package.reference import PackageReference

    for ref in (
        "adyen/dabstep@latest",
        "swe-bench/swe-bench-verified@latest",
        "dbt-labs/ade-bench@1",
    ):
        parsed = PackageReference.parse(ref)
        assert parsed.org and parsed.short_name and parsed.ref
        block = HarborBenchmarkBlock(kind="harbor", dataset=ref)
        assert block.dataset == ref


def test_schema_coexists_with_other_kinds_in_union():
    """`HarborBenchmarkBlock` lives alongside surviving per-benchmark kinds."""
    from razorback.spec.schema import (
        AdeBenchBenchmarkBlock,
        HarborLocalBenchmarkBlock,
        LocalBenchmarkBlock,
        Spider2DbtBenchmarkBlock,
    )

    cases = [
        ({"kind": "harbor", "dataset": "adyen/dabstep@latest"}, HarborBenchmarkBlock),
        ({"kind": "harbor-local", "tasks_root": "/tmp", "tasks": ["t"]}, HarborLocalBenchmarkBlock),
        ({"kind": "ade-bench", "dataset": "dbt-labs/ade-bench@latest"}, AdeBenchBenchmarkBlock),
        ({"kind": "spider2-dbt", "tasks_root": "/tmp", "tasks": ["t"]}, Spider2DbtBenchmarkBlock),
        ({"kind": "local", "task_paths": []}, LocalBenchmarkBlock),
    ]
    for benchmark_dict, expected_cls in cases:
        spec = Spec(
            version=1,
            experiment="x",
            agent=NopAgentBlock(kind="nop"),
            benchmark=benchmark_dict,
        )
        assert isinstance(spec.benchmark, expected_cls), (
            f"{benchmark_dict['kind']} dispatched to {type(spec.benchmark).__name__}, "
            f"expected {expected_cls.__name__}"
        )
