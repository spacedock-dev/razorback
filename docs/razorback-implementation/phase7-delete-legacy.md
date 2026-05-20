---
id: sdaahx3ehzyk421zk2bmn5fa
title: Phase 7 — delete _legacy/ holding tank (optional)
status: backlog
source: plan Phase 7 (v2 reconciliation plan at docs/superpowers/plans/2026-05-19-razorback-reconciliation-plan.md)
started:
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
mod-block:
---

## Problem

Phase 7 is the optional cleanup that deletes
`src/razorback/_legacy/`. Per D6's default, one release cycle elapses
after Phase 6 promotes v2 to canonical; if no parity test, rollback,
or external consumer still references `_legacy/`, the holding tank
deletes. The plan does not gate later work on this phase — `_legacy/`
is harmless and doesn't pollute the canonical surface — but
deletion keeps the codebase tidy and removes a future maintenance
liability.

The captain decides whether to execute Phase 7 at all. If executed,
each deletion is its own commit per logical group for bisect
friendliness.

## Acceptance criteria

**AC-1 — Walking skeleton holds.**
A DAB benchmark runs end-to-end via the canonical v2 path after the
deletion.
Verified by: `uv run rk run examples/specs/bookreview-claude.frozen.yaml`
exits 0 and produces a non-degraded `summary.json`. Per plan AC-7.1.

**AC-2 — `_legacy/` audited.**
Every module under `src/razorback/_legacy/` has a status:
- imported-by-parity-test (keep or retire test)
- imported-by-deprecation-alias (decide whether the alias is still
  needed)
- unreferenced (delete)
Verified by: an audit report committed alongside this entity's
deletion commits enumerates each module and its disposition. Per
plan AC-7.2.

**AC-3 — `_legacy/` removed or trimmed per the audit.**
One commit per logical deletion group for bisect-friendliness.
Each commit is bisect-clean (tests pass between commits).
Verified by: `git log --oneline -- src/razorback/_legacy/` shows
the deletion commits in logical groupings; `git bisect run uv run
pytest` across the deletion commits exits 0 at every step. Per
plan AC-7.3.

**AC-4 — No stray imports from `_legacy/`.**
`grep -r 'from razorback._legacy'` returns no hits (or only hits
the captain explicitly chose to retain per the audit).
Verified by: the grep command run from the worktree's repo root
returns no hits. Per plan AC-7.4.

**AC-5 — `uv run pytest` exits 0 after the deletion.**
Per plan AC-7.5.

**AC-6 — Post-deletion DAB smoke matches Phase 6's smoke score.**
Verified by: a post-deletion DAB smoke run's headline score matches
Phase 6's smoke result within statistical tolerance (per `rk score
--against-constant` or `rk diff` if available). Per plan AC-7's
walking-skeleton-check note.

## Test plan

- **Audit:** module-by-module disposition table for everything in
  `_legacy/`.
- **Bisect-clean deletion:** `git bisect run uv run pytest` exits
  0 across the deletion commits.
- **Grep verification:** `grep -r 'from razorback._legacy'`
  returns no unauthorized hits.
- **Post-deletion smoke:** DAB end-to-end produces the same score
  as Phase 6's smoke.
- **Acceptance command:** `uv run rk run
  examples/specs/bookreview-claude.frozen.yaml` exits 0 after the
  deletion.

## Out of scope

- **Captain may decline to execute this phase.** Per plan Phase 7
  status note: this phase is optional; the captain decides whether
  to execute it at all. If declined, the entity stays in backlog
  indefinitely without blocking later work.
- Removing modules the captain explicitly retains (deprecation
  aliases, parity-test imports the captain wants to keep).
- Re-importing previously-sidelined modules. The promotion path is
  Phase 6's direction only.

## Depends on

- `phase6-promote-v2-canonical` (Phase 6 created the `_legacy/`
  contents; Phase 7 audits and deletes; one-release-cycle delay
  per D6 default before this entity activates)
