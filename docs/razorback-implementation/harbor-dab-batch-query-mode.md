---
id: 65edwgd257aem15f4fheazjv
title: harbor-DAB batch query_mode (per-dataset task with all queries; mirror DAB upstream)
status: plan
source: Captain probe 2026-05-21 ("do we have a way to test halt/resume and batch mode with spacedock on dab yet?") + Goal 1 RESUME T0 review — razorback's harbor-DAB adapter is per-query-shaped (one task per `<dataset>-q<id>`) but the workspace-readme variants tell the agent it's in batch query mode. The variants currently differ by prose only.
started: 2026-05-21T15:47:02Z
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

DAB upstream's `benchmark/run.sh` accepts `--query-mode {batch,
per-query}` (default `batch`). In **batch** mode, ONE agent
invocation per dataset solves every query in the workspace.
In **per-query** mode, ONE agent invocation per query.

Razorback's harbor-DAB adapter
(`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py:65`)
hardcodes per-query task shape: `task_name = f"{dataset}-q{query_id}"`
(line 112). For bookreview that's 3 separate harbor tasks
(`bookreview-q1`, `bookreview-q2`, `bookreview-q3`), each
materialized into its own workdir with ONE query, dispatched as
3 separate agent invocations.

**The workspace-readme variants we use (spacedock,
direct-minimal, direct-structured) all say "batch query mode" in
their prose** (see
`/Users/clkao/git/dataagentbench/benchmark/workspace-readmes/workspace-readme-sql-only.md`
line 30+: "benchmark-provided hints enabled, batch query mode,
Docker isolation"). The agent reads "solve every query in the
workspace during this single agent turn" — but the workspace has
ONE query, so there's nothing to batch.

Goal 1's archived PARTIAL ship and the in-flight RESUME both
operate under this per-query shape. The 3 variants thus differ
ONLY by prose framing (the previously-acknowledged ML reviewer F8
caveat). To reproduce the paper's batch-mode claims, harbor-DAB
must materialize per-dataset (not per-query) tasks under
`query_mode: batch`.

Razorback source grep for `query_mode` / `QueryMode`: **0 matches.**
The concept doesn't exist in razorback today.

## Acceptance criteria

**AC-1 — Spec exposes `query_mode: {batch, per-query}` on the
harbor-DAB benchmark block.** Default `per-query` (preserves
current behavior); explicit `batch` triggers the per-dataset task
shape. Schema extension in
`src/razorback/spec/schema.py` (or the harbor-DAB-specific block
location).
Verified by: a unit test asserts the schema accepts both values
and rejects others.

**AC-2 — Batch-mode materialization produces one task per
(dataset).** Under `query_mode: batch`,
`materialize_local_task` (or the analogous DAB function) emits
`task_name = dataset` (no `-q<id>` suffix). The materialized
workdir contains ALL queries (`query1/`, `query2/`, `query3/`
sibling subdirs) and the instruction prompt enumerates them.
Verified by: a unit test materializes a bookreview spec in batch
mode and asserts exactly one task dir contains `query1`,
`query2`, `query3` subdirs.

**AC-3 — Per-query mode unchanged.**
The existing per-query path (one task per `dataset-q<id>`) stays
working for back-compat. All existing PKG-13/14/15/16/17/21/25
tests stay green.
Verified by: `uv run pytest packages/razorback-plugin-dab/`
passes.

**AC-4 — Batch-mode verifier aggregates over per-query verdicts.**
The verifier for a batch-mode task runs all queries' verifiers in
sequence and returns a per-query-verdict map (NOT a single bool).
`rk score` consumes the map and stratifies pass@1 per query.
Verified by: a unit test asserts a batch-mode trial's
`per_trial_outcomes.json` contains a query-keyed verdict map; a
follow-up `rk score` against the matrix's per-cell results
produces stratified per-query rewards.

**AC-5 — Goal 1 RESUME re-dispatches with `query_mode: batch`.**
Goal 1 RESUME's matrix spec generator emits batch-mode specs for
the 3 variants × 12 datasets = 36 cells. Each cell is now
genuinely one agent turn per (variant, dataset).
Verified by: regenerated frozen spec for spacedock/bookreview has
`benchmark.query_mode: batch`; a live `rk run` of that cell shows
one agent invocation handling all 3 questions.

## Test plan

- **Unit:** new tests for schema (AC-1), batch-mode materialization
  (AC-2), per-query regression (AC-3), verdict aggregation (AC-4).
- **Integration:** live `rk run` against bookreview batch-mode
  produces a single agent-turn trial with verdicts for q1, q2, q3.
- **Acceptance:** Goal 1 RESUME re-dispatches under batch mode.

## Out of scope

- Per-query mode deprecation. Stay supported indefinitely.
- ade-bench / Goal 2. Different adapter; if ade-bench has a batch
  concept it's a sibling entity.
- Spacedock workflow variants. Already covered by the workspace-
  readme variant selector; this entity only changes task shape.
- Verifier aggregation strategy beyond per-query reduction. AC-4
  intentionally keeps the per-query verdict map; downstream
  stratification (per-question pass@1) is `rk score`'s job.

## Depends on

- PKG-13 / 14 / 15 / 16 / 17 / 21 / 25 — all shipped harbor-DAB
  prerequisites
- spacedock_solver_v2 — already supports the multi-question
  agent turn (its design intent)

## Resume hook

After this entity merges:
1. Goal 1 RESUME's T1 regenerates frozen specs with
   `query_mode: batch`.
2. The matrix dispatches as 36 cells of batch-mode (vs the prior
   ~108 = 36×3 per-query invocations). Wall projection drops
   ~3× (one agent turn per cell vs three).
3. Per-variant comparison becomes load-bearing — variants now
   differ by agent ARCHITECTURE (spacedock_solver_v2 vs claude-
   cli-as-ClaudeCode-subclass per the per-variant-kinds entity)
   AND by task SHAPE (batch agent turn per dataset).
4. Cost projection improves correspondingly (one agent setup
   teardown per dataset; intra-task tool use shares context).
