---
id: bpb83at5rrcm0z77maf6bbqb
title: Spacedock dispatch manifests are per trial
status: backlog
source: 2026-05-24 ADE full-run audit gap - parallel Spacedock run wrote one job-level subagent-trace-manifest.json
started:
completed:
verdict:
score: 0.93
worktree:
issue:
pr:
mod-block:
---

## Problem

Full parallel `spacedock_solver` runs currently collapse FO dispatch
provenance to one job-level `subagent-trace-manifest.json`. That is not enough
for strict audit of a full ADE or DAB score because each trial must prove its
own Spacedock dispatch prompt, worker identity, and trace location.

## Acceptance criteria

**AC-1 - Full parallel runs emit one dispatch manifest per trial.**
Each `spacedock_solver` trial directory has a
`subagent-trace-manifest.json` or equivalent per-trial trace manifest that
names the trial, prompt mode, dispatched worker, and trace artifact paths.
Verified by: an automated fixture with at least two parallel Spacedock trials
asserts both trial directories contain distinct manifests.

**AC-2 - Job-level provenance no longer overwrites trial provenance.**
If a job-level rollup is retained, it references all per-trial manifests and
does not replace or overwrite them.
Verified by: tests assert a two-trial run has two distinct manifest payloads
plus any rollup inventory, with no shared final-write collapse.

**AC-3 - Strict audit can fail closed on missing trial manifests.**
`rk audit --policy strict` reports missing Spacedock dispatch coverage for any
trial listed in the run manifest that lacks the per-trial dispatch manifest.
Verified by: an audit fixture with one manifest-bearing trial and one missing
trial emits a coverage failure for the missing trial.

**AC-4 - Smoke and legacy single-trial layouts keep working.**
Existing single-trial Spacedock smoke behavior remains readable by audit and
does not regress score output.
Verified by: the existing Spacedock solver prompt/provenance tests and a
single-trial audit fixture stay green.

## Test plan

Add focused unit or integration fixtures around the manifest writer and strict
audit discovery path, then run the relevant `uv run pytest` subset plus lint on
the touched files.

## Out of scope

Changing score semantics or relaunching the full ADE/DAB score run.
