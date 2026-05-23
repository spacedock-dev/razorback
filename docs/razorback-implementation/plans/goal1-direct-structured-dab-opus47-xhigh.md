# Goal 1 Sibling — DAB Direct-Structured Matrix, opus-4.7 + reasoning_effort=xhigh — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/goal1-direct-structured-dab-opus47-xhigh.md`

**Goal:** Produce a paper-comparable direct-structured baseline against the post-sprint canonical infrastructure (per-query `rk score`, runs_dir outside worktree, freeze CAS, `kind: claude-cli`, `dataset: dab@1.0`, `workspace_variant: direct-structured`) with `model: claude-opus-4-7`, `reasoning_effort: xhigh`, `query_mode: batch`, `concurrency.trials: 1`, N=1 trial per cell across all 12 DAB datasets. Captain-facing headline compares to `paper direct_baseline = 0.4376` (`examples/drivers/dab-paper-matrix.sh:196`).

**This is a research RUN entity, not a feature change.** No source code is modified. The 12 direct-structured specs already exist on disk from commit `a6ab344` (regen: 36 dab paper matrix specs with reasoning_effort: xhigh) with `kind: claude-cli`, `model: claude-opus-4-7`, `reasoning_effort: xhigh`, `workspace_variant: direct-structured`, `query_mode: batch`. The matrix driver natively supports `--variants direct-structured`. The plan-stage worker pre-paid the mechanism-check bill by tracing the `direct-structured` path end-to-end through the source (see "Mechanism check" below). Implementation stage is freeze + dispatch + aggregate + report.

**Tech Stack:** Python 3.12, bash. No new runtime dependencies. No source-tree edits.

---

## AC ↔ Task map

| AC | Description | Tasks |
|---|---|---|
| AC-1 | 12 direct-structured specs carry `agent.kind: claude-cli`, `agent.model: claude-opus-4-7`, `agent.reasoning_effort: xhigh`, `benchmark.kind: harbor_dab`, `benchmark.dataset: dab@1.0`, `benchmark.workspace_variant: direct-structured`, `benchmark.query_mode: batch`, `trials: 1`. **Already on disk at commit `a6ab344`.** | T1 (verify-shape; no regen) |
| AC-2 | Each spec freezes cleanly: `*.frozen.yaml` + `provenance.yaml` adjacent, no `SpecError` / `AliasDriftError` | T2 (freeze loop) |
| AC-3 | Full 12-cell run completes; each cell produces a run-dir with `summary.json`, `provenance.yaml`, per-trial `result.json` + `reward_per_query.json`, and `score.json`; `--continue-on-fail` keeps the matrix going through individual cell failures; `dispatch-ledger.tsv` records `status: ok` for all 12 (or documents failures per cell) | T3 (dry-run smoke), T4 (mechanism-smoke gate: bookreview cell solo), T5 (full 12-cell dispatch), T6 (per-cell artifact verification) |
| AC-4 | Per-query pooled pass@1 + per-cell sub-table + Wilson CI + verdict against `paper direct_baseline = 0.4376`; captain-facing report at `docs/razorback-implementation/_evidence/goal1-direct-structured-dab-opus47-xhigh-report.md` mirrors the spacedock report's shape | T7 (aggregator run), T8 (captain-facing report) |
| AC-5 | Per-cell `provenance.yaml` records `solver_workflow_content_hash` (may be null for `claude-cli` agent kind — that's expected and named in the deviations section), `harbor_agent_kwargs_hash`, `reasoning_effort: xhigh`, resolved opus-4.7 model version (`pin_model_version: true`); re-run from same spec hits existing freeze CAS subdir | T2 (freeze-time fields), T8 (final-report provenance enumeration) |

**Riskiest contract first (the mechanism gate):** `agent.kind: claude-cli` + `benchmark.workspace_variant: direct-structured` is a well-trodden path on the rest of the harbor surface, but this entity is the first goal1 paper-comparable matrix run for that combination at opus-4.7+xhigh. The plan-stage worker did the static-trace check (below); the implementation stage adds a runtime mechanism-smoke gate (Task 4) on the smallest cell (`bookreview`) BEFORE the full 12-cell dispatch burns wallclock. If the smoke cell engages DBs and produces a non-empty `result.json`, the matrix is safe to dispatch.

---

## Mechanism check — DONE in plan stage (do not redo)

The plan-stage worker performed this static-source trace on the `direct-structured` workspace variant before writing the plan:

1. **WORKSPACE_VARIANTS enumeration.** `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py:7` declares `WORKSPACE_VARIANTS = ("spacedock", "direct-structured", "direct-minimal")` — `direct-structured` is first-class.
2. **README template exists.** `packages/razorback-plugin-dab/tests/unit/test_workspace_readme_variants.py:test_direct_structured_has_layout_block` asserts the rendered README contains `Workspace layout`, `db_config.yaml`, `dab-postgres`, and the `answers.json` output contract. Test is green on main.
3. **Dispatcher threads the variant.** `src/razorback/translate.py:381` passes `--workspace-variant spec.benchmark.workspace_variant` directly into the plugin's `razorback-plugin-dab generate` CLI invocation; no special-case branch needed in `translate.py` for direct-structured vs spacedock.
4. **Spec shape verified.** `examples/specs/goal1/direct-structured/bookreview.yaml` carries the post-sprint canonical shape (`kind: claude-cli`, `dataset: dab@1.0`, `workspace_variant: direct-structured`, `query_mode: batch`, `reasoning_effort: xhigh`, `trials: 1`, `tools_allowed: [Bash, Read, Write, Edit, Glob, Grep]`).
5. **Matrix driver supports the variant.** `examples/drivers/dab-paper-matrix.sh:14, 29` declare `direct-structured` in the default-variants tuple; `:196` maps it to `target="direct_baseline=0.4376"` for per-cell `rk score --against-constant`. The driver loop at `:107` and the freeze-spec validation at `:87-100` are variant-agnostic.
6. **Generator already at xhigh.** `examples/drivers/generate-dab-paper-matrix-specs.py:54, 88, 142` accepts `--reasoning-effort` and injects it; the 12 specs on disk were regenerated with `--reasoning-effort xhigh` at commit `a6ab344`. **No regen needed.**

**Verdict:** The direct-structured path is a well-trodden surface; the spec shape is post-sprint canonical and already at `xhigh`; the matrix dispatcher routes it without special-casing. Implementation stage starts at freeze (T2). Runtime mechanism-smoke at the `bookreview` cell (Task 4) catches any DB-access or workspace-README assumption mismatch BEFORE the full matrix burns 2–3 hours.

---

## Surface map — what changes

| File | Change |
|---|---|
| `examples/specs/goal1/direct-structured/*.frozen.yaml` *(12 files, host-specific, gitignored)* | Emitted by T2 freeze loop. Carry `sealed_hash`, plus the `claude-cli`-relevant subset of provenance fields. |
| `examples/specs/goal1/direct-structured/provenance.yaml` *(1 file, last-write-wins sidecar)* | Emitted alongside the last frozen spec. |
| `_runs/goal1-direct-structured-opus47-xhigh/direct-structured/<dataset>/<run>/<job>/{result.json,summary.json,provenance.yaml,score.json,audit.json,events.jsonl,dispatch.log}` *(12 cells)* | Emitted by T5 (matrix dispatch). Out-of-tree, gitignored. |
| `_runs/goal1-direct-structured-opus47-xhigh/dispatch-ledger.tsv` | Emitted by T5; one row per cell with `variant`, `dataset`, `spec_frozen`, `runs_dir`, `status`, `exit_code`, `cost_usd`. |
| `_runs/goal1-direct-structured-opus47-xhigh/direct-structured/aggregate-score.json` | Emitted by T7 (aggregator). Per-dataset Wilson CIs + pooled per-query pass@1 + against-constant verdict vs `paper=0.4376`. |
| `docs/razorback-implementation/_evidence/goal1-direct-structured-dab-opus47-xhigh-report.md` *(new)* | Final captain-facing report emitted by T8 mirroring the spacedock report's shape. |
| `docs/razorback-implementation/_evidence/goal1-direct-structured-cells/<dataset>/{summary.json,result.json,reward_per_query.json,score.json,provenance.yaml}` *(12 dirs)* | Per-cell evidence mirror committed to git (file sizes 5–500MB stay in `_runs/`). |

## Surface map — what stays

- All Python source under `src/razorback/` and `packages/razorback-plugin-dab/src/`. This is a research run, not a code change.
- `examples/specs/goal1/direct-structured/*.yaml` — 12 source specs unchanged at commit `a6ab344`.
- `examples/drivers/dab-paper-matrix.sh` — driver unchanged.
- `examples/drivers/aggregate-goal1-scores.py` — aggregator unchanged; it walks all three variants and emits a per-variant `aggregate-score.json`. T7 reads only the `direct-structured/aggregate-score.json` it emits.
- `src/razorback/runs/aggregate.py:reduce_per_query_stratified` — canonical per-query reducer (post-`1s`/`d8`) consumed by the aggregator.

---

## Spec ambiguity & guardrails to flag before T1

1. **N=1 vs N=5.** Entity is explicit: N=1, `concurrency.trials: 1`, batch mode, direct-structured variant only. Do not promote to N=5; that's a sibling follow-up entity per the entity's "Out of scope" section.
2. **Budget ceiling.** Entity estimates `~$25-40` total at the per-cell budget cap. The plan uses `--max-cell-budget-usd 10.0` (matches the spacedock plan's cap; keeps a single runaway cell from burning $60+). Matrix-wide implicit ceiling is `12 × $10 = $120`.
3. **Variant scoping.** The matrix driver defaults to all 3 variants × 12 datasets = 36 cells. T5 MUST pass `--variants direct-structured` to scope to 12 cells.
4. **runs_dir + freeze_dir location.** Per the spacedock report's captain-approved deviation #1, sandbox blocks `$XDG_DATA_HOME` and Colima virtiofs requires runs-dir under `/Users/...`. This plan uses the same convention: `_runs/goal1-direct-structured-opus47-xhigh/` for runs (matches the entity body's path) and `_runs/_razorback-freeze/` for the freeze CAS (`RAZORBACK_FREEZE_DIR` env var). Project-root `_runs/` is gitignored.
5. **DATAAGENTBENCH_DATA_ROOT.** Per the spacedock report's deviation #3, the dispatcher's env MUST include `DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data`. Without it, all 12 cells fast-fail with `dataset X not hydrated, found LFS pointer`. T4 (smoke) catches this in the first 60s of the first cell if it's misset; T5 inherits the export.
6. **API auth.** The dispatcher reads `$CLAUDE_CODE_OAUTH_TOKEN` (or `~/.claude/benchmark-token`). T4 fails-fast if neither is present; do NOT run on a free-tier session.
7. **Hard-blocker condition.** Per entity dispatch: if T4 (bookreview smoke) reveals the `claude-cli` agent kind cannot engage the DBs from the direct-structured workspace README (e.g., the README assumes a DB-access path the dispatcher doesn't provide), surface to captain at the impl-stage gate. Do NOT silently widen scope by editing the README template or the dispatcher.

---

## Tasks

### T1 — Verify the 12 specs satisfy AC-1 (no regen)

- **Goal:** Confirm the specs on disk at commit `a6ab344` carry the required shape; no edit needed.
- **Commands:**
  ```bash
  cd /Users/clkao/git/razorback
  ls examples/specs/goal1/direct-structured/*.yaml | wc -l            # 12
  grep -l "kind: claude-cli" examples/specs/goal1/direct-structured/*.yaml | wc -l    # 12
  grep -l "model: claude-opus-4-7" examples/specs/goal1/direct-structured/*.yaml | wc -l    # 12
  grep -l "reasoning_effort: xhigh" examples/specs/goal1/direct-structured/*.yaml | wc -l   # 12
  grep -l "workspace_variant: direct-structured" examples/specs/goal1/direct-structured/*.yaml | wc -l  # 12
  grep -l "dataset: dab@1.0" examples/specs/goal1/direct-structured/*.yaml | wc -l    # 12
  grep -l "query_mode: batch" examples/specs/goal1/direct-structured/*.yaml | wc -l   # 12
  ```
- **Expected:** every command returns `12`. If any return `< 12`, surface to captain; do NOT silently regen (the spacedock plan's regen path required a generator change too; this plan inherits the post-sprint shape directly).
- **Spec §-cite:** Entity AC-1 verification commands.

### T2 — Freeze 12 direct-structured specs

- **Command (per spec):** `uv run rk freeze <spec> --allow-missing`
- **Loop:**
  ```bash
  cd /Users/clkao/git/razorback
  export RAZORBACK_FREEZE_DIR=/Users/clkao/git/razorback/_runs/_razorback-freeze
  mkdir -p "$RAZORBACK_FREEZE_DIR"
  fail=0
  for spec in examples/specs/goal1/direct-structured/*.yaml; do
      uv run rk freeze "$spec" --allow-missing || { echo "FREEZE FAILED: $spec" >&2; fail=$((fail+1)); }
  done
  echo "freeze failures: $fail"
  ```
  Note: `--allow-missing` is required because `pin_model_version: true` resolves only at `rk run` time on a live API call; freeze pre-flight leaves `model_resolved_version` unfilled and tags provenance accordingly. This matches the spacedock plan's T3.
- **Verification:**
  - `ls examples/specs/goal1/direct-structured/*.frozen.yaml | wc -l` returns `12`.
  - For each frozen spec, `grep -E "reasoning_effort: xhigh|sealed_hash:" <spec>.frozen.yaml` returns at least two matching lines.
  - `fail == 0`.
  - All 12 frozen specs share the same `sealed_hash` (agent block is byte-identical across cells; only `benchmark.datasets[0]` differs). Verify: `grep "sealed_hash:" examples/specs/goal1/direct-structured/*.frozen.yaml | awk '{print $NF}' | sort -u | wc -l` returns `1`.
  - Freeze CAS populated: `ls "$RAZORBACK_FREEZE_DIR" | wc -l` returns at least `1` new sealed_hash subdir.
- **Spec §-cite:** Entity AC-2, AC-5.

### T3 — Dry-run smoke against the matrix driver

- **Command:**
  ```bash
  bash examples/drivers/dab-paper-matrix.sh --dry-run \
      --variants direct-structured \
      --output-dir _runs/goal1-direct-structured-opus47-xhigh
  ```
- **Expected:** Prints 12 lines, one per `direct-structured/<dataset>`, in the order: agnews, bookreview, crmarenapro, DEPS_DEV_V1, GITHUB_REPOS, googlelocal, music_brainz_20k, PANCANCER_ATLAS, PATENTS, stockindex, stockmarket, yelp. Prints `Total cells: 12 (expect 3 x 12 = 36 with defaults)`. Exits 0. No `missing frozen spec` warnings.
- **Spec §-cite:** Entity AC-3 dispatch shape.

### T4 — Mechanism-smoke gate (bookreview cell solo, end-to-end)

**This is the smallest end-to-end exercise of the riskiest contract per CL's "Validating new mechanisms" rule — Task 0 in the captain's hint #2.** It catches any direct-structured-vs-claude-cli mismatch BEFORE the full matrix burns 2–3 hours.

- **Command:**
  ```bash
  export RAZORBACK_FREEZE_DIR=/Users/clkao/git/razorback/_runs/_razorback-freeze
  export DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data
  # CLAUDE_CODE_OAUTH_TOKEN sourced from ~/.claude/benchmark-token by the driver.
  bash examples/drivers/dab-paper-matrix.sh \
      --variants direct-structured \
      --datasets bookreview \
      --output-dir _runs/goal1-direct-structured-opus47-xhigh \
      --max-cell-budget-usd 10.0
  ```
- **Wallclock budget:** ~5–10 min (bookreview is the cheapest cell per spacedock's cycle-1 ledger: 161s for spacedock; direct should be comparable or faster).
- **Pass criteria (ALL must hold):**
  1. `_runs/goal1-direct-structured-opus47-xhigh/direct-structured/bookreview/*/*/result.json` exists.
  2. `result.json` parses as JSON; `stats.n_completed_trials >= 1` and `stats.n_errored_trials == 0`.
  3. The trial's `events.jsonl` (or harbor's `claude-code.txt`) shows at least one `assistant` event with a `tool_use` block invoking `Bash` or `Read` — i.e., the agent engaged with the workspace.
  4. The trial's `steps/main/verifier/test-stdout.txt` exists (verifier ran) and does NOT contain `ModuleNotFoundError: common_scaffold` (the verifier-fix from commit `d6fbfdd` is in main).
  5. `score.json` exists and the `--against-constant direct_baseline=0.4376` verdict line is present.
- **Hard-blocker conditions (escalate to captain at impl-stage gate; do NOT widen scope):**
  - The agent never engages with Bash/Read tools (workspace README isn't getting through, or DB-access path mismatch).
  - The verifier reports a structural mismatch between the README's promised answer schema and what the agent emitted (README assumption broken).
  - `result.json` is missing despite `rc == 0` (dispatch shape broken for `claude-cli` + `direct-structured`).
- **Spec §-cite:** Entity AC-3 + entity test-plan "Smoke (mechanism gate)".

### T5 — Full 12-cell dispatch

- **Command:**
  ```bash
  export RAZORBACK_FREEZE_DIR=/Users/clkao/git/razorback/_runs/_razorback-freeze
  export DATAAGENTBENCH_DATA_ROOT=/Users/clkao/git/dataagentbench/data
  bash examples/drivers/dab-paper-matrix.sh \
      --variants direct-structured \
      --output-dir _runs/goal1-direct-structured-opus47-xhigh \
      --max-cell-budget-usd 10.0 \
      --continue-on-fail
  ```
- **Idempotence:** the bookreview cell from T4 is preserved (driver's `result.json`-based skip at `dab-paper-matrix.sh:116-139` recognizes it as completed). Net new work is 11 cells.
- **Failure containment:** `--continue-on-fail` is mandatory. Without it, the first failing cell stops the matrix; the captain-facing aggregator gets a partial result that doesn't distinguish cell-specific from systemic failure. With it, every cell gets its chance and `dispatch-ledger.tsv` pins which failed.
- **Per-cell artifacts** (written to `_runs/goal1-direct-structured-opus47-xhigh/direct-structured/<dataset>/`):
  - `dispatch.log` — `rk run` stdout/stderr.
  - `<run-name>/<job-name>/result.json` — per-trial reward stats.
  - `<run-name>/<job-name>/summary.json` — sealed-hash + cost summary.
  - `<run-name>/<job-name>/audit.json` — `rk audit --policy strict --format json` (driver line `:190`).
  - `<run-name>/<job-name>/score.json` — `rk score --against-constant direct_baseline=0.4376 --format json` (driver line `:196, :200`).
  - `<run-name>/<job-name>/steps/main/verifier/{test-stdout.txt, reward_per_query.json}` — verifier output + per-query reward sidecar.
  - `budget.json` — `--max-budget-usd-running` per-cell tracking.
- **Matrix-wide artifacts** (written to `_runs/goal1-direct-structured-opus47-xhigh/`):
  - `dispatch-ledger.tsv` — one row per cell.
  - `dispatch-failures.tsv` — appended for any non-zero exit.
- **Wallclock estimate:** Per entity test plan, ~2–3 hours total at `query_mode: batch` + opus-4.7 + xhigh. Direct-structured tends to be faster than spacedock (no crew loop), so the spacedock run's 6675s (1.85h) is the rough upper bound. Implementation stage MUST dispatch as a long-running command (background or detached session) and poll `dispatch-ledger.tsv` for progress.
- **Spec §-cite:** Entity AC-3.

### T6 — Per-cell artifact verification

- **Goal:** Confirm AC-3 quantitatively before running the aggregator.
- **Commands:**
  ```bash
  ROOT=_runs/goal1-direct-structured-opus47-xhigh/direct-structured
  find "$ROOT" -name result.json    | wc -l    # 12 (or document gaps in T8)
  find "$ROOT" -name summary.json   | wc -l    # 12
  find "$ROOT" -name score.json     | wc -l    # 12 (failed cells emit no score.json)
  find "$ROOT" -name provenance.yaml | wc -l   # 12
  # Sanity: per-cell result.json parses + non-zero completed trials
  for rj in $(find "$ROOT" -name result.json); do
      python3 -c "import json; b=json.load(open('$rj')); s=b['stats']; print('$rj', s['n_completed_trials'], s['n_errored_trials'])"
  done
  # Ledger inspection
  column -t -s$'\t' _runs/goal1-direct-structured-opus47-xhigh/dispatch-ledger.tsv
  ```
- **Acceptance:** Per AC-3 — every cell that ran has `summary.json` + `provenance.yaml` + `result.json` + `reward_per_query.json`; cells that failed have a documented row in `dispatch-failures.tsv` and a `status: run_failed` row in `dispatch-ledger.tsv`. Failed cells do NOT block AC-4 — the aggregator handles partial coverage and the report's "Failure analysis" section enumerates them.
- **Spec §-cite:** Entity AC-3 verification.

### T7 — Captain-facing aggregator

- **Command:**
  ```bash
  uv run python examples/drivers/aggregate-goal1-scores.py \
      --matrix-root _runs/goal1-direct-structured-opus47-xhigh \
      --out-dir _runs/goal1-direct-structured-opus47-xhigh
  ```
- **Aggregator flag surface** (verified by `grep -n add_argument examples/drivers/aggregate-goal1-scores.py:218-228`):
  - `--matrix-root` (default `runs/goal1/matrix`): root containing `<variant>/<dataset>/<experiment>/<hash>/result.json`.
  - `--out-dir` (default `runs/goal1/matrix`): where to write per-variant `aggregate-score.json` and `matrix-summary.json`.
- **Output:** `_runs/goal1-direct-structured-opus47-xhigh/direct-structured/aggregate-score.json` carrying per-stratum + pooled binary + pooled per-query pass@1, Wilson 95% CIs, and `against_constant` block with `name=direct_baseline`, `value=0.4376`, `verdict`, `per_query_verdict`. The aggregator emits aggregate-score.json for all three variants but `spacedock/` and `direct-minimal/` will be empty/null per `aggregate_variant`'s missing-cell handling — that's expected.
- **Spec §-cite:** Entity AC-4 aggregate.

### T8 — Captain-facing report

- **File:** `docs/razorback-implementation/_evidence/goal1-direct-structured-dab-opus47-xhigh-report.md`
- **Shape (mirrors `goal1-rerun-dab-spacedock-opus47-xhigh-report.md`):**
  1. **Frontmatter + headline.** `title:`, `entity:`, `date:`, `status:`. Headline: `Direct-structured pooled per-query pass@1 = X (95% Wilson CI [lo, hi]) across <Q> query cells over <S> dataset strata. Verdict vs paper direct_baseline=0.4376: <above|inside CI|below>.` Plus a one-line context: this is the paper-comparable direct baseline against which spacedock's `0.722 [0.591, 0.824]` (from `d8`) can be read; if direct ≥ spacedock, the crew loop's contribution is questioned; if direct < spacedock, the loop earns its keep.
  2. **Per-dataset table.** Columns: `dataset`, `n_total`, `n_pass` (binary), `reward` (continuous), `pass@1` (binary), `per_query_pass@1 (n_correct/n_total)`, `wilson_95ci` (per-query), `wallclock`, `verifier_ok`, `against paper=0.4376`. Pooled row at bottom showing both the binary and per-query numbers (the spacedock report's `pooled` row is the template).
  3. **AC-5 — Provenance enumeration.** Two sub-tables, mirroring the spacedock report:
     - **Frozen-spec fields** (per-cell, from `examples/specs/goal1/direct-structured/<dataset>.frozen.yaml`): `dataset`, `sealed_hash`, `reasoning_effort`, `pin_model_version`, `model_resolved_version`. Note: the `spacedock_skill_version` column from the spacedock report DOES NOT apply to `claude-cli` agent kind — name this deviation in the report's "Deviations" section.
     - **Provenance.yaml fields** (per-cell from run-dir): `image_digest`, `agent_cli_hash`, `harness_git_sha`, `harbor_version`, `unresolved`. Note: `solver_workflow_hash` may be `null` for `claude-cli` (no spacedock_solver wrapper) — this is expected and is part of the deviations.
  4. **Freeze CAS check.** `RAZORBACK_FREEZE_DIR` value; `ls $RAZORBACK_FREEZE_DIR | wc -l` output; cross-reference the single new `sealed_hash` subdir against the frozen specs.
  5. **Cost ledger.** Sum the `cost_usd` column of `dispatch-ledger.tsv` if populated; per-cell range; total. If telemetry is null (per the spacedock report's deviation #5, this is a known harness gap), document it and note the budget gate did not trip.
  6. **Wallclock ledger.** Total wallclock across 12 cells; per-cell min/max; comparison against the entity's estimate (2–3h).
  7. **Failure analysis.** Any rows from `dispatch-failures.tsv` with cell ID, exit code, first ~40 lines of matching `dispatch.log`. If zero failures, write "12/12 cells `status: ok`."
  8. **Deviations from plan.** Document any deviations encountered, including:
     - The `solver_workflow_hash`/`spacedock_skill_version` null-for-claude-cli expectation (entity AC-5 explicitly names this).
     - The `_runs/` vs `$XDG_DATA_HOME` runs-dir relocation (already captain-approved per the spacedock report).
     - The `DATAAGENTBENCH_DATA_ROOT` env-var requirement (already captain-approved per the spacedock report).
     - Cost-telemetry null (already captain-approved as a known gap).
  9. **Provenance.** Reducer source (`src/razorback/runs/aggregate.py:reduce_per_query_stratified` at commit `f76443b`); fixture source (12 cell run-dirs); matrix-execution source (this entity); date.
  10. **Artifact retention.** Per-cell mirror of `summary.json` + `provenance.yaml` + `result.json` + `score.json` + `reward_per_query.json` to `docs/razorback-implementation/_evidence/goal1-direct-structured-cells/<dataset>/`. Full per-trial trajectories (jsonl logs, multi-MB) stay in `_runs/`.
  11. **Follow-ups suggested.** (a) The natural head-to-head report (spacedock vs direct-structured at same point) the entity's resume-hook calls for. (b) Same harness gaps the spacedock report names: cost telemetry, N=5 reproduction.
- **Sanity-check before commit:**
  - Headline `value=0.4376` and `name=direct_baseline` match `dab-paper-matrix.sh:196`.
  - Per-cell rows match `dispatch-ledger.tsv` count.
  - Verdict (`above|inside CI|below`) derived from the per-query Wilson 95% CI against `0.4376`.
- **Spec §-cite:** Entity AC-3, AC-4, AC-5.

---

## TDD checkpoints

- This plan has no RED→GREEN unit-test pair because no source is being modified. The only mechanism-equivalent of TDD is **T4 (bookreview smoke)** — the smallest end-to-end exercise of the riskiest contract before the full matrix runs. T4 MUST pass cleanly before T5.
- T3 (dry-run) is a second mechanism check at the dispatch layer: it proves the 12 frozen specs are discoverable by the dispatcher BEFORE T4 spends API tokens on a misconfigured cell.

---

## Risk register

| Risk | Mitigation |
|---|---|
| `claude-cli` agent kind cannot engage DBs from the direct-structured workspace README at runtime | T4 (bookreview smoke) catches this in 5–10 min before T5 burns 2–3 hours. Hard-blocker → escalate to captain at impl-stage gate; do NOT silently widen scope by editing README templates. |
| `DATAAGENTBENCH_DATA_ROOT` unset → all 12 cells fast-fail with LFS-pointer errors | T4 catches this in the first 60s. T5 inherits the export from the T4 shell session. |
| Single cell burns $60+ | `--max-cell-budget-usd 10.0` per-cell cap. |
| Matrix runs >3 hours | T5 dispatch is `--continue-on-fail`; the dispatcher writes to `dispatch-ledger.tsv` after each cell, so a session interruption is safe to resume via idempotence (T5 re-invocation skips completed cells). |
| `--allow-missing` masks a real provenance gap | The `model_resolved_version` field is the only one expected missing pre-`rk run`; it gets populated by `rk run` when the API call resolves the canonical model SHA. T8's AC-5 enumeration confirms it's non-null in every cell's `provenance.yaml`. |
| Idempotence false-positive (stale `result.json` from a prior dispatch causes T5 to skip a cell that should re-run) | T5 dispatches into a fresh `_runs/goal1-direct-structured-opus47-xhigh/` subdir that did not exist before this entity. No cross-contamination with prior goal1 / goal1-resume / goal1-rerun-spacedock runs. The bookreview cell from T4 IS the intended skip — same matrix root, same spec hash, no contamination. |
| Verifier `common_scaffold` import bug from spacedock cycle 1 recurs | Fixed in `main` at commit `d6fbfdd` and verified in the spacedock cycle-2 re-run (zero `ModuleNotFoundError` across all 4 re-executed cells). T4 cross-checks `test-stdout.txt` for the regex; T5 inherits. |
| Cost telemetry null (known harness gap) | Documented in T8 deviations; budget gate does not depend on it (the per-cell `--max-budget-usd-running` enforces independently). |
| Direct-structured underperforms paper baseline materially (e.g., per-query=0.20 vs paper=0.4376) | This is a valid scientific result, not a failure. Report writes `below` verdict, captain reads the head-to-head against spacedock=0.722 (gap=0.5) and decides next steps. The plan does NOT branch on the headline value. |

---

## Definition of done (plan-stage perspective)

The implementation stage signals done when:
- 12 frozen specs exist under `examples/specs/goal1/direct-structured/*.frozen.yaml`, each with `reasoning_effort: xhigh` + `sealed_hash`.
- 12 run-dirs exist under `_runs/goal1-direct-structured-opus47-xhigh/direct-structured/<dataset>/`, each with `result.json` + `summary.json` + `provenance.yaml` + `score.json` + `reward_per_query.json` (failed cells documented in `dispatch-failures.tsv`).
- `_runs/goal1-direct-structured-opus47-xhigh/direct-structured/aggregate-score.json` exists with `against_constant.name=direct_baseline` and `value=0.4376`.
- `docs/razorback-implementation/_evidence/goal1-direct-structured-dab-opus47-xhigh-report.md` is committed with all 11 sections from T8.
- `dispatch-ledger.tsv` shows 12 rows; either all `status: ok` OR every `status: run_failed` row has a documented failure-mode entry in the final report.
- Per-cell evidence mirror committed at `docs/razorback-implementation/_evidence/goal1-direct-structured-cells/<dataset>/`.
