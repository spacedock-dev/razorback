---
id: 0zzncavtj3yk4c0f90m0jhx7
title: PKG-23 — generate harbor-shaped compose for ade-bench (not symlink upstream)
status: backlog
source: PKG-20 follow-up — Goal 2 T0 cycle 3 2026-05-20 (worktree commit 4114020 on spacedock-ensign/goal2-ade-bench-haiku-baseline) — _validate_definition passes but docker compose up fails because PKG-20 symlinks ade-bench's upstream compose verbatim instead of generating a harbor-shaped one
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Problem

PKG-20 closed the **file-presence** half of harbor's task contract:
`materialize_local_task` now synthesizes
`environment/docker-compose.yaml` so harbor's
`DockerEnvironment._validate_definition` passes. But PKG-20 took a
shortcut — it **symlinks** ade-bench's upstream
`shared/defaults/docker-compose-duckdb-dbt.yaml` (or sibling
variant) verbatim into the materialized view-dir.

That upstream file is not a harbor-shaped compose:

- Its services use ade-bench's `T_BENCH_*` env vars
  (`T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME`,
  `T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME`, `T_BENCH_TEST_DIR`,
  `T_BENCH_TASK_LOGS_PATH`, `T_BENCH_CONTAINER_LOGS_PATH`,
  `T_BENCH_REPO_ROOT`) that razorback's translator doesn't set.
- Its only service is `client` (the DBT/duckdb workspace) — there
  is no `main` service. ade-bench's own runner spawns the agent
  outside compose.
- Harbor's overlay `docker-compose-prebuilt.yaml` adds a `main`
  service with `image: ${PREBUILT_IMAGE_NAME}` (defaults to
  `dab-agent:latest` — wrong image for ade-bench).

Result: `docker compose up --detach --wait` fails with
"warning: T_BENCH_* not set" + "Error pull access denied for
dab-agent". Goal 2 cannot get past `rk run` Phase 2.

The right contract is for `materialize_local_task` to GENERATE a
**harbor-shaped** compose specific to each ade-bench task — one
that defines a `main` service (the agent, using a sibling
`ade-bench-agent:latest` image) and any infrastructure services
(the `client` DBT container, populated from ade-bench's
shared/defaults but with razorback-supplied env values instead of
`T_BENCH_*` placeholders).

## Acceptance criteria

**AC-1 — Materializer generates a harbor-shaped compose.**
`materialize_local_task` writes
`environment/docker-compose.yaml` as a NEW file (not a symlink),
shaped per harbor's contract:
- services include a `main` service whose `image` is
  `ade-bench-agent:latest` (or a configurable per-spec image
  name) — this is the agent container the razorback claude-cli
  invokes
- services include any auxiliary containers ade-bench's task
  needs (the duckdb-dbt or snowflake-dbt client), with build/image
  config sourced from ade-bench's `shared/defaults/<variant>.yaml`
  but with explicit values (no `T_BENCH_*` placeholders)
Verified by: a unit test asserts the generated compose for
airbnb001 contains a `main` service whose `image:` is non-empty
and a `client` (or sibling) service whose env vars do NOT include
unresolved `${T_BENCH_*}` strings.

**AC-2 — Generation reads ade-bench's variant compose and
substitutes razorback-shaped values.** The substitution map is:
- `${T_BENCH_REPO_ROOT}` → the materialized task's `ade_bench_root`
  path (resolved at materialize time)
- `${T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME}` → a per-variant
  resolved image name (e.g., `ade-bench-duckdb-dbt:latest` for the
  duckdb-dbt variant); image build is OUT OF SCOPE for PKG-23 but
  the name is wired
- `${T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME}` →
  `${task_slug}-client` (per-cell unique)
- `${T_BENCH_TEST_DIR}` → `/workspace/tests` (harbor convention)
- `${T_BENCH_TASK_LOGS_PATH}` → `/workspace/logs/task`
- `${T_BENCH_CONTAINER_LOGS_PATH}` → `/workspace/logs/container`
Verified by: a unit test asserts the substitution map is applied
for at least one variant.

**AC-3 — `main` service config is consistent across ade-bench
tasks.** The `main` service definition follows the same shape as
harbor-DAB's `main` (which uses `dab-agent:latest`). For ade-bench
that means `image: ade-bench-agent:latest` (placeholder — image
build is OUT OF SCOPE; the name is wired) + mounts for the
workspace + healthcheck consistent with harbor's `--wait` contract.
Verified by: unit test asserts the `main` service has the required
mount points; integration test (after image is built — see
PKG-23-followup) asserts `docker compose up --wait` succeeds.

**AC-4 — Goal 2's T0 smoke succeeds.**
After PKG-23 lands AND `ade-bench-agent:latest` is built (separate
follow-up — see Out of scope), `rk run` against Goal 2's T0
airbnb001 frozen spec reaches Phase 3 (agent turn).
Verified by: a live `rk run` produces result.json with
non-degenerate per_trial_outcomes.

## Test plan

- **Unit:** `tests/unit/test_ade_bench_materialize_local_task.py`
  extends with cases for AC-1 (compose shape), AC-2 (substitution
  map), AC-3 (`main` service consistency).
- **Integration:** Materialize airbnb001, run `docker compose
  config` against the generated compose, parse the output and
  assert no unresolved `${T_BENCH_*}` placeholders.
- **Acceptance:** Live `rk run` against airbnb001 frozen spec
  reaches Phase 3.

## Out of scope

- **`ade-bench-agent:latest` image build.** PKG-23 wires the name
  but does NOT build the image. File a separate follow-up (PKG-25
  candidate or sibling) to define the Dockerfile + add a
  `razorback ade-bench setup` command analogous to dataagentbench's
  `benchmark/setup.sh` lines 143-146. For PKG-23 unit tests, the
  image name is asserted but no pull/build attempted.
- **DAB regression.** PKG-23 only changes ade-bench materialization;
  harbor-DAB's compose generation (in
  `packages/razorback-plugin-dab/.../generate/compose.py`) is
  unchanged.
- **Multi-variant matrix dispatch.** PKG-23 ships single-variant
  correctness (variants[0] default per PKG-20). Per-cell variant
  selection at matrix dispatch time stays PKG-20's scope.

## Depends on

- PKG-19 (ade-bench data bind-mount) — shipped
- PKG-20 (env-definition synthesis) — shipped; PKG-23 supersedes
  the symlink-the-upstream-compose shortcut with a generated
  compose
- `ade-bench-agent:latest` image (separate follow-up — see Out of
  scope) — needed for AC-4 live smoke; PKG-23 can ship through
  validation with AC-4 marked PARTIAL pending the image

## Resume hook

After PKG-23 merges + `ade-bench-agent:latest` is built (separate
follow-up), Goal 2's implementation resumes against its existing
worktree. The T0 probe + 48-cell matrix dispatch then become
runnable.
