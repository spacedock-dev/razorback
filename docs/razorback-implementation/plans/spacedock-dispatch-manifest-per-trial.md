# Spacedock Dispatch Manifests Per Trial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve Spacedock first-officer dispatch provenance independently for every Harbor trial in parallel `spacedock_solver` runs.

**Architecture:** Keep the existing `razorback.agents.subagent_traces` manifest writer, but make its target a trial directory instead of the run/job root. Audit then enumerates Spacedock trials from `manifest.json` and fails strict policy when any listed trial lacks its own dispatch manifest. Smoke validation accepts the new per-trial layout while retaining the legacy single-trial root-manifest fallback.

**Tech Stack:** Python 3.12, pytest, Typer `CliRunner`, existing Harbor trial-directory layout, existing Razorback run artifacts.

---

## AC - Task Map

| AC | Required behavior | Tasks |
|---|---|---|
| AC-1 | Full parallel runs emit one dispatch manifest per trial; each manifest names the trial, prompt mode, worker dispatches, and trace artifact paths | T1, T2 |
| AC-2 | Job-level provenance no longer overwrites trial provenance | T1, T2 |
| AC-3 | `rk audit --policy strict` fails closed when a run manifest lists a Spacedock trial without a per-trial dispatch manifest | T5, T6 |
| AC-4 | Single-trial smoke and legacy layouts remain readable; score output is not changed | T3, T4, T7 |

## Spec Cites

- `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §3.2: `rk audit --policy strict` is the post-hoc trajectory scanner and exits non-zero on non-clean trials.
- Spec §4.3 and §8.4: `SpacedockSolverAgent` owns runtime adaptation and is the right place to emit dispatch evidence after the inner runtime writes its JSONL trace.
- Spec §7.1: `manifest.json` lists per-trial paths in the run-dir contract; this task uses that public run artifact for audit enumeration.
- Spec §9.4: Layer 3 post-hoc audit must inspect parent traces and subagent trace manifests, and strict matrix dispatch depends on this before score readout.
- `docs/agent-run-architecture.md` "Desired state": parallel full-dataset runs retain one dispatch manifest per trial rather than a collapsed job-level manifest.

## Surface Map

| File | Change |
|---|---|
| `src/razorback/agents/subagent_traces.py` | Add manifest metadata fields: `trial.trial_id`, `prompt_mode`, and `trace_artifacts[]` with paths relative to the trial directory. Preserve the existing `dispatches[].subagent_type` worker identity field. |
| `src/razorback/agents/spacedock_solver.py` | Change `_maybe_write_subagent_trace_manifest()` to pass the trial directory (`Path(self.logs_dir).resolve().parent`) instead of the run/job root (`parents[1]`). Pass prompt mode based on runtime: `spacedock-claude-first-officer` or `spacedock-codex-first-officer`. |
| `src/razorback/agents/subagent_smoke.py` | Accept either a trial directory or a run directory. For a run directory, validate all listed Spacedock trial manifests; retain the legacy single-trial root `subagent-trace-manifest.json` fallback only when exactly one trial is listed. |
| `src/razorback/audit/dispatch_manifests.py` | New focused audit helper: load Spacedock trial inventory from `manifest.json` + `spec.frozen.yaml`, read per-trial dispatch manifests, and emit `trace_coverage` findings for missing, malformed, or zero-capture dispatch coverage. |
| `src/razorback/audit/cli.py` | Seed audit roots from Spacedock `manifest.json.per_trial_paths` and append dispatch-manifest findings for each trial before reducing status. |
| `tests/integration/test_spacedock_cleanup_writes_trace_manifest.py` | Update expectations from run-root manifest to per-trial manifests; add two-trial parallel fixture that fails with the current overwrite behavior. |
| `tests/unit/test_subagent_traces_writer.py` | Assert the additive manifest metadata fields and relative trace artifact paths. |
| `tests/unit/test_subagent_smoke_validator.py` | Cover run-dir validation, per-trial validation, and legacy single-trial root-manifest compatibility. |
| `tests/integration/test_dab_paper_matrix_spacedock_gate.py` | Update prose/static assertions so the matrix smoke gate still points at the run dir and the validator handles per-trial manifests internally. |
| `tests/unit/audit/conftest.py` and `tests/unit/audit/test_rk_audit_cli.py` | Add strict-audit fixtures for two Spacedock trials where one manifest is missing, both manifests are present, and the legacy single-trial root layout is present. |

## Decisions

- Do not retain a job-level dispatch manifest. The root `subagent-trace-manifest.json` is the current collapse point; the implementation should stop writing it for new multi-trial runs.
- Keep the manifest schema version `razorback-subagent-traces-v1` and add fields additively. Existing consumers that read `captured` and `dispatches` keep working.
- The trial manifest is written by `SpacedockSolverAgent.run()` while Harbor still exposes the pre-relocation layout `<run-dir>/<trial-name>/agent/`. Passing the trial directory still works after relocation because `write_subagent_trace_manifest()` already searches both direct `agent/` and `steps/*/agent/` logs.
- `rk score`, `summary.json`, `per_trial_outcomes.json`, and full ADE/DAB score relaunches are out of scope. This task affects provenance and audit discovery only.

## Tasks

### T1 - RED: Parallel Trial Writer Fixture

**Files:**
- Modify: `tests/integration/test_spacedock_cleanup_writes_trace_manifest.py`
- Modify: `tests/unit/test_subagent_traces_writer.py`

- [ ] **Step 1: Add a two-trial parallel writer test**

Add a test named `test_parallel_spacedock_runs_write_distinct_trial_manifests`. Build this layout:

```text
<tmp>/run/
  trial-a__aaaa/agent/claude-code.txt
  trial-b__bbbb/agent/claude-code.txt
```

Use the existing `_FakeInnerAgent`, but give each trial a distinct `tool_use_id` and prompt. Run two `SpacedockSolverAgent.run(...)` calls through `asyncio.gather`.

Expected assertions:

```python
assert not (run_dir / "subagent-trace-manifest.json").exists()
for trial_name in ("trial-a__aaaa", "trial-b__bbbb"):
    manifest_path = run_dir / trial_name / "subagent-trace-manifest.json"
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text())
    assert payload["trial"]["trial_id"] == trial_name
    assert payload["prompt_mode"] == "spacedock-claude-first-officer"
    assert payload["trace_artifacts"][0]["path"] == "agent/claude-code.txt"
    assert payload["captured"] == 1
```

- [ ] **Step 2: Update single-run writer expectations**

Change existing assertions in `test_run_writes_manifest_adjacent_to_provenance`, `test_run_for_codex_runtime_writes_manifest`, and `test_run_writes_manifest_when_inner_agent_raises` so they expect:

```python
manifest_path = logs_dir.parent / "subagent-trace-manifest.json"
assert not (cell_run_dir / "subagent-trace-manifest.json").exists()
```

- [ ] **Step 3: Extend unit writer assertions**

In `tests/unit/test_subagent_traces_writer.py`, assert the additive fields for both Claude and Codex fixtures:

```python
assert manifest["trial"]["trial_id"] == "cell"
assert manifest["prompt_mode"] is None
assert manifest["trace_artifacts"][0]["kind"] == "parent_log"
assert manifest["trace_artifacts"][0]["path"] == "steps/main/agent/claude-code.txt"
```

- [ ] **Step 4: Run RED tests**

Run:

```bash
uv run pytest tests/integration/test_spacedock_cleanup_writes_trace_manifest.py tests/unit/test_subagent_traces_writer.py -x -v
```

Expected: fail because the current hook writes `run/subagent-trace-manifest.json` and the manifest lacks `trial`, `prompt_mode`, and `trace_artifacts`.

**Spec cites:** §4.3, §8.4, §9.4; AC-1, AC-2.

### T2 - GREEN: Trial-Scoped Manifest Writer

**Files:**
- Modify: `src/razorback/agents/subagent_traces.py`
- Modify: `src/razorback/agents/spacedock_solver.py`

- [ ] **Step 1: Add writer metadata parameters**

Change the writer signature to:

```python
def write_subagent_trace_manifest(
    trial_dir: Path,
    *,
    prompt_mode: str | None = None,
) -> dict[str, Any]:
```

Inside `_find_runtime_log`, continue returning `(txt_path, runtime)`. Add a helper:

```python
def _relative_trace_artifact(path: Path, trial_dir: Path, runtime: str) -> dict[str, str]:
    return {
        "kind": "parent_log",
        "runtime": runtime,
        "path": path.relative_to(trial_dir).as_posix(),
    }
```

Populate:

```python
"trial": {"trial_id": trial_dir.name},
"prompt_mode": prompt_mode,
"trace_artifacts": [_relative_trace_artifact(txt_path, trial_dir, runtime)],
```

- [ ] **Step 2: Move the hook target to the trial directory**

In `_maybe_write_subagent_trace_manifest()`, replace:

```python
cell_run_dir = logs_dir.parents[1]
write_subagent_trace_manifest(cell_run_dir)
```

with:

```python
trial_dir = logs_dir.parent
prompt_mode = (
    "spacedock-codex-first-officer"
    if self._runtime == "codex"
    else "spacedock-claude-first-officer"
)
write_subagent_trace_manifest(trial_dir, prompt_mode=prompt_mode)
```

- [ ] **Step 3: Keep error handling scoped**

Keep the existing `FileNotFoundError`, `IndexError`, and `OSError` debug skip in this task. Do not add audit failures inside the agent hook; audit handles missing coverage from run artifacts.

- [ ] **Step 4: Run GREEN tests**

Run:

```bash
uv run pytest tests/integration/test_spacedock_cleanup_writes_trace_manifest.py tests/unit/test_subagent_traces_writer.py -x -v
```

Expected: pass.

**Spec cites:** §4.3, §8.4, §9.4; AC-1, AC-2.

### T3 - RED: Smoke Validator Understands Run Dirs

**Files:**
- Modify: `tests/unit/test_subagent_smoke_validator.py`
- Modify: `tests/integration/test_dab_paper_matrix_spacedock_gate.py`

- [ ] **Step 1: Add run-dir smoke tests**

Add tests that create:

```text
<tmp>/run/
  manifest.json                 # per_trial_paths: ["trial-a__aaaa", "trial-b__bbbb"]
  spec.frozen.yaml              # agent.kind: spacedock_solver
  trial-a__aaaa/subagent-trace-manifest.json  # captured: 1
  trial-b__bbbb/subagent-trace-manifest.json  # captured: 1
```

Assert `validate(run_dir) == 0`.

- [ ] **Step 2: Add missing-trial smoke test**

Remove `trial-b__bbbb/subagent-trace-manifest.json` and assert:

```python
assert validate(run_dir) == EXIT_MANIFEST_MISSING
```

The stderr should name `trial-b__bbbb/subagent-trace-manifest.json`.

- [ ] **Step 3: Add legacy single-trial fallback test**

Create a run dir with one `per_trial_paths` entry and a root `subagent-trace-manifest.json` with `captured: 1`. Assert `validate(run_dir) == 0`. This protects AC-4.

- [ ] **Step 4: Run RED tests**

Run:

```bash
uv run pytest tests/unit/test_subagent_smoke_validator.py tests/integration/test_dab_paper_matrix_spacedock_gate.py -x -v
```

Expected: fail because `subagent_smoke.validate()` only checks `<arg>/subagent-trace-manifest.json`.

**Spec cites:** §3.2, §9.4; AC-4.

### T4 - GREEN: Smoke Validator Per-Trial Inventory

**Files:**
- Modify: `src/razorback/agents/subagent_smoke.py`

- [ ] **Step 1: Add run-manifest helpers**

Add helpers that read `manifest.json`:

```python
def _listed_trial_dirs(run_dir: Path) -> list[Path]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [run_dir / str(name) for name in payload.get("per_trial_paths") or []]
```

- [ ] **Step 2: Validate trial manifests before root fallback**

If `_listed_trial_dirs(arg)` returns entries, require each `trial_dir / "subagent-trace-manifest.json"` to exist and have `captured >= 1`. Only use `arg / "subagent-trace-manifest.json"` when there is exactly one listed trial and no per-trial manifest exists.

- [ ] **Step 3: Preserve direct trial-dir behavior**

If no `manifest.json` exists, keep the current behavior: validate `<arg>/subagent-trace-manifest.json`.

- [ ] **Step 4: Run GREEN tests**

Run:

```bash
uv run pytest tests/unit/test_subagent_smoke_validator.py tests/integration/test_dab_paper_matrix_spacedock_gate.py -x -v
```

Expected: pass.

**Spec cites:** §3.2, §9.4; AC-4.

### T5 - RED: Strict Audit Fails on Missing Trial Dispatch Manifests

**Files:**
- Modify: `tests/unit/audit/conftest.py`
- Modify: `tests/unit/audit/test_rk_audit_cli.py`

- [ ] **Step 1: Add a Spacedock run fixture with one missing manifest**

Create `spacedock_dispatch_gap_run_dir`:

```text
run/
  manifest.json
  spec.frozen.yaml
  trial-a__aaaa/result.json
  trial-a__aaaa/subagent-trace-manifest.json
  trial-b__bbbb/result.json
```

Use `manifest.json`:

```json
{
  "run_dir_version": 1,
  "per_trial_paths": ["trial-a__aaaa", "trial-b__bbbb"],
  "benchmark_kind": "dab"
}
```

Use `spec.frozen.yaml`:

```yaml
agent:
  kind: spacedock_solver
  runtime: codex
```

- [ ] **Step 2: Add strict audit assertion**

Add:

```python
def test_rk_audit_strict_fails_on_missing_spacedock_trial_manifest(
    spacedock_dispatch_gap_run_dir,
):
    result = runner.invoke(app, ["audit", str(spacedock_dispatch_gap_run_dir), "--policy", "strict"])
    assert result.exit_code == 23
    payload = _parse_json_stdout(result)
    assert payload["summary"]["coverage_missing"] == 1
    missing = [t for t in payload["trials"] if t["taint_status"] == "coverage_missing"][0]
    assert missing["trial_id"] == "trial-b__bbbb"
    assert missing["findings"][0]["missing_reason"] == "spacedock_dispatch_manifest_absent"
```

- [ ] **Step 3: Add all-present and legacy assertions**

Add a fixture with both trial manifests and assert strict exits 0. Add a legacy fixture with one listed trial plus root `subagent-trace-manifest.json` and assert strict exits 0.

- [ ] **Step 4: Run RED tests**

Run:

```bash
uv run pytest tests/unit/audit/test_rk_audit_cli.py -x -v
```

Expected: fail because audit does not enumerate `manifest.json.per_trial_paths` for Spacedock dispatch coverage and does not inspect `subagent-trace-manifest.json`.

**Spec cites:** §3.2, §7.1, §9.4; AC-3, AC-4.

### T6 - GREEN: Audit Dispatch Coverage Helper

**Files:**
- Create: `src/razorback/audit/dispatch_manifests.py`
- Modify: `src/razorback/audit/cli.py`

- [ ] **Step 1: Add Spacedock run detection**

Implement `is_spacedock_run(run_dir: Path) -> bool` that returns true when `spec.frozen.yaml` contains `agent.kind: spacedock_solver`. Use the existing project dependency `yaml.safe_load` directly:

```python
def is_spacedock_run(run_dir: Path) -> bool:
    spec_path = run_dir / "spec.frozen.yaml"
    if not spec_path.is_file():
        return False
    try:
        payload = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return False
    agent = payload.get("agent") if isinstance(payload, dict) else None
    return isinstance(agent, dict) and agent.get("kind") == "spacedock_solver"
```

- [ ] **Step 2: Add trial inventory**

Implement:

```python
def listed_spacedock_trial_roots(run_dir: Path) -> list[Path]:
    if not is_spacedock_run(run_dir):
        return []
    payload = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    return [run_dir / str(name) for name in payload.get("per_trial_paths") or []]
```

Skip non-directories defensively; missing directories do not become audit rows in this task because AC-3 is about listed trials that lack dispatch manifests, not missing Harbor results.

- [ ] **Step 3: Add per-trial findings**

Implement:

```python
def scan_trial(run_dir: Path, trial_root: Path) -> list[dict]:
    per_trial = trial_root / "subagent-trace-manifest.json"
    legacy_root = run_dir / "subagent-trace-manifest.json"
    manifest_path = per_trial
    if not per_trial.is_file() and len(listed_spacedock_trial_roots(run_dir)) == 1:
        manifest_path = legacy_root
    if not manifest_path.is_file():
        return [_coverage("missing", "spacedock_dispatch_manifest_absent", per_trial, trial_root)]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [_coverage("missing", "spacedock_dispatch_manifest_invalid", manifest_path, trial_root)]
    if int(payload.get("captured") or 0) < 1:
        return [_coverage("partial", "spacedock_dispatch_events_absent", manifest_path, trial_root)]
    return []
```

The `_coverage(...)` helper must emit the same finding shape `taint._coverage_findings()` uses: `category: "trace_coverage"`, `confidence: "high"`, `source_kind: "spacedock_dispatch_manifest"`, `status`, and `missing_reason`.

- [ ] **Step 4: Wire audit roots and findings**

In `audit/cli.py`, seed `_discover_trial_roots(run_dir)` with `dispatch_manifests.listed_spacedock_trial_roots(run_dir)` before the existing trace-root discovery. In `_audit_run_dir`, append `*dispatch_manifests.scan_trial(run_dir, trial_root)` to the findings list before `_reduce_trial_status()`.

- [ ] **Step 5: Run GREEN tests**

Run:

```bash
uv run pytest tests/unit/audit/test_rk_audit_cli.py -x -v
```

Expected: pass.

**Spec cites:** §3.2, §7.1, §9.4; AC-3, AC-4.

### T7 - Acceptance Subset and Scope Guard

**Files:**
- No production files beyond T2, T4, and T6.
- No score reducer files.

- [ ] **Step 1: Run focused acceptance subset**

Run:

```bash
uv run pytest \
  tests/unit/test_subagent_traces_writer.py \
  tests/integration/test_spacedock_cleanup_writes_trace_manifest.py \
  tests/unit/test_subagent_smoke_validator.py \
  tests/integration/test_dab_paper_matrix_spacedock_gate.py \
  tests/unit/audit/test_rk_audit_cli.py \
  -x -v
```

Expected: pass.

- [ ] **Step 2: Run score-adjacent smoke only if touched by imports**

Do not change score semantics. If the implementation only touches the files in this plan, run:

```bash
uv run pytest tests/unit/test_runs_aggregate.py tests/unit/test_diff_per_trial_outcomes_sidecar.py -x -v
```

Expected: pass or same pre-existing baseline failures. This is a guard against accidental import breakage, not a score relaunch.

- [ ] **Step 3: Do not relaunch the full ADE/DAB score run**

Record in the implementation report that full-score relaunch is out of scope for this entity. Validation can use synthetic fixtures plus the focused pytest subset above.

**Spec cites:** §3.2, §9.4; AC-1 through AC-4.

## TDD Checkpoints

| Checkpoint | RED | GREEN |
|---|---|---|
| Per-trial writer path and metadata | T1 | T2 |
| Smoke validator run-dir compatibility | T3 | T4 |
| Strict audit dispatch coverage | T5 | T6 |
| Acceptance and score scope guard | T7 step 1 | T7 step 2 |

## Completion Criteria

- A two-trial synthetic parallel run produces two distinct `trial-dir/subagent-trace-manifest.json` payloads and no root overwrite.
- Strict audit exits 23 for a Spacedock run manifest where any listed trial lacks its dispatch manifest.
- A single-trial legacy root manifest remains accepted by smoke and audit.
- No files under `src/razorback/score*`, score reducers, or full-score drivers change for this entity.
