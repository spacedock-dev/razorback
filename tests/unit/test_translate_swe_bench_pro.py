# tests/unit/test_translate_swe_bench_pro.py
# ABOUTME: AC-1/AC-2 — swe-bench-pro kind:harbor wiring through the generic materializer.
# ABOUTME: Fixture-backed, network-free via the _resolve_harbor_dataset_tasks monkeypatch seam.
from razorback.translate import _is_swe_bench_pro_dataset


def test_detects_swe_bench_pro_fully_qualified():
    # Spec datasets with plugin=None must be fully qualified <org>/<name>@<ref>
    # (spec/schema.py:209-232). PackageReference.parse rejects the bare short
    # form, so only the qualified form is a valid spec dataset.
    assert _is_swe_bench_pro_dataset("scale-ai/swe-bench-pro@latest") is True


def test_rejects_non_swe_dataset():
    assert _is_swe_bench_pro_dataset("adyen/dabstep@latest") is False
    assert _is_swe_bench_pro_dataset("spider2-dbt/spider2-dbt@1.0") is False


def test_rejects_unparseable_bare_form():
    # The bare `swe-bench-pro@latest` form is the `harbor download` CLI concept,
    # NOT a valid spec dataset ref — PackageReference.parse raises on it, and
    # the helper swallows the error and returns False. Verified at plan time.
    assert _is_swe_bench_pro_dataset("swe-bench-pro@latest") is False


import json
from pathlib import Path

import pytest

from razorback.spec.schema import HarborBenchmarkBlock, NopAgentBlock, Spec
from razorback.translate import spec_to_job_config

FIXTURE_ROOT = (
    Path(__file__).parent.parent
    / "fixtures" / "swe_bench_pro" / "harbor_task_minimal"
)


def _spec(benchmark):
    return Spec(
        version=1,
        experiment="swe-bench-pro-translator-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark=benchmark,
        trials=1,
        observers=[],
    )


def test_swe_dataset_materializes_views_with_manifest(tmp_path, monkeypatch):
    source = FIXTURE_ROOT / "swe-bench-pro-fixture-001"

    def fake_resolver(*, dataset_ref, tasks, cache_root):
        return [source]

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks", fake_resolver
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="scale-ai/swe-bench-pro@latest")
    )
    job_config, trial_name_map = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == 1
    view_dir = job_config.tasks[0].path
    # emitted path is a materialized VIEW under tasks_root, not the raw source
    assert (tmp_path / "tasks") in view_dir.parents
    assert (view_dir / "task.toml").is_file()
    # the view took the materializer branch, NOT the generic pass-through:
    # only the materializer writes view_manifest.json with benchmark_kind.
    manifest = json.loads((view_dir / "view_manifest.json").read_text())
    assert manifest["benchmark_kind"] == "swe-bench-pro"
    assert trial_name_map == {}


def test_swe_dataset_requires_tasks_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [FIXTURE_ROOT / "swe-bench-pro-fixture-001"],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="scale-ai/swe-bench-pro@latest")
    )
    with pytest.raises(Exception) as exc:
        spec_to_job_config(spec, job_name="job", jobs_dir=tmp_path, tasks_root=None)
    assert "tasks_root" in str(exc.value).lower()
