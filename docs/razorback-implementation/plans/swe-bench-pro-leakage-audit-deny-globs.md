# swe-bench-pro Leakage Deny-Globs (gold/test-patch isolation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the path deny-glob set the swe-bench-pro task-view materializer passes as `exclude_globs`, so a resolved swe-bench-pro task's gold patch / test patch / FAIL_TO_PASS-shaped answer files never reach the agent, and prove the exclusion is fail-closed with a negative leakage test.

**Architecture:** swe-bench-pro rides the GENERIC `materialize_harbor_task_view` (design doc Architecture decision — *no* benchmark-specific view transform, unlike spider2's `harbor_view.py` wrapper). E1 wired the swe branch in `_build_harbor` to call the generic materializer WITHOUT `exclude_globs` (so it uses `DEFAULT_SOLUTION_DENY_GLOBS`). E2 adds a swe-specific constant `SWE_BENCH_PRO_DENY_GLOBS` in `leakage.py` (next to the default, NOT a new `harbor_view.py`), extends the deny set for SWE leakage shapes, and wires the swe branch to pass it as `exclude_globs=`. The fail-closed mechanism (`assert_no_denied_paths`, already called inside the materializer) is reused unchanged.

**Tech Stack:** Python 3, `fnmatch`-based glob matching (`harbor_tasks/leakage.py`), `uv run pytest`, existing E1 fixture tree under `tests/fixtures/swe_bench_pro/`.

## Global Constraints

- Do NOT mutate `DEFAULT_SOLUTION_DENY_GLOBS` — it is shared by spider2/ade/dabstep/generic harbor; widening it changes their behavior. Add a swe-specific constant that is `DEFAULT_SOLUTION_DENY_GLOBS + (...)`, mirroring `SPIDER2_DBT_DENY_GLOBS` (`benchmarks/spider2_dbt/harbor_view.py:20-31`) and `ADE_BENCH_DENY_GLOBS` (`benchmarks/ade_bench/harbor_view.py:16-18`).
- For every directory denied, include BOTH the bare form (`gold/**`) and the nested form (`**/gold/**`). `fnmatch`'s `**/` prefix requires a leading path segment, so `**/gold/**` alone misses a TOP-LEVEL `gold/` dir (spider2 precedent comment, `harbor_view.py:21-24`).
- The defense is the materializer's path-based exclusion (`assert_no_denied_paths`, `harbor_tasks/leakage.py:26-44`), NOT `rk audit`. Do NOT add trace-level `rk audit` SWE signatures — out of scope (entity Out of scope; `audit/cli.py:79-92` only taints `forbidden_lookup`).
- Reuse E1's fixture tree (`tests/fixtures/swe_bench_pro/harbor_task_minimal/`); do not invent a new fixture root.
- All tests fixture-backed and network-free (monkeypatch `_resolve_harbor_dataset_tasks`, as the E1 tests do).
- Acceptance command (entity Test plan): `uv run pytest tests/ -k 'swe_bench_pro and leak'`.

---

## Captain decisions to flag (open)

These are surfaced to the captain at the plan gate; the plan picks a justified default for each so implementation is unblocked, but each is captain-overridable.

1. **The exact swe glob set.** The plan proposes the set in Task 1 below. The concrete leakage shapes (`*.patch`, `*.diff`, `gold*`, `test_patch*`, `FAIL_TO_PASS`/`PASS_TO_PASS`) are reasoned from the **public SWE-bench / SWE-bench-Pro task format** (each instance ships `patch` = gold, `test_patch`, and `FAIL_TO_PASS`/`PASS_TO_PASS` test-name lists). We CANNOT hydrate harbor's `scale-ai/swe-bench-pro` to confirm the on-disk filenames harbor uses when it lands these as sibling files. **ASSUMPTION (captain-verifiable):** harbor exposes the gold/test patch as sibling files whose paths contain `gold`, `patch`, or `diff`, and the FAIL_TO_PASS/PASS_TO_PASS sets as files whose names contain those tokens. If harbor's real layout differs (Task 0 probe documents what we can/can't see), the captain confirms or amends the glob set before merge.
2. **Whether to deny `*.patch` / `*.diff` broadly.** A blanket `**/*.patch` could strip a *legitimate* task file (some repos ship `.patch` fixtures the agent is meant to edit). The plan denies `**/*.patch`/`**/*.diff` ONLY under answer-bearing parents (`gold*`, `solution*`, `test_patch*`) plus the specific top-level names, NOT a blanket `**/*.patch`. Rationale in Task 1. Captain may widen to blanket if the harbor layout proves it safe.
3. **Escalation hook (design doc E2).** IF the Task 0 probe (or the captain's knowledge of harbor) shows the gold/test patch is NOT a sibling file but lives **inline** in `task.toml` / verifier metadata / an env var, then path globs cannot strip it. The plan does NOT silently build a view transform for that case — it HALTS and surfaces "swe-bench-pro gold patch is inline, not a sibling file; path globs insufficient — captain decision needed (defense-in-depth audit layer or a view content transform, both out of E2 scope)." See Task 0.

---

## AC ↔ Task map

| Acceptance criterion | Task(s) | TDD checkpoint (failing test first) |
| --- | --- | --- |
| (probe, Test plan) Probe the resolved-task shape, commit as evidence | Task 0 | n/a — committed probe note + assumption record |
| **AC-1** — materialized swe view excludes gold/test-patch/answer paths | Task 1 (constant), Task 2 (positive materialize test) | Task 2 Step 1: test asserts no `*.patch`/`test_patch*`/`gold*` survives + `assert_no_denied_paths` doesn't raise → fails before Task 1+Task 3 wired |
| **AC-2** — negative leakage test FAILS when swe globs reverted | Task 3 (wire branch) + Task 4 (negative leakage test, load-bearing) | Task 4 Step 1: plant gold/test-patch files → materialize via swe branch → assert excluded; revert proof asserts they leak/raise → fails without Task 1+Task 3 |
| **AC-3** — the swe branch actually passes the extended `exclude_globs` | Task 3 (wire) + Task 5 (wiring assertion test) | Task 5 Step 1: test (and `grep -F`) asserts `_build_harbor` swe branch passes `SWE_BENCH_PRO_DENY_GLOBS` (not bare default) → fails before Task 3 |

**Riskiest-first ordering rationale:** The load-bearing proof is the **negative leakage test (Task 4)** — plant → materialize → assert excluded → revert globs → assert leak/raise. It is the entity's AC-2 and the whole reason E2 exists. Tasks are ordered so the deny set (Task 1) and the production wiring (Task 3) exist before Task 4 exercises them, and Task 4's revert half is designed to FAIL without the Task 1+Task 3 fix. Task 0 (probe) runs first because it can trigger the escalation hook and abort the rest.

---

## File Structure

- **Modify** `src/razorback/harbor_tasks/leakage.py` — add `SWE_BENCH_PRO_DENY_GLOBS` constant (Task 1). Lives here (not a new `benchmarks/swe_bench_pro/harbor_view.py`) because the design doc mandates swe uses the GENERIC materializer with no benchmark-specific transform; the constant is the *only* swe-specific artifact, so it belongs beside `DEFAULT_SOLUTION_DENY_GLOBS`.
- **Modify** `src/razorback/translate.py` — swe branch in `_build_harbor` (currently lines ~412-433) passes `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS` and imports it (Task 3).
- **Modify** `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/` — add realistic SWE leakage-shaped files (Task 2): a `gold/` dir with a patch, a top-level `test_patch.diff`, a `FAIL_TO_PASS.json`. (fixture-002 left as-is for the multi-instance E1 tests.)
- **Create** `tests/unit/test_swe_bench_pro_leakage.py` — the swe deny-glob unit tests, positive materialize test, negative leakage test, and AC-3 wiring assertion (Tasks 2, 4, 5). New file (the E1 file `test_translate_swe_bench_pro.py` covers wiring; leakage gets its own file matching the entity's `-k 'swe_bench_pro and leak'` acceptance filter — note the test names below all contain `leak`).

---

### Task 0: Probe the resolved swe-bench-pro task shape (evidence + escalation gate)

**Files:**
- Create: `docs/razorback-implementation/plans/swe-bench-pro-leakage-probe-note.md` (committed evidence)

**Interfaces:**
- Produces: a documented decision — either "path globs sufficient, proceed with Task 1 glob set" OR "gold/test patch is inline, not a sibling file → HALT + captain decision".

This task does NOT hydrate the network dataset (entity: network-free; E1's live `harbor download` smoke was non-gating). It records what is KNOWABLE offline and pins the assumption.

- [ ] **Step 1: Inspect the E1 fixture + the SWE-bench format**

Read `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/` (E1 planted `solution/gold_patch.diff`, caught by the DEFAULT `solution/**` glob). Note what the DEFAULT set already covers vs the SWE shapes it does NOT: confirm via the existing globs (`leakage.py:7-14`) that none of `*.patch`, `*.diff`, `test_patch*`, top-level `gold/`, `FAIL_TO_PASS*`, `PASS_TO_PASS*` are matched.

Run to confirm the gap concretely:

```bash
uv run python -c "
from razorback.harbor_tasks.leakage import matches_denied_path, DEFAULT_SOLUTION_DENY_GLOBS as D
for p in ['gold/patch.diff','test_patch.diff','FAIL_TO_PASS.json','PASS_TO_PASS.json','patches/gold.patch','tests/test_patch.py']:
    print(p, matches_denied_path(p, D))
"
```

Expected: every path prints `False` — the default set covers NONE of the SWE leakage shapes. This is the gap E2 closes.

- [ ] **Step 2: Record the assumption + escalation decision**

Write `swe-bench-pro-leakage-probe-note.md` documenting: (a) the SWE-bench-Pro instance format (gold `patch`, `test_patch`, `FAIL_TO_PASS`/`PASS_TO_PASS`); (b) the offline-unverifiable ASSUMPTION (harbor lands these as sibling files with `gold`/`patch`/`diff`/`test_patch`/`FAIL_TO_PASS`/`PASS_TO_PASS` in their paths); (c) the escalation decision: since we reason the patches ARE sibling files (harbor task layout reflects a repo checkout + sibling answer files, as the E1 fixture's `solution/gold_patch.diff` already models), path globs ARE the right defense — proceed. IF a future hydration shows the patch is inline in `task.toml`/verifier metadata, that is the captain-decision escalation, not an E2 code change.

- [ ] **Step 3: Commit**

```bash
git add docs/razorback-implementation/plans/swe-bench-pro-leakage-probe-note.md
git commit -m "plan(E2): probe swe-bench-pro leakage shape + record glob assumption"
```

---

### Task 1: Add the `SWE_BENCH_PRO_DENY_GLOBS` constant

**Files:**
- Modify: `src/razorback/harbor_tasks/leakage.py:7-14` (add constant after `DEFAULT_SOLUTION_DENY_GLOBS`)
- Test: `tests/unit/test_swe_bench_pro_leakage.py` (created here)

**Interfaces:**
- Produces: `SWE_BENCH_PRO_DENY_GLOBS: tuple[str, ...]` exported from `razorback.harbor_tasks.leakage`, equal to `DEFAULT_SOLUTION_DENY_GLOBS + (<swe additions>)`. Consumed by Task 3's `_build_harbor` swe branch and by Tasks 2/4/5 tests.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_swe_bench_pro_leakage.py` with this first test (note: file + every test name contains `leak` so the `-k 'swe_bench_pro and leak'` acceptance filter selects them):

```python
# tests/unit/test_swe_bench_pro_leakage.py
# ABOUTME: AC-1/AC-2/AC-3 — swe-bench-pro gold/test-patch leakage deny-globs.
# ABOUTME: Fixture-backed, network-free; mirrors the spider2 deny-glob proof.
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


def test_swe_leak_globs_cover_gold_and_test_patch_shapes():
    # Realistic SWE leakage shapes the DEFAULT set misses. Both top-level and
    # nested forms for denied DIRS (fnmatch `**/` needs a leading segment, so
    # `**/gold/**` alone misses a top-level `gold/`).
    for path in [
        "gold/patch.diff",            # top-level gold dir
        "a/b/gold/patch.diff",        # nested gold dir
        "gold_patch.diff",            # top-level gold-prefixed file
        "patches/gold_patch.diff",    # nested gold-prefixed file
        "test_patch.diff",            # top-level test patch
        "tests/test_patch.py",        # nested test patch
        "FAIL_TO_PASS.json",          # top-level fail-to-pass set
        "meta/FAIL_TO_PASS.txt",      # nested
        "PASS_TO_PASS.json",          # top-level pass-to-pass set
        "meta/PASS_TO_PASS.txt",      # nested
    ]:
        assert matches_denied_path(path, SWE_BENCH_PRO_DENY_GLOBS), path


def test_swe_leak_globs_do_not_overmatch_legitimate_files():
    # Guard against false positives: ordinary repo files the agent MUST see are
    # NOT denied. A blanket `**/*.patch` would strip these — we do not use one.
    for path in [
        "app/buggy.py",
        "src/utils.py",
        "README.md",
        "tests/test_app.py",          # an ordinary test file (no `test_patch`)
        "docs/changelog.diff",        # a `.diff` NOT under a gold/solution parent
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
# fixtures alongside the repo checkout. The DEFAULT set covers solution*/answer*
# but NONE of those SWE shapes. This superset adds them; it is passed as
# `exclude_globs=` from the swe branch in translate._build_harbor (it does NOT
# mutate the shared DEFAULT, which spider2/ade/dabstep/generic-harbor depend on).
#
# For every denied DIR we include BOTH the bare (`gold/**`) and nested
# (`**/gold/**`) forms: fnmatch's `**/` prefix needs a leading path segment, so
# `**/gold/**` alone misses a TOP-LEVEL `gold/` dir (spider2 precedent,
# benchmarks/spider2_dbt/harbor_view.py:20-31).
#
# We deliberately do NOT add a blanket `**/*.patch` / `**/*.diff`: some repos
# ship legitimate `.patch`/`.diff` fixtures the agent must edit. We deny patch
# files only under answer-bearing parents (gold*/solution*) and the specific
# top-level/nested SWE answer filenames.
SWE_BENCH_PRO_DENY_GLOBS = DEFAULT_SOLUTION_DENY_GLOBS + (
    # gold patch directory and gold-prefixed files (top-level + nested)
    "gold/**",
    "**/gold/**",
    "gold*",
    "**/gold*",
    # the test patch (the hidden tests that grade the fix), top-level + nested
    "test_patch*",
    "**/test_patch*",
    # FAIL_TO_PASS / PASS_TO_PASS test-name sets, top-level + nested
    "FAIL_TO_PASS*",
    "**/FAIL_TO_PASS*",
    "PASS_TO_PASS*",
    "**/PASS_TO_PASS*",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -v`
Expected: PASS (3 tests).

Note on the false-positive test: `gold*` matches `gold_patch.diff` AND would match any top-level file literally named `gold*`. We accept that — a file named `gold...` in a SWE task root is overwhelmingly answer data. `docs/changelog.diff` and `tests/test_app.py` are NOT matched (no `gold`/`test_patch`/`FAIL_TO_PASS` token), confirming we avoided the blanket-`*.patch` false-positive trap.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/harbor_tasks/leakage.py tests/unit/test_swe_bench_pro_leakage.py
git commit -m "feat(leakage): add SWE_BENCH_PRO_DENY_GLOBS for gold/test-patch shapes"
```

---

### Task 2: Plant realistic SWE leakage fixtures + positive materialize test (AC-1)

**Files:**
- Modify: `tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001/` (add leakage-shaped files)
- Test: `tests/unit/test_swe_bench_pro_leakage.py` (append)

**Interfaces:**
- Consumes: `SWE_BENCH_PRO_DENY_GLOBS` (Task 1); `materialize_harbor_task_view`, `assert_no_denied_paths` (`harbor_tasks/materialize.py:26`, `leakage.py:26`).
- Produces: a fixture-001 tree carrying SWE answer files, used by Task 4's negative test too.

The E1 fixture only has `solution/gold_patch.diff` (caught by DEFAULT `solution/**`). Add SWE shapes the default MISSES so the materialize test is meaningful.

- [ ] **Step 1: Add leakage-shaped files to fixture-001**

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

Also add one legitimate agent-visible file the agent MUST see, to prove non-overmatch — `app/buggy.py`:
```
def buggy():
    return None
```

(Leave the existing `solution/gold_patch.diff`, `instruction.md`, `task.toml`, `environment/Dockerfile` untouched.)

- [ ] **Step 2: Write the failing positive materialize test**

Append to `tests/unit/test_swe_bench_pro_leakage.py`:

```python
import shutil
from pathlib import Path

from razorback.harbor_tasks.leakage import assert_no_denied_paths
from razorback.harbor_tasks.materialize import materialize_harbor_task_view

FIXTURE_ROOT = (
    Path(__file__).parent.parent
    / "fixtures" / "swe_bench_pro" / "harbor_task_minimal"
)


def test_materialized_swe_view_excludes_gold_and_test_patch_leak(tmp_path):
    # AC-1: materialize fixture-001 through the generic materializer with the
    # SWE deny set and assert no gold/test-patch/FAIL_TO_PASS path survives and
    # the materializer's own fail-closed check stays green.
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
    # the gold/test-patch/FAIL_TO_PASS answer files did NOT survive
    assert not (view / "gold" / "gold_patch.diff").exists()
    assert not (view / "test_patch.diff").exists()
    assert not (view / "FAIL_TO_PASS.json").exists()
    assert not (view / "solution" / "gold_patch.diff").exists()  # DEFAULT still holds
    # the legitimate repo file the agent MUST see DID survive
    assert (view / "app" / "buggy.py").is_file()
    # no answer file survives anywhere, and the fail-closed gate does not raise
    survivors = [
        p.relative_to(view).as_posix()
        for p in view.rglob("*")
        if p.is_file()
        and matches_denied_path(p.relative_to(view).as_posix(), SWE_BENCH_PRO_DENY_GLOBS)
    ]
    assert survivors == [], survivors
    assert_no_denied_paths(view, deny_globs=SWE_BENCH_PRO_DENY_GLOBS)  # no raise
```

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py::test_materialized_swe_view_excludes_gold_and_test_patch_leak -v`
Expected: PASS. (This test passes once Task 1's constant exists because it calls the materializer directly with the swe set — it does NOT depend on the Task 3 wiring. The wiring is proven by Tasks 4/5.)

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/swe_bench_pro/harbor_task_minimal/swe-bench-pro-fixture-001 tests/unit/test_swe_bench_pro_leakage.py
git commit -m "test(leakage): swe view excludes gold/test-patch fixtures (AC-1)"
```

---

### Task 3: Wire the swe `_build_harbor` branch to pass `SWE_BENCH_PRO_DENY_GLOBS` (AC-3 production wiring)

**Files:**
- Modify: `src/razorback/translate.py` — import (top, near line 12-20) + swe branch `materialize_harbor_task_view(...)` call (lines ~419-433)

**Interfaces:**
- Consumes: `SWE_BENCH_PRO_DENY_GLOBS` (Task 1).
- Produces: the production swe branch now passes `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS` (no longer the bare default). Tasks 4 and 5 assert this.

- [ ] **Step 1: Add the import**

In `src/razorback/translate.py`, the existing import block already imports `materialize_harbor_task_view` (line 20). Add the deny-glob constant import. Locate the leakage/materialize imports near the top and add:

```python
from razorback.harbor_tasks.leakage import SWE_BENCH_PRO_DENY_GLOBS
```

(If `translate.py` has no existing `from razorback.harbor_tasks.leakage import ...` line, add this new line beside the `materialize` import at line 20. Run `grep -n "harbor_tasks.leakage\|harbor_tasks.materialize" src/razorback/translate.py` first to place it with the sibling imports.)

- [ ] **Step 2: Pass `exclude_globs` in the swe branch**

In the swe-bench-pro `else` branch of `_build_harbor` (currently `translate.py:419-433`), add `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS,` to the `materialize_harbor_task_view(...)` call and update the now-stale comment. The block becomes:

```python
            else:
                # swe-bench-pro uses the GENERIC materializer directly — no
                # benchmark-specific view transform (design doc Architecture
                # decision). The BRANCH passes environment_env (merged into the
                # view's task.toml) AND the SWE-hardened deny set
                # SWE_BENCH_PRO_DENY_GLOBS (gold patch / test patch /
                # FAIL_TO_PASS shapes the DEFAULT set misses — entity E2).
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
Expected: PASS (all E1 tests still green — the env/manifest assertions are unaffected; the leakage-clean test `test_swe_resolves_n_views_with_manifest_leakage_clean` still passes because `solution/**` is in both sets).

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

This is the entity's load-bearing proof. It drives the FULL production path (`spec_to_job_config` → `_build_harbor` swe branch → materializer), mirroring spider2's `test_planted_forbidden_files_are_excluded_from_view` (`test_translate_spider2_dbt.py:182-213`). The "revert" half proves the test FAILS without the fix.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_swe_bench_pro_leakage.py`:

```python
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
    """Plant gold/test-patch/FAIL_TO_PASS answer files the DEFAULT set misses."""
    (source / "gold").mkdir(exist_ok=True)
    (source / "gold" / "gold_patch.diff").write_text("+return 42\n")
    (source / "test_patch.diff").write_text("+assert buggy() == 42\n")
    (source / "FAIL_TO_PASS.json").write_text('["test_returns_42"]\n')


def test_planted_swe_patches_are_excluded_from_view_leak(tmp_path, monkeypatch):
    # AC-2 (forward): plant gold/test-patch files in an ISOLATED source copy,
    # run the FULL production path, assert none survive into the view.
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
    assert not (view / "gold" / "gold_patch.diff").exists()
    assert not (view / "test_patch.diff").exists()
    assert not (view / "FAIL_TO_PASS.json").exists()
    survivors = [
        p.relative_to(view).as_posix()
        for p in view.rglob("*")
        if p.is_file()
        and matches_denied_path(
            p.relative_to(view).as_posix(), SWE_BENCH_PRO_DENY_GLOBS
        )
    ]
    assert survivors == [], survivors


def test_reverting_swe_globs_leaks_planted_patches_leak(tmp_path, monkeypatch):
    # AC-2 (revert / load-bearing): with the SWE globs REVERTED to the bare
    # DEFAULT set, the same planted files SURVIVE into the materialized view
    # (and the swe-set fail-closed gate would raise on that view). This is the
    # proof the test FAILS without the Task-1 + Task-3 fix: if SWE_BENCH_PRO_*
    # ever collapses back to the default, this assertion flips.
    base = FIXTURE_ROOT / "swe-bench-pro-fixture-001"
    source = tmp_path / "src" / "swe-bench-pro-fixture-001"
    shutil.copytree(base, source)
    _plant_swe_leakage(source)

    # Materialize with the REVERTED (default) deny set, simulating "before E2".
    view = materialize_harbor_task_view(
        source_task_dir=source,
        view_root=tmp_path / "views",
        benchmark_kind="swe-bench-pro",
        benchmark_task_id=source.name,
        transform_name="swe-bench-pro-harbor-task-view",
        exclude_globs=DEFAULT_SOLUTION_DENY_GLOBS,  # REVERTED
        view_mode="copy",
    )
    # The planted answer files LEAK through the default set (proves the default
    # is insufficient and the SWE additions are load-bearing).
    assert (view / "gold" / "gold_patch.diff").is_file()
    assert (view / "test_patch.diff").is_file()
    assert (view / "FAIL_TO_PASS.json").is_file()
    # And the SWE fail-closed gate (the production deny set) WOULD reject this
    # leaked view — raising LeakageError naming the survivors.
    with pytest.raises(LeakageError):
        assert_no_denied_paths(view, deny_globs=SWE_BENCH_PRO_DENY_GLOBS)
```

- [ ] **Step 2: Run the tests to verify both pass (after the fix)**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -k leak -v`
Expected: PASS. The forward test passes because Task 3 wired the swe set into production; the revert test passes because reverting to the default lets the planted files survive AND the swe gate raises on them.

- [ ] **Step 3: Prove the test is load-bearing (manual sanity, do NOT commit the revert)**

Temporarily edit `leakage.py` so `SWE_BENCH_PRO_DENY_GLOBS = DEFAULT_SOLUTION_DENY_GLOBS` (collapse the additions), then run:

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -k leak -v`
Expected: `test_planted_swe_patches_are_excluded_from_view_leak` FAILS (planted files now survive) and `test_reverting_swe_globs_leaks_planted_patches_leak`'s final `pytest.raises(LeakageError)` FAILS (the gate no longer raises). This confirms the suite is load-bearing. **Revert the temporary edit** (`git checkout src/razorback/harbor_tasks/leakage.py`) and re-run to confirm green before committing.

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

- [ ] **Step 1: Write the failing test (runtime spy)**

Append to `tests/unit/test_swe_bench_pro_leakage.py`:

```python
import subprocess


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
Expected: all tests in `test_swe_bench_pro_leakage.py` PASS (the `-k` filter selects every test — file name + each test name contains both `swe_bench_pro`-suite and `leak`). Record the pass count.

- [ ] **Step 2: Run the broader swe + leakage suites for regression**

Run: `uv run pytest tests/unit/test_swe_bench_pro_leakage.py tests/unit/test_translate_swe_bench_pro.py tests/unit/test_spider2_dbt_harbor_view.py -v`
Expected: all PASS — confirms E1 wiring untouched and spider2 deny-glob proof unaffected (shared default unchanged).

- [ ] **Step 3: No-commit verification gate**

Confirm `git status` shows a clean tree (all task commits landed) and `grep -F 'exclude_globs=SWE_BENCH_PRO_DENY_GLOBS' src/razorback/translate.py` returns the wiring line. Do not claim completion without these two observed.

---

## Self-Review

**1. Spec coverage:**
- AC-1 (view excludes gold/test-patch/answer paths) → Task 1 (constant) + Task 2 (positive materialize test). ✓
- AC-2 (negative test fails when globs reverted) → Task 4 (forward + revert halves; Step 3 proves load-bearing). ✓
- AC-3 (branch passes extended set, not bare default) → Task 3 (wire) + Task 5 (runtime spy + `grep -F`). ✓
- Test plan: probe-then-harden → Task 0 (probe note) + Tasks 2/4/5 (unit + negative + wiring). Acceptance command `uv run pytest tests/ -k 'swe_bench_pro and leak'` → Task 6 Step 1; every test name contains `leak`. ✓
- Out of scope honored: NO `rk audit` SWE signatures added; NO new view transform; escalation hook is a Task 0 HALT-and-surface, not a build. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step shows complete code; every run step shows the command + expected output. ✓

**3. Type consistency:** `SWE_BENCH_PRO_DENY_GLOBS` named identically in Tasks 1, 2, 3, 4, 5. `matches_denied_path`, `assert_no_denied_paths`, `materialize_harbor_task_view`, `LeakageError` match their real signatures in `leakage.py`/`materialize.py`. `spec_to_job_config`/`HarborBenchmarkBlock`/`NopAgentBlock`/`Spec` match the E1 test imports. ✓

**4. Contradiction check:** Task 2's positive test passes after Task 1 alone (calls materializer directly); only Tasks 4/5 depend on Task 3's wiring — ordering is consistent (Task 3 precedes 4/5). The fixture additions in Task 2 are committed and reused by Task 4's isolated-copy plant (Task 4 copies the base fixture then plants into the copy, so the committed fixture extras and the planted extras don't collide — Task 4 plants the same names into an isolated tmp copy, overwriting identically; no conflict). ✓
