# Plan: rk score delegates to the post-harbor aggregator (drop binary pass@1 reducer)

Entity: `docs/razorback-implementation/rk-score-uses-benchmark-aggregator.md`
Spec: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §3.2, §8.3a, §6.5

## Architecture decision

There are two reasonable dispatch shapes the entity body raises:

1. **Per-benchmark aggregator (`benchmarks/<kind>/aggregate.py:aggregate_job_result`).** `rk score` would load `spec.frozen.yaml`, read `benchmark.kind`, and call the matching aggregator.
2. **Single source of truth via `runs/aggregate.py:_stratified_pass_at_1`.** `rk score` would call the same reducer the post-harbor aggregator already runs on the run-dir.

**Pick: option 2.** Justification, evidence-grounded:

- `runs/aggregate.py:_stratified_pass_at_1` is already filesystem-state-driven (reads
  `run_dir/<trial>/result.json` + `agent/stratum.json`). `rk score`'s input is exactly
  that filesystem state. No `JobResult` reconstruction needed.
- `benchmarks/dab/aggregate.py:aggregate_job_result` takes a `JobResult.trial_results`
  iterable + a `trial_name_map` keyed by trial-name-prefix. `rk score` has neither. To
  reuse it we would have to fabricate both from filesystem state — that's a new code
  path with its own bugs.
- The entity body claims `benchmarks/ade_bench/aggregate.py` exists. **It does not.**
  Only a stale `__pycache__/aggregate.cpython-312.pyc` remains under
  `src/razorback/benchmarks/ade_bench/`. Option 1 would block on creating
  ADE-bench's aggregator first, which is out-of-scope per the entity.
- Mathematically: `summary.json[stratified_pass_at_1]` is, by definition, the output of
  `_stratified_pass_at_1`. If `rk score` calls the same function on the same run-dir,
  AC-1's "same number as summary.json" is true by construction, not by test luck.
- Out-of-scope per the entity: "Cross-benchmark unification of the aggregator shape". The
  single-source path keeps each benchmark's `aggregate_job_result` untouched — they
  continue to be the post-harbor writer for `summary.json` inside the dab plugin's
  path (when it's the live path); on disk the artifact is the same.

What this means for AC-2 (ADE-bench): once `rk score` reads from the same filesystem
contract as `runs/aggregate.py`, an ADE-bench run-dir scores correctly as soon as its
trial-dirs carry `stratum.json` (or task-view manifest) sidecars — the same precondition
`summary.json` already enforces. The dispatch becomes a no-op: there is no per-benchmark
branch; the reducer is universal across benchmark kinds, by way of the stratum tags the
benchmark plugins already write. **The entity's "dispatch on `spec.benchmark.kind`"
framing is wrong: the right move is no dispatch at all, because the post-harbor
aggregator is already benchmark-agnostic by stratum-tag.**

(If a future benchmark needs a non-pass@1 metric, it grows a per-benchmark reducer at
that point. YAGNI now.)

## AC ↔ task map

| AC | Tasks |
|---|---|
| AC-1 (DAB pass@1 matches `summary.json`) | T2 (extract reducer), T3 (wire CLI), T4 (round-trip integration) |
| AC-2 (ADE-bench pass@1 matches `summary.json`) | T2 (reducer is benchmark-agnostic), T4 (round-trip on ADE-bench fixture) |
| AC-3 (Wilson CI + `--against-constant` preserved with correct math) | T5 (per-query Wilson + drop stratum-level Wilson), T6 (verdict + render updates), T7 (existing tests adjusted) |
| AC-4 (`reduce_trials` deleted) | T8 (delete + grep gate) |

## Spec §-cites per task

- T2/T3/T4: §8.3a "single-run statistical readout"; §3.2 "Per-stratum pass@1 with Wilson CI"; §6.5 stratified mean recipe (verbatim DAB).
- T5/T6: §8.3a "Per-stratum pass@1 with Wilson 95% CI (level via --alpha)". The original Wilson math is for binary k/n; on per-query continuous data it stops being a binomial — the design rule below names the substitution.
- T7: §3.2 `--against-constant` paper-reproduction surface.
- T8: §9.2 counting honesty (preserved — `n_completed` denominator still excludes errored trials, that logic moves from `score/reduce.py` to the new path).

## AC-3 substantive design question: Wilson CI on per-query data

The existing `wilson_ci(k, n, alpha)` is a binomial proportion CI: each trial is one
Bernoulli draw. Under the new path:

- The per-query cell `(dataset, query_id)` is binomial: `k = sum(reward >= 1.0 over the
  trials of that query)`, `n = trials of that query`. Wilson applies directly.
- The dataset stratum is the **mean of per-query proportions** within the dataset, not
  the proportion across all trials in the dataset. That is not a binomial; Wilson is
  the wrong CI for it.

Options considered:

- (a) Per-query Wilson at the cell level; drop stratum-level CI (emit `wilson_ci: null`
  on the dataset stratum).
- (b) Stratum-level bootstrap CI on the continuous per-query metric. Correct, but
  introduces a single-arm bootstrap path that `rk score` does not have today; non-
  trivial new statistics surface — entity is plumbing, not stats expansion.
- (c) Drop CI entirely (per-query and stratum). Loses information for cells where the
  binomial CI is valid and well-defined.

**Recommendation: (a).** The per-query Wilson cell is the mathematically honest CI; the
stratum-level CI was already a fiction once `summary.json` switched to per-query
stratification (which it already has, since 2026-05-22). Keeping the field but
emitting `null` at the stratum level is the smallest correct move and explicit about
the gap.

**Effect on `--against-constant`:**

- Per-stratum verdict (`verdict.py:_stratum_verdict`) currently consumes `wilson_ci`.
  When the stratum CI is `null`, the verdict becomes a point comparison via the same
  `_point_verdict` already used for the stratified row. No new branches needed in
  `verdict.py` — feed it the dataset's point estimate.
- The cell-level verdict (per query) is new optional surface and out of scope for AC-3
  (which only requires CI brackets the benchmark-native point estimate). The cell
  Wilson CIs ride in the JSON for analyst use; the markdown table stays at the
  dataset granularity.

Out of scope acknowledged in the entity body: "Per-stratum Wilson CIs on per-query data
... is a separate stats question." This plan honors that — option (b)/single-arm
bootstrap is deferred. Option (a) is the minimum honest answer that the entity's AC-3
requires.

## Tasks (TDD order; riskiest-contract-first)

### T1 — Stage the integration test (smallest end-to-end exercise of the riskiest path)

Per CL's rule on validating new mechanisms: the riskiest contract here is "the number
`rk score` emits is the same number that's in `summary.json`". Write that test FIRST
and let it red-bar everything else.

- Add `tests/integration/test_rk_score_matches_summary.py` (new file). Two cases:
  1. DAB fixture run-dir (reuse / extend `tests/fixtures/score/mixed_trial_run_dir` —
     or better, copy a real goal1 fixture if one is checked into `tests/fixtures/`;
     check first via `find tests/fixtures -name summary.json`). The test:
     - Runs the rk-run post-harbor aggregator on the fixture (or reads its already-
       written `summary.json`).
     - Runs `rk score <run-dir> --format json` via Typer's `CliRunner`.
     - Asserts `score_output["stratified_pass_at_1"] == summary["stratified_pass_at_1"]`
       (exact float equality is fine — same computation, same inputs).
  2. ADE-bench fixture run-dir — minimum-viable: a hand-built run-dir with two trial
     dirs carrying `result.json` + `agent/stratum.json` with
     `{"benchmark_kind": "ade-bench", "benchmark_task_id": "..."}` shape. Run the
     post-harbor aggregator on it (or hand-write `summary.json`), then assert the
     same equality. If no ADE-bench fixture is available, build the minimum one in
     `tests/fixtures/score/ade_bench_run_dir/`.

- Run the test. Confirm it red-bars (current `rk score` returns the binary pass@1 from
  `score/reduce.py:reduce_trials`, which generally != per-query stratified mean).

This is the contract gate. Everything downstream stays inside it.

### T2 — Extract the per-query reducer for shared use

`runs/aggregate.py:_stratified_pass_at_1` is internal. The cleanest factor:

- Move the body into a public-named function with a typed return:
  - `runs/aggregate.py:reduce_per_query_stratified(trial_dirs: list[Path]) -> StratifiedReport`
  - Or: split into `read_trial_outcomes(run_dir) -> list[TrialOutcome]` +
    `reduce_per_query_stratified(outcomes) -> StratifiedReport` if the in-memory
    pass-by-list shape is needed for unit tests (it is — see T5).
- Keep `aggregate_summary()` calling the new function so its output is byte-for-byte
  unchanged. Existing tests under `tests/unit/test_runs_aggregate*.py` pin that surface.
- Run the existing `runs/aggregate` tests; they must stay green. **This is a refactor,
  not a logic change.** TDD-wise: the failing test is T1; T2 is the smallest move that
  exposes the function `rk score` will call.

The `StratifiedReport` shape this plan proposes (TypedDict, for `score/render.py`'s use):

```python
class QueryCell(TypedDict):
    query_id: int | str | None
    n_trials: int
    n_correct: int     # binary count, for Wilson
    pass_at_1: float   # always c / n at the query level
    wilson_ci: tuple[float, float] | None  # binomial CI on (n_correct, n_trials)

class DatasetStratum(TypedDict):
    dataset: str
    n_queries: int
    dataset_pass_at_1: float        # mean of QueryCell.pass_at_1
    queries: list[QueryCell]
    wilson_ci: None                  # explicit null — mean-of-proportions isn't binomial

class StratifiedReport(TypedDict):
    score_version: int
    alpha: float
    strata: dict[str, DatasetStratum]
    stratified_pass_at_1: float | None
    n_trials_total: int
    n_trials_completed: int
    n_trials_errored: int
    error_reason: str | None
```

This shape is a strict superset of what `summary.json` currently writes, with the
Wilson cells added at the per-query level and the binary pass count carried alongside.

### T3 — Wire `rk score` to the shared reducer

- Replace `cli/score.py:48-50`:
  - Drop `from razorback.score.reduce import reduce_trials`.
  - Drop `from razorback.score.load import ... load_run_dir`.
  - Call `runs/aggregate.py`'s `read_trial_outcomes(run_dir)` + `reduce_per_query_stratified(outcomes, alpha=alpha)`.
- Decision: **delete `score/load.py:TrialRecord` and `score/reduce.py` entirely.** They
  exist only to feed `reduce_trials`. The new reducer takes its inputs from
  `runs/aggregate.py`'s outcome reader. Per CL's rule "YOU MUST WORK HARD to reduce
  code duplication": keeping `score/load.py` would mean two filesystem walkers with
  different stratum-resolution precedence (the entity's debrief already flagged the
  drift).
- One concern: `score/load.py:_resolve_stratum_payload` has slightly different stratum
  fallback than `runs/aggregate.py:_resolve_stratum` (former requires sidecar OR
  task-view-manifest; latter also parses `<dataset>-q<n>__` from trial-dir names).
  The post-harbor aggregator's precedence is the right one (it ships the headline
  number); the score path inherits it on consolidation.
- Run T1. It must turn green.

### T4 — Round-trip integration test on a real goal1 run-dir

Per the entity's "Test plan → Acceptance" bullet: extend T1's test (or add a sibling
`tests/integration/test_rk_score_matches_summary_goal1.py` gated by a fixture-exists
check) to run against a checked-in goal1-like run-dir if one exists. If not, the T1
fixtures suffice — the AC explicitly names "any goal1 spacedock run-dir" but doesn't
require the test to consume one (CI doesn't carry spacedock run-dirs at full scale).

Run: confirm `rk score <fixture-run-dir> --against-constant paper=0.577` emits the
same `stratified_pass_at_1` value as the run-dir's `summary.json`.

### T5 — Per-query Wilson CIs (AC-3 honest answer)

- In `reduce_per_query_stratified`, for each `QueryCell` compute `wilson_ci(k=n_correct,
  n=n_trials, alpha=alpha)` and attach.
- For each `DatasetStratum`, leave `wilson_ci=None` (the explicit null — design decision
  above).
- Stratified row: no run-level CI (already the case today; `_point_verdict` handles the
  verdict).
- Unit tests in a new `tests/unit/test_per_query_wilson.py`:
  - A query with `k=3, n=5, alpha=0.05` returns the Wilson CI matching the existing
    `diff/stats.py:wilson_ci(k=3, n=5, alpha=0.05)` output (so the math is unchanged,
    only the granularity moved).
  - All-pass query (`k=n=5`) gives a Wilson CI with upper bound 1.0.
  - Zero-trial query (`n=0`) returns `wilson_ci=(0.0, 1.0)` per existing convention.

### T6 — Render + verdict updates (AC-3 surface)

- `score/render.py:_report_to_jsonable` must consume `DatasetStratum` (not
  `StratumStats`). The JSON shape changes:
  - `strata[<dataset>].queries: [{query_id, n_trials, n_correct, pass_at_1, wilson_ci}]`
    is added.
  - `strata[<dataset>].wilson_ci` becomes `null` always (was previously the binary
    Wilson on `n_pass / n_completed`). Document this in the §3.3 JSON shape header
    comment in `score/render.py`.
- `score/verdict.py:_stratum_verdict` currently returns `"matches"` or
  `"outside-CI"`. When the stratum CI is `null`, return a point-verdict shape: `{
  "verdict": "matches" | "above" | "below", "ci": None, "side": None }` using
  `_point_verdict` semantics. Add the optional `cells` field carrying per-query
  cell verdicts (verdict-against-constant per query Wilson cell). The latter is
  bonus surface, not AC-3-required — add only if it falls out cleanly.
- Update `tests/unit/test_score_render.py`, `tests/unit/test_score_verdict.py`, and
  the JSON snapshot in `tests/unit/test_score_json_schema_snapshot.py` to the new
  shape. Snapshot regeneration is acceptable per CL's "tests MUST cover ALL
  functionality" rule — the snapshot is the contract here, regenerate it once the
  shape is set.

### T7 — Adjust / replace `tests/unit/test_score_*` to the new reducer

- `test_score_load.py`, `test_score_reduce.py`, `test_score_counting.py`: many of
  these test `TrialRecord` / `reduce_trials` directly. Those code paths are being
  deleted. Re-target the surviving counting / stratum-precedence assertions at the
  new reducer; delete tests that pin the binary `passed = reward >= 1.0`
  reduction (which is precisely the thing AC-4 says must go).
- Cross-check `test_score_no_regression_pkg17.py` — its purpose is to pin that
  `rk score` and `summary.json` agree. Read it; if it already asserts agreement,
  T1's test may be redundant — fold or rename rather than duplicate.

### T8 — Delete the binary reducer; grep gate for AC-4

- Delete `src/razorback/score/reduce.py`.
- Delete `src/razorback/score/load.py` (if T3's consolidation absorbed its job).
- Update `src/razorback/score/__init__.py` exports.
- Grep gate (run before commit):

  ```bash
  rg "passed=\\(reward is not None and reward >= 1.0\\)" src/ tests/
  ```

  Must return zero hits outside test fixtures explicitly testing the binary
  reduction (per AC-4). If any production hits remain, fix them before commit.

- A second grep gate confirming no callers of `reduce_trials`:

  ```bash
  rg "reduce_trials|score\\.reduce" src/ tests/
  ```

  Expected zero hits outside the deleted file's own removal commit.

### T9 — End-to-end smoke

- Run `pytest tests/unit/test_cli_score.py tests/unit/test_score_*.py tests/integration/test_rk_score_matches_summary*.py -x`.
- Run `pytest tests/unit/test_runs_aggregate*.py` to confirm the reducer extraction
  didn't perturb `summary.json` output.
- Pristine output check (CL's rule): no warnings, no stray prints, no skipped tests
  that should run.

## Out-of-scope guard rails

- ADE-bench's `aggregate.py` is NOT being created in this entity. The post-harbor
  aggregator's stratum-tag-driven reducer makes one unnecessary for the score path.
  If `rk run` for ADE-bench requires its own `aggregate_job_result` later (e.g., to
  read non-pass@1 metrics per task), that's a separate entity.
- No cross-arm / paired statistics. `rk diff` is unchanged.
- No single-arm bootstrap. (The AC-3 honest CI question is resolved by per-query
  Wilson + null at stratum level.)

## Risk register

- **R1 — Stratum-precedence drift between `score/load.py` and `runs/aggregate.py`.**
  Resolved by deletion (T3, T8): only one walker remains.
- **R2 — `test_score_json_schema_snapshot.py` is a contract test other tools depend
  on.** Search the codebase for consumers of the §3.3 JSON shape before regenerating
  the snapshot. If `rk runs diff` or any external tool parses `strata.*.wilson_ci`,
  we keep emitting `null` (which is already in the shape, valid per the original
  schema comment); we are only changing whether it's ever non-null at the dataset
  level. The cell-level fields are additions, which is forward-compatible.
- **R3 — Existing `test_score_no_regression_pkg17.py` may already pin the post-harbor
  agreement.** Read it in T7. If it already does the AC-1 check, T1 is redundant and
  we extend the existing test instead of adding a sibling.

## Validation order (mechanism-first per CL's "Validating new mechanisms")

1. T1 first: smallest end-to-end exercise of the riskiest path (number agreement). Red.
2. T2 + T3: minimum to turn T1 green. Green.
3. T4 (AC-2 ADE-bench fixture) — second-riskiest contract: cross-benchmark generality.
4. T5/T6 (CI math) — narrower, well-typed change.
5. T7/T8 (delete legacy) — purely additive proof-of-removal once everything above is
   green.

## Files touched

- `src/razorback/cli/score.py` (rewire imports + reducer call)
- `src/razorback/runs/aggregate.py` (extract `read_trial_outcomes`,
  `reduce_per_query_stratified`; keep `aggregate_summary` byte-equivalent)
- `src/razorback/score/render.py` (consume new shape; cells + null stratum CI)
- `src/razorback/score/verdict.py` (point-verdict at stratum when CI is null)
- `src/razorback/score/__init__.py` (export surface)
- **Delete:** `src/razorback/score/reduce.py`, `src/razorback/score/load.py`
- `tests/integration/test_rk_score_matches_summary.py` (new)
- `tests/unit/test_per_query_wilson.py` (new)
- `tests/unit/test_score_*.py` (retarget / delete per T7)
- `tests/unit/test_score_json_schema_snapshot.py` (snapshot regen)

## Spec section anchors

- §3.2 — `rk score` CLI surface.
- §3.3 — JSON shape (the file-level docstring in `score/render.py` documents this;
  this plan keeps the documented shape compatible by additive change + null-typing).
- §6.5 — Stratified mean recipe; per-query pass@1 averaged within dataset, then
  across datasets. The very recipe `runs/aggregate.py:_stratified_pass_at_1` and
  `benchmarks/dab/aggregate.py:_build_summary` already implement.
- §8.3a — `rk score` single-run statistical readout: "Per-stratum pass@1 with Wilson
  95% CI ... Overall stratified pass@1 (the macro-average across strata)." The CI
  language is preserved at the per-query cell level; the macro-average at the
  stratum level is exactly what `summary.json` already emits.
- §9.2 — counting honesty (`n_completed` denominator, errored exposed). Preserved
  through `n_trials_completed` / `n_trials_errored` carried in `StratifiedReport`.
