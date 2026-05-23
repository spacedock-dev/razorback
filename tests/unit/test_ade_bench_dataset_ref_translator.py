# ABOUTME: RED translator tests for the ade-bench dataset-ref source-resolver path.
# ABOUTME: AC-2: translator calls dataset resolver + materializer; AC-3: docker_image_override preserved.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from razorback.spec.schema import AdeBenchBenchmarkBlock, NopAgentBlock, Spec
from razorback.translate import spec_to_job_config


FAKE_DATASET = (
    Path(__file__).parent.parent / "fixtures" / "ade_bench" / "fake_dataset"
).resolve()


def _make_dataset_spec(
    *,
    tasks: list[str] | None = None,
    docker_image_override: str | None = None,
) -> Spec:
    kwargs: dict = {
        "kind": "ade-bench",
        "dataset": "dbt-labs/ade-bench@latest",
    }
    if tasks is not None:
        kwargs["tasks"] = tasks
    if docker_image_override is not None:
        kwargs["docker_image_override"] = docker_image_override
    return Spec(
        version=1,
        experiment="gb-translator",
        agent=NopAgentBlock(kind="nop"),
        benchmark=AdeBenchBenchmarkBlock(**kwargs),
        trials=1,
        observers=[],
    )


def _install_resolver_stub(monkeypatch, *, items=None, raises=None):
    """Patch resolve_dataset_tasks on the translator's import surface."""
    from razorback.benchmarks.ade_bench import dataset_ref as dr

    captured = {"calls": []}

    def fake_resolve(*, dataset_ref, tasks, cache_root):
        captured["calls"].append(
            {"dataset_ref": dataset_ref, "tasks": tasks, "cache_root": cache_root}
        )
        if raises is not None:
            raise raises
        return items if items is not None else [
            dr.ResolvedDatasetTask(
                path=FAKE_DATASET / "ade-bench-airbnb001",
                task_slug="ade-bench-airbnb001",
                requested_slug="airbnb001",
                content_hash="sha256:" + "a" * 64,
                dataset_content_hash="c" * 64,
            ),
            dr.ResolvedDatasetTask(
                path=FAKE_DATASET / "ade-bench-airbnb002",
                task_slug="ade-bench-airbnb002",
                requested_slug="airbnb002",
                content_hash="sha256:" + "b" * 64,
                dataset_content_hash="c" * 64,
            ),
        ]

    monkeypatch.setattr(
        "razorback.benchmarks.ade_bench.dataset_ref.resolve_dataset_tasks",
        fake_resolve,
    )
    return captured


def test_translator_dataset_ref_calls_resolver_then_materializer(tmp_path, monkeypatch):
    captured = _install_resolver_stub(monkeypatch)
    spec = _make_dataset_spec()

    cfg, trial_name_map = spec_to_job_config(
        spec, job_name="testjob", jobs_dir=tmp_path
    )

    assert len(captured["calls"]) == 1
    call = captured["calls"][0]
    assert call["dataset_ref"] == "dbt-labs/ade-bench@latest"
    assert call["tasks"] is None
    assert call["cache_root"] is not None

    assert len(cfg.tasks) == 2
    assert trial_name_map == {}


def test_translator_dataset_ref_does_not_call_resolve_task_dirs(tmp_path, monkeypatch):
    _install_resolver_stub(monkeypatch)

    def boom(*args, **kwargs):
        raise AssertionError("resolve_task_dirs must not be called on dataset-ref path")

    monkeypatch.setattr(
        "razorback.benchmarks.ade_bench.tasks.resolve_task_dirs", boom
    )

    spec = _make_dataset_spec()
    spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)


def test_translator_emits_taskconfig_path_per_resolved_task(tmp_path, monkeypatch):
    _install_resolver_stub(monkeypatch)
    spec = _make_dataset_spec()
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)

    assert len(cfg.tasks) == 2
    for tc in cfg.tasks:
        assert tc.path is not None
        assert tc.path.is_absolute()
        assert tc.is_git_task() is False
    expected_root = (
        tmp_path / "testjob" / "_razorback" / "task_views"
    )
    for tc in cfg.tasks:
        assert tc.path.parent == expected_root
        assert (tc.path / "view_manifest.json").is_file()


def test_translator_dataset_ref_subset_passes_subset_to_resolver(tmp_path, monkeypatch):
    captured = _install_resolver_stub(monkeypatch)
    spec = _make_dataset_spec(tasks=["airbnb001"])
    spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    assert captured["calls"][0]["tasks"] == ["airbnb001"]


def test_translator_preserves_docker_image_override_through_dataset_path(tmp_path, monkeypatch):
    """AC-3 guardrail: dataset-ref source selection MUST NOT bypass the image override layer."""
    _install_resolver_stub(monkeypatch)
    spec = _make_dataset_spec(docker_image_override="shared-dbt-duckdb:latest")
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)

    import tomllib

    for tc in cfg.tasks:
        task_toml = tomllib.loads((tc.path / "task.toml").read_text())
        assert task_toml["environment"]["docker_image"] == "shared-dbt-duckdb:latest"
        env = task_toml["environment"]["env"]
        assert env["RAZORBACK_BENCHMARK_KIND"] == "ade-bench"
        # benchmark_task_id matches the stripped (suffix) slug
        assert env["RAZORBACK_BENCHMARK_TASK_ID"] in {"airbnb001", "airbnb002"}


def test_translator_writes_dataset_ref_and_content_hashes_into_manifest(tmp_path, monkeypatch):
    """AC-2: view_manifest.json carries dataset_ref + dataset_content_hash + task_content_hash."""
    _install_resolver_stub(monkeypatch)
    spec = _make_dataset_spec()
    cfg, _ = spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)

    by_hash = {
        "sha256:" + "a" * 64: False,
        "sha256:" + "b" * 64: False,
    }
    for tc in cfg.tasks:
        manifest = json.loads((tc.path / "view_manifest.json").read_text())
        assert manifest["dataset_ref"] == "dbt-labs/ade-bench@latest"
        assert manifest["dataset_content_hash"] == "c" * 64
        assert manifest["task_content_hash"] in by_hash
        by_hash[manifest["task_content_hash"]] = True
        assert manifest["schema_version"] >= 2
    assert all(by_hash.values()), "every per-task content hash must appear in manifests"


def test_translator_dataset_ref_resolver_failure_translates_to_spec_error(tmp_path, monkeypatch):
    """AC-5 error path: resolver exceptions surface as SpecError with dataset_ref + cause."""
    from razorback.errors import SpecError

    _install_resolver_stub(monkeypatch, raises=SpecError(
        "failed to resolve dataset 'dbt-labs/ade-bench@latest': registry 503"
    ))

    spec = _make_dataset_spec()
    view_root = tmp_path / "testjob" / "_razorback" / "task_views"
    with pytest.raises(SpecError) as exc:
        spec_to_job_config(spec, job_name="testjob", jobs_dir=tmp_path)
    msg = str(exc.value)
    assert "dbt-labs/ade-bench@latest" in msg
    assert "registry 503" in msg
    # No view_manifest written if resolver fails before materialization.
    if view_root.exists():
        assert not any(view_root.rglob("view_manifest.json"))
