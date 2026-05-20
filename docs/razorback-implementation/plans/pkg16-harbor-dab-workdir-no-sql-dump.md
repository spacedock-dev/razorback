# PKG-16 — harbor-DAB plugin removes SQL dump from agent workdir (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop exposing server-ingested dump files (`*.sql`, BSON dump folders) to the agent's harbor workdir for every DAB dataset, so the agent must query the live postgres/mongo service instead of grepping the dump. Preserve file-backed sqlite/duckdb live-DB files (those ARE the live DB) and preserve the postgres/mongo init bind-mount path.

**Architecture:** The leak point is `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py:_materialize_task_dir` (lines 202–210): it copies the entire `query_dataset/` subtree into `steps/main/workdir/query_dataset/`. The compose generator then bind-mounts the SQL dump from THAT workdir-relative path into postgres's init.d. The fix has two halves: (a) classify each `query_dataset/` entry against `db_config.yaml` to identify server-ingested dumps (postgres `sql_file`, mongo `dump_folder`) vs file-backed live DBs (sqlite `db_path`, duckdb `db_path`), copy only the file-backed engines into the workdir, and stage the dumps separately under `<task_dir>/environment/_initdb/`; (b) re-point compose bind-mount sources from `../steps/main/workdir/{sql_file}` to `./_initdb/{name}`. Result: the agent's workdir contains metadata + sqlite/duckdb live DBs only; the dumps still bind-mount into postgres/mongo containers but from a path the agent container cannot see.

**Tech Stack:** Python 3.13, pytest, PyYAML, harbor task config, claude-cli (opus-4.7) for the AC-3 smoke.

## AC ↔ task map

| AC   | Tasks                              |
| ---- | ---------------------------------- |
| AC-1 | T2 (fixture+RED), T3 (impl GREEN)  |
| AC-2 | T3 (compose bind-mount re-point), T4 (PKG-13 regression guard)  |
| AC-3 | T8 (opus-4.7 bookreview re-smoke)  |
| AC-4 | T5 (12-dataset catalog walk test)  |
| AC-5 | T7 (full `uv run pytest` sweep)    |
| AC-6 | T9 (reconciliation-baseline update) |

## Spec §-cites

- PKG-16 entity: `docs/razorback-implementation/pkg16-harbor-dab-workdir-no-sql-dump.md` (all six ACs)
- PKG-13 entity: `docs/razorback-implementation/_archive/...` — DONE; the prepare.py compose-loading + reachability-gate changes from PKG-13 (T1, T5, T7, T8, T9) must keep passing.
- PKG-14 entity: `docs/razorback-implementation/pkg14-harbor-dab-lfs-bindmount-reuse.md` — BACKLOG; this plan deliberately does NOT depend on PKG-14's bind-mount-from-data_root refactor. PKG-16 stages dumps under `<task_dir>/environment/_initdb/` so the change is local to the existing copy-into-task-dir mechanism. If/when PKG-14 lands, the staging dir collapses into the data_root bind-mount and PKG-16's filter still applies to whatever copy step remains for the agent workdir.
- Reconciliation-baseline doc: `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`.

## File structure

| File | Responsibility | Action |
| ---- | -------------- | ------ |
| `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` | Materialize task-dir; classify dataset files; stage dumps under `environment/_initdb/`; copy non-dump files into workdir | Modify (lines 39–46 constants, lines 202–210 workdir copy) |
| `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py` | Generate compose; bind-mount sources for dab-postgres / dab-mongo init | Modify (lines 56–73 source path for `sql_file` / `dump_folder`) |
| `packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py` | AC-1 + AC-4 unit tests — workdir absence of `*.sql`/`*.bson`/BSON-dump folders across synthetic per-dataset fixtures | Create |
| `packages/razorback-plugin-dab/tests/unit/test_prepare_per_query.py` | Existing PKG-13/AC-3 task-dir layout tests | Modify — update `test_compose_bind_mount_sources_resolve_to_real_files` so the postgres bind-mount source resolves under `environment/_initdb/`, not `steps/main/workdir/query_dataset/`. Add a new assertion that `steps/main/workdir/query_dataset/{sql_file}` does NOT exist. |
| `examples/specs/pkg16-bookreview-claude-harbor-dab-n3-opus47.yaml` | AC-3 re-smoke spec (model = opus-4.7) | Create |
| `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md` | AC-6 — annotate PKG-13 9/9 entry as INFLATED and add PKG-16 honest re-smoke row | Modify (during validation stage; out of this plan's scope to execute; AC-6 spec text included for the validator) |

## Risk-first ordering rationale

The riskiest contract is **the compose bind-mount source path**. If postgres/mongo can no longer find the dump after the workdir change, every downstream test fails AND PKG-13's reachability-gate tests collapse. So the FIRST mechanism-validation task (T1) is a paper-only inspection of compose.py + prepare.py that confirms the staging directory choice and the resolve-relative-to behavior. Then T2 writes a failing test that asserts BOTH halves: (a) workdir does NOT contain the dump, (b) compose bind-mount source for postgres resolves to an existing file outside the workdir. T3 makes that test pass. T4 re-runs the existing PKG-13 prepare suite to confirm no regression. T5 expands the absence test to all 12 datasets via a synthetic-fixture loop (AC-4). T6 is the live `docker compose config` regression — already covered by PKG-13's integration test, just re-run. T7 is the full `uv run pytest` sweep (AC-5). T8 is the opus-4.7 re-smoke (AC-3). T9 is the doc update (AC-6).

Comprehensive runs come AFTER the smallest end-to-end mechanism check passes. The 12-dataset loop (T5) and `docker compose config` (T6) come AFTER the bookreview unit test (T2/T3) confirms the staging mechanism works; the live opus-4.7 smoke (T8) comes AFTER both unit and `docker compose config` confirm the contract holds.

---

## Task 1 — Mechanism review (no code)

**Files:** none modified.

- [ ] **Step 1: Inspect the current bind-mount source resolution.**

Read `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py:56-73` and confirm: for `db_type == "postgres"` with `sql_file: query_dataset/books_info.sql`, the emitted volume entry is `../steps/main/workdir/query_dataset/books_info.sql:/docker-entrypoint-initdb.d/books_info.sql:ro`. The base path for resolution is the compose file's parent: `<task_dir>/environment/`. So `../steps/main/workdir/...` resolves to `<task_dir>/steps/main/workdir/...`. The dump must move out of `steps/main/workdir/` AND the compose source must be re-pointed to the new location.

- [ ] **Step 2: Choose the staging directory.**

Stage dumps at `<task_dir>/environment/_initdb/{basename}`. Rationale: (a) compose file is at `<task_dir>/environment/docker-compose.yaml`, so `./_initdb/{name}` resolves cleanly relative to it; (b) `environment/` is the harbor "task-author override" directory — the agent's runtime container never bind-mounts it as a writable path; (c) leading underscore conveys "plugin-private staging" (matches existing `_upstream_validate.py` convention from `_install_validator`); (d) keeps the per-task-dir self-contained — no dependency on PKG-14's data_root bind-mount.

- [ ] **Step 3: Identify the classification key.**

In `db_config.yaml`, server-ingested dumps are referenced by:
- `db_clients.<name>.sql_file` (postgres) → file relative to dataset_dir, basename copied into `environment/_initdb/`.
- `db_clients.<name>.dump_folder` (mongo) → folder relative to dataset_dir, basename copied into `environment/_initdb/`.

File-backed live engines are referenced by:
- `db_clients.<name>.db_path` (sqlite, duckdb) → file relative to dataset_dir. These STAY in `steps/main/workdir/{path}` because the agent must read them as the live DB.

The workdir filter is: copy `query_dataset/` contents EXCEPT entries whose path matches any `sql_file` or `dump_folder` basename/folder-name declared in `db_config.yaml`.

- [ ] **Step 4: Commit a note (no code change).**

No commit. Step 1–3 are paper-only mechanism review. Proceed to Task 2.

---

## Task 2 — RED: workdir absence test (bookreview synthetic)

**Files:**
- Create: `packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py`

- [ ] **Step 1: Write the failing test.**

Create `packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py`:

```python
# ABOUTME: PKG-16 AC-1 + AC-4 — agent workdir excludes server-ingested dump files.
# ABOUTME: Tests bookreview (postgres+sqlite) and a 12-dataset synthetic catalog walk.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab import datasets as catalog
from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


def _build_bookreview(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    qdir.mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump({
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": "query_dataset/books_info.sql",
            },
            "review_database": {
                "db_type": "sqlite",
                "db_path": "query_dataset/review_query.db",
            },
        }
    }))
    (qdir / "db_description.txt").write_text("Bookreview schema.")
    qd = qdir / "query_dataset"
    qd.mkdir()
    (qd / "books_info.sql").write_text(
        "CREATE TABLE books (id INT);\nINSERT INTO books VALUES (1);\n" * 50
    )
    (qd / "review_query.db").write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "How many books?"}')
    return data_root


def test_postgres_sql_dump_absent_from_workdir(tmp_path: Path):
    data_root = _build_bookreview(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    assert not (workdir / "query_dataset" / "books_info.sql").exists(), (
        "AC-1: SQL dump must not appear in the agent workdir"
    )
    leaked_sql = list(workdir.rglob("*.sql"))
    assert leaked_sql == [], f"AC-1: stray .sql under workdir: {leaked_sql}"


def test_sqlite_live_db_still_in_workdir(tmp_path: Path):
    data_root = _build_bookreview(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    assert (workdir / "query_dataset" / "review_query.db").exists(), (
        "sqlite is a file-backed live DB — must remain in workdir for the agent"
    )


def test_postgres_dump_staged_under_environment_initdb(tmp_path: Path):
    data_root = _build_bookreview(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
    )
    task_dir = manifest[0]["task_dir"]
    assert (task_dir / "environment" / "_initdb" / "books_info.sql").exists(), (
        "dump must be staged outside the agent workdir but still inside the task dir"
    )


def test_compose_bind_mount_resolves_to_staged_dump(tmp_path: Path):
    data_root = _build_bookreview(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=tmp_path / "tasks"
    )
    compose_path = manifest[0]["task_dir"] / "environment" / "docker-compose.yaml"
    compose = yaml.safe_load(compose_path.read_text())
    pg_vols = compose["services"]["dab-postgres"]["volumes"]
    assert pg_vols, "expected at least one postgres init bind-mount"
    for entry in pg_vols:
        src = entry.split(":", 1)[0]
        resolved = (compose_path.parent / src).resolve()
        assert resolved.exists(), f"bind-mount source missing: {resolved}"
        # AC-1 + AC-2: source must NOT be the agent workdir copy.
        assert "steps/main/workdir" not in str(resolved), (
            f"AC-1: postgres bind-mount source still resolves into agent workdir: {resolved}"
        )
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py -v`
Expected: `test_postgres_sql_dump_absent_from_workdir` FAILS (the `.sql` IS in the workdir today); `test_postgres_dump_staged_under_environment_initdb` FAILS (the staging dir does not exist yet); `test_compose_bind_mount_resolves_to_staged_dump` FAILS (the bind-mount source resolves under `steps/main/workdir`); `test_sqlite_live_db_still_in_workdir` PASSES (sqlite is already kept).

- [ ] **Step 3: Commit (RED).**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py
git commit -m "test(pkg16): RED — agent workdir must exclude server-ingested SQL dump"
```

---

## Task 3 — GREEN: classify dump files; stage under environment/_initdb/; re-point compose

**Files:**
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py:39-46` (the `_DATASET_SAFE` constant is replaced by a classifier helper) and `prepare.py:202-210` (the workdir copy loop).
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py:56-73` (the `sql_file` / `dump_folder` source path).

- [ ] **Step 1: Add the dump-classifier helper in prepare.py.**

Before `_materialize_task_dir`, add:

```python
def _dump_paths(db_config: dict) -> set[str]:
    """Return the set of dataset-relative paths that postgres or mongo
    ingest at compose-up time. These are the files the agent must NOT
    see in its workdir — the live-DB contract requires that the agent
    query the postgres/mongo service instead of reading the dump.

    File-backed engines (sqlite, duckdb) are NOT included here — those
    files ARE the live DB and must remain reachable from the workdir.
    """
    paths: set[str] = set()
    for cfg in (db_config or {}).get("db_clients", {}).values():
        if not isinstance(cfg, dict):
            continue
        for key in ("sql_file", "dump_folder"):
            value = cfg.get(key)
            if value:
                paths.add(str(value).lstrip("./"))
    return paths
```

- [ ] **Step 2: Replace the `_DATASET_SAFE` copy loop with a filtered copy + dump staging.**

At `prepare.py:41-46`, remove `_DATASET_SAFE` and replace the loop at `prepare.py:202-210` with:

```python
    # PKG-16 AC-1: server-ingested dump files (postgres .sql, mongo BSON folder)
    # must NOT appear in the agent workdir. Stage them at <task_dir>/environment/_initdb/
    # so the compose can still bind-mount them into the DB container's init.d.
    dump_rel_paths = _dump_paths(db_config)
    initdb_dir = env_dir / "_initdb"
    for rel in sorted(dump_rel_paths):
        src = dataset_dir / rel
        if not src.exists():
            continue
        initdb_dir.mkdir(exist_ok=True)
        dst = initdb_dir / Path(rel).name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # Metadata files: copy if present (small, schema-only).
    for name in ("db_config.yaml", "db_description.txt", "db_description_withhint.txt"):
        src = dataset_dir / name
        if src.exists():
            shutil.copy2(src, workdir / name)

    # query_dataset/: copy entries that are NOT server-ingested dumps.
    # Sqlite (.db) and duckdb (.duckdb) live-DB files MUST remain here —
    # the agent reads them directly. SQL dumps and BSON folders are excluded
    # because they leak ground-truth rows to the agent.
    src_qd = dataset_dir / "query_dataset"
    if src_qd.is_dir():
        dst_qd = workdir / "query_dataset"
        dst_qd.mkdir(exist_ok=True)
        excluded_names = {Path(p).name for p in dump_rel_paths if p.startswith("query_dataset/")}
        for entry in sorted(src_qd.iterdir()):
            if entry.name in excluded_names:
                continue
            if entry.is_dir():
                shutil.copytree(entry, dst_qd / entry.name)
            else:
                shutil.copy2(entry, dst_qd / entry.name)
```

(Leave the existing `_QUERY_SAFE` copy loop at `prepare.py:212-215` and the `_QUERY_FORBIDDEN` belt-and-braces sweep at `prepare.py:218-223` UNCHANGED. They remain the per-query gate.)

- [ ] **Step 3: Re-point the compose bind-mount sources for dab-postgres / dab-mongo.**

In `compose.py`, change the source paths emitted at lines 63–65 and 71–73:

```python
        if kind == "postgres":
            db_name = cfg.get("db_name") or f"{dataset_name}_db"
            pg_dbs.append(db_name)
            sql_file = cfg.get("sql_file")
            if sql_file:
                # PKG-16 AC-1: dump is staged at <task_dir>/environment/_initdb/{basename}
                # (out of the agent workdir). Compose lives at
                # <task_dir>/environment/docker-compose.yaml, so the source is
                # ./_initdb/{basename} — a sibling of the compose file.
                init_volumes_pg.append(
                    {"src": f"./_initdb/{Path(sql_file).name}", "dst": f"/docker-entrypoint-initdb.d/{Path(sql_file).name}"}
                )
        elif kind == "mongo":
            db_name = cfg.get("db_name") or f"{dataset_name}_db"
            mongo_dbs.append(db_name)
            dump_folder = cfg.get("dump_folder")
            if dump_folder:
                init_volumes_mongo.append(
                    {"src": f"./_initdb/{Path(dump_folder).name}", "dst": f"/docker-entrypoint-initdb.d/{Path(dump_folder).name}"}
                )
```

- [ ] **Step 4: Run the new test to verify it passes.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Run the existing prepare/per-query suite to surface regressions.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_per_query.py -v`
Expected: `test_compose_bind_mount_sources_resolve_to_real_files` will FAIL — it currently asserts that the bind-mount source resolves to `../steps/main/workdir/...`. That assertion is the OLD contract; PKG-16 inverts it. Task 4 updates this test.

- [ ] **Step 6: Commit (GREEN, partial — prepare suite not yet updated).**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py \
        packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py
git commit -m "feat(pkg16): stage DB dumps under environment/_initdb/ to remove from agent workdir"
```

---

## Task 4 — Update PKG-13 prepare-suite to the new contract

**Files:**
- Modify: `packages/razorback-plugin-dab/tests/unit/test_prepare_per_query.py` (the `test_compose_bind_mount_sources_resolve_to_real_files` and `test_workdir_carries_safe_files` cases).

- [ ] **Step 1: Update the bind-mount source assertion.**

In `test_compose_bind_mount_sources_resolve_to_real_files`, replace the docstring and assertion to match the PKG-16 contract: the postgres bind-mount source must resolve to a file that exists AND is NOT under `steps/main/workdir/`:

```python
def test_compose_bind_mount_sources_resolve_to_real_files(tmp_path: Path):
    """PKG-16 AC-1 + AC-2: the postgres init bind-mount source must resolve
    to an existing file AND must not point into the agent workdir.
    """
    data_root = _build_synthetic_data_root(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset="bookreview", tasks_root=out
    )
    compose_path = manifest[0]["task_dir"] / "environment" / "docker-compose.yaml"
    compose = yaml.safe_load(compose_path.read_text())
    pg_volumes = compose["services"]["dab-postgres"]["volumes"]
    assert pg_volumes, "expected at least one postgres init volume"
    for entry in pg_volumes:
        src = entry.split(":", 1)[0]
        resolved = (compose_path.parent / src).resolve()
        assert resolved.exists(), f"bind-mount source missing: {resolved}"
        assert "steps/main/workdir" not in str(resolved), (
            f"PKG-16 AC-1: dump must not be sourced from agent workdir: {resolved}"
        )
```

- [ ] **Step 2: Update `test_workdir_carries_safe_files` to remove the now-invalid expectation.**

The current assertion `assert (workdir / "query_dataset").is_dir()` is still true (sqlite stays there). But there is no assertion that the SQL dump exists in the workdir — good. No change needed if the test only checks for metadata files + `query_dataset/` being a directory. Confirm by reading lines 129–139; if no `*.sql` assertion exists there, leave the test alone.

(Note for the executor: if the existing test happens to assert `*.sql` presence anywhere — it currently does not, per the source — REMOVE that assertion as a PKG-16 contract change. Do NOT add a "dump must be absent from workdir" assertion here; that lives in `test_workdir_no_dump.py` (Task 2).)

- [ ] **Step 3: Run the prepare suite.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_per_query.py -v`
Expected: all cases PASS.

- [ ] **Step 4: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/tests/unit/test_prepare_per_query.py
git commit -m "test(pkg16): update PKG-13 prepare-suite to assert dump is not workdir-sourced"
```

---

## Task 5 — AC-4: 12-dataset catalog walk for workdir-absence

**Files:**
- Modify: `packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py` (append catalog-walk test).

- [ ] **Step 1: Add a fixture builder + parametrized test for all 12 datasets.**

Append to `packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py`:

```python
# AC-4: walk the 12-dataset catalog and confirm the workdir-absence contract
# holds for every dataset using a synthetic per-dataset fixture (no LFS deps).

_PG_DUMP_NAMES = {
    "bookreview": "books_info.sql",
    "crmarenapro": "support.sql",
    "googlelocal": "googlelocal.sql",
    "PANCANCER_ATLAS": "pancancer_atlas.sql",
    "PATENTS": "patents.sql",
}
_MONGO_DUMP_NAMES = {
    "agnews": "agnews_articles",
    "yelp": "yelp_business",
}


def _backend_to_client_cfg(dataset_name: str, backend: str) -> dict:
    """Return a synthetic db_clients entry for one backend on one dataset."""
    if backend == "postgres":
        return {
            "db_type": "postgres",
            "db_name": f"{dataset_name.lower()}_db",
            "sql_file": f"query_dataset/{_PG_DUMP_NAMES.get(dataset_name, dataset_name.lower() + '.sql')}",
        }
    if backend == "mongo":
        return {
            "db_type": "mongo",
            "db_name": f"{dataset_name.lower()}_db",
            "dump_folder": f"query_dataset/{_MONGO_DUMP_NAMES.get(dataset_name, dataset_name.lower())}",
        }
    if backend == "sqlite":
        return {"db_type": "sqlite", "db_path": f"query_dataset/{dataset_name.lower()}.db"}
    if backend == "duckdb":
        return {"db_type": "duckdb", "db_path": f"query_dataset/{dataset_name.lower()}.duckdb"}
    raise AssertionError(f"unknown backend: {backend}")


def _build_synthetic_dataset(root: Path, dataset: catalog.DabDataset) -> Path:
    data_root = root / "data"
    qdir = data_root / f"query_{dataset.name}"
    qdir.mkdir(parents=True, exist_ok=True)
    clients = {
        f"{backend}_client": _backend_to_client_cfg(dataset.name, backend)
        for backend in dataset.backends
    }
    (qdir / "db_config.yaml").write_text(yaml.safe_dump({"db_clients": clients}))
    (qdir / "db_description.txt").write_text(f"{dataset.name} schema.")
    qd = qdir / "query_dataset"
    qd.mkdir(exist_ok=True)
    for cfg in clients.values():
        for key in ("sql_file", "dump_folder", "db_path"):
            rel = cfg.get(key)
            if not rel:
                continue
            target = data_root.parent / "data" / f"query_{dataset.name}" / rel
            if key == "dump_folder":
                target.mkdir(parents=True, exist_ok=True)
                (target / "metadata.bson").write_bytes(b"\x00" * 64)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("INSERT INTO t VALUES (1);\n" * 10)
    q1 = qdir / "query1"
    q1.mkdir(exist_ok=True)
    (q1 / "query.json").write_text('{"question": "synthetic"}')
    return data_root


@pytest.mark.parametrize("dataset", catalog.DAB_DATASETS, ids=lambda d: d.name)
def test_workdir_excludes_all_dump_artifacts_for_each_dataset(
    tmp_path: Path, dataset: catalog.DabDataset
):
    data_root = _build_synthetic_dataset(tmp_path, dataset)
    manifest = prepare_dataset_tasks(
        data_root=data_root, dataset=dataset.name, tasks_root=tmp_path / "tasks"
    )
    assert manifest, f"{dataset.name}: expected at least one task"
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    # AC-1 + AC-4: no .sql under the workdir for any dataset.
    leaked_sql = list(workdir.rglob("*.sql"))
    assert leaked_sql == [], f"{dataset.name}: .sql leaked into workdir: {leaked_sql}"
    # AC-1 + AC-4: no mongo BSON dump folder under the workdir for any mongo dataset.
    leaked_bson = [p for p in workdir.rglob("*.bson")]
    assert leaked_bson == [], f"{dataset.name}: BSON dump leaked into workdir: {leaked_bson}"
```

- [ ] **Step 2: Run the parametrized test.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py -v`
Expected: 12 parametrized cases + 4 bookreview-specific cases all PASS.

- [ ] **Step 3: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py
git commit -m "test(pkg16): AC-4 catalog walk — workdir excludes dumps for all 12 datasets"
```

---

## Task 6 — Live compose-config regression for bookreview

**Files:**
- Modify: `packages/razorback-plugin-dab/tests/integration/test_compose_parses.py` (only if PKG-13's existing test makes a `steps/main/workdir/` source-path assertion; otherwise just re-run).

- [ ] **Step 1: Read the existing PKG-13 integration test.**

Read `packages/razorback-plugin-dab/tests/integration/test_compose_parses.py`. If it asserts the bind-mount source resolves under `steps/main/workdir/`, change the assertion to require `environment/_initdb/`. If the test only runs `docker compose config` and checks for non-zero exit, leave it alone.

- [ ] **Step 2: Run the integration test under docker.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/integration/test_compose_parses.py -v -s`
Expected: PASS. (If the harness has no docker available, mark this step SKIPPED and rely on Task 8's live smoke for AC-2 verification.)

- [ ] **Step 3: Commit if any change was required.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/tests/integration/test_compose_parses.py
git commit -m "test(pkg16): integration compose-config check tracks new dump staging path" || \
  echo "no changes — integration test already path-agnostic"
```

---

## Task 7 — AC-5: full plugin pytest sweep

**Files:** none modified.

- [ ] **Step 1: Run the full plugin test suite from a clean working tree.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/ -v`
Expected: all 70+ existing tests + the 16 new PKG-16 cases (4 bookreview-specific + 12 parametrized) PASS. Specifically confirm the following PKG-13 tests still pass:

- `tests/unit/test_validator_q1_hardening.py`
- `tests/unit/test_validator_q2_q3_length_cap.py`
- `tests/unit/test_reachability_gate.py`
- `tests/unit/test_compose_postgres.py`
- `tests/unit/test_compose_mongo.py`
- `tests/unit/test_compose_hybrid.py`
- `tests/unit/test_compose_sidecar.py`
- `tests/unit/test_task_toml_lint.py`
- `tests/integration/test_ac9_missing_dataset.py`
- `tests/integration/test_reachability_gate_fails.py`

- [ ] **Step 2: If any unexpected failure surfaces, STOP and investigate.**

Do not "fix forward" by editing tests. Apply the systematic-debugging protocol: identify the root cause, decide whether PKG-16 is altering a contract the test legitimately encodes, and patch the implementation (not the test) unless the test asserts the OLD pre-PKG-16 contract.

- [ ] **Step 3: Commit nothing if all green; otherwise commit fix + record decision in the stage report.**

---

## Task 8 — AC-3: bookreview honest re-smoke at opus-4.7

**Files:**
- Create: `examples/specs/pkg16-bookreview-claude-harbor-dab-n3-opus47.yaml`

- [ ] **Step 1: Create the spec.**

Create `examples/specs/pkg16-bookreview-claude-harbor-dab-n3-opus47.yaml`:

```yaml
# ABOUTME: PKG-16 AC-3 — honest re-smoke after workdir SQL-dump removal, opus-4.7.
# ABOUTME: Per-run $5 cap via --max-budget-usd-running; subscription auth.
version: 1
experiment: pkg16-bookreview-claude-harbor-dab-n3-opus47-honest
agent:
  kind: claude-cli
  model: claude-opus-4-7
  sampling:
    temperature: 0.0
  tools_allowed: [Bash, Read, Write, Edit, Glob, Grep]
benchmark:
  kind: harbor_dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets:
    - bookreview
  workspace_variant: direct-minimal
  hints: false
trials: 3
experiment_meta:
  max_budget_usd: 5.0
  estimated_cost_usd: 1.5
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

- [ ] **Step 2: Confirm the run command.**

The validator runs:

```bash
cd /Users/clkao/git/razorback && \
  uv run rk run examples/specs/pkg16-bookreview-claude-harbor-dab-n3-opus47.yaml \
    --runs-dir _runs/pkg16-bookreview-opus47 \
    --max-budget-usd-running 5
```

This is the spec the validation stage will dispatch. The implementation-stage worker does NOT run this — live runs cost money and live opus-4.7 invocations are validation-stage gated. Commit the spec only.

- [ ] **Step 3: Commit.**

```bash
cd /Users/clkao/git/razorback
git add examples/specs/pkg16-bookreview-claude-harbor-dab-n3-opus47.yaml
git commit -m "spec(pkg16): AC-3 bookreview opus-4.7 honest re-smoke (N=3)"
```

---

## Task 9 — AC-6: reconciliation-baseline doc update spec

**Files:**
- Reference: `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md` — UPDATED IN VALIDATION STAGE, not implementation stage.

- [ ] **Step 1: Capture the doc-update spec in this plan (no edit yet).**

The validation-stage worker will:

1. Append a new run row beneath the PKG-13 T14-re-run row:

   ```markdown
   ### PKG-16 honest re-smoke (post-workdir-dump-removal, opus-4.7)

   **Date:** {YYYY-MM-DD of validation}
   **Razorback commit:** {SHA on PKG-16 worktree branch}
   **Cost:** {actual $ from `rk runs cost`}
   **Wall-clock:** {trial total from result.json}

   | Mode                                  | n | reward=1.0 count | pass@1 | Wilson 95% CI    |
   | ------------------------------------- | - | ---------------- | ------ | ---------------- |
   | v1 dump-file (opus-4.5)               | 3 | 3                | 1.000  | [0.4385, 1.0000] |
   | v2 live-DB (opus-4.5, dump in workdir)| 9 | 9                | 1.000  | [0.7008, 1.0000] |
   | v3 live-DB (opus-4.7, dump REMOVED)   | 9 | {N}              | {p}    | [{lo}, {hi}]     |

   Run-dir: `_runs/pkg16-bookreview-opus47/...`
   ```

2. Annotate the PKG-13 9/9 row's interpretation:

   > **POTENTIALLY INFLATED — agent had Read+Bash access to `books_info.sql` in the workdir; the PKG-16 re-smoke supersedes this anchor for Goal 1.**

3. Update the "Comparison against pre-registered shift band (AC-6)" section to acknowledge that the PKG-13 9/9 was conditional on the workdir leak, and that the pre-registered band at opus-4.7 is now anchored by the PKG-16 re-smoke.

- [ ] **Step 2: No commit — this task only specifies what the validation stage will do.**

The plan-stage worker does not edit the reconciliation doc; AC-6 closes during validation.

---

## Self-review

**Spec coverage:**

- AC-1 (workdir absent of `*.sql`/`*.bson`/...) → T2 + T3 + T5
- AC-2 (postgres init still loads dump, agent does not see it) → T3 (compose source re-point) + T6 (`docker compose config` regression) + T8 (live smoke proves DB populates)
- AC-3 (bookreview opus-4.7 re-smoke distinguishable from 9/9) → T8 (spec) + validation-stage dispatch
- AC-4 (all 12 datasets benefit) → T5 (parametrized catalog walk)
- AC-5 (no regression) → T4 (update old contract test) + T7 (full sweep)
- AC-6 (reconciliation-baseline doc update) → T9 (spec for validation-stage edit)

**Placeholder scan:** No "TBD"/"TODO"/"appropriate"/"similar to Task N" left. Test code is inline.

**Type consistency:** `_dump_paths` (Task 3.1) returns `set[str]`; consumed as `dump_rel_paths` (Task 3.2) — consistent. Bind-mount source path `./_initdb/{basename}` consistent between `compose.py` (Task 3.3), the test (Task 2.1 step 4 `_initdb`), and the doc (this plan's File Structure table). Staging dir name `_initdb` consistent across `prepare.py` step 2, `compose.py` step 3, and tests.

**Out-of-scope kept out:** PKG-14 bind-mount-from-data_root is not assumed. PKG-15 mongo init mechanism is independent. F1/F3/F4/F5/F8/F9/F10 are explicitly out of scope per the entity. ade-bench generalization is filed separately if needed.

---

## Execution handoff

Plan written. The first-officer will dispatch the implementation stage on a worktree branch `pkg16-harbor-dab-workdir-no-sql-dump/main` per the worker-key convention. The validation stage (T8 live dispatch + T9 doc update) runs AFTER implementation lands and the worktree pytest sweep is green.
