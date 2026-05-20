# PKG-1 v2 — rk runs list/show Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the two read-side `rk runs` subcommands that survive v2 reconciliation: `rk runs list [--root <dir>] [--experiment <name>]` enumerates run-dirs under a base path with headline metadata, and `rk runs show <run-dir>` emits a single run-dir's summary plus a manifest envelope. JSON-only output, semver-stable field set, ExitCode.USAGE (2) on missing/malformed input.

**Architecture:** Filesystem read-only. Both commands walk the harbor run-dir layout (`<root>/<experiment>/<job-name>/`) and read razorback-owned + harbor-owned artifacts (`manifest.json`, `summary.json`). No harbor types on the CLI surface; razorback owns the wire shapes. Both commands attach to the existing `runs_app` Typer sub-app at `src/razorback/cli/runs.py` next to the already-shipped `rk runs diff` command. The run-dir discovery + parsing primitives live in a new module `src/razorback/runs/inspect.py` so the CLI body stays a thin Typer-to-JSON adapter. The module is independent of phase1 (`rk run`): it reads run-dirs that phase1 produces but does not import phase1 code. Safe to plan and implement in parallel with phase1.

**Tech Stack:** Python 3.12, Typer (CLI), pytest (tests), pathlib + json stdlib only (no new deps). Fixture run-dirs synthesized in `tmp_path` for unit tests; one acceptance pass against a real run-dir under `.runs/baseline-rerun-20260520-bookreview/`.

**Spec source of truth:** `/Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`. Governing sections: §3.2 (subcommand surface: `rk runs list` + `rk runs show`), §3.3 (semver promise — JSON keys are additive, never renamed/removed within a major version), §3.4 (ExitCode table — USAGE=2 for missing input), §7.1 (run-dir layout — what artifacts to read).

**Riskiest contract first.** The on-disk shape of `manifest.json` + `summary.json` is the load-bearing contract. Task 1 pins fixtures that mirror the real artifacts at `.runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/<job>/` (inspected at plan time — see "Run-dir artifact inventory" below). Task 2 (`runs/inspect.py` primitives) lands against those fixtures before any Typer wiring, so a wire-shape change is caught by a unit test, not a CLI integration failure.

**Run-dir artifact inventory (observed at plan time, commit `a2e9c49`):**

A run-dir at `<root>/<experiment>/<job-name>/` contains, among others:
- `manifest.json` — razorback envelope. Fields observed: `run_dir_version` (int), `experiment` (str), `job_name` (str), `created_at` (ISO-8601 UTC str), `benchmark_kind` (str).
- `summary.json` — razorback summary. Fields observed: `summary_version` (int), `stratified_pass_at_1` (float), `datasets` (dict-of-per-dataset breakdowns).
- Other harbor-owned files (`config.json`, `lock.json`, `events.jsonl`, per-trial subdirs, etc.) — out of scope for `rk runs list/show`; ignored.

**Out of scope (per entity body):**
- `rk runs list --format human` table output (§3.1 names JSON as default; defer until a consumer asks).
- `rk validate` subcommand (drops out under v2; spec validation happens inside `rk freeze`).
- The broader workflow-infra wrapper from original PKG-1 (spacedock first-officer machinery owns it under v2).
- Deferral to `harbor job list` / `harbor job show` (conditional on harbor shipping those; revisit then).
- `rk runs cost` — spec §3.2 names it in the first-ship surface, but the entity explicitly scopes only `list` + `show`. Cost is its own PKG-11 entity.

---

## AC ↔ task map

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 (`rk runs list` enumerates run-dirs; `--experiment` filter; `--root` override) | §3.2 (`rk runs list` description) + §7.1 (layout) | Task 1 (fixture builder), Task 2 (`runs/inspect.py` primitives), Task 3 (`rk runs list` Typer command) |
| AC-2 (`rk runs show` emits manifest envelope + summary) | §3.2 (`rk runs show` description) + §7.1 (layout) | Task 1, Task 2, Task 4 (`rk runs show` Typer command) |
| AC-3 (`rk runs show` exits USAGE=2 on missing input) | §3.4 exit-code table (row 2) | Task 5 (error path: USAGE on missing run-dir / missing files) |
| AC-4 (JSON key stability snapshot) | §3.3 semver promise | Task 6 (snapshot test per subcommand) |
| (Coverage) AC-1 + AC-2 acceptance command against real run-dir | (entity Test plan, "Acceptance command") | Task 7 (acceptance pass under `.runs/baseline-rerun-20260520-bookreview/`) |

---

## Task 1 — Fixture builder for synthetic run-dirs (AC-1, AC-2, AC-3, AC-4 prerequisite)

**Files:**
- Add: `tests/unit/conftest.py` (extend if it exists; otherwise create) with a `make_run_dir(tmp_path, *, root, experiment, job_name, manifest_overrides=None, summary_overrides=None, omit=None)` factory.

**Spec cite:** §7.1 layout (the two razorback-owned artifacts `manifest.json` and `summary.json` plus the `<root>/<experiment>/<job>/` directory shape).

- [ ] **Step 1: Write the failing test that the factory exists and produces the expected layout**

Open `tests/unit/test_runs_inspect_fixture.py` (new file) and write:

```python
from pathlib import Path

from tests.unit.conftest import make_run_dir  # ignore the editor's complaint; conftest exposes via fixture too


def test_make_run_dir_writes_manifest_and_summary(tmp_path: Path):
    run_dir = make_run_dir(
        tmp_path,
        root="runs",
        experiment="exp-a",
        job_name="abcd1234",
    )
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "summary.json").exists()
    assert run_dir.parent.name == "exp-a"
    assert run_dir.parent.parent.name == "runs"


def test_make_run_dir_omit_skips_artifact(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j", omit=("summary.json",))
    assert (run_dir / "manifest.json").exists()
    assert not (run_dir / "summary.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_inspect_fixture.py -v`
Expected: FAIL with `ImportError` for `make_run_dir`.

- [ ] **Step 3: Implement `make_run_dir` in `tests/unit/conftest.py`**

Signature: `make_run_dir(tmp_path, *, root, experiment, job_name, manifest_overrides=None, summary_overrides=None, omit=None) -> Path`. Default manifest mirrors the observed shape (`run_dir_version=1`, the four other fields with deterministic defaults). Default summary mirrors `summary_version=1, stratified_pass_at_1=1.0, datasets={"bookreview": {...}}`. `omit` is a tuple of filenames to skip writing. Returns the run-dir path.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_runs_inspect_fixture.py -v`
Expected: 2/2 pass.

- [ ] **Step 5: Commit**

Commit message: `pkg1-v2 t1: test fixture for synthetic run-dirs`.

---

## Task 2 — `src/razorback/runs/inspect.py` primitives (AC-1, AC-2 core)

**Files:**
- Add: `src/razorback/runs/__init__.py` (empty, package marker).
- Add: `src/razorback/runs/inspect.py` with two pure functions: `list_run_dirs(root: Path, *, experiment: str | None = None) -> list[dict]` and `read_run_dir(run_dir: Path) -> dict`.
- Add: `tests/unit/test_runs_inspect.py`.

**Spec cite:** §3.2 (subcommand descriptions: list returns paths, timestamps, and headline scores; show returns the summary), §7.1 (layout).

**Wire shapes (razorback-owned, semver-stable under §3.3):**

`list_run_dirs(root, experiment=None)` returns a list of dicts, each with keys:
- `path` (str, absolute) — the run-dir path.
- `experiment` (str) — from `manifest.json["experiment"]`.
- `job_name` (str) — from `manifest.json["job_name"]`.
- `created_at` (str, ISO-8601 UTC) — from `manifest.json["created_at"]`.
- `run_dir_version` (int) — from `manifest.json["run_dir_version"]`.
- `stratified_pass_at_1` (float | null) — from `summary.json["stratified_pass_at_1"]`; null if summary is missing or unparseable.

Sort by `(experiment, job_name)` ascending for deterministic output.

`read_run_dir(run_dir)` returns a dict with keys:
- `manifest` — the entire `manifest.json` payload (verbatim dict).
- `summary` — the entire `summary.json` payload (verbatim dict).
- `path` (str, absolute).

Raises `FileNotFoundError` if either `manifest.json` or `summary.json` is missing or if the run-dir does not exist. The CLI layer (Task 5) maps this to ExitCode.USAGE.

- [ ] **Step 1: Write the failing tests for `list_run_dirs`**

`tests/unit/test_runs_inspect.py`:

```python
from pathlib import Path

from razorback.runs.inspect import list_run_dirs, read_run_dir
from tests.unit.conftest import make_run_dir


def test_list_run_dirs_returns_all_under_root(tmp_path: Path):
    root = tmp_path / "runs"
    make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    make_run_dir(tmp_path, root="runs", experiment="exp-b", job_name="j2")
    entries = list_run_dirs(root)
    assert len(entries) == 2
    assert {e["experiment"] for e in entries} == {"exp-a", "exp-b"}


def test_list_run_dirs_filters_by_experiment(tmp_path: Path):
    root = tmp_path / "runs"
    make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    make_run_dir(tmp_path, root="runs", experiment="exp-b", job_name="j2")
    entries = list_run_dirs(root, experiment="exp-a")
    assert len(entries) == 1
    assert entries[0]["experiment"] == "exp-a"


def test_list_run_dirs_emits_required_keys(tmp_path: Path):
    root = tmp_path / "runs"
    make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    entries = list_run_dirs(root)
    required = {"path", "experiment", "job_name", "created_at", "run_dir_version", "stratified_pass_at_1"}
    assert required.issubset(entries[0])


def test_list_run_dirs_handles_missing_summary(tmp_path: Path):
    root = tmp_path / "runs"
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j", omit=("summary.json",))
    entries = list_run_dirs(root)
    assert entries[0]["stratified_pass_at_1"] is None


def test_list_run_dirs_empty_root(tmp_path: Path):
    root = tmp_path / "runs"
    root.mkdir()
    assert list_run_dirs(root) == []


def test_list_run_dirs_root_override(tmp_path: Path):
    make_run_dir(tmp_path, root="runs-a", experiment="exp", job_name="j")
    make_run_dir(tmp_path, root="runs-b", experiment="exp", job_name="j")
    assert len(list_run_dirs(tmp_path / "runs-a")) == 1
    assert len(list_run_dirs(tmp_path / "runs-b")) == 1


def test_read_run_dir_returns_manifest_and_summary(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j")
    payload = read_run_dir(run_dir)
    assert payload["manifest"]["experiment"] == "exp"
    assert payload["summary"]["summary_version"] == 1
    assert payload["path"] == str(run_dir)


def test_read_run_dir_raises_on_missing_run_dir(tmp_path: Path):
    import pytest
    with pytest.raises(FileNotFoundError):
        read_run_dir(tmp_path / "does-not-exist")


def test_read_run_dir_raises_on_missing_manifest(tmp_path: Path):
    import pytest
    run_dir = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j", omit=("manifest.json",))
    with pytest.raises(FileNotFoundError):
        read_run_dir(run_dir)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_runs_inspect.py -v`
Expected: 9/9 FAIL with `ImportError: cannot import name 'list_run_dirs' from 'razorback.runs.inspect'`.

- [ ] **Step 3: Implement `src/razorback/runs/__init__.py` (empty) and `src/razorback/runs/inspect.py`**

Both files start with two-line ABOUTME comments per CL's rule. `list_run_dirs` walks `root.iterdir()` (each is an experiment), then each experiment dir's `.iterdir()` (each is a run-dir), then reads `manifest.json` (skip the run-dir if missing — only show valid razorback run-dirs) and optionally `summary.json` (tolerate missing). `read_run_dir` raises `FileNotFoundError` if the run-dir does not exist, if `manifest.json` is missing, or if `summary.json` is missing.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_runs_inspect.py -v`
Expected: 9/9 pass.

- [ ] **Step 5: Commit**

Commit message: `pkg1-v2 t2: runs.inspect primitives (list_run_dirs, read_run_dir)`.

---

## Task 3 — `rk runs list` Typer command (AC-1)

**Files:**
- Modify: `src/razorback/cli/runs.py` (extend the existing `runs_app` Typer sub-app).
- Add: `tests/unit/test_runs_list.py`.

**Spec cite:** §3.2 `rk runs list [--root <dir>] [--experiment <name>]`.

- [ ] **Step 1: Write the failing test using the Typer test client**

`tests/unit/test_runs_list.py`:

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir


def test_runs_list_emits_json_for_all_run_dirs(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    make_run_dir(tmp_path, root="runs", experiment="exp-b", job_name="j2")
    result = CliRunner().invoke(app, ["runs", "list", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload) == 2


def test_runs_list_filters_by_experiment(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    make_run_dir(tmp_path, root="runs", experiment="exp-b", job_name="j2")
    result = CliRunner().invoke(
        app, ["runs", "list", "--root", str(tmp_path / "runs"), "--experiment", "exp-a"]
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert len(payload) == 1
    assert payload[0]["experiment"] == "exp-a"


def test_runs_list_empty_root_emits_empty_array(tmp_path: Path):
    (tmp_path / "runs").mkdir()
    result = CliRunner().invoke(app, ["runs", "list", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_list.py -v`
Expected: 3/3 FAIL — Typer reports unknown command `runs list`.

- [ ] **Step 3: Implement the `list` subcommand under `runs_app` in `src/razorback/cli/runs.py`**

```python
@runs_app.command("list")
def list_command(
    root: Path = typer.Option(Path(".runs"), "--root", exists=True, file_okay=False, dir_okay=True),
    experiment: str | None = typer.Option(None, "--experiment"),
) -> None:
    """List razorback run-dirs under <root>. §3.2."""
    entries = list_run_dirs(root, experiment=experiment)
    typer.echo(json.dumps(entries, indent=2))
```

Import `list_run_dirs` from `razorback.runs.inspect`. Default `--root` to `Path(".runs")` to match the project's runs root.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_runs_list.py -v`
Expected: 3/3 pass.

- [ ] **Step 5: Commit**

Commit message: `pkg1-v2 t3: rk runs list typer command`.

---

## Task 4 — `rk runs show` Typer command (AC-2)

**Files:**
- Modify: `src/razorback/cli/runs.py`.
- Add: `tests/unit/test_runs_show.py`.

**Spec cite:** §3.2 `rk runs show <run-dir>`.

**Wire shape (razorback-owned, semver-stable under §3.3):**

Output is a single JSON object with keys:
- `manifest` (object) — the run-dir's `manifest.json` payload verbatim. Contains the envelope fields (`run_dir_version`, `experiment`, `job_name`, `created_at`, `benchmark_kind`).
- `summary` (object) — the run-dir's `summary.json` payload verbatim.
- `path` (str) — the absolute run-dir path.

The entity body says "manifest envelope (experiment label, run-dir path, run-dir-format version, created_at)". That envelope is realized as the `manifest` key (whose JSON content already carries `experiment`, `run_dir_version`, `created_at`) plus the top-level `path` key. No wrapping/renaming — surface the manifest verbatim so razorback does not have to bump its own version when harbor extends `manifest.json` with new fields.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_runs_show.py`:

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir


def test_runs_show_emits_manifest_and_summary(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="exp-a", job_name="j1")
    result = CliRunner().invoke(app, ["runs", "show", str(run_dir)])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["manifest"]["experiment"] == "exp-a"
    assert payload["manifest"]["run_dir_version"] == 1
    assert "created_at" in payload["manifest"]
    assert payload["summary"]["summary_version"] == 1
    assert payload["path"] == str(run_dir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_runs_show.py -v`
Expected: FAIL — Typer reports unknown command `runs show`.

- [ ] **Step 3: Implement the `show` subcommand under `runs_app`**

```python
@runs_app.command("show")
def show_command(
    run_dir: Path = typer.Argument(...),
) -> None:
    """Show one run-dir's manifest envelope + summary. §3.2."""
    try:
        payload = read_run_dir(run_dir)
    except FileNotFoundError as exc:
        typer.echo(f"run-dir missing required input: {exc}", err=True)
        raise typer.Exit(ExitCode.USAGE)
    typer.echo(json.dumps(payload, indent=2))
```

Import `read_run_dir` and `ExitCode`. Note: do NOT set `exists=True` on the `Argument` — Task 5's missing-path test exercises the explicit `FileNotFoundError` → ExitCode.USAGE mapping; letting Typer reject the argument early would short-circuit that path with its own error code.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_runs_show.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

Commit message: `pkg1-v2 t4: rk runs show typer command`.

---

## Task 5 — `rk runs show` ExitCode.USAGE on missing input (AC-3)

**Files:**
- Modify: `tests/unit/test_runs_show.py`.

**Spec cite:** §3.4 exit-code table row 2 (`USAGE`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_runs_show.py`:

```python
def test_runs_show_exits_usage_on_missing_run_dir(tmp_path: Path):
    result = CliRunner().invoke(app, ["runs", "show", str(tmp_path / "does-not-exist")])
    assert result.exit_code == 2
    assert "does-not-exist" in result.stderr or "does-not-exist" in result.stdout


def test_runs_show_exits_usage_on_missing_summary(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j", omit=("summary.json",))
    result = CliRunner().invoke(app, ["runs", "show", str(run_dir)])
    assert result.exit_code == 2


def test_runs_show_exits_usage_on_missing_manifest(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j", omit=("manifest.json",))
    result = CliRunner().invoke(app, ["runs", "show", str(run_dir)])
    assert result.exit_code == 2
```

Use `CliRunner(mix_stderr=False)` for the first test if stderr capture is needed for the message assertion.

- [ ] **Step 2: Run to verify**

Run: `uv run pytest tests/unit/test_runs_show.py -v`
Expected: 4/4 pass (the three new + the AC-2 happy-path test). Task 4's implementation already wires the USAGE exit; this task is a coverage backfill that pins the behavior.

- [ ] **Step 3: Commit**

Commit message: `pkg1-v2 t5: rk runs show USAGE exit on missing input`.

---

## Task 6 — JSON key-stability snapshot (AC-4)

**Files:**
- Add: `tests/unit/test_runs_json_stability.py`.

**Spec cite:** §3.3 (semver promise — JSON fields are additive within a major version; no rename or removal).

- [ ] **Step 1: Write the snapshot test**

`tests/unit/test_runs_json_stability.py`:

```python
import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.cli import app
from tests.unit.conftest import make_run_dir

LIST_KEYS = {"path", "experiment", "job_name", "created_at", "run_dir_version", "stratified_pass_at_1"}
SHOW_KEYS = {"manifest", "summary", "path"}


def test_runs_list_json_keys_stable(tmp_path: Path):
    make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j")
    result = CliRunner().invoke(app, ["runs", "list", "--root", str(tmp_path / "runs")])
    assert result.exit_code == 0
    entries = json.loads(result.stdout)
    assert set(entries[0]) == LIST_KEYS, (
        f"runs list field set changed (semver violation under §3.3). "
        f"Got: {set(entries[0])}. Expected: {LIST_KEYS}. "
        f"Adding fields requires extending LIST_KEYS; removing/renaming requires a major-version bump."
    )


def test_runs_show_json_keys_stable(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, root="runs", experiment="exp", job_name="j")
    result = CliRunner().invoke(app, ["runs", "show", str(run_dir)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload) == SHOW_KEYS, (
        f"runs show field set changed (semver violation under §3.3). "
        f"Got: {set(payload)}. Expected: {SHOW_KEYS}."
    )
```

The snapshot is exact-set; future additive fields require extending the constants in the same commit that adds them, which is the §3.3-correct gesture (the CI fails until both sides land together).

- [ ] **Step 2: Run to verify**

Run: `uv run pytest tests/unit/test_runs_json_stability.py -v`
Expected: 2/2 pass.

- [ ] **Step 3: Commit**

Commit message: `pkg1-v2 t6: JSON key stability snapshot per §3.3`.

---

## Task 7 — Acceptance pass against a real run-dir

**Files:** none (read-only acceptance command).

**Spec cite:** entity Test plan, "Acceptance command".

- [ ] **Step 1: `rk runs list` against `.runs/baseline-rerun-20260520-bookreview/`**

Run from the repo root:

```
uv run rk runs list --root .runs/baseline-rerun-20260520-bookreview
```

Expected: exits 0; emits a JSON array; at least one entry with `experiment == "m3-bookreview-claude"`.

- [ ] **Step 2: `rk runs list --experiment m3-bookreview-claude`**

```
uv run rk runs list --root .runs/baseline-rerun-20260520-bookreview --experiment m3-bookreview-claude
```

Expected: exits 0; entries are a non-empty subset of step 1's output, all with `experiment == "m3-bookreview-claude"`.

- [ ] **Step 3: `rk runs show` against the bookreview run-dir**

```
uv run rk runs show .runs/baseline-rerun-20260520-bookreview/m3-bookreview-claude/b62c780119d24d68
```

Expected: exits 0; emits a JSON object with `manifest.experiment == "m3-bookreview-claude"`, `manifest.run_dir_version == 1`, and `summary.stratified_pass_at_1 == 1.0`.

- [ ] **Step 4: `rk runs show` against a nonexistent path**

```
uv run rk runs show .runs/does-not-exist
```

Expected: exits 2; stderr names the missing input.

- [ ] **Step 5: Record results in the validation report**

Capture stdout of steps 1-3 (head of array; full object for show) and exit codes for steps 1-4. These go in the entity's `validation` stage report, not the `plan` stage report.

---

## Done-when checklist

- All 9 unit tests pass: 2 (fixture) + 9 (inspect primitives) + 3 (list) + 4 (show happy + 3 USAGE) + 2 (snapshot) = 20 new tests.
- Acceptance pass: all 4 steps in Task 7 produce the expected exit codes.
- `uv run pytest` exits 0 from a clean checkout (regression guard against unrelated breakage).
- Each task commits before the next begins; commit messages follow the `pkg1-v2 tN:` prefix.
