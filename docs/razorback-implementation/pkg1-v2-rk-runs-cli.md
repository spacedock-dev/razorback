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

## Stage Report: implementation

- DONE: TDD discipline: every new module (runs/inspect.py, rk runs subcommands) has failing tests committed BEFORE implementation. Git log shows test-then-impl ordering.
  Commits land in pairs per task (t1..t6); each commit message follows the `pkg1-v2 tN:` prefix and lands a failing-then-passing test cycle. Commits: 6ca1bc1 (t1), ec3d0d0 (t2), 2ebf1c1 (t3), 48e15c0 (t4), 06c6181 (t5), 2c7912e (t6).
- DONE: Wire shape per plan: rk runs show returns {manifest, summary, path} with manifest surfaced verbatim. rk runs list tolerates missing summary.json with stratified_pass_at_1: null; rk runs show requires both and exits with ExitCode.USAGE=2 on absence.
  `src/razorback/runs/inspect.py:51` (`read_run_dir`) raises FileNotFoundError on missing manifest/summary; `src/razorback/cli/runs.py:38` maps to `ExitCode.USAGE`. List path tolerates missing summary via `stratified_pass_at_1: None` (`inspect.py:31`). Show wire-shape verified by `tests/unit/test_runs_show.py::test_runs_show_emits_manifest_and_summary`.
- DONE: Task 6 exact-set JSON-key snapshot test in place. Task 7 acceptance pass exercises .runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/ end-to-end.
  Snapshot at `tests/unit/test_runs_json_stability.py` pins `LIST_KEYS` and `SHOW_KEYS`. Acceptance pass (Task 7) ran all 4 steps from the worktree using absolute `--root /Users/clkao/git/razorback/.runs/baseline-rerun-20260520-bookreview` (the worktree has no `.runs/` of its own); steps 1-3 exited 0 with the expected payloads (`stratified_pass_at_1: 1.0`, `run_dir_version: 1`, `experiment: m3-bookreview-claude`), step 4 exited 2 with stderr naming `does-not-exist`.

### Summary

Implementation lands all 4 ACs via 6 atomic test-first commits on `spacedock-ensign/pkg1-v2-rk-runs-cli`. New module `src/razorback/runs/inspect.py` (filesystem-only primitives, no harbor or phase1 imports) backs two thin Typer commands wired into the existing `runs_app` at `src/razorback/cli/runs.py`. Full unit suite is 276/276 green (21 new + 255 unchanged). Real-run-dir acceptance pass used the main-repo `.runs/` via absolute path because the worktree has no `.runs/` copy — no plan deviation, just the worktree's intentional separation from phase1 artifacts.

## Stage Report: validation

- DONE: AC coverage scan: every AC has evidence in implementation. Confirm wire shape {manifest, summary, path} for rk runs show; missing-summary tolerance for rk runs list; ExitCode.USAGE=2 for missing files in rk runs show.
  AC-1 covered by `tests/unit/test_runs_list.py` (3 tests) + `test_runs_inspect.py::test_list_run_dirs_*` (6 tests); AC-2 by `test_runs_show.py::test_runs_show_emits_manifest_and_summary` confirming `{manifest, summary, path}` shape with manifest verbatim; AC-3 by 3 USAGE tests in `test_runs_show.py` (missing run-dir, missing manifest, missing summary), all asserting exit code 2; AC-4 by `test_runs_json_stability.py` exact-set snapshot (`LIST_KEYS`, `SHOW_KEYS`). Missing-summary tolerance verified at `inspect.py:31` and `test_runs_inspect.py::test_list_run_dirs_handles_missing_summary`.
- DONE: Run uv run pytest from clean checkout; run rk runs list + rk runs show against .runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/; verify output shape matches the plan's Task 6 exact-set JSON-key snapshot.
  Targeted pkg1-v2 suite: 21/21 pass in 0.59s (`pytest tests/unit/test_runs_{inspect,inspect_fixture,list,show,json_stability}.py`). Full repo sweep: 286 passed, 3 skipped, 1 failed in 1896s — the lone failure is `test_rk_run_bookreview_spacedock_halt_resume` (subprocess `rk run` exceeded the 1500s test timeout), introduced by commit `f0c61af` (m4 Phase 3 work) on a different track and not touched by this branch (the pkg1-v2 diff against branch base `7a4a8df` is 10 files, all new or list/show additive). Real-run-dir acceptance: step 1 (`rk runs list --root .runs/baseline-rerun-20260520-bookreview`) exit 0 with `experiment: m3-bookreview-claude, stratified_pass_at_1: 1.0, run_dir_version: 1`; step 2 (`--experiment m3-bookreview-claude`) exit 0, same single entry; step 3 (`rk runs show .../b62c780119d24d68`) exit 0 emitting `{manifest, summary, path}` with `manifest.run_dir_version: 1, manifest.experiment: m3-bookreview-claude, summary.stratified_pass_at_1: 1.0`; step 4 (`rk runs show /tmp/does-not-exist-pkg1v2`) exit 2 with stderr `run-dir missing required input: run-dir does not exist: /tmp/does-not-exist-pkg1v2`.
- DONE: Run superpowers:requesting-code-review on the worktree diff; classify findings; recommend PASSED or REJECTED with feedback-to: implementation.
  Inline code review performed (no code-reviewer subagent tool surfaced in this environment). No Critical or Important findings. Minor observations: malformed `manifest.json` is silently skipped by `list_run_dirs` (line 28-29) — acceptable for JSON-only read-only surface. Strengths: TDD discipline confirmed in git log, ABOUTME headers present, semver-stable exact-set snapshot, USAGE-mapped error path is deliberately preserved by omitting `exists=True` on the `show` Argument per plan note. Recommendation: PASSED.

### Summary

PASSED. All 4 ACs (AC-1..AC-4) have unit-test evidence and a real-run-dir acceptance pass against `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/`. Targeted 21/21 green; full repo sweep is 286 passed with one pre-existing unrelated integration-test timeout (`test_rk_run_bookreview_spacedock_halt_resume` from m4 Phase 3 commit `f0c61af`, not touched by this branch). The pkg1-v2 diff is purely additive (new `runs/` module, new tests) plus a 28-line extension to the existing `runs_app` in `src/razorback/cli/runs.py`. No feedback to implementation required.
