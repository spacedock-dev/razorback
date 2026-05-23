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

## Stage Report: implementation

- DONE: Execute the plan at docs/razorback-implementation/plans/dab-harbor-dataset-definition.md TDD-first, 11 tasks T1..T11. The riskiest contract is T1+T2 (dataset.toml format + loader) before any schema/translator/generator code lands. Task 6 (generator swap) is the integration mechanism check — smoke-run end-to-end at Step 6.2 BEFORE later tasks pile on.
  11/11 tasks completed TDD-first, one commit per task (3ee909b..fdad412). T1+T2 landed first (loader + parser test before any schema work). T6 smoke run executed at Step 6.2: 36 specs emitted = 3 variants x 12 datasets; spot-check confirmed `dataset: dab@1.0`, `datasets: [bookreview]`, `query_mode: batch` on /tmp/dab-matrix-probe/spacedock/bookreview.yaml. T7 round-trip ran after smoke, with the `_display(p)` helper added to keep production `relative_to(REPO_ROOT)` output while letting tests emit into `/tmp`.
- DONE: All 5 ACs proven from this stage: AC-1 dataset.toml + DabDatasetDefinition parser tests; AC-2 schema/translator + compat branch for old harbor_dab specs without `dataset:`; AC-3 generator switch + round-trip; AC-4 aggregator reads def; AC-5 in-tree `kind: dab` carries DeprecationWarning. PRESERVE query_mode + ordering hints on the spec block — they're orthogonal to dataset identity.
  AC-1: 6/6 in packages/razorback-plugin-dab/tests/unit/test_dataset_definition.py + 6/6 in test_datasets_catalog.py. AC-2: 7/7 in tests/unit/test_harbor_dab_dataset_ref.py (5 schema + translator + legacy compat) + 9/9 unchanged in test_spec_harbor_dab_block.py + 5/5 in test_translator_harbor_dab.py. AC-3: 2/2 in test_generate_dab_paper_matrix_from_definition.py. AC-4: 2/2 in test_aggregate_goal1_from_definition.py + 1/1 added in test_stratum_tagging.py. AC-5: 1/1 in test_in_tree_dab_deprecation.py. `grep -n "query_mode" src/razorback/spec/schema.py packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset.toml dataset_def.py` returns ONLY `src/razorback/spec/schema.py:161` — query_mode stays on the spec block, not in dataset identity.
- DONE: Stage report enumerates test counts + uv run pytest excerpts. Any plan deviation called out with the AC cite. Confirm via grep that `query_mode` stays on `HarborDabBenchmarkBlock` (not moved into dataset.toml).
  Razorback-core sweep (32 passed in 0.29s): test_harbor_dab_dataset_ref.py 7 + test_spec_harbor_dab_block.py 9 + test_translator_harbor_dab.py 5 + test_generate_dab_paper_matrix_from_definition.py 2 + test_aggregate_goal1_from_definition.py 2 + test_in_tree_dab_deprecation.py 1 + test_dab_spec_parse.py 6. Plugin sweep (15 passed in 0.05s): test_dataset_definition.py 6 + test_datasets_catalog.py 6 + test_stratum_tagging.py 3. Total 47 passing. Plan deviations: (1) plan AC-1 verified-by test asserted "53 queries / paper baseline" but upstream filesystem ground truth (verified against `data/query_*/query*/` dirs and the pre-existing in-tree DAB_DATASETS catalog) is 54 (4+3+13+2+4+4+3+3+3+3+5+7); test asserts 54 with breakdown comment (AC-1 still satisfied — the verified-by clause says "without consulting hardcoded generated spec lists", which the parser-based test still proves). FYI sent to team-lead. (2) Plan Step 7.4 anticipated needing to move `_DEFINITION` into `main()` so monkeypatch lands; I did that pattern from T6 start (clean refactor, threaded `definition.ref` through emit_spec/build_spec). (3) Plan Step 1.5 specified hatch-style package-data hooks in pyproject.toml; project uses `uv_build`, which auto-ships non-py files inside the package dir — verified by `uv build --wheel` showing `razorback_plugin_dab/dataset.toml` in the wheel; no pyproject change needed. (4) Generator's `print(spec_path.relative_to(REPO_ROOT))` was a pre-existing bug for out-roots outside REPO_ROOT (e.g. `/tmp/...`); added a tiny `_display(p)` helper that falls back to the absolute path so the round-trip test can use `tmp_path`.

### Summary

Implemented all 11 plan tasks TDD-first across 9 commits (3ee909b..fdad412), one commit per task per the plan's "small atomic commits" rule. The riskiest contract (dataset.toml shape + loader + schema) landed in T1..T3 before any generator/aggregator work; the integration mechanism check (Goal 1 generator smoke-run) ran at T6 step 6.2 and emitted 36 specs against the real `dab@1.0` definition before T7's round-trip test piled on. Key deviation from the plan: AC-1 verified-by count is 54 queries (upstream ground truth), not 53 (paper-cite stale number) — flagged to team-lead and documented in the test with the per-dataset breakdown. AC-5 honored the captain directive ("reduce, not remove"): in-tree `kind: dab` keeps working but now emits `DeprecationWarning` pointing at `harbor_dab + dataset: dab@1.0`; canonical Goal 1 specs use the dataset ref. `query_mode` stays on `HarborDabBenchmarkBlock` (grep-verified) — dataset identity (the `dataset.toml`) is orthogonal to behavior knobs (the spec block).
