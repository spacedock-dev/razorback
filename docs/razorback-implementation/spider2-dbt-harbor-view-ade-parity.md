---
id: nygs3pzdz4dx5hzwn6dsm0qa
title: spider2-dbt — harbor_view dbt+DuckDB parity with ade-bench
status: validation
source: ade_bench/harbor_view.py + ade_bench/preflight.py as reference; spider2-dbt is a dbt+DuckDB benchmark like ade-bench
started: 2026-06-18T08:49:13Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-spider2-dbt-harbor-view-ade-parity
issue:
pr:
mod-block: merge:pr-merge
---

## Problem

`materialize_spider2_harbor_task_view` is minimal — it applies
deny-globs but skips the dbt+DuckDB harness work ade-bench already
solved. spider2-dbt tasks are dbt projects on DuckDB, so the view must
install declared dbt packages at image-build time, validate the source
`.duckdb` before agent runtime, and reuse preinstalled packages at
verify time (no registry access mid-verify). This task ports the
ade-bench patterns (`_ensure_dbt_deps_image_layer`,
`_ensure_workspace_preflight_image_layer`,
`_ensure_dbt_deps_test_setup_uses_preinstalled_packages`) into the
spider2 view + a new `spider2_dbt/preflight.py`.

## Acceptance criteria

**AC-1 — Views with a `packages.yml` get a dbt-deps image layer.**
Verified by: a test (mirroring `test_ade_bench_harbor_view`) asserting
the dbt-deps marker + `dbt deps` line appear in the view's
`environment/Dockerfile` when `packages.yml` is present, and are absent
when it is not.

**AC-2 — A preflight validates the source DuckDB before agent runtime.**
Verified by: `tests/unit/test_spider2_dbt_workspace_preflight.py`
asserting `spider2_dbt/preflight.py` passes on a present/readable
`.duckdb` and fails with a named error on a missing/corrupt one.

**AC-3 — The agent view excludes gold/solution paths.**
Verified by: a test asserting `gold/**`, `expected/**`, `golden/**`,
and the shared solution deny-globs are absent from the materialized
view (extends the existing `SPIDER2_DBT_DENY_GLOBS`).

## Test plan

Unit tests mirroring `tests/unit/test_ade_bench_harbor_view.py` and
`test_ade_bench_workspace_preflight.py`, against a
`tests/fixtures/spider2_dbt/` dbt task with a `packages.yml` and a
small `.duckdb`. Validation acceptance command: `uv run pytest -k spider2_dbt`.

## Out of scope

Source resolution / run wiring (`spider2-dbt-source-resolution-and-run-wiring`)
and the `duckdb_match` verifier (`spider2-dbt-duckdb-match-verifier`).
Building/pulling a real shared dbt-duckdb image — manifests record the
authored tag and leave the digest null when unresolved (per PKG-40).

## Stage Report: plan

- DONE: Map the 3 ACs to concrete modules with a TDD checkpoint each
  AC↔task table in `plans/spider2-dbt-harbor-view-ade-parity.md`: AC-2→`spider2_dbt/preflight.py` (Task 1), AC-1→`_ensure_dbt_deps_image_layer` (Task 2), AC-2 image-side→`_ensure_workspace_preflight_image_layer` (Task 3), AC-3→`SPIDER2_DBT_DENY_GLOBS` lock (Task 4). Each task names the ade_bench reference ported and a failing-test-first checkpoint.
- DONE: Name exactly which ade_bench patterns port over and what differs for spider2
  Per-task "Port from"/"What differs" lines with verified cites: `ade_bench/preflight.py:23,77,97-101,199,249,266`; `ade_bench/harbor_view.py:20,62,69,76,92,116,140,149,279`. Key divergence pinned: spider2 uses `dbt_project/packages.yml` (not ade-bench `project/…`); no family contracts; db-metadata/gdown layer not ported.
- DONE: Define the image/workdir contract for spider2-dbt task views
  "Image/workdir contract" § (Task 0): dbt project root = `/app`, agent-produced DuckDB = `/app/<db_name>.duckdb`, preflight script at `/tmp/razorback_spider2_preflight.py`. Marked as the stable invariant r5 (`spider2-dbt-duckdb-match-verifier`) depends on.
- DONE: Write a standard separate plan doc with an AC-to-task map and cites to the ade_bench reference modules; keep generic materializer + non-spider2 behavior unchanged
  `docs/razorback-implementation/plans/spider2-dbt-harbor-view-ade-parity.md` written. Explicit "Build order & rationale" notes `harbor_tasks/materialize.py` and `harbor_tasks/leakage.py` are NOT modified; all spider2 behavior added under `benchmarks/spider2_dbt/`.

### Summary

Produced a separate plan doc (standard flow, per the FO dispatch) mapping AC-1/AC-2/AC-3 to four code tasks plus a Task-0 written contract. The riskiest surface — the `/app` + `/app/<db_name>.duckdb` image/workdir contract the r5 verifier depends on — is pinned first as prose; the riskiest mechanism (AC-2 preflight's real DuckDB open / fail-closed) is built first with a real `duckdb.connect` round-trip test. All ade_bench reference cites were verified against the source files. AC-3 is noted as mostly already satisfied (deny-globs present at `spider2_dbt/harbor_view.py:10-21`), so its task is a locking test. Key spider2 divergence flagged: `dbt_project/` layout vs ade-bench `project/`.

## Implementation summary

Modules added/touched (all under `src/razorback/benchmarks/spider2_dbt/`; generic `harbor_tasks/materialize.py` + `harbor_tasks/leakage.py` byte-for-byte unchanged):
- new `preflight.py` — `Spider2WorkspacePreflightError`, `preflight_spider2_workspace`, `preflight_script_text`, `main` CLI (`RAZORBACK_SPIDER2_PREFLIGHT`).
- `harbor_view.py` — added `_ensure_spider2_build_context_layer` (RIDER), `_ensure_dbt_deps_image_layer`, `_ensure_workspace_preflight_image_layer`, `_has_dbt_project`, `_has_dbt_packages_manifest`, `_insert_before_final_cmd`; wired into `materialize_spider2_harbor_task_view`.

Harbor surfaces touched: the spider2 view's `environment/Dockerfile` now gains (in order before the final `CMD`) a build-context COPY landing `dbt_project/` at `/app`, the dbt-deps RUN, and the preflight COPY+RUN.

## Stage Report: implementation

- DONE: Implement the approved plan TDD-first so all 3 ACs pass: new `spider2_dbt/preflight.py`; `_ensure_dbt_deps_image_layer` adding a dbt-deps layer when `dbt_project/packages.yml` is present; deny-glob regression lock. `uv run pytest` green.
  Red→green per task; `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` → 28 passed. Commits: preflight + tests, then harbor_view + tests.
- DONE: RIDER (Codex finding 2): build-time preflight `RUN ... --workspace /app` must NOT fail on a missing dbt project; this entity owns the COPY/context landing `dbt_project/` + source `.duckdb` at `/app` BEFORE the preflight RUN; verify at build-context level.
  `_ensure_spider2_build_context_layer` `shutil.copytree`s `dbt_project/` (incl. its `.duckdb`) into the `environment/` build context and emits `COPY dbt_project/ /app/` before the preflight RUN. `test_preflight_build_context_holds_duckdb_before_preflight_run` parses the COPY src from the Dockerfile and asserts a real `*.duckdb` exists under it in the build context — build-context proof, not text inspection.
- DONE: Pin the image/workdir contract (`/app` dbt root, agent DB at `/app/<db_name>.duckdb`, preflight at `/tmp/...`) as the stable r5-facing invariant; keep generic materializer + non-spider2 harbor behavior byte-for-byte unchanged.
  `_APP_ROOT="/app"` and preflight at `/tmp/razorback_spider2_preflight.py` constant-pinned in `harbor_view.py`. `materialize.py`/`leakage.py` untouched (git diff empty); ade_bench + translate regression suites 25 passed.
- SKIPPED: verifier-time `test-setup.sh` dbt-deps reuse helper (`_ensure_dbt_deps_test_setup_uses_preinstalled_packages`).
  Plan Task-2 note: r5 verifier out of scope; spider2 fixture has `tests/test.sh` not `tests/test-setup.sh`. Deferred to r5.

### Summary

Ported the three ade_bench harness patterns into a new `spider2_dbt/preflight.py` (real DuckDB round-trip, fails closed with a named error) and three Dockerfile-layer helpers in `harbor_view.py`, all TDD-first. The mandatory RIDER is satisfied structurally: the entity now stages `dbt_project/` (carrying the source `.duckdb`) into the `environment/` build context and COPYs it to `/app` before the preflight RUN, proven by a build-context-level test that resolves the COPY source and asserts a real `.duckdb` is present. The one structural divergence — `dbt_project/` (not ade-bench `project/`) for the packages-manifest and build-context lookups — is implemented and tested. Note: `uv run pytest -k spider2_dbt` collection trips a PRE-EXISTING unrelated broken module (`tests/unit/test_task_identity_scoring.py` imports the nonexistent `razorback.score.load`, present verbatim in base commit `996d42b`); excluding that module the spider2 acceptance is 28 passed and ade_bench/translate regression is 25 passed.

## Stage Report: validation

- DONE: Independently reproduce the 3 ACs from a clean worktree checkout (AC-2 preflight fail-closed on missing/corrupt/empty/no-sources + pass; AC-1 dbt-deps layer present iff `dbt_project/packages.yml`; AC-3 deny-glob lock). Run `uv run pytest -k spider2_dbt` (excluding pre-existing-broken `test_task_identity_scoring.py`).
  Fresh `git clone --single-branch` to /tmp; `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` → 28 passed. AC-2 8/8 with every named `reason`; AC-1/AC-3 7/7. Detail in validation/spider2-dbt-harbor-view-ade-parity.md.
- DONE: Scrutinize the mandatory RIDER (build-context COPY before preflight RUN; real `*.duckdb` under the COPY source at build-context level; `/app` + `/app/<db_name>.duckdb` contract pinned for r5).
  Exercised the materializer directly: COPY `dbt_project/`→`/app/` (idx 4) precedes preflight RUN (idx 11); COPY source resolves under `environment/` and holds a real `demo.duckdb`; `_APP_ROOT="/app"` + `/tmp/razorback_spider2_preflight.py` pinned. Build-context proof, not text.
- DONE: Run superpowers:requesting-code-review; confirm generic `materialize.py`/`leakage.py` + non-spider2 harbor behavior unchanged; confirm the only failing item is the pre-existing `razorback.score.load` collection error (base `996d42b`), not a regression. Give a gate verdict.
  Generic surfaces byte-for-byte unchanged (empty diff 996d42b..HEAD); ade_bench+translate regression 72 passed/1 skipped; broken module confirmed pre-existing on base. Code review found a Critical defect (B1). Verdict: REJECTED → implementation.
- FAILED: Gate PASSED.
  B1 (Critical, reproduced from clean checkout, NEW in this entity): the three Dockerfile-writing helpers in `harbor_view.py` write through the link-mode symlinked `environment/Dockerfile`, corrupting the version-controlled source fixtures (`spider2-fixture-00{1,2}/environment/Dockerfile`). Default production path (translate bind→link) rewrites the user's source Dockerfile and can leak the idempotency marker, suppressing layer injection on later runs. Fix: unlink-then-write guard mirroring `materialize.py:140-146`.

### Summary

Verified all 3 ACs and the mandatory RIDER from a clean clone of the worktree branch: `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` → 28 passed; the RIDER's COPY-before-preflight ordering and real-`.duckdb`-in-build-context were confirmed by independently exercising the materializer; the `/app` contract is pinned; generic `materialize.py`/`leakage.py` are unchanged and non-spider2 regression is 72 passed; the `razorback.score.load` collection error is pre-existing on base `996d42b`, not a regression. However the code review surfaced — and I independently reproduced — a Critical defect: in the default link materialize mode the new Dockerfile helpers write through the symlinked Dockerfile and corrupt the committed source fixtures (and in production rewrite the user's source task Dockerfile, risking marker-leak that skips layer injection). The generic materializer already guards this exact hazard for `task.toml`. **Gate: REJECTED → implementation** (fix B1 + restore corrupted fixtures + re-run for a clean tree). The corrupted fixtures are intentionally left dirty in the worktree as the reproduction artifact.

## Feedback Cycles

### Cycle 1 — validation gate REJECTED (2026-06-18)

Validation (our own reviewer, no Codex needed) found a Critical defect.
Routing back to `implementation`:

1. **[Critical] B1 — Dockerfile-writing helpers corrupt the source fixture under link mode.**
   The three new helpers in `harbor_view.py` (`_ensure_spider2_build_context_layer`,
   `_ensure_dbt_deps_image_layer`, `_ensure_workspace_preflight_image_layer`)
   call `dockerfile.write_text(...)` on `environment/Dockerfile`. In the default
   production path `translate.py:376` maps `bind`->`view_mode="link"`, so that
   Dockerfile is a SYMLINK back into the source tree — the write follows the link
   and mutates the version-controlled `spider2-fixture-00{1,2}/environment/Dockerfile`
   (and can leak the idempotency marker, suppressing layer injection on later runs).
   This is the same symlink-write-through class fixed for `task.toml` at
   `materialize.py:140-146`.
   **Fix:** apply the unlink-then-write pattern (unlink the symlink before
   `write_text`, so the view owns a real file) in ALL three helpers; restore the
   two corrupted fixture Dockerfiles to their committed content; add a test
   proving link mode never mutates the source Dockerfile (mirror
   `test_link_mode_symlinks_files_but_never_mutates_source_task_toml`). Keep AC-1/2/3
   + the build-context rider green.

## Stage Report: implementation (cycle 2)

- DONE: Apply the unlink-then-write pattern to ALL THREE Dockerfile-writing helpers in `harbor_view.py`
  Added `if dockerfile.is_symlink(): dockerfile.unlink()` before each `dockerfile.write_text(...)` in `_ensure_spider2_build_context_layer`, `_ensure_dbt_deps_image_layer`, `_ensure_workspace_preflight_image_layer`, mirroring `materialize.py:140-146`.
- DONE: Restore the two corrupted source fixture Dockerfiles and confirm a clean `git status`
  `git checkout` on `spider2-fixture-00{1,2}/environment/Dockerfile`; `git diff tests/fixtures/` is now empty.
- DONE: Add a regression test proving link mode never mutates the source Dockerfile; FAILS without guard, passes with it
  `test_link_mode_injects_layers_but_never_mutates_source_dockerfile`: confirmed FAILED on stashed (un-guarded) helper (`assert not is_symlink` -> True), PASSES with the fix.
- DONE: Keep AC-1/AC-2/AC-3 + the build-context rider green
  `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` -> 29 passed.

### Summary

Fixed the Critical symlink-write-through defect: under `view_mode="link"` the reflected `environment/Dockerfile` is a symlink into the source tree, so the three layer-injection helpers' `write_text` calls followed the link and corrupted the version-controlled fixtures. Guarded all three with the existing unlink-then-write pattern, restored the two dirty fixtures, and added a regression test (proven red-then-green). The preflight helper's `script_path.write_text` needed no guard since that file is view-owned, not symlinked. Pre-existing unrelated `uv.lock` change left unstaged.

## Stage Report: validation (cycle 2)

- DONE: Confirm the Critical defect B1 is fixed: from a clean checkout, exercise the materializer in link mode and assert the SOURCE fixture Dockerfiles are NOT mutated (git diff tests/fixtures empty) while the view Dockerfile is a real file carrying the injected layers. Confirm the regression test `test_link_mode_injects_layers_but_never_mutates_source_dockerfile` is load-bearing (fails without the unlink guard).
  Fresh clone of branch HEAD `7f31b7b`. Direct link-mode materialize: source Dockerfile sha unchanged + no marker leak; view Dockerfile `is_file() and not is_symlink()` with all 3 layers. `git diff tests/fixtures` empty (vs HEAD and vs base). Stripped all 3 guards → regression test FAILS at `assert not is_symlink()`; restored → passes. Guard mirrors `materialize.py:144-145`.
- DONE: Confirm no regression to AC-1/AC-2/AC-3 + the build-context rider: `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py` (expect 29 passed). Generic `materialize.py`/`leakage.py` and non-spider2 harbor behavior unchanged.
  29 passed, 751 deselected (EXIT 0). `materialize.py`/`leakage.py` byte-for-byte unchanged vs `996d42b`. ade_bench harbor_view + preflight → 13 passed.
- DONE: Confirm the `/app` + `/app/<db_name>.duckdb` image/workdir contract is still pinned and stable for r5 to consume. Give a gate verdict.
  `_APP_ROOT="/app"` (harbor_view.py:29); preflight at `/tmp/razorback_spider2_preflight.py --workspace /app`; agent DB at `/app/<db_name>.duckdb` via `COPY dbt_project/ /app/`. Pinned and stable.
- DONE: Gate verdict.
  PASSED → done. Report appended to validation/spider2-dbt-harbor-view-ade-parity.md (cycle-2 section).

### Summary

Independently re-verified the cycle-1 fix from a fresh clone of branch HEAD `7f31b7b` (no production code written). B1 is genuinely fixed: the unlink-then-write guard is present in all three Dockerfile-writing helpers (mirroring `materialize.py:144-145`), the two source fixtures are restored and clean (`git diff tests/fixtures` empty), and the regression test is proven load-bearing — stripping the three guards makes `test_link_mode_injects_layers_but_never_mutates_source_dockerfile` fail at `assert not is_symlink()`. A direct link-mode materialize leaves the source Dockerfile byte-for-byte unchanged (no marker leak) while the view Dockerfile is a real owned file carrying all three layers. Acceptance is `29 passed`; generic materializer/leakage unchanged; the `/app` contract is pinned for r5. The pre-existing `razorback.score.load` collection error (and two further base-failing tests in `test_generate_matrix_specs.py` / `test_rk_research_new.py`, both failing on clean `996d42b`) are unrelated and out of scope. **Gate: PASSED → done.**

### Cycle 2 — validation gate REJECTED (2026-06-18, captain via Codex review)

A Codex adversarial review of the implementation surfaced two valid preflight
robustness gaps; captain chose fix-both. Both confirmed live. Routing back to
`implementation`:

1. **[high] db_name not pinned — preflight glob-firsts; the `/app/<db_name>.duckdb` contract is prose-only.**
   `preflight.py` supports `--db-name`/`--db-path` (resolves `workspace/f"{db_name}.duckdb"`, else `sorted(glob("*.duckdb"))[0]`), but the injected RUN (`harbor_view.py:194-202`) passes only `--task-id` + `--workspace`, so the build-time guard always glob-firsts and can validate the wrong DB under multi/stale-DB drift.
   **Fix:** IMPLEMENT db_name resolution (parse the dbt `profiles.yml` `path:` / source `.duckdb` filename; slug fallback) and pass `--db-name` into the injected preflight RUN; OR fail closed when >1 `*.duckdb` and none specified. Expose the resolver as an importable function so the **r5 verifier can reuse it** (this IS the shared contract r5 consumes — don't leave it prose-only). Add a test: a multi-DB workspace pins the right DB (or fails closed), and the injected RUN carries `--db-name`.
2. **[medium] Source-table check ignores schema.**
   The dbt `sources:` parser records bare table names and the DuckDB query selects `DISTINCT table_name` (`preflight.py:161-163`), so `other.raw_orders` satisfies a source expecting `main.raw_orders`.
   **Fix:** track required + observed relations as `(schema, table)` pairs (honor dbt source/table `schema` fields; compare against `information_schema.tables.table_schema` + `table_name`). Add a test: a table in the wrong schema does NOT satisfy the source.

Keep AC-1/2/3, the build-context rider, and the cycle-1 unlink-then-write fix green.
