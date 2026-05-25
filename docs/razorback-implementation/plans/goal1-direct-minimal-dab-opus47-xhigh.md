# Goal 1 Sibling — DAB Direct-Minimal Matrix, opus-4.7 + reasoning_effort=xhigh — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/goal1-direct-minimal-dab-opus47-xhigh.md`

**Goal:** Close the three-way crew-loop comparison at opus-4.7 + reasoning_effort=xhigh + batch + N=1 by producing the direct-minimal point alongside the archived d8 spacedock (stratified=0.7055) and 7q direct-structured (stratified=0.6719). Captain-facing headline is **stratified-per-query** against `paper direct_baseline=0.4376` (same paper baseline as direct-structured — the DAB paper does not break out a separate direct-minimal number).

**This is a research RUN entity, not a feature change.** No Python source is modified. The 12 direct-minimal specs already exist on disk at the post-hm shape (`kind: harbor + plugin: dab + plugin_args.workspace_variant: direct-minimal`, `kind: claude-cli`, `model: claude-opus-4-7`, `reasoning_effort: xhigh`, `query_mode: batch`, `trials: 1`) — verified at the head of plan stage. The **one** spec-data change is adding `experiment_meta.paper_baseline: {name: direct, value: 0.4376}` to all 12 specs (7q added it to direct-structured at commit `de9cfba` but the hm migration that touched direct-minimal at commit `40ed8a2` predated the paper_baseline injection). The post-everything-stack discipline (k3 leak-guard, wp audit-taint, hm dispatch shape, k4 reasoning_effort threading, rk audit strict gating, `rk run --explain` preflight, `rk score` paper_baseline auto-pull, aggregator hard-coded direct-minimal→0.4376) is all in place; implementation stage is **spec-edit + freeze + preflight + smoke + dispatch + audit + aggregate + report**.

**Tech Stack:** Python 3.12, bash. No new runtime dependencies. No source-tree edits.

**Structural template:** Mirrors `docs/razorback-implementation/plans/goal1-direct-structured-dab-opus47-xhigh.md` (7q), adapted for the direct-minimal variant.

---

## AC ↔ Task map

| AC | Description | Tasks |
|---|---|---|
| AC-1 | 12 direct-minimal specs carry `agent.kind: claude-cli`, `agent.model: claude-opus-4-7`, `agent.reasoning_effort: xhigh`, `benchmark.kind: harbor`, `benchmark.plugin: dab`, `benchmark.dataset: dab@1.0`, `benchmark.plugin_args.workspace_variant: direct-minimal`, `benchmark.plugin_args.query_mode: batch`, `trials: 1`, AND `experiment_meta.paper_baseline.{name: direct, value: 0.4376}`. **11/12 fields are already on disk (post-hm); paper_baseline is the one new field.** | T1 (verify pre-existing shape), T2 (file-gen: inject paper_baseline) |
| AC-2 | Each spec freezes cleanly: `*.frozen.yaml` + `provenance.yaml` adjacent; `rk run --explain --explain-format json` resolves to expected shape with `reasoning_effort: xhigh` threaded into resolved kwargs, `plugin: dab`, `plugin_args.workspace_variant: direct-minimal`; per-cell explain-JSONs committed under `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/per-cell-preflight/` | T3 (freeze loop), T4 (rk run --explain preflight) |
| AC-3 | Full 12-cell run completes; each cell produces a run-dir with `summary.json`, `provenance.yaml`, per-trial `result.json` + `reward_per_query.json`, `audit.json` (driver's per-cell `rk audit --policy strict` gate), `score.json` (driver's per-cell `rk score` auto-pulled paper_baseline); `--continue-on-fail` keeps the matrix going through individual cell failures; `dispatch-ledger.tsv` records every cell | T5 (T0 mechanism-smoke gate on bookreview), T6 (full 12-cell dispatch), T7 (per-cell artifact verification) |
| AC-4 | Audit clean across the matrix: `jq -r '.taint_status' .../<cell>/audit.json` returns `clean` for all 12 cells; AGNEWS trace shows either branch (a) declined `load_dataset` outright OR branch (b) attempted-and-self-corrected per k3's verifier shape; document the `gv audit-scanner-subagent-jsonl-coverage` limitation (backlog) and note direct-minimal is claude-cli single-session so the coverage gap doesn't apply | T8 (audit verdict aggregation) |
| AC-5 | Per-query (stratified) headline emitted against paper direct baseline; aggregator produces `per_query_pass_at_1_mean_over_strata` for the 12 cells; captain-facing report at `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/report.md` leads with the stratified-per-query number against `paper direct_baseline=0.4376`; report includes three-way comparison table with d8 spacedock + 7q direct-structured numbers | T9 (aggregator run), T10 (captain-facing report) |
| AC-6 | Per-cell `provenance.yaml` records `harbor_agent_kwargs_hash`, `reasoning_effort: xhigh`, resolved opus-4.7 model version, post-hm `kind: harbor + plugin: dab` shape via plugin_args hash; `solver_workflow_content_hash` is null for claude-cli (expected and documented); sampled re-freeze of bookreview produces the same `sealed_hash` | T3 (freeze-time provenance), T10 (final-report provenance enumeration) |

**Riskiest contract first (mechanism gate):** The `agent.kind: claude-cli` + `benchmark.plugin: dab` + `plugin_args.workspace_variant: direct-minimal` combination is a first-class path on the harbor surface (verified statically in the **Mechanism check** section below), but this entity is the first goal1 paper-comparable matrix run of that combination at opus-4.7+xhigh. The riskiest concrete contract is **the `_DIRECT_MINIMAL` workspace README** — the shortest variant; the agent gets only the task statement, the answer-file contract, and the k3 leak-guard `## Rules` block. The runtime mechanism-smoke gate (T5) executes the **bookreview** cell solo BEFORE the full 12-cell dispatch burns wallclock; if `claude-cli` cannot engage the DBs from the minimal README, the matrix is escalated to the captain rather than silently widening scope (e.g., editing the README template). T0 in the captain's hint #2.

---

## Mechanism check — DONE in plan stage (do not redo)

The plan-stage worker performed this static-source trace before writing the plan:

1. **WORKSPACE_VARIANTS enumeration.** `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py:7` declares `WORKSPACE_VARIANTS = ("spacedock", "direct-structured", "direct-minimal")` — `direct-minimal` is first-class.
2. **`_DIRECT_MINIMAL` template at `:10-30`.** Carries: (a) Task block with `query.json` + `db_config.yaml` + `db_description.txt` pointer and the answer-file contract; (b) k3's `## Rules` leak-guard block (HuggingFace `datasets.load_dataset` / `hf://` / public CSV / web search / LLM-as-oracle forbidden; the workspace databases are the only authoritative source; `"UNABLE TO DETERMINE"` if unanswerable). The k3 port is confirmed present at lines 21-30. No `## Workspace layout` / `## Database access` / `## Output contract` headings (those are direct-structured + spacedock additions).
3. **Dispatcher threads the variant.** The post-hm dispatch shape (`benchmark.kind: harbor + plugin: dab + plugin_args.workspace_variant: direct-minimal`) is the generic Harbor plugin surface; the plugin's CLI accepts the variant and renders the appropriate README via `render_workspace_readme(variant="direct-minimal", ...)` at `:124-133`.
4. **Matrix driver supports the variant.** `examples/drivers/dab-paper-matrix.sh:14, 29` declare `direct-minimal` in the default-variants tuple; `:251-261` maps it (alongside `direct-structured`) to **score auto-pull** — i.e., `rk score "$cell_run_dir" --format json` with NO `--against-constant`, relying on `src/razorback/cli/score.py:_load_paper_baseline` to read `experiment_meta.paper_baseline` from the cell's `spec.frozen.yaml`. The driver loop and validation are variant-agnostic.
5. **Score auto-pull from frontmatter.** `src/razorback/cli/score.py:40-65` reads `<run-dir>/spec.frozen.yaml`'s `experiment_meta.paper_baseline.{name, value}`; the `constant_source` field in `score.json` distinguishes `"spec.frontmatter"` from `"cli"`. AC-5's verification command (`per_query_verdict` field source = `spec.frontmatter` per 12/12 score.json files) hinges on the spec carrying the field. **This is why T2 (paper_baseline injection) is mandatory.**
6. **Aggregator hard-codes the target.** `examples/drivers/aggregate-goal1-scores.py:24-28` maps `direct-minimal → ("direct_baseline", 0.4376)`. The captain-facing aggregate verdict uses this hard-coded value regardless of the per-cell `score.json`'s `constant_source`. (Both should agree at `0.4376`; if they disagree the implementation must surface it.)
7. **k4 reasoning_effort threading.** k4's translator change threads `agent.reasoning_effort` into the claude-cli resolved kwargs; `rk run --explain --explain-format json` exposes this in the resolved-kwargs section. T4 asserts the value is `xhigh` per cell. (Empirically verify the exact dotted path on first invocation, since explain-JSON schema is not pinned in the entity.)
8. **wp audit-taint extends to claude-cli.** `src/razorback/audit/claude_code.py` adapts the claude-cli trace shape; `razorback.audit.taint` owns the forbidden-pattern list. The driver fires `rk audit --policy strict` on every cell (NOT variant-gated — `dab-paper-matrix.sh:217-244`). Exit code 23 = cheating (REJECT); 0 = clean; other non-zero = audit error.
9. **gv subagent-jsonl-coverage gap is irrelevant here.** Per `docs/razorback-implementation/audit-scanner-subagent-jsonl-coverage.md` (status: backlog), the audit scanner's discovery glob walks only `**/agent/claude-code.txt` (the OUTER claude session log). direct-minimal is **claude-cli single-session** — there is no subagent dispatch, no inner JSONL trace, no coverage gap. The audit verdict here is complete despite gv being unshipped.
10. **Generator stale.** `examples/drivers/generate-dab-paper-matrix-specs.py` still emits the legacy `kind: harbor_dab` shape AND does NOT inject `experiment_meta.paper_baseline`. The 12 direct-minimal specs on disk were migrated to `kind: harbor + plugin: dab` at hm commit 3 (`40ed8a2`) but never received paper_baseline. T2 injects it as a one-off edit (matches 7q's commit `de9cfba` shape on direct-structured); regenerating from the stale generator would undo the hm migration. **Do NOT run the generator.**

**Verdict:** The direct-minimal path is a well-trodden surface; the spec shape is post-hm canonical and already at `xhigh`; the matrix dispatcher routes it without special-casing; the score-aggregator pipeline auto-pulls the paper baseline from the spec. The only spec gap is the missing `experiment_meta.paper_baseline` block (T2). Implementation stage starts at T1 (verify-shape) and proceeds linearly. Runtime mechanism-smoke at the bookreview cell (T5) catches any DB-access or workspace-README assumption mismatch in 5–10 minutes BEFORE the full matrix burns 2–3 hours.

---

## Surface map — what changes

| File | Change | Committed? |
|---|---|---|
| `examples/specs/goal1/direct-minimal/*.yaml` *(12 files)* | T2: inject `experiment_meta.paper_baseline: {name: direct, value: 0.4376}`. No other field touched. | Yes (committed to `main` before T3) |
| `examples/specs/goal1/direct-minimal/*.frozen.yaml` *(12 files)* | Emitted by T3 freeze loop. Carry `sealed_hash` + the claude-cli-relevant subset of provenance fields, including `experiment_meta.paper_baseline` (pass-through from source spec per `src/razorback/provenance/freeze_cmd.py:3` comment). | Host-specific; **not** committed to git (gitignored). Mirror committed under per-cell evidence dir in T10. |
| `examples/specs/goal1/direct-minimal/provenance.yaml` *(1 file, last-write-wins sidecar)* | Emitted alongside the last frozen spec. | Same as above. |
| `_runs/goal1-direct-minimal-opus47-xhigh/direct-minimal/<dataset>/<run>/<job>/{result.json,summary.json,provenance.yaml,score.json,audit.json,events.jsonl,dispatch.log}` *(12 cells)* | Emitted by T6 matrix dispatch. Out-of-tree, gitignored. | No. Mirrored to evidence dir in T10. |
| `_runs/goal1-direct-minimal-opus47-xhigh/dispatch-ledger.tsv` | Emitted by T6; one row per cell with `variant`, `dataset`, `spec_frozen`, `runs_dir`, `status`, `exit_code`, `cost_usd`. | Mirror committed to evidence dir in T10. |
| `_runs/goal1-direct-minimal-opus47-xhigh/direct-minimal/aggregate-score.json` | Emitted by T9 aggregator. Per-dataset Wilson CIs + pooled binary + pooled per-query pass@1 + stratified-per-query mean + against-constant verdict vs `direct_baseline=0.4376` (aggregator hard-coded). | Mirror committed to evidence dir in T10. |
| `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/report.md` *(new)* | T10 captain-facing report. **STRATIFIED-PER-QUERY headline only** — pooled/binary numbers may appear in supplementary tables but NOT in the headline (captain standing directive). | Yes (committed to `main`). |
| `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/per-cell-preflight/<dataset>-explain.json` *(12 files)* | T4 `rk run --explain --explain-format json` output per cell. | Yes (committed to `main`). |
| `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/cells/<dataset>/{summary.json,result.json,reward_per_query.json,score.json,audit.json,provenance.yaml}` *(12 dirs)* | Per-cell evidence mirror committed to git (full per-trial trajectories stay in `_runs/`). | Yes. |

## Surface map — what stays

- All Python source under `src/razorback/` and `packages/razorback-plugin-dab/src/`. This is a research run.
- `examples/drivers/dab-paper-matrix.sh` — driver unchanged.
- `examples/drivers/aggregate-goal1-scores.py` — aggregator unchanged.
- `examples/drivers/generate-dab-paper-matrix-specs.py` — generator unchanged. **DO NOT RUN IT.** It would undo hm's `kind: harbor_dab → kind: harbor + plugin: dab` migration and would not inject `experiment_meta.paper_baseline`. T2 is a targeted yaml edit on the 12 already-migrated specs.
- `src/razorback/runs/aggregate.py:reduce_per_query_stratified` — canonical per-query reducer.
- `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py` — `_DIRECT_MINIMAL` template with k3 leak-guard prose; do NOT touch.

---

## Spec ambiguity & guardrails to flag before T1

1. **N=1 vs N=5.** Entity is explicit: `trials: 1`, N=1, batch mode, direct-minimal variant only. Do not promote to N=5; per "Out of scope" that's a sibling follow-up entity.
2. **Budget ceiling.** Entity estimates `~$25-40` total at `--max-cell-budget-usd 10.0` (same cap as 7q's plan). Matrix-wide implicit ceiling is `12 × $10 = $120`. The per-spec `experiment_meta.max_budget_usd: 20.0` is the spec-side cap (rk budget gate); the driver flag is the per-cell runtime cap. Both are in play.
3. **Variant scoping.** The matrix driver defaults to all 3 variants × 12 datasets = 36 cells. T5 + T6 MUST pass `--variants direct-minimal` to scope to 12 cells.
4. **runs_dir + freeze_dir location.** Same captain-approved deviation as the d8/7q runs: sandbox blocks `$XDG_DATA_HOME` and Colima virtiofs requires runs-dir under `/Users/…`. This plan uses `_runs/goal1-direct-minimal-opus47-xhigh/` for runs and `_runs/_razorback-freeze/` for the freeze CAS (env var `RAZORBACK_FREEZE_DIR`). Project-root `_runs/` is gitignored.
5. **`DATAAGENTBENCH_DATA_ROOT`.** Per d8/7q deviation #3, the dispatcher's env MUST include `DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data`. Without it, all 12 cells fast-fail with `dataset X not hydrated, found LFS pointer`. T5 catches this in the first 60s of the bookreview smoke; T6 inherits the export from the T5 shell session.
6. **API auth.** The dispatcher reads `$CLAUDE_CODE_OAUTH_TOKEN` (or `~/.claude/benchmark-token`). T5 fails-fast if neither is present; do NOT run on a free-tier session.
7. **Hard-blocker condition.** Per entity dispatch: if T5 (bookreview smoke) reveals `claude-cli` cannot engage the DBs from the **minimal** workspace README (e.g., the README is too sparse and the agent never figures out the DB-access path), surface to captain at the impl-stage gate. Do NOT silently widen scope by editing the `_DIRECT_MINIMAL` template or the dispatcher. The whole point of the three-way is to measure direct-minimal's behavior at its current README.
8. **STRATIFIED ONLY in captain-facing headline.** Captain standing directive (2026-05-25). The aggregator emits both `pooled_pass_at_1` (binary) and `per_query_pass_at_1_mean_over_strata` (stratified-per-query); the captain-facing report's HEADLINE leads with stratified-per-query. Pooled/binary numbers may appear in supplementary per-cell tables but must NOT appear in the headline. Violations of this rule are a Rule #1 problem.
9. **Three-way comparison numbers.** d8 spacedock stratified = `0.7055` (from `_archive/goal1-rerun-headline-per-query-recompute.md`). 7q direct-structured stratified = `0.6719` (from `_archive/goal1-direct-structured-dab-opus47-xhigh.md`). Both numbers are the `per_query_pass_at_1_mean_over_strata` field of their respective `aggregate-score.json`. T10 cites both verbatim. Re-deriving them is out of scope.

---

## Tasks

### T1 — Verify the 12 specs satisfy AC-1's pre-existing shape (no regen, no edit)

- **Goal:** Confirm 11/12 AC-1 sub-clauses are already on disk at the post-hm shape.
- **Commands:**
  ```bash
  cd /Users/clkao/git/razorback
  D=examples/specs/goal1/direct-minimal
  ls "$D"/*.yaml | wc -l                                              # 12
  grep -l "kind: claude-cli"             "$D"/*.yaml | wc -l           # 12
  grep -l "model: claude-opus-4-7"       "$D"/*.yaml | wc -l           # 12
  grep -l "reasoning_effort: xhigh"      "$D"/*.yaml | wc -l           # 12
  grep -l "kind: harbor$"                "$D"/*.yaml | wc -l           # 12 (post-hm)
  grep -l "plugin: dab"                  "$D"/*.yaml | wc -l           # 12
  grep -l "workspace_variant: direct-minimal" "$D"/*.yaml | wc -l      # 12
  grep -l "dataset: dab@1.0"             "$D"/*.yaml | wc -l           # 12
  grep -l "query_mode: batch"            "$D"/*.yaml | wc -l           # 12
  grep -l "^trials: 1"                   "$D"/*.yaml | wc -l           # 12
  grep -l "kind: harbor_dab"             "$D"/*.yaml | wc -l           # 0 (legacy gone)
  ```
- **Expected:** all 12-counts return `12`; the legacy check returns `0`. If any deviate, STOP and surface to captain — do NOT run the generator; that would undo hm.
- **Spec §-cite:** Entity AC-1 verification (sub-clauses 1, 2, 4 of the entity's bulleted list).

### T2 — Inject `experiment_meta.paper_baseline` into all 12 specs

- **Goal:** Add the one missing AC-1 field (the third sub-clause of the entity's bulleted list).
- **Why a targeted edit not a regen:** The generator at `examples/drivers/generate-dab-paper-matrix-specs.py` (a) still emits legacy `kind: harbor_dab` and (b) does NOT inject paper_baseline. Running it would undo the hm migration. 7q precedent at commit `de9cfba` ("7q AC-1: add experiment_meta.paper_baseline to direct-structured specs") used a targeted yaml edit; this plan inherits.
- **Shape (matches 7q exactly):**
  ```yaml
  experiment_meta:
    max_budget_usd: 20.0
    estimated_cost_usd: 2.0
    paper_baseline:
      name: direct
      value: 0.4376
  ```
- **Edit method:** Per-spec `Edit` tool call appending `  paper_baseline:\n    name: direct\n    value: 0.4376` under each spec's existing `experiment_meta:` block (after `estimated_cost_usd: 2.0`). Twelve specs, twelve identical edits.
- **Verification:**
  ```bash
  grep -l "paper_baseline" examples/specs/goal1/direct-minimal/*.yaml | wc -l        # 12
  grep -l "name: direct"   examples/specs/goal1/direct-minimal/*.yaml | wc -l        # 12
  grep -l "value: 0.4376"  examples/specs/goal1/direct-minimal/*.yaml | wc -l        # 12
  # YAML still parses:
  for s in examples/specs/goal1/direct-minimal/*.yaml; do
    python3 -c "import yaml,sys; yaml.safe_load(open('$s'))" || { echo "PARSE FAIL: $s"; exit 1; }
  done
  ```
- **Commit:** Stage the 12 edited spec files only; commit message `goal1-direct-minimal: add experiment_meta.paper_baseline to 12 specs (mirrors 7q de9cfba)`. Do NOT bundle with other edits.
- **Spec §-cite:** Entity AC-1 third bullet (`grep -l "paper_baseline" … returns all 12`).

### T3 — Freeze 12 direct-minimal specs

- **Command (per spec):** `uv run rk freeze <spec> --allow-missing`
- **Loop:**
  ```bash
  cd /Users/clkao/git/razorback
  export RAZORBACK_FREEZE_DIR=/Users/clkao/git/razorback/_runs/_razorback-freeze
  mkdir -p "$RAZORBACK_FREEZE_DIR"
  fail=0
  for spec in examples/specs/goal1/direct-minimal/*.yaml; do
      uv run rk freeze "$spec" --allow-missing || { echo "FREEZE FAILED: $spec" >&2; fail=$((fail+1)); }
  done
  echo "freeze failures: $fail"
  ```
  `--allow-missing` is required because `pin_model_version: true` resolves only at `rk run` time on a live API call (same as 7q's T2).
- **Verification:**
  - `ls examples/specs/goal1/direct-minimal/*.frozen.yaml | wc -l` returns `12`.
  - `fail == 0`.
  - All 12 frozen specs share the same `sealed_hash` (agent block + plugin_args.workspace_variant are byte-identical across cells; only `benchmark.tasks[0]` differs — check whether this affects the sealed-hash computation empirically). Verify: `grep "sealed_hash:" examples/specs/goal1/direct-minimal/*.frozen.yaml | awk '{print $NF}' | sort -u | wc -l` returns `1` IF tasks doesn't enter the seal; `12` if it does. Document whichever in T10.
  - Each frozen spec contains `experiment_meta.paper_baseline.name: direct` and `value: 0.4376` (pass-through). Verify: `grep -A2 "paper_baseline:" examples/specs/goal1/direct-minimal/*.frozen.yaml` shows `name: direct` + `value: 0.4376` per file.
  - Freeze CAS populated: `ls "$RAZORBACK_FREEZE_DIR"` shows at least one new sealed_hash subdir.
- **Spec §-cite:** Entity AC-2 freeze, AC-6 provenance.

### T4 — `rk run --explain` preflight on all 12 frozen specs

- **Goal:** Per entity AC-2: confirm `reasoning_effort: xhigh` threads through to resolved kwargs, `plugin: dab` resolves, `workspace_variant: direct-minimal` is in plugin_args, for ALL 12 cells. Catch k4-class regressions BEFORE T5 spends API tokens.
- **Loop:**
  ```bash
  cd /Users/clkao/git/razorback
  export RAZORBACK_FREEZE_DIR=/Users/clkao/git/razorback/_runs/_razorback-freeze
  OUT=docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/per-cell-preflight
  mkdir -p "$OUT"
  fail=0
  for spec in examples/specs/goal1/direct-minimal/*.frozen.yaml; do
    name=$(basename "$spec" .frozen.yaml)
    uv run rk run "$spec" --explain --explain-format json \
        > "$OUT/${name}-explain.json" 2> "$OUT/${name}-explain.stderr" \
        || { echo "EXPLAIN FAILED: $spec" >&2; fail=$((fail+1)); }
  done
  echo "explain failures: $fail"
  ```
- **Field-path discovery (do this empirically on the first cell):**
  ```bash
  jq 'paths(scalars) | select(.[-1] == "reasoning_effort")' \
      "$OUT/bookreview-explain.json"
  jq 'paths(scalars) | select(.[-1] == "workspace_variant")' \
      "$OUT/bookreview-explain.json"
  jq 'paths(scalars) | select(.[-1] == "plugin")' \
      "$OUT/bookreview-explain.json"
  ```
  Then use the dotted paths the queries return for the per-cell assertions. **Do NOT hard-code a path the entity doesn't pin.**
- **Per-cell assertions (using the paths discovered above):**
  ```bash
  for j in "$OUT"/*-explain.json; do
    # Assert reasoning_effort: xhigh somewhere in the resolved kwargs.
    jq -e '.. | objects | select(.reasoning_effort? == "xhigh")' "$j" > /dev/null \
      || { echo "MISSING reasoning_effort=xhigh: $j"; exit 1; }
    # Assert plugin: dab.
    jq -e '.. | objects | select(.plugin? == "dab")' "$j" > /dev/null \
      || { echo "MISSING plugin=dab: $j"; exit 1; }
    # Assert workspace_variant: direct-minimal.
    jq -e '.. | objects | select(.workspace_variant? == "direct-minimal")' "$j" > /dev/null \
      || { echo "MISSING workspace_variant=direct-minimal: $j"; exit 1; }
  done
  ```
- **Commit:** Stage the 12 `*-explain.json` files (the `.stderr` files only if non-empty); commit message `goal1-direct-minimal: rk run --explain preflight evidence (12/12)`.
- **Spec §-cite:** Entity AC-2 verification (all three sub-clauses).

### T5 — T0 mechanism-smoke gate (bookreview cell solo, end-to-end)

**This is the smallest end-to-end exercise of the riskiest contract per CL's "Validating new mechanisms" rule — Task 0 in the captain's hint #3.** Catches direct-minimal-vs-claude-cli-vs-minimal-README mismatch BEFORE the full matrix burns 2–3 hours.

- **Command:**
  ```bash
  export RAZORBACK_FREEZE_DIR=/Users/clkao/git/razorback/_runs/_razorback-freeze
  export DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data
  # CLAUDE_CODE_OAUTH_TOKEN sourced from ~/.claude/benchmark-token by the driver.
  bash examples/drivers/dab-paper-matrix.sh \
      --variants direct-minimal \
      --datasets bookreview \
      --output-dir _runs/goal1-direct-minimal-opus47-xhigh \
      --max-cell-budget-usd 10.0
  ```
- **Wallclock budget:** ~5–10 min (bookreview is the cheapest cell per d8's cycle-1 ledger; comparable here).
- **Pass criteria (ALL must hold):**
  1. `_runs/goal1-direct-minimal-opus47-xhigh/direct-minimal/bookreview/*/*/result.json` exists.
  2. `result.json` parses; `stats.n_completed_trials >= 1` and `stats.n_errored_trials == 0`.
  3. The trial's `events.jsonl` (or harbor's `agent/claude-code.txt`) shows at least one `assistant` event with a `tool_use` invoking `Bash` or `Read` — i.e., the agent engaged with the workspace from the minimal README.
  4. The trial's `steps/main/verifier/test-stdout.txt` exists and does NOT contain `ModuleNotFoundError: common_scaffold` (k4-era verifier fix).
  5. `score.json` exists; `constant_source == "spec.frontmatter"`; `name == "direct"`; `value == 0.4376` (proves T2's paper_baseline injection round-trips through freeze + score auto-pull).
  6. `audit.json` exists; `summary.clean >= 1`; `summary.tainted == 0`.
- **Hard-blocker conditions (escalate to captain at impl-stage gate; do NOT widen scope):**
  - The agent never engages with Bash/Read tools (minimal README didn't give the agent enough to engage — this is the central direct-minimal failure mode the captain wants measured).
  - The verifier reports a structural mismatch (README's answer schema vs what the agent wrote).
  - `result.json` missing despite `rc == 0` (dispatch shape broken).
  - `score.json` shows `constant_source == "cli"` or missing the `value: 0.4376` — means T2 didn't round-trip through freeze.
- **Note on (1):** "Agent never engages tools" is a hard-blocker for the dispatch shape, not for the science. If the agent DOES engage tools but answers wrong, that's a valid scientific result (low direct-minimal score) — the matrix continues. The blocker is mechanism, not headline.
- **Spec §-cite:** Entity AC-3 + entity test-plan "Smoke first".

### T6 — Full 12-cell dispatch

- **Command:**
  ```bash
  export RAZORBACK_FREEZE_DIR=/Users/clkao/git/razorback/_runs/_razorback-freeze
  export DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data
  bash examples/drivers/dab-paper-matrix.sh \
      --variants direct-minimal \
      --output-dir _runs/goal1-direct-minimal-opus47-xhigh \
      --max-cell-budget-usd 10.0 \
      --continue-on-fail
  ```
- **Idempotence:** the bookreview cell from T5 is preserved (driver's `result.json`-based skip at `dab-paper-matrix.sh:115-139`). Net new work is 11 cells.
- **Failure containment:** `--continue-on-fail` is mandatory. Every cell gets its chance; `dispatch-ledger.tsv` pins which failed.
- **Per-cell artifacts** (under `_runs/goal1-direct-minimal-opus47-xhigh/direct-minimal/<dataset>/`):
  - `dispatch.log` — `rk run` stdout/stderr.
  - `<run-name>/<job-name>/result.json` — per-trial reward stats.
  - `<run-name>/<job-name>/summary.json` — sealed-hash + cost summary.
  - `<run-name>/<job-name>/audit.json` — `rk audit --policy strict --format json` (driver line `:225`).
  - `<run-name>/<job-name>/score.json` — `rk score --format json` (driver line `:258`; auto-pulls `direct=0.4376` from frozen spec frontmatter).
  - `<run-name>/<job-name>/steps/main/verifier/{test-stdout.txt, reward_per_query.json}`.
  - `budget.json` — per-cell running budget.
- **Matrix-wide artifacts** (under `_runs/goal1-direct-minimal-opus47-xhigh/`):
  - `dispatch-ledger.tsv` — one row per cell.
  - `dispatch-failures.tsv` — appended for any non-zero exit.
- **Wallclock estimate:** ~2–3 hours total at `query_mode: batch` + opus-4.7 + xhigh, per the entity test plan. Direct-minimal should be comparable to or slightly faster than direct-structured (no procedure prompt → fewer tokens up front, but the agent may flail more without structural guidance — could cancel out). d8's 1.85h spacedock run is the rough upper bound.
- **Dispatch as long-running command:** Implementation stage MUST background (`run_in_background: true`) and poll `dispatch-ledger.tsv` for progress via `BashOutput`, per the ensign-shared-core background-bash discipline.
- **Spec §-cite:** Entity AC-3.

### T7 — Per-cell artifact verification

- **Goal:** Confirm AC-3 quantitatively before running the aggregator.
- **Commands:**
  ```bash
  ROOT=_runs/goal1-direct-minimal-opus47-xhigh/direct-minimal
  find "$ROOT" -name result.json      | wc -l    # 12 (or document gaps in T10)
  find "$ROOT" -name summary.json     | wc -l    # 12
  find "$ROOT" -name score.json       | wc -l    # 12 (failed cells emit no score.json)
  find "$ROOT" -name audit.json       | wc -l    # 12
  find "$ROOT" -name provenance.yaml  | wc -l    # 12
  for rj in $(find "$ROOT" -name result.json); do
    python3 -c "import json; b=json.load(open('$rj')); s=b['stats']; print('$rj', s['n_completed_trials'], s['n_errored_trials'])"
  done
  column -t -s$'\t' _runs/goal1-direct-minimal-opus47-xhigh/dispatch-ledger.tsv
  ```
- **Acceptance:** Per AC-3 — every cell that ran has `summary.json` + `provenance.yaml` + `result.json` + `reward_per_query.json` + `audit.json` + `score.json`; failed cells have rows in `dispatch-failures.tsv` and `status: run_failed`/`external-oracle-cheating`/etc. rows in `dispatch-ledger.tsv`. Failed cells do NOT block AC-5 — the aggregator handles partial coverage; the report's "Failure analysis" section enumerates them.
- **Spec §-cite:** Entity AC-3 verification.

### T8 — Audit verdict aggregation (AC-4)

- **Goal:** Confirm `clean` across the matrix; surface AGNEWS trace per k3 verifier shape.
- **Commands:**
  ```bash
  ROOT=_runs/goal1-direct-minimal-opus47-xhigh/direct-minimal
  for a in "$ROOT"/*/*/*/audit.json; do
    ds=$(basename "$(dirname "$(dirname "$(dirname "$a")")")")
    status=$(jq -r '.taint_status // (.summary | "clean=" + (.clean|tostring) + " tainted=" + (.tainted|tostring))' "$a")
    echo -e "${ds}\t${status}"
  done | tee /tmp/dm-audit-summary.txt

  # AGNEWS special-attention: confirm branch (a) declined load_dataset OR
  # branch (b) attempted-and-self-corrected per k3 verifier shape.
  AGNEWS_DIR=$(ls -d "$ROOT"/agnews/*/* 2>/dev/null | head -1)
  if [[ -n "$AGNEWS_DIR" ]]; then
    grep -E "load_dataset|datasets\.|hf://|from datasets" \
        "$AGNEWS_DIR/agent/claude-code.txt" "$AGNEWS_DIR/events.jsonl" 2>/dev/null \
        | head -10 || echo "AGNEWS: no load_dataset trace (branch a)"
  fi
  ```
- **Acceptance:** All 12 cells `clean` (taint_status or `tainted: 0`). AGNEWS trace classified branch (a) or (b). If any cell is `tainted`, the entity's verdict is REJECT — surface to captain immediately.
- **gv coverage gap:** Direct-minimal is claude-cli single-session (no subagent dispatch); `gv audit-scanner-subagent-jsonl-coverage` is backlog and IRRELEVANT to this entity. T10 documents this explicitly.
- **Spec §-cite:** Entity AC-4 (taint_status check) and AC-4 (AGNEWS classification).

### T9 — Captain-facing aggregator

- **Command:**
  ```bash
  uv run python examples/drivers/aggregate-goal1-scores.py \
      --matrix-root _runs/goal1-direct-minimal-opus47-xhigh \
      --out-dir _runs/goal1-direct-minimal-opus47-xhigh
  ```
- **Output:** `_runs/goal1-direct-minimal-opus47-xhigh/direct-minimal/aggregate-score.json` carries per-stratum + pooled binary + pooled per-query + **stratified-per-query mean** (`per_query_pass_at_1_mean_over_strata`), Wilson 95% CIs, and `against_constant` with `name=direct_baseline`, `value=0.4376`, `verdict`, `per_query_verdict` (aggregator hard-codes this for `direct-minimal` — independent of frontmatter auto-pull). The aggregator also emits empty/null aggregate-score.json for `spacedock/` and `direct-structured/` since the matrix-root has only direct-minimal populated — that's expected; ignore them.
- **Sanity check:** `jq '.against_constant' _runs/goal1-direct-minimal-opus47-xhigh/direct-minimal/aggregate-score.json` shows `name: "direct_baseline"`, `value: 0.4376`. The per-cell `score.json` files show `constant_source: "spec.frontmatter"`, `name: "direct"`, `value: 0.4376` — note the `name` differs (`direct_baseline` aggregator-side vs `direct` spec-side) because the spec value carries the entity's chosen name; the values must agree at `0.4376`. T10 documents this naming asymmetry.
- **Spec §-cite:** Entity AC-5 aggregate.

### T10 — Captain-facing report

- **File:** `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/report.md`
- **STRATIFIED ONLY in headline.** Pooled and binary numbers may appear in supplementary tables but the headline leads with stratified-per-query (`per_query_pass_at_1_mean_over_strata`). Captain standing directive.
- **Shape (mirrors 7q's `_archive/goal1-direct-structured-dab-opus47-xhigh.md` and 7q's report under `_evidence/`):**
  1. **Frontmatter + headline.**
     - `title: Goal 1 direct-minimal report (paper-comparable, opus-4.7 + xhigh + batch + N=1)`
     - `entity: docs/razorback-implementation/goal1-direct-minimal-dab-opus47-xhigh.md`
     - `date: YYYY-MM-DD`, `status: shipped|cycle-2-pending|...`
     - **Headline (one line):** `Direct-minimal stratified-per-query pass@1 = X across 12 dataset strata. Verdict vs paper direct_baseline=0.4376: <above|inside CI|below>.`
     - **One-line three-way context:** "This closes the three-way at opus-4.7 + xhigh + batch + N=1: spacedock (d8) = 0.7055, direct-structured (7q) = 0.6719, direct-minimal (this) = X."
  2. **Three-way comparison table** (lead the body with this — it's what the captain asked for):
     | Variant | Stratified pass@1 | Paper baseline | Verdict | Source |
     |---|---|---|---|---|
     | spacedock (d8) | 0.7055 | 0.577 | above | `_archive/goal1-rerun-headline-per-query-recompute.md` |
     | direct-structured (7q) | 0.6719 | 0.4376 | above | `_archive/goal1-direct-structured-dab-opus47-xhigh.md` |
     | **direct-minimal (this)** | **X** | 0.4376 | ? | this report |
  3. **Per-dataset table.** Columns: `dataset`, `n_total`, `n_pass` (binary), `reward` (continuous), `pass@1` (binary), `per_query_pass@1 (n_correct/n_total)`, `wilson_95ci` (per-query), `wallclock`, `verifier_ok`, `audit_status`. Pooled row at bottom showing BOTH the binary and per-query numbers. Mark the binary pooled row "(supplementary — not the headline)".
  4. **AC-6 — Provenance enumeration.** Two sub-tables, mirroring 7q's:
     - **Frozen-spec fields** (per-cell, from `*.frozen.yaml`): `dataset`, `sealed_hash`, `reasoning_effort`, `pin_model_version`, `model_resolved_version`, `experiment_meta.paper_baseline.{name, value}`. The `solver_workflow_content_hash` column is `null` for `claude-cli` (named in Deviations).
     - **Provenance.yaml fields** (per-cell from run-dir): `image_digest`, `agent_cli_hash`, `harness_git_sha`, `harbor_version`, `harbor_agent_kwargs_hash`, `unresolved`.
  5. **Freeze CAS check.** `RAZORBACK_FREEZE_DIR` value; `ls $RAZORBACK_FREEZE_DIR | wc -l`; cross-reference new sealed_hash subdir(s) against the frozen specs; note the sealed_hash cardinality finding from T3 (1 vs 12).
  6. **Cost ledger.** Sum the `cost_usd` column of `dispatch-ledger.tsv`; per-cell range; total. If telemetry is null (known harness gap), document it and note the budget gate did not trip.
  7. **Wallclock ledger.** Total wallclock; per-cell min/max; comparison vs entity estimate (2–3h).
  8. **Audit verdict block (AC-4).**
     - All 12 cells reporting `clean`; cite `taint_status` field per cell.
     - AGNEWS classification: branch (a) declined `load_dataset` OR branch (b) attempted-and-self-corrected (cite trace lines).
     - **gv coverage limitation:** "direct-minimal is claude-cli single-session — no subagent dispatch. The `gv audit-scanner-subagent-jsonl-coverage` backlog gap (scanner walks only outer `agent/claude-code.txt`, not `agent/sessions/projects/*/{uuid}.jsonl`) is structurally irrelevant to this entity. The audit verdict here is complete despite gv being unshipped."
  9. **Failure analysis.** Any rows from `dispatch-failures.tsv` with cell ID, exit code, first ~40 lines of `dispatch.log`. If zero failures, write "12/12 cells `status: ok`."
  10. **Deviations from plan.** Document:
      - `solver_workflow_content_hash` null-for-claude-cli expectation (AC-6 explicitly names this).
      - `_runs/` vs `$XDG_DATA_HOME` runs-dir relocation (captain-approved per d8/7q reports).
      - `DATAAGENTBENCH_DATA_ROOT` env-var requirement (captain-approved per d8/7q).
      - Cost-telemetry null (known harness gap).
      - `paper_baseline.name` naming asymmetry — spec-side `name: direct` vs aggregator-side `name: direct_baseline`; values agree at `0.4376`. Per-cell `score.json.constant_source == "spec.frontmatter"`.
      - If T3 found that `sealed_hash` varies across cells (because `benchmark.tasks[0]` is in the seal), name this — d8/7q's "byte-identical agent block" assumption may not hold the same way here.
  11. **Research signal interpretation (the captain-facing payoff):**
      - One short paragraph reading the three-way: does the procedure prompt in direct-structured provide measurable lift over direct-minimal? Does the spacedock crew loop provide measurable lift over either? At N=1 the three numbers are point estimates; significance claims require the per-stratum CI machinery the entity explicitly lists out-of-scope.
      - Cite the resume-hook from the entity verbatim.
  12. **Provenance.** Reducer source + commit SHA; matrix-execution source (this entity); date; this plan's path.
  13. **Artifact retention.** Per-cell mirror of `summary.json` + `provenance.yaml` + `result.json` + `score.json` + `audit.json` + `reward_per_query.json` to `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/cells/<dataset>/`. Full per-trial trajectories (events.jsonl, multi-MB) stay in `_runs/`.
  14. **Follow-ups suggested.** (a) Pairwise CI machinery for the three-way at N=1 (separate methodology entity, per entity "Out of scope"). (b) N=5 paper-grade reproduction (separate sibling). (c) Same harness gaps the d8/7q reports name (cost telemetry, gv subagent JSONL coverage if it ships).
- **Sanity-check before commit:**
  - Headline cites the stratified number (not pooled).
  - Three-way table cites 0.7055 and 0.6719 verbatim from the named archives.
  - Per-cell `score.json` `constant_source == "spec.frontmatter"` for 12/12 (T9's auto-pull worked).
  - Audit verdict block lists `clean` for 12/12.
- **Commit:** Stage the report + per-cell evidence mirror + (if not already) the T4 preflight evidence; commit message `goal1-direct-minimal: ship paper-comparable report (stratified-per-query=X vs paper=0.4376; three-way complete)`.
- **Spec §-cite:** Entity AC-3, AC-4, AC-5, AC-6.

---

## TDD checkpoints

- This plan has no RED→GREEN unit-test pair because no Python source is modified.
- T2 (paper_baseline injection) is a yaml edit; the verification commands in T2 (`grep -l … wc -l` and `python3 -c "yaml.safe_load(...)"`) are the equivalent of a green test.
- T4 (`rk run --explain`) is a static mechanism check at the dispatch layer: it proves the 12 frozen specs resolve correctly BEFORE T5 spends API tokens.
- T5 (bookreview smoke) is the runtime mechanism check — the smallest end-to-end exercise of the riskiest contract per CL's "Validating new mechanisms" rule. T5 MUST pass cleanly before T6.

---

## Risk register

| Risk | Mitigation |
|---|---|
| `claude-cli` agent kind cannot engage DBs from the **minimal** workspace README (the central direct-minimal risk: README is too sparse for the agent to figure out the DB path) | T5 (bookreview smoke) catches this in 5–10 min before T6 burns 2–3 hours. Hard-blocker → escalate to captain; do NOT widen scope by editing the `_DIRECT_MINIMAL` template. Measuring the gap is the science. |
| Agent engages tools but answers poorly across the matrix (e.g., stratified=0.20) | This is a valid scientific result, not a failure. Report writes `below` verdict; the three-way captain-reads spacedock=0.7055 vs direct-structured=0.6719 vs direct-minimal=0.20 (large gap). Plan does NOT branch on the headline value. |
| `DATAAGENTBENCH_DATA_ROOT` unset → all 12 cells fast-fail with LFS-pointer errors | T5 catches this in the first 60s. T6 inherits the export from the T5 shell. |
| Single cell burns $60+ | `--max-cell-budget-usd 10.0` per-cell cap (matrix-wide ceiling $120). |
| Matrix runs >3 hours | T6 dispatch is `--continue-on-fail`; the driver writes to `dispatch-ledger.tsv` after each cell; a session interruption is safe to resume via idempotence. |
| `--allow-missing` masks a real provenance gap | The `model_resolved_version` field is the only one expected missing pre-`rk run`; `rk run` populates it on the API call. T10's AC-6 enumeration confirms it's non-null in every cell's `provenance.yaml`. |
| T2's yaml edit breaks the spec parser (e.g., wrong indent) | The per-spec `python3 -c "yaml.safe_load(...)"` round-trip in T2's verification catches this; T3 freeze would also catch a structural break, but T2's verification catches it earlier without spending the freeze pre-flight cost. |
| `paper_baseline` doesn't round-trip through freeze | T5's `score.json.constant_source` field is the canary. If it's `"cli"` or missing, freeze stripped the field (regression in `src/razorback/provenance/freeze_cmd.py`'s pass-through). Hard-blocker; surface to captain. |
| Verifier `common_scaffold` import bug from d8 cycle 1 recurs | Fixed in `main` per d8 cycle 2. T5 cross-checks `test-stdout.txt`; T6 inherits. |
| Cost telemetry null (known harness gap) | Documented in T10 deviations; budget gate enforces independently via `--max-budget-usd-running`. |
| `gv audit-scanner-subagent-jsonl-coverage` backlog | Direct-minimal is claude-cli single-session — no subagent dispatch — the coverage gap is structurally irrelevant. T10 documents this explicitly. |
| Sealed_hash cardinality (one vs 12) | Empirical question per T3. Document whichever finding in T10; d8/7q assumed byte-identical agent block, but direct-minimal's plugin_args may serialize `tasks[0]` into the seal differently. Not a hard-blocker either way. |

---

## Definition of done (plan-stage perspective)

The implementation stage signals done when:
- 12 source specs at `examples/specs/goal1/direct-minimal/*.yaml` carry `experiment_meta.paper_baseline: {name: direct, value: 0.4376}` (committed to `main`).
- 12 frozen specs exist at `examples/specs/goal1/direct-minimal/*.frozen.yaml` (host-local, gitignored), each carrying `reasoning_effort: xhigh`, `sealed_hash`, and `experiment_meta.paper_baseline`.
- 12 `rk run --explain` JSONs committed under `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/per-cell-preflight/`.
- 12 run-dirs at `_runs/goal1-direct-minimal-opus47-xhigh/direct-minimal/<dataset>/`, each with `result.json` + `summary.json` + `provenance.yaml` + `score.json` + `audit.json` + `reward_per_query.json` (failed cells documented in `dispatch-failures.tsv`).
- `_runs/goal1-direct-minimal-opus47-xhigh/direct-minimal/aggregate-score.json` exists with `against_constant.name=direct_baseline`, `value=0.4376`, and a non-null `per_query_pass_at_1_mean_over_strata`.
- `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/report.md` is committed with all 14 sections from T10; headline cites stratified-per-query (NOT pooled); three-way table cites 0.7055 + 0.6719 verbatim.
- Per-cell evidence mirror committed at `docs/razorback-implementation/_evidence/goal1-direct-minimal-v1/cells/<dataset>/`.
- `dispatch-ledger.tsv` shows 12 rows; either all `status: ok` OR every failed row has a documented failure-mode entry in the final report.
- All 12 cells `clean` in the audit block (or the entity verdict is REJECT and surfaced to captain).
