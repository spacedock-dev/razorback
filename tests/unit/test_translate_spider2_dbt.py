# ABOUTME: Translator coverage for the spider2-dbt kind:harbor branch in _build_harbor.
# ABOUTME: Family detect, filter-then-materialize, leakage-clean views, benchmark env (AC-1/AC-2).
import shutil

from razorback.translate import _is_spider2_dbt_dataset


def test_detects_spider2_dbt_fully_qualified():
    # Spec datasets with plugin=None must be fully qualified <org>/<name>@<ref>
    # (spec/schema.py:209-226). PackageReference.parse rejects the bare short
    # form, so only the qualified form is a valid spec dataset.
    assert _is_spider2_dbt_dataset("spider2-dbt/spider2-dbt@1.0") is True


def test_rejects_non_spider2_dataset():
    assert _is_spider2_dbt_dataset("adyen/dabstep@latest") is False


def test_rejects_unparseable_short_form():
    # The bare `spider2-dbt@1.0` form is the `harbor download` CLI concept,
    # NOT a valid spec dataset ref — PackageReference.parse raises on it, and
    # the helper swallows the error and returns False. Verified at plan time.
    assert _is_spider2_dbt_dataset("spider2-dbt@1.0") is False


from pathlib import Path

import pytest

from razorback.spec.schema import HarborBenchmarkBlock, NopAgentBlock, Spec
from razorback.translate import spec_to_job_config

FIXTURE_ROOT = (
    Path(__file__).parent.parent
    / "fixtures" / "spider2_dbt" / "harbor_task_minimal"
)


def _spec(benchmark):
    return Spec(
        version=1,
        experiment="spider2-translator-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark=benchmark,
        trials=1,
        observers=[],
    )


def test_spider2_dataset_materializes_views(tmp_path, monkeypatch):
    source = FIXTURE_ROOT / "spider2-fixture-001"

    def fake_resolver(*, dataset_ref, tasks, cache_root):
        return [source]

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks", fake_resolver
    )
    spec = _spec(
        HarborBenchmarkBlock(
            kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0"
        )
    )
    job_config, trial_name_map = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == 1
    view_dir = job_config.tasks[0].path
    # emitted path is a materialized VIEW under tasks_root, not the raw source
    assert (tmp_path / "tasks") in view_dir.parents
    assert (view_dir / "task.toml").is_file()
    assert trial_name_map == {}


def test_spider2_dataset_requires_tasks_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [FIXTURE_ROOT / "spider2-fixture-001"],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0")
    )
    with pytest.raises(Exception) as exc:
        spec_to_job_config(spec, job_name="job", jobs_dir=tmp_path, tasks_root=None)
    assert "tasks_root" in str(exc.value).lower()


import subprocess


def _rg_leakage_hit(view: Path) -> subprocess.CompletedProcess:
    """Run the rider's unescaped `gold|expected|golden` alternation over a view.

    `view_manifest.json` is the materializer's provenance record: it lists the
    deny globs (`tests/expected/**`, `**/gold/**`, `**/golden/**`) and the
    checksums of every excluded source file by design — an audit trail, NOT
    leaked answer content. So the leakage scan excludes the manifest; a hit on
    any other file means real answer data survived the deny globs.
    """
    return subprocess.run(
        ["rg", "-l", "--glob", "!view_manifest.json", "gold|expected|golden", str(view)],
        capture_output=True,
        text=True,
    )


def test_spider2_resolves_n_views_all_leakage_clean(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("spider2-fixture-*"))
    assert len(sources) >= 2, "need >1 fixture instance to prove N task-view dirs"

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == len(sources)
    for task in job_config.tasks:
        view = task.path
        assert (view / "task.toml").is_file()
        # leakage-clean: no gold/expected/golden answer content survives
        hit = _rg_leakage_hit(view)
        assert hit.returncode == 1 and hit.stdout == "", (
            f"leakage in {view}: {hit.stdout}"
        )


def test_planted_forbidden_files_are_excluded_from_view(tmp_path, monkeypatch):
    """Rider (plan-gate cycle 1): plant forbidden answer files in a fixture
    source dir and assert the materialized view excludes them — a NEGATIVE
    leakage proof distinct from the positive AC-1 scan above.

    The planted files carry the gold/expected/golden answer content the deny
    globs exist to strip; if any survives into the view, the rider's unescaped
    `rg -l 'gold|expected|golden'` alternation fires on a real (non-manifest)
    file and the test fails.
    """
    # Build an isolated source copy so the committed fixture stays clean.
    src_root = tmp_path / "src"
    base = FIXTURE_ROOT / "spider2-fixture-001"
    source = src_root / "spider2-fixture-001"
    shutil.copytree(base, source)
    # Plant forbidden files matching SPIDER2_DBT_DENY_GLOBS by path.
    (source / "tests" / "expected").mkdir(parents=True, exist_ok=True)
    (source / "tests" / "expected" / "expected.csv").write_text("id\ngold-value\n")
    (source / "gold").mkdir(exist_ok=True)
    (source / "gold" / "answer.sql").write_text("select 'golden';\n")
    (source / "golden").mkdir(exist_ok=True)
    (source / "golden" / "result.txt").write_text("expected golden output\n")

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [source],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0")
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    view = job_config.tasks[0].path
    # None of the planted answer FILES survive into the view (the deny globs
    # strip files; empty parent dirs may remain — that is not leakage).
    assert not (view / "tests" / "expected" / "expected.csv").exists()
    assert not (view / "gold" / "answer.sql").exists()
    assert not (view / "golden" / "result.txt").exists()
    # And the rider's content scan finds no surviving answer data.
    hit = _rg_leakage_hit(view)
    assert hit.returncode == 1 and hit.stdout == "", (
        f"planted leakage survived into {view}: {hit.stdout}"
    )


def test_exclude_tasks_drops_spider2_source_slug(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("spider2-fixture-*"))
    assert len(sources) >= 2, "need >1 fixture instance to prove exclusion keeps the other"
    excluded_slug = sources[0].name  # e.g. "spider2-fixture-001" (SOURCE slug)

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(
            kind="harbor",
            dataset="spider2-dbt/spider2-dbt@1.0",
            exclude_tasks=[excluded_slug],
        )
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    # the excluded source produced no view; the others did
    assert len(job_config.tasks) == len(sources) - 1
    view_names = {t.path.name for t in job_config.tasks}
    # filter ran on the SOURCE slug, so neither the source slug nor its
    # `spider2-dbt-<slug>` view appears in the emitted set
    assert excluded_slug not in view_names
    assert f"spider2-dbt-{excluded_slug}" not in view_names
    # sanity: a surviving task's view IS the `spider2-dbt-<slug>` form
    kept_slug = sources[1].name
    assert f"spider2-dbt-{kept_slug}" in view_names


def test_n_tasks_caps_spider2_before_materialize(tmp_path, monkeypatch):
    sources = sorted(FIXTURE_ROOT.glob("spider2-fixture-*"))
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: list(sources),
    )
    spec = _spec(
        HarborBenchmarkBlock(
            kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0", n_tasks=1
        )
    )
    job_config, _ = spec_to_job_config(
        spec, job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert len(job_config.tasks) == 1
