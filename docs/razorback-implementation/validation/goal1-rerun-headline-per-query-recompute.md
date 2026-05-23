---
title: Validation — Goal 1 re-run, recompute captain-facing headline against canonical per-query reducer (post-1s)
entity: docs/razorback-implementation/goal1-rerun-headline-per-query-recompute.md
branch: spacedock-ensign/goal1-rerun-headline-per-query-recompute
worktree: .worktrees/spacedock-ensign-goal1-rerun-headline-per-query-recompute
validator: spacedock-ensign-goal1-rerun-headline-per-query-recompute-validation
date: 2026-05-23
verdict: PASS (captain auto-approval pre-authorized per sprint directive)
---

## Gate decision

**PASS — approve to `done`.**

All 4 ACs reproduce end-to-end against worktree branch
`spacedock-ensign/goal1-rerun-headline-per-query-recompute` (HEAD `3433f39`).
The captain-facing headline at
`docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md`
now reads the per-query number (`0.722 [0.591, 0.824]`, 39/54 query passes,
verdict `above` vs paper `0.577`) instead of the archived binary
`0.333 [0.138, 0.609]`. Audit history (cycle-1 + cycle-2 binary headlines)
preserved verbatim. The binary-headline directive from captain
2026-05-23 is closed end-to-end.

No new test regressions vs `main` baseline. Code-review pass surfaced
no Critical or Important findings.

## AC reproduction

### AC-1 — Recomputed headline reads `reward_per_query.json`

**Verified-by clause:** run `examples/drivers/aggregate-goal1-scores.py`
against the existing matrix root; assert pooled per-query pass@1 = 0.722
(39/54), yelp contribution = 6/7 not 0.

**Reproduced from clean checkout (worktree HEAD `3433f39`):**

```
$ uv run python examples/drivers/aggregate-goal1-scores.py \
    --matrix-root /Users/clkao/git/razorback/_runs/goal1-rerun-spacedock-opus47-xhigh
spacedock: scored 12/12 strata; pooled_pass@1=0.3333333333333333;
  pooled_per_query_pass@1=0.7222222222222222 (39/54); verdict=matches
direct-structured: scored 0/12 strata; ... no_data
direct-minimal: scored 0/12 strata; ... no_data
wrote .../runs/goal1/matrix/matrix-summary.json
```

(The stdout `verdict=matches` is the binary verdict; the per-query verdict
lives in JSON under `against_constant.per_query_verdict`, which reads `above`.)

**Yelp contribution (from `aggregate-score.json`):**

```
strata.yelp.per_query_pass_at_1     = 0.8571428571428571
strata.yelp.n_query_correct         = 6
strata.yelp.n_query_trials          = 7
strata.yelp.per_query_strata.yelp.dataset_pass_at_1 = 0.8571428571428571
                                                       (= 6/7 by passing per-query
                                                        query_ids 1,2,3,5,6,7)
```

**Pooled per-query headline (from same JSON):**

```
pooled_per_query_pass_at_1          = 0.7222222222222222
pooled_n_query_correct              = 39
pooled_n_query_trials               = 54
pooled_per_query_wilson_95ci        = [0.5910955707120475, 0.8238317234697763]
against_constant.per_query_verdict  = "above"
```

PASS — yelp contributes 6/7 (per_query_pass_at_1 = 0.857), pooled per-query
pass@1 = 0.722 (39/54), strictly different from the archived binary 0.333.

### AC-2 — Captain-facing report headline replaced

**Verified-by clause:**
`grep -F 'stratified_pass_at_1 = 0.333' report.md` returns 0 matches in the
Headline section and ≥1 match in the Audit history subsection.

**Reproduced:**

```
$ grep -nF 'stratified_pass_at_1 = 0.333' \
    docs/razorback-implementation/_evidence/goal1-rerun-dab-spacedock-opus47-xhigh-report.md
32:**Spacedock pooled `stratified_pass_at_1 = 0.333` ...**
278:   `stratified_pass_at_1 = 0.333` is a known under-count for DAB batch-mode
```

Line 32 falls inside `## Audit history — prior headlines` → `### Cycle-2
binary headline (pre-1s, archived)` (header at line 30). Line 278 is in
the `## Follow-ups` section. 0 matches inside the new `## Headline (post-1s
recompute — per-query)` block (lines 10-23).

New Headline reads:
```
**Spacedock pooled per-query pass@1 = 0.722 (95% Wilson CI [0.591, 0.824])
 across 54 query cells over 12 dataset strata.**
**Verdict vs paper `spacedock=0.577`: `above` (paper sits below the per-query
 CI lower bound at 0.591).**
```

PASS — Headline replaced; banner-box notice removed and replaced with the
one-line scoring callout; audit history preserves both prior binary
headlines (cycle-1 0.375 + cycle-2 0.333) as required.

### AC-3 — Per-cell table surfaces per-query pass@1

**Verified-by clause:** table column header includes `per_query_pass@1`;
yelp's row shows `per_query_pass@1: 0.857` (= 6/7).

**Reproduced:**

```
$ grep -n '^| dataset ' docs/.../goal1-rerun-dab-spacedock-opus47-xhigh-report.md
62:| dataset | n_total | n_pass | reward | pass@1 | per_query_pass@1 | wilson_95ci | ...
$ grep -n '^| yelp ' docs/.../goal1-rerun-dab-spacedock-opus47-xhigh-report.md
75:| yelp | 1 | 0 | 0.857 | 0.0 | 0.857 (6/7) | [0.0, 0.793] | 392s | 1 | yes | inside CI |
```

Per-cell `per_query_pass@1` cross-checks (from the per-row diff inspection):
all 12 cells show per_query_pass@1 matching continuous `reward` to four
decimals (yelp 0.857 = 6/7, crmarenapro 0.692 = 9/13, googlelocal 0.750 = 3/4,
PANCANCER_ATLAS 0.667 = 2/3, agnews 0.500 = 2/4, DEPS_DEV_V1 0.500 = 1/2,
GITHUB_REPOS 0.500 = 2/4, four 1.000 cells, PATENTS 0.000). No divergence
> 0.05 — no rows flagged. Pooled row shows `0.722 (39/54)` with both
per-query and binary CIs displayed for audit.

PASS.

### AC-4 — Provenance retained

**Verified-by clause:** bottom of report carries a 4-line provenance block
with the four citations; `git log` confirms the cited commit.

**Reproduced:**

```
$ sed -n '195,200p' docs/.../goal1-rerun-dab-spacedock-opus47-xhigh-report.md
## Provenance — post-1s recompute

- **Reducer source:** ... merged into `main` at commit `f76443b` on 2026-05-23.
- **Fixture source:** 12 cell run-dirs at `_runs/.../<dataset>/` ...
- **Matrix-execution source:** entity `an goal1-rerun-dab-spacedock-opus47-xhigh` (archived) ...
- **Recompute date:** 2026-05-23.

$ git show -s --format='%H %s' f76443b
f76443b605848185930bdf18c4238d712dba4e53
  merge: 1s runs-aggregate-single-score-reducer — single canonical per-query
         reducer, 6/7 DAB batch fix, validation PASSED cycle 2

$ git log --oneline main -- docs/.../runs-aggregate-single-score-reducer.md | head -2
c1fa7ad archive: runs-aggregate-single-score-reducer
eb33957 terminalize: 1s PASSED
```

PASS — block is 4 lines, citations resolve. The `1s` archive lineage and
`f76443b` merge commit both confirmed.

## Pytest baseline check

**Worktree branch `spacedock-ensign/goal1-rerun-headline-per-query-recompute`:**

```
$ uv run pytest --tb=no -q --ignore=tests/unit/test_task_identity_scoring.py
9 failed, 603 passed, 12 skipped, 22 warnings in 46.10s
```

(Without `--ignore`, pytest collection errors out on
`test_task_identity_scoring.py` because `razorback.score.load` was deleted
in commit `1f7592d feat: delete score/reduce.py + score/load.py` on `main`.
That deletion is pre-existing and unrelated to this branch.)

**Baseline `main`:**

```
$ uv run pytest --tb=no -q --ignore=tests/unit/test_task_identity_scoring.py
10 failed, 602 passed, 12 skipped, 22 warnings in 72.33s
```

The 9 worktree failures are a strict subset of the 10 main failures. The
10th main-only failure
(`test_dab_retirement.py::test_in_tree_dab_adapter_directory_is_not_active`)
fails on `main` because of a stale `src/razorback/benchmarks/dab/__pycache__/`
directory in the working tree (the source files are git-removed; the
pycache lingers). The worktree was created clean, so the directory doesn't
exist there. This is environmental noise on `main`'s working tree, not a
regression introduced by either branch.

**Conclusion:** zero new regressions introduced by this entity. The 9
pre-existing failures (`test_worktree_teardown_preserves_runs`,
`test_claude_benchmark_spec_generator`, two `test_generate_matrix_specs`,
five `test_generate_matrix_specs_per_variant_kind`) all reproduce identically
on both branches.

## Code review summary

(Performed inline against `git diff eef0c7a..HEAD` — base = `advance: d8
entering implementation`, head = `3433f39 docs(report): goal1-rerun post-1s
per-query recompute headline`. Two commits, 191 ins / 78 del across 3 files.)

### Strengths
- Driver delegates cleanly to canonical `reduce_per_query_stratified` +
  `count_trials` + `read_trial_outcomes`; binary `n_pass`/`n_total`/`pass_at_1`/
  `wilson_95ci` preserved alongside per-query fields for audit.
- Mechanism-first validation honored: yelp smoke (raw reducer against one
  cell, returned 0.857 with 7 queries / 6 passes) ran before any driver
  code change, per plan.
- Per-query verdict added to JSON as `against_constant.per_query_verdict`
  so the report's verdict matches the data.
- Audit history preserved verbatim (cycle-1 `0.375`, cycle-2 `0.333`, full
  banner-box rationale moved into `## Audit history` subsection — not
  deleted, satisfying AC-2's explicit non-deletion clause).
- Provenance block citations all resolve: `f76443b` is the real 1s merge
  commit; `c1fa7ad` is the real 1s archive commit.
- Per-cell sanity holds: every cell's `per_query_pass@1` agrees with its
  continuous `reward` to four decimals — no silent fallback-to-binary bug.

### Issues

**Critical:** none.

**Important:** none.

**Minor:**

1. `examples/drivers/aggregate-goal1-scores.py:240` — `json.dumps(...,
   default=list)` is used to serialize tuples coming through
   `pooled_per_query_ci`. An explicit `list(pooled_per_query_ci)`
   conversion (already done one level up at line 207) would be clearer
   than relying on the `default=` fallback. Functional; not blocking.
2. The per-cell `wilson_95ci` column in the per-dataset table still
   displays the BINARY cell-level Wilson CI (n=1), not the per-query
   Wilson CI. The pooled row resolves this by showing both CIs. The per-
   query Wilson CIs do live in the JSON under
   `strata.<ds>.per_query_strata.<ds>.queries[].wilson_ci` but aren't
   surfaced in the markdown. Acceptable scoping decision for this
   entity; could be a follow-up if captain wants per-cell per-query CIs
   in the table.

### Assessment

**Ready to merge: Yes.** All 4 ACs verified with concrete numerical
evidence; numbers match the entity's claims exactly; no new pytest
regressions; provenance resolves; audit trail preserved as required.

## Verdict

**PASS.** Closes the captain directive "stop reporting binary for dab"
(follow-up #4 from archived `an goal1-rerun-dab-spacedock-opus47-xhigh`).
The captain-facing headline now reads `0.722 [0.591, 0.824]` (per-query)
with verdict `above` vs paper `0.577`, replacing the under-counted binary
`0.333 [0.138, 0.609]`. Captain auto-approval pre-authorized per the
sprint directive in the dispatch prompt; advance to `done`.
