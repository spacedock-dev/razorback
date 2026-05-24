---
id: wpjrjfhkbp8zvqqpj83g9v5b
title: DAB spacedock — verify-stage adversarial trace audit (port upstream's External-oracle audit contract)
status: validation
source: 2026-05-23 7q validation cheating-audit finding — leak-guard prose alone is not enough; opus-4.7+xhigh may still attempt external lookups + admit them. DAB upstream's spacedock workflow (`~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` lines 128-135) includes an `External-oracle audit` step in the `verify` stage that scans the analyze-stage tool-use trace for matches against `huggingface`, `datasets.load_dataset`, `hf://`, `from datasets import`, `requests.get` to public data hosts, web-search invocations, or LLM-as-oracle patterns — and REJECTs with the offending event index. Razorback's spacedock `verify` stage (in `examples/solver_workflows/dab_paper_matrix/README.md`) has no such contract. Auto-approve: false because the workflow contract is captain-facing.
score: 0.9
auto-approve: false
worktree: .worktrees/spacedock-ensign-dab-verify-stage-external-oracle-audit
issue:
pr:
mod-block: 
started: 2026-05-23T22:58:25Z
completed:
verdict:
---

## Problem

The DAB spacedock `verify` stage in razorback today (`examples/solver_workflows/dab_paper_matrix/README.md`) says: "Re-read `query.json`. Confirm the candidate answer matches the question shape (single string). Write the final answer to `answers.json`. The verifier reads this file. Nothing else is graded." It performs NO adversarial audit of the analyze stage's tool-use trace.

DAB upstream's `verify` stage in `~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` (lines 117-135 verbatim) does TWO things:

1. **Adversarial re-derivation:** "Re-derive each answer independently, challenge intermediate assumptions, hunt for counterexamples, verify join correctness, test boundary conditions, and sanity-check magnitudes. If issues are found, REJECT with numbered findings; the workflow will feed back to `analyze`."

2. **External-oracle audit:** "Before passing, scan the analyze stage's tool-use trace (`claude-output.jsonl` events with `name: \"Bash\"` or `name: \"Read\"`) for evidence of forbidden external lookups: matches for `huggingface`, `datasets.load_dataset`, `hf://`, `from datasets import`, `requests.get` to public data hosts, web-search tool invocations, or LLM-call patterns asking another model for the answer. If any are found, REJECT with a finding pointing to the offending event index and the specific external source."

The External-oracle audit is the EXACT cheating audit our 7q validator just ran by captain directive. Upstream has it as a STRUCTURAL workflow contract; razorback has it as a one-off captain-directive that wouldn't fire without explicit captain intervention. This entity makes it durable workflow contract.

## Acceptance criteria

**AC-1 — Razorback's spacedock solver workflow README has the External-oracle audit contract.**
`examples/solver_workflows/dab_paper_matrix/README.md` `verify` stage section includes an "External-oracle audit" block that names the same forbidden patterns as upstream: `huggingface`, `datasets.load_dataset`, `hf://`, `from datasets import`, `requests.get` to public data hosts, web-search invocations, LLM-as-oracle patterns. The block specifies the audit MUST run before the verify stage passes, and any match triggers REJECT with the offending event index.
Verified by: `grep -F 'External-oracle audit' examples/solver_workflows/dab_paper_matrix/README.md` matches; `grep -F 'datasets.load_dataset\|huggingface\|hf://' examples/solver_workflows/dab_paper_matrix/README.md` matches all three.

**AC-2 — Razorback ships a `rk audit external-oracle` subcommand or library helper that mechanizes the verify-stage check.**
A consumer-facing helper that takes a run-dir path and scans the `claude-code.txt` trace for forbidden patterns; emits structured findings (event index, matched pattern, snippet ≤200 chars, severity). Cycle-1 shipped this as `src/razorback/agents/external_oracle_audit.py`; **cycle-2 SUPERSEDED that module** with an extension to the existing `src/razorback/audit/taint.py` plus a new claude-cli adapter at `src/razorback/audit/claude_code.py`. The captain-facing CLI is now `rk audit <cell-run-dir> --policy strict` (exit 0 clean / 23 tainted / other non-zero error). One canonical taint surface, two trace shapes (codex + claude-cli + harbor-codex).
Verified by: `uv run rk audit <real-agnews-cell-dir> --policy strict` returns exit 23 with claude_code_trace findings naming `from datasets import` and `load_dataset` at the agnews cheating lines; the same against the real bookreview cell returns exit 0.

**AC-3 — Solver-workflow verify stage prompt-level rule references the helper.**
The `verify` stage prose in `examples/solver_workflows/dab_paper_matrix/README.md` instructs the agent to invoke (or describes the harness invoking) the audit against its own run-dir as part of its self-audit, and REJECT if exit code is non-zero. Cycle-2 updated the prose to reference `rk audit --policy strict` (the cycle-1 prose referenced `python -m razorback.agents.external_oracle_audit`; SUPERSEDED).
Verified by: workflow README's verify section names `rk audit --policy strict` + the 0/23/other exit-code semantic.

**AC-4 — Per-cell post-run hook automation (defense in depth like ne's smoke gate).**
The matrix dispatcher (`examples/drivers/dab-paper-matrix.sh`) invokes the external-oracle audit as a per-cell gate after rk-run and before rk-score, for every variant (NOT variant-gated). A failing audit marks the cell `status: external-oracle-cheating` in `dispatch-ledger.tsv`. Cycle-2 changed the invocation from a separate `external_oracle_audit` module call to the canonical `rk audit --policy strict` (which now ALSO writes the per-cell `audit.json` artifact previously written by the post-gate rk audit invocation — folded into one call).
Verified by: integration tests at `tests/integration/test_dab_paper_matrix_external_oracle_gate.py` cover (a) hook ordering between rk run and rk score, (b) exit-23 → external-oracle-cheating mapping, (c) failing audit appends to FAILURES_LOG + decrements ok_cells, (d) synthetic cheating cell exits 23 end-to-end, (e) synthetic clean cell exits 0 end-to-end.

**AC-5 — Unit tests for the audit module.**
Cycle-1 shipped 7 fixtures at `tests/unit/test_external_oracle_audit.py` — SUPERSEDED; deleted in cycle-2 along with the module they tested. Cycle-2 substituted: 11 claude-cli adapter tests at `tests/unit/audit/test_claude_code_adapter.py` (load_dataset python heredoc, clean Bash, pip install rapidfuzz CLEAN, pip install datasets flagged, WebSearch tool_use flagged, curl huggingface flagged, tool_result-echo defense, missing trace, discover_trial_roots, rk audit strict end-to-end cheating + clean); 4 new captain-principle tests in `tests/unit/audit/test_taint_keep_verbatim.py` (generic-lib CLEAN, each named lib taints, version-pinned named lib taints, huggingface-cli taints).
Verified by: `uv run pytest tests/unit/audit/ -v` passes 46/46; `uv run pytest tests/integration/test_dab_paper_matrix_external_oracle_gate.py -v` passes 5/5.

## Test plan

- **Mechanism gate first (per CLAUDE.md):** run the new module against the existing agnews cell from 7q's run-dir. It MUST flag the `load_dataset` event with the right index + snippet, OR the module isn't fit for purpose.
- **Unit tests:** the four synthetic fixtures above (load_dataset, clean, requests.get, Python-import).
- **Dispatcher integration:** synthetic cell injection per AC-4.
- **Cross-cell:** re-run the audit against ALL 12 7q cells; verify clean cells PASS, agnews REJECTs, music_brainz_20k flags as suspected (pip install of generic lib).
- **Full pytest:** stays green.

## Out of scope

- **Workspace README leak-guard prose port.** Sibling entity `k34cqr2myjsh6aaqm6fhz5nw`. Deters at the prompt layer; this entity catches what slips past.
- **Network-layer block.** Sibling entity `wjfra5rje67399g6msza9zg6`. Hard guard regardless of prompt + trace.
- **Full upstream `taint.py` schema parity.** Upstream's `taint.json` carries `schema_version`, `policy_mode`, `categories` (public_egress + dynamic_install + answer_key_access), `confirmed_count`/`suspected_count`/`suppressed_count`, etc. This entity ships the MINIMUM external-oracle audit; full taint scanner is sibling entity `8yb8fzx5549j8q1w23c7xbr9`.
  *Cycle-2 update:* sibling entity `8y`'s "scanner port" half is now PARTIALLY SUPERSEDED by cycle-2's `audit/taint.py` extension (claude-cli adapter at `audit/claude_code.py` + pip-rule rebalance per captain principle). `8y`'s remaining scope: read-only rootfs + duckdb extension cache + the full taint.json schema fields above. Update `8y` entity body to reflect the narrower scope when it's resumed.
- **direct-minimal / direct-structured verify-stage audit.** Those variants don't have a verify stage today (no spacedock crew loop). This entity scopes to the spacedock solver workflow. Direct variants would need the audit run as a separate post-cell hook (which AC-4's dispatcher integration provides incidentally).
- **agnews-only re-run of 7q.** Same as the sibling leak-guard entity — file a follow-on 7q impl cycle after these ship.

## Depends on

- **`k34cqr2myjsh6aaqm6fhz5nw` dab-workspace-readme-leak-guard-prose-port** (sibling, parallel) — pure-prose deterrence + this entity's mechanical audit = defense in depth. Either can land first; both land together for the trustworthy 7q re-run.
- **`ne spacedock-solver-real-fo-dispatch-and-smoke-gate`** (in flight) — sets the pattern for "razorback agent module + dispatcher hook + manifest writer" that this entity's external-oracle audit mirrors. The smoke-gate writer at `src/razorback/agents/subagent_traces.py` and validator at `src/razorback/agents/subagent_smoke.py` are the design template for `src/razorback/agents/external_oracle_audit.py`.

## Resume hook

When this lands, the spacedock workflow can no longer be cheated by an agent that finds a way around the prompt rule. The audit fires at every cell. Failed cells are flagged in `dispatch-ledger.tsv` and the captain-facing aggregator. Combined with the workspace-README prose port (sibling `k3`), the leak-guard discipline reaches parity with DAB upstream's verify-stage contract.

## Stage Report: plan

- DONE: Plan-output flex: 5 ACs but multi-subsystem (workflow README + new src/razorback/agents/external_oracle_audit.py module + dispatcher hook + unit tests + cross-cell smoke). Recommend separate plan doc at `docs/razorback-implementation/plans/dab-verify-stage-external-oracle-audit.md`.
  Separate plan doc written at `docs/razorback-implementation/plans/dab-verify-stage-external-oracle-audit.md` with AC↔task map (AC-1..AC-5 → T0..T6), spec §-cites per task, six-task sequence.
- DONE: Mechanism validation — read DAB upstream's verify-stage prose at `~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` lines 117-135 verbatim. Also read razorback's existing module template: `src/razorback/agents/subagent_traces.py` + `src/razorback/agents/subagent_smoke.py` (just shipped via ne) — these are the design pattern for the new external_oracle_audit module. Confirm dab-paper-matrix.sh's smoke-gate hook pattern (commit 39847a5) is what the external-oracle audit hook mirrors. Then probe the existing agnews trace at `_runs/goal1-direct-structured-opus47-xhigh/direct-structured/agnews/.../steps/main/agent/claude-code.txt` to confirm the exact event-index/snippet shape the audit must recognize.
  Upstream lines 117-135 read verbatim; ne templates read from worktree (`subagent_traces.py` writer pattern + `subagent_smoke.py` 0/2/3 exit contract); dab-paper-matrix.sh lines 197-218 confirmed as the hook template; real agnews trace at `.worktrees/spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh/_runs/.../agnews__uR698Wh/steps/main/agent/claude-code.txt` probed — confirmed forbidden patterns at lines 26 (`from datasets import`), 30 (`curl huggingface.co`), 38 (`load_dataset("ag_news")`), 40 (`load_dataset("fancyzhx/ag_news")`), 45/48/53 (subsequent calls). Bookreview cell confirmed clean. Music_brainz_20k cell probed: only `pip install duckdb/rapidfuzz` matches, which is OUT OF SCOPE per upstream's verbatim pattern list — sibling taint-scanner entity `8y` handles that. Plan §Risk register explicitly fences the false-positive boundary.
- DONE: Sequence the impl-stage tasks. T0 mechanism gate: run a prototype `scan_attempt_external_oracle` against the real agnews trace; must emit the right finding before any production module lands. Then T1 RED unit tests (4 synthetic fixtures: load_dataset, clean, requests.get, python-import-only) → T2 GREEN module → T3 dispatcher hook + ledger row → T4 workspace solver README verify-stage prose addition → T5 cross-cell smoke against all 12 7q cells → T6 stage report.
  Plan §Task sequence enumerates T0 (mechanism gate against real agnews + bookreview traces, throwaway scratch_scan.py, must emit ≥6 findings on agnews and 0 on bookreview before T1), T1 (RED — 6 fixtures: A load_dataset+fancyzhx, B clean, C requests.get public host, D from-datasets-import heredoc, E WebSearch tool_use, F missing-trace), T2 (GREEN module + sidecar `external-oracle-audit.json` with schema `razorback-external-oracle-audit-v1`, exit contract 0/2/3 mirroring `subagent_smoke.py`), T3 (RED+GREEN dispatcher hook NOT variant-gated + integration test + aggregator passthrough check), T4 (workflow README verify-stage prose with AC-1/AC-3 grep verification), T5 (cross-cell smoke over all 12 cells), T6 (stage report).

### Summary

Wrote separate plan doc at `docs/razorback-implementation/plans/dab-verify-stage-external-oracle-audit.md` per the 5-AC multi-subsystem flex (workflow README + module + hook + tests + cross-cell smoke). Mechanism gate (T0) is sequenced first: prototype scan against the real on-disk agnews trace must emit findings at the line numbers confirmed by plan-stage probe (26/30/38/40/45/48/53) and bookreview must emit zero before T1 begins. Design mirrors the `ne` templates exactly — `_find_claude_code_txt` shape, 0/2/3 exit-code contract, sidecar manifest writer, dispatcher-hook block between rk-run and rk-audit — with the load-bearing difference that the audit hook is NOT variant-gated (fires for all 3 variants, not just spacedock). Out-of-scope boundary explicit: generic-lib `pip install` (music_brainz_20k case) is sibling-entity `8y`'s taint-scanner concern, not this audit's.

## Stage Report: implementation

- DONE: T0 mechanism gate — throwaway scratch_scan.py emitted 12 findings against real agnews trace covering all 7 expected lines (26/30/38/40/45/48/53), 0 against bookreview. Scratch deleted; git status clean.
- DONE: T1+T2 — AC-2 + AC-5. tests/unit/test_external_oracle_audit.py (7 fixtures: A load_dataset+fancyzhx, B clean Bash-only, C requests.get to raw.githubusercontent.com, D from-datasets-import heredoc, E WebSearch tool_use, F missing-trace, plus tool_result-echo defense). src/razorback/agents/external_oracle_audit.py module with 0/2/3 exit contract and razorback-external-oracle-audit-v1 sidecar schema.
  commit caeb7d6. uv run pytest tests/unit/test_external_oracle_audit.py: 7/7 PASS. Live AC-2 check: real agnews cell → exit 2 with `fancyzhx/ag_news` snippet + load_dataset pattern_id; real bookreview cell → exit 0.
- DONE: T3 — AC-4. examples/drivers/dab-paper-matrix.sh per-cell hook between rk-run and rk-audit (NOT variant-gated; fires for all 3 variants). rc==2 → status=external-oracle-cheating, decrement ok_cells, increment failed_cells, append to FAILURES_LOG, skip rk-audit/rk-score. rc==3 → status=external-oracle-audit-error. tests/integration/test_dab_paper_matrix_external_oracle_gate.py (5 tests: hook ordering, distinct statuses, FAILURES_LOG contract, synthetic cheating cell e2e, synthetic clean cell e2e). Aggregator passthrough: aggregate-goal1-scores.py reads result.json not ledger, so no aggregator edit needed — ledger is the captain's surface.
  commit 107401c. uv run pytest tests/integration/test_dab_paper_matrix_external_oracle_gate.py + tests/unit/test_dab_paper_matrix_driver_shape.py: 7/7 PASS. bash -n dispatcher: OK. dry-run still emits 36 cells.
- DONE: T4 — AC-1 + AC-3. examples/solver_workflows/dab_paper_matrix/README.md verify-stage section gained an External-oracle audit block naming the upstream forbidden patterns verbatim (huggingface, datasets.load_dataset, hf://, from datasets import, requests.get to 6 named public hosts, WebSearch/WebFetch, openai/anthropic/google.generativeai LLM oracles) and tied to the harness invocation `python -m razorback.agents.external_oracle_audit <cell-run-dir>` with the 0/2/3 exit-code contract.
  commit 54ef9f1. AC-1/AC-3 grep verification: all 9 required literals matched (External-oracle audit:1, datasets.load_dataset:1, huggingface:3, hf:///1, from datasets import:2, requests.get:1, web-search:1, LLM-call:1, python -m razorback.agents.external_oracle_audit:1).
- DONE: T5 — cross-cell smoke against all 12 7q direct-structured cells under .worktrees/spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh/_runs/goal1-direct-structured-opus47-xhigh/direct-structured/. Result table:

      cell             exit  confirmed  suspected
      agnews           2     12         0
      bookreview       0     0          0
      crmarenapro      0     0          0
      DEPS_DEV_V1      0     0          0
      GITHUB_REPOS     0     0          0
      googlelocal      0     0          0
      music_brainz_20k 0     0          0
      PANCANCER_ATLAS  0     0          0
      PATENTS          0     0          0
      stockindex       0     0          0
      stockmarket      0     0          0
      yelp             0     0          0

  agnews REJECTed exactly as the 7q validation report documented; music_brainz_20k stayed clean (pip install of generic-lib is OUT OF SCOPE per plan §Risk register — sibling entity 8y's taint scanner concern); all 10 remaining cells clean. No previously-undetected cheating surfaced. Full pytest: 647 passed, 12 skipped, 9 pre-existing failures (confirmed identical on sibling k3 worktree at same base 2abdd05; failures pre-date this work and are not caused by it). Pre-existing import error in tests/unit/test_task_identity_scoring.py (`razorback.score.load` missing) deselected.

### Summary

Shipped the verify-stage External-oracle audit contract in three layers — Python module (src/razorback/agents/external_oracle_audit.py with 0/2/3 exit codes + razorback-external-oracle-audit-v1 sidecar), dispatcher hook (dab-paper-matrix.sh, non-variant-gated, fires for all 3 variants between rk-run and rk-audit), and workflow README prose (mirrors DAB upstream verbatim + ties to the harness invocation). Cross-cell smoke verified the audit's calibration: agnews emits 12 confirmed findings across the 7 expected line numbers, all 11 other cells stay clean including music_brainz_20k's pip-install events (out-of-scope generic-lib install per plan). The ne smoke-gate templates (subagent_traces.py / subagent_smoke.py) referenced in the plan were design templates only — they have not merged to my branch's base (2abdd05), so the external-oracle audit ships standalone without depending on the smoke gate's presence in the dispatcher.

## Stage Report: implementation (cycle 2 — (b) extend audit/taint.py + Option A rewire)

- DONE: Extend `src/razorback/audit/taint.py` with claude-cli trace coverage.
  Added sibling adapter `src/razorback/audit/claude_code.py` (modeled on `audit/harbor_codex.py`) — `discover_trial_roots` finds `**/agent/claude-code.txt`; `scan_trial` parses `event.type == "assistant" → message.content[*].type == "tool_use"`, extracts `input.command` for Bash / `input.file_path` for Read, flags WebSearch/WebFetch tool_use directly, re-uses `taint._scan_command` for all pattern logic. Wired into `audit/cli.py`'s `_discover_trial_roots` + `_audit_run_dir`. The captain-facing API surface (`rk audit ... --policy strict`, exit 23 on findings) is unchanged.
- DONE: Rebalance the PyPI rule per captain principle.
  Replaced the upstream `pip install\b` regex in `audit/taint.py` `FORBIDDEN_SHELL_PATTERNS` with a named-libs alternation `(datasets|huggingface|huggingface_hub|transformers|evaluate)(\b|[*=<>~])`. Added `huggingface-cli|hf` binary as a separate forbidden-pattern. The named-lib list mirrors `razorback.agents.claude_invoke.DISALLOWED_TOOLS` so audit and runtime block-list stay consistent. Generic compute libraries (rapidfuzz, scikit-learn, duckdb, numpy, pandas) are now CLEAN — captain principle encoded.
- DONE: Tests cover both changes plus regression-guard the rebalance.
  46/46 audit tests pass (`tests/unit/audit/`). New test classes: captain-principle generic-lib CLEAN; each of the 5 named libs flagged; version-pinned named libs flagged; huggingface-cli flagged; claude-cli adapter end-to-end (load_dataset python heredoc, clean Bash, generic-lib pip CLEAN, named-lib pip flagged, WebSearch tool_use flagged, curl huggingface flagged, tool_result-echo defense, missing trace returns empty, discover_trial_roots, rk audit strict end-to-end cheating + clean). One existing verbatim-port test updated to assert the new captain-principle regex literal instead of the upstream-verbatim one (the actual behavior assertion — `pip install datasets` flagged — preserved).
- DONE: Empirically verified against real 7q cells.
  `rk audit --policy strict <real-agnews-cell>` returns exit 23 with claude_code_trace findings at lines 26 (`from datasets import`), 28+32+34 (`pip install datasets`), 30 (curl `huggingface.co`), 38/40/45/48/53 (`load_dataset`). All 7 plan-required line numbers covered. `rk audit --policy strict <real-bookreview-cell>` returns exit 0. `rk audit --policy strict <real-music_brainz_20k-cell>` returns exit 0 (pip install duckdb/rapidfuzz CLEAN per captain principle — would have been REJECTED under the upstream-verbatim regex).
- DONE: Discarded cycle-1's `src/razorback/agents/external_oracle_audit.py` (8KB) and its 7-fixture test file `tests/unit/test_external_oracle_audit.py`. `git rm` clean; no lingering imports anywhere in the tree (`grep -r razorback.agents.external_oracle_audit src/ tests/ examples/` returns nothing post-rewire).
- DONE: Rewired `examples/drivers/dab-paper-matrix.sh` per-cell hook.
  Folded the previously-separate gate call into the existing `rk audit` invocation (single per-cell audit run, not two). Exit 0 → continue to rk score; exit 23 → ledger status `external-oracle-cheating` + roll back from `ok_cells` to `failed_cells` + skip scoring + continue; any other non-zero → ledger status `external-oracle-audit-error` + same rollback. Hook remains NOT variant-gated; fires for all 3 variants. `bash -n` clean; `--dry-run` still emits 36 cells.
- DONE: Rewired `tests/integration/test_dab_paper_matrix_external_oracle_gate.py`. Same 5-test contract (hook ordering, exit-23 mapping, FAILURES_LOG, synthetic cheating cell e2e, synthetic clean cell e2e) but now invokes `rk audit --policy strict` through the typer CliRunner instead of the deleted module's subprocess invocation. 5/5 pass.
- DONE: Updated workflow README prose at `examples/solver_workflows/dab_paper_matrix/README.md`. Verify-stage External-oracle audit block now references `uv run rk audit <cell-run-dir> --policy strict --format json` and the 0/23/other exit-code semantic, with the named-lib list (datasets / huggingface_hub / transformers / evaluate) called out and the captain-principle (rapidfuzz, scikit-learn, duckdb, numpy, pandas CLEAN) made explicit. All upstream-verbatim forbidden patterns from cycle-1 preserved. AC-1/AC-3 grep verification: `External-oracle audit`:1, `datasets.load_dataset`:1, `huggingface`:3, `hf://`:1, `from datasets import`:2, `web-search`:1, `rk audit`:2, `--policy strict`:1.
- DONE: Cross-cell smoke against all 12 7q direct-structured cells under `_runs/goal1-direct-structured-opus47-xhigh/direct-structured/`. Result table:

      cell              exit  clean  tainted  top_finding
      agnews            23    0      1        from datasets impo[rt]
      bookreview        0     1      0        -
      crmarenapro       0     1      0        -
      DEPS_DEV_V1       0     1      0        -
      GITHUB_REPOS      0     1      0        -
      googlelocal       0     1      0        -
      music_brainz_20k  0     1      0        -
      PANCANCER_ATLAS   0     1      0        -
      PATENTS           0     1      0        -
      stockindex        0     1      0        -
      stockmarket       0     1      0        -
      yelp              0     1      0        -

  Exact match with cycle-1's cross-cell verdict — the rewire preserved correct behavior. agnews REJECTed; music_brainz_20k stayed CLEAN (validates captain principle); 10 other cells clean. No previously-undetected cheating surfaced.

- DONE: Full pytest: 655 passed, 12 skipped, 9 pre-existing failures (identical to cycle-1 and to sibling k3 worktree at the same base 2abdd05 — pre-date this work). Net delta vs cycle-1: +8 passing tests (deleted 7 cycle-1 unit + 5 cycle-1 integration; added 11 claude_code adapter + 4 captain-principle taint + 5 integration). One pre-existing import error at `tests/unit/test_task_identity_scoring.py` (`razorback.score.load` missing) deselected, same as cycle-1.

### Summary

Cycle-2 replaced cycle-1's parallel scanner module (`agents/external_oracle_audit.py`) with an extension to the existing `audit/taint.py` per captain Option-(b) decision. Two contract-changing edits: (1) added `audit/claude_code.py` adapter sibling to `audit/harbor_codex.py` that teaches taint to read the claude-cli `assistant.tool_use` event shape, fixing a previously silent-blindness bug — any `rk audit` invocation against claude-cli traces before this change silently reported CLEAN, including the agnews cheating cell; (2) rebalanced taint.py's `pip install` regex from "any package" to the four named canonical-data libraries (datasets/huggingface_hub/transformers/evaluate) plus huggingface-cli/hf binaries, mirroring `claude_invoke.DISALLOWED_TOOLS`, per the captain principle that generic compute libraries (rapidfuzz, scikit-learn, duckdb, numpy, pandas) are CLEAN.

Razorback now has ONE canonical taint surface (`rk audit --policy strict`) that handles codex + harbor-codex + claude-cli trace shapes uniformly. Razorback's `audit/taint.py` diverges from upstream `dab lib/taint.py` for the first time — worth a future captain decision on whether to upstream the changes (claude-cli support may help upstream too if they ever add a claude-cli runtime; the PyPI rebalance is razorback-specific policy and likely should stay forked). Sibling entity `8y dab-taint-scanner-and-readonly-rootfs-port`'s "scanner port" half is now partially SUPERSEDED — `8y` is updated in §Out of scope; remaining `8y` scope is read-only rootfs + duckdb extension cache + full taint.json schema fields.

The captain-facing implication for any prior `rk audit` invocation against claude-cli traces: those previously silently reported CLEAN; this fix changes that to correctly report TAINTED on cheating events. The 7q validation report's manual grep finding for agnews is now mechanically detectable.

## Stage Report: validation

- DONE: Reproduce each AC's `Verified by:` clause against the worktree branch.
  AC-1: README grep at `examples/solver_workflows/dab_paper_matrix/README.md` matches all required literals (External-oracle audit, datasets.load_dataset, huggingface, hf://, from datasets import, requests.get, WebSearch/WebFetch/web-search, --policy strict). AC-3: synthetic claude-trace cell → exit 23 (`test_rk_audit_strict_rejects_synthetic_cheating_cell`); synthetic clean cell → exit 0 (`test_rk_audit_strict_passes_synthetic_clean_cell`). AC-4: `dab-paper-matrix.sh` lines 186-219 invoke `rk audit --policy strict` between rk-run and rk-score, non-variant-gated, exit-23 → ledger `external-oracle-cheating` + ok_cells rollback + FAILURES_LOG append; 3 dispatcher-shape tests + 2 e2e tests all PASS. AC-5: 11 claude_code adapter tests + 4 captain-principle taint tests covering load_dataset/clean/requests.get/from-datasets-import/WebSearch/curl-huggingface/named-lib-pip/generic-lib-pip-CLEAN/tool_result-defense/missing-trace/discover_trial_roots/rk-audit-strict-e2e — all 51 PASS in 1.10s.
- DONE: Empirically verify silent-blindness fix end-to-end against real 7q cells.
  Real agnews cell (`.worktrees/spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh/_runs/.../agnews/.../2fa90bb140485d77`) → exit 23, finding at trace line 26 with pattern `from datasets import` and event_id `toolu_01PoLakXsdsXDY6GEHNS1FWe`. Real music_brainz_20k cell → exit 0 (1 clean trial; validates the captain-principle PyPI regex rebalance). Outputs captured at `/tmp/wp-validation-agnews-audit.json` and `/tmp/wp-validation-mbr-audit.json`.
- DONE: Run `uv run pytest` full suite + baseline comparison.
  Worktree branch: 655 passed / 12 skipped / 9 failed in 48.39s (identical to ensign's claim). Each of the 9 failing test files has empty `git log 2abdd05..HEAD` — they are pre-existing on the worktree's base (`2abdd05`) and not touched by wp's diff. The one collection error (`tests/unit/test_task_identity_scoring.py` imports missing `razorback.score.load`) is the same pre-existing import error documented in the implementation report; ignored via `--ignore=...`. Net delta vs cycle-1: +20 new passing tests added, 12 superseded tests removed = +8 net, matching the ensign's claim.
- DONE: Run code review against the worktree branch.
  No `Task` / general-purpose Agent dispatch tool is exposed to this validator (team-lead handles dispatching). I performed the review directly using the `superpowers:requesting-code-review` template against every changed file in `2abdd05..HEAD`. Findings classified by severity: 0 Critical, 0 Important, 4 Minor (none blocking). Findings cover: (a) divergence well-documented in three places (taint.py docstring, commit `d9326f1` body, entity body); (b) `claude_code.py` structurally mirrors `harbor_codex.py` sibling correctly; (c) test coverage is dense — 11 adapter + 4 regression + 5 integration; (d) regex/parsing safe — attempted adversarial flag interleaving against the captain-principle pip-install pattern; no evasion found. Full review at `docs/razorback-implementation/validation/dab-verify-stage-external-oracle-audit.md`.
- DONE: Write validation report at `docs/razorback-implementation/validation/dab-verify-stage-external-oracle-audit.md`.
  Per-AC verdict (5/5 PASS), silent-blindness reproduction, full pytest output, code review findings, gate decision (APPROVE). Captain-attention note flagged: the dispatch prompt's claim that "wp's frontmatter does NOT carry `auto-approve: false`" is incorrect — the entity's frontmatter line 7 IS `auto-approve: false`. Per validation-stage discipline, auto-merge should NOT happen automatically; captain (or FO with captain ack) should review before no-ff merge + archive.

### Summary

All 5 AC clauses reproduce on the worktree branch with exact-match evidence captured in the per-AC section of the validation report. The contract change (`audit/taint.py` PyPI rebalance + new `audit/claude_code.py` claude-cli adapter) is documented in three places (module docstring, cycle-2 commit body, entity body), structurally consistent with the existing `audit/harbor_codex.py` sibling, and end-to-end verified against real 7q cells: agnews now correctly exits 23 (was silently CLEAN before fix) and music_brainz_20k stays CLEAN under the rebalance (would have been REJECTed under the upstream-verbatim regex). 51/51 owned tests pass; 9 full-suite failures confirmed pre-existing via `git log 2abdd05..HEAD` per file. Gate decision: APPROVE with one captain-attention note — the dispatch's claim about `auto-approve` was wrong; the entity IS opted out, so auto-mod-block + auto-merge should not fire here without captain sign-off.
