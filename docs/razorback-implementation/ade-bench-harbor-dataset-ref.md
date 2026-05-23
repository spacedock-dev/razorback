---
id: gbejh94n05b1096a6fhqeq0h
title: ADE-Bench uses Harbor published dataset references
status: validation
source: 2026-05-23 captain directive — consume canonical Harbor dataset refs instead of local ADE task roots
started: 2026-05-23T04:58:35Z
completed:
verdict:
score: 0.85
worktree: .worktrees/spacedock-ensign-ade-bench-harbor-dataset-ref
issue:
pr:
mod-block: merge:pr-merge
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

## Stage Report: plan

- DONE: Separate plan doc at docs/razorback-implementation/plans/ade-bench-harbor-dataset-ref.md per the README's 4+-AC rule. AC↔task map for AC-1..AC-5.
  Written at docs/razorback-implementation/plans/ade-bench-harbor-dataset-ref.md with the AC-to-task table covering AC-1..AC-5; eight tasks (T0 probe through T8 acceptance sweep).
- DONE: Probe Harbor's published-dataset resolver surface — name the exact import path razorback should call, the package format Harbor exposes for `ade-bench@1.0`, and how the result is materialized into local task directories that the existing task-view materializer (pkg40) consumes. If Harbor's surface is unclear, plan a Phase-0 probe task before writing code.
  Surface named: `harbor.tasks.client.TaskClient.download_tasks(task_ids=[PackageTaskId(org="harbor", name="ade-bench", ref="1.0")], output_dir=..., export=True)` returning `BatchDownloadResult.results[*].path` + `content_hash` (harbor/tasks/client.py:457, harbor/models/task/id.py:35). T0 is a 6-step bounded probe that validates the export layout BEFORE schema/translator code lands — `TaskConfig(name=..., ref=...)` natively was rejected because it bypasses the PKG-40 materializer.
- DONE: AC-3 task-view interaction: Specify how resolved Harbor tasks flow into the task-view materializer at packages/.../harbor_view.py without bypassing the solution-file exclusion + image override + runtime tooling layers. Cite the integration point.
  Integration point cited at src/razorback/benchmarks/ade_bench/harbor_view.py:22 (`materialize_ade_harbor_task_view`) and src/razorback/translate.py:311 (translator call site). T3 has an explicit guardrail test (`test_translator_preserves_docker_image_override_through_dataset_path`) asserting the dataset-ref path passes `docker_image` into the same materializer; T4 step 4 extends only the kwargs surface, not the call shape — so ADE_BENCH_DENY_GLOBS, dbt-deps Dockerfile layer, and RAZORBACK_BENCHMARK_* env injection apply unchanged.

### Summary

Wrote a separate plan doc with eight tasks. Riskiest-first: T0 probes Harbor's `TaskClient.download_tasks([PackageTaskId])` export layout in 6 bounded steps before any schema/translator code lands. The dataset-ref path is wired as a sibling source-resolver under the existing PKG-40 materializer (not a replacement); `dataset_ref` + `dataset_content_hash` ride into `view_manifest.json` (schema_version bump to 2) and freeze `provenance.yaml` to satisfy AC-2's pinning requirement. AC-5's no-submodule clause is enforced as an in-test `git submodule status` assertion in T7, not just a docs claim.
