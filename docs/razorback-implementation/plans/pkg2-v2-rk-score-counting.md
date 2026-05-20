# PKG-2 v2: `rk score` Counting Honesty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the counting-honesty rules `rk score`'s single-run statistical readout consumes per spec §3.2 + §8.3a + §9.2: errored trials are counted in a `n_errored` field but excluded from the `n_completed` denominator that feeds pass@1 and Wilson CI; a stratum with `n_completed == 0` emits `pass_at_1: null` and `wilson_ci: null` rather than zero-counting; and a top-level `error_reason` field names the dominant exception class so the operator can see why a stratum or run was inconclusive. PKG-2 v2 is a **contract-shape fragment** of Phase 4a: this plan owns the counting rules + their unit tests; the sibling plan `phase4a-rk-score-wilson-stratified` (xm) consumes the rules via the `reduce_trials(records, *, alpha) -> ScoreReport` signature and folds the tests into Task 2 + Task 3 of its own task list.

**Spec source of truth:** `/Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`. Governing sections:

- **§3.2**, `rk score <run-dir> [--format markdown|json] [--alpha 0.05]` first-ship subcommand surface. Names per-stratum pass@1 + Wilson 95% CI + stratified mean + `--against-constant` paper-reproduction line. The CLI surface that consumes the counting rules.
- **§8.3a**, single-run statistical readout. Names "Trial counts per stratum (with errored-vs-completed distinction, honoring the AC-4.4 counting contract)" as a required output line. The reducer + renderer must surface `n_completed`, `n_errored`, `n_total` per stratum and the `error_reason` field on inconclusive strata.
- **§9.2** (per the entity body), counting-honesty discipline: errored trials must not be silently double-counted as failed passes, and Wilson CIs / stratified means must not be computed off a denominator polluted with non-completion events.

Spec §8.3a's verbatim "honoring the AC-4.4 counting contract" pins this fragment's load-bearing rule: **the pass@1 denominator is `n_completed`, never `n_total`.** A trial that errored (non-zero exit, no verifier output, dominant exception class recorded) sits in `n_errored` and is excluded from the rate calculation; it does NOT count as a failed pass.

**Architecture:** This plan owns **rules + tests**, not modules. The modules live in xm's `phase4a-rk-score-wilson-stratified`:

- **Producer side**, `src/razorback/score/load.py` (xm Task 1): the loader extracts `state ∈ {"completed", "errored"}` and (when errored) `error_class` per trial from `result.json`. This plan pins the `state` derivation rule (Section "State derivation rule" below) and the trial-fixture taxonomy the loader-side test must exercise.
- **Reducer side**, `src/razorback/score/reduce.py` (xm Task 2 + Task 3): the reducer groups by stratum, counts `n_completed` + `n_errored` + `n_total`, divides pass@1 by `n_completed`, falls back to `pass_at_1: null` + `wilson_ci: null` + `error_reason: <class>` on `n_completed == 0`, and rolls the same logic up to the run level. This plan pins the reducer's per-stratum and run-level rules (Sections "Counting rule" + "Null-result rule" + "Error-reason rule" below).
- **Renderer side**, `src/razorback/score/render.py` (xm Task 5): the JSON shape carries `n_total`, `n_completed`, `n_errored`, `error_reason` per stratum + at the top level. This plan pins the key set + null-encoding (Section "Wire shape" below).

The signature xm consumes verbatim is:

```python
def reduce_trials(records: list[TrialRecord], *, alpha: float) -> ScoreReport
```

where `TrialRecord.state ∈ {"completed", "errored"}` and `TrialRecord.error_class: str | None` are the producer-side primitives this plan's rules depend on.

**Tech Stack:** Python 3.12, pytest. No new modules from this fragment; xm's plan owns module creation. Tests land in `tests/unit/test_score_counting.py` (this plan's net-new file) and exercise the reducer via xm's `reduce_trials` import.

**Riskiest contract first.** The error-state taxonomy fixture (one PASS, one FAIL, one ERROR, one OTHER) is the load-bearing seam: every counting rule below cascades off how the loader maps `result.json` shape to the four-cell state space. The fragment's Task 1 ships this fixture set + the loader-side assertion that the four cells resolve to `(state, passed, error_class)` triples; xm's Task 1 imports and exercises it. If the loader misreads any of the four cells, every reducer test downstream is meaningless.

**Phase dependencies:**

- **`phase4a-rk-score-wilson-stratified` (plan landed):** Hosts the modules this plan's rules feed. xm's AC ↔ task map cites this fragment for AC-3 (counting honesty: `n_completed` denominator; `n_errored` exposed; all-errored → null + `error_reason`). xm's Task 2 Step 4 and Task 3 Steps 1-3 implement the tests this plan pins; xm's Task 3 implements the null + error_reason branch.
- **`phase3-spacedock-solver-v2` (plan landed):** Provides the sealed-state contract on trial output. `SpacedockSolverAgent` v2's `result.json` carries the `status: completed|errored` and `exception_info.class` fields the loader maps to `state` and `error_class`. The sealed-state contract is the run-dir-as-input boundary, `rk score` reads `result.json` as a black box and never reaches into `_razorback/freeze/`. Implementation queues behind phase3 done because the loader-side state derivation depends on phase3 finalising the `result.json` `status` field's possible values.
- **Phase 2 DAB harbor adapter (Task 11 landed per #34):** Produces `agent/stratum.json` per trial. Counting honesty is benchmark-agnostic, but the per-stratum rollup needs the stratum tag. This plan does NOT pin stratum-tag shape, xm's plan owns that, but the fixtures here use the DAB shape `{"stratum": {"dataset": "bookreview", "query_id": N}}` for consistency.

**Out of scope:**

- Wilson CI math, stratified-mean macro-average, `--against-constant` verdict logic, JSON schema snapshot, markdown rendering. All owned by xm's `phase4a-rk-score-wilson-stratified` (this plan's sibling).
- Paired statistics, McNemar, Holm-Bonferroni, bootstrap CI. All deferred to `rk diff` per spec §8.3.
- Trial-state taxonomy beyond `completed` / `errored`. The spec's two-cell partition is sufficient; "timed-out", "killed", "skipped" all collapse into `errored` with the `error_class` field carrying the discriminator. If a future spec revision needs a third trial state, it lands as a v2-bump on `score_version` per spec §3.3.
- Cost / latency telemetry on errored trials. Spec §3.2 names `rk runs cost` as the cost surface; this plan stays in the score domain.

---

## State derivation rule (loader-side, consumed by xm Task 1)

A trial's `state` is derived from its `result.json` shape exactly as follows:

| Result.json shape | `state` | `passed` | `error_class` |
|-------------------|---------|----------|---------------|
| `verifier_result.rewards.reward` is a number AND `exception_info` is null | `"completed"` | `reward >= 1.0` | `null` |
| `exception_info` is not null OR `verifier_result` is null OR `verifier_result.rewards` is null | `"errored"` | `null` | `exception_info.class` if present, else `"UnknownError"` |

Rationale: the spec §8.3a "errored-vs-completed" partition is binary. The verifier-output presence test is the canonical completion signal (harbor's `JobResult` envelope carries `verifier_result: null` precisely when the trial did not reach verification). The `exception_info.class` dominates as the error class when both branches fire (e.g., post-verifier exception).

The `reward >= 1.0` threshold matches `benchmarks/dab/aggregate.py:21` (PORT-OUT inventory entry) and is the DAB convention. Razorback core's reducer treats it as the benchmark-agnostic "passed" predicate per phase2 AC-8, adapters that use a different reward scale tag their trials' rewards so this threshold holds, or publish a per-adapter `passed_threshold` field on `stratum.json` for future extension (out of scope for this ship; ade-bench's adapter sets the precedent when it lands).

---

## Counting rule (reducer-side, consumed by xm Task 2)

For each stratum group:

```
n_total      = len(records)
n_completed  = len([r for r in records if r.state == "completed"])
n_errored    = len([r for r in records if r.state == "errored"])
n_pass       = len([r for r in records if r.state == "completed" and r.passed])
pass_at_1    = n_pass / n_completed                            # iff n_completed > 0
wilson_ci    = wilson_ci(n_pass, n_completed, alpha)           # iff n_completed > 0
```

Invariants:

- `n_total == n_completed + n_errored` always.
- `n_pass <= n_completed` always.
- The pass@1 denominator is **always** `n_completed`, never `n_total`. A stratum with one pass + one fail + one errored has `pass_at_1 == 0.5`, NOT `0.333…`.

Run-level (stratified) rollup:

```
stratified_n_total      = sum(stratum.n_total      for stratum in strata)
stratified_n_completed  = sum(stratum.n_completed  for stratum in strata)
stratified_n_errored    = sum(stratum.n_errored    for stratum in strata)
stratified_pass_at_1    = mean(stratum.pass_at_1   for stratum in strata if stratum.pass_at_1 is not None)
```

The macro-average reducer (xm AC-1) operates on `pass_at_1` values, NOT on raw `n_pass / n_completed` ratios, strata where `pass_at_1 is None` (all-errored) drop out of the macro-average rather than zero-counting. If every stratum's `pass_at_1 is None`, `stratified_pass_at_1 is None` and the top-level `error_reason` fires (see "Null-result rule" below).

---

## Null-result rule (reducer-side, consumed by xm Task 3)

When a stratum has `n_completed == 0` (all trials errored):

- `pass_at_1` is `None` (JSON `null`), NOT `0.0` and NOT raised.
- `wilson_ci` is `None`, NOT `[0.0, 0.0]`.
- `n_pass` is `0`.
- `error_reason` is set (see "Error-reason rule" below).

When the run has `stratified_n_completed == 0` across every stratum:

- `stratified_pass_at_1` is `None`.
- Top-level `error_reason` is set, naming the dominant exception class across all errored trials in the run.

Rationale: a stratum-or-run with no completions has no rate to report. Zero-counting (`pass_at_1: 0.0`) silently treats "we don't know" as "everyone failed", the §9.2 counting-honesty discipline forbids it. The downstream `--against-constant` verdict (xm Task 4) preserves this, a `pass_at_1: null` produces `verdict: null` rather than a comparison against the constant.

---

## Error-reason rule (reducer-side, consumed by xm Task 3)

`error_reason` names the dominant exception class across the errored trials in the group:

- **Per-stratum** `error_reason`: the most-frequent `error_class` value across that stratum's errored trials. Ties broken alphabetically. Only set when `n_completed == 0`; absent (key not present) otherwise.
- **Top-level** `error_reason`: same logic across all errored trials in the run. Only set when `stratified_n_completed == 0`; absent otherwise.

The dominant-class rule (rather than enumerating all classes) keeps the wire shape scalar and operator-scannable. The full per-trial exception detail lives in `result.json`; `error_reason` is the headline for the score readout. If the operator needs the full breakdown, they grep `result.json` files; this is the same precedent as `summary.json` carrying scalar headline fields rather than enumerated traces.

When a stratum has mixed `completed` + `errored` trials (n_completed > 0), `error_reason` is NOT set on that stratum, the `pass_at_1` and `wilson_ci` carry the signal, and `n_errored` carries the count for the operator to flag if it crosses an acceptable-error-rate threshold. (The acceptable threshold itself is an operator-policy decision; this plan does not encode one.)

`"UnknownError"` is the fallback string when an errored trial has neither `exception_info.class` nor any other identifying field. It indicates a malformed `result.json` rather than a specific exception type and should rarely appear in healthy runs; its presence in `error_reason` is a signal to the operator that the run-dir itself is suspect.

---

## Wire shape (renderer-side, consumed by xm Task 5)

Per-stratum object inside `report["strata"][<label>]`:

```json
{
  "n_total": 3,
  "n_completed": 2,
  "n_errored": 1,
  "n_pass": 1,
  "pass_at_1": 0.5,
  "wilson_ci": [0.094, 0.906],
  "error_reason": null
}
```

- `n_total`, `n_completed`, `n_errored`, `n_pass`: non-negative integers; always present.
- `pass_at_1`: float in `[0.0, 1.0]` OR `null` when `n_completed == 0`.
- `wilson_ci`: pair `[lo, hi]` OR `null` when `n_completed == 0`.
- `error_reason`: string OR `null`. Present-and-null on no-error and mixed paths; present-and-set on `n_completed == 0`.

Top-level rollup fields inside `report`:

```json
{
  "stratified_pass_at_1": 0.5,
  "stratified_n_total": 6,
  "stratified_n_completed": 4,
  "stratified_n_errored": 2,
  "error_reason": null
}
```

Same null-encoding discipline: `stratified_pass_at_1` is `null` and top-level `error_reason` is the string when every stratum's pass@1 is null; otherwise top-level `error_reason` is `null` and `stratified_pass_at_1` is the macro-average.

The `error_reason: null` default on the no-error and mixed paths is load-bearing for the schema snapshot (xm Task 9): every stratum object carries the `error_reason` key regardless of whether it's set, so the JSON shape is stable under §3.3.

---

## AC ↔ task map

| AC (entity body) | Governing §-cite | Task(s) |
|------------------|------------------|---------|
| AC-1 (Wilson 95% CI per stratum + stratified mean) | spec §3.2; §8.3a | Owned by xm's `phase4a-rk-score-wilson-stratified` Task 2 + Task 6. This plan provides the `reduce_trials` signature only. |
| AC-2 (trial-state taxonomy: errored not silently counted as failed passes; `n_completed` denominator; `score: null` + `error_reason` on all-errored) | spec §3.2; §8.3a; §9.2 | Task 1 (state-taxonomy fixtures + loader-side assertion); Task 2 (reducer counting + null-result rule tests); Task 3 (error-reason rule test). xm imports these as its Task 2 Step 4 + Task 3 Steps 1-3. |
| AC-3 (`--against-constant <name=value>` inside-CI / outside-CI line per stratum) | spec §3.2; §8.3a | Owned by xm's Task 4. This plan provides the `pass_at_1 is None → verdict is null` rule that xm's Task 4 Step 4 imports. |
| AC-4 (adapter's stratum tagging honored without hard-coding) | spec §8.3a; phase2 AC-8 | Owned by xm's Task 1 + Task 8. This plan's fixtures use DAB-shaped tags for consistency but do not pin tag shape. |
| AC-5 (JSON output stable under §3.3 semver) | spec §3.3 | Owned by xm's Task 9 snapshot. This plan pins the `error_reason` key's presence-with-null-default discipline that the snapshot exercises. |

---

## Task 1, Error-state taxonomy fixtures + loader-side assertion (AC-2 prerequisite)

**Files:**

- Create: `tests/fixtures/score/error_taxonomy/` (handcrafted four-trial run-dir, one trial per state cell)
  - `trial-pass/result.json`, `verifier_result.rewards.reward: 1.0`, `exception_info: null`
  - `trial-fail/result.json`, `verifier_result.rewards.reward: 0.0`, `exception_info: null`
  - `trial-error-subprocess/result.json`, `verifier_result: null`, `exception_info.class: "SubprocessError"`
  - `trial-error-other/result.json`, `verifier_result: null`, `exception_info.class: "TimeoutError"`
  - Each trial has `agent/stratum.json` with `{"stratum": {"dataset": "bookreview", "query_id": <N>}}`.
- Create: `tests/unit/test_score_counting.py` (this fragment's net-new test file)

**Spec cite:** §8.3a (errored-vs-completed); state-derivation table above.

**Steps:**

- [ ] **Step 1: Construct the four-trial fixture under `tests/fixtures/score/error_taxonomy/`.**

Each `result.json` mirrors the real-fixture shape at `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/bookreview-q1__xgRg3Eo/result.json` (read at plan time): top-level `verifier_result`, `exception_info`, `step_results`. Only the fields the state-derivation table reads need realistic values; other fields can be minimal stubs.

- [ ] **Step 2: Failing test, loader maps each cell correctly.**

```python
def test_loader_resolves_four_state_cells():
    records = load_run_dir(FIXTURE_ROOT / "error_taxonomy")
    by_name = {r.trial_name: r for r in records}
    assert by_name["trial-pass"].state == "completed"
    assert by_name["trial-pass"].passed is True
    assert by_name["trial-pass"].error_class is None

    assert by_name["trial-fail"].state == "completed"
    assert by_name["trial-fail"].passed is False
    assert by_name["trial-fail"].error_class is None

    assert by_name["trial-error-subprocess"].state == "errored"
    assert by_name["trial-error-subprocess"].passed is None
    assert by_name["trial-error-subprocess"].error_class == "SubprocessError"

    assert by_name["trial-error-other"].state == "errored"
    assert by_name["trial-error-other"].passed is None
    assert by_name["trial-error-other"].error_class == "TimeoutError"
```

This is the load-bearing seam; xm's Task 1 Step 1 imports this fixture and re-asserts it.

- [ ] **Step 3: Run the test red, then await xm's Task 1 implementation, then green.**

`uv run pytest tests/unit/test_score_counting.py::test_loader_resolves_four_state_cells -v`

- [ ] **Step 4: Commit.** `pkg2-v2: error-state taxonomy fixtures + loader-side assertion`.

---

## Task 2, Reducer counting + null-result rule tests (AC-2 reducer-side)

**Files:**

- Extend: `tests/unit/test_score_counting.py`

**Spec cite:** §3.2 + §8.3a + §9.2 (counting-honesty); counting rule + null-result rule above.

**Steps:**

- [ ] **Step 1: Failing test, `n_completed` denominator, mixed strata.**

Fixture: one stratum with one pass + one fail + one errored. Assert:

```python
report = reduce_trials(records, alpha=0.05)
assert report.strata["bookreview"].n_total == 3
assert report.strata["bookreview"].n_completed == 2
assert report.strata["bookreview"].n_errored == 1
assert report.strata["bookreview"].n_pass == 1
assert report.strata["bookreview"].pass_at_1 == 0.5  # NOT 0.333...
assert report.strata["bookreview"].error_reason is None  # mixed path
```

- [ ] **Step 2: Failing test, all-completed denominator edge case.**

Fixture: one stratum with three passes (no errors). Assert `n_total == n_completed == 3`, `n_errored == 0`, `pass_at_1 == 1.0`, `wilson_ci` not null, `error_reason is None`.

- [ ] **Step 3: Failing test, all-errored stratum yields null pass@1 + null Wilson CI.**

Fixture: one stratum with three errored trials. Assert `pass_at_1 is None`, `wilson_ci is None`, `n_pass == 0`, `n_completed == 0`, `n_errored == 3`.

- [ ] **Step 4: Failing test, all-errored run-level rollup.**

Fixture: two strata, both with all-errored trials. Assert `stratified_pass_at_1 is None`, `stratified_n_completed == 0`, top-level `error_reason` is set (test value in Task 3).

- [ ] **Step 5: Failing test, macro-average drops null strata.**

Fixture: three strata, A: 2-pass 0-fail 0-errored (pass@1=1.0); B: 0-pass 2-fail 0-errored (pass@1=0.0); C: 0-pass 0-fail 2-errored (pass@1=None). Assert `stratified_pass_at_1 == 0.5` (mean of `[1.0, 0.0]`, NOT `(1.0+0.0+0)/3 = 0.333`).

- [ ] **Step 6: Run tests red, await xm Task 2 + Task 3 implementation, then green.**

`uv run pytest tests/unit/test_score_counting.py -v`

- [ ] **Step 7: Commit.** `pkg2-v2: reducer counting + null-result rule tests`.

---

## Task 3, Error-reason rule tests (AC-2 error_reason field)

**Files:**

- Extend: `tests/unit/test_score_counting.py`

**Spec cite:** §8.3a (errored-vs-completed); error-reason rule above.

**Steps:**

- [ ] **Step 1: Failing test, single-class all-errored stratum names the class.**

Fixture: stratum A with three trials, all `error_class: "SubprocessError"`. Assert `report.strata["A"].error_reason == "SubprocessError"`.

- [ ] **Step 2: Failing test, mixed-class all-errored stratum picks dominant.**

Fixture: stratum A with two `SubprocessError` + one `TimeoutError`. Assert `report.strata["A"].error_reason == "SubprocessError"`.

- [ ] **Step 3: Failing test, tie broken alphabetically.**

Fixture: stratum A with one `SubprocessError` + one `TimeoutError` (1 ↔ 1). Assert `report.strata["A"].error_reason == "SubprocessError"` (alphabetical).

- [ ] **Step 4: Failing test, top-level error_reason on all-errored run.**

Fixture: two strata, A: three `SubprocessError`; B: one `SubprocessError` + two `TimeoutError`. Total: four `SubprocessError` + two `TimeoutError`. Assert `report.error_reason == "SubprocessError"`.

- [ ] **Step 5: Failing test, mixed stratum has no per-stratum error_reason.**

Fixture: stratum A with one pass + one errored (`SubprocessError`). Assert `report.strata["A"].error_reason is None` (n_completed > 0; error_reason absent on mixed paths).

- [ ] **Step 6: Failing test, `UnknownError` fallback when error_class is null.**

Fixture: stratum A with three errored trials, all with `exception_info: null` (malformed `result.json` shape, loader fills `error_class = "UnknownError"`). Assert `report.strata["A"].error_reason == "UnknownError"`.

- [ ] **Step 7: Run tests red, await xm Task 3 implementation, then green.**

`uv run pytest tests/unit/test_score_counting.py -v`

- [ ] **Step 8: Commit.** `pkg2-v2: error-reason rule tests`.

---

## Task 4, Coordination check: xm folds the rules into its task list (AC-1..AC-5 cross-plan)

**Files:**

- No new files; this is a verification step that xm's `phase4a-rk-score-wilson-stratified` plan reflects this fragment's rules.

**Steps:**

- [ ] **Step 1: Re-read `docs/razorback-implementation/plans/phase4a-rk-score-wilson-stratified.md` AC ↔ task map.**

Verify the table's AC-3 row cites this fragment (line 47 in xm's plan at commit-time: "AC-3 (counting honesty: `n_completed` denominator; `n_errored` exposed; all-errored → null + `error_reason`) | spec §9.2 (counting-honesty); §8.3a (AC-4.4 contract reference) | Task 1 (loader extracts state); Task 2 (reducer uses `n_completed`); Task 3 (all-errored null branch)").

- [ ] **Step 2: Verify xm Task 1 Step 1's TrialRecord shape carries the required fields.**

xm's Task 1 names `state`, `passed`, `error_class` on `TrialRecord`. Confirmed at xm plan lines 76-82.

- [ ] **Step 3: Verify xm Task 2 Step 4 covers the `n_completed` denominator test.**

xm plan line 177 ("Fixture: stratum A has one completed-pass, one completed-fail, one errored. Assert ... `pass_at_1 == 0.5` (1/2, NOT 1/3).") confirms the test belongs to xm's task list; this fragment's Task 2 Step 1 is the same test with `error_reason is None` added.

- [ ] **Step 4: Verify xm Task 3 covers null + error_reason branch.**

xm plan lines 192-222 (Task 3) directly implements this fragment's Task 2 + Task 3 rules.

- [ ] **Step 5: If any drift between this fragment's rules and xm's task descriptions surfaces, file a corrections task and ping `team-lead`.**

If xm's plan needs an edit, route through the first officer rather than directly amending xm's plan from this fragment.

- [ ] **Step 6: Commit the coordination verification.**

No file changes; commit message: `pkg2-v2: coordination check against xm phase4a-rk-score-wilson-stratified` (empty commit allowed if no other commits in this task).

---

## Out of scope (verbatim from entity)

- Paired-comparison statistics (per-query exact-McNemar, Holm-Bonferroni family-wise correction, paired bootstrap CI). Spec §8.3 names these as `rk diff`'s responsibility, shipping in Phase 4b when the autoresearch loop needs them.
- TOST equivalence testing. Per the v2 design call: advanced stats in code is overkill; the analyze-stage agent interprets `rk score`'s numbers.
- Markdown formatting. Spec §3.1 names JSON as the default; `--format markdown` is a polish flag, defer until consumer demand.
- Per-trial cost/latency accounting. Spec §3.2 names `rk runs cost` as the cost-summary surface; PKG-2 v2 stays in the score domain.

---

## Naming conventions per CL's rules

- Field: `n_completed`, `n_errored`, `n_total`, `n_pass` (not `completed_count`, not `n_passed_v2`).
- Field: `error_reason` (not `dominant_error`, not `error_class_majority`).
- State value: `"completed"` / `"errored"` (not `"complete"` / `"error"`, not `"ok"` / `"fail"`).
- Test file: `tests/unit/test_score_counting.py` (not `test_pkg2_v2.py`, not `test_counting_honesty_v2.py`).
- The `wilson_ci` import keeps its current name per xm's plan and the module inventory's KEEP-EXTRACT note.
