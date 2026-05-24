# ABOUTME: PKG-14 AC-2 + AC-4 — bind mode skips per-task SQL dump copy (≤10MB);
# ABOUTME: copy mode restores the dump alongside other dataset payload in workdir.

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks


def _build_bookreview_data_root(
    root: Path, dump_size_mb: int = 50, sqlite_size_mb: int = 0,
) -> Path:
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
    sqlite_path = qdir / "query_dataset" / "review_query.db"
    if sqlite_size_mb > 0:
        # Synthetic SQLite payload sized for CoW disk-delta measurement.
        # The header is real; the body is zero-fill to keep generation cheap.
        header = b"SQLite format 3\x00"
        with sqlite_path.open("wb") as f:
            f.write(header)
            remaining = sqlite_size_mb * 1024 * 1024 - len(header)
            chunk = b"\x00" * (1024 * 1024)
            while remaining > 0:
                n = min(len(chunk), remaining)
                f.write(chunk[:n])
                remaining -= n
    else:
        sqlite_path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    (qdir / "query_dataset" / "schema_notes.txt").write_text("safe workdir file")
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "How many books?"}')
    return data_root


def _build_file_backed_data_root(root: Path) -> Path:
    data_root = root / "data"
    qdir = data_root / "query_bookreview"
    (qdir / "query_dataset" / "nested").mkdir(parents=True)
    (qdir / "db_config.yaml").write_text(yaml.safe_dump({
        "db_clients": {
            "review_database": {
                "db_type": "sqlite",
                "db_path": "query_dataset/review_query.db",
            },
            "analytics_database": {
                "db_type": "duckdb",
                "db_path": "query_dataset/nested/analytics.duckdb",
            },
        }
    }))
    (qdir / "db_description.txt").write_text("Bookreview schema.")
    (qdir / "query_dataset" / "review_query.db").write_bytes(
        b"SQLite format 3\x00" + b"\x00" * (8 * 1024 * 1024)
    )
    (qdir / "query_dataset" / "nested" / "analytics.duckdb").write_bytes(
        b"DUCK" + b"\x00" * (8 * 1024 * 1024)
    )
    (qdir / "query_dataset" / "nested" / "safe.txt").write_text("keep me")
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
    """AC-2: under bind mode, the per-task dir contains no dataset SQL dump."""
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


def test_bind_mode_no_sql_dump_in_workdir(tmp_path: Path):
    """AC-1: bind mode must not copy the postgres SQL dump into the agent workdir."""
    data_root = _build_bookreview_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    task_dir = manifest[0]["task_dir"]
    workdir = task_dir / "steps" / "main" / "workdir"
    assert not (workdir / "query_dataset" / "books_info.sql").exists(), (
        "AC-1: bind mode must not stage the SQL dump in the agent workdir"
    )


def test_copy_mode_keeps_sql_dump_in_workdir(tmp_path: Path):
    """AC-4: --materialize=copy restores the pre-PKG-14 copy behavior."""
    data_root = _build_bookreview_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="copy",
    )
    task_dir = manifest[0]["task_dir"]
    workdir = task_dir / "steps" / "main" / "workdir"
    assert (workdir / "query_dataset" / "books_info.sql").exists(), (
        "AC-4: copy mode must keep the SQL dump in the agent workdir"
    )


def test_bind_mode_keeps_sqlite_live_db_in_workdir(tmp_path: Path):
    """AC-2: bind mode omits SQLite/DuckDB physical copies from the workdir."""
    data_root = _build_file_backed_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    assert not (workdir / "query_dataset" / "review_query.db").exists(), (
        "SQLite DB must be a read-only main bind mount, not a physical copy"
    )
    assert not (workdir / "query_dataset" / "nested" / "analytics.duckdb").exists(), (
        "DuckDB DB must be a read-only main bind mount, not a physical copy"
    )
    assert (workdir / "query_dataset" / "nested" / "safe.txt").read_text() == "keep me"


def test_copy_mode_keeps_file_backed_dbs_in_workdir(tmp_path: Path):
    """AC-2: copy mode keeps provenance-strict physical SQLite/DuckDB copies."""
    data_root = _build_file_backed_data_root(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="copy",
    )
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    assert (workdir / "query_dataset" / "review_query.db").exists(), (
        "copy mode must retain the SQLite DB physical copy"
    )
    assert (workdir / "query_dataset" / "nested" / "analytics.duckdb").exists(), (
        "copy mode must retain the DuckDB DB physical copy"
    )


def test_invalid_materialize_mode_rejected(tmp_path: Path):
    data_root = _build_bookreview_data_root(tmp_path)
    with pytest.raises(ValueError, match="materialize_mode"):
        prepare_dataset_tasks(
            data_root=data_root,
            dataset="bookreview",
            tasks_root=tmp_path / "tasks",
            materialize_mode="symlink",
        )


def _filesystem_free_bytes(path: Path) -> int:
    """Bytes free on the filesystem containing path.

    On darwin/APFS, `du` does NOT reflect clonefile dedup — both a cloned
    file and its source report the full apparent size. The filesystem-level
    free-space delta (this function) is the only reliable signal that
    `cp -c` produced a CoW reference rather than a full copy.
    """
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="AC-1 CoW assertion requires APFS clonefile (darwin host)",
)
def test_bind_mode_sqlite_uses_cow_materialization(tmp_path: Path):
    """PKG-21 AC-1: SQLite live DB is materialized via APFS clonefile.

    A ≥100 MiB SQLite file in the source must consume <5 MiB of filesystem
    free space during bind-mode materialization. Under shutil.copytree the
    free-space drop is ≥100 MiB — the entire .db is duplicated on disk.
    """
    sqlite_mb = 100
    data_root = _build_bookreview_data_root(
        tmp_path, dump_size_mb=1, sqlite_size_mb=sqlite_mb,
    )
    free_before = _filesystem_free_bytes(tmp_path)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="bind",
    )
    free_after = _filesystem_free_bytes(tmp_path)
    consumed = free_before - free_after
    # Per-task FS delta budget: workdir scaffolding (task.toml, instruction.md,
    # docker-compose, settings.json, sqlite header, restore shims, etc.)
    # totals well under 5 MiB. The 100 MiB sqlite payload must be CoW-shared.
    # Allow some headroom for filesystem activity outside this test (other
    # processes, journaling). The test still discriminates clearly between
    # CoW (<5 MiB) and full copy (≥100 MiB).
    assert consumed < 5 * 1024 * 1024, (
        f"AC-1: bind-mode materialization consumed "
        f"{consumed / (1024*1024):.1f}MiB of FS free space; expected <5MiB "
        f"(the {sqlite_mb}MiB sqlite must be CoW-cloned)"
    )
    # Sanity: the sqlite file is omitted from the physical workdir and exposed
    # as a read-only main-service file mount.
    task_dir = manifest[0]["task_dir"]
    sqlite_in_workdir = task_dir / "steps" / "main" / "workdir" / "query_dataset" / "review_query.db"
    assert not sqlite_in_workdir.exists()
    compose = yaml.safe_load((task_dir / "environment" / "docker-compose.yaml").read_text())
    main_volumes = compose["services"]["main"]["volumes"]
    assert any(entry.endswith("/workspace/query_dataset/review_query.db:ro") for entry in main_volumes)


def test_bind_mode_linux_uses_reflink_cp(tmp_path: Path, monkeypatch):
    """PKG-25 AC-1: on linux, _clone_or_copy_tree uses cp --reflink=auto.

    Hardlink (os.link) is unsafe — writes through the dst path mutate the
    shared inode and silently corrupt the source dataset. The correct
    primitive is cp --reflink=auto: reflink CoW on btrfs/xfs/ext4-reflink,
    full physical copy fallback otherwise. This test asserts the
    invocation contract on the unit (_clone_or_copy_tree) directly so the
    sys.platform monkeypatch does not leak into the broader orchestrator
    (which imports pydantic lazily and tries to resolve sysconfig data for
    the mocked platform).
    """
    from razorback_plugin_dab.generate import prepare as prepare_mod

    monkeypatch.setattr(prepare_mod.sys, "platform", "linux")

    recorded_calls: list[list[str]] = []

    def recording_run(argv, *args, **kwargs):
        recorded_calls.append(list(argv))
        # Honor the cp call by physically copying so the test fixture
        # tree still gets materialized for subsequent assertions.
        if isinstance(argv, list) and argv and argv[0] == "cp":
            import shutil
            shutil.copyfile(argv[-2], argv[-1])
            class _R:
                returncode = 0
            return _R()
        raise AssertionError(f"unexpected subprocess.run argv: {argv!r}")

    monkeypatch.setattr(prepare_mod.subprocess, "run", recording_run)

    def _no_link(*a, **k):
        raise AssertionError(
            "PKG-25: os.link must not be invoked on linux — use cp --reflink=auto"
        )
    monkeypatch.setattr(prepare_mod.os, "link", _no_link)

    src_root = tmp_path / "src"
    src_root.mkdir()
    (src_root / "a.db").write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    sub = src_root / "sub"
    sub.mkdir()
    (sub / "b.duckdb").write_bytes(b"DUCK")
    (src_root / "ignored.sql").write_bytes(b"dump payload")

    dst_root = tmp_path / "dst"
    prepare_mod._clone_or_copy_tree(
        src_root, dst_root, ignore_names={"ignored.sql"},
    )

    assert (dst_root / "a.db").exists()
    assert (dst_root / "sub" / "b.duckdb").exists()
    assert not (dst_root / "ignored.sql").exists()

    cp_calls = [c for c in recorded_calls if c and c[0] == "cp"]
    assert cp_calls, "PKG-25: expected cp invocations on linux materialization"
    for argv in cp_calls:
        assert argv[:2] == ["cp", "--reflink=auto"], (
            f"PKG-25 AC-1: linux materialization must use cp --reflink=auto; got {argv!r}"
        )


def test_clone_or_copy_tree_docstring_is_honest():
    """PKG-25 AC-2: docstring no longer claims hardlink CoW.

    The previous docstring asserted "copy-on-write happens at the filesystem
    level when one inode is opened for write" — false for hardlinks. The
    new docstring must mention --reflink=auto and must not contain the
    wrong claim.
    """
    from razorback_plugin_dab.generate.prepare import _clone_or_copy_tree

    doc = _clone_or_copy_tree.__doc__ or ""
    assert "copy-on-write happens at the filesystem level when one inode is opened for write" not in doc, (
        "PKG-25 AC-2: docstring still asserts the wrong hardlink-CoW claim"
    )
    assert "--reflink=auto" in doc, (
        "PKG-25 AC-2: docstring must document the cp --reflink=auto primitive"
    )


def test_bind_mode_linux_cross_device_falls_back(monkeypatch):
    """PKG-25 AC-4: cross-device handling is delegated to cp --reflink=auto.

    Our code must NOT pre-check device identity (os.stat(...).st_dev) or
    branch on EXDEV — those would reintroduce the os.link hazard. The
    contract is: invoke cp --reflink=auto and let it fall back to a full
    physical copy when reflink is unavailable for any reason (including
    cross-device).
    """
    import inspect

    from razorback_plugin_dab.generate import prepare as prepare_mod

    src = inspect.getsource(prepare_mod._clone_or_copy_tree)
    assert "st_dev" not in src, (
        "PKG-25 AC-4: _clone_or_copy_tree must not pre-check device identity; "
        "delegate cross-device handling to cp --reflink=auto"
    )
    assert "EXDEV" not in src, (
        "PKG-25 AC-4: _clone_or_copy_tree must not branch on EXDEV; "
        "delegate cross-device handling to cp --reflink=auto"
    )
    assert "os.link" not in src, (
        "PKG-25: _clone_or_copy_tree must not call os.link (unsafe hardlink)"
    )


def test_bind_mode_unsupported_platform_raises(tmp_path: Path, monkeypatch):
    """PKG-21 AC-2: an unsupported platform raises a clear NotImplementedError."""
    from razorback_plugin_dab.generate import prepare as prepare_mod

    monkeypatch.setattr(prepare_mod.sys, "platform", "win32")
    data_root = _build_bookreview_data_root(tmp_path, dump_size_mb=1)
    with pytest.raises(NotImplementedError, match="win32"):
        prepare_dataset_tasks(
            data_root=data_root,
            dataset="bookreview",
            tasks_root=tmp_path / "tasks",
            materialize_mode="bind",
        )


def test_copy_mode_keeps_sqlite_via_full_copy(tmp_path: Path):
    """PKG-21 AC-3: copy mode produces a full physical copy of sqlite (distinct inode)."""
    data_root = _build_bookreview_data_root(tmp_path, dump_size_mb=1)
    manifest = prepare_dataset_tasks(
        data_root=data_root,
        dataset="bookreview",
        tasks_root=tmp_path / "tasks",
        materialize_mode="copy",
    )
    src = data_root / "query_bookreview" / "query_dataset" / "review_query.db"
    workdir = manifest[0]["task_dir"] / "steps" / "main" / "workdir"
    dst = workdir / "query_dataset" / "review_query.db"
    assert dst.exists()
    # copy mode goes through shutil.copytree → distinct inodes.
    assert os.stat(src).st_ino != os.stat(dst).st_ino, (
        "AC-3: copy mode must produce a distinct inode (not a hardlink)"
    )
