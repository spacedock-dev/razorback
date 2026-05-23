---
id: k05te9qfkv1at7qh3zay5naf
title: Historical wallclock ordering hints for job dispatch
status: plan
source: Captain directive 2026-05-23 - "optionally ordering the job based on a previous run result file as ordering hint"
started: 2026-05-23T00:47:29Z
completed:
verdict:
score: 0.75
worktree:
issue:
pr:
mod-block:
---

## Problem

Harbor's trial queue dispatches tasks in the order Razorback gives it.
For parallel benchmark runs, that means a long-running task near the end
of the input list can become the tail that dominates wallclock time.

Razorback should optionally accept historical run results as a task
ordering hint. When prior wallclock data is available, a run can dispatch
known slow tasks first while preserving deterministic behavior for tasks
without timing history.

## Acceptance criteria

**AC-1 - Optional ordering hint input.**
`rk run` accepts a previous run artifact or run directory as an optional
ordering hint source. The default behavior is unchanged when no hint is
provided.
Verified by: a CLI/spec test covers both default order and hinted order.

**AC-2 - Wallclock extraction is robust.**
Razorback extracts per-task elapsed wallclock from existing result
artifacts when `started_at` and `finished_at` or equivalent fields are
available. Missing, malformed, or incomplete timing data is ignored with
a clear warning.
Verified by: fixture tests cover complete timing, missing fields, and
partial historical coverage.

**AC-3 - Longest-known-first scheduling.**
When enabled, tasks with known prior wallclock are sorted descending by
elapsed time before building the Harbor `JobConfig`; unknown tasks retain
their original relative order under a documented tie policy.
Verified by: a concurrency >1 queue test asserts the first scheduled
tasks are the historical longest tasks.

**AC-4 - Results semantics do not change.**
Ordering changes dispatch order only. Trial identity, task ids, scoring,
provenance, audit output, and result aggregation remain tied to the
original benchmark task identifiers.
Verified by: `rk score` over a hinted run produces the same task-keyed
shape as an equivalent unhinted run.

**AC-5 - Provenance records the hint.**
Frozen specs or run metadata record the hint file path, ordering mode,
and number of tasks with usable timing data so the scheduling choice is
reproducible.
Verified by: a sampled run manifest/provenance file contains those
fields.

## Test plan

- Unit: parse historical result fixtures into `{task_id: seconds}`.
- Unit: stable longest-known-first ordering with unknown-task tie policy.
- Integration: build a small Harbor-backed job with `max_concurrency > 1`
  and assert the queued trial order follows the hint.
- Regression: default `rk run` without a hint preserves input order.

## Out of scope

- Changing Harbor's queue implementation.
- Dynamic reprioritization after a run has started.
- Predicting durations for tasks with no history.
- Treating wallclock as a score metric.

## Notes

Installed Harbor has no built-in wallclock or priority scheduling hook.
The implementation should reorder Razorback's task list before handing
the job to Harbor rather than patching Harbor internals.
