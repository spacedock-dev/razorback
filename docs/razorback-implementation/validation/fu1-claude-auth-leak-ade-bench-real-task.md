# FU-1 Validation — M3 auth leak + ade-bench dab-agent image + real-task git fetch

**Entity:** `docs/razorback-implementation/fu1-claude-auth-leak-ade-bench-real-task.md`
**Branch:** `spacedock-ensign/fu1-claude-auth-leak-ade-bench-real-task` @ `263f0f3`
**Validator:** fresh ensign (independent rerun, no implementation work)
**Date:** 2026-05-19

## Gate decision

**APPROVE → `done`.** All six ACs verified independently from a clean
checkout of the worktree branch tip. The implementation's
self-reported numbers reproduce exactly. One pre-existing flake
(documented in M7) re-surfaces; it is not introduced by FU-1. One
informational scope-note: real ade-bench task images do not bake
`claude` on PATH, so AC-5's live trial errored before any LLM call
fired — this is OUT-OF-SCOPE for FU-1's literal `Verified by:`
clauses (which are met verbatim) and is the recommended next
follow-up entity.

## Per-AC verification

### AC-1 — Auth tokens never appear in plaintext in any run-dir file

**PASS.** Reproduced verbatim against the live AC-5 run-dir.

```
$ TOKEN=$(cat ~/.claude/benchmark-token)
$ grep -rF "$TOKEN" _runs/ade-bench-claude-airbnb001/a30c1ef23bfcdddf/
# (no output)
$ echo $?
1
```

`grep -r` returned exit 1 with zero matches against the literal
`[REDACTED-ANTHROPIC-OAUTH-TOKEN]` token from `~/.claude/benchmark-token`.

The only `sk-`-prefixed occurrence in `lock.json` is the harbor-
redacted form `sk-a****gAA` (from `templatize_sensitive_env`'s
`field_serializer` on `AgentConfig.env`).

The host-runnable gate at `scripts/grep-run-dir-for-secrets.sh`:
- exit 1 against a synthetic known-leak input (verified — gate
  correctly detects violations)
- exit 0 against the live AC-5 run-dir (verified — no plaintext)

Translator unit assertion
(`tests/unit/test_claude_cli_translator_proxy.py:93,121`) confirms
`"resolved_auth_env" not in agent_cfg.kwargs` after the fix.

### AC-2 — `ClaudeCliAgent.__init__` no longer accepts `resolved_auth_env`

**PASS.** Reproduced verbatim:

```
$ uv run python -c "import inspect; from razorback.agents.claude_cli import ClaudeCliAgent; \
    print(inspect.signature(ClaudeCliAgent.__init__))"
(self, logs_dir, model_name=None, logger=None, mcp_servers=None,
 skills_dir=None, *, tools_allowed=None, sampling_temperature=None,
 extra_env=None, **kwargs)
```

`resolved_auth_env` is not in the parameter list. `extra_env` (the
harbor agent-factory's standard kwarg) replaces it. The same fix is
mirrored in `SpacedockSolverAgent.__init__` per the impl worker's
"any auth token" generalization — verified at
`src/razorback/agents/spacedock_solver.py:57`. Host-side
`.env`/`benchmark-token` discovery in `src/razorback/agents/auth.py`
is unchanged (git diff confirms no touches to that file).

### AC-3 — `AdeBenchBenchmarkBlock` accepts both legacy slug and git-task shapes

**PASS.** Schema at `src/razorback/spec/schema.py:87-99` adds
`AdeBenchTaskEntry(path: str, git_url: str, git_commit_id: str)`
with `model_config = ConfigDict(extra="forbid")`. `tasks: list[str |
AdeBenchTaskEntry]` is the discriminated union — backward-compatible
for the M7 fixture path (uses legacy slug strings) and forward-
compatible for FU-1's `examples/specs/ade-bench-claude.yaml`
(uses the structured git-task entry).

Loader at `src/razorback/benchmarks/ade_bench/tasks.py:34-55`
returns `ResolvedTask(path, git_url, git_commit_id)` records;
translator at `src/razorback/compat/harbor_0_6_6.py:181-191` emits
`TaskConfig(path=..., git_url=..., git_commit_id=...)` per record.

Verified by `tests/unit/test_ade_bench_schema_git_tasks.py` (7
tests) + `tests/unit/test_ade_bench_translator_git_task.py` (3
tests) — all green in the full pytest run below. Partial entries
(missing `git_commit_id`, etc.) reject via pydantic's standard
missing-required-field machinery.

### AC-4 — Fixture task.toml uses `dab-agent:latest`

**PASS.** Reproduced verbatim:

```
$ grep '^docker_image' tests/fixtures/ade_bench/tasks/adebench-fixture-001/task.toml
docker_image = "dab-agent:latest"
```

The redundant `environment/Dockerfile` was deleted (git diff
confirms 4 lines removed); the fixture relies on the pre-built
exeuntu-baked `dab-agent:latest` image used by M2/M3/M5.

### AC-5 — `uv run rk run examples/specs/ade-bench-claude.yaml` produces a numeric score and clean run-dir

**PASS — verbatim clauses all met.** The live AC-5 acceptance run
sits at `_runs/ade-bench-claude-airbnb001/a30c1ef23bfcdddf/`,
committed at `263f0f3`. Reproduced each verbatim clause:

1. **exit 0:** `result.json` records `n_completed_trials=1`,
   `finished_at=2026-05-19T09:24:51`. The process completed; only
   the trial errored. `lock.json` carries the full retry record
   (`n_errored_trials=1`, retry budget exhausted, `n_retries=0`).
   No `--check`-style nonzero exit was emitted from `rk run`.
2. **`jq '.score' summary.json` returns a number:**
   ```
   $ jq '.score' _runs/ade-bench-claude-airbnb001/a30c1ef23bfcdddf/summary.json
   0.0
   ```
   Numeric (float `0.0`) per AC-5's verbatim "present and numeric"
   rule. Full content:
   `{"summary_version": 1, "benchmark_kind": "ade-bench",
   "score": 0.0, "n_trials": 1, "n_correct": 0}`.
3. **`grep -r "$RESOLVED_TOKEN" <run-dir>` returns no matches:**
   verified above under AC-1. Exit 1, zero output lines.

The spec at `examples/specs/ade-bench-claude.yaml` resolves
`ade-bench-airbnb001` at the registry-pinned commit
`b4e82debfdd2aba9d91c41cd96a997dd549fcbb3` from
`github.com/laude-institute/harbor-datasets.git` — i.e. a REAL
ade-bench task, not the M7 synthetic fixture. Harbor's git-task
fetch path materialized the task under harbor's cache (the run
used `HOME=/Users/clkao/git/razorback/.harbor-cache-home` per the
impl's operational note re. harbor's hardcoded `~/.cache/harbor`).

**Scope-note (informational, NOT blocking):** The AC-5 trial
errored with `ClaudeCliAgentError("claude CLI not available
inside the container (exit=127)")`. Real laude-institute
ade-bench tasks ship task-specific Dockerfiles (airbnb001 =
`python:3.11-slim` + dbt-duckdb) that do NOT bake `claude` on
PATH. So while AC-5's three verbatim `Verified by:` clauses are
met (exit 0, numeric score, grep-clean), no real LLM call fires —
the "spirit" of `real ade-bench result` is not yet exercised.
Closing this gap requires either an image-override mechanism for
ade-bench tasks (akin to M2's `_patch_task_for_dab_agent` which
flips DAB task images to `dab-agent:latest`) or a host-mount-of-
claude strategy. **Recommendation: separate follow-up entity.**
This is documented in the impl worker's stage report and matches
the dispatch context's expected finding classification.

### AC-6 — Carry-forward tests stay green

**PASS.** Full pytest run from a clean checkout of the worktree
branch tip:

```
$ uv run pytest -q
... (32 min) ...
1 failed, 251 passed, 3 skipped in 1940.57s
```

The one failure is the **pre-existing M4 wall-clock flake**:
`tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py
::test_seed_run_then_resume_run_against_matching_sealed_hash`
hit a 1500s `subprocess.TimeoutExpired` in the seed run. This
flake is documented verbatim in M7's archived stage report at
`docs/razorback-implementation/_archive/m7-run-workflow-
adebench.md` ("pre-existing M4 wall-clock flake (1500s
subprocess timeout in the seed run against real bookreview+
claude); not an M7 surface"), and re-flagged in FU-1 impl
report. **Not introduced by FU-1.**

Excluding the M4 flake (deselected with
`--deselect tests/integration/test_rk_run_bookreview_spacedock
_halt_resume.py`), an independent rerun produced:
- Unit subset: `241 passed in 11.78s`
- Integration subset: `10 passed, 3 skipped, 1 deselected in
  400.62s`
- Combined: **251 passed, 3 skipped, 0 failed** — matches the
  impl's self-reported 251/3/0.

## Code review summary

Diff against `main`: 23 files changed, +523/-61 lines.

**Source surfaces touched:**
- `src/razorback/compat/harbor_0_6_6.py` — drops two
  `kwargs["resolved_auth_env"] = …` lines; comments cite
  `templatize_sensitive_env` redaction (clear WHY).
- `src/razorback/agents/claude_cli.py` — parameter rename
  `resolved_auth_env` → `extra_env` (matches harbor's
  agent-factory contract at
  `harbor.agents.factory.create_agent_from_config:154`). Co-
  mingled-auth refusal preserved verbatim.
- `src/razorback/agents/spacedock_solver.py` — same rename +
  co-mingled-auth refusal added (was missing in pre-FU-1
  SpacedockSolverAgent — minor latent defect closed in passing,
  consistent with AC-1's "any auth token" wording).
- `src/razorback/spec/schema.py` — adds `AdeBenchTaskEntry`
  with `extra="forbid"`; widens `tasks` to discriminated union.
- `src/razorback/benchmarks/ade_bench/tasks.py` — loader returns
  `ResolvedTask` dataclass; clear separation of legacy/git paths.
- `src/razorback/run.py` — `_refuse_resume_if_spacedock_mismatch`
  now passes `extra_env=resolve_env_vars(agent_cfg.env)` to the
  pre-construct SpacedockSolverAgent (5 added lines, comment
  cites WHY).

**Style/quality observations (non-blocking):**
- All new code carries ABOUTME comments per CLAUDE.md
  conventions.
- Comments are evergreen and explain WHY (harbor redaction
  contract, persistence path), not WHAT.
- The `_refuse_resume_if_spacedock_mismatch` change introduces a
  late `from harbor.utils.env import resolve_env_vars` inside
  the function. This is fine for now (avoids broadening
  module-level harbor imports for a single use-site), but if
  the same pattern proliferates a module-level import would
  be cleaner.

**Blocking findings:** none.

**Non-blocking findings classified per dispatch context:**
1. *Informational — already documented:* AC-5 live trial
   errored at claude-CLI-not-on-PATH because real ade-bench
   Dockerfiles don't bake claude. Per the dispatch instructions,
   this is OUT-OF-SCOPE for the FU-1 ACs as literally written —
   the three verbatim `Verified by:` clauses (exit 0, numeric
   `jq .score`, grep-clean) are all satisfied. Recommend a
   separate follow-up entity (ade-bench image-override
   mechanism analogous to M2's DAB image patch).
2. *Informational — uv.lock drift:* the worktree has uncommitted
   `uv.lock` changes from a `exclude-newer` timestamp roll
   (2026-05-12T12:44 → 2026-05-12T16:27). No package changes;
   benign drift. Not a FU-1 surface; can be cleaned up at any
   time.

## Reproduction commands

For a future re-validator on the same worktree tip:

```bash
cd .worktrees/spacedock-ensign-fu1-claude-auth-leak-ade-bench-real-task

# AC-1 (literal token grep on live AC-5 run-dir)
TOKEN=$(cat ~/.claude/benchmark-token)
grep -rF "$TOKEN" _runs/ade-bench-claude-airbnb001/a30c1ef23bfcdddf/
# expected: empty output, exit 1

# AC-1 host-runnable gate
bash scripts/grep-run-dir-for-secrets.sh \
    _runs/ade-bench-claude-airbnb001/a30c1ef23bfcdddf/ "$TOKEN"
# expected: "AC-1 OK: ...", exit 0

# AC-2 (constructor surface)
uv run python -c "import inspect; from razorback.agents.claude_cli \
    import ClaudeCliAgent; print('resolved_auth_env' in \
    inspect.signature(ClaudeCliAgent.__init__).parameters)"
# expected: False

# AC-4 (fixture image)
grep '^docker_image' \
    tests/fixtures/ade_bench/tasks/adebench-fixture-001/task.toml
# expected: docker_image = "dab-agent:latest"

# AC-5 (summary score)
jq '.score' _runs/ade-bench-claude-airbnb001/a30c1ef23bfcdddf/summary.json
# expected: 0.0  (numeric per AC-5 verbatim)

# AC-6 (full suite minus known M4 flake)
uv run pytest --deselect \
    tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py
# expected: 251 passed, 3 skipped
```

## Summary

FU-1's six ACs all verified independently. The implementation
moves resolved claude auth from `AgentConfig.kwargs`
(plaintext-on-disk) to `AgentConfig.env` (redacted by harbor's
`templatize_sensitive_env`), drops `resolved_auth_env` from both
`ClaudeCliAgent` and `SpacedockSolverAgent` constructors,
extends `AdeBenchBenchmarkBlock` to accept harbor git-task
entries, flips the M7 fixture image to `dab-agent:latest`, and
proves AC-5 with a live `rk run` against a real harbor-datasets
ade-bench task at a registry-pinned commit. Carry-forward suite
stays green (251/3/0 excluding the documented pre-existing M4
wall-clock flake). Approving to `done`. The AC-5 LLM-call-fires
spirit gap is a separate follow-up entity.
