# Phase 4a — `rk score` Wilson CIs + stratified mean + `--against-constant` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `rk score <run-dir>` as the single-run statistical readout per spec §3.2 + §8.3a. Given one harbor run-dir, the command emits JSON (or markdown) carrying per-stratum pass@1 with Wilson 95% CI (level via `--alpha`), the run's overall stratified pass@1 (macro-average across strata), per-stratum trial counts with the errored-vs-completed distinction (counting-honesty per §9.2; folds in `pkg2-v2-rk-score-counting`), and when invoked with `--against-constant <name=value>`, an inside-CI / outside-CI verdict per stratum so the paper-reproduction readout for goals 1+2 can answer "did we reproduce" against the published 0.577 (spacedock) / 0.4376 (direct-baseline) constants.

**Architecture:** `rk score` is a thin Typer subcommand on top of three pure-functional units. Three layers:

- **Loader** (`score/load.py`): walks `<run-dir>/<trial-name>/result.json` (per-trial agent result with completed/errored status) plus `<run-dir>/<trial-name>/agent/stratum.json` (the side-channel emitted by the phase2 DAB harbor adapter per phase2 Task 11, AC-8); produces a list of `TrialRecord` dicts with stratum tag, pass/fail (`reward >= 1.0`), and error state (non-zero exit, no verifier output). Also reads `<run-dir>/per_trial_outcomes.json` (the v1 wire format Phase 1's translator emits in the harbor run-dir root) as the secondary outcomes source, with `result.json` precedence for the errored/completed taxonomy that `per_trial_outcomes.json` lacks.
- **Reducer** (`score/reduce.py`): groups `TrialRecord` by stratum, computes per-stratum (`n_completed`, `n_errored`, `n_total`, `pass_at_1`, `wilson_ci`), and the macro-average stratified mean across per-stratum pass@1. Wilson CI is `from razorback.diff.stats import wilson_ci` — the verbatim KEEP-EXTRACT primitive at `src/razorback/diff/stats.py:14-33` per the module inventory at `docs/superpowers/plans/2026-05-19-razorback-inventory.md:482-501`.
- **Renderer** (`score/render.py`): emits JSON (default) per the §3.3 stable-schema promise, or markdown (`--format markdown`) with one row per stratum + a final stratified-mean row + optional `--against-constant` verdict lines.

The CLI front-end (`cli/score.py`) wires `--alpha`, `--format`, `--against-constant`, and the run-dir positional. `--against-constant <name=value>` parses to `(name, float(value))` and emits one verdict per stratum: `<name>=<value>` is inside the stratum's CI (`matches`) or outside (`outside-CI`), plus a final verdict on the stratified mean.

The reducer is benchmark-agnostic. AC-8 (phase2)'s `stratum.json` shape is `{"dataset": "bookreview", "query_id": 1, "backends": [...]}` for DAB; ade-bench's harbor adapter will land its own `stratum.json` shape (e.g., `{"split": "test", "category": "..."}`). `rk score` reads the `stratum` key and uses its scalar fields (skipping list-typed fields like `backends`) to construct the stratum label; the default stratum scope is `dataset` for DAB and the adapter's primary scalar key otherwise. The `--stratify-by <field>` flag (out of scope for AC-1..AC-9; named here for future extension) is not implemented in this phase; the default field selection is hard-coded to `dataset` with a fallback to the first scalar field. Per the entity's AC-6 ("benchmark-agnostic stratified mean reducer"), the reducer never names DAB.

**Tech Stack:** Python 3.12, Typer (subcommand registration), `scipy.stats.norm` (already a dependency via `diff/stats.py`), `pathlib`, `json`. No new dependencies. Markdown output is a string template — no markdown library needed.

**Spec source of truth:** `/Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`. This plan cites:

- §3.2 (`rk score` CLI surface: `rk score <run-dir> [--format markdown|json] [--alpha 0.05]`; behavior: per-stratum Wilson CI + stratified mean + `--against-constant`).
- §3.3 (semver promise: JSON output stable within the major version).
- §8.3a (single-run statistical readout: Wilson CI per stratum, stratified mean, errored-vs-completed counting, `--against-constant` paper-reproduction line).
- §9.2 (counting-honesty discipline; the source of the AC-4.4 contract referenced from §8.3a).
- Module inventory `docs/superpowers/plans/2026-05-19-razorback-inventory.md:482-501` (`diff/stats.py:14-33` `wilson_ci` is KEEP-EXTRACT verbatim; `benchmarks/dab/aggregate.py` is PORT-OUT — the DAB-shaped stratified-mean aggregator does NOT come into razorback core).

**Input contracts (dependencies):**

- **`phase3-spacedock-solver-v2` (sealed-state contract):** `rk score` reads the harbor run-dir produced by `rk run`. The run-dir layout in harbor 0.6.6 (verified by phase3 Task 6 at `<run-dir>/_razorback/freeze/<sealed_hash>/`) places per-trial output at `<run-dir>/<trial-name>/result.json` (per the existing fixture at `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/`) and the per-run summary at `<run-dir>/summary.json` with `summary_version: 1`. The sealed-state contract is the run-dir-as-input boundary: `rk score` reads the run-dir as a black box and never reaches into the `_razorback/freeze/` tree.
- **Phase 2 DAB harbor adapter (AC-8 stratum tagging):** Per phase2 Task 11 (completed per task #34), every trial carries a `stratum.json` side-channel file at `<run-dir>/<trial-name>/agent/stratum.json` (or wherever phase2's verifier `test.sh` placed it — phase2's plan calls out `/logs/verifier/stratum.json` as the trial-end landing site). The shape is `{"stratum": {"dataset": "bookreview", "query_id": 1, "backends": [...]}}`. `rk score` reads the `stratum.dataset` field as the default stratum label; if absent, falls back to the v1 `per_trial_outcomes.json` `dataset` field. Phase2 AC-8's verbatim text "rk score consumes via stratum.json" pins this consumer-side contract.
- **`pkg2-v2-rk-score-counting` (counting-honesty integration):** The errored-vs-completed distinction lives in this entity's AC-3 (folds in `dk` pkg2-v2 AC-1+AC-2). The per-trial `result.json` already carries `completed` / `errored` status (per the fixture's `stats.n_completed_trials` + `stats.n_errored_trials` keys); the loader maps these to per-trial `state` and the reducer counts only `state == "completed"` in the denominator.

**Phase dependencies:**

- **`phase1-rk-run-v2-wrapper` (landed):** Provides the harbor run-dir layout `rk score` reads from. Phase 1's `rk run` invokes harbor and writes provenance into the run-dir; `rk score` is purely read-only against that artifact.
- **`phase2-dab-harbor-adapter` (in progress; AC-8 task 11 already completed per #34):** Provides the per-trial stratum tagging this consumer reads. The producer-consumer contract pin (phase2 Task 11 Step 3 integration test) lives on the producer side; this plan's AC-5 integration test exercises the consumer side against the same fixture pattern.
- **`pkg1-v2-rk-runs-cli` (plan approved):** Sibling CLI surface for `rk runs list/show/cost`. Independent — `rk score` and `rk runs *` share no code.

---

## AC ↔ task map

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 (per-stratum Wilson 95% CI + overall stratified pass@1) | spec §3.2; §8.3a | Task 2 (Wilson + stratified mean reducer); Task 6 (CLI wires `--alpha`) |
| AC-2 (Wilson CI fixture correctness, literature reference values) | spec §8.3a (Wilson 1927) | Task 2 unit test against `n=20, k=10, CI=[0.299, 0.701]` |
| AC-3 (counting honesty: `n_completed` denominator; `n_errored` exposed; all-errored → null + `error_reason`) | spec §9.2 (counting-honesty); §8.3a (AC-4.4 contract reference) | Task 1 (loader extracts state); Task 2 (reducer uses `n_completed`); Task 3 (all-errored null branch) |
| AC-4 (`--against-constant <name=value>` inside/outside-CI per stratum) | spec §3.2 (paper-reproduction line); §8.3a | Task 4 (verdict logic); Task 6 (CLI flag) |
| AC-5 (paper-reproduction readout shape on real run-dir) | spec §8.3a ("uses this to check whether the published 0.577/0.4376 numbers fall within the run's CI") | Task 7 (integration test against `.runs/baseline-rerun-20260520-bookreview/` fixture) |
| AC-6 (adapter stratum tagging honored without hard-coding) | spec §8.3a ("per the adapter's stratum tagging"); phase2 AC-8 | Task 1 (loader reads `stratum.json` generically); Task 8 (ade-bench fixture test alongside DAB fixture test) |
| AC-7 (`--format markdown` human-readable equivalent) | spec §3.2 (`--format markdown\|json`) | Task 5 (markdown renderer); Task 6 (CLI flag) |
| AC-8 (JSON output stable under §3.3 semver promise) | spec §3.3 | Task 9 (snapshot test pins schema keys) |
| AC-9 (`uv run pytest` exits 0) | n/a | Task 10 (suite-green sweep from worktree branch tip) |

**Riskiest contract first.** Task 1 (the loader's input contract — what `rk score` reads from disk) is the load-bearing seam: every downstream test exercises trial records the loader produced. Per CL's "Validating new mechanisms" rule, Task 1 ships before the reducer (Task 2), because if the loader's view of "trial state" or "stratum tag" misreads the on-disk shape, the reducer's correctness is meaningless. Task 1's smallest end-to-end exercise is a three-trial fixture (one completed-success, one completed-failure, one errored) the loader resolves and the test asserts back as a list of `TrialRecord` dicts with the expected `state` and `stratum` values.

The second-riskiest contract is the JSON output schema (AC-8). Task 9's snapshot test lands at the end of the plan once Tasks 1-5 have stabilized the shape, but a placeholder key list lives in Task 5's renderer docstring from the start so reviewers can audit drift.

---

## Task 1 — Loader: walk run-dir, read trial state + stratum (`src/razorback/score/load.py`, AC-1 + AC-3 + AC-6 prerequisite)

**Files:**
- Create: `src/razorback/score/__init__.py`
- Create: `src/razorback/score/load.py`
- Create: `tests/unit/test_score_load.py`
- Create: `tests/fixtures/score/mixed_trial_run_dir/` (handcrafted three-trial run-dir: one completed-success, one completed-failure, one errored, all tagged `dataset: bookreview`)

**Spec cite:** §3.2 (rk score reads `<run-dir>`); §8.3a (errored-vs-completed counting); phase2 plan Task 11 (stratum.json contract); module inventory entry for `benchmarks/dab/aggregate.py` (PORT-OUT — razorback does NOT carry DAB-specific aggregation logic).

`TrialRecord` is a small dataclass (or TypedDict) with fields:

```python
{
    "trial_name": str,          # e.g., "bookreview-q1__xgRg3Eo"
    "stratum": str,             # e.g., "bookreview" — the resolved stratum label
    "state": str,               # "completed" | "errored"
    "passed": bool | None,      # True/False for completed; None for errored
    "reward": float | None,     # from per_trial_outcomes.json; None on errored
    "error_class": str | None,  # dominant exception class when errored
}
```

**Steps:**

- [ ] **Step 1: Failing test — three-trial run-dir loads to three records.**

Construct the fixture at `tests/fixtures/score/mixed_trial_run_dir/`:

```
mixed_trial_run_dir/
├── per_trial_outcomes.json   # outcomes_version: 1; three rows
├── summary.json              # summary_version: 1
├── trial-completed-pass/
│   ├── result.json           # status: completed; verifier reward 1.0
│   └── agent/stratum.json    # {"stratum": {"dataset": "bookreview", "query_id": 1}}
├── trial-completed-fail/
│   ├── result.json           # status: completed; verifier reward 0.0
│   └── agent/stratum.json    # {"stratum": {"dataset": "bookreview", "query_id": 2}}
└── trial-errored/
    ├── result.json           # status: errored; non-zero exit; no verifier output
    └── agent/stratum.json    # {"stratum": {"dataset": "bookreview", "query_id": 3}}
```

Assert `load_run_dir(<path>)` returns three `TrialRecord` rows with the expected `state` / `passed` / `stratum` triples.

- [ ] **Step 2: Implement the loader.**

```python
def load_run_dir(run_dir: Path) -> list[TrialRecord]:
    """Walk <run-dir>/<trial-name>/, read result.json + agent/stratum.json per trial."""
```

Walks `run_dir.iterdir()` for trial subdirs (filtering against non-trial children like `summary.json`, `provenance.yaml`, `tasks/`, the v1 `per_trial_outcomes.json` file). For each trial dir, reads `result.json` to get `status` and either `evals.*.metrics[0].mean` (per-trial reward) or `evals.*.errors[0].class` (error class). Reads `agent/stratum.json` (falling back to `logs/verifier/stratum.json` per the phase2 verifier landing site) and resolves `stratum.dataset` as the default stratum label. If `stratum.json` is absent, falls back to the per-trial-outcomes `dataset` field via `per_trial_outcomes.json` lookup. If both are absent, raises `ScoreInputError("trial X has no stratum tag")`.

- [ ] **Step 3: Run the test green.**

`uv run pytest tests/unit/test_score_load.py -v`

- [ ] **Step 4: Commit.** `phase4a: rk score loader, walks run-dir for per-trial state + stratum`.

---

## Task 2 — Reducer: per-stratum Wilson CI + stratified mean (`src/razorback/score/reduce.py`, AC-1 + AC-2 + AC-3 + AC-6)

**Files:**
- Create: `src/razorback/score/reduce.py`
- Create: `tests/unit/test_score_reduce.py`

**Spec cite:** §8.3a (Wilson CI per stratum + macro-average stratified mean + `n_completed` denominator).

```python
from razorback.diff.stats import wilson_ci  # KEEP-EXTRACT verbatim

def reduce_trials(records: list[TrialRecord], *, alpha: float) -> ScoreReport:
    """Group by stratum, compute per-stratum stats, stratified mean."""
```

The output `ScoreReport` carries:

```python
{
    "score_version": 1,
    "alpha": 0.05,
    "strata": {
        "bookreview": {
            "n_total": 3,
            "n_completed": 2,
            "n_errored": 1,
            "n_pass": 1,
            "pass_at_1": 0.5,
            "wilson_ci": [0.094, 0.906],
        },
        ...
    },
    "stratified_pass_at_1": 0.5,    # macro-average across strata
    "stratified_n_completed": 2,
    "stratified_n_errored": 1,
}
```

**Steps:**

- [ ] **Step 1: Failing test — Wilson CI at n=20, k=10, α=0.05 matches literature [0.299, 0.701].**

Construct twenty synthetic `TrialRecord` rows (ten passed, ten failed, all completed, all `stratum=A`). Assert `reduce_trials(records, alpha=0.05).strata["A"].wilson_ci == approx((0.299, 0.701), abs=1e-3)`. Reference: Wilson 1927; the [0.299, 0.701] value is in Newcombe 1998's Table 1 row n=20, k=10.

- [ ] **Step 2: Failing test — α=0.10 half-width shrinks vs α=0.05.**

Same fixture; assert `wilson_ci(α=0.10)` half-width < `wilson_ci(α=0.05)` half-width by at least 10% (the z-shift from 1.96 to 1.645 narrows the interval).

- [ ] **Step 3: Failing test — stratified mean = macro-average of per-stratum pass@1.**

Fixture: three strata with pass@1 of 0.6, 0.4, 0.2 (e.g., A: 6/10 passed; B: 4/10; C: 2/10; all completed). Assert `stratified_pass_at_1 == (0.6 + 0.4 + 0.2) / 3 == approx(0.4)`. NOT a trial-weighted average — the spec's macro-average gives each stratum equal weight regardless of N.

- [ ] **Step 4: Failing test — denominator is `n_completed`, not `n_total`.**

Fixture: stratum A has one completed-pass, one completed-fail, one errored. Assert `strata["A"].n_completed == 2`, `strata["A"].n_errored == 1`, `strata["A"].n_total == 3`, `strata["A"].pass_at_1 == 0.5` (1/2, NOT 1/3).

- [ ] **Step 5: Implement the reducer.**

`scipy.stats.norm` already imported via `diff/stats.py`. `reduce.py` imports `wilson_ci` from there.

- [ ] **Step 6: Run tests green.**

`uv run pytest tests/unit/test_score_reduce.py -v`

- [ ] **Step 7: Commit.** `phase4a: rk score reducer, per-stratum Wilson CI + macro-average stratified mean`.

---

## Task 3 — Counting honesty: all-errored stratum → null score + `error_reason` (`reduce.py` branch + tests, AC-3)

**Files:**
- Extend: `src/razorback/score/reduce.py`
- Extend: `tests/unit/test_score_reduce.py`

**Spec cite:** §8.3a (AC-4.4 contract reference); `pkg2-v2-rk-score-counting` AC-2.

When a stratum has `n_completed == 0` (all trials errored), `pass_at_1` is `None`, `wilson_ci` is `None`, and an `error_reason` field names the dominant exception class (the most-frequent `error_class` across the stratum's errored trials, with ties broken alphabetically).

The same logic applies at the run level: if `n_completed == 0` across every stratum, `stratified_pass_at_1` is `None` and a top-level `error_reason` is emitted.

**Steps:**

- [ ] **Step 1: Failing test — all-errored stratum yields null score + error_reason.**

Fixture: three errored trials in stratum A, all `error_class: "SubprocessError"`. Assert `strata["A"].pass_at_1 is None`, `strata["A"].wilson_ci is None`, `strata["A"].error_reason == "SubprocessError"`.

- [ ] **Step 2: Failing test — mixed errored classes, dominant wins.**

Fixture: two `SubprocessError` + one `TimeoutError` all errored. Assert `error_reason == "SubprocessError"`.

- [ ] **Step 3: Failing test — all-errored run-level rollup.**

Fixture: every trial across two strata errored. Assert `stratified_pass_at_1 is None`, top-level `error_reason` set.

- [ ] **Step 4: Implement the null + error_reason branches.**

- [ ] **Step 5: Run tests green.**

- [ ] **Step 6: Commit.** `phase4a: rk score counting honesty, null score + error_reason on all-errored stratum`.

---

## Task 4 — `--against-constant <name=value>` verdict logic (`src/razorback/score/verdict.py`, AC-4)

**Files:**
- Create: `src/razorback/score/verdict.py`
- Create: `tests/unit/test_score_verdict.py`

**Spec cite:** §3.2 (`--against-constant <name=value>` paper-reproduction line); §8.3a ("matches-published-constant line per stratum").

```python
def against_constant(report: ScoreReport, *, name: str, value: float) -> AgainstConstantReport:
    """For each stratum + the stratified mean, emit inside-CI / outside-CI verdict."""
```

The output:

```python
{
    "name": "paper",
    "value": 0.577,
    "per_stratum": {
        "bookreview": {"verdict": "matches", "ci": [0.50, 0.65]},
        ...
    },
    "stratified": {"verdict": "outside-CI", "mean": 0.4, "ci": None},
}
```

For the stratified-mean row, the CI is `None` in this phase (no run-level bootstrap CI on the macro-average — that's `rk diff`'s territory); the verdict is a point comparison: `matches` when `abs(mean - value) <= tolerance` (tolerance = 0.0; i.e., the stratified mean equals the constant), `above` when `mean > value`, `below` when `mean < value`. This is a degenerate verdict — the operator's quoted CI uses the per-stratum lines. The stratified row exists for operator scanability.

A stratum's verdict is `matches` when `ci_lo <= value <= ci_hi`, else `outside-CI` with the side (`above` if `value > ci_hi`; `below` if `value < ci_lo`).

**Steps:**

- [ ] **Step 1: Failing test — inside-CI verdict.**

Fixture: stratum A's `wilson_ci = [0.50, 0.65]`. Assert `against_constant(report, name="paper", value=0.577).per_stratum["A"].verdict == "matches"`.

- [ ] **Step 2: Failing test — outside-CI verdict, above.**

Same CI; `value=0.70`. Assert `verdict == "outside-CI"`, `side == "above"`.

- [ ] **Step 3: Failing test — outside-CI verdict, below.**

Same CI; `value=0.30`. Assert `verdict == "outside-CI"`, `side == "below"`.

- [ ] **Step 4: Failing test — null score → null verdict.**

Stratum with `pass_at_1 is None` (all errored). Assert verdict is `null` (the JSON shape carries `verdict: null` rather than raising).

- [ ] **Step 5: Implement the verdict logic.**

- [ ] **Step 6: Run tests green.**

- [ ] **Step 7: Commit.** `phase4a: rk score --against-constant, per-stratum inside/outside-CI verdict`.

---

## Task 5 — JSON + markdown renderer (`src/razorback/score/render.py`, AC-7 + AC-8 prep)

**Files:**
- Create: `src/razorback/score/render.py`
- Create: `tests/unit/test_score_render.py`

**Spec cite:** §3.2 (`--format markdown|json`); §3.3 (JSON schema stable within major version).

```python
def render_json(report: ScoreReport, verdict: AgainstConstantReport | None) -> str: ...
def render_markdown(report: ScoreReport, verdict: AgainstConstantReport | None) -> str: ...
```

The markdown renderer produces a per-stratum table:

```
| stratum    | n_completed | n_errored | pass@1 | 95% CI         | vs paper=0.577 |
|------------|-------------|-----------|--------|----------------|----------------|
| bookreview |           2 |         1 |  0.500 | [0.094, 0.906] | matches        |
| ...        |             |           |        |                |                |

stratified pass@1: 0.500  (vs paper=0.577: below)
```

The JSON shape is the `ScoreReport` + optional `against_constant` field; the canonical key list is documented in `render.py`'s module docstring so reviewers can audit drift before Task 9's snapshot lands.

**Steps:**

- [ ] **Step 1: Failing test — JSON keys present and stable.**

Run the renderer against a two-stratum, no-error fixture; assert the JSON parses and `result["strata"]["A"].keys() == {"n_total", "n_completed", "n_errored", "n_pass", "pass_at_1", "wilson_ci", "error_reason"}` (`error_reason` defaults to `null` on no-error path).

- [ ] **Step 2: Failing test — markdown contains one row per stratum + stratified row.**

Assert the markdown output has `(n_strata + 1)` data rows + the stratified summary line.

- [ ] **Step 3: Failing test — markdown carries verdict column when `against_constant` is set.**

Assert presence of `"vs paper=0.577"` column header and `"matches"` / `"outside-CI"` values in the rows.

- [ ] **Step 4: Implement both renderers.**

- [ ] **Step 5: Run tests green.**

- [ ] **Step 6: Commit.** `phase4a: rk score JSON + markdown renderers`.

---

## Task 6 — CLI wiring: `rk score` Typer subcommand (`src/razorback/cli/score.py`, AC-1 + AC-4 + AC-7 wiring)

**Files:**
- Create: `src/razorback/cli/score.py`
- Modify: `src/razorback/cli/__init__.py` (register the subcommand)
- Create: `tests/unit/test_cli_score.py`

**Spec cite:** §3.2 (`rk score <run-dir> [--format markdown|json] [--alpha 0.05]`).

```python
@app.command("score")
def score_command(
    run_dir: Path,
    alpha: float = typer.Option(0.05, "--alpha"),
    format: str = typer.Option("json", "--format"),
    against_constant: str | None = typer.Option(None, "--against-constant"),
):
    """rk score <run-dir>: per-stratum Wilson CIs + stratified mean."""
```

The `--against-constant` value parses as `<name>=<value>`; invalid format → `typer.BadParameter`. `--format` accepts `json` or `markdown` only; anything else → `typer.BadParameter`.

The body:

1. `records = load_run_dir(run_dir)`
2. `report = reduce_trials(records, alpha=alpha)`
3. `verdict = against_constant(report, name=name, value=value) if against_constant else None`
4. `typer.echo(render_json(report, verdict) if format == "json" else render_markdown(report, verdict))`
5. Exit 0 on success; exit 1 with stderr message on `ScoreInputError`.

**Steps:**

- [ ] **Step 1: Failing test — `rk score <fixture-run-dir>` returns exit 0 + valid JSON.**

Using `tests/fixtures/score/mixed_trial_run_dir/` from Task 1; Typer `CliRunner` invocation.

- [ ] **Step 2: Failing test — `--against-constant paper=0.577` adds the verdict block.**

Assert the JSON output's `against_constant` field is populated with the `paper=0.577` comparison.

- [ ] **Step 3: Failing test — invalid `--against-constant` syntax raises BadParameter.**

Pass `--against-constant paper`; assert exit non-zero with `BadParameter` message.

- [ ] **Step 4: Failing test — `--format markdown` returns the markdown table.**

Assert exit 0 and the output contains the table header `| stratum`.

- [ ] **Step 5: Implement the CLI body.**

- [ ] **Step 6: Wire in `cli/__init__.py`.**

```python
from razorback.cli.score import score_command
app.command("score")(score_command)
```

- [ ] **Step 7: Run tests green.**

- [ ] **Step 8: Commit.** `phase4a: rk score CLI, alpha + format + against-constant`.

---

## Task 7 — Integration test: real baseline-rerun run-dir end-to-end (AC-5)

**Files:**
- Create: `tests/integration/test_score_baseline_rerun.py`

**Spec cite:** §8.3a (paper-reproduction readout); entity AC-5.

The fixture is the existing `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/` run-dir (three bookreview trials, all completed-pass per its `summary.json` and `per_trial_outcomes.json`). The test invokes `rk score <that-dir> --against-constant stratified_pass_at_1=0.577 --alpha 0.05` via `CliRunner` and asserts:

- Exit 0.
- JSON output's `strata["bookreview"].pass_at_1 == 1.0`.
- JSON output's `strata["bookreview"].n_completed == 3`, `n_errored == 0`.
- JSON output's `against_constant.per_stratum["bookreview"].verdict in {"matches", "outside-CI"}` (the precise verdict depends on the CI bounds for n=3 k=3 at α=0.05 — the test pins the actual computed verdict, not a hard-coded one, to avoid arithmetic-brittleness on the boundary).

This is the AC-5 paper-reproduction readout shape test; goals 1+2's analyze stage will run this exact command line against fresh harbor-DAB-produced run-dirs.

If the fixture run-dir lacks `agent/stratum.json` (because phase2's stratum tagging hadn't landed when this run-dir was created), Task 7 includes a one-time fixture upgrade step: hand-write `stratum.json` files under each of the three trial dirs to match the bookreview shape. This fixture upgrade is acceptable because the run-dir is a stored test fixture, not a freshly-produced artifact under test.

**Steps:**

- [ ] **Step 1: Verify `agent/stratum.json` presence in the fixture; hand-write if missing.**

Inspect `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/bookreview-q1__xgRg3Eo/`; if `agent/stratum.json` is absent, create it with `{"stratum": {"dataset": "bookreview", "query_id": 1}}` (and matching `query_id: 2, 3` for q2, q3 trials).

- [ ] **Step 2: Failing test — `rk score <fixture> --against-constant stratified_pass_at_1=0.577 --alpha 0.05` exits 0.**

- [ ] **Step 3: Add assertions on the JSON shape.**

- [ ] **Step 4: Run the test green.**

`uv run pytest tests/integration/test_score_baseline_rerun.py -v`

- [ ] **Step 5: Commit.** `phase4a: rk score integration, baseline-rerun bookreview fixture end-to-end`.

---

## Task 8 — Adapter-agnostic stratum tagging: ade-bench fixture (AC-6)

**Files:**
- Create: `tests/unit/test_score_stratum_tagging.py`
- Create: `tests/fixtures/score/ade_bench_run_dir/` (handcrafted three-trial run-dir; stratum tags carry an ade-bench-shaped key, e.g., `{"stratum": {"split": "test", "category": "..."}}`)

**Spec cite:** §8.3a ("per the adapter's stratum tagging"); entity AC-6; phase2 AC-8.

The test constructs two fixtures: one DAB-tagged (stratum key `dataset`) and one ade-bench-tagged (stratum key `split` or whatever ade-bench's harbor adapter will land — for this phase, the test pins the contract that `rk score` reads the first scalar key under `stratum.*` as the label, not the hard-coded string `"dataset"`).

This task pins the future-proofing seam. When `phase4a-ade-bench-harbor-adapter` (backlog) ships, its stratum tags drop into `rk score` without code change.

**Steps:**

- [ ] **Step 1: Failing test — DAB fixture yields `stratum="bookreview"`.**

Reuse `tests/fixtures/score/mixed_trial_run_dir/` from Task 1. Assert the loader's `record.stratum == "bookreview"`.

- [ ] **Step 2: Failing test — ade-bench fixture yields `stratum="test"` (or the first scalar tag).**

Construct `tests/fixtures/score/ade_bench_run_dir/` with three trials; each `agent/stratum.json` carries `{"stratum": {"split": "test", "category": "X"}}`. Assert `record.stratum == "test"` (the first scalar key when `dataset` is absent).

- [ ] **Step 3: Failing test — neither key present raises ScoreInputError naming the trial.**

Construct a trial whose `agent/stratum.json` has `{"stratum": {"backends": ["postgres"]}}` (no scalar fields, only a list). Assert `ScoreInputError` is raised with the trial name in the message.

- [ ] **Step 4: Implement the generic stratum-key resolution in `load.py`.**

Resolution rule: prefer `stratum.dataset` (DAB convention); else first scalar (str / int / float / bool) value in iteration order; else raise.

- [ ] **Step 5: Run tests green.**

- [ ] **Step 6: Commit.** `phase4a: rk score, benchmark-agnostic stratum resolution (DAB + ade-bench fixtures)`.

---

## Task 9 — JSON schema snapshot (AC-8)

**Files:**
- Create: `tests/unit/test_score_json_schema_snapshot.py`
- Create: `tests/fixtures/score/snapshots/score_report_v1.json`

**Spec cite:** §3.3 (semver promise: JSON output stable within the major version).

The snapshot test renders the JSON for a known fixture (the `mixed_trial_run_dir` from Task 1), normalizes float precision to 6 decimal places, and compares against the checked-in `score_report_v1.json`. The test fails if any key is renamed or removed; key additions are allowed (within-major minor change), tested via `assert expected_keys.issubset(actual_keys)`.

If the schema is intentionally changed within a major, the operator updates the snapshot and bumps `score_version` (v1 → v2). For this initial ship, `score_version: 1`.

**Steps:**

- [ ] **Step 1: Generate the canonical snapshot.**

Run `uv run rk score tests/fixtures/score/mixed_trial_run_dir/ --alpha 0.05` once; capture stdout to `tests/fixtures/score/snapshots/score_report_v1.json`. Round floats to 6 dp.

- [ ] **Step 2: Failing test — snapshot keys preserved.**

`assert expected_keys.issubset(actual_keys)` over the recursive key set; fail diff includes the missing keys.

- [ ] **Step 3: Run the test green.**

- [ ] **Step 4: Commit.** `phase4a: rk score JSON schema snapshot, semver-stable key set`.

---

## Task 10 — `uv run pytest` exits 0 sweep (AC-9)

**Files:**
- No new files.

- [ ] **Step 1: Run the full razorback unit suite.**

`uv run pytest tests/unit/ -v 2>&1 | tee /tmp/score-unit.log`. Assert all tests pass; no regression in pre-existing tests.

- [ ] **Step 2: Run the full razorback integration suite.**

`uv run pytest tests/integration/ -v 2>&1 | tee /tmp/score-int.log`. Same assertion.

- [ ] **Step 3: Run the workspace-wide sweep including plugin and phase2.**

`uv run pytest 2>&1 | tee /tmp/score-all.log` (from the repo root; honors the `uv` workspace). Asserts the new `rk score` tests don't shadow plugin or phase2 test discovery.

- [ ] **Step 4: Commit the validation log.**

If any log captures a regression, fix-forward rather than skipping. Commit message: `phase4a: rk score, uv run pytest green from worktree tip`.

---

## Out of scope (verbatim from entity)

- Paired-comparison statistics (per-query exact-McNemar, Holm-Bonferroni family-wise correction, paired bootstrap CI). Spec §8.3 names these as `rk diff`'s responsibility; ships in Phase 4b per `phase4b-rk-diff-paired-stats`.
- TOST equivalence testing. Per the v2 design call: advanced stats in code is overkill; analyze-stage agents interpret.
- Per-trial cost/latency accounting. Spec §3.2 names `rk runs cost` as the cost-summary surface.

---

## Naming conventions per CL's rules

Module / function names tell what the code does (the v2 spec language), not history or implementation:

- Module: `src/razorback/score/` (not `v2_score`, not `score_v2`).
- Function: `load_run_dir`, `reduce_trials`, `render_json`, `against_constant` (not `compute_score_v2`, not `parse_run_dir_new`).
- Dataclass: `TrialRecord`, `ScoreReport`, `AgainstConstantReport` (not `ScoreReportV2`).
- Exception: `ScoreInputError` (not `ScoreInputErrorNew`).

The wilson_ci import from `diff/stats.py` keeps its current name — the inventory marks the function as KEEP-EXTRACT verbatim, so no rename here.
