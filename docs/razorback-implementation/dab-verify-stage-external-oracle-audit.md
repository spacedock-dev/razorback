---
id: wpjrjfhkbp8zvqqpj83g9v5b
title: DAB spacedock — verify-stage adversarial trace audit (port upstream's External-oracle audit contract)
status: plan
source: 2026-05-23 7q validation cheating-audit finding — leak-guard prose alone is not enough; opus-4.7+xhigh may still attempt external lookups + admit them. DAB upstream's spacedock workflow (`~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` lines 128-135) includes an `External-oracle audit` step in the `verify` stage that scans the analyze-stage tool-use trace for matches against `huggingface`, `datasets.load_dataset`, `hf://`, `from datasets import`, `requests.get` to public data hosts, web-search invocations, or LLM-as-oracle patterns — and REJECTs with the offending event index. Razorback's spacedock `verify` stage (in `examples/solver_workflows/dab_paper_matrix/README.md`) has no such contract. Auto-approve: false because the workflow contract is captain-facing.
score: 0.9
auto-approve: false
worktree:
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
A consumer-facing helper that takes a run-dir path and scans the `claude-code.txt` trace for forbidden patterns; emits structured findings (event index, matched pattern, snippet ≤200 chars, severity). Lives at `src/razorback/agents/external_oracle_audit.py` (or sibling to `subagent_traces.py`/`subagent_smoke.py` from `ne`). Mirror the contract of the smoke validator's exit codes (0 clean / 2 dirty / 3 error).
Verified by: `python -m razorback.agents.external_oracle_audit <real-agnews-cell-dir>` returns exit 2 + names the `load_dataset` event index + the `fancyzhx/ag_news` URI in the snippet; `python -m razorback.agents.external_oracle_audit <real-bookreview-cell-dir>` returns exit 0.

**AC-3 — Solver-workflow verify stage prompt-level rule references the helper.**
The `verify` stage prose in `examples/solver_workflows/dab_paper_matrix/README.md` instructs the agent to invoke (or describes the harness invoking) `python -m razorback.agents.external_oracle_audit` against its own run-dir as part of its self-audit, and REJECT if exit code is non-zero. Mirrors how DAB upstream's solver workflow ties the prose audit to a concrete check.
Verified by: workflow README's verify section names the command + the exit-code semantic.

**AC-4 — Per-cell post-run hook automation (defense in depth like ne's smoke gate).**
The matrix dispatcher (`examples/drivers/dab-paper-matrix.sh`) — modeled on `ne`'s subagent-smoke-gate hook (commit 39847a5) — invokes the external-oracle audit as a post-cell gate after rk-run and before rk-audit. A failing audit marks the cell `status: external-oracle-cheating` in `dispatch-ledger.tsv` and the captain-facing aggregator surfaces it (mirrors how `ne` handles `captured == 0`).
Verified by: synthetic cell with a `load_dataset` event in claude-code.txt triggers the dispatcher to mark `status: external-oracle-cheating`; clean cell stays `status: ok`.

**AC-5 — Unit tests for the audit module.**
Synthetic claude-code.txt fixtures: one with a `load_dataset('fancyzhx/ag_news')` event (must REJECT with the right finding), one with a clean Bash-only trace (must PASS), one with `requests.get('https://raw.githubusercontent.com/...')` (must REJECT), one with `from datasets import load_dataset` Python import (must REJECT — same import-layer attack as agnews used).
Verified by: `uv run pytest tests/unit/test_external_oracle_audit.py -v` passes.

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
- **direct-minimal / direct-structured verify-stage audit.** Those variants don't have a verify stage today (no spacedock crew loop). This entity scopes to the spacedock solver workflow. Direct variants would need the audit run as a separate post-cell hook (which AC-4's dispatcher integration provides incidentally).
- **agnews-only re-run of 7q.** Same as the sibling leak-guard entity — file a follow-on 7q impl cycle after these ship.

## Depends on

- **`k34cqr2myjsh6aaqm6fhz5nw` dab-workspace-readme-leak-guard-prose-port** (sibling, parallel) — pure-prose deterrence + this entity's mechanical audit = defense in depth. Either can land first; both land together for the trustworthy 7q re-run.
- **`ne spacedock-solver-real-fo-dispatch-and-smoke-gate`** (in flight) — sets the pattern for "razorback agent module + dispatcher hook + manifest writer" that this entity's external-oracle audit mirrors. The smoke-gate writer at `src/razorback/agents/subagent_traces.py` and validator at `src/razorback/agents/subagent_smoke.py` are the design template for `src/razorback/agents/external_oracle_audit.py`.

## Resume hook

When this lands, the spacedock workflow can no longer be cheated by an agent that finds a way around the prompt rule. The audit fires at every cell. Failed cells are flagged in `dispatch-ledger.tsv` and the captain-facing aggregator. Combined with the workspace-README prose port (sibling `k3`), the leak-guard discipline reaches parity with DAB upstream's verify-stage contract.
