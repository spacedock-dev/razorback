---
id: gvqgfh0f6hw8mttm9ryqkvpq
title: rk audit scanner walks subagent JSONL traces (spacedock-variant coverage gap)
status: backlog
source: 2026-05-25 captain audit probe on archived d8 spacedock matrix. `src/razorback/audit/claude_code.py:_trace_sources` (wp's ship) globs only `**/agent/claude-code.txt` — discovers the OUTER claude session's event log, parses it as JSONL via `_scan_jsonl`. For claude-cli runs the outer log is the complete tool-call trace; for spacedock_solver runs the outer log is mostly dispatch metadata and the actual Bash/file/network tool calls happen inside subagent claude sessions whose traces land at `**/agent/sessions/projects/*/{uuid}.jsonl`. The discovery glob does not walk into that subtree. Concrete contamination case found on d8: spacedock/agnews trial at `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/agnews/.../agnews__JM7sQoz/steps/main/agent/sessions/projects/-workspace/2d6c4860-be41-4ba3-a161-364546e1331e.jsonl:76,80` shows two consecutive Bash tool_use invocations of `python3 -c "from datasets import load_dataset; ds = load_dataset('ag_news'); ..."` — the canonical post-7q-finding cheating pattern. Both attempts failed at the network layer (HF Hub unreachable), so the score wasn't compromised, but the AUDIT VERDICT IS WRONG: d8's `audit.json` for that trial reports `clean: 1, tainted: 0` because the scanner never opened the subagent JSONL. wp's `_scan_jsonl` function is structurally capable of parsing these traces (it already handles JSONL); the gap is purely in trace discovery.
score: 0.88
auto-approve: false
worktree:
issue:
pr:
mod-block:
started:
completed:
verdict:
---

## Problem

`rk audit --policy strict` returns false-clean verdicts on every
spacedock-variant run because its trace-discovery only walks
`**/agent/claude-code.txt` (the outer claude session's event log).
For `agent.kind: spacedock_solver` runs:

- Outer claude session = the spacedock_solver wrapper that invokes
  `--agent spacedock:first-officer` and waits.
- Inner subagent sessions (the first-officer + ensigns) = where the
  actual Bash/file/network tool calls happen. Their event logs land
  at `agent/sessions/projects/<project>/<uuid>.jsonl` in JSONL form
  (one event per line, same shape as the outer claude-code.txt).

The audit scanner reads the outer claude-code.txt and reports
`clean` because no cheating-shape tool calls exist there — by
construction, the outer session doesn't execute Bash; it dispatches.
Any cheating that happens inside a subagent slips through.

Concrete reproduction in archived d8: spacedock/agnews trial's
subagent JSONL contains a Bash tool_use of
`python3 -c "from datasets import load_dataset; ds = load_dataset('ag_news')"`
(toolu_id `01AW64HCFx5hKhyc3ZCPbUJa` at line 76 of the JSONL).
A second attempt explicitly unsets HF offline env vars
(toolu_id `01HD9mZdy47kRoa1ZfDE23Zf` at line 80) — escalation
behavior the leak-guard prose would have caught at the deterrence
layer. Both attempts failed at the network layer (HF Hub
unreachable in the container), so d8's agnews score is uncompromised,
but the audit verdict `clean: 1, tainted: 0` is structurally false.

For claude-cli runs (e.g., 7q post-redo), this gap doesn't fire —
the outer claude-cli session is also where tool calls live. The
coverage gap is specific to multi-agent dispatch shapes.

## Acceptance criteria

**AC-1 — `_trace_sources` discovers subagent JSONL traces.**
The function `src/razorback/audit/claude_code.py:_trace_sources(trial_root)`
returns an iterator that includes both:
- Outer claude-code.txt: `**/agent/claude-code.txt` (existing behavior)
- Subagent JSONL: `**/agent/sessions/projects/*/*.jsonl`

Verified by:
- `grep -n "sessions/projects" src/razorback/audit/claude_code.py` returns ≥1 match in `_trace_sources` or a sibling discovery function it composes.
- A unit test `tests/unit/audit/test_trace_sources_subagent_jsonl.py` (or extension of an existing audit test) asserts that given a fixture trial root with both an outer `claude-code.txt` and a subagent JSONL at `agent/sessions/projects/-workspace/abc.jsonl`, `_trace_sources` returns both paths.

**AC-2 — Audit detects the d8 agnews cheating pattern when scanner sees subagent JSONL.**
Re-running `rk audit --policy strict` against the d8 agnews trial
root (or a fixture-copy of its JSONL) after the fix produces a
`tainted` verdict citing the `load_dataset` tool_use in the
subagent trace.
Verified by:
- A unit test fixture in `tests/fixtures/audit/d8-agnews-subagent.jsonl` (or test fixtures dir convention) carrying the load_dataset Bash tool_use captured from d8.
- `tests/unit/audit/test_scan_subagent_jsonl_detects_load_dataset.py` asserts `_scan_jsonl(fixture)` returns ≥1 finding with `category` matching the load_dataset / datasets-import pattern; and `scan_trial(trial_root)` rolls that into a `tainted` taint_status.

**AC-3 — Existing audit behavior preserved for claude-cli single-session shape.**
The fix is purely additive — outer claude-code.txt scanning continues unchanged for runs that have no subagent JSONL.
Verified by:
- Existing audit tests (whichever cover claude-cli single-session scans) pass without modification.
- `rk audit --policy strict` on a 7q-shape trial root (claude-cli, no subagents) produces the same finding set as pre-fix (`clean` if it was clean, same `tainted` evidence if it wasn't).

**AC-4 — d8 re-scan surfaces the actual contamination picture.**
After the fix lands, re-scan all 12 d8 spacedock cells (16 trials including cycle1 retries) and emit a captain-facing summary citing per-cell `taint_status` + the specific cheating-pattern Bash invocations found.
Verified by:
- A re-scan script or manual invocation produces `taint_status` per trial in the d8 run-dir at `_runs/goal1-rerun-spacedock-opus47-xhigh/`.
- Summary cited in stage report: total trials with `tainted` verdict, breakdown by pattern (load_dataset, huggingface_hub, kaggle, web-fetch, etc.). This informs whether d8 needs a full rerun (substantive cheating that affected scores) or just a documented amendment (attempts that failed at network layer, like agnews).

**AC-5 — Existing pytest stays green; failure set byte-identical to baseline `main`.**
Verified by: `uv run pytest tests/` exits 0 modulo pre-existing failures; failure set unchanged.

## Test plan

- **Mechanism check first:** read `src/razorback/audit/claude_code.py` end-to-end; confirm `_scan_jsonl` is already JSONL-aware and the only change needed is `_trace_sources`. Spot-check by manually running `_scan_jsonl(d8-agnews-subagent-jsonl-path)` in a Python shell and confirming it returns ≥1 finding.
- **RED test first** for AC-1 (discovery returns subagent JSONL) and AC-2 (scan_trial fires on subagent cheating). Both should fail on baseline `main`.
- **GREEN implementation:** extend `_trace_sources` discovery list. Single-file edit, additive.
- **Regression sweep:** AC-3 — existing claude-cli single-session tests stay GREEN.
- **Operational verification (AC-4):** re-scan d8 in-place; emit the contamination summary.

## Out of scope

- **Rerunning d8 spacedock matrix.** Captain decision 2026-05-25: file the
  scanner fix first; only redo d8 if the re-scan surfaces substantive
  contamination (cells where cheating SUCCEEDED, not just attempted).
  d8 rerun would be a separate entity if the re-scan motivates it.
- **Extending the scanner to other multi-agent dispatch shapes (codex
  subagents).** Codex uses a different sessions layout; if codex
  subagents ever need scanning, file a sibling at that time. This
  entity is scoped to the claude-multi-agent path that spacedock_solver
  uses today.
- **Backporting the scanner fix to the audit.json files already
  written.** Re-scanning d8's existing JSONLs is in AC-4's scope, but
  rewriting d8's archived `audit.json` files is out of scope —
  archived artifacts stay as-is; the re-scan produces a NEW
  contamination summary instead.

## Depends on

- (none — wp's `_scan_jsonl` already does the heavy lifting; this is
  a 1-line discovery extension + tests)

## Resume hook

When this lands, every future spacedock-variant run gets honest
audit coverage. d8's contamination picture becomes fully known
via the AC-4 re-scan, informing whether a d8 redo is warranted.
Future entities running spacedock_solver agents — including any
post-d8 paper-comparable spacedock matrices — get structurally
complete audit verdicts without manual subagent grep.

`auto-approve: false` because audit policy is captain-facing
research-integrity surface — a false-clean verdict on a published
headline is research misconduct in the limit.
