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

### External-oracle audit

Before passing, scan the analyze stage's tool-use trace
(`steps/main/agent/claude-code.txt` — the razorback equivalent of the
upstream DAB `claude-output.jsonl`) for evidence of forbidden external
lookups. The cell MUST be REJECTed with the offending event index if
the trace contains any of:

- `huggingface` (the host or the python library)
- `datasets.load_dataset` (or the bare `load_dataset(...)` after a
  `from datasets import load_dataset`)
- `hf://` URI references
- `from datasets import` Python imports (the import-layer attack the
  agnews cheating event used)
- `requests.get` to public data hosts
  (`raw.githubusercontent.com`, `huggingface.co`,
  `datasets-server.huggingface.co`, `api.github.com`, `kaggle.com`,
  `drive.google.com`)
- web-search tool invocations (`WebSearch`, `WebFetch`)
- LLM-call patterns asking another model for the answer
  (`openai.`, `anthropic.messages.create`, `google.generativeai.`)

The audit is mechanized by `razorback.agents.external_oracle_audit`.
Invoke it against the cell's run-dir:

    python -m razorback.agents.external_oracle_audit <cell-run-dir>

The exit-code contract mirrors the subagent smoke validator:

- `0` — clean. Proceed with the answer-shape check above.
- `2` — at least one confirmed forbidden pattern in the trace.
  REJECT the cell; the offending event indices are written to
  `<cell-run-dir>/external-oracle-audit.json` and surfaced in the
  dispatch ledger as `status: external-oracle-cheating`.
- `3` — `claude-code.txt` could not be located or parsed.
  REJECT the cell as `status: external-oracle-audit-error`.

The matrix dispatcher (`examples/drivers/dab-paper-matrix.sh`) runs
this gate automatically for every cell across all three variants
between `rk run` and `rk audit`. The verify-stage agent must treat a
non-zero exit as a REJECT and not write an answer that would otherwise
pass the answer-shape check.
