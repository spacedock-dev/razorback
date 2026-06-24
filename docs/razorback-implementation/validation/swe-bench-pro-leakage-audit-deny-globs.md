# Validation Report: swe-bench-pro — leakage deny-globs (gold/test patch isolation)

- Entity: `docs/razorback-implementation/swe-bench-pro-leakage-audit-deny-globs.md` (cycle-3 plan report authoritative)
- Branch under test: `swe-bench-pro-leakage-audit-deny-globs` @ `a06a51d`
- Worktree: `.worktrees/swe-bench-pro-leakage-audit-deny-globs` — `git status` clean, at branch tip (confirmed)
- Base for diffs/regression: `main` @ `31d796e`
- Validator: fresh independent verifier (did NOT trust implementer self-report; reproduced everything)

## GATE DECISION: APPROVE

All 3 ACs PASS with independently reproduced evidence. The security design is correct: over-match (which would corrupt the agent's repo) is eliminated, the shared default is untouched, and AC-2 is verifiably load-bearing. The code-review's two Important findings are **under-match** shapes (case-sensitivity, `gold.diff` variant) that reduce entirely to the already-flagged **captain-decision #1** ("exact harbor answer filenames" — unhydrate-able offline). They are not AC failures and not regressions. They are non-blocking for the gate but are recorded below as a sharpening of the captain-verifiable assumption the captain should confirm on first real hydration.

---

## Per-AC PASS/FAIL

### AC-1 — materialized swe view excludes gold/test-patch/answer paths AND keeps legit nested repo files — PASS

`Verified by:` a test that materializes the fixture task through the swe materializer branch and asserts `assert_no_denied_paths` does not raise and no `*.patch`/`test_patch*`/`gold*` survives.

Command:
```
uv run pytest tests/ -k 'swe_bench_pro and leak' -v
```
Output: `9 passed, 860 deselected in 2.02s`. The AC-1 positive materialize test `test_materialized_swe_view_strips_root_answers_keeps_nested_repo_leak` PASSED — root answers stripped (`gold/gold_patch.diff`, `test_patch.diff`, `FAIL_TO_PASS.json`, `solution/gold_patch.diff` all absent from view), legit nested `src/answer_engine.py` survives, `assert_no_denied_paths` does not raise.

### AC-2 — negative leakage test FAILS when swe deny-globs reverted (load-bearing) — PASS

`Verified by:` a test that plants gold/test-patch files, materializes, asserts excluded; reverting the globs makes materialize leak / not raise.

LOAD-BEARING REVERT PROOF (validator-run, before/after):
- BEFORE (production set): `uv run pytest tests/unit/test_swe_bench_pro_leakage.py -k leak` → 8 passed.
- REVERT: validator edited `SWE_BENCH_PRO_DENY_GLOBS = ("solution/**","solutions/**","tests/expected/**")` (the revert baseline the plan names). Re-ran:
  ```
  4 failed, 4 passed
  FAILED test_swe_leak_globs_deny_task_root_answer_artifacts
  FAILED test_materialized_swe_view_strips_root_answers_keeps_nested_repo_leak
  FAILED test_planted_swe_answers_are_excluded_from_view_leak
  FAILED test_reverting_swe_globs_leaks_planted_answers_leak  -> "DID NOT RAISE LeakageError"
  ```
  Critically `test_planted_swe_answers_are_excluded_from_view_leak` FAILED (planted answers leaked into the production view) and the `pytest.raises(LeakageError)` assertion FAILED (curated set no longer raises). The test is genuinely load-bearing.
- AFTER (`git checkout` restore): `8 passed`. Green restored.

### AC-3 — the swe branch actually passes the curated exclude_globs — PASS

`Verified by:` a test (or grep) asserting the swe `_build_harbor` branch passes the extended exclude_globs.

- Static: `grep -nF 'exclude_globs=SWE_BENCH_PRO_DENY_GLOBS' src/razorback/translate.py` → `432:                        exclude_globs=SWE_BENCH_PRO_DENY_GLOBS,`
- Runtime spy: `test_swe_branch_passes_curated_exclude_globs_leak` PASSED — captured `exclude_globs == SWE_BENCH_PRO_DENY_GLOBS` and `!= DEFAULT_SOLUTION_DENY_GLOBS`.

---

## Independent fnmatch deny/allow evidence

Validator wrote its OWN probe against the IMPLEMENTED `SWE_BENCH_PRO_DENY_GLOBS` (read verbatim from `src/razorback/harbor_tasks/leakage.py:38-56`, not copied from the report) using the real matcher `fnmatch.fnmatch(rel_posix, pattern)`.

- STANDALONE: `**/answer*`, `**/solution.*`, `**/*answers*` all ABSENT from the set. Confirmed standalone, not a default superset.
- ALLOW (14 nested legit repo files, none denied — over-match check): `src/answer_engine.py`, `lib/myanswers.py`, `pkg/solution_helpers.py`, `src/solution_loader.py`, `config/answers_schema.json`, `tests/test_patch_helpers.py`, `a/test_patch/file.py`, `astropy/io/tests/test_patch_io.py`, `django/test/patches.py`, `lib/patch.py`, `src/patches/apply.py`, `docs/changelog.diff`, `docs/gold_notes.md`, `tests/fixtures/gold_case.py` → ALL `allow ok`. **`src/answer_engine.py` clean (the captain-named over-match case).**
- DENY (14 task-root answer artifacts, all denied): `gold/patch.diff`, `gold_patch.diff`, `gold.patch`, `test_patch.diff`, `FAIL_TO_PASS.json`, `PASS_TO_PASS.json`, `patch`, `patch.diff`, `solution.patch`, `solution.cfg`, `answer.json`, `answers.json`, `solution/x.py`, `tests/expected/out.csv` → ALL `deny ok`.
- RESULT: PASS (0 allow failures, 0 deny failures).

---

## Shared-default-unchanged confirmation

`git diff main -- src/razorback/harbor_tasks/leakage.py` shows ONLY additions (the `SWE_BENCH_PRO_DENY_GLOBS` block + its comment); no edits or removals to `DEFAULT_SOLUTION_DENY_GLOBS` (leakage.py:7-14). The generic `materialize_harbor_task_view` default param `exclude_globs: tuple[str, ...] = DEFAULT_SOLUTION_DENY_GLOBS` (materialize.py:36) is untouched (no diff). spider2/ade/dabstep dependents unaffected.

---

## Full suite + regression-vs-preexisting classification (validator's own base check)

Branch: `uv run pytest tests/ -q` → **853 passed, 4 failed, 12 skipped**.

The 4 failures: `test_codex_runtime_dispatch_constructs_inner_agent`, `test_worktree_remove_force_does_not_destroy_runs`, `test_matrix_specs_carry_query_mode_batch`, `test_rk_research_new_creates_scaffold_tree`.

Base check (validator created a throwaway detached worktree at `main`/`31d796e`, confirmed `SWE_BENCH_PRO_DENY_GLOBS` is absent there, ran the 4 named tests):
```
4 failed in 21.17s  (same 4 tests)
```
→ All 4 are PRE-EXISTING on main, NOT regressions caused by this branch. Throwaway worktree removed after the check.

E1 swe-bench-pro + spider2 suites: green within the full run (`test_translate_swe_bench_pro.py`, `test_spider2_dbt_harbor_view.py` all pass; the acceptance `-k` run shows the E1 leakage-clean test `test_swe_resolves_n_views_with_manifest_leakage_clean` PASSED).

---

## Deviation scrutiny (ruff E402 import consolidation)

Commit `e6b84d7 style(leakage): consolidate test imports to top (ruff E402)` — `git show` confirms it touches ONLY `tests/unit/test_swe_bench_pro_leakage.py` (21 insertions, 26 deletions), moving imports + the `FIXTURE_ROOT`/`_REVERT_BASELINE` constants from mid-file to the top. Identical symbols, no production code, no behavior change. Tests remain green. Benign.

---

## Code-review findings (classified)

Reviewer: `superpowers:requesting-code-review` (general-purpose, base `main`). Validator independently reproduced every under-match claim via fnmatch probe.

### Blocking: NONE

### Non-blocking (captain-verifiable — sharpen the existing assumption #1, do not block merge)

The whole defense rests on harbor emitting answer artifacts as task-ROOT sibling files with EXACT names — already flagged as captain-decision #1 (unhydrate-able offline) and the Task-0 sibling-file assumption (plan decisions 1 & 4, probe note (b)/(e)). The reviewer's two Important findings are additional shapes of that SAME unverified-filename surface, confirmed by validator probe:

1. **Case-sensitivity under-match (Important).** `fnmatch` on posix is case-sensitive; the matcher does no lowercasing. ESCAPES: `Gold.patch`, `GOLD.patch`, `Patch`, `PATCH`, `Gold_patch.diff`, `FAIL_to_PASS.json`, `fail_to_pass.json`, `Answer.json`, `Solution.patch`. If harbor capitalizes any answer filename, it leaks silently with no fail-closed backstop.
2. **`gold.diff` / bare `gold` variant under-match (Important).** Covered: `gold_patch.diff`, `gold.patch`. ESCAPES: `gold`, `gold.diff`, `goldpatch.diff`. The fixture itself mixes `gold/gold_patch.diff` (with `_patch`) and `test_patch.diff` (with `.diff`), so a `gold.diff` gold patch is a plausible real name.
3. **Nested-metadata-dir under-match (Minor).** ESCAPES: `meta/gold.patch`, `grading/FAIL_TO_PASS.json`, `.harbor/gold.patch`, `verifier/gold/patch.diff`. This is the deliberate consequence of root-anchoring (the same property that prevents over-match). Acceptable given the recorded "task-root sibling" assumption.

These are NOT AC failures, NOT regressions, and NOT over-match (no legit repo file is wrongly stripped). They are the expected residual of a precise root-anchored set whose exactness depends on harbor's real layout — which E2 explicitly cannot verify offline and explicitly defers to the captain. The set is correct for the documented/assumed layout (lowercase, root-level, the assumed names). Recommended (non-blocking) follow-up at merge time: the captain confirms harbor's real answer filenames + casing on first real hydration and amends the root-anchored names if they differ (exactly the captain-decision-1 mechanism the plan already defines). Optionally add `"gold.diff"` and a case-sensitivity note to tighten before that hydration.

### Reviewer verdict: "With fixes" (the fixes being the captain-verifiable assumption sharpening above) — Strengths confirmed: standalone design correct, shared default untouched, AC-2 load-bearing, AC-3 double-covered, ruff commit test-only.

---

## Summary

Gate: **APPROVE**. AC-1/AC-2/AC-3 all PASS with independently reproduced evidence (acceptance 9 passed; revert proof shows 4 fail-on-revert incl. the production-path leak and the LeakageError no-raise; AC-3 wiring at translate.py:432 + runtime spy). Independent fnmatch probe confirms `src/answer_engine.py` clean, all 14 deny matched, set is standalone. Shared `DEFAULT_SOLUTION_DENY_GLOBS` and the generic materializer default param are byte-for-byte unchanged. Full suite 853 passed; the 4 failures are confirmed pre-existing on main (validator's own base check). The E402 deviation is test-only. Code review found no blocking issues; the under-match shapes (casing, `gold.diff`, nested dirs) are the already-flagged captain-decision-1 unverifiable-filename surface, recommended for captain confirmation at merge but not gate-blocking.

---

## Validation cycle 2 (2026-06-24) — fail-closed deep-scan guard

Independent re-verification of the cycle-2 guard (`assert_no_swe_answer_leak` +
`is_swe_answer_artifact`, leakage.py:93-131) added after the cycle-1 gate was
rejected for the nested-leak hole. Reproduced from the committed branch tip
(`f3e8b66`, base `main` `620030b`); worktree clean.

### THE GUARD — raises on nested answers (2a) — PASS

Independent tmp-dir probe calling the function directly (not via the test file):
`repo/test_patch.diff`, `meta/gold_patch.diff`, `repo/sub/FAIL_TO_PASS.json`,
`gold/anything.txt` → `is_swe_answer_artifact` all True; `assert_no_swe_answer_leak`
RAISED `LeakageError` listing all 4. Named tests: 12/12 pass, incl.
`test_swe_answer_leak_guard_raises_on_nested_answers_leak` and the production-path
`test_swe_branch_deep_guard_raises_on_nested_leak_in_production_leak`.

### THE GUARD — no false positive (2b) — PASS

`tests/test_patch_helpers.py`, `src/answer_engine.py`, `lib/patch.py`,
`docs/gold_notes.md`, `a/test_patch/file.py`, `src/patches/apply.py`,
`config/answers_schema.json` → all `is_swe_answer_artifact`=False;
`assert_no_swe_answer_leak` on a legit-only view did NOT raise.

### Wired in production (2c) — PASS

translate.py:446 `assert_no_swe_answer_leak(view)` runs inside the per-source loop
AFTER `materialize_harbor_task_view` returns (line 433-445) and BEFORE
`task_paths.append(view)` (line 447), in the swe (else) branch. A leaking view can
never reach `JobConfig`.

### LOAD-BEARING (3) — PASS

Neutered `is_swe_answer_artifact` to `return False` → the 2 nested-leak tests FAILED
with "DID NOT RAISE <LeakageError>" (incl. the end-to-end production-path test).
Restored → 2 passed, `git diff` clean. The guard is genuinely load-bearing.

### 3 original ACs still green (4) — PASS

`pytest -k 'swe_bench_pro and leak'` → 13 passed. AC-2 independent revert (collapsed
`SWE_BENCH_PRO_DENY_GLOBS` to drop the answer-artifact globs) → 5 tests FAIL: the
planted root answers are no longer glob-stripped (and the deep guard catches them,
raising LeakageError on the positive-path test) — load-bearing confirmed. Restored → green.

### Case-insensitivity (5) — PARTIAL / one BLOCKING gap

Basenames are case-folded: `Gold.patch`, `GOLD_PATCH.DIFF`, `gold.diff`,
`Test_Patch.diff`, `FAIL_TO_PASS.JSON` → all True. BUT the `gold/` parent-dir rule
(leakage.py:106) is case-SENSITIVE: `is_swe_answer_artifact('x/Gold/secret.diff')`=False,
`'x/GOLD/secret.diff')`=False, while `'x/gold/secret.diff')`=True. Cycle-1 feedback
explicitly directed "make the guard case-insensitive"; this is a PARTIAL implementation.
The code comment (leakage.py:73-76) claims the case-fold is a "safe superset" — false
for the dir rule. A swe answer file landing under a `Gold/`/`GOLD/` dir leaks silently
with no backstop. BLOCKING.

### Shared default + pass-through unchanged (6) — PASS

`git diff main -- leakage.py`: additions only, no removals. `DEFAULT_SOLUTION_DENY_GLOBS`
byte-identical on main (7-14). `materialize.py:36` default param still
`DEFAULT_SOLUTION_DENY_GLOBS`. `git diff main --stat` touches no
`src/razorback/benchmarks/` — spider2/ade/generic pass-through unaffected.

### Full suite + regression classification (7) — PASS

`pytest tests/ -q` → 857 passed, 4 failed, 12 skipped. The 4
(test_codex_runtime_dispatch_constructs_inner_agent, test_worktree_remove_force_does_not_destroy_runs,
test_matrix_specs_carry_query_mode_batch, test_rk_research_new_creates_scaffold_tree)
reproduce on a fresh detached `main` worktree (HEAD 620030b, SWE guard ABSENT — grep
count 0) → pre-existing, NOT regressions. E1 swe + spider2: 121 passed.

### Code review (8) — verdict "With fixes"; 1 Important reclassified BLOCKING by gate

Reviewer (general-purpose, base main): no Critical. 1 Important — the case-sensitive
`gold/` dir compare (leakage.py:106), independently reproduced above. 2 Minor —
`gold_patch.*` glob redundant with the `gold_patch.diff` literal; `rglob` does not
descend dir-level symlinks (latent coupling, not currently reachable since the
materializer makes real dirs + per-file symlinks). Over-match residual (top-level repo
file named `patch`/`solution.*` if harbor flattens the repo) judged accept-as-documented:
fails toward OVER-strip (visible broken task), not under-strip (silent leak); deep guard
is exact-name and does not widen it; collapses to captain-decision #1. Uncovered leak
shapes — bare `gold` (no ext), a non-answer-named `*.patch` that is the gold patch,
gold nested under a non-`gold/` dir (`solution/the_fix.diff`, `meta/answer.patch`) — all
unknowable-filename shapes that collapse to captain-decision #1 (the real harbor layout
cannot be hydrated offline). Non-blocking.

### GATE DECISION: REJECT → implementation

The guard closes the nested-leak hole, is load-bearing, false-positive-free, and wired
in production; the 3 ACs stay green; the shared default is untouched; the 4 failures are
pre-existing. The single blocking item is that the cycle-1-directed case-insensitivity is
implemented for basenames only, leaving the `gold/` parent-dir rule case-sensitive — a
real silent-leak shape for `Gold/`/`GOLD/`-nested answers, contradicting the code's own
"safe superset" comment.

CONCRETE FIX (one word, leakage.py:106):
`parts[-2] == _SWE_ANSWER_PARENT_DIR` → `parts[-2].lower() == _SWE_ANSWER_PARENT_DIR`
and add a `Gold/`/`GOLD/`-nested case to `test_swe_answer_leak_guard_raises_on_nested_answers_leak`.
Re-validate the dir rule catches mixed-case `gold` dirs. The 2 Minor findings and all
unknowable-filename shapes remain captain-decision #1 (non-blocking).
