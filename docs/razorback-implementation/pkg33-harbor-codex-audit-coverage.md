---
id: 0yvb96r26n54nkavg7myr0va
title: PKG-33 Harbor-shaped Codex audit coverage
status: backlog
source: goal3 DAB Codex run validation
started:
completed:
verdict:
score: 0.93
worktree:
issue:
pr:
mod-block:
---

## Problem

`rk audit` currently reports zero scanned trials for Harbor-shaped Codex DAB
run directories, because discovery only recognizes older sentinel files. Full
DAB and ade-bench score runs need audit coverage over the Codex traces written
under each Harbor trial.

## Acceptance criteria

**AC-1 — Harbor-shaped Codex trials are discovered by `rk audit`.**
Verified by: a unit or integration test with a minimal run-dir fixture containing
`<trial>/steps/main/agent/codex.txt` and/or Codex session JSONL, where
`uv run rk audit <fixture> --format json` reports one trial instead of zero.

**AC-2 — Forbidden solver-side lookup attempts in Harbor Codex traces are
reported as tainted under strict audit.**
Verified by: a test fixture containing an agent command such as `curl`,
`wget`, `git clone`, `pip install`, public web access, or Docker socket
inspection in `steps/main/agent/codex.txt` or session JSONL, where
`uv run rk audit <fixture> --policy strict --format json` exits with the
taint error code and names the offending source.

**AC-3 — Benchmark setup/install commands remain separable from solver trace
taint.**
Verified by: a fixture with setup-time package installation in `job.log` and a
clean solver trace, where strict audit does not taint the trial because only the
solver trace is scanned for forbidden lookup attempts.

## Test plan

Add focused audit tests for Harbor-shaped Codex trial discovery and forbidden
command detection. Run the new tests plus the existing audit suite with
`uv run pytest tests/unit/audit -q`.

## Out of scope

This task does not change benchmark scoring, model defaults, or the solver's
database-answering strategy.
