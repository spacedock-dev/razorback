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
- `requests.get` / `curl` / `wget` to public data hosts
- `pip install` of one of the named canonical-data libraries:
  `datasets`, `huggingface_hub`, `transformers`, `evaluate`
  (generic compute libraries like `rapidfuzz`, `scikit-learn`,
  `duckdb`, `numpy`, `pandas` are CLEAN)
- `huggingface-cli` or `hf` binary invocations
- web-search tool invocations (`WebSearch`, `WebFetch`,
  upstream `web_search` / `web.run`)
- LLM-call patterns asking another model for the answer

The audit is mechanized by `rk audit --policy strict`, which delegates
to `razorback.audit.taint` (the shared taint scanner, ported from
upstream DAB with razorback divergences) and
`razorback.audit.claude_code` (the claude-cli trace adapter). Invoke
it against the cell's run-dir:

    uv run rk audit <cell-run-dir> --policy strict --format json

The exit-code contract:

- `0` — clean. Proceed with the answer-shape check above.
- `23` — at least one trial in the cell tainted by a forbidden
  lookup (the `TAINT_FINDINGS` exit). REJECT the cell; the
  offending findings are written to `<cell-run-dir>/audit.json`
  and surfaced in the dispatch ledger as
  `status: external-oracle-cheating`.
- any other non-zero — audit could not run cleanly (trace missing,
  scanner error, etc.). REJECT the cell as
  `status: external-oracle-audit-error`.

The matrix dispatcher (`examples/drivers/dab-paper-matrix.sh`) runs
this gate automatically for every cell across all three variants
between `rk run` and `rk score`. The verify-stage agent must treat a
non-zero exit as a REJECT and not write an answer that would otherwise
pass the answer-shape check.
