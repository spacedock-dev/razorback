# Validation: Phase 1 -- rk run v2 wrapper

- Worktree branch: `spacedock-ensign/phase1-rk-run-v2-wrapper`
- Validated commits: `1978cd2..8d51c48` (20 commits)
- Validator: `spacedock-ensign-phase1-rk-run-v2-wrapper-validation`

## Gate decision: REJECT to implementation

A real authentication bug introduced by the harbor-subprocess delegation route
silently breaks AC-1 in a way that AC-1's test does not catch. Reproduced
independently in this validation; root cause identified at the line level. See
"AC-1 finding" below for the concrete fix.

Feedback-to: `spacedock-ensign-phase1-rk-run-v2-wrapper-implementation`

## AC verdicts

- **AC-1 (walking skeleton holds, run-dir result.json parses):** FAIL --
  reproduction confirmed: 3/3 trials reward=0.0, 40s wallclock (baseline
  rerun was 6:30 with reward=1.0). The test as written (`n_errored_trials ==
  0`) passes because harbor's per-trial accounting treats a fast,
  no-answer-file claude-cli invocation as a "completed" trial -- but the
  agent did not actually execute. See "AC-1 root cause" below.
- **AC-2 (alias-drift + harbor exit-code passthrough):** PASS -- unit tests
  cover both pre-checks. `tests/unit/test_rk_run_v2_pre_checks.py::*` 4
  tests; alias-drift mock asserts `AliasDriftError`; harbor non-zero
  asserts exit 30. `cli/run.py:153-165, 194-196`.
- **AC-3 (byte-faithful spec.frozen.yaml + provenance.yaml in run-dir):**
  PASS -- `tests/unit/test_rk_run_v2_provenance_artifacts.py` 4 tests
  green; integration run confirmed both files at
  `{run-dir}/spec.frozen.yaml` and `{run-dir}/provenance.yaml` with
  spec.frozen.yaml byte-identical to input.
- **AC-4 (extracted behaviors preserve semantics):** PASS -- `errors.py`
  extends ExitCode with `BudgetExceeded(22)`, `TaintFindings(23)`,
  `ConfigInvalid(24)`; auth + alias-drift KEEP-VERBATIM tests pass
  from re-pointed v2 paths.
- **AC-5 (v1 modules sidelined to _legacy/):** PASS -- `git log
  --diff-filter=R --follow src/razorback/_legacy/run.py` shows R100
  rename; commit 4118090 moves run.py + manifest + observers + runtime
  + compat + cli/validate.py + cli/spec.py.
- **AC-6 (translator emits import_path):** PASS --
  `test_translate_spacedock_solver_import_path.py` 4 tests green;
  emits `razorback.agents.spacedock_solver:SpacedockSolverAgent`.
- **AC-7 (uv run pytest exits 0):** PASS -- 198/198 unit tests pass in
  3.34s; integration test passes in 41.95s. Total 213 collected.
- **AC-8 (runs-dir mount-visibility canary):** PASS --
  `tests/unit/test_runs_dir_canary.py` 5 tests green; canary fires
  ConfigInvalidError when probe sees the runs-dir as missing inside
  the container; `cli/run.py:139-145` runs it BEFORE harbor delegation.

## AC-1 root cause

The v2 wrapper writes JobConfig to `{run-dir}/_job_config.yaml` and invokes
`harbor run -c <yaml>` as a subprocess. The serializer
`harbor.models.trial.config.AgentConfig._serialize_env`
(`harbor/models/trial/config.py:54-57`) calls
`templatize_sensitive_env` (`harbor/utils/env.py:58-75`) during
`model_dump_json`. For the OAuth token:

- value type: sensitive (matches `_SENSITIVE_KEY_RE` for `TOKEN`)
- already-a-template? no
- `os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") == value`? **no** -- razorback
  reads the token from `~/.claude/benchmark-token` via `dotenv_values`
  semantics; it never lives in `os.environ`
- result: falls through to `redact_sensitive_value(value)` →
  `"sk-a****gAA"` written to disk

Harbor reads the templatized YAML back, gets the redacted string, passes
that as `CLAUDE_CODE_OAUTH_TOKEN` to the container. claude-cli auths fail
immediately, exits in 0.6 seconds without writing `/workspace/answers.json`.
The DAB verifier reads the missing file as "empty answer" and emits
reward=0.0. Harbor's per-trial accounting reports 3/3 completed, 0
errored -- because environment.exec doesn't check return_code and the
agent doesn't raise.

Evidence:
- `cli/run.py:185-186` -- `job_config.model_dump_json(indent=2)` triggers
  the field_serializer
- Validation run dir
  `.test-tmp/validation-smoke/_runs/_deterministic-smoke/bc7421b6432e225a/_job_config.yaml`
  contains `"CLAUDE_CODE_OAUTH_TOKEN": "sk-a****gAA"` literal
- All 3 per-trial `agent_execution` windows are 0.6s vs baseline 128s
- Per-trial verifier stdout: `DAB verify (/tests/validate.py): empty answer`
- v1 (`_legacy/run.py:128`) bypasses this by calling
  `Job.create(job_config)` in-process -- the JobConfig pydantic instance
  is never serialized, so the field_serializer never runs

Why the impl worker's cycle-2 test passed: the assertion is
`stats.n_completed_trials >= 1 and n_errored_trials == 0`. Both hold under
the auth-broken path. The test is too lenient: it conflates "harbor
finished without exceptions" with "the agent actually executed". The 1.0
reward baseline outcome from AC-0.1(b) was specifically called out in the
spec as the determinism anchor, and the implementation worker noted "the
3/3 reward=1.0 baseline reproduction is a validation-stage concern" -- but
it IS the AC's mechanism check, since the entire point of the walking
skeleton is to prove the agent can execute and produce an answer end-to-end.

## Fix options for implementation

Pick one (in increasing order of disruption):

1. **Push the token into os.environ before serializing.** Set
   `os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = resolution.env["CLAUDE_CODE_OAUTH_TOKEN"]`
   in `cli/run.py` BEFORE `job_config.model_dump_json(...)`. Then
   templatize emits `${CLAUDE_CODE_OAUTH_TOKEN}` instead of the redacted
   value, and the harbor subprocess inherits the real token via
   `harbor_env = {**os.environ, ...}` at `cli/run.py:189`. Smallest
   change; preserves disk-redaction discipline. Symmetric handling for
   `ANTHROPIC_API_KEY`.
2. **Bypass field_serializer via model_dump.** Use
   `job_config.model_dump(mode="python")` + a custom JSON/YAML emitter
   that emits the env dict raw, but the on-disk file then contains the
   plaintext token -- a regression vs harbor's intentional discipline.
3. **In-process invocation.** Replace the subprocess with `await
   Job.create(job_config); await job.run()` like v1 -- but that
   defeats Phase 1's stated delegation model.

Option 1 is the minimal-blast-radius fix and aligns with the existing
HOME/DOCKER_HOST forwarding pattern (commits 56eaa58 + 58c4ac5).

## AC-1 strengthening (required regardless of fix)

The integration test must assert reward, not just completion. Add to
`tests/integration/test_rk_run_v2_deterministic_smoke.py`:

```python
mean = harbor_result["stats"]["evals"][...]["metrics"][0]["mean"]
assert mean == 1.0, f"deterministic-smoke baseline is 1.0, got {mean}"
```

Without this, future regressions of the same class will pass the test.

## Test suite (AC-7)

`uv run pytest tests/unit/`: **198 passed in 3.34s** -- clean.
`uv run pytest tests/integration/test_rk_run_v2_deterministic_smoke.py`:
**1 passed in 41.95s** -- passes despite reward=0.0 (see "AC-1 strengthening").
Total: 213 collected, 199/213 effective passes; 14 are integration-marker
tests not run as part of unit sweep.

## Code review findings

Worktree diff `1978cd2..HEAD` (20 commits, 996 +/- 16 lines across 27 files).

Blocking:

- **`cli/run.py:185-186` -- JobConfig serialization redacts the OAuth token.**
  Root cause of AC-1 failure. See "AC-1 root cause" above.

Non-blocking:

- **`cli/run.py:46-60` `_invoke_harbor`** -- uses `capture_output=False` so
  harbor's stdout/stderr stream to the parent terminal. Fine for CLI
  interactive use, but pytest captures stdout, so test failures lose
  harbor's diagnostic output. Consider streaming harbor output to a log
  file under the run-dir for post-mortems.
- **`cli/run.py:107-120` `_write_provenance_artifacts`** -- writes
  spec.frozen.yaml + provenance.yaml AFTER `_invoke_harbor` returns
  successfully. If harbor exits 30, the run-dir contains neither file.
  AC-3's intent is that the artifacts always reflect what was attempted,
  so consider writing them before the harbor invocation (after the
  pre-checks and the canary, but before the agent runs).
- **`cli/run.py:188 _stage_harbor_home`** -- creates `.harbor-home/` under
  the resolved runs-dir on every invocation. Multiple concurrent runs
  in the same runs-dir would share the same harbor cache directory; if
  harbor is not robust to that, this would surface as flaky CI failures.
  Document the contract or use a per-run subdir.
- **`agents/auth.py:62`** -- the OAuth-mode value-only resolution returns
  `AuthResolution(mode="oauth", env={"CLAUDE_CODE_OAUTH_TOKEN": token})`.
  Test inventory P1-T2/T3 confirms parity with v1, so this is preserved
  intentionally. Once Option 1 above lands, document the env-coupling
  contract in `resolve_claude_auth`'s docstring (the caller MUST mirror
  to os.environ before serializing JobConfig).
- **`tests/conftest.py:14-34 collect_ignore_glob`** -- the list will need
  pruning when Phase 6/7 deletes `_legacy/`. Leave a TODO/cite the
  Phase number.

## Evidence index

- Validation run dir (live, reward=0.0 confirmed): regenerable via the
  command in "Reproduction" below; the validation-smoke artifact was
  cleaned up after analysis.
- Impl worker's manual-smoke run (also reward=0.0): noted in cycle-2
  stage report at impl worker, kept under `.test-tmp/manual-smoke/...`
  in this worktree.
- Baseline reproduction (v1 path, reward=1.0): `.runs/baseline-rerun-20260520-smoke/...`
  on `main` per `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`.

## Reproduction

```sh
cd /Users/clkao/git/razorback/.worktrees/spacedock-ensign-phase1-rk-run-v2-wrapper
mkdir -p .test-tmp/validation-smoke/_runs
uv run python -c "
from razorback.spec.freeze import freeze_spec
from razorback.spec.parse import parse_spec_file
from pathlib import Path
spec = parse_spec_file(Path('examples/specs/_deterministic-smoke.yaml'))
Path('.test-tmp/validation-smoke/_deterministic-smoke.frozen.yaml').write_text(freeze_spec(spec))
"
uv run python -m razorback.cli run .test-tmp/validation-smoke/_deterministic-smoke.frozen.yaml \
  --runs-dir .test-tmp/validation-smoke/_runs
grep -A1 CLAUDE_CODE_OAUTH_TOKEN .test-tmp/validation-smoke/_runs/_deterministic-smoke/*/_job_config.yaml
# expect: "sk-a****gAA"
```

---

## Cycle 2 (2026-05-20): PASS

- Validated commits: `9ae5afb..e822955` (cycle-3 impl diff: d663703 test strengthening, 39a4391 os.environ mirror fix, e822955 stage report)
- Validator: `spacedock-ensign-phase1-rk-run-v2-wrapper-validation-cycle2`

### Gate decision: APPROVE to done

The cycle-3 fix resolves the cycle-1 blocking finding cleanly. The validator's recommended minimal-blast-radius fix (Option 1: mirror `AgentConfig.env` into `os.environ` before `model_dump_json`) is exactly what landed at `cli/run.py:185-194`, and the strengthened AC-1 assertion (`metrics[0].mean == 1.0`) catches the redaction class of bug for future regressions.

### AC-1 cycle-2 re-verification

Live integration run (`uv run pytest tests/integration/test_rk_run_v2_deterministic_smoke.py -v -s`): **1 passed in 365.66s (6:05 wallclock)**, within the 6:30 baseline window for the deterministic-smoke spec.

Mid-run inspection at the worktree's `.test-tmp/t-32714966/_runs/_deterministic-smoke/bc7421b6432e225a/_job_config.yaml` shows:

```
"CLAUDE_CODE_OAUTH_TOKEN": "${CLAUDE_CODE_OAUTH_TOKEN}"
```

templatized, not redacted. The cycle-1 reproduction grep would have shown `"sk-a****gAA"` here. Harbor subprocess inherits the real token via `harbor_env = {**os.environ, ...}` at `cli/run.py:200` and the agent runs to completion.

Top-level `result.json` after the run:

```json
"evals": {
  "claude-cli__claude-opus-4-5__adhoc": {
    "n_trials": 2..3,  // observed mid-run; final test assertion guarantees 3
    "metrics": [{"mean": 1.0}],
    "reward_stats": {"reward": {"1.0": [...trial-ids...]}}
  }
}
```

The strengthened assertion at `tests/integration/test_rk_run_v2_deterministic_smoke.py:79` requires `mean == 1.0`; the test passed, so all three trials reported reward=1.0.

**Pre-fix counter-test:** the impl worker's cycle-3 stage report claims the strengthened test was run against the pre-fix code at d663703 (test) before 39a4391 (impl) and reported `mean=0.0`, matching the validator's cycle-1 reproduction. The git log confirms d663703 precedes 39a4391 by one commit, and the test file at d663703 is identical to the current test file (the impl-only commit 39a4391 did not touch the test). This validator did not re-run the destructive pre-fix experiment (would require a 6-minute checkout/run/reset cycle to re-prove a fact already established in cycle 1's report); accepting the impl worker's claim on the basis that (a) the cycle-1 validator independently reproduced reward=0.0 against the same code path, (b) the test is git-traceable to the same content at both commits, and (c) the strict `assert mean == 1.0` clause would fail at `mean=0.0` by construction.

### AC-2 through AC-8 cycle-2 re-verification

`uv run pytest tests/ -q --ignore=tests/integration`: **198 passed in 3.17s**, clean.
`uv run pytest tests/integration/test_rk_run_v2_deterministic_smoke.py`: **1 passed in 365.66s**, AC-1 PASS with reward=1.0.

AC-2/AC-3/AC-4/AC-5/AC-6/AC-7/AC-8 verdicts from cycle 1 (PASS) hold unchanged: the cycle-3 fix touched only `cli/run.py:185-194` (the 11-line env-mirror block) and the integration test file. None of the AC-2..8 verifying paths were modified.

### Code review of cycle-3 diff

Diff scope `9ae5afb..e822955`, 3 files, 38 insertions, 2 deletions.

**Blocking:** none.

**Non-blocking:**

- **`cli/run.py:188` em-dash in comment.** The new comment block has one em-dash glyph (`os.environ, so mirror` would be the consistent form). Style policy commit `a2e9c49` bans em-dashes in spec/plan files; the policy's reach into code comments is not explicit. The validation report itself was scrubbed for em-dashes in cycle 1 (commit c44a7cf), so applying the same rule to the impl comment would be consistent. Trivial cleanup; not a gate blocker.
- **`cli/run.py:192-194` global os.environ mutation.** The fix mutates the process-wide `os.environ` to make harbor's `templatize_sensitive_env` round-trip. This is a deliberate, documented contract (the multi-line comment above it explains why) and is the minimal change. Note for future readers: a `rk run` invocation now leaves `CLAUDE_CODE_OAUTH_TOKEN` (and any other AgentConfig.env keys) set in the parent process's environment after the command returns. For the CLI single-shot use case this is irrelevant (process exits), but a hypothetical test that calls `run_command` directly and inspects `os.environ` afterward would see the leak. Worth a docstring note on `run_command` once the auth-contract docstring lands (validator cycle-1 non-blocking item already filed).
- **All cycle-1 non-blocking findings still apply** (harbor stdout capture, provenance-write ordering, `.harbor-home` concurrency, auth contract docstring, `_legacy` collect_ignore TODO). None block APPROVE; all are queued for follow-up.

### Test sweep summary

| Suite | Result | Wallclock |
|---|---|---|
| `tests/unit/` | 198/198 PASS | 3.17s |
| `tests/integration/test_rk_run_v2_deterministic_smoke.py` | 1/1 PASS, mean=1.0 | 6:05 |

### Recommendation

**APPROVE to `done`.** AC-1 walking-skeleton holds end-to-end with the deterministic-smoke baseline (reward=1.0, matching v1's `.runs/baseline-rerun-20260520-smoke/` anchor). AC-2..8 unchanged from cycle 1 PASS. Code review surfaces only minor non-blocking polish items, all already filed.

