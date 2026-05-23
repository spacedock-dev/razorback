---
id: d6m63hvwse766rd47qj8spw3
title: Canonical sealed hash contract for freeze and runtime task identity
status: backlog
source: 2026-05-23 staff audit - frozen agent.sealed_hash no longer matches runtime spacedock solver hash
started:
completed:
verdict:
score: 0.94
worktree:
issue:
pr:
mod-block:
---

## Problem

Razorback now has more than one active definition of the solver sealed hash.
`rk freeze` writes `agent.sealed_hash` from one input shape, while the runtime
spacedock solver recomputes a broader hash that includes benchmark task and
batch identity. That makes freeze/resume provenance ambiguous: a frozen spec can
look sealed while the value actually used at task runtime is different.

## Acceptance criteria

**AC-1 - One canonical sealed-hash input builder exists.**
Freeze, translation, and spacedock solver runtime all consume the same typed
input object or intentionally named variants of it.
Verified by: tests import the builder through the public internal API instead
of copying hash-input construction in multiple modules.

**AC-2 - Frozen and runtime hash semantics are explicit.**
The code and spec distinguish either a pre-task base sealed hash plus per-task
runtime sealed hash, or a single task-specific frozen hash. There is no field
named `sealed_hash` whose meaning changes between freeze and runtime.
Verified by: `rk freeze` output, translated Harbor kwargs, and runtime artifacts
carry the documented field names.

**AC-3 - Task-view identity is covered.**
ADE-Bench and Spider2-DBT task-view runs include benchmark kind, task id, batch
mode, and child task ids in the hash surface when that identity affects the
solver context.
Verified by: fixture tests assert distinct hashes for two task ids with the
same model/workflow prompt and stable hashes for resume of the same task id.

**AC-4 - Regression coverage prevents drift.**
A test compares the frozen spec value, translated kwargs, and runtime agent hash
for at least one task-view run.
Verified by: the test fails if any layer silently recomputes a different value.
