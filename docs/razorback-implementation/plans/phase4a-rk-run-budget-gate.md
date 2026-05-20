# Phase 4a — rk run budget gate (`--max-budget-usd-running`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `rk run` with `--max-budget-usd-running <file>`, the per-experiment running-budget gate. Before launching a trial, `rk run` reads the file's running total, adds this invocation's pre-launch cost estimate, and refuses with `BudgetExceededError` (exit 22) when the sum would exceed `experiment.max_budget_usd`. On successful completion the invocation's actual cost (from harbor's `summary.json`) atomically appends to the file. When the agent runtime emits no cost data (the subscription-auth `cost_usd: null` case Phase 0 baseline-rerun found), the gate degrades gracefully instead of treating the missing data as zero.

**Architecture:** The gate hooks into Phase 1's `rk run` body at two seams (the same harbor-delegation seam Phase 1 designed in `cli/run.py`'s `run_command`):

- **Pre-launch (after pre-checks, before `_invoke_harbor`):** read running-total file, compute estimate from the frozen spec, compare against `experiment.max_budget_usd`, raise `BudgetExceededError` if over.
- **Post-completion (after `_invoke_harbor` returns 0):** read the harbor-produced run-dir's `summary.json`, extract the actual cost, atomically append to the running-total file.

The atomic append uses lock-then-fsync-then-rename to survive concurrent invocations and mid-run crashes. The estimate source is `experiment.estimated_cost_usd` (or `experiment.max_budget_usd / n_invocations` as a fallback when the field is absent — but the entity body's AC-3 names the frozen-spec field as the authoritative source, so the fallback is escalation-to-spec-author territory and not implemented here). When the actual cost is unknown (subscription auth's `cost_usd: null`), the file records a `cost_usd: null` entry with the estimate retained so the running total still reflects the pre-launch belief; the gate's overage decision later uses the larger of (sum of known actuals + estimate-for-unknowns) so subscription-mode invocations cannot silently bypass the cap.

**Tech Stack:** Python 3.12, Typer (CLI flag extension), `json` (running-total file format), `fcntl.flock` (advisory file lock for concurrent safety on POSIX), `pathlib` (file paths). No new dependencies. The running-total file is a small JSON document; jsonschema validation is unnecessary at this size.

**Spec source of truth:** `/Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`. This plan cites:
- §3.1 (`rk run` CLI surface; path canonicalization)
- §3.2 (`rk run` description: budget check reads `--max-budget-usd-running <file>`, adds estimate, refuses on overage, appends actual on completion)
- §3.4 (exit code 22 reserved for `BudgetExceededError`)
- §6.1 (top-level spec shape: `experiment.max_budget_usd: 500`)
- §8.1 (rk run is a thin wrapper around harbor; razorback adds pre-checks)

**Phase dependencies:**

- **`phase1-rk-run-v2-wrapper` (landed):** Provides `cli/run.py`'s `run_command` body and the `_invoke_harbor` seam. This plan modifies that body to add the budget-gate pre-launch and post-completion calls. `BudgetExceededError(22)` is already defined in `errors.py` (Phase 1 Task 1 completed per task #43); this plan exercises it. The plan cites Phase 1's structure by concept (the pre-checks zone before `_invoke_harbor`; the post-completion zone after `_invoke_harbor` returns 0), not exact line numbers, because Phase 1's body wording may shift.
- **`phase4a-rk-runs-cost` (sibling, backlog):** The read-side cost summary. The two entities share a cost-source convention: `summary.json` is authoritative; harbor's emitted cost field is the fallback. This plan and `rk runs cost` MUST agree on the field name and precedence; if either changes, the other tracks. The two are independently implementable; the running-total file format is owned by this plan.
- **Phase 0 baseline-rerun finding (cited):** `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md` §"Phase 0 side findings" item C documents the subscription-auth (`CLAUDE_CODE_OAUTH_TOKEN`) cost-telemetry gap: `agent_result.cost_usd` is `null` and the five token fields are all `null` per trial. This plan's AC-2 + AC-3 + Task 5 explicitly handle this — the gate must distinguish "no cost data available" from "cost data present and zero" and degrade gracefully.

---

## AC ↔ task map

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 (`--max-budget-usd-running <file>` reads running total + refuses on overage) | spec §3.2 (rk run description); §3.4 exit 22 | Task 1 (running-total file format + reader), Task 2 (decision logic), Task 6 (CLI flag wiring) |
| AC-2 (on completion, actual cost appends atomically) | spec §3.2 ("on completion it appends the actual cost") | Task 4 (atomic append writer), Task 6 (post-completion wiring) |
| AC-3 (pre-launch estimate from frozen spec, not post-hoc) | entity body verbatim; spec §6.1 (`experiment.estimated_cost_usd` is the source) | Task 3 (estimator reader); Task 2 cross-cuts decision input |
| AC-4 (exit code 22 reserved for `BudgetExceededError`; message names budget/total/estimate) | spec §3.4 row 22 | Task 6 (CLI body raises with the formatted message); Task 2 (the message body construction) |
| AC-5 (without flag, `rk run` behaves unchanged — opt-in) | entity body verbatim | Task 6 (flag default = None; passthrough when None); Task 7 (regression test against the deterministic micro-spec) |
| AC-6 (atomic append survives crash — file's invariant holds at any read point) | entity body verbatim | Task 4 (lock + fsync + rename writer); Task 5 (crash-recovery unit test) |
| AC-7 (`uv run pytest` exits 0) | n/a | Task 8 (suite green from worktree branch tip) |

**Riskiest contract first.** Task 1 (running-total file format) and Task 4 (atomic append) are the on-disk contracts every downstream consumer (this entity's gate, `rk runs cost`, the matrix dispatcher) reads. Per CL's "Validating new mechanisms" rule + the entity dispatch's checklist item #2 (cost-telemetry gap handling), these two tasks land BEFORE the CLI wiring (Task 6). The smallest end-to-end exercise of the riskiest paths is Task 5's crash-recovery test, which exercises Task 4's writer through a simulated crash. Subscription-auth's `cost_usd: null` case is the second-riskiest contract; it lands in Task 4's writer (the null-cost branch) and is exercised by a dedicated test in Task 5.

---

## Task 1 — Running-total file format + reader (`src/razorback/budget.py`, AC-1 prerequisite)

**Files:**
- Create: `src/razorback/budget.py`
- Test: Create: `tests/unit/test_budget_running_total_io.py`

**Spec cite:** §3.2 (running total file semantics); entity body AC-1, AC-6.

The running-total file is a JSON document at the path the operator passes via `--max-budget-usd-running`. The shape:

```json
{
  "version": 1,
  "experiment": "dab-paper-reproduction",
  "max_budget_usd": 500,
  "invocations": [
    {
      "started_at": "2026-05-20T12:00:00Z",
      "completed_at": "2026-05-20T12:34:56Z",
      "estimate_usd": 12.50,
      "actual_usd": 11.80,
      "run_dir": "/Users/.../jobs_dir/job-hash",
      "cost_known": true
    },
    {
      "started_at": "2026-05-20T13:00:00Z",
      "completed_at": null,
      "estimate_usd": 12.50,
      "actual_usd": null,
      "run_dir": null,
      "cost_known": null
    }
  ]
}
```

Field semantics:
- `version: 1` — schema version. The reader refuses unknown versions with `ConfigInvalidError` (exit 24).
- `experiment` — must match `spec.experiment`; mismatch raises `ConfigInvalidError` (the operator pointed at the wrong file).
- `max_budget_usd` — captured on first write from `spec.experiment.max_budget_usd`; subsequent invocations cross-check and refuse with `ConfigInvalidError` on mismatch (the spec's budget changed mid-experiment).
- `invocations[]` — append-only list. Records are stamped at pre-launch with `actual_usd: null, completed_at: null, cost_known: null`, then updated at completion to fill in `actual_usd`, `completed_at`, and `cost_known`.
- `cost_known` — `true` when harbor's `summary.json` carried a non-null cost; `false` when the cost was null (subscription auth's telemetry gap); `null` while the invocation is in-flight or crashed before completion.

The **running total** is the sum:
- For invocations with `cost_known: true`: `actual_usd`
- For invocations with `cost_known: false`: `estimate_usd` (the operator's pre-launch belief is the best available proxy when telemetry is absent)
- For invocations with `cost_known: null` (in-flight or crashed): excluded from the total. AC-6's invariant — "the total reflects only fully-completed invocations" — applies to crashed invocations; in-flight invocations are treated as crashed by the next read.

This rule ensures the gate's decision is conservative under telemetry gaps: subscription-mode runs charge the pre-launch estimate against the cap rather than appearing free. AC-3's "pre-launch sum (running total + estimate) versus `experiment.max_budget_usd`" is computed as `current_total + this_invocation_estimate`.

- [ ] **Step 1: Write the failing test for the running-total reader**

Create `tests/unit/test_budget_running_total_io.py`:

```python
# ABOUTME: AC-1 + AC-6: budget-gate running-total file reader and shape contract.
# ABOUTME: Exercises subscription-auth cost_known=false handling per Phase 0 baseline finding.

import json
from pathlib import Path

import pytest

from razorback.budget import (
    RunningTotal,
    read_running_total,
    current_total_usd,
)
from razorback.errors import ConfigInvalidError


def _write(path: Path, body: dict) -> None:
    path.write_text(json.dumps(body))


def test_read_missing_file_returns_empty_running_total(tmp_path: Path):
    rt = read_running_total(tmp_path / "budget.json", experiment="exp-1", max_budget_usd=100.0)
    assert rt.invocations == []
    assert rt.experiment == "exp-1"
    assert rt.max_budget_usd == 100.0


def test_read_existing_file_parses_invocations(tmp_path: Path):
    p = tmp_path / "budget.json"
    _write(p, {
        "version": 1,
        "experiment": "exp-1",
        "max_budget_usd": 100.0,
        "invocations": [
            {
                "started_at": "2026-05-20T12:00:00Z",
                "completed_at": "2026-05-20T12:30:00Z",
                "estimate_usd": 10.0,
                "actual_usd": 9.5,
                "run_dir": "/runs/job-1",
                "cost_known": True,
            },
        ],
    })
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert len(rt.invocations) == 1
    assert rt.invocations[0].actual_usd == 9.5
    assert rt.invocations[0].cost_known is True


def test_current_total_excludes_in_flight_and_crashed(tmp_path: Path):
    p = tmp_path / "budget.json"
    _write(p, {
        "version": 1,
        "experiment": "exp-1",
        "max_budget_usd": 100.0,
        "invocations": [
            {"estimate_usd": 10.0, "actual_usd": 9.5, "cost_known": True,
             "started_at": "...", "completed_at": "...", "run_dir": "..."},
            # Subscription-auth: cost_known=False; estimate counts toward total.
            {"estimate_usd": 10.0, "actual_usd": None, "cost_known": False,
             "started_at": "...", "completed_at": "...", "run_dir": "..."},
            # In-flight (or crashed): cost_known=None; excluded from total.
            {"estimate_usd": 10.0, "actual_usd": None, "cost_known": None,
             "started_at": "...", "completed_at": None, "run_dir": None},
        ],
    })
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    # 9.5 (known actual) + 10.0 (subscription-auth estimate fallback)
    # = 19.5. The in-flight invocation contributes 0.
    assert current_total_usd(rt) == pytest.approx(19.5)


def test_experiment_name_mismatch_raises_config_invalid(tmp_path: Path):
    p = tmp_path / "budget.json"
    _write(p, {
        "version": 1, "experiment": "wrong", "max_budget_usd": 100.0, "invocations": []
    })
    with pytest.raises(ConfigInvalidError) as exc_info:
        read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert "wrong" in str(exc_info.value)
    assert "exp-1" in str(exc_info.value)


def test_budget_mismatch_raises_config_invalid(tmp_path: Path):
    p = tmp_path / "budget.json"
    _write(p, {
        "version": 1, "experiment": "exp-1", "max_budget_usd": 100.0, "invocations": []
    })
    with pytest.raises(ConfigInvalidError):
        read_running_total(p, experiment="exp-1", max_budget_usd=200.0)


def test_unknown_version_raises_config_invalid(tmp_path: Path):
    p = tmp_path / "budget.json"
    _write(p, {"version": 99, "experiment": "exp-1", "max_budget_usd": 100.0, "invocations": []})
    with pytest.raises(ConfigInvalidError):
        read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_budget_running_total_io.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'razorback.budget'`.

- [ ] **Step 3: Implement `src/razorback/budget.py`**

Create `src/razorback/budget.py`:

```python
# ABOUTME: Phase 4a running-budget gate file I/O + decision logic.
# ABOUTME: Tracks per-invocation estimates and actuals across a multi-invocation experiment.

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from razorback.errors import ConfigInvalidError


SCHEMA_VERSION = 1


@dataclass
class Invocation:
    started_at: Optional[str]
    completed_at: Optional[str]
    estimate_usd: float
    actual_usd: Optional[float]
    run_dir: Optional[str]
    cost_known: Optional[bool]


@dataclass
class RunningTotal:
    experiment: str
    max_budget_usd: float
    invocations: list[Invocation] = field(default_factory=list)


def read_running_total(
    path: Path,
    *,
    experiment: str,
    max_budget_usd: float,
) -> RunningTotal:
    """Read the running-total JSON file. Returns an empty RunningTotal if absent.

    Raises ConfigInvalidError on schema version mismatch, experiment-name mismatch,
    or max_budget_usd mismatch (the operator pointed at the wrong file or the spec
    changed mid-experiment).
    """
    if not path.exists():
        return RunningTotal(experiment=experiment, max_budget_usd=max_budget_usd)
    body = json.loads(path.read_text())
    if body.get("version") != SCHEMA_VERSION:
        raise ConfigInvalidError(
            f"running-total file version mismatch: got {body.get('version')!r}, "
            f"expected {SCHEMA_VERSION}. File: {path}"
        )
    if body.get("experiment") != experiment:
        raise ConfigInvalidError(
            f"running-total file experiment name {body.get('experiment')!r} "
            f"does not match spec.experiment {experiment!r}. File: {path}"
        )
    if body.get("max_budget_usd") != max_budget_usd:
        raise ConfigInvalidError(
            f"running-total file max_budget_usd {body.get('max_budget_usd')} "
            f"does not match spec.experiment.max_budget_usd {max_budget_usd}. "
            f"The spec's budget changed; resolve before re-running. File: {path}"
        )
    invocations = [Invocation(**inv) for inv in body.get("invocations", [])]
    return RunningTotal(
        experiment=experiment,
        max_budget_usd=max_budget_usd,
        invocations=invocations,
    )


def current_total_usd(rt: RunningTotal) -> float:
    """Sum of completed-invocation costs.

    - cost_known is True: use actual_usd (telemetry available).
    - cost_known is False: use estimate_usd (subscription-auth: telemetry null;
      the pre-launch belief is the conservative proxy).
    - cost_known is None: exclude (in-flight or crashed before completion).
    """
    total = 0.0
    for inv in rt.invocations:
        if inv.cost_known is True:
            total += inv.actual_usd or 0.0
        elif inv.cost_known is False:
            total += inv.estimate_usd
        # cost_known is None → skip
    return total
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_budget_running_total_io.py -v`
Expected: PASS (six tests).

- [ ] **Step 5: Commit**

```bash
git add src/razorback/budget.py tests/unit/test_budget_running_total_io.py
git commit -m "Phase 4a Task 1: running-total file format + reader (AC-1 + AC-6 prerequisite)"
```

---

## Task 2 — Budget-gate decision logic (`budget.py::decide_budget`, AC-1 + AC-4)

**Files:**
- Modify: `src/razorback/budget.py` (add `decide_budget`)
- Test: Create: `tests/unit/test_budget_decision.py`

**Spec cite:** §3.2 (decision rule: refuse with `BudgetExceededError` if running total + estimate exceeds `experiment.max_budget_usd`); §3.4 row 22.

The decision logic is a pure function: given the running total and this invocation's estimate, return a `Decision` (proceed or refuse-with-budget-exceeded). The error message names the budget, the running total, and the estimate per AC-4.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_budget_decision.py`:

```python
# ABOUTME: AC-1 + AC-4: budget-gate pre-launch decision logic.

import pytest

from razorback.budget import RunningTotal, Invocation, decide_budget
from razorback.errors import BudgetExceededError, ExitCode


def test_decide_allows_when_estimate_fits():
    rt = RunningTotal(experiment="exp-1", max_budget_usd=100.0, invocations=[
        Invocation(started_at="", completed_at="", estimate_usd=20.0,
                   actual_usd=20.0, run_dir="", cost_known=True),
    ])
    # 20 (used) + 30 (estimate) = 50, well under 100. No raise.
    decide_budget(rt, estimate_usd=30.0)


def test_decide_refuses_when_estimate_pushes_over():
    rt = RunningTotal(experiment="exp-1", max_budget_usd=100.0, invocations=[
        Invocation(started_at="", completed_at="", estimate_usd=80.0,
                   actual_usd=80.0, run_dir="", cost_known=True),
    ])
    with pytest.raises(BudgetExceededError) as exc_info:
        decide_budget(rt, estimate_usd=30.0)
    assert exc_info.value.exit_code == ExitCode.BUDGET_EXCEEDED == 22
    msg = str(exc_info.value)
    # AC-4: message names budget, running total, and estimate.
    assert "100" in msg
    assert "80" in msg
    assert "30" in msg


def test_decide_at_exact_boundary_proceeds():
    rt = RunningTotal(experiment="exp-1", max_budget_usd=100.0, invocations=[
        Invocation(started_at="", completed_at="", estimate_usd=70.0,
                   actual_usd=70.0, run_dir="", cost_known=True),
    ])
    # 70 + 30 = 100, exactly at budget. The condition is "would exceed",
    # so equality proceeds; only strictly greater refuses.
    decide_budget(rt, estimate_usd=30.0)


def test_decide_with_subscription_auth_estimates_counted():
    # cost_known=False invocations contribute their estimate.
    rt = RunningTotal(experiment="exp-1", max_budget_usd=100.0, invocations=[
        Invocation(started_at="", completed_at="", estimate_usd=80.0,
                   actual_usd=None, run_dir="", cost_known=False),
    ])
    with pytest.raises(BudgetExceededError):
        decide_budget(rt, estimate_usd=30.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_budget_decision.py -v`
Expected: FAIL with `ImportError: cannot import name 'decide_budget' from 'razorback.budget'`.

- [ ] **Step 3: Add `decide_budget` to `src/razorback/budget.py`**

Append:

```python
from razorback.errors import BudgetExceededError


def decide_budget(rt: RunningTotal, *, estimate_usd: float) -> None:
    """Raise BudgetExceededError if running_total + estimate would exceed the cap.

    The condition is strictly greater; equality at the cap proceeds.
    Per AC-4 the error message names budget, running total, and estimate.
    """
    used = current_total_usd(rt)
    projected = used + estimate_usd
    if projected > rt.max_budget_usd:
        raise BudgetExceededError(
            f"budget exceeded: experiment.max_budget_usd={rt.max_budget_usd}, "
            f"running_total_usd={used:.4f}, this_invocation_estimate_usd={estimate_usd:.4f}, "
            f"projected_total_usd={projected:.4f}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_budget_decision.py -v`
Expected: PASS (four tests).

- [ ] **Step 5: Commit**

```bash
git add src/razorback/budget.py tests/unit/test_budget_decision.py
git commit -m "Phase 4a Task 2: budget-gate decision logic (AC-1 + AC-4)"
```

---

## Task 3 — Pre-launch estimate reader (`budget.py::read_estimate_from_spec`, AC-3)

**Files:**
- Modify: `src/razorback/budget.py` (add `read_estimate_from_spec`)
- Modify: `src/razorback/spec/schema.py` (add `experiment.estimated_cost_usd` optional field)
- Test: Create: `tests/unit/test_budget_estimate_source.py`

**Spec cite:** entity body AC-3 ("estimator reads `experiment.estimated_cost_usd` (or a per-spec estimate field) from the frozen spec"); spec §6.1 (top-level shape: `experiment:` block).

AC-3 names `experiment.estimated_cost_usd` as the source. The spec §6.1 example doesn't yet have this field — `rk freeze` (Phase 4a PKG-8) is responsible for populating it. This plan adds the schema slot (a single optional Decimal/float field on the `experiment:` block) so the spec parser accepts it; the budget gate consumes it. When the field is absent from a frozen spec, the gate raises `ConfigInvalidError` with a message naming the missing field and pointing at `rk freeze` as the producer (per entity body "Out of scope" item 4: "Cost estimation for not-yet-frozen specs. The frozen spec must carry the estimate before `rk run` invokes; `rk freeze` is responsible").

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_budget_estimate_source.py`:

```python
# ABOUTME: AC-3: pre-launch estimate sourced from frozen spec's experiment.estimated_cost_usd.

from pathlib import Path
import pytest

from razorback.budget import read_estimate_from_spec
from razorback.errors import ConfigInvalidError
from razorback.spec.parse import parse_spec_text


SPEC_WITH_ESTIMATE = """
version: 1
experiment: exp-1
agent:
  kind: nop
benchmark:
  kind: local
  task_paths: []
trials: 1
experiment_meta:
  max_budget_usd: 100.0
  estimated_cost_usd: 12.5
"""

SPEC_WITHOUT_ESTIMATE = """
version: 1
experiment: exp-1
agent:
  kind: nop
benchmark:
  kind: local
  task_paths: []
trials: 1
experiment_meta:
  max_budget_usd: 100.0
"""


def test_estimate_reads_from_frozen_spec_field():
    spec = parse_spec_text(SPEC_WITH_ESTIMATE)
    estimate = read_estimate_from_spec(spec)
    assert estimate == pytest.approx(12.5)


def test_missing_estimate_raises_config_invalid_naming_rk_freeze():
    spec = parse_spec_text(SPEC_WITHOUT_ESTIMATE)
    with pytest.raises(ConfigInvalidError) as exc_info:
        read_estimate_from_spec(spec)
    msg = str(exc_info.value)
    assert "estimated_cost_usd" in msg
    assert "rk freeze" in msg
```

Note: the field name on the `experiment_meta:` block versus the top-level `experiment:` string is a spec-schema collision the implementer resolves by adding a nested `experiment_meta:` block. The spec §6.1 example uses `experiment:` (the name string) and a separate `experiment:` block at the bottom for `max_budget_usd`. The current spec schema in `src/razorback/spec/schema.py` resolves this differently (verify on read; if there is no nested experiment block today, add one called `experiment_meta:` to carry `max_budget_usd` + `estimated_cost_usd` without conflicting with `experiment:` the name field). The implementer reads the existing schema before naming; if the schema already has a `budget` or `experiment` nested block, the new field hangs off that block. **Escalate to FO** if the schema's current `experiment` field is the string name only — schema additions touch `rk freeze`'s extension work in PKG-8 and the dispatch should be coordinated.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_budget_estimate_source.py -v`
Expected: FAIL — either `read_estimate_from_spec` missing or spec schema rejects the field.

- [ ] **Step 3: Add the schema slot in `src/razorback/spec/schema.py`**

The exact edit depends on the existing schema shape. Likely additions:

```python
class ExperimentMetaBlock(BaseModel):
    max_budget_usd: float | None = None
    estimated_cost_usd: float | None = None
```

Then on `Spec`: `experiment_meta: ExperimentMetaBlock | None = None`.

If the existing `Spec` already has a nested block named differently (e.g., `experiment_budget:`), extend that block instead. **Do not** rename existing fields; this is an additive change per spec §3.3 (provenance freeze format: new fields may be added).

- [ ] **Step 4: Add `read_estimate_from_spec` to `src/razorback/budget.py`**

Append:

```python
from razorback.spec.schema import Spec


def read_estimate_from_spec(spec: Spec) -> float:
    """Return the spec's pre-launch cost estimate.

    AC-3: the source is the frozen spec's experiment.estimated_cost_usd field
    (populated by `rk freeze` per PKG-8). Missing field is a hard error — the
    operator must re-freeze with cost-estimation logic before the gate can run.
    """
    meta = getattr(spec, "experiment_meta", None)
    estimate = getattr(meta, "estimated_cost_usd", None) if meta else None
    if estimate is None:
        raise ConfigInvalidError(
            "spec is missing experiment_meta.estimated_cost_usd; "
            "re-freeze with `rk freeze` (PKG-8 adds cost-estimation) before "
            "passing --max-budget-usd-running."
        )
    return float(estimate)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_budget_estimate_source.py -v`
Expected: PASS (two tests).

- [ ] **Step 6: Commit**

```bash
git add src/razorback/budget.py src/razorback/spec/schema.py tests/unit/test_budget_estimate_source.py
git commit -m "Phase 4a Task 3: estimate sourced from frozen spec's experiment_meta.estimated_cost_usd (AC-3)"
```

---

## Task 4 — Atomic append writer (`budget.py::stamp_started` + `stamp_completed`, AC-2 + AC-6)

**Files:**
- Modify: `src/razorback/budget.py`
- Test: Create: `tests/unit/test_budget_atomic_append.py`

**Spec cite:** §3.2 ("on completion it appends the actual cost"); entity body AC-2 (atomic append; concurrent invocations see consistent running totals) and AC-6 (crash invariant: at any read point, the total reflects only fully-completed invocations).

The writer needs two operations:

1. **`stamp_started(path, spec, estimate, run_dir)`** — pre-launch: append a new invocation record with `actual_usd: null, completed_at: null, cost_known: null`. This record is treated as in-flight; if the process crashes here, the record stays `cost_known: null` forever (excluded from total). The append is atomic under `fcntl.flock` + tempfile-rename.

2. **`stamp_completed(path, run_dir, actual_usd, cost_known)`** — post-completion: locate the invocation record by `run_dir` (the unique key for in-flight records) and update its `actual_usd`, `completed_at`, and `cost_known`. The implementation re-reads the file under lock to absorb concurrent writers, applies the update, and writes via tempfile-rename.

`actual_usd=None, cost_known=False` is the subscription-auth path. The cost-source convention (which field in `summary.json` carries the actual cost) is shared with `phase4a-rk-runs-cost`; this plan extracts the source via a helper `read_actual_cost_from_run_dir(run_dir) -> tuple[Optional[float], bool]` (returns `(cost, known)`).

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_budget_atomic_append.py`:

```python
# ABOUTME: AC-2 + AC-6: atomic running-total appender survives concurrent writes and crashes.

import json
from pathlib import Path

import pytest

from razorback.budget import (
    read_running_total,
    stamp_started,
    stamp_completed,
    current_total_usd,
)


def test_stamp_started_creates_in_flight_record(tmp_path: Path):
    p = tmp_path / "budget.json"
    stamp_started(
        path=p, experiment="exp-1", max_budget_usd=100.0,
        estimate_usd=10.0, run_dir="/runs/job-1",
    )
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert len(rt.invocations) == 1
    inv = rt.invocations[0]
    assert inv.estimate_usd == 10.0
    assert inv.run_dir == "/runs/job-1"
    assert inv.cost_known is None
    assert inv.actual_usd is None
    assert inv.completed_at is None
    # AC-6: in-flight record excludes from running total.
    assert current_total_usd(rt) == 0.0


def test_stamp_completed_updates_in_flight_record(tmp_path: Path):
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    stamp_completed(path=p, run_dir="/runs/job-1",
                    actual_usd=9.5, cost_known=True)
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    inv = rt.invocations[0]
    assert inv.actual_usd == 9.5
    assert inv.cost_known is True
    assert inv.completed_at is not None
    assert current_total_usd(rt) == 9.5


def test_stamp_completed_subscription_auth_null_cost(tmp_path: Path):
    """Phase 0 baseline-rerun finding: agent_result.cost_usd is null on subscription auth."""
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    stamp_completed(path=p, run_dir="/runs/job-1",
                    actual_usd=None, cost_known=False)
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    inv = rt.invocations[0]
    assert inv.actual_usd is None
    assert inv.cost_known is False
    # The estimate counts toward the running total since telemetry is absent.
    assert current_total_usd(rt) == 10.0


def test_concurrent_appends_see_consistent_total(tmp_path: Path):
    """Two stamp_started + stamp_completed pairs interleave without losing data."""
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=20.0, run_dir="/runs/job-2")
    stamp_completed(path=p, run_dir="/runs/job-2", actual_usd=18.0, cost_known=True)
    stamp_completed(path=p, run_dir="/runs/job-1", actual_usd=9.5, cost_known=True)
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert len(rt.invocations) == 2
    assert current_total_usd(rt) == pytest.approx(27.5)


def test_crash_between_start_and_complete_leaves_in_flight(tmp_path: Path):
    """AC-6: crash mid-invocation does NOT corrupt the file.

    Simulates a crash by calling stamp_started but never calling stamp_completed.
    The next read sees the in-flight record and excludes it from the total.
    """
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    # Simulated crash: process dies; no stamp_completed.

    # Subsequent read: in-flight record present, excluded from total.
    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert len(rt.invocations) == 1
    assert rt.invocations[0].cost_known is None
    assert current_total_usd(rt) == 0.0  # AC-6 invariant


def test_stamp_completed_for_unknown_run_dir_raises(tmp_path: Path):
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    with pytest.raises(ValueError):
        stamp_completed(path=p, run_dir="/runs/no-such",
                        actual_usd=9.5, cost_known=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_budget_atomic_append.py -v`
Expected: FAIL with `ImportError: cannot import name 'stamp_started' from 'razorback.budget'`.

- [ ] **Step 3: Implement `stamp_started` + `stamp_completed` + `_atomic_write`**

Append to `src/razorback/budget.py`:

```python
import datetime as _dt
import fcntl
import os
import tempfile
from dataclasses import asdict


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, body: dict) -> None:
    """Write JSON to path via tempfile+rename, fsync'd."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".budget-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(body, f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        os.unlink(tmp_name)
        raise


def _read_locked(path: Path) -> tuple[dict, int]:
    """Read JSON under an exclusive flock; returns (body, lock_fd).

    The caller MUST close the lock fd when done (releases the flock).
    For a new file, creates the lockfile alongside.
    """
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)
    if path.exists():
        body = json.loads(path.read_text())
    else:
        body = {}
    return body, lock_fd


def _release_lock(lock_fd: int) -> None:
    fcntl.flock(lock_fd, fcntl.LOCK_UN)
    os.close(lock_fd)


def stamp_started(
    *,
    path: Path,
    experiment: str,
    max_budget_usd: float,
    estimate_usd: float,
    run_dir: str,
) -> None:
    body, lock_fd = _read_locked(path)
    try:
        if not body:
            body = {
                "version": SCHEMA_VERSION,
                "experiment": experiment,
                "max_budget_usd": max_budget_usd,
                "invocations": [],
            }
        else:
            # Validate consistency (also enforced by read_running_total).
            if body.get("experiment") != experiment:
                raise ConfigInvalidError(
                    f"running-total file experiment mismatch: "
                    f"{body.get('experiment')!r} vs {experiment!r}"
                )
            if body.get("max_budget_usd") != max_budget_usd:
                raise ConfigInvalidError(
                    f"running-total file budget mismatch: "
                    f"{body.get('max_budget_usd')} vs {max_budget_usd}"
                )
        body["invocations"].append({
            "started_at": _now_iso(),
            "completed_at": None,
            "estimate_usd": estimate_usd,
            "actual_usd": None,
            "run_dir": run_dir,
            "cost_known": None,
        })
        _atomic_write(path, body)
    finally:
        _release_lock(lock_fd)


def stamp_completed(
    *,
    path: Path,
    run_dir: str,
    actual_usd: Optional[float],
    cost_known: bool,
) -> None:
    body, lock_fd = _read_locked(path)
    try:
        if not body:
            raise ValueError(
                f"stamp_completed called against missing running-total file: {path}"
            )
        invs = body.get("invocations", [])
        matched = None
        for inv in invs:
            if inv["run_dir"] == run_dir and inv["cost_known"] is None:
                matched = inv
                break
        if matched is None:
            raise ValueError(
                f"no in-flight invocation found for run_dir={run_dir!r} in {path}"
            )
        matched["completed_at"] = _now_iso()
        matched["actual_usd"] = actual_usd
        matched["cost_known"] = cost_known
        _atomic_write(path, body)
    finally:
        _release_lock(lock_fd)


def read_actual_cost_from_run_dir(run_dir: Path) -> tuple[Optional[float], bool]:
    """Read the actual cost from a harbor-produced run-dir.

    Returns (cost_usd, cost_known). cost_known is False when the agent runtime
    emitted null cost (subscription-auth telemetry gap per Phase 0 baseline).
    Source precedence: `summary.json` first (razorback's writer), then harbor's
    `result.json` `stats.cost_usd`. Shared convention with `rk runs cost`
    (phase4a-rk-runs-cost AC-3).
    """
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        body = json.loads(summary_path.read_text())
        if "cost_usd" in body:
            v = body["cost_usd"]
            return (float(v) if v is not None else None, v is not None)
    result_path = run_dir / "result.json"
    if result_path.exists():
        body = json.loads(result_path.read_text())
        stats = body.get("stats", {}) or {}
        if "cost_usd" in stats:
            v = stats["cost_usd"]
            return (float(v) if v is not None else None, v is not None)
    # No cost field at all — distinct from "field present but null".
    return (None, False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_budget_atomic_append.py -v`
Expected: PASS (six tests).

- [ ] **Step 5: Commit**

```bash
git add src/razorback/budget.py tests/unit/test_budget_atomic_append.py
git commit -m "Phase 4a Task 4: atomic stamp_started/stamp_completed writer (AC-2 + AC-6)"
```

---

## Task 5 — Crash-recovery + cost-telemetry-gap dedicated tests (AC-6 + AC-2 subscription path)

**Files:**
- Test: Create: `tests/unit/test_budget_crash_recovery.py`

**Spec cite:** entity body AC-6 ("A crash between estimate-write and actual-cost-write does not corrupt the running-total file."); Phase 0 baseline-rerun §"Phase 0 side findings" item C.

This task is dedicated test surface, no new production code. It exercises:

1. **Crash mid-invocation:** start, simulate kill, restart, re-read → total reflects only completed invocations. (Already covered in Task 4's `test_crash_between_start_and_complete_leaves_in_flight`; this task adds the explicit "subsequent rk runs cost call honors the invariant" scenario.)
2. **Subscription-auth null-cost path through `read_actual_cost_from_run_dir`:** the harbor-produced run-dir contains a `result.json` with `stats.cost_usd: null` and a `summary.json` without a cost field; the reader returns `(None, False)` and the gate's running total counts the estimate.
3. **Mixed-mode experiment:** three sequential invocations — two with API-key auth (cost_known=true) and one with subscription auth (cost_known=false). The running total at the end is `actual_1 + estimate_2 + actual_3`.

- [ ] **Step 1: Write the test**

Create `tests/unit/test_budget_crash_recovery.py`:

```python
# ABOUTME: AC-6: crash-recovery atomicity; AC-2 cost-telemetry-gap end-to-end.

import json
from pathlib import Path

import pytest

from razorback.budget import (
    read_running_total,
    stamp_started,
    stamp_completed,
    current_total_usd,
    read_actual_cost_from_run_dir,
)


def test_crash_invariant_holds_for_rk_runs_cost_consumer(tmp_path: Path):
    """Phase 0 baseline cited finding: rk runs cost must see consistent totals."""
    p = tmp_path / "budget.json"
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    stamp_completed(path=p, run_dir="/runs/job-1",
                    actual_usd=9.5, cost_known=True)

    # Second invocation crashes: stamp_started only.
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-2")
    # Simulated crash here.

    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    assert len(rt.invocations) == 2
    # AC-6 invariant: only completed invocations contribute.
    assert current_total_usd(rt) == 9.5


def test_subscription_auth_null_cost_reader(tmp_path: Path):
    """Phase 0 baseline-rerun item C: agent_result.cost_usd is null on subscription auth."""
    run_dir = tmp_path / "run-x"
    run_dir.mkdir()
    # Harbor emits result.json with stats.cost_usd: null (subscription-billed).
    (run_dir / "result.json").write_text(json.dumps({
        "stats": {"n_completed_trials": 3, "cost_usd": None}
    }))
    # No summary.json, or summary.json without cost field.

    cost, known = read_actual_cost_from_run_dir(run_dir)
    assert cost is None
    assert known is False


def test_api_key_auth_present_cost_reader(tmp_path: Path):
    run_dir = tmp_path / "run-y"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(json.dumps({"cost_usd": 12.50}))

    cost, known = read_actual_cost_from_run_dir(run_dir)
    assert cost == 12.50
    assert known is True


def test_mixed_mode_experiment_total(tmp_path: Path):
    """API-key invocation + subscription invocation + API-key invocation."""
    p = tmp_path / "budget.json"
    # Invocation 1: API-key, actual 9.5.
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-1")
    stamp_completed(path=p, run_dir="/runs/job-1", actual_usd=9.5, cost_known=True)
    # Invocation 2: subscription, cost null; estimate 10 counts.
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-2")
    stamp_completed(path=p, run_dir="/runs/job-2", actual_usd=None, cost_known=False)
    # Invocation 3: API-key, actual 11.2.
    stamp_started(path=p, experiment="exp-1", max_budget_usd=100.0,
                  estimate_usd=10.0, run_dir="/runs/job-3")
    stamp_completed(path=p, run_dir="/runs/job-3", actual_usd=11.2, cost_known=True)

    rt = read_running_total(p, experiment="exp-1", max_budget_usd=100.0)
    # 9.5 (known) + 10.0 (subscription estimate fallback) + 11.2 (known) = 30.7
    assert current_total_usd(rt) == pytest.approx(30.7)
```

- [ ] **Step 2: Run tests; expect pass against Task 4's writer**

Run: `uv run pytest tests/unit/test_budget_crash_recovery.py -v`
Expected: PASS (four tests).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_budget_crash_recovery.py
git commit -m "Phase 4a Task 5: crash-recovery + subscription-auth telemetry-gap tests (AC-6 + AC-2)"
```

---

## Task 6 — CLI wiring: `--max-budget-usd-running` flag on `rk run` (AC-1 + AC-2 + AC-4 + AC-5)

**Files:**
- Modify: `src/razorback/cli/run.py`
- Test: Create: `tests/unit/test_rk_run_budget_gate.py`

**Spec cite:** §3.1 (`rk run` flag surface); §3.2 ("budget check reads `--max-budget-usd-running <file>`"); §3.4 row 22 (`BudgetExceededError` exit 22); entity body AC-5 (without the flag, behavior unchanged — opt-in).

This task wires the budget gate into Phase 1's `run_command` body. The wiring zone is the same seam Phase 1's plan designs: pre-launch hooks land **after** the alias-drift + canary pre-checks, **before** `_invoke_harbor` (so the gate refuses before harbor spends compute); post-completion hooks land **after** `_invoke_harbor` returns 0, **before** the spec.frozen.yaml + provenance.yaml artifact write (so a budget-tracking failure does not silently lose the cost record).

The flag default is `None` (per AC-5: opt-in). When `None`, `run_command` skips all budget logic and behaves exactly like Phase 1's body.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_rk_run_budget_gate.py`:

```python
# ABOUTME: AC-1 + AC-4 + AC-5: rk run --max-budget-usd-running CLI surface.

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from razorback.cli import app
from razorback.errors import ExitCode


@pytest.fixture
def frozen_spec_with_budget(tmp_path: Path) -> Path:
    """Frozen spec with experiment_meta.max_budget_usd + estimated_cost_usd."""
    spec_yaml = tmp_path / "frozen.yaml"
    spec_yaml.write_text(
        "version: 1\n"
        "experiment: exp-budget-test\n"
        "agent:\n"
        "  kind: nop\n"
        "benchmark:\n"
        "  kind: local\n"
        "  task_paths: []\n"
        "trials: 1\n"
        "experiment_meta:\n"
        "  max_budget_usd: 50.0\n"
        "  estimated_cost_usd: 30.0\n"
        "provenance:\n"
        "  model_resolved_version: claude-opus-4-5-20251022\n"
        "  harbor_version: 0.6.6\n"
    )
    return spec_yaml


def test_without_flag_behavior_unchanged(frozen_spec_with_budget: Path, tmp_path: Path):
    """AC-5: omitting --max-budget-usd-running runs unchanged from Phase 1."""
    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._resolve_model_version", return_value=("claude-opus-4-5-20251022", "...")), \
         patch("razorback.cli.run._invoke_harbor", return_value=0), \
         patch("razorback.cli.run._write_provenance_artifacts"):
        runner = CliRunner()
        result = runner.invoke(app, [
            "run", str(frozen_spec_with_budget),
            "--runs-dir", str(tmp_path / "_runs"),
        ])
        assert result.exit_code == 0


def test_budget_gate_refuses_when_over(frozen_spec_with_budget: Path, tmp_path: Path):
    """AC-1 + AC-4: file already has 30 used; spec estimate 30; cap 50; refuse with exit 22."""
    budget_file = tmp_path / "budget.json"
    budget_file.write_text(json.dumps({
        "version": 1, "experiment": "exp-budget-test", "max_budget_usd": 50.0,
        "invocations": [{
            "started_at": "...", "completed_at": "...", "estimate_usd": 30.0,
            "actual_usd": 30.0, "run_dir": "/prior", "cost_known": True,
        }],
    }))
    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._resolve_model_version", return_value=("claude-opus-4-5-20251022", "...")), \
         patch("razorback.cli.run._invoke_harbor") as harbor_mock:
        runner = CliRunner()
        result = runner.invoke(app, [
            "run", str(frozen_spec_with_budget),
            "--runs-dir", str(tmp_path / "_runs"),
            "--max-budget-usd-running", str(budget_file),
        ])
        assert result.exit_code == ExitCode.BUDGET_EXCEEDED == 22
        # AC-1: harbor NOT invoked when gate refuses.
        harbor_mock.assert_not_called()
        # AC-4: error message names the cap, total, and estimate.
        assert "50" in result.output
        assert "30" in result.output


def test_budget_gate_allows_when_under_then_appends(
    frozen_spec_with_budget: Path, tmp_path: Path
):
    """AC-2: budget allows; harbor runs; actual cost appends to file."""
    budget_file = tmp_path / "budget.json"  # absent initially
    runs_dir = tmp_path / "_runs"

    def fake_harbor(job_config_yaml: Path) -> int:
        # Simulate harbor writing summary.json with the actual cost.
        # The run_dir is derived deterministically in run_command;
        # the test harness inspects it via the post-run reader.
        # For this test, locate the run_dir under runs_dir and inject summary.json.
        for run_dir in runs_dir.rglob("job-*"):
            (run_dir / "summary.json").write_text(json.dumps({"cost_usd": 25.0}))
        return 0

    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._resolve_model_version", return_value=("claude-opus-4-5-20251022", "...")), \
         patch("razorback.cli.run._invoke_harbor", side_effect=fake_harbor), \
         patch("razorback.cli.run._write_provenance_artifacts"):
        runner = CliRunner()
        result = runner.invoke(app, [
            "run", str(frozen_spec_with_budget),
            "--runs-dir", str(runs_dir),
            "--max-budget-usd-running", str(budget_file),
        ])
        assert result.exit_code == 0, result.output
        body = json.loads(budget_file.read_text())
        assert len(body["invocations"]) == 1
        inv = body["invocations"][0]
        assert inv["actual_usd"] == 25.0
        assert inv["cost_known"] is True


def test_budget_gate_records_subscription_auth_null_cost(
    frozen_spec_with_budget: Path, tmp_path: Path
):
    """Phase 0 cost-telemetry-gap path: harbor emits cost_usd: null; gate records as cost_known=False."""
    budget_file = tmp_path / "budget.json"
    runs_dir = tmp_path / "_runs"

    def fake_harbor(job_config_yaml: Path) -> int:
        for run_dir in runs_dir.rglob("job-*"):
            (run_dir / "result.json").write_text(json.dumps({
                "stats": {"n_completed_trials": 1, "cost_usd": None}
            }))
        return 0

    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._resolve_model_version", return_value=("claude-opus-4-5-20251022", "...")), \
         patch("razorback.cli.run._invoke_harbor", side_effect=fake_harbor), \
         patch("razorback.cli.run._write_provenance_artifacts"):
        runner = CliRunner()
        result = runner.invoke(app, [
            "run", str(frozen_spec_with_budget),
            "--runs-dir", str(runs_dir),
            "--max-budget-usd-running", str(budget_file),
        ])
        assert result.exit_code == 0, result.output
        body = json.loads(budget_file.read_text())
        inv = body["invocations"][0]
        assert inv["actual_usd"] is None
        assert inv["cost_known"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_rk_run_budget_gate.py -v`
Expected: FAIL — `run_command` doesn't yet accept `--max-budget-usd-running`.

- [ ] **Step 3: Extend `run_command` in `src/razorback/cli/run.py`**

The Phase 1 body has zones (per `phase1-rk-run-v2-wrapper.md` Task 7): pre-checks (parse spec, canary, alias-drift, harbor-drift), then translation + harbor invocation, then provenance artifact write.

Insert the budget-gate pre-launch zone after the pre-checks and before `_invoke_harbor`. Insert the post-completion zone after `_invoke_harbor` returns 0 and before the provenance artifact write.

Add to `run_command` signature:

```python
max_budget_usd_running: Optional[Path] = typer.Option(
    None,
    "--max-budget-usd-running",
    help="Path to running-total JSON file; the gate refuses on overage and "
         "appends actual cost on completion (per spec §3.2 + §3.4 exit 22).",
),
```

Then, **after the pre-checks** (alias-drift + canary) and **before** `_invoke_harbor`:

```python
budget_run_dir_for_stamp: Optional[Path] = None
if max_budget_usd_running is not None:
    from razorback.budget import (
        decide_budget,
        read_estimate_from_spec,
        read_running_total,
        stamp_started,
    )
    meta = getattr(spec, "experiment_meta", None)
    max_budget = getattr(meta, "max_budget_usd", None) if meta else None
    if max_budget is None:
        typer.echo(
            "ConfigInvalidError: --max-budget-usd-running requires "
            "spec.experiment_meta.max_budget_usd",
            err=True,
        )
        raise typer.Exit(ExitCode.CONFIG_INVALID)
    try:
        estimate = read_estimate_from_spec(spec)
        rt = read_running_total(
            max_budget_usd_running,
            experiment=spec.experiment,
            max_budget_usd=max_budget,
        )
        decide_budget(rt, estimate_usd=estimate)
    except BudgetExceededError as exc:
        typer.echo(f"BudgetExceededError: {exc}", err=True)
        raise typer.Exit(ExitCode.BUDGET_EXCEEDED)
    except ConfigInvalidError as exc:
        typer.echo(f"ConfigInvalidError: {exc}", err=True)
        raise typer.Exit(ExitCode.CONFIG_INVALID)
    # Stamp the in-flight record AFTER the gate decides "proceed".
    budget_run_dir_for_stamp = run_dir  # the run_dir Phase 1 derived earlier
    stamp_started(
        path=max_budget_usd_running,
        experiment=spec.experiment,
        max_budget_usd=max_budget,
        estimate_usd=estimate,
        run_dir=str(budget_run_dir_for_stamp),
    )
```

And **after `_invoke_harbor` returns 0**, **before** provenance artifact write:

```python
if max_budget_usd_running is not None and budget_run_dir_for_stamp is not None:
    from razorback.budget import read_actual_cost_from_run_dir, stamp_completed
    actual_cost, cost_known = read_actual_cost_from_run_dir(budget_run_dir_for_stamp)
    stamp_completed(
        path=max_budget_usd_running,
        run_dir=str(budget_run_dir_for_stamp),
        actual_usd=actual_cost,
        cost_known=cost_known,
    )
```

Note: when `_invoke_harbor` returns non-zero (exit 30), the budget file's in-flight record is left as `cost_known: null`. AC-6's crash invariant covers this: a subsequent read sees the in-flight record and excludes it. The operator's next invocation will either rerun against the same `run_dir` (idempotent, the in-flight record stays in-flight until a successful completion overwrites it) or against a fresh `run_dir` (and the prior in-flight record stays excluded forever). This matches the "crashed invocation" semantics in Task 1's design.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_rk_run_budget_gate.py -v`
Expected: PASS (four tests).

- [ ] **Step 5: Commit**

```bash
git add src/razorback/cli/run.py tests/unit/test_rk_run_budget_gate.py
git commit -m "Phase 4a Task 6: rk run --max-budget-usd-running CLI surface (AC-1 + AC-2 + AC-4 + AC-5)"
```

---

## Task 7 — Integration test: two sequential `rk run` invocations against the deterministic micro-spec (AC-1 + AC-5)

**Files:**
- Test: Create: `tests/integration/test_budget_gate_two_invocations.py`

**Spec cite:** entity body "Test plan" Integration test; AC-1 + AC-5.

This test exercises the full CLI path against the deterministic micro-spec (`examples/specs/_deterministic-smoke.frozen.yaml`, baseline 3/3 pass per `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md` §"Smoke run"). The integration covers:

- First invocation: budget allows; the trial runs; the file gains an actual-cost record.
- Second invocation against the same file: the gate refuses with exit 22; the file is unchanged.
- Regression: a third invocation **without** the flag against the same spec runs unchanged (AC-5 passthrough).

This test is gated on the deterministic micro-spec carrying an `experiment_meta:` block. Phase 1's `_deterministic-smoke.frozen.yaml` was authored before this block existed; Task 7's pre-flight is to verify (or extend) the smoke spec to include `experiment_meta: { max_budget_usd: 1.0, estimated_cost_usd: 0.6 }`. If the smoke spec lacks the block, this task adds it.

- [ ] **Step 1: Verify the smoke spec carries the budget metadata**

Run: `grep -n "experiment_meta\|max_budget_usd" /Users/clkao/git/razorback/examples/specs/_deterministic-smoke.frozen.yaml`

If absent, add the block. The values (1.0 cap, 0.6 estimate) are designed so two invocations would exceed (0.6 + 0.6 = 1.2 > 1.0) — the second invocation tests the refusal path.

If the smoke spec is generated/refrozen, instead edit the source `examples/specs/_deterministic-smoke.yaml` and re-freeze via `uv run rk freeze examples/specs/_deterministic-smoke.yaml`.

- [ ] **Step 2: Write the integration test**

Create `tests/integration/test_budget_gate_two_invocations.py`:

```python
# ABOUTME: AC-1 + AC-5 integration: budget gate refuses on second invocation against same file.
# ABOUTME: Uses the Phase 1 walking-skeleton smoke spec for end-to-end coverage.

import json
import subprocess
from pathlib import Path

import pytest


SMOKE_SPEC = Path("examples/specs/_deterministic-smoke.frozen.yaml")


@pytest.mark.integration
def test_two_sequential_invocations_second_refuses(tmp_path: Path, colima_safe_tmp_path: Path):
    budget_file = tmp_path / "budget.json"
    runs_dir = colima_safe_tmp_path / "_runs"

    # First invocation: budget allows; trial runs; file gains an actual-cost record.
    rc1 = subprocess.run([
        "uv", "run", "rk", "run", str(SMOKE_SPEC),
        "--runs-dir", str(runs_dir),
        "--max-budget-usd-running", str(budget_file),
    ], capture_output=True, text=True)
    assert rc1.returncode == 0, rc1.stderr
    body1 = json.loads(budget_file.read_text())
    assert len(body1["invocations"]) == 1
    # cost_known may be True (API-key) or False (subscription); both are valid.
    assert body1["invocations"][0]["cost_known"] in (True, False)

    # Second invocation: estimate (0.6) + running total would exceed 1.0; refuse with 22.
    rc2 = subprocess.run([
        "uv", "run", "rk", "run", str(SMOKE_SPEC),
        "--runs-dir", str(runs_dir),
        "--max-budget-usd-running", str(budget_file),
    ], capture_output=True, text=True)
    assert rc2.returncode == 22, rc2.stderr
    # AC-1: file unchanged on refusal (no new invocation record).
    body2 = json.loads(budget_file.read_text())
    assert len(body2["invocations"]) == 1


@pytest.mark.integration
def test_without_flag_regression_against_smoke(colima_safe_tmp_path: Path):
    """AC-5: omitting --max-budget-usd-running runs the smoke spec unchanged from Phase 1."""
    runs_dir = colima_safe_tmp_path / "_runs-no-budget"
    rc = subprocess.run([
        "uv", "run", "rk", "run", str(SMOKE_SPEC),
        "--runs-dir", str(runs_dir),
    ], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr
```

Note: this test depends on `colima_safe_tmp_path` (the fixture at `tests/conftest.py:12-23` that ensures the runs-dir is Colima-visible per the bookreview-regression investigation). It is `@pytest.mark.integration`-marked so it can be skipped on CI environments without docker.

- [ ] **Step 3: Run the test**

Run: `uv run pytest tests/integration/test_budget_gate_two_invocations.py -v -m integration`
Expected: PASS (two tests). The first test runs the smoke spec twice, ~10-15 min total against a real docker environment. If the smoke spec already passed in Phase 1 Task 9, this is the same wall-clock budget.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_budget_gate_two_invocations.py
# Plus smoke spec edits if Step 1 added experiment_meta:
git add examples/specs/_deterministic-smoke.yaml examples/specs/_deterministic-smoke.frozen.yaml
git commit -m "Phase 4a Task 7: integration test for two-invocation budget gate + AC-5 passthrough"
```

---

## Task 8 — `uv run pytest` green sweep (AC-7)

**Files:** none new.

- [ ] **Step 1: Run the full suite from the worktree tip**

Run: `uv run pytest -v`
Expected: ALL tests pass. If failures appear in `_legacy/`-tagged DROP tests (Phase 1 sidelined them), confirm they were already expected-fail before this entity began. New failures specific to this entity's tasks (1-7) are this entity's responsibility.

- [ ] **Step 2: If failures appear, triage**

Read the failure list. For each:
- **Direct effect of Tasks 1-7:** fix here.
- **Pre-existing failure unrelated to budget gate:** escalate via SendMessage(to="team-lead") with a one-line description of the failure and the Phase 4a entity's stance (not this entity's responsibility to fix).

- [ ] **Step 3: Commit only if Step 2 required follow-up fixes**

```bash
git add -u src/razorback/ tests/
git commit -m "Phase 4a Task 8: green-sweep follow-up fixes"
```

---

## Mechanism validation order

Per CL's "Validating new mechanisms" rule + the entity dispatch checklist's item #2 (graceful degradation under cost-telemetry gap), the order optimizes for catching contract failures cheaply:

1. **Task 1 (running-total file format)** — minutes. The smallest contract — JSON shape, schema-version refusal, experiment/budget cross-check.
2. **Task 2 (decision logic)** — minutes. Pure function. Confirms the refuse/proceed math agrees with AC-1 + AC-4.
3. **Task 4 (atomic writer)** — minutes. Crash-recovery test exercises the lock + rename invariant under simulated kill.
4. **Task 5 (subscription-auth path)** — minutes. The cost-telemetry-gap finding becomes a regression test before any CLI wiring depends on it.
5. **Task 3 (estimator)** — minutes. Spec-schema slot + missing-field error.
6. **Task 6 (CLI wiring)** — tens of minutes (mocked harbor). The wiring under mocked harbor + mocked canary confirms the CLI passes args through correctly.
7. **Task 7 (integration)** — 10-15 minutes wall-clock against the smoke spec. The riskiest path — full subprocess invocation with real `harbor run` — runs last, after the underlying contracts are individually validated.
8. **Task 8 (green sweep)** — minutes. Final cross-cut.

The smoke-spec budget pair (cap 1.0, estimate 0.6) is the smallest end-to-end exercise of the riskiest contract (a real two-invocation refusal across a real harbor invocation). Per CL's rule, the smoke-spec dollar+time bill is well under the bookreview-12 matrix Phase 4a unlocks; pay the small bill first.

---

## Out of scope (echo of entity body, captured for the implementer)

- Per-trial budget gating — harbor's concern via `spec.agent.max_budget_usd` per spec §6.2 (already in v1; unchanged in v2).
- Dynamic budget adjustment mid-run — the budget is read-once per invocation.
- Cost-source semantics beyond `summary.json` precedence over `result.json` — `phase4a-rk-runs-cost` (sibling) owns the shared read-side convention.
- Cost-estimation for not-yet-frozen specs — `rk freeze` (PKG-8) populates `experiment_meta.estimated_cost_usd`; this plan only consumes it.
- Markdown formatting of budget messages — JSON-stable output per §3.3; human-readable polish on consumer demand.
- Top-level `rk runs cost` JSON output schema — owned by the sibling entity; this plan and that entity share the cost-source precedence rule (`summary.json` first, then `result.json.stats.cost_usd`) and nothing else.

---

## Stage report template (for implementer)

When implementation completes, append a `## Stage Report: implementation` section to the entity file naming each Task by ID and the commit SHA(s) that closed it. Include the `uv run pytest` summary line at the end (e.g., `262 passed in 4m 12s`).
