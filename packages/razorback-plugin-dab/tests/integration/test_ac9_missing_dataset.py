# ABOUTME: AC-9 validator — fresh-checkout scenario produces documented error.
# ABOUTME: Hydrate-and-rerun cycle exits 0 after real content replaces the LFS pointer.

import re
import subprocess
from pathlib import Path

import yaml

from razorback_plugin_dab.hydration import LFS_POINTER_MARKER


def _seed_lfs_pointer_data_root(root: Path, sql_pointer: bool, db_pointer: bool) -> Path:
    data_root = root / "dab-no-lfs"
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
    (qdir / "db_description.txt").write_text("Bookreview schema description.")
    q1 = qdir / "query1"
    q1.mkdir()
    (q1 / "query.json").write_text('{"question": "ok?"}')
    (q1 / "validate.py").write_text("def validate(a):\n    return (True, '')\n")
    qd = qdir / "query_dataset"
    qd.mkdir()
    pointer = (
        LFS_POINTER_MARKER + b"\noid sha256:deadbeef\nsize 12345\n"
    )
    if sql_pointer:
        (qd / "books_info.sql").write_bytes(pointer)
    else:
        (qd / "books_info.sql").write_text("-- real sql\n" * 100)
    if db_pointer:
        (qd / "review_query.db").write_bytes(pointer)
    else:
        (qd / "review_query.db").write_bytes(b"SQLite format 3\x00" + b"\x00" * 200)
    return data_root


def _uv_run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "razorback-plugin-dab"] + args,
        capture_output=True, text=True,
    )


def test_lfs_pointer_data_root_exits_2_with_documented_message(tmp_path: Path):
    data_root = _seed_lfs_pointer_data_root(tmp_path, sql_pointer=True, db_pointer=False)
    out = tmp_path / "tasks"

    result = _uv_run([
        "generate", "--datasets", "bookreview",
        "--data-root", str(data_root), "--out", str(out),
    ])

    assert result.returncode == 2, result.stderr
    expected_re = (
        r"razorback-plugin-dab: dataset bookreview not hydrated, "
        r"found LFS pointer at .*books_info\.sql\.\n"
        r"Hydrate with:\n"
        r"  cd .* && git lfs pull"
    )
    assert re.search(expected_re, result.stderr), f"stderr: {result.stderr!r}"


def test_hydrate_and_rerun_succeeds(tmp_path: Path):
    data_root = _seed_lfs_pointer_data_root(tmp_path, sql_pointer=True, db_pointer=False)
    out = tmp_path / "tasks"

    # First run fails.
    first = _uv_run([
        "generate", "--datasets", "bookreview",
        "--data-root", str(data_root), "--out", str(out),
    ])
    assert first.returncode == 2

    # Simulate `git lfs pull` by replacing the pointer with real content.
    pointer_path = data_root / "query_bookreview" / "query_dataset" / "books_info.sql"
    pointer_path.write_text("-- real sql dump\n" * 200)

    # Rerun succeeds.
    second = _uv_run([
        "generate", "--datasets", "bookreview",
        "--data-root", str(data_root), "--out", str(out),
    ])
    assert second.returncode == 0, second.stderr
    assert (out / "bookreview-q1" / "task.toml").exists()
