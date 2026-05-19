# M3 — `ClaudeCliAgent` end-to-end — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `uv run rk run examples/specs/bookreview-claude.yaml` execute against the real `bookreview` dataset under `/Users/clkao/git/dataagentbench/data/` using the real `claude -p` CLI inside harbor's docker environment, producing a `summary.json` whose bookreview pass@1 is strictly greater than `0.0`. The agent declares its required-env contract through harbor's `EnvironmentConfig.env` mechanism; auth is loaded from project-root `.env` via `dotenv_values` (precedence: `ANTHROPIC_API_KEY` > `CLAUDE_CODE_OAUTH_TOKEN`); the proxy lock-down from `run_experiment.py:1497-1525` rides into the container so the agent can reach `api.anthropic.com` while remaining sealed off from huggingface / kaggle.

**Architecture:** A `razorback.agents.claude_cli` module adds a single `ClaudeCliAgent(BaseAgent)` subclass plus a `razorback.agents.auth` helper for `.env`-driven token discovery. A `razorback.agents.registry` module exposes a pydantic-validated kwargs schema per `agent.kind`; the spec parser routes `agent.kind: claude-cli` to `ClaudeCliAgentConfig` and the translator stamps `AgentConfig(import_path=…, kwargs=…, env=…)` plus an `EnvironmentConfig.env` carrying the proxy block. The run orchestrator dispatches a single instruction string per trial (one task = one query); harbor fans out per-query containers exactly as M2's DAB adapter set up.

**Tech Stack:** Python 3.12, `uv`, Pydantic 2.11, PyYAML 6, harbor 0.6.6 (pinned in M1), pytest 8 with `pytest-asyncio` 0.24, `python-dotenv` (already transitively present; pin explicitly if not), docker via Colima, the operator's host `claude` CLI (`brew install anthropic-claude-code` or equivalent).

**Source of truth:** the design doc at `/Users/clkao/git/dataagentbench/docs/superpowers/specs/2026-05-18-razorback-python-on-harbor.md`. Section anchors below cite it as `§N.N`. The 7 ACs live in the M3 entity at `docs/razorback-implementation/m3-claude-cli-agent.md`. The auth + proxy discipline is inherited verbatim from `/Users/clkao/git/dataagentbench/benchmark/lib/run_experiment.py` lines 1440-2046 and `/Users/clkao/git/dataagentbench/benchmark/solve.sh` line 105.

**M2 inputs (do not duplicate):**

- DAB benchmark adapter: `src/razorback/benchmarks/dab/{prepare,verify,aggregate,reset}.py`. M2 already materializes one harbor task dir per `(dataset, query_id)`, copies `validate.py`/`verify.py` into `<task_dir>/tests/`, fans out tasks through `spec_to_job_config`, and wires the aggregator. M3 changes only the **agent** half of the pipeline; the benchmark half is fixed.
- Spec parser: `src/razorback/spec/{schema,parse,freeze}.py`. M3 extends `AgentBlock` with a discriminated union; the `nop` and (already-shipped M2) `local`/`dab` benchmark blocks are untouched.
- Translator: `src/razorback/compat/harbor_0_6_6.py::spec_to_job_config`. M3 extends; does not fork. After M2 it returns `(JobConfig, trial_name_map)`; M3 keeps that shape and adds the `claude-cli` agent path.
- Orchestrator: `src/razorback/run.py::_execute_run_async`. M2's DAB aggregator dispatch is preserved; M3 changes only what the translator builds, not how the orchestrator dispatches.
- Manifest writer, observers, channel drainer, `derive_job_name`, exit-code map — unchanged.

**Authoritative external reference (DO NOT redesign — adapt verbatim):**

- `/Users/clkao/git/dataagentbench/benchmark/lib/run_experiment.py`:
  - **Lines 1440-1495** — `write_per_attempt_settings_json`: how the DAB harness packages auth into a per-attempt settings.json that gets bind-mounted at `~/.claude/settings.json` inside the container. M3 does NOT replicate the bind-mount mechanism (harbor's `BaseEnvironment.write_file` is the equivalent surface); but it inherits the **only-one-of** discipline (lines 1479-1482: `if api_key: env["ANTHROPIC_API_KEY"] = …; if oauth_token: env["CLAUDE_CODE_OAUTH_TOKEN"] = …`).
  - **Lines 1497-1525** — `_PROXY_EXEMPT_HOSTS` and `_CONTAINER_PROXY_BLOCK_ENV`: the literal proxy lock-down that harbor's `EnvironmentConfig.env` must carry. **AC-7's test asserts this dict's contents.** Copy the constants into `razorback.agents.proxy` and re-export; do NOT paraphrase the host list.
  - **Lines 1668-1683** — `build_agent_command(agent="claude", …)`: the `claude -p $PROMPT --verbose --output-format stream-json --tools … --disallowedTools … --settings … --permission-mode bypassPermissions` argv. The shape razorback emits is a SIMPLIFIED variant (no stream-json, no per-attempt settings — see Task 4 §4.2 for the diff and rationale).
  - **Lines 1897-1917** — `read_claude_token()` and `load_env_api_key()`: the auth source-of-truth. `load_env_api_key()` uses `dotenv_values(PROJECT_ROOT / ".env")` — NOT `os.environ`. `read_claude_token()` reads `~/.claude/benchmark-token`. **Copy this discipline into `razorback.agents.auth`.**
  - **Lines 1993-2003** — the precedence rule, copied here for the AC-2 fixture:
    ```python
    elif agent == "claude":
        (isolated_home / ".claude").mkdir(parents=True, exist_ok=True)
        api_key = load_env_api_key()
        if api_key:
            env["ANTHROPIC_API_KEY"] = api_key
        else:
            token = read_claude_token()
            if token:
                env["CLAUDE_CODE_OAUTH_TOKEN"] = token
            else:
                env["HOME"] = str(source_home)
    ```
    `load_env_api_key()` is `.env`-only (`dotenv_values(env_path).get("ANTHROPIC_API_KEY")`); `os.environ.get("ANTHROPIC_API_KEY")` is **deliberately not consulted** as a fallback. This is the discipline AC-3 enforces.

- `/Users/clkao/git/dataagentbench/benchmark/solve.sh` **line 105**: the literal `claude -p "$(cat "$PROMPT_FILE")" --allowedTools "Bash,Read,Write,Edit,Glob,Grep" --disallowedTools … --permission-mode "bypassPermissions"` shape. M3 emits the equivalent argv list (no shell, no $(cat); the prompt is passed via argv directly).

- `/Users/clkao/git/razorback/.venv/lib/python3.12/site-packages/harbor/agents/base.py`: the BaseAgent contract.
  - `name() -> str` (static, abstractmethod)
  - `version(self) -> str | None` (abstractmethod)
  - `async setup(self, environment: BaseEnvironment) -> None` (abstractmethod)
  - `async run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None` (abstractmethod)
  - Constructor signature: `(logs_dir, model_name=None, logger=None, mcp_servers=None, skills_dir=None, *args, **kwargs)` — kwargs lands the agent-specific config (the registry-validated `ClaudeCliAgentConfig` fields).
  - `BaseEnvironment.exec(command, cwd=None, env=None, timeout_sec=None, user=None) -> ExecResult` is the agent's escape hatch to the container.

- `/Users/clkao/git/razorback/.venv/lib/python3.12/site-packages/harbor/utils/env.py::get_required_host_vars` and `resolve_env_vars`: the `${VAR}` and `${VAR:-default}` template syntax harbor recognizes in `EnvironmentConfig.env`. **Harbor's mechanism resolves from `os.environ`; razorback CANNOT use it for auth** because AC-3 forbids the `os.environ` source. Razorback resolves auth itself (Task 3) and stamps literal values into `AgentConfig.env` and `EnvironmentConfig.env`. Templates ARE used for the non-auth proxy fields, where `os.environ` is acceptable (these are razorback-managed constants, not host secrets).

**AC ↔ task map (1:1):**

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 — `ClaudeCliAgent` declares required env via harbor's required-env mechanism (alternation) | §6.2 BaseAgent subclasses; §9.2 tools_allowed; harbor `EnvironmentConfig.env` + `get_required_host_vars` (verbatim file at `.venv/.../harbor/utils/env.py:133-156`) | Tasks 2, 3 |
| AC-2 — `setup()` scrubs env, injects exactly the chosen auth, never co-mingles | §6.2 setup-time env scrub; `run_experiment.py:1993-2003` precedence | Tasks 3, 4 |
| AC-3 — auth loaded from project-root `.env` via `dotenv_values`, NOT `os.environ` | `run_experiment.py:1905-1917` load_env_api_key | Task 3 |
| AC-4 — `version()` returns `claude --version` output | §6.2 BaseAgent.version | Task 4 |
| AC-5 — `supported_sampling()` returns exactly `{"temperature"}` | §6.2: "supported_sampling() returns {temperature} only — Anthropic does not honor seed" | Task 4 |
| AC-6 — end-to-end bookreview run produces non-zero score | §6.5 DAB adapter; §8.M3 acceptance | Tasks 1 (smoke), 6 (full) |
| AC-7 — proxy block from `run_experiment.py:1497-1525` rides into the container | `run_experiment.py:1497-1525` verbatim | Tasks 5, 6 |

**Riskiest contract first.** Task 1 is a one-trial, one-query, real-`claude`-CLI smoke against bookreview that bypasses razorback's registry/schema layer and exercises the **claude-CLI-in-harbor-docker** path directly. Per CL's "Validating new mechanisms" rule, if the claude CLI cannot reach `api.anthropic.com` from inside harbor's docker container (auth mode mismatch, proxy block too tight, harbor's `EnvironmentConfig.env` mechanism doesn't accept the literal we expect, the container image lacks the `claude` binary, etc.), every subsequent scaffolding task is wasted. Task 1 either lands the smoke green (proving the auth/proxy/exec triangle works) or STOPs and escalates via `SendMessage(to="team-lead", …)`. No registry, no schema, no proper agent class scaffolding before Task 1 is green.

**Working agreements pulled forward from M1/M2:**

- Repo layout follows §7: `src/razorback/agents/{__init__,registry,auth,proxy,claude_cli}.py` for M3.
- All Python source files start with the `ABOUTME:` two-line comment header (per CL's global rules). YAML/TOML/markdown data files do not.
- Pinned harbor is `harbor==0.6.6`; imports follow `docs/pre-m1-findings.md` "Harbor API map".
- macOS+Colima only mounts `/Users/<user>/` into the docker VM. The host `claude` binary lives at `$(which claude)` (typically `/Users/<user>/.local/bin/claude` or `/opt/homebrew/bin/claude`); the project root with `.env` is `/Users/clkao/git/razorback/`. All paths Colima must see are absolute under `/Users/...`.
- TDD: every behavior task writes the failing test first, runs it red, then makes it green, then commits.
- Commits: one focused commit per task. Format: `m3: <short summary>`.
- One commit per behavior task. Plan-stage commits (this document) land on `main`; implementation commits will land on the worktree branch the FO creates at the start of M3 implementation.

---

## File structure

Files created or modified by this plan. Existing files (from M1/M2) marked `[existing]`.

```
examples/
└── specs/
    └── bookreview-claude.yaml                        [new] M3 acceptance spec
src/razorback/
├── spec/
│   └── schema.py                                     [existing — extend]
├── compat/
│   └── harbor_0_6_6.py                               [existing — extend]
├── run.py                                            [existing — unchanged after M2]
└── agents/
    ├── __init__.py                                   [new]
    ├── registry.py                                   [new] — agent-kind → kwargs schema map
    ├── auth.py                                       [new] — dotenv_values + read_claude_token
    ├── proxy.py                                      [new] — copied PROXY_BLOCK + EXEMPT_HOSTS
    └── claude_cli.py                                 [new] — ClaudeCliAgent(BaseAgent)
tests/
├── unit/
│   ├── test_claude_cli_required_env.py               [new] AC-1
│   ├── test_claude_cli_setup_env_scrub.py            [new] AC-2
│   ├── test_claude_cli_auth_dotenv_only.py           [new] AC-3
│   ├── test_claude_cli_version.py                    [new] AC-4
│   ├── test_claude_cli_supported_sampling.py         [new] AC-5
│   ├── test_claude_cli_registry.py                   [new] registry shape
│   └── test_claude_cli_translator_proxy.py           [new] AC-7
├── integration/
│   ├── test_claude_cli_smoke_bookreview.py           [new] Task 1 — risk-first smoke (gated)
│   └── test_rk_run_bookreview_claude.py              [new] AC-6 end-to-end (gated)
└── fixtures/
    └── claude_cli/
        └── .env.sample                               [new] documents AC-3 fixture shape
docs/razorback-implementation/
└── m3-claude-cli-agent.md                            [existing — append stage report only]
```

---

## Task 0: Pre-flight — confirm host CLI, harbor docker, DAB data root

**Files:** none.

- [ ] **Step 1: Verify operator environment**

```bash
cd /Users/clkao/git/razorback
which claude
claude --version
docker info | head -3
.venv/bin/python -c "import harbor; print(harbor.__version__)"
ls /Users/clkao/git/dataagentbench/data/query_bookreview/
test -f .env && grep -c '^ANTHROPIC_API_KEY=\|^CLAUDE_CODE_OAUTH_TOKEN=' .env || echo "no .env auth tokens"
```

Expected:
- `which claude` prints a path; `claude --version` prints e.g. `0.6.3 (Claude Code)`.
- `docker info` succeeds (Colima up); harbor reports `0.6.6`.
- `query_bookreview/` lists `query1`, `query2`, `query3`, `query_dataset` and the dataset files.
- `.env` contains exactly **one** of `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN`. (If `~/.claude/benchmark-token` is the only token source, document that — Task 3's tests cover both code paths.)

If any preflight check fails:
- `claude` missing → STOP, escalate via `SendMessage(to="team-lead", …)`; the operator needs to install the Claude CLI.
- No `.env` auth nor `~/.claude/benchmark-token` → STOP, escalate; AC-6 integration test cannot run without credentials.
- harbor version != 0.6.6 → STOP, escalate; the compat layer is pinned.

- [ ] **Step 2: Confirm M2 ships on this branch**

```bash
git log --oneline -1 -- src/razorback/benchmarks/dab/aggregate.py
git log --oneline -1 -- src/razorback/compat/harbor_0_6_6.py
test -f examples/specs/bookreview-nop.yaml
```

Each must show an `m2: …` commit. If M2's adapter isn't on the current branch when M3 implementation kicks off, the FO will rebase or escalate; the plan itself need not block on M2's worktree merge.

- [ ] **Step 3: No commit. This is a check, not a change.**

---

## Task 1: RISKIEST CONTRACT — claude-CLI-in-harbor-docker smoke against bookreview

**Why first:** Per CL's "Validating new mechanisms" rule and the M3 entity's checklist item #2: the claude-CLI-in-container path is the load-bearing risk in this milestone. If `claude -p` cannot reach `api.anthropic.com` past harbor's network isolation when launched via `environment.exec`, every later task scaffolds around a broken contract. Task 1 builds the **smallest** integration exercise that proves the path works — bypassing the registry, the pydantic schemas, and even razorback's `BaseAgent` subclass. It runs a hand-rolled `BaseAgent` subclass via harbor directly, on ONE query of bookreview, asserts the verifier emits a numeric reward (pass OR fail — the test does NOT require a passing answer), and exits.

**Files:**
- Create: `tests/integration/test_claude_cli_smoke_bookreview.py`

This test is the **integration mechanism check** described in the entity's checklist. If it fails, STOP and escalate before any other M3 file lands. If it passes, the rest of the plan is implementation detail.

- [ ] **Step 1: Write the smoke test**

`tests/integration/test_claude_cli_smoke_bookreview.py`:

```python
# ABOUTME: M3 Task 1 — RISK-FIRST smoke for the claude-CLI-in-harbor-docker path.
# ABOUTME: Bypasses razorback's registry/schema layer; runs an ad-hoc BaseAgent subclass
# ABOUTME: against one bookreview query inside harbor's docker env. Asserts the verifier
# ABOUTME: writes a numeric reward (the path works); does NOT require the agent to pass.

import asyncio
import json
import os
import shutil
from pathlib import Path

import pytest
from dotenv import dotenv_values
from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.job import Job
from harbor.models.agent.context import AgentContext
from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig, RetryConfig
from harbor.models.trial.config import AgentConfig, EnvironmentConfig, TaskConfig, VerifierConfig

from razorback.benchmarks.dab.prepare import prepare_dataset_tasks


DAB_DATA = Path("/Users/clkao/git/dataagentbench/data")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_CLAUDE = shutil.which("claude")
DOTENV_API_KEY = dotenv_values(PROJECT_ROOT / ".env").get("ANTHROPIC_API_KEY")
OAUTH_TOKEN = (Path.home() / ".claude" / "benchmark-token").read_text().strip() \
    if (Path.home() / ".claude" / "benchmark-token").exists() else None


pytestmark = pytest.mark.skipif(
    not (DAB_DATA / "query_bookreview").exists()
    or HOST_CLAUDE is None
    or not (DOTENV_API_KEY or OAUTH_TOKEN),
    reason="Smoke needs bookreview dataset, host `claude` CLI, and one auth token (in .env or ~/.claude/benchmark-token)",
)


# Verbatim copy of run_experiment.py:1509-1525 — DO NOT paraphrase. The smoke depends
# on this exact host list to reach api.anthropic.com from inside the container.
PROXY_EXEMPT = (
    ".anthropic.com,api.anthropic.com,statsig.anthropic.com,"
    "featuregates.org,.statsig.com,"
    ".openai.com,api.openai.com,auth.openai.com,chatgpt.com,"
    "pypi.org,files.pythonhosted.org,pypi.python.org"
)
PROXY_BLOCK_ENV = {
    "HTTP_PROXY": "http://127.0.0.1:1",
    "HTTPS_PROXY": "http://127.0.0.1:1",
    "http_proxy": "http://127.0.0.1:1",
    "https_proxy": "http://127.0.0.1:1",
    "NO_PROXY": PROXY_EXEMPT,
    "no_proxy": PROXY_EXEMPT,
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
}


class _SmokeClaudeAgent(BaseAgent):
    """Minimal claude-CLI agent for the smoke. The full agent ships in Task 4."""

    @staticmethod
    def name() -> str:
        return "claude-cli-smoke"

    def version(self) -> str:
        return "0.0.0-smoke"

    async def setup(self, environment: BaseEnvironment) -> None:
        # Sanity: the host `claude` binary must exist inside the container too.
        # If the harbor image doesn't ship claude, we'd need a Dockerfile addition;
        # at smoke time we expect the image (the M2 Dockerfile + whatever the FO baked)
        # to carry it. If `claude --version` returns non-zero here, the smoke fails fast.
        result = await environment.exec("claude --version")
        assert result.return_code == 0, (
            "claude CLI missing inside container — Task 1 STOP: "
            "the image does not ship the host CLI. "
            f"stderr={getattr(result, 'stderr', '')!r}"
        )

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        env = dict(PROXY_BLOCK_ENV)
        if DOTENV_API_KEY:
            env["ANTHROPIC_API_KEY"] = DOTENV_API_KEY
        else:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = OAUTH_TOKEN  # type: ignore[assignment]

        # The smallest claude invocation that reaches the API: no plugins, no MCP,
        # only Bash/Read/Write/Edit/Glob/Grep tools (mirrors solve.sh:106).
        cmd = (
            "claude -p " + json_quote(instruction) +
            " --allowedTools Bash,Read,Write,Edit,Glob,Grep "
            "--disallowedTools WebFetch --disallowedTools WebSearch "
            "--permission-mode bypassPermissions"
        )
        result = await environment.exec(cmd, cwd="/work", env=env, timeout_sec=300)
        # We don't assert pass/fail here — the smoke only proves the path works.
        # The verifier (M2's tests/test.sh + verify.py) reads /work/answers.json
        # and emits reward.json. Empty / wrong answers still produce a numeric reward.
        context.return_code = result.return_code


def json_quote(s: str) -> str:
    # Shell-safe single-arg quoting — claude -p takes the prompt as one positional arg.
    import shlex
    return shlex.quote(s)


@pytest.mark.timeout(600)
def test_claude_cli_smoke_writes_numeric_reward(tmp_path):
    tasks_root = tmp_path / "tasks"
    manifest = prepare_dataset_tasks(
        data_root=DAB_DATA, dataset="bookreview", tasks_root=tasks_root
    )
    # Pick exactly one query — the smoke must be small (~$0.02, ~3 min wallclock).
    q1 = next(e for e in manifest if e["query_id"] == 1)

    jobs_dir = tmp_path / "_jobs"
    job_name = "smoke" + "0" * 11

    config = JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=1,
        agents=[AgentConfig(import_path=_import_path_of(_SmokeClaudeAgent))],
        tasks=[TaskConfig(path=q1["task_dir"])],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
    )

    result = asyncio.run(_run_one(config))
    # The contract: one trial completed, verifier emitted a numeric reward.
    # PASS or FAIL on the answer is irrelevant — that's AC-6's test, not AC-Task-1.
    assert result.stats.n_completed_trials == 1, (
        f"smoke failed: completed={result.stats.n_completed_trials} "
        f"errored={result.stats.n_errored_trials}"
    )
    [trial] = result.trial_results
    assert trial.verifier_result is not None, "verifier did not run — smoke STOP"
    assert "reward" in (trial.verifier_result.rewards or {}), (
        "verifier produced no reward dict — smoke STOP"
    )
    reward = trial.verifier_result.rewards["reward"]
    assert isinstance(reward, (int, float)), f"reward not numeric: {reward!r}"


async def _run_one(config):
    job = await Job.create(config)
    return await job.run()


def _import_path_of(cls) -> str:
    return f"{cls.__module__}:{cls.__name__}"
```

- [ ] **Step 2: Run the smoke**

```bash
uv run pytest tests/integration/test_claude_cli_smoke_bookreview.py -v -s --timeout=600
```

Expected outcomes and branches:

- **PASS** — the claude-CLI-in-harbor-docker contract holds. Proceed to Task 2. The smoke test stays in the suite (gated by the skipif) as a permanent regression check.
- **FAIL with `claude --version` non-zero inside container** — STOP, escalate. The harbor image we're targeting doesn't ship the `claude` binary; the plan needs a Dockerfile addition (a custom image with `claude` baked in) that the FO commissions before M3 implementation resumes.
- **FAIL with "Not logged in" / "No anthropic API key"** — STOP, escalate. The auth env vars aren't reaching the agent process; recheck `environment.exec(env=...)` passes them through. (Harbor 0.6.6 documents this kwarg as supported; if it doesn't actually pass through, that's the contract gap to surface.)
- **FAIL with network refused on `api.anthropic.com`** — STOP, escalate. The proxy block's `NO_PROXY` list isn't being honored; verify the host list matches `run_experiment.py:1509-1513` verbatim.
- **FAIL with verifier crash / no reward.json** — likely a problem in M2's adapter, not M3; escalate with the verifier stdout (`run_dir/trials/<trial>/verifier/test-stdout.txt`).

Do NOT attempt to "fix" any of these failure modes inline — the plan is wrong about a load-bearing contract; the FO must commission a fix or revise the design.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_claude_cli_smoke_bookreview.py
git commit -m "m3: risk-first smoke — claude-CLI-in-harbor-docker against bookreview"
```

---

## Task 2: Agent-kind registry + `ClaudeCliAgentConfig` schema (AC-1)

**Files:**
- Create: `src/razorback/agents/__init__.py`
- Create: `src/razorback/agents/registry.py`
- Modify: `src/razorback/spec/schema.py` (extend `AgentBlock` to a discriminated union)
- Create: `tests/unit/test_claude_cli_registry.py`
- Create: `tests/unit/test_claude_cli_required_env.py`

§6.2 design wording:

> Razorback ships a pydantic registry keyed by `agent.kind`; the spec parser validates the agent block against the registered schema *before* `AgentConfig` is constructed. Failures raise a typed `SpecError` with a field path; the run never reaches harbor.

§9.2 design wording (for AC-1's required-env declaration):

> Razorback's tool-allowlist (`agent.tools_allowed`) attaches to razorback's own agent shims (`ClaudeCliAgent`, `CodexCliAgent`, `SpacedockSolverAgent`). The enforcement runs at agent setup (env scrub, MCP server filtering) and post-run (audit against `events.jsonl`).

The required-env declaration is the agent's contract with harbor's `EnvironmentConfig.env` mechanism (defined verbatim at `.venv/lib/python3.12/site-packages/harbor/utils/env.py:133-156` — `get_required_host_vars` extracts host env names from `${VAR}` and `${VAR:-default}` templates). `ClaudeCliAgent.required_env()` returns a class-level declaration listing the env names the agent's `run()` will consume. The translator (Task 5) stamps these names as `${VAR}` templates into `EnvironmentConfig.env` AND as literal-resolved values into `AgentConfig.env` (so the secrets ride alongside the agent, not in the task config). AC-1 requires the declaration name **either** `ANTHROPIC_API_KEY` **or** `CLAUDE_CODE_OAUTH_TOKEN` (alternation, not both — the precedence rule decides which is live at any one trial).

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_claude_cli_registry.py`:

```python
# ABOUTME: Tests for razorback.agents.registry — agent.kind → kwargs schema mapping.
# ABOUTME: Asserts claude-cli kind validates a minimal config and rejects unknown fields.

import pytest

from razorback.agents.registry import resolve_agent_kind, AgentKindError


def test_claude_cli_kind_resolves_to_a_schema_and_import_path():
    entry = resolve_agent_kind("claude-cli")
    assert entry.import_path == "razorback.agents.claude_cli:ClaudeCliAgent"
    # The schema class is callable with `model`, `tools_allowed`, `prompt_file` (M3 fields).
    cfg = entry.config_schema(model="claude-opus-4-5", tools_allowed=[], prompt_file=None)
    assert cfg.model == "claude-opus-4-5"
    assert cfg.tools_allowed == []


def test_claude_cli_kind_rejects_unknown_kwargs():
    entry = resolve_agent_kind("claude-cli")
    with pytest.raises(Exception):  # pydantic ValidationError
        entry.config_schema(model="x", tools_allowed=[], prompt_file=None, frobnicator=True)


def test_unknown_kind_raises_agent_kind_error():
    with pytest.raises(AgentKindError):
        resolve_agent_kind("definitely-not-a-real-kind")


def test_nop_kind_still_resolves_for_back_compat_with_m1_m2():
    entry = resolve_agent_kind("nop")
    assert entry.import_path is None  # nop uses harbor's bundled AgentName.NOP
    cfg = entry.config_schema()  # no kwargs accepted
    assert cfg.model_dump() == {}
```

`tests/unit/test_claude_cli_required_env.py`:

```python
# ABOUTME: AC-1 — ClaudeCliAgent declares required-env names; the declaration is an
# ABOUTME: alternation (ANTHROPIC_API_KEY OR CLAUDE_CODE_OAUTH_TOKEN — not both required).

from razorback.agents.claude_cli import ClaudeCliAgent


def test_required_env_lists_exactly_the_two_auth_alternates():
    declared = ClaudeCliAgent.required_env()
    # AC-1: the agent declares its auth contract. The names are well-known; the precedence
    # at run time is settled by setup() (AC-2), but the *declaration* is the alternation.
    assert isinstance(declared, dict)
    assert declared["mode"] == "alternation"
    assert sorted(declared["names"]) == ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]


def test_required_env_is_a_class_method_callable_without_instance():
    # The translator (Task 5) reads required_env() before constructing an instance.
    # Must be a classmethod or staticmethod — assert by calling on the class.
    declared = ClaudeCliAgent.required_env()
    assert declared is not None
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_claude_cli_registry.py tests/unit/test_claude_cli_required_env.py -v
```

Expected: ImportError on `razorback.agents.{registry,claude_cli}`.

- [ ] **Step 3: Implement the registry**

`src/razorback/agents/__init__.py`:

```python
# ABOUTME: razorback.agents — custom BaseAgent subclasses and their config registry.
# ABOUTME: §6.2; per-kind pydantic schema validated before AgentConfig construction.
```

`src/razorback/agents/registry.py`:

```python
# ABOUTME: Agent-kind registry (§6.2) — maps agent.kind to (config schema, import path).
# ABOUTME: The spec parser validates kwargs against the schema before harbor sees them.

from pathlib import Path
from typing import Type

from pydantic import BaseModel, ConfigDict, Field

from razorback.errors import RazorbackError


class AgentKindError(RazorbackError):
    """Raised when agent.kind is not registered."""


class NopAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # nop takes no kwargs.


class ClaudeCliAgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(default="claude-opus-4-5")
    tools_allowed: list[str] = Field(default_factory=list)
    prompt_file: Path | None = None
    # NOTE: sampling lives under agent.sampling at the spec level, not under kwargs.
    # We keep this schema narrow (the three fields the design names in §6.2 example specs).


class AgentKindEntry:
    """Tuple-like: config schema + import path. import_path=None means harbor-bundled."""
    def __init__(self, config_schema: Type[BaseModel], import_path: str | None) -> None:
        self.config_schema = config_schema
        self.import_path = import_path


_REGISTRY: dict[str, AgentKindEntry] = {
    "nop": AgentKindEntry(NopAgentConfig, None),
    "claude-cli": AgentKindEntry(
        ClaudeCliAgentConfig,
        "razorback.agents.claude_cli:ClaudeCliAgent",
    ),
}


def resolve_agent_kind(kind: str) -> AgentKindEntry:
    try:
        return _REGISTRY[kind]
    except KeyError:
        raise AgentKindError(f"unknown agent.kind: {kind!r} (registered: {sorted(_REGISTRY)})")
```

- [ ] **Step 4: Extend `spec/schema.py` — discriminated `AgentBlock`**

Replace the body of `src/razorback/spec/schema.py` with (preserving M2's discriminated `BenchmarkBlock`):

```python
# ABOUTME: Pydantic schema for the razorback spec.
# ABOUTME: Top-level forbids unknown keys; agent and benchmark are discriminated unions.

from pathlib import Path
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from razorback.agents.registry import resolve_agent_kind


class SamplingBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature: float = 0.0
    top_p: float | None = None
    seed: int | None = None


class NopAgentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["nop"]


class ClaudeCliAgentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["claude-cli"]
    model: str = "claude-opus-4-5"
    sampling: SamplingBlock = Field(default_factory=SamplingBlock)
    tools_allowed: list[str] = Field(default_factory=list)
    prompt_file: Path | None = None


AgentBlock = Annotated[
    Union[NopAgentBlock, ClaudeCliAgentBlock],
    Field(discriminator="kind"),
]


class LocalBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["local"] = "local"
    task_paths: list[Path] = Field(default_factory=list)


class DabBenchmarkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["dab"]
    data_root: Path
    datasets: list[str] = Field(min_length=1)


BenchmarkBlock = Annotated[
    Union[LocalBenchmarkBlock, DabBenchmarkBlock],
    Field(discriminator="kind"),
]


class ObserverBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["jsonl", "stdout"]
    path: str | None = None


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    experiment: str
    agent: AgentBlock
    benchmark: BenchmarkBlock
    trials: int = 1
    observers: list[ObserverBlock] = Field(default_factory=list)
```

- [ ] **Step 5: Stub `claude_cli.py` so `required_env` test goes green**

`src/razorback/agents/claude_cli.py` (skeleton — fully fleshed out in Task 4):

```python
# ABOUTME: ClaudeCliAgent — wraps `claude -p`. Skeleton lands here for AC-1's required_env;
# ABOUTME: setup/run flesh out in Task 4. supported_sampling stays the source of truth.

from harbor.agents.base import BaseAgent


class ClaudeCliAgent(BaseAgent):
    SUPPORTS_WINDOWS = False

    @staticmethod
    def name() -> str:
        return "claude-cli"

    def version(self) -> str | None:
        return None  # Task 4 wires `claude --version`.

    @classmethod
    def required_env(cls) -> dict:
        """AC-1: declare the alternation. Translator (Task 5) reads this."""
        return {"mode": "alternation", "names": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]}

    @staticmethod
    def supported_sampling() -> set[str]:
        return set()  # Task 4 returns {"temperature"}.

    async def setup(self, environment) -> None:  # Task 4
        raise NotImplementedError

    async def run(self, instruction, environment, context) -> None:  # Task 4
        raise NotImplementedError
```

- [ ] **Step 6: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_claude_cli_registry.py tests/unit/test_claude_cli_required_env.py tests/unit/test_spec_parse.py tests/unit/test_dab_spec_parse.py -v
```

Expected: every test passes. The M2 spec-parse tests still parse because `LocalBenchmarkBlock` is unchanged and `NopAgentBlock` keeps `kind: nop` valid.

- [ ] **Step 7: Commit**

```bash
git add src/razorback/agents/__init__.py src/razorback/agents/registry.py src/razorback/agents/claude_cli.py src/razorback/spec/schema.py tests/unit/test_claude_cli_registry.py tests/unit/test_claude_cli_required_env.py
git commit -m "m3: agent-kind registry + ClaudeCliAgent required_env declaration (AC-1)"
```

---

## Task 3: `.env`-only auth loader (AC-2, AC-3)

**Files:**
- Create: `src/razorback/agents/auth.py`
- Create: `tests/unit/test_claude_cli_auth_dotenv_only.py`

The discipline is verbatim from `run_experiment.py:1905-1917` + `1993-2003`:

1. `load_env_api_key()` reads `dotenv_values(PROJECT_ROOT / ".env")` and returns `values.get("ANTHROPIC_API_KEY")`. **NOT `os.environ.get(...)` as a fallback.**
2. `read_claude_token()` reads `~/.claude/benchmark-token` if it exists.
3. The precedence rule: `ANTHROPIC_API_KEY` from `.env` wins; if absent, fall back to `CLAUDE_CODE_OAUTH_TOKEN` from `~/.claude/benchmark-token`. **Never both.**
4. AC-3 explicitly asserts the negative path: even if `monkeypatch` sets `ANTHROPIC_API_KEY` in `os.environ`, the loader returns `None` for that key unless `.env` also declares it.

This is the load-bearing AC. The DAB harness's `prepare_agent_environment` (line 1995) calls `load_env_api_key()` — which is `dotenv_values`-backed — exactly to avoid host-env contamination (the operator's shell may carry an ANTHROPIC_API_KEY for a different account; the project's `.env` is the authoritative source for this run).

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_claude_cli_auth_dotenv_only.py`:

```python
# ABOUTME: AC-3 — auth tokens are loaded from project-root .env via dotenv_values.
# ABOUTME: os.environ is NOT a fallback for ANTHROPIC_API_KEY discovery.

from pathlib import Path

import pytest

from razorback.agents.auth import resolve_claude_auth, AuthResolution


def test_anthropic_api_key_from_dotenv_wins(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=sk-from-dotenv\nCLAUDE_CODE_OAUTH_TOKEN=ignored\n")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "benchmark-token").write_text("oauth-from-home")

    resolution = resolve_claude_auth(project_root=tmp_path, home=home)
    assert resolution == AuthResolution(
        mode="api-key",
        env={"ANTHROPIC_API_KEY": "sk-from-dotenv"},
    )


def test_falls_back_to_oauth_when_dotenv_lacks_api_key(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# no api key here\n")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "benchmark-token").write_text("oauth-token-xyz")

    resolution = resolve_claude_auth(project_root=tmp_path, home=home)
    assert resolution == AuthResolution(
        mode="oauth",
        env={"CLAUDE_CODE_OAUTH_TOKEN": "oauth-token-xyz"},
    )


def test_never_co_mingles_both(tmp_path):
    """AC-2 negative — even with both inputs present, only ONE name reaches env."""
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-1\n")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "benchmark-token").write_text("oauth-2")

    resolution = resolve_claude_auth(project_root=tmp_path, home=home)
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in resolution.env
    assert resolution.env == {"ANTHROPIC_API_KEY": "sk-1"}


def test_os_environ_is_not_a_source(tmp_path, monkeypatch):
    """AC-3 verbatim: a process-env value does NOT get picked up unless also in .env."""
    (tmp_path / ".env").write_text("# empty\n")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)  # no benchmark-token

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-os-environ")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-from-os-environ")

    # No .env value AND no ~/.claude/benchmark-token → raises.
    with pytest.raises(Exception):
        resolve_claude_auth(project_root=tmp_path, home=home)


def test_raises_when_neither_source_has_credentials(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    with pytest.raises(Exception):
        resolve_claude_auth(project_root=tmp_path, home=home)


def test_anthropic_api_key_in_dotenv_with_empty_value_is_treated_as_missing(tmp_path):
    """dotenv_values returns '' for KEY= with no value; treat as missing, not as authorized."""
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=\n")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "benchmark-token").write_text("oauth")

    resolution = resolve_claude_auth(project_root=tmp_path, home=home)
    assert resolution.mode == "oauth"
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_claude_cli_auth_dotenv_only.py -v
```

Expected: ImportError on `razorback.agents.auth`.

- [ ] **Step 3: Implement `auth.py`**

```python
# ABOUTME: Claude CLI auth — .env-only ANTHROPIC_API_KEY discovery + ~/.claude/benchmark-token fallback.
# ABOUTME: Discipline copied verbatim from run_experiment.py:1897-1917 + 1993-2003.

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values

from razorback.errors import RazorbackError


class AuthDiscoveryError(RazorbackError):
    """No usable credential found in .env or ~/.claude/benchmark-token."""


@dataclass(frozen=True)
class AuthResolution:
    mode: Literal["api-key", "oauth"]
    env: dict[str, str] = field(default_factory=dict)


def _load_env_api_key(project_root: Path) -> str | None:
    """Mirror run_experiment.py:1905-1917 — .env-only, NOT os.environ.

    Returns the literal value if present and non-empty; None otherwise.
    """
    env_path = Path(project_root) / ".env"
    if not env_path.exists():
        return None
    values = dotenv_values(env_path)
    value = values.get("ANTHROPIC_API_KEY")
    if value is None or value == "":
        return None
    return value


def _read_claude_token(home: Path) -> str | None:
    """Mirror run_experiment.py:1897-1902 — ~/.claude/benchmark-token, stripped."""
    token_path = Path(home) / ".claude" / "benchmark-token"
    if not token_path.exists():
        return None
    contents = token_path.read_text().strip()
    return contents or None


def resolve_claude_auth(*, project_root: Path, home: Path | None = None) -> AuthResolution:
    """Resolve the single chosen auth credential per the precedence rule.

    Precedence (verbatim from run_experiment.py:1993-2003):
      1. ANTHROPIC_API_KEY from <project_root>/.env via dotenv_values.
      2. CLAUDE_CODE_OAUTH_TOKEN from ~/.claude/benchmark-token.

    NEVER both; NEVER os.environ. Raises AuthDiscoveryError if neither yields a credential.
    """
    home_path = Path.home() if home is None else Path(home)
    api_key = _load_env_api_key(project_root)
    if api_key is not None:
        return AuthResolution(mode="api-key", env={"ANTHROPIC_API_KEY": api_key})
    token = _read_claude_token(home_path)
    if token is not None:
        return AuthResolution(mode="oauth", env={"CLAUDE_CODE_OAUTH_TOKEN": token})
    raise AuthDiscoveryError(
        "no claude credentials found. Add ANTHROPIC_API_KEY to "
        f"{Path(project_root) / '.env'} or write a token to "
        f"{home_path / '.claude' / 'benchmark-token'}."
    )
```

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_claude_cli_auth_dotenv_only.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/agents/auth.py tests/unit/test_claude_cli_auth_dotenv_only.py
git commit -m "m3: auth.py — .env-only ANTHROPIC_API_KEY + ~/.claude/benchmark-token (AC-3)"
```

---

## Task 4: `ClaudeCliAgent` setup() / run() / version() / supported_sampling() (AC-2, AC-4, AC-5)

**Files:**
- Modify: `src/razorback/agents/claude_cli.py`
- Create: `tests/unit/test_claude_cli_setup_env_scrub.py`
- Create: `tests/unit/test_claude_cli_version.py`
- Create: `tests/unit/test_claude_cli_supported_sampling.py`

### 4.1 — `version()` parses `claude --version` (AC-4)

`version()` shells `claude --version` (host side), parses the version string, caches on the instance. Per the BaseAgent contract (`harbor/agents/base.py:85-86`), `version()` returns `str | None`. The DAB harness uses `subprocess.run(["claude", "--version"], capture_output=True)` and reads `stdout`.

### 4.2 — `run()` builds the claude argv (AC-2, AC-7-adjacent)

The argv inside the container is the **simplified** variant of `run_experiment.py:1668-1683`. Per the design:

- No `--verbose --output-format stream-json`: M3 reads `events.jsonl` for token cost; razorback doesn't parse claude's stream-json yet (that's M5+).
- No `--settings <path>`: razorback ships no per-attempt settings.json in M3; the auth comes from `AgentConfig.env` (passed via `environment.exec(env=...)`), and `DISALLOWED_TOOLS` is enforced via `--disallowedTools` directly. The full settings.json path lights up when MCP servers + hook scripts (M4+) need it.
- No `--plugin-dir`: M3 ships no plugins; the spec block has no `plugins:` field yet.

The literal shape M3 emits (per query, instruction is the rendered prompt):

```
claude -p <instruction-as-argv> \
  --allowedTools <comma-list> \
  --disallowedTools <name> --disallowedTools <name> ... \
  --permission-mode bypassPermissions \
  --model <agent.model>
```

The agent runs ONE `claude -p` per `environment.exec` call. The trial maps 1:1 to `(dataset, query_id)`, so one invocation per trial is correct.

### 4.3 — `setup()` env scrub (AC-2)

`setup()` validates that:
- `claude --version` runs inside the container (proves the binary is on PATH).
- The agent's `_resolved_auth` (set by the translator before `setup()` runs — see Task 5) has exactly one key.
- The instance stashes the auth dict and proxy block for `run()` to consume.

`setup()` does NOT mutate `os.environ` on the host. The "env scrub" is at the **container-process** level: when `run()` calls `environment.exec(env=...)`, the `env` dict carries ONLY the chosen auth name plus the proxy block plus `HOME` — NOT the operator's entire host environment.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_claude_cli_supported_sampling.py`:

```python
# ABOUTME: AC-5 — supported_sampling() returns exactly {"temperature"}.

from razorback.agents.claude_cli import ClaudeCliAgent


def test_supported_sampling_is_exactly_temperature():
    assert ClaudeCliAgent.supported_sampling() == {"temperature"}


def test_supported_sampling_omits_top_p_and_seed():
    s = ClaudeCliAgent.supported_sampling()
    assert "top_p" not in s
    assert "seed" not in s
```

`tests/unit/test_claude_cli_version.py`:

```python
# ABOUTME: AC-4 — version() returns the string parsed from `claude --version`.

from unittest.mock import patch
import subprocess

from razorback.agents.claude_cli import ClaudeCliAgent


def _agent(tmp_path):
    return ClaudeCliAgent(logs_dir=tmp_path, model_name="claude-opus-4-5")


def test_version_parses_claude_cli_output(tmp_path):
    fake = subprocess.CompletedProcess(args=["claude", "--version"], returncode=0,
                                       stdout="0.6.3 (Claude Code)\n", stderr="")
    with patch("razorback.agents.claude_cli.subprocess.run", return_value=fake) as run:
        agent = _agent(tmp_path)
        assert agent.version() == "0.6.3 (Claude Code)"
        run.assert_called_once()
        called_argv = run.call_args.args[0]
        assert called_argv == ["claude", "--version"]


def test_version_returns_none_on_cli_missing(tmp_path):
    with patch("razorback.agents.claude_cli.subprocess.run",
               side_effect=FileNotFoundError("claude")):
        agent = _agent(tmp_path)
        assert agent.version() is None


def test_version_returns_none_on_nonzero_exit(tmp_path):
    fake = subprocess.CompletedProcess(args=["claude", "--version"], returncode=1,
                                       stdout="", stderr="boom")
    with patch("razorback.agents.claude_cli.subprocess.run", return_value=fake):
        agent = _agent(tmp_path)
        assert agent.version() is None
```

`tests/unit/test_claude_cli_setup_env_scrub.py`:

```python
# ABOUTME: AC-2 — setup() scrubs env, injects ONLY the chosen auth, never co-mingles.

from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.claude_cli import ClaudeCliAgent


def _make_environment(version_rc=0):
    env = MagicMock()
    env.exec = AsyncMock(return_value=MagicMock(return_code=version_rc, stdout="0.6.3 (Claude Code)\n", stderr=""))
    return env


@pytest.mark.asyncio
async def test_setup_with_only_api_key_carries_only_api_key(tmp_path):
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-1"},
    )
    await agent.setup(_make_environment())
    # The setup-stashed env dict carries the api key and the proxy block, NOT the oauth token.
    assert "ANTHROPIC_API_KEY" in agent._exec_env
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in agent._exec_env
    assert agent._exec_env["ANTHROPIC_API_KEY"] == "sk-1"


@pytest.mark.asyncio
async def test_setup_with_only_oauth_carries_only_oauth(tmp_path):
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        resolved_auth_env={"CLAUDE_CODE_OAUTH_TOKEN": "oauth-1"},
    )
    await agent.setup(_make_environment())
    assert "CLAUDE_CODE_OAUTH_TOKEN" in agent._exec_env
    assert "ANTHROPIC_API_KEY" not in agent._exec_env


@pytest.mark.asyncio
async def test_setup_refuses_to_co_mingle(tmp_path):
    with pytest.raises(Exception):
        ClaudeCliAgent(
            logs_dir=tmp_path,
            model_name="claude-opus-4-5",
            resolved_auth_env={
                "ANTHROPIC_API_KEY": "sk-1",
                "CLAUDE_CODE_OAUTH_TOKEN": "oauth-1",
            },
        )


@pytest.mark.asyncio
async def test_setup_carries_proxy_block_into_exec_env(tmp_path):
    """The proxy block from run_experiment.py:1515-1525 must ride alongside the auth."""
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-1"},
    )
    await agent.setup(_make_environment())
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
              "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        assert k in agent._exec_env
    assert agent._exec_env["HTTP_PROXY"] == "http://127.0.0.1:1"
    assert ".anthropic.com" in agent._exec_env["NO_PROXY"]


@pytest.mark.asyncio
async def test_setup_validates_claude_binary_inside_container(tmp_path):
    """setup() runs `claude --version` inside the container; non-zero exit → raise."""
    env = _make_environment(version_rc=127)
    agent = ClaudeCliAgent(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-1"},
    )
    with pytest.raises(Exception):
        await agent.setup(env)
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_claude_cli_supported_sampling.py tests/unit/test_claude_cli_version.py tests/unit/test_claude_cli_setup_env_scrub.py -v
```

Expected: 11 failing (assertion errors / NotImplementedError).

- [ ] **Step 3: Flesh out `claude_cli.py`**

Replace the Task 2 stub with the full body:

```python
# ABOUTME: ClaudeCliAgent (§6.2) — wraps `claude -p`. setup() validates auth & CLI presence;
# ABOUTME: run() emits one claude invocation per trial; version() parses `claude --version`.

import shlex
import subprocess
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.errors import RazorbackError


class ClaudeCliAgentError(RazorbackError):
    pass


_DEFAULT_ALLOWED_TOOLS = ("Bash", "Read", "Write", "Edit", "Glob", "Grep")
_DEFAULT_DISALLOWED_TOOLS = (
    "WebFetch", "WebSearch",
    "Bash(curl *)", "Bash(wget *)", "Bash(git clone *)",
    "Bash(huggingface-cli *)", "Bash(hf *)",
    "Bash(pip install datasets*)", "Bash(pip install huggingface*)",
    "Bash(pip install transformers*)", "Bash(pip install evaluate*)",
    "Bash(pip3 install datasets*)", "Bash(pip3 install huggingface*)",
    "Bash(pip3 install transformers*)", "Bash(pip3 install evaluate*)",
)


class ClaudeCliAgent(BaseAgent):
    SUPPORTS_WINDOWS = False
    SUPPORTS_ATIF = False

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        logger=None,
        mcp_servers=None,
        skills_dir=None,
        *,
        resolved_auth_env: dict[str, str] | None = None,
        tools_allowed: list[str] | None = None,
        sampling_temperature: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name,
            logger=logger,
            mcp_servers=mcp_servers,
            skills_dir=skills_dir,
            **kwargs,
        )
        # AC-2: refuse co-mingled auth at construction time, before harbor runs anything.
        env = dict(resolved_auth_env or {})
        if "ANTHROPIC_API_KEY" in env and "CLAUDE_CODE_OAUTH_TOKEN" in env:
            raise ClaudeCliAgentError(
                "ANTHROPIC_API_KEY and CLAUDE_CODE_OAUTH_TOKEN cannot both be set."
            )
        self._resolved_auth_env = env
        self._tools_allowed = list(tools_allowed) if tools_allowed else list(_DEFAULT_ALLOWED_TOOLS)
        self._sampling_temperature = sampling_temperature
        self._exec_env: dict[str, str] = {}

    @staticmethod
    def name() -> str:
        return "claude-cli"

    def version(self) -> str | None:
        """AC-4: parse `claude --version`'s stdout. Cached on the instance."""
        if getattr(self, "_version_cache", None) is not None:
            return self._version_cache
        try:
            result = subprocess.run(
                ["claude", "--version"], capture_output=True, text=True, timeout=10
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            self._version_cache = None
            return None
        if result.returncode != 0:
            self._version_cache = None
            return None
        self._version_cache = result.stdout.strip()
        return self._version_cache

    @classmethod
    def required_env(cls) -> dict:
        """AC-1: alternation declaration — ANTHROPIC_API_KEY OR CLAUDE_CODE_OAUTH_TOKEN."""
        return {"mode": "alternation", "names": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]}

    @staticmethod
    def supported_sampling() -> set[str]:
        """AC-5: Anthropic models honor temperature only. No seed, no top_p."""
        return {"temperature"}

    async def setup(self, environment: BaseEnvironment) -> None:
        """AC-2 — build the exec env dict (auth + proxy block); validate `claude` binary."""
        result = await environment.exec("claude --version")
        if result.return_code != 0:
            raise ClaudeCliAgentError(
                f"claude CLI not available inside the container "
                f"(exit={result.return_code}, stderr={getattr(result, 'stderr', '')!r})"
            )
        self._exec_env = {**PROXY_BLOCK_ENV, **self._resolved_auth_env}

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        """One `claude -p <instruction>` per trial."""
        cmd_parts = [
            "claude", "-p", shlex.quote(instruction),
            "--allowedTools", ",".join(self._tools_allowed),
        ]
        for disallowed in _DEFAULT_DISALLOWED_TOOLS:
            cmd_parts.extend(["--disallowedTools", shlex.quote(disallowed)])
        cmd_parts.extend(["--permission-mode", "bypassPermissions"])
        if self.model_name:
            cmd_parts.extend(["--model", self.model_name])
        cmd = " ".join(cmd_parts)
        result = await environment.exec(
            cmd,
            cwd="/work",
            env=self._exec_env,
            timeout_sec=600,
        )
        context.return_code = result.return_code
```

- [ ] **Step 4: Add `pytest-asyncio` config if missing**

If the M2 plan hasn't already enabled asyncio mode, add to `pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
asyncio_mode = "auto"
```

(M1 already pinned `pytest-asyncio==0.24`; check `uv tree | grep pytest-asyncio` if uncertain.)

- [ ] **Step 5: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_claude_cli_supported_sampling.py tests/unit/test_claude_cli_version.py tests/unit/test_claude_cli_setup_env_scrub.py -v
```

Expected: 11 passed.

- [ ] **Step 6: Commit**

```bash
git add src/razorback/agents/claude_cli.py tests/unit/test_claude_cli_setup_env_scrub.py tests/unit/test_claude_cli_version.py tests/unit/test_claude_cli_supported_sampling.py
git commit -m "m3: ClaudeCliAgent setup/run/version/supported_sampling (AC-2, AC-4, AC-5)"
```

---

## Task 5: Translator — proxy block + `EnvironmentConfig.env` + agent kwargs (AC-7)

**Files:**
- Create: `src/razorback/agents/proxy.py`
- Modify: `src/razorback/compat/harbor_0_6_6.py`
- Create: `tests/unit/test_claude_cli_translator_proxy.py`

### 5.1 — `proxy.py` (verbatim from `run_experiment.py:1497-1525`)

```python
# ABOUTME: HTTP egress block — verbatim from run_experiment.py:1497-1525.
# ABOUTME: NO_PROXY exempts the anthropic + statsig + openai + pypi hosts the claude CLI needs.

# Verbatim copy of run_experiment.py:1509-1513. DO NOT paraphrase the host list — the smoke
# test (Task 1) asserts the path works with EXACTLY these hosts.
PROXY_EXEMPT_HOSTS = (
    ".anthropic.com,api.anthropic.com,statsig.anthropic.com,"
    "featuregates.org,.statsig.com,"
    ".openai.com,api.openai.com,auth.openai.com,chatgpt.com,"
    "pypi.org,files.pythonhosted.org,pypi.python.org"
)

# Verbatim copy of run_experiment.py:1515-1525.
PROXY_BLOCK_ENV: dict[str, str] = {
    "HTTP_PROXY": "http://127.0.0.1:1",
    "HTTPS_PROXY": "http://127.0.0.1:1",
    "http_proxy": "http://127.0.0.1:1",
    "https_proxy": "http://127.0.0.1:1",
    "NO_PROXY": PROXY_EXEMPT_HOSTS,
    "no_proxy": PROXY_EXEMPT_HOSTS,
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
}
```

### 5.2 — translator extension

The translator now does FOUR things for `agent.kind == "claude-cli"`:

1. Resolve auth via `resolve_claude_auth(project_root=…)`. The `project_root` comes from the M3 spec — for an absolute spec path `examples/specs/bookreview-claude.yaml`, the project root is the spec file's repo root (i.e. `Path(__file__).resolve().parents[?]`). The translator accepts an explicit `project_root` kwarg passed by the orchestrator (which knows the spec's location).
2. Build `AgentConfig(import_path="razorback.agents.claude_cli:ClaudeCliAgent", kwargs={...}, env={…})`. The `env` carries the resolved auth as literal values (not templates — AC-3 means we don't want harbor reading `os.environ`). The `kwargs` carries `resolved_auth_env={…}`, `tools_allowed=[…]`, `sampling_temperature=…`.
3. Build `EnvironmentConfig.env = {**PROXY_BLOCK_ENV}` per trial — literal proxy block stamped into the task config. **AC-7 asserts this dict.**
4. Keep M2's DAB task fan-out unchanged. The trial_name_map is identical to M2's; the only thing that changes is the agent and env blocks.

### 5.3 — the test (AC-7)

`tests/unit/test_claude_cli_translator_proxy.py`:

```python
# ABOUTME: AC-7 — the spec → JobConfig translator stamps the proxy block from
# ABOUTME: run_experiment.py:1497-1525 into EnvironmentConfig.env for claude DAB specs.

from pathlib import Path

import pytest

from razorback.compat.harbor_0_6_6 import spec_to_job_config
from razorback.spec.parse import parse_spec_text


def _make_fixture_dataset(root: Path) -> Path:
    ds = root / "query_bookreview"
    (ds / "query_dataset").mkdir(parents=True)
    (ds / "db_config.yaml").write_text("db_clients: {}\n")
    (ds / "db_description.txt").write_text("desc")
    for qid in (1,):
        q = ds / f"query{qid}"
        q.mkdir()
        (q / "query.json").write_text(f'"Q{qid}?"')
        (q / "validate.py").write_text(f"def validate(s): return ('{qid}' in s, 'ok')\n")
    return root


CLAUDE_SPEC = """\
version: 1
experiment: m3-bookreview-claude
agent:
  kind: claude-cli
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
  tools_allowed: [Bash, Read, Write, Edit, Glob, Grep]
benchmark:
  kind: dab
  data_root: {data_root}
  datasets:
    - bookreview
trials: 1
"""


def test_translator_stamps_proxy_block_into_environment_env(tmp_path, monkeypatch):
    data_root = _make_fixture_dataset(tmp_path / "data")
    # Make resolve_claude_auth happy.
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test\n")
    spec = parse_spec_text(CLAUDE_SPEC.format(data_root=data_root))

    cfg, _trial_map = spec_to_job_config(
        spec,
        job_name="claude" + "0" * 11,
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
        project_root=tmp_path,
    )

    [task] = cfg.tasks
    # AC-7: literal proxy lock-down values land in the task's environment block.
    # The translator may set them per-task or globally; the AC's assertion is on shape.
    env_block = _get_task_environment_env(cfg, task)
    assert env_block["HTTP_PROXY"] == "http://127.0.0.1:1"
    assert env_block["HTTPS_PROXY"] == "http://127.0.0.1:1"
    assert "anthropic" in env_block["NO_PROXY"]
    assert "statsig" in env_block["NO_PROXY"]
    assert "pypi" in env_block["NO_PROXY"]
    assert env_block["HF_HUB_OFFLINE"] == "1"


def test_translator_passes_resolved_auth_into_agent_kwargs(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-test-2\n")
    spec = parse_spec_text(CLAUDE_SPEC.format(data_root=data_root))

    cfg, _ = spec_to_job_config(
        spec,
        job_name="claude" + "0" * 11,
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
        project_root=tmp_path,
    )
    agent_cfg = cfg.agents[0]
    assert agent_cfg.import_path == "razorback.agents.claude_cli:ClaudeCliAgent"
    assert agent_cfg.kwargs["resolved_auth_env"] == {"ANTHROPIC_API_KEY": "sk-test-2"}
    assert agent_cfg.kwargs["tools_allowed"] == ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
    assert agent_cfg.kwargs["sampling_temperature"] == 0.0


def test_translator_never_emits_both_auth_names(tmp_path):
    """AC-2 at the translator layer: even when both sources resolve, only one rides."""
    data_root = _make_fixture_dataset(tmp_path / "data")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=sk-1\n")
    home = tmp_path / "fake-home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "benchmark-token").write_text("oauth-2")
    spec = parse_spec_text(CLAUDE_SPEC.format(data_root=data_root))

    cfg, _ = spec_to_job_config(
        spec,
        job_name="claude" + "0" * 11,
        jobs_dir=tmp_path / "jobs",
        tasks_root=tmp_path / "tasks",
        project_root=tmp_path,
        home=home,
    )
    auth_env = cfg.agents[0].kwargs["resolved_auth_env"]
    assert "ANTHROPIC_API_KEY" in auth_env
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in auth_env


def test_translator_raises_when_no_credentials(tmp_path):
    data_root = _make_fixture_dataset(tmp_path / "data")
    (tmp_path / ".env").write_text("# empty\n")
    home = tmp_path / "fake-home-no-token"
    (home / ".claude").mkdir(parents=True)
    spec = parse_spec_text(CLAUDE_SPEC.format(data_root=data_root))

    with pytest.raises(Exception):
        spec_to_job_config(
            spec,
            job_name="claude" + "0" * 11,
            jobs_dir=tmp_path / "jobs",
            tasks_root=tmp_path / "tasks",
            project_root=tmp_path,
            home=home,
        )


def _get_task_environment_env(cfg, task) -> dict[str, str]:
    """Pull the EnvironmentConfig.env for `task` out of the JobConfig.

    Harbor 0.6.6 carries env on `TaskConfig`'s referenced task dir (task.toml's
    `[environment].env` block) OR on `TrialConfig.environment.env`. M3's translator
    stamps env on the task.toml's environment block written during prepare;
    fall back to checking task.toml on disk if the model field is empty.
    """
    # Implementation detail; the test reads back from the materialized task.toml.
    import tomllib
    task_toml = task.path / "task.toml"
    data = tomllib.loads(task_toml.read_text())
    return data.get("environment", {}).get("env", {})
```

NOTE on test shape: the `_get_task_environment_env` helper reads the *materialized* task.toml — not the in-memory `cfg` — because harbor 0.6.6's `EnvironmentConfig` lives on the per-task task.toml (top-level `[environment].env`), not on `TaskConfig` itself. The translator's per-task env stamping happens during `prepare_dataset_tasks` (which writes task.toml). **This is a change to M2's `prepare.py`** — Task 5's translator passes an `env` kwarg into `prepare_dataset_tasks`, and `prepare.py` writes `[environment].env = …` into the emitted task.toml. M2's `prepare.py` currently writes only `[task]`; M3 extends it.

- [ ] **Step 1: Write the failing tests**

(Above.)

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_claude_cli_translator_proxy.py -v
```

Expected: ImportError / TypeError on the new translator kwargs.

- [ ] **Step 3: Extend `prepare.py` to accept an env block**

In `src/razorback/benchmarks/dab/prepare.py`:

```python
def prepare_dataset_tasks(
    *,
    data_root: Path,
    dataset: str,
    tasks_root: Path,
    task_env: dict[str, str] | None = None,   # NEW for M3
) -> list[TaskManifestEntry]:
    ...
    for query_dir in sorted(...):
        ...
        _materialize_task_dir(
            task_name=task_name,
            dataset_dir=dataset_dir,
            query_dir=query_dir,
            task_dir=task_dir,
            task_env=task_env or {},
        )
    ...


def _materialize_task_dir(*, task_name, dataset_dir, query_dir, task_dir, task_env):
    ...
    (task_dir / "task.toml").write_text(_task_toml(task_name, task_env))
    ...


def _task_toml(task_name: str, task_env: dict[str, str]) -> str:
    body = (
        f'schema_version = "1.2"\n\n'
        f'[task]\nname = "razorback/{task_name}"\n'
        f'description = "DAB {task_name} as a harbor task."\n'
    )
    if task_env:
        body += "\n[environment]\nimage = \"dab-agent:latest\"\n\n[environment.env]\n"
        for k, v in task_env.items():
            # TOML basic-string escape: backslash and double-quote.
            esc = v.replace("\\", "\\\\").replace('"', '\\"')
            body += f'{k} = "{esc}"\n'
    return body
```

(M2's tests for `prepare.py` continue to pass because `task_env=None` defaults to no `[environment]` section, which is the M2 shape.)

The `image = "dab-agent:latest"` line names the docker image the harbor docker env should run inside. M2's `_dockerfile()` writes a `python:3.12-slim`-based image; M3 expects a `dab-agent:latest` image that ships the `claude` binary. The smoke test (Task 1) is the proof: if `claude --version` fails inside that image, the FO needs to commission an image-build step (a Dockerfile in `examples/specs/` or `scripts/` that does `FROM dab-agent:latest` + `RUN install claude-code`). Per CL's "YAGNI" rule, M3 doesn't ship that Dockerfile if the operator already has `dab-agent:latest` baked locally; the integration test (Task 6) and the smoke (Task 1) gate on `docker image inspect dab-agent:latest`.

- [ ] **Step 4: Extend the translator**

In `src/razorback/compat/harbor_0_6_6.py`:

```python
# ABOUTME: Spec → harbor 0.6.6 JobConfig translator (§6.1).
# ABOUTME: Supports agent.kind ∈ {nop, claude-cli}, benchmark.kind ∈ {local, dab}.

from pathlib import Path
from typing import Any

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig, RetryConfig
from harbor.models.trial.config import AgentConfig, TaskConfig, VerifierConfig

from razorback.agents.auth import resolve_claude_auth
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.benchmarks.dab.prepare import prepare_dataset_tasks
from razorback.errors import SpecError
from razorback.spec.schema import (
    ClaudeCliAgentBlock,
    DabBenchmarkBlock,
    LocalBenchmarkBlock,
    NopAgentBlock,
    Spec,
)


def spec_to_job_config(
    spec: Spec,
    *,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path | None = None,
    project_root: Path | None = None,
    home: Path | None = None,
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    agent_cfg, task_env = _build_agent_config(spec, project_root=project_root, home=home)

    if isinstance(spec.benchmark, LocalBenchmarkBlock):
        return _build_local(spec=spec, job_name=job_name, jobs_dir=jobs_dir, agent_cfg=agent_cfg), {}
    if isinstance(spec.benchmark, DabBenchmarkBlock):
        if tasks_root is None:
            raise SpecError("DAB specs require tasks_root.")
        return _build_dab(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            tasks_root=Path(tasks_root),
            agent_cfg=agent_cfg,
            task_env=task_env,
        )
    raise SpecError(f"unsupported benchmark block: {type(spec.benchmark).__name__}")


def _build_agent_config(
    spec: Spec, *, project_root: Path | None, home: Path | None,
) -> tuple[AgentConfig, dict[str, str]]:
    """Returns (agent_config, task_env_to_stamp_into_task_toml)."""
    if isinstance(spec.agent, NopAgentBlock):
        return AgentConfig(name=AgentName.NOP.value), {}
    if isinstance(spec.agent, ClaudeCliAgentBlock):
        if project_root is None:
            raise SpecError("claude-cli agent requires project_root for .env auth discovery.")
        resolution = resolve_claude_auth(project_root=project_root, home=home)
        kwargs: dict[str, Any] = {
            "resolved_auth_env": dict(resolution.env),
            "tools_allowed": list(spec.agent.tools_allowed),
            "sampling_temperature": spec.agent.sampling.temperature,
        }
        agent_cfg = AgentConfig(
            import_path="razorback.agents.claude_cli:ClaudeCliAgent",
            model_name=spec.agent.model,
            kwargs=kwargs,
            env=dict(resolution.env),  # secrets ride on the agent config, not the task.
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env
    raise SpecError(f"unsupported agent block: {type(spec.agent).__name__}")


def _build_local(*, spec, job_name, jobs_dir, agent_cfg) -> JobConfig:
    assert isinstance(spec.benchmark, LocalBenchmarkBlock)
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=[TaskConfig(path=Path(p).resolve()) for p in spec.benchmark.task_paths],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
    )


def _build_dab(
    *, spec, job_name, jobs_dir, tasks_root, agent_cfg, task_env,
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    assert isinstance(spec.benchmark, DabBenchmarkBlock)
    manifest_all: list[dict] = []
    for dataset in spec.benchmark.datasets:
        manifest_all.extend(
            prepare_dataset_tasks(
                data_root=Path(spec.benchmark.data_root),
                dataset=dataset,
                tasks_root=tasks_root / dataset,
                task_env=task_env,  # NEW for M3 — propagates into task.toml
            )
        )
    tasks = [TaskConfig(path=entry["task_dir"]) for entry in manifest_all]
    trial_name_map = {
        entry["task_name"]: (entry["dataset"], entry["query_id"])
        for entry in manifest_all
    }
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=1,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=tasks,
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
    ), trial_name_map
```

- [ ] **Step 5: Update `run.py` to pass `project_root` to the translator**

In `src/razorback/run.py::_execute_run_async`:

```python
project_root = Path.cwd()  # rk run is invoked from the repo root; .env lives here.
tasks_root = run_dir / "tasks"
job_config, trial_name_map = spec_to_job_config(
    spec,
    job_name=job_name,
    jobs_dir=run_dir.parent,
    tasks_root=tasks_root,
    project_root=project_root,
)
```

- [ ] **Step 6: Run tests, confirm green**

```bash
uv run pytest tests/unit -v
```

Expected: every M1, M2, and new M3 unit test passes.

- [ ] **Step 7: Commit**

```bash
git add src/razorback/agents/proxy.py src/razorback/compat/harbor_0_6_6.py src/razorback/benchmarks/dab/prepare.py src/razorback/run.py tests/unit/test_claude_cli_translator_proxy.py
git commit -m "m3: translator — proxy block, agent kwargs, task.toml env stamping (AC-7)"
```

---

## Task 6: Acceptance spec + end-to-end integration test (AC-6)

**Files:**
- Create: `examples/specs/bookreview-claude.yaml`
- Create: `tests/integration/test_rk_run_bookreview_claude.py`

### 6.1 — the spec

```yaml
version: 1
experiment: m3-bookreview-claude
agent:
  kind: claude-cli
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
  tools_allowed: [Bash, Read, Write, Edit, Glob, Grep]
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets:
    - bookreview
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

`trials: 1` is the AC-6 floor — three queries × one trial × one real claude CLI invocation. Expected cost: ~$0.05–0.15 depending on response length. Expected wallclock: 5–10 minutes.

### 6.2 — the test (AC-6)

`tests/integration/test_rk_run_bookreview_claude.py`:

```python
# ABOUTME: AC-6 — `uv run rk run examples/specs/bookreview-claude.yaml` writes
# ABOUTME: a summary.json whose bookreview pass@1 is strictly greater than 0.0.

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "examples" / "specs" / "bookreview-claude.yaml"
DAB_DATA = Path("/Users/clkao/git/dataagentbench/data/query_bookreview")
HAS_AUTH = bool(
    dotenv_values(REPO / ".env").get("ANTHROPIC_API_KEY")
    or (Path.home() / ".claude" / "benchmark-token").exists()
)


@pytest.mark.skipif(
    not DAB_DATA.exists() or shutil.which("claude") is None or not HAS_AUTH,
    reason="AC-6 needs bookreview dataset, host `claude` CLI, and an auth token",
)
@pytest.mark.timeout(900)
def test_rk_run_bookreview_claude_produces_nonzero_score(tmp_path):
    runs_root = tmp_path / "_runs"
    env = {**os.environ}
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(SPEC), "--runs-dir", str(runs_root)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, f"rk run failed:\nstdout={result.stdout}\nstderr={result.stderr}"

    experiment_dir = runs_root / "m3-bookreview-claude"
    [run_dir] = list(experiment_dir.iterdir())
    summary = json.loads((run_dir / "summary.json").read_text())

    # AC-6: bookreview pass@1 strictly > 0.0.
    book = summary["datasets"]["bookreview"]
    assert book["dataset_pass_at_1"] > 0.0, (
        f"bookreview pass@1 not strictly > 0.0 — got {book['dataset_pass_at_1']}; "
        f"per-query: {[(q['query_id'], q['pass_at_1']) for q in book['queries']]}"
    )
```

- [ ] **Step 1: Author the spec**

(Above.)

- [ ] **Step 2: Smoke-parse**

```bash
uv run python -c "from razorback.spec.parse import parse_spec_file; print(parse_spec_file('examples/specs/bookreview-claude.yaml'))"
```

Expected: prints a populated `Spec(...)` without raising.

- [ ] **Step 3: Run the integration test**

```bash
uv run pytest tests/integration/test_rk_run_bookreview_claude.py -v -s --timeout=900
```

Expected on the first real run: PASS, with bookreview pass@1 > 0.0 (typically 0.33–0.67 — claude usually nails one of the three bookreview queries; the AC is "non-zero", not a baseline score).

Failure-triage rules (do NOT inline-fix; escalate or revise the right module):
- `n_completed_trials < 3` and reward=0 across the board → check Task 1's smoke first. The path is broken — the smoke must be re-run.
- All trials complete, all rewards 0 → the agent ran but answered every query wrong. This is the AC-6 failure mode the entity explicitly flags as a STOP (the design assumes claude can solve at least one bookreview query). Escalate.
- `summary.json` missing `datasets.bookreview` → the aggregator dispatch broke; check `run.py`'s `isinstance(spec.benchmark, DabBenchmarkBlock)` branch.

- [ ] **Step 4: Commit**

```bash
git add examples/specs/bookreview-claude.yaml tests/integration/test_rk_run_bookreview_claude.py
git commit -m "m3: end-to-end bookreview-claude spec + integration test (AC-6)"
```

---

## Task 7: Final acceptance — full suite + the §8.M3 command

**Files:** none.

- [ ] **Step 1: Full unit suite**

```bash
uv run pytest tests/unit -v
```

Expected: every M1, M2, and M3 unit test green. Pristine output — no pydantic deprecation, no "coroutine was never awaited" lines. Per CL's rules.

- [ ] **Step 2: Full integration suite (slow, costs ~$0.05–0.15)**

```bash
uv run pytest tests/integration -v -s --timeout=900
```

Expected: AC-6 integration test passes. Task 1's smoke is redundant after AC-6 passes, but stays in the suite as a regression check.

- [ ] **Step 3: The §8.M3 acceptance command**

```bash
uv run rk run examples/specs/bookreview-claude.yaml
```

Expected: exit code 0; `_runs/m3-bookreview-claude/<job_name>/summary.json` exists; `jq '.datasets.bookreview.dataset_pass_at_1' …/summary.json` returns a value strictly > 0.0.

- [ ] **Step 4: No commit (acceptance run only).**

---

## Task 8: Cross-reference plan from the M3 entity body

**Files:**
- Modify: `docs/razorback-implementation/m3-claude-cli-agent.md` — Test plan section only

- [ ] **Step 1: Append one line under the Test plan section**

```
- **Implementation plan:** `docs/razorback-implementation/plans/m3-claude-cli-agent.md`.
```

Do not change the frontmatter; do not rewrite the Test plan; do not paraphrase existing bullets.

- [ ] **Step 2: Commit**

```bash
git add docs/razorback-implementation/m3-claude-cli-agent.md
git commit -m "m3: cross-reference implementation plan from entity Test plan"
```

---

## Self-review notes

- **AC coverage (1:1 with the AC↔task map at the top):**
  - AC-1 → Task 2 (registry + `required_env()` declaration test).
  - AC-2 → Tasks 3 (auth precedence), 4 (setup env-scrub test, never co-mingles).
  - AC-3 → Task 3 (`.env`-only loader, monkeypatched `os.environ` does not bleed).
  - AC-4 → Task 4 (`version()` parses `claude --version` via mocked subprocess).
  - AC-5 → Task 4 (`supported_sampling() == {"temperature"}`).
  - AC-6 → Tasks 1 (smoke, 1 query), 6 (full 3-query bookreview-claude integration).
  - AC-7 → Task 5 (translator stamps PROXY_BLOCK_ENV literally into task.toml's `[environment.env]`).
- **Riskiest contract first.** Task 1 — claude-CLI inside harbor docker reaching `api.anthropic.com` through the proxy block — runs *before* any registry/schema/agent-class code lands. If it red-lines, the FO is told to STOP and revise, not to scaffold around a broken contract. This satisfies the M3 entity's checklist item #2 verbatim.
- **`run_experiment.py` discipline inheritance.** The plan reads lines 1440-2046 verbatim and inherits the OAuth/API-key precedence rule:
  - `ANTHROPIC_API_KEY` from `.env` via `dotenv_values` first (`run_experiment.py:1905-1917` → `razorback.agents.auth._load_env_api_key`).
  - `CLAUDE_CODE_OAUTH_TOKEN` from `~/.claude/benchmark-token` as fallback (`run_experiment.py:1897-1902` → `razorback.agents.auth._read_claude_token`).
  - Never both; never from `os.environ`. Verbatim per `run_experiment.py:1993-2003`, tested by AC-2 and AC-3 in Task 3.
  - The proxy block (`run_experiment.py:1497-1525`) is copied byte-for-byte into `razorback.agents.proxy` with the test asserting the host list from line 1509-1513 verbatim. This satisfies the entity's checklist item #3.
- **Harbor's "required-env declaration mechanism".** Razorback uses harbor's `EnvironmentConfig.env: dict[str, str]` (the task.toml `[environment.env]` block) as the declaration surface (harbor's `get_required_host_vars` reads it). The agent class also exposes a `required_env()` class method (AC-1) that the translator and audit tooling can introspect *before* the run starts. Razorback resolves auth itself (Task 3) rather than using harbor's `${VAR}` template (which reads `os.environ`) because AC-3 forbids that source for auth.
- **No design divergence requiring escalation.** The design doc says "harbor's required-env declaration"; harbor 0.6.6's actual mechanism is `EnvironmentConfig.env` with `${VAR}` templates. The two reconcile: declaration = `required_env()` (a razorback-level introspection surface) + `EnvironmentConfig.env` (the harbor-level surface). The plan's tests assert the harbor surface (AC-1: `required_env()` content; AC-7: `EnvironmentConfig.env` content). If the FO finds at implementation time that harbor's docker env does NOT pass `AgentConfig.env`'s secrets through `environment.exec`'s child process env, the contract gap surfaces in Task 1 (smoke), not later — that's the whole point of risk-first.
- **No backwards-compat shims.** M2 already returns `(JobConfig, dict)` from `spec_to_job_config`; M3 keeps that shape and threads the new `project_root` / `home` kwargs through. The M1 schema's `AgentBlock` is replaced (not extended) by the discriminated union (`NopAgentBlock | ClaudeCliAgentBlock`); the existing `kind: nop` specs keep parsing because `NopAgentBlock` accepts that discriminator.
- **TDD discipline.** Every behavior task (1, 2, 3, 4, 5, 6) writes the failing test first, runs it red, then makes it green. Task 7 is acceptance (no new tests). Task 8 is docs cross-ref.
- **Commit cadence.** One focused commit per task; format `m3: <summary>`.
- **Implementation worktree.** Per Spacedock's plan-on-main + worktree-on-implementation discipline, this plan commits to `main` directly. The implementation stage will create a worktree (`.worktrees/spacedock-ensign-m3-claude-cli-agent/`) and land Tasks 1–8's code there.
