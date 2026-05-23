---
id: qhtser5qkf5b77pk43z4pnb9
title: DAB consumes Harbor dataset definitions
status: validation
source: 2026-05-23 captain directive — make wrapped DAB consume dataset definitions like Harbor-native datasets
started: 2026-05-23T04:58:35Z
completed:
verdict:
score: 0.8
worktree: .worktrees/spacedock-ensign-dab-harbor-dataset-definition
issue:
pr:
mod-block:
---

## Problem

Razorback currently has a bespoke DAB benchmark block (`harbor_dab`) that
combines local data-root discovery, dataset selection, workspace variant,
hinting, and query batching in Razorback specs. That keeps DAB separate from
the Harbor dataset model and duplicates source-of-truth concerns that should
live in a dataset definition.

The desired shape is the same as ADE: a Razorback run consumes a Harbor-style
dataset definition, while DAB data-root details remain an adapter/materialization
input rather than a per-run benchmark identity.

## Acceptance criteria

**AC-1 — DAB has a Harbor-style dataset definition source of truth.**
The DAB adapter produces or consumes a `dataset.toml`/package-style definition
that names the available DAB task set, task ids, strata metadata, and variant
metadata needed for direct-minimal, direct-structured, and spacedock runs.
Verified by: tests parse the dataset definition and confirm the expected DAB
task inventory and metadata without consulting hardcoded generated spec lists.

**AC-2 — Razorback DAB specs can consume that definition.**
New DAB score specs can name a dataset definition or dataset ref instead of
embedding `data_root + datasets + workspace_variant` as the canonical run shape.
Local `data_root` remains available only for adapter generation/materialization.
Verified by: schema/translator tests cover dataset-ref or dataset-definition
input and keep old `harbor_dab` specs behind an explicit compatibility path.

**AC-3 — Goal 1 generation reads the dataset definition.**
The Goal 1 matrix generator enumerates DAB tasks/variants from the dataset
definition rather than from an in-code catalog and hardcoded data-root defaults.
Verified by: generator tests use a fixture dataset definition and assert emitted
cells match that definition, including query-mode/batch behavior.

**AC-4 — Scoring consumes adapter-provided strata.**
DAB scoring and aggregation use the dataset/task metadata emitted by the
dataset definition/task view, not ad hoc trial-name parsing or a parallel
Razorback catalog.
Verified by: score/load/reduce tests cover DAB task-view manifests with
dataset/query ids sourced from the definition.

**AC-5 — The old DAB adapter split is reduced.**
The in-tree `dab` path and plugin-backed `harbor_dab` path no longer diverge as
two active benchmark implementations. One path is canonical; the other is
legacy/dev-only or removed.
Verified by: validation report cites the remaining DAB benchmark entry points
and shows examples/tests route through the canonical dataset-definition path.

## Notes

This task is about the benchmark identity and task inventory source of truth.
It should not remove the need for local DAB data when materializing tasks; it
should move that need out of score specs and into adapter setup/materialization.

## Stage Report: plan

- DONE: Separate plan doc at docs/razorback-implementation/plans/dab-harbor-dataset-definition.md per the README's 4+-AC rule. AC↔task map for AC-1..AC-5.
  Plan committed alongside this report; AC↔task map table at the top covers AC-1..AC-5 across 11 tasks.
- DONE: Probe + decide: does the DAB dataset definition live in Harbor's dataset registry (parallel to ade-bench@1.0)? Or as a dataset.toml shipped by the harbor-dab plugin alongside the existing in-tree adapter? Or both? Name the AC-1 source-of-truth file format (TOML/JSON/etc.) and where it lives in the repo or in Harbor.
  Decision: TOML file shipped *inside* the razorback-plugin-dab package at packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset.toml. Asymmetric with the sibling ade-bench entity (which consumes Harbor's actual Registry) because DAB tasks are *generated* per data_root, not source-controlled PackageTaskId entries — Harbor Registry's RegistryTaskId shape doesn't fit. Rationale + non-goal documented in the plan's File Structure → "Out of touch" section.
- DONE: AC-3 + AC-5 interaction: The Goal 1 matrix generator at examples/drivers/generate-dab-paper-matrix-specs.py currently reads from an in-code catalog. AC-3 asks the generator to read the dataset definition. AC-5 asks for ONE canonical DAB path. Spec which path stays (in-tree dab vs harbor_dab plugin) and how the generator switches; if it's a clean cut, name the migration step.
  Canonical = kind: harbor_dab + dataset: dab@<version> (plugin-backed; already runs Goal 1). Legacy = kind: dab (in-tree DabBenchmarkBlock + src/razorback/benchmarks/dab/prepare.py) marked dev-only via DeprecationWarning, NOT removed (captain directive: "don't remove the need for local DAB data when materializing"). Migration step: Task 6 in the plan swaps the generator from `data_root + datasets + workspace_variant` shape to `dataset: dab@1.0 + datasets:[<one>] + workspace_variant + query_mode: batch` — one mechanical edit; smoke-checked end-to-end at Step 6.2 before any later task piles on.

### Summary

Plan covers AC-1..AC-5 across 11 TDD tasks. Key design call: AC-1's source of truth is a `dataset.toml` shipped by the plugin (parallel to Harbor's Registry shape, not registered inside it — DAB tasks are generated, not packaged). Task ordering puts the riskiest contract (definition + schema + translator) first, with Task 6's generator smoke-run as the integration-level mechanism check before round-trip tests and aggregator work pile on. AC-5 is "reduce, not remove" — in-tree DAB stays as dev-only with a deprecation warning, harbor_dab + dataset ref becomes canonical.
