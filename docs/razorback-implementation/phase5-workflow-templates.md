---
id: zgaactcgj955qn04t0jaj7dg
title: Phase 5 — solver workflow README templates
status: backlog
source: plan Phase 5 + spec §5 (v2 spec at docs/superpowers/specs/2026-05-19-razorback-on-harbor.md)
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
mod-block:
---

## Problem

Phase 5 ships the two workflow README templates per spec §5:
`docs/templates/experiment-workflow/README.md` (six stages: pending,
propose, smoke, full, analyze, conclude) and
`docs/templates/run-workflow/README.md` (four stages: pending,
reconciling, completed, failed). Both ship as package data so a
captain can copy them into a new research repo. No razorback-shipped
mods — per-stage prompt content carries the stage-level behavior the
prior mod design enumerated (leak-guard at propose, budget-check
prompt at smoke/full, analyze prompt calls `rk score
--against-constant` or `rk diff`).

Phase 5 ships AFTER Phase 6 because Phase 6 promotes v2 to canonical
`agent.kind: spacedock_solver`; Phase 5's templates reference the
canonical name, so they must come after the rename or they dangle on
`spacedock_solver`. The end-to-end hypothesis smoke (AC-5.4) is
the strongest single demonstration of v2 razorback's integration
shape working as a unit.

## Acceptance criteria

> **Amendments 2026-05-25 by FO at captain directive.** Session work
> from 2026-05-23 through 2026-05-25 shipped surfaces phase5's
> originally-filed ACs predate: k3 (workspace-readme leak-guard prose
> for external-oracle lookups), wp (rk audit --policy strict gate),
> hm (kind: harbor + plugin: <name> generic dispatch + rk score
> `paper_baseline` auto-pull from `experiment_meta.paper_baseline`
> spec frontmatter), k4 (translator reasoning_effort threading),
> codex's `rk run --explain` pre-flight, and 7q + d8 + an's
> three-way crew-loop study with the stratified-only headline
> directive. The AC body below is updated in place; the ORIGINAL
> 2026-05-NN language is preserved in the entity's git history.
> Key shifts: analyze stage uses `paper_baseline` auto-pull (NOT
> CLI `--against-constant`); smoke/full add `rk run --explain` +
> `rk audit --policy strict` per-cell gates; stratified-only headline
> per captain standing directive; propose-stage leak-guard scope
> broadens to external-oracle lookups (k3-shipped language).

**AC-1 — Walking skeleton holds.**
Razorback continues to run DAB end-to-end via the direct CLI; Phase
5 adds the workflow templates without breaking direct CLI use.
Verified by: deterministic micro-spec passes both before and after
the template add. Per plan AC-5.1.

**AC-2 — `docs/templates/experiment-workflow/README.md` exists with
six stages and the required per-stage prompt content.**
- six stages: pending, propose, smoke, full, analyze, conclude
- sd-b32 ID style
- `experiment.max_budget_usd` declared in the template spec
- **propose** prompt: instructs the operator-ensign on what the
  solver-workflow README must not reference. **Scope (broadened
  2026-05-25 per k3-shipped surface):** both internal leak surfaces
  (answer keys, ground-truth columns, per-task hints) AND external-
  oracle lookups (HuggingFace `datasets.load_dataset`, `hf://`
  paths, public CSV/JSON downloads of the same dataset, web-search
  oracles, kaggle downloads, cached prior answers from earlier
  runs). Captain reviews at the gate. Recommend citing
  `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/
  workspace_readme.py`'s `## Rules` block as the canonical leak-
  guard prose to copy into the propose-stage's recommended
  solver-workflow README.
- **smoke** / **full** prompts:
  - Run **`rk run --explain --explain-format json <frozen-spec>`**
    as a cheap per-cell pre-flight gate BEFORE any live burn
    (codex-shipped 2026-05-24 surface). Verify resolved
    `agent.kwargs.reasoning_effort` matches the spec (k4-class
    translator drops are caught here at zero cost). Cite
    CLAUDE.md's "validate smallest end-to-end exercise of the
    riskiest path FIRST" rule.
  - Run `rk runs cost <root>` before dispatch and refuse if
    running total + estimate exceeds `experiment.max_budget_usd`;
    the `rk run --max-budget-usd-running <file>` flag is the
    invocation-time backstop.
  - Per-cell discipline: sandwich `rk run` between **`rk audit
    --policy strict`** and `rk score` (wp-shipped gate; canonical
    sandwich pattern at `examples/drivers/dab-paper-matrix.sh:217-
    225`). Each cell produces `audit.json` + `score.json`; the
    next-stage analyze prompt cites the audit verdict explicitly.
- **analyze** prompt:
  - For **single-benchmark, task-binary** workflows (ADE-bench /
    swe-bench-verified / spider2-dbt / dabstep / etc.): run `rk
    score <run-dir>`. The `score.json`'s `stratified_pass_at_1`
    field is the canonical-for-that-benchmark headline; the
    `against_constant.stratified.verdict` block is the verdict
    line. `rk score` auto-pulls `paper_baseline` from
    `spec.frozen.yaml`'s `experiment_meta.paper_baseline` (hm
    commit 5 surface) — **do NOT pass `--against-constant` on
    the CLI** unless the run lacks a paper-canonical baseline.
  - For **DAB-paper multi-dataset matrices** (12 cells over the
    DAB dataset): use the matrix aggregator
    (`examples/drivers/aggregate-goal1-scores.py` or successor).
    The aggregator emits `per_query_pass_at_1_mean_over_strata`
    which IS the paper-canonical lens for DAB. **PRECONDITION:**
    the aggregator's `against_constant.per_query_verdict` field
    currently computes against `pooled_per_query_ci` instead of
    the stratified mean (filed as the aggregator-fix entity in
    `## Depends on`); that fix must land before phase5 references
    the matrix-aggregator path.
  - **Stratified-only headline** (captain standing directive
    2026-05-25): the analyze-stage report's headline cites the
    benchmark-canonical stratified lens against the paper
    baseline. Pooled-per-query and binary-pooled numbers MAY
    appear in supplementary tables but MUST NOT lead the
    headline.
  - Paste the relevant JSON block into the entity body; write a
    verdict that cites the lens + value + paper_baseline +
    direction (above / inside CI / below).
  - **Audit-coverage caveat for spacedock-variant runs:** until
    `gv audit-scanner-subagent-jsonl-coverage` ships (filed
    2026-05-25), `rk audit --policy strict` on
    `agent.kind: spacedock_solver` runs does NOT walk the
    subagent JSONL at `agent/sessions/projects/*/*.jsonl` —
    the audit verdict on spacedock-variant runs is structurally
    incomplete. The analyze-stage prompt must surface this gap
    to the captain when the spec's agent kind is
    `spacedock_solver`; document the limitation as a known caveat
    until `gv` ships.
Verified by: the template parses against spacedock's workflow-README
schema; the propose / smoke / full / analyze stage prompts contain
the named guidance verbatim. Per plan AC-5.2.

**AC-3 — `docs/templates/run-workflow/README.md` exists with four
stages.**
Four stages (pending, reconciling, completed, failed). No
stage-completion-signal mods required because halt-resume's real-mod
machinery defers per AC-3.6's hand-fake note (spec §5.2).
Verified by: the template parses against spacedock's workflow-README
schema. Per plan AC-5.2.

**AC-4 — Package data shipping.**
`pyproject.toml` ships `docs/templates/` so a captain can copy
templates into a new project.
Verified by: `python -c "import importlib.resources; print(list(
importlib.resources.files('razorback').joinpath('templates').iterdir()))"`
lists both template directories from an installed razorback wheel.
Per plan AC-5.3.

**AC-5 — End-to-end hypothesis smoke (AC-5.4).**
A captain copies the experiment-workflow template into a fresh dir,
instantiates it against DAB via the new harbor adapter, and runs ONE
hypothesis end-to-end (propose → freeze → smoke → analyze →
conclude). The full path works.
Verified by: integration test executes the smoke end-to-end:
- propose-stage prompt + captain gate catch a deliberate leak-guard
  violation (the smoke's propose stage tries to reference an
  answer-key column; the captain gate rejects)
- smoke-stage prompt enforces budget via `rk runs cost`
- analyze stage produces `rk score --against-constant` output in
  the entity body
- conclude stage is reachable

Per plan AC-5.4. This is Phase 5's strongest single demonstration.

**AC-6 — `uv run pytest` exits 0.**
Per plan AC-5.5.

## Test plan

- **Schema tests:** both templates parse against spacedock's
  workflow-README schema (likely via spacedock's own parser).
- **Package data test:** the installed wheel exposes
  `templates/experiment-workflow/` + `templates/run-workflow/` via
  `importlib.resources`.
- **Stage-prompt content test:** propose / smoke / full / analyze
  prompts contain the named guidance phrases verbatim.
- **End-to-end smoke (AC-5):** the AC-5.4 hypothesis cycle runs
  against the harbor-DAB adapter; outputs land per the named
  expectations.
- **Acceptance command:** captain copies the template into a fresh
  dir, dispatches one hypothesis end-to-end; the analyze stage's
  entity body carries `rk score --against-constant` output.

## Out of scope

- Razorback-shipped workflow mods (leak-guard, tool-deny-runtime,
  baseline-compare, cost-ceiling, stage-boundary-freeze,
  phase-stats-writer). Spec §8.5 documents the collapse: the first
  four collapse to per-stage prompt content + spec block field
  (`tools_denied`) + CLI flag (`--max-budget-usd-running`); the
  last two defer with halt-resume's real-mod machinery.
- `rk init` scaffolding subcommand. D4's default: defer until
  consumer materializes; templates ship as copy-and-modify.
- Failure-mode-analysis workflow template. `1k`
  pkg11-failure-mode-analysis-workflow filed as post-v2 follow-up.

## Depends on

> **Dependency list reworked 2026-05-25 by FO at captain directive.**
> Many of the originally-cited dependencies shipped during the
> 2026-05-23..2026-05-25 work window; their roles are now consumed
> by phase5's template prompts. The Phase 6 ordering note is
> partially obsolete (hm already collapsed per-benchmark kinds to
> `kind: harbor + plugin: <name>` at the dispatch shape; Phase 6's
> remaining role is the v2-canonical rename + cleanup, not the
> dispatch shape itself). Original wording preserved in git history.

**Hard preconditions** (must land before phase5 references the
named surface):

- **Aggregator-fix entity** (filed at backlog 2026-05-25 as
  `goal1-matrix-aggregator-stratified-verdict-fix`): the matrix
  aggregator at `examples/drivers/aggregate-goal1-scores.py:189`
  computes `per_query_verdict` from `pooled_per_query_ci` instead
  of the stratified mean. Phase5's analyze-stage prompt for
  DAB-paper-shape multi-dataset matrices references this aggregator;
  the verdict must compute against the paper-canonical stratified
  lens before phase5 ships.

**Shipped surfaces phase5 consumes** (all DONE / archived):

- **`hm generic-harbor-benchmark-surface-design`** (DONE,
  PR #2 merged): collapse per-benchmark `kind:` into
  `kind: harbor + plugin: <name>` + `razorback.plugin_args`
  entry-point. Phase5's template spec block uses this canonical
  shape, NOT the legacy `kind: harbor_dab` / `kind: ade-bench` /
  `kind: spider2-dbt` forms. Also ships `rk score` auto-pulling
  `experiment_meta.paper_baseline` from spec frontmatter
  (hm commit 5), which the analyze-stage prompt relies on.
- **`k3 dab-workspace-readme-leak-guard-prose-port`** (DONE,
  PR #1 merged): canonical leak-guard prose for workspace
  READMEs (HuggingFace `datasets.load_dataset` / `hf://` /
  public CSV downloads / web-search oracles / cached prior
  answers — forbidden). Phase5's propose-stage prompt cites this
  prose as the recommended template for solver-workflow READMEs.
- **`wp dab-verify-stage-external-oracle-audit`** (DONE, merged
  pre-session): `rk audit --policy strict` gate + extended
  `audit/taint.py` with claude-cli scanner. Phase5's smoke/full
  stage prompts mandate the per-cell `rk run` → `rk audit
  --policy strict` → `rk score` sandwich.
- **`k4 translate-reasoning-effort-thread-through-claude-cli`**
  (DONE, PR #3 merged): translator threads `reasoning_effort`
  on the claude-cli code path. The `rk run --explain` pre-flight
  in phase5's smoke/full prompts verifies the threading at
  per-cell zero cost.
- **codex `rk run --explain`** (DONE, commit `d967c4c` on main):
  pre-flight planner that resolves a spec without invoking Harbor.
  Phase5's smoke/full prompts mandate this as the cheap pre-flight
  gate before live burn.

**Awareness-of** (relevant but not blocking):

- **`gv audit-scanner-subagent-jsonl-coverage`** (filed at backlog
  2026-05-25): extends audit scanner to subagent JSONL traces.
  Phase5's analyze-stage prompt surfaces the current spacedock-
  variant audit-coverage gap as a known caveat until gv ships.
- **`et translate-prompt-file-thread-through-claude-cli`** (filed
  at backlog 2026-05-25): k4 sibling for prompt_file threading.
  Phase5 templates don't currently use `agent.prompt_file`, so
  this doesn't block; awareness-of only.
- **`phase4a-rk-runs-cost`** (DONE; phase5's smoke/full prompts
  reference this command)
- **`phase4a-rk-run-budget-gate`** (DONE; invocation-time backstop
  the smoke/full prompts reference)
- **`phase4a-rk-score-wilson-stratified`** (DONE; the underlying
  `rk score` surface phase5's analyze stage invokes)
- **`phase4a-rk-audit-taint-port`** (DONE; wp's ship is the
  current state of this surface)

**Phase 6 (`phase6-promote-v2-canonical`) — relationship reframed:**

The original dependency note said "phase5 ships AFTER phase6 because
phase6 promotes v2 to canonical `agent.kind: spacedock_solver`;
phase5's templates reference the canonical name." That's now
partially obsolete:

- hm already established `agent.kind: spacedock_solver` as the
  active dispatch shape (k3 + wp + hm + k4 sequence all use it
  unambiguously)
- Phase 6's remaining work is the v2-promotion-related cleanup,
  not the dispatch shape itself
- Phase 5 can ship templates that reference `agent.kind:
  spacedock_solver` independently of when Phase 6 ships

The strict ordering "phase5 after phase6" can be relaxed to
"phase5 references `agent.kind: spacedock_solver` (already canonical
post-hm); phase6 finishes the v2 cleanup independently." The
captain may choose to keep the strict ordering for narrative
discipline, but it's no longer mechanically required.
