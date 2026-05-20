# Harbor source probe — AC-0.3, AC-0.4, AC-0.6

**Date:** 2026-05-20
**Scope:** Read-only inspection of harbor at `~/git/razorback/.venv/lib/python3.12/site-packages/harbor/` (canonical install for this project; `~/.venv/...` does not exist).
**Resolves:** AC-0.3, AC-0.4, AC-0.6 in `2026-05-19-razorback-reconciliation-plan.md`

## AC-0.3 spec format compatibility

### Harbor's `JobConfig` (what `harbor run -c <yaml>` accepts)

Source: `harbor/models/job/config.py:244-302` (`JobConfig(BaseModel)`).
Loaded by `harbor/cli/jobs.py:1051-1056` via `JobConfig.model_validate(yaml.safe_load(...))`.

Top-level fields (`JobConfig`):

- `job_name: str` (default = timestamp)
- `jobs_dir: Path = Path("jobs")`
- `n_attempts: int = 1`
- `timeout_multiplier: float = 1.0`
- `agent_timeout_multiplier`, `verifier_timeout_multiplier`, `agent_setup_timeout_multiplier`, `environment_build_timeout_multiplier: float | None = None`
- `debug: bool = False`
- `n_concurrent_trials: int = 4`
- `quiet: bool = False`
- `retry: RetryConfig`
- `environment: EnvironmentConfig`
- `verifier: VerifierConfig`
- `metrics: list[MetricConfig]`
- `agents: list[AgentConfig]` (note: **plural list**)
- `datasets: list[DatasetConfig]`
- `tasks: list[TaskConfig]`
- `artifacts: list[str | ArtifactConfig]`

Pydantic `JobConfig` is **not** declared with `extra="forbid"` (config.py:244, no `model_config`), so harbor silently drops any keys it doesn't know. That matters for the gap analysis below.

### Harbor's `AgentConfig` (what each entry of `agents:` accepts)

Source: `harbor/models/trial/config.py:44-63`.

- `name: str | None` — registered short-name (`claude-code`, `aider`, …) routed through `AgentFactory._AGENT_MAP` (`harbor/agents/factory.py:61`).
- `import_path: str | None` — `"module.path:ClassName"`. If `name` is absent, this loads any class via `create_agent_from_import_path` (factory.py:96-133). This is the **entry-point dispatch** mechanism razorback's plan refers to.
- `model_name: str | None`
- `override_timeout_sec`, `override_setup_timeout_sec`, `max_timeout_sec: float | None`
- `kwargs: dict[str, Any]` — splatted into the agent constructor (factory.py:161, 170). This is where `model`, `sampling`, `stages`, `tools_allowed`, `prompts`, `prompt_contents`, `sealed_hash`, `prior_frozen_spec_path` land for `SpacedockSolverAgent`.
- `env: dict[str, str]` — resolved through `resolve_env_vars(config.env)` and passed as `extra_env=` (factory.py:154, 160). This is how `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` reach `SpacedockSolverAgent._extra_env` (spacedock_solver.py:79).

### Razorback's spec format (current)

Source: `src/razorback/spec/schema.py`.

Top-level `Spec` (`schema.py:135-143`, `extra="forbid"`):

- `version: int`
- `experiment: str`
- `agent: AgentBlock` (singular discriminated union: `nop` | `claude-cli` | `spacedock-solver`)
- `benchmark: BenchmarkBlock` (discriminated: `local` | `dab` | `ade-bench`)
- `trials: int = 1`
- `observers: list[ObserverBlock]`
- `provenance: ProvenanceBlock`

`SpacedockSolverAgentBlock` (`schema.py:31-65`):
`kind`, `model`, `sampling{temperature,top_p,seed}`, `stages`, `tools_allowed`, `prompts`, `prompt_contents`, `sealed_hash`.

### Field-by-field gap

| Razorback concept                | Harbor counterpart                                | Gap / translation                                                                                                                                                                       |
| -------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `version: int`                   | (none)                                            | razorback-only; not passed                                                                                                                                                              |
| `experiment: str`                | `job_name: str`                                   | rename / derive (`derive_job_name` already exists at `src/razorback/spec/freeze.py:59`)                                                                                                 |
| `agent: <one block>` (singular)  | `agents: list[AgentConfig]`                       | wrap razorback's single block into a 1-element list                                                                                                                                     |
| `agent.kind = "spacedock-solver"`| `agent.name` OR `agent.import_path`               | razorback's `kind` is **not** in harbor's `AgentName` enum. Must use `import_path="razorback.agents.spacedock_solver:SpacedockSolverAgent"` (entry-point dispatch — factory.py:164-172).  |
| `agent.kind = "claude-cli"`      | `agent.name = "claude-code"`                      | rename. (Razorback's `claude-cli` block is shaped differently from `ClaudeCode` flags; see AC-0.4 mitigation.)                                                                          |
| `agent.kind = "nop"`             | `agent.name = "nop"`                              | direct rename (`harbor/agents/nop.py` exists)                                                                                                                                           |
| `agent.model`                    | `agent.model_name`                                | rename (`model` → `model_name`). Razorback's `SpacedockSolverAgent.__init__` still accepts `model=` as a kwarg (spacedock_solver.py:51), so when going through `kwargs` it works either way; but `claude-code` reads from `model_name`, not `model`. |
| `agent.sampling.{temperature,top_p,seed}` | (none on `AgentConfig`)                  | harbor has no first-class sampling block. For `spacedock-solver`: passes through `kwargs` into our agent. For `claude-code`: harbor's `ClaudeCode` has **no `sampling` kwarg** at all — sampling is governed by the underlying claude CLI's own flags (`--effort`, `--thinking`, etc.). Razorback's `claude-cli` sampling fields are silently lost when targeting `ClaudeCode`. |
| `agent.stages`                   | (none)                                            | razorback-only; passed via `kwargs` to `SpacedockSolverAgent`                                                                                                                            |
| `agent.tools_allowed`            | `ClaudeCode` `allowed_tools` (CliFlag, claude_code.py:81) | for `spacedock-solver`: passed via kwargs to our agent. For `claude-code`: rename `tools_allowed` → `allowed_tools` and join list into a comma/space string (harbor's `CliFlag` expects `str`, see base.py:48-58). |
| `agent.prompts`, `prompt_contents`, `sealed_hash` | (none)                                  | razorback-only; passed via `kwargs` to `SpacedockSolverAgent`                                                                                                                            |
| `benchmark: <block>` (singular)  | `tasks: list[TaskConfig]` + `datasets: list[DatasetConfig]` | razorback's benchmark blocks must be expanded into a list of `TaskConfig` (or `DatasetConfig`) entries before invoking harbor. `LocalBenchmarkBlock.task_paths` → multiple `TaskConfig(path=…)`. `AdeBenchBenchmarkBlock` already declares git-task fields matching `TaskConfig` (schema.py:87-105 — note the comment "matching harbor's TaskConfig git-task shape"). `DabBenchmarkBlock` (data_root + datasets) → `DatasetConfig(path=data_root/<name>)`. |
| `trials: int`                    | `n_attempts: int` (semantics ≠ identical!)        | **Likely gap.** `trials` in razorback means "number of independent trials per task"; harbor's `n_attempts` is the per-trial retry count (jobs.py:505-515). Need to confirm — re-running N times might be modelled by duplicating tasks or by a harbor-side knob not present. **Mark as a gap to resolve when picking translation strategy.** |
| `observers: list[ObserverBlock]` | (closest analog: `metrics: list[MetricConfig]` for reward emitters, plus harbor's built-in event log) | harbor has its own observer/event infrastructure (`harbor/publisher/`, `harbor/observers/` does not exist in installed package — `ls` shows no `observers/`). Razorback's `jsonl`/`stdout` observers map to harbor's progress and event-log facilities. **Gap to confirm**: whether razorback needs to subscribe to harbor's events post-`harbor run`, or whether harbor already writes a per-job event JSONL we can point users at. |
| `provenance: ProvenanceBlock`    | (none)                                            | razorback-only; stays in `spec.frozen.yaml` / `provenance.yaml` next to harbor's run dir (spec §7.1). Does not flow into `JobConfig` at all.                                            |

### Translation strategy

**Decision:** razorback should **rewrite the spec into a `JobConfig`** before invoking `harbor run`, *not* try to make razorback's YAML directly harbor-acceptable. Reasons:

1. The shapes differ on more than naming: razorback has singular `agent`/`benchmark`, harbor has plural `agents`/`tasks`. Field renames (`model` → `model_name`, `experiment` → `job_name`, `tools_allowed` → `allowed_tools`) cannot be done by harbor-side aliasing because harbor's models are not razorback-aware.
2. razorback owns extra blocks (`provenance`, `observers`, `version`) that have no equivalent in `JobConfig` and would be silently dropped (since `JobConfig` is not `extra="forbid"`). Keeping them outside `JobConfig` lets `rk freeze` stamp them into `spec.frozen.yaml` / `provenance.yaml` per spec §7.1.
3. For `kind: spacedock-solver`, razorback's class is not in harbor's `_AGENT_MAP`. Entry-point dispatch via `AgentConfig.import_path = "razorback.agents.spacedock_solver:SpacedockSolverAgent"` is the only path that works without monkey-patching harbor (factory.py:164-172).

Concrete translation pseudocode (sketch):

```python
def to_job_config(spec: Spec) -> JobConfig:
    agent_cfg = _translate_agent(spec.agent)            # AgentConfig
    task_cfgs, dataset_cfgs = _translate_benchmark(spec.benchmark)
    return JobConfig(
        job_name=spec.experiment,                       # or derive_job_name(...)
        n_attempts=1,                                   # NOT spec.trials — open question
        agents=[agent_cfg],
        tasks=task_cfgs,
        datasets=dataset_cfgs,
    )
```

**Open question (filed as a gap, not a blocker):** how razorback's `trials: N` semantics map onto harbor — likely by duplicating trial entries or running the job N times, not via `n_attempts`. Worth resolving as part of AC-0.2 (harbor entry-point execution probe).

## AC-0.4 `ClaudeCode.__init__` constructor signature

Source: `harbor/agents/installed/claude_code.py:104-112`.

```python
def __init__(
    self,
    logs_dir: Path,
    memory_dir: str | None = None,
    *args,
    **kwargs,
):
    self.memory_dir = memory_dir
    super().__init__(logs_dir, *args, **kwargs)
```

Direct constructor params: **two** (one positional + one keyword with default).

But `**kwargs` is the real surface area. It walks two inheritance hops:

### `BaseInstalledAgent.__init__` (base.py:147-173)

```python
def __init__(
    self,
    logs_dir: Path,
    prompt_template_path: Path | str | None = None,
    version: str | None = None,
    extra_env: dict[str, str] | None = None,
    *args,
    **kwargs,
):
```

Additionally, this hop **auto-extracts** any kwarg whose name matches a `CliFlag.kwarg` or `EnvVar.kwarg` declared on the class (base.py:157-160). For `ClaudeCode` (claude_code.py:33-98), the accepted CLI / env kwargs are:

| Kwarg               | Type   | CLI flag                | Notes                            |
| ------------------- | ------ | ----------------------- | -------------------------------- |
| `max_turns`         | int    | `--max-turns`           | env fallback `CLAUDE_CODE_MAX_TURNS` |
| `reasoning_effort`  | enum   | `--effort`              | low/medium/high/xhigh/max         |
| `thinking`          | enum   | `--thinking`            | enabled/adaptive/disabled         |
| `thinking_display`  | enum   | `--thinking-display`    | summarized/omitted                |
| `max_thinking_tokens`| int   | `--max-thinking-tokens` | env fallback `MAX_THINKING_TOKENS` (also surfaces as env var inside container) |
| `max_budget_usd`    | str    | `--max-budget-usd`      |                                   |
| `fallback_model`    | str    | `--fallback-model`      |                                   |
| `append_system_prompt`| str  | `--append-system-prompt`|                                   |
| `allowed_tools`     | str    | `--allowedTools`        | string (comma-separated tools)    |
| `disallowed_tools`  | str    | `--disallowedTools`     |                                   |

### `BaseAgent.__init__` (base.py:27-44 in `harbor/agents/base.py`)

```python
def __init__(
    self,
    logs_dir: Path,
    model_name: str | None = None,
    logger: logging.Logger | None = None,
    mcp_servers: list[MCPServerConfig] | None = None,
    skills_dir: str | None = None,
    *args,
    **kwargs,
):
```

### Full effective surface for `ClaudeCode(...)`

Positional/standard:
- `logs_dir: Path` (**only mandatory parameter** — supplied by harbor's trial runner at `harbor/trial/trial.py:195`)

Optional keyword:
- `memory_dir` (claude_code.py)
- `prompt_template_path`, `version`, `extra_env` (BaseInstalledAgent)
- `model_name`, `logger`, `mcp_servers`, `skills_dir` (BaseAgent)
- Any of the 10 CLI/ENV declarative kwargs above (`max_turns`, `reasoning_effort`, …, `disallowed_tools`).

### Mandatory kwargs that razorback would struggle to supply

**None.** Only `logs_dir` is mandatory, and razorback never has to supply it because harbor's trial runner injects it at construction time via `AgentFactory.create_agent_from_config(..., logs_dir=trial_paths.agent_dir, ...)` (factory.py:140, trial.py:195).

`memory_dir`, `model_name`, and the CLI-flag kwargs all default to `None` and are accessed through `_resolve_raw_value` (base.py:175-184), which falls back to env vars and then to `None`.

### Coupling note (razorback's `SpacedockSolverAgent`, not `ClaudeCode`)

The task asks about `ClaudeCode`, but the more interesting coupling is between razorback's `SpacedockSolverAgent` (which derives from `BaseAgent`, not `BaseInstalledAgent`) and the harbor surface:

- Razorback's `SpacedockSolverAgent.__init__` (`src/razorback/agents/spacedock_solver.py:43-94`) declares its own keyword-only params (`model`, `sampling`, `stages`, `tools_allowed`, `prompts`, `sealed_hash`, optional `prompt_contents`, `prior_frozen_spec_path`, `extra_env`) and forwards `**kwargs` to `BaseAgent.__init__`.
- `BaseAgent.__init__` accepts `logger`, `mcp_servers`, `skills_dir` as known kwargs. Anything else in `**kwargs` is silently swallowed by `BaseAgent`'s `*args, **kwargs` (base.py:35-36) — meaning if harbor ever adds a new mandatory kwarg to `BaseAgent`, razorback's agent will not break, but it also won't pick it up. Acceptable for now.
- Razorback's agent accepts `extra_env` as a named kwarg (spacedock_solver.py:59), matching the way `AgentFactory.create_agent_from_config` passes it (factory.py:160, 169). This is the only routing detail that has to stay aligned with harbor.

**Coupling summary:** no mandatory kwarg from harbor's side that razorback would have trouble supplying. The relationship is bidirectional in name only — razorback declares the kwargs it needs in its own `__init__`, and harbor's `AgentFactory` happily splats `**config.kwargs` into them.

## AC-0.6 per-trial run-dir layout

### Files harbor writes per trial

Source of truth: `harbor/models/trial/paths.py` (the `TrialPaths` dataclass docstring at lines 78-124 is authoritative and matches the code).

Single-step trial:

```
<jobs_dir>/<job_name>/trials/<trial_name>/
├── agent/              # mounted into the container at /logs/agent/
├── verifier/           # mounted into the container at /logs/verifier/
├── artifacts/          # mounted into the container at /logs/artifacts/
│   └── manifest.json   # written at trial end if any artifacts were collected (trial.py:907)
├── config.json         # full TrialConfig pydantic dump (trial.py:934)
├── result.json         # TrialResult pydantic dump (trial.py:440)
├── exception.txt       # written only on failure (trial.py:971, 998)
└── trial.log           # per-trial logger output (paths.py:226-230)
```

Multi-step trial adds:

```
└── steps/<step_name>/
    ├── agent/
    ├── verifier/
    └── artifacts/
        └── manifest.json
```

`agent/`, `verifier/`, `artifacts/` are created by `TrialPaths.mkdir()` (paths.py:128-131) at the start of every trial, regardless of step count. For multi-step trials, the root-level mount dirs are emptied into `steps/<name>/` after each step and removed via `cleanup_empty_mount_dirs()` (paths.py:133-142).

### What does the agent receive as `logs_dir`?

`harbor/trial/trial.py:195` calls `AgentFactory.create_agent_from_config(..., logs_dir=self._trial_paths.agent_dir, ...)`. So `logs_dir` inside any agent (`ClaudeCode`, `SpacedockSolverAgent`, etc.) is **`<trial_dir>/agent/`**, *not* the trial root.

### Confirming razorback's `agent_freeze/` is collision-safe

Razorback's `SpacedockSolverAgent` writes `self.logs_dir / "agent_freeze"` (`src/razorback/agents/spacedock_solver.py:215`). Expanded, that path is:

```
<jobs_dir>/<job_name>/trials/<trial_name>/agent/agent_freeze/
├── .git/
├── phase_stats.json
└── sealed_hash.txt
```

This lives **inside** the harbor-mounted `agent/` subtree — i.e., entirely within the agent-owned dir. Harbor itself writes only sibling files at the **trial root** (`config.json`, `result.json`, `exception.txt`, `trial.log`), under `verifier/`, under `artifacts/`, or under `steps/` (multi-step only). Harbor never writes anything under `agent/` other than what the in-container agent process writes via the bind mount (`agent/` is just a mount target — see env paths at paths.py:36-38).

**No collision exists** between `agent/agent_freeze/` and anything harbor controls. The only collision risk is with other things `ClaudeCode` (when used as the underlying claude CLI) writes into `/logs/agent/` from inside the container — e.g., `claude-code.txt` (the stream-json transcript at claude_code.py:498) and the `sessions/projects/…/<id>.jsonl` Claude session tree (claude_code.py:163). The literal name `agent_freeze` does not appear in any harbor-shipped agent's output paths (`grep -r "agent_freeze" harbor/` returns no hits in the install).

### Spec §7.1 discrepancy (minor, worth flagging)

The spec at `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md:619-630` shows the freeze tree under `trials/<task>-NNNN/logs_dir/agent_freeze/`. There is **no `logs_dir/` directory** in harbor's actual on-disk layout — `logs_dir` is the Python name of the agent's bind-mount parameter, which resolves to `trials/<trial_name>/agent/` on disk (paths.py:144-155). The path in the wild is:

```
trials/<trial_name>/agent/agent_freeze/   # actual
trials/<trial_name>/logs_dir/agent_freeze/  # spec §7.1 (incorrect literal)
```

Not a blocker — the spec text is unambiguous about *intent* ("the agent's `self.logs_dir`"). Worth fixing the on-disk literal in spec §7.1 during plan execution; flagging here so it's not forgotten.

## Summary

No blockers uncovered; the plan can proceed as written, but two open questions and one spec wording fix should be filed:

1. **(filed as open question)** `trials: int` semantics — razorback's "N independent trials" does not map cleanly onto harbor's `n_attempts: int` (which is per-trial retries). Resolve in AC-0.2 by checking how harbor's CLI exposes "run the same task N times" (likely via duplicating `tasks:` entries; harbor has no top-level `n_trials`).
2. **(filed as open question)** `observers` translation — razorback's `jsonl`/`stdout` observer blocks have no slot in `JobConfig`. Harbor's own publisher/event infrastructure (`harbor/publisher/`) likely emits a per-job event stream that razorback can consume post-`harbor run`; needs confirmation against AC-0.2.
3. **(filed as spec wording fix)** Spec §7.1 path literal should change `logs_dir/agent_freeze/` → `agent/agent_freeze/` to match harbor's on-disk layout. Cosmetic, but it would confuse any new reader cross-referencing the spec against the run-dir.

AC-0.4 has the cleanest outcome: `ClaudeCode` has only one mandatory positional (`logs_dir`), which harbor injects itself, and razorback never needs to supply it. The `**kwargs` surface is wide but declarative (driven by `CLI_FLAGS` / `ENV_VARS`), so razorback's translation layer can pass through `claude-cli` block fields with simple rename rules.

AC-0.6's risk is essentially zero: razorback's `agent_freeze/` lives strictly inside harbor's agent-owned subtree, with no overlapping file names from harbor itself or from `ClaudeCode`'s in-container output.
