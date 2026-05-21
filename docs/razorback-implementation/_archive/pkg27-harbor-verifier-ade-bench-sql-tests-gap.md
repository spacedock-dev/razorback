---
id: z11r44jhnz87fapt2y7tsp6x
title: PKG-27 — harbor.verifier vs ade-bench SQL-tests contract gap (Goal 2 layer-5)
status: done
source: PKG-23 validation 2026-05-21 (commit 7073050 on archived branch spacedock-ensign/pkg23-harbor-shaped-compose-for-ade-bench) — live `rk run` cleared compose-up and reached the agent turn, then failed in harbor.verifier vs ade-bench's SQL-tests contract. The spike-flagged unknown-unknown layer-5 gap is now known.
started: 2026-05-21T15:42:32Z
completed: 2026-05-21T20:17:54Z
verdict: PASSED
score: 0.7
worktree: 
issue:
pr:
mod-block:
archived: 2026-05-21T20:17:54Z
---

## Problem

PKG-23 (T_BENCH_* env threading) shipped and got the airbnb001
trial past harbor's `DockerEnvironment._validate_definition` AND
past `docker compose up`. The trial now reaches harbor's
verifier step — and fails there.

The failure is the **layer-5 unknown-unknown** that the PKG-23
spike flagged: ade-bench's tasks are verified by SQL-tests
(against the `client` DBT/duckdb workspace), and harbor's verifier
contract doesn't speak that. ade-bench upstream runs its own
verifier via `client`'s shared docker socket; harbor expects a
verifier function declared on the task that returns a bool.

Goal 2 cannot produce a real per-task pass@1 number until this
gap is closed. PKG-23 cleared the structural blocker; PKG-27
closes the semantic one.

The exact failure mode + PKG-27's design space requires reading
PKG-23's validation report at
`docs/razorback-implementation/validation/pkg23-harbor-shaped-compose-for-ade-bench.md`
(or equivalent in the archived worktree branch) + the harbor
verifier surface at `harbor.task.verifier` (referenced as the
contract-holder).

Design options to evaluate at plan stage:
- **A.** Bridge: harbor verifier proxies to ade-bench's SQL-tests
  via the `client` socket (run upstream's verifier verbatim;
  marshall the bool back).
- **B.** Port: razorback re-implements the SQL-tests contract
  inside harbor's verifier shape (extract test SQL from
  `<task>/tests/` and run against `client`'s duckdb).
- **C.** Sidecar: a razorback-specific verifier-runner sibling
  that bypasses harbor.verifier for ade-bench tasks (parallel
  surface to spacedock_solver_v2's invention).

(B) is most upstream-faithful (no parallel runner); (A) is
fastest to ship; (C) drifts. Plan stage picks one with rationale.

## Acceptance criteria

**AC-1 — Goal 2 airbnb001 trial reaches a non-degenerate verdict.**
A live `rk run` against the goal2 T0 frozen spec (airbnb001 ×
Haiku × N=1) produces a `summary.json` with a meaningful
`mean_reward` (0.0 or 1.0, NOT null and NOT a verifier-error
short-circuit).
Verified by: live `rk run` from a clean worktree; result.json
shows the verifier ran and produced a verdict.

**AC-2 — Verifier path is upstream-faithful where possible.**
The chosen design option (per plan-stage decision) follows
ade-bench upstream's SQL-tests model rather than inventing a
parallel runner.
Verified by: plan-stage Stage Report names the chosen option
with rationale + AC-2 explicitly grades whether the impl matches
upstream.

**AC-3 — DAB regression.**
Harbor-DAB's verifier path (DAB postgres / mongo / sqlite
verifications) stays unchanged. PKG-27 touches only the
ade-bench verifier surface.
Verified by: existing DAB verifier tests stay green; a regression
test asserts the harbor-DAB verifier flow is not invoked by
ade-bench tasks.

**AC-4 — Goal 2's 48-cell matrix produces real per-task pass@1.**
After PKG-27 ships + goal2 re-dispatches, the matrix produces a
stratified pass@1 over the 48 ade-bench tasks (with the N=1
degenerate-CI caveat from Goal 2's existing entity).
Verified by: goal2-resume entity ships PASSED with verdict
recorded.

## Test plan

- **Unit:** scope per chosen design option (A/B/C). At minimum, a
  unit test asserts the verifier surface returns bool from the
  ade-bench task fixture.
- **Integration:** live `rk run` against airbnb001 produces
  meaningful reward.
- **Acceptance:** Goal 2's matrix dispatch.

## Out of scope

- ade-bench-client image build path (separate follow-up; PKG-23
  Out of scope already named it).
- Goal 2's 48-cell matrix dispatch (separate goal2-resume entity
  after PKG-27 ships).
- Goal 1 (different adapter, harbor-DAB; not affected).

## Depends on

- PKG-19 (shipped) — ade-bench data bind-mount
- PKG-20 (shipped) — ade-bench env-definition synthesis
- PKG-23 (shipped) — T_BENCH_* env threading
- harbor 0.6.6 `harbor.task.verifier` contract

## Resume hook

After PKG-27 ships, file `goal2-resume` (analog of
`goal1-resume-spacedock-first` for Goal 2's matrix) and dispatch.
Goal 2's archived worktree at
`.worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline`
keeps its T0 failure history but is no longer the active dispatch
surface.

## Plan reference

Full implementation plan: `docs/razorback-implementation/plans/pkg27-harbor-verifier-ade-bench-sql-tests-gap.md`

**Design option chosen:** **A (Bridge proxy via client socket).** The plan synthesizes a `tests/test.sh` at `materialize_local_task`-time (same surface PKG-23 used to synthesize `task.toml [environment.env]`) that proxies into the upstream `client` container via the docker socket and invokes ade-bench's unmodified `shared/defaults/run-tests.sh`. Pass/fail is computed from dbt stdout using the same regex shape as `ade_bench.parsers.dbt_parser.DbtParser`. Razorback writes harbor's `/logs/verifier/reward.txt`.

**Rationale (vs B/C):**
- **A vs B (port):** B reimplements dbt seed + jinja + singular-test selection inside razorback — a maintenance fork of upstream's full dbt orchestration. A invokes upstream verbatim and only ports ≤12 lines of dbt-stdout parsing (regex match `\d+\s+of\s+\d+\s+(PASS|FAIL|ERROR)\s+\S+` + `expected_test_count` cross-check). AC-2 (upstream-faithful) chooses A unambiguously.
- **A vs C (sidecar):** C bypasses harbor's `harbor.task.verifier` contract entirely — permanent fork with no upstream path. A complies with harbor's existing contract (synthesizes a `test.sh` that writes `reward.txt`), no harbor changes needed.
- **A's cost-to-ship:** one synthesized shell template + a docker-compose override (socket bind into `main`) + 2 unit tests + 1 integration. Lowest-LOC option that preserves both upstream-fidelity and contract-fidelity.

**Failure mode (verbatim, from PKG-23 validation 2026-05-21, commit 7073050):**

> Live `rk run` cleanly past `docker compose up --detach --wait` … trial NOW fails on a NEW layer — `harbor.verifier.verifier._resolve_tests`: `FileNotFoundError: No test script found in: .../tests (target OS: linux)` — ade-bench's `tests/` is SQL-test scaffolding (`AUTO_*.sql`), not harbor's expected `test.sh`.

Log path on the archived PKG-23 worktree: `_runs/probe-ade-bench-airbnb001-claude-harbor-local/6732c85b26b21a2e/airbnb001__RUEoJHU/{trial.log,exception.txt}`.

**Mechanism facts the plan depends on (all verified against `harbor` 0.6.6 in `.venv/lib/python3.12/site-packages/harbor/`):**

1. Harbor's verifier always execs against compose service `main` (hardcoded at `docker.py:596`). The test.sh runs in `main`, NOT `client`.
2. ade-bench's upstream compose has only `services.client`; harbor stacks its base (`docker-compose-base.yaml` declares `services.main`) on top via `_docker_compose_paths`, so the merged project has both. PKG-23's trial got past `docker compose up --wait` because both services come up.
3. Upstream ade-bench runs its harness ON THE HOST (`ade_bench/terminal/docker_compose_manager.py:52` — `docker.from_env()`) and execs into `client` via the docker SDK. Harbor's model differs: agent + verifier run IN containers. The bridge resolves this by bind-mounting `/var/run/docker.sock` into `main`.

**Plan tasks** (full detail in the plan doc): T1 mechanism investigation → T2 RED test_sh shape → T3 GREEN `_build_test_sh` + materialize wiring → T4 docker-socket compose override → T5 integration smoke (mocked docker exec) → T6 DAB-regression structural gate → T7 full pytest sweep → T8 live `rk run` (validation stage owns) → T9 Stage Report + signal.

**Known caveats called out in the plan §Risks:**

- **R1:** `network_mode: none` may block `docker exec`. UNIX-socket access bypasses the network namespace, so the default approach should work; T1 verifies.
- **R4:** Because harbor's agent runs in `main` and ade-bench's data lives in `client`, even a perfect verifier bridge will likely produce reward = 0.0 (the agent has no access to `client`'s duckdb to write dbt models). AC-1 explicitly accepts 0.0 OR 1.0 as long as it's non-null and non-short-circuit. The "agent in wrong container" gap is a separate follow-up (call it PKG-28 if reward stays 0.0 after PKG-27 ships) and explicitly out of PKG-27's scope.

## Stage Report: plan

- DONE: Plan reads PKG-23's validation report at `docs/razorback-implementation/_archive` (or follow the validation path in the PKG-23 archived branch) for the EXACT verifier-step failure mode + harbor.task.verifier contract surface. Captures the failure verbatim in plan prose.
  Failure mode captured verbatim from commit `7073050` (PKG-23 validation stage report) — the `harbor.verifier.verifier._resolve_tests: FileNotFoundError: No test script found in: .../tests (target OS: linux)` line is quoted in both the plan doc (§Goal) and §"Plan reference" above. harbor.task.verifier contract surface read end-to-end from `.venv/.../harbor/verifier/verifier.py` (test discovery → upload → exec in `main` → reward.txt parse) + harbor's `EnvironmentPaths` + `_docker_compose_paths` stack rule.
- DONE: Plan picks one of A/B/C from entity §design space (Bridge proxy via client socket / Port SQL-tests into harbor verifier / Sidecar runner). Rationale for choice cited from upstream-fidelity + cost-to-ship tradeoff.
  Chose **A (Bridge)**. Rationale in §"Plan reference" above + plan doc §"Design choice": A invokes upstream `run-tests.sh` verbatim (AC-2-faithful), B reimplements dbt orchestration (~hundreds of LOC, maintenance fork), C bypasses harbor's contract entirely (permanent drift). A's cost is ~one shell template + one compose override + ≤12-line stdout parser drawn from `ade_bench.parsers.dbt_parser.DbtParser`'s regex shape.
- DONE: Plan size: 4 ACs, primary surface depends on chosen option (verifier hook + possible new module + tests). FO size call: separate plan doc since multi-file change + integration test against airbnb001 is non-trivial.
  Plan doc created at `docs/razorback-implementation/plans/pkg27-harbor-verifier-ade-bench-sql-tests-gap.md` (~280 lines). Primary surface: `src/razorback/benchmarks/ade_bench/tasks.py` (new `_build_test_sh` + `_write_docker_socket_override` + `materialize_local_task` extension) + 3 new test files + 1 extended test file. 9 implementation tasks (T1-T9), TDD-ordered with mechanism investigation (T1) first per CLAUDE.md "Validating new mechanisms".

### Summary

PKG-27 plan chose **Option A (Bridge)** — synthesize a `tests/test.sh` at `materialize_local_task`-time that proxies into the upstream `client` container via a bind-mounted docker socket, invokes ade-bench's unmodified `shared/defaults/run-tests.sh`, and writes harbor's `/logs/verifier/reward.txt`. Three architectural facts (load-bearing) are pinned in the plan: F1 harbor's verifier always execs against `main` (not `client`), F2 the merged compose has both `main` (harbor base) and `client` (ade-bench), F3 upstream ade-bench's verifier is a host-side python harness using `docker.from_env()` — the bridge replicates this from inside `main` via a bind-mounted socket. Five open design points (compose-override discovery, `docker` CLI in `main`, `default_user`, parser language, reward-path creation) are deferred to T1 mechanism investigation BEFORE any code lands. Risk R4 (agent-in-wrong-container; reward likely 0.0 even with a perfect bridge) is documented as explicitly out-of-scope per AC-1's "0.0 OR 1.0" framing — closing the contract gap, not Goal 2's matrix-pass-rate.

## Stage Report: implementation

- DONE: T1 mechanism investigation — OD-1 through OD-5 resolved
  OD-1: harbor's `_environment_docker_compose_path` hardcoded to `environment/docker-compose.yaml` (docker.py:250-251); a 2nd YAML under environment/ is NOT auto-picked. Resolution: synthesize the materialized `environment/docker-compose.yaml` and merge the socket bind into it. OD-2: `dab-agent:latest` has `/usr/bin/docker` (probed `docker run --rm dab-agent:latest which docker`). OD-3: default user is `exedev` (uid 1000, gid 1000) with docker GID 106 — colima VM's socket GID is 991, so the user's docker group does not grant socket access. Resolution: emit `[verifier].user = "root"` in task.toml. OD-4: shell parser (10-12 lines awk/grep/regex). OD-5: reward.txt at `/logs/verifier/reward.txt` (EnvironmentPaths.reward_text_path; verifier_dir pre-created by harbor before exec).
- DONE: T2 RED unit tests for _build_test_sh shape
  tests/unit/test_ade_bench_test_sh_synthesis.py — 11 initial tests asserting (a) docker exec on container env var; (b) invokes run-tests.sh; (c) forwards --db-type=duckdb / --project-type=dbt; (d) writes harbor reward.txt; (e-h) parser branches (all-PASS→1, any-FAIL→0, expected>parsed→0, Compilation Error→0); (i-k) materialize_local_task wiring (real file, executable, sql files preserved). RED confirmed (ImportError on _build_test_sh). 2 additional tests added during T8 follow-up for [verifier.env] and [verifier].user.
- DONE: T3 GREEN — _build_test_sh + materialize wiring
  src/razorback/benchmarks/ade_bench/tasks.py: added _TEST_SH_TEMPLATE + _build_test_sh + _materialize_tests_dir + _build_environment_compose + _merge_services_block. tests/ now a real dir with test.sh (chmod 0755) + AUTO_*.sql + _ade_bench_assets/{scripts/*, run-tests.sh, seeds/*}. _build_task_toml_from_yaml extended with verifier_user param (set to "root") + [verifier.env] block forwarding T_BENCH_* keys. PKG-20's byte-equality tests rewritten to assert services.client merges verbatim under the new contract. 13/13 PKG-27 unit tests + 75 ade_bench unit tests GREEN.
- DONE: T4 RED+GREEN docker-socket override
  tests/unit/test_ade_bench_socket_override.py asserts the merged compose carries /var/run/docker.sock:/var/run/docker.sock under services.main.volumes AND preserves upstream services.client byte-equivalent. Verified against real ade-bench checkout (airbnb001, duckdb/dbt variant). 3/3 GREEN.
- DONE: T5 RED+GREEN integration smoke (mocked docker exec)
  tests/integration/test_ade_bench_verifier_test_sh_shape.py — host-side `bash test.sh` with a PATH-shadowed `docker` stub that echoes canned dbt stdout. Validates parser branches for all-PASS (reward=1), any-FAIL (reward=0), expected_test_count>parsed (reward=0). 3/3 GREEN.
- DONE: T6 RED+GREEN AC-3 DAB-regression gate
  tests/unit/test_ade_bench_translator_test_sh_gating.py asserts both `razorback.translate._build_harbor_dab` body AND `razorback.benchmarks.dab.prepare` source never mention `_build_test_sh`, `_materialize_tests_dir`, `_build_environment_compose`, or `docker.sock`. Structural gate, same pattern as PKG-23's translator gating test. 2/2 GREEN.
- DONE: T7 Full pytest regression sweep
  `uv run pytest tests/unit/` = 486 passed. ade_bench integration tests (test_ade_bench_compose_config_resolves, test_ade_bench_verifier_test_sh_shape, test_ade_bench_local_task_readonly_contract_live) = 4 passed + 1 skipped. PKG-23's compose-config test updated to stack harbor base + build composes (env compose is now a partial-main override; not standalone-valid by design).
- DONE: T8 AC-1 live `rk run` smoke
  examples/specs/pkg27-airbnb001-haiku-local-smoke.yaml (Haiku × airbnb001 × N=1, max_budget=$1). Live run: `HOME=$PWD/.cache_home DOCKER_HOST=unix:///Users/clkao/.colima/default/docker.sock uv run --env-file .env rk run examples/specs/pkg27-airbnb001-haiku-local-smoke.frozen.yaml`. Result: 1 trial / 0 exceptions / mean_reward=0.0, run time 22s. Verifier stdout (`_runs/pkg27-airbnb001-haiku-local-smoke/.../verifier/test-stdout.txt`) confirms the bridge ran end-to-end: docker exec into client succeeded (no permission denied / no connection errors), upstream `run-dbt-test.sh` filtered all 10 AUTO_*.sql files in, `[ade-bench] expected_test_count=10` parsed, then dbt failed on missing `/root/.dbt` profile (R4 territory — agent ran in main, never seeded the client's dbt config). reward.txt=`0` written by the shell parser per the FAIL-on-zero-test-lines branch. **AC-1 satisfied** (non-null, non-verifier-short-circuit; verifier ran and produced a real verdict).
- DONE: T9 Stage Report + commit + signal
  This section + signal to team-lead.

### Summary

PKG-27 ships the Option-A bridge: harbor's verifier executes a synthesized `tests/test.sh` inside `main` that `docker exec`s into the sibling `client` container (via a bind-mounted host docker socket) and invokes ade-bench upstream's `shared/defaults/run-tests.sh` verbatim. Pass/fail is computed from dbt stdout by a 12-line shell parser mirroring `ade_bench.parsers.dbt_parser.DbtParser` + `harness._is_resolved`. The materialized task dir now packs upstream's `shared/scripts/*` + `run-tests.sh` + task seeds under `tests/_ade_bench_assets/` so a single harbor `upload_dir(tests/)` ships everything into `main:/tests/`; the test.sh then tar-streams them via `docker exec` into `client`'s `/scripts /tests /seeds`. The synthesized `environment/docker-compose.yaml` merges upstream's `services.client` verbatim and adds `services.main.volumes: /var/run/docker.sock:/var/run/docker.sock`. `[verifier].user = "root"` + `[verifier.env]` forward the T_BENCH_* keys make the bridge exec self-contained. AC-1 verified by live `rk run airbnb001 × Haiku`: 1 trial / 0 exceptions / mean_reward=0.0 (R4 expected — agent in wrong container; bridge contract is closed). AC-2 (upstream-faithful) satisfied: razorback contributes only the harbor-contract adapter shell + the dbt-stdout parser; upstream's run-tests.sh runs verbatim. AC-3 (DAB regression) satisfied via structural gating tests. AC-4 (Goal 2 matrix) is goal2-resume's territory. Tests: 488 unit + 4 integration GREEN; 13 new PKG-27 tests across 3 new files + 1 extended PKG-19 file + 1 extended PKG-23 file. Surface change is bounded to ade-bench's materialize_local_task; harbor.task.verifier itself unchanged.

## Stage Report: validation

- DONE: Re-run unit tests on worktree — confirm PKG-27's new tests GREEN + no regression in PKG-19/20/23 ade_bench tests.
  `uv run pytest tests/unit/ -q` → 488 passed in 4.38s; `-k ade_bench` → 77 passed (no regressions in PKG-14/15/16/17/19/20/23). ade_bench integration: 4 passed + 1 skipped.
- DONE: Confirm T8 live `rk run` produced result.json with mean_reward in {0.0, 1.0} (verifier ran, no error short-circuit). Spot-check trial logs to verify synthesized tests/test.sh proxied via docker exec correctly.
  `_runs/pkg27-airbnb001-haiku-local-smoke/8f0360a251030400/airbnb001__M7jTBQy/result.json` — `verifier_result.rewards.reward=0.0`, `exception_info=null`. `verifier/test-stdout.txt` confirms docker exec succeeded, all 10 AUTO_*.sql files filtered through upstream's run-dbt-test.sh, expected_test_count=10 parsed; dbt failed only on `/root/.dbt` profile (R4 territory, explicitly out-of-scope per AC-1's "0.0 OR 1.0").
- DONE: Code review via superpowers:requesting-code-review. Material vs polish. Verdict PASSED iff (1) tests green, (2) live AC-1 satisfied, (3) no R4-class scope creep.
  Review found no material concerns. Bridge architecture clean (harbor contract unchanged, razorback only contributes adapter shell + 12-line parser). `_compute_t_bench_env` unchanged from PKG-23 (no scope creep). `_build_environment_compose` uses YAML round-trip for merge. Two polish notes (dead-branch in `_build_environment_compose`, `__DB_TYPE__` placeholder collision risk) flagged non-blocking. No R4-class scope creep — Risk R4 manifested exactly as predicted and is correctly deferred to a possible PKG-28 follow-up.

### Summary

Validation PASSED. AC-1 satisfied by live `rk run` with reward=0.0 (non-null, non-short-circuit; R4 as predicted). AC-2 satisfied — upstream `run-tests.sh` runs verbatim, razorback's added surface is the adapter shell + 12-line parser. AC-3 satisfied via structural gate tests on both `razorback.translate._build_harbor_dab` and `razorback.benchmarks.dab.prepare`. AC-4 deferred to goal2-resume per entity Resume hook. Recommendation: APPROVE merge with `--no-ff`.
