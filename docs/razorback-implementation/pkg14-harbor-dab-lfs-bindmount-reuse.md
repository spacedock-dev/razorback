---
id: f7aysbtft576c30q9zxaz62z
title: PKG-14 — harbor-DAB plugin reuses LFS data via bind-mount instead of copying
status: backlog
source: Captain question 2026-05-20 during PKG-13 ENOSPC blocker; disk math for Goal 1 matrix
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

The harbor-DAB plugin currently materializes per-(dataset, query) task workdirs by **copying** the dataset subtree via `shutil.copy*` (per `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py:_materialize_task_dir`). Compose bind-mounts then reference the COPIED files at `./workdir/{sql_file}`.

For Goal 1's matrix (3 variants × 12 datasets × N=5 = 180 trials), the disk math is roughly:

- Source data at `~/git/dataagentbench/data/`: 7.8GB total across 12 datasets (~650MB average per dataset).
- Per-trial materialization copies the relevant `query_dataset/` subtree.
- Worst-case duplication: ~117GB for the full matrix.

This caused the PKG-13 ENOSPC mid-implementation (~$5GiB target couldn't be sustained).

**Fix:** bind-mount the existing `~/git/dataagentbench/data/query_<dataset>/` paths read-only directly from the compose, instead of copying to per-task workdirs. The plugin already accepts `--data-root` and knows the dataset path; this is a `compose.py` + `prepare.py` source-resolution change.

## Acceptance criteria

**AC-1 — Compose bind-mount sources resolve to `data_root` paths, not workdir-relative copies.**
Generated `docker-compose.yaml` for dab-postgres / dab-mongo references the LFS data via absolute paths under the plugin's `--data-root` (e.g., `/Users/clkao/git/dataagentbench/data/query_bookreview/books_info.sql`). No `shutil.copy*` of dataset subtrees in the default materialization path.
Verified by: a fresh `harbor task list` against a generated task dir shows the compose volumes resolve to absolute `data_root` paths; the per-task `workdir/query_dataset/` directory does NOT exist by default.

**AC-2 — Run-dir disk delta drops to ≤10MB per task (provenance + spec only, not data).**
After `rk run` against a single (dataset, query) trial under the new bind-mount path, the trial's task-dir disk footprint is ≤10MB (instruction.md + task.toml + docker-compose.yaml + a small workdir for the agent's outputs, but no copied dataset).
Verified by: `du -sh <task-dir>` ≤ 10MB on a bookreview-q1 trial.

**AC-3 — Read-only contract enforced.**
Bind-mount mode is `:ro` for every dataset path. The agent container CANNOT modify the source data. A synthetic test attempts `chmod / rm / write` against a bind-mounted path and observes EROFS or similar.
Verified by: a unit test or shell script under `tests/integration/test_lfs_readonly_contract.py`.

**AC-4 — Optional copy-mode opt-in for provenance-strict runs.**
Plugin exposes `--materialize=copy` (or equivalent flag) that restores the old copy behavior. Default is bind-mount; copy is opt-in for runs where the operator needs a self-contained run-dir tarball.
Verified by: a unit test that exercises both modes and confirms behavior differs as documented.

**AC-5 — Hydration check still works under bind-mount mode.**
The existing AC-9 hydration check (PKG-13 inherits it; previously PKG-2 phase2) still detects LFS-pointer files at `data_root` and fails fast before the matrix begins. The bind-mount mode does not bypass hydration.
Verified by: existing `test_ac9_missing_dataset.py` continues to pass; a new synthetic test simulates an LFS-pointer at `data_root/query_bookreview/books_info.sql` and the plugin refuses to generate.

**AC-6 — Goal 1 matrix smoke under new path produces honest events.jsonl with `psql --host dab-postgres`.**
A single-dataset N=1 smoke run against bookreview produces an `events.jsonl` with at least one `psql` or `dab-postgres` connection event (per the PKG-13 AC-2 observability contract). This validates that the bind-mount path doesn't break the live-DB execution chain.
Verified by: `grep -E "psql|dab-postgres" <run-dir>/<trial>/events.jsonl` returns at least one hit.

## Test plan

- Plan stage reviews PKG-13's compose generator changes (AC-1+AC-4) and identifies the touchpoints in `compose.py` and `prepare.py` where copy → bind-mount switches.
- Implementation stage applies the path-resolution change TDD-first; runs the existing 49+ plugin unit tests after each task to ensure no regression.
- Validation stage exercises the disk-delta test (AC-2) on a real run and the read-only contract test (AC-3) under a real Docker invocation.

## Out of scope

- Generalizing to ade-bench (Goal 2's blocker; separate entity if needed).
- Optimizing harbor's own image cache or build cache (orthogonal disk concern).
- Re-running Goal 1 itself; that's the goal1 entity, downstream of PKG-14.

## Depends on

- PKG-13 (in implementation) — the compose-loading + reachability gate must work BEFORE the bind-mount optimization, otherwise we can't tell if a smoke failure is the bind-mount or the underlying stack.
- 51 phase2-dab-harbor-adapter (done; bind-mount work is on its plugin shape).

## Blocks

- Goal 1 — DAB paper reproduction (disk-feasibility constraint at 180 trials).
- Goal 2 — ade-bench Haiku baseline (similar disk profile if ade-bench plugin has the same copy pattern; investigate separately).
