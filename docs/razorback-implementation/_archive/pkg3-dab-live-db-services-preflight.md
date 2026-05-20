---
id: 8w41h6pvpc8zzhaag5txr8xa
title: PKG-3 — DAB live DB services + preflight (no more degraded-mode dump-file access)
status: backlog
source: CL 2026-05-19 — razorback's DAB adapter serves degraded-mode dump-file access; first-DAB-result 0.6746 is not comparable to upstream DAB
score: 1.0
started:
completed:
verdict:
worktree:
issue:
pr:
mod-block:
---

## Problem

Razorback's M2 DAB adapter today materializes single-service
docker-compose tasks (`dab-agent:latest` only) and bind-mounts the
DAB dataset's `query_dataset/` tree as-is. The agent gets the
**dump files** (`books_info.sql`, mongo bson dumps, etc.) and
sqlite databases.

This is the **degraded fallback shape**, not the canonical DAB
access path. Dataagentbench's `run_experiment.py:916-922`
documents this explicitly:

> The `sql_file:` field exists in some postgres entries as a
> **dump fallback for when the live postgres server is
> unreachable**. `prep_workspace()` does a preflight; if
> postgres is unreachable, preflight exits.

The canonical DAB shape is **multi-service docker-compose** with
`dab-postgres` + `dab-mongo` + `dab-agent` as siblings on a shared
`dab-net` network. The agent connects to the DBs via service
hostnames and `db_config.yaml`'s connection parameters. The dump
files are inputs to the DB-init scripts, not the agent's interface.

### Methodological implication for M5's 0.6746 result

The first-DAB-result `stratified_pass_at_1 = 0.6746` was produced
with the degraded shape. Claude in bookreview's `1.000` run almost
certainly grepped the `books_info.sql` file or loaded it into
sqlite/duckdb in-process, not queried a live postgres. The score
is **not directly comparable to dataagentbench's upstream
leaderboard** which evaluates against live DBs.

Already-shipped M5 snapshot at
`docs/razorback-implementation/m5-first-dab-result-summary.json`
needs a retroactive degraded-mode marker; the next snapshot taken
after PKG-3 lands is the first genuinely DAB-comparable result.

## Unlocks

- `experiments.smoke/full` produces DAB scores that ARE comparable
  to upstream DAB baselines.
- `per_trial_state_reset.compose_services` declaration becomes
  honest (today: DAB declares True per §6.5 but there are no
  compose services to reset, so the declaration is vacuous).
- The HAL reliability stack (PKG-4) can run robustness experiments
  against DAB with confidence that the underlying access shape
  matches what the leaderboard's other entries used.

## Acceptance criteria

**AC-1 — Razorback's `prepare.py` constructs multi-service
docker-compose for tasks whose `db_config.yaml` declares
postgres or mongo backends.**
Verified by: a unit test feeds a fixture `db_config.yaml` with
one postgres + one sqlite client (the bookreview shape) and
asserts the generated `docker-compose.yaml` declares:
  - `services.main` (dab-agent, as today)
  - `services.dab-postgres` with image `postgres:17` (or
    pinned version), `POSTGRES_DB` and `POSTGRES_USER` env
    matching `db_config.yaml`'s connection params
  - shared network (`dab-net` or per-task variant) wiring the
    services together
A second fixture with mongo backend asserts `services.dab-mongo`
with image `mongo:8` appears similarly.

**AC-2 — Dump files load into the live DBs at startup.**
Verified by: a unit test (or integration test against a real
postgres container) confirms `books_info.sql` is loaded into
`bookreview_db` via postgres's `docker-entrypoint-initdb.d/`
mechanism, so a `psql -c 'SELECT count(*) FROM books'` from
inside the agent container returns a positive number. Same
shape for mongo via `docker-entrypoint-initdb.d/*.js` or
`mongorestore`.

**AC-3 — Preflight: `pg_isready` + mongo ping before agent
setup; FAIL the trial with a typed `PreflightError` (new exit
code or reuse `HARBOR_RUNTIME=30`) if either is unhealthy.**
Verified by: a unit test patches the postgres container to
fail health-check; the trial fails with the typed error
naming "postgres unreachable" rather than letting the agent
get a connection-refused mid-task. A second test confirms
both healthy → preflight passes.

**AC-4 — Agent's `db_config.yaml` access works against the live
DB hostnames (`dab-postgres`, `dab-mongo`), not the dump files.**
Verified by: integration test against a live bookreview task
spawns the multi-service stack, the agent's connection
parameters point at `dab-postgres:5432` (not a file path), and
`psql --host dab-postgres -c "SELECT 1"` from inside the
agent container exits 0.

**AC-5 — Live `uv run rk run examples/specs/bookreview-claude.yaml`
produces a score that's genuinely DAB-comparable: the agent's
`agent/` subtree shows postgres-protocol connection evidence
(not file-grep evidence).**
Verified by: live invocation. Inspect the agent's stdout/stderr
or `events.jsonl`; cite a substring like `dab-postgres:5432`
or `psql` invocation in the agent's trajectory. The score
itself doesn't need to match M5's 0.6746 — it can be different
(better or worse), but it MUST come from a live-DB run.

**AC-6 — The M5 snapshot at
`docs/razorback-implementation/m5-first-dab-result-summary.json`
is retroactively marked as degraded-mode.**
Verified by: the snapshot gains a top-level field
`db_access_mode: "degraded_dump_files"` with an inline comment
or sibling note pointing at PKG-3 as the fix. A NEW snapshot
taken post-PKG-3 carries `db_access_mode: "live_services"`.

**AC-7 — `per_trial_state_reset.compose_services` declaration
is honest about the multi-service shape.**
Verified by: a unit test inspects the DAB adapter's declared
`per_trial_state_reset` and asserts `compose_services: True`
(was vacuously True before; now True because the multi-service
stack IS reset between trials) plus an assertion that the
compose stack actually torn down and re-up between trials.

**AC-8 — Carry-forward tests stay green.**
Verified by: `uv run pytest` from a clean checkout exits 0
with all prior tests passing alongside new PKG-3 tests.

## Test plan

- **Unit tests:** compose generation (postgres-only, mongo-only,
  hybrid, no-DB fixtures); preflight pg_isready + mongo ping
  (both happy + each unhealthy); db_config.yaml → connection-string
  mapping; per_trial reset shape.
- **Integration test:** live multi-service stack for one
  bookreview task (cost-bearing: ~$1-3 for one claude run);
  verifier reward.txt produced; agent's events.jsonl shows
  postgres-protocol traffic.
- **Acceptance command:** `uv run rk run examples/specs/
  bookreview-claude.yaml` exits 0 with live-DB access path
  confirmed in agent trajectory.

## Out of scope

- Re-running the full 6-dataset M5 acceptance to produce a
  PKG-3-era stratified score. That's a separate experiment-
  workflow entity once experiments/ is commissioned.
- Hardening dab-postgres/dab-mongo images (auth, TLS, etc.).
  DAB tasks run in an isolated docker network; default-creds
  are fine inside the network.
- Extending the live-services pattern to non-DAB benchmarks
  (ade-bench, etc.). Different adapter.
- Caching DB-init across trials. Each trial gets a fresh stack
  per §6.5's reset declaration.
- Re-cite M5's 0.6746 externally with the new asterisks. PKG-3
  produces the un-asterisked successor; the asterisked version
  remains for historical record.
