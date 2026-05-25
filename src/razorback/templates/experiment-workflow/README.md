---
commissioned-by: spacedock@0.12.1
entity-type: hypothesis
entity-label: hypothesis
entity-label-plural: hypotheses
id-style: sd-b32
stages:
  defaults:
    worktree: false
    concurrency: 2
  states:
    - name: pending
      initial: true
      gate: true
    - name: propose
      gate: true
    - name: smoke
      gate: true
    - name: full
      gate: true
    - name: analyze
    - name: conclude
      terminal: true
      gate: true
---

# Experiment workflow template

Copy this template into a research repo (e.g. `<research>/hypotheses/`)
to drive a single hypothesis from `pending` through `conclude`. Each
entity carries the hypothesis, the frozen spec it ships, and the
analyze-stage verdict against `experiment_meta.paper_baseline`.

The workflow is razorback-native (no razorback-shipped mods) — the
per-stage prompts below carry the captain-facing behavior that earlier
designs encoded in mods. Captain gates fire at every stage marked
`gate: true`; the captain enforces the prompt-guided checks at the
gate, not a runtime mod.

## Spec block

Every hypothesis entity ships a frozen spec at
`spec.frozen.yaml` (sibling to the entity body). The spec uses the
canonical v2 dispatch shape:

```yaml
agent:
  kind: spacedock_solver   # canonical post-hm (Phase 6)
  kwargs:
    reasoning_effort: high
benchmark:
  kind: harbor
  plugin: <name>           # e.g. ade-bench, spider2-dbt, dabstep
razorback:
  plugin_args: {...}       # plugin-defined; auto-resolved via entry-point
experiment:
  max_budget_usd: 5.00     # hard cap; smoke/full prompts refuse if exceeded
experiment_meta:
  paper_baseline: 0.4376   # canonical paper-baseline; rk score auto-pulls this
  paper_baseline_lens: stratified_pass_at_1
```

Captain edits the spec at `propose`; once it freezes (via the
`pending → propose → smoke` transition), the file is treated as
read-only by smoke/full/analyze.

## Stage: pending

The hypothesis enters `pending` when the captain files it. The body
carries the question being tested and the plain-English hypothesis the
experiment will reject or confirm.

- **Inputs:** captain's question; the benchmark and dataset under
  test
- **Outputs:** a seed entity body with title, source (paper section,
  prior experiment, or open question), and the
  `## Acceptance criteria` block naming the verdict the experiment
  must produce (e.g. "spacedock variant beats the paper's
  direct-baseline at p<0.05 on stratified_pass_at_1")
- **Good:** the AC names a measurable verdict against the paper
  baseline; the hypothesis is small enough to ship through smoke in
  one work session
- **Bad:** vague hypotheses ("does the agent do better"); ACs
  measured by prose deliverables instead of `score.json` fields

## Stage: propose

The captain (or an ensign at captain direction) writes the frozen
spec, the recommended solver-workflow README, and any prompt-side
guard rails. The captain reviews at the gate before smoke fires.

### Leak-guard discipline

The propose-stage prompt's primary job is to prevent the recommended
solver-workflow README from leaking ground truth into the agent's
context. Both internal and external leak surfaces are forbidden:

**Internal leak surfaces** (the benchmark's own answer artifacts):

- answer keys committed alongside the workspace
- ground-truth columns embedded in workspace databases
- per-task hints baked into READMEs or system prompts

**External-oracle lookups** (k3 surface, broadened 2026-05-25):

- HuggingFace `datasets` library — `datasets.load_dataset`,
  `hf://...` paths for label or answer lookup
- public CSV/JSON downloads of the same dataset (kaggle, GitHub,
  vendor sites, cached mirrors)
- web-search engines, search APIs, kaggle downloads
- LLM-as-oracle calls (asking another model "what is the answer
  to X")
- cached prior answers from earlier runs or any artifact outside
  the current workspace

The recommended solver-workflow README must state: **the workspace
data is the only authoritative source. If a question is unanswerable
from it, the agent returns `"UNABLE TO DETERMINE"`.**

### Canonical leak-guard prose

Copy the `## Rules` block from
`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/workspace_readme.py`
(lines 23-29 / 56-62 / 99-105 — direct-minimal / direct-structured /
spacedock variants) as the canonical leak-guard prose for the
solver-workflow README. The DAB plugin's renderer is the source of
truth; new benchmark plugins should re-use it via the
`razorback.plugin_args` entry-point rather than re-derive it.

### Captain gate

The captain reviews the propose-stage output (frozen spec +
recommended solver-workflow README) at the `propose → smoke` gate.
The captain rejects if the README references any of the forbidden
external-oracle surfaces above, if the frozen spec is missing
`experiment.max_budget_usd` or `experiment_meta.paper_baseline`, or
if `agent.kind` is not `spacedock_solver` (Phase 6 canonical).

**Captain-gate enforcement is human-in-the-loop, not a razorback-
shipped mod.** Phase 5 + spec §8.5 collapse: the leak-guard /
tool-deny-runtime / baseline-compare / cost-ceiling mods fold to
per-stage prompt content + `tools_denied` spec block field + the
`rk run --max-budget-usd-running` CLI flag.

## Stage: smoke

A cheap end-to-end exercise of the frozen spec on a minimal slice of
the dataset. The smoke prompt drives the operator-ensign through a
pre-flight, a budget check, and the per-cell sandwich.

### Pre-flight: `rk run --explain`

Before any live burn, run `rk run --explain --explain-format json
<frozen-spec>` to resolve the spec end-to-end WITHOUT invoking
Harbor. The explain plan is free; it surfaces translator drops and
plugin-arg resolution mistakes at zero cost.

Verify the resolved plan against the frozen spec:

- `agent.kind: spacedock_solver` resolves cleanly (Phase 6)
- `agent.kwargs.reasoning_effort` matches the spec's declared
  value (catches k4-class translator drops where the field silently
  drops on the claude-cli path)
- `benchmark.plugin` resolves via the `razorback.plugin_args`
  entry-point to the expected `PluginArgs` class
- `razorback.plugin_args` validates against the plugin's pydantic
  schema (catches typos before they burn API)

If the explain plan disagrees with the frozen spec, STOP and surface
to the captain. Do not proceed to live burn.

CLAUDE.md rule: "validate smallest end-to-end exercise of the
riskiest path FIRST." `rk run --explain` is the smallest possible
exercise — zero API spend, zero docker, zero harbor invocation —
and it catches the riskiest contract (spec-to-runtime translation)
before any spend.

### Budget check: `rk runs cost`

Before dispatching the smoke run, check the running budget against
`experiment.max_budget_usd`:

```bash
rk runs cost <run-root>
```

Refuse to dispatch if the running total + the estimated smoke cost
exceeds `experiment.max_budget_usd`. The
`rk run --max-budget-usd-running <file>` flag is the invocation-time
backstop; the prompt's pre-dispatch check is the cheap front-stop.

### Per-cell sandwich: `rk run` → `rk audit --policy strict` → `rk score`

For each cell in the smoke slice:

```bash
rk run <frozen-spec> --task-id <task> --out <cell-dir>
rk audit --policy strict <cell-dir>
rk score <cell-dir>
```

The audit step (wp-shipped 2026-05-23 surface) walks the run's
event log + agent JSONL for forbidden external-oracle calls;
`--policy strict` fails the run if any are found. The canonical
sandwich pattern lives at
`examples/drivers/dab-paper-matrix.sh:217-225`.

Each cell produces `audit.json` + `score.json`. The next-stage
analyze prompt cites the audit verdict explicitly.

### Captain gate

At the `smoke → full` gate, the captain reviews:

- the smoke slice's `score.json` outputs (per-cell pass rate)
- the audit verdicts (any `--policy strict` failures block
  promotion to full)
- the running cost against `experiment.max_budget_usd`
- whether the smoke result is consistent with the hypothesis
  (the captain may abandon the hypothesis here rather than
  burning the full budget)

## Stage: full

Same sandwich as smoke, run over the full dataset (all cells of the
matrix the hypothesis targets). The full prompt repeats the smoke
prompt's discipline — pre-flight, budget check, per-cell sandwich —
at full-dataset scale.

### Pre-flight, budget, sandwich

- `rk run --explain --explain-format json <frozen-spec>` once at
  the start; confirm the resolved plan matches the smoke-stage
  resolved plan (no spec drift)
- `rk runs cost <run-root>` before dispatch and at every cell
  checkpoint; refuse if the running total exceeds
  `experiment.max_budget_usd`
- Per-cell: `rk run` → `rk audit --policy strict` → `rk score`,
  same as smoke

### Cell-level budget gating

For long-running matrices, the invocation-time backstop is the
authoritative cost ceiling. Pass
`--max-budget-usd-running <budget-file>` to each `rk run`
invocation; the runner refuses to dispatch the next cell once the
shared budget file's running total crosses the cap.

### Captain gate

At the `full → analyze` gate, the captain reviews:

- the full matrix's per-cell `audit.json` + `score.json`
- any `--policy strict` audit failures (these block promotion;
  the analyze stage cannot run on incomplete data)
- the final running cost against `experiment.max_budget_usd`

## Stage: analyze

Roll up the matrix's per-cell `score.json` files into a hypothesis-
level verdict against the paper baseline.

### Single-benchmark, task-binary workflows

For single-benchmark workflows (ADE-bench / swe-bench-verified /
spider2-dbt / dabstep / etc.):

```bash
rk score <run-dir>
```

The `score.json`'s `stratified_pass_at_1` field is the
benchmark-canonical headline. `rk score` auto-pulls
`paper_baseline` from `spec.frozen.yaml`'s
`experiment_meta.paper_baseline` (hm commit 5 surface) — **do NOT
pass `--against-constant` on the CLI** unless the run lacks a
paper-canonical baseline. The post-hm shape is canonical.

Inspect the verdict block in `score.json`:

```json
{
  "stratified_pass_at_1": <number>,
  "against_constant": {
    "stratified": {
      "verdict": "above" | "inside_ci" | "below",
      "ci_low": <number>,
      "ci_high": <number>,
      "paper_baseline": <number>
    }
  }
}
```

The headline cites the lens (stratified_pass_at_1), the value,
the paper_baseline, and the direction read from
`against_constant.stratified.verdict` (the dotted path into
`score.json`).

### DAB-paper multi-dataset matrices (deferred to follow-up)

The DAB-paper matrix-aggregator path (12 cells over the DAB
dataset, rolled up via `examples/drivers/aggregate-goal1-scores.py`)
is **deferred to a follow-up entity**
(`phase5-followup-dab-matrix-analyze`).

The aggregator currently has a known bug at
`examples/drivers/aggregate-goal1-scores.py:189`: it computes
`per_query_verdict` from `pooled_per_query_ci` instead of the
stratified mean. Entity
`goal1-matrix-aggregator-stratified-verdict-fix` is in flight; once
that lands, the follow-up entity authors the DAB-matrix half of
this analyze prompt and references the fixed aggregator.

Until then, the DAB-paper matrix uses the single-benchmark path
above on the matrix-aggregator output once entity-08's fix lands.

### Stratified-only headline directive (captain standing 2026-05-25)

The analyze-stage report's HEADLINE cites the benchmark-canonical
stratified lens against the paper baseline. Pooled-per-query and
binary-pooled numbers MAY appear in supplementary tables but MUST
NOT lead the headline. The captain has standing direction
(2026-05-25) that the stratified lens is the default for
paper-comparison verdicts; stratified-only headline is the rule.

### Audit-coverage caveat for spacedock-variant runs

Until `gv audit-scanner-subagent-jsonl-coverage` ships, `rk audit
--policy strict` on `agent.kind: spacedock_solver` runs does NOT
walk the subagent JSONL at
`agent/sessions/projects/*/*.jsonl`. The audit verdict on
spacedock-variant runs is structurally incomplete on this gap;
the prompt surfaces this caveat to the captain explicitly when the
frozen spec's `agent.kind` is `spacedock_solver`. Document the
limitation as a known caveat until `gv` ships.

### Output

Paste the relevant JSON block from `score.json` into the entity
body under `## Analyze`. Write a verdict line citing:

- the lens (stratified_pass_at_1)
- the measured value
- the paper_baseline value
- the direction (above paper / inside CI / below paper)
- for spacedock_solver runs, the audit-coverage caveat above

## Stage: conclude

Terminal. The captain reviews the analyze-stage verdict and writes
the conclusion paragraph:

- whether the hypothesis is confirmed, rejected, or inconclusive
- what the captain learned (the verdict is one signal; the
  per-cell audit findings and per-cell failure modes are the
  other signals)
- the follow-up hypotheses this experiment surfaces

The entity is marked `verdict: PASSED` (hypothesis ran cleanly to
conclusion, regardless of whether the agent beat the baseline)
or `verdict: REJECTED` (the experiment failed to reach analyze
cleanly — e.g., audit failures, budget overrun, broken spec).

The captain gate at `analyze → conclude` is the human enforcement
point for the experimental conclusion. No razorback-shipped mod
enforces this; the captain reads the analyze output and writes
the conclude block.
