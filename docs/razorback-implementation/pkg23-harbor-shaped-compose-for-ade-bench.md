---
id: 0zzncavtj3yk4c0f90m0jhx7
title: PKG-23 — thread T_BENCH_* env vars from razorback translator (ade-bench client)
status: validation
source: PKG-20 follow-up — Goal 2 T0 cycle 3 2026-05-20 (worktree commit 4114020 on spacedock-ensign/goal2-ade-bench-haiku-baseline) — _validate_definition passes but docker compose up fails because PKG-20 symlinks ade-bench's upstream compose verbatim instead of generating a harbor-shaped one
started: 2026-05-21T06:11:54Z
completed:
verdict:
score: 0.85
worktree: .worktrees/spacedock-ensign-pkg23-harbor-shaped-compose-for-ade-bench
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

## AC-1 correction (plan §Mechanism-precise architectural finding)

`T_BENCH_REPO_ROOT` resolves to `ade_bench_root` (the `~/git/ade-bench`
checkout), NOT the materialized view-dir. The view-dir lacks the
`docker/` subtree that ade-bench's compose template references via
`dockerfile: docker/base/Dockerfile.duckdb-dbt`. Upstream ade-bench's
own `DockerComposeManager` sets `repo_root=str(REPO_ROOT)` to the same
value (`ade_bench/terminal/docker_compose_manager.py:86`). The
entity's original AC-1 wording ("the materialized view-dir") is
preserved above for provenance; the implementation honors the
correction.

## Build paths (AC-4 documentation)

PKG-23 wires
`T_BENCH_TASK_DOCKER_CLIENT_IMAGE_NAME=ade-bench-client-{task_slug}:latest`
but does NOT build the image. The build path lives in ade-bench
upstream:

- **Build context:** `~/git/ade-bench/` (i.e., `T_BENCH_REPO_ROOT`).
- **Dockerfile (duckdb-dbt variant):** `docker/base/Dockerfile.duckdb-dbt`.
- **Sibling variants:** `docker/base/Dockerfile.snowflake-dbt`,
  `docker/base/Dockerfile.snowflake-dbtf`.
- **Build command (manual, pre-`rk run`):**

  ```bash
  cd ~/git/ade-bench
  docker build -f docker/base/Dockerfile.duckdb-dbt \
    -t ade-bench-client-airbnb001:latest .
  ```

  Note: the upstream Dockerfile is variant-keyed (one per
  db_type/project_type), NOT task-keyed. A single built image with the
  variant-prefixed tag covers every task in that variant; razorback's
  per-task `ade-bench-client-{task_slug}:latest` is a per-task ALIAS
  pointing at the variant image (or the user can build per-task with
  `--build-arg`s — out of PKG-23 scope to choose).

- **Follow-up entity:** PKG-XX `ade-bench-client image build path` —
  wire a `razorback ade-bench setup` command analogous to
  dataagentbench's `benchmark/setup.sh` that pre-builds all four
  variant images and tags them with the razorback-side naming
  convention.

## Stage Report: plan

- DONE: Plan resolves the translator hook location: most likely src/razorback/translate.py (where AdeBenchLocalTaskEntry gets translated to harbor spec). Plan names the exact insertion point and the env-dict propagation path into harbor's docker compose invocation.
  Plan §Mechanism-precise architectural finding establishes the real wire is task.toml-side (`harbor.environments.docker.docker._compose_task_env = resolve_env_vars(task_env_config.env)`); plan lands env-dict-producing logic in `src/razorback/benchmarks/ade_bench/tasks.py:_compute_t_bench_env` + `_build_task_toml_from_yaml`, with `src/razorback/translate.py:_build_ade_bench` as the dispatcher; cross-cited harbor source paths in §Spec §-cites.
- DONE: Plan size: 4 ACs, primary surface is translate.py + tests. Separate plan doc since translator hook + integration test + 6-var env mapping + per-task ID derivation is non-trivial. Write a separate plan doc at docs/razorback-implementation/plans/pkg23-harbor-shaped-compose-for-ade-bench.md.
  Plan doc lives at `docs/razorback-implementation/plans/pkg23-harbor-shaped-compose-for-ade-bench.md` (11 tasks, AC↔task map, file structure, risk-first ordering rationale).
- DONE: Plan TDD-orders: failing unit test for AC-1 (env-dict population) FIRST; implementation; AC-2 ade-bench-gated test; AC-3 live `rk run` integration test against airbnb001 frozen spec.
  Task 1 = paper-only mechanism review; Task 2 = AC-1 RED unit (5 failing tests on `[environment.env]`); Task 3 = AC-1 GREEN implementation; Task 4 = AC-1 docker-config integration RED→PASS; Task 5 = value-shape iteration; Tasks 6/7 = AC-2 gating; Task 8 = AC-3 LIVE handoff to validation stage; Task 9 = AC-4 docs; Task 10 = full pytest regression gate; Task 11 = validation handoff.

### Summary

Plan corrects two phrasings in the entity (load-bearing for implementation): (1) the "translator hook" lands task.toml-side (via `[environment.env]`), not as a translator-subprocess `env=` arg — harbor's `DockerEnvironment._run_docker_compose_command` reads `task_env_config.env` from task.toml; (2) `T_BENCH_REPO_ROOT` must resolve to `ade_bench_root` (the `~/git/ade-bench` checkout), NOT the materialized view-dir, because the upstream compose's `dockerfile: docker/base/Dockerfile.duckdb-dbt` resolves relative to it and the view-dir lacks the `docker/` subtree. Both corrections are flagged in the plan and Task 9 documents the AC-1 correction back into the entity body. The live `rk run` (AC-3) is explicitly deferred to the validation stage per captain standing orders (`.env` / `ANTHROPIC_API_KEY` paid API tier).

## Stage Report: implementation

- DONE: AC-1 — Translator populates six T_BENCH_* env vars for ade-bench tasks.
  `_compute_t_bench_env` + extended `_build_task_toml_from_yaml` emit `[environment.env]` carrying the six keys (commit on `feat(pkg23): GREEN`); unit suite `tests/unit/test_ade_bench_t_bench_env.py` 5/5 PASS; integration `tests/integration/test_ade_bench_compose_config_resolves.py` PASS — `docker compose config` against airbnb001's materialized compose resolves with zero `${T_BENCH_*}` placeholders.
- DONE: AC-2 — Env-var population is gated on AdeBenchLocalTaskEntry.
  Translator-level + structural gating asserted in `tests/unit/test_ade_bench_translator_t_bench_env.py` (2/2 PASS); harbor-DAB code path never imports `materialize_local_task` / `_compute_t_bench_env` / mentions `T_BENCH_*`. Structural gating confirmed by source-inspection assertion.
- SKIPPED: AC-3 — Goal 2's T0 cycle 4 failure mode is gone (live `rk run` against airbnb001 reaches Phase 3).
  Live `rk run` is validation-stage scope per plan Task 8 and captain standing orders (paid API tier). Implementation stage shipped the prerequisite: the airbnb001 probe spec now pins `db_type: duckdb`/`project_type: dbt` so PKG-20's `_select_compose_variant` lands on `docker-compose-duckdb-dbt.yaml`. Probe spec freezes offline (`uv run rk freeze --allow-missing` clean).
- DONE: AC-4 — ade-bench-client-{task_slug} image build path documented (but not implemented).
  §Build paths section appended to entity body documenting Dockerfile location (`~/git/ade-bench/docker/base/Dockerfile.duckdb-dbt`), build context (`T_BENCH_REPO_ROOT`), manual build command, and follow-up entity placeholder for the eventual `razorback ade-bench setup` command.

### Plan deviations

- **Entity AC-1 vs implementation:** entity wording said `T_BENCH_REPO_ROOT` resolves to the "materialized view-dir"; implementation honors the plan's correction (`ade_bench_root` absolute path) because the upstream compose's `dockerfile: docker/base/Dockerfile.duckdb-dbt` resolves relative to it and the view-dir lacks `docker/`. Documented in the new §AC-1 correction section of the entity body.
- **T_BENCH_TASK_DOCKER_CLIENT_CONTAINER_NAME:** chose deterministic `{task_slug}-client` (no trial-id suffix) — harbor's `--project-name` per-trial prefix already isolates concurrent trials at the compose-project layer, and container_name within a project is unique by definition. Plan Task 5's counter-option (interpolate harbor session-id) deferred unless validation surfaces an actual collision.
- **T10 full pytest sweep:** unit suite (472 tests) PASS in 4s; PKG-23-adjacent integration (`test_ade_bench_compose_config_resolves`, `test_ade_bench_local_task_readonly_contract_live`, `test_freeze_idempotency_pkg8`) all PASS. `tests/integration/test_budget_gate_two_invocations.py` times out at 60s — confirmed PRE-EXISTING (reproduces after `git stash` of any worktree-local changes); the two timing-failing tests shell out via subprocess and appear environment/auth-shaped, NOT PKG-23-shaped. PKG-23's surfaces (translator + ade_bench tasks module) have no overlap with the budget-gate test.

### Summary

PKG-23 closes AC-1, AC-2, and AC-4 in the implementation stage. The six `T_BENCH_*` env vars now flow from the razorback translator into harbor's `docker compose up` via the synthesized `task.toml`'s `[environment.env]` table — the load-bearing wire confirmed against `harbor.environments.docker.docker.DockerEnvironment._run_docker_compose_command`. `docker compose config` resolves the airbnb001 compose with zero unresolved placeholders. AC-3 (live `rk run`) is deferred to validation stage per plan Task 8; the probe spec is now variant-pinned and freezes cleanly. Stage-report deviations documented above: one entity AC-1 wording correction, one deterministic-container_name choice with rationale, one pre-existing test-suite timeout flagged as out-of-scope.

## Stage Report: validation

- DONE: Re-run unit tests on ade_bench surface; confirm PKG-23 tests GREEN + no regression in PKG-19/PKG-20.
  `uv run pytest tests/unit/` — 472/472 PASS in 4.12s. PKG-23 surfaces (`test_ade_bench_t_bench_env.py` 5/5, `test_ade_bench_translator_t_bench_env.py` 2/2) all PASS; PKG-19 (`test_ade_bench_materialize_local_task.py` 18/18) + PKG-20 (`test_ade_bench_translator_local_root.py` 2/2) unchanged.
- DONE: AC-1 integration — `docker compose config` resolves T_BENCH_* placeholders.
  `tests/integration/test_ade_bench_compose_config_resolves.py` PASS — `docker compose config` against the materialized airbnb001 compose produces a fully-resolved compose with no `${T_BENCH_*}` placeholders.
- DONE: AC-3 live `rk run` against airbnb001 frozen spec — Goal 2 T0 cycle 4 failure mode is gone.
  Live `rk run examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml` with `HOME=$PWD/.cache_home` + `DOCKER_HOST=unix:///Users/clkao/.colima/default/docker.sock` + worktree-local `.env`-auth + `~/git/ade-bench` symlinked into `cache_home/git/`. Trial `airbnb001__RUEoJHU` cleanly past `docker compose up --detach --wait` (10+ compose-subcommand invocations succeeded via the harbor-home `.docker/cli-plugins` symlink that razorback's `_stage_harbor_home` provides). The PKG-20/cycle-4 `unknown flag: --project-name` / `please specify build context` failure mode is GONE. The trial NOW fails on a NEW layer — `harbor.verifier.verifier._resolve_tests`: `FileNotFoundError: No test script found in: .../tests (target OS: linux)` — ade-bench's `tests/` is SQL-test scaffolding (`AUTO_*.sql`), not harbor's expected `test.sh`. This matches the entity's AC-3 success criterion verbatim ("OR fails with a NEW, documented failure mode (not the T_BENCH_REPO_ROOT one)") and the §Out of scope "layer-5 contract gap (UNKNOWN-UNKNOWN per spike)" carve-out. Trial log: `_runs/probe-ade-bench-airbnb001-claude-harbor-local/6732c85b26b21a2e/airbnb001__RUEoJHU/{trial.log,exception.txt}`.
- DONE: Code review via superpowers:requesting-code-review.
  Reviewed the 6-commit diff (4b1ed8d..6f30193). Verdict CLEAN. Findings: (1) `_compute_t_bench_env` mirrors upstream `DockerComposeManager` env construction; docstring documents each var. (2) `_build_task_toml_from_yaml` extends with backward-compat default `t_bench_env=None`; TOML escaping handles `\` + `"` (sufficient for absolute paths on darwin/linux). (3) AC-2 gating is structural: `_compute_t_bench_env` reachable only via `materialize_local_task` ← `_build_ade_bench` (ade-bench-only translator dispatch). (4) Tests cover all six keys, the load-bearing `T_BENCH_REPO_ROOT == ade_bench_root` correction, container-side `/logs` value, per-slug image-name determinism, and the harbor-DAB structural-gate. (5) Integration test gracefully skips when ade-bench checkout is absent (clean CI behavior). No defects, no security concerns, no missing test coverage.

### Validation deviations

- **`HOME=$PWD/.cache_home` requires two-level docker shim.** The captain's dispatch said "HOME=$PWD/.cache_home + DOCKER_HOST". Bare HOME shim breaks two contracts simultaneously: (a) `~/git/ade-bench` expansion (the probe spec uses `ade_bench_root: ~/git/ade-bench`); (b) `~/.docker/cli-plugins/docker-compose` plugin discovery (with HOME pointing at the worktree, docker can't find the compose plugin and rejects `--project-name`). Validation added two symlinks under `.cache_home/`: `git/ade-bench → /Users/clkao/git/ade-bench` and `.docker/cli-plugins → /Users/clkao/.docker/cli-plugins` (+ `.docker/modules`). Razorback's own `_stage_harbor_home` (src/razorback/cli/run.py:69-85) does the equivalent for harbor's deeper `_runs/.harbor-home` HOME redirect, so the per-trial harbor subprocess gets docker plugins via `.harbor-home/.docker → real ~/.docker` (which now resolves through `.cache_home/.docker → ~/.docker`).
- **AC-4 client image absent — not a validation blocker.** `ade-bench-client-airbnb001:latest` was NOT pre-built. Live `rk run` still succeeded at `docker compose up` because ade-bench's compose has `build:` context next to `image:` — docker compose builds the image on the fly from `${T_BENCH_REPO_ROOT}/docker/base/Dockerfile.duckdb-dbt`. AC-4 stays documentation-only per entity §Out of scope; the follow-up `razorback ade-bench setup` entity remains the right home for the pre-build wiring.
- **Verifier-layer gap files a follow-up.** AC-3's "new failure mode" is real and goal-2-relevant: harbor's verifier expects a shell test script in `tests/`, but ade-bench tasks ship SQL test files for their dbt/duckdb runner. This is the §Out of scope "layer-5 contract gap (UNKNOWN-UNKNOWN per spike)" surfacing post-compose-up. Validation does NOT re-open PKG-23 for this; per entity §Out of scope it is a new pkg2X-* entity's scope (ade-bench verifier shim → harbor verifier surface). The captain/FO can file it from session debrief if Goal 2's matrix needs it.

### Summary

PKG-23 verdict: **PASSED** (conditional on the verifier-layer follow-up entity being filed). All four ACs are closed: AC-1 (translator populates six T_BENCH_* env vars) + AC-2 (gated on `AdeBenchLocalTaskEntry`) via 472 unit + 1 integration test all green; AC-3 (Goal 2 T0 cycle 4 failure mode gone) via live `rk run` reaching the verifier layer with the PKG-20 build-context failure absent; AC-4 (client-image build path) via §Build paths documentation. The live trial surfaces a NEW layer-5 failure (harbor verifier vs. ade-bench SQL tests) which is the entity's documented out-of-scope unknown-unknown — a follow-up entity is the right home, not a PKG-23 re-open.
