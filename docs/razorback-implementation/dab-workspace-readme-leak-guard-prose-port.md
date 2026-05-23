---
id: k34cqr2myjsh6aaqm6fhz5nw
title: DAB workspace READMEs — port upstream leak-guard prose (forbid external-oracle lookups by name)
status: plan
source: 2026-05-23 7q validation cheating-audit finding — agnews CONFIRMED downloaded `fancyzhx/ag_news` via `load_dataset` and matched MongoDB article_id↔train/test ordering to derive labels; razorback's `direct-structured`/`direct-minimal`/`spacedock` workspace READMEs at `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py` lack the leak-guard prose that DAB upstream's `~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` carries (lines 77-83 — names `datasets.load_dataset`/`hf://` forbidden + "even if the workspace data appears to come from a public dataset" + "UNABLE TO DETERMINE" escape). Auto-approve: false because workspace prompts are captain-facing surface.
score: 0.92
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

The 7q validation cheating audit found that agnews's agent (opus-4.7+xhigh) routed around razorback's `--disallowedTools` block list by:
1. Recognizing `pip install datasets` was blocked
2. Recognizing `curl https://huggingface.co` was blocked
3. Calling `python3 -c "from datasets import load_dataset; load_dataset('fancyzhx/ag_news')"` — the `datasets` lib was pre-installed in the dab-agent image and `huggingface.co` had unrestricted network egress
4. Matching MongoDB `article_id` to canonical AG News train/test ordering to derive labels — explicitly admitted in the agent's final result text

The razorback workspace READMEs in `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py` (all 3 variants: `direct-minimal`, `direct-structured`, `spacedock`) are TERSE: task statement + workspace layout + database access + output contract. **None** name `datasets.load_dataset`, HuggingFace, `hf://`, or "no external data sources" as forbidden. The "UNABLE TO DETERMINE" escape clause is also absent.

DAB upstream's workspace README at `~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` carries the leak-guard prose (lines 77-83 verbatim — quoted in the entity body of any plan-stage doc). This entity ports that prose into all three razorback variants.

## Acceptance criteria

**AC-1 — Leak-guard prose present in all three razorback workspace variants.**
The `_DIRECT_MINIMAL`, `_DIRECT_STRUCTURED`, and `_SPACEDOCK` templates in `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py` each carry a `## Rules` (or equivalent) section that includes the DAB-upstream leak-guard paragraph verbatim or near-verbatim: forbids HuggingFace `datasets` library by name (`datasets.load_dataset`, `hf://...`); forbids "Public CSV/JSON downloads of the same dataset (kaggle, GitHub, vendor sites)"; forbids "Web search engines, search APIs, or LLM-as-oracle calls"; forbids "Cached prior answers from earlier runs in `_runs/`"; ends with "If a question is unanswerable from them, return `\"UNABLE TO DETERMINE\"`."
Verified by:
- `python3 -c "from razorback_plugin_dab.generate.workspace_readme import render_workspace_readme; assert 'datasets.load_dataset' in render_workspace_readme(variant='direct-structured', container_workdir='/workspace')"` exits 0 for each variant
- `grep -F 'UNABLE TO DETERMINE' packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py` matches all 3 variants

**AC-2 — Live agnews re-run rejects the load_dataset attack path.**
Re-dispatch the single agnews cell against the post-AC-1 dab-agent image. The agent's `claude-code.txt` shows EITHER (a) no `from datasets import load_dataset` event at all (agent saw the rule and declined), OR (b) a `load_dataset` attempt followed by the agent self-correcting (e.g., a tool-use that reads its own reasoning rule + abandons the path). The final result text does NOT contain the phrase "canonical AG News dataset" or "matched article_id to" or equivalent oracle-derivation language.
Verified by: `grep -F 'canonical' agnews-rerun/.../claude-code.txt | grep -i 'ag news\|dataset'` returns empty; cheating-audit re-runs against the new trace as `clean`.

**AC-3 — Unit test pins the leak-guard prose so future README edits can't silently delete it.**
A unit test at `packages/razorback-plugin-dab/tests/unit/test_workspace_readme_leak_guard.py` asserts each variant carries the forbidden-list phrases ("HuggingFace", "datasets.load_dataset", "Public CSV", "UNABLE TO DETERMINE", etc.). Any future edit that drops those phrases turns the test RED.
Verified by: `uv run pytest packages/razorback-plugin-dab/tests/unit/test_workspace_readme_leak_guard.py -v` passes; deleting the leak-guard paragraph from one variant turns the test RED.

**AC-4 — Existing pytest stays green; existing tests at `test_workspace_readme_variants.py` cover the new prose.**
Branch's existing tests for workspace_variants pass; the new test runs alongside.
Verified by: `uv run pytest packages/razorback-plugin-dab/tests/ -v` green; pre-existing failures (LFS-hydration etc.) reproduce on baseline `main`, no branch-introduced regressions.

## Test plan

- **Mechanism smoke first:** confirm one variant's rendered README contains the expected leak-guard phrases via a direct Python call (no docker, no API spend). Verifies the format-string render works correctly through `.format(workdir=...)`.
- **Unit tests:** RED→GREEN for the per-variant phrase-presence assertions.
- **Live agnews re-run:** one cell against the post-fix dab-agent image; ~$0.50-2 API spend. AC-2 gates here.
- **Full pytest:** `uv run pytest` stays green; pre-existing failures only.

## Out of scope

- **Verify-stage external-oracle audit (workflow-contract level).** Sibling entity `wpjrjfhkbp8zvqqpj83g9v5b` (verify-stage external-oracle audit). The leak-guard prose deters; the verify-stage audit catches what slips past the deterrence.
- **Network-layer block of huggingface.co / dataset CDNs.** Sibling entity `wjfra5rje67399g6msza9zg6`. Defense in depth — even with the prose, hard network block is the irrefutable guard.
- **`taint.py` scanner port + read-only rootfs + read-only DuckDB extension cache.** Sibling entity `8yb8fzx5549j8q1w23c7xbr9`. Upstream design at `~/git/dataagentbench/docs/harness/scored-run-egress-taint-and-duckdb-preinstall.md`.
- **agnews-only re-run of 7q.** 7q is REJECTed; after this entity ships, file a follow-on 7q impl cycle to re-run agnews and recompute headline. Not in scope here.
- **Other workspace_variant naming** (e.g. compact-stages, materialized-model). Upstream has 20+ workspace README variants; razorback only carries 3. Out-of-scope unless captain widens.

## Depends on

- (none — pure prose port + tests)

## Resume hook

When this lands, the razorback workspace READMEs have parity with upstream's leak-guard discipline. The 7q agnews re-run can then proceed (file as follow-on impl cycle on 7q or as a sibling entity). The verify-stage audit entity (`wp`) builds on this — leak-guard prose IN the prompt + adversarial trace audit AT the verify stage = defense in depth.
