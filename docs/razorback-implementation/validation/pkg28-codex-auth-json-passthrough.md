# PKG-28 Validation

Branch: `spacedock-ensign/pkg28-codex-auth-json-passthrough`
Worktree: `<worktree>`

## Command Evidence

Targeted implementation tests:

```text
uv run pytest tests/unit/test_claude_cli_auth_dotenv_only.py tests/integration/test_v2_freeze_dir_mechanism.py -q
```

Output:

```text
...................                                                      [100%]
19 passed in 0.23s
```

Focused lint:

```text
uv run ruff check src/razorback/agents/auth.py src/razorback/translate.py tests/unit/test_claude_cli_auth_dotenv_only.py tests/integration/test_v2_freeze_dir_mechanism.py
```

Output:

```text
All checks passed!
```

Unit sweep:

```text
uv run pytest tests/unit -q
```

Output summary:

```text
481 passed in 5.38s
```

## Acceptance Criteria

### AC-1 - PASS

Verifier clause:

```text
unit tests cover `.env` API-key precedence, explicit `CODEX_AUTH_JSON_PATH`, and default home auth-file fallback.
```

Command:

```text
uv run pytest tests/unit/test_claude_cli_auth_dotenv_only.py -q
```

Covered by the targeted command above as part of the 19-test run. The new unit coverage exercises API-key precedence over a home auth file, explicit `CODEX_AUTH_JSON_PATH`, default `<home>/.codex/auth.json`, and missing credentials text.

Code review anchors:

```text
src/razorback/agents/auth.py:92-138
tests/unit/test_claude_cli_auth_dotenv_only.py:82-153
```

### AC-2 - PASS

Verifier clause:

```text
a translator test builds a Codex v2 job config with a temporary home containing `.codex/auth.json` and asserts `AgentConfig.env["CODEX_AUTH_JSON_PATH"]` points at that file.
```

Command:

```text
uv run pytest tests/integration/test_v2_freeze_dir_mechanism.py -q
```

Covered by the targeted command above as part of the 19-test run. `test_translator_uses_codex_auth_json_for_codex_runtime` builds a `spacedock_solver_v2` Codex spec, passes a temp `home`, and asserts `agent_cfg.env == {"CODEX_AUTH_JSON_PATH": str(auth_path)}`.

Code review anchors:

```text
src/razorback/translate.py:161-162
tests/integration/test_v2_freeze_dir_mechanism.py:210-253
```

### AC-3 - PASS

Verifier clause:

```text
unit test for missing credentials.
```

Command:

```text
uv run pytest tests/unit/test_claude_cli_auth_dotenv_only.py tests/integration/test_v2_freeze_dir_mechanism.py -q
```

Output:

```text
19 passed in 0.23s
```

Missing-credential coverage is present in both `test_codex_auth_missing_credentials_message_names_supported_options` and `test_translator_codex_runtime_fails_without_credentials`. Both assert the raised `AuthDiscoveryError` message names `OPENAI_API_KEY`, `CODEX_AUTH_JSON_PATH`, and `.codex/auth.json`.

### AC-4 - PASS

Freeze command:

```text
uv run rk freeze examples/specs/_codex-smoke-v2.yaml --allow-missing
```

Output:

```text
wrote examples/specs/_codex-smoke-v2.frozen.yaml
wrote examples/specs/provenance.yaml
```

Run command:

```text
uv run rk run examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir runs/pkg28-codex-auth-smoke --allow-plugin-drift --allow-alias-drift
```

Output summary:

```text
1/1 Mean: 0.000
Trials: 0
Exceptions: 1
Mean: 0.000
Exception: SpacedockSolverAgentError Count: 1
Total runtime: 14s
Results written to <worktree>/runs/pkg28-codex-auth-smoke/_codex-smoke-v2/48ec13559b2746a5/result.json
```

Exact later-stage failure, with the worktree path scrubbed:

```text
SpacedockSolverAgentError: resume restore via git checkout failed at <worktree>/runs/pkg28-codex-auth-smoke/_codex-smoke-v2/_razorback/freeze/cdfe61ef1efa1d4f4504af3aaa3061b1 (rc=127)
```

This is past Razorback auth preflight and not an `AuthDiscoveryError`.

Run-dir contract check: the latest smoke run wrote `manifest.json`, `summary.json`, `result.json`, `provenance.yaml`, `spec.frozen.yaml`, `_job_config.yaml`, `events.jsonl`, `per_trial_outcomes.json`, `job.log`, `lock.json`, and per-trial `config.json`, `result.json`, `trial.log`, and `exception.txt`. `manifest.json` reports `run_dir_version: 1`, `n_trials_total: 1`, `n_trials_completed: 0`, `n_trials_errored: 1`, and `per_trial_paths: ["hello-world__NvhXuS6"]`. `summary.json` reports `summary_version: 1`, `n_trials_total: 1`, `n_trials_completed: 0`, `n_trials_errored: 1`, and trial `error_reason: "SpacedockSolverAgentError"`.

## Secret Leakage Review

Tracked-file scan:

```text
git grep -n -E '"(access|refresh|id)_token"|Bearer |sk-proj-|sk-[A-Za-z0-9_-]{20,}' -- src tests docs/razorback-implementation/pkg28-codex-auth-json-passthrough.md
```

Output:

```text
tests/integration/test_no_auth_leak_in_run_dir.py:14:GREP_SENTINEL = "sk-ant-TEST-SENTINEL-FU1-DO-NOT-USE-XYZ123"
```

The only token-shaped tracked hit is an existing sentinel fixture. The PKG-28 diff passes auth file paths through `AgentConfig.env`; it does not read or serialize auth JSON contents into tracked source, tests, or docs. The smoke run-dir is ignored/untracked, and this report records only scrubbed paths and exception classes.

## Code Review

`superpowers:requesting-code-review` is not available as a callable skill/tool in this Codex session. I performed an inline code-review pass against the worktree diff with the same blocking/non-blocking classification.

Blocking findings: none.

Non-blocking findings:

- `resolve_codex_auth` silently falls through from an unreadable explicit `CODEX_AUTH_JSON_PATH` to default home auth if present. This is not an AC violation because the AC only requires supported credential options and clear failure when none are present, but a future UX hardening task could choose to fail specifically on a configured-but-unreadable explicit path.

Reviewed code paths:

```text
src/razorback/agents/auth.py:92-138
src/razorback/translate.py:161-162
tests/unit/test_claude_cli_auth_dotenv_only.py:82-153
tests/integration/test_v2_freeze_dir_mechanism.py:210-295
```

## Gate Decision

APPROVE to `done`.

AC-1 through AC-3 pass with focused unit/integration coverage and the unit sweep is green. AC-4 reaches Harbor/Codex execution and fails later with `SpacedockSolverAgentError`, not `AuthDiscoveryError`. No blocking code-review findings or tracked secret-leakage findings were found.
