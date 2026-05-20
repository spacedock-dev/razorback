---
id: f7aysbtft576c30q9zxaz62z
title: PKG-14 — harbor-DAB plugin reuses LFS data + postgres DB volume across trials
status: backlog
source: Captain question 2026-05-20 during PKG-13 ENOSPC blocker; captain follow-up 2026-05-20 on cross-variant DB reuse; disk + time math for Goal 1 matrix
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

Goal 1's matrix runs 3 variants × 12 datasets × N=1..5 trials. Two independent perf/disk problems compound at matrix scale:

**Problem A — dataset-source copy duplication.** The harbor-DAB plugin currently materializes per-(dataset, query) task workdirs by **copying** the dataset subtree via `shutil.copy*` (per `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py:_materialize_task_dir`). Compose bind-mounts then reference the COPIED files at `./workdir/{sql_file}`.

Disk math for the matrix:

- Source data at `~/git/dataagentbench/data/`: 7.8GB total across 12 datasets (~650MB average per dataset).
- Per-trial materialization copies the relevant `query_dataset/` subtree.
- Worst-case duplication: ~117GB for the full matrix at N=5; ~23GB at N=1.

This caused the PKG-13 ENOSPC mid-implementation and ENOSPC again on rebuild at session 2026-05-20 (1.9GiB free target couldn't be sustained).

**Fix A:** bind-mount the existing `~/git/dataagentbench/data/query_<dataset>/` paths read-only directly from the compose, instead of copying to per-task workdirs. The plugin already accepts `--data-root` and knows the dataset path; this is a `compose.py` + `prepare.py` source-resolution change.

**Problem B — postgres init-from-dump re-runs per trial.** Each per-trial compose currently brings up a fresh `dab-postgres` container with an EMPTY data volume and runs the `/docker-entrypoint-initdb.d/*.sql` dump file at boot. For a typical DAB dataset, this `psql < books_info.sql` boot-time init takes 30s-3min depending on dataset size. At matrix scale (3 variants × 12 datasets × N=1 = 36 trials), the same dataset's DB gets re-initialized 3 times (once per variant); at N=5, 15 times. This is wall-clock waste AND disk churn on the volume that gets created and torn down per trial.

**Fix B:** per-dataset NAMED postgres data volume that persists across trials of the same dataset. The compose generator emits a stable volume name keyed on the dataset (e.g., `dab-postgres-data-{dataset}-v1`); the volume is created and seeded ONCE per dataset (first trial of any variant on that dataset runs the init); subsequent trials on the same dataset (any variant, any N) attach the existing volume with the data already loaded. Postgres detects the existing data and skips `docker-entrypoint-initdb.d/*` execution per its standard semantics.

Fix B is independent of Fix A — Fix A removes the per-trial dataset copy on the host; Fix B removes the per-trial DB-init wall-clock cost. Both are needed for Goal 1's matrix to run within the captain's autonomy envelope.

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

**AC-7 — Per-dataset NAMED postgres data volume persists across trials.**
The compose generator emits a stable, dataset-keyed NAMED volume for the postgres data directory (e.g., `dab-postgres-data-{dataset}-v1`), not an anonymous per-task volume. The volume name is a function of `(dataset, schema_version)` only — NOT of `(variant, trial_idx, task_id)` — so the SAME volume attaches across:
- Different `workspace_variant` values (`direct-minimal`, `direct-structured`, `spacedock`).
- Different trial indices within a variant (N=1..N=5).
- Different harbor task-ids on the same dataset.

Verified by: a fresh `harbor task generate` against bookreview + spacedock variant and another against bookreview + direct-minimal variant produce compose files that reference IDENTICAL volume names for the postgres data path. A `docker volume ls` after running both shows ONE `dab-postgres-data-bookreview-v1` volume, not two.

**AC-8 — Second trial on same dataset skips dump-file init (postgres detects pre-initialized volume).**
After the FIRST trial on a given dataset completes (which runs `docker-entrypoint-initdb.d/*.sql` against an empty volume), subsequent trials on the SAME dataset (any variant, any trial idx) bring up `dab-postgres` against the existing populated volume; postgres detects the existing PG_DATA per its standard semantics and SKIPS the `docker-entrypoint-initdb.d/*` execution.

Verified by: a two-trial smoke (trial 1 = direct-minimal, trial 2 = spacedock, both on bookreview). Trial 1's `dab-postgres` container logs show `running /docker-entrypoint-initdb.d/books_info.sql`. Trial 2's `dab-postgres` container logs show `PostgreSQL Database directory appears to contain a database; Skipping initialization` and DO NOT show `running /docker-entrypoint-initdb.d/`. Wall-clock for trial 2's `dab-postgres` reachability ≤ 10s (vs trial 1's ~30s-3min depending on dataset).

**AC-9 — Schema bump invalidates old volumes (forward-compat safety).**
The volume name includes a schema version suffix (`-v1`, `-v2`, ...) so that future changes to the dump-file contents (e.g., new query rows, schema migrations) can be invalidated by bumping the suffix without manual `docker volume rm`. The plugin reads the schema version from a `schema_version:` field in the dataset catalog (default `v1`).

Verified by: a unit test bumps the dataset's `schema_version` to `v2`, regenerates the compose, and asserts the new volume name is `dab-postgres-data-{dataset}-v2` (distinct from the v1 volume).

**AC-10 — Volume-reuse contract works with the read-only data bind-mount (AC-3).**
The bind-mount mode (AC-1, AC-3) and the volume-reuse (AC-7, AC-8) compose correctly — the dump-file SQL is bind-mounted read-only from `data_root`, and the postgres data volume is a separate NAMED volume that postgres writes into on first boot and reads on subsequent boots. Neither mode interferes with the other.

Verified by: the two-trial smoke above runs under the bind-mount default (AC-1); both ACs (AC-3 EROFS on source data, AC-8 skip-init on second trial) hold simultaneously.

**AC-11 — Optional fresh-volume override for clean-run requests.**
The plugin exposes `--postgres-volume-mode={reuse,fresh}` (or equivalent flag) where `reuse` is the default and `fresh` forces a unique per-task volume name (the current behavior). This lets operators force a clean DB init when investigating a suspected pollution issue, without removing the optimization for the matrix case.

Verified by: a unit test exercises both modes and confirms the compose's volume name carries a per-task hash under `fresh` mode and the stable dataset-keyed name under `reuse` mode.

## Test plan

- Plan stage reviews PKG-13's compose generator changes and identifies the touchpoints in `compose.py` and `prepare.py` where copy → bind-mount switches (AC-1) AND where anonymous postgres volumes → dataset-keyed NAMED volumes (AC-7).
- Implementation stage applies both changes TDD-first; runs the existing 70+ plugin unit tests after each task to ensure no regression.
- Validation stage exercises:
  - Disk-delta test (AC-2) on a real run.
  - Read-only contract test (AC-3) under a real Docker invocation.
  - Two-trial cross-variant smoke (AC-7, AC-8) confirming postgres init runs ONCE per dataset, not once per variant.
  - Schema-bump invalidation (AC-9) via fixture.

## Out of scope

- Generalizing to ade-bench (Goal 2's blocker; separate entity if needed).
- Optimizing harbor's own image cache or build cache (orthogonal disk concern).
- Re-running Goal 1 itself; that's the goal1 entity, downstream of PKG-14.
- mongo-side volume reuse. If/when the harbor-DAB mongo path is wired up (dab-mongo-probe report), an analogous AC for the mongo init.js volume reuse will be a follow-up entity; PKG-14 scopes the postgres path only because that's what Goal 1's 12-dataset matrix exercises today.

## Depends on

- PKG-13 (DONE) — the compose-loading + reachability gate works on main; PKG-14 modifies the same compose-generation code path PKG-13 hardened.
- 51 phase2-dab-harbor-adapter (DONE) — bind-mount + volume-reuse work is on its plugin shape.

## Blocks

- Goal 1 — DAB paper reproduction (disk-feasibility constraint + cross-variant DB-reuse wall-clock constraint; captain explicitly called out "we need to run both dab-minimum and dab-spacedock, we don't want to re-instantiate the db" on 2026-05-20).
- Goal 2 — ade-bench Haiku baseline (disk-feasibility for matrix; ade-bench plugin's per-task disk profile is investigated separately by the ade-bench probe).
