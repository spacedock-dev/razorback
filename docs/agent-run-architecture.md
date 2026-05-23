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

- `RazorbackClaudeCode` in `src/razorback/agents/_runtime/claude.py`
  - subclasses Harbor `ClaudeCode`
  - normalizes Claude auth handling
  - applies Razorback tool allow/deny policy
  - preserves Harbor Claude telemetry/log surfaces

These adapters should stay runtime-specific. Shared provenance, sealing,
freeze, score, and benchmark identity logic should not move into
`RazorbackCodex` or `RazorbackClaudeCode`. There is no `RazorbackAgent` base
class today; if shared runtime-layer behavior becomes necessary, add a
runtime-neutral base/helper rather than putting it in a Codex- or
Claude-specific subclass.

### `SpacedockSolverAgent`

`SpacedockSolverAgent` in `src/razorback/agents/spacedock_solver.py` is an
outer solver wrapper. It currently:

- computes sealed run identity from model, sampling, workflow hash, prompt
  hashes, task identity, and runtime kwargs
- owns freeze/resume CAS and checkpoint commits
- reads a `solver_workflow/README.md`
- prepends that README to the benchmark task instruction
- builds an inner runtime adapter (`RazorbackCodex`, `RazorbackClaudeCode`, or
  future `pi`)
- delegates actual solving to that inner runtime adapter

Important: this class does not currently invoke Spacedock first-officer
dispatch. It is a sealed, checkpointed, README-structured solver wrapper.

## Current Implementation Map

Razorback currently has two implemented agent entry shapes:

- `agent.kind: claude-cli`
  - translates directly to `RazorbackClaudeCode`
  - this is the direct non-Spacedock path for Claude

- `agent.kind: spacedock_solver`
  - translates to `SpacedockSolverAgent`
  - `SpacedockSolverAgent` then builds the selected inner runtime adapter
    (`runtime: codex` -> `RazorbackCodex`, `runtime: claude` ->
    `RazorbackClaudeCode`)
  - this is currently README-structured and checkpointed, not first-officer
    dispatch

There is no direct `agent.kind: codex` schema path today. Current Codex example
specs use `agent.kind: spacedock_solver` with `runtime: codex`, so they are
`structured+freeze` unless the solver prompt is changed to boot a true
first-officer workflow.

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
- Codex minimal would need a direct Codex agent schema/translator path, or a
  `spacedock_solver` bypass mode that delegates directly without prepending a
  workflow README or sealing checkpoints.

### Structured

Structured runs use the same runtime adapter, but prepend a workflow README to
the task instruction.

Shape:

```text
Harbor trial
  -> RazorbackCodex or RazorbackClaudeCode
  -> workflow README + task instruction
```

This is "structured" because the model receives a procedure prompt. It is not a
Spacedock workflow run. There are no enforced stage boundaries, separate
workers, or gates.

The current implementation usually reaches this shape through
`SpacedockSolverAgent`, which also adds sealing and freeze/checkpoint behavior:

```text
Harbor trial
  -> SpacedockSolverAgent
       -> sealed hash / freeze checkpoints
       -> workflow README + task instruction
       -> RazorbackCodex or RazorbackClaudeCode
```

That should be understood as `structured+freeze`, not true Spacedock dispatch.

### Structured + Freeze

`structured+freeze` is useful for provenance and resume experiments, but it is
not meaningful stage checkpointing by itself. Since a structured run is still a
single `codex exec` or `claude --print` invocation, checkpoints mark setup,
before-agent, and after-agent boundaries. They do not guarantee reusable
intermediate stages unless the prompt asks the agent to write stage notes.

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

This is not implemented in the benchmark solver today. The current
`spacedock_solver` name is therefore overloaded: it provides structured prompt
and checkpoint behavior, but not first-officer dispatch.

## Benchmark-Specific Artifacts

### DAB

DAB tasks are answer-artifact tasks. The verifier expects `answers.json`.

- Minimal: runtime adapter reads task files and writes `answers.json`.
- Structured: workflow README gives the model a solve/verify procedure, then it
  writes `answers.json`.
- Spacedock workflow: first officer dispatches real stages, and the terminal
  stage writes `answers.json`.

### ADE-Bench

ADE-Bench tasks are dbt repair tasks. The verifier grades the final dbt project
state. There is no generic `answers.json` equivalent.

- Minimal: runtime adapter edits the dbt project directly.
- Structured: workflow README guides exploration, implementation, validation,
  and final cleanup, but one agent still performs the work.
- Spacedock workflow: first officer dispatches real dbt repair stages; the
  terminal state is the repaired project, not a separate answer file.

## Naming Rule

Use `spacedock` only when first-officer/ensign dispatch actually runs.

Use `structured` for workflow-README prompting without Spacedock dispatch.
Use `structured+freeze` when the sealed/checkpoint wrapper is part of the
experiment.
