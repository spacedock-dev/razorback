from __future__ import annotations

import argparse
import json
import re
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

    payload["observed_tables"] = sorted(_format_relations(observed_tables))

    required_tables = _read_dbt_source_tables(workspace)
    if required_tables:
        payload["required_tables"] = sorted(_format_relations(required_tables))
        payload["required_tables_source"] = "dbt_source_metadata"
        missing = sorted(_format_relations(required_tables - observed_tables))
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


def resolve_spider2_db_name(workspace: Path, *, task_slug: str) -> str:
    """Resolve the agent-facing DuckDB stem for `/app/<db_name>.duckdb`.

    This is the SHARED `/app/<db_name>.duckdb` contract: the build-time
    preflight (`harbor_view.py`) and the r5 verifier
    (`spider2-dbt-duckdb-match-verifier`) MUST import and reuse this exact
    resolution so all three agree on which DuckDB the agent operates against.

    Resolution order:
      1. The dbt `profiles.yml` active output's `path:` value — the active
         output is `outputs[target]` (dbt's own selection rule), not whichever
         output is listed first. Strip directories and the `.duckdb` suffix to
         get the stem. Fails closed when several outputs exist but `target:` is
         missing/unknown, or when the target output is non-DuckDB.
      2. Exactly one `*.duckdb` already present in the workspace — use its stem.
      3. The task slug (used as the DB name when the project ships nothing).

    Fails CLOSED (`Spider2WorkspacePreflightError`, reason `ambiguous duckdb
    file`) when >1 `*.duckdb` exists and no `profiles.yml` `path:` pins one, so
    a multi/stale-DB workspace never silently validates the wrong DB.
    """
    workspace = Path(workspace)

    profile_path = _read_profiles_db_path(workspace, task_slug=task_slug)
    if profile_path:
        return Path(profile_path).name.removesuffix(".duckdb")

    if workspace.is_dir():
        candidates = sorted(workspace.glob("*.duckdb"))
        if len(candidates) == 1:
            return candidates[0].name.removesuffix(".duckdb")
        if len(candidates) > 1:
            raise Spider2WorkspacePreflightError(
                {
                    "status": "failed",
                    "reason": "ambiguous duckdb file",
                    "task_id": task_slug,
                    "candidates": sorted(c.name for c in candidates),
                }
            )

    return task_slug


def _read_profiles_db_path(workspace: Path, *, task_slug: str) -> str | None:
    """Return the active dbt `profiles.yml` DuckDB output `path:`, if any.

    dbt selects the active output as `outputs[target]`, so this honors the
    profile's `target:` field rather than returning whichever output happens
    to be listed first. With multiple outputs the `target:` is REQUIRED and
    must name a DuckDB output:

      * a profile with exactly one output uses it (no `target:` needed);
      * a profile with several outputs and a `target:` returns
        `outputs[target]`'s DuckDB `path:`;
      * fail CLOSED (`Spider2WorkspacePreflightError`) when several outputs
        exist but `target:` is missing/unknown (`unresolved dbt target`), or
        when the target-selected output is not DuckDB (`target output not
        duckdb`) — never silently pin the wrong DB.

    Profiles whose active output ships no `.duckdb` `path:` contribute nothing
    here, leaving the single-glob / slug fallbacks in `resolve_spider2_db_name`
    to take over.
    """
    try:
        import yaml
    except Exception:
        return None
    if not workspace.is_dir():
        return None

    def _duckdb_path(output: dict[str, Any]) -> str | None:
        path = output.get("path")
        if isinstance(path, str) and path.strip().endswith(".duckdb"):
            return path.strip()
        return None

    for profiles_path in sorted(workspace.rglob("profiles.yml")):
        try:
            document = yaml.safe_load(profiles_path.read_text())
        except Exception:
            continue
        for profile in _iter_dicts(list(_as_dict(document).values())):
            outputs = _as_dict(profile.get("outputs"))
            output_dicts = {
                name: out for name, out in outputs.items() if isinstance(out, dict)
            }
            if not output_dicts:
                continue

            target = profile.get("target")
            if isinstance(target, str) and target.strip():
                target = target.strip()
                if target not in output_dicts:
                    raise Spider2WorkspacePreflightError(
                        {
                            "status": "failed",
                            "reason": "unresolved dbt target",
                            "task_id": task_slug,
                            "target": target,
                            "outputs": sorted(output_dicts),
                        }
                    )
                selected = output_dicts[target]
                path = _duckdb_path(selected)
                if path is None:
                    raise Spider2WorkspacePreflightError(
                        {
                            "status": "failed",
                            "reason": "target output not duckdb",
                            "task_id": task_slug,
                            "target": target,
                            "type": selected.get("type"),
                        }
                    )
                return path

            # No explicit target. A single output is unambiguous; preserve the
            # historical single-output fallback. With several outputs and no
            # target, dbt cannot pick one either -> fail closed.
            if len(output_dicts) == 1:
                (only_output,) = output_dicts.values()
                path = _duckdb_path(only_output)
                if path is not None:
                    return path
                continue
            raise Spider2WorkspacePreflightError(
                {
                    "status": "failed",
                    "reason": "unresolved dbt target",
                    "task_id": task_slug,
                    "target": None,
                    "outputs": sorted(output_dicts),
                }
            )
    return None


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


_SOURCE_CALL_RE = re.compile(
    r"""\bsource\s*\(\s*(['"])(?P<source>[^'"]+)\1\s*,\s*(['"])(?P<table>[^'"]+)\3\s*\)"""
)
_JINJA_IF_ELSE_RE = re.compile(
    r"""\{%\s*if\s+(?P<condition>.*?)\s*%\}(?P<true>.*?)\{%\s*else\s*%\}(?P<false>.*?)\{%\s*endif\s*%\}""",
    re.DOTALL,
)
_JINJA_EXPR_RE = re.compile(r"""\{\{\s*(?P<expr>.*?)\s*\}\}""", re.DOTALL)
_VAR_CALL_RE = re.compile(
    r"""^var\s*\(\s*(['"])(?P<name>[^'"]+)\1(?:\s*,\s*(?P<default>.*?))?\s*\)$""",
    re.DOTALL,
)


def _read_dbt_source_tables(workspace: Path) -> set[tuple[str, str]]:
    """Read dbt `sources:` as `(schema, table)` relations.

    The relation schema is resolved with dbt's precedence: a table-level
    `schema` overrides a source-level `schema`, which in turn defaults to the
    source `name` (dbt's documented default when a source omits `schema`). The
    table identifier follows the same `identifier`-over-`name` precedence.

    When the project contains static `source('source_name', 'table_name')`
    references, only those referenced declarations are required. Some upstream
    Spider2 exports carry stale or duplicate source metadata for tables that no
    model reads; failing the image build on those unused declarations rejects an
    otherwise runnable task. If no static references are found, fall back to
    enforcing every declared source table. Both relation parts are lowercased to
    match `_read_duckdb_tables`.
    """
    try:
        import yaml
    except Exception:
        return set()

    referenced_sources = _read_referenced_source_names(workspace)
    render_context = _read_dbt_render_context(workspace, yaml)
    relations: set[tuple[str, str]] = set()
    for yaml_path in _iter_candidate_dbt_yaml_files(workspace):
        try:
            document = yaml.safe_load(yaml_path.read_text())
        except Exception:
            continue
        for source in _iter_dicts(_as_list(_as_dict(document).get("sources"))):
            source_name = source.get("name")
            source_schema = source.get("schema") or source_name
            source_external_location = _as_dict(source.get("meta")).get(
                "external_location"
            )
            for table in _iter_dicts(_as_list(source.get("tables"))):
                table_name = table.get("name")
                if not (
                    isinstance(source_name, str)
                    and source_name.strip()
                    and isinstance(table_name, str)
                    and table_name.strip()
                ):
                    continue
                source_key = (source_name.strip().lower(), table_name.strip().lower())
                if referenced_sources and source_key not in referenced_sources:
                    continue
                table_external_location = _as_dict(table.get("meta")).get(
                    "external_location"
                )
                if source_external_location or table_external_location:
                    continue
                name = table.get("identifier") or table_name
                schema = table.get("schema") or source_schema
                if not (
                    isinstance(name, str)
                    and name.strip()
                    and isinstance(schema, str)
                    and schema.strip()
                ):
                    continue
                name = _render_dbt_metadata_value(name, render_context)
                schema = _render_dbt_metadata_value(schema, render_context)
                if "{{" in name or "{%" in name or "{{" in schema or "{%" in schema:
                    continue
                relations.add((schema.strip().lower(), name.strip().lower()))
    return relations


def _read_referenced_source_names(workspace: Path) -> set[tuple[str, str]]:
    """Return static dbt source references as `(source_name, table_name)` pairs."""
    if not workspace.is_dir():
        return set()

    referenced: set[tuple[str, str]] = set()
    excluded_parts = {".git", ".venv", "dbt_packages", "logs", "target"}
    for sql_path in sorted(workspace.rglob("*.sql")):
        if excluded_parts & set(sql_path.relative_to(workspace).parts):
            continue
        try:
            text = sql_path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        for match in _SOURCE_CALL_RE.finditer(text):
            referenced.add(
                (
                    match.group("source").strip().lower(),
                    match.group("table").strip().lower(),
                )
            )
    return referenced


def _read_dbt_render_context(workspace: Path, yaml_module: Any) -> dict[str, Any]:
    context: dict[str, Any] = {
        "vars": {},
        "target": {"schema": "main"},
    }

    project_path = workspace / "dbt_project.yml"
    if project_path.is_file():
        try:
            document = yaml_module.safe_load(project_path.read_text())
        except Exception:
            document = None
        vars_value = _as_dict(_as_dict(document).get("vars"))
        context["vars"] = _flatten_dbt_vars(vars_value)

    target_schema = _read_profiles_target_schema(workspace, yaml_module)
    if target_schema:
        context["target"]["schema"] = target_schema

    return context


def _flatten_dbt_vars(value: dict[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, child in value.items():
        if not isinstance(key, str):
            continue
        flattened[key] = child

    for child in value.values():
        if not isinstance(child, dict):
            continue
        for key, nested_child in child.items():
            if isinstance(key, str) and key not in flattened:
                flattened[key] = nested_child
    return flattened


def _read_profiles_target_schema(workspace: Path, yaml_module: Any) -> str | None:
    for profiles_path in sorted(workspace.rglob("profiles.yml")):
        try:
            document = yaml_module.safe_load(profiles_path.read_text())
        except Exception:
            continue
        for profile in _iter_dicts(list(_as_dict(document).values())):
            outputs = {
                name: out
                for name, out in _as_dict(profile.get("outputs")).items()
                if isinstance(out, dict)
            }
            if not outputs:
                continue

            target = profile.get("target")
            selected = None
            if isinstance(target, str) and target.strip() in outputs:
                selected = outputs[target.strip()]
            elif len(outputs) == 1:
                (selected,) = outputs.values()

            schema = _as_dict(selected).get("schema")
            if isinstance(schema, str) and schema.strip():
                return schema.strip()
    return None


def _render_dbt_metadata_value(value: str, context: dict[str, Any]) -> str:
    text = value
    while True:
        match = _JINJA_IF_ELSE_RE.search(text)
        if match is None:
            break
        replacement = (
            match.group("true")
            if _eval_dbt_condition(match.group("condition"), context)
            else match.group("false")
        )
        text = text[: match.start()] + replacement + text[match.end() :]

    return _JINJA_EXPR_RE.sub(
        lambda match: _stringify_dbt_value(
            _eval_dbt_expr(match.group("expr"), context)
        ),
        text,
    )


def _eval_dbt_condition(expr: str, context: dict[str, Any]) -> bool:
    value = _eval_dbt_expr(expr, context)
    if isinstance(value, str):
        return value.lower() not in {"", "0", "false", "none", "null"}
    return bool(value)


def _eval_dbt_expr(expr: str, context: dict[str, Any]) -> Any:
    parts = [part.strip() for part in expr.split("~")]
    if len(parts) > 1:
        return "".join(
            _stringify_dbt_value(_eval_dbt_expr(part, context)) for part in parts
        )

    value = expr.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if value == "target.schema":
        return _as_dict(context.get("target")).get("schema", "main")
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    var_match = _VAR_CALL_RE.match(value)
    if var_match:
        var_name = var_match.group("name")
        vars_value = _as_dict(context.get("vars"))
        if var_name in vars_value:
            return vars_value[var_name]
        default = var_match.group("default")
        if default is not None:
            return _eval_dbt_expr(default, context)
        return ""

    return value


def _stringify_dbt_value(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return ""
    return str(value)


def _format_relations(relations: set[tuple[str, str]]) -> list[str]:
    return [f"{schema}.{table}" for schema, table in relations]


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


def _read_duckdb_tables(db_path: Path) -> set[tuple[str, str]]:
    import duckdb

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            """
        ).fetchall()
    finally:
        conn.close()
    return {(str(row[0]).lower(), str(row[1]).lower()) for row in rows}


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
