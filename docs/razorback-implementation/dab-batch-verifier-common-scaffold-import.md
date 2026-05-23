---
id: 296yjetkwygm8es8fve7yqy3
title: DAB batch verifier packages common_scaffold imports
status: backlog
source: DAB gpt-5.5/xhigh full batch run 2026-05-23 — common_scaffold verifier import failures
started:
completed:
verdict:
score: 0.92
worktree:
issue:
pr:
mod-block:
---

## Problem

The full DAB Codex batch run completed 12/12 trials, but four datasets
were unscored because generated batch validators import
`common_scaffold.validate.levenshtein` and the Harbor task verifier
environment does not include `common_scaffold` on Python's import path.
The DAB batch adapter must materialize verifier dependencies so affected
datasets produce score artifacts instead of verifier tracebacks.

## Acceptance criteria

**AC-1 — Batch DAB tasks make `common_scaffold` importable to validators.**
Generated batch task `tests/` content or verifier environment includes the
upstream DAB `common_scaffold` package needed by validators such as
`GITHUB_REPOS`, `PANCANCER_ATLAS`, `PATENTS`, and `stockmarket`.
Verified by: a materialization test or fixture imports an affected
`validate_qN.py` from the generated task and resolves
`common_scaffold.validate.levenshtein` without external network access.

**AC-2 — Batch verification emits score artifacts for affected validators.**
An affected batch task no longer exits before writing `reward.json` and
`reward_per_query.json` when a validator with a `common_scaffold` import is
present.
Verified by: a focused verifier test or generated-task smoke checks both
artifact files exist and parse as JSON after running `/tests/test.sh` or
`verify_batch.py`.

**AC-3 — Existing DAB batch and per-query behavior stays green.**
The fix does not break existing DAB materialization, verifier, or score
aggregation behavior.
Verified by: `UV_FROZEN=1 uv run --frozen pytest packages/razorback-plugin-dab/tests tests/unit/test_runs_aggregate.py tests/unit/test_rk_score.py -q` or a narrower equivalent justified in the validation report.

## Test plan

Implementation should add a regression test around the generated batch
task shape for at least one affected validator and run the focused DAB
plugin tests. Validation should independently run the regression and a
small affected DAB batch smoke that reaches score artifacts.

## Out of scope

This task does not tune solver prompts, rerun the full DAB 12-dataset
score, or change the solver's answers. It only fixes verifier packaging
so those runs can be scored.
