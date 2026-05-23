# Validation Report — rk score delegates to benchmark-native aggregator (drop binary pass@1 reducer)

- Entity: `docs/razorback-implementation/rk-score-uses-benchmark-aggregator.md`
- Worktree: `.worktrees/spacedock-ensign-rk-score-uses-benchmark-aggregator`
- Branch: `spacedock-ensign/rk-score-uses-benchmark-aggregator`
- Base: `966d29a` → Head: `78b32d0`
- Date: 2026-05-22
- Verdict: **APPROVE → done**

## Headline

`rk score` and `summary.json` now emit the same `stratified_pass_at_1` for every fixture: 0.5 (DAB mixed), 1.0 (ADE-bench), 0.25 (unequal-trials discriminator). Binary reducer (`score/reduce.py` + `score/load.py`) is deleted; AC-4 grep gates return zero hits. 555 unit tests pass; the 3 failing tests under `tests/integration/` (`test_rk_run_nop`, `test_rk_run_bookreview_claude`, `test_rk_run_bookreview_spacedock_halt_resume`) are pre-existing `rk run` integration failures unrelated to the score reducer change.

## AC walk

### AC-1 — `rk score <DAB run-dir>` emits paper's per-query stratified pass@1 (PASS)

**Round-trip equality (DAB fixture `mixed_trial_run_dir`):**

```
summary.stratified_pass_at_1 = 0.5
score.stratified_pass_at_1   = 0.5
equal: True
```

Reproduced by `aggregate_summary(run_dir)` followed by `rk score --format json` on the same run-dir, then asserting object equality (not `pytest.approx`). Pinned by `tests/integration/test_rk_score_matches_summary.py::test_rk_score_matches_summary_json_for_dab_fixture`.

### AC-2 — `rk score <ADE-bench run-dir>` emits ADE-bench pass@1 the same way (PASS)

**Round-trip equality (ADE-bench fixture `ade_bench_run_dir`):**

```
summary.stratified_pass_at_1 = 1.0
score.stratified_pass_at_1   = 1.0
equal: True
```

Same single-source path through `runs/aggregate.py:reduce_per_query_stratified`; no per-benchmark dispatch. `benchmarks/ade_bench/aggregate.py` is not invoked (and does not exist; only a stale `.pyc` remained — plan stage flagged this and the entity body was corrected in commit `3278283`, a body-only edit separate from the code commits). Pinned by `tests/integration/test_rk_score_matches_summary.py::test_rk_score_matches_summary_json_for_ade_bench_fixture`.

### AC-3 — Wilson CI + `--against-constant` decorations preserved (PASS)

**Per-query Wilson CIs present at cell level; stratum-level CI null.** Direct observation of `rk score` output on `unequal_trials_run_dir`:

```json
"queries": [
  {"query_id": 1, "n_trials": 2, "n_correct": 1, "pass_at_1": 0.5,
   "wilson_ci": [0.09453120573423074, 0.9054687942657693]},
  {"query_id": 2, "n_trials": 1, "n_correct": 0, "pass_at_1": 0.0,
   "wilson_ci": [...]}
],
"wilson_ci": null   // at stratum level
```

`--alpha` flag propagates to cell-level Wilson (pinned by `test_per_query_wilson.py::test_alpha_flag_propagates_to_cell_wilson`). `--against-constant` reuses `verdict.py:_point_verdict` at both stratum and run level (CI is null, so it must be a point comparison) — pinned by 8 cases in `tests/unit/test_score_verdict.py`. CI math is the unchanged `razorback.diff.stats.wilson_ci` reused from `rk diff`.

### AC-4 — Binary `score/reduce.py:reduce_trials` is deleted (PASS)

**Grep gate 1:**

```
$ grep -rn 'passed=(reward is not None and reward >= 1.0)' src/
(zero hits)
```

**Grep gate 2 (file deletion):**

```
$ ls src/razorback/score/reduce.py src/razorback/score/load.py
ls: src/razorback/score/reduce.py: No such file or directory
ls: src/razorback/score/load.py: No such file or directory
```

Both files removed in commit `aa5ee6b`. The `src/razorback/score/` package retains only `__init__.py`, `render.py`, and `verdict.py` — the user-facing surface no longer reaches the binary reducer.

## Discriminator check — unequal-trials fixture exercises the asymmetry

The first officer flagged: confirm the unequal-trials fixture actually exercises `k != n*pct` for some query (so the test isn't performative). Verified by inspecting `tests/fixtures/score/unequal_trials_run_dir/`:

- q1 has n=2 trials (1 pass + 1 fail) → per-query pass@1 = 0.5
- q2 has n=1 trial (1 fail) → per-query pass@1 = 0.0
- Per-query mean = (0.5 + 0.0) / 2 = **0.25**
- Binary mean across all 3 trials = 1/3 = **0.333…**

The two paths disagree (0.25 vs 0.333) on this fixture, so the test red-bars any regression that reintroduces a binary reducer. Discriminator is real.

## Test bundle re-run

```
$ uv run pytest tests/unit/test_per_query_wilson.py tests/unit/test_score_verdict.py \
    tests/integration/test_rk_score_matches_summary.py \
    tests/unit/test_runs_aggregate.py tests/unit/test_runs_aggregate_events.py -v
============================== 33 passed in 0.85s ==============================
```

```
$ uv run pytest -m 'not integration' --timeout=60 -q
3 failed, 555 passed, 4 skipped, 4 deselected, 16 warnings in 120.39s
```

The 3 failures are all in `tests/integration/test_rk_run_*` (not the score path) and reproduce identically on `main` (`test_rk_run_nop` fails on `events.jsonl is empty`; the spacedock-halt-resume test fails on `agent.sealed_hash missing`; the bookreview-claude test was already failing). They are pre-existing environmental/integration issues outside this entity's scope.

## Code review findings

I reviewed the diff against `main` (25 files changed; +670 / -1844 lines, mostly test-suite consolidation). The implementation is clean and focused. Key findings:

### Strengths

- **Clean delete.** `score/reduce.py`, `score/load.py`, and four legacy test files (`test_score_counting.py`, `test_score_load.py`, `test_score_no_regression_pkg17.py`, `test_score_reduce.py`, `test_score_stratum_tagging.py`) gone outright — no dead-code shim or "for compat" stub left behind.
- **TypedDicts at the contract boundary.** `QueryCell`, `DatasetStratum`, `StratifiedReport`, `TrialOutcome` give the new shape a strict shape, and `build_stratum_view` makes the legacy-surface projection explicit instead of implicit.
- **Round-trip pin is structural, not numeric.** The integration test asserts `==` between `summary.json` and `rk score`, not `pytest.approx`. Drift in either path red-bars immediately.
- **AC-3 honest math.** Stratum-level CI is `null` (mean-of-proportions is not binomial), not faked with a Wilson on the dataset-level k/n. The plan-stage write-up justifies this and the implementation matches.
- **Wilson CI shares `razorback.diff.stats.wilson_ci`.** No new CI math; `rk score` and `rk diff` use the same function, pinned by `test_per_query_wilson_matches_diff_stats_wilson`.

### Important (non-blocking)

1. **Two reducers compute the same per-query stratified math.** `runs/aggregate.py` now has *both* `_stratified_pass_at_1` (used by `aggregate_summary` → `summary.json`) and `reduce_per_query_stratified` (used by `rk score`). They produce equal output today — that's what the round-trip test enforces — but the entity body claims "single source of truth," and what shipped is two parallel implementations of the same math living in the same file. The test catches drift, but a future refactor could legitimately consolidate `aggregate_summary` to call `reduce_per_query_stratified` and drop `_stratified_pass_at_1`. **Non-blocking** because the round-trip test pin prevents silent drift; flag for the next session if a structural-cleanup entity is filed.
   - `src/razorback/runs/aggregate.py:271` (new) and `src/razorback/runs/aggregate.py:354` (old)

### Minor

1. **`build_stratum_view` reports `n_errored=0` per stratum** even when errored trials belong to that dataset. The docstring at `src/razorback/score/verdict.py:43-47` documents the choice (errored trials never land in per-cell view; run-level `stratified_n_errored` is authoritative). Slight rendering wart: in `mixed_trial_run_dir`, the markdown table shows `n_errored=0` per stratum but the JSON's `stratified_n_errored=1`. Documented; acceptable.

2. **`SCORE_REPORT_VERSION = 1` lives in `runs/aggregate.py`.** Slightly out of place (it's the `rk score` JSON shape version, not the run-dir aggregator's), but consistent with the single-source-of-truth direction. Cosmetic.

### Assessment

**Ready to merge: Yes.** All four ACs PASS with verified evidence. The "Important" finding is real duplication but is structurally pinned by the round-trip test, so it cannot silently regress; it belongs in a follow-up consolidation entity rather than blocking this merge. No Critical findings.

## Gate decision

**APPROVE → advance to `done`.**

- AC-1: PASS (DAB round-trip equality)
- AC-2: PASS (ADE-bench round-trip equality; entity body wording fix landed separately at `3278283`)
- AC-3: PASS (per-query Wilson present at cell level; stratum CI null; `--against-constant` reuses `_point_verdict`)
- AC-4: PASS (both grep gates return zero hits; both files deleted)
- Discriminator: real (unequal-trials fixture exercises `k != n*pct`)
- Full test suite: 555 passed; 3 failures all pre-existing on `main` and unrelated to score path

No blocking findings; one Important non-blocking duplication call-out for the next session.
