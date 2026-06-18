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
from razorback.translate import SpecError, spec_to_job_config

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
    with pytest.raises(SpecError) as exc:
        spec_to_job_config(spec, job_name="job", jobs_dir=tmp_path, tasks_root=None)
    assert "tasks_root" in str(exc.value).lower()


_LEAKAGE_TERMS = ("gold", "expected", "golden")


def _is_verifier_only(rel: Path) -> bool:
    """True for the verify-time-only `tests/` subtree.

    Harbor uploads the task's `tests/` dir into the container ONLY at verify
    time and wipes/recreates it around the agent run, so it is never part of
    the agent-visible view:
      - harbor/verifier/verifier.py:133-138 uploads `tests/` inside `verify()`.
      - harbor/trial/trial.py `_verify_step` first `reset_dirs(remove=[tests_dir,
        verifier_dir])` then re-uploads — the agent step never sees `/tests`.
    The spider2-dbt materializer deliberately stages the gold .duckdb + eval
    spec + comparator there (`_ensure_verifier_assets`); those are the verifier's
    answer key, NOT agent-visible leakage. Scoping the scan to the agent-visible
    portion (everything OUTSIDE `tests/`) keeps real leakage protection intact:
    any answer data that survives into an agent-reachable path still trips.
    """
    return rel.parts[:1] == ("tests",)


def _leakage_hits(view: Path) -> list[Path]:
    """Pure-Python reimplementation of the rider's `rg -l 'gold|expected|golden'`,
    scoped to the AGENT-VISIBLE portion of the view.

    Walks the view dir and reports any file whose NAME or CONTENT matches the
    case-sensitive alternation `gold|expected|golden` — matching the rider's
    unescaped `rg -l` semantics. Two exclusions, both principled:

    - `view_manifest.json` is the materializer's provenance record: it lists the
      deny globs (`tests/expected/**`, `**/gold/**`, `**/golden/**`) and the
      checksums of every excluded source file by design — an audit trail, NOT
      leaked answer content.
    - The verify-time-only `tests/` subtree (see `_is_verifier_only`): Harbor
      uploads it to the container only at verify time and removes it during the
      agent run, so the gold .duckdb / eval spec / comparator the verifier needs
      there are never agent-visible.

    A hit on any other file means real answer data survived into an
    agent-reachable path.
    """
    hits: list[Path] = []
    for path in sorted(view.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "view_manifest.json":
            continue
        if _is_verifier_only(path.relative_to(view)):
            continue
        if any(term in path.name for term in _LEAKAGE_TERMS):
            hits.append(path)
            continue
        try:
            content = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if any(term in content for term in _LEAKAGE_TERMS):
            hits.append(path)
    return hits


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
        hits = _leakage_hits(view)
        assert hits == [], f"leakage in {view}: {hits}"


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
    hits = _leakage_hits(view)
    assert hits == [], f"planted leakage survived into {view}: {hits}"


def test_leakage_scan_still_fires_on_agent_visible_answer_content(tmp_path):
    """Guard: the `tests/`-scoped exclusion must NOT blanket-disable the scan.

    Plant `gold`-named answer content BOTH in an agent-visible path (view root)
    AND under the verify-time-only `tests/` subtree, then assert `_leakage_hits`
    reports the agent-visible one and ignores the verifier-only one. This pins
    the B1 fix to scoping (exclude only `tests/`), not weakening the scanner.
    """
    view = tmp_path / "view"
    (view / "models").mkdir(parents=True)
    (view / "models" / "answer_gold.sql").write_text("select 'leak';\n")
    (view / "tests").mkdir()
    (view / "tests" / "gold.duckdb").write_bytes(b"verifier-only gold answer key")

    hits = _leakage_hits(view)
    assert view / "models" / "answer_gold.sql" in hits, "agent-visible leak missed"
    assert view / "tests" / "gold.duckdb" not in hits, "verifier-only asset flagged"


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


def _materialize_spider2(tmp_path, monkeypatch, *, materialize_mode):
    """Run the spider2-dbt translate branch and return the single emitted view.

    Uses an isolated copy of the fixture as the source so a link-mode run can
    never mutate the committed fixture tree (the view symlinks back into it).
    """
    source = tmp_path / "src" / "spider2-fixture-001"
    shutil.copytree(FIXTURE_ROOT / "spider2-fixture-001", source)
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks",
        lambda **k: [source],
    )
    spec = _spec(
        HarborBenchmarkBlock(kind="harbor", dataset="spider2-dbt/spider2-dbt@1.0")
    )
    job_config, _ = spec_to_job_config(
        spec,
        job_name="job",
        jobs_dir=tmp_path,
        tasks_root=tmp_path / "tasks",
        materialize_mode=materialize_mode,
    )
    return job_config.tasks[0].path


def test_materialize_bind_produces_symlinked_view_files(tmp_path, monkeypatch):
    """`--materialize bind` must thread bind->view_mode='link' through
    `_build_harbor` into `materialize_spider2_harbor_task_view`, so non-denied
    source files appear as symlinks in the view (no eager duplication of large
    task trees). Parity with ade-bench, which threads the mode via cli/run.py:313.
    """
    view = _materialize_spider2(tmp_path, monkeypatch, materialize_mode="bind")
    # a non-denied source file (the dbt model) is materialized as a symlink
    linked = view / "dbt_project" / "models" / "example.sql"
    assert linked.is_file()
    assert linked.is_symlink(), "bind mode must symlink, not copy, view files"


def test_materialize_copy_still_copies_view_files(tmp_path, monkeypatch):
    """`copy` mode (and the bind default mapping) must keep copying — the file
    is a real copy, not a symlink, so reverting the bind->link mapping is caught.
    """
    view = _materialize_spider2(tmp_path, monkeypatch, materialize_mode="copy")
    copied = view / "dbt_project" / "models" / "example.sql"
    assert copied.is_file()
    assert not copied.is_symlink(), "copy mode must copy, not symlink, view files"


from harbor.models.task.config import TaskConfig as HarborTaskConfig


def test_materialized_view_carries_benchmark_env(tmp_path, monkeypatch):
    source = FIXTURE_ROOT / "spider2-fixture-001"
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
    view_toml = job_config.tasks[0].path / "task.toml"
    cfg = HarborTaskConfig.model_validate_toml(view_toml.read_text())
    assert cfg.environment.env["RAZORBACK_BENCHMARK_KIND"] == "spider2-dbt"
    assert cfg.environment.env["RAZORBACK_BENCHMARK_TASK_ID"] == "spider2-fixture-001"
