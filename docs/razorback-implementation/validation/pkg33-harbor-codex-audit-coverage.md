# PKG-33 Validation Report

Validator: `spacedock-ensign`
Role asset read: local `ensign` skill
Worktree: `.worktrees/spacedock-ensign-pkg33-harbor-codex-audit-coverage`
Branch: `spacedock-ensign/pkg33-harbor-codex-audit-coverage`

## Gate Decision

REJECT back to implementation.

AC-1 and AC-3 pass. AC-2 passes for session JSONL and the real guarded BookReview run is correctly tainted, but review found a blocking gap for actual Harbor `codex.txt` command events. The implementation's `codex.txt` taint test uses session-style `response_item` JSON instead of the observed `item.completed` / `command_execution` shape in live `codex.txt`, so a `codex.txt`-only Harbor trace with `curl` is discovered but reported clean.

## Acceptance Evidence

### AC-1 - Harbor-shaped Codex trials are discovered by `rk audit`

PASS.

Verified by clause: "a unit or integration test with a minimal run-dir fixture containing `<trial>/steps/main/agent/codex.txt` and/or Codex session JSONL, where `uv run rk audit <fixture> --format json` reports one trial instead of zero."

Command:

```bash
uv run --frozen rk audit .pkg33-validation-fixtures/ac1-clean --format json
```

Output evidence:

```json
"summary": {"clean": 1, "coverage_missing": 0, "tainted": 0}
"trial_id": "task-a/query-1/trial-0"
"taint_status": "clean"
```

Exit code: 0.

### AC-2 - Forbidden solver-side lookup attempts in Harbor Codex traces are reported as tainted under strict audit

FAIL for `codex.txt` coverage; PASS for session JSONL coverage.

Verified by clause: "a test fixture containing an agent command such as `curl`, `wget`, `git clone`, `pip install`, public web access, or Docker socket inspection in `steps/main/agent/codex.txt` or session JSONL, where `uv run rk audit <fixture> --policy strict --format json` exits with the taint error code and names the offending source."

Session JSONL command:

```bash
uv run --frozen rk audit .pkg33-validation-fixtures/ac2-tainted-session --policy strict --format json
```

Output evidence:

```text
TaintFindingsError: rk audit --policy strict found 1 non-clean trial(s) (tainted=1, coverage_missing=0)
```

```json
"summary": {"clean": 0, "coverage_missing": 0, "tainted": 1}
"source_kind": "harbor_codex_session"
"source_path": "steps/main/agent/sessions/2026/05/21/session.jsonl"
"pattern": "(?m)(?:^|[;&|]\\s*)(?:curl|wget)\\b"
```

Exit code: 23.

Blocking counterexample for observed `codex.txt` shape:

```bash
uv run --frozen rk audit "$tmp/run" --policy strict --format json
```

Fixture line:

```json
{"type":"item.completed","item":{"id":"cmd-1","type":"command_execution","command":"/bin/bash -lc 'curl https://example.com/data.csv'","status":"completed"}}
```

Output evidence:

```json
"summary": {"clean": 1, "coverage_missing": 0, "tainted": 0}
"findings": []
```

Exit code: 0. This is the same event family present in the live guarded BookReview `steps/main/agent/codex.txt`.

### AC-3 - Benchmark setup/install commands remain separable from solver trace taint

PASS.

Verified by clause: "a fixture with setup-time package installation in `job.log` and a clean solver trace, where strict audit does not taint the trial because only the solver trace is scanned for forbidden lookup attempts."

Command:

```bash
uv run --frozen rk audit .pkg33-validation-fixtures/ac3-setup-only --policy strict --format json
```

Output evidence:

```json
"summary": {"clean": 1, "coverage_missing": 0, "tainted": 0}
"findings": []
```

Exit code: 0.

## Test Commands

Command:

```bash
uv run --frozen pytest tests/unit/audit -q
```

Output:

```text
............................                                             [100%]
28 passed in 0.88s
```

Command:

```bash
uv run pytest tests/unit/audit -q
```

Output:

```text
Resolving despite existing lockfile due to removal of global exclude newer
............................                                             [100%]
28 passed in 0.86s
```

Command:

```bash
uv run --frozen pytest tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_discovers_harbor_codex_txt_trial tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_taints_harbor_codex_session_command tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_taints_harbor_codex_txt_command tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_ignores_job_log_setup_install -vv
```

Output:

```text
tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_discovers_harbor_codex_txt_trial PASSED [ 25%]
tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_taints_harbor_codex_session_command PASSED [ 50%]
tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_taints_harbor_codex_txt_command PASSED [ 75%]
tests/unit/audit/test_rk_audit_cli.py::test_rk_audit_strict_ignores_job_log_setup_install PASSED [100%]
============================== 4 passed in 0.77s ===============================
```

Note: the non-frozen pytest command rewrote `uv.lock` by removing the `[options] exclude-newer` block. That generated validation churn was reverted before writing this report.

## Real Guarded BookReview Run

Command:

```bash
uv run rk audit <repo>/runs/goal3-dab-codex/runs/bookreview-guarded/codex-dab-bookreview/e3a437f3cc875bb5 --policy strict --format json
```

Output evidence:

```json
"summary": {"clean": 1, "coverage_missing": 0, "tainted": 2}
"trial_id": "bookreview-q1__B6TZoF2", "taint_status": "clean"
"trial_id": "bookreview-q2__eH6YcV6", "taint_status": "tainted", "source_kind": "harbor_codex_session", "source_path": "steps/main/agent/sessions/2026/05/21/rollout-2026-05-21T09-32-16-019e49e0-e642-7fb1-a7e8-8b6d8b5adaa8.jsonl", "pattern": "(?m)(?:^|[;&|]\\s*)(?:curl|wget)\\b"
"trial_id": "bookreview-q3__u6wKUdd", "taint_status": "tainted", "source_kind": "harbor_codex_session", "source_path": "steps/main/agent/sessions/2026/05/21/rollout-2026-05-21T09-38-00-019e49e6-2555-78c3-afc2-a576f7508f7c.jsonl", "pattern": "(?m)(?:^|[;&|]\\s*)docker\\s+(?:ps|inspect|exec|cp|run|compose|container|image|network|volume|pull)\\b"
```

Exit code: 23.

The live run is tainted, not clean. This is validation evidence, not a PKG-33 failure by itself, because the new audit code correctly detects taint through session JSONL in that run.

## Run-Dir Contract Check

Spec section 7 says Harbor owns the run and trial layout, and Razorback's durable write surface is the sibling `_razorback/freeze/<sealed_hash>/`; Razorback must not modify Harbor trial `agent/`, `verifier/`, or `artifacts/` subtrees.

Observed guarded BookReview layout includes Harbor trial roots such as `bookreview-q1__B6TZoF2/steps/main/agent/`, `bookreview-q2__eH6YcV6/steps/main/agent/`, `bookreview-q3__u6wKUdd/steps/main/agent/`, plus `_razorback/freeze/d9a68b1d348ca0a1fd87fa93b71cac5e/`. `rk audit` read `steps/main/agent/codex.txt` and `steps/main/agent/sessions/**/*.jsonl` and emitted JSON only. No production files or run-dir artifacts were modified by validation.

## Code Review

`superpowers:requesting-code-review` is not available as a callable skill/tool in this Codex session. I performed an inline review of the worktree diff with blocking/non-blocking classification.

Blocking:

- `src/razorback/audit/harbor_codex.py:129` only scans events whose top-level `type` is `response_item`. Actual Harbor `steps/main/agent/codex.txt` from the guarded BookReview run contains `item.completed` events with `item.type == "command_execution"` and `item.command`. A minimal `codex.txt` fixture with `curl` in that shape is discovered but strict audit exits 0 with `tainted: 0`. The codex text test at `tests/unit/audit/conftest.py:164` writes a session-style `response_item` into `codex.txt`, so it does not cover the observed file format.

Non-blocking:

- None.

Concrete fixes for implementation:

- Teach the Harbor Codex scanner to handle `item.completed` / `command_execution` and `tool_execution` events in `codex.txt`, reusing the existing DAB taint event scanner semantics where practical.
- Replace or add a `codex.txt` fixture that matches the observed live `codex.txt` shape.
- Re-run `uv run --frozen pytest tests/unit/audit -q` and the guarded BookReview audit.
