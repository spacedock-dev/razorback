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
