---
id: gbejh94n05b1096a6fhqeq0h
title: ADE-Bench uses Harbor published dataset references
status: backlog
source: 2026-05-23 captain directive — consume canonical Harbor dataset refs instead of local ADE task roots
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

Razorback's current ADE path consumes local Harbor-shaped task directories
(`tasks_root + tasks`) or explicit git-task entries. That is Harbor-compatible,
but it is not Harbor registry-native: users still need to know where the ADE
tasks live and how they were materialized. Harbor already exposes canonical
published datasets such as `ade-bench@1.0`; Razorback should consume that
dataset reference and let Harbor resolve/materialize the task package set.

The local Harbor-shaped task-root path may stay as a development/debug escape
hatch, but the public score path for ADE should be a dataset ref.

## Acceptance criteria

**AC-1 — ADE specs accept a Harbor dataset reference.**
`benchmark.kind: ade-bench` can name a published Harbor dataset ref such as
`ade-bench@1.0` without requiring `tasks_root`. Specs can still select a subset
of task ids for smoke runs.
Verified by: schema/parser tests cover dataset-ref-only, dataset-ref + subset,
and old local-task-root compatibility.

**AC-2 — Dataset resolution uses Harbor's public resolver.**
Razorback resolves the dataset through Harbor's dataset/task client, materializes
tasks into a cache or run-owned staging area, and records the resolved dataset
version/content hash when Harbor exposes it.
Verified by: unit tests patch Harbor's resolver/client and assert package task
ids become local task directories without invoking the old ADE-specific root
loader.

**AC-3 — ADE task views still provide Razorback controls.**
Resolved Harbor tasks pass through the generic task-view materializer so
Razorback can still apply solution-file exclusion, image overrides, runtime
tooling layers, scoring metadata, and future batching/freeze wrappers.
Verified by: translator tests assert resolved dataset tasks produce task views
with `RAZORBACK_BENCHMARK_KIND=ade-bench` and per-task ids.

**AC-4 — Examples stop teaching local ADE roots as the canonical path.**
The primary ADE Codex/Claude smoke specs and generator use the published
dataset ref by default. Local fixture/root examples are marked as test fixtures
or dev-only.
Verified by: `rg "tasks_root: .*ade" examples/specs examples/drivers` returns
only fixture/dev examples, and a new smoke spec names `ade-bench@1.0`.

**AC-5 — No submodule requirement.**
The implementation does not require adding ade-bench or harbor-datasets as a
git submodule. Network/materialization failures surface as clear setup errors.
Verified by: validation report includes a clean checkout run without any new
git submodules and an error-path test for resolver failure.

## Notes

This should layer under the existing task-view abstraction rather than replacing
it. The new boundary is source selection: registry dataset ref -> Harbor
materialized tasks -> Razorback task views -> Harbor run.
