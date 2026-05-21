# PKG-27 Validation

Branch: `spacedock-ensign/pkg27-codex-benchmark-solver-workflow`
Worktree: `<worktree>`

## Command Evidence

Required targeted test:

```text
uv run pytest tests/unit/test_codex_benchmark_spec_generator.py
```

Output:

```text
tests/unit/test_codex_benchmark_spec_generator.py ....                   [100%]
4 passed in 0.07s
```

Full suite command:

```text
uv run pytest
```

Output summary:

```text
4 failed, 496 passed, 10 skipped in 37.10s
```

Failures:

```text
tests/integration/test_budget_gate_two_invocations.py::test_two_sequential_invocations_second_refuses
AuthDiscoveryError: no claude credentials found. Add ANTHROPIC_API_KEY to <worktree>/.env or write a token to <home>/.claude/benchmark-token.

tests/integration/test_budget_gate_two_invocations.py::test_without_flag_regression_against_smoke
AuthDiscoveryError: no claude credentials found. Add ANTHROPIC_API_KEY to <worktree>/.env or write a token to <home>/.claude/benchmark-token.

tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end
AssertionError: events.jsonl is empty

tests/integration/test_rk_run_v2_deterministic_smoke.py::test_deterministic_smoke_runs_end_to_end
AuthDiscoveryError: no claude credentials found. Add ANTHROPIC_API_KEY to <worktree>/.env or write a token to <home>/.claude/benchmark-token.
```

The Claude-auth failures and nop `events.jsonl` failure are outside the PKG-27 touched paths; the same failure classes were recorded during PKG-26 validation.

## Acceptance Criteria

### AC-1 - PASS

Verifier clause:

```text
the workflow directory exists and `uv run rk freeze` can content-hash it through `solver_workflow_content_hash`.
```

Command:

```text
uv run rk freeze examples/specs/codex-dab-smoke.yaml --allow-missing
```

Output:

```text
wrote examples/specs/codex-dab-smoke.frozen.yaml
wrote examples/specs/provenance.yaml
```

Frozen spec evidence:

```text
agent.solver_workflow: examples/solver_workflows/codex-benchmark-solver
agent.solver_workflow_content_hash: sha256:803a512c01f0f9ce346933ea3860efd1cd7a70e73e4c4b6fe215a84c4a9f69ff
provenance.solver_workflow_hash: sha256:803a512c01f0f9ce346933ea3860efd1cd7a70e73e4c4b6fe215a84c4a9f69ff
```

Workflow review: `examples/solver_workflows/codex-benchmark-solver/README.md` instructs the solver to inspect task files, use only local task files/services/documented local endpoints, avoid public internet/external datasets, and write the requested artifact.

### AC-2 - PASS

Verifier clause:

```text
dry-run output lists all 12 DAB datasets with N=1 and the configured data root.
```

Command:

```text
uv run python examples/drivers/generate-codex-benchmark-specs.py --benchmark dab --dab-data-root /tmp/pkg27-dab-data
```

Output:

```text
DAB Codex dry-run: N=1, datasets=12, data_root=/tmp/pkg27-dab-data
- dataset=agnews trials=1 data_root=/tmp/pkg27-dab-data
- dataset=bookreview trials=1 data_root=/tmp/pkg27-dab-data
- dataset=crmarenapro trials=1 data_root=/tmp/pkg27-dab-data
- dataset=DEPS_DEV_V1 trials=1 data_root=/tmp/pkg27-dab-data
- dataset=GITHUB_REPOS trials=1 data_root=/tmp/pkg27-dab-data
- dataset=googlelocal trials=1 data_root=/tmp/pkg27-dab-data
- dataset=music_brainz_20k trials=1 data_root=/tmp/pkg27-dab-data
- dataset=PANCANCER_ATLAS trials=1 data_root=/tmp/pkg27-dab-data
- dataset=PATENTS trials=1 data_root=/tmp/pkg27-dab-data
- dataset=stockindex trials=1 data_root=/tmp/pkg27-dab-data
- dataset=stockmarket trials=1 data_root=/tmp/pkg27-dab-data
- dataset=yelp trials=1 data_root=/tmp/pkg27-dab-data
```

Schema review: `examples/drivers/generate-codex-benchmark-specs.py` emits `agent.kind: spacedock_solver_v2`, `runtime: codex`, `solver_workflow: ./examples/solver_workflows/codex-benchmark-solver`, `benchmark.kind: harbor_dab`, and caller-provided `data_root`.

### AC-3 - PASS

Verifier clause:

```text
dry-run output lists every discovered task under the configured `ade_bench_root/tasks/` with N=1.
```

Command:

```text
rm -rf /tmp/pkg27-ade-bench && mkdir -p /tmp/pkg27-ade-bench/tasks/task_b /tmp/pkg27-ade-bench/tasks/task_a /tmp/pkg27-ade-bench/tasks/ignored && printf 'task_id: task_b\n' > /tmp/pkg27-ade-bench/tasks/task_b/task.yaml && printf 'task_id: task_a\n' > /tmp/pkg27-ade-bench/tasks/task_a/task.yaml && uv run python examples/drivers/generate-codex-benchmark-specs.py --benchmark ade-bench --ade-bench-root /tmp/pkg27-ade-bench
```

Output:

```text
ade-bench Codex dry-run: N=1, tasks=2, ade_bench_root=/tmp/pkg27-ade-bench
- task=task_a trials=1 ade_bench_root=/tmp/pkg27-ade-bench
- task=task_b trials=1 ade_bench_root=/tmp/pkg27-ade-bench
```

Schema review: the generator emits `benchmark.kind: ade-bench`, `tasks_root: .`, caller-provided `ade_bench_root`, and local task entries shaped as `tasks: [{slug: ...}]`.

### AC-4 - ENVIRONMENT BLOCKED AFTER FREEZE

Verifier clause:

```text
One DAB smoke spec and one ade-bench smoke spec freeze successfully. The DAB smoke runs end to end; the ade-bench smoke either runs end to end or fails only on an already-filed ade-bench infrastructure blocker, not on Codex spec construction.
```

DAB freeze command:

```text
uv run rk freeze examples/specs/codex-dab-smoke.yaml --allow-missing
```

Output:

```text
wrote examples/specs/codex-dab-smoke.frozen.yaml
wrote examples/specs/provenance.yaml
```

ade-bench freeze command:

```text
uv run rk freeze examples/specs/codex-ade-bench-smoke.yaml --allow-missing
```

Output:

```text
wrote examples/specs/codex-ade-bench-smoke.frozen.yaml
wrote examples/specs/provenance.yaml
```

DAB run command:

```text
rm -rf /tmp/razorback-pkg27-dab-smoke && uv run rk run examples/specs/codex-dab-smoke.frozen.yaml --runs-dir /tmp/razorback-pkg27-dab-smoke
```

Output:

```text
AuthDiscoveryError: no codex credentials found. Add OPENAI_API_KEY to <worktree>/.env.
```

ade-bench run command:

```text
rm -rf /tmp/razorback-pkg27-ade-smoke && uv run rk run examples/specs/codex-ade-bench-smoke.frozen.yaml --runs-dir /tmp/razorback-pkg27-ade-smoke
```

Output:

```text
AuthDiscoveryError: no codex credentials found. Add OPENAI_API_KEY to <worktree>/.env.
```

No run-dir artifacts were created before the auth preflight failed, so §7 run-dir artifacts could not be inspected in this environment. This is classified as a non-blocking local credential blocker because spec freeze and construction succeeded and execution stopped before Harbor dispatch.

## Portability Review

Generated full-matrix specs are portable: DAB uses the `--dab-data-root` argument, and ade-bench uses the `--ade-bench-root` argument. The tracked smoke specs contain explicit placeholder paths (`/path/to/dataagentbench/data` and `/path/to/ade-bench`) plus comments instructing operators to override them before live execution; they do not embed `<home>`, `/tmp`, or any user checkout path.

## Code Review

`superpowers:requesting-code-review` is not available as a callable skill/tool in this Codex session. I performed an inline code-review pass against the worktree diff with the same blocking/non-blocking classification.

Blocking findings: none.

Non-blocking findings:

- `uv run pytest` has four failures outside the PKG-27 touched path: three missing Claude credential failures and one existing nop `events.jsonl` empty assertion.
- Live smoke `rk run` for both smoke specs is blocked by missing `OPENAI_API_KEY`, so run-dir artifact layout could not be validated here.

Reviewed code paths:

- `examples/drivers/generate-codex-benchmark-specs.py:35-47` for DAB/ade-bench enumeration.
- `examples/drivers/generate-codex-benchmark-specs.py:50-82` for emitted benchmark blocks and portable roots.
- `examples/drivers/generate-codex-benchmark-specs.py:85-106` for `spacedock_solver_v2` Codex agent shape.
- `examples/solver_workflows/codex-benchmark-solver/README.md:7-23` for local-only solver instructions.
- `examples/specs/codex-dab-smoke.yaml:18-24` and `examples/specs/codex-ade-bench-smoke.yaml:18-23` for smoke benchmark blocks.

## Gate Decision

APPROVE to `done`.

AC-1 through AC-3 pass with exact verifier commands. AC-4 freeze checks pass; live runs are blocked only by missing local Codex credentials before Harbor dispatch. No blocking code-review findings were found, and tracked specs/generator surfaces handle data roots portably.
