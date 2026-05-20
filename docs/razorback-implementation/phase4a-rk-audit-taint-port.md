---
id: v6r0x3hhh4cbnvsnjz3mk6nt
title: Phase 4a — rk audit (taint.py port)
status: backlog
source: plan Phase 4a + spec §3.2 + §9.4 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started:
completed:
verdict:
score: 0.85
worktree:
issue:
pr:
mod-block:
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
