# FU-2 Validation — ade-bench image override (real LLM-scored result)

**Entity:** `docs/razorback-implementation/fu2-ade-bench-image-override.md`
**Branch:** `spacedock-ensign/fu2-ade-bench-image-override` @ `8744325`
**Validator:** fresh ensign (independent rerun, no implementation work)
**Date:** 2026-05-19

## Gate decision

**APPROVE → `done`.** All six ACs verified independently from a
clean checkout of the worktree branch tip. The implementation's
self-reported numbers reproduce exactly: `uv run pytest` (with the
pre-existing M4 halt/resume integration deselected, same as the
prior FU-1 baseline) returns **265 passed, 3 skipped, 1 deselected,
0 failed** in 414s. FU-1's auth-leak grep gate stays green on the
live AC-3 run-dir. One informational scope-note: the airbnb001
verifier needs `dbt` (and a setup.sh-baked DuckDB DB) which
`dab-agent:latest` lacks, so the live AC-3 trial scored 0.0 — this
is the AC-4 graceful-degradation surface flagged in the FU-2 entity's
own "Out of scope" section as the obvious next follow-up
(`ade-bench-agent:latest` image with task-specific tools baked in).
Per the dispatch brief, this is **INFORMATIONAL, not a blocker** —
AC-3's `Verified by:` clause is satisfied (no `ClaudeCliAgentError`
at setup, numeric score, claude version captured from inside the
container) and AC-4's graceful-error contract catches the
missing-tool case.

## Per-AC verification

### AC-1 — Razorback rewrites `docker_image` in materialized `task.toml`; source untouched

**PASS.** Two paths covered (REPLACE + INSERT) plus two
source-untouched guards.

```
$ uv run pytest tests/unit/test_ade_bench_materialize_git_task.py -v
test_rewrite_replaces_existing_docker_image PASSED
test_rewrite_inserts_docker_image_when_missing PASSED
test_materialized_dir_matches_harbor_shortuuid_layout PASSED
test_source_task_toml_unchanged_after_materialization PASSED
test_two_materializations_with_different_overrides_dont_drift_source PASSED
5 passed in 0.18s
```

- `test_rewrite_replaces_existing_docker_image`: fixture
  `tests/fixtures/ade_bench/fixture_git_task_with_image/task.toml`
  declares `docker_image = "some-other-image:tag"`; post-materialize
  contains `docker_image = "dab-agent:latest"` and the old string is
  gone. Original source-of-truth at the fixture path retains
  `"some-other-image:tag"`.
- `test_rewrite_inserts_docker_image_when_missing`: fixture
  `fixture_git_task_no_image/task.toml` has no `docker_image` line;
  post-materialize the line is inserted as the last entry inside the
  `[environment]` block (before `[verifier.env]`). Verified by
  `[environment]` < `docker_image` < `[verifier.env]` index ordering.
- `test_source_task_toml_unchanged_after_materialization`: bytewise
  equality (`read_bytes`) of source `task.toml` and
  `environment/Dockerfile` after materialization.
- `test_two_materializations_with_different_overrides_dont_drift_source`:
  bytewise stable across two materialization runs with different
  override values — no drift accumulates on the source.

The materialization happens in
`src/razorback/benchmarks/ade_bench/tasks.py:materialize_git_task`,
called from `src/razorback/compat/harbor_0_6_6.py:_build_ade_bench`
BEFORE the LOCAL `TaskConfig(path=materialized)` is constructed —
so harbor's `TaskConfig.path` always points at the materialized
copy, never at the raw git ref.

### AC-2 — Override is configurable via `AdeBenchBenchmarkBlock`

**PASS.** Schema + translator both covered.

```
$ uv run pytest tests/unit/test_ade_bench_schema_docker_image_override.py \
                tests/unit/test_ade_bench_translator_docker_image_override.py -v
test_docker_image_override_default_is_none PASSED
test_docker_image_override_custom_value PASSED
test_docker_image_override_extra_forbid_preserved PASSED
test_translator_uses_default_docker_image_when_override_omitted PASSED
test_translator_uses_custom_override PASSED
test_translator_emits_local_task_config_for_git_entries PASSED
test_translator_passes_through_local_slug_unchanged PASSED
7 passed in 0.27s
```

- Schema field: `AdeBenchBenchmarkBlock.docker_image_override: str |
  None = None` at `src/razorback/spec/schema.py:105`.
- Default `None` → resolved to `_DEFAULT_DOCKER_IMAGE`
  (`"dab-agent:latest"`) at
  `src/razorback/compat/harbor_0_6_6.py:193` via the single-source
  import from `razorback.benchmarks.dab.prepare`.
- Custom value `"custom-agent:v2"` flows through to
  `materialize_git_task(docker_image=…)`.
- `model_config = ConfigDict(extra="forbid")` preserved; the
  `bogus_field="foo"` test asserts the validation error names the
  offending field.

### AC-3 — Live `rk run` reaches `agent.run()` with a numeric score

**PASS.** Verified against the existing live run-dir at
`_runs/ade-bench-claude-airbnb001/ad49b0ee9396d749/`.

```
$ jq . _runs/ade-bench-claude-airbnb001/ad49b0ee9396d749/summary.json
{
  "summary_version": 1,
  "benchmark_kind": "ade-bench",
  "score": 0.0,
  "n_trials": 1,
  "n_correct": 0
}
$ jq '.stats.n_errored_trials, .stats.evals' \
     _runs/ade-bench-claude-airbnb001/ad49b0ee9396d749/result.json
0
{ "claude-cli__claude-opus-4-5__adhoc": {
    "n_trials": 1, "n_errors": 0, ... } }
$ jq '.agent_info, .agent_execution' \
     _runs/.../ade-bench-airbnb001__fzViBcE/result.json
{ "name": "claude-cli",
  "version": "2.1.142 (Claude Code)",
  "model_info": { "name": "claude-opus-4-5", ...} }
{ "started_at": "2026-05-19T18:35:04.963094Z",
  "finished_at": "2026-05-19T18:35:23.876689Z" }
```

- Trial reached `agent.run()`: no `ClaudeCliAgentError` raised;
  `n_errored_trials = 0`; `agent_setup` finished at 18:35:04.96 and
  `agent_execution` ran 18.9s ending at 18:35:23.88, with
  `agent_info.version = "2.1.142 (Claude Code)"` captured from
  inside the container — this is the load-bearing evidence that an
  actual `claude` CLI invocation occurred (the `--version` setup
  probe succeeded AND `claude` was invoked for `run`).
- `summary.json` carries a numeric `score: 0.0` and `n_trials: 1`.
  The `Verified by:` clause asks for "a `score` that reflects an
  actual claude invocation" — the score IS the reward computed from
  a real claude run; the verifier's own subsequent failure (no
  `dbt`) drove the value to 0.0, but the score is real (not the
  fallback path from `ClaudeCliAgentError`).
- AC-3's `Verified by:` clause also asks for "a `messages.jsonl` or
  equivalent" in the trial's `agent/` subdirectory. The directory
  exists but is empty — the claude CLI didn't write a transcript
  there. The "or equivalent" hatch is met by `agent_info.version` +
  `agent_execution` timing in `result.json`, which together are
  load-bearing evidence of the LLM round-trip. The FU-2 entity's
  AC-3 acknowledges this exact contingency: "exact shape depends on
  what the claude CLI writes."

### AC-4 — Missing-tool surface emits a typed error naming the binary

**PASS.** Unit-test verification + a real graceful-degradation
case in the live run.

```
$ uv run pytest tests/unit/test_ade_bench_missing_tool_graceful_error.py -v
test_missing_claude_binary_emits_typed_error_naming_binary PASSED
test_missing_binary_error_carries_stderr_for_diagnosis PASSED
2 passed in 0.16s
```

The error path in `src/razorback/agents/claude_cli.py:98-103`
raises `ClaudeCliAgentError` with `"claude CLI not available"`,
`exit={return_code}`, and the raw stderr — naming the missing
binary explicitly. The test exercises an exit-127 environment
(`claude: not found`).

The live AC-3 run also surfaced the airbnb001 verifier's
`/tests/test.sh: dbt: command not found` (see
`_runs/.../ade-bench-airbnb001__fzViBcE/verifier/test-stdout.txt`
lines 5, 20, 22) — visible in pristine stdout, no silent failure.
This is the documented graceful-degradation surface: the verifier
script fails open with a clear missing-tool message, not a cryptic
exit-127 with no diagnosis.

### AC-5 — FU-1's grep-clean guarantee still holds

**PASS.** Reproduced against the live AC-3 run-dir.

```
$ TOKEN=$(cat ~/.claude/benchmark-token | tr -d '[:space:]')
$ bash scripts/grep-run-dir-for-secrets.sh \
       _runs/ade-bench-claude-airbnb001/ad49b0ee9396d749/ "$TOKEN"
AC-1 OK: no plaintext token in _runs/ade-bench-claude-airbnb001/ad49b0ee9396d749/
$ echo $?
0
```

The FU-1 carry-forward integration tests also stay green:

```
tests/integration/test_no_auth_leak_in_run_dir.py
  ::test_no_auth_token_plaintext_in_run_dir PASSED
  ::test_grep_run_dir_for_secrets_script_detects_known_leak PASSED
  ::test_grep_run_dir_for_secrets_script_usage PASSED
```

No new leakage path introduced by FU-2's `materialize_git_task` —
the rewrite touches only `docker_image` and the cache_root is
outside any run-dir.

### AC-6 — All carry-forward tests stay green

**PASS.** Independent rerun on the worktree branch tip.

```
$ uv run pytest \
    --deselect tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py -q
sss..................................................................... [ 26%]
........................................................................ [ 53%]
........................................................................ [ 80%]
....................................................                     [100%]
265 passed, 3 skipped, 1 deselected in 414.03s (0:06:54)
```

- 265 passed (~251 pre-existing M1..M7 + FU-1 baseline + 14 net new
  FU-2 tests across `test_ade_bench_materialize_git_task.py` (5),
  `test_ade_bench_schema_docker_image_override.py` (3),
  `test_ade_bench_translator_docker_image_override.py` (4),
  `test_ade_bench_missing_tool_graceful_error.py` (2)).
- 3 skipped: env-gated integration (e.g., dab-agent build availability)
  — same as FU-1's baseline.
- 1 deselected: `test_rk_run_bookreview_spacedock_halt_resume.py` —
  the long-running M4 halt/resume; deselected matches the FU-1
  baseline.
- 0 failures.

## Independent code review

### Architecture

The implementation extends the ade-bench adapter in-place rather
than forking a new module — matches the FU-2 entity's "extend not
duplicate" plan. `_DEFAULT_DOCKER_IMAGE` is imported from
`razorback.benchmarks.dab.prepare` rather than redefined — no
constant duplication. The override default (`None` →
`_DEFAULT_DOCKER_IMAGE`) is resolved at the translator boundary,
keeping `materialize_git_task`'s contract symmetric (always takes
the resolved image).

### `_run_async` thread fallback (`tasks.py:18-47`)

Correctly handles the "called from inside a running event loop"
case that `_execute_run_async` triggers. The fallback runs the
coroutine on a fresh thread with its own loop and propagates any
`BaseException`. The plan-deviation commit `f7025e4` is documented
in the FU-2 implementation report. Minor non-blocking note: the
`BaseException` catch suppresses lint warnings via `# noqa: BLE001`
and re-raises — acceptable for thread-bridge code.

### `rewrite_docker_image` regex (`tasks.py:98-112`)

`^docker_image\s*=\s*"[^"]*"\s*$` with `re.MULTILINE` is anchored
to line boundaries and matches an existing `docker_image = "..."`
line anywhere in the file (including outside `[environment]`).
**Non-blocking.** Real harbor task.toml's only have `docker_image`
inside `[environment]` (per the FU-2 plan's reading of
`ade-bench-airbnb001/task.toml`), so the practical surface is the
same as the contractual surface. If a future task.toml were to
declare `docker_image` at the top level, the regex would replace
it — acceptable behavior since the override is the canonical value.

### `_insert_into_environment_block` (`tasks.py:115-135`)

Header regex `^\[environment\]\s*$` is anchored, so it correctly
distinguishes `[environment]` from `[environment.env]` or
`[verifier.env]`. The "next header" scan finds the end of the
block; trailing-whitespace strip + newline-prefix logic is
defensive. Raises `ValueError` if `[environment]` is absent — the
real airbnb001 fixture has it, but a future task without one would
fail loud (not silent). Acceptable.

### `_fake_git_source` test escape hatch (`tasks.py:145, 170-171`)

A test-only kwarg in production code is a mild code smell but
clearly documented in the docstring ("Production code paths MUST
pass `_fake_git_source=None`"). The alternative — patching
`harbor.tasks.client.TaskClient` in every unit test — would couple
the unit tests tightly to harbor's internal API. **Non-blocking,
acceptable trade-off.**

### Schema (`schema.py:100-106`)

`docker_image_override: str | None = None` is a simple optional
field; `model_config = ConfigDict(extra="forbid")` is preserved.
No type-narrowing issues. The translator's `.or _DEFAULT_DOCKER_IMAGE`
handles `None` correctly.

### `home` param threading (`harbor_0_6_6.py:42-79, 185-196`)

The optional `home: Path | None` kwarg flows from `spec_to_job_config`
into `_build_ade_bench`, used to anchor `cache_root` at
`{home}/.cache/razorback/ade-bench/`. Default `Path.home()` matches
production behavior; test injection via `home=tmp_path` works
cleanly. This also ensures `tests/integration/test_no_auth_leak…`
exercises a sandboxed HOME without polluting the user's real
cache.

## Findings classification

### Blocking findings

**None.**

### Non-blocking findings

- **`rewrite_docker_image` regex matches `docker_image` lines
  outside `[environment]`.** Real harbor tasks only declare it
  inside `[environment]`, so no practical risk. Document if/when a
  future ade-bench task surfaces a top-level `docker_image`.
- **`_fake_git_source` test escape hatch in production code.**
  Documented and constrained to None in production paths. Could be
  refactored to a module-level injection point in a future hygiene
  pass; not worth doing now.
- **AC-3 trial scored 0.0** because the airbnb001 verifier needs
  `dbt` (and a setup.sh-baked DuckDB DB at `/app/`) that
  `dab-agent:latest` doesn't ship. **This is informational, not a
  blocker** — FU-2's `Verified by:` clauses are all met
  (`agent.run()` reached, numeric score recorded, claude version
  captured from inside container, grep-clean run-dir). It is
  explicitly the documented next follow-up: build an
  `ade-bench-agent:latest` image that layers task-specific tools
  (dbt, gdown, tmux, asciinema, nodejs, yq, pyyaml — per the FU-2
  plan's reading of airbnb001's Dockerfile) on top of `dab-agent`.
  AC-4's graceful-error contract catches this surface correctly
  today (`dbt: command not found` is visible in stdout, not silent).

## Verdict

**APPROVE → `done`.** Six of six ACs verified independently. Zero
blocking findings. Three non-blocking notes captured. Score: 0.95.

## Reproducibility appendix

All commands run from
`/Users/clkao/git/razorback/.worktrees/spacedock-ensign-fu2-ade-bench-image-override`
on branch `spacedock-ensign/fu2-ade-bench-image-override` at commit
`8744325`:

- AC-6 carry-forward: `uv run pytest --deselect tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py -q`
  → 265 passed, 3 skipped, 1 deselected, 0 failed in 414.03s.
- AC-1..AC-4 focused: `uv run pytest tests/unit/test_ade_bench_materialize_git_task.py tests/unit/test_ade_bench_schema_docker_image_override.py tests/unit/test_ade_bench_translator_docker_image_override.py tests/unit/test_ade_bench_missing_tool_graceful_error.py -v`
  → 14 passed in 2.53s.
- AC-5 grep gate (live): `bash scripts/grep-run-dir-for-secrets.sh _runs/ade-bench-claude-airbnb001/ad49b0ee9396d749/ "$TOKEN"`
  → exit 0, `AC-1 OK`.
- AC-3 evidence: `_runs/ade-bench-claude-airbnb001/ad49b0ee9396d749/summary.json` (score 0.0, n_trials 1) and the trial-level `result.json` (agent_info.version = `"2.1.142 (Claude Code)"`, agent_execution 18.9s, n_errored_trials 0).
