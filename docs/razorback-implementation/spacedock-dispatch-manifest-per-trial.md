---
id: bpb83at5rrcm0z77maf6bbqb
title: Spacedock dispatch manifests are per trial
status: plan
source: 2026-05-24 ADE full-run audit gap - parallel Spacedock run wrote one job-level subagent-trace-manifest.json
started: 2026-05-24T04:29:17Z
completed:
verdict:
score: 0.93
worktree:
issue:
pr:
mod-block:
---

## Problem

Full parallel `spacedock_solver` runs currently collapse FO dispatch
provenance to one job-level `subagent-trace-manifest.json`. That is not enough
for strict audit of a full ADE or DAB score because each trial must prove its
own Spacedock dispatch prompt, worker identity, and trace location.

## Acceptance criteria

**AC-1 - Full parallel runs emit one dispatch manifest per trial.**
Each `spacedock_solver` trial directory has a
`subagent-trace-manifest.json` or equivalent per-trial trace manifest that
names the trial, prompt mode, dispatched worker, and trace artifact paths.
Verified by: an automated fixture with at least two parallel Spacedock trials
asserts both trial directories contain distinct manifests.

**AC-2 - Job-level provenance no longer overwrites trial provenance.**
If a job-level rollup is retained, it references all per-trial manifests and
does not replace or overwrite them.
Verified by: tests assert a two-trial run has two distinct manifest payloads
plus any rollup inventory, with no shared final-write collapse.

**AC-3 - Strict audit can fail closed on missing trial manifests.**
`rk audit --policy strict` reports missing Spacedock dispatch coverage for any
trial listed in the run manifest that lacks the per-trial dispatch manifest.
Verified by: an audit fixture with one manifest-bearing trial and one missing
trial emits a coverage failure for the missing trial.

**AC-4 - Smoke and legacy single-trial layouts keep working.**
Existing single-trial Spacedock smoke behavior remains readable by audit and
does not regress score output.
Verified by: the existing Spacedock solver prompt/provenance tests and a
single-trial audit fixture stay green.

## Test plan

Add focused unit or integration fixtures around the manifest writer and strict
audit discovery path, then run the relevant `uv run pytest` subset plus lint on
the touched files.

## Out of scope

Changing score semantics or relaunching the full ADE/DAB score run.

## Stage Report: plan

- DONE: Plan identifies the per-trial manifest writer and strict-audit discovery changes.
  Plan written at `docs/razorback-implementation/plans/spacedock-dispatch-manifest-per-trial.md`; see Surface Map and Tasks T1-T6.
- DONE: Plan maps concrete tests or fixtures to AC-1 through AC-4.
  AC map covers T1/T2 for AC-1 and AC-2, T5/T6 for AC-3, and T3/T4/T7 for AC-4 with named pytest files and fixtures.
- DONE: Plan keeps score semantics and full score relaunch out of scope.
  Plan Decisions and T7 explicitly exclude score reducer changes and full ADE/DAB score relaunches.

### Summary

Created a separate standard plan document for the four-AC task. The plan moves the dispatch manifest target from the job root to each trial directory, adds strict-audit trial coverage discovery from run `manifest.json`, preserves legacy single-trial readability, and leaves scoring behavior untouched.
