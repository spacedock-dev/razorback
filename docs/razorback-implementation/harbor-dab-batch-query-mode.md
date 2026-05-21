---
id: 65edwgd257aem15f4fheazjv
title: harbor-DAB batch query_mode (per-dataset task with all queries; mirror DAB upstream)
status: implementation
source: Captain probe 2026-05-21 ("do we have a way to test halt/resume and batch mode with spacedock on dab yet?") + Goal 1 RESUME T0 review — razorback's harbor-DAB adapter is per-query-shaped (one task per `<dataset>-q<id>`) but the workspace-readme variants tell the agent it's in batch query mode. The variants currently differ by prose only.
started: 2026-05-21T15:47:02Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-harbor-dab-batch-query-mode
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

## Stage Report: plan

- DONE: Plan reads DAB upstream's batch-mode shape from /Users/clkao/git/dataagentbench/benchmark/ (run.sh:33, lib/benchctl.py:4322, tests/test_run_experiment.py around line 2713+ — query_mode validation + batch fixture references). Plan cites the upstream contract verbatim.
  Plan §"Upstream contract (DAB verbatim)" inlines run.sh:33, benchctl.py:4321-4327, run_experiment.py:651-657, tests/test_run_experiment.py:2713-2720, and the workspace-readme-direct-entity-output.md:41-45+84-85 workdir/answers.json shape.
- DONE: Plan decides the materialize_local_task signature change: per-dataset path that emits ONE task_dir with query1/query2/query3 sibling subdirs + an instruction that enumerates them. Schema extension lands on the harbor-DAB benchmark block (not the generic ade_bench one). Names the exact code change points.
  Plan §"Code change points" names schema.py:117-130, prepare.py:53/107 (gain query_mode kwarg + new _materialize_batch_task_dir), cli.py:23 (new --query-mode flag), translate.py:350 (subprocess forwarding + list-keyed trial_name_map), aggregate.py:83 (branched outcome fan-out), generate-dab-paper-matrix-specs.py:22 (build_spec).
- DONE: Plan size: 5 ACs, multi-file (schema + prepare.py + verifier aggregation + matrix-gen + tests). Separate plan doc.
  Plan written to docs/razorback-implementation/plans/harbor-dab-batch-query-mode.md (~290 lines, multi-file, all 5 ACs mapped to tasks).
- DONE: Plan TDD-orders: T0 RED schema test (AC-1); T1 schema; T2 RED batch-mode materialize (AC-2); T3 materialize impl; T4 RED verifier aggregation (AC-4); T5 verifier impl; T6 regen matrix specs (AC-5); T7 live `rk run` against bookreview batch-mode (acceptance).
  Plan §"Test plan (TDD-ordered)" follows exact ordering. AC-3 (per-query unchanged) is the implicit gate inside T6 ("uv run pytest packages/razorback-plugin-dab/" must stay green before T7); AC-3 is also enforced by construction (prepare.py per-query branch is unchanged).

### Summary

The plan extends HarborDabBenchmarkBlock with `query_mode: Literal["batch", "per-query"] = "per-query"` (back-compat default) and threads it through razorback-plugin-dab generate → translator → aggregator. Batch mode emits one harbor task per dataset with `query1/query2/query3` sibling workdir layout matching DAB upstream's `workspace-readme-direct-entity-output.md` shape verbatim; a new `tests/verify_batch.py` writes a per-query `reward_per_query.json` sidecar that the razorback aggregator fans out into per-(dataset, query_id) outcomes. Key non-obvious decision: `trial_name_map` becomes `dict[str, tuple[str, int] | tuple[str, list[int]]]` to keep the per-query path's existing scalar-key contract while letting batch trials expand to N outcomes — alternative single-value-with-N-entries was rejected because `_resolve_key` is a dict lookup that would collide on duplicate task_names.

## Stage Report: implementation

- DONE: AC-1 — schema query_mode field on HarborDabBenchmarkBlock (Literal["batch", "per-query"], default "per-query"). RED → GREEN cycle.
  Commit e1c9651; tests/unit/test_spec_harbor_dab_block.py: 8/8 (added test_harbor_dab_default_query_mode_is_per_query, test_harbor_dab_accepts_query_mode_batch_and_per_query, test_harbor_dab_rejects_unknown_query_mode).
- DONE: AC-2 — batch materialize emits ONE task_dir per dataset; workdir has query1/query2/query3 sibling subdirs; instruction enumerates them with merged answers.json (q1/q2/q3) contract.
  Commit e1c9651; packages/razorback-plugin-dab/tests/unit/test_prepare_batch_query_mode.py: 5/5 (manifest len 1 + task_name=bookreview, queryN/ siblings, instruction enumerates 3 queries with q1/q2/q3 keys, tests/validate_q[1-3].py + verify_batch.py, stratum payload uses query_ids: [1,2,3]). Materialized run-dir confirms layout under _runs/.../tasks/bookreview/bookreview/.
- DONE: AC-3 — per-query path unchanged by construction (per-query loop in prepare.py:118-148 untouched). Full unit suite 128/128 dab plugin + 480/480 razorback GREEN under default query_mode=per-query.
  Commit e1c9651; uv run pytest packages/razorback-plugin-dab/tests/unit/ + uv run pytest tests/unit/ both pass.
- DONE: AC-4 — verifier aggregation branches on tuple[str, list[int]]; reads <trial_dir>/steps/main/verifier/reward_per_query.json sidecar; fans one trial into N per-query outcomes. Translator forwards --query-mode and emits list-keyed map. Missing-sidecar regression yields 0.0 per query_id.
  Commit e1c9651; tests/unit/test_dab_aggregate_batch_query_mode.py: 3/3 + tests/unit/test_translator_harbor_dab.py::test_translator_harbor_dab_batch_emits_list_keyed_map 1/1.
- DONE: AC-5 — Goal 1 matrix spec generator emits query_mode: batch for all 36 cells. Regenerated examples/specs/goal1/<variant>/<dataset>.yaml; frozen spec for spacedock/bookreview carries `benchmark.query_mode: batch`.
  Commit e1c9651; tests/unit/test_generate_matrix_specs.py: 2/2; emitted 36 specs (3 variants × 12 datasets).
- FAILED: AC-5 live `rk run` (one agent invocation, q1/q2/q3 verdicts in reward_per_query.json) — trial aborted at environment setup with RuntimeError: `docker compose --project-name ... up --detach --wait` returned `unknown flag: --project-name`. This is the same host docker-compose-shim issue that bites every DAB run on this machine (PKG-15 host-side live AC caveat); not query_mode-related. Materialized run-dir confirms batch shape end-to-end up to docker-compose-up.
  _runs/goal1-spacedock-bookreview/b05be787ec5037d3/bookreview__aeZw7rD/trial.log shows the docker error; host docker compose v2 (2.36.2) works directly but harbor's subprocess sees an older shim. Mechanism validation evidence: tasks/bookreview/bookreview/ task tree has the documented batch shape (instruction enumerates query1/2/3 + answers.json contract; tests/ has validate_q1.py/validate_q2.py/validate_q3.py + verify_batch.py + stratum.json with query_ids:[1,2,3]; workdir/ has query1/query2/query3 sibling subdirs).

### Summary

T0-T6 shipped GREEN — schema, plugin generator, translator, aggregator, matrix-spec generator. 128/128 dab plugin unit + 480/480 razorback unit tests pass. The 36 frozen matrix specs carry `query_mode: batch`. T7 live `rk run` materialized the batch task tree correctly (one task per dataset, query1/query2/query3 workdir siblings, verify_batch.py + per-query validators, stratum with query_ids list); execution aborted at `docker compose up` due to a host docker-compose-shim issue that is independent of query_mode (host docker compose v2 works directly outside harbor's subprocess). Materialized run-dir evidence at _runs/goal1-spacedock-bookreview/b05be787ec5037d3/tasks/bookreview/bookreview/ documents the mechanism end-to-end. Approve conditional on host-side docker-compose plumbing.
