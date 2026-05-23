# Validation Report — Make run aggregation and `rk score` use one score reducer

- Entity: `docs/razorback-implementation/runs-aggregate-single-score-reducer.md`
- Worktree: `.worktrees/spacedock-ensign-runs-aggregate-single-score-reducer`
- Branch: `spacedock-ensign/runs-aggregate-single-score-reducer`
- Merge base vs `main`: `9e4f9a7`
- Branch HEAD: `ee68069` (implementation report) — code at `3b594ee`
- Date: 2026-05-23
- Verdict: **REJECT-bounce-to-implementation** (one new test failure introduced by the branch — one-line docstring fix)

## Headline

Four ACs are functionally satisfied: the canonical reducer reads the
`reward_per_query.json` sidecar and returns `6/7` for the yelp batch
fixture, `_stratified_pass_at_1` is gone, `aggregate_summary` and
`rk score` agree byte-for-byte on the AC-1 fixture, and the
three-family unit + paired-integration suites pass.

Blocker: the branch introduces one **new** test failure —
`tests/unit/test_dab_retirement.py::test_active_code_does_not_import_in_tree_dab_adapter`
— because `_load_reward_per_query`'s docstring contains the literal
substring `benchmarks/dab` (inside the reference `_legacy/benchmarks/dab/aggregate.py`).
That substring is one of the dab-retirement guard's forbidden needles.
Fix is a one-line docstring rewrite. Recommend a fresh implementation
cycle for the fix, then re-validation.

## AC walk

### AC-1 — One reducer is authoritative; reads per-query sidecar (PASS)

**Single-reducer grep** (excluding `_legacy/`):

```
$ cd .worktrees/spacedock-ensign-runs-aggregate-single-score-reducer
$ grep -rn '\b_stratified_pass_at_1\b' src/ tests/ --include='*.py' | grep -v _legacy
$ echo $?
1   # zero matches
```

(The `per_arm_stratified_pass_at_1` identifier in `src/razorback/diff/diff.py` and `tests/unit/test_diff_compose.py` is a distinct token, not the deleted private reducer.)

**6/7 fixture reduction.** Fixture `tests/fixtures/score/dab_batch_run_dir/yelp__Cc94VEd/`:
- `result.json` composite reward = 0.857142857
- `steps/main/verifier/reward_per_query.json` = six 1.0s (q1, q2, q3, q5, q6, q7) + one 0.0 (q4)

Unit test `test_batch_mode_reads_reward_per_query_sidecar` passes:
```
$ uv run pytest tests/unit/test_runs_aggregate_per_query_reducer.py::test_batch_mode_reads_reward_per_query_sidecar -v
… 1 passed in 0.65s
```
The canonical reducer reports the yelp stratum's `dataset_pass_at_1 == 6/7` and `stratified_pass_at_1 == 6/7`, not 0.0.

**`summary.json` ↔ `rk score` byte parity** on the AC-1 fixture:
```
summary[stratified_pass_at_1] = 0.8571428571428571
score[stratified_pass_at_1]   = 0.8571428571428571
byte-equal: True
repr-equal: True
== 6/7: True
```
Both surfaces consume the same `reduce_per_query_stratified` reducer via the new public `count_trials(run_dir)` helper, so accounting stays per-physical-trial despite fanning.

### AC-2 — Legacy `datasets` shape is a render adapter (PASS, with caveat)

`_render_legacy_datasets(report)` in `src/razorback/runs/aggregate.py:485-508` maps the canonical `StratifiedReport.strata` into the existing `summary.json` `{dataset_pass_at_1, n_queries, queries:[{query_id, n_trials, n_correct, pass_at_1}]}` shape with no per-cell `wilson_ci` or stratum-level metadata.

Unit test `test_batch_mode_summary_json_renders_per_query_datasets_block` asserts the rendered shape inline:
```
$ uv run pytest tests/unit/test_runs_aggregate_per_query_reducer.py::test_batch_mode_summary_json_renders_per_query_datasets_block -v
… 1 passed in 0.65s
```
- `set(yelp.keys()) == {"dataset_pass_at_1", "n_queries", "queries"}`
- `frozenset(cell.keys()) == {"query_id", "n_trials", "n_correct", "pass_at_1"}` for every cell
- `yelp["dataset_pass_at_1"] == 6/7`, `n_queries == 7`, all seven per-query rows present with the right `n_correct` map

Caveat: AC-2 reads "matches the pre-change snapshot for per-query mode." The test asserts shape and value inline rather than diffing against a committed snapshot file. The shape enumeration is exhaustive (full key sets, full value map for yelp), but a literal snapshot fixture would be slightly stronger. Not a blocker — the DAB per-query and ADE fixtures round-trip cleanly through `aggregate_summary` (covered by AC-3).

### AC-3 — Three-family coverage (PASS)

```
$ uv run pytest tests/unit/test_runs_aggregate_per_query_reducer.py -v
… test_batch_mode_reads_reward_per_query_sidecar               PASSED
… test_batch_mode_summary_json_renders_per_query_datasets_block PASSED
… test_dab_per_query_fixture_still_falls_through               PASSED
… test_ade_bench_round_trip_runs_clean                         PASSED
… 4 passed in 0.65s
```
All three families covered: `dab_batch_run_dir` (sidecar fan + render snapshot), `mixed_trial_run_dir` (DAB per-query, fall-through, 3 trials with completed-pass / completed-fail / errored), `ade_bench_run_dir` (task-view stratum, no `dataset` key, no sidecar, 3 trials).

### AC-4 — Paired integration regression (PASS)

```
$ uv run pytest tests/integration/test_rk_score_matches_summary.py -v
… test_rk_score_matches_summary_json_for_dab_fixture             PASSED
… test_rk_score_matches_summary_json_for_ade_bench_fixture       PASSED
… test_rk_score_matches_summary_with_unequal_trials_per_query    PASSED
… test_rk_score_matches_summary_json_for_dab_batch_fixture       PASSED
… 4 passed in 0.50s
```
The new third case (`test_rk_score_matches_summary_json_for_dab_batch_fixture`) is the AC-4 paired assertion; it confirms `summary["stratified_pass_at_1"] == score["stratified_pass_at_1"] == 6/7` on the AC-1 fixture.

## Full pytest

```
$ uv run pytest --ignore=tests/unit/test_task_identity_scoring.py -q
… 10 failed, 599 passed, 12 skipped in 45.52s
```

`test_task_identity_scoring.py` collection error (`ModuleNotFoundError: razorback.score.load`) is pre-existing on `main` — `src/razorback/score/load.py` was deleted in `1f7592d` but the test still imports it. Verified by running on baseline `main`: same collection error reproduces.

**Branch-vs-baseline failure delta:**

| Test | On branch | On `main` | Verdict |
|---|---|---|---|
| `test_claude_benchmark_spec_generator::test_goal1_claude_specs_use_per_variant_agent_kind` | FAIL | FAIL | pre-existing |
| `test_dab_retirement::test_active_code_does_not_import_in_tree_dab_adapter` | **FAIL (new)** | PASS | **NEW REGRESSION** |
| `test_dab_retirement::test_in_tree_dab_adapter_directory_is_not_active` | PASS | FAIL | pre-existing |
| `test_generate_matrix_specs::test_matrix_specs_carry_query_mode_batch` | FAIL | FAIL | pre-existing |
| `test_generate_matrix_specs::test_matrix_specs_query_mode_batch_for_all_variants` | FAIL | FAIL | pre-existing |
| `test_generate_matrix_specs_per_variant_kind::test_spacedock_variant_emits_spacedock_solver_kind` | FAIL | FAIL | pre-existing |
| `test_generate_matrix_specs_per_variant_kind::test_direct_minimal_variant_emits_claude_cli_kind` | FAIL | FAIL | pre-existing |
| `test_generate_matrix_specs_per_variant_kind::test_direct_structured_variant_emits_claude_cli_kind` | FAIL | FAIL | pre-existing |
| `test_generate_matrix_specs_per_variant_kind::test_spacedock_solver_workflow_path_exists` | FAIL | FAIL | pre-existing |
| `test_generate_matrix_specs_per_variant_kind::test_spacedock_block_does_not_carry_tools_allowed_default_csv` | FAIL | FAIL | pre-existing |
| `test_worktree_teardown_preserves_runs::test_worktree_remove_force_does_not_destroy_runs` | FAIL | FAIL | pre-existing (LFS hydration) |

Net: 9 of 10 branch failures match `main` failures verbatim. One pre-existing failure (`test_in_tree_dab_adapter_directory_is_not_active`) actually *resolves* on the branch (unrelated to this work — possibly fixed by upstream `main` movement before the branch's merge base). One **new** failure (`test_active_code_does_not_import_in_tree_dab_adapter`) is the branch's regression — see below.

## Code review

### Blocking finding — `benchmarks/dab` substring in active source

`src/razorback/runs/aggregate.py:197` in the `_load_reward_per_query` docstring:

```python
"""...
Mirrors the legacy reader at
`_legacy/benchmarks/dab/aggregate.py:_load_per_query_rewards` but takes a
trial_dir directly.
"""
```

The `tests/unit/test_dab_retirement.py::test_active_code_does_not_import_in_tree_dab_adapter` guard scans `src/razorback/**`, `tests/**`, `examples/**` for the forbidden substring `benchmarks/dab` (and `razorback.benchmarks.dab`). The guard's `_legacy/` exclusion only applies to file *paths*, not to the literal substring occurring in active-code docstrings.

The path `_legacy/benchmarks/dab/aggregate.py` contains the needle `benchmarks/dab`, so this docstring trips the guard. The test is detecting exactly what it is designed to detect: an active-code reference to the in-tree DAB adapter location. The "legacy" qualifier in the reference doesn't help — the guard is string-literal.

**Fix.** One-line docstring rewrite that avoids the literal substring. Options:

- "Mirrors the legacy DAB aggregator's `_load_per_query_rewards` reader (see `_legacy/`); takes a trial_dir directly."
- Or move the file-path reference into a non-`.py`/`.md`/`.yaml`/`.toml` file (e.g., a separate comment file), though that's over-engineering.

Recommended: rewrite the docstring to drop the explicit path; the function name + `_legacy/` reference is enough provenance.

### Non-blocking observations

1. **Cost on row 0 only** (`aggregate.py:329`): `_fan_batch_trial` rides `cost_usd` only on the first fanned row, keeping the `_job_cost_usd` sum honest. Downstream consumers that group cost by `(dataset, query_id)` would see a skewed per-cell distribution. Out of scope for the entity ACs, and the trial-level `result.json` is the source of truth for cost. Documenting here for future per-cell cost work.

2. **Synthetic `error_reason="BatchSidecarEmpty"`** (`aggregate.py:361`): When a sidecar exists but parses to an empty dict, the trial is marked errored with a fresh error class. No test asserts on this label, and no consumer keys on it, but it is a new entry in the error-class namespace. Worth a one-line comment or a `_legacy`-mirrored constant if other code starts caring.

3. **Stale `_resolve_stratum` docstring** (`aggregate.py:105`): References `rk score/load.py:110-146`, but `load.py` was deleted in `1f7592d` (pre-merge-base). Not a regression introduced by this branch — flagging for cleanup hygiene.

4. **AC-2 snapshot interpretation**: The test asserts shape inline rather than diffing a committed snapshot file. Slightly weaker than literal snapshot equality but exhaustive over key sets and values. Acceptable.

## Gate Decision

**REJECT — bounce to implementation** for the one-line docstring fix.

The regression is small enough that the FO could conceivably auto-approve a re-validation after a fix-and-recommit. Per the dispatch's auto-approval clause, this is a "true blocker" only in the narrow sense that pytest reports a net-new failure on the branch that did not exist on the merge base. Functionally, the four ACs are satisfied end-to-end and the canonical-reducer collapse is shipped; the regression is a self-inflicted false-positive on a dab-retirement guard that the impl ensign would have caught had they run the full pytest before signaling completion.

Recommended next dispatch: re-enter implementation, rewrite the
`_load_reward_per_query` docstring to drop the literal `benchmarks/dab`
substring, re-run `tests/unit/test_dab_retirement.py`, commit, and re-dispatch
validation. Expected turnaround is minutes.
