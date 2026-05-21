# PKG-27 — Validation Report

**Entity:** `docs/razorback-implementation/pkg27-harbor-verifier-ade-bench-sql-tests-gap.md`
**Branch:** `spacedock-ensign/pkg27-harbor-verifier-ade-bench-sql-tests-gap`
**Worktree:** `.worktrees/spacedock-ensign-pkg27-harbor-verifier-ade-bench-sql-tests-gap`
**Impl head:** `721ffb4` — `impl(pkg27): T8 live smoke + T9 Stage Report — AC-1 satisfied (mean_reward=0.0)`
**Validation date:** 2026-05-21

## Verdict

**PASSED** — all four ACs satisfied per the plan's defined boundaries.

- **AC-1** (non-degenerate verdict) — live `rk run` produced `reward=0.0` with the verifier running end-to-end (no short-circuit). Confirmed via `result.json` + `verifier/test-stdout.txt` spot-check.
- **AC-2** (upstream-faithful) — synthesized `test.sh` invokes `bash /tests/run-tests.sh` verbatim inside the `client` container; razorback contributes only the harbor-contract adapter shell + a 12-line dbt-stdout parser mirroring `ade_bench.parsers.dbt_parser.DbtParser`.
- **AC-3** (DAB regression) — structural source-inspection gate verifies neither `razorback.translate._build_harbor_dab` nor `razorback.benchmarks.dab.prepare` reaches PKG-27's surface (`_build_test_sh`, `_materialize_tests_dir`, `_build_environment_compose`, `docker.sock`). 488 unit tests + 4 ade_bench integration tests green; no regression in PKG-14/15/16/17/19/20/23 surfaces.
- **AC-4** (goal2 matrix) — explicitly out of scope per the entity Resume hook; owned by the forthcoming `goal2-resume` entity.

R4 risk (agent in `main`, data in `client` → reward likely 0.0 even with a perfect bridge) materialized exactly as documented. AC-1 explicitly accepts `0.0 OR 1.0` as long as it is non-null and non-short-circuit — satisfied.

## AC-by-AC verification

### AC-1 — Goal 2 airbnb001 trial reaches a non-degenerate verdict

**Verified by:** live `rk run` at `_runs/pkg27-airbnb001-haiku-local-smoke/8f0360a251030400/` (Haiku × airbnb001 × N=1).

`summary.json`:

```json
"n_trials_total": 1, "n_trials_completed": 1, "n_trials_errored": 0
"trials": [{ "trial_id": "airbnb001__M7jTBQy", "reward": 0.0, "error_reason": null }]
```

`result.json` (trial): `verifier_result.rewards.reward = 0.0`, `exception_info = null`, verifier wallclock ~2s (`verifier.started_at` → `finished_at`). Non-null, non-error-short-circuit.

Verifier stdout (`verifier/test-stdout.txt`, 905 B) confirms the bridge actually executed:

```
Filtering for db_type='duckdb', project_type='dbt'
Including: AUTO_daily_agg_reviews_equality.sql
...
Including: AUTO_wow_agg_reviews_existence.sql
[ade-bench] expected_test_count=10
Merging schema into dbt_project.yml...
Warning: dbt_project.yml not found
Usage: dbt seed [OPTIONS]
Try 'dbt seed --help' for help.
Error: Invalid value for '--profiles-dir': Path '/root/.dbt' does not exist.
...
```

Spot-check observations:
1. `docker exec` from `main` → `client` succeeded (no permission-denied / no docker-not-found).
2. The 10 `AUTO_*.sql` files harbor uploaded to `main:/tests/` reached `client` via the tar-stream staging (visible in `Including:` lines emitted by upstream's `run-dbt-test.sh`).
3. `--db-type=duckdb --project-type=dbt` flag forwarding (synthesized in `_build_test_sh`) was honored by upstream's filter.
4. Upstream's `expected_test_count=10` parser line printed by `run-dbt-test.sh:59` was reached.
5. `dbt seed` and `dbt test` failed only because `/root/.dbt` profile was unseeded — this is R4 territory (agent ran in `main`, never seeded `client`'s dbt config). It is NOT a verifier-error short-circuit.
6. `reward.txt = "0"` was written by the shell parser's FAIL-on-zero-test-lines branch (the dbt errors short-circuited before any `N of M PASS|FAIL` lines printed; the parser correctly attributed this as FAIL).

AC-1 satisfied: the verifier ran, parsed dbt stdout per the documented contract, and emitted a real verdict.

### AC-2 — Verifier path upstream-faithful

**Verified by:** code inspection of `src/razorback/benchmarks/ade_bench/tasks.py:313-414` (the `_TEST_SH_TEMPLATE`) + unit tests `tests/unit/test_ade_bench_test_sh_synthesis.py`.

The synthesized `test.sh` body contains `docker exec -w /app "${CLIENT}" bash /tests/run-tests.sh --db-type=... --project-type=...` (template line 374-376) — upstream's `shared/defaults/run-tests.sh` runs verbatim. Razorback contributes:
- The harbor-contract adapter shell (writes `/logs/verifier/reward.txt`).
- A 12-line dbt-stdout parser (5 fail-checks via `grep -qE` mirroring `ade_bench.parsers.dbt_parser.DbtParser` + `harness._is_resolved`).
- Asset staging (`tar -C ... | docker exec -i tar -xf -`) — replicates upstream `DockerComposeManager.put_archive` from inside `main` rather than the host.

No dbt orchestration is reimplemented in razorback. AC-2 satisfied.

Tests passing (8 of the 13 PKG-27 unit tests cover AC-2 specifically):
- `test_build_test_sh_invokes_docker_exec_on_client_container`
- `test_build_test_sh_runs_upstream_run_tests_sh_verbatim`
- `test_build_test_sh_forwards_db_and_project_type_flags`
- 4 parser-branch tests (`all_pass→1`, `any_fail→0`, `parsed<expected→0`, `compilation_error→0`)
- `test_synthesized_compose_preserves_client_service` — `services.client` is byte-equal to upstream's `shared/defaults/docker-compose-duckdb-dbt.yaml`.

### AC-3 — DAB regression

**Verified by:** `tests/unit/test_ade_bench_translator_test_sh_gating.py` (2 tests, structural gate, same shape as PKG-23's translator-gating).

Both DAB code paths inspected — `razorback.translate._build_harbor_dab` (extracted by `def` boundary) and `razorback.benchmarks.dab.prepare` (whole module) — asserted to NOT mention `_build_test_sh`, `_materialize_tests_dir`, `_build_environment_compose`, or `docker.sock`. PKG-27's surface is reachable only from `materialize_local_task`, which is called only on `AdeBenchLocalTaskEntry` (gating same as PKG-19/20/23).

Full unit-test sweep: 488 passed in 4.4s. ade_bench subset: 77 passed. Integration: 4/4 ade_bench tests pass + 1 skipped. No regressions in PKG-14/15/16/17/19/20/23 surfaces.

AC-3 satisfied.

### AC-4 — Goal 2 48-cell matrix pass@1

**Out of scope (deferred):** per entity §"Resume hook" and §"Out of scope", AC-4 is owned by the forthcoming `goal2-resume` entity, dispatched after PKG-27 ships. Not gated by this validation.

## Mechanism integrity (R1–R4 status)

- **R1** (network_mode: none blocks docker exec) — did not materialize. Live run executed `docker exec` from `main` to `client` successfully via UNIX socket (which bypasses network namespaces, as the plan predicted).
- **R2** (cold image build) — ade-bench-client-airbnb001 built on-the-fly during compose-up. Wallclock impact absorbed in the 22s run time.
- **R3** (parser drift) — parser regex pinned to current upstream shape; covered by 5 parser-branch unit tests.
- **R4** (agent in `main`, data in `client` → reward likely 0.0) — materialized as predicted. Reward 0.0 from missing `/root/.dbt` profile inside `client`. Out of PKG-27's scope; a follow-up entity (provisionally PKG-28) is the right place for the "agent runs in wrong container" structural fix.

## Code review (material vs polish)

**Material (no concerns):**
- Bridge architecture is clean and contract-correct: harbor's `harbor.task.verifier` surface is unchanged; the synthesized `test.sh` complies with the existing contract by writing `/logs/verifier/reward.txt`.
- `_compute_t_bench_env` is untouched from PKG-23 (no scope creep).
- `_build_environment_compose` uses a YAML round-trip (`_merge_services_block`) for the merge — correct call for a synthesized file.
- `[verifier].user = "root"` + `[verifier.env]` block forwarding T_BENCH_* — the right answer to OD-3 (default user `exedev` is not in a docker group with the right GID).
- Asset staging via `tar | docker exec -i tar -xf -` is the right shape to replicate upstream's `put_archive` from inside `main`.
- AC-3 structural gate is robust (source-inspection at `def` boundaries).

**Polish (non-blocking):**
- `tasks.py:731-740` — the `if upstream.lstrip().startswith("services:")` true-branch always wins for real ade-bench composes (all start with `services:`). The else branch is defensive dead code. Not material; leave as-is.
- `__DB_TYPE__` / `__PROJECT_TYPE__` placeholder substitution via `str.replace()`. Tiny collision risk if a future template literal embeds the same string. Not material; documented in `_build_test_sh` docstring.
- `REWARD_DIR` env override is correctly noted in the template as a test affordance.

No material code-review concerns. No R4-class scope creep observed in the implementation.

## Test execution summary

```
$ uv run pytest tests/unit/ -q
488 passed in 4.38s

$ uv run pytest tests/unit/ -q -k "ade_bench"
77 passed, 411 deselected in 1.24s

$ uv run pytest tests/integration/test_ade_bench_compose_config_resolves.py \
    tests/integration/test_ade_bench_verifier_test_sh_shape.py \
    tests/integration/test_ade_bench_local_task_readonly_contract_live.py -q
4 passed, 1 skipped in 0.58s
```

## Artifacts referenced

- `_runs/pkg27-airbnb001-haiku-local-smoke/8f0360a251030400/summary.json`
- `_runs/pkg27-airbnb001-haiku-local-smoke/8f0360a251030400/result.json`
- `_runs/pkg27-airbnb001-haiku-local-smoke/8f0360a251030400/airbnb001__M7jTBQy/result.json`
- `_runs/pkg27-airbnb001-haiku-local-smoke/8f0360a251030400/airbnb001__M7jTBQy/verifier/{reward.txt,test-stdout.txt}`
- `examples/specs/pkg27-airbnb001-haiku-local-smoke.yaml`

## Recommendation

**APPROVE — merge with `--no-ff`.** PKG-27 closes the layer-5 verifier contract gap that PKG-23 surfaced. Reward 0.0 is the documented R4 outcome and explicitly accepted by AC-1; the follow-up "agent runs in wrong container" gap belongs in a new entity (PKG-28 if it materializes) after Goal 2 matrix resume confirms the structural-side fix is needed at scale.
