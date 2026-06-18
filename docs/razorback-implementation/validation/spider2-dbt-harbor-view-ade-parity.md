# Validation: spider2-dbt — harbor_view dbt+DuckDB parity with ade-bench

**Entity:** `spider2-dbt-harbor-view-ade-parity`
**Branch:** `spacedock-ensign/spider2-dbt-harbor-view-ade-parity`
**Range reviewed:** `996d42b` (base / merge-base with main) .. `185c89d` (HEAD)
**Method:** independent reproduction from a fresh `git clone --single-branch` of the worktree branch into `/tmp/spider2-validation-clean` (no production code written).

**Gate verdict: REJECTED → back to `implementation`.**

The 3 ACs and the RIDER are functionally implemented and well-tested, but
running the acceptance command corrupts version-controlled fixture files in
the default production materialize path. This is a Critical, blocking defect
with a narrow root cause and a known fix pattern already present in the
generic materializer.

---

## Acceptance command

`uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py`
→ **28 passed, 751 deselected** (clean checkout, `EXIT 0`).

The `--ignore` is required: bare `uv run pytest -k spider2_dbt` trips a
collection error in `tests/unit/test_task_identity_scoring.py`
(`ModuleNotFoundError: No module named 'razorback.score.load'`). Confirmed
**pre-existing on base `996d42b`** (`git show 996d42b:tests/unit/test_task_identity_scoring.py`
line 5 imports `razorback.score.load`; `src/razorback/score/load.py` does not
exist at HEAD). **Not a regression.**

---

## AC results

### AC-1 — dbt-deps image layer when `packages.yml` present — PASS
`uv run pytest tests/unit/test_spider2_dbt_harbor_view.py -v` →
- `test_spider2_view_installs_dbt_packages_when_packages_yml_present` PASS:
  `RUN if [ -f /app/packages.yml ]; then cd /app && dbt deps; fi` present, before `CMD`.
- `test_spider2_view_omits_dbt_deps_layer_when_no_packages_yml` PASS:
  no `dbt deps` when manifest absent.

### AC-2 — preflight validates source DuckDB, fails closed — PASS
`uv run pytest tests/unit/test_spider2_dbt_workspace_preflight.py -v` → **8 passed.**
Reproduced every named failure mode with real DuckDB round-trips:
- missing → `reason: "duckdb file missing"`
- corrupt → `reason: "duckdb inspection failed"` (+ `error`)
- empty / no user tables → `reason: "no user tables present"`
- declared dbt `sources:` table missing → `reason: "required dbt source tables missing"`
- valid DuckDB → `status: "passed"`; CLI exits `2` on failure with JSON payload, `0` on pass.
Named error type: `Spider2WorkspacePreflightError` (preflight.py:13).

### AC-3 — view excludes gold/golden/expected/solution — PASS
- `test_spider2_view_excludes_gold_solution_expected_paths` PASS: planted
  `gold/`, `golden/`, `tests/expected/`, `expected/`, `solution/` files do not
  survive into the materialized view.
- `test_spider2_deny_globs_cover_required_families` PASS:
  `{gold/**, expected/**, golden/**} ⊆ SPIDER2_DBT_DENY_GLOBS` and
  `DEFAULT_SOLUTION_DENY_GLOBS ⊆ SPIDER2_DBT_DENY_GLOBS`. Both top-level
  (`gold/**`) and nested (`**/gold/**`) forms present (harbor_view.py:13-24).

### RIDER (mandatory) — build-context preflight ordering — PASS (functionally)
Independently exercised `materialize_spider2_harbor_task_view` (copy mode) and
inspected the on-disk build context:
- Layer order in the emitted Dockerfile: `COPY dbt_project/ /app/` (idx 4) →
  dbt-deps RUN (idx 7) → preflight `COPY`+`RUN` (idx 11) → `CMD` last. **COPY-to-`/app`
  precedes the preflight RUN.**
- **Build-context proof (not text inspection):** the COPY source `dbt_project/`
  resolves under `environment/` and contains a real `demo.duckdb`
  (`staged.rglob("*.duckdb")` non-empty). So `--workspace /app` cannot fail on a
  missing project/DB.
- Contract pinned for r5: `_APP_ROOT = "/app"` (single constant, harbor_view.py:29),
  preflight at `/tmp/razorback_spider2_preflight.py`, `--workspace /app`.
  Explicit and stable.

---

## Regression sweep

- `uv run pytest -k "ade_bench or translate" --ignore=tests/unit/test_task_identity_scoring.py`
  → **72 passed, 1 skipped, 706 deselected.** No regressions in ade_bench or
  non-spider2 translate/harbor behavior.
- Generic surfaces **byte-for-byte unchanged** vs base:
  `git diff 996d42b..HEAD --stat src/razorback/harbor_tasks/materialize.py src/razorback/harbor_tasks/leakage.py`
  → empty.

---

## Code review findings

Dispatched `superpowers:requesting-code-review` (general-purpose reviewer,
read-only on the worktree). Findings classified:

### BLOCKING (Critical)

**B1 — link-mode symlink write-through corrupts version-controlled fixtures.**
`src/razorback/benchmarks/spider2_dbt/harbor_view.py` — the three Dockerfile
helpers (`_ensure_spider2_build_context_layer` :112/131,
`_ensure_dbt_deps_image_layer` :143/153,
`_ensure_workspace_preflight_image_layer` :178/199) do
`dockerfile.read_text()` / `dockerfile.write_text(...)` on
`view_dir/"environment"/"Dockerfile"`. In the **default production path**,
`translate.py:376` maps `materialize_mode="bind"` → `view_mode="link"`, so that
Dockerfile is a **symlink back into the source task tree**; `write_text`
follows the link and overwrites the source file.

- Independently reproduced from a clean checkout: running
  `tests/unit/test_translate_spider2_dbt.py` (12 passed) OR
  `tests/integration/test_rk_run_spider2_dbt_explain.py` (1 passed) leaves
  `tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-00{1,2}/environment/Dockerfile`
  modified in git (the injected `COPY dbt_project/ /app/` + preflight block is
  written into the **committed source** Dockerfile, which is a 1-line
  `FROM python:3.12` at HEAD).
- Proven NEW in this entity: base `996d42b` `harbor_view.py` has no Dockerfile
  writes; swapping the base file in and re-running the same test leaves fixtures
  CLEAN (12 passed), while the HEAD file dirties them.
- Production severity (reviewer's independent escalation): beyond a dirty tree,
  this (a) rewrites the user's real source task Dockerfile on disk on every
  materialize, and (b) leaks the idempotency marker into the source — so a later
  `copy`-mode materialize sees the marker already present and **skips layer
  injection**, producing a view without the dbt-deps/preflight layers.
- The generic materializer already guards this exact hazard for `task.toml`
  (`materialize.py:140-146`: unlink the symlink, then write a real view-owned
  file). The new spider2 helpers do not replicate it.
- **Fix:** before each `write_text`, if the Dockerfile is a symlink, read its
  contents, `unlink()`, then write a real file — a small shared helper
  (`_materialize_real_file`) called at the top of each of the three helpers.
  Scope is narrow: only the `Dockerfile` is symlinked; the preflight-script
  `write_text` (:176) and the `shutil.copytree` (:123) land in real view-owned
  dirs and are safe (copytree is additionally guarded by `not staged.exists()`).

**Live evidence:** the worktree currently carries the corrupted fixtures
(`git status`: modified `spider2-fixture-00{1,2}/environment/Dockerfile`) from a
prior test run — left in place intentionally as the reproduction artifact for
the fix. (The `uv.lock` modification is unrelated: `uv sync`/`uv run` drops the
`exclude-newer` pin; benign, not this entity's work.)

### NON-BLOCKING (Important / Minor — fold into B1's fix or note for follow-up)

- **N1 (Important):** the six translate/integration tests pass the shared
  `FIXTURE_ROOT` as source under the default link mode and are the corruption
  vector; even after B1 they should adopt the isolated-`copytree` pattern that
  `test_spider2_dbt_harbor_view.py::_materialize_spider2` already uses. Add a CI
  guard that fails if the working tree is dirty after the suite — would have
  caught this automatically. Recommend a regression test: after a `link`-mode
  materialize, the **source** Dockerfile is unchanged and the **view** Dockerfile
  is a real file carrying the layers.
- **N2 (Minor):** `dbt deps` RUN (harbor_view.py:150) assumes `dbt` is on PATH at
  that build step; document the assumption or gate on `command -v dbt`.
- **N3 (Minor):** injected preflight RUN passes no `--db-name`, so it relies on
  `glob("*.duckdb")[0]` rather than the pinned `<db_name>.duckdb` — fine at build
  time (only the COPY'd source is present) but softer than the "pinned contract"
  comment claims.
- **N4 (Minor):** if `pyyaml` is absent in-container, dbt source-table
  enforcement silently degrades (preflight.py:108-109); worth a comment.

---

## Gate decision

**REJECTED → `implementation`.** Concrete required fix:

1. **(B1, blocking)** Guard the three Dockerfile-writing helpers in
   `harbor_view.py` against link-mode symlink write-through: replace a symlinked
   `environment/Dockerfile` with a real, view-owned file before patching
   (mirror `materialize.py:140-146`). Add a regression test proving a `link`-mode
   materialize leaves the source Dockerfile byte-for-byte unchanged and the view
   Dockerfile a real file with the injected layers.
2. Restore the corrupted committed fixtures
   (`spider2-fixture-00{1,2}/environment/Dockerfile` back to `FROM python:3.12`)
   and re-confirm `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py`
   leaves the working tree clean.
3. (Recommended, N1) make the translate/integration tests hermetic and add the
   dirty-tree CI guard.

Everything else — all 3 ACs, the RIDER build-context proof, the pinned `/app`
contract, unchanged generic materializer/leakage, no non-spider2 regressions —
is verified and sound. Re-run this validation after B1 lands.

---

## Re-validation — cycle 2 (2026-06-18)

**Range reviewed:** `996d42b` (base) .. `7f31b7b` (HEAD, includes cycle-1 fix).
**Method:** fresh `git clone --single-branch` of the worktree branch into
`/tmp/spider2-dbt-validate-c2` (since torn down); no production code written.
Pre-existing dirty `uv.lock` in the worktree is a harness artifact — ignored.

**Gate verdict: PASSED → `done`.**

### B1 fix is real and load-bearing

- **Fix present in all three helpers.** `git show 7f31b7b` adds the
  `if dockerfile.is_symlink(): dockerfile.unlink()` guard immediately before
  each `dockerfile.write_text(...)` in `_ensure_spider2_build_context_layer`
  (harbor_view.py:135), `_ensure_dbt_deps_image_layer` (:163), and
  `_ensure_workspace_preflight_image_layer` (:215). Byte-identical pattern to
  the reference at `materialize.py:144-145`. The fourth `write_text` (:188,
  `razorback_spider2_preflight.py`) correctly needs no guard — that file is
  freshly created and view-owned, never symlinked into source.
- **Fixtures restored / clean.** In the fresh clone `git status --short --
  tests/fixtures` is empty; `git diff 996d42b HEAD -- tests/fixtures` is empty;
  both `spider2-fixture-00{1,2}/environment/Dockerfile` are `FROM python:3.12`
  with zero `Razorback:` markers.
- **Regression test is load-bearing.** Stripped all three guards from a clean
  checkout (left `write_text` intact); `test_link_mode_injects_layers_but_never_mutates_source_dockerfile`
  then FAILS at `assert not view_dockerfile.is_symlink()` (the view Dockerfile
  is still a symlink, so the write would follow it). Restored the guard → test
  passes. Confirms the test guards the exact B1 hazard.
- **Independent end-to-end proof.** Exercised `materialize_spider2_harbor_task_view(..., view_mode="link")`
  directly (outside the test) against a source with `packages.yml` + a real
  `.duckdb`: the source `environment/Dockerfile` is byte-for-byte unchanged
  (sha unchanged), no `Razorback` marker leaked into source, and the view
  Dockerfile `is_file() and not is_symlink()` carrying all three injected
  layers (build-context COPY, `dbt deps` RUN, preflight COPY+RUN). The working
  tree stayed clean after the run.

### No regression to AC-1/AC-2/AC-3 + build-context rider

`uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py`
→ **29 passed, 751 deselected** (clean checkout, `EXIT 0`) — matches the
expected 29 (28 from cycle 1 + the new regression test). Generic
`materialize.py`/`leakage.py` byte-for-byte unchanged vs base
(`git diff --stat 996d42b HEAD` empty for both). Non-spider2 harbor behavior
unchanged: `test_ade_bench_harbor_view.py` + `test_ade_bench_workspace_preflight.py`
→ 13 passed.

### `/app` contract still pinned for r5

`_APP_ROOT = "/app"` (harbor_view.py:29); preflight script COPY'd to
`/tmp/razorback_spider2_preflight.py` and invoked `--workspace /app`; agent DB
lands at `/app/<db_name>.duckdb` via `COPY dbt_project/ /app/`. Stable invariant
for the r5 `duckdb_match` verifier.

### Code review (focused on the fix diff)

No blocking findings. The `is_file()` precheck (:109/:146/:184) follows
symlinks so link-mode Dockerfiles are still processed (reach the unlink guard);
`text = dockerfile.read_text()` reads the source content as the injection base
before the unlink, then the patched content is written to the fresh view-owned
file. Non-blocking nit (N2): the identical 4-line guard comment is duplicated
verbatim across the three helpers — a one-line `# see materialize.py:144` would
suffice. Not a correctness issue; not gating.

### Pre-existing, unrelated failures (NOT regressions)

`tests/unit/test_task_identity_scoring.py` (`ModuleNotFoundError: razorback.score.load`)
— confirmed present verbatim on base `996d42b`. While running the full unit
suite I also observed `test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch`
and `test_rk_research_new.py::test_rk_research_new_creates_scaffold_tree` failing;
both ALSO fail on a clean `996d42b` worktree and this entity touches only
`benchmarks/spider2_dbt/{harbor_view,preflight}.py` (the sole two source files
in `git diff --name-only 996d42b HEAD`), so neither can be a regression from
this work. Surfaced here for the captain's awareness, out of this entity's scope.

### Decision

All three ACs, the build-context rider, the pinned `/app` contract, and the
cycle-1 Critical defect B1 are verified from a clean checkout. The fix is real,
mirrors the established pattern, and its regression test is proven load-bearing.
**PASSED → `done`.**

---

## Cycle 3 — re-review of the cycle-2 Codex findings fix (2026-06-18)

Re-validated the cycle-3 fix commit `e60795e` from the worktree branch HEAD
`73fd832`. No production code written; verification by exercising behavior.

### Finding 1 (high) — db_name pinned into the injected preflight RUN; resolver importable + fails closed — VERIFIED FIXED

- **Importable for r5:** `from razorback.benchmarks.spider2_dbt.preflight import resolve_spider2_db_name`
  imports cleanly. r5 (`spider2-dbt-duckdb-match-verifier`) can reuse the same
  `/app/<db_name>.duckdb` resolution.
- **Resolver behavior (exercised directly):**
  - ambiguous multi-DB (`a.duckdb`, `b.duckdb`, no profiles) → raises
    `Spider2WorkspacePreflightError(reason="ambiguous duckdb file", candidates=['a.duckdb','b.duckdb'])`
  - single `demo.duckdb` → `"demo"`
  - `profiles.yml` `path: /some/dir/pinned.duckdb` overrides even a 2-DB dir → `"pinned"`
  - empty workspace → slug fallback `"myslug"`
- **Wired into the injected RUN (exercised via the materializer):** a real
  end-to-end materialize of a single-DB task emits
  `RUN python /tmp/razorback_spider2_preflight.py --task-id spider2-fixture-001 --workspace /app --db-name spider2-fixture-001`
  — `--db-name` is present and resolved against the view's dbt project dir
  (`harbor_view.py:216-220`), not glob-firsted.
- **Fail-closed is load-bearing at materialize time:** materializing a task whose
  `dbt_project/` carries two `*.duckdb` and no `profiles.yml` raises
  `Spider2WorkspacePreflightError(reason="ambiguous duckdb file")` — the build
  aborts rather than validating the wrong DB.

### Finding 2 (medium) — schema-aware source-table check — VERIFIED FIXED

Exercised `preflight_spider2_workspace` against a real DuckDB:

- dbt source expects `main.raw_orders`; DuckDB has `other.raw_orders` (wrong schema)
  → raises `reason="required dbt source tables missing"`, `missing_tables=['main.raw_orders']`.
  The wrong-schema table does NOT satisfy the source.
- After creating `main.raw_orders` → `status="passed"`, `missing_tables=[]`.

Confirmed in code: `_read_dbt_source_tables` returns `(schema, table)` with dbt
precedence (table.schema > source.schema > source.name; identifier > name), and
`_read_duckdb_tables` selects `table_schema, table_name`; the comparison at
`preflight.py:75` is a `(schema, table)` tuple set difference. Both sides
lowercased consistently.

### No regression

- `uv run pytest -k spider2_dbt --ignore=tests/unit/test_task_identity_scoring.py`
  → **38 passed, 751 deselected** (matches expected ~38).
- Generic `materialize.py` / `leakage.py`: `git diff 996d42b..HEAD` empty —
  byte-for-byte unchanged.
- ade_bench harbor_view + workspace_preflight regression → 13 passed.
- Cycle-1 unlink-then-write fix intact: 3 `if dockerfile.is_symlink():` guards in
  `harbor_view.py`; `test_link_mode_injects_layers_but_never_mutates_source_dockerfile`
  present and green.
- `/app` + `/app/<db_name>.duckdb` contract still pinned (`_APP_ROOT="/app"`,
  preflight `--workspace /app`, COPY `dbt_project/ /app/`).
- Pre-existing unrelated failures confirmed on base: `razorback.score.load` is
  MISSING in `996d42b` (the `test_task_identity_scoring` import error); the three
  named files (`test_task_identity_scoring`, `test_generate_matrix_specs`,
  `test_rk_research_new`) are untouched by this branch (empty diff vs base) — not
  regressions. Harness `uv.lock` ignored per dispatch. `git status` clean.

### Code review

Focused adversarial review of the fix diff (`e60795e`). No blocking findings.
Non-blocking observation: the resolver is invoked against the view's on-disk dbt
project dir as the stand-in for the container `/app` root — coherent with the
runtime contract. Schema precedence and consistent lowercasing make the set
difference correct.

### Gate

Both cycle-2 findings are genuinely fixed and load-bearing; the resolver is
importable for r5; no regression to AC-1/2/3, the build-context rider, or the
cycle-1 unlink fix. **PASSED → `done`.**
