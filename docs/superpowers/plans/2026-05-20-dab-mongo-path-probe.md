# DAB MongoDB path probe — harbor-DAB plugin

Date: 2026-05-20
Branch: spacedock-ensign/dab-mongo-probes (forked from PKG-13 branch)
Sibling worker: PKG-13 validation (do not touch).

## Verdict

**FAIL** across both candidates (`agnews`, `yelp`). Two real bugs surfaced. Mongo path is not viable for the 12-dataset matrix as currently implemented. PKG-13 closed the postgres path (bookreview 9/9 reward=1.0); mongo needs a follow-up entity before Goal 1's matrix can include mongo datasets.

Recommended follow-up entity slug: **`pkg15-harbor-dab-mongo-init-restore`** (compose generator + setup hook layer).

## Phase 1 — mongo dataset inventory

Scanned `/Users/clkao/git/dataagentbench/data/query_*/db_config.yaml`. Datasets that declare a `db_type: mongo` client:

| Dataset           | Path                                                              | Backends declared |
|-------------------|-------------------------------------------------------------------|-------------------|
| `agnews`          | `data/query_agnews/db_config.yaml`                                | mongo + sqlite    |
| `yelp`            | `data/query_yelp/db_config.yaml`                                  | mongo + duckdb    |

No mongo-only and no postgres+mongo hybrid datasets exist. Both candidates pair mongo with a file-backed engine (sqlite/duckdb) that does not require a compose service. From the compose-generator's perspective these are mongo-only stacks.

Probed candidates: both (procedure allowed up to 2).

## Phase 2 — Generation evidence (read-only)

### agnews

- Task tree: `_runs/probe-agnews/tasks/agnews-q{1..4}/` generated via `razorback-plugin-dab generate --datasets agnews --workspace-variant direct-minimal`.
- Spec: `examples/specs/probe-agnews-claude-harbor-dab.yaml`.
- `.compose-services.json`:
  ```json
  {"compose_file": "docker-compose.yaml", "services": ["dab-mongo", "main"]}
  ```
  Confirms the AC-2 evidence shape from PKG-13 T3: compose was emitted with `dab-mongo`.
- `task.toml` has **no `[steps.healthcheck]`** for mongo (compare with bookreview's postgres TCP probe). The reachability gate added in PKG-13 T5 is postgres-only by design (`_postgres_db_name` in `prepare.py` returns `None` for non-postgres datasets, and `_task_toml_body` skips the healthcheck block).
- Compose `volumes` for `dab-mongo` mounts `../steps/main/workdir/query_dataset/agnews_articles:/docker-entrypoint-initdb.d/agnews_articles:ro`.
- Stratum sidecar tags `{"backends": ["mongo", "sqlite"]}` per-query.

### yelp

- Task tree: `_runs/probe-yelp/tasks/yelp-q{1..7}/`.
- Spec: `examples/specs/probe-yelp-claude-harbor-dab.yaml`.
- `.compose-services.json`:
  ```json
  {"compose_file": "docker-compose.yaml", "services": ["dab-mongo", "main"]}
  ```
- Compose mounts `../steps/main/workdir/query_dataset/yelp_business:/docker-entrypoint-initdb.d/yelp_business:ro`.

## Phase 3 — Mechanism check (docker compose up, no agent)

For each candidate I brought up the compose stack and queried mongo directly to verify whether the database was populated.

### agnews-q1 mechanism check

```
$ docker compose up -d  # dab-mongo Healthy after auto-init
$ docker compose exec -T dab-mongo mongosh --quiet --eval "db.getMongo().getDBNames()"
[ 'admin', 'config', 'local' ]
$ docker compose exec -T dab-mongo mongosh --quiet --eval "db.getSiblingDB('articles_db').getCollectionNames()"
[]
$ docker compose exec -T dab-mongo mongosh --quiet --eval "db.getSiblingDB('articles_db').articles.countDocuments({})"
0
$ docker compose exec -T dab-mongo ls /docker-entrypoint-initdb.d/agnews_articles/
articles_db   # BSON dump folder is mounted, but mongo init ignored it
```

The bind-mount lands correctly inside the container at `/docker-entrypoint-initdb.d/agnews_articles/articles_db/articles.bson`, but `articles_db` does not exist in mongo and zero documents are loaded.

### yelp-q1 mechanism check

Same compose-up + mongosh probe:

```
$ docker compose exec -T dab-mongo mongosh --quiet --eval "db.getMongo().getDBNames()"
[ 'admin', 'config', 'local' ]
$ docker compose exec -T dab-mongo mongosh --quiet --eval "db.getSiblingDB('yelp_db').getCollectionNames()"
[]
$ docker compose exec -T dab-mongo mongosh --quiet --eval "db.getSiblingDB('yelp_db').business.countDocuments({})"
0
```

Same outcome: empty database, zero documents.

## Phase 3 (cont.) — agent-loop smoke (agnews only)

`uv run rk run examples/specs/probe-agnews-claude-harbor-dab.yaml --runs-dir _runs/probe-agnews --max-budget-usd-running 5`

Results (4 trials, all reward=0.0, cost via subscription so $0, total wallclock 18m42s, ~4.7m/trial well under the 15-min target):

| Trial        | reward | Verifier stdout                                                                          |
|--------------|-------:|------------------------------------------------------------------------------------------|
| agnews-q1    | 0.0    | `empty answer`                                                                            |
| agnews-q2    | 0.0    | `Ground truth '0.14414414414414414' (tol=0.0001) not found in LLM output: 8/37`           |
| agnews-q3    | 0.0    | `Ground truth numeric value '336.6363636363636' (tol=0.01) not found in LLM output: 330.36` |
| agnews-q4    | 0.0    | `Ground truth 'Africa' not found in LLM output: South America`                            |

q1 returning "empty answer" is the direct fingerprint of an agent that queried the mongo collection, got no documents, and surrendered. q2-q4 returned plausible but wrong numbers/regions, consistent with the agent fabricating from priors or partial sqlite-only data when mongo content was unreachable.

Yelp agent-loop run was **skipped**: the mechanism-level mongosh evidence above proves the bug is identical (empty mongo DB on auto-init), and spending another ~19 minutes of agent-loop wallclock would only confirm what the empty-DB observation already establishes. Procedure permitted "up to 2" candidates and required STOP/surface on real bug discovery; both criteria are satisfied.

Session budget: $0 spent (subscription auth). $25 cumulative cap not approached.

## Phase 4 — Bugs surfaced

### Bug 1: mongo init mechanism is broken (CRITICAL)

**Layer**: plugin compose generator (`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py:67-73`).

**Root cause**: the compose generator mounts the BSON dump folder at `/docker-entrypoint-initdb.d/<dump_folder_name>`. The official `mongo` image only auto-executes `.sh` and `.js` files in that directory; folders of `.bson` files are silently ignored. The container starts healthy with an empty database. Upstream DAB's own `benchmark/setup.sh:165` uses an external `docker exec dab-mongo mongorestore --db "$db_name" /tmp/mongodump/"$db_name"` step explicitly because of this — there is no auto-restore mechanism for BSON in the mongo image.

**Evidence**:
- Live mongosh probe: `articles_db` and `yelp_db` are absent post-init.
- Bind-mount lands inside container correctly (`ls /docker-entrypoint-initdb.d/agnews_articles/articles_db/` shows `articles.bson`).
- Agent rewards 0/4 with "empty answer" / fabricated outputs.

**Fix shape** (out of scope for this probe): either (a) emit an init `.sh` shim alongside the BSON dump that runs `mongorestore` on first start, (b) move dump restore into a one-shot init-container service in compose, or (c) add a per-step setup hook in the agent container that runs `mongorestore` against `dab-mongo` before the agent step.

### Bug 2: mongo path has no reachability gate (MEDIUM)

**Layer**: plugin task.toml emitter (`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py:252-276`).

**Root cause**: PKG-13 T5's reachability gate is gated on `if postgres_db:`; mongo datasets get no `[steps.healthcheck]`. The comment in `_postgres_db_name` (line 284) explicitly scopes this postgres-only by design. Combined with Bug 1, the failure mode is silent: compose is loaded, container is healthy, but the data is missing — exactly the silent-failure shape PKG-13 T5 was supposed to eliminate.

**Fix shape**: emit an analogous mongo reachability probe using `python3 -c "import socket; s=socket.create_connection(('dab-mongo', 27017), timeout=5); s.close()"` plus a content-presence assertion against expected db/collection names. The content-presence assertion is what would have caught Bug 1 fail-fast.

### Adjacent observations (not bugs)

- `dab-agent:latest` image ships `pymongo 4.17.0` (good) but has no `mongosh` / `mongorestore` / `mongodump` binaries. Agents must use pymongo from python; they cannot shell out to mongo CLI. Adequate for query-time access, but blocks any agent-side workaround for Bug 1.
- Stratum tagging is correct (`{"backends": ["mongo", "sqlite"]}` per-query). PKG-13 T11's AC-8 tagging carries over cleanly.
- Compose file structure, sidecar, bind-mount sources, network naming all pass PKG-13's structural checks. Bug 1 lives strictly at the init-script layer, not in surrounding plumbing.

## Recommendation for the 12-dataset matrix

Block agnews and yelp from Goal 1's 12-dataset matrix until pkg15-harbor-dab-mongo-init-restore lands. The 10 non-mongo datasets remain viable (8 postgres-eligible per PKG-13 T11 reconciliation, plus sqlite/duckdb-only stacks which need no live DB service).

If pkg15 is sequenced after Goal 1 kickoff, the matrix should explicitly tag mongo datasets as `blocked: pkg15` rather than running them and getting reward=0 noise.

## Files in this commit

- `examples/specs/probe-agnews-claude-harbor-dab.yaml`
- `examples/specs/probe-yelp-claude-harbor-dab.yaml`
- `docs/superpowers/plans/2026-05-20-dab-mongo-path-probe.md` (this file)
- `_runs/probe-agnews/` (gitignored if applicable; raw evidence)
- `_runs/probe-yelp/` (gitignored if applicable; raw evidence)
