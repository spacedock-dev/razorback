# Phase 4a — rk audit (taint.py port) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `rk audit <run-dir>` as Layer 3 of the three-layer leak-protection stack (spec §9.4). The CLI walks a run-dir's trial traces (parent agent logs, subagent trace manifests, recursive subagent traces) and pattern-matches against forbidden shell commands, forbidden tool calls, and the same patterns hidden inside heredoc bodies / `python -c` strings. Per-trial taint status emits as `clean` / `tainted` / `coverage_missing`. `--policy strict` exits with `TaintFindingsError` (exit 23) on any non-`clean` trial; `--policy audit` (default) reports without failing.

**Architecture:** The scan core is a verbatim port of dataagentbench's `benchmark/lib/taint.py` (561 LoC) with attribution. Its transitive dependency `benchmark/lib/subagent_traces.py` (870 LoC) ports the read-side surface only — capture-side helpers used at trial-runtime in dataagentbench (`prepare_codex_spacedock_trace_capture`, `materialize_hook_traces`, `write_trace_manifest`) are out of scope for razorback's post-hoc audit and stay un-ported. Razorback-specific glue is thin: a Typer subcommand (`rk audit`), a `--policy {audit|strict}` flag, JSON / markdown output formatters, and the policy → exit-code mapping that raises `TaintFindingsError` (exit 23, already in `src/razorback/errors.py` from Phase 1's P1-T1).

**Tech Stack:** Python 3.12, Typer (CLI), stdlib `re` / `shlex` / `tokenize` (already used by the source `taint.py`). No new third-party deps.

**Spec source of truth:** `/Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §3.2 (CLI surface), §3.4 (exit code 23), §9.4 (three-layer leak-protection stack, Layer 3 wraps `taint.py`). The spec is concurrently being edited by `ra` (spec-corrections-from-phase0-probes); this plan cites section identities, not verbatim wording, so it does not invalidate on `ra`'s edits.

**Port-source authoritative reference:**
- `/Users/clkao/git/dataagentbench/benchmark/lib/taint.py` (561 LoC) — verbatim port target. Module-level globals, helpers, and public entry points (`discover_scan_inputs`, `scan_attempt`, `decide_status`, `render_markdown`) port unchanged.
- `/Users/clkao/git/dataagentbench/benchmark/lib/subagent_traces.py` (870 LoC) — partial port; read-side helpers only (see Task 3 for the line-range cut).

**Concurrent dependency status:**
- `ra` spec-corrections-from-phase0-probes: in `validation` at plan time. Phase 4a's port does not block on `ra` (the section identities §3.2 / §3.4 / §9.4 are stable; only wording is in flight). The commit message's spec cite uses section identities.
- Phase 1 (P1-T1): completed. `src/razorback/errors.py` already carries `TaintFindingsError(exit_code=23)` and `ExitCode.TAINT_FINDINGS = 23`. **Validation step at Task 1:** confirm by reading `src/razorback/errors.py` from the worktree branch tip; if the symbol is absent, add it before proceeding (the task list shows P1-T1 completed but `errors.py` on `main` at plan time only carries through `HARBOR_RUNTIME = 30`; the worktree branch may carry the addition. Re-verify, do not assume.)
- Phase 1 CLI scaffold (`src/razorback/cli/__init__.py`): completed; `rk audit` registers as a sibling subcommand of `rk run`, `rk score`, `rk freeze`. Follow the existing `cli/run.py` Typer pattern.

---

## AC ↔ task map (1:1 with cross-cutting tasks called out)

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-6 (attribution) | spec §9.4 Layer 3 ("port of dataagentbench's `benchmark/lib/taint.py` with attribution") | Task 2 (taint.py port body), Task 3 (subagent_traces.py partial port), Task 7 (commit-message attribution + grep proof) |
| AC-2, AC-3 (pattern categories + recursive subagent scan) | spec §9.4 Layer 3 #1-3 (subagent escape, heredoc / python-c masking, hook-config drift) | Task 2 (port body carries all pattern categories), Task 5 (KEEP-VERBATIM tests from dataagentbench re-anchored at the new import paths) |
| AC-1, AC-4 (per-trial taint status + `coverage_missing` distinct from `clean`) | spec §3.2 (`rk audit` description) — emits `clean` / `tainted` / `coverage_missing` per trial | Task 4 (razorback glue: per-trial reducer + output shape), Task 6 (razorback integration test) |
| AC-5 (`--policy strict` exits 23) | spec §3.4 exit-code table (row 23) + §3.2 (`--policy strict`) | Task 4 (CLI flag + exit-code mapping), Task 6 (integration test asserts exit 23 vs 0) |
| AC-7 (`uv run pytest` exits 0) | (plan AC-4a.7 ↦ entity AC-7) | Task 8 (test-suite green from worktree branch tip) |

**Riskiest contract first.** Task 2 (verbatim port of `taint.py`) + Task 3 (partial port of `subagent_traces.py`) land BEFORE the razorback glue (Task 4) so the KEEP-VERBATIM tests from dataagentbench (Task 5) can be re-pointed and run as the mechanism check. Per CL's "Validating new mechanisms" rule, mechanism validation precedes integration. The fixture-driven integration test (Task 6) follows once the unit-level KEEP-VERBATIM tests pass.

**Module inventory anchors (per `docs/superpowers/plans/2026-05-19-razorback-inventory.md`):**
- REWRITTEN-FROM-SPEC + verbatim out-of-tree port: `rk audit` (§3.2, §9.4 Layer 3) — line 708-710 of the inventory names it as "REWRITTEN FROM SPEC. Ports dataagentbench's `benchmark/lib/taint.py` mechanism (out-of-tree; not in `src/razorback/`)". Out-of-tree means the source is **outside** razorback (in dataagentbench); the port lands inside `src/razorback/audit/`.
- ADAPT-EXTRACT: `src/razorback/errors.py:7-16` (already adapted in P1-T1 to add `TAINT_FINDINGS = 23` + `TaintFindingsError`); `src/razorback/cli/__init__.py:8-19` (Typer-wiring pattern survives; add `audit` subcommand registration).
- NEW: `src/razorback/audit/__init__.py`, `src/razorback/audit/taint.py`, `src/razorback/audit/subagent_traces.py`, `src/razorback/audit/cli.py`, plus tests under `tests/unit/audit/` and a fixture run-dir under `tests/fixtures/audit/`.

**Out of scope per entity body:**
- Benchmark-name / dataset-name / answer-key string scanning over trial transcripts (separate pattern category from forbidden tool invocations). Deferred per reconciliation plan's "Package J" section.
- Harbor's `harbor analyze --rubric reward_hacking` delegation as a second-layer post-hoc check.
- Layer 1 static leak guard (workflow-README review at propose stage) — Phase 5 owns this.
- Layer 2 runtime leak guard (`tools_denied` PreToolUse hooks) — `v4 pkg9-v2-tools-denied-field` owns this.
- Capture-side trace materialization (subagent_traces.py lines 1-260: `TraceCaptureConfig`, `prepare_codex_spacedock_trace_capture`, `materialize_hook_traces`, `_hook_event_to_trace_events`, `_hook_tool_item`). The audit reads pre-existing manifests; it does not write them. Phase 3 (spacedock solver v2) owns capture wiring on the runtime side.

---

## Task 1 — Verify `TaintFindingsError(23)` + `ExitCode.TAINT_FINDINGS = 23` are wired in `src/razorback/errors.py`

**Files:**
- Read: `src/razorback/errors.py` (from the Phase 4a worktree branch tip)

**Why:** P1-T1 in the task list is marked completed, but `errors.py` on `main` at plan time shows only `HARBOR_RUNTIME = 30` as the last code. The Phase 1 worktree branch may carry the addition; this task confirms before proceeding. If absent, the entity body's AC-5 (`exit 23`) cannot be satisfied.

**Steps:**
- [ ] `git log -1 --oneline -- src/razorback/errors.py` to confirm the file's source.
- [ ] Read `src/razorback/errors.py`; verify `ExitCode.TAINT_FINDINGS = 23` and `class TaintFindingsError(RazorbackError)` exist with `exit_code = ExitCode.TAINT_FINDINGS`.
- [ ] If absent, add both (same shape as `SeedMismatchError` at `errors.py:28-30`). Same shape: 2-line docstring citing §3.2 `rk audit --policy strict`, `exit_code: int = ExitCode.TAINT_FINDINGS`.

**Validation:** `uv run python -c "from razorback.errors import TaintFindingsError, ExitCode; assert TaintFindingsError().exit_code == 23 == ExitCode.TAINT_FINDINGS"`.

---

## Task 2 — Verbatim port `taint.py` to `src/razorback/audit/taint.py` with attribution

**Files:**
- Create: `src/razorback/audit/__init__.py` (package marker — 2-line ABOUTME).
- Create: `src/razorback/audit/taint.py` (verbatim port of 561 LoC).

**Why:** AC-6 (attribution) + AC-2 (pattern categories) + AC-3 (recursive subagent scan) all rest on the verbatim port. The source is stable in dataagentbench; rewriting from spec would re-invent the heredoc / python-c masking machinery (`_mask_python_heredoc_bodies`, `_mask_shell_quoted_strings`, `_python_c_sources`, `_python_tokens`, `_scan_python_source`) and the recursive subagent scan logic (`scan_attempt` → `discover_scan_inputs` → `_scan_jsonl` traversal of `subagent_trace` source kinds). Verbatim port preserves the upstream behavior we are validating against.

**Source mapping (file:line in `/Users/clkao/git/dataagentbench/benchmark/lib/taint.py` → target lines in `src/razorback/audit/taint.py`):**
| Source lines | Symbol | Target |
|---|---|---|
| 1-8 (imports) | stdlib + `from benchmark.lib import subagent_traces` | Imports re-pointed to `from razorback.audit import subagent_traces` |
| 11-24 | `FORBIDDEN_SHELL_PATTERNS`, `FORBIDDEN_TOOL_PATTERNS` | verbatim |
| 27-31 | `_rel` | verbatim |
| 34-60 | `discover_scan_inputs` | verbatim |
| 63-76 | `_scan_text` | verbatim |
| 79-83 | `_shell_words` | verbatim |
| 86-96 | `_shell_scripts` | verbatim |
| 99-118 | `_heredoc_sources` | verbatim |
| 121-126 | `_line_invokes_python_before_heredoc` | verbatim |
| 129-151 | `_mask_python_heredoc_bodies` | verbatim |
| 154-183 | `_mask_shell_quoted_strings` | verbatim |
| 186-201 | `_python_c_sources` | verbatim |
| 204-214 | `_python_sources` | verbatim |
| 217-235 | `_python_tokens` | verbatim |
| 238-247 | `_finding` | verbatim |
| 250-264 | `_scan_python_source` | verbatim |
| 267-278 | `_scan_command` | verbatim |
| 281-302 | `_scan_event` | verbatim |
| 305-328 | `_scan_jsonl` | verbatim |
| 331-381 | `_coverage_findings` | verbatim |
| 384-409 | `_root_timed_out`, `_attempt_timeout_roots`, `_attempt_timed_out` | verbatim |
| 412-425 | `_frontmatter_status` | verbatim |
| 428-489 | `_attempt_completion_findings` | verbatim |
| 492-499 | `decide_status` | verbatim |
| 502-540 | `scan_attempt` | verbatim |
| 543-561 | `render_markdown` | verbatim |

**Steps:**
- [ ] Create `src/razorback/audit/__init__.py` with the 2-line ABOUTME header per CLAUDE.md: `# ABOUTME: Post-hoc trajectory taint scanner (rk audit, spec §3.2 + §9.4 Layer 3).` + `# ABOUTME: Ports dataagentbench's benchmark/lib/taint.py + benchmark/lib/subagent_traces.py (read-side).`
- [ ] Create `src/razorback/audit/taint.py`. Prepend a 6-line header:
  - Line 1: `# ABOUTME: Port of dataagentbench/benchmark/lib/taint.py (verbatim, 2026-05-20).`
  - Line 2: `# ABOUTME: Layer 3 of the leak-protection stack (spec §9.4); driven by rk audit (§3.2).`
  - Lines 4-7: Module-level docstring naming the source path verbatim: `"""Port of dataagentbench/benchmark/lib/taint.py.\n\nSource: /Users/clkao/git/dataagentbench/benchmark/lib/taint.py (561 LoC, ported 2026-05-20).\nUpstream behavior preserved verbatim; only the import path to subagent_traces is re-pointed.\n"""`
- [ ] Copy lines 1-561 of the source verbatim into the body below the header. The ONLY edit is line 8: replace `from benchmark.lib import subagent_traces` with `from razorback.audit import subagent_traces`.
- [ ] Run `diff <(tail -n +7 src/razorback/audit/taint.py) /Users/clkao/git/dataagentbench/benchmark/lib/taint.py` and confirm the only diff is the import line (one-line diff at line 8 of source).

**Validation:** `python -c "from razorback.audit import taint; assert callable(taint.scan_attempt)"`. The KEEP-VERBATIM tests in Task 5 are the real validation.

---

## Task 3 — Partial port of `subagent_traces.py` to `src/razorback/audit/subagent_traces.py` (read-side surface only)

**Files:**
- Create: `src/razorback/audit/subagent_traces.py`

**Why:** `taint.py` imports `subagent_traces.iter_trace_roots`, `subagent_traces.parent_has_completed_spawns`, and `subagent_traces.hook_reconciliation_issues`. Without these, `taint.py` cannot import. The full 870-LoC source carries capture-side helpers (`prepare_codex_spacedock_trace_capture`, `materialize_hook_traces`, `write_trace_manifest`) that razorback's post-hoc audit does not invoke — the audit reads pre-existing manifests written by Phase 3's spacedock-solver runtime. We port only the read-side surface plus its transitive helper closure.

**Source mapping (file:line in `/Users/clkao/git/dataagentbench/benchmark/lib/subagent_traces.py` → target):**

| Source lines | Symbol(s) | Status |
|---|---|---|
| 1-8 (imports + module-level) | stdlib | verbatim |
| 21-26 | `TraceCaptureConfig` dataclass | **DROP** — capture-side only, unused by `taint.py`. |
| 42-56 `_codex_trace_paths` | capture-side path resolver | **DROP** |
| 56-87 `prepare_codex_spacedock_trace_capture` | capture-side | **DROP** |
| 90-103 `_read_jsonl` | helper used by `materialize_hook_traces` + read-side; check usage in `parent_has_completed_spawns` / `iter_trace_roots` / `hook_reconciliation_issues`. PORT if any read-side caller transitively depends. |
| 105-175 `_hook_event_to_trace_events` | capture-side | **DROP** (verify no read-side caller) |
| 176-201 `_hook_tool_item` | capture-side | **DROP** |
| 202-245 `materialize_hook_traces` | capture-side | **DROP** |
| 246-256 `sha256_file` | capture-side | **DROP** (verify no read-side caller) |
| 257-275 `_collab_item`, `_stage_from_prompt` | helpers for `parse_parent_lifecycle` | **PORT** (read-side transitive dep) |
| 276-316 `parse_parent_lifecycle` | read-side | **PORT** if `parent_has_completed_spawns` calls it; otherwise drop. |
| 317-325 `parent_has_completed_spawns` | **read-side, used by `taint.py:53`** | **PORT verbatim** |
| 326-360 `_under_ignored_trace_root`, `iter_trace_roots` | **read-side, used by `taint.py:37`** | **PORT verbatim** |
| 361-368 `first_thread_id` | possibly read-side | **PORT if `hook_reconciliation_issues` calls it** |
| 369-411 `_trace_stats` | read-side helper | **PORT if `hook_reconciliation_issues` calls it** |
| 413-453 `_trace_files_by_thread`, `_hook_stage_by_thread`, `_hook_event_counts` | read-side helpers | **PORT if `hook_reconciliation_issues` calls them** |
| 454-500 `hook_reconciliation_issues` | **read-side, used by `taint.py:350`** | **PORT verbatim** |
| 501-660 `_entry_for_trace`, `reconcile_traces` | capture-side (manifest writing) | **DROP** |
| 661-676 `coverage_missing_reason` | possibly read-side | inspect: PORT if `hook_reconciliation_issues` or any other read-side helper calls it; otherwise DROP. |
| 677-825 `write_trace_manifest`, `read_trace_coverage`, `combine_coverage_statuses`, `read_trace_coverage_recursive` | mixed | inspect each: PORT read-side (`read_trace_coverage`, `combine_coverage_statuses`, `read_trace_coverage_recursive`) only if `taint.py` invokes them (it does not — but verify by `grep -n "subagent_traces\." /Users/clkao/git/dataagentbench/benchmark/lib/taint.py`). The `write_*` helpers stay DROPPED. |

**Steps:**
- [ ] Build the read-side closure: `grep -n "subagent_traces\." /Users/clkao/git/dataagentbench/benchmark/lib/taint.py` yields the entry points (`iter_trace_roots`, `parent_has_completed_spawns`, `hook_reconciliation_issues`).
- [ ] For each entry point, trace its transitive callees inside `subagent_traces.py` (e.g., `hook_reconciliation_issues` calls `_hook_stage_by_thread` and `_hook_event_counts` and `_trace_files_by_thread`).
- [ ] Port the closure verbatim into `src/razorback/audit/subagent_traces.py`. Prepend a header identical in shape to Task 2's: `# ABOUTME: Port of dataagentbench/benchmark/lib/subagent_traces.py (read-side closure, 2026-05-20).` + a module-level docstring naming the source path + listing the ported / dropped symbols.
- [ ] Exclude all capture-side symbols (`TraceCaptureConfig`, `prepare_codex_spacedock_trace_capture`, `_codex_trace_paths`, `_hook_event_to_trace_events`, `_hook_tool_item`, `materialize_hook_traces`, `_entry_for_trace`, `reconcile_traces`, `write_trace_manifest`). The module-level docstring lists them under "## Dropped (capture-side, lives in the runtime, not razorback's audit)".
- [ ] Verify the port imports cleanly: `python -c "from razorback.audit import subagent_traces; assert callable(subagent_traces.iter_trace_roots) and callable(subagent_traces.parent_has_completed_spawns) and callable(subagent_traces.hook_reconciliation_issues)"`.

**Validation:** Task 2's `taint.py` port must import cleanly atop this module: `python -c "from razorback.audit import taint, subagent_traces; taint.scan_attempt"`. The KEEP-VERBATIM tests in Task 5 exercise the joint surface.

**Risk:** Closure-determination errors. Mitigation: when in doubt, port a borderline helper rather than drop it. The cost of an unused helper is 30 LoC; the cost of a missing helper is an `AttributeError` at test time.

---

## Task 4 — Razorback CLI glue: `rk audit` Typer command + per-trial reducer + `--policy` → exit-code mapping

**Files:**
- Create: `src/razorback/audit/cli.py`
- Modify: `src/razorback/cli/__init__.py` (register the subcommand)

**Why:** AC-1, AC-4, AC-5. The port from Task 2 emits a run-level result (`scan_attempt` returns one dict with `status` + `findings`). The entity body specifies per-trial taint status (`clean` / `tainted` / `coverage_missing`). The glue layer:
1. Discovers per-trial subdirectories under the run-dir (one per `(task, query, trial_index)` per spec §7.1).
2. Calls `scan_attempt(trial_subdir, taint_policy="audit")` for each trial. (Default `taint_policy="audit"` is the upstream policy that ignores findings for status purposes; the per-trial classification comes from the `findings` shape, not `scan_attempt`'s own `status`.)
3. Reduces each trial's findings to one of `clean` / `tainted` / `coverage_missing` per the rule below.
4. Emits run-level JSON or markdown output per `--format`.
5. Maps `--policy strict` + any non-`clean` trial → raise `TaintFindingsError` (exit 23). `--policy audit` (default) → exit 0 regardless of findings (still emits the findings in the output).

**Per-trial reducer rule (derived from the upstream finding shape):**
- Any finding with `category in {"forbidden_lookup"}` → `tainted`.
- Else any finding with `category == "trace_coverage"` and `status in {"missing", "partial"}` → `coverage_missing`.
- Else any finding with `category == "attempt_incomplete"` (`status` in `{"timed_out", "non_terminal", "timed_out_non_terminal"}`) → `coverage_missing` (treat incomplete attempts as missing coverage rather than clean — the entity body's AC-4 invariant "silent absence of audit data must not be reported as a clean pass").
- Else any finding with `category == "scanner_error"` → `coverage_missing`.
- No findings → `clean`.

**Run-level JSON output shape:**
```json
{
  "schema_version": "rk-audit-v1",
  "run_dir": "<absolute path>",
  "policy": "audit",
  "trials": [
    {"trial_id": "<task>/<query>/trial-<N>", "trial_path": "<rel>", "taint_status": "clean|tainted|coverage_missing", "findings": [...]}
  ],
  "summary": {"clean": N, "tainted": N, "coverage_missing": N}
}
```

The `findings` per trial are the verbatim list from `scan_attempt`; razorback does not reshape them.

**Steps:**
- [ ] Create `src/razorback/audit/cli.py` with a Typer subcommand `audit(run_dir: Path, policy: str = "audit", format: str = "json")`.
- [ ] Discover trial subdirectories: enumerate harbor's run-dir layout per spec §7.1. The exact path shape (`<run-dir>/<task>/<query>/trial-<N>/` vs `<run-dir>/trials/<task>/<query>/<N>/`) depends on harbor's `run_dir` emit. Inspect a real bookreview run-dir from Phase 1's deterministic-smoke output (`/Users/clkao/git/razorback/runs/*` or wherever the Phase 1 walking-skeleton lands them) before hardcoding the glob. **Discovery rule:** a "trial root" is any directory containing one of `{codex-output.jsonl, claude-output.jsonl, traces/manifest.json}` per the upstream `discover_scan_inputs` semantics. Implementation: walk the run-dir; for each subdirectory that contains any of the three sentinel files, treat it as a trial root and call `scan_attempt(trial_root)`. (This avoids hardcoding harbor's path layout.)
- [ ] Apply the per-trial reducer rule above to each trial's `scan_attempt` output.
- [ ] Format output as JSON (default) or markdown (reuse `taint.render_markdown` per-trial, prefixed with the trial_id; run-level summary table at top).
- [ ] Policy mapping: at end of run, if `policy == "strict"` and any trial has `taint_status != "clean"`, `raise TaintFindingsError(...)`. Else exit 0. Wire the error → exit-code via the same pattern `cli/run.py` uses for `AliasDriftError` → exit 21.
- [ ] Register the subcommand in `src/razorback/cli/__init__.py` next to the existing `run`, `freeze`, `score` registrations.

**Validation:** Task 6's integration test against a fixture run-dir.

---

## Task 5 — KEEP-VERBATIM port of dataagentbench's `test_taint.py` test suite

**Files:**
- Create: `tests/unit/audit/__init__.py`
- Create: `tests/unit/audit/test_taint_keep_verbatim.py`

**Why:** AC-2 (pattern categories) + AC-3 (recursive subagent scan) + AC-4 (coverage-missing distinct from clean) all assert behaviors that dataagentbench's existing test suite already covers exhaustively. Per the test inventory's KEEP-VERBATIM rubric (`docs/superpowers/plans/2026-05-19-razorback-test-inventory.md` line 12: "KEEP-VERBATIM — survives unchanged in v2, only import paths may be re-pointed"), these tests port wholesale.

**Source:** `/Users/clkao/git/dataagentbench/benchmark/tests/test_taint.py` (409 LoC, 18 test functions). The functions cover:
- `test_prompt_and_command_output_mentions_do_not_taint_attempt` (false-positive guard — clean trajectory passes)
- `test_audit_regex_literals_do_not_taint_attempt` (false-positive guard)
- `test_malformed_python_heredoc_does_not_abort_scan` (robustness)
- `test_local_rg_audit_pattern_terms_do_not_taint_attempt` (false-positive guard)
- `test_subagent_only_forbidden_lookup_taints_attempt` (AC-3 recursive scan)
- `test_shell_install_or_download_commands_taint_attempt` (AC-2 shell pattern)
- `test_shell_download_command_still_taints_attempt` (AC-2 shell pattern)
- `test_web_search_tool_execution_taints_attempt` (AC-2 web-search pattern)
- `test_missing_subagent_trace_coverage_fails_under_fail_policy` (AC-4 coverage_missing)
- `test_partial_subagent_trace_coverage_is_reported_but_clean_under_audit` (AC-4 coverage)
- `test_stale_manifest_with_extra_hook_session_fails_under_fail_policy` (AC-4)
- `test_timed_out_*` + `test_nonterminal_*` (AC-4 attempt_incomplete)
- `test_fresh_nested_subagent_trace_forbidden_lookup_fails_top_level_attempt` (AC-3 recursive)
- `test_nested_subagent_trace_forbidden_lookup_taints_attempt` (AC-3 recursive)

**Steps:**
- [ ] Copy `/Users/clkao/git/dataagentbench/benchmark/tests/test_taint.py` verbatim into `tests/unit/audit/test_taint_keep_verbatim.py`.
- [ ] Prepend 2-line ABOUTME header: `# ABOUTME: KEEP-VERBATIM port of dataagentbench/benchmark/tests/test_taint.py.` + `# ABOUTME: Exercises the verbatim taint.py + subagent_traces.py port for AC-2/3/4.`
- [ ] Re-point the single import: replace `from benchmark.lib import taint` with `from razorback.audit import taint`.
- [ ] If any fixture builder in the test file imports `benchmark.lib.subagent_traces` directly, re-point to `razorback.audit.subagent_traces`.
- [ ] Run `uv run pytest tests/unit/audit/test_taint_keep_verbatim.py -x`. All 18 should pass green; any failure is a port defect (likely a missing helper from Task 3's closure determination, or an import-path mismatch). Fix by porting the missing helper, not by modifying the test.

**Validation:** `uv run pytest tests/unit/audit/test_taint_keep_verbatim.py -v` shows 18/18 pass.

**Anti-pattern guard:** Per CLAUDE.md "Never delete a test because it's failing." If a KEEP-VERBATIM test fails after re-pointing, the port is incomplete — re-trace Task 3's closure and add the missing helper. Do not modify the test body.

---

## Task 6 — Razorback integration test: `rk audit` against a fixture run-dir

**Files:**
- Create: `tests/fixtures/audit/runs/example-run/` (a synthesized run-dir; minimal three-trial fixture)
- Create: `tests/unit/audit/test_rk_audit_cli.py`

**Why:** AC-1 + AC-5. AC-1 requires the CLI to walk a run-dir's trial traces and emit per-trial taint status as JSON. AC-5 requires `--policy strict` → exit 23 vs `--policy audit` (default) → exit 0. The KEEP-VERBATIM tests in Task 5 exercise `taint.scan_attempt`'s behavior at the trial level; this integration test exercises the razorback CLI glue (Task 4).

**Fixture structure:**
```
tests/fixtures/audit/runs/example-run/
  task-a/query-1/trial-0/
    codex-output.jsonl              (one clean event — read-file tool, no forbidden patterns)
    traces/manifest.json            (capture_status: "complete", empty traces list)
  task-a/query-1/trial-1/
    codex-output.jsonl              (event with a "pip install datasets" Bash command_execution)
    traces/manifest.json            (capture_status: "complete", empty traces list)
  task-a/query-1/trial-2/
    codex-output.jsonl              (clean event)
    # traces/manifest.json deliberately absent → coverage_missing
```

The fixture files are minimal hand-rolled JSONL (the shape mirrors `test_taint.py`'s helper builders at lines 5-78; reuse those helpers to construct the fixture programmatically via a `conftest.py` builder rather than checking in raw JSONL — keeps the fixture readable).

**Steps:**
- [ ] Create `tests/unit/audit/conftest.py` with a `make_run_dir(tmp_path)` builder fixture that uses the same JSONL-builder helpers as `test_taint.py` (copy them; they are not the test functions themselves so not part of the KEEP-VERBATIM contract).
- [ ] Test: `test_rk_audit_emits_per_trial_status` — invokes the CLI via Typer's `CliRunner`, asserts the JSON output's `trials[].taint_status` is `["clean", "tainted", "coverage_missing"]` in trial order, and `summary == {"clean": 1, "tainted": 1, "coverage_missing": 1}`.
- [ ] Test: `test_rk_audit_policy_strict_exits_23` — same fixture, `--policy strict`, asserts `result.exit_code == 23` and JSON findings present.
- [ ] Test: `test_rk_audit_policy_audit_exits_0` — same fixture, default policy, asserts `result.exit_code == 0` and the same findings are reported.
- [ ] Test: `test_rk_audit_all_clean_exits_0_under_strict` — fixture with only the clean trial; `--policy strict` exits 0.

**Validation:** `uv run pytest tests/unit/audit/test_rk_audit_cli.py -v` shows 4/4 pass.

---

## Task 7 — Commit message attribution + grep proof of in-tree attribution

**Files:**
- Modify: `src/razorback/audit/taint.py` (verify the ABOUTME + docstring header from Task 2 cites `/Users/clkao/git/dataagentbench/benchmark/lib/taint.py`)
- Modify: `src/razorback/audit/subagent_traces.py` (verify the same attribution shape from Task 3)

**Why:** AC-6 verbatim: "`grep -n 'dataagentbench' src/razorback/audit/` returns the attribution; the commit's body cites the source." This task is the final attribution-check before the worktree commits.

**Steps:**
- [ ] `grep -rn "dataagentbench" src/razorback/audit/` returns at least 2 matches (one per ported file's ABOUTME + docstring).
- [ ] Commit message body for the Phase 4a worktree commit cites both source paths + line ranges + the port date: `Ports /Users/clkao/git/dataagentbench/benchmark/lib/taint.py (561 LoC, lines 1-561, 2026-05-20) and the read-side closure of /Users/clkao/git/dataagentbench/benchmark/lib/subagent_traces.py (lines 317-325 + 326-360 + 454-500 + transitive closure of helpers, 2026-05-20).`

**Validation:** `grep -n "dataagentbench" src/razorback/audit/taint.py src/razorback/audit/subagent_traces.py` returns >= 2 matches.

---

## Task 8 — `uv run pytest` green from worktree branch tip

**Files:**
- None (verification only).

**Why:** AC-7. Catches regressions in the wider razorback test suite from the CLI registration / errors-module touch.

**Steps:**
- [ ] `uv run pytest` from worktree root.
- [ ] If any test fails outside `tests/unit/audit/`, investigate (likely a CLI-registration import error or a Typer subcommand naming collision). Fix root cause, not by skipping the test.

**Validation:** `uv run pytest` exit 0 with the full count including the new audit suite. Capture the trial count in the stage report (e.g., "264 → 286 tests, all green").

---

## Acceptance verification recap

| Entity AC | Verified by |
|---|---|
| AC-1 (`rk audit` walks trial traces, per-trial status) | Task 6 (`test_rk_audit_emits_per_trial_status`) |
| AC-2 (pattern categories: shell, web-search, heredoc, python-c) | Task 5 (KEEP-VERBATIM tests cover all four) |
| AC-3 (recursive subagent trace scan) | Task 5 (`test_subagent_only_forbidden_lookup_taints_attempt`, `test_nested_*`) |
| AC-4 (`coverage_missing` distinct from `clean`) | Task 5 (`test_missing_subagent_trace_coverage_*`, `test_partial_*`) + Task 6 (`test_rk_audit_emits_per_trial_status` asserts `coverage_missing` ≠ `clean`) |
| AC-5 (`--policy strict` exits 23) | Task 6 (`test_rk_audit_policy_strict_exits_23` + `test_rk_audit_policy_audit_exits_0`) |
| AC-6 (attribution) | Task 7 (grep + commit message) |
| AC-7 (`uv run pytest` exit 0) | Task 8 |

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Closure-determination error in Task 3 (missing read-side helper from `subagent_traces.py`) | When in doubt, port; the cost of an unused helper is 30 LoC, the cost of a missing one is `AttributeError`. KEEP-VERBATIM tests (Task 5) catch this at the mechanism-check step before any razorback glue lands. |
| Harbor's run-dir trial-subdirectory layout differs from the fixture in Task 6 | Task 4's discovery rule walks by sentinel-file presence, not by hardcoded glob. The integration test against a real Phase 1 deterministic-smoke run-dir (Task 8 extension if needed) validates the discovery against actual harbor output. |
| Spec §3.2 / §3.4 / §9.4 wording changes during `ra` validation | This plan cites section identities, not exact wording. The port behavior is anchored to the source `taint.py`, not the spec wording. Commit attribution + ABOUTME comments use stable identities. |
| `errors.py` does not carry `TaintFindingsError` at worktree branch tip despite P1-T1 being marked completed | Task 1 verifies before Task 4 needs it. If absent, Task 1 adds it; this is a 5-LoC fix not a blocker. |

---

## Dependencies (recap from entity body)

- Entity body's "Depends on" lists `ra` spec-corrections-from-phase0-probes. The dependency is at spec-wording level only; this plan does not block on `ra`'s merge because the cited section identities are stable.
- The walking-skeleton run-dir from Phase 1 (deterministic-smoke) is the eventual real-data integration anchor. Task 8 may run `rk audit` against it once Phase 1 lands its smoke artifacts, but the synthesized fixture in Task 6 is the load-bearing AC-1 + AC-5 evidence.
