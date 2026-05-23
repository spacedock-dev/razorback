# PKG-34 Validation Report

Entity: `docs/razorback-implementation/pkg34-codex-solver-workflow-prompt-and-dab-db-hints.md`

Branch: `spacedock-ensign/pkg34-codex-solver-workflow-prompt-and-dab-db-hints`

Validated job directory: `.runs/pkg34/bookreview-codex/codex-dab-bookreview/32e361679554f5e4`

## Acceptance Criteria

### AC-1 - PASS

`spacedock_solver_v2` sends the solver workflow instructions to the inner
runtime before task text.

Evidence:

```text
$ uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_codex_benchmark_spec_generator.py -q
.............                                                            [100%]
13 passed in 0.20s
```

Review evidence:

- `src/razorback/agents/spacedock_solver_v2.py` reads `solver_workflow/README.md`
  and composes `# Solver workflow instructions` before `# Task instruction`.
- `tests/unit/test_spacedock_solver_v2_class.py` asserts the delegated
  instruction contains the README text before `task instruction`.

### AC-2 - PASS

Generated Codex DAB specs use structured workspace hints, and `hints: false` is
preserved.

Evidence:

```text
$ uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_codex_benchmark_spec_generator.py -q
.............                                                            [100%]
13 passed in 0.20s
```

```text
$ rg -n "workspace_variant|hints|datasets|trials" .runs/pkg34/specs/dab/bookreview.yaml .runs/pkg34/specs/dab/bookreview.frozen.yaml examples/specs/codex-dab-smoke.yaml
.runs/pkg34/specs/dab/bookreview.frozen.yaml:27:  workspace_variant: direct-structured
.runs/pkg34/specs/dab/bookreview.frozen.yaml:28:  hints: false
.runs/pkg34/specs/dab/bookreview.yaml:23:  workspace_variant: direct-structured
.runs/pkg34/specs/dab/bookreview.yaml:24:  hints: false
examples/specs/codex-dab-smoke.yaml:23:  workspace_variant: direct-structured
examples/specs/codex-dab-smoke.yaml:24:  hints: false
```

Spec generation command, with local data root normalized for portability:

```text
$ export DAB_DATA_ROOT=<DAB_DATA_ROOT>
$ uv run --frozen python examples/drivers/generate-codex-benchmark-specs.py --benchmark dab --dab-data-root "$DAB_DATA_ROOT" --out-root .runs/pkg34/specs --write --freeze
wrote .runs/pkg34/specs/dab/bookreview.frozen.yaml
DAB Codex dry-run: N=1, datasets=12, data_root=<DAB_DATA_ROOT>
- dataset=bookreview trials=1 data_root=<DAB_DATA_ROOT>
wrote .runs/pkg34/specs/dab/bookreview.yaml
```

### AC-3 - PASS

The Codex benchmark workflow explicitly forbids solver-side container, host, and
shell-network probing.

Review evidence from `examples/solver_workflows/codex-benchmark-solver/README.md`:

- Lines 9-11 direct the solver to read task-local instructions and workspace
  files first.
- Lines 15-17 forbid package-manager commands, `curl`, `wget`, DNS lookups for
  outside hosts, web searches, and remote API calls while solving.
- Lines 22-25 direct database tasks to read the workspace `README.md` and
  `db_config.yaml`, then use documented service names such as `dab-postgres`
  and `dab-mongo`.
- Lines 26-28 forbid Docker, Docker socket, host-network, and shell-network
  probing to discover services.

### AC-4 - PASS

Generated BookReview Codex rerun completed all 3 trials, scored 3/3, and passed
strict audit with no tainted or coverage-missing trials.

Run command:

```text
$ rm -rf .runs/pkg34/bookreview-codex
$ uv run --frozen rk run .runs/pkg34/specs/dab/bookreview.frozen.yaml --runs-dir .runs/pkg34/bookreview-codex --allow-plugin-drift --allow-alias-drift
  3/3 Mean: 1.000
Trials: 3
Exceptions: 0
Mean: 1.000
Reward 1.0 Count: 3
Results written to .runs/pkg34/bookreview-codex/codex-dab-bookreview/32e361679554f5e4/result.json
```

Score command:

```text
$ uv run --frozen rk score .runs/pkg34/bookreview-codex/codex-dab-bookreview/32e361679554f5e4 --format json
{
  "strata": {
    "bookreview": {
      "n_total": 3,
      "n_completed": 3,
      "n_errored": 0,
      "n_pass": 3,
      "pass_at_1": 1.0,
      "error_reason": null
    }
  },
  "stratified_pass_at_1": 1.0,
  "stratified_n_completed": 3,
  "stratified_n_errored": 0,
  "error_reason": null
}
```

Strict audit command, with path fields omitted from the excerpt for portability:

```text
$ uv run --frozen rk audit .runs/pkg34/bookreview-codex/codex-dab-bookreview/32e361679554f5e4 --policy strict --format json
{
  "policy": "strict",
  "schema_version": "rk-audit-v1",
  "summary": {
    "clean": 3,
    "coverage_missing": 0,
    "tainted": 0
  },
  "trials": [
    {"trial_id": "bookreview-q1__TfRUQdG", "taint_status": "clean", "findings": []},
    {"trial_id": "bookreview-q2__j5r8EX7", "taint_status": "clean", "findings": []},
    {"trial_id": "bookreview-q3__6gbybGo", "taint_status": "clean", "findings": []}
  ]
}
```

## Review Findings

Blocking findings: none.

Non-blocking findings: none.

## Gate Decision

PASS. AC-1 through AC-4 are independently verified, `hints: false` is preserved,
the BookReview rerun scored 3 completed passing trials, and strict audit
reported 3 clean trials with no taint or coverage gaps.
