# Razorback: A Research-Stats Extension to Harbor

**Status:** Draft
**Date:** 2026-05-19

---

## 1. Introduction

### 1.1 What razorback is

Razorback is a small CLI and Python package that adds three things to
harbor's agent-benchmark stack:

1. **Reproducible runtime provenance.** A `freeze` subcommand pins
   provider model versions, image digests, agent CLI binaries, and
   prompt file content, then refuses to execute a job whose live inputs
   have drifted from the frozen record.
2. **Paired-statistics comparison between two job-runs.** A `diff`
   subcommand emits per-query Wilson confidence intervals, exact
   McNemar p-values, paired bootstrap CIs on stratified deltas, and
   minimum-detectable-effect at fixed N. This is the quantitative
   complement to harbor's qualitative LLM-driven analysis.
3. **A multi-runtime spacedock-solver agent with halt-resume.** A
   parameterizable harbor agent class that adapts claude, codex, or pi
   to act as a spacedock first-officer driving a workflow README
   through a benchmark task; supports stage-boundary freeze and
   sealed-input resume refusal.

Razorback also ships two spacedock workflow README templates — an
experiment workflow (hypothesis lifecycle: propose → smoke → full →
analyze → conclude) and a run workflow (trial reconciliation) — that
together describe how an LLM-driven autoresearch loop operates on top
of razorback and harbor.

### 1.2 Glossary

- **Harbor** — agent-benchmark framework
  (`github.com/harbor-framework/harbor`). Provides the engine: job
  fan-out, executor lifecycle, trial event emission, the installed-agent
  catalog (claude_code, codex, pi, and ~20 others), the verifier
  framework, the docker/singularity environment framework, and a full
  CLI (`harbor run`, `harbor analyze`, `harbor sweeps`, `harbor view`,
  `harbor publish`, etc.). Razorback consumes harbor; razorback does
  not wrap or replace harbor's CLI.
- **Spacedock** — workflow framework where an LLM agent operates
  against markdown workflow definitions. Provides skills (first-officer,
  ensign, commission, debrief) that load a workflow README and drive an
  operator through its stages. Razorback consumes spacedock as a Claude
  plugin running inside its solver agent.
- **Operator** — an LLM-driven actor running inside the
  spacedock-solver agent, executing a workflow's stages.
- **Workflow README** — a markdown file (`README.md`) plus sibling
  entity files and mod files that together define a spacedock workflow:
  its stages, entity schema, gates, and per-stage behavior. Spacedock
  skills consume workflow READMEs; the README is the operator-facing
  contract.
- **Solver workflow README** — a workflow README that defines how a
  spacedock-solver agent solves one benchmark task. The autoresearch
  loop's hypothesize step modifies the solver workflow README to try a
  different solver variant.
- **Trial** — one execution of one agent on one task. Harbor concept.
- **Run** — one invocation of `harbor run`; produces a run-dir
  containing many trials. Harbor concept.
- **Hypothesis** — one entity in the experiment workflow; corresponds
  to one solver-variant + the experiments that test it.

### 1.3 Non-goals

- Razorback does not own the execution engine. Harbor does. `rk run`
  is a thin pass-through that resolves the frozen spec and invokes
  `harbor run` underneath, so the workflow operator sees one CLI
  surface (`rk *`) regardless of which layer is doing the work. If
  razorback's capabilities ever upstream into harbor, the pass-through
  collapses to a CLI rename, not a behavioral change.
- Razorback is not a benchmark library. Benchmarks live in harbor's
  catalog as adapters publishable via `harbor publish`. Razorback does
  not ship benchmark adapters.
- Razorback is not a workflow engine. Spacedock is. Razorback ships
  workflow README templates and a few generic mods; the workflow
  semantics belong to spacedock.
- Razorback is not an LLM-trajectory analyzer. Harbor's `harbor
  analyze` (Claude-SDK-driven rubric scoring) and `harbor jobs
  summarize` cover that. Razorback's `rk diff` is classical inferential
  statistics, not qualitative critique.
- Razorback does not wrap every harbor feature. Features harbor adds
  do not automatically surface in razorback.

---

## 2. Architecture

### 2.1 Three layers

```
┌──────────────────────────────────────────────────────────────────────┐
│ Autoresearch loop (spacedock workflows)                              │
│                                                                      │
│ Experiment workflow:                                                 │
│   pending → propose → smoke → full → analyze → conclude              │
│   Owns hypothesis lifecycle, leak guards, captain gates.             │
│   Dispatches a run-workflow entity per smoke / full stage.           │
│                                                                      │
│ Run workflow:                                                        │
│   pending → reconciling → completed | failed                         │
│   Reconciles target trial count, dispatches make-up runs.            │
│                                                                      │
│ Both consume razorback's commands and templates.                     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ each stage shells one to four commands
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Razorback (this project)                                             │
│                                                                      │
│ CLI:                                                                 │
│   rk run      — pass-through to `harbor run`, with razorback's       │
│                 alias-drift pre-check on the frozen spec             │
│   rk freeze   — resolve and pin runtime provenance                   │
│   rk diff     — paired statistics between two runs                   │
│   rk runs list/show — scriptable run-dir inspection (until           │
│                       upstreamed into harbor)                        │
│                                                                      │
│ Agent class:                                                         │
│   SpacedockSolverAgent — multi-runtime, halt-resume,                 │
│                          harbor.kind: spacedock_solver               │
│                                                                      │
│ Workflow README templates:                                           │
│   experiment-workflow/  run-workflow/                                │
│                                                                      │
│ Generic mods consumed by the templates:                              │
│   leak-guard  baseline-compare  cost-ceiling                         │
│   stage-boundary-freeze  phase-stats-writer                          │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ rk freeze writes provenance;           
                               │ SpacedockSolverAgent registers via     
                               │ harbor's agent-plugin discovery        
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Harbor                                                               │
│                                                                      │
│ Engine: Job fan-out, executor lifecycle, trial event emission        │
│ CLI:    harbor run, jobs, analyze, sweeps, view, publish, adapter,   │
│         task, dataset, trial, cache, auth, check, init, ...          │
│ Agents: claude_code, codex, pi, aider, gemini_cli, swe_agent, +18    │
│ Adapters: published per-benchmark via `harbor publish`               │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Where razorback sits

Razorback is the thin layer that supplies what harbor does not:
research-grade statistical comparison, reproducible runtime
provenance, the spacedock-solver runtime adapter with halt-resume, and
the workflow README templates that describe how to do
hypothesis-driven research on top of the stack.

Razorback does not own job execution, trial fan-out, the
installed-agent catalog, the verifier framework, the environment
framework, trajectory analysis, sweeps, the web viewer, or the adapter
catalog. Those are harbor's. Razorback consumes them.

A user with a private benchmark publishes their adapter to harbor
(`harbor publish`) and invokes the runner through razorback's CLI
(`rk run`) so the same surface covers freeze, run, diff, and
list/show. They reach for razorback's distinctive value when they
want to compare two runs statistically (`rk diff`), pin runtime
provenance for reproducibility (`rk freeze`), or use the
spacedock-solver agent (`agent.kind: spacedock_solver`) to drive a
multi-stage workflow-README-based solver against the benchmark.

---

## 3. The deterministic CLI surface

### 3.1 Design rules

- One subcommand, one purpose. Composite operations live in workflows.
- JSON by default. A `--format human` flag prints a table; workflow
  operators parse JSON.
- Idempotent where possible. Re-running `rk freeze` on a spec already
  frozen produces an identical output.
- No harbor types in subcommand arguments, output, or exit codes.
- Stable exit codes. Each subcommand enumerates them; workflow
  operators branch on the codes.
- The CLI is the operator's uniform surface. Subcommands that
  delegate to harbor (`rk run`) stay under `rk *` for workflow
  ergonomics; the operator does not context-switch between two CLIs.
  If razorback's distinctive subcommands eventually upstream into
  harbor, the surface becomes a CLI rename, not a behavioral change.

### 3.2 Subcommand surface

```
rk run <frozen-spec.yaml>
rk freeze <spec.yaml>
rk diff <run-a> <run-b> [--format markdown|json] [--alpha 0.05]
                       [--bootstrap-iters 10000] [--family-wise-alpha 0.05]
                       [--bootstrap-cluster query|trial]
rk runs list [--root <dir>] [--experiment <name>]
rk runs show <run-dir>
```

Optional follow-ons, ship when consumer demand exists:

```
rk constraints check <spec.yaml> --constraints <path|@name>
rk baseline promote <run-dir> --to <baseline-dir> [...]
rk baseline verify <baseline-dir|@name>
rk registry <list|resolve|add|remove> [args]
```

Each command:

- **`rk run`** — accepts a frozen spec; runs the alias-drift pre-check
  (re-resolves the model alias against the provider API and refuses
  with `AliasDriftError` on drift); invokes `harbor run` under the
  hood with the frozen spec. The run-dir layout, exit code semantics
  for harbor failures (exit 30 = harbor runtime failure), and JSON
  output for harbor-side errors pass through. Razorback adds the
  pre-check, `--allow-alias-drift` override, and the
  `provenance.yaml` + `spec.frozen.yaml` artifacts in the run-dir.
- **`rk freeze`** — resolve every dynamic input (model alias →
  provider-resolved version, image tag → digest, agent CLI →
  binary hash, prompt file → content hash, harbor version),
  write `<spec>.frozen.yaml` and `provenance.yaml` alongside.
  Refuses on any unresolved field unless `--allow-missing` is passed.
- **`rk diff`** — compare two harbor run-dirs paired by `(task,
  query, trial_index)`. Emits JSON with per-query deltas, per-arm
  Wilson CIs on pass@1, exact-McNemar p (per query, with
  family-wise correction across queries within a dataset and across
  datasets via Holm-Bonferroni at `--family-wise-alpha`), a paired
  bootstrap CI on the stratified delta (resampling at the cluster
  level per `--bootstrap-cluster`, default `query` since N trials of
  the same query are not independent observations), a
  power-at-fixed-N line, and an achieved-power-at-observed-effect
  line. `--alpha` sets the per-test confidence level;
  `--bootstrap-iters` sets B. Refuses when only one run has a seed
  set; paired comparisons require shared upstream conditions.
- **`rk runs list`** — list run-dirs under a root, optionally filtered
  by experiment. Emits JSON with paths, timestamps, and headline
  scores. **Defer to `harbor job list` if and when harbor ships one.**
- **`rk runs show`** — print a run's summary, per-task scores, trial
  counts. **Defer to `harbor job show` if and when harbor ships one.**

The optional commands ship when a consumer (an experiment-workflow
stage, a published research artifact) demands them. The experiment
workflow template's `conclude` stage uses `rk baseline promote` when
the project is configured for promotion; a project that does not run
baseline promotion treats `conclude` as a manual captain decision and
ships razorback without the optional `baseline`/`constraints`/`registry`
commands.

### 3.3 Stability promise

Razorback follows semver on two surfaces:

**Subcommand surface.** Inside a major version: no subcommand is
removed; no argument changes meaning; exit codes do not change; JSON
output fields are not removed (new fields may be added); human output
may change freely.

**Provenance freeze format.** `<spec>.frozen.yaml` and
`provenance.yaml` field names are stable within a major version. New
fields may be added; existing fields do not move or rename.

Workflow markdown pins razorback by major version (e.g.,
`razorback>=1,<2`), or by exact version for paper reproducibility.

### 3.4 Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic error |
| 2 | Usage / argument error |
| 10 | `SpecError` — spec validation failure |
| 11 | `ProvenanceError` — unresolved provenance field |
| 12 | `ConstraintViolation` — constraints check failed |
| 20 | `SeedMismatchError` — resume input hash mismatch |
| 21 | `AliasDriftError` — provider model alias resolved differently than frozen |
| 30 | Harbor runtime failure (passed through from `harbor run`) |

---

## 4. The spacedock-solver agent

### 4.1 Why razorback owns this class

Razorback ships exactly one custom harbor agent: `SpacedockSolverAgent`.
It exists because there is real adaptation work — knowing how to make
claude vs codex vs pi each behave as a spacedock first-officer is
runtime-specific glue that a spec author should not have to write
inline. Encapsulating that glue behind one parameterizable class lets
a workflow spec name the solver behavior once and pick the runtime
without rewriting the agent block.

The class is a **runtime adapter**. It does not contain solver logic.
Solver logic lives in the workflow README the class points at.

### 4.2 Spec shape

```yaml
agent:
  kind: spacedock_solver
  runtime: claude              # claude | codex | pi
  model: claude-opus-4-5       # provider-specific
  solver_workflow: ./solvers/dab-baseline-v3/   # workflow README dir
  max_turns: 200
  max_budget_usd: 10
  tools_allowed: []
  resume_from_freeze: <prior-run-dir>/trials/<task>-NNNN/logs_dir/agent_freeze/   # optional
```

### 4.3 Class responsibilities

1. **Runtime selection.** `runtime: claude` constructs harbor's
   `claude_code` agent inside the class with claude-shaped kwargs;
   `runtime: codex` constructs harbor's `codex` with codex-shaped
   kwargs; `runtime: pi` constructs harbor's `pi` with pi-shaped
   kwargs.
2. **Workspace bootstrap.** Copy the contents of `solver_workflow`
   into the trial workspace at a known path so the inner runtime's
   spacedock first-officer can discover and operate on it.
3. **Runtime configuration for spacedock.** For claude: set
   `skills_dir` to include the spacedock plugin; set
   `append_system_prompt` to "You are the first officer for the
   workflow at /workspace/solver/; begin the Startup procedure." For
   codex and pi: the equivalent per-runtime configuration. The class
   knows the mapping.
4. **Freeze-dir contract.** Expose `self.logs_dir / "agent_freeze/"`
   as the durable per-stage write surface. The workflow's mods commit
   into the embedded git at stage boundaries; the class does not write
   here itself.
5. **Sealed-hash refusal.** In `__init__`, before any harbor I/O,
   compute the sealed-input hash from `(model, sampling, solver_workflow
   content hash, prompt content hashes, spacedock skill version, harbor
   agent kwargs)`. If `resume_from_freeze` is set, read the prior run's
   sealed hash and refuse with `SeedMismatchError` if they differ.
6. **Resume mechanic.** If `resume_from_freeze` is set, restore the
   trial workspace from the freeze's embedded git before invoking the
   inner runtime. The inner runtime sees a workspace already in
   mid-workflow state and resumes.
7. **Phase-stats schema validation.** Surface
   `assert_phase_stats_schema(path)` for downstream consumers. The
   stats themselves are written by workflow mods, not by the class.

### 4.4 Halt-resume contract

Halt-resume is a three-party contract plus a documented consumer
surface:

- **The class** owns the sealed-hash check and the resume restore
  mechanic.
- **The workflow's mods** (provided by razorback as generic mods)
  write `phase_stats.json` and commit the workspace at stage
  boundaries.
- **The trial's `logs_dir/agent_freeze/`** is the on-disk surface
  shared between the class and the mods. It contains:
  - `.git/` — a private git repo holding workspace snapshots per stage
  - `phase_stats.json` — per-stage tokens/cost/wallclock
  - `sealed_hash.txt` — the sealed-input hash, written at first stage

Downstream consumers (`rk diff`, an experiment-workflow analyze stage)
read `phase_stats.json` and the trial's `result.json` to attribute
cost per stage. They are not part of the halt-resume contract itself.

`SpacedockSolverAgent` declares `per_trial_state_reset` accurately
based on its inner runtime's reset capability; harbor's docker
environment guarantees per-trial container resets which covers most of
the picture.

### 4.5 Registration with harbor

`SpacedockSolverAgent` registers with harbor via harbor's agent-plugin
discovery mechanism. The expected shape is a `pyproject.toml` entry-point
group that harbor scans at `harbor run` time; razorback's package
declares:

```toml
[project.entry-points."harbor.agents.installed"]
spacedock_solver = "razorback.agents.spacedock_solver:SpacedockSolverAgent"
```

Users write `agent.kind: spacedock_solver` in their spec and harbor
routes to razorback's class. No harbor monorepo PR is required.

**Open question.** The exact entry-point group name and registration
shape depends on harbor's published plugin contract. Razorback's
`harbor publish` / `cli/template-adapter` surface implies such a
mechanism exists, but the contract must be confirmed against the
pinned harbor version before implementation. **Fallback if no
plugin contract exists:** razorback's CLI grows a thin spec-translation
pre-pass (`rk run` rewrites `agent.kind: spacedock_solver` to
`agent.kind: claude_code` with appropriate kwargs, then invokes
`harbor run`). This trades the wire-through cleanness for keeping the
solver-agent abstraction owned by razorback.

---

## 5. Autoresearch workflow templates

Razorback ships two workflow README templates under
`docs/templates/`. Both are spacedock workflows. Operators instantiate
them per (research project, benchmark) by copying the template and
filling in project-specific fields.

### 5.1 Experiment workflow

**Purpose.** Owns one hypothesis's full lifecycle: propose a solver
variant, smoke-test it against a small slice, scale to a full run,
analyze the result against a baseline, and conclude (promote or
discard).

**Stages.**

| Stage | Owner | Action |
|-------|-------|--------|
| `pending` | captain | seeded entity; awaits captain greenlight |
| `propose` | operator | author or edit the solver-workflow README; `rk freeze` the spec; captain reviews the leak-guard constraint check; gate |
| `smoke` | operator | dispatch a run-workflow entity for a one-task subset; check against a tripwire; advance or fall back |
| `full` | operator | dispatch a run-workflow entity for the full benchmark slice at target N |
| `analyze` | operator | `rk diff` against the registered baseline; write a verdict |
| `conclude` | captain | promote the hypothesis as the new baseline (`rk baseline promote`, if configured) or discard; gate |

**Required mods.**

- **leak-guard** (static, at propose) — runs the constraint check
  that forbids solver-workflow READMEs from referencing answer-key
  files, ground-truth columns, or per-task hints the benchmark
  forbids. README-static; catches what the operator authors.
- **tool-deny-runtime** (runtime, wired into the spacedock-solver
  agent) — installs PreToolUse hooks that block the benchmark's
  per-benchmark forbidden tool set at execution time (e.g., for DAB,
  the `DISALLOWED_TOOLS` list from dataagentbench's reference
  implementation: `Bash(pip install datasets*)`,
  `Bash(pip install dataagentbench*)`,
  `Bash(huggingface-cli login*)`, and the rest of that list). Catches
  what the operator's static README cannot — an agent that decides
  mid-trial to download the reference dataset. Required alongside
  `leak-guard`; the two together provide static + runtime
  defense-in-depth.
- **baseline-compare** — at analyze, runs `rk diff` against the
  registered baseline run-dir and writes the result into the entity
  body.
- **cost-ceiling** — at smoke and full, refuses dispatch if the
  estimated run cost exceeds the per-experiment ceiling
  (`experiment.max_budget_usd`); maintains a running total across
  dispatched runs in the experiment so per-trial enforcement isn't
  the only guard. Refuses dispatch when the running total + the next
  run's estimate would exceed the ceiling.

**ID style.** sd-b32 (hypotheses run in parallel; reconcile without
coordination).

### 5.2 Run workflow

**Purpose.** Owns one harbor run's lifecycle: reconcile target trial
count against actual completions, dispatch make-up `harbor run`
invocations for shortfalls, mark completed or failed.

**Stages.**

| Stage | Owner | Action |
|-------|-------|--------|
| `pending` | operator | seeded by an experiment-workflow smoke/full stage |
| `reconciling` | operator | invoke `harbor run` on the assigned spec; check trial counts; loop until target reached or max-attempts exhausted |
| `completed` | terminal | target met |
| `failed` | terminal | max attempts exhausted; surface to captain |

**Required mods.**

- **stage-boundary-freeze** — fires on the spacedock-solver agent's
  stage-completion signal (when the workflow's operator commits a
  stage report); commits the agent's workspace to
  `logs_dir/agent_freeze/.git`.
- **phase-stats-writer** — at the same boundary, writes the stage's
  tokens/cost/wallclock to `logs_dir/agent_freeze/phase_stats.json`.

### 5.3 Solver workflow README contract

The solver workflow README is the artifact a `SpacedockSolverAgent`
loads via its `solver_workflow` parameter. Razorback does not ship
solver workflow READMEs — they are project-specific and live in the
research project's repo. Razorback specifies the contract:

- **Standard spacedock workflow README shape.** Stages, entity schema,
  mods. Spacedock skills consume it without modification.
- **A `## Stages` section.** Each stage's name is what the
  stage-boundary-freeze + phase-stats-writer mods key off.
- **A `## Leak guard` section.** Names the constraint file the
  experiment workflow's leak-guard mod uses to validate this README.
- **A `## Reset declaration` section.** Names which per-trial state
  surfaces (agent_container, compose_services, host_workspace) the
  solver workflow resets between trials.

Hypothesis variants are git diffs over this README plus its sibling
files. The autoresearch loop's propose stage produces a new directory
of (README + entities + mods) and points the next `SpacedockSolverAgent`
spec at it.

---

## 6. Spec format

A spec is a YAML file passed to `rk freeze` and then to `harbor run`.
The spec is razorback-extended where razorback adds value; the rest
passes through to harbor.

### 6.1 Top-level shape

```yaml
version: 1
experiment: dab-paper-reproduction
labels:
  hypothesis-id: hp-r41-7a2k
  workflow: experiment-workflow

provenance:
  pin_model_version: true
  pin_image_digest: true
  pin_agent_cli_hash: true
  pin_prompt_content: true

agent:
  kind: spacedock_solver
  runtime: claude
  model: claude-opus-4-5
  sampling:
    temperature: 0.0
  solver_workflow: ./solvers/dab-baseline-v3/
  max_turns: 200
  max_budget_usd: 10
  tools_allowed: []

benchmark:
  # passes through to harbor's task/dataset config
  dataset: dab
  tasks: [bookreview, agnews, crmarenapro]

environment:
  # passes through to harbor's environment config
  kind: docker

trials: 5
concurrency:
  trials: 4

experiment:
  max_budget_usd: 500           # cost-ceiling mod refuses dispatch beyond this
                                # across all runs in this experiment, not just
                                # per-trial

constraints:
  path: ./constraints/leak-guard.yaml
```

### 6.2 The `spacedock_solver` agent block

The agent block is razorback's contribution to the spec. Fields:

| Field | Type | Description |
|---|---|---|
| `kind` | const `spacedock_solver` | routes to razorback's agent class |
| `runtime` | enum `claude\|codex\|pi` | which inner harbor runtime to use |
| `model` | string | provider-specific model name |
| `sampling` | dict | temperature/seed/top_p as supported per runtime |
| `solver_workflow` | path | dir containing the solver workflow README + entities + mods |
| `max_turns` | int | per-trial turn budget |
| `max_budget_usd` | number | per-trial cost ceiling |
| `tools_allowed` | list[string] | allowlist passed to inner runtime |
| `resume_from_freeze` | path (optional) | a prior trial's freeze dir; triggers the resume path |

Razorback validates this block at `rk freeze` time and at spec → harbor
JobConfig translation time.

### 6.3 Validation

`rk freeze` runs spec validation as a side effect:

- The agent block is validated against razorback's pydantic schema
  for `spacedock_solver`.
- The `solver_workflow` path exists and contains a `README.md`.
- The `constraints` path exists and parses as the leak-guard format.
- All `prompt_file` paths exist and are readable.
- Every `provenance.pin_*: true` field has a corresponding resolvable
  input.

Other blocks (`benchmark`, `environment`, `trials`, `concurrency`)
pass through to harbor; harbor validates them at `harbor run` time.

---

## 7. Run-dir contract

Razorback adds two artifacts to the run-dir harbor produces; the rest
of the layout is harbor's.

### 7.1 Layout

```
<harbor-run-dir>/
├── (harbor's standard run-dir layout)
├── spec.frozen.yaml              # razorback writes at `rk freeze`
├── provenance.yaml               # razorback writes at `rk freeze`
└── trials/<task>-NNNN/
    ├── (harbor's standard trial layout)
    └── logs_dir/
        └── agent_freeze/         # SpacedockSolverAgent contract
            ├── .git/             # workspace snapshots per stage (mods write)
            ├── phase_stats.json  # per-stage tokens/cost/wallclock (mods write)
            └── sealed_hash.txt   # sealed-input hash (class writes at first stage)
```

`logs_dir/agent_freeze/` is the only razorback-owned subtree under
harbor's run-dir layout. Razorback does not modify harbor's `agent/`,
`verifier/`, or `artifacts/` subtrees.

### 7.2 `phase_stats.json`

```json
{
  "<stage-name-1>": {
    "tokens_in": N,
    "tokens_out": N,
    "tokens_reasoning": N,
    "tokens_cache_read": N,
    "tokens_cache_write": N,
    "cost_usd": F,
    "wallclock_s": F
  },
  "<stage-name-2>": {...},
  ...
}
```

Stage names match the solver workflow README's `## Stages` list. The
five token fields are required: `tokens_in` / `tokens_out` are the
visible-to-model accounting; `tokens_reasoning` distinguishes
thinking-mode reasoning tokens (which dominate cost on Opus and vary
10× across stages); `tokens_cache_read` and `tokens_cache_write`
track prompt-caching behavior. Cost-of-research analysis at the
$300-500 paper-reproduction budget requires this granularity to
attribute spend per stage and per token-type.

Razorback ships `assert_phase_stats_schema(path)` for downstream
validation.

### 7.3 Stability

`spec.frozen.yaml`, `provenance.yaml`, and `phase_stats.json` follow
the same stability promise as razorback's subcommand surface:
field-additive within a major version.

---

## 8. Inside razorback (implementation)

This section describes razorback's modules. Operators do not read it.

### 8.1 `rk run`: pass-through with alias-drift pre-check

`rk run` is a thin wrapper. It:

1. Reads the frozen spec.
2. Re-resolves the model alias against the provider API; refuses
   with `AliasDriftError` if the resolved version differs from
   `provenance.yaml.model_resolved_version` unless
   `--allow-alias-drift` is passed.
3. Invokes `harbor run` in-process (via harbor's Python API) or by
   subprocess (via the harbor CLI), passing the frozen spec through
   unchanged.
4. Surfaces harbor's exit code as-is (exit 30 reserved for harbor
   runtime failures; razorback's own exit codes do not collide).
5. Writes `spec.frozen.yaml` and `provenance.yaml` into the
   harbor-produced run-dir.

Implementation note: razorback does not own JobConfig construction
(that's harbor's responsibility for the kinds harbor recognizes).
Razorback's contribution to the run flow is the pre-check and the
provenance artifacts, both around `harbor run`, not inside it.

### 8.2 `rk freeze`: provenance resolution

`rk freeze` is the choke point. The resolver:

- Queries the provider API for the resolved model version string
  (e.g., `claude-opus-4-5` → `claude-opus-4-5-20251022`). Records into
  `provenance.yaml.model_resolved_version` with API timestamp.
- Calls `docker image inspect` to pin the image digest when
  `provenance.pin_image_digest: true`.
- Hashes the agent's CLI binary (`which claude`, `which codex`).
- Captures the consuming repo's git SHA into
  `provenance.yaml.harness_git_sha`.
- Pins the installed harbor version. Major-version drift between
  freeze and `harbor run` is a hard error.
- Reads every `prompt_file` reference, content-hashes, and pins.
- Reads `solver_workflow/README.md` (and sibling files), content-hashes
  recursively, and pins under `provenance.yaml.solver_workflow_hash`.

The resolver retries each external call with exponential backoff.
Hard failure (404 on the model name, image not pullable) refuses to
write the frozen spec.

At `harbor run` time, razorback's pre-run check re-resolves the model
version. If the provider returns a version that differs from the
frozen `model_resolved_version`, the check refuses with
`AliasDriftError` (exit code 21). Pass `--allow-alias-drift` to
override.

### 8.3 `rk diff`: paired statistics

`rk diff` reads both run-dirs' trial results, pairs trials by `(task,
query, trial_index)`, and computes:

- Per-arm, per-query Wilson 95% CI on pass@1 (level set by `--alpha`).
- Per-query exact-McNemar p, using exact binomial when discordant
  count is small. **Family-wise correction across queries within a
  dataset and across datasets via Holm-Bonferroni at
  `--family-wise-alpha`** (default 0.05); the JSON output carries
  both raw per-test p-values and the family-wise-adjusted p-values.
  Without this, a 12-dataset comparison at α=0.05 has family-wise
  error rate of roughly 46%; per-dataset "hypothesis X beats baseline
  on dataset Y" claims are uncitable without the adjustment.
- Paired bootstrap CI on the stratified delta (B set by
  `--bootstrap-iters`, default 10000, percentile method). **The
  bootstrap resamples at the cluster level specified by
  `--bootstrap-cluster` (default `query`).** N trials of the same
  query share prompt + model + environment + provider seed (where
  honored); resampling at the trial level treats correlated
  observations as independent and produces anti-conservatively narrow
  CIs. Resampling at the query level (cluster bootstrap) handles the
  intra-cluster correlation honestly.
- Power-at-fixed-N: the minimum detectable effect at α and 80% power
  for the given trials × queries.
- Achieved-power-at-observed-effect: the post-hoc power given the
  observed effect size, so null results can be interpreted as either
  "no effect" or "insufficient N".

At small N (DAB's local default is N=5), discordant counts of 1 or 2
are common and exact-McNemar p clusters near 1.0; the CIs and MDE
carry the signal that hypothesis tests miss at this N.

`rk diff` refuses when only one run has a seed set: a halt-resume
hypothesis paired against a fresh model-then-analyze baseline compares
two different upstream conditions even when sampling parameters match.
Both sides must share the same seed.

### 8.4 `SpacedockSolverAgent`: runtime adaptation

The class is structured as:

```
__init__(...):
    # 1. validate kwargs against pydantic schema
    # 2. compute sealed_hash from (model, sampling, solver_workflow content,
    #    prompts, spacedock skill version)
    # 3. if resume_from_freeze: read prior sealed_hash, refuse on mismatch
    # 4. construct the inner runtime adapter (claude_code, codex, pi) with
    #    per-runtime kwargs derived from self.runtime + self.kwargs

setup(env):
    # 1. workspace bootstrap: copy solver_workflow contents into the env
    # 2. if resume_from_freeze: git restore the workspace from the freeze
    # 3. write sealed_hash.txt to logs_dir/agent_freeze/
    # 4. delegate to inner.setup(env)

run():
    # delegate to inner.run() — the workflow mods do the rest

cleanup():
    # delegate to inner.cleanup()
```

Per-runtime adapter sub-modules (`_claude.py`, `_codex.py`, `_pi.py`)
hold the per-runtime kwarg construction. Each is ~50-100 LoC of
parameter translation.

### 8.5 Workflow templates and generic mods

The workflow README templates live as plain markdown under
`docs/templates/{experiment,run}-workflow/README.md`. Razorback's
`pyproject.toml` ships them as package data so they are accessible at
runtime for the captain to copy.

Generic mods live under `docs/templates/mods/`:

- `leak-guard.md` — at the propose stage, runs a static constraints
  check against the solver workflow README content and refuses on
  violation. Catches what the operator authors.
- `tool-deny-runtime.md` — wired into the spacedock-solver agent's
  PreToolUse hook config; blocks the benchmark's per-benchmark
  forbidden tool list at execution time. Catches what the operator's
  static README cannot — an agent that decides mid-trial to
  short-circuit the benchmark. Required alongside `leak-guard`.
- `baseline-compare.md` — at the analyze stage, runs `rk diff` and
  writes the result into the entity body.
- `cost-ceiling.md` — at smoke and full stages, maintains a running
  total of spent budget across all dispatched runs in the
  experiment; refuses dispatch when the running total + the next
  run's estimate would exceed `experiment.max_budget_usd`.
  Per-trial `max_budget_usd` is enforced by harbor's installed
  agent; the per-experiment ceiling is razorback's contribution.
- `stage-boundary-freeze.md` — fires when the solver-workflow's
  operator commits a stage report; commits the workspace.
- `phase-stats-writer.md` — fires at the same boundary; writes
  per-stage tokens (in/out/reasoning/cache-read/cache-write) +
  cost + wallclock.

Mods are spacedock-format markdown; razorback's contribution is the
specific mod content, not a new mod mechanism.

---

## 9. Risks and open questions

### 9.1 Harbor pre-1.0 churn

Harbor ships breaking field renames inside 0.x. Razorback's
`SpacedockSolverAgent` wraps harbor's installed agents, so changes to
those agents' constructor signatures or `BaseAgent.__init__`
parameters propagate.

Cost is bounded to razorback maintainers. Workflow markdown reads
razorback's CLI output and harbor's CLI output; a harbor field rename
touches razorback's per-runtime adapter sub-modules, not any workflow
prompt.

Realistic ongoing cost: 1-3 engineer-days per harbor minor for diff
audit and regression on the three installed-agent constructors
razorback wraps (claude_code, codex, pi). A CI matrix against pinned
harbor plus harbor HEAD surfaces drift before users encounter it.

Razorback pins harbor at a minor version; bumps follow harbor's
release cadence.

### 9.2 Harbor's agent-plugin discovery contract

`SpacedockSolverAgent` registers via `[project.entry-points."harbor.agents.installed"]`.
This is the documented harbor extension contract. If harbor changes the
entry-point group name or the registration shape, razorback's
`pyproject.toml` updates and the change propagates to users via a
razorback release.

### 9.3 Skills as a runtime-specific concept

Claude Code's `skills_dir` is the cleanest way to load spacedock as a
plugin. Codex and pi may not have a directly analogous mechanism; the
per-runtime adapter sub-module is the place that handles the
adaptation. For runtimes without skill-loading, the adapter falls back
to passing the spacedock plugin's full system-prompt content via
`append_system_prompt` or its equivalent.

### 9.4 Leak guard correctness

Razorback's leak guard is two-layered: `leak-guard` (static, at
propose) and `tool-deny-runtime` (runtime, wired into the
spacedock-solver agent's PreToolUse hooks). Both are required.

The static layer validates the solver workflow README's content
against a benchmark-specific constraints file (allow/deny lists for
file paths, banned section names, etc.). The runtime layer blocks
forbidden tool invocations during agent execution — `pip install
datasets`, `huggingface-cli login`, web fetches of the benchmark's
reference data, and the rest of the benchmark's `DISALLOWED_TOOLS`
list.

The static layer catches what the operator authors; the runtime
layer catches what the agent decides at execution time. Either alone
is insufficient — an agent under a clean static README can still
`pip install datasets` mid-trial; a benchmark with no static guard
relies entirely on runtime enforcement and can't catch
benchmark-name strings in the README's prompts.

The constraints file (static) and the DISALLOWED_TOOLS list (runtime)
are themselves benchmark-specific, written by the benchmark adapter
or the research project. Razorback provides the constraint format,
the validation runner, and the runtime PreToolUse hook config
schema. A wrong or incomplete constraints file or DISALLOWED_TOOLS
list lets information leak; this is a research-discipline concern,
not razorback's enforcement responsibility. Razorback's job is to
make both checks mechanical and refuse-able.

### 9.5 Provider non-determinism

Same prompt + same seed + same model alias does not always produce
identical output. Anthropic models do not honor seed; OpenAI honors it
sometimes. The frozen spec records the resolved model version; two
runs under the same frozen spec may differ. The DAB protocol's N=5
trials per query absorbs this; experiments at N=1 do not. `rk diff`'s
MDE-at-fixed-N output makes the absorption explicit.

### 9.6 Solver workflow halt-resume completeness

`SpacedockSolverAgent` commits the trial workspace at stage
boundaries. It does not commit external state (docker containers
outside the agent container, DB processes, host filesystem outside the
workspace). For benchmarks with stateless agent containers and
read-only inputs this is sufficient; for stateful benchmarks the
solver workflow's mods must rebuild external state on resume.

---

## 10. LoC estimate

| Component | LoC |
|---|---|
| CLI dispatch (Typer) | 150 |
| `rk run` (alias-drift pre-check + harbor pass-through) | 100-150 |
| `rk freeze` (provenance resolver) | 250-350 |
| `rk diff` (paired statistics) | 200-300 |
| `rk runs list/show` (until upstreamed) | 150-200 |
| `SpacedockSolverAgent` (class + per-runtime adapter sub-modules) | 300-500 |
| Pydantic schema for the spacedock_solver agent block | 80-120 |
| Tests (unit + integration) | 400-600 |
| Workflow README templates + mods | (markdown, not LoC) |

**Total: 1600-2400 LoC of Python** plus workflow templates and mod
markdown. Distributable as a `harbor-research` extension or as a
standalone `razorback` package.

---

## 11. Decision criteria

This design fits when:

- A research project drives hypothesis-driven benchmark experimentation
  with leak guards, baselines, and paired statistical comparisons.
- The benchmark target is a harbor-native adapter (one of harbor's
  catalog, or one the project publishes via `harbor publish`).
- The solver is a spacedock workflow definition, mutable per
  hypothesis, runnable across claude / codex / pi via a single agent
  spec.
- Workflow operators write bash; per-stage operations should be one
  command line.

Alternatives are worth considering when:

- A single benchmark is the only target and no second benchmark is
  anticipated — workflow-private Python helpers may be lighter than
  razorback.
- The research methodology does not need paired statistical comparison
  — harbor's `analyze` and `sweeps` may suffice alone.
- Halt-resume is not required — a vanilla `harbor run` with
  `claude_code` covers the case without razorback's agent class.
