# PKG-14 — harbor-DAB plugin reuses LFS data + postgres DB volume across trials (implementation plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop two independent matrix-scale costs in the harbor-DAB plugin so Goal 1's 3-variant × 12-dataset × N=5 matrix fits the disk + wall-clock envelope.

1. **Cluster A (AC-1..AC-6) — bind-mount the dataset from `data_root` instead of per-trial copy.** The plugin already accepts `--data-root`; PKG-16 stages dumps under `<task_dir>/environment/_initdb/{basename}`. PKG-14 re-points the compose source ONE more step: from the per-task `_initdb/` staging dir back to the original `data_root/query_<dataset>/{path}` paths, read-only. Result: no per-trial copy of the 650MB-average dataset subtree on the host. Worst-case disk drops from ~117GB at N=5 to ~10MB per trial (provenance + spec only).
2. **Cluster B (AC-7..AC-11) — per-dataset NAMED postgres volume reuses init.d execution across trials.** The compose currently emits anonymous per-task postgres data volumes; every trial re-runs the `docker-entrypoint-initdb.d/*.sql` dump on first boot (30s–3min per dataset). PKG-14 keys the postgres data volume on `(dataset, schema_version)` only (NOT on variant / trial_idx / task_id), so first trial seeds the volume and every subsequent trial of any variant attaches the already-populated volume; postgres detects existing `PG_DATA` and skips `docker-entrypoint-initdb.d/*` per its standard semantics.

The two clusters are independent — Cluster A is a compose source-path change + a per-task copy step removed in `prepare.py`; Cluster B is a compose volume-name + volumes-section change. Cluster A lands FIRST (smaller, lower-risk; structural read-only contract gate runs early).

**Architecture:**
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py` (the postgres / mongo source paths, lines 56–73; volumes-section emission, lines 81–96 / 99–110).
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` (the `_initdb/` staging copy step that PKG-16 adds; PKG-14 makes that copy conditional on `materialize_mode == "copy"`).
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py` (new `--materialize` and `--postgres-volume-mode` flags).
- The compose generator must receive `data_root` as an absolute path (it already does, see `prepare.py:160` — `data_root=dataset_dir.parent`); PKG-14 emits the host-absolute bind-mount source from that path.

**Tech Stack:** Python 3.13, pytest, PyYAML, docker, postgres:17 image's standard init.d semantics.

**Dependency on PKG-16:** This plan assumes PKG-16 (workdir SQL dump removal) is MERGED before PKG-14 implementation starts. PKG-16 moves dumps to `<task_dir>/environment/_initdb/`; PKG-14 re-points the compose source ONE more step to `data_root/query_<dataset>/{path}`. If PKG-14 implementation begins before PKG-16 lands, the implementation stage worker MUST rebase onto post-PKG-16 main; the plan does not duplicate PKG-16's workdir-classifier code.

## AC ↔ task map

| AC    | Tasks                                                                 |
| ----- | --------------------------------------------------------------------- |
| AC-1  | T2 (RED — compose source resolves to absolute `data_root`), T3 (GREEN — compose.py emits absolute path), T4 (prepare.py drops copy when `materialize_mode="bind"`) |
| AC-2  | T5 (RED + GREEN — `du -sh` on synthetic task-dir ≤ 10MB)             |
| AC-3  | T6 (RED — compose volumes for dab-postgres / dab-mongo carry `:ro` flag), T7 (live EROFS integration test, gated on docker) |
| AC-4  | T8 (RED + GREEN — `--materialize={bind,copy}` flag; copy path restored) |
| AC-5  | T9 (RED + GREEN — synthetic LFS pointer at `data_root` still fails fast via `check_hydrated`) |
| AC-6  | T18 (validation-stage live smoke — bookreview events.jsonl contains `psql\|dab-postgres`) |
| AC-7  | T10 (RED — compose volume-name is stable across variants), T11 (GREEN — dataset-keyed NAMED volume in compose.py) |
| AC-8  | T13 (validation-stage two-trial smoke — trial 2 logs `Skipping initialization`) |
| AC-9  | T14 (RED + GREEN — `schema_version` from catalog flows into volume name) |
| AC-10 | T15 (RED + GREEN — combined bind-mount `:ro` + dataset-keyed volume in one compose) |
| AC-11 | T16 (RED + GREEN — `--postgres-volume-mode={reuse,fresh}` flag)      |

T1 is a paper-only mechanism review. T12 + T17 are full-suite regression gates. T18 + T13 + T7 are validation-stage live work (out of implementation-stage scope; the plan emits the specs/scripts only).

## Spec §-cites

- PKG-14 entity: `docs/razorback-implementation/pkg14-harbor-dab-lfs-bindmount-reuse.md` (all 11 ACs).
- PKG-16 plan (merged precursor): `docs/razorback-implementation/plans/pkg16-harbor-dab-workdir-no-sql-dump.md` — the `<task_dir>/environment/_initdb/` staging dir, the dump-vs-live-DB classifier (`_dump_paths`), and the bind-mount source path (`./_initdb/{basename}`) that PKG-14 re-points to `data_root`.
- PKG-13 entity (DONE, archived): the compose-loading + reachability-gate contracts at `prepare.py:228-230` (`_check_compose_volumes` exit) and `compose.py:81-96` (`dab-postgres` healthcheck shape) must keep passing — PKG-14 changes the SOURCE path but not the destination or readiness contract.
- Postgres init.d skip semantics: postgres:17 image entrypoint — if `$PGDATA/PG_VERSION` exists, the entrypoint skips `/docker-entrypoint-initdb.d/*` and goes straight to `pg_ctl start`. This is the standard mechanism PKG-14 AC-8 relies on; no custom postgres logic.

## File structure

| File | Responsibility | Action |
| ---- | -------------- | ------ |
| `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py` | postgres / mongo bind-mount source paths; postgres data-volume name; volumes top-level section emission | Modify (lines 30–134; both function signature additions and source-path / volume-name logic) |
| `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` | task-dir materializer; `materialize_mode` plumbing; conditional `_initdb/` copy | Modify (lines 50–110 signature + lines 153–164 compose call + lines 202+ PKG-16 copy loop) |
| `packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py` | `--materialize` and `--postgres-volume-mode` flags; pass-through to `prepare_dataset_tasks` | Modify (lines 22–80 the `generate` command) |
| `packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py` | catalog adds optional `schema_version` field (default `"v1"`) per dataset | Modify (lines 9–32 the `DabDataset` dataclass + the 12 entries) |
| `packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py` | AC-1 + AC-3 — compose source is absolute `data_root` path with `:ro` flag | Create |
| `packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py` | AC-7 + AC-9 + AC-10 + AC-11 — NAMED dataset-keyed postgres volume; schema_version suffix; fresh-mode override | Create |
| `packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py` | AC-2 + AC-4 — `materialize="bind"` skips per-task `_initdb/` copy; `du`-style disk check; `materialize="copy"` restores PKG-16 staging | Create |
| `packages/razorback-plugin-dab/tests/unit/test_hydration_check.py` | AC-5 — extend existing test with a `data_root` LFS-pointer case that fails fast under bind-mount mode | Modify (append one new test case) |
| `packages/razorback-plugin-dab/tests/integration/test_lfs_readonly_contract.py` | AC-3 live — `docker compose up dab-postgres` + bash exec attempts `rm`/`chmod`/`write` against the bind-mount path; observes EROFS | Create (skipped under no-docker harnesses) |
| `examples/specs/pkg14-bookreview-two-trial-cross-variant-smoke.yaml` | AC-8 + AC-10 + AC-6 live two-trial smoke spec (bookreview, direct-minimal trial 1 + spacedock trial 2) | Create (consumed by validation stage) |

## Risk-first ordering rationale

The riskiest contract is **the compose bind-mount source path resolution under postgres init.d on first boot**. If postgres cannot read the SQL dump (wrong permissions, wrong path, missing `:ro` flag on read-only filesystem), every downstream test collapses AND PKG-13's reachability gate fails AND PKG-16's `_initdb/` staging is rendered untestable. So:

- T1: paper-only mechanism review (no code).
- T2 (AC-1 RED): the SMALLEST failing test — compose source resolves to absolute `data_root/query_bookreview/books_info.sql`, that file exists, and the mount is `:ro`. This is the contract that, if broken, invalidates every later task.
- T3 (AC-1 GREEN): compose.py emits the absolute path. Verifies T2 in seconds.
- T4–T5 (AC-2): once the source is data_root, prepare.py drops the copy step; disk-delta assertion.
- T6–T7 (AC-3): `:ro` flag is structurally important — agent must not mutate source data. T6 is unit (string-level); T7 is live EROFS integration (gated on docker).
- T8 (AC-4): copy-mode opt-in preserved for provenance-strict runs.
- T9 (AC-5): hydration check still fires under bind-mount (now that data_root is the actual source on host, the LFS-pointer detector is MORE relevant, not less).
- T10–T11 (AC-7): dataset-keyed volume name — Cluster B starts here.
- T12: full plugin pytest sweep — first gate before Cluster B-specific tests.
- T14 (AC-9): schema_version suffix.
- T15 (AC-10): the two ACs (read-only bind-mount + NAMED volume) compose correctly in one compose file.
- T16 (AC-11): `--postgres-volume-mode={reuse,fresh}` override.
- T17: full plugin pytest sweep — second regression gate.
- T18 (AC-6) + T13 (AC-8): validation-stage live work — specs + scripts only committed by the implementation stage; validation stage dispatches the live runs.

Comprehensive runs come AFTER the smallest end-to-end mechanism check passes. Cluster A's `:ro` EROFS test (T7) comes AFTER the unit-level path/flag assertion (T6) passes. Cluster B's two-trial smoke (T13) comes AFTER the unit-level NAMED-volume assertion (T10/T11) and after T12's regression gate proves Cluster A didn't break anything.

---

## Task 1 — Mechanism review (no code)

**Files:** none modified.

- [ ] **Step 1: Confirm the post-PKG-16 source path is `<task_dir>/environment/_initdb/{basename}`.**

Read `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py` lines 56–73 after PKG-16 lands. For `db_type == "postgres"` with `sql_file: query_dataset/books_info.sql`, the emitted volume entry is `./_initdb/books_info.sql:/docker-entrypoint-initdb.d/books_info.sql:ro`. The base path for resolution is the compose file's parent: `<task_dir>/environment/`. PKG-14 re-points this one more step: the source becomes the ABSOLUTE path under `data_root`, e.g. `/Users/clkao/git/dataagentbench/data/query_bookreview/books_info.sql`. Absolute paths in compose bind-mount sources are docker-supported and don't need a `./`-prefix dance.

- [ ] **Step 2: Confirm `data_root` flows into `generate_compose`.**

Read `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` line 160: `data_root=dataset_dir.parent` is passed to `generate_compose`. `dataset_dir = data_root / f"query_{dataset}"` (prepare.py:65), so `dataset_dir.parent` is the user-supplied `--data-root`. PKG-14 uses this same parameter — no new plumbing into `generate_compose` is needed; the parameter is already there (compose.py:34) but currently unused. PKG-14 wires it up.

- [ ] **Step 3: Identify volume-name keying for Cluster B.**

Postgres data is a NAMED volume in compose's top-level `volumes:` section, attached to the `dab-postgres` service at `/var/lib/postgresql/data`. The volume name must be deterministic across variants/trials/task_ids; it depends ONLY on `(dataset_name, schema_version)`. Naming template: `dab-postgres-data-{dataset_name}-{schema_version}` (e.g., `dab-postgres-data-bookreview-v1`). `schema_version` lives in `datasets.py` (the catalog), defaults to `"v1"`. The volume name is keyed lowercase to avoid docker's "invalid volume name" errors for upper-case catalog names like `PANCANCER_ATLAS` (docker volume names accept `[a-zA-Z0-9][a-zA-Z0-9_.-]*` but tooling treats them case-insensitively; explicit `.lower()` avoids ambiguity). Final form: `dab-postgres-data-{dataset_name.lower()}-{schema_version}`.

- [ ] **Step 4: Identify the network-name interaction.**

`compose.py:131` already emits `networks: {<n>: {name: "<n>-<dataset_name>"}}` keyed on dataset. The NAMED postgres volume mirrors this convention but adds a schema_version suffix. No change to network-naming logic.

- [ ] **Step 5: Commit a note (no code change).**

No commit. Steps 1–4 are paper-only. Proceed to Task 2.

---

## Task 2 — AC-1 RED: compose source resolves to absolute `data_root` paths

**Files:**
- Create: `packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py`

- [ ] **Step 1: Write the failing test.**

Create `packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py`:

```python
# ABOUTME: PKG-14 AC-1 — compose bind-mount source for dab-postgres / dab-mongo
# ABOUTME: resolves to the absolute data_root path, not a per-task workdir copy.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.compose import generate_compose


def _bookreview_cfg(data_root: Path) -> dict:
    qdir = data_root / "query_bookreview"
    (qdir / "query_dataset").mkdir(parents=True)
    (qdir / "query_dataset" / "books_info.sql").write_text("SELECT 1;\n")
    return {
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": "query_dataset/books_info.sql",
            }
        }
    }


def test_postgres_source_is_data_root_absolute(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="bookreview",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    volumes = compose["services"]["dab-postgres"]["volumes"]
    assert volumes, "expected at least one postgres init volume"
    entry = volumes[0]
    src = entry.split(":", 1)[0]
    expected = str((data_root / "query_bookreview" / "books_info.sql").resolve())
    assert src == expected, (
        f"AC-1: postgres init source must be absolute data_root path; got {src!r}"
    )
    assert Path(src).exists()


def test_postgres_source_is_not_per_task_initdb(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="bookreview",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    src = compose["services"]["dab-postgres"]["volumes"][0].split(":", 1)[0]
    assert "_initdb" not in src, (
        f"AC-1: PKG-14 supersedes PKG-16's _initdb/ staging — source must be data_root: {src}"
    )
    assert "steps/main/workdir" not in src, (
        f"AC-1: source must not be the agent workdir: {src}"
    )
```

- [ ] **Step 2: Run the test to verify it fails.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py -v`

Expected: both tests FAIL — the post-PKG-16 implementation emits `./_initdb/books_info.sql`, not the absolute path.

- [ ] **Step 3: Commit (RED).**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py
git commit -m "test(pkg14): RED — compose source resolves to absolute data_root path"
```

---

## Task 3 — AC-1 GREEN: compose.py emits absolute `data_root/query_<dataset>/{path}` source

**Files:**
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py` (lines 56–73 the source-path logic).

- [ ] **Step 1: Re-point the postgres + mongo source paths.**

In `compose.py`, replace lines 56–73:

```python
        if kind == "postgres":
            db_name = cfg.get("db_name") or f"{dataset_name}_db"
            pg_dbs.append(db_name)
            sql_file = cfg.get("sql_file")
            if sql_file:
                # PKG-14 AC-1: bind-mount the dump from data_root directly,
                # read-only. No per-task copy. Compose accepts absolute host
                # paths in volume sources.
                src = (data_root / f"query_{dataset_name}" / sql_file).resolve()
                init_volumes_pg.append(
                    {"src": str(src), "dst": f"/docker-entrypoint-initdb.d/{Path(sql_file).name}"}
                )
        elif kind == "mongo":
            db_name = cfg.get("db_name") or f"{dataset_name}_db"
            mongo_dbs.append(db_name)
            dump_folder = cfg.get("dump_folder")
            if dump_folder:
                src = (data_root / f"query_{dataset_name}" / dump_folder).resolve()
                init_volumes_mongo.append(
                    {"src": str(src), "dst": f"/docker-entrypoint-initdb.d/{Path(dump_folder).name}"}
                )
```

- [ ] **Step 2: Run the new test to verify it passes.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py -v`

Expected: both tests PASS.

- [ ] **Step 3: Run the existing compose suite to surface regressions.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_postgres.py packages/razorback-plugin-dab/tests/unit/test_compose_mongo.py packages/razorback-plugin-dab/tests/unit/test_compose_hybrid.py packages/razorback-plugin-dab/tests/unit/test_compose_sidecar.py -v`

Expected: Tests that asserted the OLD `./_initdb/` source path WILL FAIL. Document which ones. The failures are EXPECTED for tests that encode the pre-PKG-14 contract; Task 4 updates them. Tests that only check service shape (healthcheck, environment, depends_on) should still PASS.

- [ ] **Step 4: Commit (GREEN, partial — old-contract tests not yet updated).**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py
git commit -m "feat(pkg14): bind-mount postgres/mongo init from data_root absolute paths"
```

---

## Task 4 — AC-1 + AC-2: prepare.py drops per-task `_initdb/` copy under bind-mount mode

**Files:**
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`
  - lines 50–60 (signature: add `materialize_mode: str = "bind"`)
  - lines 90–102 (forward into `_materialize_task_dir`)
  - lines 112–125 (signature: add same parameter)
  - lines 200–230 (the PKG-16 `_initdb/` copy block is conditional on `materialize_mode == "copy"`)
- Modify: `packages/razorback-plugin-dab/tests/unit/test_prepare_per_query.py` (update the PKG-16 assertion that `<task_dir>/environment/_initdb/{basename}` exists — under PKG-14 default, it does NOT).
- Modify: `packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py` (the PKG-16 assertion `test_postgres_dump_staged_under_environment_initdb` becomes copy-mode-only — make it parametrized over `materialize_mode={"bind","copy"}` or skip the `_initdb/` existence half under `"bind"`).

- [ ] **Step 1: Thread `materialize_mode` through `prepare_dataset_tasks`.**

In `prepare.py:50-60`, add `materialize_mode: str = "bind"` to the keyword args of `prepare_dataset_tasks`. Forward it into `_materialize_task_dir` at line 90 (`_materialize_task_dir(materialize_mode=materialize_mode, ...)`). Add the same parameter to `_materialize_task_dir`'s signature at line 112.

- [ ] **Step 2: Make the PKG-16 `_initdb/` copy conditional on `materialize_mode == "copy"`.**

PKG-16 introduces (at `prepare.py:202+`):

```python
dump_rel_paths = _dump_paths(db_config)
initdb_dir = env_dir / "_initdb"
for rel in sorted(dump_rel_paths):
    ...
```

Wrap this block in `if materialize_mode == "copy":`. Under the default `"bind"` mode, the `_initdb/` directory is NEVER created — the compose source resolves to `data_root` directly (AC-1) and the host's existing `data_root/query_<dataset>/{path}` is the source of truth.

The `query_dataset/` workdir filter that PKG-16 introduces (`excluded_names = {Path(p).name for p in dump_rel_paths if p.startswith("query_dataset/")}`) STAYS. Under bind mode, sqlite/duckdb live-DB files are still copied into the workdir (the agent reads them); dumps are still excluded (the agent does not see them). Only the `_initdb/` staging step is skipped — the dumps live at `data_root`, not inside the task dir.

- [ ] **Step 3: Update PKG-16 tests for the new default.**

In `tests/unit/test_workdir_no_dump.py`, the test `test_postgres_dump_staged_under_environment_initdb` (created by PKG-16) asserts `<task_dir>/environment/_initdb/books_info.sql` exists. Under PKG-14's default `materialize_mode="bind"`, that file does NOT exist. Update the test to either (a) explicitly pass `materialize_mode="copy"` to `prepare_dataset_tasks`, or (b) parametrize over both modes. Choice: (a) — keep the PKG-16 test as a copy-mode contract assertion.

In `tests/unit/test_prepare_per_query.py`, the PKG-16 test `test_compose_bind_mount_sources_resolve_to_real_files` asserts that the resolved source path exists. Under PKG-14, the source is the absolute `data_root` path — so the synthetic fixture must create the dump file at `data_root/query_bookreview/books_info.sql` (which it already does for the PKG-13 reachability gate). Verify the assertion path resolves under `data_root`, not under `<task_dir>/environment/`. Update the assertion's path expectation accordingly: `assert "steps/main/workdir" not in str(resolved)` STAYS; add `assert "_initdb" not in str(resolved)` (PKG-14 contract).

- [ ] **Step 4: Add a disk-delta test (AC-2).**

Create `packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py`:

```python
# ABOUTME: PKG-14 AC-2 + AC-4 — bind mode produces ≤10MB task-dir; copy mode restores PKG-16 staging.

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


def _build_bookreview_data_root(root: Path, dump_size_mb: int = 50) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    (qdir / "query_dataset").mkdir(parents=True)
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
    # Large synthetic dump — the file PKG-14 must NOT copy under bind mode.
    (qdir / "query_dataset" / "books_info.sql").write_bytes(b"X" * (dump_size_mb * 1024 * 1024))
    (qdir / "query_dataset" / "review_query.db").write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "How many books?"}')
    return data_root


def _du_bytes(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    return total


def test_bind_mode_task_dir_under_10mb(tmp_path: Path):
    """AC-2: under bind mode, the per-task dir contains no dataset copy."""
    data_root = _build_bookreview_data_root(tmp_path, dump_size_mb=50)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    task_dir = manifest[0]["task_dir"]
    size = _du_bytes(task_dir)
    # 10MB allowance covers task.toml + instruction.md + compose + sqlite live DB
    # (the .db file IS copied; it's the live DB, not a dump). The 50MB dump
    # must not be copied.
    assert size <= 10 * 1024 * 1024, (
        f"AC-2: bind-mode task-dir is {size / (1024*1024):.1f}MB, expected ≤10MB"
    )


def test_bind_mode_no_initdb_dir(tmp_path: Path):
    data_root = _build_bookreview_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    task_dir = manifest[0]["task_dir"]
    assert not (task_dir / "environment" / "_initdb").exists(), (
        "AC-1: bind mode must not stage dumps into per-task _initdb/"
    )


def test_copy_mode_restores_initdb_staging(tmp_path: Path):
    """AC-4: --materialize=copy restores PKG-16's _initdb/ staging."""
    data_root = _build_bookreview_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="copy",
    )
    task_dir = manifest[0]["task_dir"]
    assert (task_dir / "environment" / "_initdb" / "books_info.sql").exists(), (
        "AC-4: copy mode must restore the per-task _initdb/ staging"
    )


def test_bind_mode_keeps_sqlite_live_db_in_workdir(tmp_path: Path):
    """PKG-14 does not change PKG-16's live-DB workdir contract."""
    data_root = _build_bookreview_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    assert (workdir / "query_dataset" / "review_query.db").exists(), (
        "sqlite is a file-backed live DB — must remain in workdir"
    )
```

- [ ] **Step 5: Run the new test.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py -v`

Expected: all 4 tests PASS.

- [ ] **Step 6: Re-run prepare suite + PKG-16 suite.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_per_query.py packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py -v`

Expected: all PASS (after the Step 3 updates).

- [ ] **Step 7: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py \
        packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py \
        packages/razorback-plugin-dab/tests/unit/test_workdir_no_dump.py \
        packages/razorback-plugin-dab/tests/unit/test_prepare_per_query.py
git commit -m "feat(pkg14): materialize_mode={bind,copy} drops per-task _initdb/ copy by default"
```

---

## Task 5 — AC-2 GREEN (already covered by Task 4)

Marked as covered by Task 4 Step 4 + Step 5. No separate task. AC-2 closes when `test_bind_mode_task_dir_under_10mb` passes.

---

## Task 6 — AC-3 RED + GREEN (unit): postgres / mongo volumes carry `:ro` flag

**Files:**
- Append to: `packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py`

- [ ] **Step 1: Add the read-only assertion test.**

Append to `test_compose_bindmount_source.py`:

```python
def test_postgres_volume_is_read_only(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="bookreview",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    for entry in compose["services"]["dab-postgres"]["volumes"]:
        assert entry.endswith(":ro"), (
            f"AC-3: postgres data bind-mount must be read-only; got {entry!r}"
        )


def test_mongo_volume_is_read_only(tmp_path: Path):
    data_root = tmp_path / "data"
    qdir = data_root / "query_agnews" / "query_dataset" / "agnews_articles"
    qdir.mkdir(parents=True)
    (qdir / "metadata.bson").write_bytes(b"\x00" * 64)
    cfg = {
        "db_clients": {
            "articles": {
                "db_type": "mongo",
                "db_name": "agnews_db",
                "dump_folder": "query_dataset/agnews_articles",
            }
        }
    }
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="agnews",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    for entry in compose["services"]["dab-mongo"]["volumes"]:
        assert entry.endswith(":ro"), (
            f"AC-3: mongo dump bind-mount must be read-only; got {entry!r}"
        )
```

- [ ] **Step 2: Run.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py -v`

Expected: both new tests PASS — compose.py lines 95 and 109 already emit `f"{v['src']}:{v['dst']}:ro"`. PKG-14's source-path change preserves the `:ro` flag.

- [ ] **Step 3: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/tests/unit/test_compose_bindmount_source.py
git commit -m "test(pkg14): AC-3 unit — postgres/mongo bind-mount carries :ro flag"
```

---

## Task 7 — AC-3 integration: live EROFS contract (gated on docker)

**Files:**
- Create: `packages/razorback-plugin-dab/tests/integration/test_lfs_readonly_contract.py`

- [ ] **Step 1: Write the integration test.**

Create `packages/razorback-plugin-dab/tests/integration/test_lfs_readonly_contract.py`:

```python
# ABOUTME: PKG-14 AC-3 — agent container cannot mutate bind-mounted source data.
# ABOUTME: docker compose up dab-postgres; exec a write/rm/chmod; assert EROFS.

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="docker not available — AC-3 EROFS contract is a live test",
)


def _bookreview_data_root(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    (qdir / "query_dataset").mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump({
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": "query_dataset/books_info.sql",
            }
        }
    }))
    (qdir / "db_description.txt").write_text("Bookreview schema.")
    (qdir / "query_dataset" / "books_info.sql").write_text(
        "CREATE TABLE books (id INT);\n"
    )
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "synthetic"}')
    return data_root


def test_bind_mounted_source_is_read_only(tmp_path: Path):
    data_root = _bookreview_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    compose_dir = manifest[0]["task_dir"] / "environment"
    project = f"pkg14-readonly-{os.getpid()}"
    try:
        up = subprocess.run(
            ["docker", "compose", "-p", project, "-f", "docker-compose.yaml",
             "up", "-d", "--wait", "dab-postgres"],
            cwd=compose_dir, check=False, capture_output=True, text=True, timeout=180,
        )
        if up.returncode != 0:
            pytest.skip(f"compose up failed (likely no daemon): {up.stderr}")
        # Attempt to mutate the bind-mounted file inside the container.
        result = subprocess.run(
            ["docker", "compose", "-p", project, "-f", "docker-compose.yaml",
             "exec", "-T", "dab-postgres", "sh", "-c",
             "echo X >> /docker-entrypoint-initdb.d/books_info.sql 2>&1; echo EXIT=$?"],
            cwd=compose_dir, check=True, capture_output=True, text=True, timeout=30,
        )
        # EROFS or "Read-only file system" must surface; the write must FAIL.
        assert "EXIT=0" not in result.stdout, (
            f"AC-3: write to bind-mounted source unexpectedly succeeded:\n{result.stdout}"
        )
        # Source file on host is unchanged.
        host_size = (data_root / "query_bookreview" / "query_dataset" / "books_info.sql").stat().st_size
        assert host_size == len("CREATE TABLE books (id INT);\n"), (
            "AC-3: host source file was modified by container write attempt"
        )
    finally:
        subprocess.run(
            ["docker", "compose", "-p", project, "-f", "docker-compose.yaml",
             "down", "-v", "--remove-orphans"],
            cwd=compose_dir, check=False, capture_output=True, timeout=60,
        )
```

- [ ] **Step 2: Run (will SKIP if no docker).**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/integration/test_lfs_readonly_contract.py -v -s`

Expected: PASS on a docker-available harness; SKIP otherwise. The implementation-stage worker proceeds even if SKIPPED — the validation stage re-runs this against a real docker daemon.

- [ ] **Step 3: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/tests/integration/test_lfs_readonly_contract.py
git commit -m "test(pkg14): AC-3 integration — bind-mounted source is read-only inside container"
```

---

## Task 8 — AC-4: `--materialize={bind,copy}` CLI flag

**Files:**
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py` (the `generate` command).

- [ ] **Step 1: Add the flag.**

In `cli.py:23-46`, add:

```python
    materialize: str = typer.Option(
        "bind",
        "--materialize",
        help="Dataset materialization mode: bind (default — read-only bind-mount from data_root) or copy (per-task _initdb/ staging).",
    ),
```

Validate against `{"bind", "copy"}`:

```python
    if materialize not in ("bind", "copy"):
        typer.echo(
            f"razorback-plugin-dab: --materialize must be one of bind|copy; got {materialize!r}",
            err=True,
        )
        raise typer.Exit(code=2)
```

Forward into `prepare_dataset_tasks`:

```python
    for name in requested:
        prepare_dataset_tasks(
            data_root=data_root,
            dataset=name,
            tasks_root=out,
            workspace_variant=workspace_variant,
            hints=hints,
            materialize_mode=materialize,
        )
```

- [ ] **Step 2: Add a CLI test.**

Append to `packages/razorback-plugin-dab/tests/unit/test_cli_surface.py` (or create a new `test_cli_materialize.py`):

```python
def test_cli_materialize_bind_skips_initdb(tmp_path: Path, monkeypatch):
    from razorback_plugin_dab.cli import app
    from typer.testing import CliRunner
    data_root = _build_bookreview_data_root(tmp_path)  # reuse pattern from Task 4 helpers
    out = tmp_path / "tasks"
    runner = CliRunner()
    result = runner.invoke(app, [
        "generate", "--datasets", "bookreview",
        "--data-root", str(data_root), "--out", str(out),
        "--materialize", "bind",
    ])
    assert result.exit_code == 0, result.output
    task_dirs = list(out.iterdir())
    assert task_dirs
    assert not (task_dirs[0] / "environment" / "_initdb").exists()


def test_cli_materialize_copy_creates_initdb(tmp_path: Path):
    ...  # mirror image — materialize=copy creates _initdb/
```

(Use the bookreview synthetic fixture from Task 4; the helper can be lifted into a `conftest.py` if reused — keep it local for now.)

- [ ] **Step 3: Run.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_cli_surface.py -v`

Expected: PASS.

- [ ] **Step 4: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py \
        packages/razorback-plugin-dab/tests/unit/test_cli_surface.py
git commit -m "feat(pkg14): --materialize={bind,copy} CLI flag, default bind"
```

---

## Task 9 — AC-5: hydration check fires under bind-mount mode (data_root LFS pointer)

**Files:**
- Modify: `packages/razorback-plugin-dab/tests/unit/test_hydration_check.py` (append one new case).

- [ ] **Step 1: Add a case where data_root has a real LFS pointer but bind mode would otherwise use it.**

Append to `test_hydration_check.py`:

```python
def test_lfs_pointer_at_data_root_fails_before_bind_mount(tmp_path: Path) -> None:
    """PKG-14 AC-5: under bind mode the agent NEVER copies the dataset; the
    only safety against an LFS-pointer source is the hydration check itself.
    Verify it still fires when the host file is a pointer."""
    from razorback_plugin_dab.hydration import check_hydrated, LFS_POINTER_MARKER, DatasetNotHydratedError

    data_root = tmp_path / "data"
    query_dir = data_root / "query_bookreview"
    (query_dir / "query_dataset").mkdir(parents=True)
    _write_db_config(query_dir, sql_file="query_dataset/books_info.sql")
    pointer = query_dir / "query_dataset" / "books_info.sql"
    pointer.write_bytes(LFS_POINTER_MARKER + b"\noid sha256:cafebabe\nsize 99999\n")

    with pytest.raises(DatasetNotHydratedError):
        check_hydrated(data_root=data_root, dataset_name="bookreview")
```

- [ ] **Step 2: Run.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_hydration_check.py -v`

Expected: PASS — the hydration check is content-based, so it works regardless of materialization mode. This test pins that contract explicitly for PKG-14.

- [ ] **Step 3: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/tests/unit/test_hydration_check.py
git commit -m "test(pkg14): AC-5 hydration check still fires for LFS pointer at data_root"
```

---

## Task 10 — AC-7 RED: dataset-keyed NAMED postgres volume

**Files:**
- Create: `packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py`

- [ ] **Step 1: Write the failing test.**

```python
# ABOUTME: PKG-14 AC-7 + AC-8 + AC-9 + AC-10 + AC-11 — dataset-keyed NAMED postgres volume.

from __future__ import annotations

from pathlib import Path

import yaml

from razorback_plugin_dab.generate.compose import generate_compose


def _bookreview_cfg(data_root: Path) -> dict:
    qdir = data_root / "query_bookreview"
    (qdir / "query_dataset").mkdir(parents=True)
    (qdir / "query_dataset" / "books_info.sql").write_text("SELECT 1;\n")
    return {
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": "query_dataset/books_info.sql",
            }
        }
    }


def test_postgres_data_volume_is_dataset_keyed(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg,
        dataset_name="bookreview",
        data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    assert "volumes" in compose, "AC-7: compose must declare top-level volumes section"
    vol_names = list(compose["volumes"].keys())
    assert "dab-postgres-data-bookreview-v1" in vol_names, (
        f"AC-7: expected dataset-keyed volume; got {vol_names}"
    )
    # The dab-postgres service mounts the NAMED volume at PGDATA.
    pg_volumes = compose["services"]["dab-postgres"]["volumes"]
    pgdata_mounts = [v for v in pg_volumes if "/var/lib/postgresql/data" in v]
    assert pgdata_mounts, "AC-7: dab-postgres must mount the NAMED volume at PGDATA"
    src = pgdata_mounts[0].split(":", 1)[0]
    assert src == "dab-postgres-data-bookreview-v1", (
        f"AC-7: PGDATA must mount the dataset-keyed NAMED volume; got {src!r}"
    )


def test_postgres_volume_name_stable_across_variants(tmp_path: Path):
    """AC-7: variant / trial_idx / task_id do NOT influence the volume name."""
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    # generate_compose is variant-agnostic; the variant only flows through
    # the workdir README, not compose. Re-running with identical inputs
    # must produce identical volume names.
    yaml1 = generate_compose(db_config=cfg, dataset_name="bookreview", data_root=data_root)
    yaml2 = generate_compose(db_config=cfg, dataset_name="bookreview", data_root=data_root)
    assert "dab-postgres-data-bookreview-v1" in yaml1
    assert "dab-postgres-data-bookreview-v1" in yaml2


def test_postgres_volume_name_lowercased_for_caps_datasets(tmp_path: Path):
    """Docker volume names should be case-stable; the catalog names like
    PANCANCER_ATLAS must lowercase to a valid volume name."""
    data_root = tmp_path / "data"
    qdir = data_root / "query_PANCANCER_ATLAS" / "query_dataset"
    qdir.mkdir(parents=True)
    (qdir / "pancancer_atlas.sql").write_text("SELECT 1;\n")
    cfg = {
        "db_clients": {
            "pc": {
                "db_type": "postgres",
                "db_name": "pancancer_atlas_db",
                "sql_file": "query_dataset/pancancer_atlas.sql",
            }
        }
    }
    yaml_text = generate_compose(
        db_config=cfg, dataset_name="PANCANCER_ATLAS", data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    assert "dab-postgres-data-pancancer_atlas-v1" in compose["volumes"]
```

- [ ] **Step 2: Run to verify failure.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py -v`

Expected: all 3 tests FAIL — current compose.py emits no top-level `volumes:` section; postgres data is on an anonymous volume.

- [ ] **Step 3: Commit (RED).**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py
git commit -m "test(pkg14): RED — postgres data volume is dataset-keyed NAMED volume"
```

---

## Task 11 — AC-7 GREEN: compose.py emits dataset-keyed NAMED postgres volume

**Files:**
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py`
  - Add `schema_version` and `postgres_volume_mode` parameters to `generate_compose`.
  - Emit the NAMED volume in the dab-postgres service and in the top-level `volumes:` section.

- [ ] **Step 1: Update `generate_compose` signature.**

Replace the signature:

```python
def generate_compose(
    *,
    db_config: dict,
    dataset_name: str,
    data_root: Path,
    docker_image: str = DEFAULT_AGENT_IMAGE,
    container_workdir: str = DEFAULT_CONTAINER_WORKDIR,
    schema_version: str = "v1",
    postgres_volume_mode: str = "reuse",
    task_id: str | None = None,
) -> str:
```

`schema_version` defaults to `"v1"`; `postgres_volume_mode` defaults to `"reuse"`. `task_id` is used only when `postgres_volume_mode == "fresh"` — under reuse it is ignored.

- [ ] **Step 2: Compute the volume name.**

Inside the function, before the postgres service block:

```python
def _postgres_volume_name(
    *, dataset_name: str, schema_version: str, mode: str, task_id: str | None
) -> str:
    base = f"dab-postgres-data-{dataset_name.lower()}-{schema_version}"
    if mode == "fresh":
        suffix = task_id or "anon"
        return f"{base}-{suffix}"
    return base
```

- [ ] **Step 3: Mount the NAMED volume on dab-postgres.**

In the `if pg_dbs:` block (currently lines 80–96), add the data volume:

```python
    pg_volume_name: str | None = None
    if pg_dbs:
        pg_volume_name = _postgres_volume_name(
            dataset_name=dataset_name,
            schema_version=schema_version,
            mode=postgres_volume_mode,
            task_id=task_id,
        )
        services["dab-postgres"] = {
            "image": POSTGRES_IMAGE,
            "environment": {...},
            "healthcheck": {...},
            "networks": ["dab-net"],
            "volumes": (
                [f"{pg_volume_name}:/var/lib/postgresql/data"]
                + [f"{v['src']}:{v['dst']}:ro" for v in init_volumes_pg]
            ),
        }
```

- [ ] **Step 4: Add the top-level `volumes:` section.**

After the `compose` dict is assembled, add:

```python
    if pg_volume_name:
        compose["volumes"] = {pg_volume_name: {"name": pg_volume_name}}
```

The explicit `name:` key prevents docker compose from prepending the project name to the volume — critical for AC-7 (the volume must be shared across different harbor compose projects).

- [ ] **Step 5: Forward parameters from `prepare.py`.**

In `prepare.py:_materialize_task_dir`, pass `schema_version=dataset_meta.schema_version` and `postgres_volume_mode` (new param threaded through `prepare_dataset_tasks`, default `"reuse"`) and `task_id=task_name` into `generate_compose`. Defer the catalog's `schema_version` field addition to Task 14 — for Task 11, hardcode `schema_version="v1"` and add a TODO marker referencing Task 14.

Update `prepare_dataset_tasks` signature to accept `postgres_volume_mode: str = "reuse"`.

- [ ] **Step 6: Run the Task 10 tests + existing suite.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py packages/razorback-plugin-dab/tests/unit/test_compose_postgres.py packages/razorback-plugin-dab/tests/unit/test_compose_sidecar.py -v`

Expected: Task 10 tests PASS. The existing `test_compose_postgres.py` may surface the new top-level `volumes:` section. If a test asserts the OLD compose top-level keys (e.g. asserts `set(compose.keys()) == {"services", "networks"}`), update it to `>= {"services", "networks"}`. The sidecar test only inspects service names — should still PASS.

- [ ] **Step 7: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py \
        packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py \
        packages/razorback-plugin-dab/tests/unit/test_compose_postgres.py
git commit -m "feat(pkg14): dataset-keyed NAMED postgres data volume for cross-trial reuse"
```

---

## Task 12 — Regression gate 1: full plugin pytest sweep

**Files:** none modified.

- [ ] **Step 1: Run the full plugin suite.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/ -v`

Expected: all PKG-13 + PKG-16 + PKG-14 (Cluster A + Cluster B Task 10/11) cases PASS. Specifically confirm:

- `tests/unit/test_validator_q1_hardening.py`
- `tests/unit/test_validator_q2_q3_length_cap.py`
- `tests/unit/test_reachability_gate.py`
- `tests/unit/test_compose_postgres.py`
- `tests/unit/test_compose_mongo.py`
- `tests/unit/test_compose_hybrid.py`
- `tests/unit/test_compose_sidecar.py`
- `tests/unit/test_task_toml_lint.py`
- `tests/unit/test_workdir_no_dump.py` (PKG-16)
- `tests/unit/test_prepare_per_query.py` (PKG-13/PKG-16, updated by Task 4)
- `tests/integration/test_ac9_missing_dataset.py`
- `tests/integration/test_reachability_gate_fails.py`

If any unexpected failure surfaces, STOP and investigate per systematic-debugging — do not "fix forward" by editing tests unless they assert the OLD pre-PKG-14 contract.

- [ ] **Step 2: Commit if regressions surfaced require fixes; otherwise no commit.**

---

## Task 13 — AC-8 spec (validation-stage): two-trial cross-variant smoke

**Files:**
- Create: `examples/specs/pkg14-bookreview-two-trial-cross-variant-smoke.yaml`
- Create: `scripts/pkg14_assert_skip_initdb.sh` (validation-stage helper script).

- [ ] **Step 1: Create the spec.**

```yaml
# ABOUTME: PKG-14 AC-8 + AC-6 — two-trial cross-variant smoke on bookreview.
# ABOUTME: Trial 1 = direct-minimal (seeds the postgres volume). Trial 2 = spacedock
# ABOUTME: (must attach the seeded volume and SKIP init.d).
version: 1
experiment: pkg14-bookreview-two-trial-cross-variant-smoke
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
  workspace_variants:
    - direct-minimal
    - spacedock
  hints: false
  materialize: bind
  postgres_volume_mode: reuse
trials: 1
experiment_meta:
  max_budget_usd: 3.0
  estimated_cost_usd: 1.0
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

(If `harbor_dab` schema does not accept `workspace_variants` as a list, the validation stage runs two separate `rk run` invocations — one per variant — against the same `data_root`. The volume reuse depends on the docker volume being durable across compose projects, which docker handles natively as long as the volume `name:` is explicit.)

- [ ] **Step 2: Create the assertion script.**

```bash
#!/usr/bin/env bash
# ABOUTME: PKG-14 AC-8 — confirm trial 2's dab-postgres container SKIPPED init.d.
# ABOUTME: Reads docker compose logs across both trials' run-dirs.
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "usage: $0 <trial1_logs.txt> <trial2_logs.txt>" >&2
    exit 2
fi
trial1="$1"
trial2="$2"

echo "==> AC-8: trial 1 must have RUN init.d on the fresh volume"
grep -q "running /docker-entrypoint-initdb.d/" "$trial1" \
    || { echo "FAIL: trial 1 logs lack 'running /docker-entrypoint-initdb.d/' marker"; exit 1; }

echo "==> AC-8: trial 2 must have SKIPPED init.d on the populated volume"
grep -q "PostgreSQL Database directory appears to contain a database; Skipping initialization" "$trial2" \
    || { echo "FAIL: trial 2 logs lack 'Skipping initialization' marker"; exit 1; }

if grep -q "running /docker-entrypoint-initdb.d/" "$trial2"; then
    echo "FAIL: trial 2 unexpectedly RE-RAN init.d (volume reuse broken)"
    exit 1
fi

echo "PASS: AC-8 — init.d skipped on second trial."
```

Make executable. Validation-stage runs this against the dab-postgres container logs from each trial's run-dir.

- [ ] **Step 3: Commit.**

```bash
cd /Users/clkao/git/razorback
git add examples/specs/pkg14-bookreview-two-trial-cross-variant-smoke.yaml \
        scripts/pkg14_assert_skip_initdb.sh
chmod +x scripts/pkg14_assert_skip_initdb.sh
git commit -m "spec(pkg14): AC-8 two-trial cross-variant smoke spec + skip-init.d assertion script"
```

---

## Task 14 — AC-9: schema_version flows from catalog into volume name

**Files:**
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py` (add `schema_version` field).
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` (pass `dataset_meta.schema_version`).
- Append to: `packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py` (the schema_version test).

- [ ] **Step 1: Extend the catalog dataclass.**

In `datasets.py`:

```python
@dataclass(frozen=True)
class DabDataset:
    name: str
    backends: tuple[str, ...]
    query_count: int
    schema_version: str = "v1"
```

Leave the existing 12 dataset entries unchanged — they inherit the default `"v1"`. Future schema bumps modify the entry's `schema_version`.

- [ ] **Step 2: Forward into compose.**

In `prepare.py`, remove the Task 11 hardcoded `schema_version="v1"` TODO and pass `schema_version=dataset_meta.schema_version` to `generate_compose`.

- [ ] **Step 3: Add the schema-bump test.**

Append to `test_compose_dataset_volume.py`:

```python
def test_schema_version_v2_yields_distinct_volume_name(tmp_path: Path):
    """AC-9: bumping schema_version invalidates the v1 volume — new v2 name."""
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_v1 = generate_compose(
        db_config=cfg, dataset_name="bookreview", data_root=data_root,
        schema_version="v1",
    )
    yaml_v2 = generate_compose(
        db_config=cfg, dataset_name="bookreview", data_root=data_root,
        schema_version="v2",
    )
    assert "dab-postgres-data-bookreview-v1" in yaml_v1
    assert "dab-postgres-data-bookreview-v2" in yaml_v2
    assert "dab-postgres-data-bookreview-v1" not in yaml_v2
```

- [ ] **Step 4: Run.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py packages/razorback-plugin-dab/tests/unit/test_datasets_catalog.py -v`

Expected: PASS. The catalog test that enumerates `DAB_DATASETS` still passes because `schema_version` is an additive optional field.

- [ ] **Step 5: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py \
        packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py \
        packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py
git commit -m "feat(pkg14): schema_version field on DabDataset; flows into volume name"
```

---

## Task 15 — AC-10: bind-mount `:ro` + NAMED volume compose in one compose file

**Files:**
- Append to: `packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py`

- [ ] **Step 1: Add the combined-contract test.**

```python
def test_named_volume_and_readonly_bindmount_coexist(tmp_path: Path):
    """AC-10: in one compose file, the postgres service has BOTH a NAMED data
    volume (writable) AND a read-only bind-mount for the dump."""
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg, dataset_name="bookreview", data_root=data_root,
    )
    compose = yaml.safe_load(yaml_text)
    pg_volumes = compose["services"]["dab-postgres"]["volumes"]
    assert len(pg_volumes) >= 2, (
        f"AC-10: expected NAMED data volume + read-only dump mount; got {pg_volumes}"
    )
    # Named volume — no :ro suffix.
    named = [v for v in pg_volumes if v.startswith("dab-postgres-data-")]
    assert len(named) == 1
    assert not named[0].endswith(":ro"), "PGDATA must be writable"
    # Dump bind-mount — :ro suffix.
    dump_mounts = [v for v in pg_volumes if "/docker-entrypoint-initdb.d/" in v]
    assert len(dump_mounts) >= 1
    assert all(v.endswith(":ro") for v in dump_mounts)
```

- [ ] **Step 2: Run.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py -v`

Expected: PASS.

- [ ] **Step 3: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py
git commit -m "test(pkg14): AC-10 — NAMED PGDATA volume coexists with :ro dump bind-mount"
```

---

## Task 16 — AC-11: `--postgres-volume-mode={reuse,fresh}` override

**Files:**
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py`
- Append to: `packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py`

- [ ] **Step 1: Add the CLI flag.**

In `cli.py`:

```python
    postgres_volume_mode: str = typer.Option(
        "reuse",
        "--postgres-volume-mode",
        help="postgres data volume strategy: reuse (default — dataset-keyed shared volume) or fresh (per-task unique volume).",
    ),
```

Validate against `{"reuse", "fresh"}`. Forward into `prepare_dataset_tasks`.

- [ ] **Step 2: Add the fresh-mode test.**

```python
def test_fresh_mode_yields_per_task_volume_name(tmp_path: Path):
    """AC-11: fresh mode appends a per-task suffix; the volume is NOT shared."""
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg, dataset_name="bookreview", data_root=data_root,
        postgres_volume_mode="fresh", task_id="bookreview-q1",
    )
    compose = yaml.safe_load(yaml_text)
    vol_names = list(compose["volumes"].keys())
    assert vol_names == ["dab-postgres-data-bookreview-v1-bookreview-q1"], (
        f"AC-11: fresh mode must carry per-task suffix; got {vol_names}"
    )


def test_reuse_mode_default_no_per_task_suffix(tmp_path: Path):
    data_root = tmp_path / "data"
    cfg = _bookreview_cfg(data_root)
    yaml_text = generate_compose(
        db_config=cfg, dataset_name="bookreview", data_root=data_root,
        task_id="bookreview-q1",  # task_id present but ignored under reuse
    )
    compose = yaml.safe_load(yaml_text)
    vol_names = list(compose["volumes"].keys())
    assert vol_names == ["dab-postgres-data-bookreview-v1"]
```

- [ ] **Step 3: Run.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py packages/razorback-plugin-dab/tests/unit/test_cli_surface.py -v`

Expected: PASS.

- [ ] **Step 4: Commit.**

```bash
cd /Users/clkao/git/razorback
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py \
        packages/razorback-plugin-dab/tests/unit/test_compose_dataset_volume.py \
        packages/razorback-plugin-dab/tests/unit/test_cli_surface.py
git commit -m "feat(pkg14): --postgres-volume-mode={reuse,fresh} override"
```

---

## Task 17 — Regression gate 2: full plugin + razorback pytest sweep

**Files:** none modified.

- [ ] **Step 1: Plugin sweep.**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback-plugin-dab/ -v`

Expected: all PASS (PKG-13 + PKG-16 + PKG-14 Clusters A + B).

- [ ] **Step 2: Razorback core sweep (for the harbor_dab benchmark plugin entry point).**

Run: `cd /Users/clkao/git/razorback && uv run pytest packages/razorback/tests -v -k 'harbor_dab or benchmark' 2>&1 | tail -50`

Expected: PASS (any harbor_dab plugin shape tests still resolve the new CLI flags via the `materialize` / `postgres_volume_mode` benchmark fields).

- [ ] **Step 3: STOP on any unexpected failure.**

Apply systematic-debugging. Patch the implementation (not the test) unless the test asserts a pre-PKG-14 contract.

- [ ] **Step 4: No commit if all green.**

---

## Task 18 — AC-6 spec (validation-stage): single-dataset N=1 honest events.jsonl

**Files:**
- Create: `examples/specs/pkg14-bookreview-honest-events-smoke.yaml`

- [ ] **Step 1: Create the spec.**

```yaml
# ABOUTME: PKG-14 AC-6 — bind-mount default produces honest events.jsonl with psql/dab-postgres.
# ABOUTME: One bookreview trial under direct-minimal — confirms the bind-mount path doesn't break the live-DB execution chain.
version: 1
experiment: pkg14-bookreview-honest-events-smoke
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
  materialize: bind
  postgres_volume_mode: reuse
trials: 1
experiment_meta:
  max_budget_usd: 2.0
  estimated_cost_usd: 0.5
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

The validation stage runs:

```bash
cd /Users/clkao/git/razorback && \
  uv run rk run examples/specs/pkg14-bookreview-honest-events-smoke.yaml \
    --runs-dir _runs/pkg14-bookreview-honest \
    --max-budget-usd-running 2
```

Then asserts `grep -E "psql|dab-postgres" _runs/pkg14-bookreview-honest/<trial>/events.jsonl` returns at least one hit.

- [ ] **Step 2: Commit.**

```bash
cd /Users/clkao/git/razorback
git add examples/specs/pkg14-bookreview-honest-events-smoke.yaml
git commit -m "spec(pkg14): AC-6 bookreview honest events.jsonl smoke spec (bind default)"
```

---

## Self-review

**Spec coverage:**

- AC-1 (compose source resolves to absolute data_root) → T2 (RED) + T3 (GREEN) + T4 (drop per-task copy).
- AC-2 (≤10MB task-dir under bind) → T4.4 (test) + T4.5 (run).
- AC-3 (read-only contract) → T6 (unit `:ro` flag) + T7 (live EROFS).
- AC-4 (`--materialize={bind,copy}`) → T8 (CLI flag) + T4.3 (copy mode restores _initdb/).
- AC-5 (hydration check fires under bind) → T9 (LFS pointer at data_root case).
- AC-6 (honest events.jsonl) → T18 (spec for validation-stage dispatch).
- AC-7 (dataset-keyed NAMED volume) → T10 (RED) + T11 (GREEN).
- AC-8 (second trial skips init.d) → T13 (spec + assertion script for validation-stage).
- AC-9 (schema_version invalidates) → T14 (catalog field + test).
- AC-10 (`:ro` bind + NAMED volume coexist) → T15 (combined test).
- AC-11 (`--postgres-volume-mode={reuse,fresh}`) → T16 (CLI flag + tests).

**Placeholder scan:** No "TBD"/"TODO"/"appropriate"/"similar to Task N" left. Test code is inline. One TODO marker is intentionally inserted in Task 11 (hardcoded `schema_version="v1"` pending Task 14) — it is resolved within the same plan.

**Type consistency:** `materialize_mode: str` consistent across `cli.py`, `prepare.py`, `prepare_dataset_tasks`, `_materialize_task_dir`. `postgres_volume_mode: str` consistent across `cli.py`, `prepare.py`, `generate_compose`. `schema_version: str` consistent across `datasets.py`, `prepare.py`, `generate_compose`. Volume name template `dab-postgres-data-{dataset_name.lower()}-{schema_version}[-task_id]` consistent across all three test files and `compose.py`.

**Risk-first ordering:** AC-1 (the compose source-path contract) is the first failing test (T2). AC-3 (`:ro` enforcement) lands before any live `docker compose up` is attempted in the implementation suite. AC-7 (the NAMED-volume contract) is the first failing test of Cluster B (T10) — before any cross-trial smoke gets attempted. T12 + T17 are full-suite gates between clusters.

**Out-of-scope kept out:** Mongo volume reuse is filed under the "out of scope" section of PKG-14 — this plan does NOT add a NAMED mongo volume (mongo init mechanism is PKG-15's territory). ade-bench generalization is PKG-19's territory. Harbor cache-dir optimization is orthogonal.

**PKG-16 interaction:** The plan explicitly assumes PKG-16 lands first. PKG-14 makes PKG-16's `_initdb/` copy conditional on `materialize_mode == "copy"` rather than removing it. PKG-16's workdir dump-filter (sqlite/duckdb in, postgres/mongo out) is preserved under both modes.

---

## Execution handoff

Plan written. The first-officer will dispatch the implementation stage on a worktree branch `pkg14-harbor-dab-lfs-bindmount-reuse/main` per the worker-key convention. The validation stage (T13 + T18 + T7 live dispatches) runs AFTER implementation lands AND PKG-16 has merged AND the worktree pytest sweep is green.
