---
id: 0yvb96r26n54nkavg7myr0va
title: PKG-33 Harbor-shaped Codex audit coverage
status: validation
source: goal3 DAB Codex run validation
started: 2026-05-21T09:44:29Z
completed:
verdict:
score: 0.93
worktree: .worktrees/spacedock-ensign-pkg33-harbor-codex-audit-coverage
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

## Stage Report: plan

- DONE: The inline plan identifies the concrete audit discovery/scanner code and tests to change for Harbor-shaped Codex traces.
  Plan below names `src/razorback/audit/cli.py`, a new `src/razorback/audit/harbor_codex.py`, and focused tests in `tests/unit/audit/conftest.py` plus `tests/unit/audit/test_rk_audit_cli.py`.
- DONE: The inline plan preserves the separation between solver trace taint and setup-time `job.log` package installation.
  Scanner scope is limited to `<trial>/steps/*/agent/{codex.txt,sessions/**/*.jsonl}`; the AC-3 test fixture puts package installation only in `job.log` and expects strict audit to stay clean.
- DONE: The inline plan names the validation command(s), including `uv run pytest tests/unit/audit -q`.
  Validation section below includes targeted pytest node commands, `uv run pytest tests/unit/audit -q`, and fixture-level `uv run rk audit ... --policy strict --format json` checks.

### Summary

Inline plan written on the entity per the FO tiny-task sizing; no separate `plans/pkg33-harbor-codex-audit-coverage.md` document was created. I followed the local cached Superpowers `writing-plans` guidance; that skill is not registered in this Codex session's available skill list, so this is an equivalent inline application rather than a callable Codex skill invocation.

### Inline Implementation Plan

Spec cites: v2 spec §3.2 (`rk audit <run-dir> --policy audit|strict --format ...` and strict non-clean exit), §7.1 (Razorback reads Harbor-owned run/trial layout without writing inside trials), and §9.4 (Layer 3 post-hoc trace scan for forbidden shell/tool lookup behavior).

Files and boundaries:

- Modify `src/razorback/audit/cli.py`: extend `_discover_trial_roots()` to union existing legacy sentinels with Harbor Codex trial roots, then extend `_audit_run_dir()` findings with Harbor Codex scan findings before `_reduce_trial_status()`.
- Add `src/razorback/audit/harbor_codex.py`: implement `discover_trial_roots(run_dir)`, `scan_trial(trial_root)`, and small JSON-event extractors for `steps/*/agent/codex.txt` plus `steps/*/agent/sessions/**/*.jsonl`. Reuse the existing taint command/tool matching semantics where possible, but keep this module Razorback-owned so the DAB verbatim port stays stable.
- Modify `tests/unit/audit/conftest.py`: add helpers that create Harbor-shaped trial fixtures under `<trial>/steps/main/agent/`, with optional `codex.txt`, session JSONL, and run-level or trial-level `job.log`.
- Modify `tests/unit/audit/test_rk_audit_cli.py`: add one CLI-level test per AC, because the public contract is `rk audit` JSON/exit behavior.

TDD checkpoints:

1. AC-1 first: write `test_rk_audit_discovers_harbor_codex_txt_trial` with a clean `<trial>/steps/main/agent/codex.txt`; verify it initially reports zero trials, then implement discovery so JSON has exactly one clean trial. This validates the risky Harbor layout contract before taint matching.
2. AC-2 second: write `test_rk_audit_strict_taints_harbor_codex_session_command` using a Codex session JSONL `response_item` tool call whose command field is `curl https://example.com/data.csv` (and source path under `steps/main/agent/sessions/...jsonl`); verify strict exits with `ExitCode.TAINT_FINDINGS` and the finding names the Harbor Codex source. Add a sibling `codex.txt` JSON-line fixture if the first extractor only covers sessions.
3. AC-3 third: write `test_rk_audit_strict_ignores_job_log_setup_install` with `job.log` containing setup installs such as `npm install -g @openai/codex` or `pip install ...`, and a clean solver trace in `steps/main/agent/`; strict audit must exit 0 with `{"clean": 1, "tainted": 0, "coverage_missing": 0}`. Do not add `job.log` to any scanner glob.

Validation commands:

- Targeted red/green during implementation: `uv run pytest tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_discovers_harbor_codex_txt_trial -q`, then the AC-2 and AC-3 pytest nodes as they are added.
- Required audit suite: `uv run pytest tests/unit/audit -q`.
- Mechanism-level CLI checks against the new temp fixtures: `uv run rk audit <fixture> --format json` for AC-1 and `uv run rk audit <fixture> --policy strict --format json` for AC-2/AC-3, confirming exit 23 only for the tainted solver trace.
- Plan-stage sanity check run: `uv run pytest tests/unit/audit -q` passed (`24 passed`).

## Stage Report: implementation

- DONE: `rk audit` discovers Harbor-shaped Codex trials under `steps/*/agent/` and reports nonzero trial coverage for clean `codex.txt` traces.
  Evidence: `test_rk_audit_discovers_harbor_codex_txt_trial` plus CLI check `clean-discovery: exit=0 ... trials=1`.
- DONE: Strict audit taints solver-side forbidden lookup attempts in Harbor Codex `codex.txt` or session JSONL traces while preserving source-path evidence.
  Evidence: strict tests cover `harbor_codex_text` and `harbor_codex_session`; CLI check reports source `steps/main/agent/sessions/2026/05/21/session.jsonl` with exit 23.
- DONE: Setup/install commands in `job.log` remain outside solver-trace taint, with `uv run pytest tests/unit/audit -q` passing.
  Evidence: `test_rk_audit_strict_ignores_job_log_setup_install`; `uv run pytest tests/unit/audit -q` passed (`28 passed`), rerun as `uv run --frozen pytest tests/unit/audit -q` also passed (`28 passed`).

### Summary

Added `src/razorback/audit/harbor_codex.py` for Harbor Codex discovery/scanning and wired it into `src/razorback/audit/cli.py` alongside the existing DAB taint port. Harbor surfaces touched are read-only scanner inputs under `<trial>/steps/*/agent/codex.txt` and `<trial>/steps/*/agent/sessions/**/*.jsonl`; `job.log` remains intentionally outside solver-trace taint. No spec deviations; one extra codex.txt taint guard was added beyond the plan's session-focused AC-2 test.
