# Phase 5 — solver workflow README templates: implementation plan

Plan for `phase5-workflow-templates` (entity id `zgaactcgj955qn04t0jaj7dg`).
Spec source: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §5
(5.0 / 5.1 / 5.2 / 5.3). Entity body governs amendments — see the
2026-05-25 Amendments block on Acceptance Criteria for the 6-shipped-
surface rewording (k3 / wp / hm / k4 / codex `rk run --explain` /
stratified-only headline).

> **Post-staff-review amendments 2026-05-25.** A staff reviewer
> surfaced 4 Material findings; captain resolved each. The plan
> below is updated in place; original wording preserved in git
> history. Summary:
>
> - **M1 (T-2 schema test):** DEFERRED. T-2 becomes a no-op
>   placeholder; AC-2 / AC-3 schema-parse verifier clauses REMOVED
>   from the entity body. Schema drift catching = future entity.
> - **M2 (AC-5 `--against-constant` text):** entity body AC-5 fixed
>   in place; T-10 already correctly avoided the legacy CLI shape.
> - **M3 (T-8 `uv_build` layout):** RESOLVED. Templates ship
>   IN-PACKAGE at `src/razorback/templates/{experiment-workflow,
>   run-workflow}/README.md`. No `uv_build` force-include glue
>   needed. T-8 simplifies; no spike required.
> - **M4 (T-10 captain-gate integration test):** DOWNGRADED. T-10
>   integration test = prompt-content lints + dry-run reachability
>   only. Captain-gate enforcement is human-in-the-loop, not
>   pytest-runnable. T-10's verifier list updated below.
>
> Q1 / Q2 / Q3 captain answers (pre-staff-review) also refined:
> Q1 = src/razorback/templates/ (REVISED post-M3, was
> docs/templates/); Q2 = assume 08 lands with fallback note (held);
> Q3 = N/A (M1 deferred the schema test entirely).

## AC ↔ task map

| AC | Description | Tasks |
|----|-------------|-------|
| AC-1 | Walking skeleton holds (deterministic micro-spec still passes) | T-1, T-9 |
| AC-2 | `docs/templates/experiment-workflow/README.md` exists with 6 stages + per-stage prompt content (propose / smoke / full / analyze) | T-2, T-3, T-4, T-5, T-7 |
| AC-3 | `docs/templates/run-workflow/README.md` exists with 4 stages | T-6 |
| AC-4 | Package data shipping (`importlib.resources` reads both template dirs from installed wheel) | T-8 |
| AC-5 | End-to-end hypothesis smoke (propose → freeze → smoke → analyze → conclude) | T-10 |
| AC-6 | `uv run pytest` exits 0 | T-9 |

Cite for each per-stage prompt clause: spec §5.1 (stage table) is
the source-of-truth row-by-row. The amendment block on the entity
body re-anchors propose/smoke/full/analyze prompt language to the
6-shipped surfaces — the plan must implement the entity-body
language, not the spec §5.1 table (which predates the amendments).

## Mechanism validation (confirmed prior to T-1)

These three artifacts must exist and be discoverable before
implementation can begin. Confirmed as of 2026-05-24:

1. **Spacedock workflow-README parser** — canonical parser lives at
   `/Users/clkao/git/spacedock/skills/commission/bin/status` (the
   `status` script the workflow directory consumes). It enforces
   the entity-schema fields (`commissioned-by`, `entity-type`,
   `id-style`, `stages.defaults`, `stages.states[]`) the templates
   must match. AC-2 / AC-3 schema tests parse against this script's
   `--validate` mode (or its YAML reader directly).
2. **Canonical leak-guard prose** — lives in
   `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/
   workspace_readme.py:23-29` (direct-minimal variant), :56-62
   (direct-structured), :99-105 (spacedock variant). The four
   forbidden surfaces enumerated there (HuggingFace `datasets` /
   `hf://`, public CSV/JSON downloads, web/LLM oracles, cached
   prior answers) ARE the k3-shipped scope the AC-2 propose-stage
   prompt language must reference. T-4 cites this file as the
   recommended leak-guard prose for solver-workflow READMEs.
3. **Matrix-aggregator fix entity status** —
   `goal1-matrix-aggregator-stratified-verdict-fix` (entity id
   `08ghk1yvkq9vzs71gzecx5bf`) is **at `plan` stage, NOT yet
   archived**. The bug it fixes lives at
   `examples/drivers/aggregate-goal1-scores.py:189` (the
   `per_query_verdict = _verdict(pooled_per_query_ci)` line).
   **DAB-paper-matrix path in AC-2's analyze prompt is GATED on
   entity 08 archiving.** See T-5 sequencing below.

## Risky-contract ordering

Per CLAUDE.md "validate smallest end-to-end exercise of the
riskiest path FIRST." The riskiest contract here is not the
template text — it is whether `importlib.resources` can serve
the template dirs from an installed wheel under razorback's
`uv_build` backend (AC-4). T-8 (package-data shipping) precedes
the bulk of template text authoring; an empty placeholder
`README.md` proves the wheel-shipping contract before the
template prose is finalized. T-10 (end-to-end smoke) is the
final integration test.

## Tasks

### T-1: Pre-flight — confirm walking skeleton still green (AC-1, AC-6)

- Run the deterministic micro-spec suite that AC-1 calls out
  (the existing nop spec / direct-CLI smoke). Capture exit code
  and a one-line `pytest`/`rk` invocation receipt.
- Run `uv run pytest -q` against the current `main` to establish
  the baseline that AC-6 must reproduce after all template work
  lands.
- **TDD checkpoint:** none — this is a baseline observation, not
  a code change. Output of this step is the receipt to compare
  against in T-9.
- **Spec cite:** §1.3 (walking-skeleton invariant), §5 (templates
  must not break direct-CLI use).

### T-2: Schema-test scaffolding (AC-2, AC-3) — DEFERRED post-staff-review M1

> **DEFERRED 2026-05-25 per M1 captain decision.** The schema-parse
> test is removed from phase5 scope. `status --validate <path>` has
> no stable contract for arbitrary file paths (it operates on workflow
> directories, not individual files), and re-implementing the YAML
> frontmatter parse inline duplicates schema knowledge. Captain
> chose to defer; phase5 ships without automated schema validation.
> AC-2 and AC-3 verifier text in the entity body updated accordingly
> (the "parses against spacedock's workflow-README schema" clause
> REMOVED).
>
> **What replaces it:** T-7 (content-verification tests) carries the
> grep-asserted prompt-content checks for each stage's required
> guidance phrases. No structural schema check.
>
> **Original T-2 content preserved below for git-history audit.**

- Write a failing test under `tests/` (likely
  `tests/test_workflow_templates_schema.py`) that:
  1. opens each of `docs/templates/experiment-workflow/README.md`
     and `docs/templates/run-workflow/README.md`,
  2. parses YAML frontmatter (the same shape the spacedock
     `status` script consumes — `commissioned-by`, `entity-type`,
     `entity-label`, `id-style`, `stages.defaults`,
     `stages.states[].name`/`.initial`/`.gate`/`.terminal`/etc.),
  3. asserts the experiment-workflow has exactly the six stages
     (pending, propose, smoke, full, analyze, conclude) in
     declared order with `pending.initial: true` and `conclude.gate:
     true`,
  4. asserts the run-workflow has exactly four stages (pending,
     reconciling, completed, failed) with `pending.initial: true`,
     `completed.terminal: true`, `failed.terminal: true`,
  5. asserts both templates declare `id-style: sd-b32` (per AC-2's
     "sd-b32 ID style" requirement).
- The test must fail before T-3 / T-6 land (no templates exist
  yet). After T-3 + T-6 it must pass.
- **TDD checkpoint:** failing-test-first. Do NOT implement the
  template files until this test exits non-zero with a
  "templates missing" error.
- **Spec cite:** §5.1 (experiment-workflow stages), §5.2 (run-
  workflow stages), §5.3 (solver-workflow README contract is
  separate, not implemented here).

### T-3: Experiment-workflow template — frontmatter + stages skeleton (AC-2)

- Create `docs/templates/experiment-workflow/README.md` with:
  - frontmatter matching the spacedock workflow-README schema
    (`commissioned-by: spacedock@<pinned-version>`, `entity-type:
    hypothesis`, `entity-label-plural: hypotheses`, `id-style:
    sd-b32`, `stages.defaults.worktree: false`,
    `stages.defaults.concurrency: 2`, and the six `stages.states[]`
    entries),
  - `experiment.max_budget_usd` declared in the template spec
    body (per AC-2 verbatim),
  - the six `## Stage: <name>` body sections in the order the
    frontmatter declares.
- Body text for propose / smoke / full / analyze is deferred to
  T-4 / T-5; this task ships the skeleton only.
- Commit message: `phase5: experiment-workflow template skeleton`.
- **TDD checkpoint:** re-run the T-2 schema test; the structural
  assertions (stage names, order, terminal/gate flags) MUST now
  pass. The body-content assertions in T-4 / T-5 still fail.
- **Spec cite:** §5.1 stages table.

### T-4: Experiment-workflow `propose` stage prompt — leak-guard prose (AC-2, broadened scope)

- Author the body of the `## Stage: propose` section. Required
  content per the 2026-05-25 amendments block on the entity:
  - The propose-stage prompt instructs the operator-ensign on
    what the solver-workflow README MUST NOT reference.
  - Scope covers BOTH internal leak surfaces (answer keys,
    ground-truth columns, per-task hints — the original AC-2
    language) AND external-oracle lookups (k3 surface):
    HuggingFace `datasets.load_dataset`, `hf://` paths, public
    CSV/JSON downloads, web-search oracles, kaggle downloads,
    cached prior answers from earlier runs.
  - Cite `packages/razorback-plugin-dab/src/
    razorback_plugin_dab/generate/workspace_readme.py`'s `## Rules`
    block (lines 23-29 / 56-62 / 99-105) as the canonical leak-
    guard prose to copy into the recommended solver-workflow
    README.
  - State that the captain reviews the propose-stage output at
    the gate (captain-gate enforcement, NOT a razorback-shipped
    mod — per spec §5.1 "Required mods. None ship from razorback
    in the first cut").
- Add a verbatim-content assertion to the T-2 schema test (or a
  sibling content test) that the propose-stage section contains
  the four named external-oracle surfaces (`HuggingFace`,
  `public CSV`, `web-search` or `LLM-as-oracle`, `cached prior
  answers`) — single source of truth lives in the entity body,
  this test pins the template to it.
- **TDD checkpoint:** content assertion is failing-test-first.
- **Spec cite:** §5.1 propose row + §6.2 `tools_denied` (runtime
  PreToolUse blocking — complement to the static-check that the
  propose-stage prompt enforces). Entity-body amendment block
  is the load-bearing source.

### T-5: Experiment-workflow `smoke` / `full` / `analyze` stage prompts (AC-2)

This task contains three sub-deliverables. Their sequencing is
constrained by the entity-08 precondition (matrix aggregator).

**T-5a: smoke + full stage prompts (no entity-08 dependency)**

- Author `## Stage: smoke` and `## Stage: full` body sections.
  Both must mandate:
  1. `rk run --explain --explain-format json <frozen-spec>` as a
     cheap per-cell pre-flight gate BEFORE any live burn (codex
     surface, on main at commit `d967c4c`). Verify resolved
     `agent.kwargs.reasoning_effort` matches the spec
     (translator-drop catch, k4-class).
  2. `rk runs cost <root>` budget check before dispatch; refuse
     if running total + estimate exceeds
     `experiment.max_budget_usd`. The `rk run
     --max-budget-usd-running <file>` flag is the invocation-time
     backstop (spec §5.1 "Required mods" note).
  3. Per-cell sandwich: `rk run` → `rk audit --policy strict` →
     `rk score`. Cite
     `examples/drivers/dab-paper-matrix.sh:217-225` as the
     canonical pattern (wp-shipped gate). Each cell produces
     `audit.json` + `score.json`; the next-stage analyze prompt
     cites the audit verdict explicitly.
- Cite CLAUDE.md's "validate smallest end-to-end exercise of the
  riskiest path FIRST" rule in the smoke-stage prose (per entity-
  body amendment).
- Extend T-2's content test with assertions for the four named
  CLI invocations (`rk run --explain`, `rk runs cost`, `rk audit
  --policy strict`, `rk score`).
- **No entity-08 dependency** — can ship as soon as T-3 lands.

**T-5b: analyze stage prompt — single-benchmark path (no entity-08 dependency)**

- Author the single-benchmark-task-binary half of `## Stage:
  analyze`:
  - For single-benchmark workflows (ADE-bench / swe-bench-
    verified / spider2-dbt / dabstep / etc.): run `rk score
    <run-dir>`. The `score.json`'s `stratified_pass_at_1` field
    is the canonical headline.
  - `rk score` auto-pulls `paper_baseline` from
    `spec.frozen.yaml`'s `experiment_meta.paper_baseline` (hm
    commit 5 surface). **Do NOT pass `--against-constant` on the
    CLI** unless the run lacks a paper-canonical baseline.
  - Stratified-only headline (captain standing directive
    2026-05-25): the analyze-stage report's headline cites the
    benchmark-canonical stratified lens against the paper
    baseline. Pooled-per-query and binary-pooled numbers MAY
    appear in supplementary tables but MUST NOT lead the
    headline.
  - Paste the relevant JSON block into the entity body; write a
    verdict citing lens + value + paper_baseline + direction
    (above / inside CI / below).
  - Audit-coverage caveat for spacedock-variant runs: until
    `gv audit-scanner-subagent-jsonl-coverage` ships, `rk audit
    --policy strict` on `agent.kind: spacedock_solver` runs does
    NOT walk the subagent JSONL at
    `agent/sessions/projects/*/*.jsonl` — the analyze-stage
    prompt must surface this gap to the captain when the spec's
    agent kind is `spacedock_solver`. Document as a known caveat
    until `gv` ships.

**T-5c: analyze stage prompt — DAB-paper-matrix path (GATED on entity 08)**

- Author the DAB-paper multi-dataset-matrix half of the analyze
  stage:
  - For DAB-paper multi-dataset matrices (12 cells over the DAB
    dataset): use the matrix aggregator
    (`examples/drivers/aggregate-goal1-scores.py` or successor).
    The aggregator emits
    `per_query_pass_at_1_mean_over_strata` which IS the paper-
    canonical lens for DAB.
- **PRECONDITION:** entity 08
  (`goal1-matrix-aggregator-stratified-verdict-fix`) must be
  ARCHIVED before T-5c lands. The bug at
  `examples/drivers/aggregate-goal1-scores.py:189` makes
  `against_constant.per_query_verdict` compute against
  `pooled_per_query_ci` instead of the stratified mean. The
  analyze-stage prompt for DAB-paper matrices cannot reference
  the aggregator's verdict field until the fix lands.
- **Branching logic at implementation-stage dispatch time:** if
  entity 08 is archived → ship T-5c as part of phase5
  implementation. If entity 08 is still at plan/implementation
  /validation → split T-5c to a follow-up entity
  (`phase5-followup-dab-matrix-analyze`) and ship phase5
  validation with the single-benchmark path only. The captain
  decides the branch at impl-stage gate review.

### T-6: Run-workflow template (AC-3)

- Create `docs/templates/run-workflow/README.md` with:
  - frontmatter (`commissioned-by`, `entity-type: run`,
    `entity-label-plural: runs`, `id-style: sd-b32`,
    `stages.defaults.worktree: false`, the four `stages.states[]`),
  - the four `## Stage: <name>` body sections (pending,
    reconciling, completed, failed),
  - no stage-completion-signal mod content (spec §5.2 defers
    halt-resume's real-mod machinery; the template ships
    without them).
- **TDD checkpoint:** the T-2 schema test's run-workflow
  assertions now pass.
- **Spec cite:** §5.2.

### T-7: Stage-prompt content test (AC-2 cont.)

- If not already folded into T-2 / T-4 / T-5, write a separate
  test that verbatim asserts the named guidance phrases in each
  per-stage prompt of the experiment-workflow template:
  - propose: external-oracle surface names (HuggingFace,
    public CSV/JSON, web-search, cached prior answers); the
    workspace_readme.py file path cite.
  - smoke / full: `rk run --explain`, `rk runs cost`, `rk audit
    --policy strict`, `rk score` invocations; the dab-paper-
    matrix.sh:217-225 cite for the sandwich pattern.
  - analyze: `stratified_pass_at_1`, `experiment_meta.
    paper_baseline`, stratified-only headline directive
    language, the `gv` audit-coverage caveat for spacedock-
    variant runs.
- **TDD checkpoint:** drives the content authoring in T-4 / T-5.

### T-8: Package data shipping (AC-4) — RISKY CONTRACT, ships EARLY (M3 resolved 2026-05-25)

- Per the "Risky-contract ordering" note above, T-8 ships as
  soon as T-3 has a minimal skeleton (and BEFORE T-4 / T-5
  prose work is finalized).
- **M3 captain decision (2026-05-25):** templates ship IN-PACKAGE
  at `src/razorback/templates/{experiment-workflow,
  run-workflow}/README.md`. No `uv_build` force-include glue
  required; standard `package-data` declaration in pyproject.toml
  is sufficient. The earlier `docs/templates/...` working-tree
  home is dropped — no symlink, no `[tool.uv_build.package-data]`
  out-of-package mapping, no spike needed.
- The AC-4 verification command remains:
  `python -c "import importlib.resources; print(list(
  importlib.resources.files('razorback').joinpath('templates')
  .iterdir()))"` which resolves cleanly because the templates ARE
  in the package namespace at `razorback/templates/...`.
- Write a failing test under `tests/` that runs the AC-4
  verification command (or its `importlib.resources.files`
  equivalent in-process) and asserts both directories appear.
  Test must fail before T-8 ships and pass after.
- **TDD checkpoint:** failing-test-first on the wheel-shipping
  contract. This is the riskiest single mechanism in phase 5.
- **Spec cite:** §5 (templates ship as package data); §5.0
  notes `rk research new` will eventually consume them but that
  is out-of-scope for phase 5.

### T-9: Regression sweep (AC-1, AC-6)

- Re-run T-1's deterministic micro-spec — must still pass.
- Run `uv run pytest -q` — must exit 0 with the same passing
  count as T-1's baseline plus the new schema/content/
  package-data tests added in T-2 / T-7 / T-8.
- If any pre-existing test regressed, STOP and surface to the
  captain rather than fixing in this phase (per CLAUDE.md "fix
  broken things immediately when you find them" — but only after
  surfacing the unexpected regression).

### T-10: Reachability + prompt-content smoke (AC-5) — DOWNGRADED post-staff-review M4

> **DOWNGRADED 2026-05-25 per M4 captain decision.** The original
> T-10 asserted "the captain gate rejects a deliberate leak-guard
> violation" — but a captain gate is human-in-the-loop; pytest
> cannot exercise it. T-10 is now a reachability + prompt-content
> lint test, NOT an end-to-end harbor-burn integration test. Docker /
> Colima / provider auth are NOT required for this test.

- Pytest under `tests/test_workflow_templates_reachability.py` (or
  similar) that:
  1. Reads the in-package templates via
     `importlib.resources.files('razorback').joinpath('templates')`
     (per AC-4 / T-8 contract); confirms both `experiment-workflow/`
     and `run-workflow/` subdirs are accessible from the installed
     package surface.
  2. Asserts via grep on the experiment-workflow stage prompts'
     text content that the named guidance phrases are present
     verbatim per AC-5's verifier list:
     - **propose-stage** prompt contains: `datasets.load_dataset`,
       `hf://`, `UNABLE TO DETERMINE`, plus internal-leak-surface
       phrases (`answer keys`, `ground-truth columns`,
       `per-task hints` — or paraphrases matching k3's prose).
     - **smoke-stage** prompt contains: `rk run --explain`,
       `rk audit --policy strict`, `rk runs cost`,
       `experiment.max_budget_usd`, `--max-budget-usd-running`.
     - **analyze-stage** prompt contains:
       `experiment_meta.paper_baseline`, `stratified_pass_at_1`,
       `against_constant.stratified.verdict`, and does NOT contain
       `--against-constant` as a CLI invocation (lint that the
       post-hm shape is canonical).
  3. Asserts the six stage subdirs / sections are addressable from
     a fresh template instantiation (`tmp_path` copy of the
     templates; reachability stub — no harbor invocation, no API
     spend). For each stage, the stub workflow driver can resolve
     the next-stage path.
- **Captain-gate enforcement is OUT OF SCOPE for this test.** The
  human captain enforces the gate at runtime; the test asserts
  only that the prompt contains the named leak-guard guidance the
  captain will read.
- **TDD checkpoint:** failing-test-first against the grep
  assertions. Drives the prompt-content authoring in T-4 / T-5.
  No `@pytest.mark.integration`, no docker, no API spend.
- **Spec cite:** §5.1 (per-stage prompt-content shape), §5
  (templates ship with the per-stage prompt content that drives
  this).

## Sequencing summary

```
T-1 (baseline)
 └─ T-2 (failing schema test)
     ├─ T-3 (experiment skeleton)        ─┐
     │   └─ T-8 (package data, EARLY)     │  parallel-safe
     ├─ T-6 (run-workflow template)       │
     ├─ T-4 (propose prompt — k3)        ─┤
     ├─ T-5a (smoke/full — codex/wp/k4)   │
     ├─ T-5b (analyze single-benchmark)   │
     └─ T-5c (analyze DAB-matrix)       ───┘  GATED on entity 08 archiving
T-7 (content test, may merge into T-2/T-4/T-5)
T-9 (regression sweep — AC-1 + AC-6)
T-10 (end-to-end smoke — AC-5)
```

T-5c is the only entity-08-gated task. Implementation-stage
dispatch must check entity 08's status:

- entity 08 archived → ship T-5c in phase5
- entity 08 not archived → split T-5c to follow-up entity
  `phase5-followup-dab-matrix-analyze`; phase5 ships
  validation with single-benchmark path only

This sequencing keeps the riskiest contracts (T-8 package-data
shipping, T-10 end-to-end) explicit and front-loaded relative to
the bulk prose work in T-4 / T-5.

## Out of scope (per entity body)

- Razorback-shipped workflow mods (leak-guard, tool-deny-runtime,
  baseline-compare, cost-ceiling, stage-boundary-freeze,
  phase-stats-writer) — spec §8.5 collapse.
- `rk init` scaffolding subcommand (D4 default: defer until
  consumer materializes).
- Failure-mode-analysis workflow template (filed as `1k`
  follow-up).
- `rk research new` scaffolding (spec §5.0; out-of-scope for
  phase 5 even though it consumes phase 5's templates).

## Open questions for captain at gate review

1. **Template canonical home.** `src/razorback/templates/...` (in-
   package) vs `docs/templates/...` (out-of-package with build-
   system glue) — T-8 mechanism investigation will surface
   `uv_build`'s actual capability. Captain decides if the
   plan/impl phase can resolve this internally or needs a
   pre-implementation spike.
2. **T-5c branching.** If entity 08 is still in flight at impl-
   stage dispatch, does the captain prefer (a) splitting T-5c
   to a follow-up entity and shipping phase5 with single-
   benchmark analyze only, or (b) blocking phase5 impl-stage
   until entity 08 archives? The plan recommends (a) — phase5
   ships the path that's safe to ship and tracks the DAB-matrix
   work as a follow-up.
3. **Test framework for spacedock-schema parse.** The schema
   test in T-2 can either (a) shell out to the spacedock
   `status` script in `--validate` mode (requires spacedock on
   PATH or as a test dependency) or (b) re-implement the
   YAML-frontmatter parse inline in the test. Plan recommends
   (b) for hermeticity — captain confirms?
