---
id: 311jw5b14cpjk1bk06qr36w0
title: PKG-29 — ensure git is available for spacedock_solver_v2 freeze repo
status: implementation
source: PKG-28 smoke follow-up — Codex auth reached Harbor, then spacedock_solver_v2 failed at freeze repo git command with rc=127
started: 2026-05-21T08:27:16Z
completed:
verdict:
score: 0.95
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

