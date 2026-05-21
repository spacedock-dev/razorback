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

## Implementation plan (inline)

Tiny task — single-file surgical fix. Plan is inline per FO
dispatch (4 ACs but one source file + one test file).

**Files touched**
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`
  (lines 365-405: `_clone_or_copy_tree`)
- `packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py`
  (rewrite the linux-branch test at lines 199-217; add cross-device test)

**TDD checkpoints (mechanism-first per PKG-25 standing order: risky
contract — wrong CoW primitive → silent data corruption — comes first)**

- **T0 (RED) — Linux invocation contract.** In
  `test_prepare_bind_materialize.py`, rename
  `test_bind_mode_linux_hardlink_fallback` → `test_bind_mode_linux_uses_reflink_cp`
  and rewrite it: monkeypatch `prepare_mod.sys.platform = "linux"`,
  monkeypatch `prepare_mod.subprocess.run` with a recording stub,
  invoke `prepare_dataset_tasks(..., materialize_mode="bind")`, then
  assert that **every** subprocess.run call for live-DB files had
  `argv == ["cp", "--reflink=auto", str(src), str(dst)]` (no
  `os.link` calls, no `cp -c` calls on the linux branch). Run pytest
  — confirm RED (fails because current code calls `os.link`, not
  subprocess.run with `cp --reflink=auto`). Governs AC-1.

- **T1 (GREEN) — Implementation swap.** In `prepare.py:399-400`,
  replace
  ```
  elif sys.platform == "linux":
      os.link(child, dst_child)
  ```
  with
  ```
  elif sys.platform == "linux":
      subprocess.run(
          ["cp", "--reflink=auto", str(child), str(dst_child)],
          check=True,
      )
  ```
  Pattern mirrors the darwin branch at lines 395-398 exactly except
  the flag (`--reflink=auto` vs `-c`). Run T0 test — confirm GREEN.
  Governs AC-1.

- **T2 (docstring) — AC-2 honest docstring.** Replace the
  `_clone_or_copy_tree` docstring (lines 366-386) with text that
  no longer claims hardlink CoW. New docstring states:
  - darwin: `cp -c` → APFS clonefile (true CoW)
  - linux: `cp --reflink=auto` → reflink on supported filesystems
    (btrfs / xfs / ext4-with-reflinks); falls back to full physical
    copy on filesystems without reflink support (safe — no inode
    sharing — but no disk-savings on those filesystems)
  - other: NotImplementedError naming sys.platform
  - Caveats section: drop the `os.link` EXDEV bullet (the new
    primitive handles cross-device by falling back to full copy);
    keep the darwin non-APFS EOPNOTSUPP bullet.
  Add a docstring inspection test (new test
  `test_clone_or_copy_tree_docstring_is_honest`) asserting
  the wrong claim string `"copy-on-write happens at the filesystem
  level when one inode is opened for write"` is absent and
  `"--reflink=auto"` is present in `_clone_or_copy_tree.__doc__`.
  Governs AC-2.

- **T3 (regression) — darwin path unchanged.** Run the full
  `test_prepare_bind_materialize.py` suite on darwin. The existing
  9/9 darwin tests stay green; the renamed linux test is now T0;
  the new docstring test is T2; net file delta: one rename, one
  new test, one rewritten body. No `os.link` references remain in
  prepare.py. Governs AC-3.

- **T4 (cross-device) — AC-4 EXDEV tolerance.** Add unit test
  `test_bind_mode_linux_cross_device_falls_back` that monkeypatches
  `prepare_mod.sys.platform = "linux"` and
  `prepare_mod.subprocess.run` with a stub that records argv and
  succeeds (we cannot easily mount two devices in a unit test — the
  cross-device behavior is a property of `cp --reflink=auto`
  itself, not our code). The unit assertion is the contract
  assertion: when subprocess.run is invoked with
  `["cp", "--reflink=auto", ...]`, our code does not pre-check
  device identity (no `os.stat(...).st_dev` comparison, no
  `EXDEV`-handling branch). i.e. we delegate cross-device handling
  to `cp`, which is documented to fall back to a full copy when
  reflink is unavailable for any reason including cross-device.
  Governs AC-4.

**Imports**
- `prepare.py` already imports `subprocess` (used by darwin branch
  at line 396) and `sys` (used at line 395) and `os` (used by
  `os.link` at line 400, soon-to-be-removed). The `os` import will
  remain — it is also used elsewhere in the file.

**Out-of-scope for impl stage (deferred)**
- Live Linux integration test on a reflink-capable filesystem
  (xfs/btrfs). We do not have Linux infra this session; the unit
  contract test (T0) is the load-bearing check. The
  `live-linux-reflink-CoW-smoke` is filed as a future entity for
  the first production Linux deployment.
- Reflink optimization on darwin. Already uses `cp -c` (clonefile).

**Mechanism-first ordering rationale**
The riskiest contract is "wrong CoW primitive → silent data
corruption on Linux". T0+T1 together exercise that contract end-to-end
(platform mock + subprocess invocation assert) — 30 seconds of test
time. Docstring fix (T2) and AC-4 contract (T4) follow. Darwin
regression (T3) is the comprehensive run that confirms no collateral.

**Risk register**
- One: a future contributor might "helpfully" pre-check
  `os.stat(src).st_dev == os.stat(dst).st_dev` and add an
  `os.link` short-circuit "for performance" — that would reintroduce
  the hardlink hazard. The AC-4 test (T4) guards against that.
- Two: `cp --reflink=auto` is GNU coreutils; busybox `cp` lacks
  `--reflink`. Production harbor-DAB containers use Debian/Ubuntu
  base images (GNU coreutils) — see PKG-23/24. Not a risk in target
  environments. Documented in the new docstring's caveats.

## Stage Report: plan

- DONE: Plan is INLINE (4 ACs, single-file change — packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py lines 365-407). Stage report on entity body, no separate plan doc.
  Implementation plan section added inline above this report; no doc under `plans/` created.
- DONE: Plan names the exact change: replace `os.link(child, dst_child)` on linux branch with `subprocess.run(['cp', '--reflink=auto', str(child), str(dst_child)], check=True)` — matches the darwin branch's pattern. Plan also names the docstring corrections (AC-2: drop the wrong hardlink-CoW claim).
  T1 quotes the before/after snippet verbatim against `prepare.py:399-400`; T2 enumerates the docstring deltas and adds an inspection test for the wrong-claim string's absence.
- DONE: Plan TDD-orders: (T0) RED unit test with sys.platform mocked to 'linux' asserting cp --reflink=auto invocation; (T1) implementation swap; (T2) docstring correction; (T3) darwin regression (existing 9/9 stay green).
  T0 → T1 → T2 → T3 listed in order; T4 added for AC-4 cross-device contract; mechanism-first rationale stated (riskiest contract = wrong CoW primitive, exercised by T0+T1 first).

### Summary

Tiny single-file surgical plan written inline on the entity body
per FO dispatch (4 ACs but one source file + one test file). Mechanism-
first TDD order: T0 (RED contract test for `cp --reflink=auto`
invocation on linux) → T1 (3-line implementation swap matching the
darwin branch's pattern) → T2 (honest docstring + inspection test) →
T3 (darwin 9/9 regression green) → T4 (AC-4 cross-device contract
delegated to `cp`). Live Linux integration smoke explicitly deferred
to a future entity since this session has no Linux infra; the unit
contract test is the load-bearing check.
