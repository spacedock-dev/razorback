# ABOUTME: workspace/README.md renderer — three variants per PKG-9 carry-forward.
# ABOUTME: direct-minimal / direct-structured / spacedock.

from __future__ import annotations


WORKSPACE_VARIANTS = ("direct-minimal", "direct-structured", "spacedock")


_DIRECT_MINIMAL = """# Task

Answer the query in `query.json` using the databases described in
`db_config.yaml` and `db_description.txt`.

Write the final answer to `{workdir}/answers.json` as a JSON object:

    {{"answer": "<your answer as a single string>"}}

The verifier reads this file. Nothing else is graded.
"""

_DIRECT_STRUCTURED = """# Task

Answer the query in `query.json` using the databases described in
`db_config.yaml` and `db_description.txt`.

## Workspace layout

    {workdir}/
    ├── README.md             ← this file
    ├── query.json            ← the query you must answer
    ├── db_config.yaml        ← database connection details
    ├── db_description.txt    ← schema documentation
    ├── query_dataset/        ← raw data files (read-only)
    └── answers.json          ← write your final answer here

## Database access

Connect to each database declared in `db_config.yaml`:
- `postgres` clients: host `dab-postgres`, port 5432, user `postgres`, password `postgres`.
- `mongo` clients: host `dab-mongo`, port 27017.
- `sqlite` / `duckdb` clients: open the file under `query_dataset/`.

## Output contract

Write `{workdir}/answers.json` containing a single JSON object:

    {{"answer": "<your answer as a single string>"}}

The verifier reads this file. Nothing else is graded.
"""

_SPACEDOCK = """# Task

You are the first officer of the data-agent crew working a DataAgentBench
query. The workspace below contains the query, the schema, and the live
databases. Drive the analysis through the `model -> analyze -> verify`
stages and commit a final answer that survives an honest verifier.

## Workspace layout

    {workdir}/
    ├── README.md             ← this file
    ├── query.json            ← the query you must answer
    ├── db_config.yaml        ← database connection details
    ├── db_description.txt    ← schema documentation
    ├── query_dataset/        ← raw data files (read-only)
    └── answers.json          ← write your final answer here

## Database access

Connect to each database declared in `db_config.yaml`:
- `postgres` clients: host `dab-postgres`, port 5432, user `postgres`, password `postgres`.
- `mongo` clients: host `dab-mongo`, port 27017.
- `sqlite` / `duckdb` clients: open the file under `query_dataset/`.

## Output contract

Write `{workdir}/answers.json` containing a single JSON object:

    {{"answer": "<your answer as a single string>"}}

The verifier reads this file. Nothing else is graded.
"""


_TEMPLATES = {
    "direct-minimal": _DIRECT_MINIMAL,
    "direct-structured": _DIRECT_STRUCTURED,
    "spacedock": _SPACEDOCK,
}


def render_workspace_readme(
    *,
    variant: str,
    container_workdir: str,
) -> str:
    if variant not in _TEMPLATES:
        raise ValueError(
            f"unknown workspace_variant {variant!r}; expected one of {WORKSPACE_VARIANTS}"
        )
    return _TEMPLATES[variant].format(workdir=container_workdir)
