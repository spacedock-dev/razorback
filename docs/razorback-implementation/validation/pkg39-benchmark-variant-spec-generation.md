# PKG-39 Validation Report

Entity: `docs/razorback-implementation/pkg39-benchmark-variant-spec-generation.md`
Branch: `spacedock-ensign/pkg39-benchmark-variant-spec-generation`
Implementation commits reviewed: `d08c3ba`, `467c88a`, `6c7d251`, `3971339`, `a459d4f`
Role asset read: `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/ensign/SKILL.md`

## Commands Run

### Focused acceptance tests

Command:

```bash
uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py
```

Result:

```text
collected 17 items
tests/unit/test_codex_benchmark_spec_generator.py .................      [100%]
17 passed in 0.11s
```

`uv.lock` churn: none from the frozen focused test command.

### Full pytest sweep

Command:

```bash
uv run pytest
```

Result:

```text
542 passed, 10 skipped, 4 failed
```

Failures were outside PKG-39 surfaces:

- `tests/integration/test_budget_gate_two_invocations.py::test_two_sequential_invocations_second_refuses`: `AuthDiscoveryError: no claude credentials found`.
- `tests/integration/test_budget_gate_two_invocations.py::test_without_flag_regression_against_smoke`: `AuthDiscoveryError: no claude credentials found`.
- `tests/integration/test_rk_run_v2_deterministic_smoke.py::test_deterministic_smoke_runs_end_to_end`: `AuthDiscoveryError: no claude credentials found`.
- `tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end`: `AssertionError: events.jsonl is empty`.

`uv.lock` churn: `uv run pytest` removed the existing `[options] exclude-newer` block. This incidental validation churn was restored before committing; final `git status --short` was clean before report edits.

### ADE Harbor-shaped generation and freeze smoke

The plan's named Harbor data root, `runs/goal4-ade-bench-codex-clean/harbor-data/ade-bench`, was not present in this checkout, so validation used a throwaway one-task Harbor-shaped root under `.test-tmp/pkg39-validation/harbor-data/ade-bench/example001/task.toml`.

Command:

```bash
mkdir -p .test-tmp/pkg39-validation/harbor-data/ade-bench/example001 .test-tmp/pkg39-validation/specs
printf 'name = "example001"\n' > .test-tmp/pkg39-validation/harbor-data/ade-bench/example001/task.toml
uv run --frozen python examples/drivers/generate-codex-benchmark-specs.py \
  --benchmark ade-bench \
  --ade-bench-root .test-tmp/pkg39-validation/harbor-data/ade-bench \
  --out-root .test-tmp/pkg39-validation/specs \
  --solver-workflow ./examples/solver_workflows/codex-ade-dbt-repair \
  --write
```

Result:

```text
ade-bench Codex dry-run: N=1, tasks=1, ade_bench_root=.test-tmp/pkg39-validation/harbor-data/ade-bench
- task=example001 trials=1 ade_bench_root=.test-tmp/pkg39-validation/harbor-data/ade-bench
wrote .test-tmp/pkg39-validation/specs/ade-bench/example001.yaml
```

Generated spec evidence:

```yaml
agent:
  solver_workflow: ./examples/solver_workflows/codex-ade-dbt-repair
benchmark:
  kind: ade-bench
  tasks_root: .test-tmp/pkg39-validation/harbor-data/ade-bench
  tasks:
  - example001
```

Command:

```bash
uv run rk freeze .test-tmp/pkg39-validation/specs/ade-bench/example001.yaml --allow-missing
```

Result:

```text
wrote .test-tmp/pkg39-validation/specs/ade-bench/example001.frozen.yaml
wrote .test-tmp/pkg39-validation/specs/ade-bench/provenance.yaml
```

Freeze artifact evidence:

```text
.test-tmp/pkg39-validation/specs/ade-bench/example001.frozen.yaml:12:  solver_workflow_content_hash: sha256:797e7ba4b431fc432c4629ab8ba1ff6e8b017211848f0f4ce94db16edbe455da
.test-tmp/pkg39-validation/specs/ade-bench/example001.frozen.yaml:52:  solver_workflow_hash: sha256:797e7ba4b431fc432c4629ab8ba1ff6e8b017211848f0f4ce94db16edbe455da
.test-tmp/pkg39-validation/specs/ade-bench/provenance.yaml:7:solver_workflow_hash: sha256:797e7ba4b431fc432c4629ab8ba1ff6e8b017211848f0f4ce94db16edbe455da
```

This validates the freeze artifacts named by spec §7.1 (`spec.frozen.yaml` equivalent and `provenance.yaml`) for the generated ADE spec. Full run-dir production was out of scope for PKG-39.

## Acceptance Criteria

### AC-1 - ADE has a checked-in Codex dbt-repair solver workflow

PASS.

Verified by:

```bash
test -f examples/solver_workflows/codex-ade-dbt-repair/README.md && rg -n "repaired project state|separate answer file|dbt|Repair" examples/solver_workflows/codex-ade-dbt-repair/README.md
```

Output:

```text
1:# Codex ADE dbt Repair Workflow
3:Work offline inside the task workspace. Inspect `instruction.md`, `task.toml`, the dbt
6:Repair the task-local dbt project so the requested behavior is implemented in the
10:Run cheap local validation when the task provides it, such as dbt compile, targeted
14:Leave the repaired project state as the graded artifact. Do not optimize for a
15:separate answer file, network access, package installs, or external datasets.
```

Review: the workflow says the graded artifact is the repaired project state and discourages a separate answer file. It does not mention or instruct `answers.json`.

### AC-2 - Codex spec generation can select solver workflow variants and Harbor-shaped ADE data

PASS.

Verified by:

```bash
uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py
```

Output:

```text
17 passed in 0.11s
```

Additional evidence:

- Tests cover solver workflow selection at `tests/unit/test_codex_benchmark_spec_generator.py:98` and CLI selection at `tests/unit/test_codex_benchmark_spec_generator.py:198`.
- Harbor-shaped ADE coverage is at `tests/unit/test_codex_benchmark_spec_generator.py:344`.
- Generator emits Harbor-shaped ADE specs with `tasks_root` and string `tasks` at `examples/drivers/generate-codex-benchmark-specs.py:118`.
- Freeze smoke from the Harbor-shaped fixture exited 0 and wrote frozen/provenance hashes as shown above.

### AC-3 - DAB spec generation exposes workspace/hints variant knobs for current experiments

PASS.

Verified by:

```bash
uv run --frozen pytest tests/unit/test_codex_benchmark_spec_generator.py
```

Output:

```text
17 passed in 0.11s
```

Additional evidence:

- Default DAB output preservation is tested at `tests/unit/test_codex_benchmark_spec_generator.py:65` and `tests/unit/test_codex_benchmark_spec_generator.py:130`.
- CLI `--workspace-variant spacedock --hints` coverage is at `tests/unit/test_codex_benchmark_spec_generator.py:239`.
- CLI `--no-hints` coverage is at `tests/unit/test_codex_benchmark_spec_generator.py:275`.
- Generator validates and emits the knobs at `examples/drivers/generate-codex-benchmark-specs.py:76` and passes them through CLI at `examples/drivers/generate-codex-benchmark-specs.py:260`.

### AC-4 - The DAB variants found in `~/git/dataagentbench` are documented for run planning

PASS.

Verified by:

```bash
rg -n "batch|context-fresh|context-resume|workspace_variant|hints|readme|query_mode" docs/razorback-implementation/notes/pkg39-dab-variant-axes.md
```

Output:

```text
19:| batch | One first-officer session handles all dataset queries. DataAgentBench records this as `query_mode=batch`. | DAB data root, workspace README, batch query mode, Razorback `workspace_variant`, and `hints`. | Generator can emit DAB specs with selected `workspace_variant` and `hints`; batch remains a run-planning label from DataAgentBench. |
20:| context-fresh | A shared context/model pass is built, then query-local solves run from that fresh context treatment. | DAB data root, context README/query README treatment, workspace/hints selection, and context build provenance. | Documented for run planning only; PKG-39 does not add a Razorback execution mode for context-fresh. |
21:| context-resume | A single workflow uses a gate/freeze point, records model/context state, and resumes query-local work from that cached point. | DAB data root, single-workflow gate/freeze README mechanism, context cache/provenance, workspace/hints selection. | Documented for run planning only; PKG-39 does not run or generate full context-resume benchmark execution. |
26:`workspace_variant` and `hints` fields. Batch, context-fresh, and
27:context-resume are recorded here as DataAgentBench run-planning axes, not as
```

The note records `/home/exedev/dataagentbench` as the available equivalent because dispatched `~/git/dataagentbench` was absent.

## Code Review

Requested protocol: `superpowers:requesting-code-review`. Codex did not expose a Superpowers subagent invocation tool in this environment, so validation read `/home/exedev/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.7/skills/requesting-code-review/SKILL.md` and applied the supplied review checklist manually to `c1f06d0..6c7d251`.

Reviewed surfaces:

- `examples/drivers/generate-codex-benchmark-specs.py`
- `tests/unit/test_codex_benchmark_spec_generator.py`
- `examples/solver_workflows/codex-ade-dbt-repair/README.md`
- `docs/razorback-implementation/notes/pkg39-dab-variant-axes.md`

Blocking findings: none.

Non-blocking findings: none for PKG-39 implementation.

Residual risks / non-PKG-39 observations:

- Full `uv run pytest` is not green in this VM due to missing Claude credentials in three integration tests and an unrelated empty-events assertion in `test_rk_run_nop_end_to_end`.
- The plan's preferred existing Harbor-shaped ADE root is absent in this checkout; validation used an equivalent throwaway root for the freeze contract.

## Gate Decision

PASSED. AC-1 through AC-4 are independently verified, the focused acceptance command is green, ADE Harbor-shaped generation and freeze smoke succeeded, and the implementation review found no blocking or non-blocking PKG-39 issues. Recommend approve to `done`.
