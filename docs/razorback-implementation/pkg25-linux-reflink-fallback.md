---
id: d1gb0y93se6wkmq88jkttxj5
title: PKG-25 — Linux reflink fallback (replace unsafe os.link with cp --reflink=auto)
status: plan
source: PKG-21 follow-up — captain probe 2026-05-20 ("PKG-21 bind-mount - is this portable? when we run this on linux?"); the docstring at packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py:371-373 misrepresents hardlink CoW semantics
started: 2026-05-21T05:51:57Z
completed:
verdict:
score: 0.9
worktree:
issue:
pr:
mod-block:
---

## Problem

PKG-21's `_clone_or_copy_tree` at `prepare.py:365-407` uses
`os.link` (hardlink) as the Linux fallback. This is **unsafe for
write workloads**:

- Hardlinks share an inode. Writing through either path mutates the
  shared inode; both paths see the change.
- The docstring at lines 371-373 claims "copy-on-write happens at
  the filesystem level when one inode is opened for write on a CoW
  filesystem". This is wrong. CoW filesystems (btrfs, ZFS, xfs,
  ext4 with reflink support) do CoW for **reflinks** (separate
  inodes pointing at shared blocks), not for **hardlinks**.

Practical consequences for SQLite/DuckDB datasets on Linux:
- The agent's container writes back to the workdir's `.db` file on
  WAL checkpoint (sqlite) or page flush (duckdb).
- That mutation propagates through the hardlink to the source
  `~/git/dataagentbench/data/<dataset>/query_dataset/*.db` — silent
  dataset corruption.

Additionally `os.link` raises `OSError(EXDEV)` if source and
destination are on different devices — common in containerized /
k8s setups where `data_root` and worktrees may live on different
volumes.

The correct mechanism is `cp --reflink=auto`: tries reflink first
(true CoW on btrfs / xfs / ext4-with-reflinks; same semantic as
APFS clonefile on darwin), falls back to a full physical copy on
filesystems that don't support reflink. The fallback is safe (no
silent inode sharing). Same UX as the existing `cp -c` on darwin
just with the Linux-portable `--reflink=auto` flag.

## Acceptance criteria

**AC-1 — Linux fallback uses `cp --reflink=auto`.**
`_clone_or_copy_tree` on `sys.platform == "linux"` invokes
`subprocess.run(["cp", "--reflink=auto", str(child), str(dst)],
check=True)` instead of `os.link(child, dst_child)`.
Verified by: unit test asserts the subprocess invocation pattern
on linux (mock sys.platform); manual test on a reflink-capable
filesystem (xfs or btrfs) asserts CoW behavior (write to dst does
NOT mutate src).

**AC-2 — Docstring is honest.**
The docstring at lines 365-386 no longer claims hardlink CoW; it
states explicitly:
- darwin: `cp -c` → APFS clonefile (true CoW)
- linux: `cp --reflink=auto` → reflink on supported filesystems
  (true CoW), full physical copy fallback otherwise (safe but no
  disk-savings on non-reflink filesystems)
- other: NotImplementedError
Verified by: docstring inspection; no "copy-on-write happens at
the filesystem level when one inode is opened for write" claim.

**AC-3 — Existing darwin behavior unchanged.**
darwin still uses `cp -c`; existing PKG-21 darwin tests (9/9
green) stay green.
Verified by: `uv run pytest
packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py`
passes on darwin.

**AC-4 — Cross-device tolerance.**
On linux, when src and dst are on different devices,
`cp --reflink=auto` falls back to full copy (does not raise
EXDEV). This is the correct safe behavior for the cross-device
case `os.link` could not handle.
Verified by: unit test (or integration test on a multi-device
fixture) asserts no EXDEV-style error on cross-device.

## Test plan

- **Unit:** `tests/unit/test_prepare_bind_materialize.py` adds:
  - a linux platform mock asserting `cp --reflink=auto`
    invocation
  - a docstring inspection test for AC-2
- **Integration (linux-only, skip if no linux runner):** assert
  reflink CoW on xfs/btrfs via a fixture file; assert full-copy
  fallback on a tmpfs/ext4-without-reflink mount.
- **Acceptance:** Existing PKG-21 darwin tests (9/9) stay green;
  the impl-stage live PANCANCER_ATLAS smoke (78 KiB/cell delta on
  darwin) is not affected.

## Out of scope

- Reflink optimization on darwin (already uses `cp -c` clonefile).
- Windows fallback — still NotImplementedError; opt into
  `materialize_mode="copy"`.
- Cross-platform fixture infrastructure beyond what already exists.

## Depends on

- PKG-21 (shipped) — this entity surgically fixes its Linux
  fallback

## Resume hook

After PKG-25 merges, future Linux production runs of harbor-DAB
are safe. No data-corruption risk on agent writes.
