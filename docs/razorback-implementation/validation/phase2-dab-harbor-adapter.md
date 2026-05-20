# Validation: Phase 2 — DAB harbor adapter (sibling package)

- entity: `docs/razorback-implementation/phase2-dab-harbor-adapter.md`
- branch: `spacedock-ensign/phase2-dab-harbor-adapter`
- diff range: `2b802f8..0847b36`
- worktree: `.worktrees/spacedock-ensign-phase2-dab-harbor-adapter`
- gate decision: **PARTIAL-PASS — approve to `done` with T14/T15 carried as a
  follow-up entity gated on Phase 1 (e3) ship + captain approval for the
  $30-60 matrix run.**

## Test suite results

Executed from the worktree on commit `0847b36`.

| suite | command | result |
| --- | --- | --- |
| plugin (46) | `uv run pytest packages/razorback-plugin-dab/tests/` | 46/46 passed in 0.78s |
| phase2 harbor_dab (9) | `uv run pytest tests/unit/test_spec_harbor_dab_block.py tests/unit/test_translator_harbor_dab.py` | 9/9 passed in 0.09s |
| all dab + harbor_dab (38) | `uv run pytest tests/unit/test_spec_harbor_dab_block.py tests/unit/test_translator_harbor_dab.py tests/unit/test_dab_*` | 38/38 passed in 0.28s |
| full razorback unit (264) | `uv run pytest tests/unit/` | 264/264 passed in 11.91s |

No regressions. The implementation report's "20 razorback Phase 2 tests"
phrasing undercounts: the harbor_dab-specific surface is 9 tests (5 schema +
4 translator), and the broader dab suite (29 pre-existing + 9 new = 38)
also stays green.

## AC coverage

### AC-1 — Walking skeleton holds on both paths — PARTIAL-PASS (live `rk run` deferred)

- In-tree path: `examples/specs/bookreview-claude-in-tree-dab.yaml`
  carries `kind: in_tree_dab` and parses via the alias at
  `src/razorback/spec/parse.py:13-18` to `DabBenchmarkBlock`. Regression
  test `tests/unit/test_translator_harbor_dab.py::test_in_tree_dab_translator_path_unchanged`
  asserts dispatch to `_build_dab` (passing).
- Harbor path: `examples/specs/bookreview-claude-harbor-dab.yaml` carries
  `kind: harbor_dab`. `_build_harbor_dab` at
  `src/razorback/compat/harbor_0_6_6.py:280-346` invokes the plugin via
  `uv run razorback-plugin-dab generate` and collects emitted task dirs.
- The live `uv run rk run …` exit-0 evidence is deferred to T14 because
  `rk run` itself lands in Phase 1 (e3). The translator path is
  exercised under a mocked subprocess in
  `test_harbor_dab_translator_invokes_plugin_and_builds_tasks`.

### AC-2 — DAB harbor adapter package builds and publishes locally — PARTIAL-PASS

- Package layout under `packages/razorback-plugin-dab/` is in place
  (pyproject.toml, src layout, tests). Root `pyproject.toml` registers
  it as a uv-workspace member; the plugin's CLI is reachable as
  `uv run razorback-plugin-dab` from the workspace root (the AC-9
  integration test invokes it that way and passes).
- `harbor adapter list` discoverability is NOT verified: razorback core
  drives the adapter via subprocess (per AC-0.2 import_path dispatch
  model and the entity's plan-stage report); the literal `harbor adapter
  list` CLI is not in scope. `uv run razorback-plugin-dab list` returns
  the 12-row catalog as JSON (verified by
  `tests/unit/test_cli_surface.py`).
- A standalone `uv build` + wheel install into a throwaway venv was not
  run; the worker explicitly substituted unit + integration discovery
  tests (see "Deviations" in the entity's implementation summary). This
  is acceptable for the workspace-install path razorback uses; a
  separate wheel-install gate matters only for out-of-workspace
  consumers, which is out of scope.

### AC-3 — All 12 DAB datasets ported as harbor task definitions — PASS

- `packages/razorback-plugin-dab/src/razorback_plugin_dab/datasets.py:16-29`
  enumerates 12 datasets with backends and query counts. Catalog test
  `tests/unit/test_datasets_catalog.py` asserts 12 rows (6/6 passing).
- Per-task prepare emits `task.toml`, `instruction.md`, `tests/` with
  `verify.py` + `validate.py` + `stratum.json`, `environment/` with
  `Dockerfile` + `settings.json` (DISALLOWED_TOOLS denylist), `steps/main/`
  with workdir + workspace-README. Verified by
  `tests/unit/test_prepare_per_query.py` (6/6 passing).
- harbor schema-validation per-task is sidestepped: the test surface
  asserts harbor's `TaskConfig(path=...)` ingests the emitted task dirs
  (the translator builds `[TaskConfig(path=p) for p in task_dirs]`),
  not that harbor's CLI validates a separately-named adapter manifest.
  This matches the AC-0.2 filesystem task-tree dispatch model
  the entity's plan-stage report cites.

### AC-4 — Live-DB mode confirmed by trajectory evidence — DEFERRED (T14)

- The compose-stack generator at
  `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py`
  emits `dab-postgres` (postgres:17) and `dab-mongo` (mongo:8) on
  `dab-net` with healthchecks. Three shape tests pass
  (postgres / mongo / hybrid).
- Workspace-README's direct-structured + spacedock variants name
  `host dab-postgres, port 5432, user dabench, password dabench` so the
  agent's `psql --host dab-postgres` invocation is materially seeded
  before the run.
- Evidence-via-`events.jsonl` requires a live container run with
  Docker / Colima up + the dab-agent:latest image + Claude API spend.
  The worker explicitly deferred this to T14 because (a) `rk run`
  lands in Phase 1, and (b) the API cost requires captain approval
  per the dispatch's $10 ceiling. T14 is open as pending task #32.

### AC-5 — Live-DB baseline committed and promoted to canonical anchor — DEFERRED (T15)

- The matrix spec exists at
  `examples/specs/dab-claude-harbor-adapter.yaml`. The baseline doc
  scaffolding at
  `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`
  is augmented (commit `8c928bd`).
- Headline-score + per-dataset breakdown is not committed because the
  matrix run has not been executed; per the dispatch, a $30-60 run is
  above the $10 unattended ceiling and requires captain approval.
  T15 is open as pending task #35.

### AC-6 — Per-dataset expected-shift bands pre-registered — PASS

- Commit `8c928bd` appends the 12-row pre-registration table to
  `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md` with
  direction + rough magnitude per dataset, acceptance-criterion text
  ("observed shifts fall within pre-registered direction; magnitudes
  within 2x of prediction"), and the methodology guardrail naming
  the postdate invariant on T15's run-dir commit.
- Commit-ordering invariant is enforced by git: `8c928bd` precedes any
  T15 run-dir commit (which has not landed yet). When T15 eventually
  ships, the rule says it MUST postdate `8c928bd`; that's a git-log
  check at T15 validation, not Phase 2's responsibility.

### AC-7 — In-tree adapter still functional — PASS

- `src/razorback/benchmarks/dab/` is untouched by the diff range. The
  v1 alias path (`kind: in_tree_dab` → internal `kind: dab`) routes
  through the existing `_build_dab` translator. The regression assertion
  is `tests/unit/test_translator_harbor_dab.py::test_in_tree_dab_translator_path_unchanged`
  (passing).
- The 29 pre-existing `test_dab_*` tests pass unchanged.

### AC-8 — Cross-dataset aggregation contract honored — PASS

- Per-trial stratum payload at
  `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/stratum.py:10-31`
  emits `{stratum: {dataset, query_id, backends}}` to
  `tests/stratum.json`; `test.sh` (at `generate/prepare.py:_test_sh`)
  copies `/tests/stratum.json` to `/logs/verifier/stratum.json` so harbor's
  verifier sink picks it up.
- `tests/unit/test_stratum_tagging.py` (2/2 passing) confirms the
  payload shape and the verifier-side copy. `rk score` / `rk diff`
  consumption of those tags is razorback core's job and not the
  adapter's; consumer-side verification belongs to Phase 4b's `rk diff`.

### AC-9 — Dataset hydration semantics named and honored — PASS

- Decision (option b, enforced prereq) is named in the plan and
  implemented at
  `packages/razorback-plugin-dab/src/razorback_plugin_dab/hydration.py`
  via `check_hydrated()` → `DatasetNotHydratedError` whose `__str__`
  matches the verbatim contract:
  `razorback-plugin-dab: dataset <name> not hydrated, found LFS pointer
  at <path>.\nHydrate with:\n  cd <data_root> && git lfs pull`.
- The CLI catches the error and exits code 2 (`cli.py:66-71`). The
  fresh-checkout + hydrate-and-rerun integration test at
  `packages/razorback-plugin-dab/tests/integration/test_ac9_missing_dataset.py`
  passes (2/2) — it seeds a real LFS-pointer-shaped data root, asserts
  exit 2 + regex on stderr, then replaces the pointer and confirms the
  re-run succeeds.

## Code review

Reviewed the diff range `2b802f8..0847b36` (42 files, +2339 / -2 lines)
against razorback's conventions and the plan's contract.

### Strengths

- Per-file ABOUTME comments are present on every new module and match
  the project's CLAUDE.md rule.
- Razorback core's contract with the plugin is subprocess-only — there's
  no `from razorback_plugin_dab import ...` in core. The plugin is a
  true sibling per D5.
- AC-9's stderr text is hard-coded as a single source of truth in
  `DatasetNotHydratedError.__init__` and asserted by regex in the
  integration test; future changes will break the test before they
  break user-facing behavior.
- Forbidden-file scrubbing in `_materialize_task_dir` (`_QUERY_FORBIDDEN`
  rglob removal) is defensive-belt over the explicit copy lists, so
  even if a future change adds a directory copy that contains
  `ground_truth.csv` or `validate.py`, those still get removed from
  the workdir. Good AC-2 safety.
- Commit ordering for AC-6 (`8c928bd` precedes any T15 run-dir commit)
  is enforced by git, not by convention.

### Non-blocking findings

1. **subprocess call uses `uv run` literally** —
   `src/razorback/compat/harbor_0_6_6.py:304` invokes
   `["uv", "run", "razorback-plugin-dab", "generate", …]`. This works
   from the workspace root but couples the translator to the uv
   toolchain rather than to the plugin entry point. For Phase 2 the
   workspace install is the only deployment shape, so this is
   acceptable; downstream wheel-install deployments would need a
   direct entry-point shell-out. Note for a follow-up.
2. **subprocess call ignores `--out` parent layout** —
   The translator passes `--out <tasks_root>/<dataset>` to the plugin
   and then iterates `out_dir.iterdir()` for emitted task dirs. The
   plugin (per `prepare.py:42-101`) writes per-query dirs directly
   under `tasks_root`, which means `<tasks_root>/<dataset>/<dataset>-q<n>/`.
   The test `test_harbor_dab_translator_invokes_plugin_and_builds_tasks`
   stubs the directory tree with `_seed_emitted_tasks(out.parent, ds, …)`
   — note `out.parent`, not `out`. That detail in the stub matches the
   real layout (the seed writes under `out_root/dataset/dataset-qN`,
   and the translator iterates `out_dir.iterdir()` where
   `out_dir = tasks_root / dataset`). The shape is internally
   consistent, but the double-level nesting (`tasks_root/dataset/dataset-qN`)
   is a small footgun — a reader expects `tasks_root/dataset-qN`. A
   follow-up could flatten this or add a comment naming the shape.
   Not blocking — the translator and the plugin agree on the layout.
3. **Trial-name-map rsplit on `-q`** — `harbor_0_6_6.py:327-332` parses
   task names with `task_name.rsplit("-q", 1)`. This fails silently
   (no map entry) for any dataset whose name contains `-q` — none of
   the current 12 do, but a future dataset like `kafka-queue-stats`
   would break it. Switch to deriving the map directly from the
   plugin's emitted manifest (`prepare_dataset_tasks` already returns
   one), or assert the rsplit shape. Not blocking for the current
   catalog.
4. **`from __future__ import annotations` is inconsistent** — most
   plugin modules have it; `hydration.py` and the verify modules use
   it; `prepare.py` uses it; `verify/verify.py` does not but does not
   use annotation features beyond stdlib types in args. Cosmetic.
5. **`pg_dbs[0]` chosen as the postgres init DB** —
   `compose.py:77, :80` picks the first declared postgres DB for
   `POSTGRES_DB` + `pg_isready -d`. None of the 12 datasets have
   multi-postgres-DB shapes per the catalog, but the codepath silently
   drops the other names rather than declaring them. A `# upstream
   confirms 1 postgres DB per dataset` comment or a `len(pg_dbs) == 1`
   assert would make the assumption explicit.
6. **CLI `validate` subcommand is name-only** — `cli.py:93-111` checks
   for the presence of `task.toml`, `instruction.md`, `tests/`. It does
   not parse `task.toml` or validate against harbor's TaskConfig
   schema. Acceptable for a smoke surface — harbor's own ingestion
   provides the real schema check at run time — but the AC-3 phrasing
   "each task's manifest passes harbor's adapter schema validation"
   could be read as stricter. Phase 2's design (filesystem task-tree
   dispatch, not registered-adapter dispatch) makes the strict reading
   moot.

### Blocking findings

None.

## Deferral analysis: AC-4 and AC-5

The implementation worker deferred T14 (live-DB bookreview end-to-end via
`rk run`) and T15 (12-dataset matrix run) explicitly because:

1. T14 needs `rk run` to exist; `rk run` is Phase 1 (e3). e3 is
   `in_progress` (task #23) as of this validation. Validating AC-4
   here would force a backward dependency on an unshipped sibling
   entity.
2. T15 requires running the full 12-dataset matrix at the Claude API
   cost ($30-60 estimated). The dispatch's standing cost ceiling is
   $10 unattended; the matrix run is above that ceiling and requires
   captain greenlight.

The infrastructure for both is in place: spec examples exist; the
translator dispatches the plugin under a tested mock; the compose
generator emits postgres + mongo + hybrid shapes verified by unit
tests; the AC-6 pre-registration table commits in the right order;
the AC-9 hydration check materializes the live data path correctly.

The deferral is acceptable as PARTIAL-PASS because the deferred ACs
have pre-registered acceptance commands and pre-existing pending
tasks (#32 T14, #35 T15) that block on concrete external events
(Phase 1 ship + captain approval) rather than on undone Phase 2 work.

## Gate decision

**Approve to `done` (PARTIAL-PASS).**

Phase 2's contract — ship the sibling-package DAB harbor adapter so
that Phase 1's `rk run` has a target to dispatch into — is delivered.
The non-deferred ACs (1 partial / 2 partial / 3 / 6 / 7 / 8 / 9) hold.
The deferred ACs (4 / 5) are gated on external events the captain
already controls.

Recommend the first officer:

1. Mark `51 phase2-dab-harbor-adapter` complete with verdict
   `PARTIAL-PASS` and a `note:` field naming T14 + T15 as carried
   forward.
2. Either: file a follow-up entity `phase2-live-db-end-to-end` that
   blocks on e3 ship + captain approval and carries T14+T15; or keep
   the existing pending tasks #32 and #35 visible and let the next
   sprint planning surface them. (No preference — both keep the
   work tracked.)
3. Do NOT dispatch the matrix run during the current validation pass.
