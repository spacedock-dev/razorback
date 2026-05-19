# FU-1 — Claude Auth Leak Fix + ade-bench dab-agent Image + Real Task git fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Per CL's "Validating new mechanisms" rule, the riskiest contract (AC-1: tokens never persisted in run-dir) is exercised in Task 1 before any of the schema/image scaffolding lands.

**Goal.** Close three FU-1 defects surfaced when CL first attempted a real-claude live run against ade-bench: (1) the M3 auth path leaks the resolved OAuth token in plaintext to four run-dir files because the token is forwarded via `AgentConfig.kwargs.resolved_auth_env` (harbor only redacts `agent.env`); (2) the M7-shipped ade-bench fixture's `task.toml` declares `docker_image = "alpine:3.19"` which lacks claude, so `claude --version` exits 127 and no live run can score; (3) razorback's `AdeBenchBenchmarkBlock` accepts only `tasks_root: Path` + slug list — it has no way to point harbor at a git-fetched real ade-bench task. The headline deliverable is **AC-5**: `uv run rk run examples/specs/ade-bench-claude.yaml` exits 0 against a real `laude-institute/harbor-datasets` ade-bench task and writes a `summary.json` whose `score` is numeric AND whose run-dir contains zero plaintext occurrences of the resolved auth token.

**Architecture.** Three small surfaces, in order of risk:

1. **`razorback.compat.harbor_0_6_6` + `razorback.agents.claude_cli` + `razorback.agents.spacedock_solver`** — stop forwarding the resolved auth token via `AgentConfig.kwargs`. The token reaches the container via `AgentConfig.env`, which harbor's `templatize_sensitive_env` redacts before it touches `lock.json` / `config.json` / `result.json` on disk. The agent reads the credential from `os.environ` inside the container (where harbor's runtime stamps it before invoking the agent's `setup()`). The host-side `.env` / `~/.claude/benchmark-token` discovery in `razorback.agents.auth` is unchanged — that discipline (never `os.environ` on the host) is correct.

2. **`tests/fixtures/ade_bench/tasks/adebench-fixture-001/task.toml`** — flip `docker_image = "alpine:3.19"` to `docker_image = "dab-agent:latest"` (the exeuntu-baked image M2/M3/M5 already use, which bakes in claude+codex+uv). Delete the now-redundant `environment/Dockerfile` (alpine had a custom Dockerfile baking in `bash`; dab-agent already has bash, claude, uv, jq, git, etc.). M3's bookreview run, M5's full-DAB run, and M7's nop-agent ade-bench smoke all use this image; FU-1 closes the gap so the claude-cli ade-bench wiring is symmetric.

3. **`razorback.spec.schema.AdeBenchBenchmarkBlock` + `razorback.benchmarks.ade_bench.tasks.resolve_task_dirs` + `razorback.compat.harbor_0_6_6._build_ade_bench`** — widen the `tasks: list[...]` schema so each entry is either a legacy local-slug string (current shape, kept backwards-compatible for the M7 fixture path) OR a structured object `{path: str, git_url: str, git_commit_id: str}` matching harbor's `TaskConfig` git-task shape. The translator maps git-shaped entries to `TaskConfig(path=..., git_url=..., git_commit_id=...)` directly — harbor handles the fetch via its `GitTaskId.get_local_path()` machinery. No `~/.cache/razorback/ade-bench` clone path is needed; harbor's task-fetch is the right surface.

**Tech stack:** Python 3.12, `uv`, Pydantic 2.11, harbor 0.6.6 (pinned, unchanged), pytest 8 with `pytest-asyncio` 0.24, Docker via Colima. No new external dependencies. The `dab-agent:latest` image is already built (M2 ships its build via setup.sh outside FU-1's scope — `docker images | grep dab-agent` confirms presence in the captain's local env per the leak-incident reproduction).

**Source of truth.** The design doc at `/Users/clkao/git/dataagentbench/docs/superpowers/specs/2026-05-18-razorback-python-on-harbor.md`. Section anchors below cite it as `§N.N`. The 6 ACs live in the FU-1 entity at `docs/razorback-implementation/fu1-claude-auth-leak-ade-bench-real-task.md`. Harbor's `TaskConfig` git-task shape comes from `.venv/lib/python3.12/site-packages/harbor/models/trial/config.py:128-185`. The harbor-datasets registry payload (commit pin) comes from `/tmp/harbor-study/registry.json` (`git_commit_id: b4e82debfdd2aba9d91c41cd96a997dd549fcbb3` for every ade-bench task).

**M3 / M7 inputs (do not duplicate):**

- **From M3** (`src/razorback/agents/auth.py`): `resolve_claude_auth(project_root, home)` returns an `AuthResolution` with `mode ∈ {"api-key", "oauth"}` and `env: dict[str, str]` carrying one key. Host-side discipline (never `os.environ`; `.env` via `dotenv_values` or `~/.claude/benchmark-token`) is unchanged. FU-1 changes only how the resolved value is forwarded to the container.
- **From M3** (`src/razorback/agents/claude_cli.py:25-58`): `ClaudeCliAgent.__init__` currently accepts `resolved_auth_env: dict[str, str] | None`. AC-2 deletes that parameter; the agent reads `os.environ["ANTHROPIC_API_KEY"]` or `os.environ["CLAUDE_CODE_OAUTH_TOKEN"]` inside `setup()` after harbor populates the container env from `AgentConfig.env`. The co-mingling check (refuse both) moves from `__init__` to `setup()` since that's where `os.environ` is observable.
- **From M3** (`src/razorback/compat/harbor_0_6_6.py:127-145`): the `ClaudeCliAgentBlock` branch of `_build_agent_config` populates both `kwargs={"resolved_auth_env": ...}` AND `env=dict(resolution.env)`. AC-1+AC-2 delete the `resolved_auth_env` kwarg; `env=dict(resolution.env)` is the only surface that reaches the container.
- **From M3** (`src/razorback/compat/harbor_0_6_6.py:101-126`): the `SpacedockSolverAgentBlock` branch has the SAME defect (`kwargs={"resolved_auth_env": ...}` plus duplicate `env=`). FU-1's AC-1 is scoped to "no plaintext in run-dir for any razorback-shipped agent"; the spacedock-solver fix is in-scope per AC-1's verbatim "any auth token" wording. The agent class fix mirrors claude-cli's (`SpacedockSolverAgent.__init__` no longer accepts `resolved_auth_env`; reads from `os.environ` at run time). The M4 + M5 carry-forward tests that pass `resolved_auth_env=...` to the constructor must update to the env-only shape (Task 4).
- **From M7** (`src/razorback/spec/schema.py:87-91`): `AdeBenchBenchmarkBlock` has `tasks: list[str] = Field(min_length=1)`. FU-1 widens this to `list[str | AdeBenchTaskEntry]` where `AdeBenchTaskEntry` is a new pydantic model with `path: str, git_url: str, git_commit_id: str` and `extra="forbid"`. Partial git entries (`git_url` without `git_commit_id` etc.) fail at validation time with a clear `SpecError`.
- **From M7** (`src/razorback/benchmarks/ade_bench/tasks.py`): `resolve_task_dirs(tasks_root, tasks)` returns a list of absolute `Path`s. FU-1's widened shape returns a list of `TaskConfig`-ready records — either `(path=...)` for legacy slugs or `(path=..., git_url=..., git_commit_id=...)` for git entries. The translator change is mechanical.
- **From M7** (`tests/fixtures/ade_bench/tasks/adebench-fixture-001/task.toml`): the M7 fixture uses `docker_image = "alpine:3.19"`. AC-4 flips this to `dab-agent:latest`. The fixture's `environment/Dockerfile` is deleted (dab-agent already provides bash). The M7 nop-smoke (which exits before claude is needed) continues to pass because the nop agent does not invoke `claude`. M7's `test_ade_bench_translator.py` and `test_ade_bench_aggregate.py` continue to pass without modification (they don't grep `task.toml` for `alpine`).

**Authoritative external references — harbor's git-task fetch path:**

`TaskConfig.is_git_task()` returns `True` when `git_url is not None`. `TaskConfig.get_task_id()` returns a `GitTaskId(git_url, git_commit_id, path)` whose `get_local_path()` materializes the task into harbor's local cache (`~/.cache/harbor/tasks/<sha>/<path>` per harbor's resolver). Harbor's docker environment loads the task from that local path before container build. FU-1 does NOT need to write any clone logic — harbor's `GitTaskId.get_local_path()` is the right surface. The first invocation of `rk run` against a git-shaped spec triggers the fetch (cold cache → clone → checkout); subsequent invocations re-use the cache.

The harbor-datasets ade-bench commit pin `b4e82debfdd2aba9d91c41cd96a997dd549fcbb3` is the registry's pin at the time of M7 (per `/tmp/harbor-study/registry.json`). FU-1's AC-5 spec uses this exact pin so the run is fully reproducible.

**Acceptance task choice (AC-5):**

The FU-1 entity body recommends `ade-bench-quickbooks002` "unless a smaller/cheaper task exists." Inspection of the registry shows 48 ade-bench tasks at the same `git_commit_id`. All ade-bench tasks share the same compose-services environment (`shared/defaults/docker-compose.yaml` + duckdb or snowflake variant per task; the M7 plan §6.5 divergence call documents this). Cost-per-task is dominated by the agent's reasoning cost on the dbt-task instruction, not the compose stack, so "smaller" reduces to "instruction complexity." `ade-bench-airbnb001` is the canonical first-task in the harbor registry order; the M7 plan named `ade-bench-simple002` but that slug is NOT in the registry (it's a hypothetical from the M7 plan's notes). The two real candidates are `ade-bench-airbnb001` (first in the registry; duckdb-variant present in `/Users/clkao/git/ade-bench/tasks/airbnb001/` for cross-reference) and `ade-bench-quickbooks002` (entity-recommended). **Plan choice: `ade-bench-airbnb001`** — first-listed in the registry, duckdb-variant (in-container state, no Snowflake credentials needed for the AC-5 smoke), well-known cross-reference exists. If `airbnb001` requires Snowflake (the harbor-datasets variant may differ from the local checkout), fall back to `quickbooks002` as Task 7 explicitly documents.

**Riskiest contract first (Task 1):**

Per CL's "Validating new mechanisms" rule and the FU-1 checklist item #1 verbatim: "AC-1 (no auth plaintext in run-dir) is the riskiest contract — its test is the first task, plus a host-runnable grep gate that future runs can re-execute trivially."

Task 1 lands the smallest possible end-to-end exercise of the **token-never-on-disk** mechanism: a `tests/integration/test_no_auth_leak_in_run_dir.py` that (a) writes a synthetic `.env` carrying a known sentinel value (`ANTHROPIC_API_KEY=sk-ant-TEST-SENTINEL-DO-NOT-USE-XYZ`) under a tmp project_root, (b) runs `rk run` against a nop-agent ade-bench spec (cost-free; the auth resolution still fires because the spec carries `agent.kind=claude-cli`... wait, the nop agent doesn't trigger auth resolution. Correct shape: the test uses a CLAUDE-CLI spec but a TASK that fails fast — the fixture task's verifier always emits `reward=0`, so the claude CLI is never actually called. The wiring still puts auth on `AgentConfig.env`; harbor still writes `config.json` / `lock.json` / `result.json`; the grep gate runs against the final run-dir), (c) asserts `grep -r "sk-ant-TEST-SENTINEL-DO-NOT-USE-XYZ" <run-dir>` returns no matches. This test FAILS against M3's current code (the literal sentinel appears in `kwargs.resolved_auth_env`) and PASSES after Task 2's translator + agent surface fix.

**The grep gate is also exposed as a host-runnable script** (`scripts/grep-run-dir-for-secrets.sh`) so future runs can re-run it trivially against any `_runs/<experiment>/<run-id>/` path. The script greps for both `ANTHROPIC_API_KEY=...`-shaped values and `CLAUDE_CODE_OAUTH_TOKEN=...`-shaped values; it accepts a run-dir path argument and the literal token to scan for, and exits non-zero if any plaintext occurrence is found (harbor's `sk-a****gAA` redacted form is allowed).

If Task 1's test cannot be made to fail against M3's current code (e.g., harbor's recent versions silently strip `kwargs` on disk after some change), STOP and `SendMessage(to="team-lead", message="FU-1 Task 1: cannot reproduce the M3 leak against current harbor 0.6.6 + razorback; need design clarification.")`. The plan does NOT proceed past Task 1 until the failure-then-fix demonstration is concrete.

**AC ↔ task map (1:1):**

| AC | Governing §-cite / external reference | Task(s) |
|----|---------------------------------------|---------|
| AC-1 — Auth tokens never appear in plaintext in any run-dir file written by razorback. Translator unit test asserts no `kwargs.resolved_auth_env`; integration test greps run-dir for the literal token; only `templatize_sensitive_env`'s redacted form may appear. | §6.2 (BaseAgent contract), harbor's `templatize_sensitive_env` (`AgentConfig._serialize_env` field_serializer) | Task 1 (RISKIEST: failing test + grep gate), Task 2 (translator + agent surface fix), Task 8 (acceptance grep) |
| AC-2 — `ClaudeCliAgent.__init__` no longer accepts the `resolved_auth_env` kwarg; the agent reads auth from container env (which harbor populates via `AgentConfig.env`). Host-side `.env` discipline in `razorback.agents.auth` unchanged. | §6.2 ("token injection from harbor's required-env declaration"), M3 entity body AC-3 (host-side `.env`-only auth) | Task 2 (`ClaudeCliAgent` signature change + `os.environ` read in `setup()`), Task 3 (carry-forward test updates) |
| AC-3 — `AdeBenchBenchmarkBlock` accepts a `tasks: list` whose entries are either local-slug strings OR objects with `{path, git_url, git_commit_id}` matching harbor's `TaskConfig` git-task shape. Partial git entries reject with a clear `SpecError`. | Harbor's `TaskConfig` (`harbor/models/trial/config.py:128-185`), M7's `AdeBenchBenchmarkBlock` (current local-slug-only shape) | Task 5 (schema widen + translator), Task 6 (`SpecError` unit tests for partial entries) |
| AC-4 — The ade-bench fixture's `task.toml` uses an image with claude on PATH. `grep '^docker_image' <task.toml>` returns `docker_image = "dab-agent:latest"`. | M3's bookreview-claude run uses `dab-agent:latest`; M2's `_patch_task_for_dab_agent` in `prepare.py` already does this for DAB; M7 fixture lagged behind. | Task 4 (fixture image flip; delete `environment/Dockerfile`) |
| AC-5 — `uv run rk run examples/specs/ade-bench-claude.yaml` exits 0 against a REAL ade-bench task pulled from `laude-institute/harbor-datasets.git` and writes a `summary.json` whose `score` is numeric AND whose run-dir contains zero plaintext occurrences of the resolved auth token. | §M3 (ClaudeCliAgent end-to-end), §6.5 (ade-bench adapter), harbor's `GitTaskId.get_local_path()` | Task 7 (update `examples/specs/ade-bench-claude.yaml` to git-task shape + real slug), Task 8 (live acceptance + grep verification) |
| AC-6 — All carry-forward tests stay green. `uv run pytest` exits 0 with the prior ~231 tests still passing alongside the new FU-1 tests. | M1–M7 carry-forward; M3's `test_claude_cli_setup_env_scrub.py`, `test_claude_cli_translator_proxy.py`, `test_spacedock_*` need updates to the env-only constructor shape. | Task 3 (carry-forward updates for env-only shape), Task 9 (full-suite green) |

**Test-first ordering:**

Tasks 1, 2, 5, 6 are TDD: failing test first, smallest implementation that makes it pass, then refactor. Task 3 is mechanical (cascade signature changes through existing tests). Tasks 4, 7 are config changes verified by greppable assertions. Task 8 is the live acceptance. Task 9 is the green-suite gate.

---

## Task 1 — Write failing test for "no auth plaintext in run-dir" (AC-1, RISKIEST contract)

**Goal.** Demonstrate the M3 leak with a concrete failing integration test, AND ship a host-runnable grep gate that future runs can re-execute trivially. After this task, before any implementation lands, the test fails with the literal sentinel appearing in `kwargs.resolved_auth_env` inside `lock.json` / `config.json` — proving the contract is broken in main.

**Files:**
- `tests/integration/test_no_auth_leak_in_run_dir.py` (NEW)
- `scripts/grep-run-dir-for-secrets.sh` (NEW; chmod +x)

**Steps:**

- [ ] **Step 1: Author the failing integration test.** Create `tests/integration/test_no_auth_leak_in_run_dir.py` with a single test that (a) writes a tmp `.env` carrying a sentinel `ANTHROPIC_API_KEY=sk-ant-TEST-SENTINEL-FU1-DO-NOT-USE-XYZ123` under `tmp_path / "project"`; (b) writes a minimal nop-agent ade-bench spec using `tests/fixtures/ade_bench/tasks/adebench-fixture-001` (the current alpine-based fixture — claude-cli auth flows through the translator regardless of agent.kind only if the spec uses `claude-cli`, so use `agent.kind=claude-cli` with the FIXTURE task whose task.toml currently uses alpine; the agent's `setup()` will fail because alpine lacks claude, BUT only AFTER the orchestrator writes `config.json` / `lock.json` — both of which contain the leak. The test runs `rk run` via the in-process `razorback.runtime.run` API or a subprocess, expects a non-zero exit, and asserts on the run-dir contents); (c) calls `grep -r "sk-ant-TEST-SENTINEL-FU1-DO-NOT-USE-XYZ123" <run-dir>` and asserts zero matches; (d) calls `grep -r "sk-a\*\*\*\*Z123" <run-dir>` (the `templatize_sensitive_env` redaction shape) and asserts AT LEAST ONE match in `<run-dir>/config.json` (proving the env-block carry path still works, just redacted). Use `subprocess.run(["grep", "-r", ...])` so the assertion mirrors the AC-5 acceptance grep verbatim.

  - **Subtle point:** the test needs `rk run` to write the run-dir files BEFORE the agent setup fails. Razorback's runtime writes `config.json` / `lock.json` at job start (before any container spins up); harbor's `JobConfig.write_*` is invoked synchronously by harbor's `Job.create()`. So even with an `agent.kind=claude-cli` spec against an alpine task (which will fail at `setup()`), the leak files are written first. If this turns out to be incorrect (harbor may defer some writes), the alternative is to use a `task.toml` that completes successfully (e.g., a synthetic verifier that always emits `reward=0` and `setup()` that's a no-op) — Task 4 provides that path implicitly once the fixture image is flipped to `dab-agent:latest`.

- [ ] **Step 2: Run the test against `main` (pre-fix).** From `/Users/clkao/git/razorback`, run `RAZORBACK_RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_no_auth_leak_in_run_dir.py -v`. Expected: the test FAILS at the grep-zero-matches assertion, because `lock.json` and `config.json` carry `"resolved_auth_env": {"ANTHROPIC_API_KEY": "sk-ant-TEST-SENTINEL-FU1-DO-NOT-USE-XYZ123"}` (verbatim, unredacted). The failure message must show the literal sentinel in the diff output — this is the contract-broken-in-main proof.

  - If the test cannot reach the failing state (e.g., harbor's recent changes silently strip `kwargs` from `config.json`), STOP and `SendMessage(to="team-lead", message="FU-1 Task 1: cannot reproduce the M3 leak against current harbor 0.6.6 + razorback main; the AC-1 contract may already be partially satisfied. Need clarification on what the leak surface looks like before scaffolding the fix.")`.

- [ ] **Step 3: Author the host-runnable grep gate.** Create `scripts/grep-run-dir-for-secrets.sh`:
  ```bash
  #!/usr/bin/env bash
  # ABOUTME: AC-1 grep gate — fail non-zero if any run-dir file contains plaintext claude auth.
  # ABOUTME: Allowed: harbor's templatize_sensitive_env redacted shape (e.g., "sk-a****gAA").
  set -euo pipefail
  RUN_DIR="${1:?usage: $0 <run-dir> [literal-token]}"
  TOKEN="${2:-}"
  if [ -z "$TOKEN" ]; then
      echo "usage: $0 <run-dir> <literal-token>" >&2
      echo "  scans <run-dir> for plaintext occurrences of <literal-token>." >&2
      exit 2
  fi
  matches=$(grep -r --include='*.json' --include='*.yaml' --include='*.jsonl' --include='*.txt' --include='*.log' -F -- "$TOKEN" "$RUN_DIR" || true)
  if [ -n "$matches" ]; then
      echo "AC-1 VIOLATION: literal token found in run-dir:" >&2
      echo "$matches" >&2
      exit 1
  fi
  echo "AC-1 OK: no plaintext token in $RUN_DIR" >&2
  exit 0
  ```
  Chmod +x. The script accepts a run-dir path and the literal token to scan; exits 0 if clean, 1 if any plaintext match is found, 2 on usage error. This is the gate AC-5's acceptance command invokes after the live run.

- [ ] **Step 4: Smoke-test the grep gate against the existing leak.** Run `scripts/grep-run-dir-for-secrets.sh _runs/ade-bench-claude-smoke/ccb869e65f79073f "[REDACTED-ANTHROPIC-OAUTH-TOKEN]"`. Expected: exits 1 with the four-file violation message. This proves the gate works against a real leak before we depend on it for AC-5.

  - Caveat (named): the live-leaked run-dir is on disk in the captain's local checkout. Don't commit anything from that directory. Reference it only via the grep-gate smoke; do NOT add the directory's contents to git.

- [ ] **Step 5: Commit.** `git add tests/integration/test_no_auth_leak_in_run_dir.py scripts/grep-run-dir-for-secrets.sh && git commit -m "fu1 task 1: failing test + grep gate for AC-1 (no auth plaintext in run-dir)"`. Push to the FU-1 worktree branch.

**Acceptance for Task 1:** test fails against `main` with the literal sentinel visible in the grep output; the grep gate exits 1 against the real leaked run-dir; both new files committed.

---

## Task 2 — Translator + ClaudeCliAgent surface fix (AC-1 + AC-2)

**Goal.** Make Task 1's test pass with the smallest change: stop forwarding the resolved auth via `AgentConfig.kwargs`; remove `resolved_auth_env` from `ClaudeCliAgent.__init__`; the agent reads auth from `os.environ` inside the container at `setup()` time. The host-side `.env` discovery in `razorback.agents.auth` is unchanged.

**Files:**
- `src/razorback/compat/harbor_0_6_6.py` (lines 127-145: `ClaudeCliAgentBlock` branch)
- `src/razorback/agents/claude_cli.py` (lines 25-58, 92-100: `__init__` + `setup`)

**Steps:**

- [ ] **Step 1: Drop `resolved_auth_env` from `ClaudeCliAgentBlock` kwargs in the translator.** In `src/razorback/compat/harbor_0_6_6.py:127-145`, the current `kwargs` dict is:
  ```python
  kwargs: dict[str, Any] = {
      "resolved_auth_env": dict(resolution.env),
      "tools_allowed": list(spec.agent.tools_allowed),
      "sampling_temperature": spec.agent.sampling.temperature,
  }
  ```
  Remove the `resolved_auth_env` line. The `env=dict(resolution.env)` keyword on `AgentConfig(...)` remains — that's the redacted-on-disk path that flows the credential to the container. Result:
  ```python
  kwargs: dict[str, Any] = {
      "tools_allowed": list(spec.agent.tools_allowed),
      "sampling_temperature": spec.agent.sampling.temperature,
  }
  agent_cfg = AgentConfig(
      import_path="razorback.agents.claude_cli:ClaudeCliAgent",
      model_name=spec.agent.model,
      kwargs=kwargs,
      env=dict(resolution.env),  # unchanged — this is the redacted surface
  )
  ```

- [ ] **Step 2: Remove `resolved_auth_env` parameter from `ClaudeCliAgent.__init__`.** In `src/razorback/agents/claude_cli.py:25-58`:
  - Delete the `resolved_auth_env: dict[str, str] | None = None` keyword-only parameter.
  - Delete `env = dict(resolved_auth_env or {})` and the `self._resolved_auth_env = env` assignment.
  - Move the "refuse co-mingled auth" check to `setup()` (where `os.environ` is observable inside the container): assert that at most one of `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` is present in `os.environ`. If both → raise `ClaudeCliAgentError("ANTHROPIC_API_KEY and CLAUDE_CODE_OAUTH_TOKEN cannot both be set")` verbatim (test text preserved).

- [ ] **Step 3: Change `setup()` to read auth from `os.environ`.** In `src/razorback/agents/claude_cli.py:92-100`:
  - Replace `self._exec_env = {**PROXY_BLOCK_ENV, **self._resolved_auth_env}` with logic that reads from `os.environ` inside the container: collect whichever of `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` is set into a local dict, raise if both, raise if neither. Build `self._exec_env = {**PROXY_BLOCK_ENV, **resolved_env}` from the locally-collected dict.
  - **Important:** the agent runs INSIDE the container; harbor stamps `AgentConfig.env` into the container env at startup before invoking the python `BaseAgent.setup()`. So `os.environ` inside the container has the credential. This is the standard harbor `BaseAgent` contract per §6.2 ("token injection from harbor's required-env declaration").
  - **Reading from `os.environ` here is correct and is NOT a violation of AC-3 (M3's host-side `.env`-only rule).** AC-3 governs host-side discovery (the `razorback.agents.auth` module on the runner machine, NEVER reads `os.environ`). This is in-container — the credential has already been resolved on the host via `.env` and stamped to the container env by harbor. The FU-1 entity body verbatim: "The host-side auth discovery discipline (.env-only, never os.environ) stays unchanged — only the in-container path changes."

- [ ] **Step 4: Run Task 1's test — it now PASSES.** From `/Users/clkao/git/razorback`, run `RAZORBACK_RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_no_auth_leak_in_run_dir.py -v`. Expected: green. `config.json` / `lock.json` no longer carry `kwargs.resolved_auth_env`; `agent.env` still carries the redacted form (`sk-a****gAA`).

  - If the test still fails (the literal sentinel appears somewhere), inspect the failing files — there may be a third surface (e.g., harbor's `result.json` echoes agent kwargs into a different field). Form a SINGLE hypothesis and test it; do NOT add multiple fixes. The FU-1 entity body names four leaking files: `lock.json`, `<run-dir>/config.json`, `<trial>/config.json`, `<trial>/result.json`. All four should be clean after Task 2.

- [ ] **Step 5: Commit.** `git add src/razorback/compat/harbor_0_6_6.py src/razorback/agents/claude_cli.py && git commit -m "fu1 task 2: stop forwarding resolved_auth_env via kwargs; ClaudeCliAgent reads auth from container os.environ (AC-1, AC-2)"`.

**Acceptance for Task 2:** Task 1's test passes; `inspect.signature(ClaudeCliAgent.__init__)` does not list `resolved_auth_env`; running the existing M3 unit tests at this point is OUT OF SCOPE — Task 3 cascades the signature change through them.

---

## Task 3 — Carry-forward updates for M3, M4, M5 tests (AC-2, AC-6)

**Goal.** Update the existing claude-cli and spacedock-solver unit tests that pass `resolved_auth_env=...` to constructors. The agent classes no longer accept the kwarg; tests must use the env-only shape. Also mirror Task 2's fix in `SpacedockSolverAgent` (the FU-1 entity scopes AC-1 to "any auth token" — spacedock has the same defect).

**Files (existing; modify):**
- `tests/unit/test_claude_cli_setup_env_scrub.py` (5 tests pass `resolved_auth_env={...}` — convert to monkeypatching `os.environ`)
- `tests/unit/test_claude_cli_translator_proxy.py` (asserts on `kwargs["resolved_auth_env"]` — flip to asserting on `env["..."]`)
- `tests/unit/test_spacedock_prompt_drift.py`, `tests/unit/test_spacedock_seed_mismatch.py`, `tests/unit/test_spacedock_tools_allowed.py`, `tests/integration/test_spacedock_git_freeze.py` (4 files reference `resolved_auth_env`)
- `src/razorback/agents/spacedock_solver.py` (mirror Task 2 fix: drop `resolved_auth_env` param; read from `os.environ` in run-time path)
- `src/razorback/compat/harbor_0_6_6.py:101-126` (drop `resolved_auth_env` from spacedock-solver translator branch's kwargs; `env=dict(resolution.env)` carries the credential)

**Steps:**

- [ ] **Step 1: Mirror Task 2 fix in spacedock-solver.** In `src/razorback/agents/spacedock_solver.py:57-178`:
  - Delete the `resolved_auth_env: dict[str, str]` keyword-only parameter.
  - Delete `self._resolved_auth_env = dict(resolved_auth_env)`.
  - In the `run()`-path that previously did `{**self._resolved_auth_env, ...}` (line 178), build the env from `os.environ` inside the container the same way `ClaudeCliAgent.setup()` does. If the agent doesn't have its own setup-time check yet, add the alternation check (refuse both `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN`) at run-time path.

- [ ] **Step 2: Drop `resolved_auth_env` from spacedock-solver translator branch.** In `src/razorback/compat/harbor_0_6_6.py:101-126`, the `SpacedockSolverAgentBlock` branch's `kwargs` dict carries `"resolved_auth_env": dict(resolution.env)` (line 114). Delete that line. `env=dict(resolution.env)` (line 123) remains.

- [ ] **Step 3: Convert claude-cli test fixtures from constructor-arg to env-monkeypatching.** In `tests/unit/test_claude_cli_setup_env_scrub.py`, every test that currently constructs `ClaudeCliAgent(... resolved_auth_env={"ANTHROPIC_API_KEY": "sk-1"})` becomes:
  ```python
  def test_xxx(monkeypatch, tmp_path):
      monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-1")
      monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
      agent = ClaudeCliAgent(logs_dir=tmp_path / "logs")
      # ... rest of the test, which now exercises os.environ-reading setup()
  ```
  The "co-mingled both → refuse" test sets both env vars and asserts `setup()` raises `ClaudeCliAgentError` (verbatim message preserved). The "only oauth present" test sets only `CLAUDE_CODE_OAUTH_TOKEN`. AC-2 spirit preserved: only one credential reaches the exec env; the agent refuses if both are present.

- [ ] **Step 4: Flip translator test assertions.** In `tests/unit/test_claude_cli_translator_proxy.py:91` and `:113`, change `agent_cfg.kwargs["resolved_auth_env"] == {...}` to `agent_cfg.env == {...}` (the `env=` path carries the credential; redaction happens at serialization, not at the Python-object level — the in-memory `env` dict still has the literal value, which is fine; only the on-disk form is redacted via `_serialize_env`). Add ONE new assertion to each test: `"resolved_auth_env" not in agent_cfg.kwargs` (the AC-1 unit-test surface verbatim).

- [ ] **Step 5: Update spacedock fixtures.** For each of `test_spacedock_prompt_drift.py`, `test_spacedock_seed_mismatch.py`, `test_spacedock_tools_allowed.py`, `test_spacedock_git_freeze.py`: remove the `resolved_auth_env={...}` constructor kwarg; if the test exercises the agent's run-time env-reading path, monkeypatch `os.environ` instead. For tests that exercise only the translator → AgentConfig surface (e.g., `test_spacedock_seed_mismatch.py:77` which feeds a synthetic kwargs dict to a freeze refusal check), remove the `resolved_auth_env` key from the synthetic dict.

- [ ] **Step 6: Run the full unit suite.** `uv run pytest tests/unit/ -x` from `/Users/clkao/git/razorback`. Expected: all green. Any test that still references `resolved_auth_env` in a constructor call or a kwargs dict surfaces here and gets fixed individually.

- [ ] **Step 7: Commit.** `git add src/razorback/agents/spacedock_solver.py src/razorback/compat/harbor_0_6_6.py tests/unit/test_claude_cli_*.py tests/unit/test_spacedock_*.py tests/integration/test_spacedock_*.py && git commit -m "fu1 task 3: cascade env-only auth shape through M3/M4/M5 tests + mirror fix in SpacedockSolverAgent (AC-1, AC-2, AC-6)"`.

**Acceptance for Task 3:** `uv run pytest tests/unit/` exits 0; `grep -rn "resolved_auth_env" src/ tests/` returns zero hits (the symbol is entirely retired); the only remaining surface that resolves auth is `razorback.agents.auth.resolve_claude_auth` (unchanged) flowing into `AgentConfig.env` (unchanged path; only the kwargs duplicate is gone).

---

## Task 4 — Flip ade-bench fixture image to dab-agent:latest (AC-4)

**Goal.** The M7 fixture's `task.toml` declares `docker_image = "alpine:3.19"`, which lacks claude. AC-4 flips it to `dab-agent:latest` (the exeuntu-baked image M2/M3/M5 use). The fixture's `environment/Dockerfile` is no longer needed (dab-agent already has bash); delete it.

**Files:**
- `tests/fixtures/ade_bench/tasks/adebench-fixture-001/task.toml` (line 7: `docker_image`)
- `tests/fixtures/ade_bench/tasks/adebench-fixture-001/environment/Dockerfile` (DELETE if it exists)

**Steps:**

- [ ] **Step 1: Inspect the current fixture.** `cat tests/fixtures/ade_bench/tasks/adebench-fixture-001/task.toml`. Expected output includes `docker_image = "alpine:3.19"`. `ls tests/fixtures/ade_bench/tasks/adebench-fixture-001/environment/` shows the Dockerfile (if present).

- [ ] **Step 2: Flip the docker_image declaration.** Edit `task.toml` line 7: `docker_image = "alpine:3.19"` → `docker_image = "dab-agent:latest"`. Leave the other `[environment]` fields (`os = "linux"`, `cpus = 1`, `memory_mb = 512`) unchanged.

- [ ] **Step 3: Delete the now-redundant Dockerfile.** If `tests/fixtures/ade_bench/tasks/adebench-fixture-001/environment/Dockerfile` exists, `git rm` it. The alpine-based fixture added bash via `apk add`; dab-agent already has bash plus claude/codex/uv/jq/git/curl.

- [ ] **Step 4: Confirm dab-agent:latest is available locally.** `docker images dab-agent:latest --format '{{.Repository}}:{{.Tag}}'`. Expected: `dab-agent:latest`. If the image is not present (e.g., a clean dev box), run the M2 setup-step (`bash /Users/clkao/git/dataagentbench/benchmark/setup.sh --global` or whatever the M2 plan named) — this is outside FU-1's scope to author, but is the same setup M3's bookreview-claude run depends on. The plan's assumption is that this image is present on any machine running FU-1 acceptance (it's been built since M2 per the captain's local checkout).

- [ ] **Step 5: Verify M7 nop-smoke still passes.** Run `uv run pytest tests/unit/test_ade_bench_translator.py tests/unit/test_ade_bench_aggregate.py -v`. Expected: green. These tests don't read `task.toml`'s `docker_image` field; they only exercise the translator's spec → JobConfig shape.

- [ ] **Step 6: Commit.** `git add tests/fixtures/ade_bench/tasks/adebench-fixture-001/task.toml && git rm -f tests/fixtures/ade_bench/tasks/adebench-fixture-001/environment/Dockerfile 2>/dev/null; git commit -m "fu1 task 4: flip ade-bench fixture image to dab-agent:latest; delete redundant Dockerfile (AC-4)"`.

**Acceptance for Task 4:** `grep '^docker_image' tests/fixtures/ade_bench/tasks/adebench-fixture-001/task.toml` returns `docker_image = "dab-agent:latest"`; the fixture no longer ships an `environment/Dockerfile`; M7 carry-forward tests stay green.

---

## Task 5 — Widen AdeBenchBenchmarkBlock schema to accept git-task entries (AC-3)

**Goal.** Extend `AdeBenchBenchmarkBlock.tasks` from `list[str]` to `list[str | AdeBenchTaskEntry]` where `AdeBenchTaskEntry` is a new pydantic model with `path: str`, `git_url: str`, `git_commit_id: str` (all required) and `extra="forbid"`. The translator builds `TaskConfig(path=..., git_url=..., git_commit_id=...)` for git entries and `TaskConfig(path=<tasks_root>/<slug>)` for legacy slug entries. Backwards-compatible: all current M7 specs continue to parse and resolve.

**Files:**
- `src/razorback/spec/schema.py` (lines 87-91: `AdeBenchBenchmarkBlock`)
- `src/razorback/benchmarks/ade_bench/tasks.py` (rewrite `resolve_task_dirs` to return rich records)
- `src/razorback/compat/harbor_0_6_6.py:167-185` (`_build_ade_bench` consumes the rich records)
- `tests/unit/test_ade_bench_schema_git_tasks.py` (NEW)

**Steps:**

- [ ] **Step 1: Write the failing schema unit test.** Create `tests/unit/test_ade_bench_schema_git_tasks.py` with four tests:
  1. `test_legacy_slug_still_parses` — a spec with `tasks: ["adebench-fixture-001"]` parses, the resolved task list has one entry with `path` set and `git_url=None, git_commit_id=None`.
  2. `test_git_task_entry_parses` — a spec with `tasks: [{"path": "datasets/ade-bench/ade-bench-airbnb001", "git_url": "https://github.com/laude-institute/harbor-datasets.git", "git_commit_id": "b4e82debfdd2aba9d91c41cd96a997dd549fcbb3"}]` parses; the resolved record has all three fields populated.
  3. `test_partial_git_entry_rejects` — three sub-cases: `{path, git_url}` without `git_commit_id`; `{path, git_commit_id}` without `git_url`; `{git_url, git_commit_id}` without `path`. Each raises `SpecError` (or pydantic `ValidationError` that the spec parser wraps as `SpecError`) whose message names the missing field.
  4. `test_mixed_list_parses` — `tasks: ["adebench-fixture-001", {"path": "...", "git_url": "...", "git_commit_id": "..."}]` parses; the resolved list has two entries with the right shapes.

  Run `uv run pytest tests/unit/test_ade_bench_schema_git_tasks.py -v` — all four fail (the current schema only accepts `list[str]`).

- [ ] **Step 2: Widen the schema.** In `src/razorback/spec/schema.py`, add a new model right above `AdeBenchBenchmarkBlock`:
  ```python
  class AdeBenchTaskEntry(BaseModel):
      """Git-task entry matching harbor's TaskConfig git-task shape (FU-1 AC-3)."""
      model_config = ConfigDict(extra="forbid")
      path: str
      git_url: str
      git_commit_id: str
  ```
  Then change `AdeBenchBenchmarkBlock.tasks` from `list[str]` to `list[str | AdeBenchTaskEntry]`:
  ```python
  class AdeBenchBenchmarkBlock(BaseModel):
      model_config = ConfigDict(extra="forbid")
      kind: Literal["ade-bench"]
      tasks_root: Path
      tasks: list[str | AdeBenchTaskEntry] = Field(min_length=1)
  ```
  Pydantic 2's union type handling will accept strings as legacy entries and dicts as git entries. The `extra="forbid"` on `AdeBenchTaskEntry` rejects partial entries when a dict carries unknown keys; missing required fields fail at field validation. Run tests 1, 2, 4 from Step 1 — they pass. Test 3 (partial entry rejection) passes too — pydantic raises a `ValidationError` because the `AdeBenchTaskEntry` model requires all three fields.

- [ ] **Step 3: Rewrite `resolve_task_dirs` to return rich records.** In `src/razorback/benchmarks/ade_bench/tasks.py`, replace `resolve_task_dirs(tasks_root, tasks: list[str])` with a function that returns a list of `TaskConfig`-ready dicts:
  ```python
  from dataclasses import dataclass
  from pathlib import Path
  from razorback.spec.schema import AdeBenchTaskEntry

  @dataclass(frozen=True)
  class ResolvedTask:
      path: Path
      git_url: str | None = None
      git_commit_id: str | None = None

  def resolve_task_dirs(
      *,
      tasks_root: Path,
      tasks: list[str | AdeBenchTaskEntry],
  ) -> list[ResolvedTask]:
      root = Path(tasks_root).resolve()
      resolved: list[ResolvedTask] = []
      for entry in tasks:
          if isinstance(entry, str):
              task_dir = root / entry
              config = task_dir / "task.toml"
              if not config.exists():
                  raise FileNotFoundError(
                      f"ade-bench task '{entry}' not found at {task_dir} "
                      f"(missing task.toml); tasks_root={root}"
                  )
              resolved.append(ResolvedTask(path=task_dir))
          else:
              resolved.append(ResolvedTask(
                  path=Path(entry.path),
                  git_url=entry.git_url,
                  git_commit_id=entry.git_commit_id,
              ))
      return resolved
  ```
  **Important:** for git-task entries, the `path` is relative (per harbor's `GitTaskId(git_url, git_commit_id, path)` shape — see `harbor/models/trial/config.py:176-179`). We do NOT prepend `tasks_root` to git entries — harbor's `GitTaskId.get_local_path()` is responsible for materializing the path. We also do NOT pre-check that the task.toml exists for git entries (the materialization happens lazily at `rk run` time inside harbor).

- [ ] **Step 4: Update `_build_ade_bench` in the translator.** In `src/razorback/compat/harbor_0_6_6.py:167-185`, the current code is:
  ```python
  task_dirs = resolve_task_dirs(
      tasks_root=spec.benchmark.tasks_root,
      tasks=spec.benchmark.tasks,
  )
  ...
  tasks=[TaskConfig(path=p) for p in task_dirs],
  ```
  Replace with:
  ```python
  resolved = resolve_task_dirs(
      tasks_root=spec.benchmark.tasks_root,
      tasks=spec.benchmark.tasks,
  )
  tasks=[
      TaskConfig(
          path=r.path,
          git_url=r.git_url,
          git_commit_id=r.git_commit_id,
      )
      for r in resolved
  ],
  ```
  Harbor's `TaskConfig.validate_task_source` validator (`harbor/models/trial/config.py:140-157`) accepts the git-task shape (`git_url` set, `path` set, `name` unset — that's a valid git task per `is_git_task()`). The validator's only constraint on git tasks is "git_commit_id requires git_url" (line 154), which the schema enforces upstream.

- [ ] **Step 5: Run the schema unit tests + M7's existing translator tests.** `uv run pytest tests/unit/test_ade_bench_schema_git_tasks.py tests/unit/test_ade_bench_translator.py -v`. Expected: all green. The M7 translator test exercises the legacy local-slug path; FU-1's new tests exercise the git-task path.

- [ ] **Step 6: Commit.** `git add src/razorback/spec/schema.py src/razorback/benchmarks/ade_bench/tasks.py src/razorback/compat/harbor_0_6_6.py tests/unit/test_ade_bench_schema_git_tasks.py && git commit -m "fu1 task 5: widen AdeBenchBenchmarkBlock to accept git-task entries (AC-3)"`.

**Acceptance for Task 5:** the four schema tests pass; M7's translator tests stay green; the schema rejects partial git entries with a typed error; `grep -n "list\[str\]" src/razorback/spec/schema.py | grep -i "tasks"` returns zero hits (the literal type signature `list[str]` for tasks no longer exists; it's `list[str | AdeBenchTaskEntry]`).

---

## Task 6 — Translator unit test for end-to-end git-task path (AC-3)

**Goal.** Bridge from "schema parses" (Task 5) to "translator emits the right TaskConfig shape." A unit test feeds a spec with a git-shaped task entry to `spec_to_job_config()` and asserts the resulting `JobConfig.tasks[0]` has `git_url + git_commit_id + path` populated. This is the per-AC-3 verbatim "the translator produces a harbor TaskConfig with the git_url + git_commit_id + relative path populated" verification.

**Files:**
- `tests/unit/test_ade_bench_translator_git_task.py` (NEW)

**Steps:**

- [ ] **Step 1: Write the test.** Create `tests/unit/test_ade_bench_translator_git_task.py`:
  - `test_spec_to_job_config_with_git_task` — feed a spec with `agent.kind=nop` (no auth resolution needed) and one git-shaped task entry; assert `cfg.tasks[0].path == Path("datasets/ade-bench/ade-bench-airbnb001")`, `cfg.tasks[0].git_url == "https://github.com/laude-institute/harbor-datasets.git"`, `cfg.tasks[0].git_commit_id == "b4e82debfdd2aba9d91c41cd96a997dd549fcbb3"`, `cfg.tasks[0].is_git_task() is True`, `cfg.tasks[0].get_task_id()` returns a `GitTaskId` (import from `harbor.models.task.id`).
  - `test_spec_to_job_config_with_legacy_slug` — feed a spec with `tasks: ["adebench-fixture-001"]`; assert `cfg.tasks[0].path` is the resolved fixture path, `cfg.tasks[0].git_url is None`, `cfg.tasks[0].is_git_task() is False`.
  - `test_spec_to_job_config_mixed_list` — combine both shapes in one spec; assert both tasks present in `cfg.tasks` with the right shapes.

- [ ] **Step 2: Run and verify.** `uv run pytest tests/unit/test_ade_bench_translator_git_task.py -v`. Expected: green (Task 5's translator change already wired this).

- [ ] **Step 3: Commit.** `git add tests/unit/test_ade_bench_translator_git_task.py && git commit -m "fu1 task 6: translator unit test for end-to-end git-task path (AC-3)"`.

**Acceptance for Task 6:** all three tests green; the AC-3 verbatim verification clause "the translator produces a harbor TaskConfig with the git_url + git_commit_id + relative path populated" is asserted by a real test.

---

## Task 7 — Update examples/specs/ade-bench-claude.yaml to use a real harbor-datasets task (AC-5 prep)

**Goal.** The current spec at `examples/specs/ade-bench-claude.yaml` uses the local fixture (`tasks_root: tests/fixtures/ade_bench/tasks`, `tasks: [adebench-fixture-001]`). Flip it to fetch a REAL ade-bench task via harbor's git-task path: `ade-bench-airbnb001` at the registry-pinned commit. Keep `agent.kind=claude-cli` from M3.

**Files:**
- `examples/specs/ade-bench-claude.yaml`

**Steps:**

- [ ] **Step 1: Inspect the current spec.** `cat examples/specs/ade-bench-claude.yaml` — confirm it's the local-fixture shape from M7.

- [ ] **Step 2: Rewrite the benchmark block.** Change to:
  ```yaml
  version: 1
  experiment: ade-bench-claude-airbnb001
  agent:
    kind: claude-cli
    tools_allowed: []
  benchmark:
    kind: ade-bench
    tasks_root: .  # ignored when every entry is a git-task; kept for legacy slug compatibility
    tasks:
      - path: datasets/ade-bench/ade-bench-airbnb001
        git_url: https://github.com/laude-institute/harbor-datasets.git
        git_commit_id: b4e82debfdd2aba9d91c41cd96a997dd549fcbb3
  trials: 1
  observers:
    - kind: jsonl
      path: events.jsonl
    - kind: stdout
  ```
  - **`tasks_root` value rationale:** the field is still required by the schema (it has no default; M7's plan kept it `Path` not `Path | None`). When every entry is a git-task, the value is unused. Setting it to `.` keeps the spec syntactically valid. (Alternative: in Task 5, make `tasks_root: Path | None = None` and require it only when at least one entry is a string slug. Cleaner shape; but it's a wider schema change than AC-3 strictly requires. Plan choice: keep `tasks_root: Path` required for now; document that the value is ignored for git-only entries. The captain can request a follow-up to make it conditional.)

- [ ] **Step 3: Smoke-validate the spec (no live run).** Run `uv run rk validate examples/specs/ade-bench-claude.yaml` (M7's command). Expected: exit 0; warnings printed (per-trial-state-reset + tools_allowed warnings are expected from M7's wiring; they're informational). If `rk validate` rejects the spec, inspect the error and adjust the schema or the spec — do not modify both.

- [ ] **Step 4: Commit.** `git add examples/specs/ade-bench-claude.yaml && git commit -m "fu1 task 7: flip ade-bench-claude.yaml to a real harbor-datasets ade-bench-airbnb001 task (AC-5 prep)"`.

**Acceptance for Task 7:** the spec carries the git-task shape; `rk validate` exits 0; the spec is ready for Task 8's live acceptance.

---

## Task 8 — Live AC-5 acceptance + AC-1 grep verification

**Goal.** Run the AC-5 acceptance command end-to-end against a real claude CLI and a real ade-bench task. Verify (a) exit 0, (b) `summary.json` carries a numeric `score`, (c) `scripts/grep-run-dir-for-secrets.sh <run-dir> "$RESOLVED_TOKEN"` returns 0 (no plaintext token in the run-dir).

**Files:**
- (no source edits — this is the live-run verification)

**Steps:**

- [ ] **Step 1: Confirm `.env` carries `ANTHROPIC_API_KEY` OR `~/.claude/benchmark-token` carries an OAuth token.** Per M3's AC-3 host-side discipline, `razorback.agents.auth` resolves from one of these two surfaces. The captain's environment has one of them set (per the leak-incident reproduction). Capture the literal value via:
  ```bash
  RESOLVED_TOKEN=$(python -c "from razorback.agents.auth import resolve_claude_auth; from pathlib import Path; r = resolve_claude_auth(project_root=Path('/Users/clkao/git/razorback')); print(next(iter(r.env.values())))")
  ```
  Don't echo this anywhere it might persist beyond the shell session — it's the captain's live credential. Keep it in a shell variable only.

- [ ] **Step 2: Run the acceptance command.** From `/Users/clkao/git/razorback`:
  ```bash
  uv run rk run examples/specs/ade-bench-claude.yaml
  ```
  Expected: exit 0; the command emits a run-dir path (something like `_runs/ade-bench-claude-airbnb001/<run-id>/`). The first invocation will be slow because harbor's git-task fetch materializes the harbor-datasets repo into harbor's cache (~few hundred MB of clone); subsequent invocations are fast. Cost: one claude-opus-4-5 invocation against a single ade-bench dbt task; budget ~$0.50-$2.00 depending on instruction complexity.

  - **If the run fails for an `airbnb001`-specific reason** (e.g., the task's compose stack requires snowflake credentials), STOP and fall back to `quickbooks002` per the FU-1 entity's recommendation: change the spec's `path:` to `datasets/ade-bench/ade-bench-quickbooks002`, rerun. Document the fallback choice in the stage report.
  - **If the run fails because harbor's git-task fetch doesn't materialize the path correctly** (e.g., `path:` should be `ade-bench-airbnb001` not `datasets/ade-bench/ade-bench-airbnb001`), inspect harbor's actual checkout shape (look at `~/.cache/harbor/tasks/` after the failed fetch) and adjust the spec's `path:` accordingly. This is a single hypothesis test; do not add scaffolding around it.

- [ ] **Step 3: Verify `score` is numeric.** `jq '.score' <run-dir>/summary.json`. Expected: a number (float, possibly 0.0 if the agent's answer didn't pass the verifier — AC-5 verbatim: "numeric", not "non-zero").

- [ ] **Step 4: Run the AC-1 grep gate.** `scripts/grep-run-dir-for-secrets.sh <run-dir> "$RESOLVED_TOKEN"`. Expected: exits 0 with the "AC-1 OK: no plaintext token in <run-dir>" message. If exits 1, AC-1 has regressed — STOP and inspect the violating file. The most likely regression is harbor 0.6.6 adding a new file shape that echoes `agent.env` without going through `_serialize_env`; this would be a harbor upstream issue, not a razorback issue.

- [ ] **Step 5: Run the AC-1 grep gate against the M3-original leaked run-dir as a comparison.** `scripts/grep-run-dir-for-secrets.sh _runs/ade-bench-claude-smoke/ccb869e65f79073f "$RESOLVED_TOKEN"`. Expected: exits 1 with the pre-fix leak evidence (proving the gate works against a known-bad input).

- [ ] **Step 6: Commit any run-dir gitignore additions** (if FU-1 produces a new top-level `_runs/<experiment-name>` directory and `.gitignore` doesn't already cover it, add it). `git add .gitignore && git commit -m "fu1 task 8: gitignore new run-dir prefix"` — only if needed.

  - Do NOT commit the live run-dir's contents. The run-dir for AC-5 contains the redacted token via `agent.env` ("sk-a****gAA"); even redacted, it doesn't belong in git. The `_runs/` prefix should already be gitignored.

**Acceptance for Task 8:** exit 0 from `rk run`; numeric `score` in `summary.json`; grep gate exits 0 against the new run-dir AND exits 1 against the M3-original leaked run-dir. AC-5 verbatim verification complete. The stage report captures the run-dir path, the `score` value, the wallclock, and the grep-gate outcomes.

---

## Task 9 — Full pytest suite green (AC-6)

**Goal.** Confirm the carry-forward gate: `uv run pytest` from the FU-1 worktree branch tip exits 0 with the prior ~231 tests still passing alongside the new FU-1 tests.

**Files:**
- (no source edits — this is the final gate)

**Steps:**

- [ ] **Step 1: Run the full unit + integration suite.** From `/Users/clkao/git/razorback`:
  ```bash
  uv run pytest -q
  ```
  Expected: all green (or env-gated integration tests skipif'd consistently with the pre-FU-1 baseline). Test count: roughly the M7 baseline of 231 + FU-1's net additions:
  - Task 1: +1 integration test (`test_no_auth_leak_in_run_dir.py`)
  - Task 5: +4 unit tests (`test_ade_bench_schema_git_tasks.py`)
  - Task 6: +3 unit tests (`test_ade_bench_translator_git_task.py`)
  - Net: +1 integration, +7 unit. Expected total: ~239 collected, depending on what's env-gated.

- [ ] **Step 2: If any test fails, root-cause first; do not add fixes around the failure.** The most likely failure modes:
  - A spacedock test that still references `resolved_auth_env` somewhere Task 3 missed → fix the test (env-only shape).
  - An M7 translator test that asserts on `len(cfg.tasks)` against a count that included a deleted Dockerfile path → fix the test (the count is unchanged; the Dockerfile is unrelated).
  - The leak-grep integration test fails on a clean checkout because the captain's `.env` isn't present → guard the test with `pytest.skipif(not (.env exists OR ~/.claude/benchmark-token exists))`, matching M3's integration-test discipline.

- [ ] **Step 3: Commit any test-skip guards or final cleanups.** `git add tests/ && git commit -m "fu1 task 9: env-gate the leak-grep integration test for clean-checkout green (AC-6)"`.

**Acceptance for Task 9:** `uv run pytest` exits 0; net test delta is +8 (1 integration + 7 unit) over the M7 baseline; zero regressions to M1–M7 tests.

---

## Plan-document self-review checklist

- [x] Plan steps map 1:1 to the 6 ACs in the FU-1 entity body (table above).
- [x] AC-1 is the riskiest contract; its test is Task 1, plus a host-runnable grep gate.
- [x] Plan reads M3's implementation surface verbatim: `src/razorback/agents/claude_cli.py`, `src/razorback/agents/auth.py` (unchanged — host-side discipline preserved), `src/razorback/compat/harbor_0_6_6.py` (lines 127-145 for claude-cli; 101-126 for spacedock-solver).
- [x] Smallest change set: only `kwargs.resolved_auth_env` is removed; `env=dict(resolution.env)` (the redacted surface) is unchanged. Host-side discovery untouched. In-container path reads from `os.environ` — exactly the contract §6.2 names ("token injection from harbor's required-env declaration").
- [x] Plan reads harbor's `TaskConfig` at `.venv/lib/python3.12/site-packages/harbor/models/trial/config.py:128-185` and razorback's `AdeBenchBenchmarkBlock` + `tasks.py` loader. The proposed schema extension accepts both shapes; partial entries reject; M7 fixture path unaffected.
- [x] The acceptance ade-bench task is `ade-bench-airbnb001` (first in the registry, duckdb-variant — no external credentials needed). Fallback `ade-bench-quickbooks002` named per the FU-1 entity recommendation.
- [x] TDD ordering: Tasks 1, 5, 6 write failing tests first. Tasks 2, 3, 4 are the implementation. Task 8 is the live acceptance. Task 9 is the green-suite gate.
- [x] Integration-level mechanism validation (Task 1's failing-then-passing leak test) precedes the comprehensive carry-forward run (Task 9). Smallest end-to-end exercise of the riskiest contract first; full-suite green at the end.
- [x] No new external dependencies; harbor 0.6.6 unchanged; no host-side `.env` discipline changes; no provenance/freeze changes.
- [x] Spacedock-solver mirror fix (same leak shape) is in-scope per AC-1's "any auth token" wording. Named explicitly in Task 3.
- [x] §-cites in the AC ↔ task map (§6.2 BaseAgent contract; harbor's `templatize_sensitive_env` field_serializer; harbor's `TaskConfig` git-task shape; M7's `AdeBenchBenchmarkBlock`).
