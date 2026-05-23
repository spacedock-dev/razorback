# Validation: DAB consumes Harbor dataset definitions

- **Entity:** `dab-harbor-dataset-definition`
- **Branch:** `spacedock-ensign/dab-harbor-dataset-definition`
- **Worktree:** `.worktrees/spacedock-ensign-dab-harbor-dataset-definition`
- **Head:** `80f64e1`
- **Base (where branch forked from main):** `0cb8751`

## Decision

**APPROVE** to `done`.

All 5 ACs pass with reproducible evidence on a fresh checkout of the worktree
branch. The implementation's bundle (47 tests) reproduces cleanly. No
qh-introduced runtime regressions found in the full-suite regression — the
non-bundle failures listed in §3 are branch-drift artifacts (phase6-promote-v2
landed on main after qh branched) and one bug in a pre-existing test that
qh's API change happened to surface; both are addressed by the post-merge
reality and not blocking.

## 1. Bundle reproduction (validation checklist #1)

### Core slice — razorback root
```
$ uv run pytest tests/unit/test_harbor_dab_dataset_ref.py \
    tests/unit/test_spec_harbor_dab_block.py \
    tests/unit/test_translator_harbor_dab.py \
    tests/unit/test_generate_dab_paper_matrix_from_definition.py \
    tests/unit/test_aggregate_goal1_from_definition.py \
    tests/unit/test_in_tree_dab_deprecation.py \
    tests/unit/test_dab_spec_parse.py
============================== 32 passed in 0.28s ==============================
```

### Plugin slice — run from `packages/razorback-plugin-dab` (avoid `tests/unit` namespace collision)
```
$ uv run pytest tests/unit/test_dataset_definition.py \
    tests/unit/test_datasets_catalog.py tests/unit/test_stratum_tagging.py
============================== 15 passed in 0.05s ==============================
```

**Bundle total: 47/47 PASSED** — matches the implementation's claim (32 core +
15 plugin).

Note on running the bundle from the repo root verbatim: pytest collection
errors with `ModuleNotFoundError: No module named 'tests.unit.test_dataset_definition'`
because the plugin's own `tests/unit/` package shares a name with the
root-level `tests/unit/` package. The plugin tests must be invoked from
`packages/razorback-plugin-dab/`. Not a logic bug; just a workspace
discovery artifact. Flagging for the captain in case a unified runner script
is wanted.

## 2. Full-suite regression (validation checklist #1)

```
$ uv run pytest -m 'not integration' --timeout=60 -q \
    --ignore=tests/unit/test_task_identity_scoring.py
10 failed, 566 passed, 8 skipped, 4 deselected, 25 warnings in 33.89s
```

- `test_task_identity_scoring.py` collection error (`razorback.score.load`
  no longer importable) is **pre-existing on main** and not introduced by qh
  — reproduced on main standalone. Excluded to let the rest run.
- The 10 failures all classify as branch-drift, not qh-introduced
  regressions — see §3.

## 3. Failure classification (the 10 non-bundle failures)

### Branch-drift from phase6-promote-v2-canonical (main rebase will resolve)

These 8 tests reference `spacedock_solver_v2` literals or the legacy
`build_spec(variant, dataset)` 2-arg signature. On `main` (post-phase6) they
were renamed/rewritten to use `spacedock_solver` and don't exist in the
v2-named form. qh did not introduce these literals — `git diff
0cb8751..HEAD | grep ^+ | grep spacedock_solver` returns zero new
references.

- `tests/unit/test_claude_benchmark_spec_generator.py::test_goal1_claude_specs_use_per_variant_agent_kind`
- `tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch`
- `tests/unit/test_generate_matrix_specs.py::test_matrix_specs_query_mode_batch_for_all_variants`
- `tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_spacedock_variant_emits_spacedock_solver_v2_kind`
- `tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_direct_minimal_variant_emits_claude_cli_kind`
- `tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_direct_structured_variant_emits_claude_cli_kind`
- `tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_spacedock_solver_workflow_path_exists`
- `tests/unit/test_generate_matrix_specs_per_variant_kind.py::test_spacedock_block_does_not_carry_tools_allowed_default_csv`

For the `test_generate_matrix_specs_per_variant_kind` failures: qh's T6
extended `build_spec` from 2 args to 3 (`variant, dataset, dataset_ref`).
The pre-existing test calls `build_spec("spacedock", "bookreview")` (2-arg).
On main, this test file was rewritten (`spacedock_solver` literal, different
signature) so the conflict won't survive a merge. **Not blocking**, but
qh's stage report should call this out — flagged below.

### Branch-drift from `test_rk_run_nop.py`
- `tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end` —
  qh's branch has the strict version (`assert lines, "events.jsonl is empty"`);
  on main this assertion is now tolerant ("Harbor may leave it empty for
  local nop runs; when rows exist, they must be valid JSON"). The test
  passes on main and fails on qh's branch with the same empty `events.jsonl`.
  Pre-merge state, not qh's doing.

### Pre-existing environmental failure
- `tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs`
  — fails on main too with `dataset bookreview not hydrated, found LFS
  pointer`. Reproduced on main standalone (1 failed, 2 passed). Environment
  issue (LFS hydration), not a code regression.

## 4. AC-by-AC verification

### AC-1 — DAB has a Harbor-style dataset definition source of truth — **PASS**

Verified by inspection of
`packages/razorback-plugin-dab/src/razorback_plugin_dab/dataset.toml`. Top-level
keys `name`, `version`, `description`, `workspace_variants`, plus a list of
`[[datasets]]` entries with `name`, `backends`, `query_count`, `query_ids`,
`schema_version`. Harbor-style identity shape (parallel to ade-bench@1.0),
not razorback-internal.

**Query count cross-check** — implementation report flagged the AC-1
"verified-by" cite of 53 was stale; ground truth is 54. Independent
verification:

```
$ python3 -c "print(4+3+13+2+4+4+3+3+3+3+5+7)"
54
$ for d in /Users/clkao/git/dataagentbench/data/query_*/; do
    ds=$(basename $d)
    count=$(ls -d ${d}query[0-9]*/ 2>/dev/null | wc -l | tr -d ' ')
    echo "$ds: $count"
  done
query_agnews: 4
query_bookreview: 3
query_crmarenapro: 13
query_DEPS_DEV_V1: 2
query_GITHUB_REPOS: 4
query_googlelocal: 4
query_music_brainz_20k: 3
query_PANCANCER_ATLAS: 3
query_PATENTS: 3
query_stockindex: 3
query_stockmarket: 5
query_yelp: 7
```

Sum = 54. `dataset.toml` matches per-dataset breakdown exactly. The dataset.toml
`query_ids` lists are 1-indexed enumerations matching the on-disk `query<N>/`
directories.

Verified by tests:
- `test_dab_dataset_definition_parses_to_pydantic_model`
- `test_definition_dataset_count_matches_paper_baseline` (asserts 12 ds)
- `test_definition_total_query_count_matches_paper_baseline` (asserts 54 q)
- `test_definition_workspace_variants_match_paper`
- `test_get_dataset_returns_entry_by_name`
- `test_get_dataset_raises_for_unknown_name`

### AC-2 — Razorback DAB specs can consume that definition — **PASS**

Schema diff at `src/razorback/spec/schema.py`:
- New optional `dataset: str | None = None` field with `<name>@<version>`
  format validator.
- `data_root: Path | None = None` (was required); `datasets: list[str] =
  Field(default_factory=list)` (was `min_length=1`).
- `_dataset_or_data_root` post-validator requires the legacy pair when
  `dataset:` is absent, preserving the old contract for legacy specs.

Translator diff at `src/razorback/translate.py:396-440`: dataset-ref branch
loads `load_default_definition()`, checks `definition.ref ==
spec.benchmark.dataset` (errors with an upgrade hint on mismatch), then
either uses the explicit `datasets:` subset or enumerates all datasets in
the definition. `data_root` falls back to env default
(`$DATAAGENTBENCH_DATA_ROOT` or `~/dataagentbench/data`) when not set.

Verified by tests:
- `test_harbor_dab_accepts_dataset_ref_without_data_root` — dataset-only spec parses
- `test_harbor_dab_dataset_ref_with_subset` — subset selector works
- `test_harbor_dab_legacy_shape_still_parses` — **legacy compat**
- `test_harbor_dab_legacy_shape_requires_data_root_when_no_dataset_ref`
- `test_harbor_dab_rejects_unknown_dataset_ref_format`
- `test_translator_uses_dataset_ref_to_enumerate_datasets`
- `test_translator_legacy_shape_still_works` — **legacy translator path**

### AC-3 — Goal 1 generation reads the dataset definition — **PASS**

`examples/drivers/generate-dab-paper-matrix-specs.py` now loops over
`definition.workspace_variants × definition.datasets` and threads
`definition.ref` through to `build_spec(..., dataset_ref=...)`. Emitted spec
carries `benchmark.dataset: dab@1.0`. Round-trip test:

- `test_generator_round_trip_matches_definition` runs the generator end-to-end
  into `tmp_path` and asserts emitted cells match
  `definition.workspace_variants × definition.datasets`.
- `test_generator_emits_query_mode_batch_for_all_variants` covers the
  query_mode behavior knob.

### AC-4 — Scoring consumes adapter-provided strata — **PASS**

`examples/drivers/aggregate-goal1-scores.py` reads `definition.datasets` for
stratum enumeration. `packages/razorback-plugin-dab/.../stratum_tagging`
attaches `dataset_name` + `schema_version` to per-task manifests from the
definition. Verified by `test_aggregate_goal1_from_definition.py` (2 tests)
and `test_stratum_tagging.py` (3 tests).

### AC-5 — The old DAB adapter split is reduced — **PASS**

Canonical: `kind: harbor_dab + dataset: dab@<version>`. Legacy: `kind: dab`
(in-tree) emits `DeprecationWarning` from
`src/razorback/benchmarks/dab/prepare.py:62-67`:

> `"in-tree DAB adapter (kind: dab) is dev-only; use kind: harbor_dab +
> dataset: dab@1.0 for canonical runs."`

Verified by `test_in_tree_dab_emits_deprecation_warning` —
DeprecationWarning is raised, contains both `harbor_dab` and `dab`,
references `dab@1.0`. Honors captain directive "reduce, not remove":
in-tree path keeps working (so existing fixture specs aren't broken), and
new canonical Goal 1 specs use the dataset ref.

Example specs `examples/specs/{bookreview-claude-in-tree-dab,dab-dev-claude,dab-dev-claude-subset}.yaml`
carry "dev-only" ABOUTME markers pointing at the canonical replacement.

### Design audit (validation checklist instruction (a)/(b)/(c))

- (a) **dataset.toml schema shape is Harbor-style**: Top-level identity
  (`name`/`version`/`description`/`workspace_variants`) plus inventory list,
  not a razorback-internal tabular shape. Matches the AC-1 ask.
- (b) **query_mode + ordering hints stay on the spec block**: `grep -n
  query_mode src/razorback/spec/schema.py packages/razorback-plugin-dab/...`
  returns only `src/razorback/spec/schema.py:161`. Dataset identity is
  orthogonal to spec-block behavior knobs. Correct.
- (c) **In-tree `kind: dab` deprecation message is informative**: Names the
  exact canonical replacement (`harbor_dab + dataset: dab@1.0`). Will give a
  user enough to migrate without grepping docs. Informative.

## 5. Code review

### Strengths
- TDD discipline visible in the commit log: 11 atomic commits, RED test
  commits precede GREEN feature commits where applicable (`071ec0f test:
  AC-1 Verified-by check` after `3ee909b feat: DAB dataset.toml + loader`,
  etc.).
- Clean separation between dataset identity (`dataset.toml`) and behavior
  (`query_mode`, `workspace_variant`, `hints`) on the spec block.
- The translator's dataset-ref branch errors clearly when the spec asks for
  a version the shipped plugin doesn't carry — actionable upgrade hint.
- The schema model_validator rejects the half-state `dataset=None AND
  data_root=None` early at parse time, not deep in the translator.
- AC-1's verified-by count was discovered to be stale (53 → 54) and fixed
  with a per-dataset breakdown comment in the test — independently
  cross-checked against `data/query_*/query[0-9]*/` (54).

### Non-blocking issues

- **Stage report should call out the build_spec signature change.** qh's T6
  extended `build_spec(variant, dataset)` to
  `build_spec(variant, dataset, dataset_ref)`. The pre-existing test
  `test_generate_matrix_specs_per_variant_kind.py::test_spacedock_variant_emits_spacedock_solver_v2_kind`
  (and 4 siblings) calls the 2-arg form and now throws `TypeError`. On main
  this test file was rewritten (phase6-promote-v2-canonical) so the
  conflict will not survive a merge — but on the worktree branch it
  silently breaks. Recommend the implementation report add a one-line
  callout: "build_spec gained a required `dataset_ref` parameter — callers
  in `test_generate_matrix_specs_per_variant_kind.py` (pre-phase6) are
  expected to be replaced by the post-phase6 versions at merge."

- **Datasets catalog `_build_catalog` runs at module import.**
  `DAB_DATASETS = _build_catalog()` triggers `load_default_definition()` at
  import time. Fine for production (the toml ships in the wheel) but
  introduces a hidden dependency: any future test that imports
  `razorback_plugin_dab.datasets` requires the package data to be present.
  Acceptable trade-off (the dataclass is preserved for legacy callers);
  noted in case the package data ever goes missing.

- **Generator's `_display(p)` helper duplicates a pre-existing
  `relative_to(REPO_ROOT)` pattern.** The stage report calls this out
  honestly — pre-existing fragility, fix surfaces in the round-trip test.
  Fine as scoped.

### Blocking issues
None.

## 6. Gate decision

**APPROVE** → status: `done`, verdict: PASSED.

- All 5 ACs pass with reproducible evidence.
- 47/47 bundle tests reproduce on a fresh checkout.
- No qh-introduced runtime regressions. The 10 full-suite failures are
  branch-drift from `phase6-promote-v2-canonical` (main rebase resolves) or
  pre-existing on main.
- `query_mode` correctly stays on the spec block (grep-verified).
- AC-1 count correction (53 → 54) is independently confirmed against the
  upstream filesystem.
- No qh commit adds a new `spacedock_solver_v2` reference (per team-lead's
  scrutiny note).
