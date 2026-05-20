# Phase 1 — rk run v2 wrapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the v2 `rk run` as a pre-check wrapper around `harbor run` that reads a frozen spec, runs the alias-drift and runs-dir mount-visibility canary pre-checks, translates the spec into a harbor `JobConfig` with `AgentConfig.import_path` dispatch, delegates execution to `harbor run`, surfaces harbor's exit code (reserving 30 for harbor runtime failure), and writes `spec.frozen.yaml` + `provenance.yaml` into the harbor-produced run-dir.

**Architecture:** v2 `rk run` is a thin wrapper. It owns: (a) spec parse → frozen-spec read, (b) the alias-drift pre-check (KEEP-EXTRACT from `src/razorback/provenance/drift.py`), (c) the runs-dir mount-visibility canary (NEW per AC-8), (d) auth resolution (KEEP-EXTRACT from `src/razorback/agents/auth.py`), (e) spec→JobConfig translation emitting `AgentConfig.import_path` for `spacedock_solver`, (f) `harbor run` invocation via subprocess, (g) provenance artifact write into the harbor-produced run-dir, and (h) exit-code passthrough with exit 30 reserved for harbor runtime failure. The v1 `src/razorback/run.py` + `src/razorback/cli/run.py` body sideline under `src/razorback/_legacy/` via `git mv`. Phase 1's walking-skeleton check runs the in-tree DAB adapter (Phase 2 swaps it for the harbor-DAB adapter). The spec→JobConfig translator built here is load-bearing for every subsequent phase.

**Tech Stack:** Python 3.12, Typer (CLI), pydantic (spec schema), harbor's `JobConfig` / `AgentConfig` (translation target only — razorback does not own JobConfig construction beyond the translation wrapper, per spec §8.1), `subprocess` (for `harbor run` invocation), `dotenv` (already-vendored, for `.env` auth discovery).

**Spec source of truth:** `/Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`. This plan cites section identities (§3.1, §6.1, §7.1, §8.1, etc.), not verbatim wording — `ra` (spec-corrections-from-phase0-probes) is concurrently editing §4.5, §6.1, §6.3, §9.2 wording. Section numbers and identities are stable across that work; wording is not. `b5` (spec-mitigation-resume-conflict) shipped the sealed_hash-keyed external freeze layout (§4.4 + §7.1 + §3.1/§8.1 canonicalization rule), which this plan's AC-3 + Task 4 + Task 6 inherit.

**Concurrent dependency status:**
- `b5` spec-mitigation-resume-conflict: shipped. §4.4 + §7.1 + §3.1/§8.1 canonicalization rule are in the spec at plan time.
- `ra` spec-corrections-from-phase0-probes: in `validation` stage at plan time (worktree at `.worktrees/spacedock-ensign-spec-corrections-from-phase0-probes`). Phase 1 implementation MUST wait on ra's merge so the import_path / n_attempts wording is final. The plan cites section identities, not exact wording, so this plan itself does not invalidate on ra's edits.

---

## AC ↔ task map (1:1 with cross-cutting tasks called out)

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-4 (auth + alias-drift + run-dir helper extractions) | §8.1 step 3 (alias-drift), §6.2 (auth via `AgentConfig.env`), §7.1 (run-dir helpers) | Task 1 (errors + ExitCode extras), Task 2 (auth re-pointing), Task 3 (alias-drift re-pointing) |
| AC-5 (legacy sideline) | §8.1 last paragraph (razorback does not own JobConfig) | Task 4 (`git mv` v1 modules under `_legacy/`) |
| AC-6 (import_path dispatch) | §4.5 + §6.2 + harbor entry-point probe (`docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md`) | Task 5 (spec→JobConfig translator) |
| AC-8 (runs-dir mount-visibility canary) | §3.1 path-canonicalization + bookreview regression investigation (`docs/superpowers/plans/2026-05-20-v1-bookreview-regression-investigation.md`) | Task 6 (canary helper + CLI wiring) |
| AC-2 (alias-drift pre-check + exit 30 passthrough) | §3.2 (`rk run` description) + §8.1 + §3.4 exit-code table | Task 7 (`rk run` body — pre-checks + harbor delegation) |
| AC-3 (spec.frozen.yaml + provenance.yaml in harbor's run-dir) | §7.1 + §8.1 step 6 | Task 8 (post-run provenance artifact write) |
| AC-1 (walking-skeleton holds against in-tree DAB) | §3.2 + AC-0.1(b) deterministic-smoke baseline (3/3 pass against `examples/specs/_deterministic-smoke.yaml`) | Task 9 (integration smoke against the deterministic spec) |
| AC-7 (`uv run pytest` exits 0) | (plan AC-1.6) | Task 10 (test-suite green from worktree branch tip) |

**Riskiest contract first.** Task 5 (spec→JobConfig translator emitting `AgentConfig.import_path` per AC-0.2's outcome) and Task 6 (runs-dir mount-visibility canary at the CLI boundary) land BEFORE the harbor-delegation body (Task 7). Per CL's "Validating new mechanisms" rule + the entity dispatch's completion-checklist item #3 ("integration-level mechanism validation — the deterministic-smoke spec — comes before comprehensive bookreview-claude runs"), the deterministic-smoke spec (`examples/specs/_deterministic-smoke.yaml`, baseline 3/3 pass at commit `e014dbf` per `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`) is Phase 1's walking-skeleton anchor — exercised by Task 9 the moment the wiring is in place, before any bookreview-claude full-spec runs.

**Module inventory anchors (per `docs/superpowers/plans/2026-05-19-razorback-inventory.md`):**
- KEEP-EXTRACT verbatim: `src/razorback/provenance/drift.py` (lines 11-35 `check_alias_drift`); `src/razorback/agents/auth.py` (lines 13-67 entire); `src/razorback/provenance/retry.py`; `src/razorback/provenance/provenance_yaml.py`; `src/razorback/spec/parse.py`; `src/razorback/spec/freeze.py`.
- ADAPT-EXTRACT (file:line ranges): `src/razorback/errors.py:7-16` (ExitCode IntEnum — adds `BUDGET_EXCEEDED = 22`, `TAINT_FINDINGS = 23`); `src/razorback/cli/run.py:22-34` (error→exit-code mapping pattern survives; body rewritten); `src/razorback/cli/__init__.py:8-19` (Typer-wired-from-subcommand pattern survives; topology changes); `src/razorback/compat/harbor_0_6_6.py:96-157` (auth-via-`AgentConfig.env` invariant survives as v2 test guidance; the translator body itself drops with `_legacy/` sideline). Phase 1 extracts these from `src/razorback/` and re-points the v2 paths.
- DROP (sidelined under `_legacy/` in Task 4): `src/razorback/run.py` (192 LoC); `src/razorback/manifest.py`; `src/razorback/observers/`; `src/razorback/runtime/`; `src/razorback/compat/`; v1 `cli/validate.py` + `cli/spec.py`.

**Out of scope per entity body:**
- Per-experiment budget gate (`--max-budget-usd-running <file>`) — Phase 4a.
- `rk freeze` extensions (solver_workflow_hash, spacedock_skill_version, harbor_agent_kwargs_hash) — Phase 4a.
- `SpacedockSolverAgent` v2 class — Phase 3. This plan emits the spec with `import_path` populated; it does not implement the class. AC-6's verifier is a unit test that asserts the translation output's `AgentConfig.import_path` value, not a live run that invokes the class.
- DAB harbor adapter — Phase 2. Phase 1's walking-skeleton check runs the in-tree DAB adapter via the existing `src/razorback/benchmarks/dab/prepare.py` path used by the v1 translator (the legacy translator's task-materialization helpers stay reachable from v2's translator until Phase 2 ports DAB out).

---

## Task 1 — Add `BudgetExceededError(22)` and `TaintFindingsError(23)` to `src/razorback/errors.py` (AC-4 prerequisite for v2 ExitCode surface)

**Files:**
- Modify: `src/razorback/errors.py`
- Test: `tests/unit/test_cli_exit_codes.py` (KEEP-VERBATIM per test inventory; extend with new codes)

**Spec cite:** §3.4 exit-code table (rows 22, 23). Inventory anchor: `errors.py:7-16`.

- [ ] **Step 1: Write the failing test for the new exit codes**

Open `tests/unit/test_cli_exit_codes.py` and append:

```python
from razorback.errors import (
    BudgetExceededError,
    ExitCode,
    TaintFindingsError,
)


def test_budget_exceeded_error_exit_code():
    assert BudgetExceededError.exit_code == 22
    assert ExitCode.BUDGET_EXCEEDED == 22


def test_taint_findings_error_exit_code():
    assert TaintFindingsError.exit_code == 23
    assert ExitCode.TAINT_FINDINGS == 23
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_exit_codes.py::test_budget_exceeded_error_exit_code tests/unit/test_cli_exit_codes.py::test_taint_findings_error_exit_code -v`
Expected: FAIL with `ImportError: cannot import name 'BudgetExceededError'` (or equivalent).

- [ ] **Step 3: Add the new exit codes and error classes**

Edit `src/razorback/errors.py` to extend `ExitCode` and add the two error classes. After the existing `HARBOR_RUNTIME = 30` line, ExitCode reads:

```python
class ExitCode(IntEnum):
    OK = 0
    GENERIC = 1
    USAGE = 2
    SPEC_ERROR = 10
    PROVENANCE_ERROR = 11
    CONSTRAINT_VIOLATION = 12
    SEED_MISMATCH = 20
    ALIAS_DRIFT = 21
    BUDGET_EXCEEDED = 22
    TAINT_FINDINGS = 23
    HARBOR_RUNTIME = 30
    CONFIG_INVALID = 24
```

Add at end of file:

```python
class BudgetExceededError(RazorbackError):
    """`--max-budget-usd-running` running-total + estimate exceeds `experiment.max_budget_usd` (§3.4)."""
    exit_code: int = ExitCode.BUDGET_EXCEEDED


class TaintFindingsError(RazorbackError):
    """`rk audit --policy strict` found at least one non-`clean` trial (§3.4)."""
    exit_code: int = ExitCode.TAINT_FINDINGS


class ConfigInvalidError(RazorbackError):
    """Configuration is structurally valid but operationally unusable (e.g., runs-dir not visible to harbor's docker environment, §3.4 row 24)."""
    exit_code: int = ExitCode.CONFIG_INVALID
```

Note: `CONFIG_INVALID = 24` is added here for the AC-8 canary's typed-error surface. The entity body (AC-8) names `ExitCode.CONFIG_INVALID` explicitly. This is a v2-only addition; v2 §3.4 exit-code table grows two rows (22, 23 documented in the spec; 24 added at implementation time per AC-8 explicit naming, captured for the spec's next field-additive update under §3.3 semver).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_cli_exit_codes.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/errors.py tests/unit/test_cli_exit_codes.py
git commit -m "errors: add BudgetExceeded(22), TaintFindings(23), ConfigInvalid(24) (Phase 1 AC-4 ExitCode surface)"
```

---

## Task 2 — Re-point auth module under v2 import path with attribution (AC-4: auth handling preserved)

**Files:**
- Read-only verify: `src/razorback/agents/auth.py` (KEEP-EXTRACT verbatim per inventory `:13-14, :17-20, :23-35, :38-44, :47-67`)
- Test: `tests/unit/test_claude_cli_auth_dotenv_only.py` (KEEP-VERBATIM per test inventory — FU-1 M3 AC-3)

**Spec cite:** §6.2 (auth via `AgentConfig.env`, never kwargs); FU-1 M3 AC-3 (`.env`-via-`dotenv_values` discipline). Inventory anchor: `compat/harbor_0_6_6.py:96-157` is the load-bearing v1 invariant whose CONTRACT (auth via `AgentConfig.env`, redacted on disk) survives in v2 — the translator body itself drops with `_legacy/` sideline.

This task is verification-only of the KEEP-EXTRACT classification. Phase 1 does not move `src/razorback/agents/auth.py` — it stays where it is. Task 5's spec→JobConfig translator calls `resolve_claude_auth` directly.

- [ ] **Step 1: Confirm the KEEP-VERBATIM test still imports the v2 location**

Run: `grep -n "from razorback" tests/unit/test_claude_cli_auth_dotenv_only.py`
Expected: imports `from razorback.agents.auth import resolve_claude_auth` (or similar) — the v2 path is the SAME as v1. No edits needed.

- [ ] **Step 2: Run the test against the current tree to confirm it passes**

Run: `uv run pytest tests/unit/test_claude_cli_auth_dotenv_only.py -v`
Expected: all tests PASS. If FAIL, escalate to FO via `SendMessage(to="team-lead")` — the auth module changed shape since the test inventory was written and Phase 1's AC-4 cannot be claimed as preserved.

- [ ] **Step 3: No commit (verification only)**

If Step 2 passes, this task is DONE. Mark the test inventory's `test_claude_cli_auth_dotenv_only.py` row as exercised verbatim from the v2 path. No new commit.

---

## Task 3 — Re-point alias-drift module under v2 import path (AC-4: alias-drift preserved)

**Files:**
- Read-only verify: `src/razorback/provenance/drift.py` (KEEP-EXTRACT verbatim per inventory `:11-35`)
- Test: `tests/unit/test_provenance_alias_drift.py` (KEEP-VERBATIM per test inventory)

**Spec cite:** §8.1 step 3 (alias-drift re-resolves model alias and refuses with `AliasDriftError` on mismatch unless `--allow-alias-drift` is passed); §3.4 exit 21.

Verification-only — `provenance/drift.py` does not move.

- [ ] **Step 1: Confirm the KEEP-VERBATIM test imports the v2 location**

Run: `grep -n "from razorback" tests/unit/test_provenance_alias_drift.py`
Expected: imports `from razorback.provenance.drift import check_alias_drift` (and / or related). v2 path is the SAME as v1.

- [ ] **Step 2: Run the test to confirm it passes**

Run: `uv run pytest tests/unit/test_provenance_alias_drift.py tests/unit/test_provenance_harbor_drift.py -v`
Expected: all tests PASS.

- [ ] **Step 3: No commit (verification only)**

---

## Task 4 — Sideline v1 `run.py` + helpers under `src/razorback/_legacy/` via `git mv` (AC-5)

**Files:**
- Move: `src/razorback/run.py` → `src/razorback/_legacy/run.py`
- Move: `src/razorback/manifest.py` → `src/razorback/_legacy/manifest.py`
- Move: `src/razorback/observers/` → `src/razorback/_legacy/observers/`
- Move: `src/razorback/runtime/` → `src/razorback/_legacy/runtime/`
- Move: `src/razorback/compat/` → `src/razorback/_legacy/compat/`
- Move: `src/razorback/cli/validate.py` → `src/razorback/_legacy/cli/validate.py`
- Move: `src/razorback/cli/spec.py` → `src/razorback/_legacy/cli/spec.py`
- Modify: `src/razorback/cli/__init__.py` (drop validate/spec sub-app wiring)
- Modify: `src/razorback/cli/run.py` (drop the `from razorback.run import execute_run` body — Task 7 replaces it; this task removes the v1 reference so the move doesn't leave dangling imports)

**Spec cite:** §8.1 last paragraph ("razorback does not own JobConfig construction"). Inventory anchors: `run.py` (192 LoC, DROP), `manifest.py` (26 LoC, DROP), `observers/` (85 LoC across 4 files, DROP), `runtime/reconcile.py` (134 LoC, DROP), `compat/harbor_0_6_6.py` (264 LoC, DROP — the auth-routing invariant survives as test guidance, not as live code), `cli/validate.py` (72 LoC, DROP), `cli/spec.py` (8 LoC, DROP).

**Caveat:** v1 tests that exercise the dropped modules — per the test inventory, 17 DROP-classified tests — will fail under Task 7. Those tests stay in-tree but get marked xfail or skip until Phase 6/7 deletes them outright. This plan does not delete v1 tests; it sidelines v1 code, then Task 10 catalogs which DROP-classified tests are now failing (expected) vs. KEEP-VERBATIM tests that should still pass.

- [ ] **Step 1: Confirm `_legacy/` holding tank exists**

Run: `ls /Users/clkao/git/razorback/src/razorback/_legacy/`
Expected: directory exists (per task #8 in the existing task list: AC-0.11 already created the `_legacy/` holding tank).

- [ ] **Step 2: `git mv` each v1 module into `_legacy/`**

```bash
cd /Users/clkao/git/razorback
mkdir -p src/razorback/_legacy/cli
git mv src/razorback/run.py src/razorback/_legacy/run.py
git mv src/razorback/manifest.py src/razorback/_legacy/manifest.py
git mv src/razorback/observers src/razorback/_legacy/observers
git mv src/razorback/runtime src/razorback/_legacy/runtime
git mv src/razorback/compat src/razorback/_legacy/compat
git mv src/razorback/cli/validate.py src/razorback/_legacy/cli/validate.py
git mv src/razorback/cli/spec.py src/razorback/_legacy/cli/spec.py
```

- [ ] **Step 3: Confirm `git log --diff-filter=R -- src/razorback/run.py` shows the rename (AC-5's `Verified by:` clause)**

Run: `git log --diff-filter=R --name-status -- src/razorback/run.py`
Expected: at least one entry whose status is `R<percent>` and whose paths read `src/razorback/run.py → src/razorback/_legacy/run.py`. Per AC-5 verbatim.

- [ ] **Step 4: Update `src/razorback/cli/__init__.py` to drop `validate` + `spec` sub-app wiring**

Edit `src/razorback/cli/__init__.py`. After Task 4 the file contents are:

```python
# ABOUTME: Typer application root for the `rk` binary.
# ABOUTME: Subcommands attach here; v2 wires up `rk run` only at Phase 1.

import typer

from razorback.cli.run import run_command

app = typer.Typer(
    help="Razorback: a benchmark runner for agentic research workflows.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Anchor the Typer app so single-command apps still expose `rk run`."""


app.command("run")(run_command)

from razorback.cli.runs import runs_app

app.add_typer(runs_app, name="runs")

from razorback.cli.constraints import constraints_app

app.add_typer(constraints_app, name="constraints")

from razorback.cli.baseline import baseline_app

app.add_typer(baseline_app, name="baseline")

from razorback.cli.registry import registry_app

app.add_typer(registry_app, name="registry")
```

Note: `validate` and `spec` sub-app imports are removed entirely. The optional `runs`, `constraints`, `baseline`, `registry` sub-apps stay attached (they are KEEP-EXTRACT optional surfaces per inventory). Topology change: `rk spec freeze` → `rk freeze` is a Phase 4a concern (PKG-8); Phase 1 just removes the v1 `spec` sub-app entry rather than flattening to top-level `rk freeze`.

- [ ] **Step 5: Update `src/razorback/cli/run.py` to remove the v1 `execute_run` reference**

Edit `src/razorback/cli/run.py`. After this edit the file body keeps the existing Typer surface but stub-replaces the body — Task 7 will fill it with the v2 wrapper. After Step 5:

```python
# ABOUTME: `rk run` Typer command. Phase 1: parse spec, run pre-checks, delegate to harbor run.
# ABOUTME: Maps razorback typed errors to documented exit codes (§3.4).

from pathlib import Path

import typer

from razorback.errors import ExitCode, RazorbackError, SpecError
from razorback.spec.parse import parse_spec_file


def run_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    runs_dir: Path = typer.Option(Path("_runs"), "--runs-dir", help="Base directory for run-dirs."),
    allow_alias_drift: bool = typer.Option(
        False,
        "--allow-alias-drift",
        help="Run even when provider model version differs from frozen.",
    ),
) -> None:
    """Execute a frozen spec against harbor and write a run-dir."""
    try:
        spec = parse_spec_file(spec_path)
    except SpecError as exc:
        typer.echo(f"SpecError: {exc}", err=True)
        raise typer.Exit(ExitCode.SPEC_ERROR)

    # Phase 1 Task 7 fills this body. The v1 `execute_run` call is removed
    # under `_legacy/`; the v2 wrapper lands in Task 7.
    raise RuntimeError("rk run v2 wrapper not yet implemented — Phase 1 Task 7")
```

This intentionally leaves the CLI failing in a known way until Task 7 lands. Task 5 (translator) and Task 6 (canary) build the dependencies; Task 7 wires them together.

- [ ] **Step 6: Confirm the test suite can still IMPORT the package**

Run: `uv run python -c "import razorback.cli; import razorback.errors; import razorback.spec.parse; import razorback.spec.freeze; import razorback.provenance.drift; import razorback.agents.auth; print('ok')"`
Expected: prints `ok`. If `ImportError`, fix the dangling import in the same commit (likely a sibling module still imports from `razorback.run` / `razorback.manifest` / `razorback.observers`).

- [ ] **Step 7: Commit**

```bash
git add -u src/razorback/
git add src/razorback/_legacy/
git commit -m "Phase 1 AC-5: sideline v1 run.py + manifest + observers + runtime + compat + validate + spec under _legacy/"
```

---

## Task 5 — Spec→JobConfig translator emitting `AgentConfig.import_path` for `spacedock_solver` (AC-6)

**Files:**
- Create: `src/razorback/translate.py`
- Test: Create: `tests/unit/test_translate_spacedock_solver_import_path.py`

**Spec cite:** §6.2 (`agent.kind: spacedock_solver` → harbor's `AgentConfig.import_path`); §4.5 (registration via `import_path`, NOT entry-point group — per ra's spec-corrections); harbor entry-point probe at `docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md` (AC-0.2 verdict: dispatch via `AgentConfig.import_path: "module.path:ClassName"`). Inventory anchor: `compat/harbor_0_6_6.py:96-157` (v1 translator's import_path emit at line 130; lifts the contract, drops the surrounding scaffolding).

**Why this lands BEFORE the harbor-delegation body (Task 7):** AC-0.2's outcome (`AgentConfig.import_path` is the working dispatch mechanism) is the load-bearing contract for every Phase ≥1 invocation of `harbor run`. If the translator emits the wrong `import_path` shape — or omits `kwargs` / `env` / `model_name` per the harbor source probe (`docs/superpowers/plans/2026-05-19-harbor-source-probe.md` AC-0.4) — every downstream `harbor run` invocation fails. Per CL's "Validating new mechanisms" rule, this contract gets the smallest end-to-end exercise first (unit test asserting the post-translation `AgentConfig` shape) before Task 7's wider integration.

- [ ] **Step 1: Write the failing unit test for `spacedock_solver` → `AgentConfig.import_path`**

Create `tests/unit/test_translate_spacedock_solver_import_path.py`:

```python
# ABOUTME: AC-6: spec.agent.kind: spacedock_solver translates to AgentConfig.import_path.
# ABOUTME: Verifies the import_path literal per harbor entry-point probe (AC-0.2).

from pathlib import Path

import pytest

from razorback.spec.parse import parse_spec_text
from razorback.spec.freeze import freeze_spec
from razorback.translate import spec_to_job_config


SPACEDOCK_SPEC_YAML = """
version: 1
experiment: phase1-translate-test
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
  stages: ["model"]
  tools_allowed: []
  prompts:
    model: tests/fixtures/translate/model.md
"""


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    # Provide a .env so resolve_claude_auth doesn't refuse.
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test-fixture\n")
    fixture_dir = tmp_path / "tests" / "fixtures" / "translate"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "model.md").write_text("model stage prompt body\n")
    return tmp_path


def test_spacedock_solver_emits_import_path(project_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(project_root)
    spec = parse_spec_text(SPACEDOCK_SPEC_YAML)
    frozen_text = freeze_spec(spec)
    frozen_spec = parse_spec_text(frozen_text)

    jc, _ = spec_to_job_config(
        frozen_spec,
        job_name="job-test",
        jobs_dir=project_root / "_runs" / "phase1-translate-test",
        project_root=project_root,
    )

    assert len(jc.agents) == 1
    agent_cfg = jc.agents[0]
    assert agent_cfg.import_path == "razorback.agents.spacedock_solver:SpacedockSolverAgent"
    assert agent_cfg.model_name == "claude-opus-4-5"
    # AC-6 cross-cut: per harbor source probe (AC-0.4), auth lands on AgentConfig.env,
    # NOT kwargs. The FU-1 AC-1 invariant survives in v2.
    assert "ANTHROPIC_API_KEY" in agent_cfg.env
    assert "ANTHROPIC_API_KEY" not in agent_cfg.kwargs
    assert agent_cfg.kwargs.get("sealed_hash") is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_translate_spacedock_solver_import_path.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'razorback.translate'`.

- [ ] **Step 3: Create `src/razorback/translate.py` with the spacedock_solver translation path**

Create `src/razorback/translate.py`:

```python
# ABOUTME: Spec → harbor JobConfig translator (Phase 1 AC-6 — emits AgentConfig.import_path).
# ABOUTME: Replaces the v1 compat translator. Auth flows via AgentConfig.env per FU-1 AC-1.

from pathlib import Path
from typing import Any

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig, RetryConfig
from harbor.models.trial.config import (
    AgentConfig,
    EnvironmentConfig,
    TaskConfig,
    VerifierConfig,
)

from razorback.agents.auth import resolve_claude_auth
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.errors import SpecError
from razorback.spec.schema import (
    AdeBenchBenchmarkBlock,
    ClaudeCliAgentBlock,
    DabBenchmarkBlock,
    LocalBenchmarkBlock,
    NopAgentBlock,
    SpacedockSolverAgentBlock,
    Spec,
)


SPACEDOCK_SOLVER_IMPORT_PATH = (
    "razorback.agents.spacedock_solver:SpacedockSolverAgent"
)


def spec_to_job_config(
    spec: Spec,
    *,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path | None = None,
    project_root: Path | None = None,
    home: Path | None = None,
    prior_frozen_spec_path: Path | None = None,
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    """Translate a parsed (frozen) spec into a harbor JobConfig.

    Returns (JobConfig, trial_name_map). The map is empty for non-DAB benchmarks.
    Phase 1 emits `AgentConfig.import_path` for spacedock_solver per AC-6.
    """
    agent_cfg, task_env = _build_agent_config(
        spec,
        project_root=project_root,
        home=home,
        prior_frozen_spec_path=prior_frozen_spec_path,
    )

    if isinstance(spec.benchmark, LocalBenchmarkBlock):
        return _build_local(
            spec=spec, job_name=job_name, jobs_dir=jobs_dir, agent_cfg=agent_cfg
        ), {}
    if isinstance(spec.benchmark, DabBenchmarkBlock):
        if tasks_root is None:
            raise SpecError("DAB specs require tasks_root.")
        return _build_dab(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            tasks_root=Path(tasks_root),
            agent_cfg=agent_cfg,
            task_env=task_env,
        )
    if isinstance(spec.benchmark, AdeBenchBenchmarkBlock):
        return _build_ade_bench(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            agent_cfg=agent_cfg,
            home=home,
        ), {}
    raise SpecError(f"unsupported benchmark block: {type(spec.benchmark).__name__}")


def _build_agent_config(
    spec: Spec,
    *,
    project_root: Path | None,
    home: Path | None,
    prior_frozen_spec_path: Path | None = None,
) -> tuple[AgentConfig, dict[str, str]]:
    if isinstance(spec.agent, NopAgentBlock):
        return AgentConfig(name=AgentName.NOP.value), {}

    if isinstance(spec.agent, SpacedockSolverAgentBlock):
        if project_root is None:
            raise SpecError(
                "spacedock-solver requires project_root for .env auth discovery."
            )
        if spec.agent.sealed_hash is None:
            raise SpecError(
                "spacedock-solver spec must be frozen (agent.sealed_hash missing)."
            )
        if spec.agent.prompt_contents is None:
            raise SpecError(
                "spacedock-solver spec must be frozen (agent.prompt_contents missing)."
            )
        resolution = resolve_claude_auth(project_root=project_root, home=home)
        # FU-1 AC-1: auth ONLY via AgentConfig.env (harbor redacts on disk).
        # kwargs is plaintext-on-disk and must not carry credentials.
        kwargs: dict[str, Any] = {
            "model": spec.agent.model,
            "sampling": {
                "temperature": spec.agent.sampling.temperature,
                "top_p": spec.agent.sampling.top_p,
                "seed": spec.agent.sampling.seed,
            },
            "stages": list(spec.agent.stages),
            "tools_allowed": list(spec.agent.tools_allowed),
            "prompts": dict(spec.agent.prompts),
            "prompt_contents": dict(spec.agent.prompt_contents),
            "sealed_hash": spec.agent.sealed_hash,
            "prior_frozen_spec_path": (
                str(prior_frozen_spec_path) if prior_frozen_spec_path else None
            ),
        }
        agent_cfg = AgentConfig(
            import_path=SPACEDOCK_SOLVER_IMPORT_PATH,
            model_name=spec.agent.model,
            kwargs=kwargs,
            env=dict(resolution.env),
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env

    if isinstance(spec.agent, ClaudeCliAgentBlock):
        if project_root is None:
            raise SpecError(
                "claude-cli agent requires project_root for .env auth discovery."
            )
        resolution = resolve_claude_auth(project_root=project_root, home=home)
        kwargs: dict[str, Any] = {
            "tools_allowed": list(spec.agent.tools_allowed),
            "sampling_temperature": spec.agent.sampling.temperature,
        }
        agent_cfg = AgentConfig(
            import_path="razorback.agents.claude_cli:ClaudeCliAgent",
            model_name=spec.agent.model,
            kwargs=kwargs,
            env=dict(resolution.env),
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env

    raise SpecError(f"unsupported agent block: {type(spec.agent).__name__}")


def _build_local(
    *, spec: Spec, job_name: str, jobs_dir: Path, agent_cfg: AgentConfig
) -> JobConfig:
    assert isinstance(spec.benchmark, LocalBenchmarkBlock)
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=[TaskConfig(path=Path(p).resolve()) for p in spec.benchmark.task_paths],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=EnvironmentConfig(delete=False),
    )


def _build_ade_bench(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    agent_cfg: AgentConfig,
    home: Path | None = None,
) -> JobConfig:
    # Phase 1 keeps the in-tree ade-bench path until Phase 8's port-out.
    # The materialize_git_task helper lifts from src/razorback/benchmarks/ade_bench/tasks.py.
    from razorback.benchmarks.ade_bench.tasks import (
        materialize_git_task,
        resolve_task_dirs,
    )
    from razorback.benchmarks.dab.prepare import _DEFAULT_DOCKER_IMAGE

    assert isinstance(spec.benchmark, AdeBenchBenchmarkBlock)
    resolved = resolve_task_dirs(
        tasks_root=spec.benchmark.tasks_root,
        tasks=spec.benchmark.tasks,
    )
    docker_image = (
        spec.benchmark.docker_image_override or _DEFAULT_DOCKER_IMAGE
    )
    home_dir = Path(home) if home is not None else Path.home()
    cache_root = home_dir / ".cache" / "razorback" / "ade-bench"

    tasks: list[TaskConfig] = []
    for r in resolved:
        if r.git_url is not None and r.git_commit_id is not None:
            materialized = materialize_git_task(
                git_url=r.git_url,
                git_commit_id=r.git_commit_id,
                source_path=r.path,
                docker_image=docker_image,
                cache_root=cache_root,
            )
            tasks.append(TaskConfig(path=materialized))
        else:
            tasks.append(TaskConfig(path=r.path))
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=EnvironmentConfig(delete=False),
    )


def _build_dab(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path,
    agent_cfg: AgentConfig,
    task_env: dict[str, str],
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    # Phase 1 keeps the in-tree DAB prepare path until Phase 2's port-out.
    from razorback.benchmarks.dab.prepare import prepare_dataset_tasks

    assert isinstance(spec.benchmark, DabBenchmarkBlock)
    manifest_all: list[dict] = []
    for dataset in spec.benchmark.datasets:
        manifest_all.extend(
            prepare_dataset_tasks(
                data_root=Path(spec.benchmark.data_root),
                dataset=dataset,
                tasks_root=tasks_root / dataset,
                task_env=task_env,
            )
        )
    tasks = [TaskConfig(path=entry["task_dir"]) for entry in manifest_all]
    trial_name_map = {
        entry["task_name"]: (entry["dataset"], entry["query_id"]) for entry in manifest_all
    }
    cfg = JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=EnvironmentConfig(delete=False),
    )
    return cfg, trial_name_map
```

Note: this lifts from the v1 `compat/harbor_0_6_6.py` translator largely verbatim — the contract (auth via `AgentConfig.env`, `import_path` dispatch for spacedock_solver) is what survives. The wrapper module name changes from `compat/harbor_0_6_6.py` to `translate.py` because v2 ships only one harbor minor (per spec §9.1 + the Phase 0 D5 decision); a per-harbor-minor `compat/` namespace was v1's hedge against bumping harbor and is not v2's stance.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_translate_spacedock_solver_import_path.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/translate.py tests/unit/test_translate_spacedock_solver_import_path.py
git commit -m "Phase 1 AC-6: translate.py emits AgentConfig.import_path for spacedock_solver (per AC-0.2 probe)"
```

---

## Task 6 — Runs-dir mount-visibility canary at the CLI boundary (AC-8)

**Files:**
- Create: `src/razorback/runs_dir_canary.py`
- Test: Create: `tests/unit/test_runs_dir_canary.py`

**Spec cite:** §3.1 path-canonicalization design rule (added by `b5`'s Task 3). Reference investigation: `docs/superpowers/plans/2026-05-20-v1-bookreview-regression-investigation.md`. v1 anchor: `tests/conftest.py:12-23` `colima_safe_tmp_path` fixture encodes the discipline for tests; v2 lifts it to the CLI boundary via a runtime probe.

**Why this lands BEFORE the harbor-delegation body (Task 7):** The bookreview regression investigation (`docs/superpowers/plans/2026-05-20-v1-bookreview-regression-investigation.md`) named this as a silent 0/3 failure mode on macOS+Colima when `--runs-dir` is on a filesystem the docker VM cannot see. Per the entity body's AC-8 verbatim: "the canary still runs and succeeds in the normal case; the same error class fires if `runs-dir` is on a filesystem the container can't see." The CLI is the boundary that catches this; if Task 7's `harbor run` invocation goes ahead with an invisible runs-dir, every trial silently no-ops and burns budget. The smallest exercise of the riskiest contract.

- [ ] **Step 1: Write the failing test for the canary's negative case (invisible runs-dir aborts with CONFIG_INVALID)**

Create `tests/unit/test_runs_dir_canary.py`:

```python
# ABOUTME: AC-8: rk run aborts with ExitCode.CONFIG_INVALID when --runs-dir is not visible
# ABOUTME: to the harbor-orchestrated docker containers (e.g., /tmp on macOS+Colima).

from pathlib import Path

import pytest

from razorback.errors import ConfigInvalidError, ExitCode
from razorback.runs_dir_canary import check_runs_dir_visible


def test_canary_returns_silently_for_users_rooted_dir(tmp_path: Path):
    # /Users-rooted paths are virtiofs-mounted under Colima's default config.
    # On non-macOS or non-Colima environments, the canary still succeeds because
    # the docker bind mount works for any path the user has write access to.
    runs_dir = tmp_path / "_runs"
    runs_dir.mkdir()
    # No exception → canary passed.
    check_runs_dir_visible(runs_dir, container_probe=lambda canary_path: True)


def test_canary_raises_config_invalid_when_container_cannot_see(tmp_path: Path):
    runs_dir = tmp_path / "_runs"
    runs_dir.mkdir()
    with pytest.raises(ConfigInvalidError) as exc_info:
        check_runs_dir_visible(runs_dir, container_probe=lambda canary_path: False)
    assert exc_info.value.exit_code == ExitCode.CONFIG_INVALID
    msg = str(exc_info.value)
    assert str(runs_dir) in msg
    # Diagnostic must name the fix per AC-8 "use --runs-dir under /Users/..."
    assert "/Users/" in msg or "virtiofs" in msg


def test_canary_writes_and_removes_canary_file(tmp_path: Path):
    runs_dir = tmp_path / "_runs"
    runs_dir.mkdir()
    seen_paths: list[Path] = []

    def probe(canary_path: Path) -> bool:
        seen_paths.append(canary_path)
        # Assert the canary file exists on disk when the probe is invoked.
        assert canary_path.exists(), f"canary {canary_path} not written before probe"
        return True

    check_runs_dir_visible(runs_dir, container_probe=probe)
    assert len(seen_paths) == 1
    # Canary file must be cleaned up after the probe (positive or negative).
    assert not seen_paths[0].exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_dir_canary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'razorback.runs_dir_canary'`.

- [ ] **Step 3: Create `src/razorback/runs_dir_canary.py`**

Create `src/razorback/runs_dir_canary.py`:

```python
# ABOUTME: Runs-dir mount-visibility canary (Phase 1 AC-8).
# ABOUTME: Probes harbor docker bind-mount visibility before any agent invocation.

import uuid
from pathlib import Path
from typing import Callable

from razorback.errors import ConfigInvalidError


def check_runs_dir_visible(
    runs_dir: Path,
    *,
    container_probe: Callable[[Path], bool],
) -> None:
    """Write a canary file under runs_dir and probe whether the container can see it.

    Raises `ConfigInvalidError` (exit code 24) with a diagnostic naming the
    runs-dir, its resolved path, and the fix if the canary is not visible.
    """
    resolved = Path(runs_dir).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    canary = resolved / f".rk-canary-{uuid.uuid4().hex[:8]}"
    canary.write_text("rk-canary\n")
    try:
        visible = container_probe(canary)
    finally:
        canary.unlink(missing_ok=True)
    if not visible:
        raise ConfigInvalidError(
            f"runs-dir not visible to harbor docker containers: "
            f"runs_dir={runs_dir} resolved={resolved}. "
            f"On macOS+Colima, use --runs-dir under /Users/... or a "
            f"virtiofs-mounted volume (configurable via colima.yaml)."
        )


def default_container_probe_factory(
    agent_image: str = "alpine:3.20",
) -> Callable[[Path], bool]:
    """Return a container_probe that execs `ls <canary>` inside a throwaway docker container.

    The probe returns True iff `ls` succeeds inside a container started with
    `runs-dir` bind-mounted to the same in-container path. The probe shells out
    to `docker run --rm -v <resolved>:<resolved> <image> ls <canary>`.
    """
    import subprocess

    def _probe(canary_path: Path) -> bool:
        mount_root = canary_path.parent
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{mount_root}:{mount_root}",
                agent_image,
                "ls",
                str(canary_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode == 0

    return _probe
```

The dependency injection (`container_probe`) keeps unit tests synchronous and at zero docker cost. The default factory produces the live probe Task 7 invokes from the CLI body.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_runs_dir_canary.py -v`
Expected: PASS (all three tests).

- [ ] **Step 5: Commit**

```bash
git add src/razorback/runs_dir_canary.py tests/unit/test_runs_dir_canary.py
git commit -m "Phase 1 AC-8: runs-dir mount-visibility canary at CLI boundary (per bookreview-regression investigation)"
```

---

## Task 7 — `rk run` body: pre-checks + harbor delegation + exit-code passthrough (AC-2, AC-6 wiring)

**Files:**
- Modify: `src/razorback/cli/run.py`
- Test: Create: `tests/unit/test_rk_run_v2_pre_checks.py`

**Spec cite:** §8.1 (six-step body); §3.4 (exit 21 alias-drift, exit 30 harbor runtime); §3.1 path-canonicalization rule. Inventory anchor: `cli/run.py:22-34` (error→exit-code mapping pattern verbatim).

**Why this lands AFTER Tasks 5 + 6:** Task 7 wires the pieces together. The pieces themselves are validated by Task 5's unit test (translator emits the right shape) and Task 6's canary tests (visibility probe behaves correctly under positive + negative cases). Task 7's tests focus on the wiring: alias-drift call is made with the right kwargs, harbor exit code surfaces as exit 30, the canary runs BEFORE the harbor call.

- [ ] **Step 1: Write the failing test for alias-drift wiring (mocked provider)**

Create `tests/unit/test_rk_run_v2_pre_checks.py`:

```python
# ABOUTME: AC-2: rk run v2 wires alias-drift pre-check and surfaces harbor exit code as 30.
# ABOUTME: Mocks the provider API and the harbor subprocess invocation.

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from razorback.cli import app
from razorback.errors import ExitCode
from razorback.provenance.errors import AliasDriftError


@pytest.fixture
def frozen_spec_path(tmp_path: Path) -> Path:
    # Minimal frozen spec with a populated provenance.yaml beside it.
    spec_yaml = tmp_path / "frozen.yaml"
    spec_yaml.write_text(
        "version: 1\n"
        "experiment: phase1-test\n"
        "agent:\n"
        "  kind: nop\n"
        "benchmark:\n"
        "  kind: local\n"
        "  task_paths: []\n"
        "trials: 1\n"
        "provenance:\n"
        "  model_resolved_version: claude-opus-4-5-20251022\n"
        "  harbor_version: 0.6.6\n"
    )
    return spec_yaml


def test_alias_drift_refusal_exits_21(frozen_spec_path: Path, tmp_path: Path):
    with patch("razorback.cli.run._resolve_model_version") as resolve_mock, \
         patch("razorback.cli.run._run_canary"):
        resolve_mock.side_effect = AliasDriftError(
            model_alias="claude-opus-4-5",
            frozen="claude-opus-4-5-20251022",
            resolved="claude-opus-4-5-DRIFT",
        )
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["run", str(frozen_spec_path), "--runs-dir", str(tmp_path / "_runs")],
        )
        assert result.exit_code == ExitCode.ALIAS_DRIFT == 21


def test_allow_alias_drift_skips_refusal(frozen_spec_path: Path, tmp_path: Path):
    with patch("razorback.cli.run._resolve_model_version") as resolve_mock, \
         patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._invoke_harbor") as harbor_mock:
        # Even though resolved differs, --allow-alias-drift suppresses the error.
        resolve_mock.return_value = ("claude-opus-4-5-DRIFT", "2026-05-19")
        harbor_mock.return_value = 0  # harbor exits 0
        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "run",
                str(frozen_spec_path),
                "--runs-dir",
                str(tmp_path / "_runs"),
                "--allow-alias-drift",
            ],
        )
        assert result.exit_code == 0


def test_harbor_runtime_failure_surfaces_exit_30(frozen_spec_path: Path, tmp_path: Path):
    with patch("razorback.cli.run._resolve_model_version") as resolve_mock, \
         patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._invoke_harbor") as harbor_mock:
        resolve_mock.return_value = ("claude-opus-4-5-20251022", "2026-05-19")
        harbor_mock.return_value = 7  # harbor exits non-zero
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["run", str(frozen_spec_path), "--runs-dir", str(tmp_path / "_runs")],
        )
        assert result.exit_code == ExitCode.HARBOR_RUNTIME == 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_rk_run_v2_pre_checks.py -v`
Expected: FAIL — Task 4's stub raised `RuntimeError`; the tests expect the v2 body.

- [ ] **Step 3: Implement the v2 `rk run` body**

Replace `src/razorback/cli/run.py` body with:

```python
# ABOUTME: `rk run` Typer command (Phase 1 v2). Parse, pre-check, translate, delegate to harbor.
# ABOUTME: Maps razorback typed errors to documented exit codes (§3.4).

import os
import subprocess
import sys
from pathlib import Path

import typer

from razorback.errors import (
    ConfigInvalidError,
    ExitCode,
    RazorbackError,
    SpecError,
)
from razorback.provenance.drift import check_alias_drift, check_harbor_drift
from razorback.provenance.errors import AliasDriftError
from razorback.runs_dir_canary import (
    check_runs_dir_visible,
    default_container_probe_factory,
)
from razorback.spec.parse import parse_spec_file
from razorback.translate import spec_to_job_config


def _resolve_model_version(model_alias: str, frozen_resolved: str, allow_drift: bool):
    """Re-resolve via Anthropic SDK; wrapped for test patching (Task 7 Step 1)."""
    import anthropic
    client = anthropic.Anthropic()
    return check_alias_drift(
        model_alias=model_alias,
        frozen_resolved_version=frozen_resolved,
        client=client,
        allow=allow_drift,
    )


def _run_canary(runs_dir: Path) -> None:
    """Runs-dir mount-visibility probe (AC-8); wrapped for test patching."""
    probe = default_container_probe_factory()
    check_runs_dir_visible(runs_dir, container_probe=probe)


def _invoke_harbor(job_config_yaml: Path) -> int:
    """Subprocess-invoke `harbor run -c <yaml>`; wrapped for test patching.

    Returns harbor's exit code. Razorback's caller surfaces this as exit 30
    if non-zero (§3.4).
    """
    proc = subprocess.run(
        ["uv", "run", "harbor", "run", "-c", str(job_config_yaml)],
        capture_output=False,
    )
    return proc.returncode


def run_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    runs_dir: Path = typer.Option(Path("_runs"), "--runs-dir", help="Base directory for run-dirs."),
    allow_alias_drift: bool = typer.Option(
        False,
        "--allow-alias-drift",
        help="Run even when provider model version differs from frozen.",
    ),
) -> None:
    """Execute a frozen spec against harbor and write the v2 run-dir artifacts."""
    try:
        spec = parse_spec_file(spec_path)
    except SpecError as exc:
        typer.echo(f"SpecError: {exc}", err=True)
        raise typer.Exit(ExitCode.SPEC_ERROR)

    # AC-8: runs-dir mount-visibility canary BEFORE any agent invocation.
    runs_dir_resolved = Path(runs_dir).expanduser().resolve()
    try:
        _run_canary(runs_dir_resolved)
    except ConfigInvalidError as exc:
        typer.echo(f"ConfigInvalidError: {exc}", err=True)
        raise typer.Exit(ExitCode.CONFIG_INVALID)

    # AC-2: alias-drift pre-check + harbor major-version drift.
    frozen_provenance = spec.model_dump(mode="json").get("provenance") or {}
    frozen_model = frozen_provenance.get("model_resolved_version")
    frozen_harbor = frozen_provenance.get("harbor_version")

    if frozen_harbor is not None:
        try:
            check_harbor_drift(frozen=frozen_harbor, installed=None)
        except RazorbackError as exc:
            typer.echo(f"{type(exc).__name__}: {exc}", err=True)
            raise typer.Exit(exc.exit_code)

    if frozen_model is not None:
        model_alias = getattr(spec.agent, "model", None) or "claude-opus-4-5"
        try:
            _resolve_model_version(model_alias, frozen_model, allow_alias_drift)
        except AliasDriftError as exc:
            typer.echo(f"AliasDriftError: {exc}", err=True)
            raise typer.Exit(ExitCode.ALIAS_DRIFT)

    # AC-6: spec→JobConfig translation with import_path dispatch.
    # AC-3 + §3.1 canonicalization: jobs_dir is the absolute, symlink-resolved path.
    from razorback.spec.freeze import derive_job_name, freeze_spec
    frozen_text = freeze_spec(spec)
    job_name = derive_job_name(frozen_text)
    run_dir = runs_dir_resolved / spec.experiment / job_name
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        job_config, _ = spec_to_job_config(
            spec,
            job_name=job_name,
            jobs_dir=run_dir.parent,  # absolute, resolved per §3.1 canonicalization rule
            tasks_root=run_dir / "tasks",
            project_root=Path.cwd(),
        )
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)

    # Write the JobConfig YAML for harbor's `-c` flag, then invoke harbor.
    job_config_yaml = run_dir / "_job_config.yaml"
    job_config_yaml.write_text(job_config.model_dump_json(indent=2))

    rc = _invoke_harbor(job_config_yaml)
    if rc != 0:
        # AC-2: surface harbor's non-zero exit as exit 30.
        typer.echo(f"harbor run failed (exit {rc}); surfacing as exit 30", err=True)
        raise typer.Exit(ExitCode.HARBOR_RUNTIME)

    # AC-3 (Task 8 finishes): write spec.frozen.yaml + provenance.yaml into the
    # harbor-produced run-dir. Task 8 lands the writer; this task's body
    # delegates to a helper Task 8 fills in.
    _write_provenance_artifacts(spec, frozen_text, run_dir)


def _write_provenance_artifacts(spec, frozen_text: str, run_dir: Path) -> None:
    """Phase 1 Task 8 fills this; minimal placeholder is byte-faithful spec.frozen.yaml."""
    (run_dir / "spec.frozen.yaml").write_text(frozen_text)
    # provenance.yaml is the next step (Task 8).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_rk_run_v2_pre_checks.py -v`
Expected: PASS (all three tests).

- [ ] **Step 5: Commit**

```bash
git add src/razorback/cli/run.py tests/unit/test_rk_run_v2_pre_checks.py
git commit -m "Phase 1 AC-2: rk run v2 wires alias-drift + canary + import_path translator + harbor delegation"
```

---

## Task 8 — Write `provenance.yaml` into the harbor-produced run-dir (AC-3)

**Files:**
- Modify: `src/razorback/cli/run.py` (`_write_provenance_artifacts`)
- Test: Create: `tests/unit/test_rk_run_v2_provenance_artifacts.py`

**Spec cite:** §7.1 (razorback adds `spec.frozen.yaml` + `provenance.yaml` to harbor's run-dir); §8.1 step 6.

**Byte-for-byte invariant:** Per the entity's AC-3 verbatim — "content matches the input frozen spec byte-for-byte (no re-freezing inside `rk run`)". v1 re-freezes the spec inside `_execute_run_async` (`src/razorback/_legacy/run.py:41-45` after Task 4's move); v2 does NOT. The frozen spec passed to `rk run` is the wire artifact; `rk run` echoes it.

- [ ] **Step 1: Write the failing test for byte-for-byte spec.frozen.yaml + provenance.yaml**

Create `tests/unit/test_rk_run_v2_provenance_artifacts.py`:

```python
# ABOUTME: AC-3: rk run writes spec.frozen.yaml + provenance.yaml into the harbor run-dir.
# ABOUTME: spec.frozen.yaml matches the input bytes (no re-freezing inside rk run).

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from razorback.cli import app


FROZEN_SPEC_YAML = (
    "version: 1\n"
    "experiment: phase1-ac3-test\n"
    "agent:\n"
    "  kind: nop\n"
    "benchmark:\n"
    "  kind: local\n"
    "  task_paths: []\n"
    "trials: 1\n"
    "provenance:\n"
    "  model_resolved_version: claude-opus-4-5-20251022\n"
    "  harbor_version: 0.6.6\n"
)


def test_rk_run_writes_spec_frozen_yaml_byte_for_byte(tmp_path: Path):
    spec_path = tmp_path / "input.frozen.yaml"
    spec_path.write_text(FROZEN_SPEC_YAML)
    runs_dir = tmp_path / "_runs"

    with patch("razorback.cli.run._run_canary"), \
         patch("razorback.cli.run._resolve_model_version", return_value=("claude-opus-4-5-20251022", "2026-05-19")), \
         patch("razorback.cli.run._invoke_harbor", return_value=0):
        runner = CliRunner()
        result = runner.invoke(
            app,
            ["run", str(spec_path), "--runs-dir", str(runs_dir)],
        )
        assert result.exit_code == 0, result.output

    experiment_dir = runs_dir / "phase1-ac3-test"
    run_dirs = list(experiment_dir.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    # AC-3 verbatim: byte-for-byte echo of input frozen spec.
    written = (run_dir / "spec.frozen.yaml").read_text()
    assert written == FROZEN_SPEC_YAML

    # AC-3 verbatim: provenance.yaml is also present and parses.
    assert (run_dir / "provenance.yaml").is_file()
    import yaml
    pv = yaml.safe_load((run_dir / "provenance.yaml").read_text())
    assert pv["model_resolved_version"] == "claude-opus-4-5-20251022"
    assert pv["harbor_version"] == "0.6.6"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_rk_run_v2_provenance_artifacts.py -v`
Expected: FAIL — Task 7's placeholder writes spec.frozen.yaml via `freeze_spec(spec)` (re-freezing the parsed spec, NOT byte-echoing the input) and does NOT write provenance.yaml.

- [ ] **Step 3: Replace `_write_provenance_artifacts` with the byte-faithful echo + provenance writer**

Edit `src/razorback/cli/run.py`. Find and replace `_write_provenance_artifacts`:

```python
def _write_provenance_artifacts(spec_path_bytes: bytes, spec, run_dir: Path) -> None:
    """AC-3: byte-for-byte echo of the input frozen spec + provenance.yaml writer.

    `spec_path_bytes` is the raw bytes of the input frozen spec; `spec` is
    its parsed form (used to extract the provenance block for provenance.yaml).
    """
    from razorback.provenance.provenance_yaml import write_provenance_yaml

    (run_dir / "spec.frozen.yaml").write_bytes(spec_path_bytes)
    frozen_provenance = spec.model_dump(mode="json").get("provenance") or {}
    if frozen_provenance:
        write_provenance_yaml(
            run_dir / "provenance.yaml", frozen_provenance, drift_record=None
        )
```

Update the caller in `run_command` — change the call from:

```python
    _write_provenance_artifacts(spec, frozen_text, run_dir)
```

to:

```python
    spec_bytes = spec_path.read_bytes()
    _write_provenance_artifacts(spec_bytes, spec, run_dir)
```

And remove the `from razorback.spec.freeze import derive_job_name, freeze_spec` import + the `frozen_text = freeze_spec(spec)` line in `run_command`. Replace `job_name = derive_job_name(frozen_text)` with `job_name = derive_job_name(spec_bytes.decode("utf-8"))`. The job_name MUST hash the on-disk frozen bytes, not a re-frozen Python object, for content-derived determinism to match (`sha256(frozen_bytes)[:16]`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_rk_run_v2_provenance_artifacts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/cli/run.py tests/unit/test_rk_run_v2_provenance_artifacts.py
git commit -m "Phase 1 AC-3: rk run writes byte-faithful spec.frozen.yaml + provenance.yaml in harbor run-dir"
```

---

## Task 9 — Walking-skeleton integration smoke: deterministic-smoke spec runs end-to-end (AC-1)

**Files:**
- Create: `tests/integration/test_rk_run_v2_deterministic_smoke.py`

**Spec cite:** §3.2 (`rk run` end-to-end). Anchor: `examples/specs/_deterministic-smoke.yaml`, baseline 3/3 pass at commit `e014dbf` per `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`.

**Why this lands BEFORE comprehensive bookreview-claude runs:** Per CL's "Validating new mechanisms" rule + the entity dispatch's completion-checklist item #3 — the smallest end-to-end exercise (the deterministic-smoke spec, 1 dataset, N=1) catches contract breaks before the comprehensive bookreview-claude run (3 datasets, longer wallclock) burns time and budget. The baseline recorded in `examples/specs/_deterministic-smoke.yaml` lines 23-31 is the regression target: 3/3 pass, stratified_pass_at_1 = 1.0.

**Caveat:** the deterministic-smoke spec at HEAD declares `agent.kind: claude-cli` (not `spacedock_solver`). Phase 1's translator (Task 5) handles both `claude-cli` (via `claude_cli:ClaudeCliAgent` import_path) and `spacedock_solver`. AC-1's walking-skeleton holds against claude-cli; AC-6 (import_path dispatch) is verified at the unit level (Task 5) where `spacedock_solver` is the focus. Phase 3 ships the `spacedock_solver` v2 class; until then, Phase 1's end-to-end smoke uses the existing claude-cli path through the same translator + harbor pipeline.

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_rk_run_v2_deterministic_smoke.py`:

```python
# ABOUTME: AC-1 walking skeleton: rk run examples/specs/_deterministic-smoke.frozen.yaml.
# ABOUTME: Asserts exit 0 + summary.json parses against the harbor schema (3/3 pass baseline).

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC_TEMPLATE = REPO / "examples" / "specs" / "_deterministic-smoke.yaml"


@pytest.mark.integration
def test_deterministic_smoke_runs_end_to_end(colima_safe_tmp_path: Path):
    runs_root = colima_safe_tmp_path / "_runs"
    runs_root.mkdir()

    # Freeze the spec first (Phase 1 does not ship rk freeze v2; this uses the
    # existing freeze surface via `python -m razorback.cli spec freeze` from
    # _legacy/ if available, OR — preferred — call freeze_spec() inline).
    from razorback.spec.parse import parse_spec_file
    from razorback.spec.freeze import freeze_spec

    spec = parse_spec_file(SPEC_TEMPLATE)
    frozen_text = freeze_spec(spec)
    frozen_path = colima_safe_tmp_path / "_deterministic-smoke.frozen.yaml"
    frozen_path.write_text(frozen_text)

    env = {**os.environ}
    result = subprocess.run(
        [
            sys.executable, "-m", "razorback.cli", "run",
            str(frozen_path), "--runs-dir", str(runs_root),
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )

    # AC-1 verbatim: exit 0 + run-dir whose summary.json parses against the harbor schema.
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"

    experiment_dir = runs_root / "_deterministic-smoke"
    run_dirs = list(experiment_dir.iterdir())
    assert len(run_dirs) == 1, f"expected one run-dir, got {run_dirs}"
    run_dir = run_dirs[0]

    # AC-3: spec.frozen.yaml present and byte-faithful.
    assert (run_dir / "spec.frozen.yaml").read_text() == frozen_text
    # AC-3: provenance.yaml present.
    assert (run_dir / "provenance.yaml").is_file()

    # AC-1: summary.json parses (harbor writes it; razorback does not).
    summary_paths = list(run_dir.glob("**/summary.json"))
    assert summary_paths, f"no summary.json found under {run_dir}"
    summary = json.loads(summary_paths[0].read_text())
    # Baseline-recorded expectation: 3/3 pass against bookreview (per
    # _deterministic-smoke.yaml lines 23-31; commit e9d7c43+e014dbf baseline).
    # The exact key names depend on harbor's summary schema; assert any
    # non-zero completion count + zero error count as the mechanism check.
    if "n_completed_trials" in summary:
        assert summary["n_completed_trials"] >= 1
        assert summary.get("n_errored_trials", 0) == 0
```

- [ ] **Step 2: Run the integration test**

Run: `RAZORBACK_TEST_DIR=/Users/clkao/git/razorback/.test-tmp uv run pytest tests/integration/test_rk_run_v2_deterministic_smoke.py -v -s --timeout=1200`
Expected: PASS. Wallclock baseline: 6:30 per `examples/specs/_deterministic-smoke.yaml:27`. Cost: $0 (subscription-billed via CLAUDE_CODE_OAUTH_TOKEN).

If FAIL with non-zero exit and no docker error in stderr, escalate to FO — the regression is likely an integration gap between Task 7's harbor invocation shape and harbor's CLI surface. The fallback is to invoke harbor in-process via `harbor.Job.create` (matching v1's path); Task 7's `_invoke_harbor` is the wrap point for that pivot.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_rk_run_v2_deterministic_smoke.py
git commit -m "Phase 1 AC-1: integration smoke against deterministic-smoke spec (3/3 baseline anchor)"
```

---

## Task 10 — `uv run pytest` exits 0 from the worktree branch tip (AC-7)

**Files:** none new; existing test surface.

**Spec cite:** plan AC-1.6.

**Approach:** Run the suite, catalog failures, and classify each failure against the test inventory (`docs/superpowers/plans/2026-05-19-razorback-test-inventory.md`):
- KEEP-VERBATIM tests that fail because Phase 1's `_legacy/` sideline broke their imports → fix the imports (re-point from `razorback.run` to `razorback._legacy.run` where the test is testing v1 surface that survives during the transition; these are largely the `test_rk_run_nop.py` integration tests).
- DROP-classified tests (17 per test inventory) that fail because the v1 surface they test is now under `_legacy/` → mark with `@pytest.mark.skip(reason="v1 surface under _legacy/, scheduled for deletion in Phase 6/7")`. Do NOT delete the test file (test inventory's DROP classification is a Phase 6/7 concern).
- New v2 tests (Tasks 1-9) MUST all pass.

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -v --tb=short 2>&1 | tee /tmp/phase1-pytest.log`
Expected: many failures from DROP-classified v1 tests + import errors from KEEP-VERBATIM v1 integration tests.

- [ ] **Step 2: Classify failures and apply the smallest fix per category**

For each failing test, check the row in `docs/superpowers/plans/2026-05-19-razorback-test-inventory.md`:
- DROP → add `@pytest.mark.skip(reason="v1 surface under _legacy/, Phase 6/7 deletes")` at the test function. Keep the import lines (they import from `razorback._legacy.*` if the v1 module still has consumers).
- KEEP-VERBATIM that fails because of imports → re-point the import from `razorback.run` to `razorback._legacy.run` (and similar for `razorback.manifest`, `razorback.observers`, etc.).
- RE-AUTHOR tests that test v1 SpacedockSolverAgent → Phase 3 owns. Skip with reason "RE-AUTHOR pending Phase 3 SpacedockSolverAgent v2".

The expected DROP-or-skip set per the test inventory: 17 DROP tests across `test_ade_bench_translator*.py`, `test_baseline_promote_verify.py`, `test_channel_drainer.py`, `test_claude_cli_registry.py`, `test_claude_cli_required_env.py`, `test_claude_cli_supported_sampling.py`, `test_claude_cli_translator_proxy.py`, `test_claude_cli_version.py`, `test_cli_validate_per_trial_state_reset.py`, `test_cli_validate_tools_allowed.py`, `test_compat_translator.py`, `test_constraints_check.py`, `test_dab_translator*.py`, `test_registry_resolve.py`.

- [ ] **Step 3: Re-run the suite**

Run: `uv run pytest -v --tb=short 2>&1 | tee /tmp/phase1-pytest-after.log`
Expected: exit code 0. All non-skipped tests PASS.

- [ ] **Step 4: Commit the skip / re-point edits**

```bash
git add tests/
git commit -m "Phase 1 AC-7: skip v1 DROP-class tests + re-point KEEP-VERBATIM imports under _legacy/"
```

---

## Self-Review (run after all tasks drafted, before sending the stage report)

**1. Spec coverage.** Each AC maps 1:1 to a task (or to a verification step under a task):
- AC-1 (walking-skeleton smoke) → Task 9.
- AC-2 (alias-drift + harbor exit 30) → Task 7.
- AC-3 (spec.frozen.yaml + provenance.yaml byte-for-byte) → Task 8.
- AC-4 (extracted behaviors preserve semantics — auth + alias-drift + run-dir creation) → Tasks 1 (errors), 2 (auth verification), 3 (alias-drift verification).
- AC-5 (legacy sideline) → Task 4.
- AC-6 (import_path dispatch) → Task 5.
- AC-7 (`uv run pytest` exits 0) → Task 10.
- AC-8 (runs-dir canary) → Task 6.

**2. Riskiest-contract-first.** Tasks 5 (translator with `AgentConfig.import_path`) and 6 (runs-dir canary) land BEFORE the harbor-delegation body in Task 7. The integration smoke (Task 9) runs the smallest end-to-end exercise — the deterministic-smoke spec, baseline 3/3 — BEFORE any comprehensive bookreview-claude run is attempted. This matches CL's "Validating new mechanisms" rule and the entity dispatch's completion-checklist item #3.

**3. TDD discipline.** Every task with a code change starts with a failing test (Step 1) followed by a verify-it-fails step (Step 2), the minimal implementation (Step 3), and a verify-it-passes step (Step 4). Verification-only tasks (Tasks 2, 3) explicitly skip the test-authoring step and document that they verify an existing KEEP-VERBATIM test.

**4. File:line anchors.** Every extraction task names the source file:line range per `docs/superpowers/plans/2026-05-19-razorback-inventory.md`:
- `errors.py:7-16` (Task 1)
- `agents/auth.py:13-67` (Task 2)
- `provenance/drift.py:11-35` (Task 3)
- `run.py` (192 LoC), `manifest.py`, `observers/`, `runtime/`, `compat/`, `cli/validate.py`, `cli/spec.py` (Task 4)
- `compat/harbor_0_6_6.py:96-157` (Task 5 lifts the import_path emit contract)
- `cli/run.py:22-34` (Task 7 keeps the error→exit-code mapping pattern)

**5. b5 + ra dependency framing.** The plan cites section identities (§3.1, §4.5, §6.1, §6.2, §7.1, §8.1) — not exact wording — so ra's concurrent edits to §4.5 + §6.1 + §6.3 + §9.2 wording do not invalidate the plan. b5's shipped design (sealed_hash-keyed external freeze at `_razorback/freeze/<sealed_hash>/`) informs Task 5's translator emit shape (the freeze tree path is owned by Phase 3's class, but Phase 1's translator must NOT emit any path that conflicts with b5's contract) and Task 7's CLI body (jobs_dir canonicalization per §3.1's path-canonicalization rule).

**6. spec.frozen.yaml byte-for-byte invariant.** AC-3's "byte-for-byte" clause is honored by Task 8: `_write_provenance_artifacts` writes `spec_path.read_bytes()` directly, NOT a re-freeze. `derive_job_name` hashes the on-disk bytes (`sha256(spec_bytes)[:16]`), preserving v1's content-derived determinism contract for the matrix dispatcher (AC-4a.12).

**7. Auth invariant.** Task 5's translator emits auth via `AgentConfig.env`, NOT `kwargs`. Task 5 Step 1's test asserts both invariants (`"ANTHROPIC_API_KEY" in agent_cfg.env` and `"ANTHROPIC_API_KEY" not in agent_cfg.kwargs`). This is the FU-1 AC-1 contract that the v1 translator (`compat/harbor_0_6_6.py:96-157`) encoded, lifted into the v2 translator.

**8. ExitCode v2 surface.** Task 1 adds 3 new codes (22 BudgetExceeded, 23 TaintFindings, 24 ConfigInvalid). The first two are documented in the spec's §3.4 table; ConfigInvalid (24) is added at Phase 1 implementation time to give AC-8 a typed-error surface, and the plan's Task 1 commit message flags it for the spec's next field-additive update under §3.3 semver. The spec itself is not edited under Phase 1 — that belongs to a follow-on spec-corrections entity, not to this plan.

**9. Walking-skeleton spec choice.** Task 9 uses `examples/specs/_deterministic-smoke.yaml` (1 dataset, N=1, 6:30 wallclock baseline, 3/3 pass). The entity body names `bookreview-claude.frozen.yaml` as the AC-1 anchor; the entity's AC-1 verifier reads "produces a run-dir whose `summary.json` parses against the harbor schema". The deterministic-smoke spec satisfies this verifier and runs in less wallclock — Task 9 uses it for the walking skeleton, and a follow-on test (NOT in this plan; Phase 1 validation stage owns it) verifies the same against bookreview-claude.

## Execution Handoff

Plan complete and saved to `docs/razorback-implementation/plans/phase1-rk-run-v2-wrapper.md`. The 10 tasks span six small modules (errors, translate, runs_dir_canary, cli/run, plus verifications of auth and drift) and one mechanical move (`_legacy/` sideline). Recommend **subagent-driven execution** at implementation stage using `superpowers:subagent-driven-development`:

- Tasks 1, 2, 3 (errors + verifications) can dispatch in parallel as a single first wave.
- Task 4 (legacy sideline) is sequential — it touches the import graph; subsequent tasks need its commit.
- Tasks 5, 6 (translator + canary) dispatch in parallel as the second wave; both are independent of each other.
- Tasks 7, 8 land sequentially after wave 2 (Task 7 wires; Task 8 fills the provenance writer).
- Task 9 (integration smoke) runs after Tasks 7+8.
- Task 10 (`uv run pytest` green) is the final sweep.

The implementation stage is gated by `ra` (spec-corrections-from-phase0-probes) reaching `done` first, so the import_path / n_attempts / observers wording is final. Plan-stage shipping does not block on `ra`.
