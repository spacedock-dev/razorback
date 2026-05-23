---
id: zbg2fm28xjke5zg955mazvz5
title: rk score delegates to benchmark-native aggregator (drop binary pass@1 reducer)
status: backlog
source: 2026-05-23 session — debrief at _debriefs/2026-05-22-01.md flagged the "two metrics from the same data" problem but no entity addressed the reducer itself. Filed after confirming `summary.json` already emits paper-faithful per-query pass@1 while `rk score` still emits binary.
started:
completed:
verdict:
score: 0.8
worktree:
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
