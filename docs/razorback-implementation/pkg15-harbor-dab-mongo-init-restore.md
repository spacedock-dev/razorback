---
id: m7x4d2pkq8r3v6n9zwfgh1p2
title: PKG-15 — harbor-DAB mongo init mechanism (BSON restore on first start)
status: backlog
source: dab-mongo-probe report 2026-05-20 (commit 3987ca1); mongo path FAIL across agnews+yelp; agent loop 4/4 reward=0.0 with "empty answer" fingerprint
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Problem

The harbor-DAB plugin's mongo path is non-functional. The dab-mongo-probe (commit 3987ca1) confirmed across both candidate datasets (agnews mongo+sqlite, yelp mongo+duckdb) that:

**Bug 1 (CRITICAL) — mongo image only auto-executes `.sh` / `.js` in `/docker-entrypoint-initdb.d/`.** The plugin's compose generator (`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py:67-73`) mounts the BSON dump folder at that path. Mongo silently ignores `.bson` files; the database starts empty. Upstream DAB's `benchmark/setup.sh:165` uses an external `docker exec dab-mongo mongorestore --db "$db_name" /tmp/mongodump/"$db_name"` step exactly because mongo has no auto-restore for BSON.

Live mongosh evidence (from the probe):
```
$ docker compose exec -T dab-mongo mongosh --quiet --eval "db.getMongo().getDBNames()"
[ 'admin', 'config', 'local' ]
$ docker compose exec -T dab-mongo mongosh --quiet --eval "db.getSiblingDB('articles_db').articles.countDocuments({})"
0
$ docker compose exec -T dab-mongo ls /docker-entrypoint-initdb.d/agnews_articles/
articles_db   # BSON folder is mounted, but ignored by mongo init
```

Agent-loop confirmation (agnews N=1):
- q1 returns "empty answer" (direct fingerprint of querying empty collection)
- q2-q4 return plausible-but-wrong outputs (agent fabricates from priors or sqlite-only data)
- 4/4 reward=0.0, $0 subscription, 18m42s wall

**Bug 2 (MEDIUM) — mongo path has no reachability gate.** PKG-13 T5's reachability gate (`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`) is postgres-only by design (`_postgres_db_name` returns None for non-postgres datasets, and `_task_toml_body` skips the healthcheck block). Combined with Bug 1, failure is silent: compose looks healthy, the agent gets no signal that the DB is empty before it starts querying.

**Impact on Goal 1:** 2 of 12 DAB datasets (agnews + yelp) use mongo. Without PKG-15, those 2 must be skipped from the matrix. 10-of-12 yields 3 per-variant stratified-pass@1 numbers — meaningful but not the full paper-reproduction set. Captain's "1x is fine" directive can accept this for the first number-shipping cycle.

## Acceptance criteria

**AC-1 — mongo init runs `mongorestore` on first start.**
The compose generator emits an init mechanism that loads BSON dumps into mongo on first start. The chosen fix is one of (operator's call inside the plan stage):
- (a) Emit a `.sh` shim alongside the BSON dump folder. The shim runs `mongorestore --db <db_name> /docker-entrypoint-initdb.d/<dump_folder>/<db_name>`. mongo auto-runs the `.sh` and the dump loads.
- (b) Add a one-shot `init` service to the compose that depends on `dab-mongo` healthy, runs `mongorestore`, and exits 0. The `main` service then `depends_on: init: { condition: service_completed_successfully }`.
- (c) Add a per-step setup hook in the agent container that runs `mongorestore` against `dab-mongo` before the agent step begins.

Verified by: after `docker compose up`, `mongosh --eval "db.getSiblingDB('articles_db').articles.countDocuments({})"` returns the expected non-zero document count (agnews ≥ 120000 documents per upstream DAB's published count; yelp_business ≥ 150000 documents).

**AC-2 — mongo reachability gate emitted alongside postgres gate.**
The compose generator's reachability-gate step (postgres-only today per PKG-13 T5) is extended to emit a mongo health probe when the dataset declares `db_type: mongo`. The probe checks that the expected database has the expected collection AND at least one document, NOT just that mongo's TCP port is open (which Bug 1 showed is misleading).

Verified by: a unit test simulates a `db_type: mongo` dataset's task.toml and asserts the healthcheck shape includes a `mongosh --eval "db.getSiblingDB('<db>').getCollection('<coll>').countDocuments() > 0"` (or equivalent) probe before the agent step.

**AC-3 — agnews + yelp re-run produces honest results.**
After AC-1 + AC-2 ship, a re-run of the dab-mongo-probe's N=1 agnews trial produces rewards consistent with a model that DID see the real data. Specifically: q1 no longer returns "empty answer"; q2-q4 return values that EITHER match ground truth OR cite real data ranges from the live `articles` collection (not fabricated from priors). The reward distribution moves off all-zero.

Verified by: `uv run rk run examples/specs/probe-agnews-claude-harbor-dab.yaml --runs-dir _runs/probe-agnews-pkg15 --max-budget-usd-running 5` produces at least one non-zero reward across q1-q4 OR every verifier stdout shows the agent's output references real article content (not fabrication).

**AC-4 — yelp re-run produces honest results.**
Same as AC-3 but on yelp. The probe skipped the yelp agent loop because mechanism evidence was sufficient; PKG-15 must close yelp too because Goal 1's matrix includes both.

Verified by: same as AC-3 but for yelp's q1-q7.

**AC-5 — Goal 1 matrix on agnews + yelp is unblocked.**
With PKG-15 shipped, the Goal 1 dispatcher includes agnews + yelp in the 12-dataset matrix (the 12 datasets are: agnews, bookreview, crmarenapro, DEPS_DEV_V1, GITHUB_REPOS, googlelocal, music_brainz_20k, PANCANCER_ATLAS, PATENTS, stockindex, stockmarket, yelp). No matrix-side skip-list.

Verified by: `bash examples/drivers/dab-paper-matrix.sh --dry-run` lists all 12 datasets (no agnews/yelp skip).

**AC-6 — Plugin unit + integration tests cover the mongo init path.**
A new test in `packages/razorback-plugin-dab/tests/` exercises the mongo init mechanism end-to-end on a small fixture (or a real mongo dataset under a long-test marker). The test asserts the mongo DB is populated after compose-up.

Verified by: the test runs green in CI / `uv run pytest` and would fail if the AC-1 mechanism regressed (e.g., the .sh shim is dropped or the init service is removed).

## Test plan

- Plan stage selects the AC-1 fix shape ((a) .sh shim, (b) init service, or (c) per-step hook). Recommendation: (a) is lowest-complexity and matches the existing init.d auto-run contract; (b) is most surgical at the compose level; (c) leaks the restore step into the agent's task, which is undesirable.
- Implementation stage applies the chosen fix TDD-first; runs the existing 70+ plugin unit tests after each task.
- Validation stage runs the agnews + yelp N=1 smoke (AC-3, AC-4) and confirms the reward distribution moves off all-zero.

## Out of scope

- Generalizing to other not-yet-supported DAB datasets that might have similar issues with other DB engines (sqlite-only is file-backed and works; duckdb-only similarly). PKG-15 closes the mongo gap only.
- Optimizing mongo restore speed (mongorestore is usually fast enough; if it dominates wall-clock at matrix scale, that's a separate perf entity).
- Mongo-side volume reuse for cross-variant runs (analogous to PKG-14's postgres volume reuse AC-7..AC-11). PKG-15 ships single-trial-correctness first; a follow-up `pkg16-harbor-dab-mongo-volume-reuse` may be filed later if Goal 1 numbers prove the mongo subset matters.

## Depends on

- PKG-13 (DONE) — compose-loading + reachability-gate scaffolding lives on main; PKG-15 extends the gate scaffold to mongo.
- 51 phase2-dab-harbor-adapter (DONE) — plugin shape is the surface PKG-15 modifies.

## Blocks

- Goal 1's full 12-dataset matrix (agnews + yelp are in the 12; PKG-15 unblocks them). For Goal 1's first-number-shipping cycle, captain accepted 10-of-12 (skip mongo). PKG-15 closes that gap for a later full reproduction claim.
