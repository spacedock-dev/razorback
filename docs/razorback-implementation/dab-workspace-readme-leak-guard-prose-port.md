---
id: k34cqr2myjsh6aaqm6fhz5nw
title: DAB workspace READMEs — port upstream leak-guard prose (forbid external-oracle lookups by name)
status: validation
source: 2026-05-23 7q validation cheating-audit finding — agnews CONFIRMED downloaded `fancyzhx/ag_news` via `load_dataset` and matched MongoDB article_id↔train/test ordering to derive labels; razorback's `direct-structured`/`direct-minimal`/`spacedock` workspace READMEs at `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py` lack the leak-guard prose that DAB upstream's `~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` carries (lines 77-83 — names `datasets.load_dataset`/`hf://` forbidden + "even if the workspace data appears to come from a public dataset" + "UNABLE TO DETERMINE" escape). Auto-approve: false because workspace prompts are captain-facing surface.
score: 0.92
auto-approve: false
worktree: .worktrees/spacedock-ensign-dab-workspace-readme-leak-guard-prose-port
issue:
pr: #1
mod-block: merge:pr-merge
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

## Plan

### Mechanism validation (done at plan time)

- **Upstream prose source:** `~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` lines 77–83 (the `Use only the workspace data.` paragraph + 4-bullet forbidden list + closing `UNABLE TO DETERMINE` sentence) — quoted verbatim below.
- **Razorback target file:** `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py`, three templates `_DIRECT_MINIMAL` (lines 10–20), `_DIRECT_STRUCTURED` (lines 22–51), `_SPACEDOCK` (lines 53–84).
- **Image rebuild check (resolved — NO rebuild needed):** `prepare.py` lines 283–286 (and again at line 440) call `render_workspace_readme(...)` and write the result to `workdir/README.md` at workspace prep time. The README is rendered per-cell from the razorback source package at every prepare invocation — it is NOT baked into the dab-agent image. A code edit to `workspace_readme.py` propagates to the next live re-run without rebuilding `dab-agent`.
- **Existing test scope:** `packages/razorback-plugin-dab/tests/unit/test_workspace_readme_variants.py` covers per-variant character (terse vs layout vs crew-loop framing) but says nothing about leak-guard prose. The new test file is purely additive — no risk of conflict.
- **Per-variant character preservation:**
  - `_DIRECT_MINIMAL` currently has no headers beyond `# Task` — adding a `## Rules` section is acceptable (it stays the shortest variant; the test `"Workspace layout" not in text` still holds).
  - `_DIRECT_STRUCTURED` already has `## Workspace layout` / `## Database access` / `## Output contract` — add `## Rules` as a fourth section between database-access and output-contract (matches upstream ordering).
  - `_SPACEDOCK` keeps its crew-loop framing (`first officer` / `model -> analyze -> verify`); add `## Rules` in the same slot as direct-structured. The crew-loop framing references "an honest verifier" — the leak-guard prose reinforces that framing rather than competing with it.

### Verbatim upstream prose to port (cite: dataagentbench workspace-readme.md L77–83)

```
**Use only the workspace data.** The benchmark provides everything needed to answer each query in the workspace's databases (`connections.yaml`, attached SQLite/PostgreSQL/MongoDB/DuckDB sources). Do **not** consult external data sources to look up answer values, labels, or ground truth — even if the workspace data appears to come from a public dataset. Specifically forbidden:
- HuggingFace `datasets` library (`datasets.load_dataset`, `hf://...`) for label/oracle lookup
- Public CSV/JSON downloads of the same dataset (kaggle, GitHub, vendor sites)
- Web search engines, search APIs, or LLM-as-oracle calls (e.g., asking another model "what is the answer to X")
- Cached prior answers from earlier runs in `_runs/` or any artifacts outside the current workspace

The workspace databases are the only authoritative source. If a question is unanswerable from them, return `"UNABLE TO DETERMINE"`.
```

Razorback variants reference `db_config.yaml` (not `connections.yaml`); single-query mode (`query.json`, not `query{N}/query.json`); and per-cell workspaces (no `_runs/` peer dir). The port should swap those names — that is mechanical adaptation, not creative paraphrasing, and the forbidden-list bullets stay verbatim. Concretely, the line `(`connections.yaml`, attached SQLite/PostgreSQL/MongoDB/DuckDB sources)` becomes `(`db_config.yaml`, attached SQLite/PostgreSQL/MongoDB/DuckDB sources)` and the `_runs/` bullet becomes `Cached prior answers from earlier runs or any artifacts outside the current workspace`.

### Task sequence (mechanism-first per CLAUDE.md)

The riskiest contract is empirical: does the leak-guard prose ACTUALLY deter opus-4.7+xhigh on agnews? That only validates at T4 (live re-run). Everything before T4 is cheap and deterministic.

- **T0 — RED unit test.** Create `packages/razorback-plugin-dab/tests/unit/test_workspace_readme_leak_guard.py`. For each variant in `WORKSPACE_VARIANTS`, assert the rendered README contains each of: `"HuggingFace"`, `"datasets.load_dataset"`, `"hf://"`, `"Public CSV"`, `"Web search engines"`, `"UNABLE TO DETERMINE"`, `"Use only the workspace data"`. Run once to confirm RED before any prose edit (proves the test actually exercises the new contract).
- **T1 — GREEN prose edits.** Add a `## Rules` section carrying the ported leak-guard paragraph to each of `_DIRECT_MINIMAL`, `_DIRECT_STRUCTURED`, `_SPACEDOCK`. Use the verbatim upstream prose with the three mechanical name swaps documented above. Keep the existing per-variant character (no extra paraphrase).
- **T2 — Unit tests green.** Run `uv run pytest packages/razorback-plugin-dab/tests/unit/test_workspace_readme_leak_guard.py packages/razorback-plugin-dab/tests/unit/test_workspace_readme_variants.py -v`. Both files green. AC-3 + AC-4-narrow gate here.
- **T3 — (No image rebuild.)** Mechanism validation above confirmed the README is rendered at workspace prep time, not baked into `dab-agent`. Skip explicitly and note in the impl stage report. If a later inspection of `_runs/...` for the live re-run shows the agent's `workdir/README.md` lacks the new prose, raise as a concern then — but the code path is direct.
- **T4 — Live agnews re-run (mechanism gate, AC-2).** Re-dispatch the single agnews cell against the post-T1 source. Budget ~$0.50–2 API. Verify per AC-2: the agent either declines `load_dataset` outright or self-corrects mid-trace, and the final result text contains no `canonical AG News` / `matched article_id to` / equivalent oracle-derivation language. Run the cheating audit re-runner against the new trace; expect `clean`. If the agent still cheats, raise as a finding (do NOT silently add more guards in this entity — that is sibling-entity scope: network block + verify-stage audit + taint scanner).
- **T5 — Full pytest.** `uv run pytest packages/razorback-plugin-dab/tests/ -v`. Existing tests stay green; pre-existing failures (LFS-hydration etc.) reproduce on baseline `main`. AC-4 gate here.

### Risks and notes

- The verbatim port keeps razorback's prose identical to upstream's, which means future upstream changes to the leak-guard paragraph create drift. Acceptable for now — sibling entities (verify-stage audit + network block) provide defense in depth so prose drift is not a single point of failure.
- `_DIRECT_MINIMAL` gains a `## Rules` section, which means it is no longer header-free. The existing test `assert "Workspace layout" not in text` for that variant still passes (the new section is `## Rules`, not `## Workspace layout`), and the variant remains the shortest of the three by a clear margin.
- AC-2's `grep` assertion is over the final result text only; a trace where the agent explored `load_dataset` then self-corrected is acceptable per the AC's `(b)` branch. The impl-stage worker should record which branch (`a` decline / `b` self-correct) the agent took, as captain-relevant signal.

## Stage Report: plan

- DONE: Plan-output flex: 4 ACs, narrow scope (one source file + one test file + one live re-run). Recommend inline plan.
  Inline plan written above; ACs already crisp in entity body (4 ACs, exactly one source file `workspace_readme.py`, one new test file `test_workspace_readme_leak_guard.py`, one live re-run cell `agnews`).
- DONE: Mechanism validation — read DAB upstream's workspace README at `~/git/dataagentbench/benchmark/workspace-readmes/workspace-readme.md` (lines 70-138) for the exact leak-guard prose. Cite line numbers. Compare to razorback's three variants in `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py`. Identify the smallest diff that ports the prose without dropping the existing per-variant character.
  Upstream prose quoted verbatim from L77–83. Smallest diff = one new `## Rules` section per variant; three mechanical name swaps (`connections.yaml`→`db_config.yaml`, query-dir pattern, `_runs/` reference). Per-variant character preserved (direct-minimal stays shortest, direct-structured keeps layout section, spacedock keeps crew-loop framing).
- DONE: Sequence the impl-stage tasks per CLAUDE.md mechanism-first.
  Sequence T0 RED → T1 GREEN → T2 unit-test gate → T3 skip-image-rebuild (mechanism-validated: prepare.py L283-286 renders per-cell) → T4 live agnews re-run (mechanism gate / AC-2) → T5 full pytest (AC-4 gate).

### Summary

Inline plan landed: verbatim port of DAB upstream's L77–83 leak-guard paragraph into all three razorback workspace variants, with three mechanical name swaps (db_config.yaml / single-query / no _runs). Image rebuild explicitly NOT required — `prepare.py` renders the README per-cell at workspace prep time from the razorback source, so a code edit propagates to the next live re-run without touching the dab-agent image. Sequenced T0→T5 with the live agnews re-run (~$0.50–2) as the empirical AC-2 gate; cheaper deterministic gates (unit test + full pytest) front-loaded.
