---
id: zkn663pcbvd5sbaaxwx5f1z5
title: swe-bench-pro — leakage deny-globs (gold/test patch isolation)
status: plan
source: docs/superpowers/specs/2026-06-24-swe-bench-pro-on-harbor-design.md (E2); harbor_tasks/leakage.py DEFAULT_SOLUTION_DENY_GLOBS + spider2-dbt deny-glob precedent
started: 2026-06-24T04:44:28Z
completed:
verdict:
score:
worktree:
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
  Chose `SWE_BENCH_PRO_DENY_GLOBS = DEFAULT_SOLUTION_DENY_GLOBS + (...)` in leakage.py (NOT a new harbor_view.py, NOT mutating the global default); justified inline.
- DONE: fnmatch top-level-dir hole handled
  Both bare (`gold/**`) and nested (`**/gold/**`) forms for denied dirs; cited spider2 precedent (`harbor_view.py:20-31`).
- DONE: Honor Out of scope
  No `rk audit` SWE signatures; no new view transform; escalation hook is a Task 0 HALT-and-surface.
- DONE: Verified glob set against live fnmatch
  Ran all 10 DENY + 5 ALLOW paths through `matches_denied_path`; every assertion in the plan's tests holds.

### Summary

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
solution.patch, answer*)`. Residual captain decisions: (1) exact harbor
answer filenames; (2) explicit no-blanket-`*.patch` judgement; (3) bare
`patch`/`answer*` root-segment surface; (4) inline-patch escalation hook.
