---
id: zkn663pcbvd5sbaaxwx5f1z5
title: swe-bench-pro — leakage deny-globs (gold/test patch isolation)
status: implementation
source: docs/superpowers/specs/2026-06-24-swe-bench-pro-on-harbor-design.md (E2); harbor_tasks/leakage.py DEFAULT_SOLUTION_DENY_GLOBS + spider2-dbt deny-glob precedent
started: 2026-06-24T04:44:28Z
completed:
verdict:
score:
worktree: .worktrees/swe-bench-pro-leakage-audit-deny-globs
issue:
pr:
mod-block:
auto-approve: false
---

## Problem

SWE-bench tasks ship the **gold patch and the test patch** alongside the
repo checkout. swe-bench-pro rides the task-view materializer (wired by
`swe-bench-pro-hydration-resolve-smoke`), whose path deny-globs strip
answer files before the agent sees them — but the current
`DEFAULT_SOLUTION_DENY_GLOBS` (`src/razorback/harbor_tasks/leakage.py:7-14`:
`solution/**`, `solutions/**`, `**/solution.*`, `**/answer*`,
`**/*answers*`, `tests/expected/**`) covers none of the SWE leakage shapes
(`*.patch`, `test_patch`, `gold`, `FAIL_TO_PASS`/`PASS_TO_PASS` fixtures).
This entity probes what a resolved swe-bench-pro task actually exposes,
then extends the deny-glob set the swe-bench-pro materializer passes as
`exclude_globs` and proves the exclusion is fail-closed.

The defense is the materializer's path-based exclusion
(`assert_no_denied_paths`, `harbor_tasks/leakage.py:25-44`), **not**
`rk audit`: `rk audit`'s strict reducer only taints
`category == "forbidden_lookup"` (`src/razorback/audit/cli.py:79-92`) and
ships no SWE signatures, so a trace-level audit AC would exit clean and is
deliberately out of scope here.

Escalation hook: if the gold/test patch cannot be stripped by path globs
(e.g. it lives inline in `task.toml` or verifier metadata rather than as a
sibling file), this entity surfaces that as a **captain decision** — it
does not silently redesign.

Depends on `swe-bench-pro-hydration-resolve-smoke` (needs the resolved
view shape to probe). `auto-approve: false` — touches the leakage/security
surface.

## Acceptance criteria

**AC-1 — The materialized swe-bench-pro view excludes gold-patch / test-patch / answer paths.**
Verified by: a test that materializes the fixture swe-bench-pro task
through the swe-bench-pro materializer branch and asserts
`assert_no_denied_paths(view_dir, deny_globs=<swe set>)` does not raise and
that no `*.patch` / `test_patch*` / `gold*` path survives in the view dir.

**AC-2 — A negative leakage test fails when the swe deny-globs are reverted.**
Verified by: a test that plants gold/test-patch-shaped files
(`gold.patch`, `test_patch.diff`, a `gold/` dir) in a fixture source task,
materializes it, and asserts they are excluded from the view; reverting the
new swe globs makes the materialize raise `LeakageError` (or the planted
files survive) — i.e. the test FAILS without the fix (load-bearing proof,
mirroring the spider2 `test_planted_forbidden_files_are_excluded_from_view`).

**AC-3 — The swe deny-glob set is the one the swe-bench-pro materializer branch actually passes.**
Verified by: a test (or `grep -F` over the wiring) asserting the
swe-bench-pro `_build_harbor` branch passes the extended `exclude_globs`
to `materialize_harbor_task_view` (not the bare default), so AC-1/AC-2
exercise the production deny set, not a test-only constant.

## Test plan

Probe-then-harden: a probe test/script records the real resolved-task
shape (committed as evidence), then unit tests around the swe deny-glob set
and a negative leakage test (plant → materialize → assert excluded →
revert → assert leaks). All fixture-backed and network-free. Acceptance
command for validation: `uv run pytest tests/ -k 'swe_bench_pro and leak'`
(quote the `-k` expression — or the suite the plan names).

## Out of scope

The example spec + scoring strata
(`swe-bench-pro-example-spec-scoring-strata`) and the full-dataset score.
Trace-level `rk audit` SWE signatures — the strict reducer
(`audit/cli.py:79-92`) only taints `forbidden_lookup`, so a gold-patch
audit signature would also require changing that reducer; deferred unless
the captain wants a defense-in-depth audit layer beyond the view
exclusion. A view materializer for swe-bench-pro itself — owned by E1; if
the probe shows path globs are insufficient, this entity surfaces the
captain decision rather than building a new transform.

## Stage Report: plan

- DONE: Write a separate STANDARD plan doc
  `docs/razorback-implementation/plans/swe-bench-pro-leakage-audit-deny-globs.md` (6 tasks, AC↔task map, riskiest-first).
- DONE: AC-1 — view excludes gold/test-patch/answer paths
  Task 1 (`SWE_BENCH_PRO_DENY_GLOBS` in leakage.py) + Task 2 (positive materialize test, TDD failing-test-first).
- DONE: AC-2 — negative leakage test fails when swe globs reverted
  Task 4 forward+revert halves; Step 3 proves load-bearing by collapsing the constant to the default.
- DONE: AC-3 — branch passes the extended set, not bare default
  Task 3 wires `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS` into `_build_harbor`; Task 5 proves it via runtime spy + `grep -F`.
- DONE: Settle deny-glob design (constant vs default)
  Chose `SWE_BENCH_PRO_DENY_GLOBS = DEFAULT_SOLUTION_DENY_GLOBS + (...)` in leakage.py (NOT a new harbor_view.py, NOT mutating the global default); justified inline. **[SUPERSEDED by cycle 3: the final set is a STANDALONE curated tuple, NOT `DEFAULT + (...)`. The broad cross-`/` default globs (`**/answer*`, `**/solution.*`, `**/*answers*`) were DROPPED because they over-match nested repo files. See cycle-3 report.]**
- DONE: fnmatch top-level-dir hole handled
  SUPERSEDED by cycle 3: the final set has NO `**/gold/**` (the cycle-1 bare+nested-dir claim is obsolete). The curated set uses only root-anchored `gold/**`; see the cycle-3 report below.
- DONE: Honor Out of scope
  No `rk audit` SWE signatures; no new view transform; escalation hook is a Task 0 HALT-and-surface.
- DONE: Verified glob set against live fnmatch
  Ran all 10 DENY + 5 ALLOW paths through `matches_denied_path`; every assertion in the plan's tests holds.

### Summary

**[NOTE: this cycle-1 summary is SUPERSEDED by cycle 3 — the final set is STANDALONE, not a superset of the default. Read the cycle-3 report for the authoritative set.]**

Plan hardens the swe-bench-pro deny set via a new `SWE_BENCH_PRO_DENY_GLOBS`
constant (superset of the default, mirroring `SPIDER2_DBT_DENY_GLOBS`/`ADE_BENCH_DENY_GLOBS`),
wired into the existing generic-materializer swe branch as `exclude_globs=`.
The load-bearing AC-2 negative test plants gold/`test_patch`/`FAIL_TO_PASS`
files, runs the full production path, and proves they leak when the globs are
reverted to the bare default. Open captain decisions: (1) the exact swe glob
set, (2) the offline-unverifiable assumption that harbor lands the gold/test
patch as sibling files (not inline in task.toml/verifier metadata) — Task 0
records this and HALTs to the captain if a future hydration shows inline.

## Stage Report: plan (cycle 2)

Reworked after a Codex antagonist review found 3 P1 + 1 P2. Root cause: `matches_denied_path` uses `fnmatch.fnmatch` where `*` CROSSES `/` — the cycle-1 broad `**/gold*`/`**/test_patch*` globs over-matched legit repo files.

- DONE: [P1] over-match / false positives
  Redesigned to a ROOT-ANCHORED set (no `**/<token>*`); added an allow-side test proving `docs/gold_notes.md`, `tests/test_patch_helpers.py`, `a/test_patch/file.py` are NOT stripped. Verified live via fnmatch.
- DONE: [P1] probe must DRIVE the set
  Task 0 now derives the glob set from the SWE answer-field format; the set is its explicit OUTPUT, not finalized blind. Covers plain `patch`/`patch.diff` per design doc :70-74.
- DONE: [P1] inherited default top-level hole
  Added bare `solution.patch`/`answer*`/`patch`/`patch.diff` (swe-scoped, not mutating the shared default). Plan's CRITICAL section states the default does NOT cover the top-level family. Verified `**/solution.*` misses root `solution.patch`.
- DONE: [P2] gold-dir reasoning
  Dropped the bare-vs-nested-dir closure claim; coverage is FILES under the answer path (`assert_no_denied_paths` only checks files/symlinks).
- DONE: re-verify final set over deny + allow lists
  16 deny + 16 allow paths through `matches_denied_path`: all deny match, all allow clean. Planted negative-test files all escape the bare default (AC-2 stays load-bearing).
- DONE: self-review
  Added a Codex-findings-resolved section to the plan self-review.

### Summary

Cycle-1 used broad `**/gold*`/`**/test_patch*` token globs that, under
`fnmatch` semantics (`*` crosses `/`), would strip legitimate files in the
real django/astropy repos swe-bench-pro ships — corrupting the benchmark.
Cycle-2 anchors every SWE answer-artifact glob at the task ROOT
(`gold/**`, `gold_patch*`, `test_patch*`, `FAIL_TO_PASS*`, `PASS_TO_PASS*`,
`patch`, `patch.diff`, `solution.patch`, `answer*`), closing the inherited
default's top-level hole swe-scoped, and adds a load-bearing allow-side test.
Final glob set: `SWE_BENCH_PRO_DENY_GLOBS = DEFAULT + (gold/**, gold_patch*,
gold.patch, test_patch*, FAIL_TO_PASS*, PASS_TO_PASS*, patch, patch.diff,
solution.patch, answer*)`. **[SUPERSEDED by cycle 3 — this `DEFAULT + (...)`
form still inherited the broad cross-`/` globs that over-match nested repo
files (`**/answer*` denies `src/answer_engine.py`). Cycle 3 replaced it with a
STANDALONE curated tuple; see the cycle-3 report for the authoritative set.]**
Residual captain decisions: (1) exact harbor
answer filenames; (2) explicit no-blanket-`*.patch` judgement; (3) bare
`patch`/`answer*` root-segment surface; (4) inline-patch escalation hook.

## Stage Report: plan (cycle 3)

Reworked per captain decision on deny-glob scope: curate a precise swe set; do NOT inherit the broad cross-`/` default globs.

- DONE: standalone curated set, NOT `DEFAULT + (...)`
  `SWE_BENCH_PRO_DENY_GLOBS` is now a standalone tuple; dropped `**/answer*`/`**/solution.*`/`**/*answers*`. A test asserts those are absent and the set is not a default superset.
- DONE: re-verify with fnmatch deny/allow probe
  19 deny match; 18 allow clean INCLUDING `src/answer_engine.py`, `lib/myanswers.py`, `pkg/solution_helpers.py`, `src/solution_loader.py`, `config/answers_schema.json` + the earlier set. Reproduced via `python -c 'import fnmatch...'`.
- DONE: AC-2 negative test stays load-bearing
  Revert baseline is the curated set with the answer-artifact globs removed (`solution/**`,`solutions/**`,`tests/expected/**`); verified the 5 planted task-root patch files all escape it, so revert truly leaks.
- DONE: [P2a] root-token collision note lists ALL collisions
  Captain-decision 3 names `answer*`/`answers*`/`gold_patch*`/`test_patch*`/`gold.patch`/`solution.*`/`patch` with their hypothetical-root files; nested forms NOT denied.
- DONE: [P2b] stale `**/gold/**` claim removed
  Corrected the cycle-1 DONE line (marked SUPERSEDED); the final set has no `**/gold/**`.
- DONE: flag default over-broad for repo benchmarks (NOT fixed)
  Plan's "Separate observation" section flags the shared default as a possible follow-up entity; E2 does not touch it.

### Summary

Captain chose a STANDALONE curated set over `DEFAULT + (...)`: the inherited
`**/answer*`/`**/solution.*`/`**/*answers*` strip nested repo files like
`src/answer_engine.py` under `fnmatch` (`*` crosses `/`). The final set is
`SWE_BENCH_PRO_DENY_GLOBS = (solution/**, solutions/**, tests/expected/**,
solution.*, answer*, answers*, gold/**, gold_patch*, gold.patch, test_patch*,
FAIL_TO_PASS*, PASS_TO_PASS*, patch, patch.diff, solution.patch)` — all
root-anchored task-root answer artifacts, no broad `**/<token>` forms. AC-2's
revert baseline drops the answer-artifact globs and the planted task-root
patches are verified to leak through it. Residual captain decisions: (1)
exact harbor answer filenames; (2) no-blanket-`*.patch`; (3) the full
root-token collision surface; (4) inline-patch escalation hook. Flagged
(out of scope): the shared default remains over-broad for future repo-based
benchmarks.

## Stage Report: implementation

- DONE: Task 0 — probe the resolved swe shape, derive the STANDALONE curated set, record assumption
  fnmatch probe reproduced (`**/answer*` strips `src/answer_engine.py`; root-anchored `answer*` does not); probe note `docs/razorback-implementation/plans/swe-bench-pro-leakage-probe-note.md` committed; sibling-file assumption documented, no inline-patch HALT (commit d5a7a11).
- DONE: AC-1 — Task 1: add STANDALONE `SWE_BENCH_PRO_DENY_GLOBS` curated tuple
  TDD red (ImportError) → green; standalone/deny/allow tests pass (commit cfcf75f).
- DONE: AC-1 — Task 2: plant task-root answer fixtures + positive materialize test
  fixture-001 gains `gold/gold_patch.diff`, `test_patch.diff`, `FAIL_TO_PASS.json`, legit nested `src/answer_engine.py`; materialize strips answers, keeps nested file (commit d4f8a57).
- DONE: AC-3 — Task 3: wire the swe `_build_harbor` branch to pass `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS`
  import + branch edit at translate.py:432; E1 suite still 10/10 (commit 431041b).
- DONE: AC-2 — Task 4: negative leakage test (plant → materialize → assert excluded → revert → assert leaks)
  forward + revert halves pass; load-bearing proven by collapsing the constant (4 tests fail incl. forward + `pytest.raises(LeakageError)`), then reverted (commit 529d23f).
- DONE: AC-3 — Task 5: runtime spy + static `grep -F` assert the branch passes the curated set
  spy captures `SWE_BENCH_PRO_DENY_GLOBS` (!= default); grep finds the wiring line (commit 5cb8efa).
- DONE: Task 6 — full acceptance + regression + ruff gate
  `pytest tests/ -k 'swe_bench_pro and leak'` → 9 passed; swe+spider2 regression 30/30; ruff clean on changed files (import consolidation, commit e6b84d7).
- DONE: Honor Out of scope
  No `rk audit` SWE signatures; no view content transform; shared `DEFAULT_SOLUTION_DENY_GLOBS` untouched (git diff: no removals); default-over-broad observation FLAGGED only.

### Implementation summary

Modules touched: `src/razorback/harbor_tasks/leakage.py` (added the STANDALONE
curated `SWE_BENCH_PRO_DENY_GLOBS` tuple beside the shared default, which is
left byte-for-byte unchanged) and `src/razorback/translate.py` (import +
swe-bench-pro `_build_harbor` branch now passes
`exclude_globs=SWE_BENCH_PRO_DENY_GLOBS`). Tests/fixtures:
`tests/unit/test_swe_bench_pro_leakage.py` (new; every test name contains
`leak`) and three task-root answer artifacts + one legit nested repo file added
to `tests/fixtures/swe_bench_pro/.../swe-bench-pro-fixture-001/`. Final set:
`(solution/**, solutions/**, tests/expected/**, solution.*, answer*, answers*,
gold/**, gold_patch*, gold.patch, test_patch*, FAIL_TO_PASS*, PASS_TO_PASS*,
patch, patch.diff, solution.patch)` — all root-anchored; no broad `**/<token>`
forms. Deviation: the plan appended test imports mid-file (TDD authoring
convenience), which tripped ruff E402; consolidated all imports to the top in a
follow-up style commit (e6b84d7) — no behavior change, tests stay green.
Full suite: 853 passed, 4 pre-existing failures (test_codex_runtime_dispatch,
test_worktree_remove_force, test_matrix_specs_carry_query_mode_batch,
test_rk_research_new) confirmed identical on main — not regressions.

## Stage Report: validation

- DONE: Confirm worktree clean + at branch tip
  `git status` clean, tip `a06a51d`; base `main` @ `31d796e`.
- DONE: Independently re-derive fnmatch evidence against IMPLEMENTED set
  Own probe (leakage.py:38-56 verbatim): 14/14 allow clean incl. `src/answer_engine.py`; 14/14 deny matched; broad `**/answer*`/`**/solution.*`/`**/*answers*` ABSENT (standalone). PASS.
- DONE: AC-1 — view excludes answers, keeps nested files
  `pytest -k 'swe_bench_pro and leak'` → 9 passed; positive materialize test green. PASS.
- DONE: AC-2 LOAD-BEARING revert check
  Reverted constant to `(solution/**,solutions/**,tests/expected/**)` → 4 failed (incl. production-path leak + `LeakageError` DID NOT RAISE); restored → 8 passed. Genuinely load-bearing. PASS.
- DONE: AC-3 wiring
  `grep -nF` → translate.py:432 `exclude_globs=SWE_BENCH_PRO_DENY_GLOBS`; runtime spy captured curated set != default. PASS.
- DONE: Shared default + generic materializer param unchanged
  `git diff main -- leakage.py` shows only additions; `DEFAULT_SOLUTION_DENY_GLOBS` (7-14) and materialize.py:36 default param untouched.
- DONE: Full suite + regression-vs-preexisting
  853 passed, 4 failed; throwaway detached `main` worktree confirms all 4 PRE-EXISTING (SWE set absent there) — not regressions. E1 swe + spider2 green.
- DONE: Deviation scrutiny (ruff E402)
  `git show e6b84d7`: test-file-only import consolidation, identical symbols, no behavior change. Benign.
- DONE: Code review (superpowers:requesting-code-review, base main)
  No blocking. Two Important under-match findings (case-sensitivity; `gold.diff` variant) + one Minor (nested dirs) independently reproduced — all reduce to captain-decision-1 (exact harbor filenames, unhydrate-able offline), not AC failures, not over-match.

### Summary

Independent verifier reproduced all 3 ACs from the committed branch: AC-1/AC-2/AC-3 PASS,
with the AC-2 revert proof (4 tests fail on revert incl. a real production-path leak and a
LeakageError no-raise) confirming the negative test is load-bearing. The independent fnmatch
probe confirms `src/answer_engine.py` is clean, all task-root answer artifacts are denied, and
the set is standalone. Shared `DEFAULT_SOLUTION_DENY_GLOBS` and the generic materializer default
param are byte-for-byte unchanged; the 4 full-suite failures are confirmed pre-existing on main.
Code review found no blocking issues — the under-match shapes (casing, `gold.diff`, nested dirs)
are the already-flagged captain-verifiable filename assumption, recommended for captain
confirmation at merge but not gate-blocking. **GATE: APPROVE.** Full report:
`docs/razorback-implementation/validation/swe-bench-pro-leakage-audit-deny-globs.md`.

## Feedback Cycles

### Cycle 1 — validation gate REJECTED (2026-06-24)

A Codex adversarial diff review + captain decision found: the root-anchored
deny set is correct for the ASSUMED task-root-sibling layout, but the tests
only model that layout, so the implementation would SILENTLY LEAK if harbor
nests answer artifacts under a checkout/metadata dir
(`repo/test_patch.diff`, `meta/gold_patch.diff` → root-only globs miss them →
answers reach the agent, scores invalid, no signal). Fix directed: add a
FAIL-CLOSED deep-scan guard (`assert_no_swe_answer_leak`) that scans the
materialized view at ALL depths by PRECISE answer-artifact signature (exact
basenames, not broad token globs) and raises `LeakageError` so a wrong layout
fails LOUD; wire it into the swe `_build_harbor` branch AFTER materialize as
the backstop (copy-time deny-globs stay as best-effort stripping). Also: add
`gold.diff` to the deny set + guard, make the guard case-insensitive, and keep
the top-level-collision over-match a documented residual tied to
captain-decision #1 (real layout). Addressed in cycle 2 below.

## Stage Report: implementation (cycle 2)

- DONE: PRIMARY FIX — fail-closed deep-scan leak guard `assert_no_swe_answer_leak`
  Added to `leakage.py`; deep-scans at all depths, raises `LeakageError` by precise signature. Helper `is_swe_answer_artifact` exact basenames (case-insensitive) + `gold_patch.*` glob + files directly under a `gold/` dir at any depth. No broad token globs (commit 11b85e7).
- DONE: wire the guard into the swe `_build_harbor` branch AFTER materialize
  Converted the comprehension to a loop; each view calls `assert_no_swe_answer_leak(view)` after `materialize_harbor_task_view` returns (translate.py).
- DONE: TDD (a) NESTED-LEAK test (load-bearing)
  `test_swe_answer_leak_guard_raises_on_nested_answers_leak` + production-path `test_swe_branch_deep_guard_raises_on_nested_leak_in_production_leak`. Both proven load-bearing (neuter guard / remove wiring → FAIL; restore → pass).
- DONE: TDD (b) NO-FALSE-POSITIVE test
  `test_swe_answer_leak_guard_allows_legit_nested_repo_files_leak` — `tests/test_patch_helpers.py`, `src/answer_engine.py`, `lib/patch.py`, `docs/gold_notes.md`, `a/test_patch/file.py` etc. do NOT trip the guard.
- DONE: TDD (c) HAPPY-PATH test
  `test_swe_answer_leak_guard_happy_path_after_root_strip_leak` — root answers stripped by deny-globs, guard passes, legit nested `src/answer_engine.py` survives.
- DONE: P2 — filename variants
  Added `gold.diff` to BOTH `SWE_BENCH_PRO_DENY_GLOBS` and the guard basenames. Guard normalizes basename to lowercase (case-insensitive) — documented as a safe superset since SWE-bench canonical names are lowercase.
- DONE: over-match residual documented (not over-scoped)
  Top-level repo file literally named `patch`/`test_patch*`/`solution.*` or a top-level `tests/expected/` dir is still stripped IF harbor flattens the repo at the task root. Kept as a documented residual tied to captain-decision #1 (real layout); allow-tests unbroken. The deep guard is precise (exact names) so it does NOT add over-match.
- DONE: record-keeping + plan note + gates
  `## Feedback Cycles` / `### Cycle 1` added; plan doc gains a cycle-2 guard-task note; `pytest tests/ -q` → 857 passed / 4 pre-existing failures (unchanged) / 12 skipped; ruff clean on changed files; shared default + generic pass-through byte-identical to main.

### Implementation summary (cycle 2)

Modules touched: `src/razorback/harbor_tasks/leakage.py` (new
`assert_no_swe_answer_leak` deep-scan guard + `is_swe_answer_artifact` helper;
`gold.diff` added to the curated deny set; shared `DEFAULT_SOLUTION_DENY_GLOBS`
unchanged) and `src/razorback/translate.py` (import the guard; swe branch loop
calls it after each materialize as the fail-closed backstop). Tests:
`tests/unit/test_swe_bench_pro_leakage.py` gains 4 cycle-2 tests (3 guard unit
tests + 1 production-wiring test); both leak tests proven load-bearing.
The guard uses PRECISE signatures (exact case-insensitive basenames, a
`gold_patch.*` glob, and the immediate-`gold/`-dir rule) — deliberately not
broad token globs — so deep-scanning at all depths catches nested answers
without false-positiving legit nested repo files. No deviation from the
cycle-2 brief; the over-match residual is documented, not narrowed, per the
captain's leak-first priority.

## Stage Report: validation (cycle 2)

- DONE: Worktree clean + at branch tip
  `git status` clean; `git log --oneline main..HEAD` shows cycle-2 guard commits 11b85e7 + f3e8b66 at tip. PASS.
- DONE: THE GUARD (2) — read `assert_no_swe_answer_leak`+`is_swe_answer_artifact` (leakage.py:93-131); wired at translate.py:446 AFTER materialize (line 433) in the swe else-branch, before `task_paths.append` → production, not test-only. PASS.
- DONE: 2a — raises on NESTED answers
  Own tmp-dir probe: `repo/test_patch.diff`, `meta/gold_patch.diff`, `repo/sub/FAIL_TO_PASS.json`, `gold/anything.txt` all → `is_swe_answer_artifact`=True; `assert_no_swe_answer_leak` RAISED LeakageError listing all 4. Named tests pass (12/12). PASS.
- DONE: 2b — NO false positive on legit nested files
  Own probe: `tests/test_patch_helpers.py`, `src/answer_engine.py`, `lib/patch.py`, `docs/gold_notes.md`, `a/test_patch/file.py`, `src/patches/apply.py`, `config/answers_schema.json` all → False; `assert_no_swe_answer_leak` on legit-only view did NOT raise. PASS.
- DONE: 3 — LOAD-BEARING
  Neutered `is_swe_answer_artifact` → `return False`: 2 nested-leak tests FAILED ("DID NOT RAISE LeakageError"), incl. production-path `test_swe_branch_deep_guard_raises_on_nested_leak_in_production_leak`. Restored → 2 passed, git diff clean. Genuinely load-bearing. PASS.
- DONE: 4 — 3 original ACs still green
  `pytest -k 'swe_bench_pro and leak'` → 13 passed. AC-2 independent revert (dropped answer-artifact globs) → 5 tests FAIL (planted root answers no longer glob-stripped; deep guard still catches them). Load-bearing confirmed. PASS.
- DONE: 5 — case-insensitivity (P2)
  Own probe: `Gold.patch`, `GOLD_PATCH.DIFF`, `gold.diff`, `Test_Patch.diff`, `FAIL_TO_PASS.JSON` all → True (basenames case-folded). PASS for basenames.
- FAILED: 5 — case-insensitivity is INCOMPLETE for the `gold/` dir rule
  `is_swe_answer_artifact('x/Gold/secret.diff')`=False, `'x/GOLD/secret.diff')`=False, but `'x/gold/secret.diff')`=True. The `gold/`-parent rule (leakage.py:106) compares case-SENSITIVELY while basenames are case-folded — partial implementation of the cycle-1-directed "make the guard case-insensitive". The code comment (leakage.py:73-76) claims case-fold is a "safe superset" — NOT true for the dir rule. Reachable shape: an answer file under a `Gold/` dir leaks silently. BLOCKING.
- DONE: 6 — shared default + pass-through unchanged
  `git diff main -- leakage.py` = NO REMOVALS (additions only); `DEFAULT_SOLUTION_DENY_GLOBS` byte-identical on main (7-14); `materialize.py:36` default param still `DEFAULT_SOLUTION_DENY_GLOBS`; `git diff main --stat` touches NO `src/razorback/benchmarks/` (spider2/ade pass-through untouched). PASS.
- DONE: 7 — full suite + 4-failure pre-existing
  `pytest tests/ -q` → 857 passed, 4 failed, 12 skipped. The 4 (test_codex_runtime_dispatch, test_worktree_remove_force, test_matrix_specs_carry_query_mode_batch, test_rk_research_new) reproduce on a throwaway detached `main` worktree where the SWE guard is ABSENT (grep count 0) → pre-existing, not regressions. E1 swe+spider2: 121 passed. PASS.
- DONE: 8 — code review (superpowers:requesting-code-review, base main)
  1 Important (the case-sensitive `gold/` dir compare — independently reproduced above), 2 Minor (basename-glob redundancy; dir-symlink scan-stop latent coupling). Reviewer verdict "With fixes". Over-match residual = captain-decision #1, accept-as-documented (over-strip not under-strip). Uncovered leak shapes (bare `gold` no-ext, non-answer-named `*.patch`, non-`gold/` nested dir like `solution/the_fix.diff`/`meta/answer.patch`) all collapse to captain-decision #1 (unknowable offline filenames).

### Summary (validation cycle 2)

GATE: **REJECT → implementation.** The cycle-2 deep-scan guard genuinely closes the
nested-leak hole and is LOAD-BEARING (neuter → 2 nested-leak tests fail incl. the
production-path one; restore → green) with NO false positive on the 7 legit nested
repo files, wired into production at translate.py:446 after materialize. The 3
original ACs stay green (AC-2 revert load-bearing), the shared default + generic
pass-through are byte-identical to main, and the 4 full-suite failures are confirmed
pre-existing on a clean-main worktree. ONE blocking gap: cycle-1 explicitly directed
"make the guard case-insensitive", but `is_swe_answer_artifact` case-folds only the
basename — the `gold/` parent-dir rule (leakage.py:106) compares case-sensitively, so
`Gold/secret.diff` / `GOLD/x.diff` leak silently while `gold/x.diff` raises. The code's
own "safe superset" claim is false for the dir rule. CONCRETE FIX (one word):
`leakage.py:106` change `parts[-2] == _SWE_ANSWER_PARENT_DIR` →
`parts[-2].lower() == _SWE_ANSWER_PARENT_DIR`, and add a `Gold/`-nested-dir case to the
guard-raises test. Re-validate: case-folded dir rule catches `Gold/`/`GOLD/`. The two
Minor findings (basename-glob redundancy, dir-symlink scan-stop) and all uncovered
unknowable-filename leak shapes remain captain-decision #1 and are non-blocking.
