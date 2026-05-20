# PKG-15 — harbor-DAB mongo init mechanism (BSON restore on first start) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the harbor-DAB plugin's mongo path actually load BSON dumps on first start, gate compose-up on real data presence (not just TCP), and unblock the 2 mongo datasets (agnews, yelp) in Goal 1's 12-dataset matrix.

**Architecture:** AC-1 fix shape (a) — emit a `restore.sh` shim alongside the BSON dump folder in `/docker-entrypoint-initdb.d/`. The mongo:8 image auto-runs `.sh` files; the shim calls `mongorestore --db <db_name> /docker-entrypoint-initdb.d/<dump_folder_basename>/<db_name>`. AC-2 extends PKG-13 T5's reachability-gate scaffolding from postgres-only to also emit a mongo content-presence probe (`mongosh --eval "db.getSiblingDB(...).getCollection(...).countDocuments() > 0"`). AC-3/AC-4 are validation-stage live re-runs of the dab-mongo-probe; AC-5 is matrix-driver unblocking; AC-6 is the unit+integration regression net.

**Tech Stack:** Python 3.13, pytest, pyyaml, tomllib; docker compose; mongo:8 + mongosh + mongorestore; harbor task.toml; `razorback_plugin_dab` package.

---

## AC ↔ Task map

| AC   | Verified by                                                                       | Tasks            |
|------|-----------------------------------------------------------------------------------|------------------|
| AC-1 | mongosh post-compose-up shows non-zero document count (agnews ≥120k, yelp ≥150k)  | T2, T3, T8       |
| AC-2 | unit test asserts mongo dataset task.toml includes content-presence mongosh probe | T4, T5, T9       |
| AC-3 | agnews N=1 re-run produces honest rewards / real-data references                  | T10              |
| AC-4 | yelp N=1 re-run produces honest rewards / real-data references                    | T11              |
| AC-5 | dab-paper-matrix dry-run lists all 12 datasets (no agnews/yelp skip)              | T12              |
| AC-6 | new test fails if shim is dropped OR mongo probe regresses                        | T2, T6, T7       |

## Risk-ordered task ordering rationale

The riskiest contracts (per code-project-guardrails / "validate the smallest end-to-end exercise of the riskiest path FIRST"):

1. **The `restore.sh` shim actually runs and loads documents inside `mongo:8`'s init.d** — this is the single load-bearing claim of AC-1. Validated by T8 (integration test under docker — smallest end-to-end mechanism exercise) BEFORE the broader live agnews/yelp re-runs in T10/T11.
2. **The compose-generated content-presence probe shape matches what harbor's healthcheck loop actually executes** — validated by T4 (unit test on emitted toml) BEFORE T5 (live negative test) and T9 (live positive test).

Everything else (matrix driver, AC scan) is downstream and rides on top of those two contracts.

## Dependency / rebase awareness

PKG-15 touches the same two files as PKG-14 (in implementation) and PKG-16 (in validation):

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py` — PKG-14 may flip bind-mount sources from `../steps/main/workdir/<dump_folder>` to `data_root`-relative absolute paths; PKG-16 may flip them to `./_initdb/<basename>`. PKG-15 introduces a NEW bind-mount entry (the shim) plus changes the existing dump-folder mount target to nest one level deeper. The plan keeps the dump-folder mount path unchanged in shape (still `/docker-entrypoint-initdb.d/<dump_folder_basename>`) so PKG-14/PKG-16 source-side changes commute with PKG-15's destination-side additions.
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` — PKG-15 extends `_postgres_db_name` into a more general `_reachability_db_targets` (or sibling `_mongo_targets`) function and extends `_task_toml`'s `[steps.healthcheck]` emission. PKG-13's postgres branch is preserved unchanged.

**Rebase order:** if PKG-14 or PKG-16 lands first, rebase PKG-15's worktree onto main, re-verify T2's compose unit test passes, and re-run T8's integration test. If PKG-15 lands first, PKG-14/PKG-16 must rebase onto PKG-15 and re-verify the mongo init path didn't regress.

## File structure

**Created:**
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/mongo_init.py` — owns the shim text (single `MONGO_RESTORE_SH` constant + `render_mongo_restore_sh(db_name, dump_folder_basename)` helper). One module, one responsibility (shim emission).
- `packages/razorback-plugin-dab/tests/unit/test_mongo_init_shim.py` — unit tests for AC-1 generator side.
- `packages/razorback-plugin-dab/tests/unit/test_mongo_reachability_gate.py` — unit tests for AC-2 task.toml shape.
- `packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py` — long-marker integration test for AC-1 end-to-end (skipped without docker; AC-6 regression net for the shim).
- `packages/razorback-plugin-dab/tests/integration/test_mongo_reachability_gate_fails.py` — AC-2 negative-path test (gate exits non-zero when mongo collection is empty / host unreachable).

**Modified:**
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py` — extend mongo branch to (1) emit `restore.sh` shim file via `mongo_init.render_mongo_restore_sh`, (2) add a second volume entry mounting the shim into `/docker-entrypoint-initdb.d/00-restore-<db_name>.sh`, (3) keep the existing dump-folder mount unchanged. New: a return value or side-effect contract so `prepare.py` knows which shim file to write.
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py` — (1) after writing `docker-compose.yaml`, write the `restore.sh` text to `<env_dir>/restore-<db_name>.sh` per mongo client; (2) extend `_postgres_db_name` callsite in `_materialize_task_dir` to also resolve a list of mongo (db_name, collection_name) probe targets; (3) extend `_task_toml` to accept and emit a mongo content-presence healthcheck when postgres is absent and mongo is present.
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py` — verify the `agnews` and `yelp` catalog entries expose a stable collection name suitable for the AC-2 probe; if not, add a `mongo_probe_collection` field per dataset (read-only addition, no removal). Inspect the existing dataclass first; if `backends` is enough, no schema change.

**Validation-stage artifacts (not implementation tasks; documented for the validation worker):**
- `_runs/probe-agnews-pkg15/` — N=1 re-run output (gitignored / non-committed evidence).
- `_runs/probe-yelp-pkg15/` — same for yelp.

---

## Stage scope

This plan covers implementation-stage work (T1–T9 and T12) plus the validation-stage spec for T10/T11 (the live re-runs). The implementation worker must finish T1–T9 + T12 before signaling completion. The live re-runs (T10/T11) belong to the validation-stage worker dispatched after implementation is committed and reviewed.

---

### Task 1: Confirm dataset catalog exposes mongo probe targets

**Files:**
- Read: `packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py`
- Possibly modify: same file (only if a `mongo_probe_collection` field is missing).
- Test: `packages/razorback-plugin-dab/tests/unit/test_datasets_catalog.py`

This is a setup task. AC-2's probe needs a concrete `(db_name, collection_name)` pair per mongo dataset. The `db_config.yaml` for each dataset declares `db_name` under `db_clients.*` (e.g. `articles_db`, `yelp_db`) but does NOT directly declare the collection name. The collection name comes from the BSON file basename inside `<dump_folder>/<db_name>/` (e.g. `articles.bson` → collection `articles`).

- [ ] **Step 1: Read the catalog source**

Run: `uv run python -c "from razorback_plugin_dab import datasets as c; d = c.by_name('agnews'); print(d)"`
Then read `/Users/clkao/git/razorback/packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py` to see the dataclass shape. Decide: does the catalog already expose collection name, or must the probe derive it from the live dump folder at generation time?

- [ ] **Step 2: Inspect upstream dump folder structure for both mongo datasets**

Run:
```bash
ls /Users/clkao/git/dataagentbench/data/query_agnews/query_dataset/agnews_articles/articles_db/
ls /Users/clkao/git/dataagentbench/data/query_yelp/query_dataset/yelp_business/yelp_db/
```
Expected: each lists `<collection>.bson` and `<collection>.metadata.json` files. Note the collection names (e.g. `articles.bson` → `articles`; `business.bson` → `business`).

- [ ] **Step 3: Decide derivation strategy and document it inline (no code yet)**

If the BSON folder is reliably structured as `<dump_folder>/<db_name>/<collection>.bson`, derive the probe collection from disk at generation time (in `prepare.py`). If structure varies, add an explicit `mongo_probe_collection` field per dataset in `datasets.py`. Default: derive from disk; only add a catalog field if discovery is unreliable.

Write a 2-3 line comment in the plan margin (or in the entity-file stage report) recording which path you picked. No code commit in this task.

- [ ] **Step 4: No commit (purely investigative)**

Move to Task 2.

---

### Task 2: AC-1 RED — unit test for `mongo_init.render_mongo_restore_sh`

**Files:**
- Create: `packages/razorback-plugin-dab/tests/unit/test_mongo_init_shim.py`

- [ ] **Step 1: Write the failing test**

```python
# ABOUTME: PKG-15 AC-1 — restore.sh shim renders mongorestore command for one BSON dump.
# ABOUTME: Shim is the mechanism that closes the mongo init gap surfaced by dab-mongo-probe.

import pytest

from razorback_plugin_dab.generate.mongo_init import render_mongo_restore_sh


def test_shim_invokes_mongorestore_with_db_and_dump_path():
    text = render_mongo_restore_sh(db_name="articles_db", dump_folder_basename="agnews_articles")
    assert text.startswith("#!/bin/sh\n")
    assert "set -eu" in text
    assert "mongorestore" in text
    assert "--db articles_db" in text
    assert "/docker-entrypoint-initdb.d/agnews_articles/articles_db" in text


def test_shim_quotes_db_name_safely():
    # db_name comes from db_config.yaml; refuse names that would shell-inject.
    with pytest.raises(ValueError):
        render_mongo_restore_sh(db_name="articles_db; rm -rf /", dump_folder_basename="agnews_articles")


def test_shim_rejects_path_traversal_in_dump_folder():
    with pytest.raises(ValueError):
        render_mongo_restore_sh(db_name="articles_db", dump_folder_basename="../../etc")
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/razorback-plugin-dab/tests/unit/test_mongo_init_shim.py -v`
Expected: FAIL — `ModuleNotFoundError: razorback_plugin_dab.generate.mongo_init`.

- [ ] **Step 3: Commit the failing test**

```bash
git add packages/razorback-plugin-dab/tests/unit/test_mongo_init_shim.py
git commit -m "test(pkg15): RED test for mongo restore.sh shim renderer (AC-1)"
```

---

### Task 3: AC-1 GREEN — implement `mongo_init.render_mongo_restore_sh`

**Files:**
- Create: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/mongo_init.py`

- [ ] **Step 1: Write the minimal implementation**

```python
# ABOUTME: Emits the .sh shim mongo:8's init.d auto-runs to mongorestore a BSON dump.
# ABOUTME: Closes PKG-15 AC-1; the official mongo image ignores .bson but auto-executes .sh.

from __future__ import annotations

import re


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def render_mongo_restore_sh(*, db_name: str, dump_folder_basename: str) -> str:
    """Return the shell text mongo:8 should auto-run from /docker-entrypoint-initdb.d/.

    Refuses names that would inject shell or path-traversal. db_name and
    dump_folder_basename are caller-controlled in principle but come from
    db_config.yaml on disk in practice — refusing unsafe values keeps a
    poisoned upstream dataset from turning into a container-side RCE.
    """
    if not _SAFE_NAME.match(db_name):
        raise ValueError(f"unsafe mongo db_name {db_name!r}")
    if not _SAFE_NAME.match(dump_folder_basename):
        raise ValueError(f"unsafe mongo dump folder basename {dump_folder_basename!r}")

    return (
        "#!/bin/sh\n"
        "set -eu\n"
        f"# PKG-15: mongo:8 image ignores .bson in /docker-entrypoint-initdb.d/.\n"
        f"# This shim is auto-executed at first-start to load the BSON dump.\n"
        f"mongorestore --db {db_name} "
        f"/docker-entrypoint-initdb.d/{dump_folder_basename}/{db_name}\n"
    )
```

- [ ] **Step 2: Run the test to confirm it passes**

Run: `uv run pytest packages/razorback-plugin-dab/tests/unit/test_mongo_init_shim.py -v`
Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/mongo_init.py
git commit -m "feat(pkg15): mongo restore.sh shim renderer (AC-1 GREEN)"
```

---

### Task 4: AC-2 RED — unit test for mongo content-presence reachability gate

**Files:**
- Create: `packages/razorback-plugin-dab/tests/unit/test_mongo_reachability_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# ABOUTME: PKG-15 AC-2 — mongo dataset emits [steps.healthcheck] with a content-presence probe.
# ABOUTME: TCP-only would not have caught Bug 1 from the dab-mongo-probe; we probe a doc count.

import tomllib
from pathlib import Path

import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


_AGNEWS_LIKE = {
    "db_clients": {
        "articles_database": {
            "db_type": "mongo",
            "db_name": "articles_db",
            "dump_folder": "query_dataset/agnews_articles",
        },
        "metadata_database": {
            "db_type": "sqlite",
            "db_path": "query_dataset/metadata.db",
        },
    }
}


def _scaffold(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_agnews"
    qdir.mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump(_AGNEWS_LIKE))
    (qdir / "db_description.txt").write_text("schema")
    qd = qdir / "query_dataset"
    qd.mkdir()
    dump_dir = qd / "agnews_articles" / "articles_db"
    dump_dir.mkdir(parents=True)
    (dump_dir / "articles.bson").write_bytes(b"\x00")
    (dump_dir / "articles.metadata.json").write_text("{}")
    (qd / "metadata.db").write_bytes(b"SQLite format 3\x00")
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "q"}')
    (q1 / "validate.py").write_text("def validate(a):\n    return (True, 'ok')\n")
    return data_root


def test_mongo_dataset_emits_content_presence_healthcheck(tmp_path: Path):
    data_root = _scaffold(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="agnews", tasks_root=out)
    task_toml = tomllib.loads((manifest[0]["task_dir"] / "task.toml").read_text())
    hc = task_toml["steps"][0]["healthcheck"]
    cmd = hc["command"]
    assert "mongosh" in cmd
    assert "dab-mongo" in cmd
    assert "articles_db" in cmd
    assert "articles" in cmd
    assert "countDocuments" in cmd
    # Must check > 0 (content presence), not just connectivity.
    assert "> 0" in cmd or ">0" in cmd
    assert hc["retries"] >= 3


def test_mongo_only_dataset_no_postgres_gate(tmp_path: Path):
    data_root = _scaffold(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="agnews", tasks_root=out)
    task_toml = tomllib.loads((manifest[0]["task_dir"] / "task.toml").read_text())
    cmd = task_toml["steps"][0]["healthcheck"]["command"]
    # Must NOT regress to a postgres probe.
    assert "dab-postgres" not in cmd
    assert "5432" not in cmd
```

- [ ] **Step 2: Run the tests and confirm both fail**

Run: `uv run pytest packages/razorback-plugin-dab/tests/unit/test_mongo_reachability_gate.py -v`
Expected: FAIL — `KeyError: 'healthcheck'` (mongo-only dataset currently emits no `[steps.healthcheck]` per PKG-13 T5 postgres-only design).

- [ ] **Step 3: Commit the failing tests**

```bash
git add packages/razorback-plugin-dab/tests/unit/test_mongo_reachability_gate.py
git commit -m "test(pkg15): RED tests for mongo content-presence reachability gate (AC-2)"
```

---

### Task 5: AC-2 GREEN — extend `prepare.py` to emit mongo healthcheck

**Files:**
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`

- [ ] **Step 1: Add a `_mongo_probe_targets` helper alongside `_postgres_db_name`**

After `_postgres_db_name` (~line 280), add:

```python
def _mongo_probe_targets(
    db_config: dict | None,
    *,
    dataset_dir: Path,
    dataset_name: str,
) -> list[tuple[str, str]]:
    """Return (db_name, collection_name) pairs for every mongo client.

    Collection name is derived from the .bson file basename under
    <data_root>/<dataset_dir>/<dump_folder>/<db_name>/ (mongo's standard
    dump layout). Returns [] when no mongo client is declared.
    """
    pairs: list[tuple[str, str]] = []
    clients = (db_config or {}).get("db_clients") or {}
    for cfg in clients.values():
        if not isinstance(cfg, dict) or cfg.get("db_type") != "mongo":
            continue
        db_name = cfg.get("db_name") or f"{dataset_name}_db"
        dump_folder = cfg.get("dump_folder")
        collection = _derive_mongo_collection(
            dataset_dir=dataset_dir, dump_folder=dump_folder, db_name=db_name,
        )
        if collection is None:
            raise ComposeError(
                f"could not derive mongo probe collection for dataset {dataset_name!r} "
                f"(db_name={db_name!r}, dump_folder={dump_folder!r}). "
                "Expected <dump_folder>/<db_name>/<collection>.bson under data_root."
            )
        pairs.append((db_name, collection))
    return pairs


def _derive_mongo_collection(
    *, dataset_dir: Path, dump_folder: str | None, db_name: str,
) -> str | None:
    if not dump_folder:
        return None
    base = dataset_dir / dump_folder / db_name
    if not base.is_dir():
        return None
    bsons = sorted(p for p in base.iterdir() if p.suffix == ".bson")
    if not bsons:
        return None
    # The largest .bson is the primary collection; ties broken by lexicographic
    # name for determinism. Probing any one collection > 0 documents is enough
    # to certify the restore actually loaded data.
    bsons.sort(key=lambda p: (-p.stat().st_size, p.name))
    return bsons[0].stem
```

Also import `ComposeError` from `compose.py` if not already (it is — line 21).

- [ ] **Step 2: Extend `_task_toml` signature and body**

Change `_task_toml`'s signature (~line 233) to accept mongo targets:

```python
def _task_toml(
    *,
    task_name: str,
    docker_image: str,
    container_workdir: str,
    postgres_db: str | None = None,
    mongo_probes: list[tuple[str, str]] | None = None,
) -> str:
```

Replace the body's trailing healthcheck block with:

```python
    if postgres_db:
        probe = (
            "python3 -c \\\"import socket; "
            "s=socket.create_connection(('dab-postgres', 5432), timeout=5); s.close()\\\""
        )
        body += (
            "\n[steps.healthcheck]\n"
            f'command = "{probe}"\n'
            "interval_sec = 5\n"
            "timeout_sec = 10\n"
            "start_period_sec = 30\n"
            "retries = 6\n"
        )
    elif mongo_probes:
        db_name, collection = mongo_probes[0]
        # PKG-15 AC-2: content-presence probe, NOT TCP-only. TCP would have
        # missed Bug 1 from the dab-mongo-probe (mongo ignored .bson and
        # started healthy with an empty DB). countDocuments() > 0 fails fast
        # if mongorestore did not run or produced no documents.
        eval_js = (
            f"db.getSiblingDB('{db_name}').getCollection('{collection}').countDocuments() > 0"
        )
        probe = (
            f"mongosh --quiet --host dab-mongo --eval \\\"{eval_js}\\\" | grep -q true"
        )
        body += (
            "\n[steps.healthcheck]\n"
            f'command = "{probe}"\n'
            "interval_sec = 5\n"
            "timeout_sec = 10\n"
            "start_period_sec = 60\n"
            "retries = 12\n"
        )
    return body
```

Rationale for `start_period_sec = 60` / `retries = 12` on the mongo branch: `mongorestore` of agnews (~120k docs) or yelp_business (~150k docs) needs more cold-start budget than postgres's `\i` SQL load. 12 × 5s = 60s of post-grace polling on top of 60s start_period gives 2m of total mongo-init budget, well above the empirically observed ~30s mongorestore wallclock for these datasets.

- [ ] **Step 3: Wire mongo targets into `_materialize_task_dir`**

In `_materialize_task_dir` (~line 128), replace:

```python
    postgres_db = _postgres_db_name(db_config, dataset_name=dataset_meta.name)
    task_toml_text = _task_toml(
        task_name=task_name,
        docker_image=docker_image,
        container_workdir=container_workdir,
        postgres_db=postgres_db,
    )
```

with:

```python
    postgres_db = _postgres_db_name(db_config, dataset_name=dataset_meta.name)
    mongo_probes = _mongo_probe_targets(
        db_config, dataset_dir=dataset_dir, dataset_name=dataset_meta.name,
    )
    task_toml_text = _task_toml(
        task_name=task_name,
        docker_image=docker_image,
        container_workdir=container_workdir,
        postgres_db=postgres_db,
        mongo_probes=mongo_probes,
    )
```

Note: the postgres branch wins when both are present (postgres+mongo hybrid). The dab-mongo-probe confirmed no such hybrid datasets exist in DAB's 12; this priority is a defensive default, not a feature.

- [ ] **Step 4: Run the AC-2 tests to confirm they pass**

Run: `uv run pytest packages/razorback-plugin-dab/tests/unit/test_mongo_reachability_gate.py packages/razorback-plugin-dab/tests/unit/test_reachability_gate.py -v`
Expected: All passing (mongo tests now green; postgres-side tests still green).

- [ ] **Step 5: Commit**

```bash
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py
git commit -m "feat(pkg15): mongo content-presence reachability gate in task.toml (AC-2 GREEN)"
```

---

### Task 6: AC-6 regression — extend compose generator to emit shim file

**Files:**
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py`
- Modify: `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`
- Modify: `packages/razorback-plugin-dab/tests/unit/test_compose_mongo.py`

- [ ] **Step 1: Extend `test_compose_mongo.py` with a failing assertion that the shim mount is present**

Append to the existing file:

```python
def test_mongo_compose_mounts_restore_shim(tmp_path: Path):
    text = generate_compose(db_config=_AGNEWS_LIKE, dataset_name="agnews", data_root=tmp_path)
    compose = yaml.safe_load(text)
    volumes = compose["services"]["dab-mongo"]["volumes"]
    # Existing dump-folder mount must stay.
    assert any("agnews_articles" in v and ":/docker-entrypoint-initdb.d/agnews_articles" in v for v in volumes)
    # New shim mount: a .sh file landing in /docker-entrypoint-initdb.d/ with a
    # numeric prefix that sorts before the dump folder (mongo runs init.d
    # entries in lexicographic order; the shim must NOT run before the bind
    # mount is in place — but the mount is always present at container start,
    # so order only matters relative to OTHER .sh files; 00- prefix is safe).
    assert any(
        v.endswith(":/docker-entrypoint-initdb.d/00-restore-articles_db.sh:ro")
        for v in volumes
    ), volumes
```

- [ ] **Step 2: Run the new assertion — confirm it fails**

Run: `uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_mongo.py::test_mongo_compose_mounts_restore_shim -v`
Expected: FAIL — no shim mount in `volumes`.

- [ ] **Step 3: Extend `compose.py` mongo branch to emit the shim mount**

Inside `generate_compose`'s mongo branch (lines 66–73), after the `init_volumes_mongo.append(...)` call for the dump folder, add a second entry for the shim:

```python
        elif kind == "mongo":
            db_name = cfg.get("db_name") or f"{dataset_name}_db"
            mongo_dbs.append(db_name)
            dump_folder = cfg.get("dump_folder")
            if dump_folder:
                dump_basename = Path(dump_folder).name
                init_volumes_mongo.append(
                    {"src": f"../steps/main/workdir/{dump_folder}",
                     "dst": f"/docker-entrypoint-initdb.d/{dump_basename}"}
                )
                # PKG-15 AC-1: mongo:8 ignores .bson in /docker-entrypoint-initdb.d/
                # but auto-runs .sh files. The shim mongorestore's the dump folder.
                # Shim text is written by prepare.py (which knows the env_dir);
                # compose only needs to mount it. Numeric 00- prefix ensures
                # lexicographic ordering relative to any other future .sh files.
                init_volumes_mongo.append(
                    {"src": f"./restore-{db_name}.sh",
                     "dst": f"/docker-entrypoint-initdb.d/00-restore-{db_name}.sh"}
                )
```

- [ ] **Step 4: Wire shim file emission into `prepare.py`**

In `prepare.py`'s `_materialize_task_dir`, after the `(env_dir / "docker-compose.yaml").write_text(compose_text)` line, add:

```python
        # PKG-15 AC-1: emit one mongo restore shim per mongo client. compose.py
        # mounts it into the mongo container's /docker-entrypoint-initdb.d/.
        from razorback_plugin_dab.generate.mongo_init import render_mongo_restore_sh
        for cfg in (db_config.get("db_clients") or {}).values():
            if not isinstance(cfg, dict) or cfg.get("db_type") != "mongo":
                continue
            db_name = cfg.get("db_name") or f"{dataset_meta.name}_db"
            dump_folder = cfg.get("dump_folder")
            if not dump_folder:
                continue
            shim_path = env_dir / f"restore-{db_name}.sh"
            shim_path.write_text(
                render_mongo_restore_sh(
                    db_name=db_name,
                    dump_folder_basename=Path(dump_folder).name,
                )
            )
            shim_path.chmod(shim_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
```

The shim lives at `<task_dir>/environment/restore-<db_name>.sh`. The compose mount source `./restore-<db_name>.sh` resolves relative to the compose file's parent directory, which IS `environment/` (per PKG-13 T1's compose-location contract).

- [ ] **Step 5: Re-run the compose unit tests**

Run: `uv run pytest packages/razorback-plugin-dab/tests/unit/test_compose_mongo.py packages/razorback-plugin-dab/tests/unit/test_compose_hybrid.py packages/razorback-plugin-dab/tests/unit/test_compose_postgres.py -v`
Expected: all passing (the new shim-mount test now green; nothing in postgres / hybrid tests touches mongo).

- [ ] **Step 6: Re-run `_check_compose_volumes`-adjacent tests**

The existing `_check_compose_volumes` (prepare.py:370) walks every compose volume src and asserts the host path exists. The new shim mount must satisfy this check; the shim file is written BEFORE `_check_compose_volumes` runs at the very end of `_materialize_task_dir` (line 230). Run:

```bash
uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_per_query.py -v
```

Expected: all passing. If a test fails because the shim source path doesn't exist, the write order is wrong — fix Step 4 to write the shim before the trailing `_check_compose_volumes(compose_path)` call.

- [ ] **Step 7: Commit**

```bash
git add packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py \
        packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py \
        packages/razorback-plugin-dab/tests/unit/test_compose_mongo.py
git commit -m "feat(pkg15): emit and bind-mount mongo restore.sh shim (AC-1, AC-6 unit-side)"
```

---

### Task 7: AC-6 regression — assert mongo-only dataset triggers gate failure when collection empty

**Files:**
- Create: `packages/razorback-plugin-dab/tests/integration/test_mongo_reachability_gate_fails.py`

This mirrors PKG-13 T6's negative-path test for postgres, scoped to mongo. It validates the AC-2 healthcheck **command** exits non-zero against an unreachable / empty mongo, without spinning up the full compose stack. The container-level docker integration test belongs in T8.

- [ ] **Step 1: Write the test**

```python
# ABOUTME: PKG-15 AC-2 negative path — mongo content-presence probe exits non-zero
# ABOUTME: when dab-mongo is unreachable (closes Bug 2 fail-fast contract).

import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


_AGNEWS_LIKE = {
    "db_clients": {
        "articles_database": {
            "db_type": "mongo",
            "db_name": "articles_db",
            "dump_folder": "query_dataset/agnews_articles",
        },
        "metadata_database": {
            "db_type": "sqlite",
            "db_path": "query_dataset/metadata.db",
        },
    }
}


def _scaffold(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_agnews"
    qdir.mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump(_AGNEWS_LIKE))
    (qdir / "db_description.txt").write_text("schema")
    qd = qdir / "query_dataset"
    qd.mkdir()
    dump_dir = qd / "agnews_articles" / "articles_db"
    dump_dir.mkdir(parents=True)
    (dump_dir / "articles.bson").write_bytes(b"\x00")
    (dump_dir / "articles.metadata.json").write_text("{}")
    (qd / "metadata.db").write_bytes(b"SQLite format 3\x00")
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "q"}')
    (q1 / "validate.py").write_text("def validate(a):\n    return (True, 'ok')\n")
    return data_root


def test_mongo_reachability_gate_fails_when_dab_mongo_unreachable(tmp_path: Path):
    """AC-2 negative path: gate exits non-zero when mongosh can't reach dab-mongo.

    Run from the host where `dab-mongo` doesn't resolve to model the
    "compose not loaded / mongorestore did not run" failure mode.
    Skipped if mongosh is not on PATH (it lives in dab-agent:latest; the
    host CI runner may not have it).
    """
    if shutil.which("mongosh") is None:
        pytest.skip("mongosh not on host PATH (it lives in container only)")

    data_root = _scaffold(tmp_path)
    out = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="agnews", tasks_root=out)
    task_toml = tomllib.loads((manifest[0]["task_dir"] / "task.toml").read_text())
    command = task_toml["steps"][0]["healthcheck"]["command"].replace('\\"', '"')

    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode != 0, (
        f"gate unexpectedly succeeded: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert re.search(
        r"(nodename nor servname|name or service not known|getaddrinfo|connection refused|server selection|host)",
        combined,
    ), f"expected connection-failure text; got: {combined!r}"
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest packages/razorback-plugin-dab/tests/integration/test_mongo_reachability_gate_fails.py -v`
Expected: either PASS (mongosh present, gate fails as expected) or SKIPPED (mongosh missing on host). Both are acceptable; SKIPPED still validates the toml shape via T4.

- [ ] **Step 3: Commit**

```bash
git add packages/razorback-plugin-dab/tests/integration/test_mongo_reachability_gate_fails.py
git commit -m "test(pkg15): AC-2 negative path — mongo gate fails when dab-mongo unreachable"
```

---

### Task 8: AC-1 mechanism check — docker integration test loads BSON dump end-to-end

**Files:**
- Create: `packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py`

This is the **single load-bearing claim of PKG-15**: that `mongo:8` + the shim, run together, populate the database. Pay this small bill before the validation-stage live re-runs (T10/T11) — if this fails, the live runs would just confirm the same regression at much higher wallclock cost.

- [ ] **Step 1: Write the test**

```python
# ABOUTME: PKG-15 AC-1 end-to-end — restore.sh + bind-mount + mongo:8 actually loads BSON.
# ABOUTME: Long-marker integration. Skipped without docker / without the upstream dab dataset.

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


pytestmark = pytest.mark.long


_DATAAGENT_BENCH_ROOT = Path(
    os.environ.get("DATAAGENTBENCH_ROOT", "/Users/clkao/git/dataagentbench")
)


def _docker_ok() -> bool:
    if shutil.which("docker") is None:
        return False
    r = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
    return r.returncode == 0


def _agnews_present() -> bool:
    return (_DATAAGENT_BENCH_ROOT / "data" / "query_agnews" / "query_dataset"
            / "agnews_articles" / "articles_db" / "articles.bson").exists()


@pytest.mark.skipif(not _docker_ok(), reason="docker daemon not available")
@pytest.mark.skipif(not _agnews_present(), reason="upstream agnews BSON not staged")
def test_agnews_compose_up_loads_articles_collection(tmp_path: Path):
    """The smallest end-to-end exercise of the AC-1 contract.

    1. Generate the agnews-q1 task dir against the real upstream data_root.
    2. docker compose up dab-mongo (skip the agent main service).
    3. Wait for the healthcheck to pass.
    4. mongosh into the container and confirm articles_db.articles has > 0 docs.
    """
    out = tmp_path / "tasks"
    data_root = _DATAAGENT_BENCH_ROOT / "data"
    manifest = prepare_dataset_tasks(data_root=data_root, dataset="agnews", tasks_root=out)
    q1 = next(m for m in manifest if m["query_id"] == 1)
    env_dir = q1["task_dir"] / "environment"
    compose = env_dir / "docker-compose.yaml"
    assert compose.exists()

    # Use a unique project name so parallel test runs don't collide.
    project = f"pkg15-{tmp_path.name}"

    try:
        # Up only the mongo service; the main service depends on it but we
        # don't need the agent for this mechanism check.
        up = subprocess.run(
            ["docker", "compose", "--project-name", project,
             "-f", str(compose), "up", "-d", "--wait", "dab-mongo"],
            capture_output=True, text=True, timeout=180,
        )
        assert up.returncode == 0, f"compose up failed: {up.stdout}\n{up.stderr}"

        # mongorestore runs from the .sh shim during init.d auto-run; it
        # completes before mongo's healthcheck flips to healthy ONLY if
        # mongo's init.d phase blocks the readiness probe. The mongo:8 image
        # DOES block readiness until init.d finishes. Therefore `--wait`
        # already guarantees the restore is done.

        # Direct probe: count documents in articles_db.articles.
        eval_js = "db.getSiblingDB('articles_db').getCollection('articles').countDocuments()"
        probe = subprocess.run(
            ["docker", "compose", "--project-name", project,
             "-f", str(compose), "exec", "-T", "dab-mongo",
             "mongosh", "--quiet", "--eval", eval_js],
            capture_output=True, text=True, timeout=60,
        )
        assert probe.returncode == 0, f"mongosh probe failed: {probe.stdout}\n{probe.stderr}"
        # Parse the integer count from mongosh output (last non-empty line).
        last = [ln for ln in probe.stdout.strip().splitlines() if ln.strip()][-1]
        count = int(last.strip())
        # Upstream DAB lists ~120k agnews articles; assert a generous floor.
        assert count > 1000, f"too few docs in articles_db.articles: {count}"
    finally:
        subprocess.run(
            ["docker", "compose", "--project-name", project,
             "-f", str(compose), "down", "-v"],
            capture_output=True, text=True, timeout=60,
        )
```

- [ ] **Step 2: Run the test locally**

Run: `uv run pytest packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py -v -m long`
Expected: PASS on a developer machine with docker + the upstream dataset; SKIPPED in CI without docker.

If it fails, this is the load-bearing failure — diagnose before proceeding to T9. Most likely culprits in order:
1. The shim is being mounted but its mode is not executable in-container — verify `ls -l /docker-entrypoint-initdb.d/00-restore-*.sh` shows `-rwxr-xr-x`. Fix: ensure `shim_path.chmod(...)` ran on the host.
2. The shim runs but `mongorestore --db articles_db /docker-entrypoint-initdb.d/agnews_articles/articles_db` finds no `.bson` files there — the bind-mount destination nesting is wrong. Verify the bind-mount destination matches the path inside the shim.
3. The compose `--wait` returns before init.d finishes (image version dependent) — extend the probe with retries inside the test.

- [ ] **Step 3: Commit**

```bash
git add packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py
git commit -m "test(pkg15): AC-1 end-to-end — mongo restore.sh loads BSON in docker (AC-6 long marker)"
```

---

### Task 9: Full plugin pytest sweep (AC-6 regression net)

**Files:**
- All under: `packages/razorback-plugin-dab/tests/`

- [ ] **Step 1: Run the full plugin test suite excluding long markers**

Run: `uv run pytest packages/razorback-plugin-dab/tests/ -v`
Expected: all green (the 70+ existing tests plus T2/T3/T4/T5/T6/T7's new tests). The long-marker T8 is excluded automatically without `-m long`.

- [ ] **Step 2: Run the long-marker test if docker is available locally**

Run: `uv run pytest packages/razorback-plugin-dab/tests/integration/test_mongo_init_docker.py -v -m long`
Expected: PASS (or SKIPPED if docker unavailable).

- [ ] **Step 3: Run the full razorback monorepo test suite**

Run: `uv run pytest -v`
Expected: all green. If anything in `packages/razorback/tests/` or the top-level suite fails because it imports / round-trips a generated task.toml that now includes a mongo `[steps.healthcheck]`, fix the snapshot or fixture — DO NOT delete tests.

- [ ] **Step 4: Commit (only if any fixture / snapshot updates were needed)**

If snapshots updated, commit them with:

```bash
git add <changed-snapshot-files>
git commit -m "chore(pkg15): refresh task.toml snapshots for mongo healthcheck addition"
```

Otherwise skip the commit.

---

### Task 10: AC-3 validation-stage spec — agnews N=1 honest re-run

**Worker:** This task is the validation-stage worker's responsibility. Implementation-stage worker stops at T9.

**Files:**
- Existing spec: `examples/specs/probe-agnews-claude-harbor-dab.yaml` (already on main per the dab-mongo-probe commit 3987ca1).

- [ ] **Step 1: Run the agnews N=1 trial**

```bash
uv run rk run examples/specs/probe-agnews-claude-harbor-dab.yaml \
  --runs-dir _runs/probe-agnews-pkg15 \
  --max-budget-usd-running 5
```

Expected wallclock: ~5m × 4 queries = ~20m. Expected cost: $0 (subscription auth).

- [ ] **Step 2: Inspect q1 verifier stdout**

```bash
cat _runs/probe-agnews-pkg15/.../tasks/agnews-q1/logs/verifier/reward.json
```

Expected: q1 verifier stdout no longer contains "empty answer". The agent's answer is either correct (reward > 0) OR cites a real article from the live mongo collection (a substring of a real article title, country name, or topic the model could not have fabricated from priors without seeing the data).

- [ ] **Step 3: Confirm the reward distribution moves off all-zero**

Acceptable outcomes (any one suffices for AC-3):
- At least one of q1/q2/q3/q4 returns reward = 1.0.
- All four return real-data-grounded outputs (no "empty answer" fingerprint; the agent references concrete article fields).

If all four still return reward = 0 AND the verifier stdout suggests fabrication, the validation worker MUST stop and escalate to the FO — do NOT pad the report. PKG-15 has not closed AC-3.

- [ ] **Step 4: Record evidence in the entity stage report**

Append the per-query verifier stdout and the reward.json paths into the validation-stage report on the entity body. Cite the run-dir path; the FO and captain will inspect.

---

### Task 11: AC-4 validation-stage spec — yelp N=1 honest re-run

**Worker:** Validation-stage worker.

**Files:**
- Existing spec: `examples/specs/probe-yelp-claude-harbor-dab.yaml`.

- [ ] **Step 1: Run the yelp N=1 trial**

```bash
uv run rk run examples/specs/probe-yelp-claude-harbor-dab.yaml \
  --runs-dir _runs/probe-yelp-pkg15 \
  --max-budget-usd-running 8
```

yelp has 7 queries; budget is bumped to $8. Expected wallclock ~35m.

- [ ] **Step 2: Same acceptance criteria as T10 Step 2/3**

At least one non-zero reward across q1–q7 OR every verifier stdout shows real-data references. Same escalation rule on failure.

- [ ] **Step 3: Record evidence in the entity stage report**

Append per-query verifier stdout + reward.json paths.

---

### Task 12: AC-5 — Goal 1 matrix driver unblocking

**Files:**
- Search target: any `dab-paper-matrix*` driver under `examples/drivers/` or `scripts/` or `packages/razorback/scripts/`. As of plan-write the file is not yet present on main (validation-stage searches confirmed none exists).
- Likely create: `examples/drivers/dab-paper-matrix.sh` (or wherever T15's "12-dataset matrix" lands — see task #35).

This task is **conditionally deferred**: the dab-paper-matrix driver is currently a pending task (#35 in the task list, "T15: 12-dataset matrix + baseline reconciliation"), not landed on main. AC-5's verification command `bash examples/drivers/dab-paper-matrix.sh --dry-run` cannot pass until that driver exists.

- [ ] **Step 1: Verify the driver does not yet exist on main**

```bash
find /Users/clkao/git/razorback -path '*/dab-paper-matrix*' -not -path '*/.worktrees/*' -not -path '*/_runs/*' -not -path '*/node_modules/*'
```

Expected: no results.

- [ ] **Step 2: Document AC-5 as carry-forward**

If the driver doesn't exist, write a `SKIPPED:` entry for AC-5 in the implementation-stage report citing T15 (task #35) as the owner. Do NOT create a stub driver — that pollutes the matrix worker's surface area.

If the driver DOES exist (e.g. another worker landed it during PKG-15's plan stage), confirm the script lists all 12 datasets including agnews and yelp without a skip-list. Patch out any `pkg15: blocked` markers introduced during the probe phase.

- [ ] **Step 3: Commit (only if patching an existing driver)**

```bash
git add examples/drivers/dab-paper-matrix.sh
git commit -m "feat(pkg15): unblock agnews+yelp in Goal 1 matrix driver (AC-5)"
```

---

## Self-Review

**1. Spec coverage:**
- AC-1 (mongo init runs mongorestore) — T2 (RED), T3 (GREEN renderer), T6 (compose + prepare wiring), T8 (end-to-end docker integration). ✓
- AC-2 (mongo content-presence reachability gate) — T4 (RED), T5 (GREEN), T7 (negative path). ✓
- AC-3 (agnews honest re-run) — T10 (validation stage). ✓
- AC-4 (yelp honest re-run) — T11 (validation stage). ✓
- AC-5 (Goal 1 matrix unblocked) — T12 (conditional; SKIPPED-with-rationale until T15 driver lands). ✓
- AC-6 (plugin tests cover mongo init) — T2 + T4 + T6 (unit), T7 + T8 (integration). ✓

**2. Placeholder scan:** No "TBD" / "TODO" / "implement later" / placeholder steps. Every code step shows the actual code. Every command shows the actual command + expected outcome.

**3. Type consistency:**
- `render_mongo_restore_sh(*, db_name, dump_folder_basename)` — referenced consistently in T2, T3, T6.
- `_mongo_probe_targets` returns `list[tuple[str, str]]` — referenced consistently in T5 step 2 + step 3.
- `_task_toml(..., mongo_probes=...)` — keyword threading matches T5 step 2's signature change and T5 step 3's callsite update.
- Shim file path `<env_dir>/restore-<db_name>.sh` and mount destination `/docker-entrypoint-initdb.d/00-restore-<db_name>.sh` consistent across T6 step 3, T6 step 4, and T8 step 2.

**4. Risk ordering:**
- AC-1's mechanism check (T8) is the smallest end-to-end exercise of the riskiest path — pays the small docker-integration bill before the validation-stage live re-runs (T10/T11) that cost ~$0 but ~55m wallclock.
- AC-2's emitted-shape test (T4) precedes any wiring (T5).
- Full pytest sweep (T9) gates implementation completion.

**5. Rebase touchpoints:** PKG-14 and PKG-16 both modify `compose.py` and `prepare.py`. The plan's compose changes are additive (one extra mount entry); the prepare changes are additive (one new helper + one new branch in `_task_toml`). No deletion of postgres behavior. If PKG-14/PKG-16 land first, the rebase strategy is a straight cherry-pick of T3/T5/T6's commits onto the new main, then re-run T9.

---

## Execution Handoff

Plan complete and saved to `docs/razorback-implementation/plans/pkg15-harbor-dab-mongo-init-restore.md`.

For PKG-15's stage flow, the implementation-stage worker executes T1–T9 + T12 in order, with full pytest sweep gating completion. The validation-stage worker (separate dispatch after implementation lands and is reviewed) executes T10 + T11 against the live upstream data.
