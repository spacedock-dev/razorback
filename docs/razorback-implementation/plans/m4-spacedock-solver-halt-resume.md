# M4 — `SpacedockSolverAgent` with halt-resume — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `SpacedockSolverAgent` — a third `BaseAgent` subclass that executes a multi-stage solve workflow (model → analyze → verify), commits the agent workspace to a private git repo at `logs_dir/agent_freeze/.git` at each stage boundary, writes `logs_dir/agent_freeze/phase_stats.json` per the §6.8 schema, and refuses to resume when sealed-stage inputs (model, sampling, stages config, prompt content) drift from the seed run's frozen spec — exiting with `SeedMismatchError` and CLI exit code 20 (§3.2). End-to-end against `bookreview` through harbor: one trial seeds, a second trial against the same `(jobs_dir, job_name)` resumes.

**Architecture:** A `razorback.agents.spacedock_solver` module adds a single `SpacedockSolverAgent(BaseAgent)` subclass that consumes a registry-validated `SpacedockSolverAgentConfig` from `AgentConfig.kwargs`. The registry (landed in M3 — Task 2 of `plans/m3-claude-cli-agent.md`) gains a `"spacedock-solver"` entry. The spec schema (extended in M3) gains a discriminated `SpacedockSolverAgentBlock` with `stages`, `seed`, `prompts`, `tools_allowed`, and `sampling`. The freeze step (M5 lands full provenance; M4 lands the slice it needs) extends `freeze_spec()` to read every `prompts.<stage>` file, content-hash it, and pin the hashes into `spec.frozen.yaml` — *the file content itself* is also pinned for hash-drift detection at run time, mirroring §6.4's promise that "the agent reads content from the frozen spec, not the file path." A small `razorback.agents.seal` module computes the canonical "sealed payload" (model + sampling + stages config + prompt hashes) and a single `sealed_hash` derived from it; the agent compares its construction-time sealed_hash against the run-dir's prior sealed_hash on resume.

**Tech Stack:** Python 3.12, `uv`, Pydantic 2.11, PyYAML 6, harbor 0.6.6 (pinned in M1), pytest 8 with `pytest-asyncio` 0.24, system `git` (subprocess, used inside the container's `environment.exec` for `agent_freeze/.git` commits AND on the host for unit-test fixtures), Colima docker as supplied by M1/M2.

**Source of truth:** the design doc at `/Users/clkao/git/dataagentbench/docs/superpowers/specs/2026-05-18-razorback-python-on-harbor.md`. Section anchors below cite it as `§N.N`. The 7 ACs live in the M4 entity at `docs/razorback-implementation/m4-spacedock-solver-halt-resume.md`. The exit-code 20 contract lives in §3.2 of the design and at `src/razorback/errors.py::ExitCode.SEED_MISMATCH`. The §6.8 `phase_stats.json` schema is a public contract the M5 aggregator reads.

**M1–M3 inputs (do not duplicate):**

- **From M1** (`src/razorback/`):
  - `errors.py::ExitCode.SEED_MISMATCH = 20`, `RazorbackError`, `SpecError` — M4 adds `SeedMismatchError(RazorbackError)` with `exit_code = ExitCode.SEED_MISMATCH`; the CLI's `cli/run.py:27-29` already maps `RazorbackError.exit_code` to `typer.Exit`, so exit code 20 surfaces with no CLI changes.
  - `spec/freeze.py::freeze_spec` — M4 extends to read+hash+pin prompt content into the frozen spec; `derive_job_name` shape unchanged.
  - `run.py::_execute_run_async` — unchanged in M4 except for the `project_root` kwarg threading already landed by M3 Task 5.
  - `manifest.py`, observers, channel drainer — unchanged.
- **From M2** (`src/razorback/benchmarks/dab/`): the prepare / verify / aggregate pipeline that fans out one harbor task per `(dataset, query_id)`. M4 changes only the **agent** half; the benchmark half is fixed. The aggregator (M2 `aggregate.py`) is unchanged in M4 — the per-stage cost rollup that consumes `phase_stats.json` is M5's work; M4 only **writes** the file per §6.8.
- **From M3** (`src/razorback/agents/`):
  - `registry.py::resolve_agent_kind` — the registry pattern is in place; M4 adds the `"spacedock-solver"` entry and `SpacedockSolverAgentConfig` schema **without** restructuring.
  - `proxy.py::PROXY_BLOCK_ENV` — the agent reuses the existing literal block.
  - `auth.py::resolve_claude_auth` — the agent uses claude credentials the same way `ClaudeCliAgent` does (the solver calls `claude -p` per stage); the auth loader is reused unmodified.
  - `claude_cli.py::ClaudeCliAgent` — `SpacedockSolverAgent` does **not** subclass it; both subclass `BaseAgent` directly. The `claude -p` invocation logic is the bit that's near-duplicated; a small `razorback.agents.claude_invoke` helper, extracted from M3's Task 4, holds the shared argv-builder. The M3 plan's Task 4 emits the argv inline in `claude_cli.py::run`; M4 Task 4 introduces the helper and refactors `ClaudeCliAgent.run` to call it. This refactor is the **only** M3-surface change M4 introduces.

**M4 sealed-input definition (divergence from M3, explicitly named):**

M3's content-hashing seals the **prompt file alone**. M4 seals **more**:

1. `agent.model` (the resolved model alias; M4 lands the alias only — full alias-drift detection is M5).
2. `agent.sampling.{temperature, top_p, seed}`.
3. `agent.stages` — the ordered list of stage names plus per-stage prompt key references.
4. `agent.prompts.<stage>` content hashes — one hash per prompt file referenced by any stage.

The four fields together produce a single `sealed_hash` (sha256 hex, first 32 chars) pinned into `spec.frozen.yaml` under `agent.sealed_hash`. AC-1 fires when the **just-constructed** `sealed_hash` for a resume spec differs from the seed run's frozen-spec `sealed_hash`. AC-3 fires when a prompt file's on-disk content differs from the hash pinned into the frozen spec at freeze time. AC-1 is the **stronger** contract; AC-3 is the per-prompt sub-check that fires inside the agent at `run()` time.

This divergence is **intentional and design-aligned**: §6.2's bullet on `SpacedockSolverAgent` names "sealed-stage inputs (model, sampling, prompt content)" as the refusal surface; the stages-config field is implied by "staged agent" but the design does not spell out a hash for it. The plan elects to include `stages` in the seal because reordering the stages or renaming one trivially invalidates a resume — the §6.2 promise of refuse-on-mismatch covers that case in spirit. The frozen-spec key is `agent.sealed_hash` (a single string), with the per-prompt hashes carried separately under `agent.prompts.<stage>.sha256` for the AC-3 sub-check; the run-dir manifest pin is `spec.frozen.yaml`'s top-level `agent.sealed_hash` field.

**Authoritative external references (DO NOT redesign — adapt verbatim):**

- `/Users/clkao/git/razorback/.venv/lib/python3.12/site-packages/harbor/agents/base.py` — the `BaseAgent` contract M4 implements. `name()` static abstractmethod, `version()` instance abstractmethod, `setup()` and `run()` async abstractmethods. Constructor signature: `(logs_dir, model_name=None, logger=None, mcp_servers=None, skills_dir=None, *args, **kwargs)`. `BaseAgent.import_path()` (line 88-93) already returns `f"{cls.__module__}:{cls.__name__}"` — Task 2's registry entry uses this directly.

- `/Users/clkao/git/razorback/.venv/lib/python3.12/site-packages/harbor/models/trial/config.py` — `AgentConfig.kwargs: dict[str, Any]` and `AgentConfig.env: dict[str, str]` (lines 44-57). M4 passes `resolved_auth_env`, `tools_allowed`, `stages`, `prompts`, `sampling`, `sealed_hash`, `model`, `agent_freeze_dir` (a relative path inside `logs_dir`) through `kwargs`.

- `/Users/clkao/git/razorback/.venv/lib/python3.12/site-packages/harbor/environments/base.py::BaseEnvironment.exec(command, cwd=None, env=None, timeout_sec=None, user=None) -> ExecResult` — the agent's escape hatch to the container. M4 uses this for `git init`, `git add -A`, `git commit -m`, and for the staged `claude -p` invocations.

- `/Users/clkao/git/dataagentbench/benchmark/lib/run_experiment.py` lines 1668-1683 (`build_agent_command`) and `/Users/clkao/git/dataagentbench/benchmark/solve.sh` line 105 — the `claude -p` argv shape. M4's per-stage invocation reuses the simplified shape locked in M3 Task 4: `claude -p <prompt> --allowedTools … --disallowedTools … --permission-mode bypassPermissions --model <resolved>`.

- The §6.8 `phase_stats.json` schema (design doc lines 564-573) — **public contract**. Verbatim shape:

  ```json
  {
    "model":   {"tokens_in": ..., "tokens_out": ..., "cost_usd": ..., "wallclock_s": ...},
    "analyze": {"tokens_in": ..., "tokens_out": ..., "cost_usd": ..., "wallclock_s": ...},
    "verify":  {"tokens_in": ..., "tokens_out": ..., "cost_usd": ..., "wallclock_s": ...}
  }
  ```

  The three stage names are **fixed by the design**: `model`, `analyze`, `verify`. M4's stages config in `agent.stages` declares this exact ordered list; the registry schema validates the list equals `["model", "analyze", "verify"]` (no other orderings, no extra stages — that's M5+ territory).

**AC ↔ task map (1:1):**

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1 — Halt-resume with mismatched sealed input exits `SeedMismatchError` (exit code 20) | §3.2 exit code 20; §6.2 third bullet ("refuses to resume when sealed-stage inputs do not match the seed's frozen spec") | Task 1 (riskiest contract) |
| AC-2 — Pydantic registry validates kwargs before harbor sees them | §6.2 ("the spec parser validates the agent block against the registered schema *before* `AgentConfig` is constructed") | Task 2 |
| AC-3 — Prompts content-hashed at freeze; agent refuses on hash drift | §6.4 ("Prompts are content-hashed at freeze time … the agent reads content from the frozen spec, not the file path, and refuses on hash drift") | Task 3 |
| AC-4 — `agent_freeze/.git` is a real git repo committed at each stage boundary | §6.2 third bullet; §6.3 layout (`logs_dir/agent_freeze/.git/`) | Task 5 |
| AC-5 — `phase_stats.json` matches the §6.8 schema | §6.8 verbatim | Task 6 |
| AC-6 — `tools_allowed` scrubs env and filters MCP servers at setup | §9.2; `run_experiment.py:1531-1549` DISALLOWED_TOOLS discipline | Task 4 |
| AC-7 — Razorback never writes inside harbor's `agent/`; razorback state lives under `logs_dir/agent_freeze/` | §6.3 ("razorback writes the `agent_freeze/` subtree there and never inside harbor's `agent/` directory") | Task 7 (audit + integration) |

**Riskiest contract first.** Task 1 is the AC-1 seed-mismatch refusal: a unit test where one fixture spec is the "seed" (a frozen spec with a `sealed_hash` baked in) and a second fixture is the "resume" (its `agent.prompt_file` content differs, producing a different `sealed_hash` when re-computed at construction time). The agent's `__init__` reads the resume spec, recomputes the sealed_hash, compares against the run-dir's prior `sealed_hash` from `spec.frozen.yaml`, and raises `SeedMismatchError` before any I/O — **before `harbor.Job.create` is even called**. The test's CLI variant asserts `subprocess.run([..., "rk", "run", resume_spec])` exits with returncode 20. If the sealed-hash contract or its run-dir wiring is wrong, the entire halt-resume promise is wrong and every later task scaffolds around a broken contract. Per CL's "Validating new mechanisms" rule, Task 1 lands first; the agent's staged-execution and git-freeze machinery come after.

**Why this satisfies the M4 entity's checklist item #2 verbatim:** the entity checklist says "the fixture explicitly mutates `agent.prompt_file` content hash between seed and resume specs; the test asserts the agent exits SeedMismatchError before reaching harbor.Job.create, and the CLI exit code is 20." Task 1 Step 1 mutates the prompt file content; Step 3 asserts `SeedMismatchError` is raised by the agent's `__init__` (before `Job.create`); Step 5 asserts the CLI subprocess returncode is 20.

**Working agreements pulled forward from M1/M2/M3:**

- Repo layout follows §7: `src/razorback/agents/{seal,claude_invoke,spacedock_solver}.py` are the new modules for M4.
- All Python source files start with the `ABOUTME:` two-line comment header (per CL's global rules). YAML/TOML/markdown data files do not.
- Pinned harbor is `harbor==0.6.6`; imports follow `docs/pre-m1-findings.md` "Harbor API map".
- macOS+Colima only mounts `/Users/<user>/` into the docker VM. All paths Colima must see are absolute under `/Users/...`.
- TDD: every behavior task writes the failing test first, runs it red, then makes it green, then commits.
- Commits: one focused commit per task. Format: `m4: <short summary>`.
- Plan-stage commits (this document) land on `main`. The implementation worktree is created at the start of M4 implementation (FO's job, not this plan's).

---

## File structure

Files created or modified by this plan. Existing files (from M1/M2/M3) marked `[existing]`.

```
examples/
└── specs/
    ├── bookreview-spacedock-seed.yaml                       [new] M4 acceptance seed spec
    ├── bookreview-spacedock-resume.yaml                     [new] M4 acceptance resume spec (matches seed)
    ├── bookreview-spacedock-resume-mismatch.yaml            [new] AC-1 fixture (drifted prompt)
    └── prompts/
        ├── spacedock-model.md                               [new] stage 1 prompt
        ├── spacedock-analyze.md                             [new] stage 2 prompt
        └── spacedock-verify.md                              [new] stage 3 prompt
src/razorback/
├── errors.py                                                [existing — extend with SeedMismatchError]
├── spec/
│   ├── schema.py                                            [existing M3 — extend AgentBlock]
│   └── freeze.py                                            [existing M1 — extend with prompt hashing]
├── agents/
│   ├── __init__.py                                          [existing M3 — unchanged]
│   ├── registry.py                                          [existing M3 — extend with spacedock-solver]
│   ├── auth.py                                              [existing M3 — unchanged]
│   ├── proxy.py                                             [existing M3 — unchanged]
│   ├── claude_cli.py                                        [existing M3 — refactor run() to use claude_invoke]
│   ├── claude_invoke.py                                     [new] — shared claude -p argv builder
│   ├── seal.py                                              [new] — sealed_hash + per-prompt content hashing
│   └── spacedock_solver.py                                  [new] — SpacedockSolverAgent(BaseAgent)
├── compat/
│   └── harbor_0_6_6.py                                      [existing M3 — extend with spacedock-solver branch]
└── run.py                                                   [existing M3 — extend to expose prior frozen spec on resume]
tests/
├── unit/
│   ├── test_spacedock_seed_mismatch.py                      [new] AC-1 — riskiest contract
│   ├── test_spacedock_registry.py                           [new] AC-2 — schema + SpecError on bad stages
│   ├── test_seal.py                                         [new] sealed_hash determinism + per-prompt hashing
│   ├── test_spec_freeze_prompts.py                          [new] AC-3 — freeze writes hashes + content
│   ├── test_spacedock_prompt_drift.py                       [new] AC-3 — run-time hash-drift refusal
│   ├── test_spacedock_phase_stats.py                        [new] AC-5 — schema
│   ├── test_spacedock_tools_allowed.py                      [new] AC-6 — MCP filtering + DISALLOWED_TOOLS
│   ├── test_spacedock_no_agent_dir_writes.py                [new] AC-7 — grep gate
│   └── test_spacedock_cli_seed_mismatch_exit_code.py        [new] AC-1 CLI variant — exit code 20
├── integration/
│   ├── test_spacedock_git_freeze.py                         [new] AC-4 — git repo at logs_dir/agent_freeze/.git
│   └── test_rk_run_bookreview_spacedock_halt_resume.py      [new] end-to-end seed → resume
└── fixtures/
    └── spacedock/
        ├── prompts/
        │   ├── model.md                                     [new]
        │   ├── analyze.md                                   [new]
        │   └── verify.md                                    [new]
        ├── seed-frozen-spec.yaml                            [new] AC-1 fixture
        └── resume-mismatch-frozen-spec.yaml                 [new] AC-1 fixture
docs/razorback-implementation/
└── m4-spacedock-solver-halt-resume.md                       [existing — append stage report only]
```

---

## Task 0: Pre-flight — confirm M3 surfaces and operator environment

**Files:** none.

- [ ] **Step 1: Verify M3's agent scaffold is on the implementation branch**

```bash
cd /Users/clkao/git/razorback
test -f src/razorback/agents/registry.py
test -f src/razorback/agents/auth.py
test -f src/razorback/agents/proxy.py
test -f src/razorback/agents/claude_cli.py
test -f src/razorback/errors.py
uv run python -c "from razorback.agents.registry import resolve_agent_kind; print(resolve_agent_kind('claude-cli').import_path)"
uv run python -c "from razorback.errors import ExitCode; assert ExitCode.SEED_MISMATCH == 20"
```

Expected: every file exists; `resolve_agent_kind('claude-cli').import_path == "razorback.agents.claude_cli:ClaudeCliAgent"`; `ExitCode.SEED_MISMATCH == 20` (already on `main` from M1).

If any file is missing: M3's implementation has not landed yet. M4's plan stage is **safe to write** without M3 implementation being complete (the plan only requires M3's *plan* — `plans/m3-claude-cli-agent.md` — which IS on `main`). However, M4 *implementation* must wait for M3 to land. STOP and escalate via `SendMessage(to="team-lead", …)` if the FO routes M4 to implementation while M3's surfaces are missing.

- [ ] **Step 2: Verify host environment**

```bash
which claude && claude --version
which git && git --version
docker info | head -3
.venv/bin/python -c "import harbor; print(harbor.__version__)"
ls /Users/clkao/git/dataagentbench/data/query_bookreview/
test -f .env && grep -c '^ANTHROPIC_API_KEY=\|^CLAUDE_CODE_OAUTH_TOKEN=' .env
```

Expected: `claude` and `git` on PATH; `git --version` ≥ 2.30 (needed for `git -C <dir> commit --allow-empty`); harbor reports `0.6.6`; bookreview dataset present; `.env` has at least one credential.

- [ ] **Step 3: No commit. This is a check, not a change.**

---

## Task 1: RISKIEST CONTRACT — `SeedMismatchError` on sealed-input drift (AC-1)

**Why first:** Per CL's "Validating new mechanisms" rule and the M4 entity's checklist item #2: the **seed-mismatch refusal** is the load-bearing contract for halt-resume. If the agent's `__init__` cannot recompute and compare the sealed_hash before any harbor I/O, every later task scaffolds around a broken refusal. Task 1 lands the smallest possible end-to-end exercise of this contract — a unit test that wires the agent's seed-mismatch check against two checked-in frozen-spec fixtures.

**Files:**
- Create: `src/razorback/errors.py` (extend — add `SeedMismatchError`)
- Create: `tests/fixtures/spacedock/prompts/model.md`
- Create: `tests/fixtures/spacedock/prompts/analyze.md`
- Create: `tests/fixtures/spacedock/prompts/verify.md`
- Create: `tests/fixtures/spacedock/seed-frozen-spec.yaml`
- Create: `tests/fixtures/spacedock/resume-mismatch-frozen-spec.yaml`
- Create: `tests/unit/test_spacedock_seed_mismatch.py`
- Create: `tests/unit/test_spacedock_cli_seed_mismatch_exit_code.py`
- Create: `src/razorback/agents/seal.py` (minimal API needed by Task 1)
- Create: `src/razorback/agents/spacedock_solver.py` (minimal skeleton; fleshed out in Tasks 2, 4, 5, 6)

§6.2 design wording (the refusal contract Task 1 enforces):

> `SpacedockSolverAgent` … refuses to resume when sealed-stage inputs (model, sampling, prompt content) do not match the seed's frozen spec.

§3.2 exit code 20:

> `SeedMismatchError` — halt-resume input hashes do not match the seed's frozen spec.

- [ ] **Step 1: Write the failing unit test (in-process, no CLI)**

`tests/fixtures/spacedock/prompts/model.md`:

```
You are the model stage. Solve the user query. Write your draft answer to /work/answers.json.
```

`tests/fixtures/spacedock/prompts/analyze.md`:

```
You are the analyze stage. Read /work/answers.json and critique your draft.
```

`tests/fixtures/spacedock/prompts/verify.md`:

```
You are the verify stage. Re-check the final answer in /work/answers.json against the query.
```

`tests/fixtures/spacedock/seed-frozen-spec.yaml`:

```yaml
version: 1
experiment: m4-seed-fixture
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
    top_p: null
    seed: 42
  stages: [model, analyze, verify]
  tools_allowed: [Bash, Read, Write, Edit, Glob, Grep]
  prompts:
    model: "sha256:SEED_MODEL_HASH_PLACEHOLDER"
    analyze: "sha256:SEED_ANALYZE_HASH_PLACEHOLDER"
    verify: "sha256:SEED_VERIFY_HASH_PLACEHOLDER"
  sealed_hash: "SEED_SEALED_HASH_PLACEHOLDER"
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
trials: 1
```

(The `_PLACEHOLDER` strings are stamped by a `conftest` helper in Step 2 — the fixture YAML is materialized with real sha256 values at test-collection time, computed from `tests/fixtures/spacedock/prompts/*.md`. We do not hand-edit hashes.)

`tests/fixtures/spacedock/resume-mismatch-frozen-spec.yaml`:

Identical to the seed spec **except** the `prompts.model` value points to a hash of a *different* model prompt (the fixture helper computes it from a synthetic `model.md` whose body is `"DRIFTED MODEL PROMPT"`), and `sealed_hash` is recomputed accordingly. The two yaml files differ ONLY in `prompts.model` and `sealed_hash` — `experiment`, `sampling`, `stages`, `tools_allowed`, etc. are byte-identical.

`tests/unit/test_spacedock_seed_mismatch.py`:

```python
# ABOUTME: AC-1 — SpacedockSolverAgent.__init__ refuses to resume when the resume spec's
# ABOUTME: sealed_hash does not match the seed run's frozen-spec sealed_hash. The refusal
# ABOUTME: must happen BEFORE any harbor I/O (no Job.create call).

import hashlib
from pathlib import Path

import pytest
import yaml

from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.agents.spacedock_solver import SpacedockSolverAgent
from razorback.errors import ExitCode, SeedMismatchError


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "spacedock"
PROMPT_DIR = FIXTURE_ROOT / "prompts"


def _materialize_seed_spec(tmp_path: Path) -> Path:
    """Stamp the seed fixture with real prompt hashes computed from prompts/*.md."""
    template = (FIXTURE_ROOT / "seed-frozen-spec.yaml").read_text()
    model_hash = prompt_sha256((PROMPT_DIR / "model.md").read_bytes())
    analyze_hash = prompt_sha256((PROMPT_DIR / "analyze.md").read_bytes())
    verify_hash = prompt_sha256((PROMPT_DIR / "verify.md").read_bytes())
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={"model": model_hash, "analyze": analyze_hash, "verify": verify_hash},
    )
    rendered = (template
        .replace("SEED_MODEL_HASH_PLACEHOLDER", model_hash)
        .replace("SEED_ANALYZE_HASH_PLACEHOLDER", analyze_hash)
        .replace("SEED_VERIFY_HASH_PLACEHOLDER", verify_hash)
        .replace("SEED_SEALED_HASH_PLACEHOLDER", sealed))
    spec_path = tmp_path / "seed.frozen.yaml"
    spec_path.write_text(rendered)
    return spec_path


def _materialize_resume_mismatch_spec(tmp_path: Path) -> Path:
    """Stamp the resume-mismatch fixture: same seed except `prompts.model` is drifted."""
    template = (FIXTURE_ROOT / "resume-mismatch-frozen-spec.yaml").read_text()
    drifted_model_body = b"DRIFTED MODEL PROMPT\n"
    drifted_model_hash = prompt_sha256(drifted_model_body)
    analyze_hash = prompt_sha256((PROMPT_DIR / "analyze.md").read_bytes())
    verify_hash = prompt_sha256((PROMPT_DIR / "verify.md").read_bytes())
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={"model": drifted_model_hash, "analyze": analyze_hash, "verify": verify_hash},
    )
    rendered = (template
        .replace("RESUME_MODEL_HASH_PLACEHOLDER", drifted_model_hash)
        .replace("RESUME_ANALYZE_HASH_PLACEHOLDER", analyze_hash)
        .replace("RESUME_VERIFY_HASH_PLACEHOLDER", verify_hash)
        .replace("RESUME_SEALED_HASH_PLACEHOLDER", sealed))
    spec_path = tmp_path / "resume.frozen.yaml"
    spec_path.write_text(rendered)
    return spec_path


def _agent_kwargs_from_frozen_spec(spec_path: Path) -> dict:
    """Read the agent block out of the frozen spec and shape it for SpacedockSolverAgent kwargs."""
    spec = yaml.safe_load(spec_path.read_text())
    agent = spec["agent"]
    return {
        "model": agent["model"],
        "sampling": dict(agent["sampling"]),
        "stages": list(agent["stages"]),
        "tools_allowed": list(agent["tools_allowed"]),
        "prompts": dict(agent["prompts"]),
        "sealed_hash": agent["sealed_hash"],
        "resolved_auth_env": {"ANTHROPIC_API_KEY": "sk-test"},
    }


def test_agent_init_refuses_when_resume_sealed_hash_mismatches_seed(tmp_path):
    """AC-1: the agent's __init__ refuses BEFORE any harbor I/O when sealed_hash drifts.

    Setup:
      1. Materialize a seed frozen spec → write to `<run_dir>/spec.frozen.yaml`.
      2. Materialize a resume-mismatch frozen spec (different `prompts.model` content).
      3. Construct SpacedockSolverAgent with kwargs taken from the resume spec, plus the
         `prior_frozen_spec_path` pointing at the seed run-dir's `spec.frozen.yaml`.
      4. Assert __init__ raises SeedMismatchError.
      5. Assert the error names the drifted field (`prompts.model`).
    """
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    seed_spec = _materialize_seed_spec(tmp_path)
    (run_dir / "spec.frozen.yaml").write_bytes(seed_spec.read_bytes())

    resume_spec = _materialize_resume_mismatch_spec(tmp_path)
    kwargs = _agent_kwargs_from_frozen_spec(resume_spec)

    with pytest.raises(SeedMismatchError) as exc:
        SpacedockSolverAgent(
            logs_dir=tmp_path / "agent_logs",
            model_name=kwargs["model"],
            prior_frozen_spec_path=run_dir / "spec.frozen.yaml",
            **kwargs,
        )

    msg = str(exc.value)
    # AC-1: the refusal message names the drifted field path so operators can fix it.
    assert "prompts.model" in msg or "sealed_hash" in msg
    # AC-1: the typed error carries exit code 20.
    assert exc.value.exit_code == ExitCode.SEED_MISMATCH


def test_agent_init_succeeds_when_sealed_hash_matches(tmp_path):
    """Negative twin: when the resume spec matches the seed, __init__ does not raise."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    seed_spec = _materialize_seed_spec(tmp_path)
    (run_dir / "spec.frozen.yaml").write_bytes(seed_spec.read_bytes())

    # The "resume" is byte-identical to the seed → sealed_hash matches.
    kwargs = _agent_kwargs_from_frozen_spec(seed_spec)
    agent = SpacedockSolverAgent(
        logs_dir=tmp_path / "agent_logs",
        model_name=kwargs["model"],
        prior_frozen_spec_path=run_dir / "spec.frozen.yaml",
        **kwargs,
    )
    assert agent.sealed_hash == kwargs["sealed_hash"]


def test_agent_init_succeeds_when_no_prior_frozen_spec(tmp_path):
    """Seed run path: no `prior_frozen_spec_path` (no run-dir yet) → no mismatch check, no raise."""
    seed_spec = _materialize_seed_spec(tmp_path)
    kwargs = _agent_kwargs_from_frozen_spec(seed_spec)
    agent = SpacedockSolverAgent(
        logs_dir=tmp_path / "agent_logs",
        model_name=kwargs["model"],
        prior_frozen_spec_path=None,
        **kwargs,
    )
    assert agent.sealed_hash == kwargs["sealed_hash"]


def test_agent_refusal_happens_before_any_harbor_io(tmp_path, monkeypatch):
    """AC-1 explicit: the refusal happens BEFORE harbor.Job.create is called.

    We monkeypatch Job.create to raise if invoked; the agent's __init__ must
    SeedMismatchError without ever touching it.
    """
    from harbor.job import Job

    def _explode(*a, **kw):
        raise AssertionError("Job.create called — refusal did NOT happen before harbor I/O")

    monkeypatch.setattr(Job, "create", _explode)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    seed_spec = _materialize_seed_spec(tmp_path)
    (run_dir / "spec.frozen.yaml").write_bytes(seed_spec.read_bytes())
    resume_spec = _materialize_resume_mismatch_spec(tmp_path)
    kwargs = _agent_kwargs_from_frozen_spec(resume_spec)

    with pytest.raises(SeedMismatchError):
        SpacedockSolverAgent(
            logs_dir=tmp_path / "agent_logs",
            model_name=kwargs["model"],
            prior_frozen_spec_path=run_dir / "spec.frozen.yaml",
            **kwargs,
        )
```

- [ ] **Step 2: Write the failing CLI-level test (exit code 20)**

`tests/unit/test_spacedock_cli_seed_mismatch_exit_code.py`:

```python
# ABOUTME: AC-1 (CLI variant) — `rk run` against a resume spec whose sealed_hash
# ABOUTME: mismatches the run-dir's prior frozen spec exits with code 20.

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from razorback.agents.seal import compute_sealed_hash, prompt_sha256


REPO = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO / "tests" / "fixtures" / "spacedock"
PROMPT_DIR = FIXTURE_ROOT / "prompts"


def _write_resume_spec_with_drifted_model_prompt(tmp_path: Path) -> tuple[Path, Path]:
    """Materialize a runs-dir with a seed frozen-spec.yaml, and a separate resume spec yaml
    whose `prompts.model` content hash differs. Returns (resume_spec_yaml, runs_dir)."""
    # 1) Build the seed frozen spec on disk → place under runs_dir as the prior.
    runs_dir = tmp_path / "_runs"
    experiment = "m4-cli-seed-mismatch"
    job_name = "0" * 16  # any 16-hex placeholder; the test re-uses it.
    run_dir = runs_dir / experiment / job_name
    run_dir.mkdir(parents=True)

    model_hash = prompt_sha256((PROMPT_DIR / "model.md").read_bytes())
    analyze_hash = prompt_sha256((PROMPT_DIR / "analyze.md").read_bytes())
    verify_hash = prompt_sha256((PROMPT_DIR / "verify.md").read_bytes())
    seed_sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={"model": model_hash, "analyze": analyze_hash, "verify": verify_hash},
    )
    seed_frozen = {
        "version": 1,
        "experiment": experiment,
        "agent": {
            "kind": "spacedock-solver",
            "model": "claude-opus-4-5",
            "sampling": {"temperature": 0.0, "top_p": None, "seed": 42},
            "stages": ["model", "analyze", "verify"],
            "tools_allowed": ["Bash", "Read", "Write", "Edit"],
            "prompts": {"model": model_hash, "analyze": analyze_hash, "verify": verify_hash},
            "sealed_hash": seed_sealed,
        },
        "benchmark": {
            "kind": "dab",
            "data_root": "/Users/clkao/git/dataagentbench/data",
            "datasets": ["bookreview"],
        },
        "trials": 1,
        "observers": [],
    }
    (run_dir / "spec.frozen.yaml").write_text(yaml.safe_dump(seed_frozen, sort_keys=False))

    # 2) Build the resume spec (NOT yet frozen) whose model prompt points at a different file.
    drifted_prompt = tmp_path / "drifted-model.md"
    drifted_prompt.write_text("DRIFTED MODEL PROMPT\n")

    resume_yaml = {
        "version": 1,
        "experiment": experiment,
        "agent": {
            "kind": "spacedock-solver",
            "model": "claude-opus-4-5",
            "sampling": {"temperature": 0.0, "top_p": None, "seed": 42},
            "stages": ["model", "analyze", "verify"],
            "tools_allowed": ["Bash", "Read", "Write", "Edit"],
            "prompts": {
                "model": str(drifted_prompt),
                "analyze": str(PROMPT_DIR / "analyze.md"),
                "verify": str(PROMPT_DIR / "verify.md"),
            },
        },
        "benchmark": {
            "kind": "dab",
            "data_root": "/Users/clkao/git/dataagentbench/data",
            "datasets": ["bookreview"],
        },
        "trials": 1,
        "observers": [],
    }
    resume_spec = tmp_path / "resume.yaml"
    resume_spec.write_text(yaml.safe_dump(resume_yaml, sort_keys=False))
    return resume_spec, runs_dir


@pytest.mark.timeout(60)
def test_rk_run_exits_20_on_seed_mismatch(tmp_path):
    """AC-1 CLI: subprocess `rk run <resume>` returncode is 20.

    This test is unit-scoped (no harbor docker; no real claude call): the agent's
    __init__ raises SeedMismatchError before harbor.Job.create runs, so the CLI
    surfaces exit code 20 with no container side effects.
    """
    resume_spec, runs_dir = _write_resume_spec_with_drifted_model_prompt(tmp_path)
    env = {**os.environ, "ANTHROPIC_API_KEY": "sk-test-fake"}
    result = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(resume_spec),
         "--runs-dir", str(runs_dir)],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 20, (
        f"expected exit code 20 (SeedMismatchError); got {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "SeedMismatchError" in result.stderr
```

- [ ] **Step 3: Run both tests, confirm red**

```bash
uv run pytest tests/unit/test_spacedock_seed_mismatch.py tests/unit/test_spacedock_cli_seed_mismatch_exit_code.py -v
```

Expected: ImportError on `razorback.agents.seal`, `razorback.agents.spacedock_solver`, `razorback.errors.SeedMismatchError`.

- [ ] **Step 4: Implement the minimal `errors.SeedMismatchError`**

Add to `src/razorback/errors.py`:

```python
class SeedMismatchError(RazorbackError):
    """Halt-resume sealed-input hashes do not match the seed's frozen spec (§3.2)."""
    exit_code: int = ExitCode.SEED_MISMATCH
```

- [ ] **Step 5: Implement the minimal `agents/seal.py`**

`src/razorback/agents/seal.py`:

```python
# ABOUTME: Sealed-input hashing for SpacedockSolverAgent halt-resume (§6.2, §6.4).
# ABOUTME: compute_sealed_hash returns the single hex string pinned into spec.frozen.yaml.

import hashlib
import json
from typing import Any


def prompt_sha256(content_bytes: bytes) -> str:
    """Return the sha256 hex of a prompt file's bytes, prefixed `sha256:`.

    The prefix is part of the wire format pinned into spec.frozen.yaml — readers
    can distinguish hash algorithms in future versions without breaking the field shape.
    """
    return "sha256:" + hashlib.sha256(content_bytes).hexdigest()


def compute_sealed_hash(
    *,
    model: str,
    sampling: dict[str, Any],
    stages: list[str],
    prompt_hashes: dict[str, str],
) -> str:
    """Compute the M4 sealed_hash from the four sealed fields.

    The hash is deterministic over a canonical JSON encoding:
      - keys sorted alphabetically at every level,
      - separators=(",", ":"),
      - prompt_hashes keys sorted,
      - stages list order preserved (the order IS part of the seal).

    Returns the first 32 hex chars of the sha256 (the §6.7 job_name convention
    uses 16; the sealed_hash gets 32 because its collision domain spans every
    prompt+model+sampling combination ever frozen — wider safety margin is cheap).
    """
    payload = {
        "model": model,
        "sampling": _canonicalize_sampling(sampling),
        "stages": list(stages),
        "prompt_hashes": {k: prompt_hashes[k] for k in sorted(prompt_hashes)},
    }
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()[:32]


def _canonicalize_sampling(sampling: dict[str, Any]) -> dict[str, Any]:
    """Coerce sampling to a canonical, JSON-deterministic shape.

    null/None values are pinned (not dropped): "seed is unset" is part of the seal.
    Float values are formatted as JSON-default Python floats (0.0 → 0.0, not "0.0").
    """
    return {
        "temperature": sampling.get("temperature"),
        "top_p": sampling.get("top_p"),
        "seed": sampling.get("seed"),
    }
```

- [ ] **Step 6: Implement the minimal `agents/spacedock_solver.py` skeleton**

`src/razorback/agents/spacedock_solver.py`:

```python
# ABOUTME: SpacedockSolverAgent (§6.2 third bullet) — staged solver with halt-resume.
# ABOUTME: __init__ recomputes sealed_hash and refuses on mismatch BEFORE any harbor I/O.

from pathlib import Path
from typing import Any

import yaml

from harbor.agents.base import BaseAgent

from razorback.agents.seal import compute_sealed_hash
from razorback.errors import SeedMismatchError, RazorbackError


class SpacedockSolverAgentError(RazorbackError):
    pass


class SpacedockSolverAgent(BaseAgent):
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
        model: str,
        sampling: dict[str, Any],
        stages: list[str],
        tools_allowed: list[str],
        prompts: dict[str, str],
        sealed_hash: str,
        resolved_auth_env: dict[str, str],
        prior_frozen_spec_path: Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name or model,
            logger=logger,
            mcp_servers=mcp_servers,
            skills_dir=skills_dir,
            **kwargs,
        )
        self._model = model
        self._sampling = dict(sampling)
        self._stages = list(stages)
        self._tools_allowed = list(tools_allowed)
        self._prompts = dict(prompts)
        self.sealed_hash = sealed_hash
        self._resolved_auth_env = dict(resolved_auth_env)

        # AC-1: BEFORE harbor I/O — refuse on sealed-hash mismatch.
        self._refuse_on_resume_mismatch(prior_frozen_spec_path)

    def _refuse_on_resume_mismatch(self, prior_frozen_spec_path: Path | None) -> None:
        if prior_frozen_spec_path is None:
            return  # First run; no prior frozen spec to compare against.
        prior = yaml.safe_load(Path(prior_frozen_spec_path).read_text())
        prior_agent = prior.get("agent", {})
        prior_sealed = prior_agent.get("sealed_hash")
        if prior_sealed is None:
            raise SpacedockSolverAgentError(
                f"prior frozen spec at {prior_frozen_spec_path} has no agent.sealed_hash — "
                "cannot validate resume."
            )
        # Recompute our own sealed_hash from the kwargs we just constructed against.
        # Stamping the value through the registry SHOULD already produce a matching
        # sealed_hash — but we recompute defensively so a tampered spec.frozen.yaml
        # cannot smuggle a mismatched (sealed_hash, prompt_hashes) pair past us.
        recomputed = compute_sealed_hash(
            model=self._model,
            sampling=self._sampling,
            stages=self._stages,
            prompt_hashes={k: v for k, v in self._prompts.items() if v.startswith("sha256:")},
        )
        if recomputed != self.sealed_hash:
            raise SeedMismatchError(
                f"resume spec's recomputed sealed_hash ({recomputed}) does not match "
                f"its declared sealed_hash ({self.sealed_hash}). "
                "Tampered or stale frozen spec."
            )
        if self.sealed_hash != prior_sealed:
            # Find the drifted field to surface in the message.
            drifted = self._find_drifted_field(prior_agent)
            raise SeedMismatchError(
                f"resume sealed_hash ({self.sealed_hash}) does not match prior seed run "
                f"sealed_hash ({prior_sealed}). Drifted field: {drifted}. "
                f"Prior frozen spec: {prior_frozen_spec_path}"
            )

    def _find_drifted_field(self, prior_agent: dict[str, Any]) -> str:
        """Compare self's sealed fields against prior_agent; return a field-path string."""
        if prior_agent.get("model") != self._model:
            return f"model (seed={prior_agent.get('model')!r}, resume={self._model!r})"
        if prior_agent.get("sampling") != self._sampling:
            return "sampling"
        if list(prior_agent.get("stages", [])) != self._stages:
            return "stages"
        prior_prompts = prior_agent.get("prompts", {})
        for name, my_hash in self._prompts.items():
            if not my_hash.startswith("sha256:"):
                continue  # Unfrozen prompts — drift detection lives in AC-3.
            if prior_prompts.get(name) != my_hash:
                return f"prompts.{name}"
        return "sealed_hash"

    @staticmethod
    def name() -> str:
        return "spacedock-solver"

    def version(self) -> str | None:
        return None  # Task 4 wires `claude --version` once we're past Task 1's contract.

    @classmethod
    def required_env(cls) -> dict:
        return {"mode": "alternation", "names": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]}

    @staticmethod
    def supported_sampling() -> set[str]:
        # Same as ClaudeCliAgent — the solver wraps `claude -p` per stage.
        return {"temperature"}

    async def setup(self, environment) -> None:  # Task 4
        raise NotImplementedError

    async def run(self, instruction, environment, context) -> None:  # Task 5
        raise NotImplementedError
```

- [ ] **Step 7: Run unit tests, confirm green**

```bash
uv run pytest tests/unit/test_spacedock_seed_mismatch.py -v
```

Expected: 4 passed (4 tests in the file).

- [ ] **Step 8: Run CLI test, confirm green**

The CLI test runs `python -m razorback.cli run <resume_spec> --runs-dir <runs_dir>`. For it to surface SeedMismatchError, the run orchestrator must:

1. Compute `derive_job_name` from the resume spec's frozen text (M1: already does this).
2. Detect that `runs_dir / experiment / <job_name> / spec.frozen.yaml` already exists (the seed's prior frozen spec).
3. Pass `prior_frozen_spec_path=<that path>` into the translator → into `AgentConfig.kwargs` → into the agent's `__init__`.
4. The agent's `__init__` raises `SeedMismatchError` (no harbor.Job.create call); the CLI's `except RazorbackError` block (`cli/run.py:27-29`) maps to exit code 20.

The CLI test fixture intentionally constructs `runs_dir / experiment / "0" * 16 / spec.frozen.yaml`. For the test to work, the resume spec's freeze MUST produce a `job_name` of `"0" * 16` — or the run orchestrator must locate the prior frozen spec by `experiment` name plus a "find any matching prior" lookup. The cleanest fix: the test computes the *actual* freeze hash of the resume spec, stamps that as the `runs_dir / experiment / <real_job_name>` directory name, and writes the seed frozen spec there. Update the test fixture helper:

In `tests/unit/test_spacedock_cli_seed_mismatch_exit_code.py`, replace the `job_name = "0" * 16` line with:

```python
# Compute the resume spec's job_name so harbor's (jobs_dir, job_name) lock matches.
from razorback.spec.parse import parse_spec_file
from razorback.spec.freeze import freeze_spec, derive_job_name
# Write resume_spec first (placeholder hashes), then read it back for the freeze.
# Defer until after resume_spec.write_text(...).
...
parsed = parse_spec_file(resume_spec)
frozen = freeze_spec(parsed)
job_name = derive_job_name(frozen)
run_dir = runs_dir / experiment / job_name
run_dir.mkdir(parents=True)
(run_dir / "spec.frozen.yaml").write_text(yaml.safe_dump(seed_frozen, sort_keys=False))
```

The order in the test body is: (a) build the resume spec yaml on disk; (b) freeze it to derive `job_name`; (c) construct the run_dir at that job_name; (d) write the seed `spec.frozen.yaml` (which carries the *seed* sealed_hash, not the resume's) into it; (e) invoke `rk run <resume_spec>`; (f) the agent's `__init__` reads the seed spec at `<run_dir>/spec.frozen.yaml`, recomputes the resume's sealed_hash, sees the mismatch, raises.

This requires the run orchestrator (`run.py::_execute_run_async`) to thread `prior_frozen_spec_path=run_dir / "spec.frozen.yaml"` into the translator. Step 9 lands that.

- [ ] **Step 9: Wire `prior_frozen_spec_path` through the orchestrator and translator**

Modify `src/razorback/run.py::_execute_run_async`:

```python
async def _execute_run_async(*, spec: Spec, runs_dir: Path) -> None:
    frozen_text = freeze_spec(spec)
    job_name = derive_job_name(frozen_text)

    run_dir = Path(runs_dir).resolve() / spec.experiment / job_name
    run_dir.mkdir(parents=True, exist_ok=True)

    prior_frozen_spec_path: Path | None = None
    spec_frozen_path = run_dir / "spec.frozen.yaml"
    if spec_frozen_path.exists():
        # Resume path: a prior run-dir for this (experiment, job_name) exists.
        prior_frozen_spec_path = spec_frozen_path

    spec_frozen_path.write_text(frozen_text)
    write_manifest(run_dir / "manifest.json", experiment=spec.experiment, job_name=job_name)
    ...
    job_config = spec_to_job_config(
        spec,
        job_name=job_name,
        jobs_dir=run_dir.parent,
        tasks_root=run_dir / "tasks",
        project_root=Path.cwd(),
        prior_frozen_spec_path=prior_frozen_spec_path,
    )
    ...
```

(The exact location of `tasks_root` and `project_root` follows the M3 plan Task 5 Step 5. M4 adds only `prior_frozen_spec_path`.)

Modify `src/razorback/compat/harbor_0_6_6.py::spec_to_job_config` to accept and thread the new kwarg into the spacedock-solver agent kwargs:

```python
def spec_to_job_config(
    spec: Spec,
    *,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path | None = None,
    project_root: Path | None = None,
    home: Path | None = None,
    prior_frozen_spec_path: Path | None = None,
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    agent_cfg, task_env = _build_agent_config(
        spec,
        project_root=project_root,
        home=home,
        prior_frozen_spec_path=prior_frozen_spec_path,
    )
    ...
```

In `_build_agent_config`, the spacedock-solver branch (added in Task 2) sets `kwargs["prior_frozen_spec_path"] = prior_frozen_spec_path` when present.

(Task 1 lands a **stub** spacedock-solver branch in `_build_agent_config` — just enough to thread the kwarg through. Task 2 fleshes out the registry-validated kwarg shape.)

- [ ] **Step 10: Run BOTH tests, confirm green**

```bash
uv run pytest tests/unit/test_spacedock_seed_mismatch.py tests/unit/test_spacedock_cli_seed_mismatch_exit_code.py -v
```

Expected: 5 passed total (4 from the in-process test, 1 from the CLI test).

- [ ] **Step 11: Commit**

```bash
git add src/razorback/errors.py src/razorback/agents/seal.py src/razorback/agents/spacedock_solver.py src/razorback/run.py src/razorback/compat/harbor_0_6_6.py tests/fixtures/spacedock/ tests/unit/test_spacedock_seed_mismatch.py tests/unit/test_spacedock_cli_seed_mismatch_exit_code.py
git commit -m "m4: risk-first — SeedMismatchError on sealed-input drift (AC-1)"
```

If Step 10's tests pass, the load-bearing M4 contract is locked. The rest of the plan is implementation detail.

**Failure-triage rules:**
- ImportError on `razorback.spec.parse` or `razorback.spec.freeze` from the CLI test — M1 surfaces missing. STOP, escalate.
- `SeedMismatchError` raised in the negative twin (`test_agent_init_succeeds_when_sealed_hash_matches`) — the `compute_sealed_hash` canonicalization is wrong. Verify the JSON key sort + the sampling canonicalization. Do NOT loosen the recompute check.
- CLI test returncode != 20 — the orchestrator did not thread `prior_frozen_spec_path`. Re-check Step 9.
- The CLI test triggers `harbor.Job.create` (i.e. `Job.create called …` AssertionError appears in the in-process test variant) — the agent's `__init__` is constructed AFTER `Job.create`. Harbor's `Job.create` instantiates the agent from `AgentConfig.import_path + kwargs`; the refusal must surface inside that construction, before `await job.run()`. The shape works because `Job.create` calls the constructor; if it doesn't, the M3 plan's translator wiring is wrong and the FO escalates.

---

## Task 2: Agent-kind registry + `SpacedockSolverAgentConfig` schema (AC-2)

**Files:**
- Modify: `src/razorback/agents/registry.py` (extend — add `SpacedockSolverAgentConfig` and `_REGISTRY` entry)
- Modify: `src/razorback/spec/schema.py` (extend `AgentBlock` discriminated union — add `SpacedockSolverAgentBlock`)
- Create: `tests/unit/test_spacedock_registry.py`

§6.2 design wording (verbatim):

> Razorback ships a pydantic registry keyed by `agent.kind`; the spec parser validates the agent block against the registered schema *before* `AgentConfig` is constructed. Failures raise a typed `SpecError` with a field path; the run never reaches harbor.

The M4 registry entry MUST:

1. Accept `agent.kind: spacedock-solver`.
2. Validate `stages == ["model", "analyze", "verify"]` exactly (the §6.8 schema fixes those three names).
3. Validate `model: str` non-empty.
4. Validate `sampling.temperature: float`, `sampling.top_p: float | None`, `sampling.seed: int | None`.
5. Validate `tools_allowed: list[str]`.
6. Validate `prompts: dict[str, str]` where keys are a superset of `stages` (each stage has a prompt; extra keys reject).
7. **Reject unknown fields** (pydantic `extra="forbid"`).
8. Map to import_path `razorback.agents.spacedock_solver:SpacedockSolverAgent`.

The spec-level `SpacedockSolverAgentBlock` (in `spec/schema.py`) is what razorback parses from yaml. The registry-level `SpacedockSolverAgentConfig` (in `agents/registry.py`) is what the translator passes to harbor as `AgentConfig.kwargs`. The two shapes differ slightly: the spec block carries raw prompt **file paths** (which the freeze step resolves into hashes); the registry config carries the resolved `prompts: dict[str, str]` (hashes) plus `sealed_hash: str`. Task 5 of the M3 plan established that the spec block validates the raw spec while the translator stamps the kwargs the agent class consumes.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_spacedock_registry.py`:

```python
# ABOUTME: AC-2 — agent.kind=spacedock-solver registry entry validates kwargs BEFORE
# ABOUTME: harbor.AgentConfig is constructed. SpecError on bad stages, bad prompts, unknown fields.

import pytest

from razorback.agents.registry import resolve_agent_kind, AgentKindError
from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text


def test_spacedock_solver_kind_resolves_to_schema_and_import_path():
    entry = resolve_agent_kind("spacedock-solver")
    assert entry.import_path == "razorback.agents.spacedock_solver:SpacedockSolverAgent"
    cfg = entry.config_schema(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=["Bash", "Read"],
        prompts={"model": "sha256:aa", "analyze": "sha256:bb", "verify": "sha256:cc"},
        sealed_hash="deadbeef" * 4,
    )
    assert cfg.stages == ["model", "analyze", "verify"]


def test_spec_parse_rejects_unknown_stages():
    """AC-2: stages != [model, analyze, verify] raises SpecError BEFORE harbor sees it."""
    bad_spec = """\
version: 1
experiment: bad-stages
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling: {temperature: 0.0, seed: 42}
  stages: [model, verify]
  tools_allowed: []
  prompts:
    model: ./prompts/m.md
    verify: ./prompts/v.md
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
"""
    with pytest.raises(SpecError) as exc:
        parse_spec_text(bad_spec)
    # The error message names the offending field path.
    assert "stages" in str(exc.value)


def test_spec_parse_rejects_prompts_missing_a_stage():
    bad_spec = """\
version: 1
experiment: missing-prompt
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling: {temperature: 0.0, seed: 42}
  stages: [model, analyze, verify]
  tools_allowed: []
  prompts:
    model: ./prompts/m.md
    analyze: ./prompts/a.md
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
"""
    with pytest.raises(SpecError) as exc:
        parse_spec_text(bad_spec)
    assert "prompts" in str(exc.value) and "verify" in str(exc.value)


def test_spec_parse_rejects_unknown_agent_kwargs():
    bad_spec = """\
version: 1
experiment: extra-key
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling: {temperature: 0.0, seed: 42}
  stages: [model, analyze, verify]
  tools_allowed: []
  prompts:
    model: ./prompts/m.md
    analyze: ./prompts/a.md
    verify: ./prompts/v.md
  frobnicator: true
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
"""
    with pytest.raises(SpecError) as exc:
        parse_spec_text(bad_spec)
    assert "frobnicator" in str(exc.value) or "extra" in str(exc.value).lower()


def test_unknown_kind_raises_agent_kind_error():
    with pytest.raises(AgentKindError):
        resolve_agent_kind("definitely-not-real")


def test_existing_kinds_still_resolve():
    """M3's nop + claude-cli kinds keep resolving — M4 only adds, never removes."""
    assert resolve_agent_kind("nop").import_path is None
    assert resolve_agent_kind("claude-cli").import_path == "razorback.agents.claude_cli:ClaudeCliAgent"
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_spacedock_registry.py -v
```

Expected: AgentKindError on `spacedock-solver` (registry entry missing); ValidationError on the spec-parse tests (the discriminated union doesn't accept `spacedock-solver`).

- [ ] **Step 3: Extend `agents/registry.py`**

Add to `src/razorback/agents/registry.py`:

```python
from typing import Literal

from pydantic import field_validator, model_validator


_VALID_STAGES = ("model", "analyze", "verify")


class _SamplingKwargs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature: float
    top_p: float | None = None
    seed: int | None = None


class SpacedockSolverAgentConfig(BaseModel):
    """Registry-level kwargs validated BEFORE harbor.AgentConfig is constructed."""
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1)
    sampling: _SamplingKwargs
    stages: list[Literal["model", "analyze", "verify"]]
    tools_allowed: list[str] = Field(default_factory=list)
    prompts: dict[str, str]
    sealed_hash: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")

    @field_validator("stages")
    @classmethod
    def _stages_must_be_exact_order(cls, v: list[str]) -> list[str]:
        if v != list(_VALID_STAGES):
            raise ValueError(
                f"stages must be exactly {list(_VALID_STAGES)!r}; got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _prompts_cover_every_stage(self) -> "SpacedockSolverAgentConfig":
        missing = set(self.stages) - set(self.prompts.keys())
        if missing:
            raise ValueError(f"prompts missing for stages: {sorted(missing)}")
        extra = set(self.prompts.keys()) - set(self.stages)
        if extra:
            raise ValueError(f"prompts has keys not in stages: {sorted(extra)}")
        return self


# Extend the existing _REGISTRY mapping (do NOT redeclare it):
_REGISTRY["spacedock-solver"] = AgentKindEntry(
    SpacedockSolverAgentConfig,
    "razorback.agents.spacedock_solver:SpacedockSolverAgent",
)
```

- [ ] **Step 4: Extend `spec/schema.py` discriminated union**

Add to `src/razorback/spec/schema.py`:

```python
from pydantic import field_validator, model_validator


class _SpecSamplingBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature: float = 0.0
    top_p: float | None = None
    seed: int | None = None


class SpacedockSolverAgentBlock(BaseModel):
    """Spec-level agent block; carries prompt FILE PATHS (the freeze step resolves them)."""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["spacedock-solver"]
    model: str = "claude-opus-4-5"
    sampling: _SpecSamplingBlock = Field(default_factory=_SpecSamplingBlock)
    stages: list[Literal["model", "analyze", "verify"]] = Field(
        default_factory=lambda: ["model", "analyze", "verify"]
    )
    tools_allowed: list[str] = Field(default_factory=list)
    # In an UNFROZEN spec: file paths. In a FROZEN spec: "sha256:<hex>" strings.
    prompts: dict[str, str] = Field(default_factory=dict)
    # Pinned by freeze; absent in unfrozen specs.
    sealed_hash: str | None = None

    @field_validator("stages")
    @classmethod
    def _stages_exact(cls, v: list[str]) -> list[str]:
        if v != ["model", "analyze", "verify"]:
            raise ValueError(f"stages must be ['model', 'analyze', 'verify']; got {v!r}")
        return v

    @model_validator(mode="after")
    def _prompts_cover_stages(self) -> "SpacedockSolverAgentBlock":
        missing = set(self.stages) - set(self.prompts.keys())
        if missing:
            raise ValueError(f"prompts missing for stages: {sorted(missing)}")
        extra = set(self.prompts.keys()) - set(self.stages)
        if extra:
            raise ValueError(f"prompts has keys not in stages: {sorted(extra)}")
        return self


# Extend the union — add SpacedockSolverAgentBlock alongside Nop and ClaudeCli:
AgentBlock = Annotated[
    Union[NopAgentBlock, ClaudeCliAgentBlock, SpacedockSolverAgentBlock],
    Field(discriminator="kind"),
]
```

`parse_spec_text` (in `src/razorback/spec/parse.py`) already wraps pydantic `ValidationError` in `SpecError` with a field path — no changes needed there. (Verify by reading the M1-shipped `parse_spec_text` body; if it doesn't wrap, M3 added that wrapping in Task 2; if neither did, add the wrap as Step 4b before running the tests.)

- [ ] **Step 5: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_spacedock_registry.py tests/unit/test_spec_parse.py tests/unit/test_dab_spec_parse.py -v
```

Expected: every test passes. M1, M2, M3 spec-parse tests stay green because the union only adds a new variant.

- [ ] **Step 6: Commit**

```bash
git add src/razorback/agents/registry.py src/razorback/spec/schema.py tests/unit/test_spacedock_registry.py
git commit -m "m4: registry + schema for spacedock-solver kind (AC-2)"
```

---

## Task 3: Freeze prompts content into `spec.frozen.yaml` + run-time drift refusal (AC-3)

**Files:**
- Modify: `src/razorback/spec/freeze.py` (extend `freeze_spec` to resolve prompt file paths to `sha256:` strings AND embed content)
- Create: `tests/unit/test_spec_freeze_prompts.py`
- Create: `tests/unit/test_spacedock_prompt_drift.py`

§6.4 design wording (verbatim):

> Prompts are content-hashed at freeze time. A spec's `prompts.model: ./prompts/model.md` resolves to file content; the hash pins into `spec.frozen.yaml`. The agent reads content from the frozen spec, not the file path, and refuses on hash drift.

The freeze step does TWO things for a spacedock-solver spec:

1. For each `prompts.<stage>` file path, read the bytes, compute `prompt_sha256(bytes)`, replace the value with the `sha256:` string.
2. Embed the prompt **content** alongside the hash so the agent at run time uses the frozen content (not the file path). The shape:

   ```yaml
   agent:
     prompts:
       model: "sha256:<hex>"
       analyze: "sha256:<hex>"
       verify: "sha256:<hex>"
     prompt_contents:
       model: |
         <prompt body>
       analyze: |
         <prompt body>
       verify: |
         <prompt body>
   ```

   The `prompt_contents` field is a frozen-spec-only field (absent from unfrozen specs). The spec schema accepts it as optional on `SpacedockSolverAgentBlock`. At run time the agent reads `prompt_contents.<stage>`, re-hashes it, and verifies the hash matches `prompts.<stage>`. **That's the AC-3 hash-drift check** — it fires when the frozen spec has been tampered with after freeze.

3. After resolving prompts, compute `agent.sealed_hash = compute_sealed_hash(...)` and stamp it.

The freeze step also accepts already-frozen prompts: when `prompts.<stage>` already starts with `sha256:`, freeze is a no-op for that prompt (idempotent re-freeze per §3.1).

- [ ] **Step 1: Write the freeze tests**

`tests/unit/test_spec_freeze_prompts.py`:

```python
# ABOUTME: AC-3 — freeze_spec resolves prompt file paths to sha256: strings AND embeds
# ABOUTME: the prompt body under prompt_contents. The sealed_hash is also pinned.

from pathlib import Path
import hashlib

import pytest
import yaml

from razorback.agents.seal import prompt_sha256, compute_sealed_hash
from razorback.spec.freeze import freeze_spec
from razorback.spec.parse import parse_spec_text


def _spec_with_prompts(tmp_path: Path) -> str:
    p = tmp_path / "prompts"
    p.mkdir()
    (p / "model.md").write_text("MODEL PROMPT\n")
    (p / "analyze.md").write_text("ANALYZE PROMPT\n")
    (p / "verify.md").write_text("VERIFY PROMPT\n")
    return f"""\
version: 1
experiment: m4-freeze
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling: {{temperature: 0.0, seed: 42}}
  stages: [model, analyze, verify]
  tools_allowed: [Bash]
  prompts:
    model: {p / "model.md"}
    analyze: {p / "analyze.md"}
    verify: {p / "verify.md"}
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
trials: 1
"""


def test_freeze_resolves_prompt_paths_to_sha256(tmp_path):
    spec = parse_spec_text(_spec_with_prompts(tmp_path))
    frozen_text = freeze_spec(spec)
    frozen = yaml.safe_load(frozen_text)

    assert frozen["agent"]["prompts"]["model"] == prompt_sha256(b"MODEL PROMPT\n")
    assert frozen["agent"]["prompts"]["analyze"] == prompt_sha256(b"ANALYZE PROMPT\n")
    assert frozen["agent"]["prompts"]["verify"] == prompt_sha256(b"VERIFY PROMPT\n")


def test_freeze_embeds_prompt_contents(tmp_path):
    spec = parse_spec_text(_spec_with_prompts(tmp_path))
    frozen = yaml.safe_load(freeze_spec(spec))
    contents = frozen["agent"]["prompt_contents"]
    assert contents["model"] == "MODEL PROMPT\n"
    assert contents["analyze"] == "ANALYZE PROMPT\n"
    assert contents["verify"] == "VERIFY PROMPT\n"


def test_freeze_pins_sealed_hash(tmp_path):
    spec = parse_spec_text(_spec_with_prompts(tmp_path))
    frozen = yaml.safe_load(freeze_spec(spec))
    expected = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={
            "model": prompt_sha256(b"MODEL PROMPT\n"),
            "analyze": prompt_sha256(b"ANALYZE PROMPT\n"),
            "verify": prompt_sha256(b"VERIFY PROMPT\n"),
        },
    )
    assert frozen["agent"]["sealed_hash"] == expected


def test_freeze_is_idempotent_on_already_frozen_prompts(tmp_path):
    """§3.1: re-freezing produces identical output."""
    spec_text = _spec_with_prompts(tmp_path)
    once = freeze_spec(parse_spec_text(spec_text))
    twice = freeze_spec(parse_spec_text(once))
    assert once == twice
```

`tests/unit/test_spacedock_prompt_drift.py`:

```python
# ABOUTME: AC-3 — at run time, the agent re-hashes prompt_contents.<stage> and refuses
# ABOUTME: if the recomputed hash differs from the frozen prompts.<stage> sha256: string.

from pathlib import Path

import pytest

from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.agents.spacedock_solver import (
    SpacedockSolverAgent,
    SpacedockSolverAgentError,
)


def test_run_refuses_when_prompt_contents_hash_does_not_match_pinned_hash(tmp_path):
    """AC-3 verbatim: 'a unit test mutates a prompt file between freeze and run; the agent
    refuses with a hash-drift error citing the pinned hash in the frozen spec.'

    Setup: build an agent with prompts={'model': 'sha256:<HASH_FOR_BODY_A>', ...} and
    prompt_contents={'model': BODY_B, ...} where prompt_sha256(BODY_B) != HASH_FOR_BODY_A.
    Calling agent.verify_prompt_contents() raises with the pinned hash in the message.
    """
    body_a = b"MODEL PROMPT A\n"
    body_b = b"MODEL PROMPT B (TAMPERED)\n"
    pinned_a = prompt_sha256(body_a)
    pinned_analyze = prompt_sha256(b"ANALYZE\n")
    pinned_verify = prompt_sha256(b"VERIFY\n")

    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={"model": pinned_a, "analyze": pinned_analyze, "verify": pinned_verify},
    )

    agent = SpacedockSolverAgent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=[],
        prompts={"model": pinned_a, "analyze": pinned_analyze, "verify": pinned_verify},
        sealed_hash=sealed,
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-test"},
        prompt_contents={
            "model": body_b.decode("utf-8"),   # drifted
            "analyze": "ANALYZE\n",
            "verify": "VERIFY\n",
        },
        prior_frozen_spec_path=None,
    )
    with pytest.raises(SpacedockSolverAgentError) as exc:
        agent.verify_prompt_contents()
    msg = str(exc.value)
    assert pinned_a in msg  # the pinned hash is cited
    assert "model" in msg   # the drifted stage is named


def test_run_passes_when_prompt_contents_hash_matches(tmp_path):
    body = b"MODEL PROMPT\n"
    pinned = prompt_sha256(body)
    pinned_a = prompt_sha256(b"A\n")
    pinned_v = prompt_sha256(b"V\n")
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={"model": pinned, "analyze": pinned_a, "verify": pinned_v},
    )
    agent = SpacedockSolverAgent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=[],
        prompts={"model": pinned, "analyze": pinned_a, "verify": pinned_v},
        sealed_hash=sealed,
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-test"},
        prompt_contents={"model": "MODEL PROMPT\n", "analyze": "A\n", "verify": "V\n"},
        prior_frozen_spec_path=None,
    )
    agent.verify_prompt_contents()  # no raise
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_spec_freeze_prompts.py tests/unit/test_spacedock_prompt_drift.py -v
```

Expected: failures — `freeze_spec` does not resolve prompts; `SpacedockSolverAgent.__init__` does not accept `prompt_contents`; `verify_prompt_contents` does not exist.

- [ ] **Step 3: Extend `spec/freeze.py`**

Replace the body of `src/razorback/spec/freeze.py`:

```python
# ABOUTME: Spec freeze — content-hash prompt files into spec.frozen.yaml (§6.4).
# ABOUTME: sealed_hash is also pinned for spacedock-solver halt-resume (§6.2).

import hashlib
from pathlib import Path

import yaml

from razorback.agents.seal import prompt_sha256, compute_sealed_hash
from razorback.spec.schema import Spec, SpacedockSolverAgentBlock


def freeze_spec(spec: Spec) -> str:
    """Return the canonical YAML for a parsed spec, with prompts resolved + sealed_hash pinned."""
    payload = spec.model_dump(mode="json")

    if isinstance(spec.agent, SpacedockSolverAgentBlock):
        _freeze_spacedock_prompts(payload["agent"])
        payload["agent"]["sealed_hash"] = compute_sealed_hash(
            model=payload["agent"]["model"],
            sampling=payload["agent"]["sampling"],
            stages=payload["agent"]["stages"],
            prompt_hashes=payload["agent"]["prompts"],
        )

    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)


def _freeze_spacedock_prompts(agent_block: dict) -> None:
    """Replace prompts.<stage> file paths with sha256: strings; embed bodies into prompt_contents."""
    prompts = agent_block.get("prompts", {})
    contents: dict[str, str] = {}
    resolved: dict[str, str] = {}
    for stage, value in prompts.items():
        if value.startswith("sha256:"):
            # Already frozen — re-use the hash; the body must be present in prompt_contents.
            existing = agent_block.get("prompt_contents", {}).get(stage)
            if existing is None:
                raise ValueError(
                    f"agent.prompts.{stage} is pre-hashed but prompt_contents.{stage} is missing"
                )
            resolved[stage] = value
            contents[stage] = existing
            continue
        path = Path(value)
        if not path.is_absolute():
            # Resolve relative to project root (cwd) per §6.4. The translator/CLI passes
            # absolute paths; relative paths only appear in test fixtures.
            path = Path.cwd() / path
        body = path.read_bytes()
        resolved[stage] = prompt_sha256(body)
        contents[stage] = body.decode("utf-8")
    agent_block["prompts"] = resolved
    agent_block["prompt_contents"] = contents


def derive_job_name(frozen_text: str) -> str:
    return hashlib.sha256(frozen_text.encode("utf-8")).hexdigest()[:16]
```

Add `prompt_contents` to `SpacedockSolverAgentBlock` in `spec/schema.py`:

```python
class SpacedockSolverAgentBlock(BaseModel):
    ...
    prompt_contents: dict[str, str] | None = None  # populated by freeze; None in unfrozen specs
```

(The `extra="forbid"` setting at the top of the class is preserved; `prompt_contents` becomes a known optional field.)

- [ ] **Step 4: Extend `SpacedockSolverAgent`**

Add to `src/razorback/agents/spacedock_solver.py`:

```python
class SpacedockSolverAgent(BaseAgent):
    def __init__(
        self,
        ...,
        prompt_contents: dict[str, str] | None = None,
        ...
    ) -> None:
        ...
        self._prompt_contents = dict(prompt_contents) if prompt_contents else {}

    def verify_prompt_contents(self) -> None:
        """AC-3: re-hash each prompt body; refuse if it does not match the pinned sha256."""
        for stage, pinned in self._prompts.items():
            if not pinned.startswith("sha256:"):
                continue  # Unfrozen — nothing to compare.
            body = self._prompt_contents.get(stage)
            if body is None:
                raise SpacedockSolverAgentError(
                    f"prompt_contents.{stage} is missing; cannot verify against pinned {pinned}"
                )
            recomputed = prompt_sha256(body.encode("utf-8"))
            if recomputed != pinned:
                raise SpacedockSolverAgentError(
                    f"prompts.{stage} hash drift: pinned {pinned}, recomputed {recomputed}. "
                    "The frozen spec's prompt_contents has been tampered with after freeze."
                )
```

(Import `prompt_sha256` at the top of `spacedock_solver.py`.)

- [ ] **Step 5: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_spec_freeze_prompts.py tests/unit/test_spacedock_prompt_drift.py tests/unit/test_spacedock_seed_mismatch.py tests/unit/test_freeze.py -v
```

Expected: 4 new tests + 2 new tests + 4 from Task 1 + the existing M1 freeze tests pass. M1's freeze test exercises the no-spacedock-solver path; it stays green because `isinstance(spec.agent, SpacedockSolverAgentBlock)` is `False` for nop/claude-cli specs.

- [ ] **Step 6: Commit**

```bash
git add src/razorback/spec/freeze.py src/razorback/spec/schema.py src/razorback/agents/spacedock_solver.py tests/unit/test_spec_freeze_prompts.py tests/unit/test_spacedock_prompt_drift.py
git commit -m "m4: freeze prompts + run-time hash-drift refusal (AC-3)"
```

---

## Task 4: `setup()` — env scrub, MCP filter, `tools_allowed` enforcement (AC-6)

**Files:**
- Create: `src/razorback/agents/claude_invoke.py` (shared argv builder extracted from M3 `claude_cli.py`)
- Modify: `src/razorback/agents/claude_cli.py` (refactor `run()` to use `claude_invoke` — the only M3-surface change)
- Modify: `src/razorback/agents/spacedock_solver.py` (implement `setup()`)
- Create: `tests/unit/test_spacedock_tools_allowed.py`

§9.2 design wording (verbatim):

> Razorback's tool-allowlist (`agent.tools_allowed`) attaches to razorback's own agent shims (`ClaudeCliAgent`, `CodexCliAgent`, `SpacedockSolverAgent`). The enforcement runs at agent setup (env scrub, MCP server filtering) and post-run (audit against `events.jsonl`).

`run_experiment.py:1531-1549` (DISALLOWED_TOOLS discipline — verbatim):

```python
DISALLOWED_TOOLS = (
    "WebFetch", "WebSearch",
    "Bash(curl *)", "Bash(wget *)", "Bash(git clone *)",
    "Bash(huggingface-cli *)", "Bash(hf *)",
    "Bash(pip install datasets*)", "Bash(pip install huggingface*)",
    "Bash(pip install transformers*)", "Bash(pip install evaluate*)",
    "Bash(pip3 install datasets*)", "Bash(pip3 install huggingface*)",
    "Bash(pip3 install transformers*)", "Bash(pip3 install evaluate*)",
)
```

(Same constant lives in M3's `claude_cli.py` under `_DEFAULT_DISALLOWED_TOOLS`. M4 hoists it into `claude_invoke.py` so both agents share one definition.)

§9.2 AC-6 means: when `tools_allowed=["Bash", "Read"]`, the agent's `setup()` must:

1. **Filter MCP servers**: if `self.mcp_servers` carries entries whose declared tools intersect the disallowed set, drop them from `self.mcp_servers`. (For M4, "disallowed" is the complement of `tools_allowed`; if `tools_allowed` is non-empty, any MCP whose `name` is NOT in `tools_allowed` is dropped.)
2. **Scrub env**: build `self._exec_env = {**PROXY_BLOCK_ENV, **self._resolved_auth_env, "HOME": "/root"}`. NOT inherit `os.environ`.
3. Validate `claude --version` runs inside the container (proves the binary is present); raise if not.
4. Validate `git --version` runs inside the container (needed for `agent_freeze/.git` commits in Task 5); raise if not.

The M3 plan's Task 4 already implemented (1)+(2)+(3) for `ClaudeCliAgent.setup()`. M4 implements the same shape for `SpacedockSolverAgent.setup()`, adding (4). The MCP-filter logic is new to both agents (M3 left it implicit by saying "the agent's `mcp_servers` list is filtered" without specifying the rule).

- [ ] **Step 1: Write the failing test**

`tests/unit/test_spacedock_tools_allowed.py`:

```python
# ABOUTME: AC-6 — setup() filters MCP servers against tools_allowed and stamps the
# ABOUTME: DISALLOWED_TOOLS list. env carries proxy block + auth + HOME only.

from unittest.mock import AsyncMock, MagicMock

import pytest

from harbor.models.task.config import MCPServerConfig

from razorback.agents.spacedock_solver import SpacedockSolverAgent
from razorback.agents.claude_invoke import DISALLOWED_TOOLS


def _make_environment(version_rc=0, git_rc=0):
    env = MagicMock()

    async def fake_exec(cmd, **kw):
        rc = version_rc if cmd.startswith("claude --version") else (
            git_rc if cmd.startswith("git --version") else 0
        )
        return MagicMock(return_code=rc, stdout="ok", stderr="")
    env.exec = AsyncMock(side_effect=fake_exec)
    return env


def _agent(tmp_path, **overrides):
    base = dict(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=["Bash", "Read"],
        prompts={"model": "p1", "analyze": "p2", "verify": "p3"},  # unfrozen → no drift check
        sealed_hash="0" * 32,
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-test"},
        prior_frozen_spec_path=None,
    )
    base.update(overrides)
    return SpacedockSolverAgent(**base)


@pytest.mark.asyncio
async def test_setup_filters_mcp_servers_against_tools_allowed(tmp_path):
    # Two MCP servers: "Bash" is allowed; "WebFetch" is NOT in tools_allowed → dropped.
    mcp_bash = MCPServerConfig(name="Bash", command="echo bash")
    mcp_webfetch = MCPServerConfig(name="WebFetch", command="echo webfetch")
    agent = SpacedockSolverAgent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=["Bash", "Read"],
        prompts={"model": "p1", "analyze": "p2", "verify": "p3"},
        sealed_hash="0" * 32,
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-test"},
        prior_frozen_spec_path=None,
        mcp_servers=[mcp_bash, mcp_webfetch],
    )
    await agent.setup(_make_environment())
    remaining = [s.name for s in agent.mcp_servers]
    assert remaining == ["Bash"]
    assert "WebFetch" not in remaining


@pytest.mark.asyncio
async def test_setup_does_not_filter_when_tools_allowed_is_empty(tmp_path):
    """Empty tools_allowed list means 'no restriction' — all MCP servers stay."""
    mcp_bash = MCPServerConfig(name="Bash", command="echo bash")
    mcp_webfetch = MCPServerConfig(name="WebFetch", command="echo webfetch")
    agent = _agent(tmp_path, tools_allowed=[])
    agent.mcp_servers = [mcp_bash, mcp_webfetch]
    await agent.setup(_make_environment())
    assert {s.name for s in agent.mcp_servers} == {"Bash", "WebFetch"}


@pytest.mark.asyncio
async def test_setup_env_carries_only_proxy_auth_and_home(tmp_path):
    agent = _agent(tmp_path)
    await agent.setup(_make_environment())
    keys = set(agent._exec_env.keys())
    assert "ANTHROPIC_API_KEY" in keys
    assert "HTTP_PROXY" in keys
    assert "NO_PROXY" in keys
    assert "HF_HUB_OFFLINE" in keys
    assert "HOME" in keys
    # AC-6: NOT the operator's whole environment.
    assert "PATH" not in keys
    assert "USER" not in keys


@pytest.mark.asyncio
async def test_setup_refuses_without_git_binary(tmp_path):
    agent = _agent(tmp_path)
    with pytest.raises(Exception):
        await agent.setup(_make_environment(git_rc=127))


@pytest.mark.asyncio
async def test_setup_refuses_without_claude_binary(tmp_path):
    agent = _agent(tmp_path)
    with pytest.raises(Exception):
        await agent.setup(_make_environment(version_rc=127))


def test_disallowed_tools_list_matches_run_experiment(tmp_path):
    """Sanity: the constant is the verbatim list from run_experiment.py:1531-1549."""
    assert "WebFetch" in DISALLOWED_TOOLS
    assert "Bash(curl *)" in DISALLOWED_TOOLS
    assert "Bash(pip install datasets*)" in DISALLOWED_TOOLS
    assert "Bash(pip3 install evaluate*)" in DISALLOWED_TOOLS
```

- [ ] **Step 2: Run test, confirm red**

```bash
uv run pytest tests/unit/test_spacedock_tools_allowed.py -v
```

Expected: ImportError on `razorback.agents.claude_invoke`; NotImplementedError on `setup()`.

- [ ] **Step 3: Create `agents/claude_invoke.py`**

`src/razorback/agents/claude_invoke.py`:

```python
# ABOUTME: Shared `claude -p` argv builder + DISALLOWED_TOOLS list.
# ABOUTME: Used by ClaudeCliAgent (M3) and SpacedockSolverAgent (M4 per-stage runs).

import shlex


DEFAULT_ALLOWED_TOOLS = ("Bash", "Read", "Write", "Edit", "Glob", "Grep")

# Verbatim from run_experiment.py:1531-1549. Do NOT paraphrase.
DISALLOWED_TOOLS = (
    "WebFetch", "WebSearch",
    "Bash(curl *)", "Bash(wget *)", "Bash(git clone *)",
    "Bash(huggingface-cli *)", "Bash(hf *)",
    "Bash(pip install datasets*)", "Bash(pip install huggingface*)",
    "Bash(pip install transformers*)", "Bash(pip install evaluate*)",
    "Bash(pip3 install datasets*)", "Bash(pip3 install huggingface*)",
    "Bash(pip3 install transformers*)", "Bash(pip3 install evaluate*)",
)


def build_claude_argv(
    *,
    prompt: str,
    model: str | None,
    tools_allowed: list[str],
) -> str:
    """Return a shell-safe `claude -p <prompt> ...` command string for environment.exec.

    Tool allowlist:
      - If `tools_allowed` is non-empty, --allowedTools is the comma-joined list.
      - Otherwise, --allowedTools is the comma-joined DEFAULT_ALLOWED_TOOLS.
    --disallowedTools is the full DISALLOWED_TOOLS tuple, one --disallowedTools flag each.
    """
    allowed = list(tools_allowed) if tools_allowed else list(DEFAULT_ALLOWED_TOOLS)
    parts = [
        "claude", "-p", shlex.quote(prompt),
        "--allowedTools", ",".join(allowed),
    ]
    for d in DISALLOWED_TOOLS:
        parts.extend(["--disallowedTools", shlex.quote(d)])
    parts.extend(["--permission-mode", "bypassPermissions"])
    if model:
        parts.extend(["--model", model])
    return " ".join(parts)
```

- [ ] **Step 4: Refactor `claude_cli.py::run` to use `build_claude_argv`**

In `src/razorback/agents/claude_cli.py`, replace the in-place argv-building block in `run()` with:

```python
from razorback.agents.claude_invoke import build_claude_argv, DISALLOWED_TOOLS  # was _DEFAULT_DISALLOWED_TOOLS

async def run(self, instruction, environment, context) -> None:
    cmd = build_claude_argv(
        prompt=instruction,
        model=self.model_name,
        tools_allowed=self._tools_allowed,
    )
    result = await environment.exec(cmd, cwd="/work", env=self._exec_env, timeout_sec=600)
    context.return_code = result.return_code
```

Remove `_DEFAULT_ALLOWED_TOOLS` and `_DEFAULT_DISALLOWED_TOOLS` from `claude_cli.py` — they live in `claude_invoke.py` now. The M3 test suite stays green because `build_claude_argv` produces the same argv shape M3's inline code produced.

- [ ] **Step 5: Implement `SpacedockSolverAgent.setup()`**

In `src/razorback/agents/spacedock_solver.py`:

```python
from razorback.agents.proxy import PROXY_BLOCK_ENV


class SpacedockSolverAgent(BaseAgent):
    async def setup(self, environment: BaseEnvironment) -> None:
        """AC-6: filter MCP servers; build exec env; validate claude + git binaries."""
        # 1) Filter MCP servers against tools_allowed (empty list = no filter).
        if self._tools_allowed:
            allowed = set(self._tools_allowed)
            self.mcp_servers = [s for s in (self.mcp_servers or []) if s.name in allowed]

        # 2) Build the exec env — proxy block + auth + HOME ONLY. No os.environ.
        self._exec_env = {
            **PROXY_BLOCK_ENV,
            **self._resolved_auth_env,
            "HOME": "/root",
        }

        # 3) Validate claude binary inside the container.
        version = await environment.exec("claude --version")
        if version.return_code != 0:
            raise SpacedockSolverAgentError(
                f"claude CLI not available inside container (exit={version.return_code}, "
                f"stderr={getattr(version, 'stderr', '')!r})"
            )

        # 4) Validate git binary inside the container — needed for agent_freeze/.git commits.
        git_v = await environment.exec("git --version")
        if git_v.return_code != 0:
            raise SpacedockSolverAgentError(
                f"git not available inside container (exit={git_v.return_code}). "
                "Task 5's freeze-on-stage-boundary requires `git`."
            )

        # 5) AC-3: verify prompt_contents hashes match pinned sha256 strings.
        self.verify_prompt_contents()
```

(Import `BaseEnvironment` at the top of `spacedock_solver.py`.)

- [ ] **Step 6: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_spacedock_tools_allowed.py tests/unit/test_claude_cli_setup_env_scrub.py tests/unit/test_claude_cli_version.py -v
```

Expected: 6 new tests + M3's claude_cli setup/version tests still green (the refactor to `claude_invoke` is behavior-preserving).

- [ ] **Step 7: Commit**

```bash
git add src/razorback/agents/claude_invoke.py src/razorback/agents/claude_cli.py src/razorback/agents/spacedock_solver.py tests/unit/test_spacedock_tools_allowed.py
git commit -m "m4: claude_invoke helper + spacedock setup() with tools_allowed (AC-6)"
```

---

## Task 5: `run()` — staged execution + `agent_freeze/.git` commits per stage (AC-4)

**Files:**
- Modify: `src/razorback/agents/spacedock_solver.py` (implement `run()`)
- Create: `tests/integration/test_spacedock_git_freeze.py`

The `run()` shape:

```python
async def run(self, instruction: str, environment, context):
    freeze_dir = self.logs_dir / "agent_freeze"
    await self._init_agent_freeze_repo(environment, freeze_dir)
    for stage in self._stages:
        prompt = self._prompt_contents[stage]
        rendered = self._render_stage_prompt(stage, prompt, instruction)
        cmd = build_claude_argv(prompt=rendered, model=self._model, tools_allowed=self._tools_allowed)
        stats_before = await self._collect_stage_metering(environment)
        result = await environment.exec(cmd, cwd="/work", env=self._exec_env, timeout_sec=600)
        stats_after = await self._collect_stage_metering(environment)
        await self._commit_stage_to_agent_freeze(environment, freeze_dir, stage)
        self._record_phase_stats(stage, stats_before, stats_after, result)
        if result.return_code != 0:
            context.return_code = result.return_code
            await self._write_phase_stats_file(environment, freeze_dir)
            return
    context.return_code = 0
    await self._write_phase_stats_file(environment, freeze_dir)
```

The `_init_agent_freeze_repo` runs `git init`, `git config user.email/name` (dummy values — no signing), `git add -A`, `git commit --allow-empty -m "seed"` inside the freeze dir. `_commit_stage_to_agent_freeze` runs `git -C <freeze_dir> add -A && git -C <freeze_dir> commit --allow-empty -m "stage: <name>"`. The "workspace capture" is the `freeze_dir`'s working tree at each stage boundary — which is just whatever the agent writes there during the stage. For DAB the agent writes its scratch files (notes, intermediate computations) into `/work` (harbor's workspace) and the *artifacts it considers part of the seal* into the freeze dir. M4 keeps the freeze-dir population minimal: the agent writes one `stage-<name>.log` file with the stage's stdout+stderr; `git add -A` snapshots that.

§9.3 design wording (verbatim):

> **Workspace capture in halt-resume is partial.** `SpacedockSolverAgent` commits the agent's directory, not the harbor-provided workspace tree or external state (docker containers, DB processes). For DAB's read-only datasets this is sufficient; for stateful benchmarks resumed via this agent, the workflow must rebuild external state.

M4 follows this discipline: the agent_freeze repo captures `logs_dir/agent_freeze/` ONLY. The `/work` tree is NOT in the repo. Resume reconstructs state from the freeze repo's HEAD; for DAB this is sufficient because the dataset is re-bind-mounted on resume.

§6.3 contract (verbatim):

> `logs_dir/` is harbor's stable per-trial surface; razorback writes the `agent_freeze/` subtree there and never inside harbor's `agent/` directory.

This means: the agent writes ONLY to `self.logs_dir / "agent_freeze"`. It MUST NOT write to `self.logs_dir.parent / "agent"` (harbor's tree). AC-7 is a separate audit on this.

- [ ] **Step 1: Write the failing integration test**

`tests/integration/test_spacedock_git_freeze.py`:

```python
# ABOUTME: AC-4 — agent_freeze/.git is a real git repo with one commit per stage boundary.
# ABOUTME: Integration-scoped: uses a fake BaseEnvironment that pipes exec through subprocess.

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from razorback.agents.spacedock_solver import SpacedockSolverAgent
from razorback.agents.seal import prompt_sha256, compute_sealed_hash


class _LocalShellEnvironment:
    """Minimal BaseEnvironment-shaped fake — pipes exec through subprocess on the host.

    Sufficient for AC-4's `git --version`, `git init`, `git add`, `git commit`,
    `claude --version`, and the staged `claude -p` calls (which we stub via a
    --version-only fake claude script on PATH).
    """

    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.default_user = None

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        actual_cwd = cwd or str(self.workdir)
        proc = subprocess.run(
            command, shell=True, cwd=actual_cwd,
            env={**os.environ, **(env or {})},
            capture_output=True, text=True, timeout=timeout_sec or 60,
        )
        result = MagicMock()
        result.return_code = proc.returncode
        result.stdout = proc.stdout
        result.stderr = proc.stderr
        return result


def _stub_claude_on_path(tmp_path: Path) -> Path:
    """Write a fake `claude` script that succeeds on --version and writes a stage log on -p."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "claude"
    stub.write_text(
        "#!/bin/bash\n"
        "if [ \"$1\" = \"--version\" ]; then echo '0.0.0-stub'; exit 0; fi\n"
        "echo \"stub claude ran with args: $@\" >> stage.log\n"
        "exit 0\n"
    )
    stub.chmod(0o755)
    return bin_dir


@pytest.mark.timeout(60)
def test_run_creates_agent_freeze_git_repo_with_stage_commits(tmp_path, monkeypatch):
    """AC-4: agent_freeze/.git is a valid repo; HEAD has 4 commits (seed + 3 stages)."""
    bin_dir = _stub_claude_on_path(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    body_m = b"MODEL PROMPT\n"
    body_a = b"ANALYZE PROMPT\n"
    body_v = b"VERIFY PROMPT\n"
    prompts = {
        "model": prompt_sha256(body_m),
        "analyze": prompt_sha256(body_a),
        "verify": prompt_sha256(body_v),
    }
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes=prompts,
    )
    agent = SpacedockSolverAgent(
        logs_dir=logs_dir,
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=["Bash"],
        prompts=prompts,
        sealed_hash=sealed,
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-test"},
        prompt_contents={"model": body_m.decode(), "analyze": body_a.decode(), "verify": body_v.decode()},
        prior_frozen_spec_path=None,
    )

    env = _LocalShellEnvironment(work_dir)
    context = MagicMock()
    asyncio.run(agent.setup(env))
    asyncio.run(agent.run("solve the bookreview query", env, context))

    freeze_dir = logs_dir / "agent_freeze"
    # AC-4: .git is a real repo.
    git_dir = freeze_dir / ".git"
    assert git_dir.exists()
    rev = subprocess.run(
        ["git", "-C", str(freeze_dir), "rev-parse", "--git-dir"],
        capture_output=True, text=True,
    )
    assert rev.returncode == 0, rev.stderr
    assert rev.stdout.strip().endswith(".git")

    # HEAD has a chain of commits — at least 4 (seed + model + analyze + verify).
    log = subprocess.run(
        ["git", "-C", str(freeze_dir), "log", "--format=%s"],
        capture_output=True, text=True,
    )
    assert log.returncode == 0
    subjects = [s for s in log.stdout.strip().split("\n") if s]
    assert any("stage: model" in s for s in subjects)
    assert any("stage: analyze" in s for s in subjects)
    assert any("stage: verify" in s for s in subjects)


@pytest.mark.timeout(60)
def test_run_never_writes_inside_harbor_agent_dir(tmp_path, monkeypatch):
    """AC-7 (positive): every razorback write lands under logs_dir/agent_freeze/."""
    bin_dir = _stub_claude_on_path(tmp_path)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    # Set up a fake "harbor agent dir" alongside logs_dir; the agent must NOT touch it.
    trial_root = tmp_path / "trial"
    (trial_root / "agent").mkdir(parents=True)  # harbor's surface
    (trial_root / "logs_dir").mkdir()           # razorback's surface
    work_dir = tmp_path / "work"; work_dir.mkdir()

    body = b"P\n"
    prompts = {k: prompt_sha256(body) for k in ("model", "analyze", "verify")}
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"], prompt_hashes=prompts,
    )
    agent = SpacedockSolverAgent(
        logs_dir=trial_root / "logs_dir",
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"], tools_allowed=[],
        prompts=prompts, sealed_hash=sealed,
        resolved_auth_env={"ANTHROPIC_API_KEY": "sk-test"},
        prompt_contents={k: body.decode() for k in prompts},
        prior_frozen_spec_path=None,
    )
    env = _LocalShellEnvironment(work_dir)
    context = MagicMock()
    asyncio.run(agent.setup(env))
    asyncio.run(agent.run("solve", env, context))

    # harbor's agent/ tree is untouched.
    assert list((trial_root / "agent").iterdir()) == []
    # razorback's agent_freeze tree is populated.
    assert (trial_root / "logs_dir" / "agent_freeze" / ".git").exists()
```

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/integration/test_spacedock_git_freeze.py -v
```

Expected: failures — `run()` is `NotImplementedError`.

- [ ] **Step 3: Implement `run()` and the freeze helpers**

In `src/razorback/agents/spacedock_solver.py`:

```python
import json
import time
from pathlib import Path

from razorback.agents.claude_invoke import build_claude_argv


class SpacedockSolverAgent(BaseAgent):
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context,
    ) -> None:
        freeze_dir = Path(self.logs_dir) / "agent_freeze"
        freeze_dir.mkdir(parents=True, exist_ok=True)
        await self._init_agent_freeze_repo(environment, freeze_dir)

        self._phase_stats: dict[str, dict] = {}
        for stage in self._stages:
            prompt_body = self._prompt_contents[stage]
            rendered = self._render_stage_prompt(stage, prompt_body, instruction)
            cmd = build_claude_argv(
                prompt=rendered, model=self._model, tools_allowed=self._tools_allowed,
            )
            t0 = time.monotonic()
            result = await environment.exec(
                cmd, cwd=str(freeze_dir), env=self._exec_env, timeout_sec=600,
            )
            wallclock = time.monotonic() - t0
            await self._commit_stage(environment, freeze_dir, stage)
            self._phase_stats[stage] = {
                "tokens_in": 0,   # M4: stub fields; M5 wires real token cost from events.jsonl.
                "tokens_out": 0,
                "cost_usd": 0.0,
                "wallclock_s": round(wallclock, 3),
            }
            if result.return_code != 0:
                context.return_code = result.return_code
                self._write_phase_stats_file(freeze_dir)
                return

        context.return_code = 0
        self._write_phase_stats_file(freeze_dir)

    async def _init_agent_freeze_repo(self, environment, freeze_dir: Path) -> None:
        """Initialize the agent_freeze/.git repo and make the seed commit."""
        cmds = [
            f"git -C {freeze_dir} init -q",
            f"git -C {freeze_dir} config user.email razorback@local",
            f"git -C {freeze_dir} config user.name razorback",
            f"git -C {freeze_dir} config commit.gpgsign false",
            f"git -C {freeze_dir} add -A",
            f"git -C {freeze_dir} commit -q --allow-empty -m seed",
        ]
        for c in cmds:
            r = await environment.exec(c)
            if r.return_code != 0:
                raise SpacedockSolverAgentError(
                    f"agent_freeze repo init failed at: {c}\nstderr={getattr(r, 'stderr', '')!r}"
                )

    async def _commit_stage(self, environment, freeze_dir: Path, stage: str) -> None:
        cmds = [
            f"git -C {freeze_dir} add -A",
            f"git -C {freeze_dir} commit -q --allow-empty -m 'stage: {stage}'",
        ]
        for c in cmds:
            r = await environment.exec(c)
            if r.return_code != 0:
                raise SpacedockSolverAgentError(
                    f"agent_freeze stage commit failed at: {c}"
                )

    def _render_stage_prompt(self, stage: str, body: str, instruction: str) -> str:
        return f"# Stage: {stage}\n\n{body}\n\n# Task instruction:\n{instruction}\n"

    def _write_phase_stats_file(self, freeze_dir: Path) -> None:
        """Write the §6.8 phase_stats.json. Public contract — DO NOT add unscoped fields."""
        # AC-5: every stage has the exact 4 fields; missing stages get all-zero placeholders.
        out = {}
        for stage in self._stages:
            s = self._phase_stats.get(stage, {})
            out[stage] = {
                "tokens_in": s.get("tokens_in", 0),
                "tokens_out": s.get("tokens_out", 0),
                "cost_usd": s.get("cost_usd", 0.0),
                "wallclock_s": s.get("wallclock_s", 0.0),
            }
        (freeze_dir / "phase_stats.json").write_text(json.dumps(out, indent=2) + "\n")
```

(The token/cost numbers are stub 0s in M4. The §6.8 schema fixes the shape; M5's aggregator picks up real numbers from `events.jsonl`. M4's job is the **shape contract**, not the dollar accounting.)

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/integration/test_spacedock_git_freeze.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/agents/spacedock_solver.py tests/integration/test_spacedock_git_freeze.py
git commit -m "m4: staged run() with agent_freeze/.git commits per stage (AC-4)"
```

---

## Task 6: `phase_stats.json` schema (AC-5)

**Files:**
- Create: `tests/unit/test_spacedock_phase_stats.py`

§6.8 design wording (verbatim — the schema is fixed):

```json
{
  "model":   {"tokens_in": ..., "tokens_out": ..., "cost_usd": ..., "wallclock_s": ...},
  "analyze": {"tokens_in": ..., "tokens_out": ..., "cost_usd": ..., "wallclock_s": ...},
  "verify":  {"tokens_in": ..., "tokens_out": ..., "cost_usd": ..., "wallclock_s": ...}
}
```

Task 5 already writes the file. Task 6 ADDS a tight schema test that inspects a fixture run-dir and asserts every key is present with the right type. The M5 aggregator will read this exact shape.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_spacedock_phase_stats.py`:

```python
# ABOUTME: AC-5 — phase_stats.json has the §6.8 schema exactly.

import json
from pathlib import Path

import pytest


_REQUIRED_STAGES = ("model", "analyze", "verify")
_REQUIRED_KEYS_PER_STAGE = ("tokens_in", "tokens_out", "cost_usd", "wallclock_s")


def test_phase_stats_schema(tmp_path):
    """The schema asserter; called against a fixture below and against integration runs."""
    fixture = tmp_path / "phase_stats.json"
    fixture.write_text(json.dumps({
        "model":   {"tokens_in": 100, "tokens_out": 50, "cost_usd": 0.001, "wallclock_s": 2.0},
        "analyze": {"tokens_in":  80, "tokens_out": 40, "cost_usd": 0.0008, "wallclock_s": 1.5},
        "verify":  {"tokens_in":  60, "tokens_out": 30, "cost_usd": 0.0006, "wallclock_s": 1.0},
    }))
    _assert_phase_stats_schema(fixture)


def test_phase_stats_rejects_missing_stage(tmp_path):
    fixture = tmp_path / "phase_stats.json"
    fixture.write_text(json.dumps({
        "model":   {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "wallclock_s": 0.0},
        "analyze": {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "wallclock_s": 0.0},
        # 'verify' missing
    }))
    with pytest.raises(AssertionError):
        _assert_phase_stats_schema(fixture)


def test_phase_stats_rejects_missing_key(tmp_path):
    fixture = tmp_path / "phase_stats.json"
    fixture.write_text(json.dumps({
        "model":   {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0},  # no wallclock_s
        "analyze": {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "wallclock_s": 0.0},
        "verify":  {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "wallclock_s": 0.0},
    }))
    with pytest.raises(AssertionError):
        _assert_phase_stats_schema(fixture)


def _assert_phase_stats_schema(path: Path) -> None:
    data = json.loads(path.read_text())
    assert isinstance(data, dict)
    for stage in _REQUIRED_STAGES:
        assert stage in data, f"missing stage: {stage}"
        for k in _REQUIRED_KEYS_PER_STAGE:
            assert k in data[stage], f"missing key {k!r} in stage {stage!r}"
        assert isinstance(data[stage]["tokens_in"], int)
        assert isinstance(data[stage]["tokens_out"], int)
        assert isinstance(data[stage]["cost_usd"], (int, float))
        assert isinstance(data[stage]["wallclock_s"], (int, float))


def test_phase_stats_schema_helper_is_importable_from_aggregator():
    """The M5 aggregator imports this helper. Lock the import path now.

    The helper lives in razorback.agents.spacedock_solver as a module-level callable so
    other code (M5's aggregator) can re-use the schema without duplicating it.
    """
    from razorback.agents.spacedock_solver import assert_phase_stats_schema
    assert callable(assert_phase_stats_schema)
```

(Move `_assert_phase_stats_schema` into `src/razorback/agents/spacedock_solver.py` as a public `assert_phase_stats_schema` function so M5's aggregator imports the canonical schema check.)

- [ ] **Step 2: Run tests, confirm red**

```bash
uv run pytest tests/unit/test_spacedock_phase_stats.py -v
```

Expected: ImportError on `razorback.agents.spacedock_solver.assert_phase_stats_schema`.

- [ ] **Step 3: Add `assert_phase_stats_schema` to `spacedock_solver.py`**

```python
def assert_phase_stats_schema(path: Path) -> None:
    """Public schema check for §6.8 phase_stats.json. M5's aggregator imports this."""
    data = json.loads(Path(path).read_text())
    assert isinstance(data, dict)
    for stage in ("model", "analyze", "verify"):
        assert stage in data, f"missing stage: {stage}"
        for k in ("tokens_in", "tokens_out", "cost_usd", "wallclock_s"):
            assert k in data[stage], f"missing key {k!r} in stage {stage!r}"
        assert isinstance(data[stage]["tokens_in"], int)
        assert isinstance(data[stage]["tokens_out"], int)
        assert isinstance(data[stage]["cost_usd"], (int, float))
        assert isinstance(data[stage]["wallclock_s"], (int, float))
```

Refactor the test's `_assert_phase_stats_schema` to call this helper.

- [ ] **Step 4: Run tests, confirm green**

```bash
uv run pytest tests/unit/test_spacedock_phase_stats.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/agents/spacedock_solver.py tests/unit/test_spacedock_phase_stats.py
git commit -m "m4: phase_stats.json schema + assert_phase_stats_schema helper (AC-5)"
```

---

## Task 7: AC-7 audit — razorback never writes into harbor's `agent/`

**Files:**
- Create: `tests/unit/test_spacedock_no_agent_dir_writes.py`

§6.3 design wording (verbatim):

> `logs_dir/` is harbor's stable per-trial surface; razorback writes the `agent_freeze/` subtree there and never inside harbor's `agent/` directory.

This AC has TWO checks:

1. **Static grep gate**: `grep -rn 'agent_dir' src/razorback/agents/` returns no matches (the path component should never appear in razorback source — razorback owns `logs_dir/agent_freeze/`, not anything under `agent/`).
2. **Integration check**: an integration test that runs the agent through a fixture and asserts the harbor-style `trial_root/agent/` tree is empty after the run (already covered as the second case in Task 5's integration test — keep it; Task 7 adds the static grep gate).

- [ ] **Step 1: Write the failing static grep test**

`tests/unit/test_spacedock_no_agent_dir_writes.py`:

```python
# ABOUTME: AC-7 — razorback source never references harbor's `agent/` directory for writes.
# ABOUTME: All razorback-owned state lives under logs_dir/agent_freeze/.

import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def test_no_agent_dir_writes_in_razorback_agents():
    """Static grep: `agent_dir` is not referenced anywhere under src/razorback/agents/.

    The agent must write under `self.logs_dir / "agent_freeze" / …`, never under
    a harbor-managed `agent/` directory. This grep is the AC-7 wire-level check;
    Task 5's `test_run_never_writes_inside_harbor_agent_dir` is the runtime check.
    """
    result = subprocess.run(
        ["grep", "-rn", "agent_dir", str(REPO / "src" / "razorback" / "agents")],
        capture_output=True, text=True,
    )
    # grep returns 1 with no output when no matches found (the desired outcome).
    assert result.returncode == 1, (
        f"`agent_dir` should not appear under src/razorback/agents/. "
        f"grep output:\n{result.stdout}"
    )
    assert result.stdout == ""


def test_agent_freeze_is_the_only_razorback_subtree_name():
    """Positive twin: `agent_freeze` IS referenced (Task 5 writes there)."""
    result = subprocess.run(
        ["grep", "-rln", "agent_freeze", str(REPO / "src" / "razorback" / "agents")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "spacedock_solver.py" in result.stdout
```

- [ ] **Step 2: Run test, confirm green (assuming Tasks 1–6 followed the rule)**

```bash
uv run pytest tests/unit/test_spacedock_no_agent_dir_writes.py -v
```

Expected: green. If red — the implementation in earlier tasks used the wrong path component. Fix the implementation, NOT the test.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_spacedock_no_agent_dir_writes.py
git commit -m "m4: AC-7 static gate — no agent_dir references under razorback/agents/"
```

---

## Task 8: Translator wiring + acceptance specs + end-to-end integration

**Files:**
- Modify: `src/razorback/compat/harbor_0_6_6.py` (extend `_build_agent_config` with the spacedock-solver branch)
- Create: `examples/specs/prompts/spacedock-model.md`
- Create: `examples/specs/prompts/spacedock-analyze.md`
- Create: `examples/specs/prompts/spacedock-verify.md`
- Create: `examples/specs/bookreview-spacedock-seed.yaml`
- Create: `examples/specs/bookreview-spacedock-resume.yaml`
- Create: `tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py`

### 8.1 — Translator branch

In `src/razorback/compat/harbor_0_6_6.py::_build_agent_config`, add the spacedock-solver branch:

```python
def _build_agent_config(
    spec, *, project_root, home, prior_frozen_spec_path,
) -> tuple[AgentConfig, dict[str, str]]:
    ...
    if isinstance(spec.agent, SpacedockSolverAgentBlock):
        if project_root is None:
            raise SpecError("spacedock-solver agent requires project_root for .env auth discovery.")
        if spec.agent.sealed_hash is None:
            raise SpecError(
                "spacedock-solver spec must be frozen (agent.sealed_hash missing). "
                "Run `rk spec freeze <spec>` first."
            )
        if spec.agent.prompt_contents is None:
            raise SpecError(
                "spacedock-solver spec must be frozen (agent.prompt_contents missing)."
            )
        resolution = resolve_claude_auth(project_root=project_root, home=home)
        kwargs = {
            "model": spec.agent.model,
            "sampling": {
                "temperature": spec.agent.sampling.temperature,
                "top_p": spec.agent.sampling.top_p,
                "seed": spec.agent.sampling.seed,
            },
            "stages": list(spec.agent.stages),
            "tools_allowed": list(spec.agent.tools_allowed),
            "prompts": dict(spec.agent.prompts),
            "prompt_contents": dict(spec.agent.prompt_contents),
            "sealed_hash": spec.agent.sealed_hash,
            "resolved_auth_env": dict(resolution.env),
            "prior_frozen_spec_path": (
                str(prior_frozen_spec_path) if prior_frozen_spec_path else None
            ),
        }
        agent_cfg = AgentConfig(
            import_path="razorback.agents.spacedock_solver:SpacedockSolverAgent",
            model_name=spec.agent.model,
            kwargs=kwargs,
            env=dict(resolution.env),
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env
    ...
```

### 8.2 — Acceptance prompts and specs

`examples/specs/prompts/spacedock-model.md`:

```
You are the MODEL stage of the spacedock solver. Read the dataset metadata
under /work and propose a first-draft answer. Write the draft to /work/answers.json.
```

`examples/specs/prompts/spacedock-analyze.md`:

```
You are the ANALYZE stage. Read /work/answers.json (the model stage's draft)
and critique it against the dataset's db_description.txt. Note any obvious errors.
```

`examples/specs/prompts/spacedock-verify.md`:

```
You are the VERIFY stage. Re-check the final /work/answers.json against the
query. If the answer is wrong, correct it. Write the final answer to /work/answers.json.
```

`examples/specs/bookreview-spacedock-seed.yaml`:

```yaml
version: 1
experiment: m4-bookreview-spacedock
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
    seed: 42
  stages: [model, analyze, verify]
  tools_allowed: [Bash, Read, Write, Edit, Glob, Grep]
  prompts:
    model: ./examples/specs/prompts/spacedock-model.md
    analyze: ./examples/specs/prompts/spacedock-analyze.md
    verify: ./examples/specs/prompts/spacedock-verify.md
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
trials: 1
observers:
  - kind: jsonl
    path: events.jsonl
  - kind: stdout
```

`examples/specs/bookreview-spacedock-resume.yaml`:

Identical to the seed spec — its purpose is to exercise the resume path against a matching frozen spec. (The integration test freezes the seed, runs it, then re-freezes the resume — which is byte-equal to the seed — and re-runs against the same `(jobs_dir, job_name)`.)

### 8.3 — Integration test

`tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py`:

```python
# ABOUTME: M4 end-to-end — seed run materializes agent_freeze/.git + phase_stats.json,
# ABOUTME: resume re-uses the same (jobs_dir, job_name) lock and passes the sealed_hash check.

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[2]
SEED_SPEC = REPO / "examples" / "specs" / "bookreview-spacedock-seed.yaml"
DAB_DATA = Path("/Users/clkao/git/dataagentbench/data/query_bookreview")
HAS_AUTH = bool(
    dotenv_values(REPO / ".env").get("ANTHROPIC_API_KEY")
    or (Path.home() / ".claude" / "benchmark-token").exists()
)


@pytest.mark.skipif(
    not DAB_DATA.exists() or shutil.which("claude") is None or not HAS_AUTH,
    reason="end-to-end needs bookreview dataset, host `claude` CLI, and an auth token",
)
@pytest.mark.timeout(1800)
def test_seed_run_then_resume_run_against_matching_sealed_hash(tmp_path):
    runs_root = tmp_path / "_runs"

    # 1) Freeze the seed spec.
    seed_frozen = tmp_path / "seed.frozen.yaml"
    freeze = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "spec", "freeze", str(SEED_SPEC),
         "--output", str(seed_frozen)],
        cwd=REPO, env={**os.environ}, capture_output=True, text=True, timeout=60,
    )
    assert freeze.returncode == 0, freeze.stderr

    # 2) Seed run.
    seed_run = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(seed_frozen),
         "--runs-dir", str(runs_root)],
        cwd=REPO, env={**os.environ}, capture_output=True, text=True, timeout=1500,
    )
    assert seed_run.returncode == 0, seed_run.stderr

    experiment_dir = runs_root / "m4-bookreview-spacedock"
    [run_dir] = list(experiment_dir.iterdir())
    # AC-4: agent_freeze/.git is a real repo (in at least one trial's logs_dir).
    [trial_dir] = list((run_dir / "trials").iterdir()) if (run_dir / "trials").exists() else [run_dir]
    # The actual trial dir layout depends on harbor's per-trial subdir naming;
    # the test searches under run_dir for the first agent_freeze it finds:
    agent_freeze_dirs = list(run_dir.rglob("agent_freeze"))
    assert agent_freeze_dirs, "no agent_freeze/ subtree found under the seed run-dir"
    for d in agent_freeze_dirs:
        assert (d / ".git").exists(), f"{d}/.git missing"
        # AC-5: phase_stats.json present and schema-valid.
        from razorback.agents.spacedock_solver import assert_phase_stats_schema
        assert_phase_stats_schema(d / "phase_stats.json")

    # 3) Resume run — re-use seed_frozen against the SAME runs_root.
    resume_run = subprocess.run(
        [sys.executable, "-m", "razorback.cli", "run", str(seed_frozen),
         "--runs-dir", str(runs_root)],
        cwd=REPO, env={**os.environ}, capture_output=True, text=True, timeout=1500,
    )
    # The resume MUST NOT exit with code 20 (matching sealed_hash → no SeedMismatchError).
    assert resume_run.returncode != 20, (
        f"resume against matching sealed_hash raised SeedMismatchError; should not.\n"
        f"stderr={resume_run.stderr}"
    )
```

(`rk spec freeze` is not yet implemented as a CLI subcommand in M1; M5 lands the full freeze command. For M4 the test invokes a small helper: `python -c "from razorback.spec.parse import parse_spec_file; from razorback.spec.freeze import freeze_spec; print(freeze_spec(parse_spec_file('<spec>')))" > seed.frozen.yaml`. If `rk spec freeze` is not on the CLI surface by M4 implementation time, the test falls back to the helper. The plan documents both invocations; the implementation worker chooses based on what's wired.)

- [ ] **Step 1: Author the prompts and specs**

(Above.)

- [ ] **Step 2: Smoke-parse the seed spec**

```bash
uv run python -c "from razorback.spec.parse import parse_spec_file; print(parse_spec_file('examples/specs/bookreview-spacedock-seed.yaml'))"
```

Expected: prints a `Spec(...)` with a `SpacedockSolverAgentBlock`.

- [ ] **Step 3: Run integration test**

```bash
uv run pytest tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py -v -s --timeout=1800
```

Expected: PASS. Cost estimate: ~$0.20–0.50 (three queries × three stages × claude calls; the verify stage is short). Wallclock: 10–25 minutes.

**Failure-triage rules:**
- Seed run returncode != 0 — check `events.jsonl` for harbor exceptions; check that `claude --version` and `git --version` both succeed inside the docker image (the M3 plan's Task 0 Step 1 covers the claude binary; M4 adds `git` to the same image).
- Resume returncode == 20 — the freeze step is not deterministic for the same spec text. Re-check `freeze_spec` idempotency (Task 3 Step 1 test covered this).
- `agent_freeze/.git` missing — Task 5's `_init_agent_freeze_repo` failed silently; rerun with `--log-cli-level=DEBUG` to see the git output.
- `phase_stats.json` missing — Task 5's `_write_phase_stats_file` was never called; check `run()` exit path.

- [ ] **Step 4: Commit**

```bash
git add src/razorback/compat/harbor_0_6_6.py examples/specs/prompts/ examples/specs/bookreview-spacedock-seed.yaml examples/specs/bookreview-spacedock-resume.yaml tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py
git commit -m "m4: translator + acceptance specs + halt-resume integration test"
```

---

## Task 9: Final acceptance — full suite + the §8.M4 commands

**Files:** none.

- [ ] **Step 1: Full unit suite**

```bash
uv run pytest tests/unit -v
```

Expected: every M1, M2, M3, and M4 unit test green. Pristine output.

- [ ] **Step 2: Full integration suite**

```bash
uv run pytest tests/integration -v -s --timeout=1800
```

Expected: M3's claude-bookreview test + M4's halt-resume test both green.

- [ ] **Step 3: §8.M4 acceptance commands**

```bash
uv run rk run examples/specs/bookreview-spacedock-seed.yaml
uv run rk run examples/specs/bookreview-spacedock-resume.yaml
```

(Or, if `rk spec freeze` is not yet wired, freeze inline via `parse_spec_file + freeze_spec` and run the frozen text.)

Expected:
- Both invocations exit code 0.
- The seed produces `agent_freeze/.git` and a schema-valid `phase_stats.json`.
- The resume against the matching sealed_hash does NOT exit code 20.

- [ ] **Step 4: AC-1 mismatch demonstration**

Hand-build a `bookreview-spacedock-resume-mismatch.yaml` whose `prompts.model` points to a different file. Freeze it. Run against the seed's runs-dir. Expected exit code 20.

```bash
uv run rk run /tmp/bookreview-spacedock-resume-mismatch.frozen.yaml --runs-dir _runs
echo $?  # → 20
```

- [ ] **Step 5: No commit (acceptance run only).**

---

## Task 10: Cross-reference plan from the M4 entity body

**Files:**
- Modify: `docs/razorback-implementation/m4-spacedock-solver-halt-resume.md` — Test plan section only

- [ ] **Step 1: Append one line under the Test plan section**

```
- **Implementation plan:** `docs/razorback-implementation/plans/m4-spacedock-solver-halt-resume.md`.
```

Do not change the frontmatter; do not rewrite the Test plan; do not paraphrase existing bullets.

- [ ] **Step 2: Commit**

```bash
git add docs/razorback-implementation/m4-spacedock-solver-halt-resume.md
git commit -m "m4: cross-reference implementation plan from entity Test plan"
```

---

## Self-review notes

- **AC coverage (1:1 with the AC↔task map at the top):**
  - AC-1 → Task 1 (riskiest contract — in-process refusal + CLI exit code 20).
  - AC-2 → Task 2 (registry + schema validator; SpecError before harbor).
  - AC-3 → Task 3 (freeze pins sha256+contents; agent verifies at setup time).
  - AC-4 → Task 5 (`agent_freeze/.git` repo + per-stage commits).
  - AC-5 → Task 5 writes the file; Task 6 locks the schema.
  - AC-6 → Task 4 (setup() filters MCP servers + scrubs env).
  - AC-7 → Task 7 (static grep gate) + Task 5's "harbor agent/ stays empty" integration test.

- **Riskiest contract first.** Task 1 — the sealed-hash refusal — runs BEFORE any registry/schema/agent-class scaffolding. The seed-mismatch test mutates `agent.prompt_file` content between seed and resume specs and asserts the agent's `__init__` raises `SeedMismatchError` before `harbor.Job.create` is reached. The CLI variant asserts exit code 20 via `subprocess.run`. Both are required by the M4 entity's checklist item #2 verbatim.

- **M3 BaseAgent pattern inheritance.** Task 2 extends the M3 registry (M3 plan Task 2) — no restructure. Task 4 reuses the M3 proxy block (M3 plan Task 5) and the M3 auth loader (M3 plan Task 3) unchanged. Task 4 introduces `claude_invoke.py` and refactors `ClaudeCliAgent.run` to use it — the only M3-surface change M4 introduces. The required-env declaration pattern (M3 AC-1) is inherited verbatim by `SpacedockSolverAgent.required_env()` (Task 1's skeleton ships it).

- **M4-specific scope.** Stages config validated as exactly `["model", "analyze", "verify"]` (per §6.8 schema). Per-trial git-freeze at `logs_dir/agent_freeze/.git`. `phase_stats.json` matches the §6.8 schema. Content-hashed prompts pinned into `spec.frozen.yaml` AND the content embedded so the agent reads from the frozen spec (§6.4). The sealed_hash extends M3's "content-hash one prompt" to "content-hash model + sampling + stages + every prompt" — divergence explicitly named in the "M4 sealed-input definition" preamble above.

- **`run_experiment.py` discipline inheritance.** The DISALLOWED_TOOLS list is moved to `claude_invoke.py` (verbatim, no paraphrase). The proxy block discipline is inherited from M3's `proxy.py` unchanged. The auth precedence is inherited from M3's `auth.py` unchanged.

- **§6.8 phase_stats.json as a public contract.** Task 6 lands `assert_phase_stats_schema` as a module-level callable so M5's aggregator imports it. The schema is the EXACT design-doc verbatim: three fixed stages (`model`, `analyze`, `verify`), four fixed fields per stage (`tokens_in`, `tokens_out`, `cost_usd`, `wallclock_s`). M4 stubs token/cost numbers as 0; M5 wires real token cost from `events.jsonl`. The shape contract is M4's deliverable.

- **No backwards-compat shims.** `spec_to_job_config` gains a new kwarg `prior_frozen_spec_path: Path | None = None`. The default is None — M2's call sites stay green without modification. The `AgentBlock` discriminated union adds a third variant; nop and claude-cli stay parseable.

- **TDD discipline.** Tasks 1, 2, 3, 4, 5, 6, 7 each write the failing test first, run it red, then make it green. Tasks 8, 9, 10 are wiring/acceptance/docs.

- **Commit cadence.** One focused commit per task; format `m4: <summary>`. Plan-stage commits land on `main`; implementation worktree is FO-created at implementation kickoff.

- **Implementation worktree.** Per Spacedock's plan-on-main + worktree-on-implementation discipline, this plan commits to `main` directly. The implementation stage creates a worktree (`.worktrees/spacedock-ensign-m4-spacedock-solver-halt-resume/`) and lands Tasks 1–10's code there.
