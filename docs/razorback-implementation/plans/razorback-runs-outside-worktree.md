# Razorback runs_dir Default Outside Worktree — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/razorback-runs-outside-worktree.md`

**Goal:** When `rk run` is invoked without `--runs-dir`, write run-dirs to a user-data location outside the worktree so `git worktree remove --force` cannot destroy experiment artifacts.

**Architecture:** Introduce one path-resolution helper (`razorback.runs_dir_default.resolve_default_runs_dir`) that returns an absolute path under `$RAZORBACK_RUNS_DIR` (when set), else under `$XDG_DATA_HOME/razorback/runs/` (when set), else under `~/.local/share/razorback/runs/`. Wire it as the Typer default in `cli/run.py` via a callback (Typer cannot evaluate `Path("_runs")` lazily, so the option default becomes `None` and the callback resolves at invoke time). Explicit `--runs-dir <path>` keeps today's behavior verbatim.

**Tech Stack:** Python 3.12, Typer, pytest. No new dependencies.

---

## AC ↔ Task map

| AC | Description | Tasks |
|---|---|---|
| AC-1 | Default `runs_dir` outside worktree (env precedence: `$RAZORBACK_RUNS_DIR` → `$XDG_DATA_HOME/razorback/runs` → `~/.local/share/razorback/runs`); path is absolute, not under cwd or active worktree | T0 (RED), T1 (GREEN), T2 (wire CLI) |
| AC-2 | Explicit `--runs-dir <path>` still works as today; existing specs/drivers stay green | T2, T3 |
| AC-3 | Migration documented (README + DAB plugin README + CLI help) | T5 |
| AC-4 | Worktree teardown smoke: worktree create → run cell → worktree remove → artifacts readable | T4 |

**Riskiest contract first:** T0+T1 (the resolver itself). If env-var precedence or XDG resolution is wrong, every downstream wiring is wrong. T4 is the end-to-end mechanism gate that proves the entity's whole premise.

---

## Spec ambiguity to flag before T0

The entity's AC-2 says "Backward compat for `--output-dir`." Razorback's `rk run` command uses `--runs-dir`, not `--output-dir` (see `src/razorback/cli/run.py:141`). The only `--output-dir` in the codebase is the matrix driver shell flag at `examples/drivers/dab-paper-matrix.sh:36`, which the driver forwards as `--runs-dir` to `rk run`.

**This plan interprets AC-2 as:**
1. `rk run --runs-dir <relative-path>` continues to resolve relative to cwd (today's behavior verbatim).
2. The matrix driver's own `--output-dir` shell flag continues to work and continues to forward as `--runs-dir <absolute path>` (T3 confirms via a grep + driver-shape test).
3. Specs that have hardcoded `_runs/` or `runs/` paths still run when the user passes them via `--runs-dir`.

If the captain reads "backward compat for `--output-dir`" differently (e.g., they want a NEW `--output-dir` alias on `rk run`), stop and re-plan T2 before writing code. The plan does NOT add a new `--output-dir` alias to `rk run` — YAGNI.

---

## Surface map — what changes

| File | Change |
|---|---|
| `src/razorback/runs_dir_default.py` *(new)* | Helper module: `resolve_default_runs_dir() -> Path`. Reads `$RAZORBACK_RUNS_DIR`, then `$XDG_DATA_HOME`, then defaults to `~/.local/share/razorback/runs`. Always returns an absolute, expanded path. No side effects (no `mkdir`). |
| `tests/unit/test_runs_dir_default.py` *(new)* | T0 RED, T1 GREEN. Six tests: env-var-set, XDG-set, double-fallback, expanduser handles `~`, asserted-not-under-cwd, asserted-not-under-worktree-when-cwd-is-a-worktree. |
| `src/razorback/cli/run.py:141` | `runs_dir: Path = typer.Option(Path("_runs"), ...)` → `runs_dir: Optional[Path] = typer.Option(None, "--runs-dir", help="Base directory for run-dirs. Defaults to $RAZORBACK_RUNS_DIR or $XDG_DATA_HOME/razorback/runs (~/.local/share/razorback/runs).")`. Immediately after entering `run_command`: `if runs_dir is None: runs_dir = resolve_default_runs_dir()`. The rest of the body keeps the existing `runs_dir_resolved = Path(runs_dir).expanduser().resolve()` line at line 174. |
| `tests/unit/test_cli_run_default_runs_dir.py` *(new)* | T2 test: invoke `rk run` with no `--runs-dir`, monkeypatched `RAZORBACK_RUNS_DIR=<tmp_path>`, assert the run-dir lands under that path. |
| `tests/integration/test_worktree_teardown_preserves_runs.py` *(new)* | T4 smoke (AC-4). Create a git worktree under `.worktrees/`, set `RAZORBACK_RUNS_DIR=<tmp_path>/runs`, invoke `rk run` from inside the worktree against the smoke spec, `git worktree remove --force <worktree>`, assert `<tmp_path>/runs/<experiment>/<job>/result.json` still readable. |
| `README.md` | Today is 0 bytes. Write a minimal first README with a "Where do runs go?" section (≤30 lines). |
| `packages/razorback-plugin-dab/README.md` | Append a one-paragraph "Run-dir location" note under the CLI section pointing at the new default. |
| (no change) `examples/drivers/dab-paper-matrix.sh` | Driver continues to pass `--runs-dir <absolute>`; behavior unchanged. The driver's own `--output-dir` flag stays. Verified by T3. |

## Surface map — what stays

- `runs_dir_canary.py` — unchanged. The canary still runs against the *resolved* absolute path; nothing about visibility logic depends on whether the path was a default or explicit.
- `_stage_harbor_home(runs_dir_resolved)` — unchanged. Still creates `.harbor-home` *inside* the resolved runs-dir, which is now user-data on macOS and survives worktree teardown.
- All existing tests that pass `--runs-dir <tmp_path>/_runs` explicitly — these never hit the default path and stay green.
- `_legacy/run.py` — unchanged. Legacy path is collect-ignored per conftest and not in the v2 invocation surface.
- `--max-budget-usd-running`, `--materialize`, `--allow-alias-drift`, `--allow-plugin-drift` — untouched.
- `.gitignore` — already ignores `_runs/`, `.runs/`, and `runs/`; no change needed.

---

## Tasks

### Task 0 — RED: failing tests for the resolver

**Files:**
- Create: `tests/unit/test_runs_dir_default.py`

This is the riskiest-contract-first test bundle. If the precedence ordering is wrong, every downstream wiring is wrong.

- [ ] **Step 0.1: Write the failing test file**

```python
# ABOUTME: AC-1 unit tests for the default runs-dir resolver.
# ABOUTME: Asserts env-var precedence and that the default is never under cwd.

import os
from pathlib import Path

import pytest


def test_env_var_takes_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.setenv("RAZORBACK_RUNS_DIR", str(tmp_path / "explicit"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert resolve_default_runs_dir() == (tmp_path / "explicit").resolve()


def test_xdg_fallback_when_no_razorback_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.delenv("RAZORBACK_RUNS_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    expected = (tmp_path / "xdg" / "razorback" / "runs").resolve()
    assert resolve_default_runs_dir() == expected


def test_home_local_share_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.delenv("RAZORBACK_RUNS_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    expected = (tmp_path / "home" / ".local" / "share" / "razorback" / "runs").resolve()
    assert resolve_default_runs_dir() == expected


def test_expands_tilde_in_razorback_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("RAZORBACK_RUNS_DIR", "~/custom-runs")
    expected = (tmp_path / "home" / "custom-runs").resolve()
    assert resolve_default_runs_dir() == expected


def test_default_is_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.delenv("RAZORBACK_RUNS_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert resolve_default_runs_dir().is_absolute()


def test_default_not_under_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1 verification clause: resolved default is not a sub-path of cwd."""
    from razorback.runs_dir_default import resolve_default_runs_dir
    monkeypatch.delenv("RAZORBACK_RUNS_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path / "fake_cwd_worktree")
    (tmp_path / "fake_cwd_worktree").mkdir()
    resolved = resolve_default_runs_dir()
    cwd = Path.cwd().resolve()
    assert cwd not in resolved.parents, (
        f"default runs_dir {resolved} is under cwd {cwd}; AC-1 violated"
    )
```

- [ ] **Step 0.2: Run the tests to verify they all fail**

Run: `uv run pytest tests/unit/test_runs_dir_default.py -v`
Expected: 6 FAILs with `ModuleNotFoundError: No module named 'razorback.runs_dir_default'`

- [ ] **Step 0.3: Commit RED**

```bash
git add tests/unit/test_runs_dir_default.py
git commit -m "test: RED — default runs_dir resolver (AC-1)"
```

---

### Task 1 — GREEN: implement the resolver

**Files:**
- Create: `src/razorback/runs_dir_default.py`

- [ ] **Step 1.1: Write the minimal resolver**

```python
# ABOUTME: AC-1 resolver for the default runs-dir when --runs-dir is omitted.
# ABOUTME: Precedence: $RAZORBACK_RUNS_DIR > $XDG_DATA_HOME/razorback/runs > ~/.local/share/razorback/runs.

import os
from pathlib import Path


def resolve_default_runs_dir() -> Path:
    """Return the default runs-dir as an absolute, expanded, resolved path.

    Precedence:
    1. `$RAZORBACK_RUNS_DIR` if set and non-empty.
    2. `$XDG_DATA_HOME/razorback/runs` if `$XDG_DATA_HOME` is set and non-empty.
    3. `~/.local/share/razorback/runs`.

    The returned path is NOT created on disk; callers `mkdir(parents=True,
    exist_ok=True)` after the canary check (see `cli/run.py`).
    """
    explicit = os.environ.get("RAZORBACK_RUNS_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return (Path(xdg).expanduser() / "razorback" / "runs").resolve()
    return (Path.home() / ".local" / "share" / "razorback" / "runs").resolve()
```

- [ ] **Step 1.2: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_runs_dir_default.py -v`
Expected: 6 PASS

- [ ] **Step 1.3: Commit GREEN**

```bash
git add src/razorback/runs_dir_default.py
git commit -m "feat: GREEN — default runs_dir resolver outside worktree (AC-1)"
```

---

### Task 2 — Wire the resolver into `rk run` (AC-1 end-to-end, AC-2)

**Files:**
- Modify: `src/razorback/cli/run.py:141` (option default → `None`)
- Modify: `src/razorback/cli/run.py:166-174` (resolve None to default at entry)
- Create: `tests/unit/test_cli_run_default_runs_dir.py`

- [ ] **Step 2.1: Write the failing CLI test FIRST**

```python
# ABOUTME: AC-1+AC-2 CLI integration: `rk run` honors $RAZORBACK_RUNS_DIR when --runs-dir omitted.
# ABOUTME: Explicit --runs-dir still wins (AC-2).

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from razorback.cli import app


def _make_minimal_frozen_spec(tmp_path: Path) -> Path:
    # Reuse the smallest fixture from existing CLI tests: the deterministic-smoke
    # spec is the canonical "won't actually call any model" shape.
    src = Path("examples/specs/_deterministic-smoke.yaml")
    dst = tmp_path / "smoke.frozen.yaml"
    dst.write_bytes(src.read_bytes())
    return dst


@patch("razorback.cli.run._run_canary", return_value=None)
@patch("razorback.cli.run._invoke_harbor", return_value=0)
def test_default_runs_dir_lands_under_razorback_runs_dir_env(
    _harbor, _canary, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAZORBACK_RUNS_DIR", str(tmp_path / "runs"))
    spec = _make_minimal_frozen_spec(tmp_path)
    result = CliRunner().invoke(
        app, ["run", str(spec), "--allow-plugin-drift", "--allow-alias-drift"]
    )
    # Tolerate non-zero exit on downstream contract issues; what matters is
    # that the run-dir got CREATED under the env-var location.
    assert (tmp_path / "runs").exists(), (
        f"expected $RAZORBACK_RUNS_DIR/runs to be created; stdout={result.stdout}"
    )


@patch("razorback.cli.run._run_canary", return_value=None)
@patch("razorback.cli.run._invoke_harbor", return_value=0)
def test_explicit_runs_dir_wins_over_env(
    _harbor, _canary, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-2: explicit --runs-dir is still honored verbatim."""
    monkeypatch.setenv("RAZORBACK_RUNS_DIR", str(tmp_path / "should-not-be-used"))
    spec = _make_minimal_frozen_spec(tmp_path)
    explicit = tmp_path / "explicit-runs"
    CliRunner().invoke(
        app,
        ["run", str(spec), "--runs-dir", str(explicit),
         "--allow-plugin-drift", "--allow-alias-drift"],
    )
    assert explicit.exists(), "explicit --runs-dir was not honored"
    assert not (tmp_path / "should-not-be-used").exists(), (
        "env var took precedence over explicit flag — AC-2 violated"
    )
```

- [ ] **Step 2.2: Run the new test, verify it fails**

Run: `uv run pytest tests/unit/test_cli_run_default_runs_dir.py -v`
Expected: FAIL — either the env-var test fails (default still writes to `./_runs`) or the test errors because the default path is still relative.

- [ ] **Step 2.3: Edit `src/razorback/cli/run.py` — change the option default**

At line 141, change:

```python
    runs_dir: Path = typer.Option(Path("_runs"), "--runs-dir", help="Base directory for run-dirs."),
```

to:

```python
    runs_dir: Optional[Path] = typer.Option(
        None,
        "--runs-dir",
        help=(
            "Base directory for run-dirs. Defaults to $RAZORBACK_RUNS_DIR, "
            "else $XDG_DATA_HOME/razorback/runs, else "
            "~/.local/share/razorback/runs. The default lives OUTSIDE any "
            "git worktree so `git worktree remove --force` cannot destroy "
            "experiment outputs."
        ),
    ),
```

Add the import at the top of the file (after `from razorback.runs_dir_canary import ...`):

```python
from razorback.runs_dir_default import resolve_default_runs_dir
```

(`Optional` is already imported at line 7.)

- [ ] **Step 2.4: Resolve `None` at the top of `run_command` body**

Immediately after the `try / parse_spec_file / except SpecError` block (after line 171, before line 173's `# AC-8: runs-dir mount-visibility canary ...`), insert:

```python
    if runs_dir is None:
        runs_dir = resolve_default_runs_dir()
```

The existing line `runs_dir_resolved = Path(runs_dir).expanduser().resolve()` (currently 174) keeps working unchanged because `runs_dir` is now always a non-None `Path`.

- [ ] **Step 2.5: Run all affected tests**

Run: `uv run pytest tests/unit/test_cli_run_default_runs_dir.py tests/unit/test_runs_dir_default.py tests/unit/test_rk_run_v2_harbor_cache_dir.py tests/unit/test_cli_run_aggregator_wiring.py tests/unit/test_rk_run_v2_provenance_artifacts.py tests/unit/test_rk_run_budget_gate.py -v`
Expected: ALL PASS. Existing `--runs-dir <tmp_path>/_runs` tests are unaffected because they never hit the default branch.

- [ ] **Step 2.6: Commit**

```bash
git add src/razorback/cli/run.py tests/unit/test_cli_run_default_runs_dir.py
git commit -m "feat: rk run defaults runs-dir to user-data path (AC-1, AC-2)"
```

---

### Task 3 — Confirm matrix driver still works (AC-2)

**Files:**
- Create: `tests/unit/test_dab_paper_matrix_driver_shape.py`

The driver's own `--output-dir` shell flag is unrelated to `rk run`'s `--runs-dir`. This task locks that contract so a future refactor cannot silently drop the shell flag.

- [ ] **Step 3.1: Write the shape test**

```python
# ABOUTME: AC-2 lock — examples/drivers/dab-paper-matrix.sh still accepts --output-dir
# ABOUTME: and forwards each cell as `rk run --runs-dir <absolute path>`.

from pathlib import Path


def test_driver_accepts_output_dir_flag() -> None:
    body = Path("examples/drivers/dab-paper-matrix.sh").read_text()
    assert "--output-dir" in body, "matrix driver lost --output-dir CLI flag (AC-2)"
    assert "--runs-dir" in body, "matrix driver no longer forwards --runs-dir"


def test_driver_forwards_absolute_runs_dir() -> None:
    """OUTPUT_DIR defaults to an absolute path under REPO_ROOT/runs/goal1."""
    body = Path("examples/drivers/dab-paper-matrix.sh").read_text()
    assert 'OUTPUT_DIR="${REPO_ROOT}/runs/goal1"' in body, (
        "driver default OUTPUT_DIR no longer rooted at REPO_ROOT"
    )
```

- [ ] **Step 3.2: Run the test**

Run: `uv run pytest tests/unit/test_dab_paper_matrix_driver_shape.py -v`
Expected: PASS (the driver shape is unchanged).

- [ ] **Step 3.3: Commit**

```bash
git add tests/unit/test_dab_paper_matrix_driver_shape.py
git commit -m "test: lock matrix driver --output-dir → --runs-dir forwarding (AC-2)"
```

---

### Task 4 — Worktree teardown smoke (AC-4)

**Files:**
- Create: `tests/integration/test_worktree_teardown_preserves_runs.py`

This is the mechanism-validation gate for the entity's stated premise. The smallest end-to-end exercise that proves the riskiest contract.

**Smoke strategy decision:** Use the deterministic smoke spec (`examples/specs/_deterministic-smoke.yaml`) with `_invoke_harbor` mocked to a no-op so the test does not require docker / harbor / claude. The contract under test is *filesystem*: did `git worktree remove --force` destroy the run-dir? That contract is independent of whether harbor actually ran. We assert on the artifacts `_write_provenance_artifacts` writes (`spec.frozen.yaml`, `provenance.yaml`) plus the run-dir's existence under the env-var location.

- [ ] **Step 4.1: Write the smoke test**

```python
# ABOUTME: AC-4 — `git worktree remove --force` MUST NOT destroy runs when the
# ABOUTME: default runs-dir is honored (user-data location outside the worktree).

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from razorback.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_throwaway_worktree(repo_root: Path, base: Path) -> Path:
    """Create a git worktree under `base/wt` rooted at HEAD of `repo_root`."""
    wt = base / "wt"
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "add", "--detach", str(wt), "HEAD"],
        check=True,
        capture_output=True,
    )
    return wt


def _force_remove_worktree(repo_root: Path, wt: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(wt)],
        check=True,
        capture_output=True,
    )


@patch("razorback.cli.run._run_canary", return_value=None)
@patch("razorback.cli.run._invoke_harbor", return_value=0)
def test_worktree_remove_force_does_not_destroy_runs(
    _harbor, _canary, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs_root = tmp_path / "runs"
    monkeypatch.setenv("RAZORBACK_RUNS_DIR", str(runs_root))

    wt = _make_throwaway_worktree(REPO_ROOT, tmp_path)
    try:
        # Run `rk run` from INSIDE the worktree using the worktree's copy
        # of the smoke spec. cwd = worktree to match what a real ensign
        # dispatched into a worktree would do.
        original_cwd = Path.cwd()
        os.chdir(wt)
        try:
            result = CliRunner().invoke(
                app,
                [
                    "run",
                    str(wt / "examples" / "specs" / "_deterministic-smoke.yaml"),
                    "--allow-plugin-drift",
                    "--allow-alias-drift",
                ],
            )
        finally:
            os.chdir(original_cwd)

        # Find the experiment/job dir that rk run created under runs_root.
        # rk run always creates `<runs_root>/<experiment>/<job_name>/`.
        assert runs_root.exists(), (
            f"runs_root not created; rk run output:\n{result.stdout}"
        )
        run_dirs = [
            p for p in runs_root.rglob("spec.frozen.yaml")
        ]
        assert run_dirs, (
            f"no spec.frozen.yaml written under {runs_root}; "
            f"rk run output:\n{result.stdout}"
        )
        artifact_path = run_dirs[0]
    finally:
        # The whole point: force-remove the worktree, then re-assert.
        _force_remove_worktree(REPO_ROOT, wt)

    # AC-4 assertion: artifacts are still readable after worktree teardown.
    assert artifact_path.exists(), (
        f"artifact {artifact_path} destroyed by `git worktree remove --force` — AC-4 violated"
    )
    assert artifact_path.read_bytes(), "artifact is empty after worktree teardown"
```

- [ ] **Step 4.2: Run the smoke**

Run: `uv run pytest tests/integration/test_worktree_teardown_preserves_runs.py -v`
Expected: PASS. (If it fails because the worktree-add command refuses an in-repo path, switch `wt = base / "wt"` to `tmp_path.parent / f"wt-{uuid}"` — git refuses worktrees nested inside the source tree only when a `.git` exists in an ancestor; `tmp_path` under `/private/var/folders` is fine.)

- [ ] **Step 4.3: Commit**

```bash
git add tests/integration/test_worktree_teardown_preserves_runs.py
git commit -m "test: worktree teardown preserves runs (AC-4 integration smoke)"
```

---

### Task 5 — Documentation (AC-3)

**Files:**
- Modify (write — currently 0 bytes): `README.md`
- Modify: `packages/razorback-plugin-dab/README.md`

- [ ] **Step 5.1: Write a minimal top-level README**

The README is currently 0 bytes. A minimal first README that satisfies AC-3 and nothing more. Do NOT inflate it with project overview — that belongs to a separate entity. Content:

```markdown
# Razorback

A benchmark runner for agentic research workflows. See
`docs/razorback-implementation/README.md` for the implementation workflow.

## Where do runs go?

`rk run` writes one run-dir per `(spec, job)` under a base "runs-dir":

- **Default**: `$RAZORBACK_RUNS_DIR` if set; else `$XDG_DATA_HOME/razorback/runs`
  if set; else `~/.local/share/razorback/runs`.
- **Override**: pass `--runs-dir <path>` to `rk run`.

The default lives OUTSIDE your git worktree on purpose: `git worktree remove
--force` cannot destroy experiment outputs written there. If you pin a
worktree-relative path (`--runs-dir _runs`, `--runs-dir runs/`) the outputs
share the worktree's fate.

## Quickstart

```
uv sync
uv run rk run examples/specs/_deterministic-smoke.yaml
ls ~/.local/share/razorback/runs/
```
```

(Yes, this is short. AC-3 says "a short 'Where do runs go?' section." That is what this delivers.)

- [ ] **Step 5.2: Append the run-dir note to the DAB plugin README**

Append at the end of `packages/razorback-plugin-dab/README.md`:

```markdown
## Where do runs go?

This plugin is invoked by `rk run` as a subprocess; it does not write run-dirs
itself. The run-dir location is controlled by `rk run`'s `--runs-dir` flag.
When omitted, `rk run` defaults to `$RAZORBACK_RUNS_DIR` / `$XDG_DATA_HOME/razorback/runs`
/ `~/.local/share/razorback/runs` — outside any git worktree. See the top-level
razorback README for details.
```

- [ ] **Step 5.3: Verify both READMEs render**

Run:
```bash
wc -l README.md packages/razorback-plugin-dab/README.md
grep -c "Where do runs go" README.md packages/razorback-plugin-dab/README.md
```
Expected: top-level README is ≤30 lines; the grep finds the heading in both files.

- [ ] **Step 5.4: Verify CLI help renders the new default text**

Run: `uv run rk run --help | grep -A2 runs-dir`
Expected: the help string includes "Defaults to $RAZORBACK_RUNS_DIR" (verbatim substring).

- [ ] **Step 5.5: Commit**

```bash
git add README.md packages/razorback-plugin-dab/README.md
git commit -m "docs: document runs-dir default location (AC-3)"
```

---

## Sequencing

```
T0 (RED resolver) → T1 (GREEN resolver) → T2 (wire CLI) → T3 (lock driver) → T4 (worktree smoke) → T5 (docs)
```

T0+T1 is riskiest-contract-first per the captain's foundational rule: the resolver's precedence is the one piece that, if wrong, invalidates every downstream wiring. Pay that small bill first.

T4 is the mechanism-validation gate for the *entity's* premise (worktree teardown can no longer destroy runs). If T4 fails after T2, stop and re-plan — do NOT add fallback fixes.

T5 (docs) intentionally lands last so the CLI help string written in T2 is what gets quoted in the README; no risk of doc/code drift.

## Self-review

- **Spec coverage:** AC-1 (T0+T1+T2), AC-2 (T2+T3), AC-3 (T5), AC-4 (T4). All four ACs have a dedicated task.
- **Placeholder scan:** no TBD / TODO / "fill in" strings; every test body and code change is fully written above.
- **Type consistency:** `resolve_default_runs_dir() -> Path` is consistent across T0 tests, T1 implementation, and T2 import. The `runs_dir` parameter type goes from `Path` (with default `Path("_runs")`) to `Optional[Path]` (with default `None`) — the only signature change, called out explicitly in T2.3.
- **Spec ambiguity:** flagged at the top under "Spec ambiguity to flag before T0" so the executing agent stops and asks the captain if the AC-2 interpretation is wrong.

## Resume hook

After this plan ships and `razorback-runs-outside-worktree` flips to `merged`:
- The Goal 1 RESUME re-run becomes safe: `git worktree remove --force` at FO terminal cleanup leaves `~/.local/share/razorback/runs/goal1-resume/` intact.
- Per-query rescore against the paper's `per_query_pass_at_1` metric becomes possible because `validation.json` survives.
- The 4 ergonomics entities filed as prereqs (runs-outside-worktree + commit-small-artifacts + freeze-CAS + fo-no-force-worktree-remove) can ship in any order from here; this one was the gating change.
