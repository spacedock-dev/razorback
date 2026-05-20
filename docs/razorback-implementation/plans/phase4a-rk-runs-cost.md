# Phase 4a — `rk runs cost` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `rk runs cost [--root <dir>] [--experiment <name>]` as the read-side cost summary surface. Walk the harbor run-dir layout under `<root>` (optionally filtered by `--experiment`), extract each run-dir's actual cost, and emit a JSON document with per-run breakdown plus a cumulative `total_usd`. The command is a sibling subcommand under the same `runs_app` Typer sub-app that already carries `rk runs list/show/diff`; it shares pkg1-v2's JSON-stable shape under spec §3.3. The subscription-auth cost-telemetry gap (Phase 0 baseline-rerun: `agent_result.cost_usd: null`) is a first-class output state — runs with missing cost data flag `cost_unknown: true` and are excluded from `total_usd` rather than silently zero-summed.

**Spec source of truth:** `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`. Governing sections: §3.2 (`rk runs cost <root>` named in the first-ship subcommand surface alongside `rk runs list/show`), §3.3 (semver promise — JSON keys additive within major version), §3.4 (ExitCode.USAGE=2 on missing input), §7.1 (run-dir layout — the artifacts cost lives in).

**Architecture:** Filesystem read-only. Layered on top of pkg1-v2 (`r0`): the run-dir enumeration reuses `razorback.runs.inspect.list_run_dirs(root, experiment=...)` (already shipped under pkg1-v2 t2). The cost-extraction primitive `read_run_cost(run_dir) -> tuple[float | None, bool]` lives in a new module `src/razorback/runs/cost.py` and follows the cost-source convention shared with `phase4a-rk-run-budget-gate`'s `read_actual_cost_from_run_dir`: precedence is `summary.json` first, then `result.json.stats.cost_usd`, then per-trial `result.json` `step_results[].agent_result.cost_usd` as harbor's current ground-truth field. Returns `(None, False)` when no cost field exists anywhere AND when the field exists but is `null` — both are "cost unknown" from the user's perspective. The CLI body wires up a thin Typer adapter that calls `list_run_dirs` + `read_run_cost` per entry, sums the known costs, and emits JSON. The `rk runs cost` subcommand attaches to `runs_app` at `src/razorback/cli/runs.py` next to the pkg1-v2 `list`/`show` commands.

**Tech Stack:** Python 3.12, Typer (CLI), pytest (tests), pathlib + json stdlib only (no new deps). Fixture run-dirs synthesized in `tmp_path` for unit tests via the `make_run_dir` factory that pkg1-v2 t1 already lands in `tests/unit/conftest.py`; one acceptance pass against the real run-dir under `.runs/baseline-rerun-20260520-bookreview/` (which is the load-bearing subscription-auth fixture — `summary.json` carries no cost field, `result.json.step_results[].agent_result.cost_usd` is `null`).

**Riskiest contract first.** The cost-source precedence is the load-bearing contract because (a) it must match `phase4a-rk-run-budget-gate.read_actual_cost_from_run_dir` exactly (the two are independently implementable but the field name and precedence must agree; either changes → the other tracks — per the budget-gate plan's "sibling backlog" note), and (b) the real run-dir at `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/` ships `summary.json` WITHOUT a `cost_usd` field today and per-trial `result.json` carries `step_results[].agent_result.cost_usd: null` under subscription auth. Task 1 pins fixtures that exercise all three precedence branches (summary-with-cost, result-stats-with-cost, all-null subscription path) before any aggregation or CLI wiring. Task 2 lands the `read_run_cost` primitive against those fixtures so a precedence regression is caught by a unit test, not a CLI integration failure. Aggregation (Task 3) and CLI wiring (Task 4) land on top of a verified primitive.

**Cost-telemetry gap discipline (dispatch checklist item #2).** Subscription-billed Claude leaves `agent_result.cost_usd: null` per Phase 0 baseline-rerun §"Phase 0 side findings" item C. `rk runs cost` distinguishes three states per run-dir:
- **cost present:** numeric value parsed; contributes to `total_usd`; element has `cost_usd: <float>`, `cost_unknown: false`.
- **cost present but null** (subscription auth — field exists, value is `null`): excluded from `total_usd`; element has `cost_usd: null`, `cost_unknown: true`; top-level `n_unknown` counter increments; top-level `warnings` array gets an entry naming the run-dir.
- **cost field absent entirely** (incomplete run-dir, harbor pre-cost-field era): same surface as the null case (`cost_unknown: true`), but treated as identical because from the consumer's perspective both are "we have no number" — distinguishing them adds shape complexity without consumer demand. The cost-source precedence walk records which source was checked-and-missing for diagnostic purposes via a `cost_source: "summary" | "result_stats" | "result_step_agent" | null` field per entry.

The `total_usd` aggregation NEVER silent-zero-counts a null. A `total_usd` of 0.0 means "every run-dir reported $0.00", not "we found no data" — the latter surfaces as `n_unknown == n_runs` with a non-empty `warnings` list. This is the §3.3-correct gesture: `total_usd: 0.0, n_unknown: 5, warnings: [...]` is a different document from `total_usd: 0.0, n_unknown: 0, warnings: []`, and the snapshot test in Task 6 pins both fields' presence so a downstream consumer cannot mistake one for the other.

**Run-dir artifact inventory (observed at plan time, commit `a2e9c49`, fixture `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/`):**
- `summary.json` — razorback summary. Today's shape carries `summary_version`, `stratified_pass_at_1`, `datasets`. **No `cost_usd` field present.** Harbor / razorback may add one later; the precedence reader checks it first regardless.
- `result.json` — harbor's JobResult envelope. Top-level `stats` block may carry a `cost_usd` field (per budget-gate plan's `read_actual_cost_from_run_dir`). In the baseline-rerun fixture, top-level `cost_usd: null` is present at line 39 (per the grep evidence at plan time).
- `<trial-dir>/result.json` — per-trial result. `step_results[].agent_result.cost_usd` carries the harbor-emitted per-trial cost. **Null under subscription auth.** If a run-dir has no top-level cost in `summary.json` or `result.json.stats`, the reader sums non-null per-trial agent costs as the final fallback; if every per-trial cost is null, the run-dir is `cost_unknown`.

**Out of scope (per entity body):**
- Per-trial cost breakdown in the CLI output. The per-run JSON element carries one `cost_usd` per run-dir; per-trial accounting (when needed) is the consumer's job via `rk runs show` or direct trial inspection.
- Budget-gate enforcement. `phase4a-rk-run-budget-gate` ships `--max-budget-usd-running <file>` on `rk run`; `rk runs cost` is read-only.
- Markdown / human formatting. Spec §3.1 names JSON as default; defer human-readable polish until consumer demand surfaces.
- Cost estimation for not-yet-run specs. `rk runs cost` reads completed runs only.
- A `--format` flag. JSON only on first ship.

---

## AC ↔ task map

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 (`rk runs cost` emits cumulative JSON; `--experiment` filter; `--root` override) | spec §3.2 (`rk runs cost` description) + entity AC-1 | Task 1 (fixtures), Task 2 (`read_run_cost`), Task 3 (`aggregate_costs`), Task 4 (Typer command) |
| AC-2 (per-run breakdown carries `{path, experiment, cost_usd, created_at}`) | entity AC-2 verbatim | Task 3 (aggregator shape), Task 4 (CLI passes shape verbatim) |
| AC-3 (cost source: `summary.json` first, harbor's emitted field fallback; precedence documented) | entity AC-3; cross-plan with `phase4a-rk-run-budget-gate.read_actual_cost_from_run_dir` | Task 2 (precedence walk + dual-source unit test) |
| AC-4 (missing cost: `cost_unknown: true`, excluded from `total_usd`, warning emitted) | entity AC-4; dispatch checklist item #2; Phase 0 §"Phase 0 side findings" item C | Task 2 (null branch), Task 3 (aggregator excludes + warns), Task 5 (subscription-auth fixture test) |
| AC-5 (exit 2 on nonexistent root, error names the missing input) | spec §3.4 USAGE row; pkg1-v2 AC-3 mirrors | Task 4 (CLI maps `FileNotFoundError` → ExitCode.USAGE) |
| AC-6 (JSON output stable under §3.3 semver) | spec §3.3 | Task 6 (snapshot pins top-level + per-run key sets) |
| AC-7 (`uv run pytest` exits 0) | entity AC-7 | Task 7 (regression sweep) |
| (Coverage) acceptance command against the real subscription-auth run-dir | entity Test plan "Acceptance command"; cost-telemetry gap | Task 8 (acceptance pass under `.runs/baseline-rerun-20260520-bookreview/`) |

---

## Wire shapes (razorback-owned, semver-stable under §3.3)

`rk runs cost --root <dir> [--experiment <name>]` stdout (JSON object):

```json
{
  "total_usd": 4.50,
  "n_runs": 3,
  "n_known": 3,
  "n_unknown": 0,
  "runs": [
    {
      "path": "/abs/path/to/run-dir",
      "experiment": "exp-a",
      "created_at": "2026-05-20T07:12:27Z",
      "cost_usd": 1.50,
      "cost_unknown": false,
      "cost_source": "summary"
    }
  ],
  "warnings": []
}
```

Top-level keys: `total_usd` (float, sum of known-only), `n_runs` (int, all enumerated), `n_known` (int, contributed to total), `n_unknown` (int, excluded), `runs` (list, sorted `(experiment, path)` ascending — same ordering as pkg1-v2 `list_run_dirs`), `warnings` (list of strings; one entry per `cost_unknown: true` run-dir naming the path and the missing-data reason).

Per-run keys: `path` (str, absolute), `experiment` (str, from `manifest.json`), `created_at` (str, ISO-8601 UTC from `manifest.json`), `cost_usd` (float | null), `cost_unknown` (bool), `cost_source` (`"summary"` | `"result_stats"` | `"result_step_agent"` | `null`).

Total-vs-unknown invariant: `n_runs == n_known + n_unknown`; `total_usd` sums only `cost_unknown: false` entries. The Task 6 snapshot pins both the top-level and per-run key sets.

---

## Task 1 — Fixture builder extension for cost-bearing run-dirs (AC-1 + AC-2 + AC-3 + AC-4 prerequisite)

**Files:**
- Modify: `tests/unit/conftest.py` — extend the existing `make_run_dir` factory (pkg1-v2 t1) with optional `cost_in_summary`, `cost_in_result_stats`, and `per_trial_costs` parameters. Add a sibling factory `make_trial_dir(run_dir, *, trial_name, agent_cost_usd)` that writes the per-trial `result.json` carrying `step_results[].agent_result.cost_usd`.

**Spec cite:** spec §7.1 (layout); plan-time inventory of `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68/` (per-trial `result.json` shape at line 99-110 of the real artifact).

- [ ] **Step 1: Write the failing tests in `tests/unit/test_cost_fixtures.py`**

```python
from pathlib import Path
import json

from tests.unit.conftest import make_run_dir, make_trial_dir


def test_make_run_dir_writes_cost_in_summary(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path, root="runs", experiment="e", job_name="j",
        cost_in_summary=2.25,
    )
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["cost_usd"] == 2.25


def test_make_run_dir_writes_cost_in_result_stats(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path, root="runs", experiment="e", job_name="j",
        cost_in_result_stats=1.50,
    )
    result = json.loads((run_dir / "result.json").read_text())
    assert result["stats"]["cost_usd"] == 1.50


def test_make_run_dir_writes_null_cost_in_result_stats(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path, root="runs", experiment="e", job_name="j",
        cost_in_result_stats=None,
    )
    result = json.loads((run_dir / "result.json").read_text())
    assert result["stats"]["cost_usd"] is None


def test_make_trial_dir_writes_per_trial_agent_cost(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="e", job_name="j")
    trial = make_trial_dir(run_dir, trial_name="t__abc", agent_cost_usd=0.30)
    body = json.loads((trial / "result.json").read_text())
    assert body["step_results"][0]["agent_result"]["cost_usd"] == 0.30
```

- [ ] **Step 2: Run to verify failure**

`uv run pytest tests/unit/test_cost_fixtures.py -v` — expect FAIL (`make_trial_dir` import error; `cost_in_summary` kwarg unknown).

- [ ] **Step 3: Extend `tests/unit/conftest.py`**

Add the three optional kwargs to `make_run_dir`. When `cost_in_summary is not None`, write a `cost_usd` field into the summary payload. When `cost_in_result_stats is not None or kwarg present`, write a `result.json` with a `stats.cost_usd` key (including the `None` → `null` branch). When `per_trial_costs` is a list of floats-or-None, materialize trial subdirs via `make_trial_dir`. Add `make_trial_dir(run_dir, *, trial_name, agent_cost_usd)` that writes a minimal `result.json` carrying `step_results: [{"agent_result": {"cost_usd": agent_cost_usd}}]`.

- [ ] **Step 4: Run to verify pass**

`uv run pytest tests/unit/test_cost_fixtures.py -v` — expect 4/4 pass.

- [ ] **Step 5: Commit**

`phase4a-rk-runs-cost t1: cost-bearing fixture extensions`.

---

## Task 2 — `src/razorback/runs/cost.py` `read_run_cost` primitive (AC-3 + AC-4 core)

**Files:**
- Add: `src/razorback/runs/cost.py` with `read_run_cost(run_dir: Path) -> tuple[float | None, bool, str | None]`.
- Add: `tests/unit/test_read_run_cost.py`.

**Spec cite:** entity AC-3 (cost-source precedence: `summary.json` first, harbor-emitted field fallback); cross-plan with `phase4a-rk-run-budget-gate.read_actual_cost_from_run_dir` (the two MUST agree on field name + precedence — if either changes the other tracks).

**Wire shape:** `read_run_cost(run_dir) -> (cost_usd, cost_known, source)`. `cost_known` is `True` iff a non-null cost was found; `source` is `"summary"`, `"result_stats"`, `"result_step_agent"`, or `None`. The function raises `FileNotFoundError` only if `run_dir` itself does not exist; missing-but-tolerated artifacts (e.g. no `summary.json`) fall through to the next precedence level.

Precedence walk:
1. `summary.json["cost_usd"]` — if key present and non-null, return `(value, True, "summary")`. If key present and null, return `(None, False, "summary")` immediately — "we asked the canonical source and got null" is a definitive answer, not a fall-through trigger.
2. Else if `result.json["stats"]["cost_usd"]` — same shape: present-non-null → `(value, True, "result_stats")`; present-null → `(None, False, "result_stats")`.
3. Else walk per-trial subdirs (`run_dir.iterdir()` for child dirs containing `result.json`). For each trial, read `step_results[].agent_result.cost_usd`. If ANY trial returns a non-null number, sum the non-null trial costs and return `(sum, True, "result_step_agent")`. If every trial cost is null, return `(None, False, "result_step_agent")`.
4. Else (no cost field found at any level): `(None, False, None)`.

The early-return on present-null is the load-bearing decision: the budget-gate plan's `read_actual_cost_from_run_dir` (lines 818-832) returns the first source it finds and does NOT fall through on null; this plan matches that semantic for cross-plan consistency. The fallback to per-trial agent_result.cost_usd is this plan's extension (the budget-gate plan stops at `result.json.stats`), justified by the observed run-dir shape where neither summary nor stats carries cost but per-trial agent costs are the harbor-current location. Note: if PKG-8 / Phase 1 later add a top-level summary or stats `cost_usd`, this extension is harmless — the higher-precedence sources catch first.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_read_run_cost.py` — eight tests covering each precedence branch and each null-vs-absent state:

```python
from pathlib import Path
import pytest

from razorback.runs.cost import read_run_cost
from tests.unit.conftest import make_run_dir, make_trial_dir


def test_summary_cost_wins(tmp_path: Path):
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j",
                      cost_in_summary=2.25, cost_in_result_stats=999.0)
    assert read_run_cost(run) == (2.25, True, "summary")


def test_result_stats_used_when_summary_lacks_cost(tmp_path: Path):
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j",
                      cost_in_result_stats=1.50)
    assert read_run_cost(run) == (1.50, True, "result_stats")


def test_summary_present_but_null_does_not_fall_through(tmp_path: Path):
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j",
                      cost_in_summary=None, cost_in_result_stats=1.50)
    # explicit null in summary is authoritative; do NOT fall through to result_stats
    assert read_run_cost(run) == (None, False, "summary")


def test_result_stats_null_does_not_fall_through(tmp_path: Path):
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j",
                      cost_in_result_stats=None)
    assert read_run_cost(run) == (None, False, "result_stats")


def test_per_trial_agent_result_used_when_higher_sources_absent(tmp_path: Path):
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j")
    make_trial_dir(run, trial_name="t1__abc", agent_cost_usd=0.30)
    make_trial_dir(run, trial_name="t2__def", agent_cost_usd=0.45)
    cost, known, source = read_run_cost(run)
    assert known is True
    assert source == "result_step_agent"
    assert cost == pytest.approx(0.75)


def test_all_null_per_trial_returns_unknown_subscription_auth(tmp_path: Path):
    # The Phase 0 baseline-rerun finding: subscription auth → all per-trial nulls.
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j")
    make_trial_dir(run, trial_name="t1__abc", agent_cost_usd=None)
    make_trial_dir(run, trial_name="t2__def", agent_cost_usd=None)
    assert read_run_cost(run) == (None, False, "result_step_agent")


def test_no_cost_field_anywhere(tmp_path: Path):
    run = make_run_dir(tmp_path, root="r", experiment="e", job_name="j")
    assert read_run_cost(run) == (None, False, None)


def test_missing_run_dir_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_run_cost(tmp_path / "nope")
```

- [ ] **Step 2: Run to verify failure**

`uv run pytest tests/unit/test_read_run_cost.py -v` — expect 8/8 FAIL (ImportError).

- [ ] **Step 3: Implement `src/razorback/runs/cost.py`**

Two-line ABOUTME header. Implement the four-level precedence walk verbatim. The summary / result.json reads tolerate a missing file (treat as "no signal"); they only "stop walking" on a key-present branch. Sum the non-null per-trial costs as floats (one harbor-style numeric per trial step). Document the cross-plan contract with `phase4a-rk-run-budget-gate.read_actual_cost_from_run_dir` in the module docstring with a pointer to the budget-gate plan path.

- [ ] **Step 4: Run to verify pass**

`uv run pytest tests/unit/test_read_run_cost.py -v` — expect 8/8 pass.

- [ ] **Step 5: Commit**

`phase4a-rk-runs-cost t2: read_run_cost precedence walk`.

---

## Task 3 — Aggregator `aggregate_costs(root, experiment=None)` (AC-1 + AC-2 + AC-4)

**Files:**
- Modify: `src/razorback/runs/cost.py` — add `aggregate_costs(root: Path, *, experiment: str | None = None) -> dict`.
- Add: `tests/unit/test_aggregate_costs.py`.

**Spec cite:** entity AC-1 (cumulative cost across run-dirs); AC-2 (per-run breakdown shape); AC-4 (missing-cost surfaced, not silently dropped).

**Wire shape:** see the "Wire shapes" section above (top-level + per-run keys).

Implementation: walk `list_run_dirs(root, experiment=experiment)` from `razorback.runs.inspect` (pkg1-v2 t2). For each entry, call `read_run_cost(Path(entry["path"]))` and assemble the per-run dict carrying `path`, `experiment`, `created_at` (passed through from `list_run_dirs`'s output verbatim — pkg1-v2 already sources it from `manifest.json["created_at"]`), `cost_usd` (float or None), `cost_unknown` (`not cost_known`), `cost_source` (the third tuple element, or null). Sum the `cost_known=True` entries into `total_usd`. Tally `n_runs`, `n_known`, `n_unknown`. Build `warnings` as one string per `cost_unknown: true` entry, formatted as `f"{path}: cost unknown (source checked: {cost_source})"` — empty list when all costs are known.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from razorback.runs.cost import aggregate_costs
from tests.unit.conftest import make_run_dir, make_trial_dir


def test_aggregate_three_run_dirs_sums_costs(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j1", cost_in_summary=1.50)
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j2", cost_in_summary=2.25)
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j3", cost_in_summary=0.75)
    doc = aggregate_costs(tmp_path / "runs")
    assert doc["total_usd"] == 4.50
    assert doc["n_runs"] == 3
    assert doc["n_known"] == 3
    assert doc["n_unknown"] == 0
    assert doc["warnings"] == []
    assert len(doc["runs"]) == 3


def test_aggregate_per_run_carries_required_fields(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j1", cost_in_summary=1.0)
    doc = aggregate_costs(tmp_path / "runs")
    entry = doc["runs"][0]
    for k in ("path", "experiment", "created_at", "cost_usd", "cost_unknown", "cost_source"):
        assert k in entry, f"missing key: {k}"


def test_aggregate_filters_by_experiment(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="foo", job_name="j", cost_in_summary=1.0)
    make_run_dir(tmp_path, root="runs", experiment="bar", job_name="j", cost_in_summary=99.0)
    doc = aggregate_costs(tmp_path / "runs", experiment="foo")
    assert doc["total_usd"] == 1.0
    assert doc["n_runs"] == 1


def test_aggregate_excludes_unknown_from_total(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j1", cost_in_summary=2.0)
    # second run: subscription-auth shape (all-null per-trial agent costs)
    run2 = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j2")
    make_trial_dir(run2, trial_name="t__a", agent_cost_usd=None)
    doc = aggregate_costs(tmp_path / "runs")
    assert doc["total_usd"] == 2.0
    assert doc["n_runs"] == 2
    assert doc["n_known"] == 1
    assert doc["n_unknown"] == 1
    assert len(doc["warnings"]) == 1
    assert "cost unknown" in doc["warnings"][0]


def test_aggregate_all_unknown_distinct_from_all_zero(tmp_path: Path):
    """AC-4 invariant: total_usd 0 + n_unknown N != total_usd 0 + n_unknown 0."""
    run = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j")
    make_trial_dir(run, trial_name="t__a", agent_cost_usd=None)
    doc = aggregate_costs(tmp_path / "runs")
    assert doc["total_usd"] == 0.0
    assert doc["n_unknown"] == 1
    assert doc["warnings"] != []


def test_aggregate_empty_root(tmp_path: Path):
    (tmp_path / "runs").mkdir()
    doc = aggregate_costs(tmp_path / "runs")
    assert doc == {"total_usd": 0.0, "n_runs": 0, "n_known": 0, "n_unknown": 0, "runs": [], "warnings": []}
```

- [ ] **Step 2: Run to verify failure**

`uv run pytest tests/unit/test_aggregate_costs.py -v` — expect FAIL (function not present).

- [ ] **Step 3: Implement `aggregate_costs` in `src/razorback/runs/cost.py`**

Use `list_run_dirs` from `razorback.runs.inspect` for enumeration so ordering, filtering, and `created_at` propagation all match pkg1-v2's shape. Sum with explicit float (default 0.0 to avoid Decimal/int promotion surprises). The all-unknown case returns `total_usd: 0.0` AND `n_unknown == n_runs` AND non-empty `warnings` — these three together are how a consumer distinguishes "real zero" from "no data".

- [ ] **Step 4: Run to verify pass**

`uv run pytest tests/unit/test_aggregate_costs.py -v` — expect 6/6 pass.

- [ ] **Step 5: Commit**

`phase4a-rk-runs-cost t3: aggregate_costs with cost-telemetry-gap surface`.

---

## Task 4 — `rk runs cost` Typer command (AC-1 + AC-2 + AC-5)

**Files:**
- Modify: `src/razorback/cli/runs.py` — attach `cost_command` to `runs_app` next to the existing `list`/`show`/`diff` commands.
- Add: `tests/unit/test_runs_cost_cli.py`.

**Spec cite:** spec §3.2 (`rk runs cost <root>`); §3.4 (USAGE=2 on missing input); entity AC-5.

Implementation matches the pkg1-v2 `list_command` shape: Typer option `--root` (path, default `Path(".runs")`), Typer option `--experiment` (str, optional). Body calls `aggregate_costs(root, experiment=experiment)` and emits `json.dumps(doc, indent=2)`. Maps `FileNotFoundError` (from `list_run_dirs` when the root does not exist) to `typer.Exit(ExitCode.USAGE)` with an `err=True` message naming the missing path. Note: do NOT set `exists=True` on the option — the explicit `FileNotFoundError` → ExitCode.USAGE mapping is what AC-5 tests against (pkg1-v2 t4 makes the same choice for `rk runs show`).

- [ ] **Step 1: Write the failing tests**

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir


def test_runs_cost_emits_aggregate_json(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="e", job_name="j1", cost_in_summary=1.50)
    make_run_dir(tmp_path, root="runs", experiment="e", job_name="j2", cost_in_summary=2.25)
    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0, result.stdout
    doc = json.loads(result.stdout)
    assert doc["total_usd"] == 3.75
    assert doc["n_runs"] == 2


def test_runs_cost_filters_by_experiment(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="foo", job_name="j", cost_in_summary=1.0)
    make_run_dir(tmp_path, root="runs", experiment="bar", job_name="j", cost_in_summary=99.0)
    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "runs"), "--experiment", "foo"])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["total_usd"] == 1.0


def test_runs_cost_usage_exit_on_missing_root(tmp_path: Path):
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(app, ["runs", "cost", "--root", str(tmp_path / "does-not-exist")])
    assert result.exit_code == 2
    assert "does-not-exist" in (result.stderr + result.stdout)
```

- [ ] **Step 2: Run to verify failure**

`uv run pytest tests/unit/test_runs_cost_cli.py -v` — expect FAIL (unknown subcommand).

- [ ] **Step 3: Implement `cost_command` on `runs_app` in `src/razorback/cli/runs.py`**

```python
@runs_app.command("cost")
def cost_command(
    root: Path = typer.Option(Path(".runs"), "--root", file_okay=False, dir_okay=True),
    experiment: str | None = typer.Option(None, "--experiment"),
) -> None:
    """Sum cost across run-dirs under <root>. §3.2."""
    try:
        doc = aggregate_costs(root, experiment=experiment)
    except FileNotFoundError as exc:
        typer.echo(f"rk runs cost: root not found: {exc}", err=True)
        raise typer.Exit(ExitCode.USAGE)
    typer.echo(json.dumps(doc, indent=2))
```

Import `aggregate_costs` from `razorback.runs.cost`. Import `ExitCode` from wherever pkg1-v2 imports it (verify on read).

- [ ] **Step 4: Run to verify pass**

`uv run pytest tests/unit/test_runs_cost_cli.py -v` — expect 3/3 pass.

- [ ] **Step 5: Commit**

`phase4a-rk-runs-cost t4: rk runs cost typer command`.

---

## Task 5 — Subscription-auth cost-telemetry-gap end-to-end fixture test (AC-4 explicit coverage)

**Files:**
- Add: `tests/unit/test_runs_cost_subscription_auth.py`.

**Spec cite:** entity AC-4 (missing cost: warning + exclusion, not silent-zero); dispatch checklist item #2 (cost-telemetry gap must be first-class); Phase 0 baseline-rerun §"Phase 0 side findings" item C.

This task is a dedicated test surface — no new production code. It exercises the all-null subscription-auth scenario end-to-end through the CLI to pin AC-4's "named, not silently dropped" guarantee.

- [ ] **Step 1: Write the test**

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir, make_trial_dir


def test_subscription_auth_run_dir_surfaces_as_unknown(tmp_path: Path):
    """Phase 0 finding: subscription-billed Claude leaves agent_result.cost_usd=null.
    rk runs cost must report this as cost_unknown, not silent-zero."""
    run = make_run_dir(tmp_path, root="runs", experiment="m3-bookreview-claude", job_name="bxxx")
    make_trial_dir(run, trial_name="bookreview-q1__a", agent_cost_usd=None)
    make_trial_dir(run, trial_name="bookreview-q2__b", agent_cost_usd=None)
    make_trial_dir(run, trial_name="bookreview-q3__c", agent_cost_usd=None)

    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["n_runs"] == 1
    assert doc["n_known"] == 0
    assert doc["n_unknown"] == 1
    assert doc["total_usd"] == 0.0
    assert len(doc["warnings"]) == 1
    assert doc["runs"][0]["cost_unknown"] is True
    assert doc["runs"][0]["cost_usd"] is None


def test_mixed_known_and_unknown_runs(tmp_path: Path):
    """Realistic mixed-mode experiment: one API-key run + one subscription run."""
    make_run_dir(tmp_path, root="runs", experiment="e", job_name="api-keyed", cost_in_summary=2.50)
    sub_run = make_run_dir(tmp_path, root="runs", experiment="e", job_name="subscription")
    make_trial_dir(sub_run, trial_name="t__x", agent_cost_usd=None)

    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["total_usd"] == 2.50  # subscription run excluded
    assert doc["n_known"] == 1
    assert doc["n_unknown"] == 1
    assert len(doc["warnings"]) == 1
```

- [ ] **Step 2: Run to verify pass**

`uv run pytest tests/unit/test_runs_cost_subscription_auth.py -v` — expect 2/2 pass (Tasks 2-4's implementation already wires this; this task pins the behavior as a regression guard).

- [ ] **Step 3: Commit**

`phase4a-rk-runs-cost t5: subscription-auth cost-gap regression guard`.

---

## Task 6 — JSON key-stability snapshot (AC-6)

**Files:**
- Add: `tests/unit/test_runs_cost_json_stability.py`.

**Spec cite:** spec §3.3 (semver promise — fields additive within major version, never renamed/removed).

Snapshot the top-level and per-run key sets exactly. Future additive fields require extending both constants in the same commit that adds them — the §3.3-correct gesture (CI fails until both sides land).

- [ ] **Step 1: Write the test**

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir

TOP_KEYS = {"total_usd", "n_runs", "n_known", "n_unknown", "runs", "warnings"}
RUN_KEYS = {"path", "experiment", "created_at", "cost_usd", "cost_unknown", "cost_source"}


def test_runs_cost_top_level_keys_stable(tmp_path: Path):
    make_run_dir(tmp_path, root="r", experiment="e", job_name="j", cost_in_summary=1.0)
    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "r")])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert set(doc) == TOP_KEYS, (
        f"rk runs cost top-level field set changed (§3.3 violation). "
        f"Got: {set(doc)}. Expected: {TOP_KEYS}."
    )


def test_runs_cost_per_run_keys_stable(tmp_path: Path):
    make_run_dir(tmp_path, root="r", experiment="e", job_name="j", cost_in_summary=1.0)
    result = CliRunner().invoke(app, ["runs", "cost", "--root", str(tmp_path / "r")])
    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert set(doc["runs"][0]) == RUN_KEYS, (
        f"rk runs cost per-run field set changed (§3.3 violation). "
        f"Got: {set(doc['runs'][0])}. Expected: {RUN_KEYS}."
    )
```

- [ ] **Step 2: Run to verify pass**

`uv run pytest tests/unit/test_runs_cost_json_stability.py -v` — expect 2/2 pass.

- [ ] **Step 3: Commit**

`phase4a-rk-runs-cost t6: JSON key-stability snapshot per §3.3`.

---

## Task 7 — `uv run pytest` regression sweep (AC-7)

**Files:** none (verification only).

- [ ] **Step 1: Run the full razorback test suite**

`uv run pytest` from the repo root. Expected: 0 failures. The new tests add 22 cases (4 fixture + 8 read_run_cost + 6 aggregate + 3 CLI + 2 subscription + 2 snapshot — minus the fixture tests being a temporary check; if kept, 25 total). Any pkg1-v2 test regression is a load-bearing signal (the new `cost.py` may not import `inspect.list_run_dirs` in a way that breaks the pkg1-v2 wire shape).

- [ ] **Step 2: If any prior test fails, STOP**

Do not proceed to Task 8. Diagnose the regression under superpowers:systematic-debugging. The most likely culprits: (a) `list_run_dirs` ordering changed because the new code mutated the inspect module; (b) `make_run_dir` default summary shape changed in a way that broke pkg1-v2's snapshot test.

---

## Task 8 — Acceptance pass against the real subscription-auth run-dir

**Files:** none (read-only acceptance command). Capture stdout into the entity's `validation` stage report (not the `plan` stage report).

**Spec cite:** entity Test plan "Acceptance command"; the real fixture `.runs/baseline-rerun-20260520-bookreview/` is the load-bearing subscription-auth case.

- [ ] **Step 1: `rk runs cost` against the baseline-rerun root**

```
uv run rk runs cost --root .runs/baseline-rerun-20260520-bookreview
```

Expected: exit 0; emits a JSON object with `n_runs >= 1`, `n_unknown >= 1` (the baseline-rerun is subscription-auth), `total_usd: 0.0`, and a non-empty `warnings` list naming the run-dir. The per-run `cost_source` is `"result_step_agent"` (since `summary.json` carries no `cost_usd` and `result.json.stats.cost_usd` is null OR walks to the per-trial fallback — verify which under the precedence walk; document the observed source in the validation report).

- [ ] **Step 2: `rk runs cost --experiment m3-bookreview-claude`**

```
uv run rk runs cost --root .runs/baseline-rerun-20260520-bookreview --experiment m3-bookreview-claude
```

Expected: exit 0; same shape as step 1 filtered to the bookreview experiment.

- [ ] **Step 3: `rk runs cost` against a nonexistent root**

```
uv run rk runs cost --root .runs/does-not-exist
```

Expected: exit 2; stderr names `does-not-exist`.

- [ ] **Step 4: Record results in the validation stage report**

Capture stdout (top-level fields; first per-run entry) and exit codes. Confirm the AC-4 invariant holds: `total_usd == 0.0` AND `n_unknown >= 1` AND `warnings` non-empty (distinct from the "no data" silent-zero path the dispatch banned). Goes in the entity's `validation` stage report, not the `plan` report.

---

## Done-when checklist

- All 25 unit tests pass (or 22 if the Task 1 fixture tests are removed once Tasks 2-3 indirectly exercise them).
- `uv run pytest` exits 0 from a clean checkout.
- Acceptance pass: all 3 steps in Task 8 produce the expected exit codes and the AC-4 invariant is documented in the validation report.
- Cost-source precedence in `read_run_cost` matches `phase4a-rk-run-budget-gate.read_actual_cost_from_run_dir` on the two shared sources (`summary.json` → `result.json.stats.cost_usd`). If the two diverge, both plans note it.
- Each task commits before the next begins; commit messages follow the `phase4a-rk-runs-cost tN:` prefix.

## Cross-plan coordination notes

- **`phase4a-rk-run-budget-gate` (sibling, queued):** Shares the cost-source precedence on the first two levels (`summary.json`, then `result.json.stats.cost_usd`). The budget-gate plan stops there; this plan extends with a third level (per-trial `result.json` `step_results[].agent_result.cost_usd`) because that is where the current real run-dir carries cost data. If either plan changes the first-two-level precedence or the field name, the other tracks. Track via cross-references in both plan files.
- **`pkg1-v2-rk-runs-cli` (r0, in flight):** This plan layers on top of `razorback.runs.inspect.list_run_dirs` (pkg1-v2 t2). The `runs_app` Typer sub-app is the same one pkg1-v2 t3/t4 attach to. The fixture factory `make_run_dir` is pkg1-v2 t1's; this plan extends it (Task 1) rather than reimplementing. If pkg1-v2 reorders its task numbers or renames the inspect module, this plan rebases.
- **Phase 1 (`phase1-rk-run-v2-wrapper`):** Phase 1 owns the run-dir contract that produces the artifacts this plan reads. If Phase 1 adds a `cost_usd` field to `summary.json` (currently absent), this plan's precedence walk picks it up automatically (level 1 of the walk) — no code change required.
