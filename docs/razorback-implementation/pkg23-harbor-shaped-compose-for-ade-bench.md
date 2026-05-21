---
id: 0zzncavtj3yk4c0f90m0jhx7
title: PKG-23 — thread T_BENCH_* env vars from razorback translator (ade-bench client)
status: plan
source: PKG-20 follow-up — Goal 2 T0 cycle 3 2026-05-20 (worktree commit 4114020 on spacedock-ensign/goal2-ade-bench-haiku-baseline) — _validate_definition passes but docker compose up fails because PKG-20 symlinks ade-bench's upstream compose verbatim instead of generating a harbor-shaped one
started: 2026-05-21T06:11:54Z
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
`DockerEnvironment._validate_definition` passes. PKG-20 chose to
**symlink** ade-bench's upstream
`shared/defaults/docker-compose-duckdb-dbt.yaml` (or sibling
variant) verbatim. Validation accepts that. **Runtime does not.**

Goal 2 T0 cycle 4 (spike 2026-05-20 with `dab-agent:latest`
rebuilt) cleanly narrowed the remaining failure to ONE surface:

- `main` service (the agent): WORKS. dab-agent:latest is found and
  starts. PKG-20's symlink + harbor's overlay handle this correctly.
- `client` service (the DBT/duckdb workspace from ade-bench
  upstream): FAILS. compose-up returns:
  `please specify build context (e.g. "." for the current directory)`
  because ade-bench's compose template uses six unresolved
  `T_BENCH_*` env vars that razorback's translator doesn't set:
  - `T_BENCH_REPO_ROOT` (immediate failure — empty build context)
  - `T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME`
  - `T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME`
  - `T_BENCH_TEST_DIR`
  - `T_BENCH_TASK_LOGS_PATH`
  - `T_BENCH_CONTAINER_LOGS_PATH`

The spike eliminates two of three remediation candidates (the
spike worker's notes):
- (a) "build a separate ade-bench agent" — WRONG: agent slot
  already works
- (c) "write a razorback-shaped compose from scratch" — high-tax:
  must track ade-bench upstream changes
- **(b) thread T_BENCH_* env vars from razorback's translator —
  CORRECT** per spike data: ade-bench's upstream compose stays
  upstream; PKG-20's symlink stays as-is; the missing piece is
  purely env-var population in the translator.

PKG-23 adds an `ade-bench-env-vars` translator hook gated on
`AdeBenchLocalTaskEntry` that populates the six env vars when
harbor invokes `docker compose up` for an ade-bench task.

## Acceptance criteria

**AC-1 — Translator populates six T_BENCH_* env vars for ade-bench
tasks.** When `translate.py` produces a harbor invocation for an
`AdeBenchLocalTaskEntry`, the spawned `docker compose up`
inherits an env dict that sets:
- `T_BENCH_REPO_ROOT` → resolved absolute path to the
  materialized task's view-dir (the harbor cache_root entry, NOT
  ~/git/ade-bench — the materialized view-dir already has
  ade-bench's `tests/` etc. via PKG-19's bind-mount)
- `T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME` → per-task deterministic
  name, e.g., `ade-bench-client-{task_slug}:latest`
- `T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME` → per-cell unique
  name, e.g., `{task_slug}-client-{trial_id_short}`
- `T_BENCH_TEST_DIR` → resolved to the materialized `tests/`
  path inside the view-dir
- `T_BENCH_TASK_LOGS_PATH` → harbor's per-trial logs path
- `T_BENCH_CONTAINER_LOGS_PATH` → harbor's container-side logs
  mount path
Verified by: a unit test runs the translator against airbnb001's
spec and asserts the six env vars are populated with non-empty
strings; `docker compose config` invoked with that env produces a
fully-resolved compose with no `${T_BENCH_*}` placeholders.

**AC-2 — Env-var population is gated on `AdeBenchLocalTaskEntry`.**
Non-ade-bench tasks (harbor-DAB, hello-world, etc.) do NOT receive
the `T_BENCH_*` env vars in their compose env. The hook is opt-in
per task type.
Verified by: a unit test asserts that DAB's translator output env
does NOT contain `T_BENCH_*` keys; ade-bench's does.

**AC-3 — Goal 2's T0 cycle 4 failure mode is gone.**
Re-running `rk run` against Goal 2's T0 airbnb001 frozen spec no
longer produces "please specify build context" — compose-up
either succeeds OR fails on a different layer-5 contract gap
(unknown-unknown per spike notes — see Out of scope).
Verified by: live `rk run` against airbnb001 reaches Phase 3
(agent turn) OR fails with a NEW, documented failure mode (not
the T_BENCH_REPO_ROOT one).

**AC-4 — `ade-bench-client-{task_slug}` image build path documented
(but not implemented).** PKG-23 wires the IMAGE NAME but does NOT
build the image. The Dockerfile + build context for
`ade-bench-client-{task_slug}` lives in
`~/git/ade-bench/shared/defaults/<variant>/` and is referenced by
`T_BENCH_REPO_ROOT` for ade-bench upstream's `docker compose
build`. Verified by: documentation in the entity body or a
follow-up PKG entity captures how the client image gets built
(possibly via a `razorback ade-bench setup` command analogous to
dataagentbench's `benchmark/setup.sh`).

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

- **`ade-bench-client-{variant}` image build.** PKG-23 wires
  the IMAGE NAME but does NOT build any image. The agent image
  (razorback-solver, formerly dab-agent) is already covered by
  PKG-24. The client image (the DBT runner) needs a separate
  build-path entity — file as PKG-23 follow-up.
- **Layer-5 contract gap (UNKNOWN-UNKNOWN per spike).** The Goal 2
  spike worker flagged: "ade-bench's `client` shares the docker
  socket with the `main` agent — that's how ade-bench's agent
  invokes DBT normally. Whether harbor's container model can
  actually drive `client` to do useful work once the build context
  resolves is the next-layer question PKG-23 needs to answer
  empirically once it clears this blocker." PKG-23 is allowed to
  succeed at AC-3 with the docker-socket-shared layer still
  broken; a Stage Report deviation documents it and files the
  next entity.
- **DAB regression.** PKG-23 only changes ade-bench translator
  behavior; harbor-DAB's compose generation
  (`packages/razorback-plugin-dab/.../generate/compose.py`) is
  unchanged. AC-2 explicitly asserts no env-var leakage to DAB.
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

## Stage Report: plan

- DONE: Plan resolves the translator hook location: most likely src/razorback/translate.py (where AdeBenchLocalTaskEntry gets translated to harbor spec). Plan names the exact insertion point and the env-dict propagation path into harbor's docker compose invocation.
  Plan §Mechanism-precise architectural finding establishes the real wire is task.toml-side (`harbor.environments.docker.docker._compose_task_env = resolve_env_vars(task_env_config.env)`); plan lands env-dict-producing logic in `src/razorback/benchmarks/ade_bench/tasks.py:_compute_t_bench_env` + `_build_task_toml_from_yaml`, with `src/razorback/translate.py:_build_ade_bench` as the dispatcher; cross-cited harbor source paths in §Spec §-cites.
- DONE: Plan size: 4 ACs, primary surface is translate.py + tests. Separate plan doc since translator hook + integration test + 6-var env mapping + per-task ID derivation is non-trivial. Write a separate plan doc at docs/razorback-implementation/plans/pkg23-harbor-shaped-compose-for-ade-bench.md.
  Plan doc lives at `docs/razorback-implementation/plans/pkg23-harbor-shaped-compose-for-ade-bench.md` (11 tasks, AC↔task map, file structure, risk-first ordering rationale).
- DONE: Plan TDD-orders: failing unit test for AC-1 (env-dict population) FIRST; implementation; AC-2 ade-bench-gated test; AC-3 live `rk run` integration test against airbnb001 frozen spec.
  Task 1 = paper-only mechanism review; Task 2 = AC-1 RED unit (5 failing tests on `[environment.env]`); Task 3 = AC-1 GREEN implementation; Task 4 = AC-1 docker-config integration RED→PASS; Task 5 = value-shape iteration; Tasks 6/7 = AC-2 gating; Task 8 = AC-3 LIVE handoff to validation stage; Task 9 = AC-4 docs; Task 10 = full pytest regression gate; Task 11 = validation handoff.

### Summary

Plan corrects two phrasings in the entity (load-bearing for implementation): (1) the "translator hook" lands task.toml-side (via `[environment.env]`), not as a translator-subprocess `env=` arg — harbor's `DockerEnvironment._run_docker_compose_command` reads `task_env_config.env` from task.toml; (2) `T_BENCH_REPO_ROOT` must resolve to `ade_bench_root` (the `~/git/ade-bench` checkout), NOT the materialized view-dir, because the upstream compose's `dockerfile: docker/base/Dockerfile.duckdb-dbt` resolves relative to it and the view-dir lacks the `docker/` subtree. Both corrections are flagged in the plan and Task 9 documents the AC-1 correction back into the entity body. The live `rk run` (AC-3) is explicitly deferred to the validation stage per captain standing orders (`.env` / `ANTHROPIC_API_KEY` paid API tier).
