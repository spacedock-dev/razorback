# ABOUTME: workspace/README.md renderer — three variants per PKG-9 carry-forward.
# ABOUTME: direct-minimal / direct-structured / spacedock.

from __future__ import annotations


WORKSPACE_VARIANTS = ("spacedock", "direct-structured", "direct-minimal")


_DIRECT_MINIMAL = """# Task

Answer the query in `query.json` using the databases described in
`db_config.yaml` and `db_description.txt`.

Write the final answer to `{workdir}/answers.json` as a JSON object:

    {{"answer": "<your answer as a single string>"}}

The verifier reads this file. Nothing else is graded.

## Rules

**Use only the workspace data.** The benchmark provides everything needed to answer the query in the workspace's databases (`db_config.yaml`, attached SQLite/PostgreSQL/MongoDB/DuckDB sources). Do **not** consult external data sources to look up answer values, labels, or ground truth — even if the workspace data appears to come from a public dataset. Specifically forbidden:
- HuggingFace `datasets` library (`datasets.load_dataset`, `hf://...`) for label/oracle lookup
- Public CSV/JSON downloads of the same dataset (kaggle, GitHub, vendor sites)
- Web search engines, search APIs, or LLM-as-oracle calls (e.g., asking another model "what is the answer to X")
- Cached prior answers from earlier runs or any artifacts outside the current workspace

The workspace databases are the only authoritative source. If a question is unanswerable from them, return `"UNABLE TO DETERMINE"`.
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

## Rules

**Use only the workspace data.** The benchmark provides everything needed to answer the query in the workspace's databases (`db_config.yaml`, attached SQLite/PostgreSQL/MongoDB/DuckDB sources). Do **not** consult external data sources to look up answer values, labels, or ground truth — even if the workspace data appears to come from a public dataset. Specifically forbidden:
- HuggingFace `datasets` library (`datasets.load_dataset`, `hf://...`) for label/oracle lookup
- Public CSV/JSON downloads of the same dataset (kaggle, GitHub, vendor sites)
- Web search engines, search APIs, or LLM-as-oracle calls (e.g., asking another model "what is the answer to X")
- Cached prior answers from earlier runs or any artifacts outside the current workspace

The workspace databases are the only authoritative source. If a question is unanswerable from them, return `"UNABLE TO DETERMINE"`.

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

## Rules

**Use only the workspace data.** The benchmark provides everything needed to answer the query in the workspace's databases (`db_config.yaml`, attached SQLite/PostgreSQL/MongoDB/DuckDB sources). Do **not** consult external data sources to look up answer values, labels, or ground truth — even if the workspace data appears to come from a public dataset. Specifically forbidden:
- HuggingFace `datasets` library (`datasets.load_dataset`, `hf://...`) for label/oracle lookup
- Public CSV/JSON downloads of the same dataset (kaggle, GitHub, vendor sites)
- Web search engines, search APIs, or LLM-as-oracle calls (e.g., asking another model "what is the answer to X")
- Cached prior answers from earlier runs or any artifacts outside the current workspace

The workspace databases are the only authoritative source. If a question is unanswerable from them, return `"UNABLE TO DETERMINE"`.

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
