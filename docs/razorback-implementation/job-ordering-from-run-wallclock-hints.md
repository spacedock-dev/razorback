---
id: k05te9qfkv1at7qh3zay5naf
title: Historical wallclock ordering hints for job dispatch
status: validation
source: Captain directive 2026-05-23 - "optionally ordering the job based on a previous run result file as ordering hint"
started: 2026-05-23T00:47:29Z
completed:
verdict:
score: 0.75
worktree: .worktrees/spacedock-ensign-job-ordering-from-run-wallclock-hints
issue:
pr:
mod-block: merge:pr-merge
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

## Stage Report: plan

- DONE: Plan maps AC-1 through AC-5 to concrete implementation tasks, tests, and verification commands.
  Evidence: `plans/job-ordering-from-run-wallclock-hints.md` has an AC-to-task map and Tasks 1-8 with targeted `uv run pytest` commands.
- DONE: Plan identifies exact likely code surfaces for ordering before Harbor `JobConfig`, historical wallclock extraction, and provenance/manifest recording.
  Evidence: the plan names `src/razorback/run_ordering.py`, `src/razorback/cli/run.py`, `src/razorback/runs/aggregate.py`, `src/razorback/provenance/provenance_yaml.py`, and `src/razorback/translate.py`.
- DONE: Plan calls out risks around default-order compatibility, task identity/scoring invariance, and partial/missing historical timing data.
  Evidence: the plan's Risks and Guardrails section covers all three risks explicitly.

### Summary

Wrote the standard separate implementation plan at `docs/razorback-implementation/plans/job-ordering-from-run-wallclock-hints.md`. The plan keeps the riskiest contract first by parsing historical timing and validating the `rk run -> spec_to_job_config -> ordered JobConfig.tasks -> _job_config.yaml` path before broader regression checks.

## Stage Report: implementation

- DONE: Implements optional `rk run --order-from-run` behavior with default no-hint task order unchanged.
  Evidence: `tests/unit/test_rk_run_ordering_hint_cli.py` asserts no-hint `_job_config.yaml` order stays `[short, unknown, long]` and hinted order becomes `[long, short, unknown]`; commits `518a030` and `fbb8b09`.
- DONE: Adds robust historical wallclock parsing and stable longest-known-first task ordering with tests for missing/malformed/partial timings.
  Evidence: `tests/unit/test_run_ordering.py` covers max repeated timing, missing `finished_at`, malformed timestamps, single result files, unknown tasks, ties, and empty summaries; commits `db9e249` and `1212642`.
- DONE: Records ordering hint metadata in run artifacts/provenance without changing task identity/scoring semantics.
  Evidence: manifest/provenance metadata is asserted in `tests/unit/test_rk_run_ordering_hint_cli.py`, and reordered scoring identity invariance is asserted in `tests/unit/test_task_identity_scoring.py`; commits `fbb8b09` and `97b375b`.

### Summary

Added `src/razorback/run_ordering.py` for historical wallclock extraction and deterministic longest-known-first sorting, then wired `src/razorback/cli/run.py` to apply it after translation and before Harbor serialization. Harbor-facing changes are limited to the `JobConfig.tasks` list order; additive `ordering_hint` metadata is written through `src/razorback/runs/aggregate.py` and `src/razorback/provenance/provenance_yaml.py`. No plan deviations were needed; the requested `superpowers` sub-skill was unavailable in this session, so the approved plan was executed directly with TDD commits.

## Stage Report: validation

- DONE: Independently verifies AC-1 through AC-5 with code inspection and concrete command output.
  Evidence: `docs/razorback-implementation/validation/job-ordering-from-run-wallclock-hints.md` records PASS evidence per AC from focused pytest output and inspection of `run_ordering.py`, `cli/run.py`, `runs/aggregate.py`, and `provenance_yaml.py`.
- DONE: Runs the focused ordering/provenance/scoring/translator regression tests or reports exact blockers.
  Evidence: focused commands passed with `18 passed`, `16 passed`, and `3 passed`; full `uv run pytest` was also run and failed with `6 failed, 566 passed, 9 skipped`.
- DONE: Writes a validation report with blocking/non-blocking findings and an explicit gate decision of PASSED or REJECTED.
  Evidence: validation report written at `docs/razorback-implementation/validation/job-ordering-from-run-wallclock-hints.md` with gate decision `REJECTED`.

### Summary

Validation reproduced the focused AC evidence and found the feature-specific behavior passes those targeted checks. The gate is rejected because full `uv run pytest` fails, including two branch-local unit regressions from new `ordering_hint` keyword plumbing in existing test doubles; no production code was edited during validation.

### Feedback Cycles

#### Cycle 1 - validation rejected 2026-05-23

Route back to implementation. Validation found focused AC suites passing, but
full `uv run pytest` failed. The branch-local fixes are:

- `tests/unit/test_cli_run_aggregator_wiring.py:43` - update the
  `safe_aggregate_run_dir` test double/capture to accept the additive
  `ordering_hint` keyword so the capture still records `benchmark_kind`.
- `tests/unit/test_run_plugin_drift_wired.py:123` - update the patched
  `_write_provenance_artifacts` capture to accept the additive
  `ordering_hint` keyword.

The remaining full-suite failures are environment/integration failures noted
in the validation report and do not need production-code fixes for this cycle.

## Stage Report: implementation (cycle 2)

- DONE: Fixes both branch-local test double regressions from additive `ordering_hint` keyword plumbing.
  Evidence: updated the aggregator and provenance patched captures in `tests/unit/test_cli_run_aggregator_wiring.py` and `tests/unit/test_run_plugin_drift_wired.py` to accept `ordering_hint=None`.
- DONE: Reruns the two failing unit tests and focused ordering/provenance suites.
  Evidence: the two rejected tests passed (`2 passed`), and the focused ordering/provenance/scoring suite plus those tests passed (`20 passed`).
- DONE: Leaves unrelated full-suite environment failures untouched and documented.
  Evidence: no production code or integration/environment tests were changed; unrelated failures remain documented in `docs/razorback-implementation/validation/job-ordering-from-run-wallclock-hints.md`.

### Summary

Fixed only the branch-local test double regressions identified by validation feedback cycle 1. The production `ordering_hint` call contract remains unchanged, and verification covered the two rejected tests plus the focused feature suites.

## Stage Report: validation (cycle 2)

- DONE: Independently verifies AC-1 through AC-5 after feedback cycle 1 with code inspection and concrete command output.
  Evidence: validation report records PASS for AC-1 through AC-5, including code inspection of `run_ordering.py`, `cli/run.py`, `runs/aggregate.py`, and `provenance_yaml.py` plus focused pytest output.
- DONE: Reruns the previously failing branch-local tests plus focused ordering/provenance/scoring/translator regression tests, or reports exact blockers.
  Evidence: required focused commands passed with `2 passed`, `26 passed`, `16 passed`, and `3 passed`; optional full suite was run and only unrelated integration/environment failures remain.
- DONE: Writes/updates the validation report with blocking/non-blocking findings and an explicit gate decision of PASSED or REJECTED.
  Evidence: `docs/razorback-implementation/validation/job-ordering-from-run-wallclock-hints.md` now includes cycle-2 blocking/non-blocking findings and gate decision `PASSED`.

### Summary

Cycle-2 validation accepted the feedback fix in `044da5e`: the two previously failing branch-local unit tests now pass, and the broader focused ordering/provenance/scoring/translator suites pass. The optional full suite still has the known external DAB data and nop events integration failures, classified as non-blocking for this ordering-hint gate.
