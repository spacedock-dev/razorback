# Validation — harbor-view task identity through scored runs (spider2-dbt + generic)

- Entity: `docs/razorback-implementation/harbor-view-task-identity-scored-runs.md`
- Branch: `spacedock-ensign/harbor-view-task-identity-scored-runs`
- Head: `7d55d33dd6ff43ab5bdf9619353a32e11710f2a3`
- Base (merge-base with `main`): `773fb5f9c94f50af529f81dfcf9496f9412b7cc9`
- Validated from a clean checkout of the worktree branch (working tree clean).

## Gate decision: APPROVE → `done`

All three ACs PASS with real command output. Code review found no Critical or
Important issues; the two Minor findings are both pre-existing and out of scope.
The single failing test is a confirmed pre-existing, unrelated failure (fails
identically on base) — not a regression.

---

## AC-by-AC results

### AC-1 — A scored spider2-dbt run preserves benchmark task identity end-to-end — PASS

`Verified by:` an integration test running a fixture spider2-dbt job to scored
artifacts asserting `summary.json` / `per_trial_outcomes.json` carry
`benchmark_kind=spider2-dbt` + correct per-task `benchmark_task_id`.

Command + output:

```
$ uv run pytest tests/integration/test_spider2_dbt_scored_run_identity.py \
    tests/unit/test_task_identity_scoring.py -p no:cacheprovider -q
... 3 passed (within 12 passed surface run below)
tests/integration/test_spider2_dbt_scored_run_identity.py::test_spider2_dbt_scored_run_carries_benchmark_identity PASSED
tests/unit/test_task_identity_scoring.py::test_aggregator_resolves_task_identity_from_view_manifest PASSED
tests/unit/test_task_identity_scoring.py::test_task_identity_outputs_are_invariant_to_dispatch_order PASSED
```

The integration test runs the actual producer (`spec_to_job_config` with
`tasks_root=run_dir/tasks`) and the actual scoring writers
(`aggregate_summary`, `write_per_trial_outcomes`) against a committed fixture
(`tests/fixtures/spider2_dbt/harbor_task_minimal/spider2-fixture-001`), then reads
the real `summary.json["trials"][0]["stratum"]` and `per_trial_outcomes.json`,
asserting both carry `benchmark_kind=spider2-dbt` and the manifest's
`benchmark_task_id`. Network/docker are avoided by a narrowly-scoped monkeypatch
of the dataset-source resolver only.

### AC-2 — Solver freeze identity discovery finds materialized view manifests — PASS

`Verified by:` a test asserting `SpacedockSolverAgent`'s `views_root` scan
resolves the view manifests produced for a spider2-dbt run.

Command + output:

```
$ uv run pytest tests/integration/test_spacedock_solver_freeze_dir_mechanism.py -v
tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_freeze_dir_discovers_benchmark_task_identity_from_view_manifest PASSED
tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_discovery_resolves_manifest_under_tasks_root PASSED
```

`test_discovery_resolves_manifest_under_tasks_root` writes a manifest at
`run_dir/tasks/spider2-dbt-bq001/view_manifest.json` and asserts
`agent._discover_task_identity_from_manifest()` resolves
`benchmark_kind=spider2-dbt`, `benchmark_task_id=bq001`. The pre-existing
discovery test was also migrated from the dead `_razorback/task_views` root onto
`run_dir/tasks`.

### AC-3 — Generic `kind: harbor` path identity unchanged / consistently fixed — PASS

`Verified by:` the existing `test_translate_harbor_block` suite stays green +
a test pinning the chosen root reconciliation does not regress non-spider2
harbor identity.

Command + output:

```
$ uv run pytest tests/unit/test_translate_harbor_block.py -v
... 8 passed
tests/unit/test_translate_harbor_block.py::test_translator_emits_one_taskconfig_per_local_task PASSED
tests/unit/test_translate_harbor_block.py::test_translator_threads_spec_concurrency PASSED
tests/unit/test_translate_harbor_block.py::test_translator_uses_correct_environment_config PASSED
tests/unit/test_translate_harbor_block.py::test_translator_rejects_missing_local_task PASSED
tests/unit/test_translate_harbor_block.py::test_harbor_block_respects_n_tasks_cap_after_resolution PASSED
tests/unit/test_translate_harbor_block.py::test_harbor_block_respects_exclude_tasks_after_resolution PASSED
tests/unit/test_translate_harbor_block.py::test_translator_resolves_dabstep_via_package_dataset_client PASSED
tests/unit/test_translate_harbor_block.py::test_generic_harbor_path_writes_no_view_manifest PASSED
```

All 7 baseline tests green + the new `test_generic_harbor_path_writes_no_view_manifest`
pins that the generic harbor path emits `TaskConfig(path=source)`, materializes
no manifest under `run_dir/tasks`, and leaves `trial_name_map` empty.
`task_views_root` is also unit-pinned (`test_task_views_root.py`, 1 passed).

---

## Full identity surface run

```
$ uv run pytest tests/integration/test_spacedock_solver_freeze_dir_mechanism.py \
    tests/integration/test_spider2_dbt_scored_run_identity.py \
    tests/unit/test_task_identity_scoring.py tests/unit/test_task_views_root.py \
    tests/unit/test_translate_harbor_block.py -p no:cacheprovider -v
================== 1 failed, 23 passed, 4 warnings in 11.33s ===================
FAILED tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_codex_runtime_dispatch_constructs_inner_agent
```

23/24 pass. The 23 are the AC surface; the 1 failure is pre-existing/unrelated
(below).

## Pre-existing unrelated failure (NOT a regression)

`test_codex_runtime_dispatch_constructs_inner_agent` fails because it requires
`RAZORBACK_SPACEDOCK_PLUGIN_DIR` to be set:

```
E  razorback.agents.spacedock_solver.SpacedockSolverAgentError: RAZORBACK_SPACEDOCK_PLUGIN_DIR is not set;
   spacedock_solver cannot dispatch through the first-officer without a plugin dir.
```

Confirmed it fails identically on base via a detached `git worktree add` at
`main` (`08449cc`; production code identical to merge-base `773fb5f` —
`git diff 773fb5f HEAD -- src/ tests/` is empty):

```
$ (base worktree) uv run pytest \
   "tests/integration/test_spacedock_solver_freeze_dir_mechanism.py::test_codex_runtime_dispatch_constructs_inner_agent" -q
E  ... SpacedockSolverAgentError: RAZORBACK_SPACEDOCK_PLUGIN_DIR is not set ...
1 failed in 1.87s
```

Same error, same cause, no relation to this entity's changes (this PR only added
two new identity tests to that file; the codex test body is untouched).

---

## Code review (`superpowers:requesting-code-review`, base `773fb5f` → head `7d55d33`)

Independent `general-purpose` reviewer. Findings classified:

### Blocking: none
No Critical, no Important.

### Non-blocking (Minor — both pre-existing, out of scope)

1. **Trial↔view matching heuristic** (`aggregate.py:142`, `spacedock_solver.py`):
   `manifest_dir.name[:32].rstrip("_-")` vs `trial_dir.name.split("__",1)[0]`.
   View names can be up to 160 chars (`materialize.py:_view_name`); two views
   sharing a 32-char prefix could collide/mismatch. Verified via `git show
   773fb5f` that BOTH the 32-char truncation and the dead root existed at base —
   this PR changed only the root, not the matcher. Latent; worth a follow-up
   issue, not a blocker here.

2. **No backward-compat shim for old `_razorback/task_views`** runs. Non-issue:
   the old root was *dead* — the producer never wrote there (that was the bug),
   so no real run ever had manifests at the old path. No source/test references
   to the old path remain except intentional comments.

### Scrutiny points from the checklist — both independently confirmed

- **(a) Resolver / producer-consumer agreement:** Traced producer end-to-end:
  `cli/run.py:311` (`tasks_root=run_dir/"tasks"`) → `translate.py:369`
  (`view_root = Path(tasks_root)`) → `materialize.py:95`
  (`manifest.write(view_dir / TASK_VIEW_MANIFEST)` under `view_root/<view>/`).
  Both consumers now call `task_views_root(run_dir) → run_dir/"tasks"`
  (`spacedock_solver.py:341`, `aggregate.py:133`). Producer and BOTH consumers
  genuinely agree. No path disagreement.

- **(b) Dead-import deviation justified:** Confirmed on base that
  `razorback.score.load` does not exist (`src/razorback/score/` contains only
  `__init__.py`, `render.py`, `verdict.py`; `import` raises
  `ModuleNotFoundError`). `tests/unit/test_task_identity_scoring.py` was
  therefore **uncollectable on base** (`pytest --collect-only` → collection
  error, 0 tests collected) — the implementer revived an already-broken file
  rather than breaking a passing one. The removed assertion block used the
  nonexistent `load_run_dir`, so it could never execute; the order-invariance
  property it targeted (benchmark_kind + benchmark_task_id stable across
  dispatch order) is still proven by the surviving
  `outcome_set(default_run) == outcome_set(reordered_run)` assertion over the
  real `per_trial_outcomes.json`. No coverage lost. Restoring a nonexistent
  function would have been inventing an API. Removal was the right call.

### Reviewer recommendations (follow-up, not gating)
- Harden the trial↔view matcher (full sanitized name or explicit view→trial key
  in the manifest) — independent of this PR.
- Optionally add an AC-1 case with a `benchmark_task_id` >32 chars to pin the
  truncation boundary.

### Reviewer verdict: Ready to merge — Yes.
