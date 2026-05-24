# Generic harbor benchmark surface — UX-first design

**Status.** Plan-stage approval pending. Captain reframed scope
twice during impl-stage: first to "ship the impl, not just the
doc"; then to "no backwards-compat required, just migrate" + "user
experience first, internal API surface is downstream of the
scenarios." This document follows the second reframing.

**What this doc replaces.** Cycle 1 of this doc enumerated 12
internal-API sections (§1-§11) plus a consumer-surface inventory
(S1-S7) plus decision trees (D1-D4: collapse-partial vs
collapse-all vs no-op + spec-amendment vs no-amendment). The
captain rejected that framing as "more details than needed" and
asked for two end-to-end user scenarios first; the internal
design falls out backwards. This rewrite does that.

**What stays from cycle 1.** The ideation spike's empirical
finding holds: `PackageDatasetClient` resolves any harbor-published
dataset (dabstep, swe-bench-verified, ade-bench, ...) into local
`task.toml + instruction.md` directories with zero razorback-side
prep code. The spike artifact is at `_spike/scratch_harbor_block.py`
(commit `d106ebf`); its findings inform the scenarios but do not
dictate the schema shape.

**Source.** Captain directive 2026-05-23 — "let's say we have a
consumer repo, targeting dabstep (another harbor-listed dataset),
would this work today?" → reframe to "no this is too complicated.
i'd assume if dabstep is already on harbor, there should be just
simple config" → reframe to "the task is implement, not just doc.
spike as needed in ideation stage" → reframe to "no backward compat
required. user experience first."

---

## §1 User scenarios

The two scenarios below drive every design decision in §2-§N. Each
scenario walks an actual researcher from "I heard about benchmark
X" through "I have a published-quality run-dir with a captain-
facing report" — every command they type, every file they edit,
every file razorback writes for them.

### §1.1 Scenario A — Researcher targets dabstep

**Persona.** Aanya, a data-analysis researcher. She saw the
dabstep paper (Adyen, 2024 — 450 financial-data-analysis questions
against a small DuckDB warehouse). She wants to know whether
`claude-haiku-4-5` matches the published 47.6% baseline at ~1/10th
the cost of the headline `claude-opus-4-5` figure. Her org has an
Anthropic API key with $200/month budget. She has not used
razorback before.

**Step 1 — install + scaffold.** Aanya runs:

```bash
$ pipx install razorback
$ rk research new dabstep --from adyen/dabstep@latest \
    --solver-runtime claude --target-model claude-haiku-4-5
```

Razorback creates `~/dabstep-research/` with this layout:

```
~/dabstep-research/
├── README.md                            # how to run + autoresearch lifecycle
├── specs/
│   ├── baseline.yaml                    # first runnable spec
│   └── README.md                        # how to author spec variants
├── solver_workflows/
│   ├── baseline/
│   │   └── README.md                    # the solver-workflow agent reads
│   └── README.md                        # how to author hypothesis variants
├── hypotheses/                          # empty — autoresearch loop populates
│   └── README.md
├── runs/                                # razorback writes here
│   └── .gitignore                       # ignore everything except _summary/
└── razorback-research.toml              # named-ref registry seed (§5.1)
```

The `specs/baseline.yaml` reads:

```yaml
version: 1
experiment: dabstep-baseline
agent:
  kind: spacedock_solver
  runtime: claude
  model: claude-haiku-4-5
  sampling:
    temperature: 0.0
  solver_workflow: ./solver_workflows/baseline
  max_turns: 16
  max_budget_usd: 2
benchmark:
  kind: harbor
  dataset: adyen/dabstep@latest
trials: 1
concurrency:
  trials: 4
experiment_meta:
  max_budget_usd: 200
  paper_baseline:
    name: paper
    value: 0.476
```

**Step 2 — smoke run.** Aanya runs:

```bash
$ cd ~/dabstep-research
$ rk freeze specs/baseline.yaml --out specs/baseline.frozen.yaml
wrote specs/baseline.frozen.yaml
wrote specs/provenance.yaml
$ rk run specs/baseline.frozen.yaml --runs-dir runs --n-tasks 5
# → ~$0.15 spent, 5 trials complete in ~6 min, writes:
runs/dabstep-baseline/dabstep-baseline_<sealed-hash>/
├── spec.frozen.yaml
├── provenance.yaml
├── summary.json                  # stratified_pass_at_1: 0.40 (2/5)
├── manifest.json
└── trials/adyen-35-0001__<uuid>/
    ├── result.json
    ├── subagent-trace-manifest.json  # ne's post-run hook — captured > 0 on spacedock
    └── steps/main/agent/claude-code.txt
$ rk audit runs/dabstep-baseline/dabstep-baseline_<sealed-hash>/ --policy strict
# → exit 0 (clean); writes audit.json next to summary.json. Strict policy exits
#   23 (TaintFindingsError) on any non-clean trial — see src/razorback/audit/taint.py.
$ rk score runs/dabstep-baseline/dabstep-baseline_<sealed-hash>/
stratified_pass_at_1: 0.40 (2/5)
per-query cells: 5 (Wilson 95% CI per cell)
taint_status: clean (5/5 trials)               # surfaced from audit.json
verdict (vs paper=0.476): below (point estimate)  # --against-constant not needed,
                                                  # auto-pulled from experiment_meta.paper_baseline
```

Aanya sees `verdict: below` and a 5-task confidence interval. The
smoke is too small to conclude. `rk audit` returned clean — no
trial reached for forbidden lookups (`datasets.load_dataset`,
public HTTP egress, etc.).

**Step 3 — full baseline.** Aanya runs the same spec without
`--n-tasks`, then re-runs `rk audit` + `rk score`:

```bash
$ rk run specs/baseline.frozen.yaml --runs-dir runs \
    --max-budget-usd-running runs/_budget.json
# → ~$5 spent (estimate: $5.10 against $200 cap), 450 trials in ~3 hrs
$ rk audit runs/dabstep-baseline/dabstep-baseline_<sealed-hash-full>/ --policy strict
# → exit 0; writes audit.json (clean: 450, suspect: 0, tainted: 0)
$ rk score runs/dabstep-baseline/dabstep-baseline_<sealed-hash-full>/
stratified_pass_at_1: 0.412 (Wilson 95% CI elided here — see JSON)
taint_status: clean (450/450 trials)
verdict (vs paper=0.476): below (point estimate)
```

Her baseline lands at 41.2%, 6.4 points under the paper. She
captures this in `hypotheses/0001-baseline-headline.md` (her own
note; razorback doesn't write this for her). The matrix driver
the scaffold dropped at `drivers/matrix.sh` chains
`rk run` → `rk audit --policy strict` → `rk score
--against-constant` per cell automatically (modeled on
`examples/drivers/dab-paper-matrix.sh:188-204`). When she scales
to a multi-variant matrix in §1.1 Step 5, the driver fires the
audit per cell and refuses to score a tainted cell.

**Step 4 — first hypothesis.** Aanya hypothesizes that giving the
solver explicit DuckDB-query-syntax examples in the workflow
README will close the gap. She copies the baseline solver workflow:

```bash
$ cp -r solver_workflows/baseline solver_workflows/h0001-duckdb-examples
$ ${EDITOR:-vi} solver_workflows/h0001-duckdb-examples/README.md
# (edits to add a DuckDB cheatsheet section)
```

And writes a sibling spec:

```bash
$ cp specs/baseline.yaml specs/h0001.yaml
$ sed -i 's|solver_workflows/baseline|solver_workflows/h0001-duckdb-examples|' specs/h0001.yaml
$ ${EDITOR:-vi} specs/h0001.yaml
# (changes experiment: dabstep-h0001-duckdb-examples)
```

**Step 5 — paired-test the hypothesis.** Aanya runs the hypothesis
spec and asks `rk diff` (ships when paired tests are needed —
spec §3.2 "Surface that ships when the autoresearch loop's analyze
stage needs paired hypothesis testing") to compare:

```bash
$ rk freeze specs/h0001.yaml --out specs/h0001.frozen.yaml
$ rk run specs/h0001.frozen.yaml --runs-dir runs \
    --max-budget-usd-running runs/_budget.json \
    --ordering-hints runs/dabstep-baseline/dabstep-baseline_<sealed>/
# → ~$5.20, 450 trials, ~2.5 hrs (ordering-hints drops tail latency)
$ rk audit runs/dabstep-h0001-duckdb-examples/dabstep-h0001_<sealed>/ --policy strict
# → exit 0 (clean across 450 trials)
$ rk diff \
    runs/dabstep-baseline/dabstep-baseline_<sealed>/ \
    runs/dabstep-h0001-duckdb-examples/dabstep-h0001_<sealed>/
delta: +0.027 (h0001 - baseline)
paired bootstrap 95% CI: [-0.011, +0.064]
holm-bonferroni adjusted p: 0.13 (not significant at alpha=0.05)
verdict: not yet distinguishable from baseline at N=450
```

The autoresearch loop is now **live**: Aanya can author a new
hypothesis, run it, audit it for leaks, paired-test it against
her own baseline (no need to recompute the baseline). The
reportable artifact is the `rk diff` JSON output paired with the
two `audit.json` clean attestations, citable in the
experiment-workflow's `analyze` stage entity.

**What had to be true for "live."**
- (a) Aanya's spacedock plugin is installed (`pipx install
  razorback` does this).
- (b) Her Anthropic API key is in the environment
  (`ANTHROPIC_API_KEY`).
- (c) Docker / Colima is running (the dab-agent image runs
  containerized via harbor's docker environment).
- (d) A `paper_baseline` constant is set on the spec (so
  `rk score` can deliver a YES/NO verdict on first ship) OR a
  baseline run-dir exists (so `rk diff` can deliver a paired
  delta). Aanya's flow uses both: paper baseline for sanity-check
  on each individual run, her own baseline-run-dir for hypothesis
  paired tests.
- (e) `dataset: adyen/dabstep@latest` resolves anonymously (no
  Harbor auth needed for public datasets).
- (f) `rk audit --policy strict` runs after each `rk run` and
  before `rk score` / `rk diff`. The autoresearch loop is NOT
  "live" if Aanya is skipping the leak audit — she'd be shipping
  verdicts on potentially tainted trajectories. The matrix
  driver from the scaffold (§2.3) chains this automatically; the
  manual sequence above mirrors what the driver does per-cell.
- (g) Each spacedock-variant trial writes
  `subagent-trace-manifest.json` with `captured > 0` (ne's
  smoke gate at `src/razorback/audit/subagent_traces.py`).
  Captured == 0 means the spacedock crew didn't load — the
  matrix driver's per-cell smoke gate REJECTs the cell.

What does NOT need to be true: no benchmark-specific razorback
plugin, no per-benchmark Pydantic class, no per-benchmark builder
shell script. The dabstep adapter is fully self-described in its
`task.toml`.

### §1.2 Scenario B — Researcher targets swe-bench-verified

**Persona.** Ben, a code-agent researcher. He wants to compare
`claude-opus-4-7` against the published SWE-Bench-Verified
baseline (the 500-task slice of SWE-Bench). His org has the
Anthropic API key, plus a sufficient budget for the bigger run
(SWE-Bench tasks are ~10x more expensive than dabstep — each
involves cloning a repo, running tests, iterating). Ben has used
razorback before for ADE-bench.

**Step 1 — install + scaffold.**

```bash
$ rk research new swe-bench-verified \
    --from swe-bench/swe-bench-verified@latest \
    --solver-runtime claude --target-model claude-opus-4-7
```

Razorback creates `~/swe-bench-verified-research/` with the same
layout shape as Aanya's. The differences are entirely in the
**generated `specs/baseline.yaml`**:

```yaml
version: 1
experiment: swe-bench-verified-baseline
agent:
  kind: spacedock_solver
  runtime: claude
  model: claude-opus-4-7
  sampling:
    temperature: 0.0
  solver_workflow: ./solver_workflows/baseline
  max_turns: 40                       # SWE-Bench needs more turns
  max_budget_usd: 12                  # higher per-trial cap
  reasoning_effort: xhigh             # the long-horizon coding default
benchmark:
  kind: harbor
  dataset: swe-bench/swe-bench-verified@latest
trials: 1
concurrency:
  trials: 4
experiment_meta:
  max_budget_usd: 6000                # ~$5400 estimate at full N
  paper_baseline:
    name: paper
    value: 0.563                      # mini-swe-agent + GPT-5-mini headline
                                      # https://hub.harborframework.com/datasets/swe-bench/swe-bench-verified
```

The defaults the scaffold picks for `max_turns`,
`max_budget_usd`, `reasoning_effort` come from a small
benchmark-defaults table razorback ships (§2.3 below). For any
benchmark not in that table, the scaffold drops the defaults at
conservative values + emits a `# TODO: tune for this benchmark`
comment.

**Step 2 — smoke (10 tasks, ~$25).**

```bash
$ rk freeze specs/baseline.yaml --out specs/baseline.frozen.yaml
$ rk run specs/baseline.frozen.yaml --runs-dir runs --n-tasks 10
# → ~$25 spent, 10 trials in ~45 min (SWE-Bench wallclock per task ~5 min p50)
$ rk audit runs/swe-bench-verified-baseline/swe-bench-verified-baseline_<sealed>/ --policy strict
# → exit 0 (clean); writes audit.json
$ rk score runs/swe-bench-verified-baseline/swe-bench-verified-baseline_<sealed>/
stratified_pass_at_1: 0.60 (6/10)
taint_status: clean (10/10 trials)
verdict (vs paper=0.563): above (point estimate; CI wide at N=10)
```

**Step 3 — full baseline (500 tasks, ~$5400 — captain budget
approval gate first).** Ben's spec carries
`experiment_meta.max_budget_usd: 6000` and the
`--max-budget-usd-running` flag enforces it pre-dispatch. The
scaffold dropped `drivers/matrix.sh` at scaffold time; that
driver wraps the cycle-3 in-tree `examples/drivers/dab-paper-matrix.sh`
pattern (lines 188-204): per-cell `rk run` → `rk audit --policy
strict` → `rk score --against-constant` → ledger row with
status, cost, taint count. It refuses dispatch on a per-cell
budget overrun (modeled on the matrix driver's existing
`--max-cell-budget-usd` flag) and stops the matrix on the first
`rk audit` strict-exit-23 cell.

```bash
$ ./drivers/matrix.sh --output-dir runs --max-cell-budget-usd 12
# → harbor.run dispatches 500 tasks in parallel (concurrency: 4),
#   wallclock ~10 hrs, total spend ~$5400 against $6000 cap.
#   Each cell writes audit.json + score.json + subagent-trace-manifest.json.
$ rk score runs/swe-bench-verified-baseline/swe-bench-verified-baseline_<sealed>/ \
    --format markdown
# stratified_pass_at_1: 0.572 (Wilson 95% CI per task in JSON)
# taint_status: clean (498/500 trials, 2 suspect — see audit.json)
# verdict vs paper=0.563: matches
```

Ben's baseline matches the published number with two
suspect-flagged trials surfaced for inspection. The autoresearch
loop is now live; subsequent hypotheses (a different solver
workflow, a different `reasoning_effort`, fewer or more
`max_turns`) compare via `rk diff` against this baseline run-dir,
paired with `rk audit` clean attestations on both sides.

**Where Scenario B differs from Scenario A.**

- (a) **Per-task wallclock + cost.** SWE-Bench tasks are
  git-clone + apply-patch + run-tests (~5 min p50, ~$10-15 per
  task) vs dabstep's DuckDB-query-and-answer (~1 min p50,
  ~$0.02-0.05 per task). This shows up in the scaffolded
  `max_turns` / `max_budget_usd` and in the
  `experiment_meta.max_budget_usd` cap.
- (b) **Verifier shape.** SWE-Bench verifier runs the project's
  pytest suite; dabstep verifier diffs a single text answer file.
  Both are *fully self-described* in the harbor adapter's
  `task.toml` — razorback never reads them. Aanya and Ben write
  the same `benchmark: { kind: harbor, dataset: <ref> }` block.
- (c) **Paper baseline source.** Aanya's 0.476 is the dabstep
  paper number; Ben's 0.563 is harbor's parity-table number for
  `mini-swe-agent` + GPT-5-mini (from the hub page itself). The
  scaffold emits the value plus a citation comment so the
  researcher can adjust the citation if they're comparing to a
  different published baseline.

What does NOT differ from Scenario A: the spec block shape, the
CLI surface, the run-dir layout, the autoresearch loop structure,
the lack of any benchmark-specific razorback code.

---

## §2 Implementation design — derived from the scenarios

### §2.1 The `benchmark:` block

Both scenarios use the same block:

```yaml
benchmark:
  kind: harbor
  dataset: <org>/<name>@<ref>
```

Plus optional task selectors when the researcher wants a subset
(passing through to harbor's `-i` / `-x` flags):

```yaml
benchmark:
  kind: harbor
  dataset: adyen/dabstep@latest
  tasks: ["35", "2712"]              # optional include selector
  exclude_tasks: ["broken-task-id"]  # optional exclude
```

`--n-tasks` is a **CLI flag on `rk run`**, not a spec field — it
is operationally a "smoke me with N before I run all of them"
override, not part of the experiment identity. Putting it on the
spec would mean the smoke run and the full run carry different
frozen specs (different sealed hashes), defeating reproducibility.
Smokes carry the same frozen spec; `--n-tasks` records as a
`provenance.yaml` annotation on this invocation only.

That is the entire spec-side shape for harbor-published
benchmarks. No per-benchmark fields. No `prep:` discriminator.
No `tasks_root:` escape hatch in this block — local
Harbor-shaped task directories get a separate, smaller block
(§2.5).

### §2.2 What dies — per-benchmark blocks migrate to `kind: harbor`

The captain's "no backwards compat" rule removes the existing
per-benchmark blocks. Each migrates to `kind: harbor` with a
matching `dataset:` reference. The frozen specs in
`examples/specs/` get rewritten in this same entity:

- **`kind: ade-bench`** with `dataset: dbt-labs/ade-bench@<ref>` →
  `kind: harbor` with the same `dataset:`. The ADE-specific
  fields drop (`batch_mode`, `docker_image_override`,
  `db_type`, `project_type`). `batch_mode: shared-context` was
  never implemented; the other three were captain-overrides that
  belong on the harbor adapter, not razorback.
- **`kind: ade-bench` with `tasks_root: <local-path>`** →
  `kind: harbor-local` (§2.5) with the same `tasks_root` +
  `tasks` fields. Local Harbor-shaped directories are a
  meaningfully different invocation (no registry resolution) and
  get their own minimal kind. Used only for dev/fixture work.
- **`kind: spider2-dbt`** → `kind: harbor-local`. It has no
  Harbor-published version today; `tasks_root` is required.
  Its `docker_image_override` + `batch_mode` either drop (the
  latter was never implemented) or migrate to the harbor
  adapter once spider2-dbt publishes.
- **`kind: harbor_dab`** with `dataset: dab@<version>` →
  `kind: harbor` with the same `dataset:` IF DAB's per-query
  task generation moves into the harbor adapter (the harbor team
  owns publishing `dab@1.0` as a generative dataset). Until that
  lands, DAB stays as a **plugin escape valve** (§2.6) under
  `kind: harbor` + `plugin: razorback-plugin-dab`. The
  workspace_variant / hints / query_mode fields move to a
  `plugin_args:` sub-block on the benchmark.
- **`kind: dab`** (legacy SUPERSEDED) → deleted.
- **`kind: local`** → unchanged. Raw `task_paths: list[Path]` is
  genuinely not a harbor concept; it is a dev fixture surface and
  stays.

The post-migration `BenchmarkBlock` union has three members:
`LocalBenchmarkBlock` (unchanged), `HarborBenchmarkBlock` (the
new generic), and `HarborLocalBenchmarkBlock` (the local
`tasks_root` escape hatch). Net change: -3 classes (`AdeBench`,
`HarborDab`, `Spider2Dbt` removed), +2 classes
(`HarborBenchmark`, `HarborLocalBenchmark` added), -1 legacy
class (`DabBenchmarkBlock`).

### §2.3 The `rk research new` command (the scaffold)

A new top-level subcommand:

```
rk research new <slug> --from <dataset-ref>
                       [--solver-runtime claude|codex|pi]
                       [--target-model <alias>]
                       [--into <dir>]            # default: ~/<slug>-research
                       [--dry-run]               # print plan, don't write
```

Effect: create the target directory with the layout from §1.1
Step 1. The shape of the scaffolded files comes from a small
template tree razorback ships at `docs/templates/research-project/`:

```
docs/templates/research-project/
├── README.md.j2                       # Jinja2 — fills in {slug, dataset_ref, model}
├── specs/
│   ├── baseline.yaml.j2
│   └── README.md
├── solver_workflows/
│   ├── baseline/
│   │   └── README.md.j2               # generic spacedock workflow shape
│   └── README.md
├── hypotheses/
│   └── README.md
├── drivers/
│   └── matrix.sh.tmpl                 # researcher-editable matrix runner
└── razorback-research.toml.j2
```

The scaffold picks benchmark-defaults from a tiny table at
`docs/templates/benchmark-defaults.toml`:

```toml
[adyen.dabstep]
max_turns = 16
max_budget_usd = 2
reasoning_effort = "default"
paper_baseline = { name = "paper", value = 0.476 }

[swe-bench.swe-bench-verified]
max_turns = 40
max_budget_usd = 12
reasoning_effort = "xhigh"
paper_baseline = { name = "paper", value = 0.563 }
```

For benchmarks not in the table, the scaffold drops conservative
defaults + emits `# TODO: tune for this benchmark` and `#
paper_baseline: { name: paper, value: 0.0 }  # TODO: cite + value`
comments. Researchers PR new entries as they characterize new
benchmarks.

The scaffold does NOT call out to Harbor's registry at scaffold
time — it accepts any `<org>/<name>@<ref>` syntactically and
defers resolution to `rk freeze`. This keeps `rk research new`
network-free and instant.

**Per-template contents (load-bearing — these were unspecified
in the cycle-3 first pass; staff review surfaced the gap).**

- **`specs/baseline.yaml.j2`.** The shape in §1.1 Step 1 lines
  81-105 verbatim. Fills `{slug, dataset_ref, model,
  solver_runtime, max_turns, max_budget_usd, reasoning_effort,
  paper_baseline}` from `benchmark-defaults.toml` plus the
  command-line flags. Includes the `agent.append_system_prompt:`
  field with a TODO marker — researchers fill it with their
  ROLE prefix (the spacedock_solver agent reads it; see v2
  spec §6.2 line 1187 + `src/razorback/spec/schema.py:112`).

- **`solver_workflows/baseline/README.md.j2`.** A minimal
  spacedock workflow README the spacedock_solver agent reads
  via `_compose_run_instruction` (`src/razorback/agents/spacedock_solver.py:302-309`).
  Required sections (in order):

  1. `# {slug} solver workflow` — title.
  2. `## Stages` — enumerates the workflow stages
    (`model` → `analyze` → `verify` is the default DAB-shaped
    spacedock flow; researchers edit per benchmark). Per v2
    spec §5.3 the stage names become halt-resume keys when
    stage-boundary-freeze mods ship.
  3. `## Reset declaration` — names which per-trial state
    surfaces (agent_container, compose_services,
    host_workspace) reset between trials. Per v2 spec §5.3.
  4. `## External-oracle audit` — pre-`verify` prose forbidding
    `datasets.load_dataset`, `hf://`, public-HTTP egress to
    dataset hosts, web-search invocations, and LLM-as-oracle
    patterns. Mirrors `wp`'s contract (the in-flight
    External-oracle audit entity at
    `docs/razorback-implementation/dab-verify-stage-external-oracle-audit.md`).
    If `wp` ships, the scaffold's template references the
    `rk audit` taint module's pattern catalog
    (`src/razorback/audit/taint.py:20-30` `forbidden_lookup`)
    so the prose and the scanner stay aligned. If `wp` is
    still in flight, the scaffold ships the prose as a stub
    with a `# TODO: align with rk audit external-oracle module
    once wp lands` marker.
  5. `## ROLE prefix` (optional) — if researchers want their
    inner-agent to operate as a first-officer (spawning
    subagent crews via the `Task` tool), the README documents
    the ROLE prefix shape and points to
    `agent.append_system_prompt:` on the spec as the carrying
    field.

  The README is the load-bearing surface — its content drives
  the spacedock_solver agent's behavior on every trial. The
  scaffold ships a benchmark-agnostic baseline; per-benchmark
  variants are the autoresearch loop's hypotheses
  (`hypotheses/h0001-*/README.md`).

- **`drivers/matrix.sh.tmpl`.** A per-cell matrix runner
  modeled on `examples/drivers/dab-paper-matrix.sh` (in-tree
  on main). Per-cell pipeline:

  ```bash
  # foreach (variant, dataset|subset):
  #   1. rk freeze spec → spec.frozen.yaml
  #   2. rk run --max-budget-usd-running runs/_budget.json \
  #            --runs-dir runs spec.frozen.yaml
  #   3. assert subagent-trace-manifest.json captured > 0 (when
  #      agent.kind == spacedock_solver) — REJECT cell if not.
  #      Read from <cell_run_dir>/trials/<task>/subagent-trace-manifest.json.
  #   4. rk audit cell_run_dir --policy strict → audit.json
  #      → REJECT cell on exit 23 (TaintFindingsError).
  #   5. rk score cell_run_dir --against-constant <baseline>=<value> \
  #            --format json → score.json
  #   6. ledger row: variant, dataset, status, cost_usd, taint_count
  ```

  The template is `# TODO`-marker-friendly: researchers add
  the matrix dimensions (variants, dataset subsets) per their
  experiment. The smoke-gate (step 3) and audit-gate (step 4)
  are non-removable structural protections. Without them, the
  matrix dispatcher silently degrades when the spacedock crew
  fails to load or a trial reaches for an oracle.

- **`razorback-research.toml.j2`.** Seed for the named-ref
  registry (v2 spec §3.2 `rk registry`). Carries the
  baseline-run-dir reference once the first baseline lands
  (`@baseline = "runs/.../baseline_<sealed>/"`) so hypothesis
  specs can cite it symbolically in `rk diff @baseline ...`
  invocations.

- **`hypotheses/README.md`.** Operator-facing — explains the
  hypothesis lifecycle (copy `solver_workflows/baseline` →
  `solver_workflows/h0001-<slug>`; copy `specs/baseline.yaml`
  → `specs/h0001.yaml`; edit the README; freeze + run + audit
  + diff against `@baseline`). Mirrors the experiment-workflow
  template shape from v2 spec §5.1.

- **`README.md.j2`.** Top-level README for the research repo.
  Walks the researcher through Step 1-5 of §1.1 above with
  benchmark-specific paths filled in.

### §2.4 The `_build_harbor` translator

One builder. Resolves the dataset ref via
`PackageDatasetClient.download_dataset` (the existing entry point
ADE-bench uses today, validated by the cycle-2 spike). Emits one
`TaskConfig(path=<downloaded-dir>)` per resolved task. Applies
spec-side `tasks` / `exclude_tasks` selectors as
`PackageTaskId.name`-verbatim matching (no prefix stripping —
heterogeneous across datasets; see §4 Spike findings).

Already shipped in cycle-2 commit `f9f3143`. Stays. The
`HarborBenchmarkBlock` schema in commit `6cbcaa8` also stays
(matches §2.1 exactly).

The harbor-local path (§2.5) is a separate small builder
`_build_harbor_local` that globs the local `tasks_root` and emits
`TaskConfig(path=tasks_root/<slug>)` per `tasks` entry. ~15 LOC.

**Freeze inputs + sealed_hash interaction** (staff-review fix).
Spec-side `_freeze_spacedock_solver` (`src/razorback/spec/freeze.py:30-61`)
does NOT include benchmark-block fields in the spec-side
`sealed_hash` computation today. Migrating `kind: ade-bench` /
`kind: harbor_dab` / `kind: spider2-dbt` → `kind: harbor` does
not perturb the spec-side `sealed_hash` for that reason.

The agent-side `task_identity` block at
`src/razorback/agents/seal.py:68-82` DOES include
`benchmark_kind`, `benchmark_task_id`, `batch_mode`, and
`child_task_ids_hash`. These are populated post-hoc from
`_discover_task_identity_from_manifest`
(`src/razorback/agents/spacedock_solver.py:214-245`) which reads
`<run-dir>/_razorback/task_views/*/view_manifest.json`. After
migration, the view manifest's `benchmark_kind` field reads
`"harbor"` (or `"harbor-local"`) instead of `"ade-bench"` /
`"harbor_dab"` / `"spider2-dbt"`. That shifts every migrated
spec's agent-side sealed_hash for otherwise-identical workloads.

**Consequence:** pre-migration freeze-CAS entries at
`$XDG_DATA_HOME/razorback/freeze/<old-sealed_hash>/` become
orphaned. A researcher resuming a pre-migration run-dir with a
post-migration agent gets `SeedMismatchError` (exit 20) — fine
under the captain's "no backwards compat" rule, but not silent.
Captured as commit 5 of §2.11 with explicit `rk freeze --rehash`
guidance for consumers; the migration commit message names the
sealed_hash break.

Spec-side `tasks: [...]` and `exclude_tasks: [...]` selectors on
`HarborBenchmarkBlock` do NOT enter the spec-side sealed_hash
(inheriting today's agent-block-only contract). They DO enter the
agent-side seal indirectly via `child_task_ids_hash` —
materialized task ids flow into the view manifest. Documented as
default-by-inheritance; sealing them deliberately is captain
decision (c) in §3.

`--n-tasks` is a CLI flag that records as a `provenance.yaml`
annotation only — does not enter the spec or the seal (§2.1
already established this). Two consecutive `rk run` invocations
of the same frozen spec with different `--n-tasks` produce
different run-dirs with the same sealed_hash, by design.

### §2.5 The `HarborLocalBenchmarkBlock` (dev escape)

```yaml
benchmark:
  kind: harbor-local
  tasks_root: ./tasks
  tasks: [my-dev-task-001]
```

Used when a researcher is iterating on a harbor adapter before
publishing it. The block is intentionally minimal; once the
adapter publishes, the researcher migrates to `kind: harbor` +
`dataset: <org>/<name>@<ref>`.

### §2.6 The plugin escape valve (`kind: harbor` + `plugin:`)

DAB's per-query task generation does not live in the published
harbor adapter today — razorback's `razorback-plugin-dab`
materializes per-query directories from a `data_root` + a
`dataset.toml`. This is the one non-collapsing case:

```yaml
benchmark:
  kind: harbor
  dataset: dab@1.0                    # plugin-resolved, not registry-resolved
  plugin: razorback-plugin-dab
  plugin_args:
    workspace_variant: direct-structured
    query_mode: per-query
    hints: false
    data_root: ${DAB_DATA_ROOT}
```

`_build_harbor` notices `plugin:` is set and routes to a thin
subprocess shim that calls `<plugin> generate --out <view-dir>
--args <serialized plugin_args>` — same shape as today's
`_build_harbor_dab` does, but the dispatch is generic. New
generative benchmarks ship their own plugin packages with the
same convention.

**Typed `plugin_args` contract** (staff-review fix). The staff
review flagged that moving `query_mode: Literal["batch",
"per-query"]` from a typed top-level field into a free-form
`plugin_args:` map drops schema validation: a typo (e.g.
`per-querie`) would parse at freeze time, pin the wrong
sealed_hash, and surface as a plugin-CLI error mid-run.

Pick: **`plugin_args` is a typed sub-model contributed by the
plugin package itself**, not a free-form `dict[str, Any]`.
Razorback ships a `PluginArgsRegistry` discovered at install
time via entry points (`razorback.plugin_args` group). Each
plugin exports a Pydantic model:

```python
# razorback_plugin_dab/plugin_args.py
class DabPluginArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_variant: Literal["direct-minimal", "direct-structured", "spacedock"] = "direct-minimal"
    query_mode: Literal["batch", "per-query"] = "per-query"
    hints: bool = False
    data_root: Path | None = None
```

`HarborBenchmarkBlock` carries `plugin_args: dict[str, Any] |
None = None` at parse time; a model_validator looks up
`self.plugin` in the registry and re-parses `plugin_args` against
the plugin's Pydantic model, raising `SpecError` with the
plugin's canonical validation message on failure. Spec authors
get the same parse-time typing they had with
`HarborDabBenchmarkBlock.query_mode`; the validation cost moves
into the plugin package rather than into razorback core.

**`trial_name_map` contract** (staff-review fix, paired with the
above). Today's `_build_harbor_dab:382-433` constructs a
`trial_name_map` of shape `(dataset, list[int])` vs
`(dataset, int)` per `query_mode`. The reducer at
`src/razorback/runs/aggregate.py:190-205` reads
`reward_per_query.json` and consumes that map.

Under the plugin contract, the plugin's `generate` subprocess
emits a `view_manifest.json` extension carrying its own
`trial_name_map_v2` shape: `{tasks: [{slug, query_ids:
list[int]}]}`. `_build_harbor`'s plugin route reads this
post-generate, constructs the in-memory map, and threads it
through to harbor exactly as `_build_harbor_dab` does today.
Plugins that don't emit the extension don't get
`reward_per_query.json`-shaped aggregation — pure pass-through
plugins (when those exist) just use the default
`(dataset, int)` shape derived from `PackageTaskId.name`.

This keeps the captain's "simple config" framing intact for the
common case (pure pass-through) and provides one well-defined
escape valve for the generative case with typed args + typed
trial-map handoff. There is exactly one plugin in-tree today
(`razorback-plugin-dab`); the contract is documented now in §2.6
so the second plugin doesn't have to invent it.

### §2.7 What dies in `translate.py` and surrounding code

- `_build_ade_bench` (lines 211-309) — deleted; functionality
  folds into `_build_harbor` (no behavior loss: image override
  was moved to the harbor adapter, deny-globs move to the
  spacedock-solver agent's runtime hook layer).
- `_build_harbor_dab` (lines 312-449) — replaced by
  `_build_harbor`'s plugin route per §2.6.
- `_build_spider2_dbt` (lines 451-499) — replaced by
  `_build_harbor_local`.
- `_build_local` (lines 193-208) — unchanged; serves
  `kind: local` (raw task_paths).
- `materialize_ade_harbor_task_view` and its `view_manifest.json`
  schema — stays as the implementation of `harbor_tasks/` per
  spec §6.1's "Task-view materialization" paragraph;
  `_build_harbor` calls it to apply the per-task transforms
  (image override, deny-globs, env injection) when the spec or
  agent block configures them. The interface stays; the call
  site moves from `_build_ade_bench` to `_build_harbor`.

**Agent-kind interaction with the smoke gate** (staff-review
fix). The scaffolded `drivers/matrix.sh.tmpl` smoke gate
(§2.3 step 3) checks `subagent-trace-manifest.json captured >
0` — but only for spacedock-variant trials. Per ne's choice
(`src/razorback/audit/subagent_traces.py` only fires when
`agent.kind == spacedock_solver`), `agent.kind: claude-cli`
trials skip the smoke gate. Both scenarios in §1 use
`spacedock_solver` so they're covered. A researcher who picks
`agent.kind: claude-cli` (e.g., captain's earlier 7q
direct-structured work) gets:
- No `subagent-trace-manifest.json` written (the inner agent
  has no subagent crew to trace).
- The smoke gate skips per-trial (correct).
- `rk audit --policy strict` still fires (it's
  benchmark/agent-kind-agnostic — taint.py scans the inner
  agent's tool-use stream).

The scaffold's `specs/baseline.yaml.j2` defaults to
`spacedock_solver` per the §1 scenarios; researchers who want
`claude-cli` edit the spec by hand. The scaffold does NOT
generate a `--target-agent-kind claude-cli` mode in this entity
— the captain authorizes adding it as a sibling entity if
demand exists.

### §2.8 The `rk score` autoresearch hook + `rk audit` chaining

The scenarios use `rk score --against-constant paper=0.476`. The
scaffold's `experiment_meta.paper_baseline` block makes the
constant **implicit**: when `experiment_meta.paper_baseline` is
set in the frozen spec, `rk score` auto-applies it without the
flag. Small UX win over the current explicit
`--against-constant <name>=<value>` (which still works as an
override).

**Taint surfacing in `rk score`** (staff-review fix). After
`rk audit` writes `audit.json` to the run-dir, `rk score`
reads it and surfaces a `taint_status:` line in its output
(clean/suspect/tainted counts). Scaffold consumers see the
clean attestation alongside the score; researchers cannot
ship a verdict that silently dropped a tainted trial. If
`audit.json` is missing, `rk score` warns and proceeds
(soft-fail to keep the old behavior workable; the matrix
driver hard-fails on missing audit.json per §2.3).

`rk diff` (deferred per spec §3.2) ships unchanged — it is the
hypothesis-pairing primitive both scenarios assume. No code
changes from this entity for `rk diff` itself; the spec amendment
in §2.10 documents the autoresearch flow with taint-paired
attestations.

### §2.9 The matrix dispatcher (`examples/drivers/`)

Today: `dab-paper-matrix.sh` (DAB-specific). The scaffold drops
a generic template at `~/<slug>-research/drivers/matrix.sh.tmpl`
that researchers edit when they want to fan one spec out across
hypothesis variants × concurrency knobs. Razorback does not ship
a generic matrix runner — matrix dimensions are intrinsically
per-experiment.

The DAB-specific dispatcher at `examples/drivers/dab-paper-matrix.sh`
moves to `~/dab-research/drivers/` as a per-project artifact (the
captain's DAB research repo) once that lives outside this
monorepo, or stays in-tree under `examples/drivers/legacy/` as
the DAB-paper-reproduction historical artifact.

### §2.10 Spec amendment scope

The v2 spec changes in this entity:

- **§5 (Autoresearch workflow templates)** — extend with two
  concrete sub-sections:
  - **§5.4 `rk research new` flow** — documents the scaffold
    command, the template tree at
    `docs/templates/research-project/` + per-template
    contracts from §2.3 (especially the
    `solver_workflows/baseline/README.md.j2` required
    sections), the benchmark-defaults table, and the
    autoresearch loop's "live" criteria.
  - **§5.5 Worked examples** — embeds the dabstep +
    swe-bench-verified scenarios from §1 above verbatim (the
    spec carries the user narrative as a normative example; the
    design doc carries the derivation). Includes the full
    `rk run` → `rk audit` → `rk score` → `rk diff` chain
    with taint surfacing in `rk score`.
- **§6.1 (Top-level shape)** — minor revision: the existing
  example YAML (line 728-734) updates from `kind: harbor_dab`
  to `kind: harbor`. The cycle-1 15-line addition (commit
  `fa0374a`) rewrites to drop the `prep:` discriminator language
  (replaced by the §2.6 `plugin:` typed-args escape valve) and
  drop the collapse-partial framing (now collapse-and-migrate
  per the captain directive).
- **§1.3 (Non-goals)** — adds a clarifying bullet that
  razorback ships **one** benchmark block (`kind: harbor`) plus
  one local escape (`kind: harbor-local`) plus one raw-task
  escape (`kind: local`); the per-benchmark Pydantic classes
  are deliberately not a razorback surface.
- **§3.2 (Subcommand surface)** — append `rk score`'s
  auto-pulled `experiment_meta.paper_baseline` behavior +
  the new `taint_status:` line in `rk score` output.
- **§7 (Run-dir contract)** — append `audit.json` and
  `subagent-trace-manifest.json` to the per-cell artifact
  inventory; both are now baseline-required for the
  autoresearch loop per §1.

No other §-sections change. The full diff is ~120 lines (up
from ~80 in the cycle-3 first pass).

### §2.11 Migration commits sequence

Six commits ship the migration (each ~independently reviewable):

1. `_build_harbor` + `HarborBenchmarkBlock` (already shipped:
   commits `6cbcaa8`, `f9f3143`; rebased onto current main
   in this cycle's revision).
2. `rk research new` command + `docs/templates/research-project/`
   tree + `docs/templates/benchmark-defaults.toml`. Per-template
   contents per §2.3.
3. **Migrate existing example specs in `examples/specs/`** from
   `kind: ade-bench` / `kind: harbor_dab` / `kind: spider2-dbt`
   to the new shape. Delete the deprecated kind-specific specs
   that have no analogue. Re-freeze any frozen specs the matrix
   dispatchers consume. **This commit explicitly captures the
   agent-side sealed_hash break** (per §2.4): commit message
   names that the view-manifest `benchmark_kind` field changes
   from `"ade-bench"` / `"harbor_dab"` / `"spider2-dbt"` to
   `"harbor"` / `"harbor-local"`, every pre-migration
   freeze-CAS entry becomes orphaned, and consumers must
   `rk freeze --rehash` every frozen spec they intend to
   resume. The commit body includes the consumer-facing
   migration recipe.
4. Delete `AdeBenchBenchmarkBlock`, `Spider2DbtBenchmarkBlock`,
   `HarborDabBenchmarkBlock` (replaced by `HarborBenchmarkBlock`
   + `HarborLocalBenchmarkBlock` + plugin escape), delete
   `DabBenchmarkBlock` (legacy SUPERSEDED). Wire `plugin:`
   dispatch in `_build_harbor` per §2.6's typed `plugin_args`
   + `trial_name_map_v2` contracts. Add the
   `razorback.plugin_args` entry-point registry.
5. Surface `taint_status:` in `rk score` output (reads
   `audit.json` from the run-dir, soft-fails when absent).
   Auto-pull `experiment_meta.paper_baseline` when set on the
   frozen spec.
6. v2 spec amendment per §2.10 (six §-sections touched).

Commit 1 is in-tree. Commits 2-6 sequence naturally once
captain approves this design.

### §2.12 What this entity does NOT cover

- `rk diff` implementation (deferred per spec §3.2; both
  scenarios assume it exists at autoresearch-loop-live time).
  Ships when paired-test demand exists.
- Generic aggregator beyond `rk score`. The scenarios use
  `rk score` only; matrix-aggregation scripts stay
  per-research-project.
- Authentication for private Harbor datasets. Both example
  benchmarks (dabstep + swe-bench-verified) are anonymous; auth
  ships when a consumer needs it.
- Promotion (`rk baseline promote`) — already deferred per
  spec §3.2; both scenarios stop at "live autoresearch loop"
  without invoking promotion.

---

## §3 Recommendation

Ship the design as described. No backwards-compat layer per
captain directive. Six-commit migration sequence per §2.11.

**This cycle's revisions** (from cycle-3 first pass + staff
design review at
`docs/razorback-implementation/_evidence/staff-review-hm-design.md`):

- §1.1 + §1.2 scenarios now show `rk audit --policy strict` +
  `taint_status:` surfacing in `rk score` + the smoke-gate
  precondition for "live." ne's wiring is treated as current
  behavior (it merged earlier this session).
- §2.3 specifies per-template contents for
  `solver_workflows/baseline/README.md.j2` and
  `drivers/matrix.sh.tmpl` — the staff review's load-bearing
  unspecified surfaces.
- §2.4 adds the freeze-inputs / sealed_hash discontinuity
  paragraph + names the orphaned freeze-CAS consequence.
- §2.6 tightens the plugin escape valve to a typed-args
  contract (Pydantic model per plugin, registered via entry
  point) + a `trial_name_map_v2` plugin-emitted shape so the
  aggregator's batch-mode path survives migration.
- §2.7 covers `agent.kind: claude-cli` behavior with the
  smoke gate (spacedock-only; claude-cli skips it; `rk audit`
  still fires).
- §2.8 surfaces `taint_status:` in `rk score` output and
  documents the hard-fail vs soft-fail policy.
- §2.11 grows to six commits — adds the spec-migration
  sealed_hash break callout (commit 3) and the
  `rk score`/taint surfacing (commit 5).

**Captain decision points** (re-answering pending; the four
cycle-3 points have changed shape):

- (a) **Ack the two revised user scenarios in §1** as the
  design driver. The flow now chains
  `rk freeze → rk run → rk audit → rk score → rk diff` with
  taint attestation. Veto if the autoresearch loop should
  treat `rk audit` differently (optional? off by default?
  gated by `--policy audit` instead of strict?).
- (b) **Ack or veto the `rk research new` scaffold contents**
  (§2.3) — specifically: (i) the
  `solver_workflows/baseline/README.md.j2` required sections
  (stages, reset declaration, External-oracle audit prose,
  optional ROLE prefix); (ii) the `drivers/matrix.sh.tmpl`
  per-cell pipeline (rk run → smoke gate → rk audit strict
  → rk score → ledger); (iii) the entry-point-discovered
  benchmark-defaults table at
  `docs/templates/benchmark-defaults.toml`.
- (c) **Ack or veto the post-migration `BenchmarkBlock` shape**
  (§2.1 + §2.2 + §2.5 + §2.6): three kinds + one plugin
  escape valve with typed `plugin_args` per plugin. Veto if
  `plugin_args` should stay free-form (the staff review's
  alternative — fewer commits, weaker validation).
- (d) **Ack or veto the migration freeze break** (§2.4 +
  §2.11 commit 3): every pre-migration freeze-CAS entry
  becomes orphaned; consumers must `rk freeze --rehash`. The
  break is permissible under "no backwards compat" — captain
  ack confirms the consumer-facing migration recipe is
  acceptable.
- (e) **NEW: Ack or veto the v2 spec amendment scope** (§2.10
  — now six §-sections touched, ~120-line diff). Particularly
  §3.2 (CLI surface) gaining `taint_status:` documentation
  and §7 (run-dir contract) gaining `audit.json` +
  `subagent-trace-manifest.json` as baseline-required
  artifacts.

(c) and (d) are the load-bearing decisions; (a) and (b) are
process / UX confirmations; (e) is doc-only and follows (c)+(d).

On approval, commits 2-6 of the §2.11 sequence ship. The
scaffold work is the substantive new code; the schema migration
is mechanical (the new union members are already in tree;
commit 4 just removes the old members and wires plugin
dispatch).

On partial veto (e.g., "keep `plugin_args` free-form for now,
revisit after the second plugin lands"), this design rewrites
the §2.6 contract and commit 4 in §2.11 shrinks.

On full reframe, this doc goes back to the drawing board with
the captain's revised framing.

---

## §4 Spike findings (preserved from cycle 2)

The ideation spike at `_spike/scratch_harbor_block.py` validated
the core mechanism end-to-end against live `adyen/dabstep@latest`.
All five spike checks passed:

1. Minimal `HarborBenchmarkBlock(kind=harbor, dataset, ...)`
   Pydantic class parses and validates.
2. Bad refs (bare names, missing ref tier) reject with errors
   that name the canonical `<org>/<name>@<ref>` shape.
3. `PackageDatasetClient.download_dataset("adyen/dabstep@latest")`
   resolves anonymously in ~3s, returns 450 `PackageTaskId`
   entries, materializes each as `task.toml + instruction.md`.
4. `JobConfig(tasks=[TaskConfig(path=resolved)])` constructs
   cleanly from the resolved task list.
5. `JobConfig` round-trips through harbor's own Pydantic model
   via `yaml.safe_dump` + `JobConfig.model_validate` — harbor
   accepts the resulting job config.

The spike surfaced **one unknown unknown** the original design
did not anticipate: `PackageTaskId.name` is heterogeneous across
harbor-published datasets:

- `adyen/dabstep`: bare integers (`'35'`, `'2712'`, ...).
- `swe-bench/swe-bench-verified`: project-prefixed slugs
  (`'matplotlib__matplotlib-14623'`).
- `dbt-labs/ade-bench`: dataset-prefixed slugs
  (`'ade-bench-f1006'`).

ADE-bench's `_strip_dataset_prefix` heuristic is ADE-specific
and would mismatch dabstep + swe-bench-verified. The generic
`_build_harbor` deliberately does NOT inherit this heuristic —
spec-side `tasks:` entries match `PackageTaskId.name` verbatim.
Consumers look up the task name on the hub page (cheaper than
fragile magic).

Spike commit: `d106ebf`. Production schema + builder + integration
test commits: `6cbcaa8`, `f9f3143` (the latter passes the live
adyen/dabstep@latest resolution in 4.4s).
