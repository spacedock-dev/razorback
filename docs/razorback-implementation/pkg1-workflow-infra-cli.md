---
id: 7npzq6jarhz9s6e2wz3ga27v
title: PKG-1 — Workflow infra CLI (rk runs list/show + rk validate file-existence)
status: backlog
source: SWE review P0-1 + P0-2 (2026-05-19)
started:
completed:
verdict:
score: 0.95
worktree:
issue:
pr:
mod-block:
---

## Problem

Two CLI gaps that block the experiment + run workflows from
operating:

1. **`rk runs list` and `rk runs show` are documented but never
   implemented.** §3.2 of the design specifies both as part of the
   v0.1 surface. Implementation only wires `diff` at
   `src/razorback/cli/runs.py:20` (`@runs_app.command("diff")`).
   Anyone following the design doc gets a Typer "No such command"
   surprise.

2. **`rk validate` does not check that referenced files exist.**
   §3.2 line 130: "ensure all referenced files exist". M7 Task 4
   (line 906 of `plans/m7-run-workflow-adebench.md`) made a
   unilateral implementation decision against this without a named
   divergence — exactly the silent-gap class the named-divergence
   discipline is supposed to catch. Today: `rk validate` against a
   misspelled `task_paths[0]` exits 0; `rk run` then fails minutes
   later inside harbor.

## Unlocks

- `experiments.propose` can pre-flight specs without late harbor
  failures (debug loop from minutes to seconds).
- `experiments.smoke` and `experiments.full` can read each run's
  `summary.json` shape via `rk runs show` and write the result into
  the entity body for the analyze stage to inspect.
- `experiments.analyze` (via `rk runs list`) can enumerate prior
  runs of an experiment for trend tracking and baseline lookup.

## Acceptance criteria

**AC-1 — `rk runs list [--experiment <name>] [--runs-dir <path>]`
emits JSON describing each run-dir under the base path.**
Verified by: a unit test against a `tmp_path` populated with two
synthetic run-dirs; the command's JSON output is an array with
each element carrying `path`, `experiment`, `job_name`,
`created_at`, and the run's headline `score` from `summary.json`.
Unit test path: `tests/unit/test_runs_list.py`.

**AC-2 — `rk runs show <run-dir>` emits the run's `summary.json`
content augmented with the `manifest.json` envelope
(experiment, job_name, run_dir_version, created_at).**
Verified by: a unit test feeds a fixture run-dir and asserts the
emitted JSON has `manifest.run_dir_version: 1`,
`manifest.created_at` is ISO 8601, and `summary.*` carries
whatever shape the run's benchmark produced (DAB stratified,
ade-bench, etc.). Unit test path:
`tests/unit/test_runs_show.py`.

**AC-3 — `rk runs list` filters by `--experiment <name>` when set
and lists all runs when omitted.**
Verified by: a unit test against fixture run-dirs from two
experiments; with `--experiment foo` only foo's runs appear;
without the flag, both experiments' runs appear.

**AC-4 — `rk runs show` exits with `ExitCode.USAGE` (2) when the
run-dir does not exist or is missing `manifest.json`.**
Verified by: a unit test passes a nonexistent path and asserts
exit code 2 with a clear error message.

**AC-5 — `rk validate` checks `.exists()` on every Path-typed field
in the spec.**
Verified by: a unit test feeds a spec with a misspelled
`agent.prompt_file` and asserts `SpecError` is raised at validate
time (exit code 10), with the missing path named in the error
message. Same for `benchmark.data_root`,
`benchmark.tasks_root`, `benchmark.task_paths[i]`.

**AC-6 — `rk validate` exits 0 on a valid spec with all paths
present.**
Verified by: a unit test against a known-good fixture spec exits
0 and emits no error output.

**AC-7 — Existing `rk validate` warnings (M7-shipped: ade-bench
compose_services warning, tools_allowed-not-enforced warning)
continue to fire alongside the new file-existence checks.**
Verified by: existing `tests/unit/test_validate_warnings.py` (or
its successor) stays green.

## Test plan

- **Unit tests:** runs list (default + --experiment filter +
  empty runs_dir); runs show (valid + missing-manifest + bad
  path); validate (missing prompt_file + missing data_root +
  missing tasks_root + missing task_paths element + warnings
  still fire).
- **Integration test:** none required — both commands are
  filesystem-only.
- **Acceptance command:** `uv run rk runs list && uv run rk runs
  show <fixture> && uv run rk validate <fixture-spec>` all exit
  0 against the test-fixture run-dir + spec.

## Out of scope

- `rk runs list --format human` table output (§3.2 mentions a
  `--format human` flag — JSON-only ships here; human-format
  defers to a polish task).
- `rk runs diff --format markdown` (separate finding; M6
  out-of-scopes markdown; not load-bearing for the experiment
  workflow which reads JSON).
- The harbor abstraction refactor (SWE P1-3 — separate concern,
  defer-OK).
