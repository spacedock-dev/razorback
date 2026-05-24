---
id: 52w1h8zh0bwfskvheckhj218
title: DAB batch materialization fits ext4 disk budget
status: plan
source: 2026-05-24 DAB full batch Codex explain preflight blocker - /dev/root filled during task-view materialization
started: 2026-05-24T05:06:33Z
completed:
verdict:
score: 0.92
worktree:
issue:
pr:
mod-block:
---

## Problem

The full DAB batch Codex explain preflight resolved `dab@1.0` and froze the
intended `spacedock_solver` spec, but `rk run --explain --explain-format json`
filled `/dev/root` before emitting JSON. The VM root filesystem is ext4, so
`cp --reflink=auto` can fall back to full physical copies for file-backed
SQLite/DuckDB payloads. Full DAB batch materialization must either stay inside
a documented disk budget or fail before partial task-copy churn, without
requiring deletion of prior run results.

## Acceptance criteria

**AC-1 - Full DAB batch explain completes without filling `/dev/root`.**
On this VM, the DAB full batch `spacedock_solver` explain command for
`dataset: dab@1.0`, `query_mode: batch`, Codex `gpt-5.5`, and `xhigh` emits
valid JSON before Harbor/model execution.
Verified by: `rk run --explain --explain-format json` exits 0 and the JSON
assertions from `docs/razorback-implementation/plans/dab-full-batch-codex-explain-preflight.md`
T3/T4 pass.

**AC-2 - Materialization has a bounded disk footprint on non-reflink ext4.**
The DAB plugin no longer depends on full physical copies of all file-backed DB
payloads when `materialize_mode: bind` runs on ext4 without reflinks.
Verified by: a focused test or measured probe proves generated task views stay
under a declared budget while preserving readable SQLite/DuckDB access.

**AC-3 - Source data remains protected from agent writes.**
Any space-saving mechanism must not allow an agent write through the task
workdir to mutate `DATAAGENTBENCH_DATA_ROOT`.
Verified by: a regression test writes or attempts to write through the
materialized task path and proves the source data file is unchanged or mounted
read-only.

**AC-4 - The DAB explain preflight can resume and finish.**
The existing `dab-full-batch-codex-explain-preflight` worktree can rerun its
exact explain command and produce the committed preflight report or a new,
non-disk blocker.
Verified by: the preflight entity records green explain JSON evidence or a
different blocker class with command/log path.

## Test plan

Measure the current DAB materialization footprint on ext4, add the smallest
mechanism test that prevents full-copy fallback from consuming the root
filesystem, then rerun the DAB full batch explain preflight.

## Out of scope

Deleting old run results, pruning Docker images, or launching the full scored
DAB model run.

## Stage Report: plan

- DONE: Plan identifies the precise disk-footprint root cause and the safest materialization mechanism to test first.
  Evidence: `docs/razorback-implementation/plans/dab-batch-materialization-disk-budget.md` §Current Root Cause names `cp --reflink=auto` full-copy fallback for SQLite/DuckDB `db_path` files on ext4, and selects read-only per-file `main` bind mounts as the first mechanism.
- DONE: Plan maps AC-1 through AC-4 to concrete tests/probes, including source-data write protection.
  Evidence: the AC-to-task table maps AC-1..AC-4 to T0..T7; T3 is the write-attempt regression proving source bytes/hash are unchanged or mounted read-only.
- DONE: Plan explicitly forbids deleting run history or launching the full scored DAB run.
  Evidence: §Prohibited Actions forbids deleting historical run/evidence dirs, Docker pruning, and any `rk run` command without `--explain`.

### Summary

Wrote the standard separate plan doc for the four-AC disk-budget task. The implementation plan starts with bounded synthetic and real-data materialization probes, validates read-only file-backed DB mounts before full scale, and only then resumes the existing explain preflight without launching a scored DAB run.
