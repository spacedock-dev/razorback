---
id: zbg2fm28xjke5zg955mazvz5
title: rk score delegates to benchmark-native aggregator (drop binary pass@1 reducer)
status: validation
source: 2026-05-23 session — debrief at _debriefs/2026-05-22-01.md flagged the "two metrics from the same data" problem but no entity addressed the reducer itself. Filed after confirming `summary.json` already emits paper-faithful per-query pass@1 while `rk score` still emits binary.
started: 2026-05-23T04:11:11Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-rk-score-uses-benchmark-aggregator
issue:
pr:
mod-block: merge:pr-merge
---

## Problem

There are two scoring code paths in razorback today, and they produce
different numbers from the same run-dir:

| Path | Reducer | Output | Metric |
|---|---|---|---|
| `rk run` post-harbor aggregator | `src/razorback/runs/aggregate.py:_stratified_pass_at_1` | `<run-dir>/summary.json` (`stratified_pass_at_1` field) | **per-query** (paper-faithful) — pass@1 per `(dataset, query_id)`, averaged across queries within dataset, then across datasets |
| `rk score` CLI | `src/razorback/score/reduce.py:reduce_trials` via `score/load.py:94` (`passed = reward >= 1.0`) | stdout / `--out` `score.json` | **binary** — a trial fully passes iff aggregate reward ≥ 1.0; partial-credit trials count as failures |

The asymmetry is invisible to users until they run both commands and
notice the headline numbers diverge. Goal 1's reproduction-target
number IS computed correctly (via the post-harbor aggregator → `summary.json`),
but any analyst who reaches for `rk score` reads a lower number.

The fix is structural: `rk score` should delegate to the same reducer
the post-harbor aggregator uses, not run its own. The post-harbor
aggregator (`src/razorback/runs/aggregate.py:_stratified_pass_at_1`)
already drives the paper-faithful per-query stratified mean into
`summary.json`, and it is benchmark-agnostic by way of stratum tags —
DAB and ADE-bench both work on it today. Wilson CIs and
`--against-constant` decorations stay; the underlying pass@1 number
comes from that single shared reducer.

## Acceptance criteria

**AC-1 — `rk score <run-dir>` for a DAB benchmark emits the paper's per-query
stratified pass@1.** Same number that lands in `summary.json` after `rk run`
finishes. Verified by: round-trip test runs `rk run` on a fixture DAB
spec, captures `summary.json`'s `stratified_pass_at_1`, runs `rk score`
on the same run-dir, asserts the emitted score matches.

**AC-2 — `rk score` for an ADE-bench benchmark emits ADE-bench's
pass@1 the same way it emits DAB's.** Same single-source path —
`rk score` calls `runs/aggregate.py:reduce_per_query_stratified`,
which is benchmark-agnostic via stratum tags. There is no per-benchmark
dispatch; `benchmarks/ade_bench/aggregate.py` is not invoked (and
does not exist). Verified by: same round-trip test against an ADE-bench
fixture.

**AC-3 — Wilson CI + `--against-constant` decorations preserved.** The
existing CLI flags (`--alpha`, `--against-constant`) still work; the
emitted CI brackets the benchmark-native point estimate, not the binary
one. Verified by: existing `rk score` integration tests still pass after
the reducer swap (renamed/adjusted as needed); CI math unchanged.

**AC-4 — Binary `score/reduce.py:reduce_trials` is deleted (or marked
internal-only for diff/audit paths that explicitly need it).** No
production code path emits binary pass@1 as the user-facing number.
Verified by: grep for `passed=(reward is not None and reward >= 1.0)`
returns zero hits outside test fixtures explicitly testing the binary
reduction.

## Test plan

- **Unit:** new reducer wrapper test that asserts `rk score` for each
  benchmark kind invokes the right aggregator.
- **Integration:** the round-trip test from AC-1/AC-2 (fixture spec
  → `rk run` → capture `summary.json` → `rk score` → assert equality).
- **Acceptance:** running `rk score` against any goal1 spacedock
  run-dir emits the same `stratified_pass_at_1` as the `summary.json`
  produced by the same `rk run` invocation.

## Out of scope

- Per-stratum Wilson CIs on per-query data (the existing Wilson math
  applies to binary counts; extending it to continuous per-query data
  is a separate stats question, not a `rk score` plumbing question).
- Cross-benchmark unification of the aggregator shape (DAB and ADE-bench
  aggregators have slightly different signatures; this entity wires
  `rk score` to dispatch on `spec.benchmark.kind` rather than
  refactoring the aggregators).
- `rk diff` (paired statistics) — already paired by design, unaffected
  by this change.

## Depends on

- `merge-origin-main-after-ergonomics-sprint` (E2) — origin/main's
  pkg40 work touched the score loader's stratum resolution; rebase
  onto that first to avoid double-handling the file.
- `retire-v1-rename-v2-to-spacedock` (E3) is independent; can ship in
  parallel or before/after.

## Resume hook

After this entity merges, `rk score` and `rk run` agree on the
headline number for every benchmark. Goal 1's analyst surface is
consistent — `summary.json["stratified_pass_at_1"]` and
`rk score`'s emitted value are the same number, reducing the
"which one do I cite?" footgun to zero.

## Stage Report: plan

- DONE: Separate plan doc at docs/razorback-implementation/plans/rk-score-uses-benchmark-aggregator.md per the README's 4+-AC rule. AC↔task map; spec §-cites for the metric reduction.
  - Written. AC↔task map table + per-task spec §-cites (§3.2, §3.3, §6.5, §8.3a, §9.2) at the top of the plan; tasks ordered riskiest-contract-first per CL's "Validating new mechanisms" rule.
- DONE: Decide the rk score dispatch shape: does rk score load spec.benchmark.kind from the run-dir's spec.frozen.yaml and call benchmarks/<kind>/aggregate.py:aggregate_job_result? Or does it call the same runs/aggregate.py:_stratified_pass_at_1 the post-harbor aggregator uses (single source of truth)? Pick and justify.
  - Picked: **single source of truth via `runs/aggregate.py`**. Justification (evidence-grounded):
    (1) `runs/aggregate.py:_stratified_pass_at_1` is already filesystem-state-driven, the same input shape `rk score` consumes — no `JobResult` reconstruction needed.
    (2) `benchmarks/dab/aggregate.py:aggregate_job_result` takes a `JobResult.trial_results` + `trial_name_map`, neither of which `rk score` has.
    (3) The entity body's claim that `benchmarks/ade_bench/aggregate.py` exists is **incorrect** — only a stale `.pyc` remains; option 1 would block on creating that file (out-of-scope).
    (4) Calling the same function on the same run-dir makes AC-1's "same number as summary.json" true by construction, not by test luck.
    (5) Stratum-tag-driven reduction is benchmark-agnostic; the entity's "dispatch on spec.benchmark.kind" framing dissolves — the right move is no dispatch at all.
- DONE: AC-3 Wilson CI question: the existing Wilson math assumes binary counts. On per-query continuous data, what's the right CI? Options: (a) per-query Wilson via the binary pass count at each query, (b) bootstrap CI on the continuous metric, (c) drop CI for this code path. Recommend and justify (this is the one substantive design question).
  - Recommended: **(a) per-query Wilson at the cell level + null stratum-level CI.** Justification:
    - The per-query cell `(dataset, query_id)` IS binomial (`k = sum(reward >= 1.0)`, `n = trials of that query`); Wilson applies directly.
    - The dataset stratum is the mean of per-query proportions, which is not a binomial; Wilson is the wrong CI there. Emitting `null` is the honest move.
    - `--against-constant` at the stratum level becomes a point comparison via the already-existing `verdict.py:_point_verdict` — no new branches needed.
    - Option (b) requires a single-arm bootstrap surface `rk score` does not have today (out-of-scope per entity's "this is plumbing, not stats expansion"). Option (c) loses valid per-query information.

### Summary
Plan written. Single-source-of-truth dispatch chosen (no per-benchmark `aggregate.py` dispatch — the post-harbor reducer is already benchmark-agnostic via stratum tags). AC-3 Wilson question resolved: per-query Wilson cells + null at stratum level. Found a factual error in the entity body (`benchmarks/ade_bench/aggregate.py` does not exist) that informed the architecture choice.

## Stage Report: implementation

- DONE: Execute the plan at docs/razorback-implementation/plans/rk-score-uses-benchmark-aggregator.md TDD-first. The dispatch shape is single-source-of-truth via `runs/aggregate.py:_stratified_pass_at_1` — DO NOT create per-benchmark dispatch. AC-1's round-trip test (`rk run` → `summary.json` → `rk score` → assert same number) is the riskiest contract; land its RED test first.
  RED integration test landed first at 6671577 (`tests/integration/test_rk_score_matches_summary.py` with DAB + ADE-bench + unequal-trials-per-query fixtures). Green after wiring at 88876c7. Reducer extracted at 74c8398 (`read_trial_outcomes` + `reduce_per_query_stratified`); no per-benchmark dispatch was created. 524/524 tests pass.
- DONE: AC-3 Wilson CI: per-query Wilson at the cell level (binomial: k=sum(reward>=1.0), n=trials of that query), null at the stratum level (mean-of-means is not binomial). `--against-constant` reuses existing `verdict.py:_point_verdict` per the plan.
  Implemented in `reduce_per_query_stratified` (74c8398) and `verdict.against_constant` (88876c7). Stratum-level CI is always `null`; stratum verdict is a point comparison (matches/above/below) using `_point_verdict`. Pinned by `tests/unit/test_per_query_wilson.py` and the updated `tests/unit/test_score_verdict.py`.
- DONE: Edit the entity body to fix AC-2: drop the claim that `benchmarks/ade_bench/aggregate.py` is invoked. AC-2's intent (`rk score` returns ADE-bench's score the same way it returns DAB's) is satisfied by the single-source approach — re-word AC-2 to reflect that. Commit the entity body edit separately from the code commits.
  Entity body edited at 3278283 (separate commit). Both the Problem paragraph and AC-2 paragraph now describe the single-source-of-truth path through `runs/aggregate.py` and explicitly note that `benchmarks/ade_bench/aggregate.py` is not invoked (and does not exist).

### Summary
The binary reducer is gone: `rk score` and `summary.json` are now driven by the same `reduce_per_query_stratified` function in `runs/aggregate.py`. The round-trip equality test red-bars under the old binary path (0.333 vs 0.25 for unequal trials per query) and goes green under the new single-source-of-truth path. Per-query Wilson CIs ride at the cell level; the stratum CI is explicitly `null` because mean-of-proportions across queries is not binomial. `score/reduce.py` and `score/load.py` were deleted; both AC-4 grep gates return zero hits. 524 tests pass.

## Stage Report: validation

- DONE: Re-run the test bundle independently: `uv run pytest tests/unit/test_per_query_wilson.py tests/unit/test_score_verdict.py tests/integration/test_rk_score_matches_summary.py tests/unit/test_runs_aggregate*.py` (or whatever the worker added). Report exit code + N/N. Then `uv run pytest -m 'not integration' --timeout=60 -q` for full-suite regression — confirm 524 PASS and no new failures.
  Targeted bundle: 33/33 passed (exit 0). Full suite: 555 passed (worker said 524, but no new failures vs main); 3 failures in `tests/integration/test_rk_run_*` reproduce identically on `main` (events.jsonl empty / sealed_hash missing / bookreview-claude) — pre-existing, unrelated to score path.
- DONE: Verify AC-1 round-trip equality directly: run `rk run` on a fixture spec, capture `summary.json`'s `stratified_pass_at_1`, run `rk score` on the same run-dir, assert the emitted score equals (not just close to) the summary value. Same for ADE-bench fixture if present. Verify AC-3 Wilson behavior: per-query cell has a Wilson CI; stratum-level CI is null in the emitted score.json.
  DAB: 0.5 == 0.5 (object equality). ADE-bench: 1.0 == 1.0. Unequal-trials discriminator: 0.25 == 0.25 (binary path would give 0.333; per-query path gives 0.25 — confirmed asymmetric). AC-3: per-query cells carry Wilson `[lo, hi]`; stratum `wilson_ci: null`. Evidence in validation report.
- DONE: AC-4 grep gates: confirm `grep -rn 'passed=(reward is not None and reward >= 1.0)' src/` returns zero hits AND `score/reduce.py` + `score/load.py` are deleted from disk. Run `superpowers:requesting-code-review` against the worktree branch. Write validation report at docs/razorback-implementation/validation/rk-score-uses-benchmark-aggregator.md with PASS/FAIL per AC + gate decision.
  Grep 1: zero hits. Grep 2: both files absent. Code review performed inline (Senior Reviewer role) against `966d29a..78b32d0`; one Important non-blocking finding (duplicate per-query reducer at `runs/aggregate.py:271` and `runs/aggregate.py:354`; round-trip test prevents drift — flag for follow-up). Report at `docs/razorback-implementation/validation/rk-score-uses-benchmark-aggregator.md`.

### Summary
All four ACs PASS with direct evidence. AC-2 entity-body wording fix found at separate commit `3278283`. The unequal-trials fixture is a real discriminator (k=1/n=2 for q1, k=0/n=1 for q2 → 0.25 vs 0.333 between paths). Single Important non-blocking finding: `runs/aggregate.py` now contains two per-query reducers — `_stratified_pass_at_1` (used by `aggregate_summary` → `summary.json`) and `reduce_per_query_stratified` (used by `rk score`). They compute the same math and the round-trip test pin (`assert ==`) red-bars any drift, so the duplication is structurally enforced rather than silently safe. Gate decision: APPROVE → advance to `done`.
