from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from razorback.benchmarks.spider2_dbt.preflight import (
    Spider2WorkspacePreflightError,
    preflight_spider2_workspace,
)


def _write_duckdb(path: Path, tables: set[str]) -> None:
    conn = duckdb.connect(str(path))
    try:
        for table in sorted(tables):
            conn.execute(f'CREATE TABLE "{table}" (id INTEGER)')
    finally:
        conn.close()


def test_present_readable_duckdb_passes(tmp_path: Path) -> None:
    _write_duckdb(tmp_path / "spider2-fixture-001.duckdb", {"orders", "customers"})

    result = preflight_spider2_workspace(
        task_id="spider2-fixture-001",
        workspace=tmp_path,
        db_name="spider2-fixture-001",
    )

    assert result["status"] == "passed"
    assert result["task_id"] == "spider2-fixture-001"
    assert "orders" in result["observed_tables"]
    assert "customers" in result["observed_tables"]


def test_present_duckdb_discovered_without_db_name(tmp_path: Path) -> None:
    _write_duckdb(tmp_path / "anything.duckdb", {"t1"})

    result = preflight_spider2_workspace(task_id="t", workspace=tmp_path)

    assert result["status"] == "passed"
    assert result["db_path"].endswith("anything.duckdb")


def test_missing_duckdb_fails_closed_with_named_error(tmp_path: Path) -> None:
    with pytest.raises(Spider2WorkspacePreflightError) as exc_info:
        preflight_spider2_workspace(
            task_id="spider2-fixture-001",
            workspace=tmp_path,
            db_name="spider2-fixture-001",
        )

    payload = exc_info.value.payload
    assert payload["status"] == "failed"
    assert payload["reason"] == "duckdb file missing"
    assert "spider2-fixture-001.duckdb" in payload["db_path"]


def test_corrupt_duckdb_fails_closed(tmp_path: Path) -> None:
    corrupt = tmp_path / "spider2-fixture-001.duckdb"
    corrupt.write_bytes(b"this is not a valid duckdb file" * 4)

    with pytest.raises(Spider2WorkspacePreflightError) as exc_info:
        preflight_spider2_workspace(
            task_id="spider2-fixture-001",
            workspace=tmp_path,
            db_name="spider2-fixture-001",
        )

    payload = exc_info.value.payload
    assert payload["status"] == "failed"
    assert payload["reason"] == "duckdb inspection failed"
    assert "error" in payload


def test_empty_duckdb_with_no_user_tables_fails(tmp_path: Path) -> None:
    _write_duckdb(tmp_path / "empty.duckdb", set())

    with pytest.raises(Spider2WorkspacePreflightError) as exc_info:
        preflight_spider2_workspace(task_id="t", workspace=tmp_path)

    assert exc_info.value.payload["reason"] == "no user tables present"


def test_dbt_source_metadata_required_tables_enforced(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    (models / "sources.yml").write_text(
        "\n".join(
            [
                "version: 2",
                "sources:",
                "  - name: canonical",
                "    tables:",
                "      - name: orders",
                "        identifier: raw_orders",
                "      - name: customers",
                "        identifier: raw_customers",
                "",
            ]
        )
    )

    # DuckDB missing raw_customers -> fails
    _write_duckdb(tmp_path / "db.duckdb", {"raw_orders"})
    with pytest.raises(Spider2WorkspacePreflightError) as exc_info:
        preflight_spider2_workspace(task_id="t", workspace=tmp_path)
    assert "raw_customers" in exc_info.value.payload["missing_tables"]

    # DuckDB with both -> passes
    (tmp_path / "db.duckdb").unlink()
    _write_duckdb(tmp_path / "db.duckdb", {"raw_orders", "raw_customers"})
    result = preflight_spider2_workspace(task_id="t", workspace=tmp_path)
    assert result["status"] == "passed"
    assert result["required_tables_source"] == "dbt_source_metadata"


def test_preflight_cli_exits_nonzero_and_emits_json_payload(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "razorback.benchmarks.spider2_dbt.preflight",
            "--task-id",
            "spider2-fixture-001",
            "--workspace",
            str(tmp_path),
            "--db-name",
            "spider2-fixture-001",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode == 2
    assert "RAZORBACK_SPIDER2_PREFLIGHT" in completed.stderr
    payload = json.loads(
        completed.stderr.split("RAZORBACK_SPIDER2_PREFLIGHT ", 1)[1]
    )
    assert payload["task_id"] == "spider2-fixture-001"
    assert payload["reason"] == "duckdb file missing"


def test_preflight_cli_passes_on_present_readable_duckdb(tmp_path: Path) -> None:
    _write_duckdb(tmp_path / "spider2-fixture-001.duckdb", {"orders"})

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "razorback.benchmarks.spider2_dbt.preflight",
            "--task-id",
            "spider2-fixture-001",
            "--workspace",
            str(tmp_path),
            "--db-name",
            "spider2-fixture-001",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode == 0
    assert "RAZORBACK_SPIDER2_PREFLIGHT" in completed.stdout
