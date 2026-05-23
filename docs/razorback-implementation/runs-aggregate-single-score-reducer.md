---
id: 1svqbefxg8fd12cy2ssp2jes
title: Make run aggregation and rk score use one score reducer
status: plan
source: 2026-05-23 staff audit + rk-score validator follow-up - duplicate stratified reducers
started: 2026-05-23T17:24:54Z
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

The v2 spec says `rk score` delegates to the same reducer that produces
`summary.json`, but the implementation still has two active stratified
pass@1 reducers. The duplicate path can drift silently and make headline scores
depend on which command produced the summary.

## Acceptance criteria

**AC-1 - One reducer is authoritative.**
`rk score` and run-dir aggregation both call the same reducer function for
stratified pass@1.
Verified by: deleting or inlining the duplicate reducer does not change JSON or
markdown outputs.

**AC-2 - Legacy output is a render adapter only.**
Any backwards-compatible `datasets` JSON shape is rendered from the canonical
reducer result rather than computed independently.
Verified by: tests assert the legacy shape for an existing fixture without
calling a second scoring implementation.

**AC-3 - DAB and Harbor task-view fixtures are both covered.**
The shared reducer preserves DAB dataset/query behavior and ADE/Spider task id
strata.
Verified by: fixture tests cover both benchmark families.

**AC-4 - Spec conformance is checked.**
The test suite has a regression that would fail if `summary.json` and
`rk score` produce different headline values for the same run directory.
Verified by: a paired assertion compares both command surfaces.
