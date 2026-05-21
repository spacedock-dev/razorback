---
id: xq336j093p6a9w69cp49xkn4
title: PKG-21 — harbor-DAB SQLite/DuckDB bind-mount (close PKG-14's per-cell 7GB copy gap)
status: plan
source: PKG-14 follow-up — Goal 1 matrix ENOSPC 2026-05-20 at cell [20/36] direct-structured/PANCANCER_ATLAS (commit dae5d33 on spacedock-ensign/goal1-dab-paper-reproduction)
started: 2026-05-21T01:52:38Z
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
---

## Problem

PKG-14 closed the per-cell dump-copy gap for postgres and mongo
datasets (the bind-mount excludes `_dump_basenames(db_config)` from
the agent workdir). It did NOT close the same gap for SQLite or
DuckDB datasets: live `.db` and `.duckdb` files still go through
`shutil.copytree()` into each cell's workdir under
`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`
lines 246-262. The pancancer dataset's `pancancer_molecular.db`
weighs ~7 GB, music-brainz weighs ~5 GB, github-repos and
deps-dev-v1 are also multi-GB.

The comment at line 237-240 records the original intent:
> "Sqlite/duckdb live DB files stay in the workdir (the agent reads them)."

That intent is correct — the agent reads SQLite/DuckDB directly,
which is part of the dataset's contract. The bug is that
`shutil.copytree` is the wrong mechanism for keeping that access:
it duplicates 7 GB per cell.

Goal 1's matrix at N=1 × 12 datasets × 3 variants = 36 cells.
PANCANCER_ATLAS × 3 variants = 21 GB just for that one dataset.
Total matrix disk pressure exceeded 30 GB and bombed at cell
[20/36] with `OSError(28) No space left on device`. The host
filesystem went from 58 GiB free at session start to 1.2 GiB
free at ENOSPC.

## Acceptance criteria

**AC-1 — SQLite/DuckDB datasets bind-mount via APFS clonefile (or
equivalent CoW) rather than full copy.** Under
`materialize_mode="bind"` (default), live `.db` and `.duckdb`
files referenced from `dataset_dir` are reflected into the agent
workdir via `cp -c` (APFS clonefile, copy-on-write — 0-byte
logical reference until write). The agent retains read AND
write access; writes create a CoW divergence local to the cell.
Verified by: unit test asserts that for a SQLite-backed dataset
fixture (≥100 MB), the per-cell on-disk delta (measured via
`du -B1 task_dir`) stays below 1 MB until the cell writes.

**AC-2 — Fallback for non-APFS filesystems.**
On non-APFS hosts (Linux, ext4), the materializer falls back to
hardlink (`os.link`) when the source and target are on the same
device. Writes inside the workdir then break the link via
copy-on-write at filesystem level (most filesystems handle this
implicitly when one inode is opened for write). If neither
clonefile nor hardlink is available, the materializer raises a
clear error naming the unsupported filesystem rather than silently
falling back to copytree.
Verified by: unit test mocks `os.statvfs` / `cp -c` failure and
asserts the fallback ordering; integration test on ext4
(via `tmpfs` fixture or docker-in-docker) asserts hardlink
behavior.

**AC-3 — `materialize_mode="copy"` preserves full-copy semantics.**
The opt-out path (`materialize_mode="copy"`) continues to do
`shutil.copytree()` for provenance-strict / self-contained-tarball
runs. PKG-21 only changes the `"bind"` default.
Verified by: existing PKG-14 tests stay green; a regression test
asserts `materialize_mode="copy"` produces a full physical copy.

**AC-4 — Smoke against the failing dataset.**
A live `rk run` of any one PANCANCER_ATLAS cell (the dataset that
ENOSPC'd Goal 1) completes from materialize → harbor up → agent
turn → verify, with per-cell on-disk delta under 100 MB (down
from the 7 GB the bug produced).
Verified by: a live single-cell run committed at
`docs/razorback-implementation/validation/pkg21-harbor-dab-sqlite-duckdb-bind/pancancer-smoke.md`
records the disk delta with `du -sh` before/after.

## Test plan

- **Unit:** `packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py`
  extends with cases for AC-1 (SQLite clonefile), AC-2 (hardlink
  fallback), AC-3 (copy mode regression).
- **Integration:** A new test (or extension of
  `test_compose_postgres.py`'s integration counterpart) materializes
  a SQLite-backed task and asserts disk-delta < 1 MB.
- **Acceptance:** `rk run` against PANCANCER_ATLAS smoke produces a
  result.json AND `du -sh task_dir` shows <100 MB.

## Out of scope

- The PKG-15 mongo healthcheck failure observed in Goal 1's
  `direct-minimal/agnews` (`mongorestore .sh` shim runs but mongo
  takes >60s to initialize, healthcheck times out at 12×5s retries).
  Filed for next session; PKG-21 only addresses the disk burn.
- Goal 1 matrix re-dispatch logistics — separate Goal 1 resume
  task after PKG-21 ships.
- Cleanup of existing 26 GB direct-minimal/ task subdirs on disk
  — that's a one-time recovery the FO handles now via captain's
  aggressive-cleanup directive, not PKG-21's scope.

## Depends on

- PKG-14 (data bind-mount + DB volume reuse) — shipped, this entity
  extends it to SQLite/DuckDB
- macOS APFS clonefile (`cp -c`) — host filesystem capability we
  exploit on darwin

## Resume hook

After PKG-21 merges to main, re-dispatch Goal 1's implementation
stage to resume the matrix:
1. Goal 1 worktree at
   `.worktrees/spacedock-ensign-goal1-dab-paper-reproduction`
   retains the 16 completed cells' scores + spec.frozen.yaml +
   provenance.yaml (small artifacts; tasks/ subdirs may be cleaned
   by FO).
2. Matrix driver is idempotent: cells with valid result.json
   skip; missing cells re-dispatch. Spacedock variant (0/12 run)
   + the 4 missing direct-structured cells + any direct-minimal
   cells that failed mongo healthcheck (agnews, yelp likely) get
   re-dispatched.
3. With PKG-21's CoW materialization, the resumed matrix's total
   on-disk footprint stays under 5 GB for the remaining ~18 cells.
