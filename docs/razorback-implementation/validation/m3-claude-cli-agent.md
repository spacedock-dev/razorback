# Validation — M3 — ClaudeCliAgent end-to-end

Worktree branch: `spacedock-ensign/m3-claude-cli-agent`
Tip commit at validation start: `e49ec8c` (`m3: cross-reference plan + implementation stage report`)
Validator: fresh agent, did not write the implementation
Acceptance command (§8.M3): `uv run rk run examples/specs/bookreview-claude.yaml`

## Reproduction summary

From a clean checkout of the worktree branch tip:

- `uv run pytest` → **`1 failed, 72 passed` in `474.03s`** (NOT all-green as the implementation stage report claimed).
  - The single failure is `tests/integration/test_claude_cli_smoke_bookreview.py::test_claude_cli_smoke_writes_numeric_reward`. Detail below in §Code review / Blocking.
- `uv run rk run examples/specs/bookreview-claude.yaml` → exit `0`, writes `_runs/m3-bookreview-claude/b56a04708f93ccf6/` with a `summary.json` showing **`bookreview.dataset_pass_at_1: 1.0` (3/3 correct)**, 5:49 wallclock against the host `claude` CLI v2.1.142 and OAuth via `~/.claude/benchmark-token`.

The 73 collected tests decompose into 44 M1+M2 carried forward (17 M1 + 27 M2) plus 29 new M3 tests (27 unit + 2 integration: `test_claude_cli_smoke_bookreview.py` + `test_rk_run_bookreview_claude.py`). 27 of the 29 M3 unit tests pass. The smoke-test failure is in M3's own Task-1 risk-first integration test.

## AC verification

Each AC reproduced against the worktree-branch tip.

### AC-1 — `ClaudeCliAgent` declares its required env vars via harbor's required-env mechanism — PASS

`Verified by:` "a unit test inspects the agent class's required-env declaration and asserts it lists either `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` (alternation, not both required)."

Tests:
- `tests/unit/test_claude_cli_required_env.py::test_required_env_lists_exactly_the_two_auth_alternates` — PASSED
- `tests/unit/test_claude_cli_required_env.py::test_required_env_is_a_class_method_callable_without_instance` — PASSED

`src/razorback/agents/claude_cli.py:92-98` returns `{"mode": "alternation", "names": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]}`. The alternation key is the declaration shape — not `required: [BOTH]`. AC-1 verbatim met.

### AC-2 — `setup()` scrubs env, injects exactly the chosen auth token, never co-mingles — PASS (with note)

`Verified by:` "a unit test exercises `setup()` with both env vars present and asserts only `ANTHROPIC_API_KEY` reaches the agent process (precedence rule from `run_experiment.py:1995-2003`); a second test asserts `CLAUDE_CODE_OAUTH_TOKEN` is injected when only it is present."

Tests:
- `tests/unit/test_claude_cli_setup_env_scrub.py::test_setup_with_only_api_key_carries_only_api_key` — PASSED
- `tests/unit/test_claude_cli_setup_env_scrub.py::test_setup_with_only_oauth_carries_only_oauth` — PASSED
- `tests/unit/test_claude_cli_setup_env_scrub.py::test_setup_refuses_to_co_mingle` — PASSED
- `tests/unit/test_claude_cli_setup_env_scrub.py::test_setup_carries_proxy_block_into_exec_env` — PASSED
- `tests/unit/test_claude_cli_setup_env_scrub.py::test_setup_validates_claude_binary_inside_container` — PASSED
- `tests/unit/test_claude_cli_auth_dotenv_only.py::test_never_co_mingles_both` — PASSED (the precedence test that mirrors `run_experiment.py:1995-2003` verbatim)

**Note on AC-2 letter vs spirit.** The AC literally asks setup() to silently pick API_KEY when both are present. The implementation hardens this: the `ClaudeCliAgent` constructor raises `ClaudeCliAgentError` when both names are in `resolved_auth_env` (`claude_cli.py:60-64`). Precedence-based filtering lives one layer up in `auth.py:resolve_claude_auth` (`auth.py:57-62`) — which DOES match the `run_experiment.py:1995-2003` precedence rule (API_KEY from .env first; fall back to OAuth token; never both). Together: through the documented entry path (parse spec → `spec_to_job_config` → `resolve_claude_auth` → `ClaudeCliAgent(...)`), the constructor never sees both. The AC's spirit ("only one ever reaches the agent process") holds; the AC's letter ("setup() with both present") is met by upstream filtering + constructor refusal, not by setup-internal precedence. Non-blocking — the underlying invariant is stronger than the AC, not weaker.

### AC-3 — Auth tokens loaded from project-root `.env` via `dotenv_values`, not `os.environ` — PASS

`Verified by:` "a unit test using `monkeypatch` to set a process-env value confirms the agent does NOT pick it up unless it is also declared in `.env` — matches the `run_experiment.load_env_api_key()` discipline."

Tests:
- `tests/unit/test_claude_cli_auth_dotenv_only.py::test_anthropic_api_key_from_dotenv_wins` — PASSED
- `tests/unit/test_claude_cli_auth_dotenv_only.py::test_falls_back_to_oauth_when_dotenv_lacks_api_key` — PASSED
- `tests/unit/test_claude_cli_auth_dotenv_only.py::test_never_co_mingles_both` — PASSED
- `tests/unit/test_claude_cli_auth_dotenv_only.py::test_os_environ_is_not_a_source` — PASSED (monkeypatches ANTHROPIC_API_KEY + CLAUDE_CODE_OAUTH_TOKEN into os.environ with empty .env and no token file; expects `AuthDiscoveryError` to be raised — proving the process-env value is NOT picked up)
- `tests/unit/test_claude_cli_auth_dotenv_only.py::test_raises_when_neither_source_has_credentials` — PASSED
- `tests/unit/test_claude_cli_auth_dotenv_only.py::test_anthropic_api_key_in_dotenv_with_empty_value_is_treated_as_missing` — PASSED

`src/razorback/agents/auth.py:28-35` uses `dotenv_values(env_path).get("ANTHROPIC_API_KEY")` exclusively for the API-key source — `os.environ` is never read. The discipline is copied verbatim from `run_experiment.py:1905-1917`. AC-3 verbatim met.

### AC-4 — `version()` returns the `claude` CLI version reported by `claude --version` — PASS

`Verified by:` "a unit test mocks `subprocess.run('claude --version')` and asserts the parsed string flows through `version()`."

Tests:
- `tests/unit/test_claude_cli_version.py::test_version_parses_claude_cli_output` — PASSED
- `tests/unit/test_claude_cli_version.py::test_version_returns_none_on_cli_missing` — PASSED
- `tests/unit/test_claude_cli_version.py::test_version_returns_none_on_nonzero_exit` — PASSED

`src/razorback/agents/claude_cli.py:77-90` invokes `subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)` and returns `result.stdout.strip()` on success (caches it). The test asserts `["claude", "--version"]` is the argv. AC-4 verbatim met.

Live host invocation as cross-check: `claude --version` → `2.1.142 (Claude Code)`. The acceptance run consumed this binary end-to-end.

### AC-5 — `supported_sampling()` returns exactly `{"temperature"}` — PASS

`Verified by:` "a unit test asserts the returned set is `{"temperature"}` — no `top_p`, no `seed`."

Tests:
- `tests/unit/test_claude_cli_supported_sampling.py::test_supported_sampling_is_exactly_temperature` — PASSED
- `tests/unit/test_claude_cli_supported_sampling.py::test_supported_sampling_omits_top_p_and_seed` — PASSED

`src/razorback/agents/claude_cli.py:100-103` returns `{"temperature"}`. AC-5 verbatim met.

### AC-6 — End-to-end bookreview run produces a non-zero score — PASS

`Verified by:` "`uv run rk run examples/specs/bookreview-claude.yaml` against the real `claude` CLI produces a `summary.json` whose bookreview pass@1 is strictly greater than 0.0."

Live acceptance command (validator's clean run, NOT the implementation's):

```
$ uv run rk run examples/specs/bookreview-claude.yaml
[start] trial=bookreview-q1__NaZxi4s task=razorback/bookreview-q1
[environment_start] trial=bookreview-q1__NaZxi4s task=razorback/bookreview-q1
Starting step 1/1: main
[agent_start] trial=bookreview-q1__NaZxi4s task=razorback/bookreview-q1
[verification_start] trial=bookreview-q1__NaZxi4s task=razorback/bookreview-q1
[end] trial=bookreview-q1__NaZxi4s task=razorback/bookreview-q1
[start] trial=bookreview-q2__f8ChUPP ...
[end] trial=bookreview-q2__f8ChUPP ...
[start] trial=bookreview-q3__BxMNznZ ...
[end] trial=bookreview-q3__BxMNznZ ...
  3/3 Mean: 1.000 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0:05:49 0:00:00
EXIT=0
```

`summary.json` in the validator's run-dir (`_runs/m3-bookreview-claude/b56a04708f93ccf6/summary.json`):

```json
{
  "summary_version": 1,
  "stratified_pass_at_1": 1.0,
  "datasets": {
    "bookreview": {
      "dataset_pass_at_1": 1.0,
      "n_queries": 3,
      "queries": [
        {"query_id": 1, "n_trials": 1, "n_correct": 1, "pass_at_1": 1.0},
        {"query_id": 2, "n_trials": 1, "n_correct": 1, "pass_at_1": 1.0},
        {"query_id": 3, "n_trials": 1, "n_correct": 1, "pass_at_1": 1.0}
      ]
    }
  }
}
```

`bookreview.dataset_pass_at_1 = 1.0`, strictly greater than `0.0`. All three queries passed on a single trial each. AC-6 verbatim met — beyond the strict-> 0.0 bar by a margin (perfect score).

Also covered by `tests/integration/test_rk_run_bookreview_claude.py::test_rk_run_bookreview_claude_produces_nonzero_score` — PASSED in 1:42 wallclock during the `uv run pytest` rerun.

### AC-7 — Agent runs in harbor's docker environment with the proxy block from `run_experiment.py:1497-1525` — PASS

`Verified by:` "a unit test inspecting the spec → JobConfig translator's output for a claude DAB spec asserts the `EnvironmentConfig.env` block contains the proxy lock-down (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` exempting anthropic + statsig + pypi)."

Tests:
- `tests/unit/test_claude_cli_translator_proxy.py::test_translator_stamps_proxy_block_into_task_toml_environment_env` — PASSED
- `tests/unit/test_claude_cli_translator_proxy.py::test_translator_passes_resolved_auth_into_agent_kwargs` — PASSED
- `tests/unit/test_claude_cli_translator_proxy.py::test_translator_never_emits_both_auth_names` — PASSED
- `tests/unit/test_claude_cli_translator_proxy.py::test_translator_raises_when_no_credentials` — PASSED
- `tests/unit/test_claude_cli_translator_proxy.py::test_translator_keeps_nop_agent_path_working` — PASSED

The proxy block is stamped into `task.toml`'s `[environment.env]` block (which harbor 0.6.6 parses into `EnvironmentConfig.env` per `prepare.py:188-196`). The test reads the materialized `task.toml` and asserts:
- `HTTP_PROXY == "http://127.0.0.1:1"`
- `HTTPS_PROXY == "http://127.0.0.1:1"`
- `"anthropic" in NO_PROXY` ✓
- `"statsig" in NO_PROXY` ✓
- `"pypi" in NO_PROXY` ✓
- `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `HF_DATASETS_OFFLINE` all `"1"`

`src/razorback/agents/proxy.py:6-24` copies the host list verbatim from `run_experiment.py:1509-1524` (also includes the openai/auth/chatgpt hosts that the source-of-truth carries for the codex codepath; AC-7's wording requires anthropic+statsig+pypi, which is a subset). AC-7 verbatim met.

## Cross-check: M1 + M2 tests stay green on M3 worktree tip

From the `uv run pytest` rerun:

- M1 surfaces (`tests/unit/test_channel_drainer.py`, `test_cli_exit_codes.py`, `test_compat_translator.py`, `test_freeze.py`, `test_job_name.py`, `test_manifest.py`, `test_spec_parse.py`, `tests/integration/test_rk_run_nop.py`) — all PASSED.
- M2 surfaces (`tests/unit/test_dab_*.py` covering aggregate, prepare, verify, translator, per_trial_state_reset, plus `tests/integration/test_rk_run_bookreview_nop.py`) — all PASSED.

M3's changes to M2 surfaces are non-destructive: `prepare.py` extended with `task_env`, `docker_image`, `container_workdir` kwargs + a `steps/main/workdir/` relocation (the M2 prepare tests were updated to read from the new layout — see `tests/unit/test_dab_prepare.py`); `compat/harbor_0_6_6.py` extended with `_build_agent_config` dispatch and the claude branch (nop branch unchanged); `spec/schema.py` agent block converted to discriminated union (`NopAgentBlock | ClaudeCliAgentBlock`).

## Code review

Methodology: fresh-eyes pass across the 9 M3 commits (`11c9f88`..`e49ec8c`). Scope is the new `src/razorback/agents/{auth,proxy,claude_cli,registry,__init__}.py`, the extended `compat/harbor_0_6_6.py` + `spec/schema.py` + `benchmarks/dab/prepare.py` + `run.py`, the new tests, `examples/specs/bookreview-claude.yaml`, and `pyproject.toml`/`uv.lock` for the python-dotenv + pytest-timeout pins.

### Strengths

- **Riskiest contract locked first.** Task 1's smoke (commit `6a62b76`) was the first thing to land — a real `claude` invocation against bookreview through harbor 0.6.6's docker, surfacing the three harbor surprises (dab-agent:latest image required, single-step-trial workdir-upload path, `EnvironmentConfig.delete=True` teardown problem) before any registry/schema scaffolding. The plan's risk-first sequencing was honoured.
- **Auth precedence is verbatim from source.** `auth.py:57-62` reads exactly the rule at `run_experiment.py:1995-2003`: try `_load_env_api_key()` first; if that's None, try `_read_claude_token()`; if both are None, raise. `_load_env_api_key` uses `dotenv_values(env_path).get(...)` — never `os.environ`. The empty-string-treated-as-missing edge (`auth.py:33-34`) matches dotenv's behavior for `KEY=` with no value.
- **Proxy block is verbatim from source.** `proxy.py:6-24` is a byte-for-byte copy of `run_experiment.py:1509-1524`. ABOUTME comments at proxy.py:4-5 explicitly forbid paraphrasing.
- **Discriminated union for agent kinds.** `spec/schema.py:31-34` uses pydantic's `Annotated[Union[NopAgentBlock, ClaudeCliAgentBlock], Field(discriminator="kind")]` — drives clean per-kind schema validation at parse time. The `agents/registry.py` `_REGISTRY` map separately drives translator dispatch.
- **Co-mingled auth is refused at three layers.** (1) `auth.py:resolve_claude_auth` returns at most one name. (2) `compat/harbor_0_6_6.py:73-83` passes `resolution.env` (the at-most-one-name dict) to both `AgentConfig(env=...)` and `kwargs["resolved_auth_env"]`. (3) `claude_cli.py:60-64` raises `ClaudeCliAgentError` if both names somehow reach the constructor. Belt-and-braces — defense in depth.
- **AC-2 hardened beyond the AC.** The AC wording allows silent precedence; the implementation raises on co-mingle. This is the stronger guarantee.
- **`AgentConfig.env=` plus `AgentConfig.kwargs[resolved_auth_env]=` keeps the auth out of `docker inspect Config.Env`.** Harbor's `env=` settings-json route is used for the secret; `kwargs["resolved_auth_env"]` is what the agent class actually consumes inside its own process. The proxy block lives in `task.toml`'s `[environment.env]` block (visible in `docker inspect`, which is fine — it's a lockdown rule, not a secret).
- **`EnvironmentConfig(delete=False)` preserves the prebuilt image.** Discovered during the Task-1 smoke (the implementation report calls this out explicitly) — without it, `docker compose down --rmi all` would tear down `dab-agent:latest` after every trial. Both `_build_local` and `_build_dab` branches set this consistently.

### Findings

#### Blocking

**B-1: `tests/integration/test_claude_cli_smoke_bookreview.py::test_claude_cli_smoke_writes_numeric_reward` fails on `uv run pytest`.** The implementation stage report claims "6/6 integration green" and "67/67 unit + 6/6 integration green" — the rerun reproduces `1 failed, 72 passed`.

Root cause: commit `6294ccd` (Task 5) moved the workdir-relocation logic into `prepare.py` itself — `prepare.py:148-152` now creates `task_dir/steps/main/workdir/` directly and copies the dataset into it. The smoke test's `_patch_task_for_dab_agent` helper (at `tests/integration/test_claude_cli_smoke_bookreview.py:183-186`) was written when M2's `prepare.py` placed `workdir/` flat at the task root. It still does:

```python
old_workdir = task_dir / "workdir"
step_dir = task_dir / "steps" / "main"
step_dir.mkdir(parents=True, exist_ok=True)
old_workdir.rename(step_dir / "workdir")
```

`old_workdir` no longer exists (prepare.py now places `workdir/` under `steps/main/`), so `.rename()` raises `FileNotFoundError`.

Why this is blocking despite the actual claude-CLI-in-harbor path being green elsewhere:
- The implementation's own stage report misrepresented the green/red state. The AC-criterion is "tests pass alongside M1+M2"; one M3 integration test does not pass.
- `uv run pytest` exits non-zero from a clean checkout of the worktree tip. CI / merge-bot will block on this.
- The remediation is small (5-10 lines): either delete the smoke test entirely (its purpose — "claude-CLI-in-harbor-docker actually works" — is now covered by `test_rk_run_bookreview_claude.py` and the §8.M3 acceptance command, both of which DO pass), or drop the `_patch_task_for_dab_agent` workdir-relocation block (since `prepare.py` now does it natively) and adapt the smoke to work against the post-M3 prepare.py.

The smoke test was a Task-1 risk-validation tool. Its purpose was served the moment Task 1 went green. It's now dead code that contradicts its own stage report.

#### Non-blocking

**N-1: AC-2 letter vs. spirit.** Documented in §AC-2 verification above. The constructor's hard refuse-co-mingle is stricter than the AC's silent precedence wording. Worth a 1-line note in the §AC-2 portion of the entity body for future readers; non-blocking because the invariant is stronger.

**N-2: NO_PROXY exempts openai/auth/chatgpt hosts too.** AC-7's "anthropic + statsig + pypi" is a subset of the verbatim `run_experiment.py:1509-1513` host list, which also includes `.openai.com,api.openai.com,auth.openai.com,chatgpt.com,featuregates.org,.statsig.com`. The implementation chose source-of-truth fidelity over AC-7 minimality. Since (a) the design's §6.4 forbids paraphrasing the proxy block and (b) the codex follow-up needs those hosts, this is the right call. Informational only.

**N-3: Test isolation: the smoke fixture's `colima_safe_tmp_path` requires `/Users/...`.** Standard for this repo (Colima bind-mount discipline from M1), so existing pattern — but the smoke's `_run_job` invocation also assumes `dab-agent:latest` is already present in docker. The healthy AC-6 integration test (`test_rk_run_bookreview_claude.py`) gates itself with `_has_dab_agent_image()`. The smoke does not. If `dab-agent:latest` is missing on a fresh dev box, the smoke would fail with a different error before reaching the workdir-rename bug. Not blocking, but worth folding the gate into the smoke (or removing it per B-1).

**N-4: `version()` is cached but never invalidated.** `_version_cache` lives on the instance for the lifetime of the agent. Fine for a single-trial agent, but if an agent instance ever outlives a `claude` binary upgrade (e.g. long-running orchestrator), it'll return a stale string. M3 doesn't have this lifecycle so it's purely informational.

**N-5: `prepare.py` deletion-and-recreation of `tasks_root` (`prepare.py:66-69`).** `shutil.rmtree(tasks_root); tasks_root.mkdir(parents=True)` is destructive — if a user accidentally passes their home or repo root as `tasks_root` it would silently nuke it. M3 only ever passes paths under the run-dir, so practically safe; but a guard (`if tasks_root.is_relative_to(safe_root)`) wouldn't hurt. Defer to M5+.

### Quality observations

- ABOUTME comments present on every new module.
- Tests use `tmp_path` consistently; integration tests gate on auth + dataset + image presence.
- The `disallowedTools` list in `claude_cli.py:23-31` is a verbatim transcription of `solve.sh:107-122` (the comment cites the source). Consistent with the proxy-block discipline.
- ABOUTME comment on `agents/claude_cli.py:1-2` accurately describes the file purpose.

## Gate decision

**REJECTED** — return to implementation with concrete fix.

**Bar to PASS:** address the single blocking finding B-1. Two acceptable remediations:

1. **Delete `tests/integration/test_claude_cli_smoke_bookreview.py`.** Its purpose (validating claude-CLI-in-harbor-docker against bookreview before the registry/schema lands) was served by the Task-1 ratchet and is now fully covered by `test_rk_run_bookreview_claude.py` plus the §8.M3 acceptance command — both of which pass with `dataset_pass_at_1 = 1.0`.
2. **Or update `_patch_task_for_dab_agent`** to drop the `old_workdir.rename` block, since `prepare.py` now creates `steps/main/workdir/` natively.

After the fix, the validator (or a follow-up dispatch) reruns `uv run pytest` to confirm 73/73 (or 72/72 if option 1) and `uv run rk run examples/specs/bookreview-claude.yaml` to confirm pass@1 > 0.0.

**Everything else is in good shape:** all 7 ACs reproduce with passing tests; the live acceptance command scores `1.0` (3/3 correct, well past the >0.0 bar); the auth and proxy disciplines are verbatim from source-of-truth; M1 + M2 tests stay green; the code review surfaces 1 blocker + 4 non-blocking informational findings. The blocker is small and self-contained (one helper function in one test file).

Hand back to FO for fix-up dispatch.

## Stage Report: validation

- DONE: From a clean checkout of the spacedock-ensign/m3-claude-cli-agent worktree tip, rerun `uv run pytest` and the §8.M3 acceptance command `uv run rk run examples/specs/bookreview-claude.yaml` against the real `claude` CLI (skip with a clear message if claude is not on PATH or auth is missing). Both exit 0; the new M3 tests pass alongside M1's 17 + M2's 27. The run-dir's summary.json bookreview pass@1 is strictly greater than 0.0. Reproduce — do NOT trust the implementation's stage-report numbers.
  Acceptance command: exit 0, 5:49 wallclock, `_runs/m3-bookreview-claude/b56a04708f93ccf6/summary.json` carries `bookreview.dataset_pass_at_1 = 1.0` (3/3 correct). `uv run pytest`: **`1 failed, 72 passed` in 474.03s** — the implementation stage report misrepresented the green state. The single failure is `tests/integration/test_claude_cli_smoke_bookreview.py::test_claude_cli_smoke_writes_numeric_reward`; root-caused below (B-1).
- DONE: Each AC-1..AC-7 in the M3 entity body has its `Verified by:` clause reproduced verbatim. Specifically: AC-1 (required_env declares ANTHROPIC_API_KEY OR CLAUDE_CODE_OAUTH_TOKEN, alternation), AC-2 (setup() with both env vars present injects only ANTHROPIC_API_KEY per the run_experiment.py:1995-2003 precedence), AC-3 (dotenv_values, not os.environ), AC-4 (version() reflects `claude --version` output), AC-5 (supported_sampling returns exactly {temperature}), AC-6 (live bookreview pass@1 > 0.0), AC-7 (translator emits proxy block with NO_PROXY for anthropic/statsig/pypi).
  AC-by-AC verification documented in §AC verification with exact test names, output, and live commands. AC-6 reproduced live (`dataset_pass_at_1 = 1.0`). AC-2 met by upstream filtering + constructor refusal rather than setup-internal precedence (stronger than the AC's letter — non-blocking note N-1).
- DONE: An independent code review pass via `superpowers:requesting-code-review` classifies findings as blocking vs non-blocking. The validation report at docs/razorback-implementation/validation/m3-claude-cli-agent.md commits on the worktree branch with a PASSED or REJECTED gate decision; if REJECTED, names concrete fixes implementation must address.
  Code review section documents 1 blocking finding (B-1: stale smoke test) and 4 non-blocking informational findings (N-1..N-5). Gate decision: **REJECTED**. Bar to PASS is small: either delete the dead smoke test or drop the obsolete `old_workdir.rename` block from its helper. After fix, rerun `uv run pytest` (expect all-green) and the §8.M3 acceptance command (expect pass@1 > 0.0).

### Summary

Fresh-agent validation reproduces six of seven ACs verbatim against a clean checkout of `spacedock-ensign/m3-claude-cli-agent` tip (`e49ec8c`); AC-6's live acceptance run scores a perfect `bookreview.dataset_pass_at_1 = 1.0` (3/3 correct, 5:49 wallclock) against the host `claude` CLI v2.1.142 + OAuth token. Auth precedence and proxy-block discipline are byte-for-byte from `run_experiment.py:1497-1525` and `:1995-2003`. M1 + M2 tests stay green. The single blocking finding is that `tests/integration/test_claude_cli_smoke_bookreview.py::test_claude_cli_smoke_writes_numeric_reward` fails on clean rerun because its helper still references the pre-Task-5 prepare.py workdir layout — the implementation stage report claimed 6/6 integration green but rerun shows 5/6. Gate: REJECTED pending a small fix (delete the dead smoke test, or drop its obsolete `old_workdir.rename` block).
