# tests/unit/test_swe_bench_pro_leakage.py
# ABOUTME: AC-1/AC-2/AC-3 — swe-bench-pro gold/test-patch leakage deny-globs.
# ABOUTME: fnmatch's `*` crosses `/`, so the SWE set is a STANDALONE curated,
# ABOUTME: task-root-scoped tuple — it does NOT inherit the default's broad **/ globs.
from razorback.harbor_tasks.leakage import (
    DEFAULT_SOLUTION_DENY_GLOBS,
    SWE_BENCH_PRO_DENY_GLOBS,
    matches_denied_path,
)


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


from pathlib import Path

from razorback.harbor_tasks.leakage import assert_no_denied_paths
from razorback.harbor_tasks.materialize import materialize_harbor_task_view

FIXTURE_ROOT = (
    Path(__file__).parent.parent
    / "fixtures" / "swe_bench_pro" / "harbor_task_minimal"
)


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
