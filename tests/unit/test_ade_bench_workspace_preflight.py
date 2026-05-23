from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from razorback.benchmarks.ade_bench.preflight import (
    AdeWorkspacePreflightError,
    contract_for_task_id,
    preflight_ade_workspace,
)


def _write_duckdb(path: Path, tables: set[str]) -> None:
    conn = duckdb.connect(str(path))
    try:
        for table in sorted(tables):
            conn.execute(f'CREATE TABLE "{table}" (id INTEGER)')
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("task_id", "db_name", "tables"),
    [
        ("airbnb001", "airbnb", {"raw_hosts", "raw_listings", "raw_reviews"}),
        ("f1001", "f1", {"circuits", "drivers", "races", "results", "status"}),
        (
            "quickbooks001",
            "quickbooks",
            {"account_data", "bill_data", "invoice_data", "sales_receipt_data"},
        ),
    ],
)
def test_known_ade_family_duckdb_tables_pass_contract(
    tmp_path: Path, task_id: str, db_name: str, tables: set[str]
) -> None:
    _write_duckdb(tmp_path / f"{db_name}.duckdb", tables)

    result = preflight_ade_workspace(
        task_id=task_id,
        workspace=tmp_path,
        db_name=db_name,
    )

    assert result["status"] == "passed"
    assert result["task_id"] == task_id
    assert result["db_name"] == db_name
    assert result["missing_tables"] == []
    assert result["required_tables_source"] == "static_family_contract"
    assert set(result["required_tables"]) <= set(result["observed_tables"])


def test_dbt_source_metadata_overrides_static_family_contract(tmp_path: Path) -> None:
    project_dir = tmp_path / "models"
    project_dir.mkdir()
    (project_dir / "sources.yml").write_text(
        "\n".join(
            [
                "version: 2",
                "sources:",
                "  - name: canonical_airbnb",
                "    tables:",
                "      - name: hosts",
                "        identifier: raw_hosts",
                "      - name: listings",
                "        identifier: raw_listings",
                "      - name: reviews",
                "        identifier: raw_reviews",
                "      - name: neighbourhoods",
                "        identifier: raw_neighbourhoods",
                "",
            ]
        )
    )
    _write_duckdb(
        tmp_path / "airbnb.duckdb",
        {"raw_hosts", "raw_listings", "raw_reviews", "raw_neighbourhoods"},
    )

    result = preflight_ade_workspace(task_id="airbnb001", workspace=tmp_path)

    assert result["status"] == "passed"
    assert result["required_tables_source"] == "dbt_source_metadata"
    assert result["required_tables"] == [
        "raw_hosts",
        "raw_listings",
        "raw_neighbourhoods",
        "raw_reviews",
    ]


def test_cross_family_duckdb_fails_closed_with_diagnostics(tmp_path: Path) -> None:
    _write_duckdb(
        tmp_path / "f1.duckdb",
        {"account_data", "bill_data", "invoice_data", "sales_receipt_data"},
    )

    with pytest.raises(AdeWorkspacePreflightError) as exc_info:
        preflight_ade_workspace(task_id="f1001", workspace=tmp_path, db_name="f1")

    payload = exc_info.value.payload
    assert "infrastructure failure" in str(exc_info.value)
    assert payload["task_id"] == "f1001"
    assert payload["family"] == "f1"
    assert {"circuits", "drivers", "races", "results"} <= set(
        payload["missing_tables"]
    )
    assert {"account_data", "bill_data", "invoice_data"} <= set(
        payload["forbidden_tables_observed"]
    )


def test_missing_duckdb_fails_closed_with_task_and_db_name(tmp_path: Path) -> None:
    with pytest.raises(AdeWorkspacePreflightError) as exc_info:
        preflight_ade_workspace(task_id="quickbooks001", workspace=tmp_path)

    payload = exc_info.value.payload
    assert payload["task_id"] == "quickbooks001"
    assert payload["db_name"] == "quickbooks"
    assert payload["status"] == "failed"
    assert "quickbooks.duckdb" in payload["db_path"]


def test_preflight_cli_exits_nonzero_and_emits_json_payload(tmp_path: Path) -> None:
    contract = contract_for_task_id("f1001")
    assert contract is not None
    _write_duckdb(tmp_path / "f1.duckdb", {"account_data", "bill_data"})

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "razorback.benchmarks.ade_bench.preflight",
            "--task-id",
            "f1001",
            "--workspace",
            str(tmp_path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert completed.returncode == 2
    assert "RAZORBACK_ADE_PREFLIGHT" in completed.stderr
    payload = json.loads(completed.stderr.split("RAZORBACK_ADE_PREFLIGHT ", 1)[1])
    assert payload["task_id"] == "f1001"
    assert payload["expected_db_name"] == "f1"
    assert "circuits" in payload["missing_tables"]
