---
id: zbg2fm28xjke5zg955mazvz5
title: rk score delegates to benchmark-native aggregator (drop binary pass@1 reducer)
status: implementation
source: 2026-05-23 session — debrief at _debriefs/2026-05-22-01.md flagged the "two metrics from the same data" problem but no entity addressed the reducer itself. Filed after confirming `summary.json` already emits paper-faithful per-query pass@1 while `rk score` still emits binary.
started: 2026-05-23T04:11:11Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-rk-score-uses-benchmark-aggregator
issue:
pr:
mod-block:
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

The fix is structural: `rk score` should delegate to the benchmark's
native aggregator, not run its own reducer. Each benchmark already
has one — `src/razorback/benchmarks/dab/aggregate.py:aggregate_job_result`
for DAB and `src/razorback/benchmarks/ade_bench/aggregate.py:aggregate_job_result`
for ADE-bench. Wilson CIs and `--against-constant` decorations stay; the
underlying pass@1 number comes from the benchmark.

## Acceptance criteria

**AC-1 — `rk score <run-dir>` for a DAB benchmark emits the paper's per-query
stratified pass@1.** Same number that lands in `summary.json` after `rk run`
finishes. Verified by: round-trip test runs `rk run` on a fixture DAB
spec, captures `summary.json`'s `stratified_pass_at_1`, runs `rk score`
on the same run-dir, asserts the emitted score matches.

**AC-2 — `rk score` for an ADE-bench benchmark emits ADE-bench's native
pass@1.** Same shape — score command delegates to
`benchmarks/ade_bench/aggregate.py`. Verified by: same round-trip test
against an ADE-bench fixture.

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
