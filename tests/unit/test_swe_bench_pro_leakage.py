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
