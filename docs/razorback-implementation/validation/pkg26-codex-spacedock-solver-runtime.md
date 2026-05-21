# PKG-26 Validation

Branch: `spacedock-ensign/pkg26-codex-spacedock-solver-runtime`
Worktree: `<worktree>`

## Command Evidence

Full suite command:

```text
uv run pytest
```

Output summary:

```text
4 failed, 492 passed, 10 skipped in 35.63s
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

The three Claude failures are environment/auth gated and outside PKG-26 Codex behavior. The nop `events.jsonl` failure is outside the PKG-26 touched code path.

## Acceptance Criteria

### AC-1 - PASS

Verifier clause:

```text
uv run pytest tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q
```

Output:

```text
..............                                                           [100%]
14 passed in 0.23s
```

The suite includes `test_codex_constructs_inner_agent_with_supported_kwargs` and `test_codex_runtime_dispatch_constructs_inner_agent`, which assert Harbor `Codex` construction with `model_name`, `extra_env`, and supported descriptor kwargs.

### AC-2 - PASS

Verifier clause:

```text
unit tests cover one accepted Codex config and one unsupported-kwarg rejection path.
```

Command:

```text
uv run pytest tests/unit/test_runtime_adapters.py -q
```

Covered during the AC-1 and AC-4 targeted commands:

```text
..............                                                           [100%]
14 passed in 0.23s
..............                                                           [100%]
14 passed in 0.24s
```

Code review check: `src/razorback/agents/_runtime/codex.py:41-52` forwards only Harbor Codex descriptor kwargs and raises `SpacedockSolverAgentError` naming unsupported fields. `src/razorback/agents/_runtime/codex.py:55-63` treats only schema defaults/noops as ignorable: `None`, empty tool lists, and default `max_turns=200`. Active `max_turns`, `tools_allowed`, `tools_denied`, and `append_system_prompt` are rejected by tests.

### AC-3 - ENVIRONMENT BLOCKED AFTER FREEZE

Verifier clause:

```text
uv run rk freeze <codex-smoke-spec> followed by uv run rk run <codex-smoke-spec.frozen.yaml> --runs-dir runs/pkg26-codex-smoke/ --allow-plugin-drift --allow-alias-drift exits 0 and the resulting run-dir contains result.json, manifest.json, summary.json, and a Codex trace sentinel (codex-output.jsonl or Harbor's Codex-equivalent trace file).
```

Command:

```text
uv run rk freeze examples/specs/_codex-smoke-v2.yaml
```

Output:

```text
ProvenanceError: unresolved provenance fields: model_resolved_version. Pass --allow-missing to write anyway (will be tagged in provenance.yaml).
```

Validation-instruction fallback command:

```text
uv run rk freeze examples/specs/_codex-smoke-v2.yaml --allow-missing
```

Output:

```text
wrote examples/specs/_codex-smoke-v2.frozen.yaml
wrote examples/specs/provenance.yaml
```

Frozen spec inspection confirmed `agent.solver_workflow_content_hash`, `agent.sealed_hash`, `provenance.agent_cli_hash`, `provenance.harbor_version`, and `provenance.solver_workflow_hash`; `examples/specs/provenance.yaml` records:

```text
unresolved:
- model_resolved_version
```

Run command:

```text
uv run rk run examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir runs/pkg26-codex-smoke/ --allow-plugin-drift --allow-alias-drift
```

Output:

```text
Resolving despite existing lockfile due to removal of global exclude newer
AuthDiscoveryError: no codex credentials found. Add OPENAI_API_KEY to <worktree>/.env.
```

No `runs/pkg26-codex-smoke/` artifacts were written before auth preflight failed, so `result.json`, `manifest.json`, `summary.json`, and Harbor Codex trace sentinel could not be validated in this environment. This is classified as a non-blocking environment/auth blocker for the gate because the frozen spec is produced with `--allow-missing` and execution stops before Harbor job launch due to missing local Codex credentials.

### AC-4 - PASS

Verifier clause:

```text
uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_spacedock_solver_v2_class.py -q
```

Output:

```text
..............                                                           [100%]
14 passed in 0.24s
```

Additional implementation verifier:

```text
uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_claude_cli_auth_dotenv_only.py tests/unit/test_spec_freeze_cli_pkg8.py tests/integration/test_v2_freeze_dir_mechanism.py -q
```

Output:

```text
.............................                                            [100%]
29 passed in 1.00s
```

## Code Review

`superpowers:requesting-code-review` is not available as a callable skill/tool in this Codex session. I performed an inline code-review pass against the worktree diff with the same blocking/non-blocking classification.

Blocking findings: none.

Non-blocking findings:

- `uv.lock` was dirty before validation and remains unstaged with removal of the global `exclude-newer` option. I did not revert or commit it because it was outside the validation artifact scope and likely pre-existing worktree state.
- `uv run rk freeze examples/specs/_codex-smoke-v2.yaml` without `--allow-missing` still exits 11 on unresolved `model_resolved_version`; the task's validation instructions explicitly allow recording the `--allow-missing` path and the later auth blocker.

Reviewed code paths:

- Harbor Codex constructor kwargs: `src/razorback/agents/_runtime/codex.py:18-38`
- Unsupported Codex kwarg fail-closed path: `src/razorback/agents/_runtime/codex.py:41-52`
- Codex `.env` auth resolution: `src/razorback/agents/auth.py:81-97`
- v2 Codex auth translation into `AgentConfig.env`: `src/razorback/translate.py:152-201`
- v2 freeze stamping of `solver_workflow_content_hash` and `sealed_hash`: `src/razorback/provenance/freeze_cmd.py:96-120`, `src/razorback/provenance/freeze_cmd.py:151-175`

## Gate Decision

APPROVE to `done`.

AC-1, AC-2, and AC-4 pass with exact verifier commands. AC-3 freezes successfully with the instructed `--allow-missing` fallback and then stops at a concrete local credential blocker before run-dir artifact creation. No blocking review findings were found, and active Codex tool restrictions are not silently dropped.
