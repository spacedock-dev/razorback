---
id: ykgrzjym3fkfcpnb103bwevv
title: spacedock_solver_v2 freeze-dir host/container mount mismatch (rc=128 git init)
status: backlog
source: PKG-26 T4 live `rk run` of spacedock cell 2026-05-21 (commit 1cb3087 on .worktrees/spacedock-ensign-pkg26-use-harbor-claude-code-adapter) — 3× SpacedockSolverAgentError: `freeze repo init failed at: git -C /Users/clkao/git/razorback/.worktrees/.../runs/goal1-spacedock-bookreview/_razorback/freeze/81bd6794a0d6ecab0d2461ccaeca044f init -q (rc=128)`. Host-path executed via environment.exec INSIDE the container; the host path is not mounted.
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

`spacedock_solver_v2` (`src/razorback/agents/spacedock_solver_v2.py`)
materializes its freeze tree at
`<run-dir>/_razorback/freeze/<sealed_hash>/` on the HOST filesystem
(see lines 166-170: "outside the trial subtree that harbor jobs
resume rmtree's"). The freeze workflow then runs
`git -C <freeze_path> init -q` via the agent's `environment.exec()`
call.

For DAB tasks under harbor-DAB, `environment.exec` runs INSIDE the
agent container (the `main` service). The host path
`/Users/clkao/git/razorback/.worktrees/.../runs/.../_razorback/freeze/...`
is not bind-mounted into that container, so `git -C <host_path>` is
operating on a path that doesn't exist from the container's
perspective. Exit code 128.

PKG-26 T4's live `rk run` against a spacedock cell surfaced this
deterministically: 3 trials × `SpacedockSolverAgentError` ("freeze
repo init failed at: ... rc=128"). The bug is orthogonal to
PKG-26's surface map (PKG-26 fixed claude-cli subclass + spec
generator + auth env passthrough + tools_denied shlex quoting + v2
freeze sealing). PKG-26 direct-minimal AC-4 evidence is conclusive
on its own; spacedock AC-4 requires THIS entity before its T2
dispatch.

This is the first time `spacedock_solver_v2` has been exercised
against `harbor_dab` end-to-end. The bug is real, latent, and
shipping-blocking for Goal 1 RESUME's spacedock variant (1/3 of
the matrix). Without it the spacedock variant cells all bomb at
the freeze-init step, returning zero reward for unrelated
infrastructure reasons.

## Acceptance criteria

**AC-1 — Freeze dir is reachable from the agent container.**
Either:
- (a) The freeze tree is materialized at a host path that IS
  bind-mounted into the container (e.g., inside the agent
  workdir), so `git -C <path> init -q` works inside the container;
- (b) The freeze tree is materialized on host AND
  spacedock_solver_v2's git invocations run ON the host (not via
  environment.exec) — they don't need to be inside the container
  since the freeze tree is razorback's own bookkeeping.
Either option is acceptable; the plan picks one with rationale.
Verified by: a live `rk run` against a goal1 spacedock cell
(bookreview is fine; small + cheap) does NOT raise
SpacedockSolverAgentError("freeze repo init failed"). The trial
completes with a real verifier reward (0.0 or 1.0).

**AC-2 — DAB regression suite stays green.**
Existing PKG-15 / PKG-16 / PKG-17 / PKG-21 / harbor-dab-batch-query-
mode test suites stay green.
Verified by: `uv run pytest packages/razorback-plugin-dab/` and
`uv run pytest tests/` pass.

**AC-3 — Halt/resume integration test stays green.**
`tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py`
continues to pass on the chosen fix.
Verified by: explicit run of the halt/resume integration test
documented in the validation report.

**AC-4 — Goal 1 RESUME spacedock cell completes end-to-end.**
After this entity merges, a live `rk run` of ONE spacedock bookreview
cell (3 questions) produces summary.json with non-null cost_usd
AND a per-query verdict map AND claude-output.jsonl AND no freeze-
init exceptions.
Verified by: live `rk run` documented in the validation report.

## Test plan

- **Unit:** scope depends on chosen option (a or b). At minimum a
  unit test asserts the freeze-init path no longer raises rc=128
  under the fix.
- **Integration:** the existing halt/resume integration test
  remains green.
- **Acceptance:** live `rk run` against goal1/spacedock/bookreview
  re-frozen spec.

## Out of scope

- Reshaping spacedock_solver_v2's freeze contract more broadly.
  This entity ONLY fixes the host/container path mismatch.
- Goal 2 / ade-bench (spacedock_solver_v2 not used there).
- harbor-DAB postgres/mongo volume mount semantics (unchanged).

## Depends on

- PKG-26 (mid-validation) — its `freeze_command` extension to seal
  v2 specs is required so the spacedock variant reaches the
  agent.run path where this bug surfaces

## Resume hook

After this entity merges, Goal 1 RESUME's T2 dispatch unblocks
fully (direct-* variants + spacedock variant all runnable end-to-end).
