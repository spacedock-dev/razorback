---
id: sx3d0m0k7h1afm9dhz44dhpc
title: Goal 3 — DAB full-dataset Codex 1x score
status: backlog
source: Captain directive 2026-05-21 — "get 1x score for full dataset of DAB and ade-bench, using codex"
started:
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

The immediate research target is a Codex score over the full DAB
dataset set at N=1. The matrix must accept the operator's local
DataAgentBench data root and produce a defensible run-dir set,
`rk score` output, and `rk audit` output for all 12 DAB catalog
datasets.

This is a score-run entity, not a benchmark-adapter refactor.

## Acceptance criteria

**AC-1 — All 12 DAB datasets dispatch at N=1 with Codex.**
The matrix covers exactly the 12 catalog datasets from
`razorback-plugin-dab`: agnews, bookreview, crmarenapro,
DEPS_DEV_V1, GITHUB_REPOS, googlelocal, music_brainz_20k,
PANCANCER_ATLAS, PATENTS, stockindex, stockmarket, and yelp.
Verified by: matrix dry-run prints 12 cells and each cell's spec
uses `agent.kind: spacedock_solver`, `runtime: codex`, and
`trials: 1`.

**AC-2 — Runs complete or classify infrastructure failures.**
Each cell either exits 0 with a run-dir containing `result.json`, or
is recorded as a concrete infrastructure failure with the failing
command and log path. Agent-answer failures count as score data;
missing Docker/data/auth do not.
Verified by: dispatch ledger covers 12/12 cells with one terminal
status per dataset.

**AC-3 — `rk score` produces the DAB Codex number.**
The result doc reports per-dataset pass@1 and an aggregate headline
score for completed DAB cells.
Verified by: `rk score` JSON artifacts exist for every completed
cell and the committed summary document cites the run-dir paths.

**AC-4 — `rk audit --policy strict` is clean or explicitly
coverage-blocked.**
Each completed run-dir is audited. Any coverage gap is named as a
coverage gap, not treated as evidence of cleanliness.
Verified by: per-cell `audit.json` artifacts or audit stderr logs
are present and summarized.

**AC-5 — Cost and provenance are captured.**
Each completed cell has `spec.frozen.yaml`, `provenance.yaml`,
`manifest.json`, `summary.json`, and a budget ledger entry.
Verified by: a provenance spot-check parses one cell's sealed inputs
and the matrix budget ledger is at or below the declared cap.

## Depends on

- `pkg26-codex-spacedock-solver-runtime`
- `pkg27-codex-benchmark-solver-workflow`
- Existing in-flight PKG-15 follow-up may be needed for agnews/yelp
  mongo healthcheck stability; do not reimplement it here.
