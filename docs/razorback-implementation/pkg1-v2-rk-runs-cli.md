---
id: r08css78b4zkmjd9yc74e4at
title: PKG-1 v2 — rk runs list/show
status: plan
source: spec §3.2 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T06:42:02Z
completed:
verdict:
score:
worktree:
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
