---
id: qhtser5qkf5b77pk43z4pnb9
title: DAB consumes Harbor dataset definitions
status: plan
source: 2026-05-23 captain directive — make wrapped DAB consume dataset definitions like Harbor-native datasets
started: 2026-05-23T04:58:35Z
completed:
verdict:
score: 0.8
worktree:
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
