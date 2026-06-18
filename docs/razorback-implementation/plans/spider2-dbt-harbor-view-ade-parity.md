# spider2-dbt — harbor_view dbt+DuckDB parity with ade-bench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Per CL's "Validating new mechanisms" rule, the riskiest contract here is **the image/workdir contract** (which container path holds the dbt project and the agent-produced `.duckdb`) because the not-yet-built verifier entity (r5, `spider2-dbt-duckdb-match-verifier`) depends on it. That contract is pinned in **Task 0** as a stable written invariant *before* any code, then each AC task is built against it. Within the code tasks the riskiest mechanism is **AC-2 preflight** (it actually opens a DuckDB file and fails closed), so it gets the smallest end-to-end exercise first: a real `duckdb.connect` round-trip in a unit test, not a mock.

**Goal.** `materialize_spider2_harbor_task_view` is currently minimal — it applies deny-globs and threads benchmark env, but skips the dbt+DuckDB harness work ade-bench already solved (`src/razorback/benchmarks/ade_bench/harbor_view.py`). spider2-dbt tasks are dbt projects on DuckDB, so the agent view must (1) install declared dbt packages at image-build time when a `packages.yml` is present, (2) validate the source `.duckdb` before agent runtime via a new `spider2_dbt/preflight.py`, and (3) keep excluding gold/solution/expected answer paths. This plan ports three ade-bench patterns into the spider2 view + a new preflight module, while leaving the generic materializer (`src/razorback/harbor_tasks/materialize.py`) and all non-spider2 behavior unchanged.

**Source of truth — the 3 ACs.** The AC text lives verbatim in the entity at `docs/razorback-implementation/spider2-dbt-harbor-view-ade-parity.md` (Acceptance criteria §). This plan does not re-derive it; the table below maps each AC to a concrete module + TDD checkpoint and cites the ade-bench reference each step ports from.

**Tech stack:** Python 3.12, `uv`, pytest 8, `duckdb` (already a dependency — `src/razorback/benchmarks/ade_bench/preflight.py:250` imports it; the existing `tests/unit/test_ade_bench_workspace_preflight.py:8` imports `duckdb` at top level), `PyYAML` (optional in preflight — imported lazily, see AC-2). No new external dependencies.

---

## AC → Task map

| AC | Task | Module(s) to touch | ade-bench reference ported | TDD checkpoint |
|----|------|--------------------|----------------------------|----------------|
| (contract) | **Task 0** | `docs/.../plans/spider2-dbt-harbor-view-ade-parity.md` (this doc, "Image/workdir contract" §) | n/a — written invariant the verifier r5 reads | n/a (doc) |
| AC-2 | **Task 1** | new `src/razorback/benchmarks/spider2_dbt/preflight.py` | `ade_bench/preflight.py` (`preflight_*_workspace`, `*WorkspacePreflightError`, `_read_duckdb_tables`, `main`, `preflight_script_text`) | `tests/unit/test_spider2_dbt_workspace_preflight.py` — passes on present/readable `.duckdb`, fails with named error on missing/corrupt |
| AC-1 | **Task 2** | `src/razorback/benchmarks/spider2_dbt/harbor_view.py` (`_ensure_dbt_deps_image_layer`, `_has_dbt_packages_manifest`, `_insert_before_final_cmd`) | `ade_bench/harbor_view.py:69-95,279-290` | `tests/unit/test_spider2_dbt_harbor_view.py` — dbt-deps marker + `dbt deps` line present when `packages.yml` present, absent when not |
| AC-2 | **Task 3** | `spider2_dbt/harbor_view.py` (`_ensure_workspace_preflight_image_layer`) | `ade_bench/harbor_view.py:116-153` | same test file — preflight script copied into view + COPY/RUN block before final CMD |
| AC-3 | **Task 4** | `spider2_dbt/harbor_view.py` (`SPIDER2_DBT_DENY_GLOBS` — already present; add a locking test) | `ade_bench/harbor_view.py:16-18` + `harbor_tasks/leakage.py:7-14` | same test file — `gold/**`, `expected/**`, `golden/**`, and shared `solution/**` deny-globs absent from materialized view |

---

## Image/workdir contract (Task 0 — the r5-facing invariant)

This section is the **stable contract** the verifier entity r5 (`spider2-dbt-duckdb-match-verifier`) and the run-wiring entity (`spider2-dbt-source-resolution-and-run-wiring`) depend on. Pin it first; do not let later code drift from it.

- **dbt project root inside the container: `/app`.** Mirrors ade-bench, whose preflight defaults `--workspace /app` (`ade_bench/harbor_view.py:140`) and whose dbt-deps RUN line is `cd /app && dbt deps` (`ade_bench/harbor_view.py:92`). The dbt project files (`dbt_project.yml`, `models/`, `profiles.yml`, and `packages.yml` when present) live under `/app` in the running container. The source-side directory that holds them is the task's `dbt_project/` dir (see fixture `tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001/dbt_project/`); the task's `environment/Dockerfile` is responsible for landing that content at `/app` (the fixture Dockerfile is `FROM python:3.12` only today — run-wiring r-source is out of scope here and owns the COPY).
- **packages.yml lookup locations (the spider2 divergence from ade-bench).** ade-bench's `_has_dbt_packages_manifest` checks `project/packages.yml` and `environment/project/packages.yml` (`ade_bench/harbor_view.py:69-73`) because ade-bench tasks nest the dbt project under `project/`. spider2-dbt tasks nest it under `dbt_project/` (fixture layout). So spider2's `_has_dbt_packages_manifest` MUST check `dbt_project/packages.yml` and `environment/dbt_project/packages.yml` — **this is the one structural difference to get right.** The dbt-deps RUN line keeps the `/app/packages.yml` guard (`RUN if [ -f /app/packages.yml ]; then cd /app && dbt deps; fi`) because at *runtime* the project root is `/app` regardless of the source-side dir name.
- **agent-produced `.duckdb` path: `/app/<db_name>.duckdb`.** ade-bench's preflight resolves `Path(workspace) / f"{db_name}.duckdb"` (`ade_bench/preflight.py:97-101`). For spider2 the same convention holds: the DuckDB file the agent's `dbt run` produces (and that r5's `duckdb_match` verifier reads) sits at `/app/<db_name>.duckdb`. The default `db_name` for spider2 is read from the dbt project's `profiles.yml`/`dbt_project.yml` target path, **or** defaults to the task slug when unresolved — Task 1 decides the exact resolution rule (see AC-2 below). r5 must read this same path; do not invent a second location.
- **preflight script lands at `/tmp/razorback_spider2_preflight.py` in the image.** Parity with ade-bench's `/tmp/razorback_ade_preflight.py` (`ade_bench/harbor_view.py:149`). The COPY+RUN pair is inserted before the final `CMD` so it runs at build time, failing the image build (not the agent run) on a bad source DuckDB.
- **What differs from ade-bench and is deliberately NOT ported:**
  - The **db-metadata-literal layer** (`_ensure_task_metadata_build_context_isolation`, `_replace_ade_metadata_copy_with_literals`, `db_file_id.txt`/`gdown` machinery — `ade_bench/harbor_view.py:156-232`) is ade-bench-only (it gdown-fetches a Drive-hosted DuckDB). spider2-dbt ships its DuckDB with the task / builds it via `dbt`, so this layer is **out of scope** (consistent with the entity's "Out of scope: building/pulling a real shared dbt-duckdb image").
  - The **static family contracts** (`_FAMILY_SENTINELS`, `_CONTRACTS` for airbnb/f1/quickbooks — `ade_bench/preflight.py:32-62`) are ade-bench task families. spider2-dbt has no fixed families, so the spider2 preflight validates **structural** properties (file present, openable, has ≥1 user table, optionally matches dbt `sources:` table names) rather than a hardcoded per-family table set. The dbt-source-metadata reader (`_read_dbt_source_tables`, `ade_bench/preflight.py:199-228`) ports over cleanly because it is family-agnostic.

---

## Task 0 — Pin the image/workdir contract (this doc)

- [ ] The "Image/workdir contract" § above is the deliverable. No code. The implementation worker reads it before Task 1 and keeps every later step consistent with it.

**Why first:** the contract is the riskiest cross-entity surface. r5 cannot be built against a moving target. Pinning it as prose before code is the "validate the riskiest contract first" discipline applied to a contract that is a *path convention* rather than a code path.

---

## Task 1 — AC-2: `spider2_dbt/preflight.py` validates the source DuckDB (riskiest mechanism, built first)

**Spec cite:** Entity AC-2 — "A preflight validates the source DuckDB before agent runtime … `spider2_dbt/preflight.py` passes on a present/readable `.duckdb` and fails with a named error on a missing/corrupt one."

**Module:** new `src/razorback/benchmarks/spider2_dbt/preflight.py`.

**Port from** `src/razorback/benchmarks/ade_bench/preflight.py`:
- `Spider2WorkspacePreflightError(RuntimeError)` carrying a `payload: dict` — direct port of `AdeWorkspacePreflightError` (`ade_bench/preflight.py:23-29`). This is the **named error** AC-2 requires.
- `preflight_script_text()` returning `Path(__file__).read_text()` — verbatim port (`ade_bench/preflight.py:77-78`). Used by the view to copy the script into the image.
- `_read_duckdb_tables(db_path)` — verbatim port (`ade_bench/preflight.py:249-263`): `duckdb.connect(..., read_only=True)`, query `information_schema.tables`, lowercase names. This is what proves the file is a *readable* DuckDB (a corrupt file raises here → caught → re-raised as the named error).
- `_read_dbt_source_tables` / `_iter_candidate_dbt_yaml_files` / `_as_dict` / `_as_list` / `_iter_dicts` — verbatim port (`ade_bench/preflight.py:199-247`); these are family-agnostic and let spider2 cross-check the DuckDB against the dbt `sources:` declared tables when present.
- `main(argv)` CLI — port of `ade_bench/preflight.py:266-293` with `PREFLIGHT_LOG_PREFIX = "RAZORBACK_SPIDER2_PREFLIGHT"`; exit 0 on pass, exit 2 + JSON-on-stderr on failure.

**What differs (the spider2 logic):** a single entrypoint
`preflight_spider2_workspace(*, task_id, workspace, db_name=None, db_path=None) -> dict[str, Any]`:
1. Resolve `db_path` = `db_path` arg, else `Path(workspace)/f"{db_name}.duckdb"` if `db_name` given, else discover the single `*.duckdb` under `workspace` (glob). Record the resolved path in the payload.
2. If the file is missing → `payload["status"]="failed"`, `payload["reason"]="duckdb file missing"`, raise `Spider2WorkspacePreflightError`.
3. `_read_duckdb_tables` — on any exception → `status="failed"`, `reason="duckdb inspection failed"`, `error=repr(exc)`, raise (corrupt-file case).
4. Compute required tables from dbt `sources:` metadata (`_read_dbt_source_tables`); if present and any are missing from the observed set → `status="failed"`, raise. If no source metadata, require only that ≥1 user table exists (empty DuckDB is a fail).
5. Otherwise `status="passed"`, return payload.
   No `_FAMILY_SENTINELS`, no `_CONTRACTS`, no forbidden-table cross-family check (those are ade-bench-only — see contract § "What differs").

**TDD checkpoint — write these failing first** in `tests/unit/test_spider2_dbt_workspace_preflight.py` (mirror `tests/unit/test_ade_bench_workspace_preflight.py`):
- [ ] `test_present_readable_duckdb_passes`: build a real DuckDB via `duckdb.connect` with ≥1 table → `preflight_spider2_workspace(...)["status"] == "passed"`.
- [ ] `test_missing_duckdb_fails_closed_with_named_error`: `pytest.raises(Spider2WorkspacePreflightError)`; assert `payload["reason"] == "duckdb file missing"` and the resolved `db_path` is in the payload.
- [ ] `test_corrupt_duckdb_fails_closed`: write garbage bytes to `<name>.duckdb` → raises `Spider2WorkspacePreflightError` with `reason == "duckdb inspection failed"`.
- [ ] `test_dbt_source_metadata_required_tables_enforced`: ship a `models/sources.yml` declaring tables, a DuckDB missing one → fails; matching DuckDB → passes (port of `test_dbt_source_metadata_overrides_static_family_contract`).
- [ ] `test_preflight_cli_exits_nonzero_and_emits_json_payload`: `subprocess.run([sys.executable, "-m", "razorback.benchmarks.spider2_dbt.preflight", ...])` on a missing DB → returncode 2, `RAZORBACK_SPIDER2_PREFLIGHT` on stderr, JSON payload parses (port of the ade-bench CLI test).

This is the **smallest end-to-end exercise of the riskiest contract**: a real DuckDB round-trip proving the file is readable, not a mocked one.

---

## Task 2 — AC-1: dbt-deps image layer when `packages.yml` present

**Spec cite:** Entity AC-1 — "Views with a `packages.yml` get a dbt-deps image layer … the dbt-deps marker + `dbt deps` line appear in the view's `environment/Dockerfile` when `packages.yml` is present, and are absent when it is not."

**Module:** `src/razorback/benchmarks/spider2_dbt/harbor_view.py`.

**Port from** `ade_bench/harbor_view.py`:
- `_DBT_DEPS_LAYER_MARKER` constant (`ade_bench/harbor_view.py:20-22`) → spider2 copy, e.g. `"# Razorback: install declared dbt packages before agent runtime."`.
- `_insert_before_final_cmd(text, block)` — verbatim port (`ade_bench/harbor_view.py:279-290`): inserts the block before the last `CMD ` line, or appends if no CMD.
- `_ensure_dbt_deps_image_layer(view_dir)` — port of `ade_bench/harbor_view.py:76-95`: no-op if no packages manifest; no-op if no `environment/Dockerfile`; no-op if marker already present (idempotent); else insert `RUN if [ -f /app/packages.yml ]; then cd /app && dbt deps; fi` before the final CMD.

**What differs:** `_has_dbt_packages_manifest(view_dir)` checks **`dbt_project/packages.yml`** and **`environment/dbt_project/packages.yml`** (NOT ade-bench's `project/…` — see contract §). Wire `_ensure_dbt_deps_image_layer(view)` into `materialize_spider2_harbor_task_view` after the `materialize_harbor_task_view(...)` call (parity with `ade_bench/harbor_view.py:62`).

**Note on `test-setup.sh`:** ade-bench also ports `_ensure_dbt_deps_test_setup_uses_preinstalled_packages` (verifier-time reuse). spider2's verifier (r5) is out of scope for this entity, and the spider2 fixture has `tests/test.sh` (not `tests/test-setup.sh`). Port the *image-build* dbt-deps layer (AC-1) now; the verifier-time reuse helper is deferred to r5 unless the fixture grows a `tests/test-setup.sh`. Record this as a deliberate scope line in the stage report.

**TDD checkpoint — write failing first** in `tests/unit/test_spider2_dbt_harbor_view.py` (mirror `tests/unit/test_ade_bench_harbor_view.py:66-119`):
- [ ] `test_spider2_view_installs_dbt_packages_when_packages_yml_present`: source with `dbt_project/packages.yml` + a Dockerfile with a `CMD` → materialized `environment/Dockerfile` contains the marker and `RUN if [ -f /app/packages.yml ]; then cd /app && dbt deps; fi`, and the `dbt deps` line precedes `CMD`.
- [ ] `test_spider2_view_omits_dbt_deps_layer_when_no_packages_yml`: source without any `packages.yml` → marker and `dbt deps` line absent from the materialized Dockerfile.

---

## Task 3 — AC-2 (image side): inject the preflight build layer into the view

**Spec cite:** Entity AC-2 (the view must run the preflight "before agent runtime"). Task 1 builds the preflight module; this task wires it into the image.

**Module:** `src/razorback/benchmarks/spider2_dbt/harbor_view.py`.

**Port from** `ade_bench/harbor_view.py:116-153` (`_ensure_workspace_preflight_image_layer`):
- `_SPIDER2_WORKSPACE_PREFLIGHT_MARKER` constant.
- Write `from razorback.benchmarks.spider2_dbt.preflight import preflight_script_text` (Task 1) and emit `environment/razorback_spider2_preflight.py` = `preflight_script_text()`.
- Insert before the final CMD:
  ```
  # Razorback: validate spider2-dbt source DuckDB before agent runtime.
  COPY razorback_spider2_preflight.py /tmp/razorback_spider2_preflight.py
  RUN python /tmp/razorback_spider2_preflight.py --task-id <slug> --workspace /app [--db-name <name>]
  ```
  using `shlex.quote` on slug/db-name (parity with `ade_bench/harbor_view.py:133-153`).

**What differs:** no `contract_for_task_id` gate (ade-bench skips tasks with no family contract — `ade_bench/harbor_view.py:117-119`). spider2 has no families, so the preflight layer is injected whenever the task is a dbt project (gate on `_has_dbt_packages_manifest` OR presence of `dbt_project/` — Task 3 picks the exact gate and documents it). `--db-name` is omitted when unresolved (preflight then discovers the single `*.duckdb`, per Task 1 step 1). Wire `_ensure_workspace_preflight_image_layer(view, task_slug=task_slug)` into `materialize_spider2_harbor_task_view` after Task 2's call.

**TDD checkpoint — write failing first** in `tests/unit/test_spider2_dbt_harbor_view.py` (mirror `test_ade_harbor_view_injects_workspace_preflight_before_cmd`, `ade_bench/harbor_view.py` test:121-171):
- [ ] `test_spider2_view_injects_workspace_preflight_before_cmd`: materialized view has `environment/razorback_spider2_preflight.py` (containing `def preflight_spider2_workspace`), the Dockerfile has the marker + the `COPY razorback_spider2_preflight.py …` line + `--task-id <slug>` + `--workspace /app`, and the preflight COPY precedes `CMD`.

---

## Task 4 — AC-3: lock the gold/solution/expected deny-globs

**Spec cite:** Entity AC-3 — "The agent view excludes gold/solution paths … `gold/**`, `expected/**`, `golden/**`, and the shared solution deny-globs are absent from the materialized view (extends the existing `SPIDER2_DBT_DENY_GLOBS`)."

**Module:** `src/razorback/benchmarks/spider2_dbt/harbor_view.py`.

**Current state:** `SPIDER2_DBT_DENY_GLOBS` (`spider2_dbt/harbor_view.py:10-21`) **already** extends `DEFAULT_SOLUTION_DENY_GLOBS` (`harbor_tasks/leakage.py:7-14`: `solution/**`, `solutions/**`, `**/solution.*`, `**/answer*`, `**/*answers*`, `tests/expected/**`) with `expected/**`, `**/expected/**`, `gold/**`, `**/gold/**`, `golden/**`, `**/golden/**`. AC-3 is therefore **mostly satisfied already** — the work is a **locking test** (so a future edit can't silently drop a glob) plus confirming the shared `solution/**` family is included.

**TDD checkpoint — write failing first** in `tests/unit/test_spider2_dbt_harbor_view.py` (a *materialized-view* assertion, not just a constant check — port the negative-leakage shape from `tests/unit/test_translate_spider2_dbt.py:144-185` `test_planted_forbidden_files_are_excluded_from_view`):
- [ ] `test_spider2_view_excludes_gold_solution_expected_paths`: copy a fixture source, plant `gold/answer.sql`, `golden/result.txt`, `tests/expected/expected.csv`, `expected/answer.txt`, and `solution/solve.sh`, materialize via `materialize_spider2_harbor_task_view`, and assert **none** of those files survive into the view. (Reuses the rider's `_leakage_hits`-style scan if helpful; the planted-file path assertions are the core.)
- [ ] (optional constant guard) `test_spider2_deny_globs_cover_required_families`: assert `{"gold/**","expected/**","golden/**"}` ⊆ `SPIDER2_DBT_DENY_GLOBS` and `DEFAULT_SOLUTION_DENY_GLOBS` ⊆ `SPIDER2_DBT_DENY_GLOBS` — catches an accidental shrink of the tuple.

---

## Fixtures

The validation acceptance command is `uv run pytest -k spider2_dbt` (entity Test plan §). The existing `tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001/` has `dbt_project/models/example.sql`, `environment/Dockerfile` (`FROM python:3.12`), `tests/`, `solution/`, `instruction.md`, `task.toml` — but **no `packages.yml` and no `.duckdb`**. Tasks 1-3 build their own sources inside `tmp_path` (the ade-bench tests do this — `tests/unit/test_ade_bench_harbor_view.py:66-103` writes a synthetic source per test), so no committed `packages.yml`/`.duckdb` fixture is strictly required. If a shared fixture is preferred, add `tests/fixtures/spider2_dbt/dbt_task_with_packages/` with a `dbt_project/packages.yml` and a small generated `.duckdb`; otherwise keep fixtures inline per-test (lower maintenance, matches ade-bench convention). The implementation worker picks one and notes it in the stage report.

---

## Build order & rationale

1. **Task 0 (contract)** — pin the path convention r5 reads, before any code can drift from it.
2. **Task 1 (AC-2 preflight module)** — the riskiest *mechanism* (real DuckDB open / fail-closed); smallest end-to-end exercise first.
3. **Task 2 (AC-1 dbt-deps layer)** — independent of Task 1; the `dbt_project/` vs `project/` divergence is the one structural risk.
4. **Task 3 (AC-2 image wiring)** — depends on Task 1's `preflight_script_text` + Task 2's insertion helper.
5. **Task 4 (AC-3 deny-glob lock)** — mostly a regression lock on existing behavior; last because lowest risk.

Each task's failing test is written **before** its implementation. Steps map 1:1 to AC items per the plan-stage "Good" bar. The generic materializer (`harbor_tasks/materialize.py`) and `harbor_tasks/leakage.py` are **not modified** — all spider2 behavior is added in `benchmarks/spider2_dbt/`.

## Out of scope (carried from the entity)

Source resolution / run wiring (`spider2-dbt-source-resolution-and-run-wiring`) and the `duckdb_match` verifier (`spider2-dbt-duckdb-match-verifier`, r5). Building/pulling a real shared dbt-duckdb image — manifests record the authored tag and leave the digest null when unresolved (per PKG-40). The ade-bench db-metadata-literal / gdown layer and the static family contracts are deliberately not ported (see contract § "What differs").
