---
id: egz5hdxxfzxxtjfq7zn81100
title: spider2-dbt — source resolution + rk run materialization wiring
status: validation
source: PKG-40 spike (notes/pkg40-spider2-harbor-surface.md) + ade_bench dataset-ref path as reference; captain chose the harbor-package source path
started: 2026-06-18T06:24:22Z
completed:
verdict:
score:
worktree: .worktrees/spacedock-ensign-spider2-dbt-source-resolution-and-run-wiring
issue:
pr:
mod-block: merge:pr-merge
auto-approve: false
---

## Problem

`src/razorback/benchmarks/spider2_dbt/{harbor_view,plugin_args}.py`
exist but nothing in the `rk run` path invokes
`materialize_spider2_harbor_task_view`, so a spider2-dbt spec cannot
resolve into Harbor task views. This task wires spider2-dbt in as a
recognized benchmark family: a `kind: harbor` spec with
`dataset: spider2-dbt/spider2-dbt@1.0` resolves source task dirs
(captain-chosen harbor-package path, mirroring the ade-bench dataset-ref
flow in `translate.py:_resolve_harbor_dataset_tasks`), runs each through
the spider2 view materializer, and emits `TaskConfig(path=view_dir)`
entries. The fully-qualified `<org>/<name>@<ref>` form is mandatory:
`HarborBenchmarkBlock` rejects a bare ref at spec-parse time when
`plugin is None` (`spec/schema.py:209-226`), and Harbor's
`PackageReference.parse` raises on `spider2-dbt@1.0` (verified at plan
time) — so the bare ref can never be a valid spec dataset. Tests run
against a local fixture source tree so the suite stays deterministic;
the bare `spider2-dbt@1.0` form appears only as the live
`harbor download` CLI smoke, which is not a gating AC (the PKG-40 spike
recorded its git-checkout failure).

`auto-approve: false` — touches the spec/translate surface.

## Acceptance criteria

**AC-1 — A `kind: harbor` / `dataset: spider2-dbt/spider2-dbt@1.0` spec resolves to N spider2 task-view dirs.**
The fully-qualified ref is the user-facing contract (the bare
`spider2-dbt@1.0` is rejected by the schema validator and is reserved
for the live `harbor download` CLI smoke only).
Verified by: an integration test that runs the resolver against
`tests/fixtures/spider2_dbt/` and asserts each emitted dir contains
`task.toml` and that `rg -l 'gold|expected|golden'` over the view
returns no matches (leakage-clean).

**AC-2 — Each materialized view carries the spider2-dbt benchmark env.**
Verified by: a test asserting the emitted task carries
`RAZORBACK_BENCHMARK_KIND=spider2-dbt` and `RAZORBACK_BENCHMARK_TASK_ID`
(per `materialize_spider2_harbor_task_view`).

**AC-3 — `rk run --explain` on a fixture spider2-dbt spec lists the resolved tasks.**
Verified by: `uv run rk run <fixture-spec>.frozen.yaml --explain` exits 0
and prints one task line per fixture instance.

## Test plan

Unit + integration around the resolver and view emission, fixture-backed.
A documented (non-gating) live smoke re-runs
`uv run harbor download spider2-dbt@1.0 --export` and records exit
status + task-dir count in the validation report (re-checking the
PKG-40 checkout blocker). Acceptance command for validation:
`uv run rk run <fixture-spec>.frozen.yaml --explain`.

## Out of scope

The dbt-deps image layer / preflight (covered by
`spider2-dbt-harbor-view-ade-parity`) and the verifier
(`spider2-dbt-duckdb-match-verifier`). A local raw-dataset generator
fallback if the harbor package stays unusable — deferred unless the
live smoke fails.

## Stage Report: plan

- DONE: Map each of the 3 ACs to concrete modules with a TDD checkpoint per AC.
  AC↔task map table in the plan; AC-1→T1/T2/T3 (`translate.py:_build_harbor`), AC-2→T4 (`harbor_view.py:31-35`), AC-3→T5/T6 (`cli/run.py:307`, `cli/run_explain.py`). Resolver path = `translate.py:_resolve_harbor_dataset_tasks`; run-time call site = `cli/run.py:311` (`tasks_root=run_dir/"tasks"`); source tree = `tests/fixtures/spider2_dbt/`.
- DONE: Exercise the riskiest mechanism first; plan the live download smoke re-checking the PKG-40 blocker; name the raw-dataset-generator fallback decision.
  T2 (materialize-on-resolve, the load-bearing contract) is implemented+proven before the CLI test (T6) and before the non-gating live smoke (T7). T7 records exit/task-dir count, re-checks the `git checkout` exit-128 blocker, and names defer-vs-build the generator as the captain's call (recommend defer). Fixture-backed tests gate AC-1/2/3 either way.
- DONE: Write the plan as a standard separate doc with an AC-to-task map table and spec/reference cites per step.
  `docs/razorback-implementation/plans/spider2-dbt-source-resolution-and-run-wiring.md` — header, Global Constraints, AC↔task table, per-step §-cites, self-review.

### Summary
Wrote the implementation plan via superpowers:writing-plans. The single wiring point is `_build_harbor` in `translate.py`: detect the spider2-dbt family by `PackageReference.short_name`, then materialize each resolved source dir through `materialize_spider2_harbor_task_view` into the run's `tasks_root`, emitting view dirs as `TaskConfig.path`. Tests reuse the existing resolver-monkeypatch seam for determinism; an `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` offline seam keeps the `rk run --explain` integration test network-free. Three claims were verified live against the repo (PackageReference parse behavior for short vs qualified refs, the explain payload key path `prompt.task_paths`, and `parse_spec_file`'s location). One open item flagged for the implementer: whether `exclude_tasks`/`n_tasks` should filter on view-dir names or source slugs.

## Feedback Cycles

### Cycle 1 — plan gate REJECTED (2026-06-18)

Codex adversarial review (`--base HEAD~3`) surfaced three design-level
defects; captain rejected the plan gate and chose **option B** (change
the dataset-ref contract). Rework brief for the next plan pass:

1. **[high] Dataset-ref contract (captain decision: B).** Amend the
   user-facing contract to the fully-qualified `spider2-dbt/spider2-dbt@1.0`
   ref **everywhere** — update AC-1 and the Problem § in this entity, and
   the plan's fixture spec / detection prose. The bare `spider2-dbt@1.0`
   form stays only as the `harbor download` CLI smoke (T7). Do NOT add
   schema support for the bare ref (that was option A, declined).
2. **[high] Env-override hijack.** The proposed
   `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` branch at the top of
   `_resolve_harbor_dataset_tasks` ignores `dataset_ref`, so a leaked env
   var could route any `kind: harbor` dataset to the spider2 fixture
   tree. Remove the production-resolver seam: keep the offline test seam
   as pytest monkeypatch only (preferred), or if an env seam is truly
   needed, guard it with `_is_spider2_dbt_dataset(dataset_ref)` so it
   never captures non-spider2 datasets.
3. **[medium] `exclude_tasks` semantics.** Apply `exclude_tasks` /
   `n_tasks` to **source paths before materialization** (or carry an
   explicit source-task-id map), so selectors stay bound to original
   Harbor task names rather than the post-materialization
   `<benchmark_kind>-<task_slug>` view names. Add a test where
   `exclude_tasks=[source_slug]` proves the excluded spider2 task is not
   emitted. Resolve this in the plan — do not defer it to the implementer.

## Stage Report: plan (cycle 1)

- DONE: Amend the dataset-ref contract to the fully-qualified `spider2-dbt/spider2-dbt@1.0` everywhere (AC-1 + Problem § in the entity, and the plan's fixture spec + detection prose); keep bare `spider2-dbt@1.0` only as the harbor-download CLI smoke. Do NOT add schema support for the bare ref.
  Entity Problem § + AC-1 now use the qualified ref and cite the schema-validator rejection of the bare form (`spec/schema.py:209-226`). Plan goal/architecture/design/fixture-spec (line 553) all use the qualified ref; bare ref kept only in T7 + the live-smoke constraint. Re-verified live: `PackageReference.parse("spider2-dbt@1.0")` raises, `"spider2-dbt/spider2-dbt@1.0"` parses (short_name=="spider2-dbt").
- DONE: Remove the global production-resolver env seam: keep the offline test seam as a pytest monkeypatch only (preferred), or guard any env seam with `_is_spider2_dbt_dataset`.
  `RAZORBACK_SPIDER2_DBT_SOURCE_ROOT` removed entirely; `_resolve_harbor_dataset_tasks` untouched. T6 rewritten to invoke `rk run --explain` in-process via Typer `CliRunner` (pattern: `tests/unit/test_rk_run_harbor_cache_dir.py`) and monkeypatch the resolver. Verified live: `--explain` returns before `_invoke_harbor` (`cli/run.py:335-346`); fixture spec has no `provenance:` so drift checks skip; `_resolve_harbor_dataset_tasks` is a monkeypatchable module attr.
- DONE: Apply `exclude_tasks`/`n_tasks` to source paths BEFORE materialization, decide it in the plan, and add a test proving `exclude_tasks=[source_slug]` drops the excluded spider2 task.
  T2 hoists selectors onto `source_paths` via a new `_apply_task_selectors`, then materializes survivors (spider2 branch returns early; generic path byte-identical). New T3b proves `exclude_tasks=["spider2-fixture-001"]` drops that source and its `spider2-dbt-<slug>` view; pins ordering against regression. Root cause confirmed live: `materialize.py:_view_name` yields `spider2-dbt-<slug>`, so a post-materialize `p.name` filter can never match a source slug.

### Summary
Reworked both the entity (Problem § + AC-1) and the plan doc to resolve the three Codex-surfaced defects per captain option B. Contract is now the fully-qualified `spider2-dbt/spider2-dbt@1.0` everywhere with no schema change; the bare ref is the `harbor download` CLI smoke only. The env-override hijack is eliminated by removing the production-resolver seam and driving the AC-3 `--explain` test in-process via `CliRunner` so a pytest monkeypatch reaches the resolver. `exclude_tasks`/`n_tasks` now filter source paths before materialization (decided in-plan, not deferred), with a dedicated T3b regression test. Every changed contract assumption was re-verified live against the repo (PackageReference.parse, schema validator shape, `_view_name`, the explain short-circuit, and the CliRunner/monkeypatch surface).

## Stage Report: implementation

- DONE: Implement the approved plan TDD-first so all 3 ACs pass; `uv run pytest` green.
  T1-T6 done TDD-first (commits 53a9d09..4c5af5f). AC-1: detection by qualified short_name + filter-then-materialize in `_build_harbor` (translate.py:348-370) + N leakage-clean views; AC-2: views carry RAZORBACK_BENCHMARK_KIND/TASK_ID; AC-3: in-process CliRunner `rk run --explain` lists one `spider2-dbt-<slug>` task per fixture instance. 18 spider2+harbor tests pass; 674 passed overall.
- DONE: Honor the cycle-1 defect fixes (no prod env seam in `_resolve_harbor_dataset_tasks`; AC-3 via CliRunner+monkeypatch; selectors on source paths BEFORE materialization with T3b regression test).
  `_resolve_harbor_dataset_tasks` untouched (no env seam); T6 monkeypatches it in-process via CliRunner. `_apply_task_selectors` runs on source paths first (translate.py:356-360); T3b `test_exclude_tasks_drops_spider2_source_slug` + `test_n_tasks_caps_spider2_before_materialize` pass.
- DONE: Rider — add a NEGATIVE leakage test planting a forbidden file and asserting the view excludes it; use unescaped `rg -l 'gold|expected|golden'`.
  `test_planted_forbidden_files_are_excluded_from_view` plants expected.csv/gold/golden answer files; surfaced a REAL deny-glob hole (fnmatch `**/gold/**` misses top-level `gold/`). Fixed by adding bare `expected/**`/`gold/**`/`golden/**` to SPIDER2_DBT_DENY_GLOBS (commit 1dfa1e4). Test fails when fix reverted (golden/result.txt leaks) — verified.

### Summary
Wired spider2-dbt as a `kind: harbor` family in `_build_harbor`: detect by `PackageReference.short_name == "spider2-dbt"`, apply exclude_tasks/n_tasks to resolved source paths, then materialize survivors through `materialize_spider2_harbor_task_view` into `tasks_root`, emitting view dirs as `TaskConfig.path`. The generic non-spider2 harbor path is byte-for-byte unchanged (test_translate_harbor_block 7/7 green). Two deviations from the plan, both justified: (1) the AC-1 `rg` leakage scan excludes `view_manifest.json`, which by design records the deny-glob list + excluded-file checksums (a provenance audit trail, not leaked answer content); (2) the mandatory rider surfaced a genuine leakage hole in `SPIDER2_DBT_DENY_GLOBS` — top-level `gold/`/`golden/`/`expected/` dirs leaked because fnmatch's `**/` prefix requires a leading segment — fixed by adding bare-form globs (strictly strengthens the deny set; the "harbor_view.py read-only" plan note predates the rider). Pre-existing, unrelated failures on the base commit (`test_task_identity_scoring` collection error from missing `razorback.score.load`; `test_generate_matrix_specs`/`test_rk_research_new`) were confirmed present at 1547f16 and are out of scope. T7 (live `harbor download` smoke, non-gating) is deferred to the validation stage per the plan.

## Stage Report: validation

- DONE: Independently reproduce each AC's Verified-by from a clean checkout (pytest + `rk run --explain`); record actual PASS/FAIL per AC.
  AC-1 PASS (test_translate_spider2_dbt.py 10 passed; 2 leakage-clean view dirs, rg rc=1 empty). AC-2 PASS (view task.toml carries RAZORBACK_BENCHMARK_KIND/TASK_ID). AC-3 PASS (integration test exit 0, prompt.task_paths=2 spider2-dbt-* names; materialize runs before explain short-circuit at run.py:307<335). Generic harbor path 7/7 green (no regression).
- DONE: Run superpowers:requesting-code-review; classify findings; scrutinize the two flagged deviations (manifest-excluded rg scan; harbor_view.py deny-glob edit).
  No Critical/Important. (a) manifest exclusion SOUND — empirically the manifest holds path-keyed sha256 + glob list, never answer content ("secret" absent). (b) deny-glob edit SOUND + strictly strengthens — pure append to an `any(fnmatch)` tuple, closes a real top-level-dir hole. Minors (import order, guard ordering, AC-2 runtime-injection scope) all non-blocking; `ruff check` passes on changed files.
- DONE: Confirm the negative-leakage test fails when the deny-glob fix is reverted; confirm cycle-1 defects did not regress.
  Reverted harbor_view.py to base globs → test_planted_forbidden_files_are_excluded_from_view FAILED (golden/result.txt leaked); restored → green. No prod env seam (RAZORBACK_SPIDER2_DBT_SOURCE_ROOT only in docs; `_resolve_harbor_dataset_tasks` body untouched). Selectors filter source paths pre-materialize (T3b passes).

### Summary
Gate verdict: PASSED → done. All three ACs reproduced PASS from a clean worktree checkout; the generic non-spider2 harbor path is unchanged (7/7). Code review surfaced no Critical/Important issues, and both pre-flagged deviations are SOUND — the `view_manifest.json` exclusion (verified to hold only checksums + glob strings, not answer content) and the `harbor_view.py` deny-glob edit (a monotonic strengthening that closes a real top-level-dir leak, proven load-bearing by the revert-and-fail check). Cycle-1 defects did not regress: no production env seam, selectors bind to source slugs before materialization. T7 live `harbor download` smoke is non-gating and reproduces the PKG-40 git-checkout exit-128 blocker; recommendation is to DEFER the raw-dataset generator since the fixture suite fully gates the ACs. Report at docs/razorback-implementation/validation/spider2-dbt-source-resolution-and-run-wiring.md.

### Cycle 2 — validation gate REJECTED (2026-06-18)

Validation recommended PASSED (ACs met), but a Codex adversarial review of
the code (`--base 1547f16`) surfaced one valid [medium] design gap and the
captain chose **bounce-and-fix-now**. Routing back to `implementation`:

1. **[medium] Spider2-dbt materialization ignores `--materialize=bind`
   (`translate.py:363-367`).** `spec_to_job_config` accepts
   `materialize_mode: Literal["bind","copy"] = "bind"` (`translate.py:93`),
   but `_build_harbor` never receives it, and the spider2 call site invokes
   `materialize_spider2_harbor_task_view(...)` with no `view_mode` -> defaults
   to `copy`. So `--materialize bind` is silently ineffective for spider2 and
   real (large) task trees are eagerly duplicated into `run_dir/tasks`. This
   is a parity gap with ade-bench (which threads the mode via `cli/run.py:313`)
   and matters for the N=1 full-dataset goal.
   **Fix:** thread `materialize_mode` from `spec_to_job_config` -> `_build_harbor`,
   map `bind`->`view_mode="link"` / `copy`->`view_mode="copy"`, pass it to
   `materialize_spider2_harbor_task_view`, and add a regression test that
   `--materialize bind` produces symlinked view files for spider2-dbt. Keep the
   generic non-spider2 harbor path behavior unchanged. Do not regress the 3 ACs
   or the cycle-1 fixes.

## Stage Report: implementation (cycle 2)

- DONE: Thread `materialize_mode` from `spec_to_job_config` (translate.py:93) into `_build_harbor`, map `bind`->`view_mode="link"` and `copy`->`view_mode="copy"`, and pass it to `materialize_spider2_harbor_task_view` at the spider2 call site. Mirror how ade-bench threads the mode (cli/run.py:313).
  Commit 0d09629. `spec_to_job_config` now passes `materialize_mode=` to `_build_harbor` (translate.py:119); `_build_harbor` gained the param (translate.py:307) and maps `link if materialize_mode=="bind" else copy` (translate.py:370-371) into the spider2 view call (translate.py:378). Removing `view_mode=view_mode` fails the bind test; restoring passes (verified).
- DONE: Add a regression test proving `--materialize bind` produces symlinked (not copied) view files for spider2-dbt, and that `copy` still copies.
  `test_materialize_bind_produces_symlinked_view_files` (bind -> `example.sql` is_symlink) + `test_materialize_copy_still_copies_view_files` (copy -> not symlink), both in test_translate_spider2_dbt.py. Bind test failed pre-fix, passes post-fix.
- DONE: No regression: the generic non-spider2 harbor path stays byte-for-byte unchanged, and the 3 ACs + cycle-1 fixes still pass. `uv run pytest` green for spider2/harbor/explain.
  Generic harbor path (translate.py:385+) untouched; test_translate_harbor_block 6/6 (dabstep excluded — network-only, fails identically on base). spider2(13) + materializer(3) + leakage + explain(1) all green; broad `tests/unit` = 674 passed. The 2 remaining failures (test_generate_matrix_specs, test_rk_research_new) and the dabstep/score-load collection error all pre-exist on base (stash-verified).

### Summary
Threaded the spec-level `materialize_mode` through `_build_harbor` into the spider2-dbt view materializer (bind->link, copy->copy), closing the parity gap where `--materialize bind` was silently ignored and large task trees were eagerly copied into `run_dir/tasks`. Enabling link mode surfaced a latent correctness bug: `_patch_task_toml` wrote through the reflected `task.toml`, which under link mode is a symlink back into the shared source — so env-injection corrupted the source fixture. Fixed by unlinking the symlink before writing so the patched `task.toml` is view-owned while the bulk tree stays symlinked; added a materializer test asserting link mode symlinks bulk files, keeps `task.toml` a real file, and never mutates the source. Generic non-spider2 harbor path is unchanged and the 3 ACs + cycle-1 fixes do not regress.

## Stage Report: validation (cycle 2)

- DONE: Reproduce the cycle-2 fix: `--materialize bind` produces symlinked spider2-dbt view files and `copy` copies them; confirm the bind test is load-bearing; confirm ade-bench-parity threading `spec_to_job_config -> _build_harbor -> materialize_spider2_harbor_task_view`.
  16/16 spider2+materializer+explain tests pass. Removing `view_mode=view_mode` at the spider2 call site fails `test_materialize_bind_produces_symlinked_view_files` (example.sql becomes a copy); restored → green. Chain verified: cli/run.py:313 → spec_to_job_config(:93) → _build_harbor(:119/:307) → bind→link map(:370-372) → materializer view_mode(:378).
- DONE: Scrutinize the NEW deviation — `_patch_task_toml` unlink-before-write (materialize.py:140-145). Confirm under link mode the patched view task.toml is view-owned and the shared SOURCE task.toml is never mutated.
  SOUND/minimal/correctly-scoped: 6 lines guarded by `is_symlink()` (no-op in copy mode). Load-bearing: reverting it fails the link-mode source-mutation test. Proven against the REAL committed fixture under view_mode="link": view task.toml is a real file with injected env, bulk files symlinked, source unchanged, `git status` clean; with the fix reverted the same run dirtied the source fixture (git M + leaked env), then `git checkout` restored it.
- DONE: Confirm no regression from cycle 1: the 3 ACs, the cycle-1 defect fixes, and the generic non-spider2 harbor path all still pass; `uv run pytest` green; note only pre-existing base failures.
  3 ACs green (16/16). No prod env seam; selectors pre-materialize; negative-leakage pass. Generic harbor path test_translate_harbor_block 7/7 (byte-equivalent rename only). Broad `tests/unit` = 676 passed, 2 failed; the 2 failures + the score.load collection error all reproduced FAILING on a fresh 1547f16 base checkout (pre-existing, not regressions).

### Summary
Gate verdict: PASSED → done. The cycle-2 materialize_mode threading is correct and the bind regression test is load-bearing; the ade-bench-parity chain is wired end-to-end. The NEW out-of-brief deviation (the `_patch_task_toml` unlink-before-write in materialize.py) is judged SOUND, minimal, and correctly scoped — it fixes a genuine latent bug that link mode exposes, is guarded so copy mode is a no-op, is proven load-bearing, and is proven not to mutate the committed source fixture under bind/link (git-clean with the fix; git-dirty + env-leak without it). No regression: 3 ACs, cycle-1 fixes, and the generic harbor path all pass; only the documented pre-existing base failures (test_generate_matrix_specs, test_rk_research_new, razorback.score.load collection error) remain, confirmed failing on base 1547f16. Cycle-2 report appended at docs/razorback-implementation/validation/spider2-dbt-source-resolution-and-run-wiring.md.
