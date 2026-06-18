---
id: r5hpxtc97nws6qfjc2j8ewz3
title: spider2-dbt — duckdb_match verifier emitting binary reward.json
status: implementation
source: Spider2 evaluation_suite/eval_utils.duckdb_match + gold/spider2_eval.jsonl schema; harbor verifier reward.json contract
started: 2026-06-18T08:49:13Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-spider2-dbt-duckdb-match-verifier
issue:
pr:
mod-block:
---

## Problem

Spider2-dbt scoring is binary `duckdb_match`: for each task the gold
spec (`spider2_eval.jsonl`) names `condition_tabs`, `condition_cols`
(0-based column indices), and `ignore_orders`; the scorer compares the
agent-produced `.duckdb` against the gold `.duckdb` table-by-table on
those columns and awards 1.0 only if every table matches, else 0.0.
This task emits a Harbor verifier (`tests/test.sh` + a bundled Python
comparator) that reproduces that semantics and writes
`/logs/verifier/reward.json` in Harbor shape. The gold `.duckdb` + eval
spec live under verifier-only paths excluded from the agent view by the
deny-globs. The retired `src/razorback/_legacy/benchmarks/dab/verify.py`
is a reference for the comparison + reward shaping.

## Acceptance criteria

**AC-1 — The comparator scores 1.0 on a matching DB and 0.0 on a mismatch.**
Verified by: a unit test with two tiny DuckDB fixtures — one matching
gold on `condition_tabs`/`condition_cols`, one differing — asserting
reward 1.0 and 0.0 respectively.

**AC-2 — Column subsetting and `ignore_orders` honor duckdb_match semantics.**
Verified by: a unit test asserting (a) a row-reordered table still
scores 1.0 when `ignore_orders` is true, and (b) a difference in a
column NOT listed in `condition_cols` does not lower the score.

**AC-3 — The emitted `tests/test.sh` writes a Harbor-shaped reward.json.**
Verified by: a test running the emitted `test.sh` against a fixture view
and asserting `/logs/verifier/reward.json` parses to `{"reward": <float>}`.

## Test plan

Unit tests build small `.duckdb` fixtures (predicted + gold) and drive
the comparator directly, plus one test that executes the generated
`test.sh`. Validation acceptance command: `uv run pytest -k spider2_dbt_verify`.

## Out of scope

dbt build orchestration inside the container (the agent runs `dbt build`;
the verifier only compares outputs) — covered by
`spider2-dbt-harbor-view-ade-parity`. Multi-DB / non-DuckDB Spider2
answer types (`string_match`, `table_match`, BigQuery/Snowflake) — the
dbt track is DuckDB-only.

## Stage Report: plan

- DONE: Map the 3 ACs to concrete modules with a TDD checkpoint each
  Plan AC↔Task table maps AC-1→T1/T2 (`duckdb_match.py`+`eval_spec.py`), AC-2→T3/T4, AC-3→T5/T6/T7 (`verify.py` + materializer-emitted `tests/test.sh`); each task has failing-test-first steps. Comparator module = `src/razorback/benchmarks/spider2_dbt/duckdb_match.py`; `test.sh` emitted by `_ensure_verifier_assets` in `spider2_dbt/harbor_view.py`.
- DONE: Exercise the riskiest mechanism first (two tiny DuckDB fixtures + comparator reproducing duckdb_match) before wiring test.sh
  T2–T4 build in-test DuckDB fixtures and prove per-table SELECT */condition_cols subset/ignore_orders semantics before any test.sh plumbing (T5–T7); reward-shaping cites `_legacy/benchmarks/dab/verify.py:30-32`.
- DONE: Write a standard separate plan doc with an AC-to-task map and cites; keep gold .duckdb + eval spec on verifier-only paths excluded from the agent view
  Plan at `docs/razorback-implementation/plans/spider2-dbt-duckdb-match-verifier.md` cites Spider2 `eval_utils.duckdb_match` + `spider2_eval.jsonl` schema. Locked design: gold lives under source `tests/gold/` (stripped by `**/gold/**`), re-copied explicitly to view `tests/` (verifier-uploaded only). Verified live: `tests/gold/gold.duckdb` denied=True, `tests/gold.duckdb`/`tests/spider2_eval.jsonl` denied=False; `duckdb` 1.5.2 importable.

### Summary

Wrote a separate implementation plan (3 ACs, 7 tasks) for the spider2-dbt duckdb_match verifier. Riskiest-first: the comparator reproducing Spider2 `duckdb_match` (per-table SELECT *, condition_cols subset, ignore_orders multiset compare, all-tables-AND) is built and proven against in-test DuckDB fixtures before any test.sh wiring. Key locked decision: gold `.duckdb` + eval spec are verifier-only by placing them under the view's `tests/` dir (Harbor uploads `tests/` to the container only at verify time, removes it around the agent run), copied explicitly so the `**/gold/**` deny-glob keeps the agent-facing tree clean — confirmed live against the deny-globs and the harbor verifier/trial source. One open item flagged: the agent-produced DB's container path (`/app/spider2.duckdb`) in the emitted test.sh is a placeholder pending the `spider2-dbt-harbor-view-ade-parity` image/workdir contract; it does not affect the gating `uv run pytest -k spider2_dbt_verify` suite.

## Stage Report: implementation

- DONE: Implement the approved plan TDD-first so all 3 ACs pass (eval-spec loader + duckdb_match comparator, verify.py CLI, materializer emitting tests/test.sh + verifier-only gold assets); `uv run pytest -k spider2_dbt_verify` green
  18 passed (commits c72d551, 06be8be, 1a3b612). `eval_spec.py`+`duckdb_match.py` (per-table SELECT *, 0-based condition_cols subset, ignore_orders Counter multiset compare, AND across condition_tabs, missing-table=mismatch) → AC-1/AC-2 (11 comparator tests); `verify.py` emit_reward → harbor `{"reward": 1.0|0.0}` at parent-created path; `_ensure_verifier_assets` in `harbor_view.py` copies the 3 modules + gold.duckdb + spider2_eval.jsonl + executable test.sh into the view's `tests/` → AC-3 (5 CLI/emission + 2 integration tests). Acceptance run excluded the pre-existing-broken `tests/unit/test_task_identity_scoring.py` (imports nonexistent `razorback.score.load`, untouched by this branch).
- DONE: RIDER — emitted test.sh predicted-DB path CONSUMES resolve_spider2_db_name to produce /app/<db_name>.duckdb (not hardcoded /app/spider2.duckdb); add a test asserting the predicted path is correct for a NON-spider2 slug/db name
  `harbor_view.py` `_ensure_verifier_assets` calls `resolve_spider2_db_name(project_dir or view, task_slug=...)` and formats `_TEST_SH_TEMPLATE` with `/app/{db_name}.duckdb`. `test_spider2_dbt_verify_test_sh_uses_resolved_db_name` materializes with `task_slug="not-spider2-slug"` (fixture ships no profiles.yml/*.duckdb → resolver falls back to slug) and asserts `/app/not-spider2-slug.duckdb` present and `/app/spider2.duckdb` absent.
- DONE: Keep gold .duckdb + eval spec on verifier-only paths; keep the generic materializer + non-spider2 harbor behavior unchanged
  Source gold lives under `tests/gold/` (matched by `**/gold/**` deny-glob, stripped from the reflected view), re-copied explicitly to the view's `tests/gold.duckdb`/`tests/spider2_eval.jsonl` (no `gold/` segment); the now-empty `gold/` dir left by reflection is pruned. Leakage-clean asserted in `test_spider2_dbt_verify_view_carries_verifier_assets`; existing harbor_view (8) + preflight (21) suites unchanged. Gold fixture is reproducible via `tests/gold/build_gold.py` (no opaque committed binary).

### Summary

Shipped the spider2-dbt duckdb_match verifier TDD-first across 3 commits: a pure comparator reproducing Spider2 `eval_utils.duckdb_match` (per-table SELECT *, 0-based condition_cols subsetting, ignore_orders multiset compare, all-tables-AND, missing-table mismatch), a `verify.py` CLI emitting harbor's `{"reward": <float>}`, and a materializer step copying the comparator+gold+test.sh into the view's verifier-only `tests/`. The mandatory rider is satisfied: the emitted `test.sh` `--predicted-db` path is resolved through ny's now-merged `resolve_spider2_db_name` (`/app/<db_name>.duckdb`), proven by a NON-spider2-slug test. Deviation from the plan's literal `_TEST_SH`: the hardcoded `/app/spider2.duckdb` was replaced by the resolver-driven template (the rider's purpose), and a `gold/`-empty-dir prune was added so the leakage assertion holds exactly. `uv run pytest -k spider2_dbt_verify` = 18 passed (ignoring one pre-existing-broken, unrelated scoring test file).

## Stage Report: validation

- DONE: Independently reproduce the 3 ACs from a clean worktree checkout (AC-1/AC-2/AC-3); run `uv run pytest -k spider2_dbt_verify --ignore=tests/unit/test_task_identity_scoring.py`
  Gating suite 18 passed. AC-1/AC-2/AC-3 all reproduce green via a standalone script driving `compare_duckdb` + the materializer; additionally executed the emitted `test.sh` end-to-end (paths substituted) → reward.json `{"reward":1.0}` match / `{"reward":0.0}` mismatch.
- DONE: Confirm the mandatory rider (resolved `/app/<db_name>.duckdb`, NOT hardcoded) for a NON-`spider2` slug; confirm duckdb_match reproduction matches Spider2 eval_utils semantics
  Rider CONFIRMED: `task_slug="not-spider2-slug"` → test.sh `--predicted-db /app/not-spider2-slug.duckdb`, no `/app/spider2.duckdb`. Faithfulness FAILED (B2): impl is row-tuple + exact-`==`; Spider2 `compare_pandas_table` is column-containment + `math.isclose(abs_tol=1e-2)` + per-column sort, and the real spec schema is `List[List[int]]`/`List[bool]` under `evaluation.parameters` (impl uses dict + single bool, flat — would not parse real gold).
- DONE: Confirm gold assets verifier-only; scrutinize the two flagged deviations; confirm no regression; give a gate verdict
  Path-based isolation sound (no `gold/` segment survives). Deviation 1 (rider path override) ACCEPTED/correct; deviation 2 (empty `gold/` prune) ACCEPTED. REGRESSION found (B1): `test_translate_spider2_dbt.py` (2 tests) pass on base `9c39af2`, fail on branch — verifier assets trip the production content-leakage scanner. 4 other full-suite failures are pre-existing on base (not regressions). Verdict: REJECTED.

### Summary

Independent verification only — no production code written. The 3 ACs as literally written reproduce green (18-passed gating suite + standalone AC repro + a real end-to-end test.sh run) and the mandatory resolver rider is satisfied for a non-spider2 slug. Verdict is REJECTED → implementation on two blocking findings: (B1) a branch-induced regression — the verifier assets written into the view's `tests/` trip `test_translate_spider2_dbt.py`'s content-leakage scanner, which passes on the merge-base; and (B2) the `duckdb_match` reproduction is not faithful to Spider2's `eval_utils.duckdb_match` (row-tuple/exact compare vs Spider2's column-containment + 1e-2 float tolerance + per-column sort) and models an incompatible eval-spec schema that would not parse a real `spider2_eval.jsonl` line. Both pre-flagged deviations (rider path override, empty `gold/` prune) are accepted as correct. Full report: docs/razorback-implementation/validation/spider2-dbt-duckdb-match-verifier.md

## Feedback Cycles

### Cycle 1 — validation gate REJECTED (2026-06-18)

Validation (reviewer fetched the real xlang-ai/Spider2 `eval_utils.duckdb_match`)
found two blocking defects. Routing back to `implementation`:

1. **[Critical] B2 — comparator + eval-spec schema do NOT match Spider2's `duckdb_match`.**
   The real Spider2 semantics (from `evaluation_suite/eval_utils.py`):
   - **Column-containment, not row-tuple equality:** transpose both tables to column-vectors; for each GOLD column (restricted to `condition_cols`), assert some PRED column-vector matches it. Per-column sorting is applied; numeric compare uses `math.isclose(abs_tol=1e-2)`.
   - **Eval-spec schema:** each gold line is `{"instance_id", "evaluation": {"func":"duckdb_match", "parameters": {"gold", "condition_tabs": [...], "condition_cols": [[int,...],...], "ignore_orders": [bool,...]}}}`. `condition_cols` is `List[List[int]]` and `ignore_orders` is `List[bool]` (per-table), NOT a flat dict + single bool. The current flat schema would silently score every prediction 1.0 on a real gold line.
   **Fix:** re-derive `compare_duckdb` to reproduce Spider2's column-containment + `math.isclose(abs_tol=1e-2)` + per-column sort, AND across `condition_tabs`, missing table = mismatch. Load the real per-table `condition_cols`/`ignore_orders` lists from `evaluation.parameters`. Add tests for the verdict-flipping cases the reviewer found (float tolerance 1e-2, column reorder, extra pred columns) and a real multi-table gold line.
2. **[high] B1 — verifier gold assets trip eg's agent-view leakage test (regression).**
   `_ensure_verifier_assets` writes `gold.duckdb` / eval spec / comparator into the view's `tests/`, and `test_translate_spider2_dbt.py`'s leakage scan (pattern `gold|expected|golden` over the materialized view) now flags them — 2 tests that pass on base `9c39af2` fail on this branch.
   **Fix:** make the agent-facing view leakage-clean while keeping the gold assets verifier-only. The view's `tests/` is uploaded only at verify time and removed during the agent run, so reconcile the leakage check to scope to the agent-visible portion (exclude the verifier-only `tests/` assets) — OR relocate/name the assets so the scan is clean — without weakening real agent-view leakage protection. Restore the 2 failing tests to green.

Keep the rider (resolver-driven `/app/<db_name>.duckdb`) and AC-3 reward.json shape intact.

## Stage Report: implementation (cycle 1)

- DONE: B2 (Critical) — re-derive `compare_duckdb` to FAITHFULLY reproduce Spider2's `eval_utils.duckdb_match` (column-containment, per-column sort, `math.isclose(1e-2)`, AND across condition_tabs, missing table = mismatch); add verdict-flipping tests
  Commit 61a1b9c. Ported `compare_pandas_table`/`vectors_match` 1:1 from xlang-ai/Spider2 `spider2-dbt/evaluation_suite/eval_utils.py` (fetched via `gh api`, decoded to /tmp): transpose to column-vectors, each gold column (restricted to `condition_cols[i]`) must match SOME pred column-vector, sorted per-column under `ignore_order`, numerics via `math.isclose(abs_tol=1e-2)`, `pd.isna` for NaN; predicted-fetch wrapped in try/except -> 0. Tests added: float-within-1e-2 (True) + beyond (False), column reorder (True), extra pred columns (True), plus a real multi-table gold line -> 0.0. 16/16 comparator tests pass.
- DONE: B2 (Critical) — fix eval-spec schema to Spider2's real shape (`evaluation.parameters` with `condition_cols: List[List[int]]`, `ignore_orders: List[bool]`); add a real multi-table gold-line test proving non-1.0 on mismatch
  Commit 61a1b9c. `EvalSpec` now holds per-table parallel lists; `load_eval_spec` drills into `evaluation.parameters` (matching Spider2 `evaluate.py:96-99` which calls `duckdb_match(result, **parameters)`), applies Spider2's None/empty defaults (`[[]]*n`, `[False]*n`), and validates list-length parity. Real-shaped multi-table line proven non-1.0 in `test_spider2_dbt_verify_multi_table_gold_line_mismatch`. Gold fixture + `build_gold.py` regenerated to the real shape.
- DONE: B1 (high) — make the agent-facing view leakage-clean while keeping gold verifier-only; restore the 2 failing `test_translate_spider2_dbt.py` tests; full `uv run pytest -k "spider2_dbt"` green
  Commit 22b9b6c. Scoped `_leakage_hits` to exclude the verify-time-only `tests/` subtree (Harbor `verifier.py:133-138` uploads `tests/` only inside `verify()`; `trial.py` `_verify_step` `reset_dirs(remove=[tests_dir,verifier_dir])` first — never agent-visible). Added a guard test planting `gold`-content in BOTH an agent-visible path (caught) and `tests/` (ignored) so the fix is scoping, not weakening. `uv run pytest -k "spider2_dbt" --ignore=tests/unit/test_task_identity_scoring.py` = 66 passed. Rider (resolver-driven `/app/<db_name>.duckdb`) + AC-3 reward.json shape untouched.

### Summary

Resolved both cycle-1 blocking defects against the authoritative xlang-ai/Spider2 source (fetched live, not the plan's prose). B2: `compare_duckdb` is now a faithful port of `eval_utils.duckdb_match` + `compare_pandas_table` (column-containment over transposed column-vectors, `math.isclose(abs_tol=1e-2)`, per-column sort, AND across tables), and `EvalSpec` models the real `evaluation.parameters` shape with per-table `List[List[int]]`/`List[bool]` lists — the prior row-tuple/exact-== + flat-dict design is gone. B1: the leakage scan is scoped to the agent-visible portion (everything outside the verify-time-only `tests/`), justified by the Harbor verify/agent dir lifecycle, with a guard test pinning it to scoping rather than disabling. Full gating suite 66 passed; acceptance `-k spider2_dbt_verify` 23 passed. No changes to the resolver rider or reward.json contract.

## Stage Report: validation (cycle 2)

- DONE: B2 — independently confirm the comparator faithfully reproduces Spider2's `eval_utils.duckdb_match` by checking against the ACTUAL xlang-ai/Spider2 source
  Fetched upstream `eval_utils.py` live via `gh api`; line-by-line confirmed column-containment, per-column sort, `math.isclose(abs_tol=1e-2)`, `pd.isna` NaN, AND across condition_tabs, predicted-fetch=mismatch. 10-case differential test (impl vs inline transcription of the oracle: float within/beyond 1e-2, column reorder, extra pred cols, NaN, missing table, multi-table) ALL AGREE. `load_eval_spec` parses real `playbook001`/`provider001` gold lines from upstream `gold/spider2_eval.jsonl` (`evaluation.parameters`, per-table List[List[int]]/List[bool]).
- DONE: B1 — confirm the agent-facing view is leakage-clean AND the fix did not weaken protection; confirm the Harbor lifecycle justification; the 2 previously-failing tests are green
  Verified Harbor lifecycle against installed package: `verifier.py:123 verify()` uploads `tests/` only inside verify(); `trial.py:570 _verify_step` `reset_dirs(remove=[verifier_dir,tests_dir])` wipes them empty pre-verify; agent gets only `workdir/`. Guard test catches agent-visible `gold` leak, ignores `tests/`. Mutation probe (blanket-True) makes the guard FAIL — confirms scoping not weakening. Production deny-globs unchanged. `test_translate_spider2_dbt.py` = 13 passed.
- DONE: Confirm no regression and the rider intact; AC-3 reward.json shape intact; give a gate verdict
  `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` = 66 passed. Independent end-to-end: emitted test.sh resolves `/app/not-spider2-slug.duckdb` (no hardcoded), and emitted verify.py writes `{"reward":1.0}`/`{"reward":0.0}`. Branch touches only spider2_dbt scope; 3 named pre-existing failures untouched. Verdict: PASSED.

### Summary

Re-review after cycle-1 fixes (61a1b9c, 22b9b6c) — independent verification only, no production code. Both blocking findings resolved against the authoritative live xlang-ai/Spider2 source: B2 — the comparator is a faithful port of `eval_utils.duckdb_match` (column-containment + 1e-2 tolerance + per-column sort + AND-across-tables), proven by a 10-case differential test against the upstream oracle and a real multi-table gold line; `load_eval_spec` reads the real `evaluation.parameters` schema. B1 — the leakage scoping is sound, not weakening: the Harbor verify-only-tests/ lifecycle is verified against the installed package, and a mutation probe confirms the guard test still fires on agent-visible leaks. Rider (`/app/<db_name>.duckdb`) and AC-3 reward.json shape intact; no regressions outside the known pre-existing set. Gate verdict: PASSED → done. Full report: docs/razorback-implementation/validation/spider2-dbt-duckdb-match-verifier.md

### Cycle 2 — validation gate REJECTED (2026-06-18, captain via Codex review)

Codex found a fail-open verifier hazard; captain chose fix-now. Confirmed live.
Routing back to `implementation`:

1. **[high] Fail-open: empty/malformed eval spec awards `{"reward": 1.0}`.**
   `load_eval_spec` (`eval_spec.py:79`) defaults `condition_tabs` to `[]` with no non-empty check and no `evaluation.func` validation; `compare_duckdb` (`duckdb_match.py:76`) returns `True` when the `condition_tabs` loop never runs. So a corrupted/truncated/schema-drifted `spider2_eval.jsonl` scores every prediction 1.0 — silently reporting broken scoring as success.
   **Fix:** fail closed in `load_eval_spec`/`EvalSpec` — require a non-empty `condition_tabs`, validate `evaluation.func == "duckdb_match"`, and raise (or otherwise force reward 0) on empty/missing. Add a negative regression test proving an empty/missing-`condition_tabs` spec raises or emits reward 0, NOT 1. Keep the faithful comparator (cycle-1 B2), the leakage scoping (cycle-1 B1), the rider, and AC-3 reward shape intact.

## Stage Report: implementation (cycle 2)

- DONE: Fail closed in `load_eval_spec`/`EvalSpec` (`eval_spec.py`): require a non-empty `condition_tabs`, and validate `evaluation.func == "duckdb_match"`. On an empty/missing `condition_tabs`, a missing/empty `evaluation`, or a wrong `func`, RAISE a clear error — never accept a zero-table spec that compare_duckdb would score as a match.
  Commit 869918d. `EvalSpec.__post_init__` now raises `ValueError` when `condition_tabs` is empty (the fail-open hazard: compare_duckdb's AND-loop returns True on zero tables). `load_eval_spec` raises on an empty/truncated file and on any `evaluation.func != "duckdb_match"`; a missing/empty `condition_tabs` falls through to the empty-spec guard and raises. TDD: red first (5 loader/construct negatives DID NOT RAISE), then green.
- DONE: Ensure the verifier path cannot emit `{"reward": 1.0}` for an empty/malformed gold spec; add a NEGATIVE regression test (empty file, missing `condition_tabs`, non-`duckdb_match` func each raise or emit reward 0 — NOT 1).
  Commit 869918d. `emit_reward` (`verify.py`) wraps `load_eval_spec`+`compare_duckdb` in try/except → reward 0 on any spec/compare error (no crash-into-pass, no silent 1.0). Negatives added: loader-level (empty file / missing condition_tabs / wrong func / missing evaluation → raise) and CLI-level over a MATCHING pred/gold pair (empty spec, wrong func → `{"reward": 0.0}`, proving fail-closed beats the would-be-1.0).
- DONE: Keep intact the faithful comparator (cycle-1 B2), the leakage scoping (cycle-1 B1), the rider, and the AC-3 reward.json shape; `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` green.
  Gating suite 73 passed (was 66; +7 new negatives), no edits to duckdb_match comparator, harbor_view leakage scoping, the resolver rider, or the reward.json contract. Focused fix touched only `eval_spec.py`, `verify.py`, and the two test files.

### Summary

Resolved the cycle-2 fail-open hazard with a focused fix. `EvalSpec` and `load_eval_spec` now fail closed: an empty/truncated `spider2_eval.jsonl`, a missing/empty `condition_tabs`, or a non-`duckdb_match` `evaluation.func` raise `ValueError` instead of yielding a zero-table spec that `compare_duckdb` silently scored 1.0; `emit_reward` catches any such failure and emits reward 0 rather than crashing or passing. Proven TDD-first by 7 negative regression tests (4 loader/construct raises + 2 CLI fail-closed-over-matching-DBs + 1 empty-EvalSpec raise) — all red before the fix, green after. The cycle-1 comparator/leakage fixes, the resolver rider, and the AC-3 reward shape are untouched; `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` = 73 passed.

## Stage Report: validation (cycle 3)

- DONE: Confirm the fail-closed fix is real and load-bearing: an empty file, a missing/empty `condition_tabs`, and a non-`duckdb_match` `evaluation.func` each RAISE in load_eval_spec/EvalSpec; and `emit_reward` (verify.py) surfaces any spec/compare failure as reward 0 (never crash-into-pass, never silent 1.0). Prove it beats the prior hazard: over a MATCHING pred/gold pair, an empty/zero-table spec now yields reward 0 (or raises), not 1.0. Confirm the negative tests fail if the guards are removed.
  Independent probe (clean branch HEAD 11c66f4): empty file / missing `condition_tabs` / empty `condition_tabs` / wrong func / `EvalSpec([])` all RAISE ValueError; over a MATCHING pred/gold pair an empty-spec and a wrong-func spec each emit `{"reward": 0.0}` (not 1.0), garbage non-JSON emits 0.0 without crashing, and a VALID matching spec still emits 1.0 (positive control — guards aren't blanket-failing). MUTATION TEST: stripping the `n==0`/empty-file/wrong-func guards made all 6 negative tests FAIL (CLI mutation reproduced the exact `{'reward': 1.0}` hazard) — guards are load-bearing; tree restored clean.
- DONE: Confirm the cycle-1 fixes are intact: the comparator still faithfully reproduces Spider2 duckdb_match (column-containment, math.isclose 1e-2, per-table condition_cols/ignore_orders), and the agent-view leakage scoping still excludes only the verify-only tests/ subtree (agent-visible leaks still caught).
  `git diff 0b64e92..869918d --name-only` touches ONLY eval_spec.py/verify.py + their 2 test files — duckdb_match.py (B2), harbor_view.py + test_translate_spider2_dbt.py (B1) untouched, so cycle-1 is intact by construction. Confirmed live anyway: comparator probe passes column-containment (reordered + extra pred col -> True), isclose 1e-2 within/beyond, per-column sort under ignore_order, ordered mismatch, missing pred table -> False. Leakage suite (`leakage_scan_still_fires` guard) 9 passed; translate suite leakage/planted/resolves 3 passed.
- DONE: Confirm no regression and rider/AC-3 intact: `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` (expect ~73 passed); emitted test.sh resolves /app/<db_name>.duckdb via ny's resolver; reward.json shape `{"reward": <float>}`. Give a gate verdict.
  Gating suite = 73 passed, 751 deselected. RIDER: materialized view with `task_slug=not-spider2-slug` -> emitted test.sh `--predicted-db /app/not-spider2-slug.duckdb`, no hardcoded `/app/spider2.duckdb`. AC-3 end-to-end via emit_reward against the materialized gold fixture: matching pred -> `{"reward": 1.0}`, mismatch -> `{"reward": 0.0}`, `set(payload)=={"reward"}` & float. Working tree clean (only known `uv.lock` churn, ignored). Verdict: PASSED.

### Summary

Cycle-3 re-validation of the fail-closed fix (commit 869918d) — independent verification only, no production code. The fix is real and load-bearing: empty file / missing-or-empty `condition_tabs` / non-`duckdb_match` func all RAISE, `emit_reward` surfaces any failure as reward 0 (no crash-into-pass, no silent 1.0), and over a MATCHING pred/gold pair the prior would-be-1.0 hazard now scores 0 — proven by a mutation test where removing the guards makes all 6 negatives fail (CLI mutation reproduced the literal `{'reward': 1.0}` hazard). A positive control confirms a valid matching spec still scores 1.0. Cycle-1 fixes (faithful column-containment comparator + 1e-2 tolerance; verify-only-tests/ leakage scoping) are untouched by the cycle-2 diff and re-confirmed live; rider (`/app/<db_name>.duckdb`) and AC-3 reward shape intact; gating suite 73 passed; only the known pre-existing unrelated failures + harness `uv.lock` churn remain. Gate verdict: PASSED -> done. Full report: docs/razorback-implementation/validation/spider2-dbt-duckdb-match-verifier.md

### Cycle 3 — validation gate REJECTED (2026-06-18, captain via Codex review)

Codex found the verifier ignores the eval spec's gold-DB basename; captain chose
fix-now. Confirmed live. Routing back to `implementation`:

1. **[high] Verifier hardcodes `gold.duckdb`, ignoring `evaluation.parameters.gold`.**
   `EvalSpec` has no `gold` field and `load_eval_spec` discards `parameters.gold`; `harbor_view.py:63` emits `--gold-db /tests/gold.duckdb` and `:125` copies a hardcoded `gold.duckdb`. Real Spider2 tasks name the gold DB per task (e.g. `playbook.duckdb`, `tpch.duckdb`), so the verifier would fail to find the gold or score against the wrong file — a benchmark-correctness defect. This is the gold-DB analog of the predicted-DB resolver ny added.
   **Fix:** add `gold` to `EvalSpec`, parse it from `evaluation.parameters.gold` (validate present for real wrapped specs), copy THAT exact file from the source `tests/gold/<gold>` into the view's verifier-only `tests/`, and emit `--gold-db /tests/<basename>`; fail closed if the named gold file is missing. Add a regression test with `parameters.gold` set to a NON-default basename (and no `gold.duckdb` present), proving the named file is used. Keep the cycle-1 comparator/leakage fixes, the cycle-2 fail-closed validation, the rider, and AC-3 reward shape intact.

## Stage Report: implementation (cycle 3)

- DONE: Add a `gold` field to `EvalSpec` and parse it from `evaluation.parameters.gold` in `load_eval_spec` (validate present/non-empty for real wrapped specs; keep the cycle-2 fail-closed behavior). The gold basename drives which file is scored — do not hardcode `gold.duckdb`.
  Commit a677c36. `EvalSpec.gold: str | None`; `load_eval_spec` reads `parameters.gold` and RAISES `ValueError` when a wrapped (`evaluation.func == duckdb_match`) line omits/empties it. Cycle-2 guards (empty file / wrong func / empty condition_tabs raise) unchanged. Confirms upstream `evaluate.py:96-99` resolves `parameters['gold']` per-task before calling `duckdb_match` (fetched live via `gh api`).
- DONE: Wire the parsed gold basename through materialization (`harbor_view.py`): copy the EXACT named file from the source `tests/gold/<basename>` into the view's verifier-only `tests/`, and emit `--gold-db /tests/<basename>` in test.sh (resolved from the spec, not hardcoded). Fail closed if the named gold file is missing.
  Commit a677c36. `_ensure_verifier_assets` calls `load_eval_spec(source tests/gold/spider2_eval.jsonl)`, copies `tests/gold/<spec.gold>` to `tests/<spec.gold>`, formats `_TEST_SH_TEMPLATE` with `gold_db=<basename>` -> `--gold-db /tests/<basename>`, and raises `FileNotFoundError` if the named gold is absent. Leakage-clean (no `gold/` segment) preserved.
- DONE: Add a regression test with `parameters.gold` set to a NON-default basename (e.g. `playbook.duckdb`) and NO `gold.duckdb` present, proving the named file is copied + scored. Keep intact: cycle-1 comparator faithfulness + leakage scoping, cycle-2 fail-closed validation, the rider (`/app/<db_name>.duckdb`), AC-3 reward shape. `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` green.
  5 new tests (red-first verified): non-default `playbook.duckdb` copied + `--gold-db /tests/playbook.duckdb` emitted + leakage-clean; named gold end-to-end scores 1.0; missing named gold fails closed; loader parses gold + raises on missing-gold-in-wrapped-spec. Gating suite = 78 passed (was 73). Cycle-1 (`duckdb_match.py`) untouched; cycle-2 guards untouched; rider + AC-3 reward shape unchanged.

### Summary

Resolved the cycle-3 gold-DB-basename defect (commit a677c36). The verifier no longer hardcodes `gold.duckdb`: `EvalSpec` carries a `gold` field, `load_eval_spec` parses `evaluation.parameters.gold` and fails closed when a real wrapped `duckdb_match` spec omits it, and `_ensure_verifier_assets` copies the EXACT spec-named gold file into the verifier-only `tests/` and emits `--gold-db /tests/<basename>` — raising if the named file is missing so a benchmark can never silently score against the wrong/missing gold. This is the gold-DB analog of the existing predicted-DB resolver rider. Proven TDD-first by 5 tests (red before, green after), including a `playbook.duckdb`/no-`gold.duckdb` regression that copies + scores the named file. Cycle-1 comparator faithfulness + leakage scoping, cycle-2 fail-closed validation, the resolver rider, and AC-3 reward shape are all intact; `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` = 78 passed.

## Stage Report: validation (cycle 4)

- DONE: Confirm the cycle-3 fix: `EvalSpec.gold` parsed from `evaluation.parameters.gold`; the materializer copies the EXACT named gold from source `tests/gold/<gold>` into the verifier-only tests/, emits `--gold-db /tests/<basename>` (not hardcoded gold.duckdb), and fails closed (FileNotFoundError) when the named gold is absent. Exercise it: a spec naming `playbook.duckdb` with NO `gold.duckdb` present copies + scores `playbook.duckdb`, leakage-clean; a wrapped spec missing `gold` raises.
  Verified live against branch HEAD bac0705 / fix commit a677c36. Standalone probe (no test infra) 11/11: wrapped-spec-missing-gold RAISES, empty-gold RAISES, gold parsed verbatim; `playbook.duckdb`+no-`gold.duckdb` materializes → only `playbook.duckdb` copied, test.sh `--gold-db /tests/playbook.duckdb`, no `/tests/gold.duckdb`, leakage-clean (no `gold/` segment); end-to-end `emit_reward` against named gold → match 1.0 / mismatch 0.0; missing named gold → FileNotFoundError. LOAD-BEARING: hardcoding `gold.duckdb` in harbor_view → 2 regression tests FAIL; disabling the loader missing-gold raise → 1 test FAILS. Tree restored clean.
- DONE: Confirm no regression to prior cycles: cycle-1 comparator faithfulness + leakage scoping; cycle-2 fail-closed validation. Confirm the rider (`/app/<db_name>.duckdb`) and AC-3 reward.json shape intact.
  Cycle-3 diff touches ONLY eval_spec.py + harbor_view.py + their 2 tests; duckdb_match.py (cycle-1, 61a1b9c) and verify.py (cycle-2/AC-3, 869918d) UNTOUCHED — intact by construction. Re-confirmed live: cycle-1 column-containment + isclose 1e-2 + per-column sort + missing-table mismatch (3/3); cycle-2 empty-file/wrong-func/empty-condition_tabs raises (3/3). Rider test `..._uses_resolved_db_name` → `/app/not-spider2-slug.duckdb` 1 passed; AC-3 `{"reward": <float>}` shape exercised end-to-end.
- DONE: `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` green (~78 passed); test_translate_spider2_dbt.py green. Give a gate verdict (PASSED -> done, or REJECTED -> implementation).
  Gating suite = 78 passed, 751 deselected. test_translate_spider2_dbt.py = 13 passed. Full suite (ignoring the broken scoring file) = 813 passed, 4 failed; the 4 failures ALSO fail on merge-base 9c39af2 (verified in a throwaway base worktree) — pre-existing/unrelated, NOT regressions. Verdict: PASSED.

### Summary

Cycle-3-fix re-validation (commit a677c36) — independent verification only, no production code. The gold-DB-basename fix is real and load-bearing: a non-default `playbook.duckdb` (with NO `gold.duckdb` present) is copied + scored + leakage-clean, the emitted test.sh carries `--gold-db /tests/playbook.duckdb`, a wrapped spec lacking `gold` raises, and a missing named gold fails closed — each proven by a standalone 11/11 probe AND a mutation test that flips the regression tests red. Cycles 1-2 (faithful column-containment comparator + 1e-2 tolerance; fail-closed empty/malformed-spec guards), the predicted-DB resolver rider, and the AC-3 `{"reward": <float>}` shape are untouched by the fix and re-confirmed live. Gating suite 78 passed; translate suite 13 passed; the only remaining full-suite failures are pre-existing on base (verified). Gate verdict: PASSED → done. Full report: docs/razorback-implementation/validation/spider2-dbt-duckdb-match-verifier.md

### Cycle 4 — validation gate REJECTED (2026-06-18, captain via Codex review)

4th adversarial Codex pass found a path-traversal hole in the (now spec-driven) gold basename; captain chose fix-now. Confirmed live. Routing back to `implementation`:

1. **[high] `evaluation.parameters.gold` used verbatim as a path component (trust boundary).**
   `gold` is external Spider2 input. `harbor_view.py:139-147` joins it as `source_gold / gold` (read) and `tests / gold` (copy2), and emits `--gold-db /tests/<gold>` in test.sh. `Path` preserves `..`/absolute components, so a spec value like `../dbt_project/foo.duckdb` passes the `is_file()` check against a file OUTSIDE `tests/gold/`, then `copy2` writes outside `view/tests/` and the emitted path leaves `/tests` — benchmark corruption / leakage from a malformed or hostile task.
   **Fix:** reject non-basename `gold` at the trust boundary (`load_eval_spec`): require `Path(g).name == g`, reject `.`/`..`/absolute/separators, before any path use. Add a `../`/absolute/separator regression test asserting fail-closed. Keep cycles 1-3 intact.

## Stage Report: implementation (cycle 4)

- DONE: Reject non-basename `gold` in `load_eval_spec` before it is used as a path component.
  Guard added in `eval_spec.py` immediately after the missing-gold check: when `gold` is a non-empty str, require `Path(g).name == g` and reject `.`/`..` → raises `ValueError` (fail-closed at the trust boundary). Bare-fixture `gold=None` still falls back to `gold.duckdb` (safe). The materializer and test.sh emitter are unchanged — the basename is sanitized upstream so both inherit the guarantee.
- DONE: Regression test for `../`/absolute/separator/`.`/`..` gold values.
  Parametrized `test_..._rejects_non_basename_gold` (5 cases: `../dbt_project/foo.duckdb`, `/etc/passwd`, `sub/dir/g.duckdb`, `..`, `.`) asserts `load_eval_spec` raises. Comparator suite 28 passed (was 23); harbor_view + verify_cli + translate suites 34 passed. Cycles 1-3 untouched.

### Summary

Resolved the cycle-4 path-traversal defect. `load_eval_spec` now fails closed on any `gold` that is not a bare basename (`..`, `.`, absolute, or containing separators), sanitizing the value at the trust boundary so both the materializer's `copy2` targets and the emitted `--gold-db /tests/<gold>` path stay inside the verifier-only gold area. One file + one parametrized test (5 cases); cycles 1-3 left intact. spider2_dbt suite green (62 across comparator/harbor_view/verify_cli/translate).

### Cycle 5 — validation gate REJECTED (2026-06-18, captain via Codex review)

5th adversarial Codex pass found the cycle-4 basename guard still admits shell metacharacters; captain chose fix-now. Confirmed live. Routing back to `implementation`:

1. **[high] Spec-controlled gold basename emitted UNQUOTED into test.sh → shell injection.**
   The cycle-4 guard rejects separators/`..`/absolute, but a POSIX-valid basename like `x.duckdb; echo '{"reward":1.0}' > /logs/verifier/reward.json #` has no separator, so `Path(g).name == g` passes; it is then interpolated unquoted into `--gold-db /tests/<gold>` in test.sh and executes as shell during verification. External task input → trust boundary.
   **Fix:** replace the basename guard in `load_eval_spec` with a conservative allowlist `^[A-Za-z0-9._-]+\.duckdb$` (subsumes the path checks AND blocks metacharacters/whitespace). Add `;`/space/`$()` regression cases. Keep cycles 1-4 intact.

## Stage Report: implementation (cycle 5)

- DONE: Replace the cycle-4 basename guard with a conservative allowlist at the trust boundary.
  `eval_spec.py`: `_SAFE_GOLD_RE = re.compile(r"[A-Za-z0-9._-]+\.duckdb")`; `load_eval_spec` rejects any non-`None` `gold` that fails `fullmatch`. Strictly tighter than the cycle-4 check — separators, `..`, absolute, whitespace, and shell metacharacters all fail closed at parse, so neither the materializer's `copy2` nor the unquoted test.sh `--gold-db` can be subverted. Bare-fixture `gold=None` → `gold.duckdb` fallback (safe) unchanged.
- DONE: Regression cases for shell-injection + wrong-suffix gold values.
  Parametrized `test_..._rejects_non_basename_gold` extended to 9 cases: the 4 path cases plus `x.duckdb; … #`, `g.duckdb $(id)`, `g .duckdb` (space), `g.sqlite` (wrong suffix). spider2_dbt suite (comparator/harbor_view/verify_cli/translate) = 66 passed. Cycles 1-4 untouched.

### Summary

Closed the cycle-5 shell-injection class definitively. The cycle-4 basename guard is replaced by a conservative `[A-Za-z0-9._-]+\.duckdb` allowlist in `load_eval_spec`, which subsumes the path-traversal checks and additionally rejects whitespace and shell metacharacters — so a spec-supplied gold name can neither escape `tests/gold/` nor inject into the unquoted `--gold-db` argument of the emitted test.sh. This is a terminal trust-boundary fix (allowlist, not edge-by-edge): one regex + the cycle-4 guard swap, 4 new regression cases (9 total). Cycles 1-4 intact; spider2_dbt suite 66 passed.

### Cycle 6 — validation gate REJECTED (2026-06-18, captain via Codex review)

6th adversarial Codex pass found the SYMMETRIC injection: the predicted-DB arg was still unquoted; captain chose fix-now. Confirmed live. Routing back to `implementation`:

1. **[high] Predicted-DB `db_name` emitted UNQUOTED into test.sh → shell injection (the other arg).**
   The cycle-5 gold allowlist only guarded `--gold-db`. `--predicted-db /app/{db_name}.duckdb` interpolated `db_name` — resolved from the task's `profiles.yml` `path:` (external input) by `resolve_spider2_db_name` — without quoting. A profile path with shell metacharacters executes during verification (overwrite reward.json / exfiltrate verifier assets). Preflight's Docker RUN already quoted this value; the verifier script did not.
   **Fix:** `shlex.quote` BOTH args at the emission point in `_ensure_verifier_assets` (terminal, source-agnostic). Keep the gold allowlist (it also guards traversal). Add a regression with a `profiles.yml` DuckDB path containing `$()`/whitespace asserting the emitted arg is quoted.

## Stage Report: implementation (cycle 6)

- DONE: `shlex.quote` both `--predicted-db` and `--gold-db` values where test.sh is emitted.
  `harbor_view.py`: `_TEST_SH_TEMPLATE` now takes fully-formed `{predicted_db}`/`{gold_db}` and `_ensure_verifier_assets` passes `shlex.quote(f"{_APP_ROOT}/{db_name}.duckdb")` and `shlex.quote(f"/tests/{gold_basename}")`. Safe names are unchanged by quoting (existing `/app/<slug>.duckdb` and `/tests/playbook.duckdb` assertions still pass); metacharacter names are single-quoted, so neither external-input arg can inject. Gold allowlist retained for traversal defense-in-depth.
- DONE: Regression for a `profiles.yml` path with shell metacharacters.
  `test_..._quotes_predicted_db_against_injection`: a `path: evil$(touch pwned).duckdb` profile materializes a test.sh whose `--predicted-db` is `shlex.quote`'d (raw `--predicted-db /app/evil$(touch pwned).duckdb` absent). Load-bearing: reverting the quote flips it red. spider2_dbt suite (comparator/harbor_view/verify_cli/translate) = 67 passed. Cycles 1-5 untouched.

### Summary

Closed the symmetric predicted-DB injection that the cycle-5 gold allowlist didn't cover. Both verifier arguments derived from external task input — `db_name` (from `profiles.yml` `path:`) and `gold_basename` (from the eval spec) — are now `shlex.quote`'d at the single test.sh emission point, so neither can be interpreted as shell syntax during verification regardless of source. The gold allowlist stays (it additionally blocks path-traversal, which quoting alone wouldn't). One-line template change + quoted format args + one load-bearing regression (profiles `$()` path). Cycles 1-5 intact; spider2_dbt suite 67 passed. The entire verifier shell boundary (both args, traversal + injection) is now sealed.

### Cycle 7 — validation gate REJECTED (2026-06-18, captain via Codex review)

7th adversarial Codex pass found a runtime-dependency gap (different class from the shell-boundary cycles); captain chose fix-now via the duckdb-only re-port. Confirmed live. Routing back to `implementation`:

1. **[high] Verifier imported undeclared/uninstalled `pandas` → crash-on-import before reward.json.**
   `duckdb_match.py` imported `pandas` at module level; `verify.py` (which imports it) runs INSIDE the task image via `python /tests/verify.py`. The image is guaranteed to have `duckdb` (the build-time preflight imports it), but NOT `pandas` — it is not in `pyproject.toml` and dbt-duckdb does not pull it in as a core dep. In an image without pandas the verifier dies during import before `emit_reward()` writes `/logs/verifier/reward.json`, turning valid runs into infra failures.
   **Fix (chosen direction: remove pandas):** re-port the column-containment compare onto duckdb's own `.fetchall()`/`.description` + stdlib (`sorted`, `math.isclose`), so the verifier depends ONLY on duckdb — the one library the image is already required to have. Keep all behavioral comparator tests green unchanged (the faithfulness net). Rejected alternative: keep pandas + add a `RUN pip install pandas` layer (network/pip/version assumptions, image bloat).

## Stage Report: implementation (cycle 7)

- DONE: Remove the `pandas` import from the verifier comparator; re-port on duckdb-native + stdlib.
  `duckdb_match.py` no longer imports pandas. `_fetch_columns` replaces `fetchdf().transpose().values.tolist()` with `cur.fetchall()` + `cur.description` (column count) → list of column-vectors of native Python scalars (NULL→None); a zero-row table still yields one empty vector per column. `_isna` (`x is None or NaN-float`) replaces `pd.isna`; `_vectors_match`, the Spider2 sort key, the `math.isclose(abs_tol=1e-2)` numeric path, condition_cols restriction, the column-containment loop, the per-table AND, and the missing-pred-table→False try/except are all preserved verbatim. Only duckdb (already required by the build-time preflight) is imported.
- DONE: Keep the behavioral comparator tests green unchanged (faithfulness net).
  All comparator tests pass unmodified: matching/mismatched DBs, all-tables-AND, missing predicted table→False, float within/beyond 1e-2 tolerance, column-containment reorder, extra-pred-column tolerated, condition_cols restrict + diff-detected, row-reorder match/mismatch under ignore_orders, multi-table gold-line mismatch. spider2_dbt suite (comparator/verify_cli/harbor_view/translate) = 67 passed. `grep import pandas` over `benchmarks/spider2_dbt/` → none (only a docstring `pd.isna` mention).

### Summary

Removed the verifier's `pandas` dependency by re-porting the comparator onto duckdb-native fetch + stdlib. `verify.py` now imports only `duckdb` — the single library the verify-time task image is already guaranteed to ship (proven by the build-time preflight that imports it) — so the emitted verifier can no longer crash-on-import in a dbt-duckdb image that lacks pandas (which is neither a project dep nor installed by any injected layer). The Spider2 `duckdb_match` semantics are preserved verbatim (column-containment, `isclose` 1e-2, Spider2 sort key, condition_cols, multi-table AND, missing-table→0, NA==NA); the full behavioral comparator suite stays green UNCHANGED as the faithfulness proof. Cycles 1-6 intact; spider2_dbt suite 67 passed. The verifier now has zero undeclared runtime deps.

### Cycle 8 — validation gate REJECTED (2026-06-18, captain via Codex review)

8th adversarial Codex pass found a SQL-injection via spec-supplied table names; captain chose fix-now. Confirmed live. Routing back to `implementation`:

1. **[high] `condition_tabs` table name interpolated raw into DuckDB SQL → reward rigging.**
   `_fetch_columns` built `SELECT * FROM "{table}"` by string interpolation, but `condition_tabs` comes from the external `spider2_eval.jsonl`. A value like `realt"; select 999 AS a; --` (existing-table prefix) breaks out of the identifier; DuckDB runs the multi-statement and `.fetchall()` returns the LAST statement's rows. So a hostile spec makes BOTH gold and pred fetches return identical injected rows → forced `reward: 1.0` over genuinely mismatched DBs. Verified live (`.venv/bin/python`: raw → `[(999,)]`; quote-doubled → CatalogException).
   **Fix:** add an identifier-quoting helper that doubles embedded `"` and use it in `_fetch_columns`; a bogus name then fails to resolve → the gold fetch raises → `emit_reward` scores 0 (fail-closed). Add a regression where `condition_tabs` carries `"; select ...; --` over mismatched DBs and assert it cannot score a match.

## Stage Report: implementation (cycle 8)

- DONE: Quote spec-supplied table identifiers in `_fetch_columns` (double embedded `"`).
  `duckdb_match.py`: new `_quote_ident(name)` returns `'"' + name.replace('"','""') + '"'`; `_fetch_columns` now does `SELECT * FROM {_quote_ident(table)}`. A breakout value becomes a single bogus identifier that doesn't resolve → CatalogException; `compare_duckdb`'s gold fetch is not try/excepted, so it raises → `emit_reward`'s wrapper scores 0 (fail-closed). Legit table names (incl. ones with special chars) are preserved.
- DONE: Regression proving `condition_tabs` cannot SQL-inject a match.
  `test_..._condition_tabs_cannot_sql_inject`: `condition_tabs=['realt"; select 999 AS a; --']` over real `realt` tables holding DIFFERENT data (genuine mismatch). Asserts `_compare` raises (cannot return a forced match). Load-bearing: reverting the quoting makes both fetches return `[(999,)]` → match → the `pytest.raises` fails. spider2_dbt suite (comparator/verify_cli/harbor_view/translate) = 68 passed. Cycles 1-7 untouched.

### Summary

Closed a benchmark-integrity SQL-injection: `condition_tabs` (external eval-spec input) was interpolated raw into the comparator's `SELECT * FROM "<table>"`, letting a hostile spec break out, run an injected statement, and force `reward: 1.0` over mismatched DBs. `_fetch_columns` now quotes the identifier with doubled `"`, so a breakout value becomes an unresolvable identifier and the fetch raises → reward 0 (fail-closed). One helper + one call-site change + one load-bearing regression (verified live that raw injects `[(999,)]` and the fix raises). This is the third trust-boundary arg sealed (gold name → cycle 5, predicted name → cycle 6, table names → now) — SQL this time, not shell. Cycles 1-7 intact; spider2_dbt suite 68 passed.

### Cycle 9 — validation gate REJECTED (2026-06-18, captain via Codex review)

9th adversarial Codex pass found a DECIMAL numeric-tolerance regression (introduced by the cycle-7 pandas removal) and a missing-gold fail-open; captain chose fix-both. Confirmed live. Routing back to `implementation`:

1. **[high] DECIMAL columns skip the `isclose(1e-2)` tolerance (regression from cycle 7).**
   DuckDB native `fetchall()` returns `decimal.Decimal` for DECIMAL/NUMERIC; `Decimal` is `numbers.Number` but NOT `numbers.Real`, so `_vectors_match`'s `isinstance(_, (int,float))` numeric branch skipped it → `!=` exact compare. Spider2's pandas `fetchdf()` had converted DECIMAL→float64, so a within-1e-2 DECIMAL match scored 0. Verified live: `_vectors_match([D('1.005')],[D('1.000')])` → False.
   **Fix:** normalize `Decimal`→`float` in `_fetch_columns` (one place; mirrors fetchdf's float64), keeping `_vectors_match`/sort-key identical to Spider2. DECIMAL within/beyond-tolerance regression tests.
2. **[medium] Missing `tests/gold/` silently kept the source test.sh → unscored task.**
   `_ensure_verifier_assets` early-returned when `tests/gold/` was absent, leaving the source `test.sh` (e.g. `fixture-002`'s `exit 0`) → a trivially-passing spider2-dbt task under dataset skew / resolver bug.
   **Fix:** fail closed (raise) when a spider2-dbt source lacks `tests/gold/spider2_eval.jsonl`; give `fixture-002` a real gold so the multi-instance/explain tests exercise two scored tasks; fail-closed materialization regression.

## Stage Report: implementation (cycle 9)

- DONE: DECIMAL tolerance — normalize Decimal→float at fetch.
  `duckdb_match.py`: new `_normalize(v)` (`float(v) if isinstance(v, Decimal) else v`) applied per cell in `_fetch_columns`; `_vectors_match` and the Spider2 sort key are unchanged (they now see floats exactly as Spider2's pandas path did). 2 regression tests: DECIMAL(10,3) within 1e-2 → match, beyond → mismatch. Load-bearing (without normalize, Decimal `!=` → the within-tol match would score False).
- DONE: Fail closed on missing gold + make fixture-002 scored.
  `harbor_view.py`: `_ensure_verifier_assets` now raises `FileNotFoundError` when `tests/gold/spider2_eval.jsonl` is absent (was a silent early-return). `tests/fixtures/.../spider2-fixture-002/tests/gold/` gains a minimal `gold.duckdb` (orders table) + `spider2_eval.jsonl`, so the multi-instance leakage test and the `rk run --explain` integration test now materialize TWO scored tasks. Test helpers `_write_source` (harbor_view) and the non-dbt `plain-001` case updated to ship gold (they assert on layers, not scoring). New `test_..._missing_gold_dir_fails_closed` asserts a no-gold source raises.
- DONE: full spider2_dbt suite green.
  `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` = 92 passed. Comparator faithfulness net (cycles 1/7), shell-boundary quoting (cycles 5/6), SQL-identifier quoting (cycle 8), and AC-3 reward shape all intact.

### Summary

Fixed a benchmark-correctness regression and a fail-open. (1) The cycle-7 pandas removal had left DECIMAL/NUMERIC values as `decimal.Decimal`, which bypassed `_vectors_match`'s `isclose(1e-2)` numeric branch (Decimal is Number, not Real) — so real dbt DECIMAL outputs within tolerance scored 0. Normalizing Decimal→float at fetch (one place) restores Spider2's float64 semantics with the comparator otherwise unchanged. (2) A spider2-dbt source missing `tests/gold/` silently kept its source `test.sh`, materializing an unscored / trivially-passing task; the materializer now fails closed, and `fixture-002` was given a real gold so the multi-instance + explain tests exercise two genuinely-scored tasks. Both proven by load-bearing regressions. Cycles 1-8 intact; spider2_dbt suite 92 passed.

### Cycle 10 — validation gate REJECTED (2026-06-18, captain via Codex review)

10th adversarial Codex pass found an unguarded symlink-write-through in the verifier-asset copies (same class as the Dockerfile/preflight/test.sh guards); captain chose fix-now. Confirmed live. Routing back to `implementation`:

1. **[high] `_ensure_verifier_assets` `copy2` calls follow symlinks → source corruption in link mode.**
   In `view_mode="link"` the generic materializer reflects allowed source files as symlinks. The 3 comparator-module copies + the gold-DB copy + the eval-spec copy used bare `shutil.copy2`, so a colliding source-provided name (`tests/verify.py`, `tests/eval_spec.py`, `tests/duckdb_match.py`, top-level `tests/spider2_eval.jsonl`, `tests/<gold>.duckdb`) is a symlink back to source → `copy2` follows it → overwrites the source task. spider2 translation binds to link mode, so this is on the live path. `test.sh`/Dockerfile/preflight already guarded this exact class; these copies didn't.
   **Fix:** unlink-before-copy helper (`if dst.is_symlink(): dst.unlink()`) for all 5 verifier-asset copies; link-mode regression seeding a source `tests/verify.py` proving the source stays unchanged.

## Stage Report: implementation (cycle 10)

- DONE: Guard all 5 verifier-asset copies against symlink write-through.
  `harbor_view.py`: new `_copy_into_view(src, dst)` unlinks a symlink `dst` before `shutil.copy2`; applied to the 3 module copies, the named gold-DB copy, and the eval-spec copy. The `test.sh` write keeps its existing guard. Same pattern as the Dockerfile/task.toml/preflight write-through fixes.
- DONE: Link-mode regression proving a colliding source file is not corrupted.
  `test_link_mode_verifier_assets_never_mutate_colliding_source_file`: seeds a source `tests/verify.py` with sentinel content, materializes in link mode, asserts the view owns a REAL (non-symlink) `verify.py` carrying the generated comparator CLI AND the source file is byte-for-byte unchanged. Load-bearing (without the guard, copy2 follows the symlink → view path stays a symlink + source content overwritten → both asserts fail). spider2_dbt suite = 93 passed.

### Summary

Closed the last instance of the link-mode symlink-write-through hazard: `_ensure_verifier_assets` copied the comparator modules, gold DB, and eval spec into `view/tests/` with bare `copy2`, so a source task shipping a colliding name (e.g. its own `tests/verify.py`) would have its source file overwritten during translate/materialize (spider2 binds to link mode). All 5 copies now route through `_copy_into_view`, which unlinks a symlink destination first — the same guard already applied to the Dockerfile, preflight script, and test.sh writes. Proven by a load-bearing link-mode regression. Cycles 1-9 intact; spider2_dbt suite 93 passed.

## Stage Report: validation (cycle 5)

- DONE: Rerun `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` and the entity's acceptance command from a clean checkout of the worktree branch; record ACTUAL output and map PASS/FAIL to each AC clause (do not trust prior reports)
  Clean branch HEAD 965f2ea: gating `-k spider2_dbt` = 93 passed, 751 deselected; acceptance `-k spider2_dbt_verify` = 49 passed, 795 deselected. AC-1/AC-2/AC-3 all PASS — confirmed by an 11-case standalone `compare_duckdb` probe (column-containment, isclose/DECIMAL 1e-2, per-column sort, condition_cols restrict, multi-table AND, missing-table→0, NA==NA) and an `emit_reward` probe (matching→`{"reward":1.0}`, mismatch/garbage/empty-spec/missing-pred→`{"reward":0.0}`, value is float, no crash-into-pass). Fail-closed + injection guards (8 unsafe-gold cases raise, SQL-injection condition_tabs raises) all confirmed live. duckdb-only: grep for pandas/numpy → none.
- DONE: Run `superpowers:requesting-code-review` against the worktree branch (base main); classify every finding as blocking or non-blocking
  Reviewer (range 9c39af2..965f2ea) independently fetched the upstream xlang-ai/Spider2 oracle and ran the suite: Critical 0, Important 0 — could construct NO external input that forces a false reward 1.0. 3 Minor (all non-blocking): `condition_cols` `[[]]`→`[[]]*n` forgiving-direction default; leakage-scoping rests on Harbor verify-only-tests/ lifecycle (suggest version-pin comment); dead `gold.duckdb` fallback for the unwrapped-fixture path. All clarity/robustness polish, no correctness defect.
- DONE: Write/refresh the validation report covering PASS/FAIL per AC with exact command+output, the code-review findings, and a gate decision
  `docs/razorback-implementation/validation/spider2-dbt-duckdb-match-verifier.md` refreshed for the cycles-1–10 HEAD. Full suite = 4 failed, 828 passed; the 4 failures reproduce on merge-base 9c39af2 (throwaway base worktree) and live in files untouched by this branch — pre-existing, NOT regressions. Gate: PASSED.

### Summary

Independent validation of the cycles-1–10 HEAD (965f2ea) — no production code written. All three ACs reproduce green from a clean branch checkout with recorded command output (gating 93 passed; acceptance `-k spider2_dbt_verify` 49 passed), and every dispatch-named focus area is confirmed by live behavioral probes rather than re-reading prior reports: faithful column-containment comparator (isclose 1e-2, per-column sort, condition_cols, multi-table AND, missing-table→0, NA==NA, DECIMAL tolerance), duckdb-only (no pandas/numpy import), fail-closed spec guards + gold-basename allowlist, sealed shell (shlex.quote both args) and SQL (identifier-quoted condition_tabs) injection boundaries, link-mode symlink-write-through guards on all 5 asset copies, and the `{"reward": <float>}` shape with no crash-into-pass. The 4 full-suite failures are pre-existing on the merge-base and outside this branch's scope (verified). The independent code review (which fetched the upstream Spider2 oracle) found zero blocking issues — 3 minor polish notes only. Gate verdict: PASSED → done. Full report: docs/razorback-implementation/validation/spider2-dbt-duckdb-match-verifier.md
