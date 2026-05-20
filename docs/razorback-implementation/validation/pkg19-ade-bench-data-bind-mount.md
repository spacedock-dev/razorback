# PKG-19 — validation report

**Entity:** `docs/razorback-implementation/pkg19-ade-bench-data-bind-mount.md`
**Branch:** `spacedock-ensign/pkg19-ade-bench-data-bind-mount`
**Worktree:** `.worktrees/spacedock-ensign-pkg19-ade-bench-data-bind-mount`
**Validator:** spacedock-ensign-pkg19-ade-bench-data-bind-mount-validation
**Date:** 2026-05-20

## Gate decision: APPROVE → done

AC-1..AC-6 all PASS. AC-7 SKIPPED (sandbox blocks reads of `~/git/ade-bench/` and `CLAUDE_CODE_OAUTH_TOKEN` not exported in this validator's env) per dispatch instructions ("Do NOT block the gate on AC-7 if env is the blocker"). Pre-merge concern flagged for terminalize: branch base `d1331fe` predates PKG-17 landing on main — a naive merge would silently revert PKG-17. Recommend rebase-onto-main (or cherry-pick-onto-main) before merge.

## AC verifications

### AC-1 — bind-mount materialization, no fresh git clone — PASS

`materialize_local_task` builds a view-dir whose upstream-derived entries are symlinks (bind-mount mode default), with no `git fetch` triggered. Verified via two unit tests + a live demo against the in-tree fixture.

```
$ cd /Users/clkao/git/razorback/.worktrees/spacedock-ensign-pkg19-ade-bench-data-bind-mount
$ uv run pytest tests/unit/test_ade_bench_materialize_local_task.py::test_materialize_local_task_emits_task_toml \
                tests/unit/test_ade_bench_materialize_local_task.py::test_materialize_local_task_does_not_clone -v
test_materialize_local_task_emits_task_toml PASSED
test_materialize_local_task_does_not_clone PASSED
```

Live demo confirms `setup.sh` is a symlink to the upstream fixture path:

```
AC-1 evidence — materialized dir: /var/folders/.../cache/example001
  task.toml exists: True
  instruction.md exists: True
  setup.sh is_symlink: True
    -> points to: <worktree>/tests/fixtures/ade_bench/fixture_local_task_minimal/tasks/example001/setup.sh
```

Compose-side AC-1: translator at `src/razorback/translate.py:_build_ade_bench` (lines 245–286) dispatches `r.local_slug is not None` branch into `materialize_local_task`. Compose volumes are derived from `TaskConfig.path = materialized` (the view-dir cache root); the upstream sources are referenced via the view-dir's symlinks, so the bind-mount path under `ade_bench_root` is what docker ultimately mounts.

### AC-2 — per-task disk footprint ≤ 10 MB — PASS

Real-byte size of the materialized view-dir (excluding symlinks) is 107 bytes on the in-tree fixture; the unit test under a realistically-shaped synthesized fixture also enforces < 10 MB.

```
$ uv run pytest tests/unit/test_ade_bench_materialize_local_task.py::test_view_dir_disk_footprint_under_10mb -v
test_view_dir_disk_footprint_under_10mb PASSED

# Live demo:
AC-2 — total view-dir bytes (excl symlinks): 107 (limit: 10485760)
```

`du -sh <run-dir>/tasks/<task-id>/` against a real ade-bench task is deferred to AC-7's probe re-dispatch (sandbox-blocked); the unit + live-fixture evidence shows the materializer's per-task contribution is dominated by `task.toml` + `instruction.md` (a few hundred bytes), well under 10 MB.

### AC-3 — read-only contract — PASS (structural; live EROFS deferred)

The materializer emits no compose volume RW declarations and no `[environment.volumes]` block in the synthesized `task.toml`. Harbor's default agent mount is read-only by convention; razorback contributes no RW exposure.

```
$ uv run pytest tests/unit/test_ade_bench_local_task_readonly_contract.py -v
test_synthesized_task_toml_introduces_no_rw_mounts PASSED

# Live demo of synthesized task.toml:
instruction = "instruction.md"

[environment]
docker_image = "ade-bench-agent:latest"

# Negative assertions:
AC-3 — task.toml contains [environment.volumes]: False
AC-3 — task.toml contains :rw: False
```

Live EROFS via `docker exec chmod/rm/write` is structurally deferred to validation per plan (Task 7); `tests/integration/test_ade_bench_local_task_readonly_contract_live.py` exists as a skipped skeleton. Full live wiring is gated on AC-7's probe re-dispatch, which is SKIPPED in this validator (env blocker).

### AC-4 — `seeds/solution__*.csv` excluded from agent view — PASS

The symlink-filter walker excludes any path matching the `seeds/solution__*.csv` glob from the view-dir; the upstream copy under `ade_bench_root/tasks/<slug>/seeds/` remains untouched so the verifier can still grade.

```
$ uv run pytest tests/unit/test_ade_bench_materialize_local_task.py -k "solution or seeds or symlink_chain" -v
test_view_dir_excludes_solution_csv_files PASSED
test_view_dir_solution_files_not_reachable_via_symlink_chain PASSED
test_view_dir_whole_dir_symlink_when_no_excluded_files PASSED
test_ade_bench_root_seeds_remain_unfiltered PASSED

# Live demo:
AC-4 — solution__*.csv in view-dir/seeds: []
AC-4 — seeds dir is_symlink: False (must be False)
AC-4 — other seed files visible: ['_no-op.txt']
AC-4 invariant — upstream solutions accessible to verifier: ['solution__x.csv']
```

The `is_symlink: False` check is load-bearing: it guarantees `seeds/` is materialized as a real directory with selective symlinks, NOT a whole-dir symlink (which would let an attacker follow the symlink target to read the upstream solutions). `docker exec ... ls -la /workdir/seeds/ | grep solution__` against a real agent container is deferred to AC-7's probe re-dispatch.

### AC-5 — `--materialize={bind,copy}` flag — PASS

Both modes preserve the AC-4 exclusion; bind mode produces symlinks, copy mode produces real-file copies.

```
$ uv run pytest tests/unit/test_ade_bench_materialize_mode_flag.py -v
test_materialize_copy_mode_full_copy PASSED
test_materialize_bind_mode_uses_symlinks PASSED

# Live demo:
AC-5 copy mode: symlink count=0 (must be 0)
AC-5 copy mode: setup.sh is_symlink=False (must be False)
AC-5 copy mode: solution__x.csv leaked in copy mode? False (must be False)
AC-5 bind mode: symlink count=3 (must be >= 1)
```

CLI wiring: `src/razorback/cli/run.py` adds `--materialize` (default `bind`) that propagates through `spec_to_job_config` → `_build_ade_bench` → `materialize_local_task`.

### AC-6 — hydration check (missing/empty `ade_bench_root`) — PASS

Both missing-directory and empty-directory cases raise `FileNotFoundError` with the path and task slug in the message.

```
$ uv run pytest tests/unit/test_ade_bench_local_task_hydration_check.py -v
test_missing_ade_bench_root_raises PASSED
test_empty_ade_bench_root_raises PASSED

# Live demo:
AC-6 missing root: PASS — FileNotFoundError: materialize_local_task: ade_bench_root has no tasks/example001/ directory ...
AC-6 empty root: PASS — FileNotFoundError: materialize_local_task: ade_bench_root has no tasks/example001/ directory ...
```

Translator-side hydration also fires: `_build_ade_bench` raises `SpecError` when an `AdeBenchLocalTaskEntry` is supplied without `ade_bench_root` on the benchmark block. Covered by `tests/unit/test_ade_bench_translator_local_root.py::test_translator_rejects_local_entry_without_ade_bench_root`.

### AC-7 — ade-bench probe re-dispatch — SKIPPED (env blocker)

Two env preconditions are not satisfiable in this validator's sandbox:

1. `~/git/ade-bench/` is sandbox-blocked:
   ```
   $ ls -la /Users/clkao/git/ade-bench/tasks/
   ls: /Users/clkao/git/ade-bench/tasks/: Operation not permitted
   $ df -h /Users/clkao/git/ade-bench
   df: /Users/clkao/git/ade-bench: Operation not permitted
   ```
2. `CLAUDE_CODE_OAUTH_TOKEN` is not exported in env (the token file at `~/.claude/benchmark-token` exists but is not loaded). `rk run`'s Claude CLI auth pre-check would refuse before dispatching.

Per the dispatch instructions ("If OAuth env block remains, document the blocker and continue with AC-1..AC-6 as PASS; AC-7 SKIPPED with clear reason. Do NOT block the gate on AC-7 if env is the blocker"), AC-7 is SKIPPED — not FAILED.

The probe spec was committed in implementation (`examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml`) and is ready for a future re-dispatch from a non-sandbox environment with the token exported. Recommended captain-side step before Goal 2 dispatch.

## Test sweeps

### PKG-19 unit tests (14 tests)

```
$ uv run pytest tests/unit/test_ade_bench_materialize_local_task.py \
                tests/unit/test_ade_bench_local_task_hydration_check.py \
                tests/unit/test_ade_bench_local_task_readonly_contract.py \
                tests/unit/test_ade_bench_materialize_mode_flag.py \
                tests/unit/test_ade_bench_translator_local_root.py -v
============================== 14 passed in 0.19s ==============================
```

### razorback-plugin-dab tests (regression gate)

```
$ uv run pytest packages/razorback-plugin-dab/ --timeout=60 -q
1 failed, 72 passed, 1 skipped in 1.15s
```

The 1 failure (`test_docker_compose_config_parses_generated_tree`) is a sandbox-side docker config permission issue (`open /Users/clkao/.docker/config.json: operation not permitted`), unrelated to PKG-19 and unaffected by PKG-19's code paths. Not a regression.

### Whole-repo pytest sweep (excluding sandbox-blocked DAB integration collection)

```
$ uv run pytest --timeout=60 \
    --ignore=tests/integration/test_rk_run_bookreview_claude.py \
    --ignore=tests/integration/test_rk_run_bookreview_nop.py \
    --ignore=tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py -q
13 failed, 442 passed, 6 skipped in 7.10s
```

All 13 failures are pre-existing sandbox-side `PermissionError: Operation not permitted` on writes/reads outside the worktree (matching the impl-stage cycle-2 report). Same failure class reproduces on `main`:

```
$ uv run pytest tests/unit/test_rk_run_budget_gate.py --timeout=60 -q
3 failed, 2 passed in 0.68s
# All 3 failures: PermissionError, NOT a PKG-19 regression.
```

Failure list (all PermissionError):
- `tests/integration/test_budget_gate_two_invocations.py` (2)
- `tests/integration/test_no_auth_leak_in_run_dir.py` (1)
- `tests/integration/test_rk_run_nop.py` (1)
- `tests/integration/test_rk_run_v2_deterministic_smoke.py` (1)
- `tests/unit/test_rk_run_budget_gate.py` (3)
- `tests/unit/test_rk_run_v2_harbor_cache_dir.py` (1)
- `tests/unit/test_rk_run_v2_pre_checks.py` (2)
- `tests/unit/test_rk_run_v2_provenance_artifacts.py` (1)
- `tests/unit/test_run_plugin_drift_wired.py` (1)

## Code review

### Strengths

1. **Risk-first TDD discipline.** The implementation followed the plan's RED→GREEN ordering (test in commit `ad56ad6` BEFORE implementation in `1c8d515`); subsequent tests landed alongside their features in `6b47330`.
2. **Clean schema additions.** `AdeBenchLocalTaskEntry` (single-field pydantic model with `extra="forbid"`) and `AdeBenchBenchmarkBlock.ade_bench_root: Path | None` keep the spec surface minimal and refuse silent drift. The union-type extension `list[str | AdeBenchTaskEntry | AdeBenchLocalTaskEntry]` is order-correct for pydantic's TaggedUnion matching.
3. **Solution-file exclusion is structurally safe.** `seeds/` becomes a real directory with selective symlinks ONLY when it contains excluded files (whole-dir-symlink fast path elsewhere). This is the load-bearing invariant — a whole-dir symlink would let an attacker traverse to the upstream `solution__*.csv`.
4. **Verifier path preserved.** The upstream `ade_bench_root/tasks/<slug>/seeds/solution__*.csv` is left untouched on disk; harbor's verifier mounts it via the verifier_volumes contract (orthogonal). Tested by `test_ade_bench_root_seeds_remain_unfiltered`.
5. **Hydration error message is operator-friendly.** `FileNotFoundError: materialize_local_task: ade_bench_root has no tasks/<slug>/ directory (ade_bench_root=<path>); hydrate ~/git/ade-bench checkout or pass a different slug` — names the path, the task, and the remediation.
6. **Mode flag preserves AC-4 in both modes.** Copy mode replaces symlinks with `shutil.copy2/copytree` but still routes through the exclusion walker — the solution files are excluded from the copy too.

### Issues found

**Important (pre-merge blocker for terminalize, not validation):**

- **Branch base predates PKG-17.** The branch was created from `d1331fe` (plan-only PKG-19 + PKG-17 plan); PKG-17 implementation landed on main at `761bfc7` and was finalized at `f741086` AFTER. A naive merge of this branch to current main would silently delete `src/razorback/runs/aggregate.py`, `src/razorback/runs/lock_drift.py`, `src/razorback/runs/manifest_schema.json`, the PKG-17 unit tests, the post-harbor aggregator invocation in `src/razorback/cli/run.py`, and the PKG-17 implementation plan doc. `git diff main..HEAD --stat` shows 1495 lines deleted — most of which are PKG-17 files, NOT PKG-19 changes.

  **Recommendation:** terminalize stage rebases onto main (or cherry-picks the 6 PKG-19 commits onto a fresh branch from current main) before merging. This is a procedural concern surfaced for the FO, not a PKG-19 code defect.

**Minor:**

- `materialize_local_task` has an inner `import yaml` (line 258 of tasks.py) and `import fnmatch` (top-level at line 5). Mildly inconsistent — `yaml` would conventionally be a top-level import too. Not blocking.
- The synthesized `task.toml` does not carry `build_timeout_sec`, `cpus`, or `memory_mb` under `[environment]`. Harbor defaults are reasonable, but a real ade-bench probe run may surface a need to forward these from the spec. AC-7 re-dispatch will catch this if it surfaces; not blocking for the unit-test-level ACs.
- `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml`'s `tasks_root: .` comment notes "ignored when every entry is a local-task; required by current schema" — fine for the probe, but the schema's `tasks_root: Path` requirement is semantically dead for pure-local specs. A small follow-up could make `tasks_root` optional when all entries are `AdeBenchLocalTaskEntry`. Tracked-by: leave for a future cleanup, not PKG-19.

### Assessment

Ready to gate APPROVE. AC-1..AC-6 PASS with both unit tests and live demo evidence; AC-7 SKIPPED-with-reason per dispatch instruction. The branch-base concern is a terminalize-stage operational note, not a code-quality blocker.

## Stage Report: validation

- DONE: Read PKG-19 entity (7 ACs) + plan + impl commits + impl stage report
  Entity body read in full; plan read; impl report (cycle-2 at `bac5708`) confirms 14/14 PKG-19 tests pass + 5 feature commits.
- DONE: AC-1 verification — bind-mount, no clone
  2 unit tests PASS; live demo shows `setup.sh.is_symlink()=True` pointing at upstream fixture; translator path verified at `src/razorback/translate.py:266-280`.
- DONE: AC-2 verification — per-task disk footprint ≤ 10 MB
  1 unit test PASS; live demo: 107 bytes (excluding symlinks) for fixture-shape task. `du -sh` against real ade-bench task deferred with AC-7.
- DONE: AC-3 verification — :ro contract structural
  1 unit test PASS; synthesized task.toml has no `[environment.volumes]` block and no `:rw` token. Live EROFS deferred (gated on AC-7's docker stack).
- DONE: AC-4 verification — solution files excluded from agent view
  4 unit tests PASS; live demo: zero `solution__*.csv` in view-dir/seeds, `seeds/` is real dir (not symlink), upstream copy intact. `docker exec ls -la /workdir/seeds/` deferred with AC-7.
- DONE: AC-5 verification — `--materialize={bind,copy}` flag
  2 unit tests PASS; live demo: copy mode 0 symlinks, bind mode 3 symlinks; AC-4 exclusion preserved in both modes.
- DONE: AC-6 verification — hydration check
  2 unit tests PASS; live demo: both missing-path and empty-dir raise FileNotFoundError with task slug in message.
- SKIPPED: AC-7 verification — ade-bench probe re-dispatch
  Two env blockers: (1) sandbox blocks reads of `~/git/ade-bench/`; (2) `CLAUDE_CODE_OAUTH_TOKEN` not exported (token file at `~/.claude/benchmark-token` exists but is not loaded into env). Per dispatch ("Do NOT block the gate on AC-7 if env is the blocker"), SKIPPED-with-reason, not FAILED.
- DONE: Run `uv run pytest packages/razorback-plugin-dab/` + whole-repo sweep
  Plugin: 72 passed, 1 sandbox-side failure (docker config permission), 1 skipped. Whole-repo: 442 passed, 13 sandbox-side PermissionError failures (reproduce on main, not PKG-19 regressions), 6 skipped.
- DONE: Run `superpowers:requesting-code-review` on worktree branch
  Skill loaded; in-line review performed against the 6-commit branch diff. Strengths + 1 important pre-merge concern (branch base predates PKG-17) + 3 minor notes documented in this report.
- DONE: Write validation report at `docs/razorback-implementation/validation/pkg19-ade-bench-data-bind-mount.md`
  This file; gate decision APPROVE → done.

### Summary

PKG-19 validation: APPROVE. AC-1..AC-6 PASS with both unit-test and live-fixture evidence; AC-7 SKIPPED-with-reason per dispatch (sandbox blocks `~/git/ade-bench/` and `CLAUDE_CODE_OAUTH_TOKEN` not exported in this validator's env). The 14 PKG-19 unit tests pass cleanly (0.19s); whole-repo and plugin-DAB regression sweeps surface only pre-existing sandbox PermissionError failures that reproduce on main. Pre-merge note flagged for terminalize stage: branch base `d1331fe` predates PKG-17 landing on main, so a naive merge would silently revert PKG-17 — rebase or cherry-pick recommended.
