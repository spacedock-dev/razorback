# ABOUTME: AC-9 — LFS-pointer detection vs real file content.
# ABOUTME: Pointer file raises DatasetNotHydratedError; real file returns silently.

from pathlib import Path

import pytest
import yaml

from razorback_plugin_dab.hydration import (
    DatasetNotHydratedError,
    LFS_POINTER_MARKER,
    check_hydrated,
)


def _write_db_config(query_dir: Path, sql_file: str) -> None:
    cfg = {
        "db_clients": {
            "books_database": {
                "db_type": "postgres",
                "db_name": "bookreview_db",
                "sql_file": sql_file,
            },
        }
    }
    (query_dir / "db_config.yaml").write_text(yaml.safe_dump(cfg))


def test_lfs_pointer_raises(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    query_dir = data_root / "query_bookreview"
    (query_dir / "query_dataset").mkdir(parents=True)
    _write_db_config(query_dir, sql_file="query_dataset/books_info.sql")
    pointer = query_dir / "query_dataset" / "books_info.sql"
    pointer.write_bytes(
        LFS_POINTER_MARKER + b"\noid sha256:deadbeef\nsize 12345\n"
    )

    with pytest.raises(DatasetNotHydratedError) as exc_info:
        check_hydrated(data_root=data_root, dataset_name="bookreview")

    message = str(exc_info.value)
    assert "razorback-plugin-dab: dataset bookreview not hydrated" in message
    assert "found LFS pointer at" in message
    assert "Hydrate with:" in message
    assert "git lfs pull" in message


def test_real_file_returns_silently(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    query_dir = data_root / "query_bookreview"
    (query_dir / "query_dataset").mkdir(parents=True)
    _write_db_config(query_dir, sql_file="query_dataset/books_info.sql")
    real = query_dir / "query_dataset" / "books_info.sql"
    real.write_bytes(b"-- a real SQL dump\nCREATE TABLE books (id INT);\n" * 50)

    check_hydrated(data_root=data_root, dataset_name="bookreview")


def test_missing_db_config_raises(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    (data_root / "query_bookreview").mkdir(parents=True)

    with pytest.raises(DatasetNotHydratedError):
        check_hydrated(data_root=data_root, dataset_name="bookreview")


def test_lfs_pointer_at_data_root_fails_before_bind_mount(tmp_path: Path) -> None:
    """PKG-14 AC-5: under bind mode the agent NEVER copies the dataset; the
    only safety against an LFS-pointer source is the hydration check itself.
    Verify it still fires when the host file at data_root is a pointer that
    PKG-14's compose would otherwise bind-mount straight into postgres."""
    data_root = tmp_path / "data"
    query_dir = data_root / "query_bookreview"
    (query_dir / "query_dataset").mkdir(parents=True)
    _write_db_config(query_dir, sql_file="query_dataset/books_info.sql")
    pointer = query_dir / "query_dataset" / "books_info.sql"
    pointer.write_bytes(LFS_POINTER_MARKER + b"\noid sha256:cafebabe\nsize 99999\n")

    with pytest.raises(DatasetNotHydratedError):
        check_hydrated(data_root=data_root, dataset_name="bookreview")
