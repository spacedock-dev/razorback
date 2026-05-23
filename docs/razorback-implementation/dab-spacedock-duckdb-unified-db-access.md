---
id: 795chb59wrh37aj2gp5xappd
title: DAB spacedock — add duckdb-unified DB-access variant (postgres + mongo via ATTACH)
status: backlog
source: Captain directive 2026-05-23 — "does our dab spacedock support enforcing querying pg/mongo through duckdb?" + 2026-05-23 follow-up "phase 1 - make it a variant, not default"
started:
completed:
verdict:
score: 0.8
worktree:
issue:
pr:
mod-block:
---

## Problem

Razorback's spacedock variant of DAB at
`examples/solver_workflows/dab_paper_matrix/README.md` instructs the agent
to connect three separate query surfaces: `postgres on dab-postgres:5432`,
`mongo on dab-mongo:27017`, and `sqlite/duckdb under query_dataset/`.
Upstream dataagentbench's canonical workspace template at
`benchmark/workspace-readmes/workspace-readme.md` uses DuckDB as the single
query engine via `ATTACH ... (TYPE POSTGRES)` and
`ATTACH ... (TYPE MONGO)`. Convergence on the duckdb-unified pattern would
give the agent one query language (SQL through duckdb), make tool-use
traces uniform across datasets, and align with upstream's taint and
reproducibility design.

This entity does NOT replace the existing direct-driver solver workflow —
it adds a **sibling variant** so the two can be benchmarked head-to-head.
The choice of which variant to run is per-spec.

## Acceptance criteria

**AC-1 — A new solver workflow exists alongside the direct-driver one.**
A new file at
`examples/solver_workflows/dab_paper_matrix_duckdb/README.md` (or similar
slug) is added without touching
`examples/solver_workflows/dab_paper_matrix/README.md`. The new file
mirrors upstream's `workspace-readme.md` DB-Access section: a
`{{DUCKDB_CONNECT}}`-equivalent connect snippet, then
`ATTACH ... (TYPE SQLITE)`,
`INSTALL postgres; LOAD postgres; ATTACH 'host=dab-postgres port=5432 ...'
AS x (TYPE POSTGRES)`, and
`LOAD mongo; ATTACH 'mongodb://dab-mongo:27017/...' AS x (TYPE MONGO)`.
Verified by:
`test -f examples/solver_workflows/dab_paper_matrix_duckdb/README.md`;
`grep -F 'TYPE POSTGRES' examples/solver_workflows/dab_paper_matrix_duckdb/README.md`
matches; `grep -F 'TYPE POSTGRES' examples/solver_workflows/dab_paper_matrix/README.md`
returns empty (the original is untouched).

**AC-2 — Specs can select the variant via solver_workflow path.**
A new spec template (or generator switch) emits 12 spacedock spec cells
that point `solver_workflow:` at the new duckdb workflow. The existing
goal1 specs at `examples/specs/goal1/spacedock/*.yaml` remain pinned to
the direct-driver workflow.
Verified by: `generate-dab-paper-matrix-specs.py --solver-workflow duckdb`
(or equivalent flag) emits cells with `solver_workflow:
examples/solver_workflows/dab_paper_matrix_duckdb`; the original
`--solver-workflow spacedock` path is unchanged.

**AC-3 — Smoke on a pg-needing cell succeeds end-to-end via duckdb ATTACH.**
A one-cell smoke against `PATENTS` (sqlite + postgres) under the new
variant finishes with a populated `reward_per_query.json` and tool-use
trace shows the agent went through duckdb `ATTACH ... TYPE POSTGRES`
rather than `psycopg2.connect`. The cell does not require attempt-time
`INSTALL postgres` if the image-preinstall sibling entity has shipped;
otherwise it relies on attempt-time `INSTALL` working over `dab-net`.
Verified by: re-run `PATENTS.frozen.yaml` (duckdb variant) cell; inspect
the agent's `claude-code.txt` jsonl for `ATTACH 'host=dab-postgres`
events; confirm `reward_per_query.json` is populated.

**AC-4 — Smoke on a mongo-needing cell succeeds end-to-end via duckdb ATTACH.**
Same shape as AC-3 but for `agnews` (mongo + sqlite) or `yelp` (mongo +
duckdb). The agent attaches mongo through duckdb. If the duckdb mongo
extension cannot be downloaded over `dab-net` at attempt time (suspected
arm64 vs amd64 mismatch — probe showed HTTP 404 against
`extensions.duckdb.org/v1.5.3/linux_arm64/mongo.duckdb_extension.gz`),
this AC depends on the image-preinstall sibling entity having shipped.
Verified by: `yelp.frozen.yaml` (duckdb variant) cell completes with
populated `reward_per_query.json`; jsonl shows `ATTACH 'mongodb://dab-mongo`
events.

**AC-5 — Per-cell artifact shape is unchanged.**
Run dirs under the new variant emit the same `summary.json`,
`provenance.yaml`, `result.json`, `reward_per_query.json`, `score.json`
keys as the direct-driver variant. The harness contract is identical;
only the agent's in-container query path differs.
Verified by: schema diff (jq -r keys) on this entity's smoke run-dirs vs.
the cycle-2 `an` run-dirs is empty.

## Test plan

- **Mechanism smoke (independent of image-preinstall):** one `PATENTS`
  cell under the new variant on the current `dab-agent:latest` image
  (`INSTALL postgres` still works over `dab-net` public egress); confirm
  `ATTACH ... TYPE POSTGRES` in the trace and non-zero reward.
- **Mongo smoke:** one `yelp` cell. If attempt-time `INSTALL mongo`
  404s on the captain's M-series box (arm64 platform), pause this AC
  and resume after the image-preinstall sibling lands.
- **Head-to-head comparison:** post-shipment full-matrix run under the
  duckdb variant; compare 12-cell per-query rewards against the
  direct-driver cycle-1/2 baseline. The duckdb variant should be in the
  same ballpark; large divergences flag a prompt regression to
  investigate.

## Out of scope

- **Replacing the direct-driver variant.** Both variants coexist; the
  captain has not asked to deprecate the original.
- **Image-side preinstall** of duckdb extensions into
  `/opt/dab/duckdb_extensions/...`. Sibling entity (filed
  separately). Inherits upstream
  `scored-run-egress-taint-and-duckdb-preinstall` design from
  `~/git/dataagentbench/docs/harness/`.
- **direct-minimal / direct-structured duckdb variants.** Captain has
  not asked. File sibling entities if/when needed.

## Depends on

- **`an goal1-rerun-dab-spacedock-opus47-xhigh`**: should land first
  so the direct-driver 12/12 baseline is in place to compare against.
- **`1s runs-aggregate-single-score-reducer`**: the duckdb-variant
  matrix run's headline number needs the per-query reducer to be
  trustworthy.
- **Sibling: `dab-agent-image-duckdb-extension-preinstall`** (filed
  separately). Phase 1 of this entity ships independently; AC-4 may
  block on the sibling.

## Resume hook

When this lands, captains can opt into the duckdb-unified prompt per
spec. After head-to-head numbers settle, captain decides whether to
promote it to default or keep both.
