# PKG-25 — Linux reflink fallback — Validation Report

**Entity:** `pkg25-linux-reflink-fallback`
**Branch:** `spacedock-ensign/pkg25-linux-reflink-fallback`
**Impl commit:** `5a22388`
**Stage-report commit:** `b4012ce`
**Verdict:** **PASSED**

## Re-run evidence

`uv run pytest packages/razorback-plugin-dab/tests/unit/test_prepare_bind_materialize.py` on darwin:

- 11/11 passed in 0.26s
- 8 pre-existing PKG-21 darwin tests GREEN (AC-3)
- 3 new PKG-25 contract tests GREEN:
  - `test_bind_mode_linux_uses_reflink_cp` (AC-1)
  - `test_clone_or_copy_tree_docstring_is_honest` (AC-2)
  - `test_bind_mode_linux_cross_device_falls_back` (AC-4)

## AC check

- **AC-1 (linux uses cp --reflink=auto).** `prepare.py:406-410` invokes
  `subprocess.run(["cp", "--reflink=auto", str(child), str(dst_child)], check=True)`.
  Mirrors the darwin branch's pattern exactly, except the flag. No `os.link`
  references remain in the file (grep confirmed). PASS.
- **AC-2 (docstring honest).** `prepare.py:365-393` — the wrong-claim
  string `"copy-on-write happens at the filesystem level when one inode is
  opened for write"` is absent; the 3-line per-platform summary (darwin /
  linux / other) is present; busybox caveat noted; EXDEV caveat dropped
  (handled by `cp` fallback). PASS.
- **AC-3 (darwin unchanged).** Darwin branch at `prepare.py:402-405`
  unchanged (`cp -c`). 8 PKG-21 darwin tests stay green. PASS.
- **AC-4 (cross-device tolerance).** `test_bind_mode_linux_cross_device_falls_back`
  inspects the source of `_clone_or_copy_tree` and asserts absence of
  `st_dev`, `EXDEV`, and `os.link` — guards against a future contributor
  reintroducing the hardlink hazard "for performance". Cross-device handling
  itself is delegated to `cp --reflink=auto`'s documented full-copy
  fallback. PASS.

## Code review

Scope: 1 source file (`prepare.py`) + 1 test file
(`test_prepare_bind_materialize.py`). Diff is small and surgical.

- **Implementation (`prepare.py:402-410`):** Two-branch dispatch on
  `sys.platform`; darwin and linux now use the same primitive shape
  (`subprocess.run(["cp", <flag>, src, dst], check=True)`) with only the
  flag differing. Consistent, minimal, no abstraction overhead. The linux
  branch is mechanically equivalent to the darwin branch, which is the
  desired symmetry given the contract.
- **Docstring (`prepare.py:365-393`):** Honest, well-structured, names the
  filesystems where reflink works (btrfs / xfs / ext4-reflink), names the
  fallback semantics (distinct inodes — safe), and documents the GNU
  coreutils dependency. No temporal/historical references; no
  apology-for-the-old-behavior text. Reads as evergreen documentation.
- **Test design:** The AC-1 test exercises `_clone_or_copy_tree` directly
  rather than via `prepare_dataset_tasks`. The implementation stage report
  documents the rationale: monkeypatching `sys.platform = "linux"` in the
  broader orchestrator leaks into pydantic's lazy sysconfig lookup and
  produces darwin-incompatible behavior. Testing the unit in isolation is
  the right call — avoids latent flakiness and matches the unit under
  test more tightly. The recording subprocess stub also performs the
  physical copy so downstream assertions on dst-tree shape still hold.
- **AC-4 guard test:** Source-inspection assertions on `st_dev`, `EXDEV`,
  `os.link` are an unusual but appropriate technique here — the
  cross-device property is enforced by `cp`'s documented behavior, not by
  our code, so the meaningful local invariant is "we do not add a
  pre-check that would short-circuit the safe path". The test names this
  intent explicitly.
- **No dead code, no orphan imports.** `os` import retained (used
  elsewhere in the file). `subprocess` and `sys` already imported for the
  darwin branch.

No defects found. The change is minimal, correct, and aligned with the
plan and ACs.

## Out-of-scope notes (follow-up)

- **Live Linux reflink CoW smoke** (xfs/btrfs fixture; write-through-dst
  does-not-mutate-src). This session has no Linux infra; the unit
  contract test is the load-bearing check. Entity-grade follow-up
  recommended at the first production Linux harbor-DAB deployment to
  close the loop on the actual filesystem-level CoW assertion.
- **Busybox cp regression risk.** Target container images
  (Debian/Ubuntu, GNU coreutils) per PKG-23/24 — not a concern in
  current deployment surfaces. Documented in the docstring caveats.

## Conclusion

All four ACs verified by the unit suite and code review. Material change
(replace `os.link` with `cp --reflink=auto`) closes the PKG-21 silent-
dataset-corruption defect on Linux. Verdict: **PASSED**.
