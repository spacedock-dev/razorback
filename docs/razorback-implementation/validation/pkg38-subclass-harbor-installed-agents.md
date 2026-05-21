# PKG-38 Validation Report

Entity: `docs/razorback-implementation/pkg38-subclass-harbor-installed-agents.md`

Branch: `spacedock-ensign/pkg38-subclass-harbor-installed-agents`

Worktree: `/home/exedev/razorback/.worktrees/spacedock-ensign-pkg38-subclass-harbor-installed-agents`

Validator logical worker id: `spacedock:ensign`

Role asset read: `/home/exedev/.codex/plugins/cache/spacedock/spacedock/0.12.0/skills/ensign/SKILL.md`

## Acceptance Criteria

### AC-1 - PASS

Codex runtime stays subclass-first.

Verified by: `uv run --frozen pytest tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q`

Evidence:

```text
$ uv run --frozen pytest tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q
.......................                                                  [100%]
23 passed in 0.26s
```

Review evidence:

- `src/razorback/agents/_runtime/codex.py` defines `RazorbackCodex(Codex)`.
- `RazorbackCodex.install()` delegates to `super().install(environment)`.
- Retained Codex overrides document the upstream method and benchmark reason.

### AC-2 - FAIL

Claude runtime stops avoidable parallel CLI wrapping.

Verified by: `uv run --frozen pytest tests/unit/test_claude_cli_*.py tests/unit/test_translate_spacedock_solver_import_path.py -q`

Evidence for the focused command:

```text
$ uv run --frozen pytest tests/unit/test_claude_cli_*.py tests/unit/test_translate_spacedock_solver_import_path.py -q
......................................                                   [100%]
38 passed in 0.56s
```

Additional generator coverage requested by the validation assignment:

```text
$ uv run --frozen pytest tests/unit/test_claude_benchmark_spec_generator.py tests/unit/test_codex_benchmark_spec_generator.py -q
..........                                                               [100%]
10 passed in 0.13s
```

Independent inspection found a compatibility regression not covered by the
focused AC command. The new `claude-cli` shim rejects any legacy
`sampling.seed` or `sampling.top_p` in `src/razorback/translate.py:216-224`.
Existing legacy specs still carry unsupported sampling metadata that the old
translator ignored, for example `examples/specs/_deterministic-smoke.yaml:8-10`
sets `temperature: 0.0` and `seed: 1`.

Full-suite evidence:

```text
$ uv run --frozen pytest -q
FAILED tests/integration/test_budget_gate_two_invocations.py::test_two_sequential_invocations_second_refuses
FAILED tests/integration/test_budget_gate_two_invocations.py::test_without_flag_regression_against_smoke
FAILED tests/integration/test_rk_run_v2_deterministic_smoke.py::test_deterministic_smoke_runs_end_to_end
...
stderr=SpecError: legacy agent.kind: claude-cli now routes to Harbor ClaudeCode, which has no temperature/top_p/seed sampling kwarg; keep sampling at its default no-op values.
...
6 failed, 531 passed, 10 skipped, 4 warnings in 40.43s
```

Because the branch makes checked-in legacy `claude-cli` smoke specs fail before
execution, AC-2's compatibility-shim requirement is not satisfied.

### AC-3 - PASS

Solver lifecycle preserves sealed input and checkpoint contracts.

Verified by: `uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_spacedock_solver_v2_lifecycle.py tests/unit/test_spec_freeze_cli_pkg8.py tests/integration/test_v2_freeze_dir_mechanism.py -q`

Evidence:

```text
$ uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_spacedock_solver_v2_lifecycle.py tests/unit/test_spec_freeze_cli_pkg8.py tests/integration/test_v2_freeze_dir_mechanism.py -q
...................................                                      [100%]
35 passed in 1.06s
```

Review evidence:

- The branch changes tests around sealed hashes and freeze CLI parity.
- `tests/integration/test_v2_freeze_dir_mechanism.py` remains in both AC-1 and
  AC-3 commands and passed, covering the `_razorback/freeze/<sealed_hash>`
  freeze-dir contract.
- No production changes moved sealed-hash computation, freeze-dir resolution, or
  checkpoint labels out of `spacedock_solver_v2`.

### AC-4 - PASS

Upstream divergence is documented where it remains.

Verified by: validator inspection plus the focused pytest commands above.

Inspection command:

```text
$ rg -n "class Razorback|def install|def setup|def run|def build_cli_flags" src/razorback/agents
src/razorback/agents/spacedock_solver.py:180:    async def setup(self, environment: BaseEnvironment) -> None:
src/razorback/agents/spacedock_solver.py:208:    async def run(
src/razorback/agents/claude_cli.py:98:    async def setup(self, environment: BaseEnvironment) -> None:
src/razorback/agents/claude_cli.py:108:    async def run(
src/razorback/agents/_runtime/codex.py:21:class RazorbackCodex(Codex):
src/razorback/agents/_runtime/codex.py:24:    def build_cli_flags(self) -> str:
src/razorback/agents/_runtime/codex.py:31:    async def install(self, environment: BaseEnvironment) -> None:
src/razorback/agents/_runtime/claude.py:23:class RazorbackClaudeCode(ClaudeCode):
src/razorback/agents/spacedock_solver_v2.py:343:    async def setup(self, environment: BaseEnvironment) -> None:
src/razorback/agents/spacedock_solver_v2.py:403:    async def run(self, instruction, environment, context):
```

Review evidence:

- `RazorbackCodex.build_cli_flags()` comments name `Codex.build_cli_flags` and
  the offline benchmark reason.
- `RazorbackCodex.install()` comments name `Codex.install` and the benchmark
  proxy-clearing reason.
- `RazorbackClaudeCode` introduces no retained Harbor method overrides.

## Full-Suite Validation

The workflow validation guidance asks for `uv run pytest` from a clean worktree.
The branch does not pass the full frozen suite:

```text
$ uv run --frozen pytest -q
FAILED tests/integration/test_budget_gate_two_invocations.py::test_two_sequential_invocations_second_refuses
FAILED tests/integration/test_budget_gate_two_invocations.py::test_without_flag_regression_against_smoke
FAILED tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end
FAILED tests/integration/test_rk_run_v2_deterministic_smoke.py::test_deterministic_smoke_runs_end_to_end
FAILED tests/unit/test_spacedock_registry.py::test_existing_kinds_still_resolve
FAILED tests/unit/test_tools_denied_claude_hook.py::test_claude_runtime_installs_four_dab_denials_verbatim_in_order
6 failed, 531 passed, 10 skipped, 4 warnings in 40.43s
```

Standalone confirmation for two stale expectation failures:

```text
$ uv run --frozen pytest tests/unit/test_spacedock_registry.py::test_existing_kinds_still_resolve tests/unit/test_tools_denied_claude_hook.py::test_claude_runtime_installs_four_dab_denials_verbatim_in_order -q
FF                                                                       [100%]
...
E       AssertionError: assert 'razorback.ag...ackClaudeCode' == 'razorback.ag...laudeCliAgent'
...
E       AssertionError: assert 'RazorbackClaudeCode' == 'ClaudeCode'
2 failed in 0.21s
```

Run-dir contract spot-check:

```text
$ uv run --frozen pytest tests/integration/test_rk_run_nop.py -q
F.                                                                       [100%]
...
E       AssertionError: events.jsonl is empty
1 failed, 1 passed in 18.84s
```

The nop run-dir failure is not obviously caused by the PKG-38 diff, but it means
the required full-suite validation is not clean.

## Code Review Findings

### Blocking

1. `src/razorback/translate.py:216-224` rejects legacy `claude-cli`
   `sampling.seed`/`sampling.top_p` values, but existing legacy smoke specs such
   as `examples/specs/_deterministic-smoke.yaml:8-10` still include `seed: 1`.
   The old translator ignored unsupported seed/top_p fields, so this branch
   breaks legacy compatibility and causes budget-gate and deterministic-smoke
   integration tests to fail before execution. Concrete fix: make the shim
   preserve old no-op compatibility for seed/top_p while still refusing active
   unsupported temperature changes, or migrate all affected specs/tests to a
   supported non-legacy solver path in the same branch.

2. The full frozen test suite is not green. Two failures are stale expectations
   for the intended PKG-38 import/class change:
   `tests/unit/test_spacedock_registry.py:102-105` still expects
   `razorback.agents.claude_cli:ClaudeCliAgent`, and
   `tests/unit/test_tools_denied_claude_hook.py:46-53` still expects the exact
   class name `ClaudeCode` instead of accepting the Harbor subclass. Concrete
   fix: update these tests to assert the Harbor-backed subclass contract.

3. `tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end` fails
   because `events.jsonl` is empty. I did not find a direct PKG-38 diff to the
   nop runner path, but the workflow's full-suite validation remains failed
   until this is fixed or explicitly accepted as an unrelated baseline issue.

### Non-Blocking

None.

## Gate Decision

REJECTED back to implementation.

Required fixes before re-validation:

1. Restore legacy `claude-cli` compatibility for checked-in specs carrying
   no-op unsupported sampling metadata, or migrate those specs/tests in this
   branch.
2. Update stale tests that still assert the pre-PKG-38 `ClaudeCliAgent` import
   path or exact `ClaudeCode` class name.
3. Make `uv run --frozen pytest -q` green, or provide an accepted baseline note
   for any unrelated full-suite failure.
4. Re-run the three AC commands plus the generator-focused tests.
