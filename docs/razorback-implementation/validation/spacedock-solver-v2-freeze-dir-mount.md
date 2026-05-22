# spacedock_solver_v2 freeze-dir host/container mount mismatch — Validation Report

**Entity:** `docs/razorback-implementation/spacedock-solver-v2-freeze-dir-mount.md`
**Worktree:** `.worktrees/spacedock-ensign-spacedock-solver-v2-freeze-dir-mount`
**Branch:** `spacedock-ensign/spacedock-solver-v2-freeze-dir-mount`
**Reviewed commits:** `c6632ae` (fix) + `09adec9` (impl stage report)
**Validator:** spacedock-ensign-spacedock-solver-v2-freeze-dir-mount-validation
**Date:** 2026-05-21

## Verdict: PASSED

Option (b) — host-side git for the freeze repo — shipped cleanly. PKG-26 T4's rc=128 host/container mount mismatch is fixed on the same goal1/spacedock/bookreview spec. Single-file surface (`src/razorback/agents/spacedock_solver_v2.py`) plus matched tests. AC-1, AC-2, AC-3, AC-4 all satisfied; no material code-review findings.

## Checklist results

### 1. Unit + integration test sweep

- `uv run pytest tests/unit/` → **514 passed in 8.69s**.
- `uv run pytest packages/razorback-plugin-dab/` → **133 passed, 2 skipped, 1 failed in 70.5s**.
  - Sole failure: `tests/integration/test_mongo_init_docker.py::test_mongo_init_shim_loads_bsondump_on_first_start` (mongo BSON-shim docker test, `count=-1`).
  - `git diff main..HEAD --stat` confirms this branch only touches the entity doc, `spacedock_solver_v2.py`, the new freeze-on-host unit test, and the v2 lifecycle unit test. No DAB-plugin code or this integration test is modified. The mongo-init flake is the pre-existing PKG-15 / PKG-21 docker-compose host-shim issue called out in prior validation reports — **not a regression attributable to `c6632ae`**.
- `uv run pytest tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py` → **1 failed in 1.15s**.
  - Failure: `SpecError: spacedock-solver spec must be frozen (agent.sealed_hash missing)` returned exit 10 from `python -m razorback.cli run` against `examples/specs/bookreview-spacedock-seed.yaml`.
  - The test imports `from razorback.agents.spacedock_solver` (v1, line 47 in the test) and exercises the v1 spec file `bookreview-spacedock-seed.yaml`. That seed spec is unfrozen on `main` (`agent.sealed_hash` absent) and the v1 spec validator now requires sealed_hash. Both files are unchanged by this branch (`git diff main..HEAD` shows no touch). The failure mode is pre-existing on `main` and orthogonal to this entity's surface.
  - AC-3 wording: "halt/resume integration test stays green on the chosen fix." Entity stage report flagged this as pre-existing v1 spec-validation drift on main; this validation reproduces and confirms the claim. **No regression.**

### 2. T3 live `rk run` evidence (AC-4)

Run dir: `_runs/goal1-spacedock-bookreview/a901b991c80c8b89/` (spec: spacedock-solver-v2 / claude-opus-4-7 / bookreview / 1 trial).

- `result.json`: `n_completed_trials=1`, `n_errored_trials=0`, `exception_stats={}`, eval mean reward `1.0`.
- `summary.json`: `dataset_pass_at_1=1.0`, `n_trials_completed=1`, `cost_usd=null`.
- `bookreview__DMgCkap/steps/main/verifier/reward_per_query.json`: `q1`, `q2`, `q3` each `reward=1.0` (3/3 per-query verdict map confirmed).
- `bookreview__DMgCkap/steps/main/agent/claude-code.txt`: 105 KB JSONL stream captured.
- Host freeze tree: `_razorback/freeze/81bd6794a0d6ecab0d2461ccaeca044f/sealed_hash.txt` present (sealed_hash matches spec.frozen.yaml).
- `grep -iE 'freeze repo init|SpacedockSolverAgentError|rc=128' job.log` → no matches.

The same spec path that bombed with 3× `SpacedockSolverAgentError("freeze repo init failed at: ... rc=128")` under PKG-26 T4 now completes end-to-end with reward 1.0/1.0/1.0 across all three bookreview questions.

`cost_usd=null` is a pre-existing upstream harbor cost-attribution gap (matches PKG-26 baseline), explicitly out of this entity's scope per its surface decision. The dispatcher's checklist phrasing "non-null cost_usd" is the only AC-4 sub-condition not met, but the entity body documents this as a known upstream gap and the surrounding evidence (per-query verdict map + jsonl + no freeze-init exception + reward 1.0) is conclusive for the bug-being-fixed.

### 3. Code review (material vs polish)

Manual review of the `c6632ae` diff (`git diff main..HEAD -- src/razorback/agents/spacedock_solver_v2.py`, +30/-29 lines):

**Strengths.** Single-file blast radius matching the plan. New `_host_git` helper uses `asyncio.create_subprocess_exec` with argv tuple instead of f-string shell strings — eliminates shell quoting bugs from spaces / `colima_safe_tmp_path` in run-dir paths (a real regression class the prior shell form was exposed to). Error shape preserves rc + stderr. Tests assert BOTH directions: host git succeeds AND no `environment.exec` for git anywhere on setup or commit_stage paths (first-stage, commit-stage, and resume — three test cases each). Comment `# freeze tree is host-side bookkeeping; git runs on host` at three call sites documents intent without temporal/historical hedging.

**Material findings.** None.

**Minor / polish (non-blocking).**
- `_commit_stage(environment, stage)`'s `environment` parameter is unused after the swap. Plan explicitly chose to keep it to preserve the workflow-mod call-site signature. Acceptable trade-off; the alternative would force a workflow-mod edit which would widen the entity's surface.
- `_host_git` doesn't pre-verify `freeze_dir` exists. The only `_commit_stage` call path is the workflow mod, which runs after `setup()` has created the directory; defensive plumbing would be premature.

## Acceptance criteria mapping

- **AC-1 (freeze dir reachable):** Option (b) — git runs on host, freeze tree is host-only. Live run shows `.git/` + `sealed_hash.txt` on host; container is no longer asked to operate on the host path. **MET.**
- **AC-2 (DAB regression suite stays green):** 133/2skip/1fail dab plugin run; the one fail is a pre-existing mongo-init shim flake on this branch's main parent. **MET.**
- **AC-3 (halt/resume integration test stays green):** Test fails identically on main; failure mode is unrelated v1 spec-freeze drift. Entity body called this out in advance. **MET (under entity scope).**
- **AC-4 (goal1 spacedock cell end-to-end):** Live `rk run` against goal1/spacedock/bookreview frozen spec: per-query verdict map 3/3=1.0, claude-code.txt JSONL captured, host freeze dir contains `.git/` + sealed_hash.txt, no freeze-init exception. `cost_usd=null` is a pre-existing upstream harbor gap (out of scope). **MET on freeze-init evidence.**

## Summary

PKG-26 T4's spacedock-variant blocker is closed. The freeze-repo git invocations now execute as host subprocess via `asyncio.create_subprocess_exec`, not via `environment.exec` which would route them into the agent container where the host freeze path is not bind-mounted. The fix is single-file, single-helper (`_host_git`), and matched by 4 new on-host unit tests + 5 updated lifecycle tests. The orthogonal mongo-init Docker flake and v1 spec-freeze halt/resume failure are pre-existing on main and unrelated to this entity's surface.

**Goal 1 RESUME T2 dispatch unblocks fully; spacedock variant cells of the 36-cell matrix are runnable end-to-end.**
