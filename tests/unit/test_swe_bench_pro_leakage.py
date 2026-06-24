# tests/unit/test_swe_bench_pro_leakage.py
# ABOUTME: AC-1/AC-2/AC-3 — swe-bench-pro gold/test-patch leakage deny-globs.
# ABOUTME: fnmatch's `*` crosses `/`, so the SWE set is a STANDALONE curated,
# ABOUTME: task-root-scoped tuple — it does NOT inherit the default's broad **/ globs.
import shutil
from pathlib import Path

import pytest

from razorback.harbor_tasks.leakage import (
    DEFAULT_SOLUTION_DENY_GLOBS,
    SWE_BENCH_PRO_DENY_GLOBS,
    LeakageError,
    assert_no_denied_paths,
    matches_denied_path,
)
from razorback.harbor_tasks.materialize import materialize_harbor_task_view
from razorback.spec.schema import HarborBenchmarkBlock, NopAgentBlock, Spec
from razorback.translate import spec_to_job_config

FIXTURE_ROOT = (
    Path(__file__).parent.parent
    / "fixtures" / "swe_bench_pro" / "harbor_task_minimal"
)

# Revert baseline: the curated SWE set with the answer-ARTIFACT globs removed,
# leaving only the root solution/answer-DIR family. Simulates "before E2 added
# the swe answer-artifact coverage". Verified at plan time: this baseline
# catches NONE of the planted task-root patch files.
_REVERT_BASELINE = ("solution/**", "solutions/**", "tests/expected/**")


def test_swe_leak_globs_are_standalone_not_default_superset():
    # The SWE set is STANDALONE (captain decision): it must NOT inherit the
    # default's broad cross-`/` globs that strip nested repo files.
    swe = set(SWE_BENCH_PRO_DENY_GLOBS)
    assert "**/answer*" not in swe
    assert "**/solution.*" not in swe
    assert "**/*answers*" not in swe
    # It is NOT a superset of the default (proves it is curated, not DEFAULT + ...).
    assert not (set(DEFAULT_SOLUTION_DENY_GLOBS) <= swe)
    # The shared default is left untouched (spider2/ade/dabstep depend on it).
    assert DEFAULT_SOLUTION_DENY_GLOBS == (
        "solution/**",
        "solutions/**",
        "**/solution.*",
        "**/answer*",
        "**/*answers*",
        "tests/expected/**",
    )


def test_swe_leak_globs_deny_task_root_answer_artifacts():
    # SWE answer artifacts at the TASK ROOT (siblings of the repo checkout).
    for path in [
        "gold/patch.diff",     # root gold answer dir
        "gold/gold_patch.diff",
        "gold_patch.diff",     # root gold-prefixed answer file
        "gold.patch",
        "test_patch.diff",     # root test patch (hidden grading tests)
        "test_patch",
        "FAIL_TO_PASS.json",   # root fail-to-pass set
        "PASS_TO_PASS.json",   # root pass-to-pass set
        "patch",               # plain gold patch artifact
        "patch.diff",
        "solution.patch",      # root solution patch (default **/ MISSES this)
        "solution.cfg",        # root solution.* family
        "answer.json",         # root answer (default **/ MISSES this)
        "answers.json",        # root answers
        "solution/x.py",       # root solution/ dir
        "solutions/y.sql",     # root solutions/ dir
        "tests/expected/out.csv",
    ]:
        assert matches_denied_path(path, SWE_BENCH_PRO_DENY_GLOBS), path


def test_swe_leak_globs_do_not_overmatch_nested_repo_files():
    # CRITICAL false-positive guard. fnmatch's `*` crosses `/`; the curated set
    # is root-anchored so NONE of these legit NESTED repo files (django/astropy/
    # sympy ship them) are stripped — incl. the captain-named answer_engine etc.
    for path in [
        "src/answer_engine.py",
        "lib/myanswers.py",
        "pkg/solution_helpers.py",
        "src/solution_loader.py",
        "config/answers_schema.json",
        "docs/gold_notes.md",
        "tests/fixtures/gold_case.py",
        "tests/gold_helper.py",
        "tests/test_patch_helpers.py",
        "a/test_patch/file.py",
        "src/test_patcher.py",
        "astropy/io/tests/test_patch_io.py",
        "django/test/patches.py",
        "lib/patch.py",
        "src/patches/apply.py",
        "docs/changelog.diff",
        "docs/patch_notes.md",
        "tools/gold_standard.py",
        "app/buggy.py",
        "README.md",
        "tests/test_app.py",
    ]:
        assert not matches_denied_path(path, SWE_BENCH_PRO_DENY_GLOBS), path


def test_materialized_swe_view_strips_root_answers_keeps_nested_repo_leak(tmp_path):
    # AC-1: materialize fixture-001 with the curated SWE set; root answer files
    # stripped, the legit NESTED repo file survives, fail-closed gate quiet.
    source = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    view = materialize_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        benchmark_kind="swe-bench-pro",
        benchmark_task_id=source.name,
        transform_name="swe-bench-pro-harbor-task-view",
        exclude_globs=SWE_BENCH_PRO_DENY_GLOBS,
        view_mode="copy",
    )
    # root answer artifacts did NOT survive
    assert not (view / "gold" / "gold_patch.diff").exists()
    assert not (view / "test_patch.diff").exists()
    assert not (view / "FAIL_TO_PASS.json").exists()
    assert not (view / "solution" / "gold_patch.diff").exists()  # solution/** holds
    # the legit NESTED repo file the agent MUST see DID survive (the inherited
    # default's **/answer* would have wrongly stripped this; standalone fixes it)
    assert (view / "src" / "answer_engine.py").is_file()
    # no denied file survives anywhere; fail-closed gate does not raise
    survivors = [
        p.relative_to(view).as_posix()
        for p in view.rglob("*")
        if p.is_file()
        and matches_denied_path(
            p.relative_to(view).as_posix(), SWE_BENCH_PRO_DENY_GLOBS
        )
    ]
    assert survivors == [], survivors
    assert_no_denied_paths(view, deny_globs=SWE_BENCH_PRO_DENY_GLOBS)  # no raise


def _swe_spec():
    return Spec(
        version=1,
        experiment="swe-bench-pro-leakage-smoke",
        agent=NopAgentBlock(kind="nop"),
        benchmark=HarborBenchmarkBlock(
            kind="harbor", dataset="scale-ai/swe-bench-pro@latest"
        ),
        trials=1,
        observers=[],
    )


def _plant_swe_leakage(source: Path) -> None:
    """Plant task-root answer files the REVERT baseline does NOT catch (so the
    revert half truly leaks). Verified at plan time."""
    (source / "gold").mkdir(exist_ok=True)
    (source / "gold" / "gold_patch.diff").write_text("+return 42\n")
    (source / "test_patch.diff").write_text("+assert buggy() == 42\n")
    (source / "FAIL_TO_PASS.json").write_text('["test_returns_42"]\n')
    (source / "patch.diff").write_text("+return 42\n")
    (source / "solution.patch").write_text("+return 42\n")


def test_planted_swe_answers_are_excluded_from_view_leak(tmp_path, monkeypatch):
    # AC-2 (forward): plant task-root answer files in an ISOLATED source copy,
    # run the FULL production path, assert none survive into the view.
    base = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    source = tmp_path / "src_copy" / "swe-bench-pro-fixture-001"
    shutil.copytree(base, source)
    _plant_swe_leakage(source)

    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks", lambda **k: [source]
    )
    job_config, _ = spec_to_job_config(
        _swe_spec(), job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    view = job_config.tasks[0].path
    for rel in [
        "gold/gold_patch.diff", "test_patch.diff", "FAIL_TO_PASS.json",
        "patch.diff", "solution.patch",
    ]:
        assert not (view / rel).exists(), rel
    survivors = [
        p.relative_to(view).as_posix()
        for p in view.rglob("*")
        if p.is_file()
        and matches_denied_path(
            p.relative_to(view).as_posix(), SWE_BENCH_PRO_DENY_GLOBS
        )
    ]
    assert survivors == [], survivors


def test_reverting_swe_globs_leaks_planted_answers_leak(tmp_path, monkeypatch):
    # AC-2 (revert / load-bearing): with the swe answer-artifact globs REMOVED
    # (revert baseline = root solution/answer-dir family only), the planted
    # task-root answers SURVIVE (proving the SWE answer-artifact globs are
    # load-bearing), and the curated SWE set WOULD reject that leaked view.
    base = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    source = tmp_path / "src_copy" / "swe-bench-pro-fixture-001"
    shutil.copytree(base, source)
    _plant_swe_leakage(source)

    view = materialize_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        benchmark_kind="swe-bench-pro",
        benchmark_task_id=source.name,
        transform_name="swe-bench-pro-harbor-task-view",
        exclude_globs=_REVERT_BASELINE,  # REVERTED (answer-artifact globs removed)
        view_mode="copy",
    )
    # the planted answer files LEAK through the revert baseline
    assert (view / "gold" / "gold_patch.diff").is_file()
    assert (view / "test_patch.diff").is_file()
    assert (view / "FAIL_TO_PASS.json").is_file()
    assert (view / "patch.diff").is_file()
    assert (view / "solution.patch").is_file()
    # the curated (production) SWE set WOULD reject the leaked view
    with pytest.raises(LeakageError):
        assert_no_denied_paths(view, deny_globs=SWE_BENCH_PRO_DENY_GLOBS)


def test_swe_branch_passes_curated_exclude_globs_leak(tmp_path, monkeypatch):
    # AC-3: spy on materialize_harbor_task_view to capture the exclude_globs the
    # PRODUCTION swe branch passes; assert it is the curated SWE set, not the
    # bare default. Mirrors how E1 proves the branch supplies environment_env.
    base = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    source = tmp_path / "src_copy" / "swe-bench-pro-fixture-001"
    shutil.copytree(base, source)

    captured = {}
    real = materialize_harbor_task_view

    def spy(**kwargs):
        captured["exclude_globs"] = kwargs.get("exclude_globs")
        return real(**kwargs)

    monkeypatch.setattr("razorback.translate.materialize_harbor_task_view", spy)
    monkeypatch.setattr(
        "razorback.translate._resolve_harbor_dataset_tasks", lambda **k: [source]
    )
    spec_to_job_config(
        _swe_spec(), job_name="job", jobs_dir=tmp_path, tasks_root=tmp_path / "tasks"
    )
    assert captured["exclude_globs"] == SWE_BENCH_PRO_DENY_GLOBS
    assert captured["exclude_globs"] != DEFAULT_SOLUTION_DENY_GLOBS


def test_swe_branch_wiring_grep_leak():
    # AC-3 (static): the swe branch source literally passes the curated set.
    src = (
        Path(__file__).parent.parent.parent
        / "src" / "razorback" / "translate.py"
    ).read_text()
    assert "exclude_globs=SWE_BENCH_PRO_DENY_GLOBS" in src
