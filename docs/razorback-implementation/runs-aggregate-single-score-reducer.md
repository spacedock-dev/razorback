---
id: 1svqbefxg8fd12cy2ssp2jes
title: Make run aggregation and rk score use one score reducer
status: validation
source: 2026-05-23 staff audit + rk-score validator follow-up - duplicate stratified reducers
started: 2026-05-23T17:24:54Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-runs-aggregate-single-score-reducer
issue:
pr:
mod-block: merge:pr-merge
---

## Problem

The v2 spec (§3.2) says `rk score` delegates to the same reducer that
produces `summary.json`, but the implementation still has two active
stratified pass@1 reducers in `runs/aggregate.py`:
`reduce_per_query_stratified` (used by `rk score`) and the private
`_stratified_pass_at_1` (used by `aggregate_summary` for
`summary.json`). The duplicate path lets headline scores drift between
command surfaces, and — more importantly — both reducers today binarize
the trial's composite `reward` field (`>= 1.0`), which silently zeros
DAB batch-mode cells whose `reward_per_query.json` sidecar carries
sub-binary aggregates. Example: yelp at composite reward `0.857`
(6/7 per-query) contributes `0` to `stratified_pass_at_1` instead of
`6/7`. The canonical reducer must consume `reward_per_query.json` for
DAB batch-mode trials so the per-query data on disk drives the
headline number. `benchmarks/dab/aggregate.py:_build_summary` (the
legacy DAB-native per-query reducer that `aggregate_job_result` uses
via `_load_per_query_rewards`) is the existing reference for this
behavior; the canonical reducer either dispatches to or merges from
it.

## Acceptance criteria

**AC-1 — One reducer is authoritative, and it consumes per-query rewards
for DAB batch-mode.**
`rk score` and run-dir aggregation both call the same reducer function
for stratified pass@1, and that reducer reads
`<trial_dir>/steps/main/verifier/reward_per_query.json` (with
`<trial_dir>/verifier/reward_per_query.json` as the single-step
fallback, matching `benchmarks/dab/aggregate.py:_load_per_query_rewards`)
when present. Per-query rows are grouped by `(dataset, query_id)` and
each cell's pass@1 is `(#per-query rewards >= 1.0) / n`. Wilson CI
attaches at the cell level; the dataset stratum stays mean-of-proportions
with `wilson_ci: null`.
Verified by: a unit test loads a fixture run-dir containing one
batch-mode DAB trial whose `reward_per_query.json` records 6 of 7
queries at `reward=1.0` and the seventh at `0.0` (composite
`reward=0.857`); the canonical reducer reports the cell's
`pass_at_1 = 6/7`, not `0.0`. Deleting `_stratified_pass_at_1` from
`runs/aggregate.py` leaves the test suite green; `aggregate_summary`
calls the same canonical reducer and writes the same
`stratified_pass_at_1` value into `summary.json` as `rk score`
prints, byte-for-byte, on the same run-dir.

**AC-2 — Legacy `datasets` JSON shape in `summary.json` is a render
adapter over the canonical reducer result.**
The `datasets` block written by `aggregate_summary` into `summary.json`
is produced by mapping the canonical `StratifiedReport.strata` into the
existing shape — no second scoring implementation. Existing
`summary.json` consumers (`rk runs diff`, fixtures, snapshots) see the
same field layout.
Verified by: tests assert the `summary.json` `datasets` shape on the
DAB and ADE fixtures matches the pre-change snapshot for per-query
mode (which already binarized correctly), and matches the new
per-query value for the batch-mode fixture introduced in AC-1.

**AC-3 — DAB batch-mode, DAB per-query, and ADE/Spider task-view fixtures
are all covered.**
The shared reducer preserves the existing DAB per-query and ADE/Spider
strata behavior (one trial = one query, composite reward already
binary) and adds correct DAB batch-mode handling (one trial = one
composite of N queries; reducer reads the sidecar).
Verified by: fixture tests cover three families — `mixed_trial_run_dir`
(DAB per-query, existing), `ade_bench_run_dir` (ADE/Spider task-view,
existing), and a new `dab_batch_run_dir` fixture with a
`reward_per_query.json` sidecar exercising the 6/7 case from
real run `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/yelp/…`.

**AC-4 — Spec conformance is checked end-to-end.**
The test suite has a regression that would fail if `summary.json` and
`rk score` produce different headline values for the same run
directory, including the DAB batch-mode case.
Verified by: `tests/integration/test_rk_score_matches_summary.py` is
extended with a third case using the AC-3 batch-mode fixture; the
paired assertion (`summary["stratified_pass_at_1"] ==
score["stratified_pass_at_1"]`) holds and the value is the per-query
mean, not the composite-binary mean.

## Plan

Plan doc: `docs/razorback-implementation/plans/runs-aggregate-single-score-reducer.md`.

## Stage Report: plan

- DONE: Expand AC-1 / AC-3 in the entity body to cover the binarization fix
  AC-1 widened to require per-query sidecar consumption + 6/7 yelp-style verification; AC-3 split into three fixture families (DAB batch, DAB per-query, ADE/Spider); legacy reducer `_legacy/benchmarks/dab/aggregate.py:_load_per_query_rewards` cited as reference; entity body re-numbered cleanly (now 4 ACs, same numbering as filed).
- DONE: Decide the plan output scope per README's flex rule
  4 ACs after widening → separate plan doc per README lines 150-158. Plan doc at `docs/razorback-implementation/plans/runs-aggregate-single-score-reducer.md` with AC↔task map table at top, code-surface map, spec §-cites per task.
- DONE: Sequence the riskiest contract first per CLAUDE.md mechanism-validation rule
  Plan Task 1 is the sole gating mechanism: fixture run-dir with `reward_per_query.json` (six at 1.0, one at 0.0) asserts `pass_at_1 == 6/7` from the canonical reducer. T2 (sidecar reader), T3 (delete `_stratified_pass_at_1`), T4 (render-adapter), T5 (fixture coverage), T6 (paired integration) all gate on T1 going green per plan's "Mechanism Validation First" section.

### Summary

The plan keeps `reduce_per_query_stratified` as the single canonical reducer and moves the behavior fix into `read_trial_outcomes` — fan a batch trial into N outcome rows when `reward_per_query.json` exists, otherwise preserve today's one-row-per-trial path. `aggregate_summary` is rewritten to call the canonical reducer and render its `StratifiedReport` into the existing `summary.json` `datasets` shape; `_stratified_pass_at_1` is deleted. Riskiest contract is the sidecar parser + outcome-fan path, validated end-to-end by Task 1's 6/7 fixture before any downstream rewrite. Out of scope: the `goal1-rerun` 12/12 recompute (separate follow-on dispatch) and any change to `per_trial_outcomes.json` / `rk runs diff`.
