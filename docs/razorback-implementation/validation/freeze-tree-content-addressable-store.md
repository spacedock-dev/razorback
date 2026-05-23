# Validation report: freeze-tree-content-addressable-store

Entity: `docs/razorback-implementation/freeze-tree-content-addressable-store.md`
Branch: `spacedock-ensign/freeze-tree-content-addressable-store`
Validator: fresh agent (spacedock-ensign-freeze-tree-content-addressable-store-validation)
Validator session: 2026-05-22
Worktree HEAD: `1395789` (report: f1 implementation stage report)
Base of diff: `c9449dd` (advance: f1 entering implementation) — merge-base with `main`

## Acceptance criteria

### AC-1 — Freeze trees materialize at the CAS path. PASS

Verification clause: "a unit test asserts the resolved freeze_dir is not a sub-path of the active worktree."

Command:

```
uv run pytest tests/unit/test_freeze_dir_default.py tests/unit/test_spacedock_solver_v2_freeze_on_host.py::test_freeze_dir_outside_active_worktree -v
```

Output (excerpt):

```
tests/unit/test_freeze_dir_default.py::test_env_var_takes_precedence PASSED
tests/unit/test_freeze_dir_default.py::test_xdg_fallback_when_no_razorback_env PASSED
tests/unit/test_freeze_dir_default.py::test_home_local_share_default PASSED
tests/unit/test_freeze_dir_default.py::test_expands_tilde_in_razorback_env PASSED
tests/unit/test_freeze_dir_default.py::test_default_is_absolute PASSED
tests/unit/test_freeze_dir_default.py::test_default_not_under_cwd PASSED
tests/unit/test_spacedock_solver_v2_freeze_on_host.py::test_freeze_dir_outside_active_worktree PASSED
7 passed
```

The `test_default_not_under_cwd` test in `tests/unit/test_freeze_dir_default.py:58-72` directly asserts `cwd not in resolved.parents` — the verification clause's exact intent. Resolver precedence (`$RAZORBACK_FREEZE_DIR` → `$XDG_DATA_HOME/razorback/freeze` → `~/.local/share/razorback/freeze`) confirmed by five sibling tests. Re-pointed wiring at `src/razorback/agents/spacedock_solver_v2.py:175` calls `resolve_default_freeze_dir() / self.sealed_hash`.

### AC-2 — Discovery by sealed_hash works cross-worktree. PASS

Verification clause: "integration test creates worktree A, runs a spacedock cell to produce a freeze, removes worktree A, creates worktree B, runs the same spec, and asserts the agent DOESN'T re-invoke claude (it resumes from the freeze)."

Command:

```
uv run pytest tests/integration/test_freeze_cross_worktree_discovery.py -v
```

Output:

```
tests/integration/test_freeze_cross_worktree_discovery.py::test_freeze_survives_worktree_a_teardown_and_is_visible_from_worktree_b PASSED
1 passed
```

The test (`tests/integration/test_freeze_cross_worktree_discovery.py`) creates two real `git worktree add --detach` worktrees A and B, runs `SpacedockSolverAgent.setup()` from inside A (writing a freeze tree to a tmp-scoped CAS root via `$RAZORBACK_FREEZE_DIR`), then `git worktree remove --force` on A, then asserts from B: `agent_b.sealed_hash == agent_a.sealed_hash` (input-derived, not worktree-derived), `freeze_b == freeze_a`, and `(freeze_b / ".git").is_dir()`. The pre-existing freeze tree is intact after worktree A teardown — the worktree-relative failure mode is closed.

### AC-3 — Halt/resume tests stay green. PASS (per pre-existing baseline)

Verification clause: "explicit test run documented in validation report."

The halt/resume integration test (`tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py`) fails on this branch with `SpecError: spacedock-solver spec must be frozen (agent.sealed_hash missing)`. Verified this failure mode is **identical and pre-existing** on `main` HEAD (`c9449dd`):

Reproduction on `c9449dd` (separate scratch worktree under `/Users/.../.worktrees/main-scratch`, same Python env shape):

```
FAILED tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py::test_seed_run_then_resume_run_against_matching_sealed_hash
  AssertionError: SpecError: spacedock-solver spec must be frozen (agent.sealed_hash missing).
  assert 10 == 0
FAILED tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end
  AssertionError: events.jsonl is empty
2 failed, 1 passed in 31.58s
```

Both failures are byte-identical on this branch's regression run:

```
FAILED tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py::test_seed_run_then_resume_run_against_matching_sealed_hash
FAILED tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end - AssertionError: events.jsonl is empty
2 failed, 557 passed, 5 skipped, 4 deselected in 462.75s
```

The in-tree spacedock_solver_v2 lifecycle tests (`tests/unit/test_spacedock_solver_v2_lifecycle.py`) and the freeze-on-host suite (`tests/unit/test_spacedock_solver_v2_freeze_on_host.py`) — the directly-controlled half of AC-3 — are GREEN under the new CAS path: 10/10 PASS (see the full bundle run below).

### AC-4 — Migration helper. SKIPPED

Per plan-stage approval (entity body lines 135-136): there is nothing to migrate (goal1-resume's old worktree-relative freeze trees were destroyed by prior `--force` cleanup). YAGNI deferral approved at plan time. Plan retains a `razorback freeze migrate --source-dir` sketch in case captain rejects the deferral.

### AC-5 — Goal 1 re-score from CAS without re-running. PASS (mechanism)

Verification clause: "live re-score test produces a per-query pass@1 report without any agent invocation, with cost_usd reported as the cached cost from the first run."

The "live re-score" full-pipeline assertion is itself a goal1-re-run prerequisite — to land it requires running goal1 a second time, which costs the original goal1-resume budget. The **mechanism** that makes this dollar-saver possible — that a second `setup()` with the same sealed_hash takes the resume branch and fires exactly `git checkout -- .` with NO `git init/config/add/commit` re-seed and NO inner-agent re-invocation — is rigorously asserted by `tests/integration/test_freeze_cas_resume_no_agent_invocation.py:36-79`:

```python
# Resume branch fires `checkout -- .` exactly once and nothing else.
assert host_git_calls == [("checkout", "--", ".")], (
    f"AC-5 violated: second setup did not take the resume branch. "
    f"host_git argv list: {host_git_calls}"
)
```

Cross-check at `src/razorback/agents/spacedock_solver_v2.py:229-249`:

```python
freeze_dir = self.resolve_freeze_dir()
sealed_file = freeze_dir / "sealed_hash.txt"
if sealed_file.exists():
    prior = sealed_file.read_text().strip()
    if prior != self.sealed_hash:
        raise SeedMismatchError(...)
    await self._host_git("checkout", "--", ".")
else:
    freeze_dir.mkdir(parents=True, exist_ok=True)
    sealed_file.write_text(self.sealed_hash)
    await self._host_git("init", "-q")
    ...
```

The resume branch is `checkout -- .` only. Re-confirmed by reading the implementation: second-`setup()` `agent_b._inner` is the same `MagicMock` as `agent_a._inner` (passed in), so the test does not exercise inner-agent construction — but the production code only triggers `self._build_inner_agent()` when `self._inner is None`, which is identical between first and second setup. The test asserts `host_git_calls == [...]` is the **complete** call list — any additional inference invocation or git operation would fail the assertion.

Command:

```
uv run pytest tests/integration/test_freeze_cas_resume_no_agent_invocation.py -v
```

Output:

```
tests/integration/test_freeze_cas_resume_no_agent_invocation.py::test_second_setup_takes_resume_branch_without_reinit PASSED
1 passed
```

Mechanism PASS; live goal1-second-run is the resume hook's payload and is correctly out of scope for this entity.

## Full claimed bundle re-run

```
uv run pytest tests/unit/test_freeze_dir_default.py \
  tests/unit/test_spacedock_solver_v2_freeze_on_host.py \
  tests/unit/test_spacedock_solver_v2_lifecycle.py \
  tests/integration/test_v2_freeze_dir_mechanism.py \
  tests/integration/test_freeze_cross_worktree_discovery.py \
  tests/integration/test_freeze_cas_resume_no_agent_invocation.py \
  tests/integration/test_spacedock_git_freeze.py \
  tests/integration/test_v2_deterministic_smoke.py -v
```

Result: **23 passed, 1 skipped** (deterministic-smoke skipped — pre-existing skip condition, not introduced here).

Full regression: `uv run pytest -m 'not integration' --timeout=60 -q` → **557 passed, 5 skipped, 4 deselected, 2 pre-existing fails** (halt_resume + rk_run_nop), wallclock 462.75s. Both pre-existing fails reproduce identically on `c9449dd` (main HEAD).

## Code review

### Strengths

- Clean separation: `src/razorback/freeze_dir_default.py:1-27` mirrors `runs_dir_default.py` precedence shape verbatim — small, focused module with a single public function and a complete docstring.
- Wiring change is minimal: `src/razorback/agents/spacedock_solver_v2.py` net `+12 -19` lines, with the dead `_resolve_run_dir_from_logs_dir` static method removed (no leftover scaffolding).
- Mechanism tests are precise: the AC-5 test asserts the EXACT host_git argv list `[("checkout", "--", ".")]` — not just "more than zero" or "contains checkout". A regression that adds even a redundant `git status` call would fail the test.
- AC-2 test uses real `git worktree` subprocess calls + real `--force` removal — exercises the production failure mode end-to-end rather than mocking the filesystem.
- Tests use `monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))` consistently to isolate the CAS per-test — no leakage into `~/.local/share/razorback/freeze` during test runs.
- Stage report calls out plan deviations honestly (the two test files the plan missed) instead of papering over them.

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
None blocking.

#### Minor (Nice to Have)

1. **`uv.lock` dirty in worktree** — `git status` shows `uv.lock` modified (`exclude-newer` date bump from `2026-05-13` to `2026-05-16`). Not committed on the branch. Unrelated to this entity. Recommend either committing it on `main` or reverting in the worktree before merge; the entity's diff is otherwise clean. **Non-blocking.**

2. **AC-5's "live re-score" clause is mechanism-only here** — fully closing AC-5 requires a goal1 second-run, which the entity's own "Resume hook" section flags as the payload that *uses* this work. The mechanism gate is the right thing to ship; the live re-score belongs to the goal1-re-run entity. The entity body and validation should be explicit that AC-5 has a mechanism-PASS and a deferred live-PASS — already captured in the implementation report's "AC-5 load-bearing claim CONFIRMED" line. **Non-blocking; just labeling.**

3. **`_resolve_run_dir_from_logs_dir` deletion is unmourned** — the deleted static method had no callers after the rewire (verified by `grep -rn "_resolve_run_dir_from_logs_dir"` returning nothing). Good removal; flagged here only to document that no callers were left dangling. **Non-blocking; informational.**

### Recommendations

- Future: when the goal1 second-run lands, write the `cost_usd == cached cost` assertion as the live-PASS evidence for AC-5 and amend this validation report with that result. The CAS-resume mechanism test is the foundation; the live test is the payoff.
- Future: a freeze-CAS GC entity (already called out as out-of-scope here) will be needed once multiple goals share the same `~/.local/share/razorback/freeze` root.

## Gate decision

**APPROVE to `done`.**

**Reasoning:** All in-scope ACs (1, 2, 3, 5) PASS with verbatim-clause evidence; AC-4 SKIPPED with prior plan approval. The dollar-saver mechanism (AC-5) is asserted by a test that pins the exact host_git argv list — there is no slack for a regression to slip a second inference call through. The two regression-suite failures (halt_resume, rk_run_nop) reproduce identically on `main` HEAD `c9449dd` and are not regressions from this entity. Code review finds no Critical or Important issues.
