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


def test_swe_resolves_n_views_with_manifest_leakage_clean(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("swe-bench-pro-fixture-*"))
    assert len(sources) >= 2, "need >1 fixture instance to prove N task-view dirs"

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="scale-ai/swe-bench-pro@latest")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == len(sources)
    for task in job_config.tasks:
        view = task.path
        assert view.name.startswith("swe-bench-pro-")
        assert (view / "task.toml").is_file()
        manifest = json.loads((view / "view_manifest.json").read_text())
        assert manifest["benchmark_kind"] == "swe-bench-pro"
        assert manifest["benchmark_task_id"].startswith("swe-bench-pro-fixture-")
        # leakage-clean: the planted DEFAULT-deny file did not survive. The
        # `solution/**` glob strips files UNDER solution/; the materializer may
        # leave an empty `solution/` dir node (it carries no answer content,
        # and the materializer's own assert_no_denied_paths only inspects
        # files/symlinks). The leakage contract is "no answer content
        # survives" — assert no files remain anywhere under solution/.
        assert not (view / "solution" / "gold_patch.diff").exists()
        if (view / "solution").exists():
            assert not any(p.is_file() for p in (view / "solution").rglob("*"))


def test_exclude_tasks_drops_swe_source_slug(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("swe-bench-pro-fixture-*"))
    assert len(sources) >= 2
    excluded_slug = sources[0].name  # SOURCE slug, e.g. "swe-bench-pro-fixture-001"

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="scale-ai/swe-bench-pro@latest",
            exclude_tasks=[excluded_slug],
        )
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == len(sources) - 1
    view_names = {t.path.name for t in job_config.tasks}
    # filter ran on the SOURCE slug, so neither the source slug nor its
    # `swe-bench-pro-<slug>` view appears in the emitted set
    assert excluded_slug not in view_names
    assert f"swe-bench-pro-{excluded_slug}" not in view_names
    # a surviving task IS the `swe-bench-pro-<slug>` view form
    kept_slug = sources[1].name
    assert f"swe-bench-pro-{kept_slug}" in view_names


def test_swe_ref_takes_materializer_branch_not_passthrough(tmp_path, monkeypatch):
    # AC-1: the swe ref must take the materializer branch. The generic
    # pass-through emits the RAW source dir (no manifest, name == source slug);
    # the materializer branch emits a `swe-bench-pro-<slug>` view WITH a
    # manifest. Assert the latter to prove the branch — not the pass-through.
    source = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [source],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="scale-ai/swe-bench-pro@latest")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    view = job_config.tasks[0].path
    assert view != source                       # NOT the raw source dir
    assert view.name == "swe-bench-pro-swe-bench-pro-fixture-001"
    assert (view / "view_manifest.json").is_file()  # only the materializer writes this


def test_n_tasks_caps_swe_before_materialize(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("swe-bench-pro-fixture-*"))
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(
            kind="harbor", dataset="scale-ai/swe-bench-pro@latest", n_tasks=1
        )
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == 1


from harbor.models.task.config import TaskConfig as HarborTaskConfig


def test_materialized_view_carries_benchmark_env(tmp_path, monkeypatch):
    source = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [source],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="scale-ai/swe-bench-pro@latest")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    view_toml = job_config.tasks[0].path / "task.toml"
    cfg = HarborTaskConfig.model_validate_toml(view_toml.read_text())
    # env passed by the _build_harbor swe branch, MERGED into task.toml by
    # materialize_harbor_task_view (_patch_task_toml) — the materializer does
    # NOT synthesize these; the branch supplies them.
    assert cfg.environment.env["RAZORBACK_BENCHMARK_KIND"] == "swe-bench-pro"
    assert cfg.environment.env["RAZORBACK_BENCHMARK_TASK_ID"] == "swe-bench-pro-fixture-001"
