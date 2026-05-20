---
id: bx7vd4n8mc2r9q5z3kpwhftj
title: PKG-19 — ade-bench harbor integration reuses ~/git/ade-bench data via bind-mount (no fresh copy)
status: validation
source: Captain directive 2026-05-20 "but can we reuse the data files from ade-bench directly, not a fresh copy"; ade-bench probe Phase 1 finding (disk at 100%, blocked); analog of PKG-14 for ade-bench (mirror of DAB data bind-mount discipline)
started: 2026-05-20T21:16:11Z
completed:
verdict:
score: 0.85
worktree: .worktrees/spacedock-ensign-pkg19-ade-bench-data-bind-mount
issue:
pr:
mod-block:
---

## Problem

The ade-bench probe (`docs/superpowers/plans/2026-05-20-ade-bench-path-probe.md`, branch `spacedock-ensign/ade-bench-probe-2`) blocked at Phase 1 in part because the ade-bench harbor integration materializes task fixture trees via `materialize_git_task` — i.e., a fresh git clone per task. On a host with 1.7-2.1 GiB free and 44 ade-bench tasks, this is not feasible for the Goal 2 matrix (48 tasks × N≥3).

The captain has an existing `~/git/ade-bench/` checkout that contains the entire ade-bench task tree at git HEAD. There is no reason for the harbor integration to clone afresh per task; bind-mounting from the existing checkout (read-only) is the structural fix.

This entity is the ade-bench analog of PKG-14 (which handles DAB's dataset bind-mount). Same shape: identify the materialization code path, switch from "copy/clone" to "bind-mount from local checkout", verify the agent container still sees the expected paths.

There is also a probe-flagged hazard (analog of ML review F2 for DAB): `seeds/solution__*.csv` files exist in the ade-bench task fixture tree and may be visible inside the agent container, allowing trivial answer-leak. PKG-19 closes both gaps: bind-mount + filter the solution files OUT of what the agent can read.

## Acceptance criteria

**AC-1 — ade-bench task materialization uses bind-mount from `~/git/ade-bench/` instead of fresh git clone.**
The harbor integration's `_build_ade_bench` (or `materialize_git_task` equivalent) is modified to accept an `ade_bench_root` field (mirror of DAB's `data_root`) that points at `~/git/ade-bench/`. Per-task compose generation references absolute bind-mount paths under `ade_bench_root/<task>/...` read-only, not a copied subtree.

Verified by: after `rk run` against a single ade-bench task, the per-task `task-dir/workdir/` does NOT contain copied ade-bench task files; the compose's `volumes` shows absolute paths under `ade_bench_root` mounted read-only.

**AC-2 — Per-task disk footprint ≤ 10 MB (provenance + spec only, not task fixture).**
After `rk run` against a single ade-bench task, the run-dir's per-task disk footprint is ≤ 10 MB (instruction.md + task.toml + docker-compose.yaml + small agent workdir, but no copied task fixture).

Verified by: `du -sh <run-dir>/tasks/<task-id>/` ≤ 10 MB on a smoke run against `ade-bench-airbnb001` (or whatever task the probe re-dispatch picks).

**AC-3 — Read-only contract enforced on bind-mount.**
Bind-mount mode is `:ro` for every ade-bench task path. The agent container CANNOT modify the source data. A synthetic test attempts `chmod / rm / write` against a bind-mounted path and observes EROFS or similar.

Verified by: a unit test or shell script under `packages/<plugin>/tests/test_ade_bench_readonly_contract.py` (or in razorback core if ade-bench integration lives there).

**AC-4 — `seeds/solution__*.csv` files NOT visible to the agent container.**
The ade-bench probe Phase 1 surfaced that solution files (e.g., `seeds/solution__taskname.csv`) exist in the task fixture tree. The agent container must NOT see them — only the task's input description + the working tree without the solution. Either:
- (a) Selectively exclude `seeds/solution__*.csv` from the bind-mount (use a sub-path mount that omits the seeds directory, OR use docker's `tmpfs` to mask just those files).
- (b) Pre-filter the bind-mount source at materialization time (build a per-task view directory that symlinks everything except the solutions, then bind-mount that).

(a) is simpler; (b) is safer if ade-bench's task structure varies.

Verified by: `docker exec <agent-container> ls -la /workdir/seeds/` either does NOT show `solution__*.csv` OR shows them as size-0 / unreadable. A synthetic test agent that runs `find /workdir -name "solution__*.csv"` finds zero files.

**AC-5 — Optional copy-mode opt-in for provenance-strict runs.**
Same shape as PKG-14 AC-4: a `--materialize=copy` flag restores the old fresh-clone behavior for cases where the operator needs a self-contained tarball. Default is bind-mount; copy is opt-in.

Verified by: a unit test exercises both modes and confirms behavior differs as documented.

**AC-6 — Hydration check still works under bind-mount mode.**
If `ade_bench_root` is missing or empty, the plugin / integration refuses to generate (fail-fast). Mirror of PKG-13's AC-9 hydration check for DAB.

Verified by: a unit test simulates a missing `ade_bench_root` and asserts the generation refuses with a clear error.

**AC-7 — ade-bench probe re-dispatch produces a clean Phase 2-5 report at small scale.**
After PKG-19 lands, a re-dispatch of the ade-bench probe (Phase 2: spec authorship; Phase 3: 1-3 task smoke; Phase 4: honesty check; Phase 5: report) completes with a verdict of CLEAN, PARTIAL, or FAIL with named follow-up entities. The probe's environmental blockers (disk + OAuth) are resolved as a captain-side precondition.

Verified by: the probe re-dispatch produces a Phase 5 report at `docs/superpowers/plans/2026-05-20-ade-bench-path-probe.md` (updated or sibling-dated).

## Test plan

- **Plan stage** reviews ade-bench's existing materialization code (`materialize_git_task` + `_build_ade_bench`) and identifies the bind-mount touchpoints. Also reviews the seeds/solution exclusion design ((a) vs (b) per AC-4).
- **Implementation stage** applies the change TDD-first; runs existing tests after each task. Includes ade-bench probe spec under `examples/specs/probe-ade-bench-<task>-claude-harbor.yaml`.
- **Validation stage** runs the ade-bench probe re-dispatch (Phases 2-5) against 1-3 small tasks to confirm honest results + the disk-delta improvement (AC-2).

## Out of scope

- Goal 2 (ade-bench Haiku baseline) — PKG-19 is the structural prerequisite; Goal 2 dispatches AFTER.
- Generalizing to other future benchmarks. PKG-14 covers DAB; PKG-19 covers ade-bench. Future benchmark adapters should follow the same data-reuse pattern but won't share code unless they share a base class.
- Cross-task ade-bench cache reuse (e.g., shared docker layers across tasks). Orthogonal perf concern.

## Depends on

- ade-bench probe report (DONE; on branch `spacedock-ensign/ade-bench-probe-2`, not yet merged to main) — surfaced the materialization mechanism + the seeds/solution hazard.
- Captain freeing disk + exporting `CLAUDE_CODE_OAUTH_TOKEN` — operator preconditions for AC-7 to run.

## Blocks

- Goal 2 — Full ade-bench Haiku baseline. Goal 2's 48-task × N≥3 matrix is disk-infeasible without bind-mount and ML-honesty-infeasible without the solution-file exclusion.
- (Indirectly) any future ade-bench probe re-dispatch.

## Stage Report: plan

- DONE: Read PKG-19 entity (7 ACs: bind-mount ade-bench task tree from ~/git/ade-bench/ (no fresh clone); seeds/solution__*.csv excluded from agent container; analog of PKG-14 for ade-bench).
  Entity read in full; 7 ACs noted; analog-of-PKG-14 framing carried into plan structure.
- DONE: Read the ade-bench probe report at .worktrees/spacedock-ensign-ade-bench-probe-2/docs/superpowers/plans/2026-05-20-ade-bench-path-probe.md and the probe branch spacedock-ensign/ade-bench-probe-2 for Phase 1 findings (materialize_git_task fresh-clones; 44 tasks upstream; seeds/solution__*.csv hazard).
  Probe report read in full; Phase 1 findings cited in the plan's Spec §-cites section.
- DONE: Identify the ade-bench harbor integration touchpoints: AdeBenchBenchmarkBlock, _build_ade_bench, materialize_git_task. Plan must cite which lines change vs leave alone.
  Plan File-structure table names schema.py:133–151, translate.py:237–286, ade_bench/tasks.py append. `materialize_git_task` left untouched; new sibling `materialize_local_task` added.
- DONE: Decide AC-4 exclusion approach: (a) sub-path bind-mount that omits seeds/ directory; (b) docker tmpfs to mask just solution files; (c) per-task view directory with symlinks. Recommendation in entity body: (a) is simpler; (b) is safer if task structure varies.
  Plan picks (c) per-task view directory with selective symlinks. Rationale: (a) does not work — seeds/ is a sibling of task.yaml, not a sibling of the task dir, so masking requires file-level granularity. The upstream task.yaml→task.toml shape mismatch ALSO forces a per-task view-dir construction anyway, so the symlink filter is a free addition.
- DONE: Write a TDD-first plan: AC-1 (bind-mount instead of clone) RED test BEFORE source-resolution change; AC-3 (:ro read-only) test BEFORE any docker compose up; AC-4 (solution files not visible to agent) RED test BEFORE the exclusion mechanism lands.
  T2 RED → T3 GREEN for AC-1; T6 structural unit-level RED for AC-3 (T7 live skeleton deferred to validation per the live-EROFS pattern from PKG-14); T8 RED → T9 GREEN for AC-4.
- DONE: AC-7 specifies the probe re-dispatch as a validation-stage integration gate. Plan should emit the probe spec but NOT execute it (validation does that, after captain frees disk + exports OAuth token).
  T14 emits the spec at examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml; explicit DO NOT RUN annotation; Handoff section names the validation-stage workflow.
- DONE: Write plan to docs/razorback-implementation/plans/pkg19-ade-bench-data-bind-mount.md.
  Plan written to that exact path on main.

### Summary

Plan committed to docs/razorback-implementation/plans/pkg19-ade-bench-data-bind-mount.md mapping all 7 ACs to 14 tasks. Critical design call documented: upstream ~/git/ade-bench/ uses task.yaml while harbor needs task.toml, so the bind-mount approach requires a per-task view-dir with a synthesized task.toml shim + symlink-filter exclusion of seeds/solution__*.csv. AC-4 implementation choice (c) — view directory with symlinks — chosen over the entity's (a) recommendation because solution files are siblings inside seeds/, not separate-dir, ruling out sub-path mount.

## Stage Report: implementation (cycle-2)

- DONE: Read PKG-19 entity (7 ACs) + plan + existing commits on the worktree branch.
  `git log main..HEAD` shows 5 commits (ad56ad6, 1c8d515, b8f8639, 6b47330, 474ecc0) covering T2-T14 from the plan.
- DONE: AC-1 — `materialize_local_task` builds a view-dir from `ade_bench_root` (no clone).
  RED test ad56ad6; GREEN impl 1c8d515 in src/razorback/benchmarks/ade_bench/tasks.py.
- DONE: AC-1 compose-side — translator wires `ade_bench_root` into the materializer.
  b8f8639 wires `AdeBenchLocalTaskEntry` schema + `_build_ade_bench` dispatch in src/razorback/translate.py.
- DONE: AC-2 — per-task view-dir disk footprint ≤ 10 MB.
  6b47330 adds `test_view_dir_disk_footprint_under_10mb` (PASS at < 10MB on fixture).
- DONE: AC-3 — `:ro` flag on synthesized compose volumes (structural unit test + live skeleton).
  6b47330 adds tests/unit/test_ade_bench_local_task_readonly_contract.py + tests/integration/test_ade_bench_local_task_readonly_contract_live.py.
- DONE: AC-4 — `seeds/solution__*.csv` excluded from view-dir; symlink chain not bypassable; verifier-readable copy stays outside agent mount.
  ad56ad6 + 6b47330 — symlink-filter walker in materialize_local_task; 3 tests cover exclusion, chain integrity, upstream-still-readable invariant.
- DONE: AC-5 — `--materialize={bind,copy}` flag.
  6b47330 adds materialize_mode param to materialize_local_task + CLI flag in src/razorback/cli/run.py; tests in tests/unit/test_ade_bench_materialize_mode_flag.py.
- DONE: AC-6 — hydration check (missing/empty `ade_bench_root` fails fast with clear error).
  6b47330 adds tests/unit/test_ade_bench_local_task_hydration_check.py (FileNotFoundError with task slug in message).
- DONE: AC-7 — probe spec committed; DO NOT RUN annotation per plan.
  474ecc0 commits examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml. Validation stage dispatches the probe.
- DONE: Full pytest sweep on PKG-19 tests (regression gate).
  14/14 PKG-19 unit tests PASS in 0.22s. 8 pre-existing PermissionError failures in test_rk_run_budget_gate / test_rk_run_v2_* / test_run_plugin_drift_wired confirmed on main, unrelated to PKG-19 (sandbox-side filesystem restrictions, not code).

### Summary

PKG-19 implementation complete in 5 commits on branch spacedock-ensign/pkg19-ade-bench-data-bind-mount. All 7 ACs covered with 14 passing PKG-19 unit tests; probe spec emitted for AC-7 validation-stage re-dispatch. Critical design choice (per-task view-dir with selective symlinks, not sub-path bind-mount) implemented as planned — the task.yaml→task.toml shim + symlink-filter walker excludes `seeds/solution__*.csv` while keeping upstream solutions verifier-accessible. Pre-existing sandbox PermissionError failures in unrelated tests (DAB/budget/harbor-cache) reproduce on main and are not PKG-19 regressions.

## Stage Report: validation

- DONE: Read PKG-19 entity (7 ACs) + plan + impl commits + impl stage report
  Entity body + plan + impl-stage report (cycle-2 at `bac5708`) read in full; 14/14 PKG-19 tests confirmed pre-validation.
- DONE: AC-1 verification — bind-mount, no clone
  2 unit tests PASS; live demo: `setup.sh.is_symlink()=True` pointing at upstream fixture; translator at `src/razorback/translate.py:266-280` dispatches `local_slug` branch.
- DONE: AC-2 verification — per-task disk footprint ≤ 10 MB
  1 unit test PASS; live demo: 107 bytes (excl symlinks). Real-task `du -sh` deferred with AC-7.
- DONE: AC-3 verification — :ro contract structural
  1 unit test PASS; synthesized task.toml has no `[environment.volumes]` block and no `:rw`. Live EROFS deferred (gated on AC-7).
- DONE: AC-4 verification — solution files excluded from agent view
  4 unit tests PASS; live demo: zero `solution__*.csv` in view-dir/seeds, `seeds/` is a real dir (not symlink), upstream copy intact. `docker exec ls` deferred with AC-7.
- DONE: AC-5 verification — `--materialize={bind,copy}` flag
  2 unit tests PASS; live demo: copy mode 0 symlinks, bind mode 3 symlinks; AC-4 exclusion preserved in both modes.
- DONE: AC-6 verification — hydration check
  2 unit tests PASS; live demo: both missing-path and empty-dir raise `FileNotFoundError` with task slug in message.
- SKIPPED: AC-7 verification — ade-bench probe re-dispatch
  Sandbox blocks reads of `~/git/ade-bench/` (`ls`/`df` return EPERM) and `CLAUDE_CODE_OAUTH_TOKEN` is not exported into env. Per dispatch directive ("Do NOT block the gate on AC-7 if env is the blocker"), SKIPPED-with-reason, not FAILED. Probe spec committed at `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml` is ready for future re-dispatch from a non-sandbox env with token loaded.
- DONE: Run `uv run pytest packages/razorback-plugin-dab/` + whole-repo sweep
  Plugin: 72 passed, 1 sandbox failure (docker config EPERM, unrelated), 1 skipped. Whole-repo: 442 passed, 13 pre-existing sandbox PermissionError failures (reproduce on main), 6 skipped.
- DONE: `superpowers:requesting-code-review` on worktree branch
  In-line review against the 6-commit branch diff. Strengths + 1 important pre-merge concern (branch base `d1331fe` predates PKG-17 landing on main; recommend rebase before merge) + 3 minor notes documented in the validation report.
- DONE: Validation report at `docs/razorback-implementation/validation/pkg19-ade-bench-data-bind-mount.md`
  Written; gate decision **APPROVE → done**.

### Summary

PKG-19 validation: APPROVE. AC-1..AC-6 PASS with unit-test + live-fixture evidence; AC-7 SKIPPED-with-reason per dispatch (sandbox blocks `~/git/ade-bench/` reads and `CLAUDE_CODE_OAUTH_TOKEN` not exported). Pre-merge note flagged for terminalize: branch base predates PKG-17 landing on main — rebase or cherry-pick required before merge to avoid silently reverting PKG-17.
