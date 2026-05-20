---
id: kfe470qp9mfr6ss95teprx2h
title: Phase 8 — validate + tag v2 release
status: backlog
source: plan Phase 8 (v2 reconciliation plan at docs/superpowers/plans/2026-05-19-razorback-reconciliation-plan.md)
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Problem

Phase 8 is the validation + release gate. Every public surface of
v2 razorback exercises end-to-end via a series of smokes; the
README at repo root reflects v2; CHANGELOG lists every sideline +
every new addition with v2 spec citations; the version tag marks
the release with a major version bump. AC-8.1 through AC-8.5
collectively cover the surfaces the prior phases shipped; AC-8.6
+ AC-8.7 + AC-8.8 + AC-8.9 are the release-hygiene gates.

Integration bugs surface only at end-to-end smoke. AC-8.5 (full
experiment workflow) is the most comprehensive and the most likely
to surface late issues.

## Acceptance criteria

**AC-1 — nop-agent smoke succeeds.**
A spec with the simplest possible agent (`agent.kind: claude_code`
or harbor's `nop` if available) freezes, runs, and produces a
run-dir with `provenance.yaml`.
Verified by: `uv run rk freeze examples/specs/_smoke-nop.yaml` +
`uv run rk run examples/specs/_smoke-nop.frozen.yaml` exit 0;
`provenance.yaml` is present in the run-dir. Per plan AC-8.1.

**AC-2 — spacedock_solver smoke succeeds.**
A spec with `agent.kind: spacedock_solver` + a minimal
solver_workflow freezes, runs, and produces
`agent_freeze/sealed_hash.txt`. (`phase_stats.json` production via
real workflow mods defers per AC-3.6; the smoke writes it via the
test harness if needed for schema validation.)
Verified by: `uv run rk freeze + rk run` exit 0; the freeze
location (sealed_hash-keyed per `b5`) carries `sealed_hash.txt`.
Per plan AC-8.2.

**AC-3 — `rk audit` smoke succeeds.**
`rk audit --policy strict` runs over a clean trial trajectory and
exits 0; a fixture trajectory with a forbidden `pip install
datasets` invocation flags tainted and exits 23.
Verified by: both invocations against the named fixtures. Per plan
AC-8.3.

**AC-4 — Resume smoke succeeds.**
Halt-resume cycle on the canonical v2 path with hand-faked freeze
writes (per AC-3.6); sealed-hash check passes; resume proceeds.
Verified by: integration test runs the halt + hand-fake + resume
cycle and asserts the resume produces a non-degraded
`summary.json`. Per plan AC-8.4.

**AC-5 — Experiment-workflow smoke succeeds.**
Phase 5's AC-5.4 hypothesis smoke, re-run post-Phase-6/7, still
works end-to-end (propose → freeze → smoke → analyze → conclude).
Verified by: the same integration test from `phase5-workflow-templates`
re-runs and exits 0. Per plan AC-8.5.

**AC-6 — `uv run pytest` exits 0 from a clean checkout.**
Verified by: `git clone <razorback> /tmp/razorback-clean && cd
/tmp/razorback-clean && uv sync && uv run pytest` exits 0. Per
plan AC-8.6.

**AC-7 — README at repo root reflects v2.**
The repo-root README describes v2's CLI surface, agent class
shape, workflow template usage, and points at the v2 spec as
source of truth. Pre-v2 README content does not appear.
Verified by: a manual read confirms the v2 surface is described;
`grep` for pre-v2 module names (`run.py`, `claude_cli.py`, etc.)
returns no live references (only links into `_legacy/` if
retained). Per plan AC-8.7.

**AC-8 — CHANGELOG lists every sideline + every new addition with
v2 spec citations.**
Each Phase 6 sideline commit appears in CHANGELOG with its v2 spec
§-cite; each Phase 1-4a addition appears with its v2 spec §-cite;
each archived backlog entity (PKG-3/4/5/6/7/10) appears with a
"port-out to harbor adapter" note.
Verified by: a CHANGELOG walk confirms each entry has a spec
citation; the validation report lists each entry against the spec
§. Per plan AC-8.8.

**AC-9 — Version tag exists with major version bump.**
A git tag (e.g., `v2.0.0`) is annotated and points at the post-AC-8
commit. The tag message cites the v2 spec doc + the reconciliation
plan doc.
Verified by: `git tag -l 'v2.*'` lists the tag; `git tag -v
<tag>` displays the annotation. Per plan AC-8.9.

## Test plan

- **Smoke battery:** AC-1 through AC-5 each runs as an integration
  test in the validation worktree; the validator captures exit
  codes + key output artifacts.
- **Clean-checkout pytest:** AC-6 runs from a fresh `git clone` +
  `uv sync` + `uv run pytest`.
- **Doc walks:** AC-7 (README), AC-8 (CHANGELOG) each verified by
  a structured walk recorded in the validation report.
- **Tag verification:** AC-9 verified by `git tag` output and
  manual inspection of the annotation.
- **Acceptance command:** the validator runs the AC-1 through AC-5
  smokes end-to-end from a clean checkout; the validation report
  links each AC to its observed output.

## Out of scope

- Performance regression analysis. The walking-skeleton invariant
  is runnability + non-degraded `summary.json`; performance
  baselines are not gated here.
- Public release to PyPI. The version tag is the local marker;
  publication is a separate captain decision.
- Cross-language client distribution. v2 ships the Python CLI
  surface; non-Python consumers are not in scope.
- Goal 1 + Goal 2 result publication. Those goals ship after Phase
  4a; Phase 8 may reference their results in CHANGELOG but does
  not gate on their publication.

## Depends on

- `phase7-delete-legacy` (optional; if executed, must precede this
  entity so `_legacy/` is in its final state)
- `phase5-workflow-templates` (AC-5 re-runs the Phase 5 smoke)
- `phase6-promote-v2-canonical` (canonical surface stable)
- `phase4a-rk-audit-taint-port` (AC-3 smokes this)
- `phase4a-rk-score-wilson-stratified` (the smokes consume `rk
  score` output)
- `phase4a-rk-runs-cost` (smokes may invoke this)
- `phase4a-rk-run-budget-gate` (smokes may invoke this)
- `phase3-spacedock-solver-v2` (AC-2 + AC-4 smoke this class)
- `phase2-dab-harbor-adapter` (smokes run against this adapter)
- `phase1-rk-run-v2-wrapper` (rk run base)
