---
id: 273s1xhb08me39xcev67vxgq
title: Goal 4 — ade-bench full-dataset Codex 1x score
status: backlog
source: Captain directive 2026-05-21 — "get 1x score for full dataset of DAB and ade-bench, using codex"
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Problem

The second research target is a Codex score over the full ade-bench
task set at N=1. Razorback already has an ade-bench local-task path,
but recent Goal 2 work found runtime blockers around upstream
compose env vars and local checkout materialization. This entity
turns the unblocked ade-bench Codex surface into a full matrix score.

This is a score-run entity. It must not silently absorb adapter
development work that belongs in PKG-23 or follow-ups.

## Acceptance criteria

**AC-1 — All discovered ade-bench tasks dispatch at N=1 with Codex.**
The matrix enumerates every task under the configured
`ade_bench_root/tasks/` and emits one trial per task with
`agent.kind: spacedock_solver`, `runtime: codex`, and
`trials: 1`.
Verified by: matrix dry-run prints the discovered task count and
one cell per slug.

**AC-2 — Local-task materialization is used.**
Specs use `benchmark.kind: ade-bench`, `AdeBenchLocalTaskEntry`,
and the local `ade_bench_root`; no per-cell clone of
`harbor-datasets` occurs.
Verified by: a sampled generated spec and materialized task path
show local-task entries and filtered `seeds/solution__*.csv`.

**AC-3 — Runs complete or classify infrastructure failures.**
Each cell either exits 0 with a run-dir containing `result.json`, or
is recorded as a concrete infrastructure failure with the failing
command and log path. Known PKG-23 env-var failures must be
reported as such, not treated as Codex score data.
Verified by: dispatch ledger covers every discovered task with one
terminal status per task.

**AC-4 — `rk score` produces the ade-bench Codex number.**
The result doc reports per-task pass@1 and an aggregate headline
score for completed ade-bench cells. With N=1, per-task CIs are
named as degenerate rather than over-interpreted.
Verified by: `rk score` JSON artifacts exist for every completed
cell and the committed summary document cites the run-dir paths.

**AC-5 — Audit, cost, and provenance are captured.**
Each completed cell has `rk audit --policy strict` output,
`spec.frozen.yaml`, `provenance.yaml`, `manifest.json`,
`summary.json`, and a budget ledger entry.
Verified by: sampled provenance parses the sealed-input fields and
the matrix budget ledger is at or below the declared cap.

## Depends on

- `pkg26-codex-spacedock-solver-runtime`
- `pkg27-codex-benchmark-solver-workflow`
- `pkg23-harbor-shaped-compose-for-ade-bench` or an equivalent
  merged fix for the ade-bench `T_BENCH_*` compose env-var blocker.
