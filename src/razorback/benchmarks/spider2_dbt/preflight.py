from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PREFLIGHT_LOG_PREFIX = "RAZORBACK_SPIDER2_PREFLIGHT"


class Spider2WorkspacePreflightError(RuntimeError):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(
            "spider2-dbt workspace preflight infrastructure failure: "
            + json.dumps(payload, sort_keys=True)
        )


def preflight_script_text() -> str:
    return Path(__file__).read_text()


def preflight_spider2_workspace(
    *,
    task_id: str,
    workspace: Path,
    db_name: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Validate the source DuckDB a spider2-dbt agent will operate against.

    spider2-dbt has no fixed task families, so this validates *structural*
    properties — the file is present, openable as a DuckDB, declares at least
    one user table, and (when the dbt project ships `sources:` metadata)
    contains every declared source table. It fails closed with a named error
    so a bad source DuckDB fails the image build rather than the agent run.
    """
    workspace = Path(workspace)
    resolved_db_path = _resolve_db_path(
        workspace=workspace, db_name=db_name, db_path=db_path
    )
    payload: dict[str, Any] = {
        "status": "checking",
        "task_id": task_id,
        "db_name": db_name,
        "db_path": str(resolved_db_path) if resolved_db_path is not None else None,
        "observed_tables": [],
        "required_tables": [],
        "required_tables_source": None,
        "missing_tables": [],
    }

    if resolved_db_path is None or not resolved_db_path.is_file():
        payload["status"] = "failed"
        payload["reason"] = "duckdb file missing"
        raise Spider2WorkspacePreflightError(payload)

    try:
        observed_tables = _read_duckdb_tables(resolved_db_path)
    except Exception as exc:
        payload["status"] = "failed"
        payload["reason"] = "duckdb inspection failed"
        payload["error"] = repr(exc)
        raise Spider2WorkspacePreflightError(payload) from exc

    payload["observed_tables"] = sorted(observed_tables)

    required_tables = _read_dbt_source_tables(workspace)
    if required_tables:
        payload["required_tables"] = sorted(required_tables)
        payload["required_tables_source"] = "dbt_source_metadata"
        missing = sorted(required_tables - observed_tables)
        payload["missing_tables"] = missing
        if missing:
            payload["status"] = "failed"
            payload["reason"] = "required dbt source tables missing"
            raise Spider2WorkspacePreflightError(payload)
    elif not observed_tables:
        payload["status"] = "failed"
        payload["reason"] = "no user tables present"
        raise Spider2WorkspacePreflightError(payload)

    payload["status"] = "passed"
    return payload


def _resolve_db_path(
    *, workspace: Path, db_name: str | None, db_path: Path | None
) -> Path | None:
    if db_path is not None:
        return Path(db_path)
    if db_name:
        return workspace / f"{db_name}.duckdb"
    if workspace.is_dir():
        candidates = sorted(workspace.glob("*.duckdb"))
        if candidates:
            return candidates[0]
    return None


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
    parser = argparse.ArgumentParser(
        description="Validate spider2-dbt DuckDB workspace data."
    )
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--workspace", type=Path, default=Path("/app"))
    parser.add_argument("--db-name")
    parser.add_argument("--db-path", type=Path)
    args = parser.parse_args(argv)

    try:
        payload = preflight_spider2_workspace(
            task_id=args.task_id,
            workspace=args.workspace,
            db_name=args.db_name,
            db_path=args.db_path,
        )
    except Spider2WorkspacePreflightError as exc:
        print(
            f"{PREFLIGHT_LOG_PREFIX} {json.dumps(exc.payload, sort_keys=True)}",
            file=sys.stderr,
        )
        return 2

    print(f"{PREFLIGHT_LOG_PREFIX} {json.dumps(payload, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
