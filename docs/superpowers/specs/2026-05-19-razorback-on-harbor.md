# Razorback: A Research-Stats Extension to Harbor

**Status:** Draft
**Date:** 2026-05-19

---

## 1. Introduction

### 1.1 What razorback is

Razorback makes agentic-benchmark research reproducible. You write a
spec, freeze its runtime inputs, run it against a harbor benchmark
adapter, read the score with confidence intervals, and audit the run
for leaks the runtime hooks missed. One `rk` CLI carries every stage;
one frozen spec carries every rerun.

Razorback ships a small Python tool (`rk`) and one custom harbor
agent: a multi-runtime spacedock-solver that drives a workflow
README through a benchmark task, with halt-and-resume across stage
boundaries. The initial CLI surface is `rk freeze`, `rk run`,
`rk score`, `rk audit`, plus run-directory navigation helpers.

Razorback is the smallest layer that turns a harbor benchmark run
into a publishable result. Everything above it (the autoresearch
loop, the hypothesis-lifecycle workflow, the baseline registry) is
research code in the consuming repo, built on this surface once the
goal-1 and goal-2 reproductions land.

### 1.2 Glossary

- **Harbor**: the agent-benchmark engine razorback consumes
  (`github.com/harbor-framework/harbor`). Owns job execution, the
  installed-agent catalog (claude_code, codex, pi, and ~20 others),
  the verifier framework, the environment framework, and its own CLI.
- **Spacedock**: the workflow framework razorback's solver agent
  loads as a plugin. An **operator** (an LLM-driven actor) runs
  against a markdown workflow definition.
- **Workflow README**: a markdown file that defines a spacedock
  workflow: its stages, entity schema, gates, mods, and per-stage
  behavior.
- **Solver workflow README**: the workflow README a
  `SpacedockSolverAgent` loads at trial start. Defines how the
  solver tackles one benchmark task. Lives in the consuming
  research repo; hypothesis variants are git diffs over it.
- **Trial**: one execution of one agent on one task.
- **Run**: one invocation of `rk run`; produces a run-directory
  containing many trials.
- **Hypothesis**: one entity in the autoresearch loop: a
  solver-workflow-README variant plus the experiments that test it.

### 1.3 Non-goals

- Razorback does not own the execution engine. Harbor does. `rk run`
  resolves the frozen spec and invokes `harbor run` underneath, so
  the operator sees one CLI surface (`rk *`) regardless of which
  layer does the work.
- Razorback is not a benchmark library. Benchmarks live in harbor's
  catalog as adapters publishable via `harbor publish`. Razorback
  ships no benchmark adapters.
- Razorback is not a workflow engine. Spacedock is. Razorback ships
  workflow README templates; the workflow semantics belong to
  spacedock.
- Razorback is not an LLM-trajectory analyzer. Harbor's `harbor
  analyze` (Claude-SDK-driven rubric scoring) and `harbor jobs
  summarize` cover qualitative critique; razorback's `rk score` and
  `rk audit` stay quantitative.

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
│   rk freeze              resolve and pin runtime provenance          │
│   rk run                 drift pre-check + budget gate, then         │
│                          pass-through to `harbor run`                │
│   rk score               Wilson CIs + stratified means               │
│   rk audit               post-hoc trajectory taint scan              │
│   rk runs list/show/cost run-dir and budget helpers                  │
│                                                                      │
│ Agent class:                                                         │
│   SpacedockSolverAgent   multi-runtime, halt-resume,                 │
│                          agent.kind: spacedock_solver                │
│                                                                      │
│ Workflow README templates (no mods at first):                        │
│   experiment-workflow/  run-workflow/                                │
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

Deferred: `rk diff` (paired statistics), adds when the autoresearch
loop's analyze stage needs paired comparison.

### 2.2 Where razorback sits

Razorback is the thin layer between a harbor benchmark run and a
publishable result. Harbor owns everything that produces trials;
razorback owns everything that turns trials into a defensible number.

Harbor's side: job execution, trial fan-out, the installed-agent
catalog, the verifier framework, the environment framework,
qualitative trajectory analysis, sweeps, the web viewer, the adapter
catalog. Razorback's side: pinning the runtime inputs so a rerun is
the same experiment (`rk freeze` + `rk run`'s drift refusal),
gating cost before the run burns budget, scoring with confidence
intervals (`rk score`), and auditing trajectories for leaks the
runtime hooks missed (`rk audit`). The spacedock-solver agent
(`agent.kind: spacedock_solver`) is razorback's only contribution
*inside* the trial, multi-runtime, halt-and-resume, README-driven.

A third-party adopter publishes their adapter via `harbor publish`,
then drives every rerun through `rk freeze; rk run; rk score`. They
reach for `rk audit` to confirm trajectories didn't bypass the
runtime leak hooks, and for the spacedock-solver agent when a
multi-stage README-driven solver is the right shape for the
benchmark.

---

## 3. The deterministic CLI surface

### 3.1 Design rules

- One subcommand, one purpose. Composite operations live in workflows.
- JSON by default. A `--format human` flag prints a table; workflow
  operators parse JSON.
- Idempotent where possible. Re-running `rk freeze` on a spec already
  frozen produces an identical output.
- No harbor types on the surface. Subcommand arguments, output, and
  exit codes use razorback's own shapes, never harbor's job-config
  classes, trial dataclasses, or internal enums.
- Stable exit codes. Each subcommand enumerates them; workflow
  operators branch on the codes.
- Path canonicalization. Commands that emit a spec for harbor to
  consume (`rk run`, the freeze writer) resolve `jobs_dir` to an
  absolute, symlink-resolved path before passing it to harbor. This
  ensures that `harbor jobs resume -p <run-dir>` and `harbor jobs
  resume` against the config resolve to the same directory; harbor's
  resume reads the config's `jobs_dir` to enumerate trial subdirs
  (`harbor/cli/jobs.py:1444-1477`), and a mismatch between the `-p`
  argument's on-disk location and the config's `jobs_dir` causes the
  resume to silently scan a different directory than the operator
  intended (see AC-0.5 probe at
  `docs/superpowers/plans/2026-05-19-harbor-resume-probe.md`,
  commit `1569853`, "Caveat from the first (invalid) attempt").
- The CLI is the operator's uniform surface. Subcommands that
  delegate to harbor (`rk run`) stay under `rk *` so the operator
  does not context-switch between two CLIs.

### 3.2 Subcommand surface

Surface that ships first (sufficient for one-sided reproduction
runs and establishing measurements):

```
rk run <frozen-spec.yaml>
rk freeze <spec.yaml>
rk score <run-dir> [--format markdown|json] [--alpha 0.05]
rk audit <run-dir> [--policy audit|strict] [--format markdown|json]
rk runs list [--root <dir>] [--experiment <name>]
rk runs show <run-dir>
rk runs cost <root>
```

Surface that ships when the autoresearch loop's analyze stage needs
paired hypothesis testing:

```
rk diff <run-a> <run-b> [--format markdown|json] [--alpha 0.05]
                       [--bootstrap-iters 10000] [--family-wise-alpha 0.05]
                       [--bootstrap-cluster query|trial]
```

Optional follow-ons, ship when consumer demand exists:

```
rk constraints check <spec.yaml> --constraints <path|@name>
rk baseline promote <run-dir> --to <baseline-dir> [...]
rk baseline verify <baseline-dir|@name>
rk registry <list|resolve|add|remove> [args]
```

Each command:

- **`rk freeze`**: resolve every dynamic input (model alias →
  provider-resolved version, image tag → digest, agent CLI →
  binary hash, prompt file → content hash, harbor version,
  spacedock skill version, solver-workflow content hash) and write
  `<spec>.frozen.yaml` + `provenance.yaml` alongside. Refuses on
  any unresolved field unless `--allow-missing` is passed.
- **`rk run`**: runs two pre-checks against the frozen spec, then
  invokes `harbor run`. The alias-drift check re-resolves the
  model alias and refuses with `AliasDriftError` on drift (override
  with `--allow-alias-drift`). The budget check reads
  `--max-budget-usd-running <file>`, adds this invocation's
  estimate, and refuses with `BudgetExceededError` (exit 22) if
  the total would exceed `experiment.max_budget_usd`; on completion
  it appends the actual cost to the running-total file. Razorback
  adds the two pre-checks and the `provenance.yaml` +
  `spec.frozen.yaml` artifacts in the run-dir; the run-dir layout,
  exit codes for harbor failures (exit 30), and JSON output for
  harbor-side errors pass through unchanged.
- **`rk score`**: read one run-dir's trial results, emit
  per-stratum pass@1 with Wilson 95% CI (level via `--alpha`) and
  the run's overall stratified mean per the adapter's stratum
  tagging. With `--against-constant <name=value>`, emits an
  inside-CI / outside-CI line per stratum, the paper-reproduction
  readout. No paired comparison; that's `rk diff`'s job.
- **`rk audit`**: post-hoc trajectory scanner. Walks a run-dir's
  trial traces (parent agent logs, subagent trace manifests,
  recursive subagent traces) and pattern-matches for forbidden
  behavior the runtime PreToolUse hooks missed: dataset-download
  shell commands (`curl`, `wget`, `pip install`, `npm install`),
  web-search tool calls (`web_search`, `web.run`), and the same
  patterns hidden inside heredoc bodies or `python -c` strings.
  Output: per-trial taint status (`clean` / `suspect` / `tainted`
  / `coverage_missing`) with findings, plus a run-level summary.
  `--policy strict` exits non-zero on any non-`clean` trial;
  `--policy audit` (default) reports without failing. Layer 3 of
  the leak-protection stack, layers 1 (propose-stage prompt +
  captain gate) and 2 (agent block `tools_denied`) are upstream
  of the run; this catches what they let through. See §9.4. Ports
  dataagentbench's `benchmark/lib/taint.py` mechanism with
  attribution.
- **`rk runs list`**: list run-dirs under a root, optionally
  filtered by experiment. Emits JSON with paths, timestamps, and
  headline scores. **Defer to `harbor job list` if and when harbor
  ships one.**
- **`rk runs show`**: print a run's summary, per-stratum scores,
  trial counts. **Defer to `harbor job show` if and when harbor
  ships one.**
- **`rk runs cost`**: read a directory of run-dirs and emit the
  cumulative cost across them. Pairs with `rk run
  --max-budget-usd-running <file>` for two-layer budget
  enforcement: the matrix dispatcher calls `rk runs cost` before
  each dispatch; `rk run` enforces the running total at invocation.
- **`rk diff`** *(ships later)*: compare two run-dirs paired by
  `(task, query, trial_index)`. Emits per-query Wilson CIs,
  family-wise-adjusted exact-McNemar p-values (Holm-Bonferroni at
  `--family-wise-alpha`), a paired bootstrap CI on the stratified
  delta resampling at the cluster level (`--bootstrap-cluster`,
  default `query`; `--bootstrap-iters` sets B), minimum-detectable
  effect at fixed N, and achieved power at observed effect.
  `--alpha` sets the per-test confidence level. Refuses when only
  one run has a seed set.

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
| 10 | `SpecError`, spec validation failure |
| 11 | `ProvenanceError`, unresolved provenance field |
| 12 | `ConstraintViolation`, constraints check failed |
| 20 | `SeedMismatchError`, resume input hash mismatch |
| 21 | `AliasDriftError`, provider model alias resolved differently than frozen |
| 22 | `BudgetExceededError`, `--max-budget-usd-running` running-total + estimate exceeds `experiment.max_budget_usd` |
| 23 | `TaintFindingsError`, `rk audit --policy strict` found at least one non-`clean` trial |
| 30 | Harbor runtime failure (passed through from `harbor run`) |

---

## 4. The spacedock-solver agent

### 4.1 Why razorback owns this class

Razorback ships exactly one custom harbor agent: `SpacedockSolverAgent`.
It exists because there is real adaptation work, knowing how to make
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
  resume_from_freeze: <prior-run-dir>/_razorback/freeze/<sealed_hash>/   # optional
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
4. **Freeze-dir contract.** Expose
   `<harbor-run-dir>/_razorback/freeze/<sealed_hash>/` as the durable
   per-stage write surface, resolved from the run-dir root rather than
   from `self.logs_dir`. The workflow's mods commit into the embedded
   git at stage boundaries; the class does not write here itself. This
   location lives outside harbor's per-trial scratch zone so it
   survives `harbor jobs resume`; see §4.4's "Harbor-resume
   interaction" and §7.1.
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
- **The run-dir's `_razorback/freeze/<sealed_hash>/`** is the on-disk
  surface shared between the class and the mods. It contains:
  - `.git/`, a private git repo holding workspace snapshots per stage
  - `phase_stats.json`, per-stage tokens/cost/wallclock
  - `sealed_hash.txt`, the sealed-input hash, written at first stage

Downstream consumers (`rk diff`, an experiment-workflow analyze stage)
read `phase_stats.json` and the trial's `result.json` to attribute
cost per stage. They are not part of the halt-resume contract itself.

`SpacedockSolverAgent` declares `per_trial_state_reset` accurately
based on its inner runtime's reset capability; harbor's docker
environment guarantees per-trial container resets which covers most of
the picture.

**Harbor-resume interaction.** `harbor jobs resume`
(`harbor/cli/jobs.py:1361-1430` → `harbor/job.py:_maybe_init_existing_job:192-228`)
rmtree's any trial directory that lacks `result.json` and re-runs the
trial under a freshly randomised `trial_name`
(`harbor/models/trial/config.py:213-222`). Razorback's freeze tree
therefore cannot live inside harbor's per-trial scratch zone: if a
`SpacedockSolverAgent` halts mid-trial (process killed, container
evicted, `harbor run` Ctrl-C'd) before `result.json` is written,
harbor's resume destroys the trial directory and every razorback file
under it, and the re-executed trial gets a new `trial_name` that
would not match any `trial_name`-keyed sibling store.

The mitigation: razorback writes the freeze tree to a sibling
directory **outside harbor's per-trial scratch zone**, keyed by
`sealed_hash` rather than `trial_name`. The freeze location is
`<harbor-run-dir>/_razorback/freeze/<sealed_hash>/` (see §7.1).
`sealed_hash` is the §4.3 + §8.4 sealed-input hash, identical across
the initial run and any subsequent `harbor jobs resume` because the
sealed inputs (model, sampling, solver_workflow content, prompts,
spacedock skill version, harbor agent kwargs) are read from
`spec.frozen.yaml`, which itself survives resume.

Consequences:

- **In-place resume of a halted trial is supported.** The re-executed
  trial recomputes `sealed_hash` from the unchanged `spec.frozen.yaml`,
  locates the existing freeze tree at the same path, and restores the
  workspace from its embedded `.git/` before invoking the inner
  runtime.
- **Cross-job `resume_from_freeze` is supported the same way.** The
  cross-job resume reads `<path>/sealed_hash.txt`, refuses on
  mismatch (`SeedMismatchError`, exit 20), and restores from
  `<path>/.git/` otherwise. The two resume mechanisms share the same
  freeze layout.
- **No partial-credit recovery on rmtree'd stages remains acceptable.**
  Stage commits are written to `_razorback/freeze/<sealed_hash>/`
  immediately as the freeze mod produces them, so per-stage cost
  attribution survives the rmtree even though the trial's `agent/`
  subtree does not.

Empirically verified by AC-0.5's probe at
`docs/superpowers/plans/2026-05-19-harbor-resume-probe.md`
(commit `1569853`).

### 4.5 Registration with harbor

`SpacedockSolverAgent` registers with harbor via harbor's
**`import_path` dispatch mechanism** (`harbor/agents/factory.py:95-133`,
`AgentFactory.create_agent_from_import_path`). Harbor does **not**
enumerate setuptools / PEP-621 entry-point groups for agents; the
dispatch surface is a Python dotted import-path string on the harbor
`JobConfig`. Specifically, `AgentConfig.import_path: "module.path:ClassName"`
(`harbor/models/trial/config.py:44-63`) names the class harbor loads
and instantiates per trial. The class must subclass
`harbor.agents.base.BaseAgent` and implement `name()`, `version()`,
`setup()`, `run()`.

Razorback's `rk run` is a thin **spec translator**. It rewrites
razorback's spec.yaml shape into a harbor `JobConfig`:

- razorback's singular `agent: { kind: spacedock_solver, ... }` block
  becomes harbor's plural
  `agents: [{ import_path: "razorback.agents.spacedock_solver:SpacedockSolverAgent", kwargs: { ... } }]`.
- razorback-only fields on the agent block (`model`, `sampling`,
  `solver_workflow`, `tools_allowed`, `tools_denied`, etc.) flow
  through harbor's `AgentConfig.kwargs` dict, which `AgentFactory`
  splats into the class constructor (`harbor/agents/factory.py:161,170`).

No setuptools entry-point declaration is needed in razorback's
`pyproject.toml`. Harbor finds `SpacedockSolverAgent` by import path
because razorback's package is installed into the same Python
environment as harbor; harbor calls `importlib.import_module` against
the `module.path` half of `import_path` and `getattr`s the `ClassName`
half (`harbor/agents/factory.py:95-133`).

Empirically verified by AC-0.2's probe at
`docs/superpowers/plans/2026-05-19-harbor-entry-point-probe.md`
("Agent dispatch probe" section): an external pip-installed package
with `import_path: probe_agent:ProbeAgent` had its `setup()` and
`run()` invoked by harbor without any entry-point declaration in the
package's `pyproject.toml`.

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
| `propose` | operator | author or edit the solver-workflow README; `rk freeze` the spec; captain reviews at the gate (the propose-stage prompt instructs the operator on what the README must not reference, answer-key files, ground-truth columns, per-task hints the benchmark forbids, and the captain's gate review confirms) |
| `smoke` | operator | check the running cost via `rk runs cost <root>` against `experiment.max_budget_usd`, refuse dispatch on overrun; dispatch a run-workflow entity for a one-task subset; check against a tripwire; advance or fall back |
| `full` | operator | same cost check as `smoke`; dispatch a run-workflow entity for the full benchmark slice at target N |
| `analyze` | operator | run `rk score --against-constant <baseline-headline>` (first-ship) or `rk diff <baseline-run> <this-run>` (when available); paste the output into the entity body and write a verdict |
| `conclude` | captain | promote the hypothesis as the new baseline (`rk baseline promote`, if configured) or discard; gate |

**Required mods.** None ship from razorback in the first cut. The
stage-level enforcement described above lives in per-stage prompt
content (what the operator-ensign is told to do at each stage) and
captain gate reviews, not in razorback-shipped mods. Runtime leak
guarding lives on the agent block via `tools_denied` (see §6.2);
per-experiment cost enforcement lives in the `rk run
--max-budget-usd-running <file>` flag invoked by the matrix
dispatcher and by the smoke/full stage prompts.

Halt-resume-related mods (`stage-boundary-freeze`,
`phase-stats-writer`) ship when halt-resume hypothesis testing
arrives as a consumer; the run workflow's initial shape (§5.2)
does not require them.

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

**Required mods.** None in the first cut. The mods that fire on the
spacedock-solver agent's stage-completion signal
(`stage-boundary-freeze` for workspace `git commit`,
`phase-stats-writer` for `phase_stats.json`) are halt-resume +
per-stage-cost-attribution machinery. They ship when those use cases
have consumers, halt-resume hypothesis testing for the freeze mod,
multi-stage solver workflows for the phase-stats mod. Goals 1+2 run
single straight-through solves; neither use case fires for them.

### 5.3 Solver workflow README contract

The solver workflow README is the artifact a `SpacedockSolverAgent`
loads via its `solver_workflow` parameter. Razorback does not ship
solver workflow READMEs, they are project-specific and live in the
research project's repo. Razorback specifies the contract:

- **Standard spacedock workflow README shape.** Stages, entity
  schema, mods. Spacedock skills consume it without modification.
- **A `## Stages` section.** Stage names become the keys the
  halt-resume freeze and per-stage cost attribution mechanisms use
  when those ship (deferred per §5.2).
- **A `## Reset declaration` section.** Names which per-trial state
  surfaces (agent_container, compose_services, host_workspace) the
  solver workflow resets between trials.
- **No leak-guard `## Leak guard` section required.** Leak
  prevention is split between the agent block's `tools_denied`
  field (runtime PreToolUse blocking; see §6.2) and the
  experiment-workflow propose stage's prompt + captain gate review
  (static check on README content). Neither requires a section in
  the solver workflow README itself.

Hypothesis variants are git diffs over this README plus its sibling
files. The autoresearch loop's propose stage produces a new
directory of (README + entities + sibling files) and points the next
`SpacedockSolverAgent` spec at it.

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
  max_budget_usd: 500           # `rk run --max-budget-usd-running <file>` refuses
                                # dispatch when the file's running-total + this
                                # invocation's estimate would exceed the ceiling.
                                # Captain-driven matrix dispatchers pass the
                                # same file across all invocations in the
                                # experiment.
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
| `tools_denied` | list[string] | denylist installed as PreToolUse hooks in the inner runtime (e.g., for DAB, the verbatim `DISALLOWED_TOOLS` list from dataagentbench's reference implementation: `Bash(pip install datasets*)`, `Bash(pip install dataagentbench*)`, `Bash(huggingface-cli login*)`, and the rest). The benchmark adapter publishes a recommended list as documentation; the captain pastes it into the spec. Required for goal-1 defensibility. |
| `resume_from_freeze` | path (optional) | a prior trial's freeze dir; triggers the resume path |

Razorback validates this block at `rk freeze` time and at spec → harbor
JobConfig translation time.

### 6.3 Validation

`rk freeze` runs spec validation as a side effect:

- The agent block is validated against razorback's pydantic schema
  for `spacedock_solver`.
- The `solver_workflow` path exists and contains a `README.md`.
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
├── trials/<task>-NNNN__<uuid7>/  # harbor owns; rmtree'd on resume if incomplete
│   └── (harbor's standard trial layout — razorback never writes here)
├── spec.frozen.yaml              # razorback writes at `rk freeze`
├── provenance.yaml               # razorback writes at `rk freeze`
└── _razorback/                   # razorback's sibling directory; harbor never touches
    └── freeze/
        └── <sealed_hash>/        # SpacedockSolverAgent contract; survives `harbor jobs resume`
            ├── .git/             # workspace snapshots per stage (mods write)
            ├── phase_stats.json  # per-stage tokens/cost/wallclock (mods write)
            └── sealed_hash.txt   # sealed-input hash (class writes at first stage)
```

`_razorback/freeze/<sealed_hash>/` is the only razorback-owned subtree
under harbor's run-dir layout. It lives **outside** harbor's
`trials/<name>/` so that `harbor jobs resume`'s rmtree of incomplete
trials (`harbor/job.py:_maybe_init_existing_job:192-228`) cannot
destroy the freeze tree. The directory is keyed by `sealed_hash` (the
§4.3 + §8.4 sealed-input hash) rather than by `trial_name`, because
`harbor jobs resume` regenerates `trial_name` for re-executed trials
(`harbor/models/trial/config.py:213-222`); `sealed_hash` is derived
from `spec.frozen.yaml`, which itself survives resume, so the same
freeze tree is addressable by the re-executed agent instance. See
§4.4's "Harbor-resume interaction" subsection for the empirical
basis (AC-0.5 probe at
`docs/superpowers/plans/2026-05-19-harbor-resume-probe.md`,
commit `1569853`). Razorback does not modify harbor's `trials/`,
`agent/`, `verifier/`, or `artifacts/` subtrees.

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
2. Canonicalizes the frozen spec's `jobs_dir` to an absolute,
   symlink-resolved path (`Path(jobs_dir).expanduser().resolve()`)
   before invoking harbor. This keeps `harbor jobs resume -p
   <run-dir>` and `harbor jobs resume` against the config in
   agreement on which directory to scan. See §3.1 design-rule on
   path canonicalization.
3. Re-resolves the model alias against the provider API; refuses
   with `AliasDriftError` if the resolved version differs from
   `provenance.yaml.model_resolved_version` unless
   `--allow-alias-drift` is passed.
4. Invokes `harbor run` in-process (via harbor's Python API) or by
   subprocess (via the harbor CLI), passing the frozen spec through
   unchanged.
5. Surfaces harbor's exit code as-is (exit 30 reserved for harbor
   runtime failures; razorback's own exit codes do not collide).
6. Writes `spec.frozen.yaml` and `provenance.yaml` into the
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

### 8.3a `rk score`: single-run statistical readout (ships first)

`rk score` reads one run-dir's trial results, groups by stratum
(typically dataset), and emits:

- Per-stratum pass@1 with Wilson 95% CI (level via `--alpha`).
- Overall stratified pass@1 (the macro-average across strata per the
  adapter's tagging).
- Trial counts per stratum (with errored-vs-completed distinction,
  honoring the AC-4.4 counting contract).
- A "matches-published-constant" line per stratum when invoked with
  `--against-constant <name=value>` (the paper-reproduction case
  uses this to check whether the published 0.577/0.4376 numbers fall
  within the run's CI on the matching stratification).

Implementation is small: Wilson CI plus the stratified-mean reducer
the adapter's stratum tags feed into. No paired-bootstrap, no
McNemar, no family-wise correction, those are paired-comparison
machinery and live in `rk diff` (ships later).

### 8.3 `rk diff`: paired statistics (ships later)

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
    # 3. write sealed_hash.txt to <run-dir>/_razorback/freeze/<sealed_hash>/
    # 4. delegate to inner.setup(env)

run():
    # delegate to inner.run(), the workflow mods do the rest

cleanup():
    # delegate to inner.cleanup()
```

Per-runtime adapter sub-modules (`_claude.py`, `_codex.py`, `_pi.py`)
hold the per-runtime kwarg construction. Each is ~50-100 LoC of
parameter translation.

### 8.5 Workflow templates (no initial mods)

The two workflow README templates live as plain markdown under
`docs/templates/{experiment,run}-workflow/README.md`. Razorback's
`pyproject.toml` ships them as package data so they are accessible
at runtime for the captain to copy.

**Razorback ships no mods in the first cut.** The stage-level
behavior the workflows depend on lives in:

- **Per-stage prompt content** in the workflow README itself,
  what the operator-ensign at each stage is instructed to do (run
  `rk freeze`, run `rk score --against-constant`, check
  `rk runs cost <root>` against `experiment.max_budget_usd`, paste
  output into the entity body, etc.).
- **Captain gate reviews** at gated stages (propose, conclude).
- **The agent block's `tools_denied` field** (§6.2) for runtime
  PreToolUse leak guarding.
- **The `rk run --max-budget-usd-running <file>` flag** (§8.1) for
  per-experiment running-budget enforcement.

The six mods the prior design described (`leak-guard`,
`tool-deny-runtime`, `baseline-compare`, `cost-ceiling`,
`stage-boundary-freeze`, `phase-stats-writer`) each collapsed into
one of the above mechanisms or deferred:

- `leak-guard`, `tool-deny-runtime`, `baseline-compare`,
  `cost-ceiling` collapsed into prompt content + spec block field
  + CLI flag. Razorback owns the CLI surface and the spec, so
  per-stage references to either are inline rather than mod-wrapped.
- `stage-boundary-freeze` and `phase-stats-writer` defer with
  halt-resume and multi-stage solvers as their consumers; both fire
  only inside trials that have internal stage boundaries, which
  goals 1+2 do not.

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

`SpacedockSolverAgent` registers via harbor's `AgentConfig.import_path`
dispatch (`harbor/agents/factory.py:95-133`). The dispatch surface is
not setuptools entry-point groups — `rk run` emits a harbor
`JobConfig` with
`agents: [{ import_path: "razorback.agents.spacedock_solver:SpacedockSolverAgent", kwargs: {...} }]`
and harbor's `AgentFactory` resolves the class by Python import. If
harbor changes its `AgentConfig` schema or its factory's resolution
shape, razorback's `rk run` translator updates and the change
propagates to users via a razorback release. No razorback
`pyproject.toml` entry-point declaration exists or is needed; see
§4.5 for the mechanism and AC-0.2's probe doc for empirical
verification.

### 9.3 Skills as a runtime-specific concept

Claude Code's `skills_dir` is the cleanest way to load spacedock as a
plugin. Codex and pi may not have a directly analogous mechanism; the
per-runtime adapter sub-module is the place that handles the
adaptation. For runtimes without skill-loading, the adapter falls back
to passing the spacedock plugin's full system-prompt content via
`append_system_prompt` or its equivalent.

### 9.4 Leak guard correctness

Razorback's leak guard is three-layered. All three are required for
goal-1-grade defensibility.

**Layer 1, static (propose-stage prompt + captain gate).** The
operator-ensign at the experiment workflow's propose stage is
instructed not to reference forbidden things in the solver workflow
README (answer-key files, ground-truth columns, per-task hints the
benchmark forbids). The captain reviews at the propose gate before
the README ships to a frozen spec. Catches authored leaks in the
workflow definition.

**Layer 2, runtime (`tools_denied` PreToolUse hooks).** The agent
block's `tools_denied` field (§6.2) installs PreToolUse hooks in
the inner runtime that block matching tool invocations at
execution time. Catches the case where an agent under a clean
README decides mid-trial to `pip install datasets` or fetch the
benchmark's reference data. Benchmark adapters publish a
recommended `tools_denied` list (e.g., for DAB, the verbatim
`DISALLOWED_TOOLS` list from dataagentbench's reference impl) as
documentation; the captain pastes it into the spec.

**Layer 3, post-hoc (`rk audit`).** Wraps a port of
dataagentbench's `benchmark/lib/taint.py` mechanism. After a trial
completes, walks the recorded traces (parent log, subagent trace
manifest, recursive subagent traces) and pattern-matches against
forbidden shell commands, forbidden tool calls, heredoc bodies,
and `python -c` invocations. Catches three classes of leak that
Layer 2 misses by design:

1. **Subagent escape.** Layer 2 hooks the parent agent; a subagent
   spawned via `claude-team` or the Agent tool may not inherit the
   parent's PreToolUse config. The post-hoc scan walks subagent
   traces.
2. **Heredoc / `python -c` masking.** Layer 2 matches against the
   `Bash` tool's `command` field; an agent that submits
   `python -c "import subprocess; subprocess.run(['pip','install','datasets'])"`
   doesn't match `Bash(pip install datasets*)` at PreToolUse time.
   The post-hoc scan tokenizes Python bodies and heredocs and
   pattern-matches inside them.
3. **Hook-config drift.** If the captain forgets `tools_denied` in
   one of the 180 matrix cells, Layer 2 is silently absent for
   that cell. The post-hoc scan catches the omission.

The matrix dispatcher runs `rk audit --policy strict` after each
cell completes; tainted cells get re-run or excluded from the
final readout. `rk score`'s output documents which trials were
excluded for taint so the readout's denominators are honest.

The taint patterns (forbidden shell commands, forbidden tool
calls, etc.) are themselves benchmark-specific. The benchmark
adapter publishes them alongside the recommended `tools_denied`
list. Razorback provides the scanning runner, the pattern format,
and the per-trial verdict mechanics; benchmark-specific rules
remain a research-discipline concern.

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

| Component | LoC | Ordering |
|---|---|---|
| CLI dispatch (Typer) | 150 | first |
| `rk run` (alias-drift pre-check + harbor pass-through + `--max-budget-usd-running`) | 150-200 | first |
| `rk freeze` (provenance resolver) | 250-350 | first |
| `rk score` (per-stratum Wilson CI + stratified mean + constant-check) | 80-120 | first |
| `rk audit` (port of dataagentbench `taint.py` with attribution; pattern-matching across shell / heredoc / python-c / subagent traces) | 500-600 | first |
| `rk runs list/show/cost` (until upstreamed) | 200-250 | first |
| `SpacedockSolverAgent` (class + per-runtime adapter sub-modules) | 300-500 | first |
| Pydantic schema for the spacedock_solver agent block (incl. `tools_denied`) | 100-140 | first |
| Tests (unit + integration; includes `rk audit` fixtures) | 600-800 | first |
| Workflow README templates (no razorback-shipped mods initial) | (markdown) | first (after goal-1/2 runs) |
| `rk diff` (paired statistics) | 200-300 | later (when autoresearch loop needs paired stats) |

**First-ship total: ~2400-3100 LoC of Python** + workflow
templates. The increase over the prior estimate is `rk audit`
(Layer 3 leak protection ported from dataagentbench's `taint.py`).
**Adds later:** ~200-300 LoC for `rk diff`'s paired-comparison
machinery when the autoresearch loop's analyze stage needs it. Distributable as a `harbor-research` extension or as a
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
  anticipated, workflow-private Python helpers may be lighter than
  razorback.
- The research methodology does not need paired statistical comparison
 , harbor's `analyze` and `sweeps` may suffice alone.
- Halt-resume is not required, a vanilla `harbor run` with
  `claude_code` covers the case without razorback's agent class.
