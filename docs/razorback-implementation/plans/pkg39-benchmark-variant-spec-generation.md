# PKG-39 Benchmark Variant Spec Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Codex benchmark spec generation cover ADE dbt-repair workflows, Harbor-shaped ADE task roots, and DAB workspace/hints/query-treatment variants without requiring full benchmark runs.

**Architecture:** Keep this conservative: extend the existing `examples/drivers/generate-codex-benchmark-specs.py` generator and its focused unit tests, add one checked-in ADE solver workflow, and add a concise DAB variant note. Do not change Harbor execution, scoring, DAB materialization, or ADE materialization unless a red generator/translator test proves the existing schema cannot express the required spec.

**Tech Stack:** Python 3.12, `uv`, pytest, PyYAML, Razorback v2 specs, Harbor task directories, `spacedock_solver_v2`.

---

## AC to Task Map

| AC | Governing spec cites | Tasks | Focused verification |
| --- | --- | --- | --- |
| AC-1 - ADE has a checked-in Codex dbt-repair solver workflow | v2 spec §4.2-4.3 solver workflow contract, §6.2 agent block, §8.2 solver workflow content hashing | T1 | `test -f examples/solver_workflows/codex-ade-dbt-repair/README.md`; review text says the graded artifact is repaired project state, not `answers.json`; freeze smoke in T6 |
| AC-2 - Codex spec generation can select solver workflow variants and Harbor-shaped ADE data | v2 spec §3.2 `rk freeze`, §6.1 benchmark translation, §6.3 validation, §7.1 run-dir artifacts | T2, T3, T6 | `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py`; one generated ADE spec freezes from `runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench` |
| AC-3 - DAB spec generation exposes workspace/hints variant knobs | v2 spec §6.1 benchmark block, §6.2 `spacedock_solver_v2`; Phase 2 DAB plan workspace/hints fields | T4, T6 | generator tests prove explicit knobs work and default DAB output remains unchanged |
| AC-4 - DAB variants found in `~/git/dataagentbench` are documented | v2 spec §5.3 hypothesis variants, §6.1 benchmark translation; DataAgentBench harness notes for batch/context modes | T5 | checked-in note names batch, context-fresh, context-resume axes and required readme/query-mode/hints inputs |

## Current Surfaces

| File | Responsibility | Planned action |
| --- | --- | --- |
| `examples/solver_workflows/codex-ade-dbt-repair/README.md` | ADE-specific Codex solver workflow | Create. Offline dbt-repair instructions; final artifact is the repaired project state. |
| `examples/drivers/generate-codex-benchmark-specs.py` | Codex DAB/ADE spec generator | Modify. Add solver workflow selection, ADE input-root mode detection/override, and DAB workspace/hints knobs. |
| `tests/unit/test_codex_benchmark_spec_generator.py` | Focused generator coverage | Modify. Add red tests for AC-1 through AC-3 and default-output preservation. |
| `docs/razorback-implementation/notes/pkg39-dab-variant-axes.md` | Concise run-planning note for DAB variants | Create. Summarize DataAgentBench batch/context/hints/readme axes; no operational benchmark run. |
| `examples/specs/codex-ade-bench-smoke.yaml` | Checked-in ADE smoke example | Modify only if needed to point at `codex-ade-dbt-repair`; avoid embedding machine-local data paths. |
| `examples/specs/codex-dab-smoke.yaml` | Checked-in DAB smoke example | Inspect only unless tests need an explicit default-preservation fixture. |
| `src/razorback/benchmarks/ade_bench/tasks.py` | Existing ADE resolver | Prefer no change. Existing string tasks resolve `<tasks_root>/<slug>/task.toml`, which already matches Harbor-shaped roots. |
| `src/razorback/spec/schema.py` and `src/razorback/translate.py` | Spec schema and Harbor translation | Inspect only. Do not add schema fields for this task unless generator tests reveal an existing field cannot express the AC. |

## DataAgentBench Reconnaissance

The dispatch names `~/git/dataagentbench`; in this VM that exact path is absent, but an equivalent checkout exists at `/home/exedev/dataagentbench`. Implementation should first check both paths and document which one was used. The relevant local evidence is:

- `docs/harness/split-query-mode-into-dispatch-and-context-axes.md`: splits query treatment into dispatch shape (`batch`, `per-query`) and context strategy (`none`, `build`, `resume`), with legacy mappings for `batch`, `context-fresh`, and `context-resume`.
- `docs/harness/context-fresh-query-mode.md`: context-fresh means a shared context/model pass plus query-local solves.
- `docs/harness/_archive/context-resume-single-workflow-gate-freeze.md`: context-resume means a single workflow with a gate/freeze point and resumed query-local work.
- `docs/hypothesis/codex-gpt55-xhigh-hints-spacedock-batch.md`: an active Codex DAB batch example carrying `query_mode: batch`, `hints: true`, and `readme: benchmark/workspace-readmes/workspace-readme.md`.
- `benchmark/tests/test_benchctl_sweep.py` and `benchmark/tests/test_benchctl_groups.py`: current run metadata treats `query_mode`, `readme_file`, `prompt_file`, and `hints` as variant/grouping fields.

Do not import code from DataAgentBench into Razorback. Use these files only to write the DAB variant note and to choose generator CLI names that match Razorback's current `harbor_dab` fields.

## Task 1: Add the ADE dbt-Repair Solver Workflow

**Spec cites:** §4.2-4.3 solver workflow, §5.3 solver workflow README contract, §6.2 `solver_workflow`.

**Files:**
- Create: `examples/solver_workflows/codex-ade-dbt-repair/README.md`
- Test: `tests/unit/test_codex_benchmark_spec_generator.py`

- [ ] **Step 1: Write the failing workflow existence/content test.**
  Add a test named `test_codex_ade_dbt_repair_workflow_is_checked_in` that asserts:
  - `examples/solver_workflows/codex-ade-dbt-repair/README.md` exists.
  - The text contains `dbt`, `repair`, and `repaired project state`.
  - The text does not instruct the solver to write `answers.json`.

- [ ] **Step 2: Run the red test.**
  Run: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py::test_codex_ade_dbt_repair_workflow_is_checked_in -q`
  Expected before the workflow exists: fail on missing file.

- [ ] **Step 3: Create the workflow README.**
  Write concise ADE-specific offline instructions:
  - inspect `instruction.md`, `task.toml`, dbt project files, and local test scripts;
  - modify the task-local dbt project to repair the failure;
  - run cheap local validation when provided;
  - leave the repaired project files as the graded artifact;
  - do not write or optimize for `answers.json`;
  - do not use network/package installs/external datasets.

- [ ] **Step 4: Run the focused test.**
  Run: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py::test_codex_ade_dbt_repair_workflow_is_checked_in -q`
  Expected: pass.

- [ ] **Step 5: Commit after Task 2 or Task 3, not standalone if the implementation worker is batching tiny doc/test changes.**
  Suggested commit message when combined: `pkg39: add ade dbt repair workflow variant`

## Task 2: Add Solver Workflow Variant Selection to the Generator

**Spec cites:** §3.2 freeze content hashing, §4.3 runtime selection, §6.2 `solver_workflow`, §8.2 `solver_workflow_hash`.

**Files:**
- Modify: `examples/drivers/generate-codex-benchmark-specs.py`
- Modify: `tests/unit/test_codex_benchmark_spec_generator.py`

- [ ] **Step 1: Add failing unit tests for solver workflow selection.**
  Add tests that call `emit_ade_bench_spec(..., solver_workflow="./examples/solver_workflows/codex-ade-dbt-repair")` and `emit_dab_spec(..., solver_workflow="./examples/solver_workflows/codex-benchmark-solver")`, then assert the emitted `agent.solver_workflow` matches the requested path and the default remains `./examples/solver_workflows/codex-benchmark-solver`.

- [ ] **Step 2: Add a CLI test for the same option.**
  Extend the existing `main()` monkeypatch style with `--solver-workflow ./examples/solver_workflows/codex-ade-dbt-repair --write` for `--benchmark ade-bench`; assert the written YAML uses that path.

- [ ] **Step 3: Run the red tests.**
  Run: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py -q`
  Expected before implementation: fail on unexpected `solver_workflow` parameter or missing CLI option.

- [ ] **Step 4: Implement the minimal generator change.**
  Replace the module-level `SOLVER_WORKFLOW` constant with `DEFAULT_SOLVER_WORKFLOW`. Add a `solver_workflow: str = DEFAULT_SOLVER_WORKFLOW` parameter to `_base_spec`, `emit_dab_spec`, and `emit_ade_bench_spec`. Add `--solver-workflow` to argparse and pass it through both benchmark branches.

- [ ] **Step 5: Run focused tests.**
  Run: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py -q`
  Expected: pass.

- [ ] **Step 6: Commit.**
  Commit message: `pkg39: parameterize codex benchmark solver workflow`

## Task 3: Support Harbor-Shaped ADE Roots in Generated Specs

**Spec cites:** §6.1 benchmark-block translation, §6.3 validation, §7.1 run-dir contract.

**Files:**
- Modify: `examples/drivers/generate-codex-benchmark-specs.py`
- Modify: `tests/unit/test_codex_benchmark_spec_generator.py`

- [ ] **Step 1: Add the Harbor-shaped ADE red test.**
  Build a temporary root shaped like `harbor-data/ade-bench/<task>/task.toml` with two tasks and no `tasks/` subdirectory. Assert `plan_ade_bench_specs(ade_bench_root=root)` returns both task names and marks rows so `emit_ade_bench_spec` emits:
  - `benchmark.kind: ade-bench`
  - `benchmark.tasks_root: <root>`
  - `benchmark.tasks: ["<task>"]`
  - no `benchmark.ade_bench_root`
  - `agent.solver_workflow: ./examples/solver_workflows/codex-ade-dbt-repair` when selected.

- [ ] **Step 2: Add the existing upstream ADE shape preservation test.**
  Keep the current `ade_bench_root/tasks/<task>/task.yaml` fixture path and assert it still emits local task entries with `tasks_root: "."`, `ade_bench_root: <root>`, and `tasks: [{"slug": "<task>"}]`.

- [ ] **Step 3: Run the red tests.**
  Run: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py -q`
  Expected before implementation: fail because `plan_ade_bench_specs` only accepts `<root>/tasks/<task>/task.yaml`.

- [ ] **Step 4: Implement a small ADE row mode.**
  Extend `AdeBenchSpecRow` with an `input_shape` literal such as `upstream` or `harbor_task_root`. In `plan_ade_bench_specs`, prefer:
  - upstream shape when `<root>/tasks/*/task.yaml` exists;
  - Harbor-shaped task root when `<root>/*/task.toml` exists;
  - otherwise raise `FileNotFoundError` naming both accepted layouts.
  Keep string task entries for Harbor-shaped roots because `resolve_task_dirs()` already checks `<tasks_root>/<slug>/task.toml`.

- [ ] **Step 5: Run focused tests.**
  Run: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py -q`
  Expected: pass.

- [ ] **Step 6: Commit.**
  Commit message: `pkg39: generate codex ade specs from harbor task roots`

## Task 4: Add DAB Workspace and Hints Knobs Without Changing Defaults

**Spec cites:** §6.1 benchmark block; §6.2 agent block. Related implementation surface: `HarborDabBenchmarkBlock.workspace_variant` and `hints`.

**Files:**
- Modify: `examples/drivers/generate-codex-benchmark-specs.py`
- Modify: `tests/unit/test_codex_benchmark_spec_generator.py`

- [ ] **Step 1: Add failing tests for explicit DAB knobs.**
  Add tests asserting `emit_dab_spec(..., workspace_variant="spacedock", hints=True)` writes `benchmark.workspace_variant: spacedock` and `benchmark.hints: true`.

- [ ] **Step 2: Add default preservation tests.**
  Keep or extend the existing default DAB test to assert default generated output remains `workspace_variant: direct-structured` and `hints: false`.

- [ ] **Step 3: Add CLI coverage.**
  Add a `main()` monkeypatch test for `--benchmark dab --workspace-variant spacedock --hints --write`; assert the generated YAML carries those values. Add a companion parse test or emitted-spec test for `--no-hints` if argparse uses an explicit BooleanOptionalAction.

- [ ] **Step 4: Run the red tests.**
  Run: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py -q`
  Expected before implementation: fail on missing parameters/options.

- [ ] **Step 5: Implement the minimal generator change.**
  Add `workspace_variant` and `hints` parameters to `emit_dab_spec`; validate choices with the same three strings already accepted by `src/razorback/spec/schema.py`. Add argparse flags:
  - `--workspace-variant {direct-minimal,direct-structured,spacedock}`, default `direct-structured`;
  - `--hints` / `--no-hints`, default `False`.
  Pass them only for DAB. Do not change ADE output.

- [ ] **Step 6: Run focused tests.**
  Run: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py -q`
  Expected: pass.

- [ ] **Step 7: Commit.**
  Commit message: `pkg39: expose dab workspace and hints variants`

## Task 5: Document DAB Variant Axes From DataAgentBench

**Spec cites:** §5.3 hypothesis variants, §6.1 benchmark translation.

**Files:**
- Create: `docs/razorback-implementation/notes/pkg39-dab-variant-axes.md`

- [ ] **Step 1: Create the note with source paths and no run results.**
  The note must name the reconnaissance checkout used (`~/git/dataagentbench` if present, otherwise `/home/exedev/dataagentbench`) and cite the specific files inspected.

- [ ] **Step 2: Document the three required axes.**
  Include a compact table:
  - batch: dispatch shape is one first-officer session over all queries; required inputs are DAB data root, workspace README, `query_mode=batch` in DataAgentBench terms, Razorback `workspace_variant`, and `hints`.
  - context-fresh: shared context/model pass plus query-local solves; required inputs are context/query README treatment in DataAgentBench, DAB data root, workspace/hints selection; Razorback only documents this for run planning unless generator support is explicitly added later.
  - context-resume: gate/freeze context pass resumed into query-local work; required inputs are the single-workflow gate/freeze README mechanism and context cache/provenance; Razorback does not run the full benchmark in PKG-39.

- [ ] **Step 3: State Razorback's current support boundary.**
  Say PKG-39 generator support covers Razorback-native `workspace_variant` and `hints` fields now. Batch/context-fresh/context-resume are recorded as run-planning axes from DataAgentBench, not full Razorback execution modes in this task.

- [ ] **Step 4: Commit.**
  Commit message: `pkg39: document dab variant axes`

## Task 6: Freeze and Smoke Verification

**Spec cites:** §3.2 `rk freeze`, §6.3 validation, §7.1 run-dir artifacts, §8.2 provenance resolution.

**Files:**
- No new implementation files. Uses generated temporary specs under a throwaway path such as `runs/pkg39-spec-smoke/`.

- [ ] **Step 1: Run the focused unit suite.**
  Run: `uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py`
  Expected: all tests pass.

- [ ] **Step 2: Generate one Harbor-shaped ADE smoke spec.**
  Use the existing Harbor-shaped root:
  `runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench`.
  Generate a single-task spec to a throwaway output root, selecting `--solver-workflow ./examples/solver_workflows/codex-ade-dbt-repair`. If the generator writes all tasks by default, use a temporary fixture root with one `<task>/task.toml` in the unit tests and freeze that emitted fixture-shaped spec instead.

- [ ] **Step 3: Freeze the ADE smoke spec.**
  Run: `uv run rk freeze <generated-ade-spec.yaml> --allow-missing`
  Expected: exit 0; frozen spec contains `agent.solver_workflow_content_hash` and `provenance.solver_workflow_hash`.

- [ ] **Step 4: Optional DAB freeze smoke without benchmark execution.**
  Generate one DAB spec with `--workspace-variant spacedock --hints --solver-workflow ./examples/solver_workflows/codex-benchmark-solver` against a placeholder or local data root and run `uv run rk freeze <generated-dab-spec.yaml> --allow-missing`. This validates spec construction only.

- [ ] **Step 5: Do not run full DAB or ADE benchmark datasets.**
  PKG-39's scope is generation, freeze, and documentation. Full benchmark runs belong to goal-level run entities.

- [ ] **Step 6: Final commit if verification required small doc/test corrections.**
  Commit message: `pkg39: verify variant spec generation`

## Acceptance Commands

```bash
uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py
uv run rk freeze <generated-ade-spec.yaml> --allow-missing
```

Optional DAB construction check:

```bash
uv run rk freeze <generated-dab-spec.yaml> --allow-missing
```

Full benchmark execution is intentionally out of scope for PKG-39.
