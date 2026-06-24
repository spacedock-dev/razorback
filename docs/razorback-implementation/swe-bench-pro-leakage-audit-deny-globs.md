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
