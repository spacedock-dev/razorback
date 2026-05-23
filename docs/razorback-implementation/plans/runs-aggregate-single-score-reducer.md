# Make `rk score` and `summary.json` Share One Per-Query Reducer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for implementation tracking.

**Goal:** Collapse the two stratified pass@1 reducers in `runs/aggregate.py` into a single canonical reducer that consumes `reward_per_query.json` for DAB batch-mode trials, so `rk score` and `summary.json` report the same per-query headline number on the same run-dir and DAB batch cells stop binarizing their composite reward.

**Architecture:** Keep `reduce_per_query_stratified` as the canonical reducer in `runs/aggregate.py`. Move per-query reward extraction into `read_trial_outcomes` (or a sibling helper invoked from it): when a trial's `reward_per_query.json` sidecar exists, emit one outcome row per per-query reward keyed on `(dataset, query_id)` from the sidecar; when it does not exist, fall back to the existing one-trial-one-row behavior. The reducer itself stays generic — it groups by `(dataset, query_id)` from the outcome rows and never reads JSON. `aggregate_summary` calls the canonical reducer and renders its `StratifiedReport` into the existing `summary.json` `datasets` shape; the private `_stratified_pass_at_1` is deleted. `rk score` already consumes the canonical reducer, so it inherits the fix for free.

**Tech Stack:** Python 3.12, pytest, Typer's CliRunner for integration. No new runtime dependencies.

---

## AC to Task Map

| AC | Governing spec cites | Tasks | Focused verification |
| --- | --- | --- | --- |
| AC-1 — One reducer, per-query for DAB batch | v2 spec §3.2 `rk score` reducer-shared invariant; §7.1 run-dir contract | T1, T2, T3, T6 | T1 unit test: 6/7 fixture → canonical reducer returns `pass_at_1 == 6/7`. T6 mechanism: round-trip `summary.json` byte-for-byte equal to `rk score` JSON on the same run-dir. |
| AC-2 — `summary.json` `datasets` block is a render adapter | v2 spec §3.3 stability (no field removal); §7.1 run-dir artifacts | T4 | Snapshot of `summary.json["datasets"]` matches pre-change layout on existing fixtures; new batch-mode fixture matches the canonical reducer's per-query value. |
| AC-3 — DAB batch / DAB per-query / ADE all covered | v2 spec §3.2; §7.1 | T1, T2, T5 | Three fixture families exercised: `dab_batch_run_dir` (new), `mixed_trial_run_dir` (existing DAB per-query), `ade_bench_run_dir` (existing ADE task-view). |
| AC-4 — Paired regression on `summary.json` vs `rk score` | v2 spec §3.2 ("output matches `summary.json`'s `stratified_pass_at_1` by construction, pinned by `tests/integration/test_rk_score_matches_summary.py`") | T6 | Existing integration test gains a third case using the batch-mode fixture; both numbers equal the per-query value. |

---

## Planned Code Surfaces

| File | Responsibility | Planned action |
| --- | --- | --- |
| `src/razorback/runs/aggregate.py` | Canonical reducer, per-trial outcome extraction, summary writer | Modify. Extract per-query reward sidecar reader (mirror `benchmarks/dab/aggregate.py:_load_per_query_rewards`). Teach `read_trial_outcomes` to fan one batch trial into N outcome rows when the sidecar exists. Rewrite `aggregate_summary` to call `reduce_per_query_stratified` and render its result into the `summary.json` `datasets` shape. Delete `_stratified_pass_at_1` after the rewrite. |
| `src/razorback/_legacy/benchmarks/dab/aggregate.py` | Legacy DAB-native aggregator (still under `_legacy/`) | Read-only reference for `_load_per_query_rewards` semantics. Do not import from `_legacy/` at runtime — copy the small reader into `runs/aggregate.py` to keep the legacy boundary clean. |
| `src/razorback/cli/score.py` | `rk score` Typer subcommand | No code change required. Inherits the per-query fix through the canonical reducer. |
| `tests/fixtures/score/dab_batch_run_dir/` | New batch-mode DAB fixture | Create. One trial dir with `result.json` (composite `reward=0.857`), `steps/main/verifier/reward_per_query.json` (q1..q7 with six at 1.0 and one at 0.0), and a `stratum` resolvable to `dataset=yelp` (via the existing trial-name heuristic or a sidecar `stratum.json`). |
| `tests/unit/test_per_query_wilson.py` | Existing canonical reducer unit tests | Extend with the batch-mode-sidecar 6/7 case (read-from-fixture rather than synthetic outcome dicts, to exercise the new outcome-emission path end-to-end). May split into a sibling file `test_runs_aggregate_per_query_reducer.py` if the file grows past ~200 lines. |
| `tests/integration/test_rk_score_matches_summary.py` | `summary.json` ↔ `rk score` paired regression | Extend with `test_rk_score_matches_summary_for_dab_batch_fixture` using the new fixture; assert both report the per-query mean (not the composite-binary mean). |
| `tests/unit/test_runs_aggregate.py` (or nearest existing summary test) | `summary.json` `datasets` shape snapshot | Extend with one assertion that the new fixture's `summary.json["datasets"]["yelp"]["queries"]` carries seven entries and the dataset-level `pass_at_1 == 6/7`. |

**Real fixture/example input (for plan reviewer reference, not committed):** `/Users/clkao/git/razorback/_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/yelp/goal1-spacedock-yelp/484d0b940af2aa7b/yelp__Cc94VEd/steps/main/verifier/reward_per_query.json` is the source the synthetic fixture mirrors (six queries at `reward=1.0`, q4 at `0.0`).

---

## Reducer Contract After This Change

- **Outcome emission (one row per per-query reward when sidecar exists):**
  - If `<trial_dir>/steps/main/verifier/reward_per_query.json` exists, emit one `TrialOutcome` row per `qN` entry in the sidecar; each row's `stratum` is `{dataset: <trial's dataset>, query_id: <int N from "qN">}` and `reward` is the per-query float.
  - Else if `<trial_dir>/verifier/reward_per_query.json` exists, same treatment (single-step trials).
  - Else fall back to today's behavior: one `TrialOutcome` per trial with `reward` from `verifier_result.rewards["reward"]`.
- **Trial accounting (`n_trials_total`, `n_trials_completed`):** continue to count trials, not per-query rows. `n_trials_completed` is the number of trials whose sidecar (or whose composite reward) produced at least one usable per-query row.
- **Errored trials:** unchanged. A trial with `exception_info` set emits a single row with `reward=None`, `error_reason=<exception_type>`.
- **`cost_usd` per outcome:** when a trial fans into N per-query rows, only the first row carries the trial's cost; the rest carry `None`. The headline `cost_usd` sums on the run-dir (`_job_cost_usd`) and does not depend on the per-outcome cost, so this is a presentation choice that keeps the per-trial diff and outcomes table sane.
- **`trial_id` per outcome:** when a trial fans, rows are named `<trial_dir.name>#q<N>` so per-trial diagnostics can still trace back to one trial dir while remaining unique. Existing `per_trial_outcomes.json` writer continues to key on the original `trial_dir.name` (it walks dirs, not outcome rows) and is not affected.

---

## Mechanism Validation First

**Riskiest contract:** the canonical reducer reads a per-query sidecar it did not read before, *and* `aggregate_summary` switches to that reducer, *and* `rk score` already calls it — so a wrong outcome-emission step changes both `summary.json` and `rk score` headline numbers simultaneously on every DAB batch run. A bad sidecar parse silently zeros real cells (today's bug, in reverse).

**Smallest end-to-end mechanism (T1):** Take a single trial-dir fixture with `result.json` (composite `reward=0.857`) and `reward_per_query.json` (6 ones and one zero across `q1..q7`); call `reduce_per_query_stratified(read_trial_outcomes(run_dir))`; assert exactly one cell whose `pass_at_1 == 6/7` and whose `n_trials == 7`, `n_correct == 6`. That single assertion validates the entire outcome-emission contract end-to-end before any `aggregate_summary` rewrite, any `summary.json` snapshot, or any CLI integration runs. Every other task in this plan is gated on T1 going green.

---

## Tasks

### Task 1: Batch-Mode Outcome Emission RED Test

**ACs:** AC-1, AC-3
**Spec cites:** §3.2 `rk score` reducer-shared invariant; §7.1 run-dir contract.

**Files:**
- Create: `tests/fixtures/score/dab_batch_run_dir/yelp__Cc94VEd/result.json`
- Create: `tests/fixtures/score/dab_batch_run_dir/yelp__Cc94VEd/steps/main/verifier/reward_per_query.json`
- Modify (or create sibling): `tests/unit/test_per_query_wilson.py`

- [ ] **Step 1: Commit the batch-mode fixture.**
  Trial dir name `yelp__Cc94VEd` (so the existing `_parse_stratum_from_trial_name` heuristic resolves `dataset=yelp` from the prefix). Note: the existing heuristic expects `<dataset>-q<n>__<suffix>` — DAB batch trial names do not carry `-qN`, so add a `<trial_dir>/agent/stratum.json` sidecar that resolves `dataset=yelp` via the existing `_resolve_stratum` candidate list, OR rename the fixture trial-dir to a shape the existing resolver accepts. Pick whichever requires no resolver change; surface the choice in the stage report.
  - `result.json`: `{"verifier_result": {"rewards": {"reward": 0.857142857}}, "step_results": []}` — composite reward only, no per-step cost.
  - `reward_per_query.json`: seven entries `q1..q7`; six at `reward: 1.0`, q4 at `reward: 0.0` (mirror the real yelp sample at `_runs/goal1-rerun-spacedock-opus47-xhigh/spacedock/yelp/…`).
- [ ] **Step 2: Add the RED unit test.**
  ```python
  def test_batch_mode_reads_reward_per_query_sidecar() -> None:
      outcomes = read_trial_outcomes(FIXTURE / "dab_batch_run_dir")
      report = reduce_per_query_stratified(outcomes, alpha=0.05)
      cells = report["strata"]["yelp"]["queries"]
      assert {c["query_id"]: c["n_correct"] for c in cells} == {1:1,2:1,3:1,4:0,5:1,6:1,7:1}
      assert report["strata"]["yelp"]["dataset_pass_at_1"] == 6/7
      assert report["stratified_pass_at_1"] == 6/7
  ```
- [ ] **Step 3: Run `uv run pytest tests/unit/test_per_query_wilson.py -k batch_mode`.**
  Must fail today: the existing reducer reads composite reward `0.857` from `result.json`, sees one outcome with `reward=0.857`, binarizes (`>= 1.0` is `False`), and reports `pass_at_1 == 0.0` for the single cell.

### Task 2: Implement Sidecar Outcome Emission GREEN

**ACs:** AC-1
**Spec cites:** §3.2; legacy reference `benchmarks/dab/aggregate.py:_load_per_query_rewards` (lines 164-199, under `_legacy/`).

**Files:**
- Modify: `src/razorback/runs/aggregate.py`

- [ ] **Step 1: Add `_load_reward_per_query(trial_dir: Path) -> dict[int, float] | None`.**
  Mirrors `_legacy/benchmarks/dab/aggregate.py:_load_per_query_rewards` but takes a `trial_dir` directly. Returns `None` when neither sidecar candidate exists (signals "not a batch trial"); returns `{}` when the sidecar exists but is empty/unparseable (signals "batch trial with no usable data" — emit one errored outcome row). Candidates in order: `<trial_dir>/steps/main/verifier/reward_per_query.json`, `<trial_dir>/verifier/reward_per_query.json`.
- [ ] **Step 2: Teach `read_trial_outcomes` to fan batch trials.**
  For each trial dir, call `_load_reward_per_query`. If it returned a non-`None` dict, emit one `TrialOutcome` per `qN` entry: `trial_id=f"{trial_dir.name}#q{N}"`, `reward=<sidecar value>`, `cost_usd` only on the first row, `stratum` derived from `_resolve_stratum(trial_dir)` with `query_id=N` overriding any composite stratum value. If `_load_reward_per_query` returned `None`, fall through to today's `_read_trial(trial_dir)` behavior unchanged.
- [ ] **Step 3: Rerun the T1 test.** Expect GREEN. If RED, do not pile on more code — re-read the sidecar candidate order and the `_resolve_stratum` precedence in `_resolve_stratum_from_task_view_manifest` (lines 130-154) before changing anything else.

### Task 3: Delete the Private Reducer

**ACs:** AC-1
**Spec cites:** §3.2 single-source-of-truth invariant.

**Files:**
- Modify: `src/razorback/runs/aggregate.py`

- [ ] **Step 1: Rewrite `aggregate_summary` to call the canonical reducer.**
  Replace `_stratified_pass_at_1(trials)` with `report = reduce_per_query_stratified(read_trial_outcomes(run_dir))` and render `report.strata` into the existing `summary.json` `datasets` shape (Task 4). Keep `summary["trials"]`, `summary["n_trials_*"]`, and `summary["cost_usd"]` writes unchanged in field layout.
- [ ] **Step 2: Delete `_stratified_pass_at_1`.**
  Once `aggregate_summary` no longer references it, remove the function. `grep _stratified_pass_at_1 src/ tests/` must return zero matches outside `_legacy/`.
- [ ] **Step 3: `uv run pytest tests/unit -k aggregate`.** All existing aggregate tests must stay GREEN before continuing.

### Task 4: `summary.json` `datasets` Render Adapter

**ACs:** AC-2
**Spec cites:** §3.3 stability promise (no field removal); §7.1 run-dir contract.

**Files:**
- Modify: `src/razorback/runs/aggregate.py` (the rendering helper added in T3)

- [ ] **Step 1: Add `_render_legacy_datasets(report: StratifiedReport) -> dict`.**
  Map each `report.strata[ds]` to `{"dataset_pass_at_1": stratum.dataset_pass_at_1, "n_queries": stratum.n_queries, "queries": [{"query_id": c.query_id, "n_trials": c.n_trials, "n_correct": c.n_correct, "pass_at_1": c.pass_at_1} for c in stratum.queries]}`. Sort top-level by stratum name (existing behavior).
- [ ] **Step 2: Snapshot test (`tests/unit/test_runs_aggregate.py` or nearest existing).**
  Run `aggregate_summary` on each of `mixed_trial_run_dir` (DAB per-query) and `ade_bench_run_dir`; assert the `datasets` block layout is byte-for-byte equal to the pre-change snapshot (commit the snapshot from `git show HEAD:.../summary.json` if one isn't already in the fixture tree). On `dab_batch_run_dir` (new), assert `datasets["yelp"]["queries"]` has seven entries and `datasets["yelp"]["dataset_pass_at_1"] == 6/7`.

### Task 5: Extend Existing Reducer Tests to Cover Three Families

**ACs:** AC-3
**Spec cites:** §3.2.

**Files:**
- Modify: `tests/unit/test_per_query_wilson.py` (or `test_runs_aggregate_per_query_reducer.py` sibling)

- [ ] **Step 1: Keep the existing synthetic-outcome tests.** They cover Wilson-CI / alpha / null-stratum-CI invariants and do not depend on file IO.
- [ ] **Step 2: Add ADE/Spider task-view round-trip via existing `ade_bench_run_dir` fixture.**
  `outcomes = read_trial_outcomes(ADE_FIXTURE)`; `report = reduce_per_query_stratified(outcomes)`; assert the strata are keyed by ADE task ids (existing `_resolve_stratum_from_task_view_manifest` precedence) and not collapsed to `default`.
- [ ] **Step 3: Confirm DAB per-query fixture (`mixed_trial_run_dir`) is unchanged.**
  Same `outcomes`/`report` shape as before; no sidecar present, fall-through path is what's exercised.

### Task 6: Paired Integration Regression on Batch-Mode Fixture

**ACs:** AC-4
**Spec cites:** §3.2 "pinned by `tests/integration/test_rk_score_matches_summary.py`".

**Files:**
- Modify: `tests/integration/test_rk_score_matches_summary.py`

- [ ] **Step 1: Add `test_rk_score_matches_summary_json_for_dab_batch_fixture`.**
  Mirror the existing tests: copy trial subdirs of `dab_batch_run_dir` into `tmp_path/exp/job`, call `aggregate_summary(work)`, read `summary.json`, run `rk score --format json`, assert `summary["stratified_pass_at_1"] == score["stratified_pass_at_1"]` and **both equal `6/7`** (not `0.0`). The equal-to-`6/7` arm is what makes this regression catch the binarization bug specifically.
- [ ] **Step 2: Run `uv run pytest tests/integration/test_rk_score_matches_summary.py`.** All three cases (DAB per-query, ADE, DAB batch) must pass.
- [ ] **Step 3: Run `uv run pytest tests/`.** Full suite must be GREEN before stage report.

---

## Out of Scope

- Re-running goal1 / goal1-rerun cells against the fixed reducer. That belongs to the `goal1-rerun-dab-spacedock-opus47-xhigh` follow-on implementation dispatch (the captain directive's "12/12 headline" recompute) and gates on this entity reaching `done`.
- Changing the `per_trial_outcomes.json` schema or `rk runs diff` arms. The `(dataset, query_id)` keying already exists there; the diff path is unaffected because it keys on trial dirs, not outcome rows.
- Cost telemetry across fanned outcome rows. Per-trial `cost_usd` sums in `_job_cost_usd` are unchanged; the per-outcome cost cosmetic ("first row carries trial cost; rest `None`") is documented above and not separately tested.
- Restoring or activating `src/razorback/_legacy/benchmarks/dab/aggregate.py`. It remains read-only reference material; this plan copies the small sidecar reader rather than importing.
