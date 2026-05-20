---
id: 1k780ws98v5r8627hg39h31p
title: PKG-11 — Failure-mode-analysis workflow template (autoresearch report-to-batch lifecycle)
status: backlog
source: CL 2026-05-20 — previous autoresearch attempt used a two-stage shape (FM categorization + ranked-hypothesis loop) that the experiment workflow alone does not capture; needs a sibling template
score: 0.7
started:
completed:
verdict:
worktree:
issue:
pr:
mod-block:
---

## Problem

The current razorback v2 spec ships two workflow README templates:
the experiment workflow (per-hypothesis lifecycle: propose → smoke
→ full → analyze → conclude) and the run workflow (trial
reconciliation). Both are *vertical* — one entity moves through one
lifecycle.

CL's previous autoresearch attempt used a different *horizontal*
shape:

1. **Failure-mode analysis**: walk a baseline run's failed trials,
   group by (task, query, error-category), classify each group with
   a failure-mode class (FM-impl, FM-plan, FM-spec, ...), produce a
   report listing the classes plus derived hardening hypotheses,
   rank the hypotheses by lift potential.
2. **Batch smoke**: take the top-K ranked hypotheses, optionally
   override the experiment workflow's propose gate for high-lift
   candidates, smoke them in sequence at concurrency=2, promote the
   ones that show lift, drop the rest.

The experiment workflow's per-hypothesis lifecycle does not capture
this. The FM analysis is a separate research artifact (one report
spawns N hypotheses); the batch-smoke is a fan-out the experiment
workflow's single-entity dispatch does not model.

The previous autoresearch run handled this informally — FM analysis
was a one-off, hypothesis dispatch was manual. A spacedock workflow
captures the shape so the loop can run with discipline.

## Unlocks

- The autoresearch loop CL wants — automated FM analysis on each
  baseline → ranked hypotheses → batch smoke → promote/drop — runs
  end-to-end under spacedock discipline with captain gates at the
  right boundaries.
- Multiple research projects can reuse the FMA template shape
  against their own benchmarks. The template ships in razorback;
  the FM-class taxonomy and lift heuristics live in the consuming
  research repo.
- Per-cycle re-analysis (after each batch of hypothesis runs,
  generate a new FMA report against the latest run-dir) becomes a
  workflow-driven cadence rather than ad-hoc.

## Depends on

- Razorback v2 ships (the experiment workflow + run workflow
  templates per spec §5).
- The first goal-1 reproduction (or any baseline run-dir) exists,
  so an FMA report has a real input to analyze.
- `rk audit` and `rk score` ship as first-cut surfaces — the FMA
  derive stage uses them to walk failed trials and read their
  trajectories.

## Acceptance criteria

**AC-1**: spec §5 grows a §5.4 "Failure-mode-analysis workflow"
section. Names the entity (one FMA report per `(baseline_run,
analysis_pass)` pair), the stages (pending → triage → classify →
derive → rank → conclude), and the output artifact (a markdown
report at `reports/<slug>.md`).
Verified by: spec §5.4 exists; references the entity, stages, and
output shape per CL's two-stage attempt description.

**AC-2**: a workflow README template ships at
`docs/templates/failure-mode-analysis-workflow/README.md`. Standard
spacedock workflow shape; per-stage prompt content tells the
analysis-stage operator what to do (read baseline run's failed
trials; classify into FM-X categories named by the research
project, not by razorback; derive hypotheses without referencing
answer-key content; rank by lift potential).
Verified by: a captain copies the template into a fresh research
repo and instantiates it against a real baseline run-dir; the
resulting workflow parses against spacedock's schema and the
analysis-stage ensign can run end-to-end on the inputs.

**AC-3**: experiment workflow's propose stage prompt is extended to
accept a failure-mode report as input. When the entity's
frontmatter names an FMA report + a hypothesis index from that
report, the propose-stage ensign authors the solver-workflow-README
change against that specific hypothesis.
Verified by: a fixture FMA report + a hypothesis entity that
references it produces a propose-stage output (solver-workflow
diff) that matches the hypothesis's named mechanism change.

**AC-4**: experiment workflow's smoke stage supports a
`gate_override` entity-frontmatter flag (set by the FMA workflow's
rank step on `lift_confidence: high` hypotheses). When set, the
propose gate auto-approves and the entity enters smoke directly.
Captain still reviews at the analyze gate.
Verified by: a hypothesis entity with `gate_override: smoke` skips
the propose-gate captain review and lands at smoke; the analyze
gate still requires captain approval.

**AC-5**: the FMA workflow's derive stage is leak-guarded. The
derive-stage prompt forbids referencing answer-key strings,
ground-truth columns, or per-task hint files. `rk audit` runs over
the analysis agent's own trajectory before the rank stage promotes
the report's hypotheses — if the analysis agent fetched forbidden
content during analysis, the FMA report is marked tainted and
captain reviews before any hypothesis from it dispatches.
Verified by: a fixture FMA run where the analysis agent
deliberately invokes a forbidden tool flags tainted before rank;
the report's hypotheses cannot dispatch through the experiment
workflow until captain clears the taint.

**AC-6**: the rank step's output is a structured table the
experiment workflow's batch-spawn step can read. Format: one row
per candidate hypothesis with `(name, fm_class, mechanism_change,
lift_estimate, cost_estimate, lift_confidence)` fields.
Verified by: a fixture rank-step output parses against the schema;
the experiment workflow's batch-spawn (a separate captain-driven
script or a new ensign-prompt) reads the table and instantiates
hypothesis entities from the top-K.

**AC-7**: per-cycle re-analysis works. After a batch of hypothesis
runs completes, the captain can dispatch a new FMA entity against
the latest run-dir. The new FMA report's hypotheses inherit nothing
from prior FMA reports (no caching that could bleed information
across cycles); each report stands alone.
Verified by: two sequential FMA runs against the same baseline
(once before hypothesis runs, once after) produce reports that may
share FM classes but list distinct hypothesis candidates if the
intervening hypothesis runs surfaced new failure modes.

## Test plan

- **Unit tests:** FMA report schema validation; gate_override flag
  plumbing in experiment-workflow's propose stage; rank-table
  parsing.
- **Integration test:** end-to-end FMA workflow run against a
  fixture baseline run-dir; output is a markdown report with the
  expected sections; experiment workflow consumes the report and
  spawns hypothesis entities.
- **Leak-guard test:** an analysis agent that invokes a forbidden
  tool flags the FMA report tainted before rank.

## Out of scope

- Specific FM-X taxonomy (FM-impl, FM-plan, FM-spec, ...). That
  taxonomy is per-research-project; razorback's template documents
  the *shape* (per-group FM-class + evidence + lift estimate), not
  the specific class names.
- Specific lift-potential heuristics. Each research project derives
  its own.
- Automating the rank → batch-spawn step beyond captain-script
  dispatch. The batch-spawn is a thin script the captain runs after
  rank completes; building a fully-automated dispatcher is a later
  follow-up.
- Caching FM analyses across baselines. Each FMA report stands
  alone (per AC-7); cross-baseline pattern detection is a later
  research question.
- Reward-hacking analysis layer. Harbor's `harbor analyze --rubric
  reward_hacking` is the right tool for that and lives outside the
  FMA workflow; the FMA workflow does taint scanning via `rk audit`
  but does not re-implement reward-hacking critique.
