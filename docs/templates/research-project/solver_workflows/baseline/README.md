# ${slug} baseline solver workflow

The spacedock-solver agent reads this README per trial and follows
the stages below. Hypothesis variants copy this directory and edit
the prose.

## Stages

The workflow uses a three-stage solve loop:

1. **`model`** — read the task instruction and any workspace files.
   Identify the question shape (single-answer factoid, code patch,
   SQL query, etc.). State your assumptions explicitly.

2. **`analyze`** — produce a candidate answer (or candidate
   artifact: the patched file, the SQL output, the answer string).
   Stay inside the task workspace — do not consult external data
   sources or run pip-install of canonical-data libraries (see
   `## External-oracle audit` below).

3. **`verify`** — re-derive the answer independently. Sanity-check
   magnitudes, boundary conditions, join correctness, and the
   answer's match against the task's expected shape. Run the
   `## External-oracle audit` before passing.

Per spec §5.3 stage names become halt-resume keys when
stage-boundary-freeze mods ship.

## Reset declaration

Between trials, razorback resets:
- `agent_container` (the inner-agent Docker container)
- `host_workspace` (the per-trial workspace directory)
- `compose_services` (any sidecar services declared in `task.toml`)

Stateful learning across trials is intentionally not supported.

## External-oracle audit

Before the `verify` stage passes, scan the analyze-stage tool-use
trace for evidence of forbidden external lookups. Razorback's
`rk audit` (Layer 3, taint scanner at `src/razorback/audit/taint.py`)
codifies the same pattern catalog the matrix driver applies. Forbidden:

- `datasets.load_dataset(...)` / `from datasets import load_dataset`
  / `hf://...` — HuggingFace canonical-dataset lookups.
- `huggingface_hub` / `transformers` / `evaluate` library imports
  whose only purpose is to fetch canonical answer-key data.
- `requests.get` (or `curl` / `wget`) to canonical-data hosts
  (huggingface.co, raw.githubusercontent.com, kaggle.com, hub
  pages of the benchmark's published dataset).
- Web search invocations (`web_search`, `web.run`) and
  LLM-as-oracle patterns (asking another model "what is the answer
  to task X?").

NOT forbidden (per captain ruling 2026-05-23): `pip install` of
generic compute libraries (scikit-learn, pandas, numpy, scipy,
duckdb, …) that ship no canonical-data downloads. Razorback's
runtime `DISALLOWED_TOOLS` list at
`src/razorback/agents/claude_invoke.py` blocks the canonical-data
host downloads at the Bash tool layer; this prose deters the
remaining paths the runtime can't see.

If the audit finds a match, REJECT the verify stage with the
offending event index. The `rk audit --policy strict` post-run
sweep is the irrefutable backstop.

## ROLE prefix (optional)

If you want the inner agent to operate as a first-officer
dispatching subagent crews via the `Task` tool, set
`agent.append_system_prompt:` on the spec to a ROLE prefix
(e.g. "You are the first officer for this benchmark trial. Use
the `Task` tool to spawn subagent workers; read this workflow
README via the first-officer skill."). The `subagent-trace-manifest.json`
written post-run records the spawn count; the matrix driver
REJECTs cells with `captured == 0` for spacedock variants.

If left unset, the spacedock-solver runs as a single-agent loop
without subagent dispatch. Both shapes are valid; the choice
depends on benchmark.
