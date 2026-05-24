# DAB spacedock — verify-stage External-oracle audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/dab-verify-stage-external-oracle-audit.md`

**Goal:** Port DAB upstream's verify-stage "External-oracle audit" contract (`~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` lines 128-135) into razorback as a durable workflow + module pair. Today the cheating audit fires only on captain directive (the 7q validation cycle on 2026-05-23 used a one-off grep). After this lands, every spacedock-variant cell — and incidentally every direct-variant cell run through `dab-paper-matrix.sh` — is gated by a mechanical audit that REJECTs on any match against the upstream forbidden-pattern list with the offending claude-code.txt event index in the finding.

**Tech stack:** Python 3.12, pytest, bash. New module at `src/razorback/agents/external_oracle_audit.py` mirrors the design of `subagent_traces.py` + `subagent_smoke.py` (commits `554bf0b`/`39847a5` on the `ne` branch). Dispatcher hook mirrors lines 197-218 of `examples/drivers/dab-paper-matrix.sh` on the same branch. Workflow README prose addition at `examples/solver_workflows/dab_paper_matrix/README.md`.

---

## AC ↔ Task map

| AC | Description | Tasks |
|---|---|---|
| AC-1 | `examples/solver_workflows/dab_paper_matrix/README.md` `verify` stage section includes an "External-oracle audit" block naming the upstream forbidden patterns (`huggingface`, `datasets.load_dataset`, `hf://`, `from datasets import`, `requests.get` to public data hosts, web-search invocations, LLM-as-oracle patterns) and the REJECT-with-event-index requirement | T4 (workflow README prose insert) |
| AC-2 | `python -m razorback.agents.external_oracle_audit <cell-dir>` returns exit 2 on real agnews cell with `load_dataset` event index + `fancyzhx/ag_news` snippet; exit 0 on real bookreview cell; lives at `src/razorback/agents/external_oracle_audit.py` sibling to `subagent_traces.py`/`subagent_smoke.py` | T1 (RED unit), T2 (GREEN module), and T0 (mechanism gate on real agnews trace BEFORE production module lands) |
| AC-3 | Verify-stage prose in solver workflow README names `python -m razorback.agents.external_oracle_audit` invocation + non-zero exit → REJECT semantic, mirroring DAB upstream's tie between prose audit + concrete check | T4 (workflow README prose, same edit as AC-1) |
| AC-4 | `examples/drivers/dab-paper-matrix.sh` post-cell hook (between rk-run and rk-audit) invokes the audit; failing audit marks ledger row `status: external-oracle-cheating`; aggregator surfaces it; synthetic `load_dataset` cell triggers `external-oracle-cheating`, clean cell stays `ok` | T3 (RED bash-integration synthetic-cell test), T3 GREEN (dispatcher hook + aggregator passthrough check) |
| AC-5 | `tests/unit/test_external_oracle_audit.py` covers 4 synthetic fixtures: `load_dataset('fancyzhx/ag_news')` event → REJECT, clean Bash-only → PASS, `requests.get('https://raw.githubusercontent.com/...')` → REJECT, `from datasets import load_dataset` Python import → REJECT | T1 (RED), T2 (GREEN); pytest run as part of T5 |

**Riskiest contract first (the mechanism gate, per CLAUDE.md):**
> "A prototype `scan_attempt_external_oracle(<real agnews cell-dir>)` returns at least one finding whose `event_index` points at the `load_dataset` Bash command on line 38 of that trace and whose `snippet` contains the string `fancyzhx/ag_news`."

If a prototype scanner against the real trace doesn't fire on the obvious cheating event, the regex shape / extraction shape is wrong and the production module is built on a false premise. T0 is sequenced as the FIRST implementation task; everything past T0 inherits its verdict.

---

## Mechanism check — T0 of implementation stage

The captain has the real agnews cheating trace on disk (no synthetic substitution allowed — `_runs/.../agnews/.../steps/main/agent/claude-code.txt` exists in the goal1-direct-structured worktree). T0 is the smallest end-to-end exercise of the riskiest contract:

1. Stand up a throwaway `scratch_scan.py` at the repo root (NOT committed) that:
   - Reads the JSONL claude-code.txt file line-by-line.
   - For each `assistant`-type event with a `tool_use` content-block whose `name == "Bash"`, extracts `input.command`.
   - Runs each upstream forbidden-pattern regex against the command. Initial patterns from DAB upstream lines 128-135 verbatim:
     - `huggingface` (case-insensitive substring; covers `huggingface.co`, `huggingface_hub`)
     - `datasets\.load_dataset` (covers `datasets.load_dataset("...")`)
     - `hf://` (HF URI scheme)
     - `from\s+datasets\s+import` (Python-import-layer attack — the exact form agnews used)
     - `load_dataset\s*\(` (broader catch — covers the bare `load_dataset(...)` after `from datasets import load_dataset`)
     - `requests\.get\s*\(\s*['"]https?://` (requests.get to a URL literal; severity refines per public-host check)
     - `WebSearch` / `WebFetch` (claude-cli web-tool names; tool_use `name` not just command substring — see T2 design)
   - Emits per-finding `{event_index, line_number, pattern, snippet[:200]}` to stdout.

2. Run against the real agnews trace:
   ```bash
   python scratch_scan.py \
       .worktrees/spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh/_runs/goal1-direct-structured-opus47-xhigh/direct-structured/agnews/goal1-direct-structured-agnews/2fa90bb140485d77/agnews__uR698Wh/steps/main/agent/claude-code.txt
   ```

3. **Verdict (must emit ≥3 findings: `from datasets import` at line 26, `load_dataset("ag_news")` at line 38, `load_dataset("fancyzhx/ag_news")` at line 40, plus the `huggingface.co` `curl` at line 30):** GREEN → patterns are calibrated; proceed to T1.
   **Verdict (zero findings):** regex shape / extraction shape is wrong — re-read the JSONL events and adjust. Do NOT proceed to T2.
   **Verdict (false positives, e.g., pattern matches in a `tool_result` echo rather than the original `tool_use.input.command`):** narrow the extraction to ONLY `type==assistant → message.content[*] → type==tool_use → input.command` (NOT `tool_result.content`). This is a load-bearing distinction — `tool_result` events echo the command back, but the OFFENSE is in the assistant's `tool_use`, not in the user-role echo.

4. Run against the real bookreview cell at `_runs/.../direct-structured/bookreview/.../claude-code.txt` — must emit ZERO findings (bookreview is the canonical "clean variant" per the entity body + the 7q validation report).

5. Delete `scratch_scan.py`. T1 builds the production tests + module from the verified pattern set.

**Why T0 belongs in implementation stage (not plan stage):** the plan-stage worker has already confirmed by direct file inspection (see `grep` output in dispatch context) that the agnews trace contains the expected forbidden patterns at the expected line numbers. T0 in implementation stage validates that a PROGRAMMATIC scan emits the same findings — which is the actual mechanism the production module must satisfy. Plan-stage workers don't write production code; T0 is the smallest production-shaped exercise.

---

## Surface map — what changes

| File | Change |
|---|---|
| `src/razorback/agents/external_oracle_audit.py` *(new)* | Per-cell external-oracle-audit module. Reads `claude-code.txt` (locate via the same `_find_claude_code_txt(cell_dir)` shape as `subagent_traces.py`: prefer `cell_dir/steps/main/agent/claude-code.txt`, fall back to `rglob`). Parses JSONL line-by-line. For each `assistant` event, walks `message.content[*]` looking for `tool_use` blocks. For each `tool_use` block: (a) if `name in {"Bash", "Read"}`, scan `input.command` (or `input.file_path` for Read) against the upstream forbidden-pattern set; (b) if `name in {"WebSearch", "WebFetch"}`, emit a finding directly (the tool name itself is the offense). Emits a finding dict `{event_index, line_number, pattern_id, pattern_label, severity, snippet}` per match. `severity` is `"confirmed"` for direct hits (`load_dataset`, `hf://`, web tools) and `"suspected"` for ambiguous ones (`requests.get` to non-data-host URLs). CLI entrypoint: `python -m razorback.agents.external_oracle_audit <cell-dir>` exits **0** if zero confirmed findings, **2** if ≥1 confirmed finding (with a stderr message `external-oracle-cheating: {n} confirmed findings`), **3** if `claude-code.txt` cannot be located or parsed (with stderr `trace-missing: {path}`). Also writes a sidecar `external-oracle-audit.json` adjacent to `subagent-trace-manifest.json` with schema `razorback-external-oracle-audit-v1` and the full findings list, so the aggregator can render per-cell offending event indices without re-running the scan. The exit-code contract (0/2/3) mirrors `subagent_smoke.py`'s contract verbatim. |
| `tests/unit/test_external_oracle_audit.py` *(new)* | T1 RED → T2 GREEN. Four synthetic claude-code.txt fixtures per AC-5: (a) `load_dataset('fancyzhx/ag_news')` Bash event → assert exit 2, finding `pattern_id == "load_dataset"`, snippet contains `fancyzhx/ag_news`, event_index matches; (b) clean Bash-only fixture (e.g., `psql` + `mongosh` commands) → assert exit 0, sidecar `findings == []`; (c) `requests.get('https://raw.githubusercontent.com/...')` → assert exit 2, severity `confirmed`; (d) Python-import-layer `from datasets import load_dataset` inside a `python3 << EOF` heredoc → assert exit 2, finding pattern_id `from_datasets_import`. Plus 1 fixture each for: (e) WebSearch tool_use → exit 2 with pattern_id `web_search_tool`; (f) missing claude-code.txt → exit 3, stderr `trace-missing`. |
| `tests/integration/test_dab_paper_matrix_external_oracle_gate.py` *(new)* | T3 RED → T3 GREEN. Builds a synthetic cell dir with the agnews-shaped `load_dataset` event, invokes the dispatcher's per-cell hook (or shells out to the validator), asserts the ledger row carries `status: external-oracle-cheating` and `_runs/.../external-oracle-audit.json` is written with `findings` non-empty. Counterpart synthetic clean cell asserts `status: ok` and sidecar `findings == []`. |
| `examples/drivers/dab-paper-matrix.sh` | T3. Add a per-cell hook block between `rk run` (lines 142-148) and `rk audit` (lines 220-222), BEFORE the existing variant-gated `subagent_smoke` block at lines 197-218 (or after it — either ordering works; pick the order that matches the entity body's "after rk-run and before rk-audit" wording). Hook is NOT variant-gated (unlike the subagent smoke gate) — every cell across all 3 variants gets audited. Pattern: `uv run python -m razorback.agents.external_oracle_audit "$cell_run_dir" > "${cell_run_dir}/external-oracle-audit.log" 2>&1 \|\| audit_rc=$?`. On `audit_rc == 2`: set `status="external-oracle-cheating"`, decrement `ok_cells`, increment `failed_cells`, append to `FAILURES_LOG`, write the ledger row with the new status + `audit_rc`, and `continue` (skip rk-audit + rk-score for the cheating cell, mirroring the smoke-gate's `continue` semantics at lines 216-217). On `audit_rc == 3`: same as 2 but with a distinct `status="external-oracle-audit-error"` so the captain can distinguish missing-trace from confirmed-cheating. |
| `examples/solver_workflows/dab_paper_matrix/README.md` | T4. Replace the current 5-line Stage: verify section (lines 26-33) with an extended block that keeps the existing answer-shape paragraph + adds two new sub-blocks: (a) "External-oracle audit" prose verbatim from DAB upstream lines 128-135 (with the razorback-specific note that the trace lives at `steps/main/agent/claude-code.txt` instead of upstream's `claude-output.jsonl`); (b) the agent-facing instruction to invoke `python -m razorback.agents.external_oracle_audit .` against its own cell-dir as part of self-audit and REJECT if exit code is non-zero. The block must contain the literal strings `External-oracle audit`, `datasets.load_dataset`, `huggingface`, and `hf://` for AC-1's grep verification. |
| `examples/drivers/aggregate-goal1-scores.py` | T3. Verify pass-through (or add a 1-line column rendering) — the new `external-oracle-cheating` and `external-oracle-audit-error` ledger statuses MUST appear in the captain-facing per-cell sub-table. If the aggregator already renders the `status` column verbatim (the `ne` work confirmed this for `subagent-dispatch-missing`), this is no-change. |

## Surface map — what stays

- `src/razorback/agents/subagent_traces.py` / `subagent_smoke.py` — untouched. The external-oracle audit is a SIBLING module, not a modification. Both share the `_find_claude_code_txt(cell_dir)` shape but each owns its own copy (no premature abstraction; 5 lines of duplication is fine per CLAUDE.md).
- `src/razorback/spec/schema.py` — no spec-level surface added. The audit fires from the dispatcher hook + the workflow README prose; the spec does not need a new field.
- `src/razorback/agents/spacedock_solver.py` — untouched. The audit is a POST-RUN cell-level check; the solver agent does not need to know about it.
- `taint.py`-style schema with `policy_mode` / `categories` / `confirmed_count`/`suspected_count` — explicitly out of scope per entity body. The sidecar `external-oracle-audit.json` carries the MINIMUM shape needed to surface findings; full taint schema is sibling entity `8yb8fzx5549j8q1w23c7xbr9`.

---

## Task sequence

### T0 — Mechanism gate: prototype scan against real agnews trace

**Spec cite:** entity body §Test plan ("Mechanism gate first (per CLAUDE.md)"); CLAUDE.md "Validating new mechanisms".

- [ ] Write a throwaway `scratch_scan.py` at repo root (NOT committed; `git status` must show it as untracked at end of T0).
- [ ] Implement the regex set above + JSONL line-by-line extraction targeting `type==assistant → message.content[*] → type==tool_use → input.command`.
- [ ] Run against the real agnews trace at `.worktrees/spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh/_runs/goal1-direct-structured-opus47-xhigh/direct-structured/agnews/goal1-direct-structured-agnews/2fa90bb140485d77/agnews__uR698Wh/steps/main/agent/claude-code.txt`. Expected findings (from plan-stage grep): line 26 (`from datasets import`), line 30 (curl `huggingface.co`), line 38 (`load_dataset("ag_news")`), line 40 (`load_dataset("fancyzhx/ag_news")`), line 45 + 48 + 53 (subsequent `load_dataset` calls). Total ≥6 findings.
- [ ] Run against the real bookreview trace at the sibling `bookreview/.../claude-code.txt` path. Expected: ZERO findings.
- [ ] If agnews emits zero findings OR bookreview emits any confirmed findings, STOP and re-read the trace shape before any production code.
- [ ] On GREEN: capture the exact line numbers + extracted snippets in a 5-line note at the top of T1 ("agnews findings calibrated against lines: 26/30/38/40/45/48/53") so T1's RED test fixtures match real-world shape.
- [ ] Delete `scratch_scan.py`.

### T1 — RED unit tests for `external_oracle_audit`

**Spec cite:** AC-5; entity body §Acceptance criteria AC-5.

- [ ] Create `tests/unit/test_external_oracle_audit.py` modeled on `tests/unit/test_subagent_smoke_validator.py` (subprocess-driven exit-code assertions) + `tests/unit/test_subagent_traces_writer.py` (in-process fixture-driven assertions).
- [ ] Fixture A: `load_dataset('fancyzhx/ag_news')` Bash event → assert subprocess exit 2 + sidecar finding `pattern_id == "load_dataset"` + `snippet` substr `fancyzhx/ag_news` + `event_index` matches.
- [ ] Fixture B: clean Bash-only fixture (`psql ...`, `mongosh ...` — no forbidden patterns) → assert exit 0 + sidecar `findings == []`.
- [ ] Fixture C: `requests.get('https://raw.githubusercontent.com/...')` Bash event → assert exit 2 + severity `confirmed` (raw.githubusercontent.com is a public data host).
- [ ] Fixture D: Python heredoc with `from datasets import load_dataset` → assert exit 2 + finding `pattern_id == "from_datasets_import"`.
- [ ] Fixture E: WebSearch `tool_use` event → assert exit 2 + finding `pattern_id == "web_search_tool"`.
- [ ] Fixture F: cell dir with no `claude-code.txt` → assert exit 3 + stderr `trace-missing`.
- [ ] Run `uv run pytest tests/unit/test_external_oracle_audit.py -v` — must fail with `ModuleNotFoundError: No module named 'razorback.agents.external_oracle_audit'` (RED).

### T2 — GREEN: implement `external_oracle_audit.py`

**Spec cite:** AC-2; AC-5.

- [ ] Create `src/razorback/agents/external_oracle_audit.py` with ABOUTME header + `SCHEMA_VERSION = "razorback-external-oracle-audit-v1"` + exit-code constants `EXIT_OK = 0`, `EXIT_EXTERNAL_ORACLE = 2`, `EXIT_TRACE_MISSING = 3`.
- [ ] Implement `_find_claude_code_txt(cell_dir)` mirroring `subagent_traces._find_claude_code_txt` exactly (prefer `cell_dir/steps/main/agent/claude-code.txt`, fall back to `rglob`).
- [ ] Implement `_iter_tool_uses(events)` generator yielding `(event_index, line_number, tool_use_block)` tuples from `assistant`-typed events.
- [ ] Implement `_PATTERNS` as an ordered list of `(pattern_id, pattern_label, compiled_regex, severity, applies_to_tool_names)` tuples. Patterns from DAB upstream lines 128-135 verbatim:
  - `huggingface` — case-insensitive substring on Bash/Read input, severity confirmed.
  - `load_dataset` — `\bdatasets\.load_dataset\s*\(` OR `\bload_dataset\s*\(` on Bash, severity confirmed.
  - `hf_uri` — `\bhf://` on Bash/Read, severity confirmed.
  - `from_datasets_import` — `\bfrom\s+datasets\s+import\b` on Bash (catches Python heredoc imports), severity confirmed.
  - `requests_get_public_host` — `\brequests\.get\s*\(\s*['"]https?://(raw\.githubusercontent\.com|huggingface\.co|datasets-server\.huggingface\.co|api\.github\.com|kaggle\.com|drive\.google\.com)` on Bash, severity confirmed; broader `requests\.get` without a known-public-host match → severity suspected.
  - `web_search_tool` — tool_use `name` ∈ `{"WebSearch", "WebFetch"}`, severity confirmed (whole tool is the offense).
  - `llm_oracle` — substring matches for `openai`, `gemini`, `anthropic.messages.create` on Bash input, severity suspected (catches "ask another model" patterns; the upstream prose explicitly mentions "LLM-call patterns asking another model for the answer").
- [ ] Implement `scan_cell(cell_dir) -> dict` returning `{schema_version, findings: [...], confirmed_count, suspected_count, trace_path}`.
- [ ] Implement `main(argv)` CLI entrypoint: call `scan_cell`, write sidecar `<cell_dir>/external-oracle-audit.json`, emit per-finding line to stdout, exit per the contract.
- [ ] Run `uv run pytest tests/unit/test_external_oracle_audit.py -v` — must pass (GREEN).
- [ ] Run `python -m razorback.agents.external_oracle_audit <real-agnews-cell-dir>` — must exit 2 + name a `load_dataset` finding with the `fancyzhx/ag_news` snippet (AC-2 verbatim).
- [ ] Run `python -m razorback.agents.external_oracle_audit <real-bookreview-cell-dir>` — must exit 0 (AC-2 verbatim).
- [ ] Commit: `feat(wp): T1+T2 — external_oracle_audit module + 6 RED/GREEN unit fixtures`.

### T3 — Dispatcher hook + integration test + aggregator passthrough

**Spec cite:** AC-4.

- [ ] Create `tests/integration/test_dab_paper_matrix_external_oracle_gate.py` modeled on the smoke-gate integration test introduced by `ne` (search the `ne` worktree for `test_dab_paper_matrix_spacedock_gate.py` for shape).
- [ ] RED test: synthetic cell dir with a `load_dataset` event → assert dispatcher invocation marks ledger row `status: external-oracle-cheating`, ledger column ordering preserved, FAILURES_LOG appended.
- [ ] RED test: synthetic clean cell → assert ledger row `status: ok` and `external-oracle-audit.json` sidecar has `findings: []`.
- [ ] Run the integration test — must fail (hook not yet present).
- [ ] Edit `examples/drivers/dab-paper-matrix.sh`: add the per-cell hook between rk-run (line 148) and the existing variant-gated `subagent_smoke` block at line 197. Use the audit-rc dispatch pattern described in Surface map. The hook is NOT variant-gated.
- [ ] Re-run integration test — must pass (GREEN).
- [ ] Inspect `examples/drivers/aggregate-goal1-scores.py` for ledger-status rendering. If status column is passed verbatim (likely, given `ne` shipped without aggregator changes), no edit needed; document the no-op in the T3 commit message. Otherwise add a 1-line rendering pass.
- [ ] Commit: `feat(wp): T3 — dispatcher external-oracle-audit hook + aggregator passthrough`.

### T4 — Workflow README verify-stage prose

**Spec cite:** AC-1, AC-3.

- [ ] Edit `examples/solver_workflows/dab_paper_matrix/README.md` Stage: verify section (lines 26-33). Keep the existing answer-shape paragraph. Append the External-oracle audit block.
- [ ] Block content: (a) one paragraph naming the upstream forbidden patterns verbatim (must contain the literal strings `External-oracle audit`, `datasets.load_dataset`, `huggingface`, `hf://`, `from datasets import`, `requests.get`, `web-search`, `LLM-call`); (b) the harness-invocation paragraph naming `python -m razorback.agents.external_oracle_audit` + the exit-code semantic (0 clean / 2 cheating / 3 trace-missing) + the REJECT instruction if exit is non-zero.
- [ ] Verify with the AC-1 / AC-3 grep commands from the entity body:
  - `grep -F 'External-oracle audit' examples/solver_workflows/dab_paper_matrix/README.md` — must match.
  - `grep -F 'datasets.load_dataset' examples/solver_workflows/dab_paper_matrix/README.md` — must match.
  - `grep -F 'huggingface' examples/solver_workflows/dab_paper_matrix/README.md` — must match.
  - `grep -F 'hf://' examples/solver_workflows/dab_paper_matrix/README.md` — must match.
  - `grep -F 'python -m razorback.agents.external_oracle_audit' examples/solver_workflows/dab_paper_matrix/README.md` — must match.
- [ ] Commit: `docs(wp): T4 — verify-stage External-oracle audit prose + harness invocation`.

### T5 — Cross-cell smoke against all 12 7q cells

**Spec cite:** entity body §Test plan ("Cross-cell"); AC-2.

- [ ] Locate all 12 direct-structured cell run-dirs at `.worktrees/spacedock-ensign-goal1-direct-structured-dab-opus47-xhigh/_runs/goal1-direct-structured-opus47-xhigh/direct-structured/{dataset}/.../claude-code.txt`. Confirmed present at plan time: `agnews, bookreview, crmarenapro, DEPS_DEV_V1, GITHUB_REPOS, googlelocal, music_brainz_20k, PANCANCER_ATLAS, PATENTS, stockindex, stockmarket, yelp`.
- [ ] Run `python -m razorback.agents.external_oracle_audit <each-cell-dir>` against all 12. Record the per-cell exit code + finding-count in a 12-line table.
- [ ] **Expected outcome (per entity body):**
  - agnews → exit 2 (the documented cheating cell from 7q's validation).
  - 11 other cells → exit 0.
- [ ] If any cell other than agnews emits a CONFIRMED finding, STOP and report to captain via stage report — that is a previously-undetected cheating event the 7q validation missed, and the entity scope may need to widen. Surface it; do not silently treat it as a false positive.
- [ ] Run `uv run pytest` (full suite) — must stay green minus the pre-existing failures already documented by 7q's validation report. Compare against the validation report's documented pre-existing failure list (do NOT introduce new failures).
- [ ] Commit: `test(wp): T5 — 12-cell cross-smoke verifies agnews-only positive`.

### T6 — Stage report + entity body update

**Spec cite:** ensign-shared-core.md §Stage Report Protocol.

- [ ] Append `## Stage Report: implementation` to the entity file at `docs/razorback-implementation/dab-verify-stage-external-oracle-audit.md` with DONE / SKIPPED / FAILED lines per the AC checklist (one line per AC + one line per T0-T5 mechanism gate / smoke).
- [ ] Evidence per line: commit SHA + `uv run pytest ...` pass-count + grep-match output.
- [ ] Summary (2-3 sentences): what shipped, the agnews-positive cross-cell verdict, any deferred follow-ups.
- [ ] Commit: `docs(wp): impl stage report — External-oracle audit shipped`.
- [ ] Signal completion to first officer per the ensign runtime contract.

---

## Risk register

| Risk | Mitigation |
|---|---|
| The `tool_use` extraction picks up matches in `tool_result` echoes (false positives) | T0 mechanism gate explicitly tests the bookreview cell expecting ZERO findings; if false positives surface there, T2's extractor narrows to `type==assistant → message.content[*] → type==tool_use → input.command` ONLY. |
| The `claude-code.txt` trace path differs across razorback runtimes (direct-structured vs spacedock) | `_find_claude_code_txt` mirrors `subagent_traces.py` exactly: prefer `cell_dir/steps/main/agent/claude-code.txt`, fall back to `rglob("claude-code.txt")`. The spacedock-variant cell layout has `claude-code.txt` at the same path; the rglob fallback handles any structural drift introduced after this plan lands. |
| A `pip install <generic-lib>` event (e.g., the duckdb/rapidfuzz events in music_brainz_20k) trips a false positive | Out of scope: the upstream forbidden-pattern list (lines 128-135) does NOT include `pip install`. Plan-stage probe confirmed music_brainz_20k contains `pip install duckdb` + `pip install rapidfuzz` but no upstream-listed pattern; the audit MUST return exit 0 for music_brainz_20k in T5. If it doesn't, the regex set is mis-calibrated. Generic-lib pip installs are the sibling `8yb8fzx5549j8q1w23c7xbr9` taint scanner's concern. |
| Adding a non-variant-gated hook to the dispatcher slows the matrix dispatch | The audit is pure-Python file-IO + regex over a single ≤200KB JSONL — negligible per-cell cost (≤100ms). Acceptable. |
| The synthetic cell fixture for the integration test (T3) drifts out of sync with real claude-code.txt JSONL shape | T0 mechanism gate captures the real-trace event shape into a 5-line note at top of T1; T3's synthetic fixture reuses the same event-block structure verbatim. |

## Out of scope (cross-reference with entity body)

- Workspace-README leak-guard prose port — sibling entity `k34cqr2myjsh6aaqm6fhz5nw`.
- Network-layer block — sibling entity `wjfra5rje67399g6msza9zg6`.
- Full upstream `taint.py` schema parity — sibling entity `8yb8fzx5549j8q1w23c7xbr9`.
- direct-minimal / direct-structured workflow README verify-stage edits — those variants have no verify stage prose. AC-4's dispatcher hook covers them mechanically; no prose addition required.
- agnews-only re-run of 7q — separate follow-on impl cycle.
