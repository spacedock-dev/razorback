---
id: ddwx0c1t0g6amrpje2mw3wcm
title: Preserve ADE main/client Harbor environment split on dataset-ref path
status: backlog
source: Goal 4 probe 2026-05-23 - superseded blocker classification from stale docker_image_override probe
started:
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

Goal 4's canonical ADE-Bench source is the Harbor published dataset ref. This
follow-up was filed after a 2026-05-23 `airbnb001` probe materialized the
dataset task view, then patched `[environment].docker_image =
"shared-dbt-duckdb:latest"`. Harbor therefore used its prebuilt single-`main`
path and failed while pulling that image before any Codex solve.

Stale conclusion note, 2026-05-23: a later no-override probe succeeded for the
same task with reward `1.0`, no exceptions, and about 3m50s total runtime:
`/home/exedev/.local/share/razorback/runs/goal4-ade-codex-no-override-probe-20260523172345/runs/ade-bench-harbor-dataset-codex/c95422940e5b34c2`.
The immediate blocker was the stale `docker_image_override`, not a demonstrated
requirement to port the older main/client split before the published ADE
dataset-ref path can run. Treat this task as optional hardening unless future
full-dataset evidence shows a split-specific failure.

Earlier ADE Harbor smokes worked through a split environment: Harbor's `main`
service runs the Razorback/DAB-style agent image with Claude/Codex tooling,
while ADE's canonical `client` service carries the dbt project, DuckDB state,
and upstream verifier. PKG-23 wired the `T_BENCH_*` env vars for that client,
and PKG-27 added the verifier bridge from `main` into `client`.

This task preserves the older main/client setup as a possible hardening path
for future split-specific failures; it is no longer the immediate Goal 4
unblocker.

## Acceptance criteria

**AC-1 - Dataset-ref ADE task views keep the ADE client service.**
For a dataset-ref task such as `airbnb001`, materialization preserves or
synthesizes an `environment/docker-compose.yaml` that includes ADE's canonical
`client` service alongside Harbor's `main` service.
Verified by: `docker compose config` on the materialized task view shows both
services and no unresolved `${T_BENCH_*}` placeholders.

**AC-2 - Main uses the Razorback agent image.**
The agent runtime runs in `main` using the existing Razorback/DAB agent image
with Codex/Claude tooling, not a dbt-only image. ADE's dbt image remains the
client environment.
Verified by: a sampled materialized `task.toml` and compose config show the
expected main image and client image/build context separately.

**AC-3 - Dataset-ref path carries the PKG-23 env wiring.**
Dataset-ref materialization populates the six `T_BENCH_*` variables needed by
ADE's compose/client path, using the same semantics validated in PKG-23.
Verified by: unit tests assert the values for `airbnb001`, including
`T_BENCH_REPO_ROOT`, client image name, client container name, test dir, task
logs path, and container logs path.

**AC-4 - Dataset-ref path carries the PKG-27 verifier bridge.**
The materialized dataset-ref task includes the synthesized `tests/test.sh`,
docker-socket bridge, and verifier env needed to execute ADE's upstream
`run-tests.sh` in the `client` container.
Verified by: unit/integration tests assert the generated `test.sh` calls
`docker exec` into the client and writes Harbor's reward file.

**AC-5 - Goal 4 smoke gets past environment setup.**
A one-task `airbnb001` Codex smoke using the canonical dataset ref reaches
agent setup or agent execution. It must not fail on pulling
`shared-dbt-duckdb:latest` as the `main` service.
Verified by: live or dry-run-with-stub evidence records the run-dir and the
first remaining blocker, if any.

## Depends on

- `ade-bench-harbor-dataset-ref`
- `pkg23-harbor-shaped-compose-for-ade-bench`
- `pkg27-harbor-verifier-ade-bench-sql-tests-gap`
- `pkg40-harbor-task-view-materializer`
