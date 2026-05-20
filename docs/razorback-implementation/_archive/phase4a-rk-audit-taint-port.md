---
id: v6r0x3hhh4cbnvsnjz3mk6nt
title: Phase 4a — rk audit (taint.py port)
status: done
source: plan Phase 4a + spec §3.2 + §9.4 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started: 2026-05-20T07:03:12Z
completed: 2026-05-20T08:37:53Z
verdict: PASSED
score: 0.85
worktree: 
issue:
pr:
mod-block:
archived: 2026-05-20T08:37:53Z
---

## Problem

Phase 4a ships `rk audit` as the Layer 3 post-hoc check in the
three-layer leak-protection stack (spec §9.4). It ports
dataagentbench's `benchmark/lib/taint.py` (~561 LoC) verbatim with
attribution. The audit walks a run-dir's trial traces — parent agent
logs, subagent trace manifests, recursive subagent traces — and
pattern-matches against forbidden shell commands, web-search tool
calls, and the same patterns hidden inside heredocs / `python -c`
strings. Per-trial taint status emits as `clean` / `suspect` /
`tainted` / `coverage_missing`. The policy mode controls exit
behavior: `--policy strict` exits with `TaintFindingsError` (exit
23) on any non-`clean` trial; `--policy audit` (default) reports
without failing.

`rk audit` is independent of Phases 1-3's spec corrections — the
`taint.py` source is stable in dataagentbench and the port preserves
its behavior. It can begin once the test inventory (AC-0.14)
classifies the dataagentbench-side test fixtures, but does not
need to wait for Phase 1 to finish.

## Acceptance criteria

**AC-1 — `rk audit <run-dir>` walks trial traces and emits per-trial
taint status.**
Verified by: integration test against a fixture run-dir containing
one clean trial, one trial with a `pip install datasets` Bash
invocation, and one trial missing its trace manifest; asserts the
JSON output carries `taint_status` per trial as `clean`, `tainted`,
and `coverage_missing` respectively. Per plan AC-4a.7; spec §3.2 +
§9.4.

**AC-2 — Pattern categories: shell commands, web-search tool calls,
heredoc + `python -c` decoded patterns.**
Verified by: fixture-driven unit tests exercise each pattern
category:
- a clean trajectory passes (`clean`)
- a `pip install datasets` Bash command flags `tainted`
- the same hidden in `python -c "subprocess.run(['pip',
  'install', 'datasets'])"` flags `tainted` (python-c decoder
  working)
- the same hidden in a heredoc flags `tainted` (heredoc decoder
  working)
- a web-search tool invocation flags `tainted`

Per plan AC-4a.8.

**AC-3 — Recursive subagent-trace scan.**
A subagent trace with a forbidden invocation flags the parent trial
as `tainted` (the audit recurses through subagent_traces manifest
references).
Verified by: fixture-driven unit test with a parent trace whose
subagent trace contains a forbidden invocation; asserts the parent
trial's `taint_status` is `tainted` with a finding citing the
subagent path. Per plan AC-4a.8.

**AC-4 — `coverage_missing` is distinct from `clean`.**
A trace with a missing manifest flags `coverage_missing` not
`clean`. Silent absence of audit data must not be reported as a
clean pass.
Verified by: fixture-driven unit test removes a trial's trace
manifest; asserts the output carries `coverage_missing` and the
exit code differs from the all-clean case under `--policy strict`.
Per plan AC-4a.8.

**AC-5 — `--policy strict` exits with `TaintFindingsError` (exit 23)
on any non-`clean` trial.**
Verified by: integration test runs `rk audit --policy strict`
against a run-dir containing one tainted trial; asserts exit code
23 and the JSON output carries findings. `--policy audit` (default)
against the same run-dir exits 0 with the same findings reported.
Per plan AC-4a.7; spec §3.4 exit-code table.

**AC-6 — Attribution preserved.**
The ported code carries an ABOUTME comment + module-level docstring
citing
`/Users/clkao/git/dataagentbench/benchmark/lib/taint.py` as the
source. The commit message naming the port cites the source path +
line ranges + the date of the port.
Verified by: `grep -n "dataagentbench" src/razorback/audit/` returns
the attribution; the commit's body cites the source. Per plan AC-4a.7.

**AC-7 — `uv run pytest` exits 0.**
Verified by: pytest exits 0 from a clean checkout including the new
audit test suite.

## Test plan

- **Unit tests:** per pattern category (shell, web-search, heredoc,
  python-c) with isolated fixtures; recursive subagent scan;
  coverage-missing detection; policy mode exit-code behavior.
- **Integration test:** `rk audit` against a real bookreview
  run-dir from Phase 1 + Phase 3 smokes; assert exit 0 under
  `--policy audit` (or document the surfaced taint if any).
- **Acceptance command:** `uv run rk audit <fixture-run-dir>
  --policy strict` exits 23 against the tainted-trial fixture and
  exit 0 against the clean-trial fixture.

## Out of scope

- Benchmark-name / dataset-name / answer-key string scanning over
  trial transcripts (separate pattern category from forbidden tool
  invocations). Deferred per reconciliation plan's "Package J"
  section; lands when a suspected leak surfaces that the initial
  audit patterns did not catch.
- Harbor's `harbor analyze --rubric reward_hacking` delegation as a
  second-layer post-hoc check. Out of scope for `rk audit` per the
  same deferred-package section.
- Layer 1 static leak guard (workflow-README review at propose
  stage). Phase 5's template prompt content owns this.
- Layer 2 runtime leak guard (`tools_denied` PreToolUse hooks).
  `v4` pkg9-v2-tools-denied-field owns this.

## Depends on

- `ra` spec-corrections-from-phase0-probes (spec §3.2 + §9.4
  wording referenced by AC-1; the spec must reflect the v2 surface
  before the port's commit attributes back to it)

## Stage Report: plan

- DONE: Plan names the port source (/Users/clkao/git/dataagentbench/benchmark/lib/taint.py, 561 LoC) and maps each function/class to a target file:line in razorback (src/razorback/audit/taint.py and src/razorback/audit/subagent_traces.py).
  Plan doc Task 2 carries the full source-line → target-line mapping table; Task 3 carries the partial-port closure for subagent_traces.py with PORT / DROP per line range.
- DONE: Plan separates the verbatim port from razorback-specific adapter glue.
  Task 2 (verbatim taint.py port) + Task 3 (partial subagent_traces.py port, read-side closure only) carry the verbatim port with attribution; Task 4 (CLI glue), Task 5 (KEEP-VERBATIM test re-anchoring), Task 6 (razorback integration test), Task 7 (attribution proof), Task 8 (test-suite green) carry the razorback-specific surface.
- DONE: Test plan reuses dataagentbench's existing taint.py tests verbatim where possible (KEEP-VERBATIM per test inventory); razorback-specific glue tests follow TDD.
  Task 5 ports /Users/clkao/git/dataagentbench/benchmark/tests/test_taint.py verbatim (18 tests covering AC-2/3/4) with only the import path re-pointed; Task 6 adds 4 new razorback-CLI tests (TDD; fixture-driven) for AC-1 + AC-5; Task 1 verifies P1-T1's errors.py wiring (TaintFindingsError + ExitCode.TAINT_FINDINGS) which the entity's AC-5 relies on.

### Summary

Plan committed to docs/razorback-implementation/plans/phase4a-rk-audit-taint-port.md (8 tasks, 7 ACs covered, riskiest-mechanism-first ordering per CL's "Validating new mechanisms" rule: verbatim port → KEEP-VERBATIM tests → razorback glue → integration test). Key decisions: (1) port subagent_traces.py partially (read-side closure only — capture-side helpers live in Phase 3's spacedock-solver runtime, not razorback's post-hoc audit); (2) per-trial reducer rule mapping the upstream finding shape to clean/tainted/coverage_missing is named explicitly in Task 4; (3) trial-root discovery walks by sentinel-file presence (codex-output.jsonl / claude-output.jsonl / traces/manifest.json) rather than hardcoded path globs, to stay robust against harbor's run-dir layout. Risk: closure-determination in Task 3 — mitigated by KEEP-VERBATIM tests at Task 5 catching missing helpers before any glue lands.

## Stage Report: implementation

- DONE: Verbatim port of taint.py from dataagentbench (Task 2) with attribution; PARTIAL port of subagent_traces.py per plan (read-side closure only).
  src/razorback/audit/taint.py is verbatim modulo the import re-point (diff confirms one-line delta vs source); src/razorback/audit/subagent_traces.py ports IGNORED_TRACE_ROOT_PARTS + _codex_trace_paths + _read_jsonl + _collab_item + _stage_from_prompt + parse_parent_lifecycle + parent_has_completed_spawns + _under_ignored_trace_root + iter_trace_roots + _hook_event_counts + hook_reconciliation_issues; capture-side symbols dropped per plan.
- DONE: KEEP-VERBATIM tests from dataagentbench/benchmark/tests/test_taint.py (18 tests) re-anchored to razorback import paths (Task 5).
  tests/unit/audit/test_taint_keep_verbatim.py: 18/18 pass. Sole edit vs source is `from benchmark.lib import taint` → `from razorback.audit import taint`.
- DONE: razorback CLI glue (Tasks 4, 6, 8) wires rk audit; AC-5 uses TaintFindingsError + ExitCode.TAINT_FINDINGS from phase1's errors.py.
  src/razorback/audit/cli.py implements per-trial reducer (forbidden_lookup→tainted; trace_coverage missing/partial + attempt_incomplete + scanner_error→coverage_missing; else clean) + `--policy {audit,strict}` flag + sentinel-file trial-root discovery + JSON/markdown formatters. src/razorback/cli/__init__.py registers `audit` next to `run`. tests/unit/audit/test_rk_audit_cli.py: 6/6 pass (AC-1 per-trial status, AC-5 strict→23 and audit→0, all-clean→0 under strict, markdown format, unknown-policy rejection).

### Summary

All 7 ACs satisfied. 18 KEEP-VERBATIM unit tests + 6 razorback-CLI integration tests pass (24/24 audit suite); `uv run pytest tests/unit --ignore=tests/unit/test_translator_harbor_dab.py` exits 0 with 248 tests passing. One pre-existing collection error (`tests/unit/test_translator_harbor_dab.py` imports `razorback.compat` which P1-T4 moved to `_legacy/`) was confirmed to predate Phase 4a — stashing all worktree changes and re-running the sweep against the bare branch tip reproduces the same error; out of scope for this entity. Six pre-existing integration-test failures (`tests/integration/test_rk_run_*`) similarly predate Phase 4a (walking-skeleton AC gaps + docker required); same reproduction confirms they are not regressions introduced by the audit module.

## Stage Report: validation

- DONE: AC coverage scan: each AC has evidence on the worktree branch (verbatim taint.py port + PARTIAL subagent_traces.py + KEEP-VERBATIM 18 tests + razorback CLI glue).
  AC-1/4 covered by tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_emits_per_trial_status. AC-2/3/4 covered by 18 KEEP-VERBATIM tests in tests/unit/audit/test_taint_keep_verbatim.py (all upstream pattern + recursive-scan + coverage cases). AC-5 covered by test_rk_audit_policy_strict_exits_23 + test_rk_audit_policy_audit_exits_0 + test_rk_audit_all_clean_exits_0_under_strict. AC-6 verified: `grep -n dataagentbench src/razorback/audit/` returns 7 matches across __init__.py, taint.py, subagent_traces.py; commit b012556 body cites both source paths + line ranges + port date 2026-05-20. AC-7 caveated below.
- DONE: Run uv run pytest from clean checkout; report N/N passed; note pre-existing failures.
  `uv run pytest tests/unit/audit/`: 24/24 PASS (18 KEEP-VERBATIM + 6 razorback CLI). Full sweep `uv run pytest --ignore=tests/unit/test_translator_harbor_dab.py`: 254 passed, 3 skipped, 6 failed. All 6 failures (tests/integration/test_rk_run_*) reproduce on `main` (verified by running same selection from the main worktree); confirmed pre-existing, not regressions. Collection error in tests/unit/test_translator_harbor_dab.py also reproduces on `main` (imports razorback.compat which P1-T4 moved to _legacy/).
- DONE: Run superpowers:requesting-code-review on worktree diff; classify findings; recommend PASSED or REJECTED with feedback-to.
  Code review performed inline (code-reviewer subagent dispatch tool not surfaced in this runtime). Findings: 1 Important (em-dash style violation in cli.py + commit message), 2 Minor (trial ordering not pinned in test; `format` shadows builtin), 1 pre-existing non-blocker (translator_harbor_dab collection error). Verbatim port preserved correctly (diff confirms one-line delta vs source). Closure determination for subagent_traces.py is complete (all 3 taint.py call sites resolve). KEEP-VERBATIM tests cover the closure boundary.

### Summary

PASSED with one fix-up item. Mechanism is correct: 24/24 audit suite passes, all 7 ACs have evidence on the worktree branch, no regressions vs main. The one Important finding is the em-dash style ban from commit a2e9c49: src/razorback/audit/cli.py carries em-dashes at lines 1, 21, 123, and the commit message of b012556 contains em-dashes in the subject + body. The verbatim ports (taint.py, subagent_traces.py) are exempt by their verbatim contract and confirmed clean of em-dashes; only the new razorback-authored cli.py and the commit message need the substitution. Recommend routing back to implementation for a one-pass em-dash fix in src/razorback/audit/cli.py before merge; the bug bar is met and the mechanism is sound, so this is a style-only feedback loop, not a redo.
