# PKG-38 Post-Feedback Validation Report

Entity: `docs/razorback-implementation/pkg38-subclass-harbor-installed-agents.md`

Branch: `spacedock-ensign/pkg38-subclass-harbor-installed-agents`

Worktree: `/home/exedev/razorback/.worktrees/spacedock-ensign-pkg38-subclass-harbor-installed-agents`

Validator logical worker id: `spacedock:ensign`

Role asset read: `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/ensign/SKILL.md`

Workflow status check: `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/commission/bin/status --workflow-dir /home/exedev/razorback/.worktrees/spacedock-ensign-pkg38-subclass-harbor-installed-agents/docs/razorback-implementation` listed `pkg38-subclass-harbor-installed-agents` as `validation`.

## Acceptance Criteria

### AC-1 - PASS

Codex runtime stays subclass-first.

Verified by:

```text
$ uv run --frozen pytest tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q
.......................                                                  [100%]
23 passed in 0.25s
```

Inspection evidence: `src/razorback/agents/_runtime/codex.py` defines `RazorbackCodex(Codex)`, delegates install to `super().install(environment)`, and documents retained overrides against upstream `Codex.build_cli_flags`, `Codex.install`, and installed-agent exec helpers.

### AC-2 - PASS

Claude runtime stops avoidable parallel CLI wrapping.

Verified by:

```text
$ uv run --frozen pytest tests/unit/test_claude_cli_*.py tests/unit/test_translate_spacedock_solver_import_path.py -q
.......................................                                  [100%]
39 passed in 0.53s
```

Post-feedback compatibility confirmation:

```text
$ uv run --frozen pytest tests/unit/test_claude_cli_compat_shim.py::test_legacy_claude_cli_ignores_seed_and_top_p_metadata -q
.                                                                        [100%]
1 passed in 0.15s
```

Inspection evidence: `src/razorback/translate.py` now only rejects non-default legacy `sampling.temperature`; it no longer rejects no-op legacy `seed` or `top_p` metadata. `tests/unit/test_claude_cli_compat_shim.py` asserts a legacy `claude-cli` spec with `seed: 1` and `top_p: 0.9` translates to `razorback.agents._runtime.claude:RazorbackClaudeCode` with unsupported sampling kwargs dropped.

### AC-3 - PASS

Solver lifecycle preserves sealed input and checkpoint contracts.

Verified by:

```text
$ uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_spacedock_solver_v2_lifecycle.py tests/unit/test_spec_freeze_cli_pkg8.py tests/integration/test_v2_freeze_dir_mechanism.py -q
...................................                                      [100%]
35 passed in 0.97s
```

Inspection evidence: the branch does not move sealed-hash computation, freeze-dir resolution, or checkpoint labels out of `spacedock_solver_v2`; the freeze-dir integration test is included in both AC-1 and AC-3 commands and passed.

### AC-4 - PASS

Upstream divergence is documented where it remains.

Verified by validator inspection plus focused pytest commands above.

Inspection evidence: `RazorbackCodex.build_cli_flags()` comments name `Codex.build_cli_flags` and the offline benchmark reason; `RazorbackCodex.install()` names `Codex.install` and the benchmark proxy-clearing reason; `exec_as_root()` and `exec_as_agent()` document the same install-only proxy constraint. `RazorbackClaudeCode` is a Harbor `ClaudeCode` subclass with no retained Harbor method overrides.

Additional focused assignment command:

```text
$ uv run --frozen pytest tests/unit/test_claude_benchmark_spec_generator.py tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_spacedock_registry.py::test_existing_kinds_still_resolve tests/unit/test_tools_denied_claude_hook.py::test_claude_runtime_installs_four_dab_denials_verbatim_in_order -q
............                                                             [100%]
12 passed in 0.26s
```

This confirms the stale assertions from the first rejection were updated: `claude-cli` resolves to `RazorbackClaudeCode`, and the tools-denied test accepts `RazorbackClaudeCode` as a Harbor `ClaudeCode` subclass.

## Full-Suite Validation

Full frozen suite result:

```text
$ uv run --frozen pytest -q
FAILED tests/integration/test_budget_gate_two_invocations.py::test_two_sequential_invocations_second_refuses
FAILED tests/integration/test_budget_gate_two_invocations.py::test_without_flag_regression_against_smoke
FAILED tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end
FAILED tests/integration/test_rk_run_v2_deterministic_smoke.py::test_deterministic_smoke_runs_end_to_end
4 failed, 534 passed, 10 skipped, 4 warnings in 34.61s
```

Credential-dependent failures classified as environmental:

```text
AuthDiscoveryError: no claude credentials found. Add ANTHROPIC_API_KEY to /home/exedev/razorback/.worktrees/spacedock-ensign-pkg38-subclass-harbor-installed-agents/.env or write a token to /home/exedev/.claude/benchmark-token.
```

Independent credential check:

```text
$ if [ -n "${ANTHROPIC_API_KEY:-}" ]; then echo ANTHROPIC_API_KEY=present; else echo ANTHROPIC_API_KEY=absent; fi
ANTHROPIC_API_KEY=absent
$ if [ -f /home/exedev/.claude/benchmark-token ]; then echo benchmark-token=present; else echo benchmark-token=absent; fi
benchmark-token=absent
$ if [ -f .env ] && grep -q '^ANTHROPIC_API_KEY=' .env; then echo worktree-env-key=present; else echo worktree-env-key=absent; fi
worktree-env-key=absent
```

The three Claude live failures are therefore environmental in this VM. They occur after the compatibility-shim fix, not as `SpecError`.

NOP empty-events failure classified as unrelated baseline:

```text
tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end
E       AssertionError: events.jsonl is empty
```

Diff check:

```text
$ git diff --exit-code main...HEAD -- src/razorback/_legacy/run.py src/razorback/cli src/razorback/runs examples/specs/nop.yaml tests/integration/test_rk_run_nop.py
```

The diff check produced no output and exited 0. The PKG-38 branch does not touch the NOP spec, NOP integration test, legacy runner, CLI package, or runs package paths implicated by this failure.

## Code Review Findings

No blocking findings.

Residual risks:

1. Full-suite validation is not green in this VM because live Claude credentials are absent.
2. `test_rk_run_nop_end_to_end` still exposes the pre-existing empty `events.jsonl` baseline, but PKG-38 does not touch that path.

## Gate Decision

PASS. Approve PKG-38 to `done`, with the full-suite residuals classified as environmental or unrelated baseline issues outside this task's diff.
