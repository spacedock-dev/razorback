# `hm` design — do-nothing comparison + alternative-tools survey

**Purpose.** Before captain approval of the `hm` proposal (`kind: harbor`
benchmark block + `rk research new` scaffold + `_build_harbor` translator
+ per-variant plugin escape), this report asks the inverse question: what
would Aanya (Scenario A — dabstep) and Ben (Scenario B — swe-bench-verified)
get if razorback ships nothing and they reach for the next-best tool?

**Method.** Read-only investigation. Source-pinned where I can run code
(harbor's vendored CLI in `.venv`), URL-pinned for external tools.

**Doc under comparison.**
`docs/superpowers/specs/2026-05-23-generic-harbor-benchmark-surface.md`
@ commit `cca7608`.

---

## Raw harbor — what's possible today

I probed `harbor` 1.x as vendored at
`/Users/clkao/git/razorback/.venv/lib/python3.12/site-packages/harbor/`
(CLI binary at `.venv/bin/harbor`). Findings are anchored to file:line
in that copy.

### Top-level surface (`harbor --help`)

`harbor` ships 17 top-level subcommands (verbatim from `harbor --help`):
`check`, `analyze`, `init`, `run`, `publish`, `upload`, `add`,
`download`, `remove`, `sync`, `view`, `adapter`, `task`, `dataset`,
`job`, `trial`, `cache`, `auth`.

Relevant subset for our two scenarios:

- **`harbor run`** — alias for `harbor job start`. The function is
  `start()` at `.venv/.../harbor/cli/jobs.py:471-1361`. Carries 40+
  flags across panels `Config / Job Settings / Agent / Environment /
  Dataset / Harbor Hub`.
  - `--dataset / -d <name@version>` (jobs.py:831-840) for a registry
    dataset.
  - `--task / -t <org/name>` (jobs.py:859-868) for a single task ref.
  - `--path / -p <local>` (jobs.py:804-813) for a local task dir.
  - `--task-git-url` + `--task-git-commit` (jobs.py:814-830) for a
    raw repo task.
  - `--include-task-name / -i` glob, `--exclude-task-name / -x` glob,
    `--n-tasks / -l N` (jobs.py:869-898) — what razorback's `tasks:` /
    `exclude_tasks:` / CLI `--n-tasks` map onto.
  - `--agent / -a <oracle|claude-code|terminus-2|aider|codex|cursor-cli
    |mini-swe-agent|swe-agent|...>` + `--agent-import-path` for a
    custom agent class.
  - `--model / -m`, `--ak/--agent-kwarg key=value`, `--ae/--agent-env`.
  - `--env / -e <docker|daytona|e2b|modal|runloop|gke|apple-container|
    singularity|islo|tensorlake>`.
  - `--n-concurrent / -n`, `--max-retries / -r`,
    `--retry-include`/`--retry-exclude` exception filters.
  - `--upload --public/--private --share-org --share-user` to push the
    finished job to Harbor Hub for browser viewing.

- **`harbor dataset list / download / init / visibility`**. Download
  shape: `harbor dataset download <name>@<version> [-o <dir>] [--cache|
  --export] [--overwrite]`. Default behavior is `export` mode to CWD;
  `--cache` writes to `~/.cache/harbor/tasks` content-addressed
  (verbatim from `harbor dataset download --help`).

- **`harbor analyze <job-or-trial-dir>`** — runs an LLM-grader pass
  (default model `haiku`) over each trial trajectory, writes
  `analysis.json` per trial. Rubric defaults to a built-in
  `(reward_hacking, task_specification)` template; researcher can pass
  `--rubric <toml|yaml|json>` and `--prompt <file>` for a custom
  evaluator. `--passing` / `--failing` / `--overwrite` flags exist. The
  implementation entrypoint is `analyzer.analyze_job` at
  `.venv/.../harbor/analyze/analyzer.py:186`.

- **`harbor job summarize [job_dir]`** — uses Claude Agent SDK to
  summarize trial failures (jobs.py:1538-1557). NLP summary, not
  statistical aggregation.

- **`harbor job resume <job_dir>`** — restart a partially-completed job
  (jobs.py:1362).

- **`harbor view`** — launches a local web viewer for trajectories.

- **`harbor init <name> --task | --dataset`** — scaffolds a NEW
  benchmark task or dataset (the author surface, not the consumer
  surface). Writes `task.toml` + `solution.sh` + `tests/` if `--task`;
  writes `dataset.toml` + metric template if `--dataset`. Not a
  researcher project scaffold — there is no `harbor consumer init` or
  equivalent.

### Per-job lifecycle artifacts

From `harbor.job.Job` (`.venv/.../harbor/job.py:340-360`):

- `<jobs_dir>/<job_name>/config.json` — the resolved `JobConfig`.
- `<jobs_dir>/<job_name>/result.json` — the rolled-up `JobResult`
  carrying `JobStats` (from `harbor/models/job/result.py:28-150`).
- `<jobs_dir>/<job_name>/job.log`.
- `<jobs_dir>/<job_name>/<lock>` (LOCK_FILENAME).
- Per-trial directories under the job dir (one per task × attempt),
  each with the agent trace, environment artifacts, verifier output.

`JobStats` (`.venv/.../harbor/models/job/result.py:28-42`) carries:
`n_completed_trials`, `n_errored_trials`, `n_running_trials`,
`n_pending_trials`, `n_cancelled_trials`, `n_retries`,
`evals: dict[str, AgentDatasetStats]`, `n_input_tokens`,
`n_cache_tokens`, `n_output_tokens`, `cost_usd`.

`AgentDatasetStats` (lines 15-26) carries `n_trials`, `n_errors`,
`metrics: list[dict]`, `pass_at_k: dict[int, float]`, `reward_stats`,
`exception_stats`.

So `pass_at_k` and `cost_usd` come for free per job. No paired
bootstrap, no confidence interval, no stratified pass@1, no
against-constant verdict.

### No autoresearch loop scaffolding

Verified by reading the `harbor` CLI surface: there is no
`harbor research new`, no `harbor freeze`, no `harbor score
--against-constant`, no `harbor diff <run-a> <run-b>`, no
`harbor experiment / hypothesis` command. The `init` command scaffolds
**task or dataset authoring** (the publisher side), not a researcher's
hypothesis-iteration project. There is no `hypotheses/` directory
convention, no `paper_baseline` constant tracking, no
`solver_workflows/` template, no `runs/_budget.json` cumulative-cost
cap, no `--ordering-hints` for tail-latency dropoff.

### Aanya with raw harbor only

She'd run, in this order:

```bash
# 1. Install harbor
$ pipx install harbor   # (or: pip install harbor-benchmark)

# 2. Configure Anthropic credentials
$ export ANTHROPIC_API_KEY=sk-...

# 3. Smoke run (5 tasks of dabstep, claude-haiku-4-5, docker env)
$ harbor run \
    --dataset adyen/dabstep@latest \
    --agent claude-code \
    --model claude-haiku-4-5 \
    --n-tasks 5 \
    --n-concurrent 4 \
    --jobs-dir ~/dabstep-runs \
    --job-name dabstep-haiku-smoke
# → writes ~/dabstep-runs/dabstep-haiku-smoke/{config.json,
#   result.json, job.log, <trial-dirs>/...}

# 4. Read pass_at_k from result.json
$ jq '.stats.evals' ~/dabstep-runs/dabstep-haiku-smoke/result.json
# → AgentDatasetStats with pass_at_k[1] = 0.40 (2/5), cost_usd = ~0.15

# 5. Compare to paper baseline (0.476) — by hand
$ echo "0.40 < 0.476 — below; CI wide at N=5"  # she does the math herself

# 6. Full run (no --n-tasks)
$ harbor run \
    --dataset adyen/dabstep@latest \
    --agent claude-code --model claude-haiku-4-5 \
    --n-concurrent 4 \
    --jobs-dir ~/dabstep-runs \
    --job-name dabstep-haiku-full
# → ~$5 spent (no pre-dispatch budget cap; only cost_usd after-the-fact),
#   pass_at_k[1] = 0.412

# 7. First hypothesis variant.
#    There is no spec file to copy, no solver_workflows/baseline
#    directory shipped by harbor. She must construct the variant by
#    either passing a different prompt template via --agent-kwarg
#    prompt_template=<path>, or writing a custom agent import path
#    and registering it via --agent-import-path my.module:MyAgent.
$ harbor run \
    --dataset adyen/dabstep@latest \
    --agent claude-code --model claude-haiku-4-5 \
    --ak prompt_template=~/dabstep-runs/prompts/duckdb-cheatsheet.md \
    --jobs-dir ~/dabstep-runs --job-name dabstep-haiku-h0001

# 8. Compare h0001 vs baseline.
#    Harbor has no `harbor diff` — she writes a Python script that
#    reads both result.json files, walks per-task rewards from
#    AgentDatasetStats.reward_stats, and computes her own paired
#    bootstrap CI.
$ python -m my_analysis paired \
    ~/dabstep-runs/dabstep-haiku-full/result.json \
    ~/dabstep-runs/dabstep-haiku-h0001/result.json
```

What she's MISSING that `hm` provides:

- **No project scaffold.** No `~/dabstep-research/{specs,solver_workflows,
  hypotheses,runs}/` layout. No `README.md` teaching the loop. No
  `razorback-research.toml`. She invents directory conventions.
- **No spec file.** Every flag goes on each invocation; her
  invocations drift across attempts. The frozen-spec + sealed-hash
  reproducibility contract (`rk freeze`, razorback's
  `solver_workflow_content_hash` recursive hash) is absent. Two runs
  with "the same" config are not provably identical.
- **No pre-dispatch budget cap.** `cost_usd` is reported AFTER the job
  finishes. `--max-budget-usd-running runs/_budget.json` doesn't exist.
  For Aanya's $5 run this is annoying; for Ben's $5400 run it's a
  $6000-overrun-risk.
- **No `paper_baseline` constant.** She hand-computes the verdict each
  time. No place for the spec to record "vs paper=0.476".
- **No paired-test primitive.** She rolls her own bootstrap.
- **No solver-workflow content hash.** When she edits her workflow
  README, nothing forces a new run-dir name; results commingle
  silently.
- **No `--ordering-hints`** tail-latency optimization.

What she GETS for free that `hm` doesn't add value on top of:

- Dataset resolution (`adyen/dabstep@latest`). The `hm` design
  re-exposes this verbatim; razorback adds nothing here except the
  spec-block wrapper.
- Container env management (docker / daytona / e2b / modal / ...).
- Per-trial trajectory capture + LLM-grader pass (`harbor analyze`).
- Job resume (`harbor job resume`).
- Trajectory browser (`harbor view`).
- `cost_usd` rollup.
- Concurrency, retries, timeout multipliers.

### Ben with raw harbor only

```bash
$ export ANTHROPIC_API_KEY=...
$ harbor run \
    --dataset swe-bench/swe-bench-verified@latest \
    --agent claude-code \
    --model claude-opus-4-7 \
    --n-tasks 10 \
    --n-concurrent 4 \
    --jobs-dir ~/swe-bench-runs \
    --job-name swe-bench-opus-smoke
# (same shape as Aanya's; differences are all on the dataset side —
#  longer per-task wallclock, ~$25 spend for the 10-task smoke,
#  identical CLI surface.)

$ harbor run \
    --dataset swe-bench/swe-bench-verified@latest \
    --agent claude-code --model claude-opus-4-7 \
    --ak max_turns=40 --ak reasoning_effort=xhigh \
    --n-concurrent 4 \
    --jobs-dir ~/swe-bench-runs --job-name swe-bench-opus-full
# → 500 tasks, ~10 hrs, ~$5400. No pre-dispatch cap; if Ben mis-set
#   the model alias to claude-opus-4-7 instead of haiku, he discovers
#   the $5400 spend post-hoc.
```

Identical surface, identical gaps. The friction items below are the
SAME as Aanya's, plus:

- **No matrix dispatcher template.** Ben wants `claude-opus-4-7`
  vs `claude-opus-4-5` vs `claude-haiku-4-5` × `reasoning_effort` ∈
  `{default, high, xhigh}` = 9 cells. Harbor's `--model` is repeatable
  (`-m` is `list[str]`, jobs.py:649-658) and runs all models within
  one job, but `--agent-kwarg` is not — he can't fan reasoning_effort
  out within a single invocation. He scripts a bash for-loop himself.

### Gap analysis vs hm scenarios

Counting features in `hm` Scenario A (§1.1 lines 53-205) the
researcher actually touches:

| Feature                                  | Raw harbor has? |
|------------------------------------------|-----------------|
| Project layout (`~/<slug>-research/`)    | No              |
| `specs/baseline.yaml` shape              | No              |
| Dataset resolution (`<org>/<name>@<ref>`)| **Yes**         |
| Container env management                 | **Yes**         |
| `solver_workflows/baseline/` template    | No              |
| `solver_workflow_content_hash` reproducibility | No        |
| `rk freeze` + `provenance.yaml`          | No              |
| Pre-dispatch `--max-budget-usd-running`  | No              |
| `experiment_meta.paper_baseline` constant| No              |
| `rk score --against-constant` verdict    | Partial (`pass_at_k` raw) |
| Per-task confidence interval (Wilson)    | No              |
| `rk diff` paired bootstrap               | No              |
| `--ordering-hints` tail-latency drop     | No              |
| `hypotheses/` directory convention       | No              |
| Per-trial trajectory + analyzer          | **Yes** (`harbor analyze`) |
| Job resume                               | **Yes**         |
| Cost rollup (`cost_usd` post-hoc)        | **Yes**         |
| `rk audit` taint scan                    | No              |

Aanya gets ~6 of ~18 features (33%) out of raw harbor. Ben gets the
same ~6 of ~18; the SWE-bench-specific knobs (`max_turns`,
`reasoning_effort`) pass through `--ak` so are equivalent.

**The 12-feature gap is the autoresearch loop + reproducibility +
scaffold layer.** Raw harbor is a benchmark **runner**; `hm` proposes
a benchmark **research project** on top of it.

---

## Alternative solutions surveyed

### Inspect (UK AISI)

- **URL.** [github.com/UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai)
  + docs at [inspect.aisi.org.uk](https://inspect.aisi.org.uk/).
- **Description.** Python eval framework from the UK AI Safety Institute.
  Ships `inspect eval <task.py> --model <model>` + `inspect view`.
  `@task` decorator returns a `Task(dataset, solver, scorer)`. ~200
  pre-built evaluations including SWE-bench (the SWE-Bench task is
  shipped in the `inspect_evals` companion package). METR is migrating
  from vivaria to inspect for evaluations work
  ([source: vivaria README](https://github.com/METR/vivaria)).

- **Aanya in inspect.** No first-class dabstep in `inspect_evals` last
  I checked. She'd write a `Task()` that loads dabstep's CSV/parquet
  manually:

  ```python
  # dabstep_task.py
  from inspect_ai import Task, task
  from inspect_ai.dataset import Sample, json_dataset
  from inspect_ai.solver import generate
  from inspect_ai.scorer import match

  @task
  def dabstep():
      return Task(
          dataset=json_dataset("./dabstep_questions.jsonl"),
          solver=[generate(max_tokens=4096)],
          scorer=match(),
      )
  ```

  ```bash
  $ inspect eval dabstep_task.py --model anthropic/claude-haiku-4-5
  $ inspect view  # browser viewer
  ```

  **Caveat: I'd need to test this to confirm** — dabstep's verifier is a
  DuckDB-query-answer match, which `inspect_ai.scorer.match` may or may
  not handle for the answer's numeric formatting. She'd likely write a
  custom scorer.

- **Ben in inspect.** SWE-bench IS in `inspect_evals`. He'd run
  `inspect eval inspect_evals/swe_bench --model anthropic/
  claude-opus-4-7 --limit 10`.

- **What inspect ships that hm proposes.** Per-eval log file with
  `EvalStats` (input/output tokens), browser viewer, `@task` decorator,
  scorer abstraction. Comparable to harbor's `result.json + harbor
  view`.

- **What hm proposes that inspect lacks.** Per
  [inspect's own eval-logs doc](https://inspect.aisi.org.uk/eval-logs.html):
  no built-in pass@k confidence intervals, no paired-bootstrap,
  no project scaffold (no `inspect init`), no
  hypothesis-comparison primitive across eval logs (the docs point to
  external "Inspect Viz" for visualisation but not a paired-stats
  CLI), no benchmark-defaults table.

- **Gap to hm.** Inspect closes the **scaffold and reproducibility**
  half of the gap (you write a `.py` file rather than a YAML; the file
  is the spec). It does NOT close the **autoresearch loop** half
  (paired bootstrap, against-constant verdict, `rk diff`).

### HuggingFace lm-evaluation-harness (EleutherAI)

- **URL.** [github.com/EleutherAI/lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness).
- **Description.** De-facto LLM eval harness for academic benchmarks
  (60+ shipped). Recently refactored to subcommands: `lm-eval run`,
  `lm-eval ls`, `lm-eval validate`, with YAML config via `--config`.

- **Aanya in lm-eval-harness.** No dabstep upstream. She authors a
  YAML task config (`tasks/dabstep.yaml`) pointing at her dataset +
  prompt template + a custom metric. Runs:
  ```bash
  $ lm-eval run --tasks dabstep --model anthropic --model_args \
      model=claude-haiku-4-5 --batch_size 4
  ```

- **What lm-eval-harness ships that hm proposes.** YAML task config
  shape (close to `hm`'s `kind: harbor` block in spirit), task
  registry, results table with per-task metric + std error (newer
  versions emit `stderr` on metrics).

- **What hm proposes that lm-eval-harness lacks.** No project
  scaffold, no paired-bootstrap, no hypothesis directory convention,
  no budget cap, no container env management (it's a logprob-and-text
  framework, not an agent-execution framework — Aanya can't really
  run a Claude Code agent inside it without surgery), no
  trajectory viewer.

- **Gap to hm.** Closes the YAML-config-shape part. Does NOT close
  the agent-execution part (where harbor wins), does not close the
  autoresearch loop. Wrong tool for an agent-based benchmark like
  dabstep or swe-bench-verified.

### SWE-bench's own runner

- **URL.** [github.com/SWE-bench/SWE-bench](https://github.com/SWE-bench/SWE-bench)
  + [evaluation guide](https://www.swebench.com/SWE-bench/guides/evaluation/).
- **Description.** Reference evaluator for SWE-bench: takes a
  `predictions.jsonl` (rows of `{instance_id, model_name_or_path,
  model_patch}`), applies each patch to a containerized repo, runs
  the project's tests, writes `results.json` (overall metrics) +
  `instance_results.jsonl` (per-instance) + `run_logs/` (per-instance
  log).

- **Ben in swe-bench official runner.**
  ```bash
  # 1. Generate predictions (out of scope of the runner itself — Ben
  #    has to drive the agent loop himself)
  $ python my_claude_swe_loop.py \
      --instances 500 --model claude-opus-4-7 \
      --out predictions.jsonl

  # 2. Evaluate
  $ python -m swebench.harness.run_evaluation \
      --dataset_name princeton-nlp/SWE-bench_Verified \
      --predictions_path predictions.jsonl \
      --max_workers 8 \
      --run_id ben-opus-2026-05-23
  # → writes results.json (total/submitted/completed/resolved counts +
  #   resolution rate %) + instance_results.jsonl + run_logs/
  ```

- **What swe-bench official runner ships.** Verifier + container
  orchestration + summary report (resolved %, counts) for ONE benchmark
  only. Modal backend (`run_modal_evaluation`) for remote dispatch.

- **What it does not.** No agent loop — Ben has to drive Claude
  himself (the runner only scores patches). No project scaffold. No
  paired stats. No hypothesis iteration. No autoresearch loop. No
  cross-benchmark support. No budget cap.

- **Per [arxiv:2602.07150 on randomness in agentic evals](https://arxiv.org/pdf/2602.07150)**
  cited in the search results: single-run pass@1 on SWE-bench varies by
  2.2-6.0 percentage points across reruns, std-dev > 1.5pp even at
  temperature 0. This is the empirical case for `rk diff` paired
  bootstrap — neither swe-bench's runner nor Ben's hand-rolled script
  surfaces this; `hm`'s paired-test design does.

- **Gap to hm.** Closes the SWE-bench-only evaluation half. Misses
  the agent loop entirely, misses cross-benchmark, misses scaffold,
  misses autoresearch. Wrong shape: it's the bottom layer of harbor,
  not a competitor to `hm`.

### METR Vivaria

- **URL.** [github.com/METR/vivaria](https://github.com/METR/vivaria).
- **Description.** METR's tool for running evaluations and agent
  elicitation research. Web UI + CLI; supports the METR Task Standard.
  Note: **METR is migrating from vivaria to inspect** per their
  README, with reduced new-feature development on vivaria.

- **Aanya/Ben in vivaria.** Run tasks via the web UI or CLI against
  the METR Task Standard. Vivaria gives a "quick feedback loop for
  'run agent on task, observe issue, make change to agent or
  reconfigure it, repeat'" (per vivaria README) — that's structurally
  the autoresearch loop, but built around the UI workflow rather than
  a CLI + frozen-spec discipline. No paired-statistics layer in the
  shipped tool. No project scaffold.

- **Gap to hm.** Closes the "iteration workflow" framing (vivaria's
  pitch is essentially the autoresearch loop, but UI-centric). Does
  NOT match harbor's dataset ecosystem (vivaria uses METR Task
  Standard, not harbor). Does NOT ship the paired-bootstrap or
  against-constant pieces.

### DataAgentBench's own runner (`~/git/dataagentbench/benchmark/`)

- **Description.** Upstream of razorback. A bash-driven harness at
  `~/git/dataagentbench/benchmark/{setup.sh, run.sh, solve.sh,
  validate.sh, rescore.sh, analysis.sh}` with `lib/` Python helpers.
  Single-purpose: DAB-only. Captain has used this for his DAB-paper
  reproduction work.

- **Aanya/Ben in dataagentbench.** N/A — it's DAB-only. Aanya
  (dabstep) would have to rewrite `setup.sh + solve.sh + validate.sh`
  for the dabstep verifier and dataset layout, which is exactly what
  the harbor adapter publishing already does. Ben (swe-bench-verified)
  ditto.

- **Gap to hm.** Provides a working precedent for the
  hypothesis-driven research project shape (entity-driven hypothesis
  capture, `--entity <slug>` reading YAML frontmatter — see
  `run.sh:15`), but is not directly usable by other researchers. It's
  the empirical evidence that the **project shape `hm` is proposing**
  works for one researcher; the question is whether to generalize it
  into razorback.

### Terminal-bench

- **URL.** [github.com/laude-institute/terminal-bench](https://github.com/laude-institute/terminal-bench).
- **Description.** Terminal sandbox + agent eval harness. CLI: `tb run`.

- **Gap to hm.** No project scaffold, no paired stats, no autoresearch
  loop. Same single-benchmark-runner shape as swe-bench's runner.

---

## Unique-value finding

### Things that ONLY hm offers vs all surveyed alternatives

1. **Project scaffold = autoresearch loop on a plate.** No surveyed
   tool ships `<tool> research new <slug>` that produces a directory
   with `specs/baseline.yaml + solver_workflows/baseline +
   hypotheses/ + runs/ + razorback-research.toml`. Inspect comes
   closest by making the eval file itself ≈ the spec, but offers no
   directory convention or hypothesis-iteration template.
2. **Spec-side frozen reproducibility with content-hashed solver
   workflows.** `rk freeze` + `solver_workflow_content_hash` (razorback's
   `freeze.py:64-78`) gives a sealed-hash run-dir convention that no
   surveyed tool ships. Inspect's eval-log captures resolved task IDs
   + model + tokens, but does not hash the solver source recursively.
3. **`rk diff` paired-bootstrap between two run-dirs.** None of
   inspect, lm-eval-harness, swe-bench, vivaria, terminal-bench, or
   raw harbor ships a paired statistical test between two evals. The
   referenced [arxiv 2602.07150](https://arxiv.org/pdf/2602.07150)
   shows single-run pass@1 varies by 2-6pp on SWE-bench — `rk diff`
   is the right primitive to address this.
4. **`experiment_meta.paper_baseline` + auto-verdict on `rk score`.**
   The "implicit against-constant" UX in `hm` §2.8 — no surveyed tool
   bakes the paper baseline into the spec and renders a verdict on
   every run.
5. **Pre-dispatch budget cap with `--max-budget-usd-running`.** Raw
   harbor reports `cost_usd` post-hoc; no alternative gates dispatch
   on a cumulative budget cap. For Ben's $5400 run this is materially
   load-bearing.

### Things hm offers that alternatives ALSO have (re-implementation candidates)

1. **Dataset resolution.** `kind: harbor` + `dataset: <org>/<name>
   @<ref>` is a 1:1 wrapper over `harbor run -d <ref>`. Razorback
   adds zero functionality on the resolution itself; the spike at
   `_spike/scratch_harbor_block.py` (commit `d106ebf`) confirms
   `PackageDatasetClient.download_dataset` does all the work in ~3s.
2. **Container env management.** Razorback inherits harbor's docker /
   daytona / e2b / modal / runloop / gke / apple-container / etc. — the
   `kind: harbor` block does not add an env discriminator.
3. **Per-trial trajectory + LLM-grader.** `harbor analyze` runs an
   LLM grader pass; razorback's `rk audit` (Phase 4a, already in tree
   at `src/razorback/audit/taint.py`) is a different lens (taint
   patterns) but the trajectory-walking infrastructure is harbor's.
4. **Concurrency, retries, timeout multipliers.** Harbor's
   `--n-concurrent / -n`, `--max-retries / -r`, `--timeout-multiplier`
   already cover this; razorback's `concurrency.trials` spec field is
   a wrapper.
5. **Job resume.** `harbor job resume <dir>` exists. Razorback's
   resume + `SeedMismatchError` adds the reproducibility check on top,
   but the underlying resume mechanism is harbor's.
6. **Cost rollup post-hoc.** `JobStats.cost_usd` exists in harbor.
   Razorback's `experiment_meta.max_budget_usd` is the pre-dispatch
   side (unique to razorback) but the post-hoc `cost_usd` reporting
   would just re-read harbor's number.

### Drop recommendations

- **DROP: razorback-side env discriminator.** `hm` §2.1 implicitly
  inherits harbor's env via the agent block, which is correct. No
  action — confirm this in the spec.
- **DROP: re-implementing dataset resolution as anything other than a
  pass-through.** The `_build_harbor` translator should be ~20 LOC of
  `PackageDatasetClient.download_dataset → TaskConfig(path=...)`. The
  spike already shows this. Don't add filter logic razorback-side —
  harbor's `-i`/`-x`/`-l` already cover the cases.
- **DROP: per-benchmark Pydantic blocks** (this is already in `hm`'s
  plan — §2.2 collapses `ade-bench`, `harbor_dab`, `spider2-dbt` into
  `kind: harbor`). Keep.
- **DROP: any razorback re-implementation of `harbor view` /
  `harbor analyze`.** Razorback should not ship its own
  trajectory-viewer or LLM-grader. Use harbor's.
- **KEEP: `rk freeze`, `rk score --against-constant`, `rk diff`,
  `rk audit`, the project scaffold, `experiment_meta.paper_baseline`,
  `--max-budget-usd-running`, `solver_workflow_content_hash`.** These
  are the unique-value features. None of the surveyed tools ship
  them.

---

## Bottom line

`hm` justifies itself, but for a narrower reason than its current
framing suggests. The `kind: harbor` block + `_build_harbor`
translator are a thin wrapper over harbor's existing dataset
resolution — they add the spec/freeze envelope, nothing more. The
**load-bearing unique value** is the autoresearch loop layer
(`rk freeze` + `rk score --against-constant` + `rk diff` + the project
scaffold + `experiment_meta.paper_baseline` + budget cap +
`solver_workflow_content_hash`). No surveyed alternative (raw harbor,
inspect, lm-eval-harness, swe-bench's runner, vivaria, terminal-bench,
dataagentbench's runner) ships that combination. Aanya/Ben can get
~33% of `hm` Scenario A/B's outcomes from raw harbor alone (dataset
resolution + container env + trajectory capture + LLM grader + job
resume + cost rollup), 50-60% by stitching harbor + inspect's `@task`
shape + a hand-rolled paired-bootstrap script, but none of the
existing tools delivers the full loop. **Recommendation: keep `hm`'s
scope but tighten the framing to "razorback is the autoresearch
project layer over harbor benchmarks" rather than "razorback adds a
generic benchmark surface."** The benchmark surface is harbor's; what
razorback adds is the research-project workflow. That framing also
naturally justifies dropping any razorback re-implementation of the
harbor pieces (env management, dataset resolution, trajectory
viewer, LLM grader) and pre-empts the cross-construct concerns the
staff review (`staff-review-hm-design.md` §Cross-construct findings)
raised about `rk audit` and `ne`'s FO-skill mount being silently
omitted from the scaffold's normative path.
