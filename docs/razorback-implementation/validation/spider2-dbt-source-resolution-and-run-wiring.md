# Validation — spider2-dbt source resolution + rk run materialization wiring

- Entity: spider2-dbt — source resolution + rk run materialization wiring
- Worktree branch: `spacedock-ensign/spider2-dbt-source-resolution-and-run-wiring`
- Range reviewed: base `1547f16` → head `0c28b72`
- Validator: fresh agent, independent reproduction from the worktree checkout

## Gate verdict: PASSED → done

All three ACs reproduced PASS from a clean checkout. Code review found no
Critical/Important issues; both pre-flagged deviations judged SOUND. The
negative-leakage rider fails when reverted (proving the deny-glob fix is
load-bearing), and the cycle-1 defects did not regress. T7 live smoke is
non-gating and reproduces the known PKG-40 blocker.

## AC reproduction (independent)

**AC-1 — `kind: harbor` / `spider2-dbt/spider2-dbt@1.0` resolves to N leakage-clean view dirs.** PASS
- `uv run pytest tests/unit/test_translate_spider2_dbt.py` → 10 passed.
- `test_spider2_resolves_n_views_all_leakage_clean` emits 2 view dirs (one
  per fixture instance), each has `task.toml`, and the rider's unescaped
  `rg -l 'gold|expected|golden'` (manifest excluded) returns rc=1 / empty.
- Empirically confirmed the view excludes answer/solution files: a
  materialized view of `spider2-fixture-001` contains only
  `dbt_project/models/example.sql, environment/Dockerfile, instruction.md,
  task.toml, tests/test.sh, view_manifest.json` — `solution/solve.sh` and
  `tests/expected/answer.txt` (content "secret") are stripped.

**AC-2 — each view carries the spider2-dbt benchmark env.** PASS
- `test_materialized_view_carries_benchmark_env`: round-trips the view's
  `task.toml`, asserts `environment.env["RAZORBACK_BENCHMARK_KIND"]=="spider2-dbt"`
  and `RAZORBACK_BENCHMARK_TASK_ID=="spider2-fixture-001"`. Passed.

**AC-3 — `rk run --explain` lists one task per fixture instance.** PASS
- `uv run pytest tests/integration/test_rk_run_spider2_dbt_explain.py` → 1 passed.
  In-process via Typer `CliRunner`, resolver monkeypatched (offline). Exit 0;
  `payload["prompt"]["task_paths"]` has 2 entries, all `spider2-dbt-*` view names.
- Verified the spider2 materialize path runs BEFORE the explain short-circuit:
  `spec_to_job_config` is called at `cli/run.py:307`, the `if explain:` return
  is at `cli/run.py:335` — so the in-process `--explain` genuinely exercises
  materialize-on-resolve.
- The literal acceptance command `uv run rk run <fixture>.frozen.yaml --explain`
  against the real registry exits 10 (`Tag '1.0' not found`) — by design: the
  cycle-1 rework deliberately removed any production env seam, so the offline
  path is the pytest monkeypatch. The AC-3 `Verified by` IS the in-process
  CliRunner test, which passes. Not a defect.

## Regression / cycle-1 defect checks

- **Generic non-spider2 harbor path unchanged:** `uv run pytest
  tests/unit/test_translate_harbor_block.py` → 7 passed. The spider2 branch
  returns early (`translate.py:383`); the generic selector logic at
  `translate.py:388-393` is byte-for-byte identical to base.
- **No production env seam (defect #2):** `rg RAZORBACK_SPIDER2_DBT_SOURCE_ROOT`
  hits only the entity/plan docs (describing its removal), never source/tests.
  `_resolve_harbor_dataset_tasks` body is untouched (only the call-site var
  rename `task_paths`→`source_paths`).
- **Selectors filter source paths pre-materialization (defect #3):**
  `_apply_task_selectors` runs on `source_paths` before the materialize loop
  (`translate.py:356-368`). `test_exclude_tasks_drops_spider2_source_slug` and
  `test_n_tasks_caps_spider2_before_materialize` both pass.
- **Negative-leakage test is load-bearing:** temporarily reverted
  `harbor_view.py` to the base deny-globs (only `**/gold/**` nested forms) →
  `test_planted_forbidden_files_are_excluded_from_view` FAILED (`golden/result.txt`
  leaked into the view). Restored the fix → green. Confirms the rider's point.
- **Known pre-existing failures (NOT this task's regressions):**
  `test_task_identity_scoring` collection error, `test_generate_matrix_specs`,
  `test_rk_research_new`, and a network-flaky live-registry test exist on base
  `1547f16` and are out of scope — not grounds for rejection.

## Pre-flagged deviation verdicts

**(a) AC-1 leakage scan excludes `view_manifest.json` — SOUND.**
`manifest.py:directory_checksums` maps `relpath → "sha256:<hex>"`; the answer
content ("secret") is reduced to an irreversible hash. Empirically confirmed:
the manifest does NOT contain "secret"; it contains `excluded_globs`
(`...expected/**, gold/**, golden/**...`) and `source_checksums` keyed by
source paths (incl. `tests/expected/answer.txt` → a sha256, not content).
The `rg` alternation only matches the manifest on those provenance path/glob
strings — audit trail, not leaked answers. Excluding it is correct and necessary.

**(b) `harbor_view.py` deny-glob edit (plan-marked read-only) — SOUND, strictly strengthens.**
The edit only *appends* bare `expected/**`/`gold/**`/`golden/**` to the existing
tuple. `matches_denied_path` is a pure `any(fnmatch(...))` over patterns, so
adding patterns can only ever exclude MORE files, never fewer — monotonic. The
fix closes a real hole: `**/gold/**` does not match a top-level `gold/` dir
(fnmatch's `**/` prefix requires a leading segment), proven by the revert test
above. The read-only note predates the cycle-1 negative-leakage rider that
surfaced the hole; the deviation is justified.

## Code review (superpowers:requesting-code-review)

No Critical, no Important. Minor (all non-blocking):
- import ordering in `translate.py:17-20` — `ruff check` PASSES on the changed
  files (no isort rule enforced), so not a lint-gate blocker.
- `tasks_root is None` guard runs after the resolver call (pays resolve cost
  before failing) — cosmetic; `rk run` always supplies `tasks_root`.
- AC-2 verifies env is written into `task.toml`; whether Harbor injects it into
  the running container is out of this slice's scope (follow-up).

## T7 — live `harbor download` smoke (non-gating)

`uv run harbor download spider2-dbt@1.0 --export` → exit 1, failing at
`git checkout 82d1fb0c... → CalledProcessError exit 128`. Reproduces the
PKG-40 spike's git-checkout blocker exactly; the live harbor package remains
unusable. Non-gating — fixture-backed tests gate AC-1/2/3.

**Generator recommendation: DEFER the raw-dataset generator.** The fixture
suite fully gates the ACs deterministically and offline. Building a generator
now is speculative work against an externally-owned blocker (the Harbor
package's broken git ref). Defer until the package is fixed or a downstream
verifier/parity task forces real data — consistent with the entity's
"Out of scope" note.

---

# Validation (cycle 2) — re-review after materialize-mode fix

- Range reviewed: base `1547f16` → head `bfd942b` (cycle-2 fix `0d09629` + report `bfd942b`)
- Validator: fresh agent, independent reproduction from the worktree checkout
- Trigger: cycle-2 feedback fix for the `[medium]` materialize-mode threading gap

## Gate verdict: PASSED → done

The cycle-2 fix threads `materialize_mode` through `_build_harbor` into the
spider2 view materializer (`bind`→`link`, `copy`→`copy`), closing the parity
gap where `--materialize bind` was silently ineffective. The NEW deviation —
the `_patch_task_toml` unlink-before-write change in `materialize.py` — is
SOUND, minimal, and correctly scoped; it is proven load-bearing, and the
committed source fixture is proven un-mutated under bind/link mode. The 3 ACs,
cycle-1 defect fixes, and the generic non-spider2 harbor path all still pass.
Only the documented pre-existing base failures remain.

## Cycle-2 fix reproduction

- `uv run pytest tests/unit/test_translate_spider2_dbt.py tests/unit/test_harbor_task_view_materializer.py tests/integration/test_rk_run_spider2_dbt_explain.py` → **16 passed**, including the new `test_materialize_bind_produces_symlinked_view_files`, `test_materialize_copy_still_copies_view_files`, and `test_link_mode_symlinks_files_but_never_mutates_source_task_toml`.
- **Bind test is load-bearing.** Removed `view_mode=view_mode` from the spider2
  call site in `translate.py` → `test_materialize_bind_produces_symlinked_view_files`
  FAILED (`example.sql` was a copy, not a symlink: "bind mode must symlink, not
  copy, view files"). Restored → green. So the threading is genuinely exercised.
- **Threading chain confirmed end-to-end (ade-bench parity).**
  `cli/run.py:313` (`materialize_mode=materialize`, the same line ade-bench uses)
  → `spec_to_job_config` (param `translate.py:93`) → `_build_harbor`
  (`translate.py:119` passes it, param `translate.py:307`) →
  `bind`→`link`/`copy`→`copy` map (`translate.py:370-372`) →
  `materialize_spider2_harbor_task_view(view_mode=…)` (`translate.py:378`).

## NEW deviation verdict — `_patch_task_toml` unlink-before-write — SOUND

The implementer added (beyond the literal brief) to `materialize.py:140-145`:
under `view_mode="link"` the reflected `task.toml` is a symlink back into the
shared source; `write_text` would follow the link and write the injected
benchmark env into the committed source fixture. The fix unlinks the symlink
first so the patched `task.toml` is a real, view-owned file.

- **Sound + minimal + correctly scoped.** 6 lines, guarded by
  `task_toml.is_symlink()`. In `copy` mode `shutil.copy2` produces a real file →
  `is_symlink()` is False → no-op. In `link` mode it replaces the symlink with a
  view-owned file. No error suppression, no fallback path, no behavior change for
  the generic harbor path. It addresses a genuine latent correctness bug that
  link mode (newly reachable via the fix) exposes.
- **Load-bearing.** Reverted the unlink block →
  `test_link_mode_symlinks_files_but_never_mutates_source_task_toml` FAILED (view
  `task.toml` stayed a symlink). Restored → green.
- **Source fixture proven un-mutated under bind/link.** Ran the real spider2
  materializer against the *committed* fixture
  `tests/fixtures/spider2_dbt/.../spider2-fixture-001` with `view_mode="link"`:
  view `task.toml` is a real file carrying `RAZORBACK_BENCHMARK_KIND`, bulk files
  are symlinks, source `task.toml` byte-for-byte unchanged, `git status` on the
  fixture tree CLEAN. With the unlink fix reverted, the same run mutated the
  source (`git status` showed `M …/spider2-fixture-001/task.toml`, injected env
  leaked in) — restored fixture via `git checkout`. This proves both directions.

## No regression from cycle 1

- **3 ACs still pass** (re-run above; 16/16 green, AC-1/2/3 covered).
- **Cycle-1 defect fixes intact:** no production env seam
  (`_resolve_harbor_dataset_tasks` body untouched); selectors filter source paths
  pre-materialize (`test_exclude_tasks_drops_spider2_source_slug`,
  `test_n_tasks_caps_spider2_before_materialize` pass); negative-leakage rider
  passes.
- **Generic non-spider2 harbor path unchanged:** `uv run pytest
  tests/unit/test_translate_harbor_block.py` → **7 passed**. The only base→head
  diff to that path is the variable rename `task_paths`→`source_paths` (then
  `task_paths = source_paths` after the spider2 early-return) — byte-equivalent.
- **Broad suite:** `uv run pytest tests/unit
  --ignore=tests/unit/test_task_identity_scoring.py` → **676 passed, 2 failed**.
  The two failures (`test_matrix_specs_carry_query_mode_batch`,
  `test_rk_research_new_creates_scaffold_tree`) and the deselected
  `razorback.score.load` collection error were all reproduced FAILING on a fresh
  `1547f16` worktree checkout — pre-existing base failures, NOT regressions.
