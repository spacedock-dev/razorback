# Agent Run Architecture

This document describes Razorback's benchmark agent layers and the intended run
variants for DAB and ADE-Bench.

## Agent Layers

### Harbor Installed Agents

Harbor provides raw installed agents such as `harbor.agents.installed.codex.Codex`
and `harbor.agents.installed.claude_code.ClaudeCode`.

These agents know how to install and invoke the tool inside a benchmark
container. They do not know Razorback benchmark policy, dataset semantics,
sealed provenance, or Spacedock workflow orchestration.

### Razorback Runtime Adapters

Razorback runtime adapters wrap Harbor's installed agents with runtime-specific
benchmark policy.

- `RazorbackCodex` in `src/razorback/agents/_runtime/codex.py`
  - subclasses Harbor `Codex`
  - disables web search
  - installs public-lookup guards and shell wrappers
  - clears proxy env during Codex installation
  - rejects unsupported Codex kwargs instead of silently dropping them
  - can stage the Spacedock plugin into Codex's skills directory and enable
    `multi_agent` when asked by the outer Spacedock solver

- `RazorbackClaudeCode` in `src/razorback/agents/_runtime/claude.py`
  - subclasses Harbor `ClaudeCode`
  - normalizes Claude auth handling
  - applies Razorback tool allow/deny policy
  - preserves Harbor Claude telemetry/log surfaces
  - can stage Spacedock plugins and invoke a named Claude sub-agent when asked
    by the outer Spacedock solver

These adapters should stay runtime-specific. Shared provenance, sealing,
freeze, score, and benchmark identity logic should not move into
`RazorbackCodex` or `RazorbackClaudeCode`. There is no `RazorbackAgent` base
class today; if shared runtime-layer behavior becomes necessary, add a
runtime-neutral base/helper rather than putting it in a Codex- or
Claude-specific subclass.

### `SpacedockSolverAgent`

`SpacedockSolverAgent` in `src/razorback/agents/spacedock_solver.py` is an
outer experiment and orchestration wrapper. It is not the raw model runtime and
it is not a generic README-prepending helper. It currently:

- computes sealed run identity from model, sampling, workflow hash, prompt
  hashes, task identity, and runtime kwargs
- owns freeze/resume CAS and checkpoint commits
- runs ADE workspace preflight before invoking the model runtime
- reads a `solver_workflow/README.md`
- injects that README into a first-officer bootstrap prompt
- builds an inner runtime adapter (`RazorbackCodex`, `RazorbackClaudeCode`, or
  future `pi`)
- configures the inner runtime for Spacedock dispatch:
  - Codex: stages the Spacedock plugin into the skills surface, enables
    `multi_agent`, and prompts Codex to resolve `spacedock:first-officer`
  - Claude: stages the Spacedock plugin and invokes
    `--agent spacedock:first-officer`
- tells the first officer to dispatch `spacedock:ensign` workers and wait for
  them
- writes dispatch trace metadata after the inner runtime returns or times out

This is the current Spacedock benchmark path. It addresses the experiment-level
work around a solver run: sealed identity, freeze/resume, runtime-specific
plugin bootstrapping, benchmark preflight, first-officer entry, and trace
evidence. The raw runtime adapters address how to run Codex or Claude safely
inside Harbor.

## Current Implementation Map

Razorback currently has three implemented agent entry shapes:

- `agent.kind: claude-cli`
  - translates directly to `RazorbackClaudeCode`
  - this is the direct non-Spacedock path for Claude

- `agent.kind: codex`
  - translates directly to `RazorbackCodex`
  - this is the direct minimal path for Codex
  - it does not carry `solver_workflow`, `sealed_hash`, workflow README
    prompting, or freeze/checkpoint behavior

- `agent.kind: spacedock_solver`
  - translates to `SpacedockSolverAgent`
  - `SpacedockSolverAgent` then builds the selected inner runtime adapter
    (`runtime: codex` -> `RazorbackCodex`, `runtime: claude` ->
    `RazorbackClaudeCode`)
  - this is the Spacedock first-officer dispatch path, with sealed
    freeze/resume and benchmark preflight

Current Codex minimal specs should use `agent.kind: codex`. Codex specs that
use `agent.kind: spacedock_solver` with `runtime: codex` are
Spacedock workflow specs, not plain structured prompts.

## Run Variants

### Minimal

Minimal runs use a Razorback runtime adapter directly.

Shape:

```text
Harbor trial
  -> RazorbackCodex or RazorbackClaudeCode
  -> task instruction
```

Use this for the plain baseline: same task workspace, same verifier, no
workflow README, no Spacedock dispatch.

Implemented today:

- Claude minimal exists through `agent.kind: claude-cli`.
- Codex minimal exists through `agent.kind: codex`.

Current gaps:

- The direct Codex path intentionally supports only Codex controls that Harbor
  exposes directly, such as `reasoning_effort` and `reasoning_summary`.
- It does not implement tool allow/deny policy fields; those fail closed at
  schema validation instead of being silently dropped.

### Structured

Structured runs use the same runtime adapter, but prepend a workflow README to
the task instruction.

Shape:

```text
Harbor trial
  -> RazorbackCodex or RazorbackClaudeCode
  -> workflow README + task instruction
```

This is "structured" because the model receives a procedure prompt. It is not
a Spacedock workflow run. There are no first-officer dispatches, separate
workers, or gates.

There is no first-class `structured` agent kind today. Do not use
`spacedock_solver` to mean "README-only structured"; it now boots Spacedock
dispatch. A future structured agent would have this shape:

```text
Harbor trial
  -> RazorbackCodex or RazorbackClaudeCode
  -> workflow README + task instruction
```

Desired state:

- Structured-only runs should be expressible without sealed/checkpoint
  semantics when the experiment only needs README prompting.
- Structured-with-freeze should also be expressible without Spacedock dispatch
  when the experiment needs sealed provenance but not workers.

Current gap:

- There is no first-class `structured` agent kind that prepends a workflow
  README without freeze/checkpoint behavior.
- There is no first-class `structured+freeze` agent kind that adds sealing and
  resume without first-officer dispatch.

### Structured + Freeze

`structured+freeze` is useful for provenance and resume experiments. It is not
currently a separate implementation. If added, it should wrap a runtime adapter
with sealed hash and freeze checkpoints, but should not stage Spacedock plugins
or ask a first officer to dispatch workers.

Even with freeze enabled, benchmark-level checkpoints currently mark setup,
before-agent, and after-agent boundaries. Reusable intermediate stage state
requires the solver workflow or worker prompts to write explicit stage notes or
artifacts.

### Spacedock Workflow

A true Spacedock workflow run should invoke the Spacedock first-officer contract
inside the benchmark task.

Intended shape:

```text
Harbor trial
  -> Razorback runtime adapter
  -> initial prompt that boots spacedock:first-officer
  -> first officer reads workflow definition
  -> first officer dispatches ensigns/workers for stages
  -> gates/rejections/reuse/checkpoints happen at real stage boundaries
  -> final artifact is produced for the benchmark verifier
```

This is the only variant that should be called `spacedock-workflow`.

This is implemented today through `agent.kind: spacedock_solver`.

Current implementation details:

- Codex uses an inline benchmark workflow contract rather than a persistent
  Spacedock entity directory. The first officer resolves the packaged
  `spacedock:first-officer` skill, dispatches a `spacedock:ensign` worker with
  `spawn_agent`, waits with `wait_agent`, then reports changed files and
  validation evidence.
- Claude uses the Spacedock plugin and `--agent spacedock:first-officer` path.
- ADE-Bench final state is still the repaired dbt project. DAB final state is
  still `answers.json`.
- The run-level freeze commits are outer lifecycle checkpoints, not guaranteed
  per-stage checkpoints inside the worker unless the workflow writes explicit
  notes/artifacts.

Desired state:

- Spacedock workflow variants should use real workflow stage boundaries as the
  unit of gate, rejection, reuse, and checkpoint evidence.
- Parallel full-dataset runs should retain one dispatch manifest per trial, not
  a collapsed job-level manifest.

Current gap:

- The Codex path is a benchmark-inline first-officer workflow, not a full
  repository-style Spacedock entity/worktree workflow.
- The current Codex prompt dispatches one worker per benchmark trial. Multi-stage
  worker dispatch, gates, and rejections need workflow/prompt support beyond
  that minimum.
- Full parallel runs currently produce incomplete dispatch provenance because
  the manifest is written at the job root and can collapse or overwrite
  per-trial traces.

## Benchmark-Specific Artifacts

### DAB

DAB tasks are answer-artifact tasks. The verifier expects `answers.json`.

- Minimal: runtime adapter reads task files and writes `answers.json`.
- Structured: workflow README gives the model a solve/verify procedure, then it
  writes `answers.json`.
- Spacedock workflow: first officer dispatches workers, and the terminal worker
  writes `answers.json`.

### ADE-Bench

ADE-Bench tasks are dbt repair tasks. The verifier grades the final dbt project
state. There is no generic `answers.json` equivalent.

- Minimal: runtime adapter edits the dbt project directly.
- Structured: workflow README guides exploration, implementation, validation,
  and final cleanup, but one agent still performs the work.
- Spacedock workflow: first officer dispatches dbt repair work; the terminal
  state is the repaired project, not a separate answer file.

## Naming Rule

Use `spacedock` only when first-officer/ensign dispatch actually runs.

Use `structured` for workflow-README prompting without Spacedock dispatch.
Use `structured+freeze` when the sealed/checkpoint wrapper is part of the
experiment.
