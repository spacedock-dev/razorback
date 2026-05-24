---
id: bpb83at5rrcm0z77maf6bbqb
title: Spacedock dispatch manifests are per trial
status: done
source: 2026-05-24 ADE full-run audit gap - parallel Spacedock run wrote one job-level subagent-trace-manifest.json
started: 2026-05-24T04:29:17Z
completed: 2026-05-24T05:04:16Z
verdict: PASSED
score: 0.93
worktree: 
issue:
pr:
mod-block:
archived: 2026-05-24T05:04:21Z
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

## Stage Report: implementation

- DONE: Per-trial Spacedock dispatch manifests and writer metadata are implemented with tests.
  `cee0990` updates `subagent_traces.py` and `spacedock_solver.py`; writer subset passed `9 passed`.
- DONE: Smoke/audit coverage handles per-trial, missing-trial, and legacy single-trial layouts.
  `9104b70` covers smoke validation and `d9d4be2` covers strict audit; acceptance subset passed `34 passed`.
- DONE: Score semantics and full ADE/DAB relaunch behavior remain untouched.
  No score reducer or full-run driver changes; score-adjacent guard passed `13 passed`.

### Summary

Implemented trial-scoped Spacedock dispatch manifests with additive `trial`, `prompt_mode`, and `trace_artifacts` metadata, and moved the Harbor post-run writer from the job root to each trial directory. Added run-dir smoke validation and a new `razorback.audit.dispatch_manifests` helper so strict audit enumerates Spacedock trials from `manifest.json` and fails closed on missing, malformed, or zero-capture dispatch coverage while preserving the legacy single-trial root fallback. Full ADE/DAB relaunch and score semantics remained out of scope per the approved plan.

## Stage Report: validation

- DONE: Validation independently reruns the manifest writer, smoke, audit, and score-guard test subsets.
  Writer subset `9 passed`; smoke subset `9 passed`; audit subset `16 passed`; score guard `13 passed`.
- DONE: Validation checks AC-1 through AC-4 with exact command output and files changed.
  Evidence recorded in `docs/razorback-implementation/validation/spacedock-dispatch-manifest-per-trial.md`.
- DONE: Validation report gives APPROVE or REJECT with blocking findings separated from non-blocking notes.
  Report gate is APPROVE; blocking findings: none; non-blocking findings: none.
- FAILED: Full project `uv run pytest` requested by the validation stage definition.
  Collection failed on pre-existing `tests/unit/test_task_identity_scoring.py` import of missing `razorback.score.load`; branch did not touch score package files.

### Summary

Validated the implementation range `dc3750d60e1867c19f2a1b4425e245666f5c7608..68d9e8cbf9203283892ad9d03edf31905ce8493a` against AC-1 through AC-4, including the T7 acceptance subset and score-adjacent guard. The validation gate is APPROVE to done, with the unrelated full-suite collection failure documented as residual baseline risk.
