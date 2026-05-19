---
id: 3w29a8smhbb32w4r07b81sst
title: FU-1 — M3 auth leak + ade-bench dab-agent image + real-task git fetch
status: plan
source: post-sprint follow-up (CL 2026-05-19)
started: 2026-05-19T14:58:09Z
completed:
verdict:
score: 0.95
worktree:
issue:
pr:
mod-block:
---

## Problem

Post-sprint follow-up surfaced when CL attempted a real claude live
run against the ade-bench fixture spec. Three issues, all blocking
the "real ade-bench result" deliverable:

1. **M3 token leak (security).** `ClaudeCliAgent`'s auth path
   forwards the resolved OAuth token via
   `AgentConfig.kwargs.resolved_auth_env`. Harbor's
   `templatize_sensitive_env` redacts `agent.env` (renders as
   `sk-a****gAA`) but does **not** redact `agent.kwargs`. The full
   token appeared in plaintext in 4 files of the run-dir:
   `lock.json`, `<run-dir>/config.json`, `<trial>/config.json`,
   `<trial>/result.json`. M3's AC-2 spec said the token should
   "never appear in `docker inspect Config.Env`" but the
   implementation chose a forwarding path that achieves the
   container env goal at the cost of plaintext persistence on disk.
   M3 validation did not grep the run-dir for the literal token, so
   the defect shipped.

2. **ade-bench fixture image lacks claude.** The M7-shipped
   ade-bench fixture task uses `docker_image = "alpine:3.19"` +
   `apk add bash` only. Claude CLI is not installed, so
   `claude --version` exits 127 at agent setup, the trial errors
   before any LLM call fires, and no real ade-bench score is
   produced. The DAB image path (`dab-agent:latest` built on
   `ghcr.io/boldsoftware/exeuntu@sha256:a1c6df...` from
   dataagentbench's setup.sh) already bakes in claude + codex + uv
   + the DB tools; razorback M2/M3/M5 all use it successfully.

3. **No path to real ade-bench tasks.** The M7 worker landed a
   hand-rolled synthetic fixture at
   `tests/fixtures/ade_bench/tasks/adebench-fixture-001/` and
   explicitly deferred "real harbor-datasets clone is post-M7"
   (M7 stage report, named divergence #2). Harbor's registry
   already exposes 48 real ade-bench tasks (e.g.
   `ade-bench-quickbooks002`,
   `ade-bench-f1003`) at
   `github.com/laude-institute/harbor-datasets.git`, but
   razorback's `AdeBenchBenchmarkBlock` accepts only a local
   `tasks_root` + slug list — no `git_url`/`git_commit_id` shape.
   So a "real ade-bench result" requires either an adapter
   extension (this entity's preferred path) or a manual clone
   into a host-specific local path.

## Acceptance criteria

**AC-1 — Auth tokens never appear in plaintext in any run-dir
file written by razorback.**
Verified by: a unit test asserts that after the spec → JobConfig
translator runs for a claude-cli spec, `AgentConfig.kwargs` does
NOT contain the resolved auth value (only `tools_allowed`,
`sampling_temperature`, etc.); a follow-up integration test runs
`rk run` against a nop-or-cheap spec with auth resolved and greps
the entire run-dir (`grep -r "$ANTHROPIC_API_KEY"
<run-dir>` returns no matches; same for any
`CLAUDE_CODE_OAUTH_TOKEN`-shaped value). Harbor's
`templatize_sensitive_env` should produce the only redacted-form
appearance.

**AC-2 — `ClaudeCliAgent.__init__` no longer accepts the
`resolved_auth_env` kwarg; the agent reads auth from container
env (which harbor populates via `AgentConfig.env`).**
Verified by: `inspect.signature(ClaudeCliAgent.__init__)` does
NOT list `resolved_auth_env`; a unit test confirms the agent
operates with the auth in the container's environment (i.e.
present in `os.environ` inside the container at run time). The
host-side `.env`/`benchmark-token` discovery in
`src/razorback/agents/auth.py` is unchanged — that discipline
(no `os.environ` on the host) is correct.

**AC-3 — `AdeBenchBenchmarkBlock` accepts a `tasks: list` whose
entries are either local-slug strings (current shape, kept
backward-compatible) OR objects with
`{path, git_url, git_commit_id}` matching harbor's
`TaskConfig` git-task shape.**
Verified by: a unit test feeds a spec with a git-shaped task
entry and asserts the translator produces a harbor `TaskConfig`
with the `git_url` + `git_commit_id` + relative `path` populated;
a second test confirms the legacy local-slug shape still parses
and resolves. Schema rejects partially-specified git entries
(`git_url` without `git_commit_id`, etc.) with a clear
`SpecError`.

**AC-4 — The ade-bench fixture's task.toml uses an image with
claude on PATH.**
Verified by: `grep '^docker_image' tests/fixtures/ade_bench/
tasks/adebench-fixture-001/task.toml` returns
`docker_image = "dab-agent:latest"` (or the equivalent
exeuntu-baked image); the fixture's Dockerfile is updated or
deleted in favor of relying on the pre-built image.

**AC-5 — `uv run rk run examples/specs/ade-bench-claude.yaml`
exits 0 against a REAL ade-bench task (pulled from
`laude-institute/harbor-datasets.git`) and writes a
`summary.json` whose `score` field is numeric (per AC-3's
"present and numeric" rule) AND whose run-dir contains zero
plaintext occurrences of the resolved auth token.**
Verified by: live invocation of the acceptance command, exit 0,
`jq '.score' <run-dir>/summary.json` returns a number, and
`grep -r "$RESOLVED_TOKEN" <run-dir>` returns no matches.

**AC-6 — All carry-forward tests stay green.**
Verified by: `uv run pytest` from a clean checkout of the
FU-1 worktree branch tip exits 0 with the prior ~231 tests still
passing alongside the new FU-1 tests.

## Test plan

- **Unit tests:** translator no longer puts the token in kwargs;
  agent constructor no longer accepts resolved_auth_env;
  AdeBenchBenchmarkBlock parses both local-slug and git-task
  shapes; partially-specified git entries reject.
- **Integration tests:** rk run against a nop spec with auth
  forwarded (run-dir token grep returns clean); rk run against a
  real ade-bench task pulled via harbor's git-task path.
- **Acceptance command:** `uv run rk run examples/specs/
  ade-bench-claude.yaml` (updated to use a real
  `ade-bench-XXX` slug from
  `laude-institute/harbor-datasets.git`).

## Out of scope

- The four non-blocking findings from prior validation reports
  (M5 N-1..N-5, M4 F1..F3) — those remain tracked-forward;
  this entity does not address them.
- Adding a generic harbor-registry resolver for ade-bench (i.e.
  `DatasetConfig(name="ade-bench")` shape). The per-task
  `git_url`/`git_commit_id` path is sufficient for AC-5 and
  matches what harbor's RegistryClient produces. A full
  registry-lookup shape can land later.
- Extending the same git-task shape to the DAB adapter. M5 ships
  a local-dataset-only path; that is intentional for the
  bookreview-and-friends DAB datasets which live in
  `/Users/clkao/git/dataagentbench/data/` and would not benefit
  from git fetching.
- Rotating the leaked OAuth token. The captain decided to leave
  the leak in place during the fix-and-rerun rather than rotate
  immediately; that is a captain-owned decision outside the
  worker's scope.

## Stage Report: plan

- DONE: Plan steps map 1:1 to the 6 ACs in the FU-1 entity body. AC-1 (no auth plaintext in run-dir) is the riskiest contract — its test is the first task, plus a host-runnable grep gate that future runs can re-execute trivially.
  AC↔task map table in the plan header; Task 1 lands the failing integration test + `scripts/grep-run-dir-for-secrets.sh` host-runnable gate; the plan body's Step 4 of Task 1 smoke-tests the gate against the existing leaked run-dir at `_runs/ade-bench-claude-smoke/ccb869e65f79073f/` to prove the gate detects a known-bad input before AC-5 depends on it. Plan at `docs/razorback-implementation/plans/fu1-claude-auth-leak-ade-bench-real-task.md`.
- DONE: The plan reads M3's current implementation surface and proposes the smallest change set that moves auth from AgentConfig.kwargs to AgentConfig.env without breaking M3/M4 carry-forward tests. The host-side auth discovery discipline (.env-only, never os.environ) stays unchanged — only the in-container path changes.
  Task 2 deletes only the `kwargs["resolved_auth_env"]` line in `compat/harbor_0_6_6.py:127-145` and the `resolved_auth_env` parameter from `ClaudeCliAgent.__init__` (lines 25-58); the `env=dict(resolution.env)` keyword on `AgentConfig(...)` is untouched (that's the redacted surface via harbor's `templatize_sensitive_env` field_serializer). `razorback.agents.auth` (host-side .env / ~/.claude/benchmark-token discovery) is explicitly unchanged. Task 3 cascades the signature change through 7 existing test files and mirrors the same fix in `SpacedockSolverAgent` (same defect shape per AC-1's "any auth token" wording).
- DONE: The plan reads harbor's TaskConfig at `.venv/lib/python3.12/site-packages/harbor/models/trial/config.py` for the git_url/git_commit_id/path fields, and razorback's AdeBenchBenchmarkBlock + tasks loader, and proposes the smallest schema extension that accepts both legacy local-slug and new git-task shapes without breaking the M7 fixture path. Cite which laude-institute/harbor-datasets ade-bench task is the AC-5 acceptance target.
  Plan §"Acceptance task choice (AC-5)" names `ade-bench-airbnb001` at `git_commit_id: b4e82debfdd2aba9d91c41cd96a997dd549fcbb3` (first in the harbor registry; duckdb-variant — no Snowflake credentials needed; cross-reference exists in `/Users/clkao/git/ade-bench/tasks/airbnb001/`). Fallback `ade-bench-quickbooks002` documented per the FU-1 entity recommendation. Task 5 adds `AdeBenchTaskEntry` (pydantic model with `path/git_url/git_commit_id`, `extra="forbid"`) to the discriminated union; `AdeBenchBenchmarkBlock.tasks` becomes `list[str | AdeBenchTaskEntry]` (backwards-compatible — M7 fixture path still parses). Partial git entries reject via pydantic's missing-required-field machinery.

### Summary

Wrote a TDD-shaped 9-task plan for FU-1: AC-1 grep-gate-first (Task 1 makes the M3 leak reproducible as a failing integration test, plus a host-runnable `scripts/grep-run-dir-for-secrets.sh` so future runs trivially re-verify), AC-2 surface fix (Tasks 2 + 3 delete `kwargs.resolved_auth_env` from translator + `ClaudeCliAgent.__init__` + `SpacedockSolverAgent.__init__`, leaving only `AgentConfig.env`'s redacted-on-disk path), AC-3 schema widen (Tasks 5 + 6 add `AdeBenchTaskEntry` to the discriminated union; partial entries reject), AC-4 fixture image flip to `dab-agent:latest` (Task 4), AC-5 live run against `ade-bench-airbnb001` at the registry-pinned commit (Tasks 7 + 8), AC-6 full-suite green (Task 9). Host-side `.env` discipline in `razorback.agents.auth` is explicitly unchanged. Plan at `docs/razorback-implementation/plans/fu1-claude-auth-leak-ade-bench-real-task.md` on `main`.
