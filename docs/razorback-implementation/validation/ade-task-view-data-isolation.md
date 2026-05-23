# Validation Report: ADE task-view data isolation preflight

Entity: `kcns444rns45420fe4g0jaza`  
Branch: `spacedock-ensign/ade-task-view-data-isolation`  
Validated commits: `52ae716`, `c02e80c`, `c920fa4`, `b9a90f1`  
Gate decision: REJECT back to implementation.

## Summary

The Dockerfile preflight injection is runnable and the runtime setup preflight
runs before the inner Codex setup. However, the implemented Airbnb contract is
wrong for real `airbnb001` workspaces: it requires `calendar`, `listings`, and
`reviews`, while current built ADE Airbnb workspaces expose
`raw_hosts`, `raw_listings`, and `raw_reviews`. Because both the Dockerfile and
runtime preflights use this contract, a canonical `airbnb001` smoke would fail
before Codex on valid task data. This blocks AC-1 and AC-3.

## Commands Run

Full required suite:

```text
$ uv run pytest
collected 657 items / 1 error
ERROR tests/unit/test_task_identity_scoring.py
ModuleNotFoundError: No module named 'razorback.score.load'
```

Focused implementation tests:

```text
$ uv run pytest tests/unit/test_ade_bench_workspace_preflight.py tests/unit/test_ade_bench_harbor_view.py tests/unit/test_spacedock_solver_ade_preflight.py -q
............                                                             [100%]
12 passed in 0.65s
```

Real cached ADE task-view injection check:

```text
$ uv run --no-sync python - <<'PY'
# materialize airbnb001, f1001, quickbooks001 from ~/.cache/razorback/ade-bench/datasets
# and print manifest task id, db_name, and Dockerfile preflight order
PY
airbnb001: manifest_task=airbnb001 db_name=airbnb after_setup=True before_cmd=True
f1001: manifest_task=f1001 db_name=f1 after_setup=True before_cmd=True
quickbooks001: manifest_task=quickbooks001 db_name=quickbooks after_setup=True before_cmd=True
```

Actual built-image table-family preflight:

```text
$ uv run --no-sync python - <<'PY'
# run current preflight.py inside local Docker images for airbnb001, f1001, quickbooks001
PY
airbnb001: rc=2 status=failed db=airbnb missing=['calendar', 'listings', 'reviews'] forbidden=[] observed_sample=['raw_hosts', 'raw_listings', 'raw_reviews']
f1001: rc=0 status=passed db=f1 missing=[] forbidden=[] observed_sample=['circuits', 'constructor_fastest_laps_by_season', 'constructor_podiums_by_season', 'constructor_points', 'constructor_pole_positions_by_season', 'constructor_results', 'constructor_retirements_by_season', 'constructor_standings']
quickbooks001: rc=0 status=passed db=quickbooks missing=[] forbidden=[] observed_sample=['account_data', 'address_data', 'bill_data', 'bill_line_data', 'bill_linked_txn_data', 'bill_payment_data', 'bill_payment_line_data', 'bundle_data']
```

Dockerfile fail-closed smoke with synthetic F1 task view carrying a
QuickBooks-shaped `f1.duckdb`:

```text
$ uv run --no-sync python - <<'PY'
# materialize f1001 task view, then docker build with the injected preflight layer
PY
injection-order: True
docker-build-return-code: 1
#10 0.419 RAZORBACK_ADE_PREFLIGHT {"db_name": "f1", "db_path": "/app/f1.duckdb", "expected_db_name": "f1", "family": "f1", "forbidden_tables_observed": ["account_data", "bill_data", "invoice_data", "sales_receipt_data"], "missing_tables": ["circuits", "drivers", "races", "results", "status"], "observed_tables": ["account_data", "bill_data", "invoice_data", "sales_receipt_data"], "status": "failed", "task_id": "f1001"}
#10 ERROR: process "/bin/sh -c python /tmp/razorback_ade_preflight.py --task-id f1001 --workspace /app --db-name f1" did not complete successfully: exit code: 2
```

Small score/audit surface check:

```text
$ uv run --no-sync rk score tests/fixtures/score/ade_bench_run_dir --format json
"stratified_pass_at_1": 1.0
"stratified_n_completed": 3
"stratified_n_errored": 0

$ uv run --no-sync rk audit tests/fixtures/score/ade_bench_run_dir --policy strict --format json
"summary": {"clean": 0, "coverage_missing": 0, "tainted": 0}
```

## Acceptance Criteria

AC-1 - ADE task views preserve task-specific dbt data: FAIL.

The materializer injects preflight into all three real task views, and `f1001`
plus `quickbooks001` pass against local built images. `airbnb001` fails against
multiple local built images because the implementation expects tables that do
not exist in the actual task workspace. The failing output above is a concrete
blocker for the required three-family sample.

AC-2 - Mismatched ADE workspace data fails before Codex starts: PASS.

The focused runtime tests pass and include
`test_ade_preflight_failure_blocks_inner_codex_setup_as_infra_failure`. The
Docker build smoke also proves the injected Dockerfile preflight is executable
and fails closed with cross-family diagnostics before `CMD`; this addresses the
Dockerfile-preflight risk explicitly.

AC-3 - Goal 4 can restart from a valid multi-family smoke: FAIL.

A canonical multi-family smoke cannot be approved because `airbnb001` would
fail the new preflight on valid Airbnb source data before any solver trial. I
did not run the full ADE matrix. The score/audit CLIs were checked on the
small ADE fixture, but that is not a substitute for the required canonical
multi-family ADE smoke.

## Code Review

Requested protocol: `superpowers:requesting-code-review`. No callable Task
subagent is available in this Codex session, so I read the cached skill at
`/home/exedev/.codex/.tmp/plugins/plugins/superpowers/skills/requesting-code-review/SKILL.md`
and applied its checklist manually to `c90c44b..c920fa4`.

Blocking:

- `src/razorback/benchmarks/ade_bench/preflight.py:32-34` hard-codes the
  Airbnb sentinel tables as `calendar`, `listings`, and `reviews`. Real
  `airbnb001` images expose `raw_hosts`, `raw_listings`, and `raw_reviews`, so
  the new preflight rejects valid Airbnb tasks. Fix the Airbnb contract or
  derive source-table requirements from the task's dbt source metadata, then
  add a test/smoke that runs the preflight against a real built Airbnb
  workspace.

Non-blocking:

- `uv run pytest` currently fails during collection on the repo-wide stale
  `tests/unit/test_task_identity_scoring.py` import of deleted
  `razorback.score.load`. This branch does not touch `src/razorback/score` or
  that test, so I classify it as existing suite debt rather than this task's
  implementation bug.

## Gate Decision

REJECT to implementation.

Concrete fixes required:

1. Correct the Airbnb family contract to match real ADE `airbnb001` workspace
   source tables, or implement metadata-derived source-table contracts.
2. Extend tests/smoke evidence so `airbnb001`, `f1001`, and `quickbooks001`
   pass/fail for the right reasons against realistic DuckDB table names.
3. Rerun the focused preflight tests, the Dockerfile fail-closed smoke, and a
   small canonical multi-family ADE smoke before returning to validation.
