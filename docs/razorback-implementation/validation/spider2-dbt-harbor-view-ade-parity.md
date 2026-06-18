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
