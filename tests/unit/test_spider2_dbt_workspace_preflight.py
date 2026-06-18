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
    resolve_spider2_db_name,
)


def _write_duckdb(path: Path, tables: set[str]) -> None:
    """Create user tables in the default (`main`) schema."""
    _write_duckdb_relations(path, {("main", table) for table in tables})


def _write_duckdb_relations(path: Path, relations: set[tuple[str, str]]) -> None:
    conn = duckdb.connect(str(path))
    try:
        for schema, table in sorted(relations):
            if schema != "main":
                conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            conn.execute(f'CREATE TABLE "{schema}"."{table}" (id INTEGER)')
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
    assert "main.orders" in result["observed_tables"]
    assert "main.customers" in result["observed_tables"]


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
                "    schema: main",
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
    assert "main.raw_customers" in exc_info.value.payload["missing_tables"]

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


# --- Finding 2 (cycle 2): source-table check must be schema-aware ----------


def test_source_table_in_wrong_schema_does_not_satisfy_source(tmp_path: Path) -> None:
    # A dbt source explicitly scoped to schema `main` must NOT be satisfied by
    # the same table name living in a different schema.
    models = tmp_path / "models"
    models.mkdir()
    (models / "sources.yml").write_text(
        "\n".join(
            [
                "version: 2",
                "sources:",
                "  - name: canonical",
                "    schema: main",
                "    tables:",
                "      - name: raw_orders",
                "",
            ]
        )
    )

    # raw_orders exists only under `other`, never under `main`.
    _write_duckdb_relations(tmp_path / "db.duckdb", {("other", "raw_orders")})

    with pytest.raises(Spider2WorkspacePreflightError) as exc_info:
        preflight_spider2_workspace(task_id="t", workspace=tmp_path)
    payload = exc_info.value.payload
    assert payload["status"] == "failed"
    assert payload["reason"] == "required dbt source tables missing"
    assert "main.raw_orders" in payload["missing_tables"]

    # Now place raw_orders in the expected `main` schema -> passes.
    (tmp_path / "db.duckdb").unlink()
    _write_duckdb_relations(tmp_path / "db.duckdb", {("main", "raw_orders")})
    result = preflight_spider2_workspace(task_id="t", workspace=tmp_path)
    assert result["status"] == "passed"
    assert result["required_tables_source"] == "dbt_source_metadata"


def test_source_schema_falls_back_to_source_level_schema(tmp_path: Path) -> None:
    # The table-level `schema`/`identifier` overrides win, but otherwise the
    # source-level `schema` (or source `name`) supplies the relation schema.
    models = tmp_path / "models"
    models.mkdir()
    (models / "sources.yml").write_text(
        "\n".join(
            [
                "version: 2",
                "sources:",
                "  - name: raw",
                "    schema: staging",
                "    tables:",
                "      - name: orders",
                "      - name: customers",
                "        schema: warehouse",
                "",
            ]
        )
    )

    _write_duckdb_relations(
        tmp_path / "db.duckdb",
        {("staging", "orders"), ("warehouse", "customers")},
    )
    result = preflight_spider2_workspace(task_id="t", workspace=tmp_path)
    assert result["status"] == "passed"
    assert "staging.orders" in result["required_tables"]
    assert "warehouse.customers" in result["required_tables"]


# --- Finding 1 (cycle 2): db_name resolution is an importable function ------


def test_resolve_db_name_from_profiles_path(tmp_path: Path) -> None:
    (tmp_path / "profiles.yml").write_text(
        "\n".join(
            [
                "example:",
                "  target: dev",
                "  outputs:",
                "    dev:",
                "      type: duckdb",
                "      path: warehouse.duckdb",
                "",
            ]
        )
    )
    assert resolve_spider2_db_name(tmp_path, task_slug="spider2-fixture-001") == "warehouse"


def test_resolve_db_name_from_single_duckdb_file(tmp_path: Path) -> None:
    _write_duckdb(tmp_path / "anything.duckdb", {"t1"})
    assert resolve_spider2_db_name(tmp_path, task_slug="spider2-fixture-001") == "anything"


def test_resolve_db_name_falls_back_to_task_slug(tmp_path: Path) -> None:
    assert (
        resolve_spider2_db_name(tmp_path, task_slug="spider2-fixture-001")
        == "spider2-fixture-001"
    )


def test_resolve_db_name_fails_closed_on_multi_db_with_no_profile(tmp_path: Path) -> None:
    _write_duckdb(tmp_path / "a.duckdb", {"t1"})
    _write_duckdb(tmp_path / "b.duckdb", {"t2"})
    with pytest.raises(Spider2WorkspacePreflightError) as exc_info:
        resolve_spider2_db_name(tmp_path, task_slug="spider2-fixture-001")
    payload = exc_info.value.payload
    assert payload["status"] == "failed"
    assert payload["reason"] == "ambiguous duckdb file"
    assert sorted(payload["candidates"]) == ["a.duckdb", "b.duckdb"]


def test_resolve_db_name_profile_pins_db_among_many(tmp_path: Path) -> None:
    # profiles.yml `path:` pins the DB even when several *.duckdb exist.
    _write_duckdb(tmp_path / "stale.duckdb", {"t1"})
    _write_duckdb(tmp_path / "warehouse.duckdb", {"t2"})
    (tmp_path / "profiles.yml").write_text(
        "\n".join(
            [
                "example:",
                "  outputs:",
                "    dev:",
                "      type: duckdb",
                "      path: /app/warehouse.duckdb",
                "  target: dev",
                "",
            ]
        )
    )
    assert resolve_spider2_db_name(tmp_path, task_slug="x") == "warehouse"
