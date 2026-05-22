# DAB paper matrix solver workflow

Solver workflow for the Goal 1 paper-matrix spacedock variant. One trial per
dataset; the spacedock variant drives the `model -> analyze -> verify`
crew loop and commits a final answer to `answers.json`.

## Stages

- model
- analyze
- verify

## Stage: model

Read `query.json`, `db_config.yaml`, and `db_description.txt`. Understand the
question and the database schema. Plan the query strategy without executing
yet. Write a one-paragraph plan to working memory.

## Stage: analyze

Execute the planned queries against the live databases. Use the connection
details in `db_config.yaml` (postgres on `dab-postgres:5432`, mongo on
`dab-mongo:27017`, sqlite/duckdb under `query_dataset/`). Aggregate results
into a single candidate answer.

## Stage: verify

Re-read `query.json`. Confirm the candidate answer matches the question
shape (single string). Write the final answer to `answers.json`:

    {"answer": "<your answer as a single string>"}

The verifier reads this file. Nothing else is graded.
