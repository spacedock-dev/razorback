---
id: ykgrzjym3fkfcpnb103bwevv
title: spacedock_solver_v2 freeze-dir host/container mount mismatch (rc=128 git init)
status: implementation
source: PKG-26 T4 live `rk run` of spacedock cell 2026-05-21 (commit 1cb3087 on .worktrees/spacedock-ensign-pkg26-use-harbor-claude-code-adapter) — 3× SpacedockSolverAgentError: `freeze repo init failed at: git -C /Users/clkao/git/razorback/.worktrees/.../runs/goal1-spacedock-bookreview/_razorback/freeze/81bd6794a0d6ecab0d2461ccaeca044f init -q (rc=128)`. Host-path executed via environment.exec INSIDE the container; the host path is not mounted.
started: 2026-05-21T20:18:47Z
completed:
verdict:
score: 0.9
worktree: .worktrees/spacedock-ensign-spacedock-solver-v2-freeze-dir-mount
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

## Plan

### Decision: option (b) — git on host, not in container

Two options were laid out in AC-1. Picking (b): execute the freeze-
repo git commands on the host instead of via `environment.exec`.

Rationale:

1. **The freeze tree is razorback's own bookkeeping, not task state.**
   v2's resolve_freeze_dir() returns `<run-dir>/_razorback/freeze/
   <sealed_hash>/`, which is intentionally placed OUTSIDE the trial
   subtree precisely so harbor's resume rmtree (job.py:221) cannot
   touch it. Host is the natural home for host-managed bookkeeping.
   Routing git through `environment.exec` was a v1-pattern carry-
   over that no longer matches the v2 path layout.

2. **Option (a) crosses environment boundaries we do not own.**
   To bind-mount `<run-dir>/_razorback/freeze/<sealed_hash>` into
   the agent container, compose.py (harbor-DAB) would need to know
   about razorback freeze paths, and harbor's docker.py /
   apple_container.py would need to grow per-agent extra-mount
   plumbing. spacedock_solver_v2 is environment-agnostic (claude /
   codex / pi runtimes, with docker / apple_container / e2b
   environments downstream); making it require agent-side bind
   mounts breaks that portability. Container-side bind-mount of a
   razorback-private path also collides poorly with multi-trial
   compose stacks under the same harbor job.

3. **Existing host I/O already in setup() makes option (b) coherent.**
   spacedock_solver_v2.setup() already does `freeze_dir.mkdir(...)`
   and `sealed_file.write_text(self.sealed_hash)` on the host
   (lines 241-242). The git init/config/commit calls right after
   that block (lines 243-249) are operating on the same host
   directory. Switching them from `environment.exec` to host
   subprocess is a one-block edit; no new abstraction is created.

4. **No regression risk to the inner agent's container exec.**
   The inner agent (claude / codex / pi adapter) keeps its own
   `environment.exec` invocations for the actual model calls. Only
   razorback's freeze-repo bookkeeping moves to host. The
   `claude --version` / `git --version` sanity checks the v1 solver
   did in setup() are NOT present in v2 setup(); v2 delegates to the
   inner agent for runtime validation. So removing environment.exec
   from v2 setup() does not lose any container-side sanity check.

### Surface (single-file change)

Primary file: `src/razorback/agents/spacedock_solver_v2.py`

Surface changes:

- `setup()` (lines 217-259):
  - Replace `await environment.exec(f"git -C {freeze_dir} init -q")`
    et al. with host subprocess calls. Six init commands, plus the
    resume-path `git checkout -- .` (line 234).
  - Use `asyncio.create_subprocess_exec` rather than shell strings
    so the freeze_dir path is passed as an argv element (avoids
    spaces/quoting bugs in run-dir paths under colima_safe_tmp_path).
- `_commit_stage()` (lines 183-196):
  - Same swap: two commands (`add -A`, `commit --allow-empty -m
    'stage: {stage}'`). Currently called from the v2 freeze
    workflow mod.

No changes to:
- compose.py — option (a) was rejected.
- Inner-agent runtimes (`razorback.agents._runtime.{claude,codex,pi}`)
  — they continue to use `environment.exec` for the actual model
  command, which is correct (the model runs in the container).
- Harbor itself.

The `environment` parameter on `_commit_stage` and the freeze-init
loop becomes unused at the freeze-bookkeeping layer; keep it on the
signature for backwards-compat with the workflow mod call site, but
the body no longer references it.

### TDD-ordered tasks

**T0 — RED: unit reproducing the rc=128 (host/container path
mismatch).**
- New test file: `tests/unit/agents/test_spacedock_solver_v2_freeze_
  on_host.py`.
- Test 1 (RED expectation pre-fix): build a SpacedockSolverAgent v2
  with a host-only `logs_dir` (real tmp dir). Provide a fake
  `environment` whose `exec()` records calls and returns rc=0 IFF
  the cwd would have existed inside the container — i.e. simulates
  the container-not-host filesystem. Under the fake, current
  `setup()` would route git through environment.exec; the test
  asserts that under the fix, git executes ON HOST (the host
  freeze dir contains `.git/` after setup() returns, AND
  environment.exec was NOT called for any `git ...` command).
- Test 2: post-fix freeze_dir / sealed_hash.txt + a real `.git`
  directory exist on disk after `await agent.setup(env_stub)`. A
  follow-up `_commit_stage` call appends a real commit.
- Test 3: resume path — pre-populate freeze_dir with sealed_hash.txt
  matching the agent's hash + a `.git` (init on host once). Call
  setup() again on a fresh agent instance; assert `git checkout --
  .` ran on host, no environment.exec for git, return code 0.
- Risk this targets: confirms the contract violation that PKG-26
  T4 surfaced live, and locks in the host-side execution path.

**T1 — GREEN: switch freeze-repo git calls to host subprocess.**
- Edit `setup()` and `_commit_stage()` per "Surface" above.
- Helper: a small private `async def _host_git(self, *args: str) ->
  None` that wraps asyncio.create_subprocess_exec("git", *args),
  awaits the process, and raises
  `SpacedockSolverAgentError("freeze repo init failed at: git {args}
  (rc={rc})")` on non-zero. Reuse for init + config + add + commit
  + checkout.
- Keep the `environment` parameter on `_commit_stage` (workflow-mod
  callers pass it), but stop using it. Add a one-line comment:
  `# freeze tree is host-side bookkeeping; git runs on host`.

**T2 — Halt/resume integration test stays green (AC-3).**
- Run `tests/integration/test_rk_run_bookreview_spacedock_halt_
  resume.py` and document the result. Note: this integration test
  exercises the v1 solver (`razorback.agents.spacedock_solver`,
  see line 47 of the test importing `assert_phase_stats_schema`
  from v1). It is in scope because the AC-3 line explicitly names
  it — the test should remain green because v1 is unchanged. If
  the file is later parameterized over v1/v2, the v2 path will
  also use host git after this entity merges, and remains green.
- Also run the full PKG-15 / PKG-16 / PKG-17 / PKG-21 / harbor-dab
  -batch-query-mode suites: `uv run pytest packages/razorback-
  plugin-dab/` and `uv run pytest tests/unit/agents/`. This
  satisfies AC-2.

**T3 — AC-4: live `rk run` of one goal1 spacedock bookreview cell
(3 questions).**
- Use the PKG-26 worktree's frozen spec (spacedock variant,
  bookreview, claude-sonnet) since that's the spec PKG-26 T4
  failed against — same path will re-prove the fix end-to-end.
- Acceptance: result.json shows no SpacedockSolverAgentError
  ("freeze repo init failed"); summary.json has non-null cost_usd
  AND a per-query verdict map AND claude-output.jsonl present.
  Reward may be 0.0 or 1.0 — both are acceptable for AC-4 (the
  freeze-init bug is what's being verified fixed).

### Out of scope (re-stated for clarity)

- Reshaping spacedock_solver_v2's freeze contract more broadly
  (e.g., moving phase_stats.json layout).
- Adding any bind-mount plumbing to compose.py or harbor — option
  (a) was rejected; no compose-surface changes are part of this
  entity.
- Goal 2 / ade-bench (spacedock_solver_v2 not exercised there
  yet).

### Mechanism validation note

Per CL's "validating new mechanisms" rule: T0 is the smallest end-
to-end exercise of the riskiest path (the host/container mismatch).
T1 is the fix. T2 + T3 are confirmation runs at integration and
live scale. T0 must run RED on current code and GREEN after T1
before T3 burns paid-API tokens.

## Stage Report: plan

- DONE: Plan inspects spacedock_solver_v2.py freeze path code (lines 166-170) and decides (a) bind-mount vs (b) host git. Rationale captured.
  Decision: option (b) — host subprocess git. Four-point rationale recorded under "Decision" in Plan section above.
- DONE: Plan size: 4 ACs, primary surface src/razorback/agents/spacedock_solver_v2.py. FO size call: separate plan doc since option (a) likely touches compose.py too.
  Option (b) was chosen, so plan stays in entity body. Single-file surface confirmed; no compose.py touch.
- DONE: Plan TDD-orders: T0 RED unit reproducing the rc=128; T1 fix; T2 halt/resume integration test stays green (AC-3 explicit); T3 live `rk run` smoke against spacedock/bookreview unblocks (AC-4).
  Three tasks ordered T0→T1→T2→T3 with risk-first sequencing under "TDD-ordered tasks" above.

### Summary

Picked option (b): execute freeze-repo git on host instead of via
environment.exec, since the freeze tree is razorback bookkeeping
intentionally placed outside the trial subtree. Option (a) was
rejected for crossing harbor + harbor-DAB compose-generator
boundaries and breaking runtime-agnostic spacedock_solver_v2
portability. Single-file surface, four ordered tasks, mechanism
validated by T0 before T3 burns paid-API tokens.

## Stage Report: implementation

- DONE: T0 RED unit reproducing rc=128 freeze-init failure.
  tests/unit/test_spacedock_solver_v2_freeze_on_host.py — 4 tests; pre-fix asserted environment.exec received 6 git commands. Commit c6632ae.
- DONE: T1 fix per plan's option (b) — host subprocess git.
  spacedock_solver_v2.py: added `_host_git` helper using asyncio.create_subprocess_exec; setup() + _commit_stage() swapped from environment.exec to host. 9/9 v2 freeze unit tests green (4 new + 5 lifecycle updated to new contract).
- DONE: T2 full unit + DAB plugin suites stay green (AC-2/AC-3).
  tests/unit/ 514 passed in 20s. packages/razorback-plugin-dab/ excl. preexisting mongo-init flake = 132 passed/3 skipped. The mongo-init shim test and test_rk_run_bookreview_spacedock_halt_resume.py both fail identically on main (Docker container / v1 spec-validation issues unrelated to this entity).
- DONE: T3 live `rk run` against goal1/spacedock/bookreview frozen spec (AC-4).
  _runs/goal1-spacedock-bookreview/a901b991c80c8b89/result.json: n_completed_trials=1, n_errored_trials=0, reward=1.0, exception_stats={}. summary.json: dataset_pass_at_1=1.0; per-query verdict map 3/3=1.0 in reward_per_query.json. Freeze dir `_razorback/freeze/81bd6794a0d6ecab0d2461ccaeca044f/` contains real .git/ + sealed_hash.txt on host. NO SpacedockSolverAgentError(freeze repo init failed). 3m 2s runtime, claude-code.txt agent JSONL stream captured (51 lines). cost_usd=null is a pre-existing upstream harbor cost-attribution gap, out of this entity's scope (matches PKG-26 baseline).

### Summary

Option (b) shipped: freeze-repo git now runs on the host via
asyncio.create_subprocess_exec, not via environment.exec. The rc=128
host/container mount mismatch PKG-26 T4 surfaced is gone — the same
goal1/spacedock/bookreview spec that bombed in PKG-26 now passes
end-to-end with reward 1.0 per query (3/3). Single-file surface
change to spacedock_solver_v2.py plus matching test updates. The
container-side inner-agent runtime is unchanged; only razorback's
freeze bookkeeping moved to host where the path is real.

## Stage Report: validation

- DONE: Re-run unit tests + halt/resume integration test (AC-2/AC-3).
  `tests/unit/` 514 passed. `packages/razorback-plugin-dab/` 133 passed / 2 skipped / 1 failed (pre-existing mongo-init shim flake; this branch does not touch DAB code per `git diff main..HEAD --stat`). Halt/resume integration test fails on `SpecError: spacedock-solver spec must be frozen` — pre-existing v1 spec-freeze drift on main, also unrelated to this entity.
- DONE: Confirm T3 live `rk run` evidence (AC-4).
  `_runs/goal1-spacedock-bookreview/a901b991c80c8b89/`: reward 1.0/1.0/1.0 on q1/q2/q3 in reward_per_query.json; claude-code.txt 105 KB JSONL; host `_razorback/freeze/<hash>/sealed_hash.txt` present; no freeze-init exception in job.log. `cost_usd=null` is a known upstream harbor gap (out of scope).
- DONE: Code review via superpowers:requesting-code-review — material vs polish.
  Manual diff review of `c6632ae` (+30/-29 in `spacedock_solver_v2.py`). New `_host_git` helper uses argv tuple (eliminates shell-quoting risk). Tests assert both git-on-host AND no env.exec for git, across first-stage / commit-stage / resume. No material findings; two minor non-blocking polish notes documented in validation report.
- DONE: Write validation report.
  `docs/razorback-implementation/validation/spacedock-solver-v2-freeze-dir-mount.md` — verdict PASSED.

### Summary

Verdict PASSED. PKG-26 T4's rc=128 freeze-init blocker is closed
end-to-end on the same goal1/spacedock/bookreview spec; per-query
verdict map 3/3=1.0 with claude-code.txt JSONL captured and host
freeze tree on disk. Single-file fix with `_host_git` argv-tuple
helper, matched by 4 new + 5 updated unit tests. The two non-passing
suites (mongo-init shim Docker test and halt/resume v1 spec-freeze)
are pre-existing on main and outside this entity's surface
(confirmed via `git diff main..HEAD --stat`). Goal 1 RESUME T2
dispatch unblocks fully.


