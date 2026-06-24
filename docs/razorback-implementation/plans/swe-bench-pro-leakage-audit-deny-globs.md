# swe-bench-pro Leakage Deny-Globs (gold/test-patch isolation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the swe-bench-pro task-view materializer a STANDALONE, curated, task-root-scoped deny-glob set so a resolved task's gold patch / test patch / FAIL_TO_PASS answer artifacts (which sit at the task root next to the repo checkout, NOT inside it) never reach the agent — WITHOUT stripping legitimate nested files in the repo the agent edits — and prove the exclusion is fail-closed with a load-bearing negative leakage test.

**Architecture:** swe-bench-pro rides the GENERIC `materialize_harbor_task_view` (design doc Architecture decision — *no* benchmark-specific view transform, unlike spider2's `harbor_view.py` wrapper). E1 wired the swe branch in `_build_harbor` to call the generic materializer WITHOUT `exclude_globs` (so it uses `DEFAULT_SOLUTION_DENY_GLOBS`). E2 adds a swe-specific constant `SWE_BENCH_PRO_DENY_GLOBS` in `leakage.py` (next to the default, NOT a new `harbor_view.py`) that is a **standalone curated tuple — NOT `DEFAULT_SOLUTION_DENY_GLOBS + (...)`** — and wires the swe branch to pass it as `exclude_globs=`. The fail-closed mechanism (`assert_no_denied_paths`, already called inside the materializer) is reused unchanged.

**Tech Stack:** Python 3, `fnmatch`-based glob matching (`harbor_tasks/leakage.py`), `uv run pytest`, existing E1 fixture tree under `tests/fixtures/swe_bench_pro/`.

## CRITICAL: fnmatch semantics + why the set is STANDALONE (the root-cause constraint)

`matches_denied_path` uses `fnmatch.fnmatch(rel_posix, pattern)` (`src/razorback/harbor_tasks/leakage.py:21-23`). **`fnmatch`'s `*` CROSSES `/`** — it is NOT path-segment globbing. Two load-bearing consequences (reproduce with `python -c 'import fnmatch; ...'`):

1. **Broad cross-`/` globs OVER-MATCH legitimate nested repo files.** The shared `DEFAULT_SOLUTION_DENY_GLOBS` (`leakage.py:7-14`) contains `**/answer*`, `**/solution.*`, `**/*answers*` — and because `*` crosses `/`, `**/answer*` strips `src/answer_engine.py`, `lib/myanswers.py`; `**/solution.*` strips `pkg/solution.cfg`; `**/*answers*` strips `config/myanswers_schema.json`. swe-bench-pro tasks ARE real repos (django, astropy, sympy, …) that legitimately ship such files. **Therefore the SWE set is a STANDALONE curated tuple — it does NOT inherit the default's broad cross-`/` globs.** It keeps only the ROOT-ANCHORED members of the solution/answer family plus root-anchored SWE answer artifacts.
2. **`**/<pat>` MISSES the top level.** `**/solution.*` etc. also do not match a TOP-LEVEL `solution.patch`/`answer.json` (the `**/` needs a leading path segment). The curated set therefore uses root-anchored forms (`solution.*`, `answer*`, `answers*`) which DO match the task-root answer files and CANNOT match nested repo files.

**Why root-anchored is safe + sufficient:** the gold/test patch are task-root **answer artifacts** — siblings of the repo checkout, not files inside it (the E1 fixture already models this with `solution/gold_patch.diff` at the task root). A root-anchored glob (`answer*`, no `/`) matches `answer.json` at the task root but cannot match `src/answer_engine.py`. This targets the answers precisely without reaching into the repo.

## Global Constraints

- **`SWE_BENCH_PRO_DENY_GLOBS` is a STANDALONE curated tuple, NOT `DEFAULT_SOLUTION_DENY_GLOBS + (...)`.** Do not inherit the default's broad cross-`/` globs (`**/answer*`, `**/solution.*`, `**/*answers*`) — they strip legitimate nested repo files. (Contrast spider2/ade, which DO use `DEFAULT + (...)` because their trees are controlled, not arbitrary repos.)
- **Curated members (all task-root-scoped):**
  - root solution/answer family: `solution/**`, `solutions/**`, `tests/expected/**`, `solution.*`, `answer*`, `answers*`
  - swe answer artifacts (task-root): `gold/**`, `gold_patch*`, `gold.patch`, `test_patch*`, `FAIL_TO_PASS*`, `PASS_TO_PASS*`, `patch`, `patch.diff`, `solution.patch`
- Use NO broad `**/<token>*` / `**/<token>` globs — they over-match the repo checkout (CRITICAL above).
- Do NOT mutate the shared `DEFAULT_SOLUTION_DENY_GLOBS` (spider2/ade/dabstep depend on it). The SWE set is independent.
- The defense is the materializer's path-based exclusion (`assert_no_denied_paths`, `harbor_tasks/leakage.py:26-44`), NOT `rk audit`. Do NOT add trace-level `rk audit` SWE signatures — out of scope (entity Out of scope; `audit/cli.py:79-92` only taints `forbidden_lookup`).
- Reuse E1's fixture tree (`tests/fixtures/swe_bench_pro/harbor_task_minimal/`); do not invent a new fixture root.
- All tests fixture-backed and network-free (monkeypatch `_resolve_harbor_dataset_tasks`, as the E1 tests do).
- Acceptance command (entity Test plan): `uv run pytest tests/ -k 'swe_bench_pro and leak'`.

---

## Captain decisions to flag (open)

Captain has decided the scope (standalone curated set, decision relayed). Remaining captain-verifiable items:

1. **The exact harbor answer filenames (Task 0 assumption).** The set is DERIVED from the SWE-bench-Pro instance format — gold `patch`, `test_patch`, `FAIL_TO_PASS`/`PASS_TO_PASS` — serialized by harbor as sibling files at the task root. We CANNOT hydrate `scale-ai/swe-bench-pro` to confirm exact filenames. **ASSUMPTION:** harbor lands them at the task root as `gold/`, `gold_patch.diff`/`gold.patch`, `test_patch.diff`, `FAIL_TO_PASS.json`, `PASS_TO_PASS.json`, and/or `patch`/`patch.diff`/`solution.patch`/`answer*`. If harbor's real filenames differ, Task 0 records the gap and the captain amends the root-anchored names before merge.
2. **`*.patch` / `*.diff` false-positive judgement (explicit).** The design doc (`:70-74`) calls out `*.patch` coverage. A blanket `**/*.patch` / `**/*.diff` would strip legitimate `.patch`/`.diff` fixtures real repos ship (`docs/changelog.diff`, `lib/patches/*.patch`). **Decision: add NO `**/*.patch` / `**/*.diff`.** Cover only the root-anchored answer names (`patch`, `patch.diff`, `gold.patch`, `solution.patch`, `gold_patch*`, `test_patch*`).
3. **Root-token collision residual (ALL collisions named).** The root-anchored token globs deny a TOP-LEVEL repo file whose name starts with these prefixes. Because they are root-anchored (one path segment, no `/`), they CANNOT match any nested path — the collision surface is ONLY the repo's top-level directory. The full list of files that WOULD be denied if they existed at the task root (acceptable — answer data overwhelmingly lives there, repo source rarely does):
   - `answer*` → root `answer.json`, `answers.json`, AND a hypothetical root `answer_engine.py`
   - `answers*` → root `answers_schema.json` and similar
   - `gold_patch*` → root `gold_patch.diff` AND a hypothetical root `gold_patch_notes.md`
   - `test_patch*` → root `test_patch.diff` AND a hypothetical root `test_patch_helpers.py`
   - `gold.patch` / `solution.patch` / `solution.*` → root `solution.cfg` etc.
   - `FAIL_TO_PASS*` / `PASS_TO_PASS*` → root `FAIL_TO_PASS.json`/`PASS_TO_PASS.json` AND hypothetical root `FAIL_TO_PASS_notes.md`/`PASS_TO_PASS_notes.md`
   - `patch` / `patch.diff` → a root file literally named `patch` (Unix-tool name, not typical repo content)
   NESTED versions of every one of these (`src/answer_engine.py`, `tests/test_patch_helpers.py`, `tools/gold_patch_notes.md`, `a/test_patch/file.py`) are NOT denied — proven in the allow-list test. Captain may narrow `answer*`→`answer.json` if a real task root collides.
4. **Escalation hook (design doc E2).** IF Task 0 (or captain knowledge) shows the gold/test patch is NOT a sibling file but lives **inline** in `task.toml` / verifier metadata / an env var, path globs cannot strip it. The plan does NOT silently build a view transform — Task 0 HALTS and surfaces: "swe-bench-pro gold/test patch is inline, not a sibling file; path globs insufficient — captain decision needed (defense-in-depth audit layer or a view content transform, both out of E2 scope)."

### Separate observation (FLAG ONLY — out of E2 scope)

The shared `DEFAULT_SOLUTION_DENY_GLOBS` RETAINS the broad cross-`/` globs (`**/answer*`, `**/solution.*`, `**/*answers*`) for spider2/ade/dabstep. Those run on CONTROLLED task trees (curated dbt projects, not arbitrary repos), so the over-match risk is low there. **But the default is over-broad for ANY future repo-based benchmark** — a possible follow-up entity should curate the default or document the repo-vs-controlled-tree distinction. E2 does NOT touch the shared default; this is flagged, not fixed.

---

## AC ↔ Task map

| Acceptance criterion | Task(s) | TDD checkpoint (failing test first) |
| --- | --- | --- |
| (probe, Test plan) Probe the resolved-task shape, DERIVE the curated set, commit as evidence | Task 0 | n/a — committed probe note that DRIVES the Task 1 set + records the assumption/escalation |
| **AC-1** — materialized swe view excludes gold/test-patch/answer paths AND keeps legit nested repo files | Task 1 (standalone tuple + deny/allow fnmatch tests), Task 2 (positive materialize test) | Task 1 Step 1 (deny+allow tests) and Task 2 Step 1 (materialize) → fail before the constant + wiring exist |
| **AC-2** — negative leakage test FAILS when swe answer-artifact globs reverted | Task 3 (wire branch) + Task 4 (negative leakage test, load-bearing) | Task 4 Step 1: plant task-root answer files → materialize via swe branch → assert excluded; revert (answer-artifact globs removed) → assert they survive / no `LeakageError` → fails without Task 1+Task 3 |
| **AC-3** — the swe branch actually passes the curated `exclude_globs` | Task 3 (wire) + Task 5 (runtime spy + `grep -F`) | Task 5 Step 1 → fails before Task 3 |

**Riskiest-first ordering rationale:** The load-bearing proof is the **negative leakage test (Task 4)** — plant → materialize → assert excluded → revert globs → assert leak. The planted task-root answer files are chosen so the **revert baseline** (the curated set with the SWE answer-artifact globs removed, leaving only `solution/**`/`solutions/**`/`tests/expected/**`) does NOT catch them (verified at plan time), so reverting genuinely leaks. Tasks are ordered so the deny set (Task 1) and production wiring (Task 3) exist before Task 4 exercises them. Task 0 runs first because it derives the set and can trigger the escalation HALT.

---

## File Structure

- **Modify** `src/razorback/harbor_tasks/leakage.py` — add `SWE_BENCH_PRO_DENY_GLOBS` STANDALONE tuple (Task 1). Lives here (not a new `benchmarks/swe_bench_pro/harbor_view.py`) because the design doc mandates swe uses the GENERIC materializer with no benchmark-specific transform; the constant is the *only* swe-specific artifact, so it belongs beside `DEFAULT_SOLUTION_DENY_GLOBS`.
- **Modify** `src/razorback/translate.py` — swe branch in `_build_harbor` (currently lines ~412-433) passes `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS` and imports it (Task 3).
- **Modify** `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/` — add task-root SWE answer files + one legit NESTED repo file (Task 2): root `gold/gold_patch.diff`, root `test_patch.diff`, root `FAIL_TO_PASS.json`, and `src/answer_engine.py` (legit nested — proves non-overmatch). (fixture-002 left as-is for the multi-instance E1 tests.)
- **Create** `tests/unit/test_swe_bench_pro_leakage.py` — the swe deny/allow unit tests, positive materialize test, negative leakage test, and AC-3 wiring assertion (Tasks 1, 2, 4, 5). New file; every test name contains `leak` to match the entity's `-k 'swe_bench_pro and leak'` acceptance filter.

---

### Task 0: Probe the resolved swe-bench-pro task shape — DERIVE the curated set (evidence + escalation gate)

**Files:**
- Create: `docs/razorback-implementation/plans/swe-bench-pro-leakage-probe-note.md` (committed evidence)

**Interfaces:**
- Produces: the DERIVED standalone curated Task 1 glob set + a documented decision — either "answer artifacts are task-root sibling files, proceed" OR "gold/test patch is inline → HALT + captain decision".

Network-free (entity constraint). Records what is knowable offline, derives the curated set from the SWE answer-field format + the task-root-layout fact, pins the assumption. **The glob set is OUTPUT of this task — Task 1 implements what Task 0 derives.**

- [ ] **Step 1: Reproduce the fnmatch evidence that drives the curated (not inherited) set**

Run:

```bash
uv run python -c "
import fnmatch
print('=== why we DROP the default broad cross-/ globs: they strip nested repo files ===')
for pat,p in [('**/answer*','src/answer_engine.py'),('**/answer*','lib/myanswers.py'),('**/solution.*','pkg/solution.cfg'),('**/*answers*','config/myanswers_schema.json')]:
    print(fnmatch.fnmatch(p, pat), repr(pat), repr(p), '<- legit nested repo file STRIPPED by inherited default')
print('=== root-anchored answer* is SAFE: cannot match nested ===')
for pat,p in [('answer*','src/answer_engine.py'),('answer*','answer.json')]:
    print(fnmatch.fnmatch(p, pat), repr(pat), repr(p))
"
```

Expected: the `**/...` rows print `True` (the inherited default WOULD strip nested repo files — why E2 curates a standalone set); `answer*` vs `src/answer_engine.py` prints `False` (root-anchored is safe) and `answer*` vs `answer.json` prints `True` (still catches the task-root answer).

- [ ] **Step 2: Derive the standalone curated set + record the assumption/escalation**

Write `swe-bench-pro-leakage-probe-note.md` documenting:
- (a) SWE-bench-Pro instance format: gold `patch`, `test_patch`, `FAIL_TO_PASS`/`PASS_TO_PASS` lists.
- (b) KEY fact: harbor lands these as sibling files at the TASK ROOT (like E1's `solution/gold_patch.diff`), NOT inside the repo checkout the agent edits → the set is task-root-scoped, standalone, never inherits the default's broad cross-`/` globs.
- (c) The derived STANDALONE set (this becomes Task 1): `solution/**`, `solutions/**`, `tests/expected/**`, `solution.*`, `answer*`, `answers*`, `gold/**`, `gold_patch*`, `gold.patch`, `test_patch*`, `FAIL_TO_PASS*`, `PASS_TO_PASS*`, `patch`, `patch.diff`, `solution.patch`.
- (d) The captain-verifiable assumption (exact filenames, decision 1) and the full root-token collision list (decision 3).
- (e) The escalation decision: patches are root sibling files → path globs are the right defense → proceed. IF a future hydration shows the patch is inline, that is the captain escalation (decision 4), NOT an E2 code change.

- [ ] **Step 3: Commit**

```bash
git add docs/razorback-implementation/plans/swe-bench-pro-leakage-probe-note.md
git commit -m "plan(E2): probe swe leakage shape; derive STANDALONE curated glob set"
```

---

### Task 1: Add the STANDALONE `SWE_BENCH_PRO_DENY_GLOBS` curated tuple

**Files:**
- Modify: `src/razorback/harbor_tasks/leakage.py:7-14` (add constant after `DEFAULT_SOLUTION_DENY_GLOBS`)
- Test: `tests/unit/test_swe_bench_pro_leakage.py` (created here)

**Interfaces:**
- Produces: `SWE_BENCH_PRO_DENY_GLOBS: tuple[str, ...]` exported from `razorback.harbor_tasks.leakage`, a STANDALONE curated tuple (NOT derived from the default). Consumed by Task 3's `_build_harbor` swe branch and Tasks 2/4/5 tests.

- [ ] **Step 1: Write the failing deny + allow tests**

Create `tests/unit/test_swe_bench_pro_leakage.py` (file + every test name contains `leak`):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -v`
Expected: FAIL with `ImportError: cannot import name 'SWE_BENCH_PRO_DENY_GLOBS'`.

- [ ] **Step 3: Add the constant**

In `src/razorback/harbor_tasks/leakage.py`, after the `DEFAULT_SOLUTION_DENY_GLOBS` tuple (line 14), add:

```python
# swe-bench-pro ships the gold patch + test patch + FAIL_TO_PASS/PASS_TO_PASS
# answer artifacts at the TASK ROOT (siblings of the repo checkout, NOT inside
# the repo the agent edits).
#
# This is a STANDALONE curated tuple, NOT `DEFAULT_SOLUTION_DENY_GLOBS + (...)`
# (captain decision). `matches_denied_path` uses `fnmatch.fnmatch` (leakage.py:
# 21-23) where `*` CROSSES `/`, so the default's broad cross-`/` globs
# (`**/answer*`, `**/solution.*`, `**/*answers*`) would strip LEGITIMATE nested
# repo files (`src/answer_engine.py`, `lib/myanswers.py`, `pkg/solution.cfg`)
# that real SWE repos (django/astropy/sympy) ship — corrupting the task. We
# therefore curate only ROOT-ANCHORED globs (one path segment, no `**/`): they
# match the task-root answer files and CANNOT reach into the repo checkout.
#
# We add NO `**/*.patch` / `**/*.diff` for the same false-positive reason
# (design-doc `*.patch` coverage is satisfied by the root-anchored
# `patch`/`patch.diff`/`gold.patch`/`solution.patch` names).
#
# Root-token collision residual: a TOP-LEVEL repo file named `answer*`,
# `gold_patch*`, `test_patch*`, `patch`, etc. would be denied (acceptable —
# answer data lives at the task root, repo source rarely does); their NESTED
# forms are NOT denied. The shared DEFAULT is left untouched.
SWE_BENCH_PRO_DENY_GLOBS = (
    # root solution/answer family (root-anchored; NOT the default's `**/` forms)
    "solution/**",
    "solutions/**",
    "tests/expected/**",
    "solution.*",
    "answer*",
    "answers*",
    # swe answer artifacts at the task root
    "gold/**",
    "gold_patch*",
    "gold.patch",
    "test_patch*",
    "FAIL_TO_PASS*",
    "PASS_TO_PASS*",
    "patch",
    "patch.diff",
    "solution.patch",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -v`
Expected: PASS (3 tests — standalone/deny/allow).

- [ ] **Step 5: Commit**

```bash
git add src/razorback/harbor_tasks/leakage.py tests/unit/test_swe_bench_pro_leakage.py
git commit -m "feat(leakage): add STANDALONE curated SWE_BENCH_PRO_DENY_GLOBS"
```

---

### Task 2: Plant task-root SWE answer fixtures + positive materialize test (AC-1)

**Files:**
- Modify: `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/` (add root answer files + a legit NESTED repo file)
- Test: `tests/unit/test_swe_bench_pro_leakage.py` (append)

**Interfaces:**
- Consumes: `SWE_BENCH_PRO_DENY_GLOBS` (Task 1); `materialize_harbor_task_view`, `assert_no_denied_paths` (`harbor_tasks/materialize.py:26`, `leakage.py:26`).
- Produces: a fixture-001 tree carrying root SWE answer files + `src/answer_engine.py`, used by Task 4's negative test too.

The E1 fixture only has `solution/gold_patch.diff`. Add task-root answer shapes plus a legit NESTED file the curated set must NOT strip — `src/answer_engine.py` is the captain-named over-match case, so it proves the standalone set fixed the inheritance bug end-to-end.

- [ ] **Step 1: Add task-root answer files + a legit nested repo file to fixture-001**

Create these committed files under `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/`:

`gold/gold_patch.diff`:
```
--- a/app/buggy.py
+++ b/app/buggy.py
@@ -1 +1 @@
-return None
+return 42
```

`test_patch.diff`:
```
--- a/tests/test_buggy.py
+++ b/tests/test_buggy.py
@@ -0,0 +1,2 @@
+def test_returns_42():
+    assert buggy() == 42
```

`FAIL_TO_PASS.json`:
```
["tests/test_buggy.py::test_returns_42"]
```

`src/answer_engine.py` (a legit NESTED repo file the agent MUST see — the captain-named over-match case; the inherited default's `**/answer*` would have stripped it, the standalone set must NOT):
```
def answer_engine():
    return "legit repo module, not an answer key"
```

(Leave the existing `solution/gold_patch.diff`, `instruction.md`, `task.toml`, `environment/Dockerfile` untouched.)

- [ ] **Step 2: Write the positive materialize test**

Append to `tests/unit/test_swe_bench_pro_leakage.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest "tests/unit/test_swe_bench_pro_leakage.py::test_materialized_swe_view_strips_root_answers_keeps_nested_repo_leak" -v`
Expected: PASS. (Passes once Task 1's constant exists — calls the materializer directly; Tasks 4/5 prove the wiring.)

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001 tests/unit/test_swe_bench_pro_leakage.py
git commit -m "test(leakage): swe view strips root answers, keeps nested repo files (AC-1)"
```

---

### Task 3: Wire the swe `_build_harbor` branch to pass `SWE_BENCH_PRO_DENY_GLOBS` (AC-3 production wiring)

**Files:**
- Modify: `src/razorback/translate.py` — import (top, near line 12-20) + swe branch `materialize_harbor_task_view(...)` call (lines ~419-433)

**Interfaces:**
- Consumes: `SWE_BENCH_PRO_DENY_GLOBS` (Task 1).
- Produces: the production swe branch now passes `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS`. Tasks 4 and 5 assert this.

- [ ] **Step 1: Add the import**

In `src/razorback/translate.py`, the existing import block already imports `materialize_harbor_task_view` (line 20). First locate the sibling import:

Run: `grep -n "harbor_tasks.leakage\|harbor_tasks.materialize" src/razorback/translate.py`

Then add this line beside the `materialize` import (line 20):

```python
from razorback.harbor_tasks.leakage import SWE_BENCH_PRO_DENY_GLOBS
```

- [ ] **Step 2: Pass `exclude_globs` in the swe branch**

In the swe-bench-pro `else` branch of `_build_harbor` (currently `translate.py:419-433`), add `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS,` and update the now-stale comment. The block becomes:

```python
            else:
                # swe-bench-pro uses the GENERIC materializer directly — no
                # benchmark-specific view transform (design doc Architecture
                # decision). The BRANCH passes environment_env (merged into the
                # view's task.toml) AND the STANDALONE curated deny set
                # SWE_BENCH_PRO_DENY_GLOBS (task-root gold patch / test patch /
                # FAIL_TO_PASS answer artifacts; root-anchored so it never
                # strips the repo checkout the agent edits — E2).
                task_paths = [
                    materialize_harbor_task_view(
                        source_task_dir=src,
                        view_root=view_root,
                        benchmark_kind="swe-bench-pro",
                        benchmark_task_id=src.name,
                        transform_name="swe-bench-pro-harbor-task-view",
                        environment_env={
                            "RAZORBACK_BENCHMARK_KIND": "swe-bench-pro",
                            "RAZORBACK_BENCHMARK_TASK_ID": src.name,
                        },
                        exclude_globs=SWE_BENCH_PRO_DENY_GLOBS,
                        view_mode=view_mode,
                    )
                    for src in selected_sources
                ]
```

- [ ] **Step 3: Run the E1 wiring suite to confirm no regression**

Run: `uv run pytest tests/unit/test_translate_swe_bench_pro.py -v`
Expected: PASS (all E1 tests still green — `test_swe_resolves_n_views_with_manifest_leakage_clean` still passes because the curated set includes `solution/**`).

- [ ] **Step 4: Commit**

```bash
git add src/razorback/translate.py
git commit -m "feat(translate): swe-bench-pro branch passes SWE_BENCH_PRO_DENY_GLOBS (AC-3)"
```

---

### Task 4: Negative leakage test — plant → materialize → assert excluded → revert → assert leaks (AC-2, load-bearing)

**Files:**
- Test: `tests/unit/test_swe_bench_pro_leakage.py` (append)

**Interfaces:**
- Consumes: `SWE_BENCH_PRO_DENY_GLOBS`, `LeakageError` (`leakage.py:17`); `spec_to_job_config`, `HarborBenchmarkBlock`, `NopAgentBlock`, `Spec` (mirroring E1 test imports `test_translate_swe_bench_pro.py:8-15`).

The entity's load-bearing proof. It drives the FULL production path, mirroring spider2's `test_planted_forbidden_files_are_excluded_from_view`. **Since the SWE set is standalone, the revert baseline is the curated set with the SWE answer-artifact globs REMOVED — leaving only the root solution/answer-dir family (`solution/**`, `solutions/**`, `tests/expected/**`).** The planted task-root patch files are chosen so this revert baseline does NOT catch them (verified at plan time: `gold_patch.diff`, `test_patch.diff`, `FAIL_TO_PASS.json`, `patch.diff`, `solution.patch` all escape it — none lives under `solution/`), so reverting genuinely leaks.

- [ ] **Step 1: Write the test**

Append to `tests/unit/test_swe_bench_pro_leakage.py`:

```python
import shutil

import pytest

from razorback.harbor_tasks.leakage import LeakageError
from razorback.spec.schema import HarborBenchmarkBlock, NopAgentBlock, Spec
from razorback.translate import spec_to_job_config

# Revert baseline: the curated SWE set with the answer-ARTIFACT globs removed,
# leaving only the root solution/answer-DIR family. Simulates "before E2 added
# the swe answer-artifact coverage". Verified at plan time: this baseline
# catches NONE of the planted task-root patch files.
_REVERT_BASELINE = ("solution/**", "solutions/**", "tests/expected/**")


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
```

- [ ] **Step 2: Run the tests to verify both pass (after the fix)**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -k leak -v`
Expected: PASS. Forward test passes (Task 3 wired the curated set into production); revert test passes (the revert baseline lets the planted task-root answers survive AND the curated set raises on them).

- [ ] **Step 3: Prove the test is load-bearing (manual sanity, do NOT commit the revert)**

Temporarily edit `leakage.py` so `SWE_BENCH_PRO_DENY_GLOBS = ("solution/**", "solutions/**", "tests/expected/**")` (drop the answer-artifact globs), then run:

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -k leak -v`
Expected: `test_planted_swe_answers_are_excluded_from_view_leak` FAILS (planted task-root answers now survive in production) and `test_reverting_swe_globs_leaks_planted_answers_leak`'s `pytest.raises(LeakageError)` FAILS (curated set no longer raises). Confirms load-bearing. **Revert the edit** (`git checkout src/razorback/harbor_tasks/leakage.py`) and re-run green before committing.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_swe_bench_pro_leakage.py
git commit -m "test(leakage): negative swe leakage proof — revert globs => leak (AC-2)"
```

---

### Task 5: AC-3 wiring assertion — the branch passes the curated set, not the default

**Files:**
- Test: `tests/unit/test_swe_bench_pro_leakage.py` (append)

**Interfaces:**
- Consumes: `SWE_BENCH_PRO_DENY_GLOBS`, `DEFAULT_SOLUTION_DENY_GLOBS`, `materialize_harbor_task_view` (for the spy), `spec_to_job_config`.

AC-3 demands proof the PRODUCTION swe branch passes the curated `exclude_globs`. Two independent checks: a runtime spy + a static `grep -F`.

- [ ] **Step 1: Write the test (runtime spy + static grep)**

Append to `tests/unit/test_swe_bench_pro_leakage.py`:

```python
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
```

- [ ] **Step 2: Run to verify it passes (after Task 3)**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -k leak -v`
Expected: PASS — the spy captures `SWE_BENCH_PRO_DENY_GLOBS` and the grep finds the literal wiring.

- [ ] **Step 3: Static grep cross-check (command, for the report)**

Run: `grep -F 'exclude_globs=SWE_BENCH_PRO_DENY_GLOBS' src/razorback/translate.py`
Expected: one matching line in the swe branch.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_swe_bench_pro_leakage.py
git commit -m "test(translate): assert swe branch passes curated exclude_globs (AC-3)"
```

---

### Task 6: Full acceptance run + verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entity's acceptance command**

Run: `uv run pytest tests/ -k 'swe_bench_pro and leak' -v`
Expected: all tests in `test_swe_bench_pro_leakage.py` PASS (every test name contains `leak`). Record the pass count.

- [ ] **Step 2: Run the broader swe + leakage suites for regression**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py tests/unit/test_translate_swe_bench_pro.py tests/unit/test_spider2_dbt_harbor_view.py -v`
Expected: all PASS — confirms E1 wiring untouched and spider2 deny-glob proof unaffected (shared default unchanged).

- [ ] **Step 3: No-commit verification gate**

Confirm `git status` shows a clean tree and `grep -F 'exclude_globs=SWE_BENCH_PRO_DENY_GLOBS' src/razorback/translate.py` returns the wiring line. Do not claim completion without these two observed.

---

## Self-Review

**1. Spec coverage:**
- AC-1 → Task 1 (standalone tuple + deny/allow tests) + Task 2 (positive materialize, keeps `src/answer_engine.py`). ✓
- AC-2 → Task 4; planted files verified to escape the revert baseline (`solution/**`/`solutions/**`/`tests/expected/**`) so revert genuinely leaks; Step 3 proves load-bearing. ✓
- AC-3 → Task 3 (wire) + Task 5 (runtime spy + `grep -F`). ✓
- Test plan: probe-then-harden → Task 0 (probe DRIVES the set) + Tasks 1/2/4/5. Acceptance `-k 'swe_bench_pro and leak'` → Task 6 Step 1. ✓
- Out of scope honored: NO `rk audit` SWE signatures; NO new view transform; escalation hook is a Task 0 HALT. ✓

**2. Captain decision (standalone curated set) applied:**
- `SWE_BENCH_PRO_DENY_GLOBS` is a STANDALONE tuple, NOT `DEFAULT + (...)`; `test_swe_leak_globs_are_standalone_not_default_superset` asserts the broad `**/answer*`/`**/solution.*`/`**/*answers*` are ABSENT and the set is not a default superset. ✓
- Dropped broad cross-`/` globs; allow-list test proves `src/answer_engine.py`, `lib/myanswers.py`, `pkg/solution_helpers.py` + the earlier set survive. ✓
- AC-2 revert baseline = answer-artifact globs removed; planted files verified to leak. ✓
- P2(a): captain-decision note lists ALL root-token collisions (`answer*`/`answers*`/`gold_patch*`/`test_patch*`/`gold.patch`/`solution.*`/`patch`) with the named hypothetical-root files. ✓
- P2(b): no `**/gold/**` exists in the final set; the stale cycle-1 "bare + nested" entity report line is corrected in the cycle-3 Stage Report. ✓
- Separate observation (default over-broad for future repo benchmarks) FLAGGED, not fixed. ✓

**3. fnmatch re-verification (deny + allow):** Run at plan time over the final standalone set — all deny paths match, all allow (legit nested repo) paths clean (incl. `src/answer_engine.py`), and all planted negative-test files escape the revert baseline. Evidence reproduced in Task 0 Step 1 and the Task 1 deny/allow tests.

**4. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step shows complete code; every run step shows command + expected output. ✓

**5. Type consistency:** `SWE_BENCH_PRO_DENY_GLOBS` named identically across Tasks 1-5. `matches_denied_path`, `assert_no_denied_paths`, `materialize_harbor_task_view`, `LeakageError` match `leakage.py`/`materialize.py`. `spec_to_job_config`/`HarborBenchmarkBlock`/`NopAgentBlock`/`Spec` match E1 test imports. Task 4 plants into an isolated tmp copy (`src_copy/`) so the committed fixture extras and planted extras overwrite identically — no collision. ✓
