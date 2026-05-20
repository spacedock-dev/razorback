---
id: r08css78b4zkmjd9yc74e4at
title: PKG-1 v2 — rk runs list/show
status: validation
source: spec §3.2 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T06:42:02Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-pkg1-v2-rk-runs-cli
issue:
pr:
mod-block:
---

## Problem

V2 reconciliation retains the `rk runs list` and `rk runs show`
subcommands from PKG-1's original scope; the `rk validate` subcommand
and the broader workflow-infra-CLI wrapper drop out. Under v2 the
workflow CLI is spacedock first-officer machinery, not razorback's
job. What survives is the read-side over harbor's run-dir layout:
operators and analyze-stage agents need to enumerate runs by
experiment and read a run's headline summary without context-switching
into harbor. Spec §3.2 names both subcommands as part of the
first-ship surface, with the caveat that razorback defers to `harbor
job list` / `harbor job show` if and when harbor ships them.

## Acceptance criteria

**AC-1 — `rk runs list [--root <dir>] [--experiment <name>]` emits
JSON describing each run-dir under the base path, optionally filtered
by experiment label.**
Verified by: unit test against a `tmp_path` populated with two
synthetic run-dirs from two experiments. With `--experiment foo` only
foo's runs appear; without the flag, both appear. Each output element
carries `path`, `experiment`, `created_at`, and the headline score
from `summary.json`. Unit test path: `tests/unit/test_runs_list.py`.

**AC-2 — `rk runs show <run-dir>` emits a JSON document containing
the run's `summary.json` content plus a manifest envelope (experiment
label, run-dir path, run-dir-format version, created_at).**
Verified by: unit test feeds a fixture run-dir and asserts the
emitted JSON carries the manifest envelope with an ISO-8601
`created_at` and a `summary` field carrying whatever the run's
benchmark produced. Unit test path: `tests/unit/test_runs_show.py`.

**AC-3 — `rk runs show` exits with `ExitCode.USAGE` (2) when the
run-dir does not exist or is missing the expected files.**
Verified by: unit test passes a nonexistent path and asserts exit
code 2 with an error message naming the missing input.

**AC-4 — JSON output stable under spec §3.3's semver promise.**
Verified by: unit test pins a snapshot of each subcommand's output
keys against a fixture; CI fails on field rename or removal within
the major version.

## Test plan

- **Unit tests:** runs list (default + `--experiment` filter +
  `--root` override + empty root); runs show (valid + missing-summary
  + nonexistent path); JSON-key-stability snapshot per subcommand.
- **Integration test:** none required — both commands are
  filesystem-only.
- **Acceptance command:** `uv run rk runs list --root <fixture-root>
  --experiment <fixture-experiment>` and `uv run rk runs show
  <fixture-run-dir>` both exit 0 against the test fixtures.

## Out of scope

- `rk runs list --format human` table output. Spec §3.1 names JSON
  as the default and `--format human` as a polish flag; defer until
  a consumer surfaces.
- `rk validate`. Spec §3.2's first-ship surface does not include
  this subcommand; spec validation runs as a side effect of `rk
  freeze` (§6.3).
- The broader workflow-infra wrapper from original PKG-1. Spacedock
  first-officer machinery owns the workflow CLI surface under v2.
- Deferral to `harbor job list` / `harbor job show`. Spec §3.2 flags
  this as conditional on harbor shipping those subcommands; revisit
  at that time.

## Stage Report: plan

- DONE: Plan covers rk runs list (enumerate run-dirs with summary headlines) and rk runs show (per-run-dir detail). Cite spec §3.3.
  Plan at `docs/razorback-implementation/plans/pkg1-v2-rk-runs-cli.md` covers both subcommands and pins JSON-key stability against §3.3 in Task 6.
- DONE: Plan separates the rk runs CLI surface (independent of phase1) from data sources (run-dirs produced by phase1 rk run). Read-only CLI; safe to plan and implement in parallel with phase1 if needed.
  Plan's Architecture paragraph names the independence explicitly; `runs/inspect.py` reads phase1 artifacts but does not import phase1 code.
- DONE: Test plan: fixture-based (use a known-good run-dir from a recent baseline-rerun under .runs/baseline-rerun-20260520-bookreview/); validation reproduces against a fresh run-dir.
  Tasks 1-6 use synthetic `tmp_path` fixtures (`make_run_dir`); Task 7 acceptance pass exercises the real `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/` run-dir end-to-end.

### Summary

Plan is a separate doc at `docs/razorback-implementation/plans/pkg1-v2-rk-runs-cli.md` (entity has 4 ACs, crossing the dispatch's ≤3-AC inline threshold). Design decisions: (1) wire shape for `rk runs show` is `{manifest, summary, path}` — the manifest is surfaced verbatim rather than re-wrapped, so razorback does not bump its own version when harbor extends `manifest.json`; (2) `rk runs list` tolerates missing `summary.json` with `stratified_pass_at_1: null`, but `rk runs show` requires both files and fails with ExitCode.USAGE=2; (3) Task 6 is an exact-set snapshot of JSON keys, so any future field addition fails the test in the same commit it lands — the §3.3-correct gesture. Run-dir artifact shapes were inspected at plan time against `.runs/baseline-rerun-20260520-bookreview/`, so the fixture builder mirrors the real layout.
