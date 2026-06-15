---
id: dka84dm5dn5fyt92px5100pw
title: Spacedock v2 freeze CAS is container-visible
status: backlog
source: 2026-05-23 staff audit — v2 writes freeze state to global CAS while translator still mounts run-dir freeze root at /razorback-freeze
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

`spacedock_solver` now resolves freeze trees through the global
`RAZORBACK_FREEZE_DIR` / XDG CAS so runs survive worktree teardown and can
resume across worktrees. The translator still mounts `<run-dir>/_razorback/freeze`
into the container as `/razorback-freeze`. Solver workflow docs tell agents to
inspect `/razorback-freeze`, but the actual freeze tree may live elsewhere.

That split can make the host-side resume mechanism work while the
container-visible checkpoint surface is empty or stale.

## Acceptance criteria

**AC-1 — One freeze root contract.**
For `spacedock_solver`, the freeze directory that the solver writes is the
same tree exposed to the container as `/razorback-freeze`.
Verified by: unit/integration test asserts `sealed_hash.txt` is visible at
`/razorback-freeze/<sealed_hash>/sealed_hash.txt` for a canonical Harbor job.

**AC-2 — Cross-worktree CAS survives.**
The fix preserves the global CAS behavior: two worktrees with the same sealed
hash resolve to the same host freeze tree unless the operator explicitly
overrides `RAZORBACK_FREEZE_DIR`.
Verified by: existing freeze cross-worktree and no-agent resume tests stay
green.

> **Superseded 2026-06-15 by per-cell freeze isolation** (see
> `_artifacts/FREEZE_REPO_RACE_HANDOFF.md`). To make `concurrency.trials > 1` safe, the
> freeze dir is now `<cas-root>/<sealed_hash>/<cell_token>`. Two worktrees now
> resolve to the same tree only when they are the *same cell* (same trial
> name), not merely the same sealed hash. The external-survival property (a
> freeze tree outlives worktree teardown) is retained.

**AC-3 — Translator and docs agree.**
The translator, solver workflow docs, and tests name the same container-visible
path and host source path semantics.
Verified by: grep-backed validation cites the mount code and solver workflow
README lines.

**AC-4 — No run-dir destruction regression.**
Worktree teardown does not delete freeze artifacts or run artifacts.
Verified by: `tests/integration/test_worktree_teardown_preserves_runs.py` and
the freeze CAS tests pass together.
