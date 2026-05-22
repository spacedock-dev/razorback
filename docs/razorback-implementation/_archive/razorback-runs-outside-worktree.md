---
id: x9wz0wb8x4gm2wfqdn5c7de6
title: razorback runs_dir default outside the worktree
status: done
source: goal1-resume-spacedock-first 2026-05-22 — FO `git worktree remove --force` destroyed `runs/goal1-resume/` with per-cell validation.json, reward_per_query.json, session jsonl traces, audit-aggregate. Per-query rescore against paper's metric now impossible without re-running.
started: 2026-05-22T23:11:16Z
completed: 2026-05-22T23:54:18Z
verdict: PASSED
score: 0.95
worktree: 
issue:
pr:
mod-block: 
archived: 2026-05-22T23:54:22Z
---

## Problem

Razorback's experiment outputs (the project's actual deliverable)
live under worktree-relative gitignored paths: `runs/`, `_runs/`,
`.runs/`. When the FO runs `git worktree remove --force` at entity
terminal cleanup, those paths get deleted along with the worktree
filesystem.

goal1-resume-spacedock-first shipped on 2026-05-22 with verdict
PASSED; the merge + force-remove sequence destroyed:

- `runs/goal1-resume/{spacedock}/{12 datasets}/.../validation.json`
  (per-query pass/fail map — would have let us rescore using
  paper's `per_query_pass_at_1` metric instead of razorback's
  binary `rk score`)
- `runs/goal1-resume/.../reward_per_query.json` (verify_batch.py's
  own per-query map)
- Session jsonl traces (the basis for the $94.77 reconstructed
  cost — now unverifiable)
- `runs/goal1-resume/audit-aggregate.json`
- All freeze trees at `<run-dir>/_razorback/freeze/<sealed_hash>/`
  that spacedock_solver_v2 wrote for halt/resume

The root cause is razorback's default — `runs_dir` defaults to a
worktree-relative path. The same FO + razorback combination
destroys outputs every time an entity ships.

## Acceptance criteria

**AC-1 — Default `runs_dir` is OUTSIDE the worktree.**
When no `--output-dir` is supplied, razorback writes to
`$XDG_DATA_HOME/razorback/runs/` (default
`~/.local/share/razorback/runs/`) or honors `$RAZORBACK_RUNS_DIR`
when set. The path is absolute, NOT worktree-relative.
Verified by: a unit test asserts the resolved default path is
not a sub-path of `Path.cwd()` or the active git worktree.

**AC-2 — Backward compat for `--output-dir`.**
Explicit `--output-dir runs/foo/` still works as today (relative
to cwd). Existing experiment specs that hardcode
worktree-relative paths still run.
Verified by: existing integration tests stay green.

**AC-3 — Migration documented.**
The repo README + razorback CLI help mention the new default
location. The harbor-DAB plugin's docs reference the same.
Verified by: README has a short "Where do runs go?" section.

**AC-4 — Worktree teardown can no longer destroy runs.**
A smoke test creates a worktree, runs a cell, removes the
worktree, then asserts the run artifacts are still readable
from the user-data location.
Verified by: an integration test exercises this sequence.

## Test plan

- **Unit:** path-resolution helper test (AC-1).
- **Integration:** worktree-create → cell-run → worktree-remove
  → artifacts-still-readable smoke (AC-4).
- **Acceptance:** running the existing goal1-resume specs against
  the new default produces a runs tree at the user-data location.

## Out of scope

- Migrating existing experiment specs to the new default. They
  can opt in over time.
- Run-dir cleanup / retention policies — that's a future entity.
- Cross-worktree run discovery / indexing — see
  `freeze-tree-content-addressable-store` for the freeze case.

## Depends on

- None. Independent infra change.

## Resume hook

After this entity merges, the next razorback experiment dispatch
writes artifacts to a path that survives worktree teardown.
Goal 1's matrix re-run becomes safe.

## Stage Report: plan

- DONE: Separate plan doc at docs/razorback-implementation/plans/razorback-runs-outside-worktree.md per the README's 4+-AC rule. Include an AC↔task map and spec §-cites where relevant.
  Plan written at `docs/razorback-implementation/plans/razorback-runs-outside-worktree.md` with an "AC ↔ Task map" table covering AC-1..AC-4 and per-task file/line cites into `src/razorback/cli/run.py:141`, `runs_dir_canary.py`, and `examples/drivers/dab-paper-matrix.sh:36`.
- DONE: Name the exact module/function for runs_dir default resolution (currently worktree-relative). Specify env-var ($RAZORBACK_RUNS_DIR) + XDG fallback ordering, and how --output-dir backward compat (AC-2) is preserved.
  New module `src/razorback/runs_dir_default.py` exposing `resolve_default_runs_dir() -> Path` with precedence `$RAZORBACK_RUNS_DIR` → `$XDG_DATA_HOME/razorback/runs` → `~/.local/share/razorback/runs`. T2 changes `cli/run.py:141` to `Optional[Path] = None` and resolves at entry; existing `--runs-dir` callers unaffected. AC-2 ambiguity flagged: razorback's `rk run` uses `--runs-dir`, the only `--output-dir` is the matrix-driver shell flag (`examples/drivers/dab-paper-matrix.sh:36`); plan interprets AC-2 as keeping both surfaces verbatim (T3 locks the driver shape).
- DONE: Spec the AC-1 unit test (path-resolution helper) and AC-4 worktree-teardown smoke test — name test file paths and the smallest end-to-end exercise that proves AC-4.
  AC-1 unit tests at `tests/unit/test_runs_dir_default.py` (6 cases incl. `test_default_not_under_cwd`). AC-4 integration smoke at `tests/integration/test_worktree_teardown_preserves_runs.py`: create throwaway worktree under `tmp_path`, run `rk run` from inside with `_invoke_harbor` mocked, `git worktree remove --force`, assert `spec.frozen.yaml` still readable at the `$RAZORBACK_RUNS_DIR`-rooted run-dir.

### Summary

Plan decomposes the entity into 6 TDD tasks (T0..T5) ordered riskiest-contract-first: resolver RED+GREEN before CLI wiring before mechanism-validation worktree smoke. The one substantive ambiguity in the spec (AC-2's "`--output-dir` backward compat" when `rk run` actually uses `--runs-dir`) is flagged at the top of the plan so the executing agent stops and asks if the interpretation is wrong before touching code. Each task lists exact file paths, complete test/code bodies, and the commit message; no placeholders.

## Stage Report: implementation

- DONE: Execute the T0..T5 plan at docs/razorback-implementation/plans/razorback-runs-outside-worktree.md TDD-first (RED → GREEN → REFACTOR per task). Riskiest contract (resolver precedence + path absoluteness) lands before CLI wiring before worktree-teardown smoke.
  Six commits, T0..T5 in plan order: e249efd (T0 RED) → ddb1388 (T1 GREEN) → 30076a0 (T2 wire CLI) → f2dbd40 (T3 driver shape) → a73b323 (T4 worktree smoke) → 0636ca5 (T5 docs). No deviations from plan.
- DONE: All 4 ACs have proof from this stage: AC-1 unit tests green; AC-2 existing rk run tests still green; AC-3 README + DAB plugin README updated with `Where do runs go?`; AC-4 worktree-teardown smoke green.
  AC-1: tests/unit/test_runs_dir_default.py 6/6 PASS. AC-2: tests/unit/test_cli_run_default_runs_dir.py::test_explicit_runs_dir_wins_over_env + tests/unit/test_dab_paper_matrix_driver_shape.py 2/2 + existing tests/unit/test_rk_run_v2_harbor_cache_dir.py + test_cli_run_aggregator_wiring.py + test_rk_run_v2_provenance_artifacts.py + test_rk_run_budget_gate.py all PASS. AC-3: README.md 25 lines (≤30), `grep -c "Where do runs go"` finds 1 in both READMEs, `rk run --help` shows the new default text. AC-4: tests/integration/test_worktree_teardown_preserves_runs.py 1/1 PASS.
- DONE: Stage report enumerates passing test counts and `uv run pytest` output excerpt for the new tests; calls out any deviation from the plan with the AC cite.
  Final bundle: 21 passed in 1.13s across the new + affected suites. Excerpt: `tests/unit/test_runs_dir_default.py ...... [28%] tests/unit/test_cli_run_default_runs_dir.py .. [38%] tests/unit/test_dab_paper_matrix_driver_shape.py .. [47%] tests/integration/test_worktree_teardown_preserves_runs.py . [52%] tests/unit/test_rk_run_v2_harbor_cache_dir.py . [57%] tests/unit/test_cli_run_aggregator_wiring.py ... [71%] tests/unit/test_rk_run_v2_provenance_artifacts.py . [76%] tests/unit/test_rk_run_budget_gate.py ..... [100%] ============================== 21 passed in 1.13s ==============================`. No deviations.

### Summary

Implemented the default-runs-dir resolver (`src/razorback/runs_dir_default.py`) and wired it through `rk run`'s `--runs-dir` Typer option (default flipped from `Path("_runs")` to `None`, resolved at command entry). All four ACs proven from this stage: AC-1 by 6 resolver unit tests, AC-2 by an explicit-flag CLI test plus the matrix-driver shape lock plus all pre-existing `rk run` test suites still green, AC-3 by minimal top-level README (25 lines with a `Where do runs go?` section) + appended DAB plugin note + CLI help string, AC-4 by an integration smoke that creates a throwaway git worktree, runs `rk run` from inside it with `RAZORBACK_RUNS_DIR` set, then `git worktree remove --force` and reasserts the artifacts.

## Stage Report: validation

- DONE: Re-run the full test bundle from the worktree on a clean checkout: `uv run pytest tests/unit/test_runs_dir_default.py tests/unit/test_cli_run_default_runs_dir.py tests/unit/test_dab_paper_matrix_driver_shape.py tests/integration/test_worktree_teardown_preserves_runs.py tests/unit/test_rk_run_v2_harbor_cache_dir.py tests/unit/test_cli_run_aggregator_wiring.py tests/unit/test_rk_run_v2_provenance_artifacts.py tests/unit/test_rk_run_budget_gate.py`. Report actual exit code + N/N pass count. Also run `uv run pytest` for full-suite regression.
  Bundle: exit 0, 21/21 PASS in 1.51s, matches impl report. Full-suite `uv run pytest -m "not integration" --timeout=60 -q`: 548 PASS, 5 SKIPPED, 4 DESELECTED, 2 FAILED (`test_rk_run_nop::test_rk_run_nop_end_to_end` and `test_rk_run_bookreview_spacedock_halt_resume`). Both failures reproduced verbatim on `main` HEAD `08168b2` — pre-existing, unrelated to this entity.
- DONE: Verify each AC's `Verified by:` clause directly against the worktree state: AC-1 unit test assertions hit real env-var precedence; AC-3 README has `Where do runs go?` section (≤30 lines) + DAB plugin README has the note + `rk run --help` shows the new default text (run the command, paste output); AC-4 smoke test exercises the worktree-create → run → worktree-remove sequence.
  AC-1: `test_default_not_under_cwd` encodes the verification clause verbatim (asserts `cwd not in resolved.parents`); 6/6 resolver tests PASS. AC-3: `wc -l README.md` = 25, `grep "Where do runs go"` matches in both READMEs, `rk run --help` shows `Defaults to $RAZORBACK_RUNS_DIR, else $XDG_DATA_HOME/razorback/runs, else ~/.local/share/razorback/runs`. AC-4: smoke creates real `git worktree add`, mocks `_invoke_harbor`/`_run_canary`, runs `rk run` from inside, `git worktree remove --force`, re-asserts artifact path readable — 1/1 PASS.
- DONE: Run superpowers:requesting-code-review against the worktree branch. Write validation report to docs/razorback-implementation/validation/razorback-runs-outside-worktree.md with PASS/FAIL per AC + blocking/non-blocking findings + gate decision (approve to done or reject back to implementation with concrete fixes).
  Report at `docs/razorback-implementation/validation/razorback-runs-outside-worktree.md`. Code review: zero blocking findings, 5 non-blocking observations (mostly stylistic; resolver behavior matches docs; AC-4 mocking scope is correct). Gate: APPROVE → `done`.

### Summary

All four ACs PASS against the worktree state with the exact `Verified by:` clause encoded per AC. 21/21 targeted bundle PASS; 548/548 non-integration tests PASS; the 2 failing tests are pre-existing on `main` and reproduce identically. Code review: zero blocking findings. Gate: APPROVE → `done`.
