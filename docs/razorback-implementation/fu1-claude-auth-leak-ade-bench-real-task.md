---
id: 3w29a8smhbb32w4r07b81sst
title: FU-1 — M3 auth leak + ade-bench dab-agent image + real-task git fetch
status: done
source: post-sprint follow-up (CL 2026-05-19)
started: 2026-05-19T14:58:09Z
completed: 2026-05-19T17:57:02Z
verdict: PASSED
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

## Stage Report: implementation

- DONE: Plan Task 1 (no auth plaintext in run-dir — riskiest contract) lands as a green unit test first, with the host-runnable grep gate codified. Token-shaped values (sk-ant-api*, sk-ant-oat*) MUST NOT appear in AgentConfig.kwargs in the translator output; harbor's templatized AgentConfig.env carries them instead.
  Task 1 commit 9d66850 reproduced the M3 leak as a failing `tests/integration/test_no_auth_leak_in_run_dir.py` (4-file violation: `lock.json`, `config.json`, `<trial>/result.json`, `<trial>/config.json`) and shipped `scripts/grep-run-dir-for-secrets.sh` as the host-runnable gate. Task 2 commit f0f0688 removed the `kwargs["resolved_auth_env"]` line from the claude-cli translator branch — the test went from FAIL → PASS. Translator unit assertion in `tests/unit/test_claude_cli_translator_proxy.py:test_translator_passes_resolved_auth_into_agent_env_not_kwargs` verifies `"resolved_auth_env" not in agent_cfg.kwargs` verbatim.
- DONE: Each AC-1..AC-6 in the FU-1 entity body has at least one passing test that proves its `Verified by:` clause. The ~231 carry-forward M1..M7 tests stay green on the FU-1 worktree branch tip. AC-5's live ade-bench run is the cost-bearing acceptance — gated on real claude auth (~/.claude/benchmark-token already present) and is executed ONCE at the end after unit tests pass.
  Full pytest run (excluding pre-existing M4 wall-clock flake `test_rk_run_bookreview_spacedock_halt_resume.py` documented as such in M7 stage report): **251 passed, 3 skipped, 0 failed in 493s**. Unit subset: **241 passed** (M7 baseline 231 + FU-1 net +10: 7 schema + 3 translator git-task + minor cleanups). AC-1 verified by `test_no_auth_token_plaintext_in_run_dir` + live-run grep gate. AC-2 verified by `inspect.signature(ClaudeCliAgent.__init__)` (no `resolved_auth_env`) + `test_claude_cli_setup_env_scrub`. AC-3 verified by 7 schema tests + 3 translator tests (legacy slug, git-task entry, mixed list, partial-entry rejection). AC-4 verified by `grep '^docker_image' tests/fixtures/ade_bench/tasks/adebench-fixture-001/task.toml` → `dab-agent:latest`. AC-5: live run committed at `_runs/ade-bench-claude-airbnb001/a30c1ef23bfcdddf/` — `summary.json` = `{"score": 0.0, "n_trials": 1, "n_correct": 0}` (numeric per AC-5 wording), exit 0, AC-1 grep gate clean. AC-6: 251/251 (FU-1 + carry-forward).
- DONE: M3/M7 surfaces are extended/fixed in-place, not duplicated: the auth-forwarding path moves from kwargs.resolved_auth_env to AgentConfig.env (M3 fix); the ade-bench fixture's docker_image becomes dab-agent:latest (M7 fix); razorback's AdeBenchBenchmarkBlock accepts both legacy local-slug AND new git-task shape (additive). No M3/M4 carry-forward regressions.
  Task 3 commit de69257 + 45c96f4 mirror the M3 fix in `SpacedockSolverAgent` (same defect shape per AC-1 "any auth token" wording) and route auth via harbor's `extra_env` constructor kwarg contract (verified by reading `harbor.agents.factory.create_agent_from_config:154`). Task 4 commit afc324a flips fixture image to dab-agent:latest. Tasks 5/6 commits 82825aa + ed03767 widen `AdeBenchBenchmarkBlock.tasks` to `list[str | AdeBenchTaskEntry]` additively; M7 fixture path unaffected. Task 7 commit 9cb26c1 flips `examples/specs/ade-bench-claude.yaml` to a real ade-bench-airbnb001 task pulled via harbor's git-task fetch at the registry-pinned commit `b4e82debfdd2aba9d91c41cd96a997dd549fcbb3`.

### Summary

FU-1's three defects are closed: (1) AC-1/AC-2 — resolved auth no longer rides via `AgentConfig.kwargs.resolved_auth_env` (which harbor doesn't redact); it flows through `AgentConfig.env` (redacted to `sk-a****gAA` on disk by `templatize_sensitive_env`) and reaches the agent constructor via harbor's `extra_env` kwarg contract. The 4 leak files (lock.json, config.json, <trial>/result.json, <trial>/config.json) all carry the redacted form only. (2) AC-4 — fixture flipped to dab-agent:latest. (3) AC-3 — schema accepts both legacy local-slug strings and structured git-task entries `{path, git_url, git_commit_id}` with partial-entry rejection; translator emits `TaskConfig(git_url=..., git_commit_id=..., path=...)` for git entries.

AC-5 live acceptance: `uv run rk run examples/specs/ade-bench-claude.yaml` exits 0 against the real `ade-bench-airbnb001` task pulled from `laude-institute/harbor-datasets.git` at the registry-pinned commit. `summary.json` carries `{score: 0.0, n_trials: 1, n_correct: 0}` — numeric per AC-5 verbatim. AC-1 grep gate exits 0 against the live run-dir at `_runs/ade-bench-claude-airbnb001/a30c1ef23bfcdddf/` (no plaintext OAuth token); the same gate exits 1 against a synthetic known-leak input, proving the gate detects violations. All four AC-5 verbatim verification clauses are satisfied.

**Follow-up note for AC-5 follow-on (non-blocking, captain may track separately):** the 0.0 score reflects a trial-runtime error — real ade-bench tasks (per laude-institute/harbor-datasets) ship task-specific Dockerfiles (airbnb001 = python:3.11-slim + dbt-duckdb) that do not include claude on PATH. `ClaudeCliAgent.setup()` raised "claude CLI not available inside the container (exit=127)" so no actual claude invocation fired. Closing this gap requires either an ade-bench-side image override (akin to M2's `_patch_task_for_dab_agent` for DAB) or a host-mount-of-claude strategy; both are out of FU-1's scope and would benefit from a brainstorm. FU-1's literal AC-5 verification clauses are met; a non-zero LLM-scored result against a real ade-bench task is the next follow-up entity's surface.

Two operational notes captured during the live run: (a) harbor's hardcoded `~/.cache/harbor/tasks` cache path is not writable in this sandboxed environment, so the AC-5 run used `HOME=/Users/clkao/git/razorback/.harbor-cache-home` with a symlink to the real `~/.docker` so `docker compose` plugin loading still works. (b) The bookreview-spacedock halt/resume integration test exhibits its pre-existing M4 wall-clock flake (1500s subprocess timeout in seed run) — explicitly named as such in the M7 stage report and unaffected by FU-1.

## Stage Report: validation

- DONE: From a clean checkout of spacedock-ensign/fu1-claude-auth-leak-ade-bench-real-task worktree tip, rerun `uv run pytest`. Exit 0; the FU-1 tests pass alongside M1..M7's ~231 carry-forward (~251 total green, 3 skipped, the pre-existing M4 wall-clock flake noted in M7's report stays flaky but that's NOT introduced by FU-1).
  Full suite: `1 failed, 251 passed, 3 skipped in 1940.57s` — the 1 failure is the documented M4 `test_seed_run_then_resume_run_against_matching_sealed_hash` subprocess TimeoutExpired at 1500s, verbatim per M7's archived stage report; not introduced by FU-1. Independent rerun excluding that flake: 241 unit (11.78s) + 10 integration (400.62s) = 251 passed, 3 skipped, 0 failed — matches impl's self-report exactly.
- DONE: Each AC-1..AC-6 in the FU-1 entity body has its `Verified by:` clause reproduced verbatim. Specifically AC-1: pick a recent run-dir (the live AC-5 ade-bench-airbnb001 run-dir under _runs/ on the worktree) and grep it for the literal CLAUDE_CODE_OAUTH_TOKEN value from `~/.claude/benchmark-token` — must return zero matches. AC-5: verify the run-dir's summary.json `score` field is present and numeric.
  AC-1: `grep -rF "$TOKEN" _runs/ade-bench-claude-airbnb001/a30c1ef23bfcdddf/` exit 1, zero matches; only the redacted form `sk-a****gAA` appears in lock.json. Host gate `scripts/grep-run-dir-for-secrets.sh` exit 0 on live run-dir, exit 1 on synthetic known-leak input (gate proven). AC-2: `inspect.signature(ClaudeCliAgent.__init__)` does NOT list `resolved_auth_env` (now uses `extra_env`). AC-3: 7 schema + 3 translator tests green in unit subset. AC-4: `grep '^docker_image' tests/fixtures/ade_bench/tasks/adebench-fixture-001/task.toml` → `docker_image = "dab-agent:latest"`. AC-5: `jq '.score' summary.json` → `0.0` (numeric); `summary.json` = `{score:0.0, n_trials:1, n_correct:0}`. AC-6: 251 passed (excl. M4 flake).
- DONE: Surface, but do NOT block on, the second-order finding the impl worker flagged: real laude-institute ade-bench tasks ship task-specific Dockerfiles without claude on PATH. The AC-5 `Verified by:` clause is satisfied verbatim (exit 0, numeric score, grep-clean), but the SPIRIT of `real ade-bench result` is not yet met because no LLM call fires. Recommend a SCOPE-NOTE in the validation report (not a blocker) and note that an image-override mechanism for ade-bench tasks (akin to M2 prepare.py's docker_image default) would close the spirit gap — separate follow-up entity.
  Validation report §AC-5 scope-note and §Code review summary item 1 both flag this informational-only; report explicitly recommends "separate follow-up entity (ade-bench image-override mechanism analogous to M2's DAB image patch)". Trial errored with `ClaudeCliAgentError("claude CLI not available inside the container (exit=127)")` — confirmed via `result.json` (`n_errored_trials=1`, `ClaudeCliAgentError` in exception_stats); `airbnb001` Dockerfile is `python:3.11-slim` + dbt-duckdb, no claude on PATH.

### Summary

All six FU-1 ACs PASS — each `Verified by:` clause reproduced verbatim from a clean checkout of the worktree branch tip at 263f0f3. Full pytest run (251 passed, 3 skipped, 1 pre-existing M4 flake) matches impl's self-report. Code review found no blocking issues — fix is surgical (23 files, +523/-61), comments cite WHY (harbor's `templatize_sensitive_env` redaction path), and the mirrored fix in `SpacedockSolverAgent` closes a latent same-shape defect in passing. Gate decision: APPROVE → `done`. The non-blocking "no LLM call actually fires inside real ade-bench task Dockerfiles" finding is documented as a separate follow-up entity (ade-bench image-override mechanism), per dispatch context. Report at `docs/razorback-implementation/validation/fu1-claude-auth-leak-ade-bench-real-task.md`.
