---
id: kw3vn8d1qj7r2p9zhx6f5tm4
title: PKG-16 — harbor-DAB plugin removes SQL dump from agent workdir (force live-DB queries)
status: implementation
source: Staff ML review 2026-05-20 finding F2; captain decision "i care only about F2"; PKG-13 debrief note H ("whether the agent actually queried postgres versus reading the SQL dump file is not directly observable")
started: 2026-05-20T20:54:07Z
completed:
verdict:
score: 0.95
worktree:
issue:
pr:
mod-block:
---

## Problem

The harbor-DAB plugin's agent workdir contains the full SQL dump (`books_info.sql`, equivalents for other datasets). The agent has Read+Bash access to the same file that postgres loads at compose-up time. PKG-13's substring-leak hardening (q1 bounded-decade match, q2/q3 length cap) closes the "paste dump verbatim" path but NOT the "grep dump and compute the answer" path. PKG-13's own debrief note H (`docs/superpowers/plans/2026-05-19-reconciliation-baseline.md:431-438`) admits: "whether the agent actually queried postgres versus reading the SQL dump file is not directly observable."

The Staff ML review's finding F2 surfaced this as a BLOCKER for Goal 1: the 9/9 reward=1.0 PKG-13 honest re-run may reflect the agent reading the SQL dump and answering from it, NOT querying postgres. If Goal 1's 12-dataset matrix runs with the same shape, the resulting numbers will be inflated by the same leak class across all 12 datasets (PKG-13's bookreview-specific hardening covers 1 of 12).

**Root cause**: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py:41-46` whitelists the entire `query_dataset/` subtree into the agent workdir via `_DATASET_SAFE`. `prepare.py:202-210` copies the directory verbatim. The SQL dump is supposed to be input for postgres at `/docker-entrypoint-initdb.d/` time, not a co-located cheat sheet for the agent.

**Fix shape**: remove the SQL dump (and any equivalent mongo BSON / sqlite / duckdb file with answers) from the agent workdir. The agent gets only the metadata files (`db_description.txt`, `db_config.yaml`, `query.json`) plus the live DB connection. The dump file is still bind-mounted into postgres's init.d for the DB to populate at compose-up; it just is not exposed at the agent's `/workdir/`.

This is the structural fix: closes the leak class across all 12 datasets at once, not just bookreview.

## Acceptance criteria

**AC-1 — Agent workdir does NOT contain `*.sql`, `*.bson`, `*.sqlite`, `*.duckdb`, or any file with `INSERT INTO`/`COPY FROM`/equivalent ground-truth payload.**
After `razorback-plugin-dab generate`, the agent's workdir under `steps/main/workdir/query_dataset/` contains ONLY: `db_description.txt`, `db_config.yaml`, `query.json` (or their per-dataset equivalents). NO file in the workdir contains the actual data rows.

Verified by: a unit test walks the generated workdir and asserts no `*.sql` / `*.bson` / `*.sqlite` / `*.duckdb` / `*.csv` (when CSV contains data rows; allow CSV if it's a schema-only file) is present. The test runs on bookreview, agnews (mongo), and a sample of other postgres datasets (e.g., crmarenapro).

**AC-2 — Postgres init still loads the dump (bind-mount source path moved, not removed).**
The compose's `dab-postgres` service still bind-mounts the SQL dump into `/docker-entrypoint-initdb.d/`. The dump comes from `data_root/query_<dataset>/` directly (which PKG-14 covers) OR from a non-workdir staging location. The agent container does NOT see this mount.

Verified by: live `docker compose up` + `psql` query against the `dab-postgres` service confirms the database is populated (e.g., `SELECT COUNT(*) FROM books_info` returns 1000+ rows for bookreview). The agent container's `ls /workdir/query_dataset/` does NOT show the `.sql` file.

**AC-3 — Bookreview honest re-smoke at opus-4.7 produces a result distinguishable from PKG-13's 9/9.**
After AC-1 + AC-2 land, re-run the PKG-13 T14-shape smoke at opus-4.7 (NOT 4.5 — Goal 1 targets 4.7). The result is the new anchor for Goal 1's bookreview baseline. Expected: NOT 9/9 reward=1.0, because the agent can no longer cheat via the dump.

The expected band is unknown a priori (PKG-13's 9/9 included the leak). A 50-80% per-question pass rate is the staff ML reviewer's prior. If the re-smoke STILL produces 9/9 after the dump is removed, that's evidence of either (a) genuine SQL competence or (b) a residual leak somewhere else (needs investigation before Goal 1 dispatches).

Verified by: `uv run rk run examples/specs/pkg16-bookreview-claude-harbor-dab-n3-opus47.yaml --runs-dir _runs/pkg16-bookreview-opus47 --max-budget-usd-running 5` completes with a recorded `result.json`. The per-question reward distribution is captured in the PKG-16 result section of `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`. The original PKG-13 9/9 entry is annotated with "INFLATED — agent had Read+Bash on `books_info.sql`; superseded by PKG-16 re-smoke."

**AC-4 — All 12 datasets benefit from the structural fix.**
Because the workdir-population layer is centralized (`prepare.py:_materialize_task_dir`), the fix applies uniformly. A unit test confirms that for each of the 12 DAB datasets, the generated workdir does NOT contain ground-truth-bearing files.

Verified by: `pytest packages/razorback-plugin-dab/tests/test_workdir_no_dump.py` runs green; the test iterates the full dataset catalog and asserts the absence pattern from AC-1 for each.

**AC-5 — Existing plugin tests still pass (no regression).**
The 70+ existing plugin tests, plus the new AC-1 + AC-4 tests, all run green. Specifically: PKG-13's `test_ac9_missing_dataset.py`, the bookreview-q1 bounded-decade test, the q2/q3 length-cap test, and the reachability-gate negative test still pass.

Verified by: `uv run pytest packages/razorback-plugin-dab/` reports N/N passed.

**AC-6 — Reconciliation-baseline doc updated honestly.**
The reconciliation-baseline doc gets a new "PKG-16 honest re-smoke (post-workdir-dump-removal, opus-4.7)" row. The PKG-13 row gets the inflation annotation per AC-3. The pre-registered shift band section is updated to acknowledge that the PKG-13 9/9 was potentially inflated by the workdir leak.

Verified by: the doc's "Run" table contains both rows; the methodology section documents the F2 fix.

## Test plan

- **Plan stage** reviews `prepare.py:_materialize_task_dir` + `_DATASET_SAFE` and identifies the smallest change that exposes only metadata files to the agent workdir while preserving the postgres / mongo init bind-mount path.
- **Implementation stage** applies the change TDD-first: write the AC-1 + AC-4 unit tests first (RED), then make them GREEN. Run the full plugin test suite after each task.
- **Validation stage** dispatches the AC-3 bookreview re-smoke at opus-4.7 with subscription auth + budget cap. Inspects the result distribution. Updates the reconciliation-baseline doc per AC-6.

## Out of scope

- F1 (stratum collapse) — captain decision 2026-05-20: "the others can wait." Stratum-per-query is a separate entity for later.
- F3 (tools_denied not enforced for claude-cli) — same decision.
- F4 (temperature not threaded) — same decision.
- F5 (no CI on `--against-constant` stratified row) — same decision.
- F7 (opus-4.5 → opus-4.7 silent model swap) — partially addressed by AC-3 re-anchoring at opus-4.7.
- F8 (3 variants are functionally identical) — outside PKG-16 scope; reproduction-doc framing change at Goal 1 result-summary time.
- F9 (macro vs micro strat recipe) — outside scope.
- F10 (image digest enforcement at compose time) — outside scope.
- Generalizing the workdir-population layer to ade-bench — that benchmark has its own probe-flagged hazard (`seeds/solution__*.csv` visible to agent container) which the ade-bench probe surfaced. Filed separately if needed.
- The mongo init mechanism (BSON dump auto-restore) — PKG-15 covers that orthogonally. PKG-16 closes the workdir leak on the agent side; PKG-15 closes the postgres init side.

## Depends on

- PKG-13 (DONE) — compose-loading + reachability-gate scaffolding lives on main. PKG-16 modifies `prepare.py:_materialize_task_dir` which PKG-13 also touched.
- 51 phase2-dab-harbor-adapter (DONE) — the plugin shape PKG-16 modifies.

## Blocks

- Goal 1 — DAB paper reproduction. Goal 1 cannot dispatch honestly until the workdir leak closes. Captain authorized this sequencing.
- (Indirectly) Re-anchoring the pre-registered shift bands at opus-4.7 (F7) depends on the AC-3 re-smoke. Goal 1's pre-reg validity is conditional on AC-3.

## Stage Report: plan

- DONE: Read PKG-16 entity (6 ACs) and identified the smallest change to prepare.py that exposes only metadata + file-backed live-DB files to the agent workdir while preserving the postgres/mongo init bind-mount path.
  Reviewed prepare.py:41-46 + prepare.py:202-210 + compose.py:56-73; the cut point is the workdir-copy loop plus the compose bind-mount source path.
- DONE: Identified the smallest change to prepare.py — replace the blanket `_DATASET_SAFE` copy with a classifier that excludes `db_config.sql_file`/`dump_folder` paths from the workdir, stages them under `<task_dir>/environment/_initdb/`, and re-points compose bind-mount sources to `./_initdb/{name}`. File-backed sqlite/duckdb files stay in the workdir because they ARE the live DB.
  Plan Task 3, prepare.py:39-46 + 202-210 + compose.py:56-73.
- DONE: Wrote a TDD-first plan that ships AC-1..AC-6 in risk-first order. T2 RED unit test (AC-1) before T3 GREEN impl; T5 12-dataset catalog walk (AC-4) after the bookreview case proves the mechanism; T6 docker-compose-config regression (AC-2); T7 full pytest sweep (AC-5); T8 opus-4.7 spec (AC-3) and T9 reconciliation doc-update spec (AC-6) for the validation stage to execute.
  Plan written at docs/razorback-implementation/plans/pkg16-harbor-dab-workdir-no-sql-dump.md.
- DONE: Cross-referenced PKG-13 prepare.py changes — Task 4 explicitly updates the PKG-13 `test_compose_bind_mount_sources_resolve_to_real_files` assertion (which encoded the OLD `steps/main/workdir/` contract) to assert the new `environment/_initdb/` contract, AND Task 7 re-runs PKG-13's reachability-gate / validator-hardening / task-toml-lint tests to confirm no regression.
  Plan Tasks 4 and 7.
- DONE: Wrote plan to docs/razorback-implementation/plans/pkg16-harbor-dab-workdir-no-sql-dump.md.
  Single file, 9 tasks, AC↔task map at top.

### Summary

Designed a structural fix at `prepare.py:_materialize_task_dir`: classify each `query_dataset/` entry against `db_config.yaml`'s `sql_file` / `dump_folder` references and copy only non-dump entries into the agent workdir, staging dumps under `<task_dir>/environment/_initdb/` and re-pointing `compose.py`'s postgres/mongo bind-mount source from `../steps/main/workdir/{sql_file}` to `./_initdb/{basename}`. Sqlite/duckdb live-DB files remain in the workdir because they ARE the live DB the agent must query directly. The plan deliberately stages dumps under the task-dir (not via PKG-14's data_root bind-mount) so PKG-16 lands independently of PKG-14; the riskiest contract (compose source resolution) is validated by Task 2's RED unit test before any code moves.

## Stage Report: implementation

- DONE: Read PKG-16 entity (6 ACs) + plan at docs/razorback-implementation/plans/pkg16-harbor-dab-workdir-no-sql-dump.md (9 tasks, TDD-first).
  Entity + plan reviewed before any code edits; 9 plan tasks executed in order.
- DONE: Execute the 9 plan tasks in order. Riskiest-contract-first: Task 2 RED unit test (workdir absence of *.sql/*.bson/*.sqlite/*.duckdb) before Task 3 GREEN impl in prepare.py:_materialize_task_dir.
  T2 RED committed at 2f1d41f (3 failed, 1 passed); T3 GREEN committed at 1c86d33 (4/4 passing).
- DONE: Plan's structural fix: classify each query_dataset/ entry against db_config.yaml's sql_file/dump_folder refs; copy ONLY non-dump entries into agent workdir; stage dumps under <task_dir>/environment/_initdb/; re-point compose.py's postgres bind-mount source from ../steps/main/workdir/{sql_file} to ./_initdb/{basename}.
  prepare.py:_dump_paths helper + filtered query_dataset/ copy + environment/_initdb/ staging; compose.py source path now `./_initdb/{basename}` (commit 1c86d33).
- DONE: Task 4 explicitly updates PKG-13's test_compose_bind_mount_sources_resolve_to_real_files assertion (the OLD steps/main/workdir/ contract) to match the new environment/_initdb/ contract.
  test_prepare_per_query.py:test_compose_bind_mount_sources_resolve_to_real_files now asserts `steps/main/workdir not in str(resolved)` (commit 57b60fc).
- DONE: Task 5 catalog walk: confirm AC-4 across all 12 datasets (test_workdir_no_dump.py).
  parametrized test runs for all 12 catalog datasets; 16/16 cases green (commit 2ce9092).
- DONE: Task 6 docker-compose-config regression (AC-2): generated compose still resolves postgres bind-mount to a real existing file under environment/_initdb/.
  integration/test_compose_parses.py::test_docker_compose_config_parses_generated_tree PASSED; live `docker compose config -q` exits 0 with the new `./_initdb/books_info.sql` source.
- DONE: Task 7 full plugin pytest sweep (AC-5): 70+ tests still pass, including PKG-13 reachability-gate / validator-hardening / task-toml-lint tests.
  `uv run pytest packages/razorback-plugin-dab/` reports 89 passed, 1 skipped (no regressions).
- DONE: Task 8 emits examples/specs/pkg16-bookreview-claude-harbor-dab-n3-opus47.yaml for the validation-stage AC-3 re-smoke (do NOT execute the smoke here; validation does that).
  Spec committed at 35249a3; opus-4.7 + temperature 0.0 + N=3 + $5 max_budget_usd.
- DONE: Task 9 stages the AC-6 reconciliation-baseline doc-update copy as a draft for validation to land.
  Plan Task 9 spec text retained in plan file; doc-edit is validation-stage scope per the entity Test plan.
- DONE: Write impl-stage stage report at the bottom of the entity file with per-task DONE/SKIPPED/FAILED entries.
  This report.

### Summary

PKG-16 implementation landed across 4 commits: RED test (2f1d41f), GREEN impl in prepare.py + compose.py (1c86d33), PKG-13 contract-update (57b60fc), 12-dataset catalog walk (2ce9092), and AC-3 opus-4.7 spec (35249a3). All 89 plugin tests pass; the live `docker compose config -q` integration test confirms postgres can still find `./_initdb/books_info.sql` while the agent's workdir contains only metadata + sqlite live DB. Note: the plan's prediction that `test_compose_bind_mount_sources_resolve_to_real_files` would FAIL after the GREEN impl proved incorrect — the existing assertion was path-agnostic (existence-only), so Task 4 strengthened it to encode the new "not under steps/main/workdir" contract rather than fixing a broken assertion.
