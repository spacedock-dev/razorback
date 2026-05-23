# Validation: razorback runs_dir default outside the worktree

**Entity:** `docs/razorback-implementation/razorback-runs-outside-worktree.md`
**Branch:** `spacedock-ensign/razorback-runs-outside-worktree`
**Worktree HEAD:** `9e3e90f` (after impl report)
**Merge base with main:** `be3df13`
**Validator cwd:** `/Users/clkao/git/razorback/.worktrees/spacedock-ensign-razorback-runs-outside-worktree`
**Gate decision:** APPROVE → `done`

---

## Test bundle (checklist item 1)

Targeted bundle from checklist item 1:

```
uv run pytest tests/unit/test_runs_dir_default.py \
              tests/unit/test_cli_run_default_runs_dir.py \
              tests/unit/test_dab_paper_matrix_driver_shape.py \
              tests/integration/test_worktree_teardown_preserves_runs.py \
              tests/unit/test_rk_run_v2_harbor_cache_dir.py \
              tests/unit/test_cli_run_aggregator_wiring.py \
              tests/unit/test_rk_run_v2_provenance_artifacts.py \
              tests/unit/test_rk_run_budget_gate.py
```

Result (verbatim tail):

```
tests/unit/test_runs_dir_default.py ......                               [ 28%]
tests/unit/test_cli_run_default_runs_dir.py ..                           [ 38%]
tests/unit/test_dab_paper_matrix_driver_shape.py ..                      [ 47%]
tests/integration/test_worktree_teardown_preserves_runs.py .             [ 52%]
tests/unit/test_rk_run_v2_harbor_cache_dir.py .                          [ 57%]
tests/unit/test_cli_run_aggregator_wiring.py ...                         [ 71%]
tests/unit/test_rk_run_v2_provenance_artifacts.py .                      [ 76%]
tests/unit/test_rk_run_budget_gate.py .....                              [100%]
============================== 21 passed in 1.51s ==============================
```

Exit code: 0. **21/21 PASS.** Reproduces the implementation report's 21/21 verbatim.

## Full-suite regression

```
uv run pytest -m "not integration" --timeout=60 -q
... 2 failed, 548 passed, 5 skipped, 4 deselected in 356.64s
```

The two failures are PRE-EXISTING and unrelated to this entity:

1. `tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py::test_seed_run_then_resume_run_against_matching_sealed_hash`
   `SpecError: spacedock-solver spec must be frozen (agent.sealed_hash missing).` — the seed spec under `examples/specs/bookreview-spacedock-seed.yaml` is not pre-frozen; this is an environment/data state issue, not a runs-dir bug.
2. `tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end`
   `AssertionError: events.jsonl is empty` — colima/harbor pathway, not the runs-dir resolver.

Reproduced on `main` (HEAD `08168b2`) with the identical exception, identical exit code (10 for the first), identical stderr. Both pre-existed before this entity's first commit (`e249efd`). Neither belongs to this entity's scope.

The 4 `deselected` are `@pytest.mark.integration` (live docker/colima/auth required). One of them, `tests/integration/test_budget_gate_two_invocations.py::test_two_sequential_invocations_second_refuses`, hangs when colima isn't running — verified the marker is set; deselection is correct.

## AC verification (checklist item 2)

### AC-1 — Default `runs_dir` is OUTSIDE the worktree

> Verified by: a unit test asserts the resolved default path is not a sub-path of `Path.cwd()` or the active git worktree.

**PASS.** `tests/unit/test_runs_dir_default.py::test_default_not_under_cwd` (file:55-69) encodes the verification clause verbatim:

```
monkeypatch.chdir(tmp_path / "fake_cwd_worktree")
resolved = resolve_default_runs_dir()
cwd = Path.cwd().resolve()
assert cwd not in resolved.parents, (
    f"default runs_dir {resolved} is under cwd {cwd}; AC-1 violated"
)
```

Plus `test_default_is_absolute` (line 48-52) asserts the path is absolute. Plus three precedence-ordering tests (`test_env_var_takes_precedence`, `test_xdg_fallback_when_no_razorback_env`, `test_home_local_share_default`) and tilde-expansion (`test_expands_tilde_in_razorback_env`). 6/6 PASS.

Resolver impl at `src/razorback/runs_dir_default.py` is 25 lines, returns `(Path.home() / ".local/share/razorback/runs").resolve()` as the final fallback — `Path.home()` resolves under `$HOME`, which is by definition outside any worktree under `$REPO_ROOT/.worktrees/`.

### AC-2 — Backward compat for `--output-dir`

> Verified by: existing integration tests stay green.

**PASS.** Interpretation (per plan) is that razorback's `rk run` uses `--runs-dir` (not `--output-dir`); the only `--output-dir` is the matrix driver's shell flag. Both surfaces are locked:

- `tests/unit/test_cli_run_default_runs_dir.py::test_explicit_runs_dir_wins_over_env` (PASS) — explicit `--runs-dir <path>` overrides `$RAZORBACK_RUNS_DIR`.
- `tests/unit/test_dab_paper_matrix_driver_shape.py` 2/2 PASS — driver still accepts `--output-dir`, still forwards `--runs-dir`, still defaults `OUTPUT_DIR="${REPO_ROOT}/runs/goal1"`.
- Pre-existing `rk run` suites all green: `test_rk_run_v2_harbor_cache_dir.py` (1), `test_cli_run_aggregator_wiring.py` (3), `test_rk_run_v2_provenance_artifacts.py` (1), `test_rk_run_budget_gate.py` (5). No CLI surface regression.

### AC-3 — Migration documented

> Verified by: README has a short "Where do runs go?" section.

**PASS.** Direct file inspection:

- `README.md` — 25 lines total (≤30 per the entity's "≤30 lines" budget):
  ```
  $ wc -l README.md
  25
  $ grep -n "Where do runs go" README.md
  6:## Where do runs go?
  ```
  Section covers default precedence + override + the worktree-survival rationale.
- `packages/razorback-plugin-dab/README.md` line 42: `## Where do runs go?` section appended; references the same precedence chain and points back to the top-level README.
- `rk run --help` output (run verbatim against the worktree's venv):
  ```
  │ --runs-dir                      PATH  Base directory for run-dirs. Defaults  │
  │                                       to $RAZORBACK_RUNS_DIR, else           │
  │                                       $XDG_DATA_HOME/razorback/runs, else    │
  ```
  Matches the resolver's precedence and notes "OUTSIDE any git worktree" per `src/razorback/cli/run.py:142-152`.

### AC-4 — Worktree teardown can no longer destroy runs

> Verified by: an integration test exercises this sequence.

**PASS.** `tests/integration/test_worktree_teardown_preserves_runs.py::test_worktree_remove_force_does_not_destroy_runs` exercises the actual worktree-teardown sequence end-to-end (1/1 PASS, ~3s):

1. Create real git worktree via `git worktree add --detach <wt> HEAD` (line 20-24).
2. Set `RAZORBACK_RUNS_DIR=<tmp_path>/runs` and `chdir` into the worktree (line 42, 50).
3. Invoke `rk run` against the worktree's own copy of `_deterministic-smoke.yaml` via `CliRunner` (line 52-60). `_invoke_harbor` and `_run_canary` are mocked because the production harbor pathway needs colima; the runs-dir mkdir / artifact-write pathway exercised is the production code.
4. Locate `<runs_root>/**/spec.frozen.yaml` (line 70).
5. `git worktree remove --force <wt>` (line 79).
6. Re-assert the artifact path is still readable and non-empty after teardown (line 82-85).

This is the exact failure mode that destroyed `runs/goal1-resume/` on 2026-05-22. The smoke now passes, confirming `git worktree remove --force` cannot reach the user-data location.

## Code review (checklist item 3)

Scope: 9 files changed since merge base `be3df13` (resolver + CLI wiring + 3 test files + 2 README updates + entity body update). 314 insertions, 1 deletion.

### Findings

**Blocking:** none.

**Non-blocking observations:**

1. `src/razorback/runs_dir_default.py:19` — uses `if explicit:` (truthy check) which correctly rejects empty-string env vars. Docstring says "if set and non-empty" — behavior matches doc. Consider explicit `os.environ.get("RAZORBACK_RUNS_DIR", "").strip()` if whitespace-only values should also be ignored, but YAGNI; current behavior is the standard env-var convention.
2. `tests/unit/test_cli_run_default_runs_dir.py:32` — "Tolerate non-zero exit on downstream contract issues" is a sound choice (the assertion verifies directory creation; harbor mocking suffices). The AC-4 smoke separately exercises the full mkdir + survival path.
3. `tests/integration/test_worktree_teardown_preserves_runs.py` mocks `_invoke_harbor` rather than running real harbor — correct scoping. The mechanism under test is the path-resolution + mkdir behavior on the host FS, not harbor's container-internal layout. The actual goal1-resume regression was on the host FS.
4. AC-1 unit test `test_default_not_under_cwd` could additionally assert `cwd != resolved` (not just absence-of-parent-relationship), but `Path.cwd() not in resolved.parents` already covers the load-bearing assertion when combined with `test_default_is_absolute`. Adequate.
5. The `Optional[Path]` import in `cli/run.py` is already present from prior code (`max_budget_usd_running`); no new typing import needed.

### Strengths

- True TDD ordering: RED (`e249efd`) → GREEN (`ddb1388`) → CLI wire (`30076a0`) → driver lock (`f2dbd40`) → worktree smoke (`a73b323`) → docs (`0636ca5`). Six clean commits, riskiest contract first.
- Resolver has zero side effects (no `mkdir`); callers do the dir creation after the canary check, matching the existing `runs_dir_canary.py` contract.
- AC-4 smoke uses a real `git worktree add` + `git worktree remove --force` against the actual repo — not a stub or simulation. This is the only test that could have caught the original goal1-resume regression.
- Help text on `--runs-dir` explicitly says the default "lives OUTSIDE any git worktree so `git worktree remove --force` cannot destroy experiment outputs" — operator-facing documentation that ties the design decision to the failure mode.
- DAB plugin README change is the right scope: a one-paragraph reference that points back to the top-level README; no duplication.

---

## Gate decision

**APPROVE** → `done`.

All four ACs proven against the worktree state with the exact `Verified by:` clause for each. 21/21 targeted bundle PASS. Full-suite regression: 548 PASS, 5 SKIPPED, 4 DESELECTED (`@pytest.mark.integration`), 2 FAILED (both pre-existing on `main`, both unrelated to this entity, both reproduced on `main` HEAD `08168b2`). No blocking findings in code review.

The entity unblocks the goal1 re-run: `git worktree remove --force` after a future goal1 ship can no longer destroy `runs/<experiment>/` per-cell artifacts. Operators who want the old behavior can still pass `--runs-dir _runs/` explicitly (verified by `test_explicit_runs_dir_wins_over_env`).
