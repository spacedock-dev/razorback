---
id: bx7vd4n8mc2r9q5z3kpwhftj
title: PKG-19 — ade-bench harbor integration reuses ~/git/ade-bench data via bind-mount (no fresh copy)
status: backlog
source: Captain directive 2026-05-20 "but can we reuse the data files from ade-bench directly, not a fresh copy"; ade-bench probe Phase 1 finding (disk at 100%, blocked); analog of PKG-14 for ade-bench (mirror of DAB data bind-mount discipline)
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
