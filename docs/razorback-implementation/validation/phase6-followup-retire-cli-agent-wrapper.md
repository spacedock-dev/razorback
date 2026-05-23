# Validation Report - Phase 6 follow-up: retire standalone CLI agent wrapper

- Entity: `phase6-followup-retire-cli-agent-wrapper`
- Branch: `spacedock-ensign/phase6-followup-retire-cli-agent-wrapper`
- Worktree: `/home/exedev/razorback/.worktrees/spacedock-ensign-phase6-followup-retire-cli-agent-wrapper`
- Implementation commits reviewed: `c9343b6`, `34251d2`, `0123bea`
- Validation-state commit present before validation: `3e6ab8d`
- Review range: `8611e34..0123bea`

## Gate Decision

PASSED. Approve to `done`.

## Acceptance Criteria

### AC-1 - Runtime adapter no longer imports the standalone wrapper: PASS

Verified by:

```bash
rg -n "ClaudeCliAgent|agents\.claude_cli" src/razorback/agents/_runtime src/razorback/translate.py
```

Result: exit code `1`, stdout empty, stderr empty. This is the expected no-hit result for the active runtime adapter and translator paths.

Broader wrapper-reference rationale:

```bash
rg -n "from razorback\.agents\.claude_cli|import razorback\.agents\.claude_cli|razorback\.agents\.claude_cli" src tests
```

Result:

```text
tests/fixtures/score/baseline_rerun_bookreview/bookreview-q3__dBAPNbE/result.json:31:            "import_path": "razorback.agents.claude_cli:ClaudeCliAgent",
src/razorback/_legacy/compat/harbor_0_6_6.py:164:            import_path="razorback.agents.claude_cli:ClaudeCliAgent",
tests/fixtures/score/baseline_rerun_bookreview/bookreview-q1__xgRg3Eo/result.json:31:            "import_path": "razorback.agents.claude_cli:ClaudeCliAgent",
tests/fixtures/score/baseline_rerun_bookreview/bookreview-q2__qg7aPaZ/result.json:31:            "import_path": "razorback.agents.claude_cli:ClaudeCliAgent",
```

These are allowed historical references: one `_legacy` compat archive and three score fixtures. The remaining `ClaudeCliAgentBlock` symbol in `src/razorback/spec/schema.py` is the legacy `agent.kind: claude-cli` schema discriminator, not an import or active standalone wrapper.

### AC-2 - Standalone wrapper is legacy-only: PASS

Entity `Verified by` command:

```bash
test -e src/razorback/agents/claude_cli.py
```

Result: exit code `1`, stdout empty, stderr empty.

Required negated check:

```bash
test ! -e src/razorback/agents/claude_cli.py
```

Result: exit code `0`, stdout empty, stderr empty.

The historical file is retained under `src/razorback/_legacy/agents/claude_cli.py` and is not imported by active runtime or translator code.

### AC-3 - Tool policy and cost/audit behavior survive: PASS

Verified by:

```bash
uv run pytest tests/unit/test_runtime_adapters.py tests/unit/test_tools_denied_claude_hook.py -q
```

Result:

```text
..................                                                       [100%]
18 passed in 0.23s
```

This focused suite covers construction of `RazorbackClaudeCode`, Harbor `ClaudeCode` subclassing, unsupported kwarg refusal, default and explicit tool-denial behavior, auth env passthrough, and the `claude-output.jsonl` audit sentinel publication path.

## Additional Checks

Compatibility/proxy/auth regression suite:

```bash
uv run pytest tests/unit/test_claude_cli_compat_shim.py tests/unit/test_claude_cli_translator_proxy.py tests/unit/test_claude_cli_setup_env_scrub.py tests/unit/test_claude_cli_kwarg_mapping.py tests/unit/test_claude_cli_version.py tests/unit/test_claude_cli_required_env.py tests/unit/test_claude_cli_supported_sampling.py tests/unit/test_ade_bench_missing_tool_graceful_error.py -q
```

Result:

```text
..........................                                               [100%]
26 passed in 0.53s
```

Runtime import-path smoke:

```bash
uv run python - <<'PY'
import importlib
module = importlib.import_module("razorback.agents._runtime.claude")
cls = getattr(module, "RazorbackClaudeCode")
print(cls.__name__)
PY
```

Result:

```text
Resolving despite existing lockfile due to removal of global exclude newer
RazorbackClaudeCode
```

Full suite:

```bash
uv run pytest
```

Result:

```text
576 passed, 12 skipped, 16 warnings in 52.82s
```

Diff hygiene:

```bash
git diff --check 8611e34..0123bea
```

Result: exit code `0`, stdout empty, stderr empty.

## Run-Dir Contract

This entity does not produce a new benchmark run-dir. The relevant spec section 7 surface is the Claude audit/cost artifact path from the runtime helper into run-dir trials. Validation covered that contract through the focused runtime adapter test that calls `populate_context_post_run()`, delegates to Harbor `ClaudeCode.populate_context_post_run()`, and verifies `claude-output.jsonl` is published from `claude-code.txt`.

## Code Review

Requested protocol: `superpowers:requesting-code-review`. The skill is not registered as a callable Codex tool in this session, so I read the cached instructions at `/home/exedev/.codex/.tmp/plugins/plugins/superpowers/skills/requesting-code-review/SKILL.md` and applied the supplied review checklist manually.

Scope reviewed: implementation diff `8611e34..0123bea`, with production focus on `src/razorback/agents/_runtime/claude.py`, `src/razorback/translate.py`, the legacy file move, and retargeted tests.

Blocking findings: none.

Non-blocking findings: none.

Assessment: ready to merge. The implementation preserves the old wrapper behavior in `RazorbackClaudeCode`, removes active imports from `_runtime` and `translate.py`, sidelines the old file under `_legacy`, and has direct regression coverage for auth, proxy, tool-denial, import-path compatibility, version capture, and audit sentinel behavior.
