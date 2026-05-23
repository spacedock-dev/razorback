---
id: 311jw5b14cpjk1bk06qr36w0
title: PKG-29 — ensure git is available for spacedock_solver_v2 freeze repo
status: done
source: PKG-28 smoke follow-up — Codex auth reached Harbor, then spacedock_solver_v2 failed at freeze repo git command with rc=127
started: 2026-05-21T08:27:16Z
completed: 2026-05-21T08:48:40Z
verdict: PASSED
score: 1.00
worktree: .worktrees/spacedock-ensign-pkg29-spacedock-solver-git-bootstrap
issue:
pr:
mod-block:
---

## Problem

`spacedock_solver_v2` stores per-run freeze state in a
sealed-hash-keyed git repository. The setup path currently assumes
`git` exists inside the trial environment and runs commands such as
`git init`, `git checkout -- .`, and `git commit`. The Codex smoke
path now gets past auth, but fails before the solver can run because
the task image lacks `git` and the freeze repo command exits 127.

Goal 3 and Goal 4 cannot produce Codex benchmark numbers until the
solver bootstrap either installs `git` or otherwise fails with a
clear infrastructure message before the benchmark burn.

## Acceptance criteria

**AC-1 — Solver setup bootstraps `git` when absent.**
Before running freeze-repo git commands, `SpacedockSolverAgent`
checks for `git` inside the trial environment and attempts a
minimal package-manager install (`apk`, `apt-get`, or `yum`) as root
when missing. Images that already have `git` are unchanged.
Verified by: unit or integration test with a fake environment proves
the setup path attempts installation before `git init` when
`command -v git` fails.

**AC-2 — Failure is clear when `git` cannot be installed.**
If the environment has no supported package manager or installation
fails, setup raises `SpacedockSolverAgentError` naming that `git` is
required for the sealed freeze repo.
Verified by: focused test for an unsupported package-manager probe.

**AC-3 — Codex smoke advances past the freeze-repo git failure.**
The checked-in Codex smoke spec no longer fails with a git rc=127
from `git init` or `git checkout`. It either completes or fails at a
later, documented Codex/benchmark layer.
Verified by: `uv run rk freeze examples/specs/_codex-smoke-v2.yaml
--allow-missing` and `uv run rk run
examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir
runs/pkg29-codex-git-smoke --allow-plugin-drift --allow-alias-drift`
does not report a freeze-repo `git` command rc=127.

**AC-4 — Existing v2 freeze/resume tests stay green.**
The new bootstrap does not weaken sealed-hash mismatch behavior or
freeze-dir resume behavior.
Verified by: `uv run pytest
tests/integration/test_v2_freeze_dir_mechanism.py
tests/unit/test_spacedock_solver_v2_class.py -q` passes.

## Depends on

- `pkg28-codex-auth-json-passthrough` — shipped.

## Stage Report: implementation

- DONE: `SpacedockSolverAgent` ensures `git` is present before sealed freeze-repo commands, with tests proving install-before-git-init behavior.
  Added `_ensure_freeze_repo_git()` in `src/razorback/agents/spacedock_solver_v2.py`; `test_first_stage_installs_git_before_git_init_when_missing` proves the apt-get install precedes `git init`.
- DONE: Unsupported package-manager or install failure raises a clear `SpacedockSolverAgentError` naming the sealed freeze repo git requirement.
  Added unsupported-package-manager and install-failure tests; both assert `git is required for the sealed freeze repo` appears in the raised `SpacedockSolverAgentError`.
- DONE: `_codex-smoke-v2` no longer fails with freeze-repo `git` rc=127; stage report records the exact next outcome and targeted tests.
  `uv run rk run examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir runs/pkg29-codex-git-smoke --allow-plugin-drift --allow-alias-drift` completed Harbor execution with `SpacedockSolverAgentError: freeze repo init failed at: git -C <run-dir>/_razorback/freeze/<sealed_hash> init -q (rc=128)`, not rc=127.

### Summary

Implemented a narrow git bootstrap in `SpacedockSolverAgent.setup`: it probes `command -v git`, installs via `apk`, `apt-get`, or `yum` when available, verifies the binary, and raises a clear agent error on unsupported or failed install paths. Verification passed with `uv run pytest tests/unit/test_spacedock_solver_v2_lifecycle.py tests/integration/test_v2_freeze_dir_mechanism.py tests/unit/test_spacedock_solver_v2_class.py -q` (`20 passed`) plus the required `_codex-smoke-v2` freeze/run commands; the smoke now advances past missing git and exposes a later `git init rc=128` environment/filesystem failure.

## Stage Report: implementation (cycle 2)

- DONE: `SpacedockSolverAgent` ensures `git` is present before sealed freeze-repo commands, with tests proving install-before-git-init behavior.
  Preserved git bootstrap and added container freeze-root mapping; `test_first_stage_installs_git_before_git_init_when_missing` and `test_first_stage_uses_container_freeze_mount_for_git_commands` cover ordering and mounted-path use.
- DONE: Unsupported package-manager or install failure raises a clear `SpacedockSolverAgentError` naming the sealed freeze repo git requirement.
  Unsupported and failed-install tests still assert `git is required for the sealed freeze repo`; git command failures now include `rc`, `stdout`, and `stderr`.
- DONE: `_codex-smoke-v2` no longer fails with freeze-repo `git` rc=127; stage report records the exact next outcome and targeted tests.
  `uv run rk run examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir runs/pkg29-codex-git-smoke-cycle2 --allow-plugin-drift --allow-alias-drift` completed freeze repo init/config/add/commit and produced reward `1.0`; later failure is `NonZeroAgentExitCodeError: The 'gpt-5.1-codex' model is not supported when using Codex with a ChatGPT account.`

### Summary

Cycle 2 fixed the remaining freeze setup blockers by mounting `<job-dir>/_razorback/freeze` into Docker at `/razorback-freeze`, resolving Harbor's direct trial layout via `_job_config.yaml`, running freeze git commands with per-command `safe.directory`, and chmodding the mounted repo after setup so host artifacts remain writable. Verification passed with `uv run pytest tests/unit/test_spacedock_solver_v2_lifecycle.py tests/integration/test_v2_freeze_dir_mechanism.py tests/unit/test_spacedock_solver_v2_class.py -q` (`24 passed`) and the required `_codex-smoke-v2` freeze/run; the freeze repo at `runs/pkg29-codex-git-smoke-cycle2/_codex-smoke-v2/<job>/_razorback/freeze/<sealed_hash>` contains seed commit `8ec0495`.
