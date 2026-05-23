from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PREFLIGHT_LOG_PREFIX = "RAZORBACK_ADE_PREFLIGHT"


@dataclass(frozen=True)
class AdeTaskDataContract:
    family: str
    task_prefixes: tuple[str, ...]
    expected_db_name: str
    required_tables: frozenset[str]
    forbidden_tables: frozenset[str]


class AdeWorkspacePreflightError(RuntimeError):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(
            "ADE workspace preflight infrastructure failure: "
            + json.dumps(payload, sort_keys=True)
        )


_FAMILY_SENTINELS: dict[str, frozenset[str]] = {
    "airbnb": frozenset({"raw_hosts", "raw_listings", "raw_reviews"}),
    "f1": frozenset({"circuits", "drivers", "races", "results", "status"}),
    "quickbooks": frozenset(
        {"account_data", "bill_data", "invoice_data", "sales_receipt_data"}
    ),
}

_CONTRACTS: tuple[AdeTaskDataContract, ...] = (
    AdeTaskDataContract(
        family="airbnb",
        task_prefixes=("airbnb",),
        expected_db_name="airbnb",
        required_tables=_FAMILY_SENTINELS["airbnb"],
        forbidden_tables=_FAMILY_SENTINELS["f1"] | _FAMILY_SENTINELS["quickbooks"],
    ),
    AdeTaskDataContract(
        family="f1",
        task_prefixes=("f1",),
        expected_db_name="f1",
        required_tables=_FAMILY_SENTINELS["f1"],
        forbidden_tables=_FAMILY_SENTINELS["airbnb"] | _FAMILY_SENTINELS["quickbooks"],
    ),
    AdeTaskDataContract(
        family="quickbooks",
        task_prefixes=("quickbooks",),
        expected_db_name="quickbooks",
        required_tables=_FAMILY_SENTINELS["quickbooks"],
        forbidden_tables=_FAMILY_SENTINELS["airbnb"] | _FAMILY_SENTINELS["f1"],
    ),
)


def contract_for_task_id(task_id: str) -> AdeTaskDataContract | None:
    slug = _normalize_task_slug(task_id)
    for contract in sorted(
        _CONTRACTS,
        key=lambda c: max(map(len, c.task_prefixes)),
        reverse=True,
    ):
        if any(slug.startswith(prefix) for prefix in contract.task_prefixes):
            return contract
    return None


def preflight_script_text() -> str:
    return Path(__file__).read_text()


def preflight_ade_workspace(
    *,
    task_id: str,
    workspace: Path,
    db_name: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    contract = contract_for_task_id(task_id)
    if contract is None:
        return {
            "status": "skipped",
            "task_id": task_id,
            "reason": "no ADE workspace data contract for task family",
        }

    resolved_db_name = db_name or contract.expected_db_name
    resolved_db_path = (
        Path(db_path)
        if db_path is not None
        else Path(workspace) / f"{resolved_db_name}.duckdb"
    )
    required_tables, required_tables_source = _required_tables_for_workspace(
        workspace=Path(workspace),
        contract=contract,
    )
    payload = _base_payload(
        task_id=task_id,
        contract=contract,
        db_name=resolved_db_name,
        db_path=resolved_db_path,
        required_tables=required_tables,
        required_tables_source=required_tables_source,
    )

    if resolved_db_name != contract.expected_db_name:
        payload["db_name_mismatch"] = {
            "expected": contract.expected_db_name,
            "observed": resolved_db_name,
        }

    if not resolved_db_path.is_file():
        payload["status"] = "failed"
        payload["reason"] = "duckdb file missing"
        raise AdeWorkspacePreflightError(payload)

    try:
        observed_tables = _read_duckdb_tables(resolved_db_path)
    except Exception as exc:
        payload["status"] = "failed"
        payload["reason"] = "duckdb inspection failed"
        payload["error"] = repr(exc)
        raise AdeWorkspacePreflightError(payload) from exc
    missing_tables = sorted(required_tables - observed_tables)
    forbidden_tables_observed = sorted(contract.forbidden_tables & observed_tables)
    payload.update(
        {
            "observed_tables": sorted(observed_tables),
            "missing_tables": missing_tables,
            "forbidden_tables_observed": forbidden_tables_observed,
        }
    )

    if (
        payload.get("db_name_mismatch")
        or missing_tables
        or forbidden_tables_observed
    ):
        payload["status"] = "failed"
        raise AdeWorkspacePreflightError(payload)

    payload["status"] = "passed"
    return payload


def _normalize_task_slug(task_id: str) -> str:
    slug = task_id.strip().lower()
    for prefix in ("ade-bench-", "ade_bench_"):
        if slug.startswith(prefix):
            return slug[len(prefix) :]
    return slug


def _base_payload(
    *,
    task_id: str,
    contract: AdeTaskDataContract,
    db_name: str,
    db_path: Path,
    required_tables: frozenset[str],
    required_tables_source: str,
) -> dict[str, Any]:
    return {
        "status": "checking",
        "task_id": task_id,
        "family": contract.family,
        "expected_db_name": contract.expected_db_name,
        "db_name": db_name,
        "db_path": str(db_path),
        "required_tables": sorted(required_tables),
        "required_tables_source": required_tables_source,
        "forbidden_tables": sorted(contract.forbidden_tables),
        "observed_tables": [],
        "missing_tables": sorted(required_tables),
        "forbidden_tables_observed": [],
    }


def _required_tables_for_workspace(
    *,
    workspace: Path,
    contract: AdeTaskDataContract,
) -> tuple[frozenset[str], str]:
    metadata_tables = _read_dbt_source_tables(workspace)
    if metadata_tables:
        return frozenset(metadata_tables), "dbt_source_metadata"
    return contract.required_tables, "static_family_contract"


def _read_dbt_source_tables(workspace: Path) -> set[str]:
    """Read dbt `sources:` table names when the task ships source metadata."""
    try:
        import yaml
    except Exception:
        return set()

    tables: set[str] = set()
    for yaml_path in _iter_candidate_dbt_yaml_files(workspace):
        try:
            document = yaml.safe_load(yaml_path.read_text())
        except Exception:
            continue
        for source in _iter_dicts(_as_list(_as_dict(document).get("sources"))):
            for table in _iter_dicts(_as_list(source.get("tables"))):
                name = table.get("identifier") or table.get("name")
                if isinstance(name, str) and name.strip():
                    tables.add(name.strip().lower())
    return tables


def _iter_candidate_dbt_yaml_files(workspace: Path):
    if not workspace.is_dir():
        return
    excluded_parts = {".git", ".venv", "dbt_packages", "logs", "target"}
    for pattern in ("*.yml", "*.yaml"):
        for path in sorted(workspace.rglob(pattern)):
            if excluded_parts & set(path.relative_to(workspace).parts):
                continue
            yield path


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _iter_dicts(values: list[Any]):
    for value in values:
        if isinstance(value, dict):
            yield value


def _read_duckdb_tables(db_path: Path) -> set[str]:
    import duckdb

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            """
        ).fetchall()
    finally:
        conn.close()
    return {str(row[0]).lower() for row in rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ADE DuckDB workspace data.")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--workspace", type=Path, default=Path("/app"))
    parser.add_argument("--db-name")
    parser.add_argument("--db-path", type=Path)
    args = parser.parse_args(argv)

    try:
        payload = preflight_ade_workspace(
            task_id=args.task_id,
            workspace=args.workspace,
            db_name=args.db_name,
            db_path=args.db_path,
        )
    except AdeWorkspacePreflightError as exc:
        print(
            f"{PREFLIGHT_LOG_PREFIX} {json.dumps(exc.payload, sort_keys=True)}",
            file=sys.stderr,
        )
        return 2

    print(f"{PREFLIGHT_LOG_PREFIX} {json.dumps(payload, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
