# swe-bench-pro Leakage Deny-Globs (gold/test-patch isolation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the path deny-glob set the swe-bench-pro task-view materializer passes as `exclude_globs`, so a resolved swe-bench-pro task's gold patch / test patch / FAIL_TO_PASS-shaped answer files (which sit at the task root next to `task.toml`) never reach the agent — WITHOUT stripping legitimate files inside the repo checkout the agent edits — and prove the exclusion is fail-closed with a load-bearing negative leakage test.

**Architecture:** swe-bench-pro rides the GENERIC `materialize_harbor_task_view` (design doc Architecture decision — *no* benchmark-specific view transform, unlike spider2's `harbor_view.py` wrapper). E1 wired the swe branch in `_build_harbor` to call the generic materializer WITHOUT `exclude_globs` (so it uses `DEFAULT_SOLUTION_DENY_GLOBS`). E2 adds a swe-specific constant `SWE_BENCH_PRO_DENY_GLOBS` in `leakage.py` (next to the default, NOT a new `harbor_view.py`), extends the deny set for SWE answer artifacts, and wires the swe branch to pass it as `exclude_globs=`. The fail-closed mechanism (`assert_no_denied_paths`, already called inside the materializer) is reused unchanged.

**Tech Stack:** Python 3, `fnmatch`-based glob matching (`harbor_tasks/leakage.py`), `uv run pytest`, existing E1 fixture tree under `tests/fixtures/swe_bench_pro/`.

## CRITICAL: fnmatch semantics (the root-cause constraint)

`matches_denied_path` uses `fnmatch.fnmatch(rel_posix, pattern)` (`src/razorback/harbor_tasks/leakage.py:21-23`). **`fnmatch`'s `*` CROSSES `/`** — it is NOT path-segment globbing. Two load-bearing consequences every glob in this plan was re-verified against (reproduce with `python -c 'import fnmatch; ...'`):

1. **Broad token globs OVER-MATCH legitimate repo files.** `**/gold*` matches `docs/gold_notes.md` and `tests/fixtures/gold_case.py`; `**/test_patch*` matches `tests/test_patch_helpers.py` and `a/test_patch/file.py`. swe-bench-pro tasks ARE real repos (django, astropy, sympy, …) that legitimately ship such files. Stripping them corrupts the task and invalidates the benchmark. **This plan therefore uses NO broad `**/<token>*` forms for the SWE answer artifacts.** The gold/test patch are answer artifacts at the TASK ROOT (siblings of `task.toml`), so they are anchored at the root with bare forms.
2. **`**/<pat>` MISSES the top level.** `**/solution.*`, `**/answer*`, `**/*answers*` in the inherited `DEFAULT_SOLUTION_DENY_GLOBS` do NOT match a TOP-LEVEL `solution.patch` / `answer.json` / `answers.json` (the `**/` needs a leading path segment). The SWE set therefore adds bare top-level forms (swe-scoped) to close that hole — see Global Constraints.

## Global Constraints

- Do NOT mutate `DEFAULT_SOLUTION_DENY_GLOBS` — it is shared by spider2/ade/dabstep/generic harbor; widening it changes their behavior. Add a swe-specific constant that is `DEFAULT_SOLUTION_DENY_GLOBS + (...)`, mirroring `SPIDER2_DBT_DENY_GLOBS` (`benchmarks/spider2_dbt/harbor_view.py:20-31`) and `ADE_BENCH_DENY_GLOBS` (`benchmarks/ade_bench/harbor_view.py:16-18`).
- **Anchor SWE answer artifacts at the task root.** Because `*` crosses `/`, the only safe way to deny `gold_patch`/`test_patch`/`FAIL_TO_PASS`/`patch`/top-level `solution.patch`/`answer*` without over-matching repo contents is bare root-anchored forms (`gold_patch*`, `test_patch*`, `FAIL_TO_PASS*`, `patch`, `patch.diff`, `solution.patch`, `answer*`) plus `gold/**` for a root `gold/` answer dir. **Do NOT add `**/<token>*` token globs** — they strip legitimate repo files (see CRITICAL above).
- The inherited default `**/solution.*` / `**/answer*` MISSES top-level `solution.patch` / `answer.json`. The SWE set closes that hole with bare top-level forms; the shared default is NOT mutated (swe-scoped fix). Do NOT claim the default already covers the top-level solution/answer family — it does not.
- The defense is the materializer's path-based exclusion (`assert_no_denied_paths`, `harbor_tasks/leakage.py:26-44`), NOT `rk audit`. Do NOT add trace-level `rk audit` SWE signatures — out of scope (entity Out of scope; `audit/cli.py:79-92` only taints `forbidden_lookup`).
- Reuse E1's fixture tree (`tests/fixtures/swe_bench_pro/harbor_task_minimal/`); do not invent a new fixture root.
- All tests fixture-backed and network-free (monkeypatch `_resolve_harbor_dataset_tasks`, as the E1 tests do).
- Acceptance command (entity Test plan): `uv run pytest tests/ -k 'swe_bench_pro and leak'`.

---

## Captain decisions to flag (open)

The plan picks a justified default for each so implementation is unblocked; each is captain-overridable.

1. **The exact swe glob set + the harbor filename assumption.** The set (Task 1) is DERIVED from the SWE-bench-Pro instance format — each instance ships a gold `patch`, a `test_patch`, and `FAIL_TO_PASS`/`PASS_TO_PASS` test-name lists — serialized by harbor as **sibling files at the task root** (the same place the E1 fixture put `solution/gold_patch.diff`). We CANNOT hydrate `scale-ai/swe-bench-pro` to confirm the exact on-disk filenames. **ASSUMPTION (captain-verifiable):** harbor lands these answer artifacts at the task root as `gold_patch.diff` / `gold.patch` / a `gold/` dir, `test_patch.diff`, `FAIL_TO_PASS.json`, `PASS_TO_PASS.json`, and/or a plain `patch`/`patch.diff`/`solution.patch`/`answer*`. If harbor's real filenames differ, Task 0 records the gap and the captain amends the root-anchored names before merge. The set is intentionally root-anchored, NOT repo-wide, to avoid false positives (decision 2).
2. **`*.patch` / `*.diff` false-positive judgement (explicit).** The design doc (`:70-74`) calls out `*.patch` coverage. A blanket `**/*.patch` / `**/*.diff` would strip legitimate `.patch`/`.diff` fixtures real repos ship (e.g. `docs/changelog.diff`, `lib/patches/*.patch`) and corrupt the benchmark. **Decision: do NOT add any `**/*.patch` or `**/*.diff` glob.** Cover only the root-anchored answer names (`patch`, `patch.diff`, `gold.patch`, `solution.patch`, `gold_patch*`, `test_patch*`). If a probe ever shows harbor scatters answer patches deeper in the tree under a known answer dir, the captain may add a dir-anchored form (e.g. `<answerdir>/**`) — never a bare `**/*.patch`.
3. **`patch` / `answer*` bare-root residual risk (explicit).** Bare `patch` denies a root file literally named `patch` (rare in a repo root; `patch` is a Unix tool, not typical repo content). Bare `answer*` denies root `answer.json`/`answers.json` but would also deny a hypothetical root `answers.py`. These are root-anchored (a single path segment, no `/`), so they CANNOT match `src/answer.py` or `docs/patch_notes.md` — the false-positive surface is only the repo's TOP-LEVEL directory. Judged acceptable: a top-level file named `answer*`/`patch` in a SWE task root is overwhelmingly answer data, not repo source. Captain may narrow to exact names (`answer.json`, `answers.json`) if a real task root collides.
4. **Escalation hook (design doc E2).** IF Task 0 (or the captain's knowledge of harbor) shows the gold/test patch is NOT a sibling file but lives **inline** in `task.toml` / verifier metadata / an env var, path globs cannot strip it. The plan does NOT silently build a view transform — Task 0 HALTS and surfaces: "swe-bench-pro gold/test patch is inline, not a sibling file; path globs insufficient — captain decision needed (defense-in-depth audit layer or a view content transform, both out of E2 scope)."

---

## AC ↔ Task map

| Acceptance criterion | Task(s) | TDD checkpoint (failing test first) |
| --- | --- | --- |
| (probe, Test plan) Probe the resolved-task shape, derive the glob set, commit as evidence | Task 0 | n/a — committed probe note that DRIVES the Task 1 set + records the assumption/escalation |
| **AC-1** — materialized swe view excludes gold/test-patch/answer paths AND keeps legit repo files | Task 1 (constant + deny/allow fnmatch tests), Task 2 (positive materialize test) | Task 1 Step 1 (deny+allow tests) and Task 2 Step 1 (materialize) → fail before the constant + wiring exist |
| **AC-2** — negative leakage test FAILS when swe globs reverted | Task 3 (wire branch) + Task 4 (negative leakage test, load-bearing) | Task 4 Step 1: plant root answer files → materialize via swe branch → assert excluded; revert proof asserts they leak (planted files escape the bare default) → fails without Task 1+Task 3 |
| **AC-3** — the swe branch actually passes the extended `exclude_globs` | Task 3 (wire) + Task 5 (runtime spy + `grep -F`) | Task 5 Step 1 → fails before Task 3 |

**Riskiest-first ordering rationale:** The load-bearing proof is the **negative leakage test (Task 4)** — plant → materialize → assert excluded → revert globs → assert leak. It is the entity's AC-2 and the whole reason E2 exists. The planted answer files are chosen so the bare DEFAULT set does NOT catch them (verified at plan time), so reverting the SWE set genuinely leaks them. Tasks are ordered so the deny set (Task 1) and production wiring (Task 3) exist before Task 4 exercises them. Task 0 runs first because it derives the set and can trigger the escalation HALT.

---

## File Structure

- **Modify** `src/razorback/harbor_tasks/leakage.py` — add `SWE_BENCH_PRO_DENY_GLOBS` constant (Task 1). Lives here (not a new `benchmarks/swe_bench_pro/harbor_view.py`) because the design doc mandates swe uses the GENERIC materializer with no benchmark-specific transform; the constant is the *only* swe-specific artifact, so it belongs beside `DEFAULT_SOLUTION_DENY_GLOBS`.
- **Modify** `src/razorback/translate.py` — swe branch in `_build_harbor` (currently lines ~412-433) passes `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS` and imports it (Task 3).
- **Modify** `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/` — add root-anchored SWE answer files + one legit repo file (Task 2): a root `gold/gold_patch.diff`, a root `test_patch.diff`, a root `FAIL_TO_PASS.json`, and `app/buggy.py` (legit). (fixture-002 left as-is for the multi-instance E1 tests.)
- **Create** `tests/unit/test_swe_bench_pro_leakage.py` — the swe deny/allow unit tests, positive materialize test, negative leakage test, and AC-3 wiring assertion (Tasks 1, 2, 4, 5). New file; every test name contains `leak` to match the entity's `-k 'swe_bench_pro and leak'` acceptance filter.

---

### Task 0: Probe the resolved swe-bench-pro task shape — DERIVE the glob set (evidence + escalation gate)

**Files:**
- Create: `docs/razorback-implementation/plans/swe-bench-pro-leakage-probe-note.md` (committed evidence)

**Interfaces:**
- Produces: the DERIVED Task 1 glob set + a documented decision — either "answer artifacts are root-anchored sibling files, proceed with the derived set" OR "gold/test patch is inline, not a sibling file → HALT + captain decision".

This task does NOT hydrate the network dataset (entity: network-free; E1's live `harbor download` smoke was non-gating). It records what is knowable offline, derives the set from the SWE-bench answer-field format, and pins the assumption. **The glob set is OUTPUT of this task, not an input — Task 1 implements what Task 0 derives.**

- [ ] **Step 1: Confirm the inherited default's coverage AND its top-level hole**

Run (reproduce the fnmatch reasoning concretely):

```bash
uv run python -c "
import fnmatch
from razorback.harbor_tasks.leakage import matches_denied_path, DEFAULT_SOLUTION_DENY_GLOBS as D
print('=== SWE shapes the default MISSES (the gap E2 closes) ===')
for p in ['gold/patch.diff','test_patch.diff','FAIL_TO_PASS.json','PASS_TO_PASS.json','patch','patch.diff']:
    print(matches_denied_path(p, D), p)
print('=== default top-level HOLE: **/ misses the root ===')
for pat,p in [('**/solution.*','solution.patch'),('**/answer*','answer.json'),('**/*answers*','answers.json')]:
    print(fnmatch.fnmatch(p, pat), repr(pat), repr(p))
print('=== why broad token globs are UNSAFE: * crosses / ===')
for pat,p in [('**/gold*','docs/gold_notes.md'),('**/test_patch*','tests/test_patch_helpers.py')]:
    print(fnmatch.fnmatch(p, pat), repr(pat), repr(p), '<- legit repo file WOULD be stripped')
"
```

Expected: the SWE shapes all print `False` (default misses them); the top-level solution/answer forms print `False` (the `**/` hole); the broad-token rows print `True` (proving `**/gold*`/`**/test_patch*` strip legit repo files — why the plan forbids them).

- [ ] **Step 2: Derive the root-anchored glob set + record the assumption/escalation**

Write `swe-bench-pro-leakage-probe-note.md` documenting:
- (a) The SWE-bench-Pro instance format: gold `patch`, `test_patch`, `FAIL_TO_PASS`/`PASS_TO_PASS` test-name lists.
- (b) The KEY architectural fact: these are **answer artifacts** that harbor lands at the TASK ROOT (siblings of `task.toml`, like the E1 fixture's `solution/gold_patch.diff`), NOT scattered through the repo checkout the agent edits. Therefore the deny set is **root-anchored**, never repo-wide `**/<token>*`.
- (c) The derived set (this becomes Task 1): `gold/**`, `gold_patch*`, `gold.patch`, `test_patch*`, `FAIL_TO_PASS*`, `PASS_TO_PASS*`, `patch`, `patch.diff`, `solution.patch`, `answer*`.
- (d) The captain-verifiable ASSUMPTION: the exact harbor filenames (decision 1) and the residual bare-`patch`/`answer*` root surface (decision 3).
- (e) The escalation decision: since the patches ARE root sibling files, path globs are the right defense — proceed. IF a future hydration shows the patch is inline in `task.toml`/verifier metadata, that is the captain-decision escalation (decision 4), NOT an E2 code change.

- [ ] **Step 3: Commit**

```bash
git add docs/razorback-implementation/plans/swe-bench-pro-leakage-probe-note.md
git commit -m "plan(E2): probe swe-bench-pro leakage shape; derive root-anchored glob set"
```

---

### Task 1: Add the `SWE_BENCH_PRO_DENY_GLOBS` constant (root-anchored, no over-match)

**Files:**
- Modify: `src/razorback/harbor_tasks/leakage.py:7-14` (add constant after `DEFAULT_SOLUTION_DENY_GLOBS`)
- Test: `tests/unit/test_swe_bench_pro_leakage.py` (created here)

**Interfaces:**
- Produces: `SWE_BENCH_PRO_DENY_GLOBS: tuple[str, ...]` exported from `razorback.harbor_tasks.leakage`, equal to `DEFAULT_SOLUTION_DENY_GLOBS + (<root-anchored SWE additions>)`. Consumed by Task 3's `_build_harbor` swe branch and Tasks 2/4/5 tests.

- [ ] **Step 1: Write the failing deny + allow tests**

Create `tests/unit/test_swe_bench_pro_leakage.py` (file + every test name contains `leak` so `-k 'swe_bench_pro and leak'` selects them):

```python
# tests/unit/test_swe_bench_pro_leakage.py
# ABOUTME: AC-1/AC-2/AC-3 — swe-bench-pro gold/test-patch leakage deny-globs.
# ABOUTME: fnmatch's `*` crosses `/`, so the SWE set is ROOT-ANCHORED, never **/token.
from razorback.harbor_tasks.leakage import (
    DEFAULT_SOLUTION_DENY_GLOBS,
    SWE_BENCH_PRO_DENY_GLOBS,
    matches_denied_path,
)


def test_swe_leak_globs_extend_default_without_mutating_it():
    # The swe set is a SUPERSET of the default (does not replace it) and the
    # shared default is left untouched (spider2/ade/dabstep depend on it).
    assert set(DEFAULT_SOLUTION_DENY_GLOBS) <= set(SWE_BENCH_PRO_DENY_GLOBS)
    assert DEFAULT_SOLUTION_DENY_GLOBS == (
        "solution/**",
        "solutions/**",
        "**/solution.*",
        "**/answer*",
        "**/*answers*",
        "tests/expected/**",
    )


def test_swe_leak_globs_deny_root_answer_artifacts():
    # SWE answer artifacts at the TASK ROOT (siblings of task.toml). The default
    # set + **/ forms MISS the top-level forms; the SWE set closes that hole.
    for path in [
        "gold/patch.diff",     # root gold answer dir
        "gold/gold_patch.diff",
        "gold_patch.diff",     # root gold-prefixed answer file
        "gold.patch",
        "test_patch.diff",     # root test patch (hidden grading tests)
        "test_patch",
        "FAIL_TO_PASS.json",   # root fail-to-pass set
        "FAIL_TO_PASS.txt",
        "PASS_TO_PASS.json",   # root pass-to-pass set
        "patch",               # plain gold patch artifact
        "patch.diff",
        "solution.patch",      # top-level solution (default **/ MISSES this)
        "answer.json",         # top-level answer (default **/ MISSES this)
        "answers.json",
        "solution/gold_patch.diff",  # still covered by default solution/**
    ]:
        assert matches_denied_path(path, SWE_BENCH_PRO_DENY_GLOBS), path


def test_swe_leak_globs_do_not_overmatch_repo_files():
    # CRITICAL false-positive guard. fnmatch's `*` crosses `/`, so a broad
    # `**/gold*` / `**/test_patch*` would strip these legit files real SWE
    # repos (django/astropy/sympy) ship. The ROOT-ANCHORED set must NOT.
    for path in [
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
        "docs/changelog.diff",     # a `.diff` NOT at root / not an answer name
        "app/buggy.py",
        "README.md",
        "tests/test_app.py",
        "src/answer_engine.py",    # nested answer*: NOT root-anchored
        "docs/patch_notes.md",     # nested patch*: NOT root-anchored
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
# answer artifacts at the TASK ROOT (siblings of task.toml), next to — but
# distinct from — the repo checkout the agent edits. The DEFAULT set covers
# solution*/answer* but NONE of these SWE shapes, and its `**/` forms MISS the
# top level (`**/solution.*` does not match a root `solution.patch`).
#
# IMPORTANT: `matches_denied_path` uses `fnmatch.fnmatch` (leakage.py:21-23),
# where `*` CROSSES `/`. A broad `**/gold*` / `**/test_patch*` would therefore
# strip LEGITIMATE repo files (`docs/gold_notes.md`, `tests/test_patch_helpers.py`)
# that real SWE repos (django/astropy/sympy) ship — corrupting the task. So we
# ROOT-ANCHOR every SWE answer-artifact glob (a single path segment, no `**/`),
# matching only the task-root answer files, never repo contents. We add NO
# `**/*.patch` / `**/*.diff` for the same false-positive reason (design-doc
# `*.patch` coverage is satisfied by the root-anchored `patch`/`patch.diff`/
# `gold.patch`/`solution.patch` names).
#
# This superset is passed as `exclude_globs=` from the swe branch in
# translate._build_harbor; it does NOT mutate the shared DEFAULT (spider2/ade/
# dabstep/generic-harbor depend on it).
SWE_BENCH_PRO_DENY_GLOBS = DEFAULT_SOLUTION_DENY_GLOBS + (
    # root gold answer dir + root gold-prefixed answer files
    "gold/**",
    "gold_patch*",
    "gold.patch",
    # the test patch (the hidden tests that grade the fix), root-anchored
    "test_patch*",
    # FAIL_TO_PASS / PASS_TO_PASS test-name sets, root-anchored
    "FAIL_TO_PASS*",
    "PASS_TO_PASS*",
    # plain root answer-artifact names (the default `**/` forms MISS the top
    # level; swe lands these at the task root)
    "patch",
    "patch.diff",
    "solution.patch",
    "answer*",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -v`
Expected: PASS (3 tests — extend/deny/allow).

- [ ] **Step 5: Commit**

```bash
git add src/razorback/harbor_tasks/leakage.py tests/unit/test_swe_bench_pro_leakage.py
git commit -m "feat(leakage): add root-anchored SWE_BENCH_PRO_DENY_GLOBS (no repo over-match)"
```

---

### Task 2: Plant root SWE answer fixtures + positive materialize test (AC-1)

**Files:**
- Modify: `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/` (add root answer files + a legit repo file)
- Test: `tests/unit/test_swe_bench_pro_leakage.py` (append)

**Interfaces:**
- Consumes: `SWE_BENCH_PRO_DENY_GLOBS` (Task 1); `materialize_harbor_task_view`, `assert_no_denied_paths` (`harbor_tasks/materialize.py:26`, `leakage.py:26`).
- Produces: a fixture-001 tree carrying root SWE answer files + `app/buggy.py`, used by Task 4's negative test too.

The E1 fixture only has `solution/gold_patch.diff` (caught by DEFAULT `solution/**`). Add root answer shapes the default MISSES so the materialize test is meaningful, plus a legit repo file to prove non-overmatch end-to-end.

- [ ] **Step 1: Add root answer files + a legit repo file to fixture-001**

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

`app/buggy.py` (a legitimate repo file the agent MUST see — proves non-overmatch):
```
def buggy():
    return None
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


def test_materialized_swe_view_excludes_root_answers_keeps_repo_leak(tmp_path):
    # AC-1: materialize fixture-001 with the SWE deny set; assert root answer
    # files are stripped, the legit repo file survives, and the fail-closed gate
    # does not raise.
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
    assert not (view / "solution" / "gold_patch.diff").exists()  # DEFAULT still holds
    # the legit repo file the agent MUST see DID survive (non-overmatch)
    assert (view / "app" / "buggy.py").is_file()
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

Run: `uv run pytest "tests/unit/test_swe_bench_pro_leakage.py::test_materialized_swe_view_excludes_root_answers_keeps_repo_leak" -v`
Expected: PASS. (Passes once Task 1's constant exists — calls the materializer directly with the swe set, does NOT depend on Task 3 wiring; Tasks 4/5 prove the wiring.)

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001 tests/unit/test_swe_bench_pro_leakage.py
git commit -m "test(leakage): swe view strips root answers, keeps repo files (AC-1)"
```

---

### Task 3: Wire the swe `_build_harbor` branch to pass `SWE_BENCH_PRO_DENY_GLOBS` (AC-3 production wiring)

**Files:**
- Modify: `src/razorback/translate.py` — import (top, near line 12-20) + swe branch `materialize_harbor_task_view(...)` call (lines ~419-433)

**Interfaces:**
- Consumes: `SWE_BENCH_PRO_DENY_GLOBS` (Task 1).
- Produces: the production swe branch now passes `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS` (no longer the bare default). Tasks 4 and 5 assert this.

- [ ] **Step 1: Add the import**

In `src/razorback/translate.py`, the existing import block already imports `materialize_harbor_task_view` (line 20). Add the deny-glob constant import. First locate the sibling import:

Run: `grep -n "harbor_tasks.leakage\|harbor_tasks.materialize" src/razorback/translate.py`

Then add this line beside the `materialize` import (line 20):

```python
from razorback.harbor_tasks.leakage import SWE_BENCH_PRO_DENY_GLOBS
```

- [ ] **Step 2: Pass `exclude_globs` in the swe branch**

In the swe-bench-pro `else` branch of `_build_harbor` (currently `translate.py:419-433`), add `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS,` to the `materialize_harbor_task_view(...)` call and update the now-stale comment. The block becomes:

```python
            else:
                # swe-bench-pro uses the GENERIC materializer directly — no
                # benchmark-specific view transform (design doc Architecture
                # decision). The BRANCH passes environment_env (merged into the
                # view's task.toml) AND the SWE-hardened deny set
                # SWE_BENCH_PRO_DENY_GLOBS (root-anchored gold patch / test
                # patch / FAIL_TO_PASS answer artifacts the DEFAULT set misses;
                # root-anchored to avoid stripping repo-checkout files — E2).
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
Expected: PASS (all E1 tests still green — env/manifest assertions unaffected; `test_swe_resolves_n_views_with_manifest_leakage_clean` still passes because `solution/**` is in both sets).

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
- Consumes: `SWE_BENCH_PRO_DENY_GLOBS`, `DEFAULT_SOLUTION_DENY_GLOBS`, `LeakageError` (`leakage.py:17`); `spec_to_job_config`, `HarborBenchmarkBlock`, `NopAgentBlock`, `Spec` (mirroring E1 test imports `test_translate_swe_bench_pro.py:8-15`).

The entity's load-bearing proof. It drives the FULL production path (`spec_to_job_config` → `_build_harbor` swe branch → materializer), mirroring spider2's `test_planted_forbidden_files_are_excluded_from_view` (`test_translate_spider2_dbt.py:182-213`). **The planted files are chosen so the bare DEFAULT set does NOT catch them** (verified at plan time: `gold/gold_patch.diff`, `test_patch.diff`, `FAIL_TO_PASS.json`, `patch.diff`, `solution.patch`, `answer.json` all escape the default) — so the revert half genuinely leaks, keeping the test load-bearing.

- [ ] **Step 1: Write the test**

Append to `tests/unit/test_swe_bench_pro_leakage.py`:

```python
import shutil

import pytest

from razorback.harbor_tasks.leakage import DEFAULT_SOLUTION_DENY_GLOBS, LeakageError
from razorback.spec.schema import HarborBenchmarkBlock, NopAgentBlock, Spec
from razorback.translate import spec_to_job_config


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
    """Plant ROOT answer files the bare DEFAULT set does NOT catch (so the
    revert half truly leaks). Verified at plan time: none of these match
    DEFAULT_SOLUTION_DENY_GLOBS."""
    (source / "gold").mkdir(exist_ok=True)
    (source / "gold" / "gold_patch.diff").write_text("+return 42\n")
    (source / "test_patch.diff").write_text("+assert buggy() == 42\n")
    (source / "FAIL_TO_PASS.json").write_text('["test_returns_42"]\n')
    (source / "patch.diff").write_text("+return 42\n")
    (source / "solution.patch").write_text("+return 42\n")
    (source / "answer.json").write_text('{"answer": 42}\n')


def test_planted_swe_answers_are_excluded_from_view_leak(tmp_path, monkeypatch):
    # AC-2 (forward): plant root answer files in an ISOLATED source copy, run
    # the FULL production path, assert none survive into the view.
    base = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    source = tmp_path / "src" / "swe-bench-pro-fixture-001"
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
        "patch.diff", "solution.patch", "answer.json",
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
    # AC-2 (revert / load-bearing): with the SWE globs REVERTED to the bare
    # DEFAULT set, the planted ROOT answer files SURVIVE into the view (proving
    # the default is insufficient and the SWE additions are load-bearing), and
    # the SWE fail-closed gate WOULD reject that leaked view.
    base = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    source = tmp_path / "src" / "swe-bench-pro-fixture-001"
    shutil.copytree(base, source)
    _plant_swe_leakage(source)

    view = materialize_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        benchmark_kind="swe-bench-pro",
        benchmark_task_id=source.name,
        transform_name="swe-bench-pro-harbor-task-view",
        exclude_globs=DEFAULT_SOLUTION_DENY_GLOBS,  # REVERTED
        view_mode="copy",
    )
    # the planted answer files LEAK through the bare default
    assert (view / "gold" / "gold_patch.diff").is_file()
    assert (view / "test_patch.diff").is_file()
    assert (view / "FAIL_TO_PASS.json").is_file()
    assert (view / "patch.diff").is_file()
    assert (view / "solution.patch").is_file()
    assert (view / "answer.json").is_file()
    # the SWE (production) deny set WOULD reject the leaked view
    with pytest.raises(LeakageError):
        assert_no_denied_paths(view, deny_globs=SWE_BENCH_PRO_DENY_GLOBS)
```

- [ ] **Step 2: Run the tests to verify both pass (after the fix)**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -k leak -v`
Expected: PASS. Forward test passes (Task 3 wired the swe set into production); revert test passes (reverting to the default lets the planted root answers survive AND the swe gate raises on them).

- [ ] **Step 3: Prove the test is load-bearing (manual sanity, do NOT commit the revert)**

Temporarily edit `leakage.py` so `SWE_BENCH_PRO_DENY_GLOBS = DEFAULT_SOLUTION_DENY_GLOBS` (collapse the additions), then run:

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -k leak -v`
Expected: `test_planted_swe_answers_are_excluded_from_view_leak` FAILS (planted root answers now survive) and `test_reverting_swe_globs_leaks_planted_answers_leak`'s `pytest.raises(LeakageError)` FAILS (gate no longer raises). Confirms the suite is load-bearing. **Revert the edit** (`git checkout src/razorback/harbor_tasks/leakage.py`) and re-run to confirm green before committing.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_swe_bench_pro_leakage.py
git commit -m "test(leakage): negative swe leakage proof — revert globs => leak (AC-2)"
```

---

### Task 5: AC-3 wiring assertion — the branch passes the extended set, not the bare default

**Files:**
- Test: `tests/unit/test_swe_bench_pro_leakage.py` (append)

**Interfaces:**
- Consumes: `SWE_BENCH_PRO_DENY_GLOBS`, `materialize_harbor_task_view` (for the monkeypatch spy), `spec_to_job_config`.

AC-3 demands proof the PRODUCTION swe branch passes the extended `exclude_globs` (not a test-only constant). Two independent checks: a runtime spy on the materializer call, AND a static `grep -F` over the wiring.

- [ ] **Step 1: Write the test (runtime spy + static grep)**

Append to `tests/unit/test_swe_bench_pro_leakage.py`:

```python
def test_swe_branch_passes_extended_exclude_globs_leak(tmp_path, monkeypatch):
    # AC-3: spy on materialize_harbor_task_view to capture the exclude_globs the
    # PRODUCTION swe branch passes; assert it is the SWE set, not the bare
    # default. Mirrors how E1 proves the branch supplies environment_env.
    base = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    source = tmp_path / "src" / "swe-bench-pro-fixture-001"
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
    # AC-3 (static): the swe branch source literally passes the SWE deny set.
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
git commit -m "test(translate): assert swe branch passes extended exclude_globs (AC-3)"
```

---

### Task 6: Full acceptance run + verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entity's acceptance command**

Run: `uv run pytest tests/ -k 'swe_bench_pro and leak' -v`
Expected: all tests in `test_swe_bench_pro_leakage.py` PASS (the `-k` filter selects every test — each test name contains `leak`). Record the pass count.

- [ ] **Step 2: Run the broader swe + leakage suites for regression**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py tests/unit/test_translate_swe_bench_pro.py tests/unit/test_spider2_dbt_harbor_view.py -v`
Expected: all PASS — confirms E1 wiring untouched and spider2 deny-glob proof unaffected (shared default unchanged).

- [ ] **Step 3: No-commit verification gate**

Confirm `git status` shows a clean tree (all task commits landed) and `grep -F 'exclude_globs=SWE_BENCH_PRO_DENY_GLOBS' src/razorback/translate.py` returns the wiring line. Do not claim completion without these two observed.

---

## Self-Review

**1. Spec coverage:**
- AC-1 (view excludes gold/test-patch/answer paths) → Task 1 (constant + deny/allow tests) + Task 2 (positive materialize test, keeps legit repo file). ✓
- AC-2 (negative test fails when globs reverted) → Task 4; planted files verified to escape the bare default so the revert genuinely leaks; Step 3 proves load-bearing. ✓
- AC-3 (branch passes extended set, not bare default) → Task 3 (wire) + Task 5 (runtime spy + `grep -F`). ✓
- Test plan: probe-then-harden → Task 0 (probe note DRIVES the set) + Tasks 1/2/4/5. Acceptance `uv run pytest tests/ -k 'swe_bench_pro and leak'` → Task 6 Step 1; every test name contains `leak`. ✓
- Out of scope honored: NO `rk audit` SWE signatures; NO new view transform; escalation hook is a Task 0 HALT-and-surface. ✓

**2. Codex P1/P2 findings resolved:**
- P1 over-match → set is ROOT-ANCHORED (no `**/<token>*`); `test_swe_leak_globs_do_not_overmatch_repo_files` proves `docs/gold_notes.md`/`tests/test_patch_helpers.py`/`a/test_patch/file.py` survive. ✓
- P1 probe drives set → Task 0 derives the set from the SWE answer-field format and is the explicit producer; the glob set is its OUTPUT. ✓
- P1 inherited default top-level hole → SWE set adds bare `solution.patch`/`answer*`/`patch`/`patch.diff`; the plan never claims the default covers the top-level family (CRITICAL section states it does not). ✓
- P2 gold-dir reasoning → dropped the bare-vs-nested-dir closure claim; coverage is FILES under the answer path (`gold/**`), consistent with `assert_no_denied_paths` checking files/symlinks. ✓

**3. fnmatch re-verification (deny + allow):** Run at plan time over the final set — all DENY paths match, all ALLOW (legit repo) paths clean, and all planted negative-test files escape the bare default. Evidence reproduced in Task 0 Step 1 and the Task 1 deny/allow tests.

**4. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step shows complete code; every run step shows command + expected output. ✓

**5. Type consistency:** `SWE_BENCH_PRO_DENY_GLOBS` named identically across Tasks 1-5. `matches_denied_path`, `assert_no_denied_paths`, `materialize_harbor_task_view`, `LeakageError` match `leakage.py`/`materialize.py`. `spec_to_job_config`/`HarborBenchmarkBlock`/`NopAgentBlock`/`Spec` match the E1 test imports. Task 4 plants the same names into an isolated tmp copy as Task 2's committed fixture extras (identical overwrite, no collision). ✓
