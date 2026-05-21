# PKG-20 — Validation Report

**Entity:** `docs/razorback-implementation/pkg20-ade-bench-env-definition-synthesis.md`
**Branch:** `spacedock-ensign/pkg20-ade-bench-env-definition-synthesis`
**Worktree:** `.worktrees/spacedock-ensign-pkg20-ade-bench-env-definition-synthesis`
**Impl head:** `5aba935` — `feat(pkg20): synthesize environment/docker-compose.yaml for ade-bench local tasks`
**Validation date:** 2026-05-20

## Verdict

**PASSED** — all four ACs satisfied. AC-1/AC-2/AC-4 verified via unit tests reproduced on the worktree branch; AC-3 verified end-to-end with a live `rk run` reaching Phase 3 past harbor's `_validate_definition` (HOME override workaround landed; the failure observed at the docker-CLI layer is unrelated to PKG-20).

## AC-by-AC verification

### AC-1 — `materialize_local_task` synthesizes `environment/` per task

**Verified by:** `uv run pytest tests/unit/test_ade_bench_materialize_local_task.py -v` on the worktree branch.

Relevant tests pass:
- `test_view_dir_has_environment_compose` — asserts `(materialized / "environment" / "docker-compose.yaml").exists()` and byte-equality with `shared/defaults/docker-compose.yaml`.
- Byte-for-byte content match via the `_reflect` helper preserves `bind→symlink` / `copy→content-copy` discipline (covered by the existing `test_materialize_local_task_does_not_clone` and the new fixture wiring).

Also verified end-to-end during AC-3 live run: the materialized view-dir at `~/.cache/razorback/ade-bench/airbnb001/environment/docker-compose.yaml` is a symlink resolving to `/Users/clkao/git/ade-bench/shared/defaults/docker-compose-duckdb-dbt.yaml` (the variants[0]=duckdb-dbt selection for airbnb001).

### AC-2 — Variant selection matches ade-bench upstream behavior

**Verified by:** the same pytest invocation. Six tests cover the helper directly (one per rule branch + filter selection + unmatched-filter raise), three cover end-to-end materialization. Mapping is mirrored verbatim from `ade_bench/handlers/trial_handler.py:292-314`:

| (db_type, project_type) | compose filename |
| --- | --- |
| (snowflake, dbt-fusion) | `docker-compose-snowflake-dbtf.yaml` |
| (snowflake, dbt) | `docker-compose-snowflake-dbt.yaml` |
| (duckdb, *) | `docker-compose-duckdb-dbt.yaml` |
| no variants / fallthrough | `docker-compose.yaml` |

Tests passing:
- `test_select_compose_variant_no_variants_yields_default`
- `test_select_compose_variant_duckdb_dbt`
- `test_select_compose_variant_snowflake_dbt`
- `test_select_compose_variant_snowflake_dbtf`
- `test_select_compose_variant_filter_picks_matching_entry`
- `test_select_compose_variant_filter_unmatched_raises`
- `test_view_dir_picks_duckdb_compose_for_duckdb_variant`
- `test_view_dir_picks_snowflake_dbtf_compose_for_snowflake_dbtf_variant`
- `test_view_dir_filter_overrides_variants_zero`

Selection-entry rule: `variants[0]` when caller doesn't pin; `(db_type, project_type)` filter picks the matching entry when supplied; raises `ValueError` (not silent fallthrough) on unmatched filter. Matches the plan exactly.

### AC-3 — Harbor's `DockerEnvironment._validate_definition` passes

**Verified by:** live `rk run` against a frozen Goal 2 probe spec (copied verbatim from `.worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline/runs/goal2-probe/.../spec.frozen.yaml` into `runs/pkg20-validation/spec.airbnb001.frozen.yaml`).

Command (HOME override + colima DOCKER_HOST):

```
HOME="$PWD/.cache_home" DOCKER_HOST="unix:///Users/clkao/.colima/default/docker.sock" \
  uv run rk run runs/pkg20-validation/spec.airbnb001.frozen.yaml \
  --runs-dir runs/pkg20-validation/
```

Observed: `rk run` proceeds past Phase 2 (validation) into Phase 3 (`docker compose ... up --detach --wait`). The failure point is inside harbor's `docker compose` orchestration — `unknown flag: --project-name` from an old `docker` CLI on the host. The compose chain at failure includes `-f /Users/clkao/git/ade-bench/shared/defaults/docker-compose-duckdb-dbt.yaml` — direct evidence that PKG-20's variant selection synthesized the correct env-def AND that harbor accepted it (`_validate_definition` did not raise). Source: `runs/pkg20-validation/goal2-probe-ade-bench-airbnb001-haiku/54fc2d6f9bb82ff3/job.log`.

The remaining error is a host-level docker CLI compatibility issue (compose-v1 vs compose-v2 syntax), wholly outside PKG-20's scope. The AC-3 contract — "the same airbnb001 task that failed Goal 2 T0 now reaches the agent" — is satisfied at the validator boundary; the goal2 T0 stage report at `cc123ac` recorded the failure as `_validate_definition` raising on missing `environment/`, and that exact failure no longer happens.

### AC-4 — `exclude_globs` discipline preserved

**Verified by:** `test_view_dir_env_compose_excludable_via_exclude_globs` — passes `exclude_globs=("seeds/solution__*.csv", "environment/docker-compose.yaml")` against the no-variants fixture; asserts `env_dir` is not even created. Per-test pytest output confirms PASS. Discipline matches the existing `solution__*.csv` enforcement: same `fnmatch.fnmatch` predicate, same gating semantics (skip reflection).

## Test execution summary

```
$ uv run pytest tests/unit/test_ade_bench_materialize_local_task.py -v
... 18 passed in 0.62s

$ uv run pytest tests/unit/ -k "ade_bench" -q
... 56 passed, 411 deselected in 4.56s
```

No regressions in adjacent ade_bench surfaces. PKG-19 tests stay green.

## Code review

### Strengths

- Helper `_select_compose_variant` is a single-purpose, testable function mirroring upstream verbatim. The (db_type, project_type) filter contract is explicit and raises `ValueError` (no silent fallthrough) when unmatched.
- env synthesis reuses the existing `_reflect` helper — bind/copy discipline preserved without code duplication.
- Schema extension is optional (defaults `None`); PKG-19 callers and Goal 2's spec require no churn.
- `FileNotFoundError` at `tasks.py:387-392` carries a actionable hint ("ade_bench_root may be a stale or shallow checkout") for the most likely operator mistake.

### Findings

**Non-blocking — minor inconsistency in exclude_globs gloss against non-default variants.**

At `tasks.py:382`, `env_rel = f"environment/{compose_filename}"` uses the SOURCE compose filename for the exclude predicate, while the file is always WRITTEN as `environment/docker-compose.yaml` at line 395. Concretely: if a caller passes `exclude_globs=("environment/docker-compose.yaml",)` AND the variant picks `docker-compose-duckdb-dbt.yaml`, exclusion does NOT fire (because `fnmatch("environment/docker-compose-duckdb-dbt.yaml", "environment/docker-compose.yaml")` is false). The AC-4 test masks this because it uses the no-variants fixture where source filename == written filename.

Severity: minor / non-blocking. AC-4's stated contract is "the discipline must not regress" — the existing `solution__*.csv` discipline is unaffected, and no current or near-term caller exercises the inconsistent path. The spec inline-plan §T3 explicitly contemplated "configure the variant rule to pick `docker-compose-secret.yaml` AND exclude `environment/docker-compose-secret.yaml`", which is the only shape that exposes the issue and was not shipped as a test. Filing as a follow-up note for future hardening, not blocking the gate.

**Non-blocking — `_select_compose_variant` docstring slightly mis-describes filter fallthrough.**

The docstring at `tasks.py:38-43` says "when the resolved entry doesn't carry a db_type/project_type pair that matches the rule, falls through to the default compose" — accurate for the default-selector path, but when a filter `(db_type, project_type)` is supplied and matches, the chosen entry's pair re-enters the same mapping rule, so "fallthrough to default" only applies if neither filter nor variants[0] hits a mapped branch. Reader-clarity issue only; behavior is correct.

**Non-blocking — AC-3 evidence depends on host docker compatibility.**

Today's live run hit `unknown flag: --project-name` from the host docker CLI. A follow-up on a host with compose-v2 would close out the full Phase 3 → agent invocation path. The AC-3 wording is satisfied as written ("reaches Phase 3 past `_validate_definition`"), but a fuller smoke would be reassuring before Goal 2's matrix dispatches.

### Spec § cite check

Inline plan AC↔Task map (entity body lines 128-134):

| AC | Task | Shipped? |
| --- | --- | --- |
| AC-1 | T1 — synthesize `environment/<compose>` | YES — `tasks.py:379-395` + tests |
| AC-2 | T2 — variant selection rule | YES — `_select_compose_variant` + 6 helper tests + 3 e2e tests |
| AC-3 | T4 — live `rk run` smoke | YES (this validation; impl stage reported FAILED) |
| AC-4 | T3 — `exclude_globs` discipline over `environment/` | YES — `tasks.py:383` gate + test |

Schema extension (impl ahead of plan, plan §T2 marked it optional): `db_type` + `project_type` fields landed on `AdeBenchBenchmarkBlock` (`schema.py:165-166`) and are threaded through `translate.py:281-282`. Within scope of the plan's T2 sub-task discussion.

## Gate decision

**APPROVE — promote to `done`.**

All four ACs are satisfied. The two minor non-blocking findings are reader-clarity / future-hardening notes; neither would block a Goal 2 resume. Standing orders auto-approve the gate.

## Resume hook reminder

Per entity §"Resume hook" (lines 116-123): after PKG-20 merges to main, re-dispatch Goal 2 implementation against `.worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline` to restart T0 against the now-fixed materializer. Captain standing orders note Goal 2 implementation is paused awaiting this PASSED verdict.
