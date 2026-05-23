# Razorback data loading architecture

**Status:** Living document (snapshot 2026-05-23)
**Companion to:** [`2026-05-19-razorback-on-harbor.md`](2026-05-19-razorback-on-harbor.md)

How a frozen razorback spec turns into a running benchmark task with its
dependent services (Postgres, Mongo, etc.) — and where the
reproducibility audit trail currently goes thin.

---

## 1. The three layers between spec and live DB

```
┌───────────────────────────────────────────────────────────────┐
│ Layer 1: Dataset identity (the resolver)                      │
│ ┌─────────────────────────────────────┐ ┌───────────────────┐ │
│ │ ADE:  dataset: <org>/<name>@<ref>   │ │ DAB:              │ │
│ │ → Harbor registry, content-addr.    │ │ dataset: dab@1.0  │ │
│ │ → Plugin: PackageDatasetClient      │ │ → plugin-shipped  │ │
│ │   .download_dataset()               │ │   dataset.toml    │ │
│ │ → fetched task packages on disk     │ │ → inventory only  │ │
│ └─────────────────────────────────────┘ └───────────────────┘ │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ Layer 2: Local data (the cache)                               │
│ ADE: Harbor's task download dir (resolver-managed)            │
│ DAB: $DATAAGENTBENCH_DATA_ROOT (operator-managed clone + LFS) │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ Layer 3: Per-task compose stack (the runtime)                 │
│ Generated/materialized per (task, query) pair:                │
│   <task>/                                                     │
│   ├── task.toml             # metadata, healthcheck           │
│   ├── instruction.md                                          │
│   └── environment/                                            │
│       ├── Dockerfile         # the agent container            │
│       └── docker-compose.yaml # multi-service stack (optional)│
│                                                               │
│ Harbor reads environment/docker-compose.yaml and starts the   │
│ stack via `docker compose up` before agent setup.             │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
                    Agent runs against live services
```

Each layer is independent: resolver pins identity, cache holds the
bytes, compose stack provides the runtime.

---

## 2. Harbor's framework-native pattern for "tasks that need services"

The pattern is **per-task `environment/docker-compose.yaml`**, not a
benchmark-specific add-on. Harbor's docker environment
(`harbor/environments/docker/docker.py:251-296`) detects the file,
merges it with harbor-generated overrides (volume bindmounts via
`_mounts_compose_path`, no-network override when `allow_internet=False`),
and starts the whole stack via `docker compose up` before agent setup.

The agent's container is just one service in the stack. The agent
reaches sibling services by container hostname over the compose network
(`dab-postgres:5432`, `dab-mongo:27017`).

### Readiness gating

Harbor ships `EnvironmentConfig.healthcheck`
(`harbor/models/task/config.py:93-128`):

```toml
# task.toml
[environment.healthcheck]
command = "psql --host dab-postgres -c 'SELECT 1'"
interval_sec = 5
timeout_sec = 30
start_period_sec = 30
retries = 6
```

Harbor runs this after `docker compose up` and **gates agent setup on
its success** (per the docstring: "All retries must pass before agent
setup begins"). This is the framework-level readiness probe; agents
never see a half-loaded DB.

### Patterns across benchmark types

| Benchmark shape | Compose? | Healthcheck? | Example |
|---|---|---|---|
| Single-container, stateless | no (just Dockerfile) | optional | swe-bench, terminal-bench |
| Multi-service with backing DB | yes | typically yes | DAB (postgres + mongo) |
| Shared-image, per-task transforms | shared base + per-task overrides | depends | ADE-Bench / Spider2-DBT via pkg40's task-view materializer |

The pattern is consistent across the catalog. Third-party adapters
published via `harbor publish` follow the same shape.

---

## 3. How DAB threads through the three layers

DAB is the most service-heavy benchmark razorback currently runs. Its
shape exercises every part of the architecture.

### At `rk freeze`

1. Spec carries `benchmark: { kind: harbor_dab, dataset: dab@1.0, datasets: [bookreview, ...], workspace_variant: spacedock, query_mode: batch }`.
2. Resolver loads `packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset.toml`,
   validates the dataset name + variant against its inventory (54 queries × 12 datasets × 3 variants).
3. `data_root` is captured **as a literal env-template string** —
   `"${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}"` — into
   `spec.frozen.yaml`. Env interpolation is deferred to run time.
4. `sealed_hash` is computed over the frozen spec content. It hashes
   the env-template string, **not** the resolved path or the data
   contents.

### At `rk run`

5. Harbor invokes the DAB plugin's task generator
   (`razorback-plugin-dab generate`).
6. Generator now evaluates `${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}`
   against the live env. Opens `<resolved>/query_yelp/db_config.yaml`,
   reads `<resolved>/query_yelp/<dump>.sql.gz` paths.
7. Generator emits **one task directory per (dataset, query) pair**
   under harbor's `tasks/` dir, each with its own
   `environment/docker-compose.yaml` declaring three services:
   - `main` — the agent container
   - `dab-postgres` — Postgres, loaded from data_root dumps via init scripts
   - `dab-mongo` — Mongo, loaded from data_root dumps via init scripts
8. Init scripts come from the `razorback-plugin-dab` package itself
   (versioned in the wheel); dumps are bind-mounted from `data_root`
   into each container per pkg14.

### Per-trial container lifecycle

9. Harbor brings up the compose stack per trial; each trial is a
   freshly-loaded DB.
10. pkg13's pre-trial smoke (currently inside the verifier scaffold,
    not in the canonical `task.toml [environment.healthcheck]` block)
    runs `psql --host dab-postgres -c "SELECT count(*) FROM <sentinel>"`
    and gates agent invocation.
11. Agent runs. Verifier reads agent output. Container teardown.
12. Per-stage commits land in the freeze CAS at
    `$XDG_DATA_HOME/razorback/freeze/<sealed_hash>/`.

### Consistency reduction

Because DBs are loaded fresh per trial from bind-mounted dumps, **live
DB consistency reduces to data_root consistency** (modulo init script
and image digest, which are independently pinned).

---

## 4. What's pinned vs what isn't

| Input | Freeze-time pin | Run-time check | Audit recoverable? |
|---|---|---|---|
| Dataset identity (which tasks/queries) | ✅ dataset.toml content in plugin wheel; `solver_workflow_content_hash` in `provenance.yaml` | ✅ schema-level validation | ✅ |
| ADE task contents (per-task) | ✅ via `view_manifest.json` v2 `task_content_hash` (gb) | ✅ resolver refuses mismatched content | ✅ |
| ADE dataset version (set of tasks) | ✅ via `dataset_content_hash` (gb) | ✅ resolver refuses mismatched content | ✅ |
| DAB data_root contents (dumps, configs) | ❌ env-template only; no hash | ❌ no check | ⚠️ only via operator memory of upstream commit |
| Container image digest | ✅ via `pin_image_digest: true` → `provenance.yaml.image_digest` | ✅ harbor enforces digest match at compose-up | ✅ |
| Init script content (in plugin) | ✅ implicit via plugin wheel version | ✅ wheel version is what's loaded | ✅ |
| DB is up + sentinel table exists | n/a | ✅ pkg13's pre-trial smoke (in verifier scaffold) | n/a |
| DB schema/row contents match expected | n/a | ⚠️ implicitly via verifier outcome (NOT a separate check) | n/a |

**The DAB `data_root` row is the audit hole.** Image, init scripts, and
dataset identity are pinned. The actual database dumps under
`$DATAAGENTBENCH_DATA_ROOT` are not.

---

## 5. Reproducibility failure modes today

Concrete scenarios where the current setup silently produces
inconsistent results without flagging:

1. **Operator `git pull`s dataagentbench between freeze and run.** Same
   frozen spec → re-run gets a different DB state → different score.
   `sealed_hash` still matches; nothing flags the drift.
2. **Operator edits files under `$DATAAGENTBENCH_DATA_ROOT` locally**
   (e.g., to test something) and forgets to revert. All subsequent
   runs use the modified data; provenance doesn't catch it.
3. **Two researchers on different machines** with different commits of
   dataagentbench. They run the same frozen spec. Scores diverge.
   The freeze CAS at `$XDG_DATA_HOME/razorback/freeze/<sealed_hash>/`
   consolidates them as "the same experiment."
4. **Trial fails mid-run; resume after operator pulled an unrelated fix
   upstream.** Resumed trial loads a different DB than the un-resumed
   trials did. Stratified pass@1 averages across inconsistent trials.
5. **`DATAAGENTBENCH_DATA_ROOT` not set; default `~/dataagentbench/data`
   doesn't exist on this machine.** Plugin reports
   `dataset not hydrated, found LFS pointer at <wrong path>`. Today's
   workaround is the operator sets the env var; the frozen spec still
   records the env-template.

---

## 6. Future improvements

Filed in priority order. Each is a separate entity if/when the operator
greenlights the scope.

### 6.1 Resolve `data_root` to absolute path at freeze time *(small)*

Generator change: replace
`data_root: "${DATAAGENTBENCH_DATA_ROOT:-~/dataagentbench/data}"` with
the resolved absolute path captured at freeze time. One-line generator
change.

**Closes:** cross-machine "different clone location" drift; "env var
unset" failure mode.
**Doesn't close:** same-machine drift (`git pull` between freeze and
run).
**Effort:** ~30 min.

### 6.2 Record `data_root_content_hash` in provenance.yaml *(medium)*

Compute recursive sha256 of the resolved `data_root` at freeze time
and store it alongside `solver_workflow_content_hash`. At run time,
the plugin re-hashes and refuses on mismatch (`DataRootDriftError`,
mirror of `AliasDriftError`'s discipline). Operator can override with
`--allow-data-root-drift` for legitimate cases (e.g., reproducing an
old run that was frozen pre-hash).

**Closes:** all five failure modes in §5.
**Effort:** ~3-4 hours (helper + tests + integration smoke).

### 6.3 Move pkg13's smoke into `task.toml [environment.healthcheck]` *(small)*

The pre-trial DB readiness probe currently ships inside the DAB
plugin's verifier scaffold (`pkg13-harbor-dab-live-db-verification-stack`).
Harbor has a framework-native `[environment.healthcheck]` block in
`task.toml` that does the same thing, gates agent setup, and applies
to any benchmark — not just DAB.

Moving the smoke into the canonical location:
- Other benchmarks inherit the discipline for free
- Removes a razorback-specific code path
- Aligns DAB with Harbor's native readiness contract

**Effort:** ~1-2 hours (generator emits the healthcheck block;
verifier scaffold loses its smoke gate).

### 6.4 Publish DAB to Harbor's dataset registry *(large)*

Today DAB is asymmetric with ADE: ADE consumes a Harbor-registry
dataset ref (`dbt-labs/ade-bench@sha256:...`), DAB consumes a
plugin-shipped `dataset.toml` + operator-managed local clone.

Publishing DAB as a Harbor registry dataset (e.g.,
`dataagentbench-team/dab@1.0`) would:
- Unify the resolver path (DAB + ADE both via `PackageDatasetClient`)
- Give DAB content-hash pinning for free (per-task `task_content_hash`)
- Eliminate the operator-managed `$DATAAGENTBENCH_DATA_ROOT` clone
- Make DAB reproducible across machines without coordinating clones

**Tradeoffs:**
- Upload bandwidth: DAB's dumps are large (~GB scale)
- Auth: who owns the publish credentials?
- Backward compat: the in-tree `kind: dab` and plugin's `dataset.toml`
  path stay valid; the registry path is additive

**Effort:** Significant — depends on Harbor's `harbor publish`
maturity, dump-size constraints, and dataset-publish auth model.
This is the long-term symmetric path but not the cheapest fix.

### 6.5 (Optional) Distributed data cache *(future)*

If multiple researchers ever share runs, a distributed cache (S3 +
content-hash addressed) could let `data_root_content_hash` drive
on-demand download. Far future; not needed until collaboration
emerges.

---

## 7. Reading order for new contributors

1. Read this doc for the layered model.
2. Read [`2026-05-19-razorback-on-harbor.md`](2026-05-19-razorback-on-harbor.md)
   §6 (spec format) and §7 (run-dir contract) for the spec/runtime
   surfaces.
3. Read `harbor/environments/docker/docker.py` for the compose-stack
   handling.
4. Read `harbor/models/task/config.py` for `EnvironmentConfig` and
   `HealthcheckConfig`.
5. Read `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py`
   for a concrete example of a benchmark-specific compose generator.

---

## 8. Living document

This doc is updated inline as the data-loading surfaces evolve.
Significant updates should bump the snapshot date at the top.
