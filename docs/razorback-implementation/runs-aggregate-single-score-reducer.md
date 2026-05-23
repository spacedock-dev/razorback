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

### Feedback Cycles

**Cycle 1 — 2026-05-23 validation REJECT, routed back to implementation.**

Validator finding (commit `582987b`, blocking): `_load_reward_per_query`'s docstring at `src/razorback/runs/aggregate.py:197` contains the literal substring `benchmarks/dab` (inside the reference `_legacy/benchmarks/dab/aggregate.py:_load_per_query_rewards`), which is matched by the `forbidden` needle in `tests/unit/test_dab_retirement.py::test_active_code_does_not_import_in_tree_dab_adapter`. The branch introduces this as a new test failure; all four ACs otherwise pass functionally.

Routed back to implementation for a one-line docstring rewrite that drops the literal `benchmarks/dab` path token while preserving the design pointer (e.g. "mirrors the legacy DAB aggregator's per-query rewards loader" without the path). Re-run `uv run pytest tests/unit/test_dab_retirement.py` to confirm green, then signal complete for re-validation. Cycle count: 1 of 3.

## Stage Report: plan

- DONE: Expand AC-1 / AC-3 in the entity body to cover the binarization fix
  AC-1 widened to require per-query sidecar consumption + 6/7 yelp-style verification; AC-3 split into three fixture families (DAB batch, DAB per-query, ADE/Spider); legacy reducer `_legacy/benchmarks/dab/aggregate.py:_load_per_query_rewards` cited as reference; entity body re-numbered cleanly (now 4 ACs, same numbering as filed).
- DONE: Decide the plan output scope per README's flex rule
  4 ACs after widening → separate plan doc per README lines 150-158. Plan doc at `docs/razorback-implementation/plans/runs-aggregate-single-score-reducer.md` with AC↔task map table at top, code-surface map, spec §-cites per task.
- DONE: Sequence the riskiest contract first per CLAUDE.md mechanism-validation rule
  Plan Task 1 is the sole gating mechanism: fixture run-dir with `reward_per_query.json` (six at 1.0, one at 0.0) asserts `pass_at_1 == 6/7` from the canonical reducer. T2 (sidecar reader), T3 (delete `_stratified_pass_at_1`), T4 (render-adapter), T5 (fixture coverage), T6 (paired integration) all gate on T1 going green per plan's "Mechanism Validation First" section.

### Summary

The plan keeps `reduce_per_query_stratified` as the single canonical reducer and moves the behavior fix into `read_trial_outcomes` — fan a batch trial into N outcome rows when `reward_per_query.json` exists, otherwise preserve today's one-row-per-trial path. `aggregate_summary` is rewritten to call the canonical reducer and render its `StratifiedReport` into the existing `summary.json` `datasets` shape; `_stratified_pass_at_1` is deleted. Riskiest contract is the sidecar parser + outcome-fan path, validated end-to-end by Task 1's 6/7 fixture before any downstream rewrite. Out of scope: the `goal1-rerun` 12/12 recompute (separate follow-on dispatch) and any change to `per_trial_outcomes.json` / `rk runs diff`.

## Stage Report: implementation

- DONE: Execute Task 1 (Mechanism Validation First — RED 6/7 fixture)
  Fixture `tests/fixtures/score/dab_batch_run_dir/yelp__Cc94VEd/` (composite reward 0.857, sidecar of six 1.0s + one 0.0) + RED test `tests/unit/test_runs_aggregate_per_query_reducer.py::test_batch_mode_reads_reward_per_query_sidecar` committed at 56f9290; confirmed RED ("{None: 0}" vs expected "{1:1,...,4:0,...,7:1}") before any production code change.
- DONE: Execute plan Tasks 2-4 (T2 sidecar reader; T3 delete `_stratified_pass_at_1`; T4 render adapter)
  T2 (commit 290d958): added `_load_reward_per_query` (mirrors legacy `_load_per_query_rewards`) and `_fan_batch_trial` in `src/razorback/runs/aggregate.py`; `read_trial_outcomes` now emits one row per `qN` when the sidecar exists. T1 went GREEN; aggregate unit tests still pass (22/22). T3+T4 (commit fb4732b): `_stratified_pass_at_1` deleted, `aggregate_summary` rewritten to call `reduce_per_query_stratified` with explicit `trial_counts` so trial accounting stays per physical trial despite fanning; `_render_legacy_datasets(report)` maps `StratifiedReport.strata` into the legacy `{dataset_pass_at_1, n_queries, queries:[{query_id,n_trials,n_correct,pass_at_1}]}` shape verbatim (no per-cell wilson_ci, no stratum-level metadata). `rk score` CLI passes the same override via the new public `count_trials(run_dir)` helper. `grep '_stratified_pass_at_1' src/ tests/` returns 0 matches outside `_legacy/`.
- DONE: Execute plan Tasks 5-6 (T5 three-family coverage; T6 paired integration regression)
  Commit 3b594ee: `test_runs_aggregate_per_query_reducer.py` now exercises all three families — the new `dab_batch_run_dir` (sidecar fan + render-adapter snapshot for AC-2), `mixed_trial_run_dir` (DAB per-query, fall-through), and `ade_bench_run_dir` (task-view stratum, no `dataset` key, no sidecar). `tests/integration/test_rk_score_matches_summary.py::test_rk_score_matches_summary_json_for_dab_batch_fixture` asserts `summary['stratified_pass_at_1'] == score['stratified_pass_at_1'] == 6/7` on the new fixture. Full integration suite 4/4 passing; full pytest suite passes except 10 pre-existing failures (LFS-hydration + matrix-spec-generator + dab-retirement) that reproduce on baseline `main` (verified by `git stash`/baseline pytest).

### Summary

Collapsed the two stratified pass@1 reducers into one canonical reducer
(`reduce_per_query_stratified`), with the DAB batch-mode fix moved into
`read_trial_outcomes` via a per-query sidecar reader that fans one trial into
N outcome rows keyed `(dataset, query_id)`. `aggregate_summary` is now a thin
render adapter over the canonical reducer; the private duplicate
`_stratified_pass_at_1` is deleted. Trial accounting stays per physical trial
via an optional `trial_counts` override (used by both `aggregate_summary` and
`rk score` CLI through the new public `count_trials(run_dir)` helper). The
6/7 yelp regression is now caught in three places: the unit reducer test, the
render-adapter snapshot, and the paired integration regression. Branch
`spacedock-ensign/runs-aggregate-single-score-reducer`, 4 commits
(56f9290, 290d958, fb4732b, 3b594ee).

## Stage Report: validation

- DONE: Reproduce each AC's `Verified by:` clause against the worktree branch
  AC-1 grep `_stratified_pass_at_1` outside `_legacy/` = 0 matches; fixture `tests/fixtures/score/dab_batch_run_dir/yelp__Cc94VEd/` reduces to `dataset_pass_at_1==6/7`; `summary[stratified_pass_at_1] == score[stratified_pass_at_1] == 0.8571428571428571` byte-equal on the AC-1 fixture (via `aggregate_summary` + `rk score`). AC-2: `_render_legacy_datasets` shape verified inline (`{dataset_pass_at_1, n_queries, queries}` outer; `{query_id, n_trials, n_correct, pass_at_1}` per cell) on the batch fixture; DAB per-query + ADE fixtures round-trip. AC-3: `tests/unit/test_runs_aggregate_per_query_reducer.py` 4/4 pass — covers all three families (`dab_batch_run_dir`, `mixed_trial_run_dir`, `ade_bench_run_dir`). AC-4: `tests/integration/test_rk_score_matches_summary.py` 4/4 pass including the new `test_rk_score_matches_summary_json_for_dab_batch_fixture` (asserts 6/7 paired).
- DONE: Run `uv run pytest` and diff branch failures against `main` baseline
  599 pass / 10 fail / 12 skipped (excluding pre-existing `test_task_identity_scoring.py::ModuleNotFoundError: razorback.score.load` collection error, also present on `main`). 9 of the 10 failures reproduce verbatim on `main`. **1 new failure**: `test_dab_retirement.py::test_active_code_does_not_import_in_tree_dab_adapter` trips on `_load_reward_per_query`'s docstring containing the literal substring `benchmarks/dab` (inside the reference `_legacy/benchmarks/dab/aggregate.py`). Pre-existing `test_in_tree_dab_adapter_directory_is_not_active` passes on the branch (resolves due to merge-base churn, unrelated).
- DONE: Run code review against the worktree branch
  Reviewed branch-only diff (5 commits, ~309 insertions in `src/razorback/{cli/score.py,runs/aggregate.py}` + tests). One blocking finding (the `benchmarks/dab` docstring needle above). Three non-blocking observations: (1) `_fan_batch_trial` rides `cost_usd` only on row 0 — by design, keeps `_job_cost_usd` sum honest; (2) synthetic `error_reason="BatchSidecarEmpty"` label introduced but no consumer keys on it; (3) `_resolve_stratum` docstring references the deleted `rk score/load.py` (pre-existing, not branch-introduced). Full report at `docs/razorback-implementation/validation/runs-aggregate-single-score-reducer.md`.

### Summary

Four ACs pass end-to-end: the canonical reducer reads `reward_per_query.json` and returns 6/7 for the yelp batch fixture; `_stratified_pass_at_1` is deleted; `aggregate_summary` and `rk score` agree byte-for-byte; three-family coverage + paired integration regression both green. Blocker: the branch introduces one new test failure — `test_dab_retirement.py::test_active_code_does_not_import_in_tree_dab_adapter` — because `_load_reward_per_query`'s docstring contains the literal `benchmarks/dab` substring (in `_legacy/benchmarks/dab/aggregate.py`). Recommended verdict: **REJECT-bounce-to-implementation** for a one-line docstring rewrite, then re-validate. Full validation report at `docs/razorback-implementation/validation/runs-aggregate-single-score-reducer.md`.

## Stage Report: validation (cycle 2)

- DONE: Re-run dab-retirement guard after cycle-1 docstring fix (commit 310f76f)
  `uv run pytest tests/unit/test_dab_retirement.py -v` → 2/2 PASS. Both `test_active_code_does_not_import_in_tree_dab_adapter` (the cycle-1 regression) and `test_in_tree_dab_adapter_directory_is_not_active` now green. `grep -n 'benchmarks/dab' src/razorback/runs/aggregate.py` returns 0 matches.
- DONE: Re-run cycle-1 green tests to confirm no regression
  `uv run pytest tests/unit/test_runs_aggregate_per_query_reducer.py tests/integration/test_rk_score_matches_summary.py -v` → 8/8 PASS (4 unit + 4 integration). All four ACs remain satisfied; the docstring paraphrase is doc-only and changes no production behavior.
- DONE: Confirm full-suite baseline diff drops by 1
  `uv run pytest --ignore=tests/unit/test_task_identity_scoring.py -q` → 600 passed / **9 failed** / 12 skipped (down from 10). The 9 remaining are the same pre-existing failures present on baseline `main`: 1 worktree-teardown LFS hydration, 1 claude-benchmark-spec, 2 generate-matrix-specs, 5 generate-matrix-specs-per-variant-kind. Zero net-new failures attributable to the branch.

### Summary

Cycle-2 docstring paraphrase resolves the sole blocker from cycle 1. All four ACs remain functionally satisfied (6/7 yelp reduction, single-reducer grep clean, byte-equal summary↔score, three-family + paired integration green); the dab-retirement guard is now green; full pytest failure count drops from 10 to 9 with all remaining failures reproducing verbatim on baseline `main`. Final verdict: **PASS**. Cycle-2 addendum appended to validation report at `docs/razorback-implementation/validation/runs-aggregate-single-score-reducer.md`.

## Stage Report: implementation (cycle 2)

- DONE: Rewrite the docstring of `_load_reward_per_query` in `src/razorback/runs/aggregate.py` (around line 197) to drop the literal `benchmarks/dab` path token while preserving the design pointer.
  Replaced `_legacy/benchmarks/dab/aggregate.py:_load_per_query_rewards` with "the legacy DAB aggregator's per-query-rewards loader" — substance unchanged, no path tokens. `grep -n 'benchmarks/dab' src/razorback/runs/aggregate.py` now returns 0 matches.
- DONE: Re-run dab-retirement and reducer/paired regression tests
  `tests/unit/test_dab_retirement.py` 2/2 PASS (incl. `test_active_code_does_not_import_in_tree_dab_adapter`). `tests/unit/test_runs_aggregate_per_query_reducer.py` + `tests/integration/test_rk_score_matches_summary.py` 8/8 PASS together.
- DONE: Append cycle-2 report and commit on worktree branch
  This section; commit on `spacedock-ensign/runs-aggregate-single-score-reducer` with the prescribed message.

### Summary

One-touch fix per cycle-1 validation feedback: paraphrased the `_load_reward_per_query` docstring to remove the `benchmarks/dab` substring that tripped `test_dab_retirement.py::test_active_code_does_not_import_in_tree_dab_adapter`. No production logic changed; reducer behavior, reducer tests, and paired integration regression all stay green.
