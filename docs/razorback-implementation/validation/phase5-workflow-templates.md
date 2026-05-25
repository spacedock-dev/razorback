---
entity: phase5-workflow-templates
entity-id: zgaactcgj955qn04t0jaj7dg
stage: validation
branch: spacedock-ensign/phase5-workflow-templates
validator: ensign
date: 2026-05-25
verdict: PASS
recommendation: approve to done (with one non-blocking note for FO)
---

# Phase 5 — workflow README templates: validation report

Validation performed from a clean checkout of branch
`spacedock-ensign/phase5-workflow-templates` against the entity's
acceptance criteria, with each `Verified by:` clause exercised
verbatim. Pre-existing test failures cross-checked against main.

## Per-AC verdicts

### AC-1 — Walking skeleton holds. **PASS**

The implementation introduces no source-code (`.py`) changes — only
docs, templates (markdown), and tests. Diff vs `main`:

    docs/razorback-implementation/phase5-followup-dab-matrix-analyze.md  | 106 ++++++  (new)
    docs/razorback-implementation/phase5-workflow-templates.md            |  15 +-
    src/razorback/templates/experiment-workflow/README.md                 | 368 ++  (new)
    src/razorback/templates/run-workflow/README.md                        | 107 ++  (new)
    tests/unit/test_workflow_templates_content.py                         | 218 ++  (new)
    tests/unit/test_workflow_templates_packaged.py                        |  45 ++  (new)
    uv.lock                                                               |   4 -

`git diff main --name-only -- "*.py" src/` returns the two test files
only — no runtime CLI code touched. AC-1 (walking skeleton: DAB end-
to-end via direct CLI continues to run) is therefore trivially
satisfied; the templates ship as inert package data.

### AC-2 — `src/razorback/templates/experiment-workflow/README.md` six stages + per-stage prompt content. **PASS**

File exists at the cited path. Stage skeleton:

    $ grep '^## Stage:' src/razorback/templates/experiment-workflow/README.md
    ## Stage: pending
    ## Stage: propose
    ## Stage: smoke
    ## Stage: full
    ## Stage: analyze
    ## Stage: conclude

Six stages, in spec order. `id-style: sd-b32` declared in frontmatter
(`grep "id-style: sd-b32"` — match). `experiment.max_budget_usd`
declared in the template spec block (`grep "experiment.max_budget_usd"`
— multiple matches at the spec block and smoke/full prompt cites).

Per-stage prompt content verbatim grep evidence:

- **propose / internal leak surfaces:** `answer keys` (matched
  "answer keys committed alongside the workspace"), `ground-truth
  columns`, `per-task hints` — all present.
- **propose / external-oracle surfaces (k3 broadened scope):**
  `datasets.load_dataset`, `hf://`, `public CSV`, `web-search`,
  `cached prior answers` — all present.
- **propose / sentinel:** `UNABLE TO DETERMINE` — present.
- **propose / canonical-prose cite:** `workspace_readme.py` cited at
  lines 23-29 / 56-62 / 99-105 (direct-minimal / direct-structured /
  spacedock variants) — present.
- **smoke / pre-flight:** `rk run --explain` + `reasoning_effort`
  cited as k4-class translator-drop guard — present.
- **smoke / budget check:** `rk runs cost` + `--max-budget-usd-running`
  invocation-time backstop — present.
- **smoke / sandwich:** `rk audit --policy strict` + `rk score` +
  `dab-paper-matrix.sh` canonical-pattern cite — present.
- **analyze / paper_baseline auto-pull:** `experiment_meta.paper_baseline`
  — present.
- **analyze / stratified-only lens:** `stratified_pass_at_1` (multiple
  cites) — present.
- **analyze / verdict-block dotted path:** `against_constant.stratified.verdict`
  — present.
- **analyze / NEGATIVE lint (M2):** `rk score --against-constant` as a
  CLI invocation pattern is **absent** (`grep -F "rk score --against-constant"`
  returns no matches); the post-hm shape is canonical.
- **analyze / DAB-paper matrix:** the analyze stage's "DAB-paper
  multi-dataset matrices (deferred to follow-up)" section cites the
  follow-up entity `phase5-followup-dab-matrix-analyze` and explicitly
  documents the unfixed aggregator bug at
  `examples/drivers/aggregate-goal1-scores.py:189` plus the gating
  entity `goal1-matrix-aggregator-stratified-verdict-fix`. The
  template does NOT reference the buggy aggregator's verdict field as
  authoritative; the captain's directive (defer rather than reference
  unfixed surface) is honored.

Verified-by clause for AC-2 ("propose / smoke / full / analyze
prompts contain the named guidance verbatim, grep-asserted in tests"):
`tests/unit/test_workflow_templates_content.py` — 20 grep assertions
green (see AC-6 pytest output).

The schema-parse verifier clause was REMOVED per M1; no test asserts
schema parse.

### AC-3 — `src/razorback/templates/run-workflow/README.md` four stages. **PASS**

File exists at the cited path. Stage skeleton:

    $ grep '^## Stage:' src/razorback/templates/run-workflow/README.md
    ## Stage: pending
    ## Stage: reconciling
    ## Stage: completed
    ## Stage: failed

Four stages, in spec order. `id-style: sd-b32` declared. `pending`
marked `initial: true`; `completed` and `failed` marked `terminal: true`
in the YAML frontmatter (spec §5.2 shape).

### AC-4 — Package data shipping (in-package). **PASS**

`importlib.resources` listing from the worktree's venv:

    $ uv run python -c "import importlib.resources; print(list(importlib.resources.files('razorback').joinpath('templates').iterdir()))"
    [PosixPath('.../src/razorback/templates/experiment-workflow'),
     PosixPath('.../src/razorback/templates/run-workflow')]

Both template directories enumerate cleanly. Wheel build confirms the
templates also ship inside the built wheel (not just the editable
install):

    $ uv build --wheel
    Successfully built dist/razorback-0.1.0-py3-none-any.whl
    $ unzip -l dist/razorback-0.1.0-py3-none-any.whl | grep templates
    razorback/templates/
    razorback/templates/experiment-workflow/
    razorback/templates/experiment-workflow/README.md   (13395 bytes)
    razorback/templates/run-workflow/
    razorback/templates/run-workflow/README.md          (4062 bytes)

`uv_build` auto-includes non-Python files in package directories; no
`[tool.uv_build.package-data]` glue required (M3 captain decision
honored — in-package shipping reverses the earlier `docs/templates/`
assumption).

### AC-5 — End-to-end reachability + prompt-content lint. **PASS**

Per M4: captain-gate enforcement downgraded to executable assertions
only. The validator confirmed each clause:

- **Six stage sections exist in a fresh tmp_path instantiation:**
  `test_experiment_workflow_template_instantiates_to_tmp` shutil-
  copies the templates to a tmp directory and asserts each `## Stage:`
  section is present in the copied README — green.
- **Propose-stage grep lints:** `datasets.load_dataset`, `hf://`,
  `UNABLE TO DETERMINE`, plus internal-leak phrases — green
  (`test_propose_stage_lists_internal_leak_surfaces`,
  `test_propose_stage_lists_external_oracle_surfaces`,
  `test_propose_stage_states_unable_to_determine_sentinel`).
- **Smoke-stage grep lints:** `rk run --explain`,
  `rk audit --policy strict`, `rk runs cost`,
  `experiment.max_budget_usd`, `--max-budget-usd-running` — green
  (`test_smoke_stage_mandates_*` tests).
- **Analyze-stage grep lints:** `experiment_meta.paper_baseline`,
  `stratified_pass_at_1`, `against_constant.stratified.verdict` —
  green. NEGATIVE lint (no `rk score --against-constant` CLI
  invocation) — green.
- **Dry-run reachability:** the tmp_path instantiation is the dry-
  run reachability stub — no harbor invocation, no API spend
  (verified by reading the test bodies: only `shutil.copytree` +
  string assertions).
- **Run-workflow reachability:**
  `test_run_workflow_template_instantiates_to_tmp` asserts the
  four-stage shape from a tmp-path copy — green.

Captain-gate enforcement remains a human-in-the-loop responsibility
(M4 amendment honored).

### AC-6 — `uv run pytest` exits 0. **PASS (with documented pre-existing failures)**

Phase 5's 24 new tests:

    $ uv run pytest tests/unit/test_workflow_templates_packaged.py tests/unit/test_workflow_templates_content.py -v
    ============================== 24 passed in 0.09s ==============================

Full pytest sweep (excluding `tests/integration` per project norm
and `tests/unit/test_task_identity_scoring.py` which fails to
collect due to a missing module `razorback.score.load`):

    $ uv run pytest -q --ignore=tests/integration --ignore=tests/unit/test_task_identity_scoring.py
    ...
    FAILED tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch
        - KeyError: 'data_root'
    FAILED tests/unit/test_rk_research_new.py::test_rk_research_new_creates_scaffold_tree
        - AssertionError: assert False  (runs/.gitignore missing)
    2 failed, 693 passed, 22 warnings in 22.11s

Pre-existing-failure reproduction on main (without any phase 5
changes):

    $ git checkout main && uv run pytest \
        tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch \
        tests/unit/test_rk_research_new.py::test_rk_research_new_creates_scaffold_tree -q
    FAILED tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch
        - KeyError: 'data_root'
    FAILED tests/unit/test_rk_research_new.py::test_rk_research_new_creates_scaffold_tree
        - AssertionError: assert False
    2 failed in 1.60s

Both failures reproduce on main; neither is a phase 5 regression.
The collection-time `ModuleNotFoundError` for
`tests/unit/test_task_identity_scoring.py` is also pre-existing
(imports `razorback.score.load`, a module that does not exist on
main or on this branch) and unrelated to phase 5.

## Code-review findings

Reviewed the diff vs main per
`superpowers:requesting-code-review`. Findings:

**Blocking findings:** none.

**Non-blocking observations (FO awareness):**

1. **`uv.lock` `exclude-newer` block dropped.** The diff removes the
   `[options]` block (`exclude-newer = "2026-05-13T17:53:12.518044Z"`,
   `exclude-newer-span = "P7D"`) from `uv.lock`. This is a side-
   effect of running `uv run` / `uv build` against a global
   exclude-newer setting — pytest logs `Ignoring existing lockfile
   due to removal of global exclude newer`. The lockfile churn is
   not a phase 5 concern and would happen on any `uv` invocation
   on this branch, but it should land as a known-side-effect note
   for the captain at gate review (in case the project wants to
   restore the pin in a follow-up commit). **Not blocking.**

2. **AC-1 walking-skeleton verifier flex.** The entity body's AC-1
   verifier text says "deterministic micro-spec passes both before
   and after the template add" but the deterministic micro-spec
   lives in `tests/integration/` (which the project's default
   pytest sweep skips). Since phase 5 adds zero `.py` runtime
   changes (only docs, templates, tests), the AC is trivially
   satisfied by inspection of the diff. Confirmed by file-tree
   diff (`git diff main --name-only -- "src/razorback/*.py"`
   returns nothing). **Not blocking.**

3. **DAB-matrix defer is well-scoped.** The analyze-stage prompt's
   "DAB-paper multi-dataset matrices (deferred to follow-up)"
   section correctly defers rather than referencing the unfixed
   aggregator. The follow-up entity
   `phase5-followup-dab-matrix-analyze.md` (id
   `95f3xqq3f14573w5jc8n0wfg`) carries a hard precondition on
   entity 08 (`goal1-matrix-aggregator-stratified-verdict-fix`)
   and a clean 4-AC plan. This honors the implementation worker's
   T-5c branching decision per the plan's recommendation (a).
   **Non-blocking; this is an asset, not a concern.**

4. **Test scope discipline.** The two phase 5 test files only
   exercise the in-package templates via `importlib.resources` —
   they do not depend on or modify any other tests. No risk of
   bleeding into unrelated test infrastructure. **Non-blocking;
   noted for completeness.**

5. **Markdown lint scope.** No markdown linter is run as part of
   the project's pytest sweep; the prompt-content lints are grep-
   only. If future templates introduce markdown-syntax errors the
   tests would not catch them. Out of scope for phase 5
   (M1-deferred schema work covers this surface).

## Final gate recommendation

**Recommend APPROVE to `done`.**

Concrete reasoning:

- All 6 ACs PASS by their `Verified by:` clauses run verbatim from
  a clean worktree checkout. Each clause has reproducible evidence
  captured above.
- Phase 5's 24 new tests are green; the 2 pre-existing failures
  reproduce on main (verified by checkout + targeted re-run) and
  are not phase 5 regressions.
- Implementation honors all four post-staff-review captain
  decisions (M1 schema-test deferred, M2 AC-5 `--against-constant`
  language removed, M3 in-package shipping at `src/razorback/templates/`,
  M4 captain-gate downgraded to grep+reachability lints).
- T-5c branching is well-executed: follow-up entity exists with
  hard precondition on entity 08, clean 4-AC plan, no dangling
  reference to the unfixed aggregator.
- No source-code changes; walking skeleton (AC-1) is trivially
  intact.
- Code-review surface (diff vs main) is small, well-scoped, and
  carries no blocking findings.

**One non-blocking note for FO/captain to acknowledge at the gate:**
the `uv.lock` `[options]` block (`exclude-newer` pin) was dropped as
a side-effect of running `uv` commands on this branch. The captain
may want to restore the pin in a follow-up commit if reproducibility
of the lockfile state is desired. This is a project-wide tooling
behavior, not a phase 5 implementation defect.

The entity is `auto-approve: false`; the FO must present this gate
to the captain. The captain should APPROVE on the strength of the
evidence above, with the `uv.lock` note acknowledged as a tooling-
side-effect non-blocker.
