# Goal 1 Re-run — DAB Spacedock Matrix, opus-4.7 + reasoning_effort=xhigh — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/goal1-rerun-dab-spacedock-opus47-xhigh.md`

**Goal:** Produce a fresh DAB spacedock baseline against the post-sprint canonical infrastructure (per-query `rk score`, runs_dir outside worktree, freeze CAS, `kind: spacedock_solver`, `dataset: dab@1.0`) with `model: claude-opus-4-7`, `reasoning_effort: xhigh`, `query_mode: batch`, `concurrency.trials: 1`, N=1 trial per cell across all 12 DAB datasets.

**This is a research RUN entity, not a feature change.** The only code touched is a minimal additive `--reasoning-effort` flag on the existing matrix-spec generator (mirrors the shape already shipped on `examples/drivers/generate-codex-benchmark-specs.py`). Everything else is dispatch, polling, aggregation, and report-writing.

**Tech Stack:** Python 3.12, Typer, pytest, bash. No new runtime dependencies.

---

## AC ↔ Task map

| AC | Description | Tasks |
|---|---|---|
| AC-1 | 12 spacedock specs carry `kind: spacedock_solver` + `dataset: dab@1.0` + `reasoning_effort: xhigh` + `query_mode: batch`; no `data_root + datasets` (without `dataset:`) shape | T0 (RED test), T1 (GREEN: add `--reasoning-effort` to generator), T2 (regen 12 specs) |
| AC-2 | Each spec freezes cleanly: `spec.frozen.yaml` + `provenance.yaml` adjacent, no `SpecError` / `AliasDriftError`, `solver_workflow_content_hash` + post-phase6 canonical kind recorded | T3 (freeze-loop) |
| AC-3 | All 12 cells run sequentially (`concurrency.trials: 1`); each cell emits run-dir with `summary.json`, `provenance.yaml`, per-trial `result.json` + `reward_per_query.json`; freeze CAS holds 12 sealed_hash subdirs; cell N failure does not block N+1..12 | T4 (per-cell dispatch + ledger), T5 (matrix sweep) |
| AC-4 | Aggregate `stratified_pass_at_1` via `rk score` per cell + captain-facing aggregator across 12 run-dirs; compared against `paper=0.577` with `--against-constant`; per-query Wilson CIs per `(dataset, query_id)`; stratum-level CI null per zb design | T6 (per-cell score), T7 (aggregator) |
| AC-5 | Per-cell `provenance.yaml` records `solver_workflow_content_hash`, `spacedock_skill_version`, `harbor_agent_kwargs_hash`, `reasoning_effort: xhigh`, resolved opus-4.7 model version (`pin_model_version: true`); re-run from same spec hits existing freeze CAS subdir | T3 (freeze-time fields), T8 (final-report enumeration) |

**Riskiest contract first (the mechanism gate):** `reasoning_effort: xhigh` must thread end-to-end from spec → frozen spec → sealed_hash → claude-cli `--effort xhigh` flag. The plan-stage worker has already paid this small bill (see "Mechanism check — DONE in plan stage" below); implementation stage inherits the result rather than re-discovering it the slow way.

---

## Mechanism check — DONE in plan stage (do not redo)

The plan-stage worker performed this end-to-end probe on bookreview before scaling up:

1. Regenerated `examples/specs/goal1/spacedock/bookreview.yaml` via the current `generate-dab-paper-matrix-specs.py` (post-qh canonical shape: `dataset: dab@1.0` + `kind: spacedock_solver`).
2. Hand-injected `reasoning_effort: xhigh` into the `agent:` block of bookreview.yaml.
3. Ran `uv run rk freeze examples/specs/goal1/spacedock/bookreview.yaml --allow-missing`. Result: `bookreview.frozen.yaml` emitted with `agent.reasoning_effort: xhigh` + `agent.sealed_hash` bound to it.
4. Probed the claude runtime adapter directly:
   ```python
   from razorback.agents._runtime import claude as claude_adapter
   inner = claude_adapter.build_inner_agent(
       logs_dir=tmp, model="claude-opus-4-7",
       harbor_agent_kwargs={"max_turns": 200, "reasoning_effort": "xhigh"},
       extra_env={"ANTHROPIC_API_KEY": "sk-fake"},
   )
   print(inner.build_cli_flags())
   ```
   Output included `--effort xhigh` — harbor `ClaudeCode.CLI_FLAGS` declares `choices=["low", "medium", "high", "xhigh", "max"]` at `.venv/.../harbor/agents/installed/claude_code.py:44`, so the value is accepted by the harbor flag layer without an Anthropic-API-side rejection at flag-build time.
5. **Schema-import side fix (committed alongside this plan):** `src/razorback/spec/schema.py` was importing `field_validator` only but using `@model_validator` on `HarborDabBenchmarkBlock` (introduced in commit `cf52c26`). This broke every `rk` CLI entry path on main. The plan-stage worker added `model_validator` to the pydantic import; without this, no `rk freeze` / `rk run` step in this plan executes. Implementation stage inherits a green entry point.

**Verdict:** `xhigh` is accepted. The plan proceeds at `xhigh` and does NOT need the entity's "fall back to high" branch.

---

## Surface map — what changes

| File | Change |
|---|---|
| `src/razorback/spec/schema.py` | Add `model_validator` to the pydantic import (1-line additive, fixes pre-existing breakage from `cf52c26`). **Already applied in plan-stage commit.** |
| `examples/drivers/generate-dab-paper-matrix-specs.py` | Add `--reasoning-effort` argparse flag (default `None`); when set, inject into the `agent:` block of every emitted spec. Mirror the shape of `examples/drivers/generate-codex-benchmark-specs.py`'s `--reasoning-effort` plumbing. |
| `tests/unit/test_dab_paper_matrix_spec_generator.py` *(new)* | T0 RED, T1 GREEN. Three tests: (a) default behavior emits no `reasoning_effort` key; (b) `--reasoning-effort xhigh` emits `reasoning_effort: xhigh` in every cell's `agent:` block; (c) shape regression — the spacedock cells have `kind: spacedock_solver` + `dataset: dab@1.0` + `query_mode: batch` and lack the legacy `data_root` field. |
| `examples/specs/goal1/spacedock/*.yaml` *(12 files, regen)* | Regenerated via T2 with `--reasoning-effort xhigh`. Each cell carries `kind: spacedock_solver` + `dataset: dab@1.0` + `reasoning_effort: xhigh` + `query_mode: batch`. |
| `examples/specs/goal1/spacedock/*.frozen.yaml` *(12 files, new)* | Emitted by T3 via the per-cell freeze loop. Carry `sealed_hash`, `solver_workflow_content_hash`. |
| `examples/specs/goal1/spacedock/provenance.yaml` *(per-spec siblings)* | Emitted alongside each frozen spec. Records `pin_model_version: true` + resolved opus-4.7 model version + the 5 AC-5 fields. |
| `examples/drivers/dab-paper-matrix.sh` | No change. Driver already supports `--variants spacedock` to walk only the 12 spacedock cells, idempotence on existing result.json, per-cell budget at `--max-budget-usd-running`, audit + score per cell, ledger TSV. T4+T5 use it as-is. |
| `examples/drivers/aggregate-goal1-scores.py` | No change. Already reads `runs/.../<variant>/<dataset>/*/*/result.json`, computes per-stratum + overall Wilson CIs, emits `--against-constant paper=0.577` verdict per dataset and overall. T7 uses it as-is. |
| `docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh.md` *(new)* | Final captain-facing report emitted by T8: per-cell `summary.json` excerpts, aggregate pass@1 + CI, against-constant verdict, per-cell `provenance.yaml` evidence enumeration, cost ledger total. |

## Surface map — what stays

- `src/razorback/spec/schema.py` — only the import line changes; the schema's structural changes from `cf52c26` (the `dataset` field on `HarborDabBenchmarkBlock`) stay.
- `src/razorback/spec/agent_kwargs.py` — already threads `reasoning_effort` through `build_v2_harbor_agent_kwargs` into `harbor_agent_kwargs`.
- `src/razorback/provenance/freeze_cmd.py` — already extracts `agent.reasoning_effort` and binds it into the sealed_hash.
- `src/razorback/agents/_runtime/claude.py` — already forwards `reasoning_effort` to harbor's `ClaudeCode._flag_kwargs`.
- `.venv/.../harbor/agents/installed/claude_code.py:44` — `xhigh` is already in the `CliFlag.choices` list; no harbor patch needed.
- Per-query `rk score` shape (zb): aggregator reads per-cell `result.json` `stats.evals.<eval_id>.reward_stats.reward` exactly as it does today.
- runs_dir outside worktree (x9): `--runs-dir` is passed explicitly by the dispatcher; the new XDG default does not affect this plan because the dispatcher is explicit.
- Freeze CAS (f1): the per-cell freeze step at T3 populates `$XDG_DATA_HOME/razorback/freeze/<sealed_hash>/` as a side-effect of freeze; AC-3's CAS-population check at T5 is just a `ls`.

---

## Spec ambiguity & guardrails to flag before T0

1. **N=1 vs N=5.** Entity is explicit: N=1 first-cut, parallel=1, batch mode, spacedock variant only. Do not promote to N=5 inside this plan; that's a sibling follow-up entity.
2. **Budget ceiling.** Entity estimates `12 × ~$5/cell ≈ $60` based on goal1-resume reconstruction. The dispatcher's per-cell `--max-budget-usd-running` is set per cell via `--max-cell-budget-usd`. The plan's recommendation: pass `--max-cell-budget-usd 10.0` (2× the estimate) — keeps a single runaway cell from burning $60+. The matrix-wide ceiling is implicit at 12 × $10 = $120; the dispatcher does not enforce this directly. If the captain wants a matrix-wide kill switch, that's a future plumbing entity, not a blocker here.
3. **Variant scoping.** The matrix driver defaults to all 3 variants × 12 datasets = 36 cells. T5 MUST pass `--variants spacedock` to scope to 12 cells.
4. **Pre-existing test failures.** Running `pytest tests/unit/test_spec_freeze_cli_pkg8.py` before any code change is the smoke for the freeze CLI; this plan's T0 RED test runs in isolation and does not depend on the whole tree being green.
5. **API auth.** The dispatcher reads `$CLAUDE_CODE_OAUTH_TOKEN` (or `~/.claude/benchmark-token`). T5 fails-fast if neither is present; do NOT run on a free-tier session that would emit `cost_usd: null`.

---

## Tasks

### T0 — Generator unit test (RED)

- **Goal:** Add `tests/unit/test_dab_paper_matrix_spec_generator.py` with three tests that fail against the current generator.
- **Tests:**
  1. `test_generator_default_emits_no_reasoning_effort`: invoke `build_spec("spacedock", "bookreview", "dab@1.0")` (or the equivalent argparse path with no `--reasoning-effort`); assert the returned dict's `agent` block has NO `reasoning_effort` key.
  2. `test_generator_with_reasoning_effort_xhigh_injects_into_agent`: invoke with `reasoning_effort="xhigh"`; assert `agent.reasoning_effort == "xhigh"`.
  3. `test_generator_spacedock_cell_shape`: invoke for spacedock + bookreview; assert `benchmark.kind == "harbor_dab"`, `benchmark.dataset == "dab@1.0"`, `benchmark.query_mode == "batch"`, `benchmark.workspace_variant == "spacedock"`, and `"data_root" not in benchmark`.
- **Run:** `uv run pytest tests/unit/test_dab_paper_matrix_spec_generator.py -x -v`; expected RED.
- **Spec §-cite:** Entity AC-1.

### T1 — Generator change (GREEN)

- **Goal:** Make T0 pass. Edit `examples/drivers/generate-dab-paper-matrix-specs.py` to accept `--reasoning-effort` and inject it into the `agent:` block when set.
- **Shape (match codex generator):**
  ```python
  parser.add_argument("--reasoning-effort", default=None,
                      help="Inject reasoning_effort into the agent: block of every emitted spec.")
  # in build_spec signature, accept reasoning_effort: str | None = None
  # in build_spec body, after _build_agent_block:
  if reasoning_effort is not None:
      spec["agent"]["reasoning_effort"] = reasoning_effort
  # main() passes args.reasoning_effort through
  ```
- **Run:** `uv run pytest tests/unit/test_dab_paper_matrix_spec_generator.py -x -v`; expected GREEN.
- **Verification:** `uv run python examples/drivers/generate-dab-paper-matrix-specs.py --reasoning-effort xhigh && grep -l "reasoning_effort: xhigh" examples/specs/goal1/spacedock/*.yaml | wc -l` returns 12.
- **Spec §-cite:** Entity AC-1 verification command.

### T2 — Regen 12 spacedock specs

- **Command:** `uv run python examples/drivers/generate-dab-paper-matrix-specs.py --reasoning-effort xhigh`
- **Verification:**
  - `ls examples/specs/goal1/spacedock/*.yaml | wc -l` returns 12.
  - `grep -l "reasoning_effort: xhigh" examples/specs/goal1/spacedock/*.yaml | wc -l` returns 12.
  - `grep -L "^benchmark:" examples/specs/goal1/spacedock/*.yaml` returns empty.
  - `grep -l "kind: spacedock_solver" examples/specs/goal1/spacedock/*.yaml | wc -l` returns 12.
  - `grep -l "dataset: dab@1.0" examples/specs/goal1/spacedock/*.yaml | wc -l` returns 12.
  - `grep -l "data_root:" examples/specs/goal1/spacedock/*.yaml | wc -l` returns 0 (no legacy local-root shape).
- **Spec §-cite:** Entity AC-1.

### T3 — Freeze 12 spacedock specs

- **Command (per spec):** `uv run rk freeze <spec> --allow-missing`
- **Loop:**
  ```bash
  for spec in examples/specs/goal1/spacedock/*.yaml; do
      uv run rk freeze "$spec" --allow-missing || echo "FREEZE FAILED: $spec" >&2
  done
  ```
  Note: `--allow-missing` is required because `pin_model_version: true` resolves only at `rk run` time on a live API call; freeze pre-flight leaves `model_resolved_version` unfilled and tags the provenance. This matches the existing generator's `freeze_spec()` helper at line 81.
- **Verification:**
  - `ls examples/specs/goal1/spacedock/*.frozen.yaml | wc -l` returns 12.
  - For each frozen spec, `grep -E "reasoning_effort: xhigh|sealed_hash:|solver_workflow_content_hash:" <spec>.frozen.yaml` shows all three lines.
  - Exit codes from the loop all = 0.
- **Spec §-cite:** Entity AC-2, AC-5.

### T4 — Dry-run smoke against the matrix driver

- **Command:** `bash examples/drivers/dab-paper-matrix.sh --dry-run --variants spacedock --output-dir runs/goal1-rerun-spacedock-opus47-xhigh`
- **Expected:** Prints 12 lines, one per `spacedock/<dataset>`, in the order: agnews, bookreview, crmarenapro, DEPS_DEV_V1, GITHUB_REPOS, googlelocal, music_brainz_20k, PANCANCER_ATLAS, PATENTS, stockindex, stockmarket, yelp. Prints `Total cells: 12 (expect 3 x 12 = 36 with defaults)`. Exits 0.
- **Verification:** The dry-run resolves frozen-spec paths for all 12 — no `missing frozen spec` warnings.
- **Spec §-cite:** Entity AC-3 dispatch shape.

### T5 — Full 12-cell dispatch

- **Command:**
  ```bash
  bash examples/drivers/dab-paper-matrix.sh \
      --variants spacedock \
      --output-dir "$XDG_DATA_HOME/razorback/runs/goal1-rerun-spacedock-opus47-xhigh" \
      --max-cell-budget-usd 10.0 \
      --continue-on-fail
  ```
- **Failure containment (matches entity AC-3 "Failure of an individual cell does not block subsequent cells"):** `--continue-on-fail` is mandatory. Without it, the first failing cell stops the matrix and the captain-facing aggregator gets a partial result that doesn't tell us whether the failure was cell-specific or systemic. With it, every cell gets its chance and the ledger TSV pins which cells failed.
- **Per-cell artifacts:** the driver writes to `${OUTPUT_DIR}/spacedock/<dataset>/`:
  - `dispatch.log` — `rk run` stdout/stderr.
  - `<run-name>/<job-name>/result.json` — per-trial reward stats.
  - `<run-name>/<job-name>/summary.json` — sealed-hash + cost summary.
  - `<run-name>/<job-name>/audit.json` — `rk audit --policy strict --format json`.
  - `<run-name>/<job-name>/score.json` — `rk score --against-constant spacedock=0.577 --format json`.
  - `budget.json` — `--max-budget-usd-running` per-cell tracking.
- **Matrix-wide artifacts:** the driver writes to `${OUTPUT_DIR}/`:
  - `dispatch-ledger.tsv` — one row per cell with `variant`, `dataset`, `spec_frozen`, `runs_dir`, `status`, `exit_code`, `cost_usd`.
  - `dispatch-failures.tsv` — appended for any non-zero exit.
- **Order:** alphabetical within spacedock (the driver's default `DATASET_ARR`). This is deterministic; no `--datasets` override needed.
- **Wallclock estimate:** 12 cells × ~10–15 min/cell at `query_mode: batch` + opus-4.7 + xhigh ≈ 2–3 hours. Implementation stage MUST dispatch in background (or via a long-running session) and poll `dispatch-ledger.tsv` for progress.
- **Idempotence:** if a cell already has a clean `result.json` from a prior partial run, the driver skips it (lines 116-139 of `dab-paper-matrix.sh`). Safe to re-invoke after a session interruption.
- **Spec §-cite:** Entity AC-3.

### T6 — Per-cell `rk score --against-constant paper=0.577`

- **Status:** The matrix driver already runs `rk score --against-constant spacedock=0.577` per cell (lines 193-203 of `dab-paper-matrix.sh`). Output lands at `${cell_run_dir}/score.json`.
- **Plan-side action:** None separate from T5. Just verify post-T5:
  ```bash
  find "$OUTPUT_DIR/spacedock" -name score.json | wc -l
  ```
  should return 12 (one per cell that ran successfully; failed cells have no `score.json`).
- **Note:** The captain's entity says "compared against `paper=0.577`". The driver uses the label `spacedock=0.577` (line 195). That's a label-only difference; the constant value is identical and the verdict semantics are the same. T8's final report normalizes the label to `paper=0.577` for captain-facing presentation.
- **Spec §-cite:** Entity AC-4 per-cell scoring.

### T7 — Captain-facing aggregator

- **Command:**
  ```bash
  uv run python examples/drivers/aggregate-goal1-scores.py \
      --runs-root "$XDG_DATA_HOME/razorback/runs/goal1-rerun-spacedock-opus47-xhigh" \
      --variants spacedock \
      --output docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-aggregate.json
  ```
  (Read the aggregator's actual flag surface before running — the script's `--help` is the source of truth. If the flags differ, T7's command line is updated; the semantic shape — runs-root + variant filter + JSON output — stays.)
- **Output:** A single JSON with per-dataset Wilson CIs, overall stratified pass@1, against-constant verdict (inside-CI / above / below) per dataset and overall against `paper=0.577`.
- **Spec §-cite:** Entity AC-4 aggregate.

### T8 — Final captain-facing report

- **File:** `docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh.md`
- **Contents:**
  1. Headline: aggregate stratified pass@1 + 95% Wilson CI + against-constant verdict vs `paper=0.577`.
  2. Per-dataset table: dataset, n_total, n_pass, n_errored, pass@1, CI, against-constant verdict, cost_usd, wallclock.
  3. Per-cell `provenance.yaml` field enumeration (AC-5): table with columns `dataset`, `solver_workflow_content_hash`, `spacedock_skill_version`, `harbor_agent_kwargs_hash`, `reasoning_effort`, `model_resolved_version`. All 12 rows must have all 5 columns populated.
  4. Freeze CAS check: `ls $XDG_DATA_HOME/razorback/freeze | wc -l` output (must include the 12 new sealed_hashes plus whatever else is cached); plus a per-cell `<sealed_hash>` cross-reference from the frozen spec to the freeze tree.
  5. Cost ledger: `dispatch-ledger.tsv`'s `cost_usd` column summed; per-cell range; total.
  6. Failure analysis: any rows from `dispatch-failures.tsv` with cell ID, exit code, the first ~40 lines of the matching `dispatch.log`.
- **Spec §-cite:** Entity AC-3, AC-4, AC-5.

---

## TDD checkpoints

- T0 (RED) → T1 (GREEN) is the only true TDD pair here. The rest of the plan is dispatch + observation, not unit-level logic.
- The mechanism check at the top of this doc (DONE in plan stage) is the integration-level "smallest end-to-end exercise of the riskiest contract" per CL's "Validating new mechanisms" rule.
- T4 (dry-run) is a second mechanism check: it proves the 12 frozen specs are discoverable by the dispatcher BEFORE T5 burns $60+ of API time.

---

## Risk register

| Risk | Mitigation |
|---|---|
| `xhigh` rejected by Anthropic API at first `rk run` (not at flag-build) | Mechanism check confirmed CLI flag accepts xhigh. If runtime rejects, T5 surfaces in the FIRST cell's `dispatch.log`; abort, downgrade to `reasoning_effort: high`, regen+refreeze+redispatch. The entity's test plan already names this fallback. |
| Single cell burns $60+ | `--max-cell-budget-usd 10.0` per-cell cap. |
| Matrix runs >3 hours | T5 dispatch is `--continue-on-fail`; the dispatcher writes to `dispatch-ledger.tsv` after each cell, so a session interruption is safe to resume via idempotence (T5 re-invocation). |
| pre-existing `model_validator` import bug in `schema.py` | Fixed in plan-stage commit (additive 1-line pydantic import). Implementation stage inherits a green entry point. |
| `--allow-missing` masks a real provenance gap | The `model_resolved_version` field is the only one expected missing pre-`rk run`; it gets populated by `rk run` when the API call resolves the canonical model SHA. T8's AC-5 enumeration confirms it's non-null in every cell's `provenance.yaml`. |
| Idempotence false-positive (stale `result.json` from a prior dispatch causes T5 to skip a cell that should re-run) | The plan dispatches into a NEW `$XDG_DATA_HOME/razorback/runs/goal1-rerun-spacedock-opus47-xhigh` subdir that did not exist before this entity. No cross-contamination with prior goal1 / goal1-resume runs. |

---

## Definition of done (plan-stage perspective)

The implementation stage signals done when:
- 12 frozen specs exist under `examples/specs/goal1/spacedock/*.frozen.yaml`, each with `reasoning_effort: xhigh` + `sealed_hash`.
- 12 run-dirs exist under `$XDG_DATA_HOME/razorback/runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/<dataset>/`, each with `result.json` + `summary.json` + `provenance.yaml` + `score.json`.
- `docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh.md` is committed with the AC-3 / AC-4 / AC-5 evidence enumerated.
- `dispatch-ledger.tsv` shows 12 rows; either all `status: ok` OR every `status: run_failed` row has a documented failure-mode entry in the final report.
