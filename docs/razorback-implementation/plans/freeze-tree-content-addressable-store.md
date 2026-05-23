# Freeze Tree Content-Addressable Store — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/freeze-tree-content-addressable-store.md`

**Goal:** Move `spacedock_solver_v2`'s sealed-hash-keyed freeze trees out of the per-run-dir layout and into a process-/user-data CAS so they survive worktree teardown and any worktree can discover any prior freeze by sealed_hash.

**Architecture:** Introduce one path-resolution helper (`razorback.freeze_dir_default.resolve_default_freeze_dir`) that mirrors x9's `runs_dir_default` shape exactly — precedence `$RAZORBACK_FREEZE_DIR` → `$XDG_DATA_HOME/razorback/freeze` → `~/.local/share/razorback/freeze`. Re-point `SpacedockSolverAgent.resolve_freeze_dir` from `<run-dir>/_razorback/freeze/<sealed_hash>/` to `<cas-root>/<sealed_hash>/`. The agent still owns the sealed_hash key derivation; only the parent directory changes. Cross-worktree discovery (AC-2) and re-score from CAS (AC-5) fall out of the path change automatically — two agents with the same sealed_hash resolve to the SAME directory regardless of which worktree they were invoked from.

**Tech Stack:** Python 3.12, pytest. No new dependencies. No CLI surface change for AC-1..AC-3; AC-4's migration helper adds one `razorback freeze migrate` Typer subcommand IF we keep AC-4 in scope (see "AC-4 re-baseline" below).

---

## Baseline assumptions (re-baseline since entity body was written)

The entity body's "Depends on" line says AC-5 requires `razorback-runs-outside-worktree` AND `commit-small-artifacts-by-default`. Re-baseline as of 2026-05-22:

- `razorback-runs-outside-worktree` (x9) — **shipped** (status=done, archived).
  `src/razorback/runs_dir_default.py` is the reference pattern this entity copies.
- `commit-small-artifacts-by-default` (jp) — **SUPERSEDED, not shipping** (archived 2026-05-22T23:14:13Z).
  The captain decided experiment artifacts are not meant to be committed to source. The failure mode it targeted is closed structurally by x9 + this entity + `fo-no-force-worktree-remove` (z5). See `docs/razorback-implementation/_archive/commit-small-artifacts-by-default.md` "Supersession (2026-05-22)" section.

**Therefore AC-5's clause "After this entity + razorback-runs-outside-worktree + commit-small-artifacts-by-default ship" becomes "After this entity + x9 ship (already done)".** The dependency on jp is removed because re-scoring from a freeze tree reads from the CAS, not from in-repo committed artifacts. The plan does NOT block on jp.

## AC-4 re-baseline (migration helper)

The entity body's AC-4 prescribes a `razorback freeze migrate` CLI that walks old worktree-relative freeze paths and moves them into the CAS. The captain's dispatch notes:

> AC-4 migration helper: goal1-resume's old worktree-relative freeze trees were destroyed by prior FO --force cleanup, so there is nothing to migrate today. Recommend either deferring AC-4 (mark out-of-scope) OR scoping it to a simple `--source-dir`-driven helper for future use. Name the recommendation.

**Recommendation: defer AC-4 — mark as out of scope for this entity, file a follow-up if a need arises.**

Rationale:
1. The original target data (the goal1-resume freeze trees) is gone; the helper has nothing to migrate today.
2. Building a migration tool for hypothetical future freeze trees at hypothetical legacy paths is YAGNI. The shape of those paths is well-known (`<run-dir>/_razorback/freeze/<sealed_hash>/`), and a future entity can ship a one-shot `mv` script in 30 minutes when a real migration target appears.
3. The other four ACs (AC-1..AC-3 + AC-5) are the load-bearing ones. AC-5 is the proof of the entity's whole premise. Spending implementation budget on a dead-code CLI subcommand robs the ACs that actually matter.

The plan below treats AC-4 as **SKIPPED (deferred)** in the stage report; the entity body is not modified by this plan stage (frontmatter and AC list belong to the captain).

If the captain rejects this recommendation, the smallest scoped helper is a `razorback freeze migrate --source-dir <PATH>` Typer subcommand that:
- Walks `<source-dir>/**/_razorback/freeze/<hash>/` patterns.
- For each match, computes the CAS destination from the directory name (the `<hash>` is the sealed_hash).
- Refuses with rc=1 if `<cas-dest>` already exists with a different `sealed_hash.txt`.
- Otherwise `shutil.move`s the tree.
- Is idempotent: re-running on an empty source-dir is a no-op rc=0.

Implementation effort estimate for that path: one ~30-line CLI function + one unit test against a tmp_path fixture freeze tree. A `Task 4` skeleton is sketched at the bottom of this plan for that fallback.

---

## AC ↔ Task map

| AC | Description | Tasks |
|---|---|---|
| AC-1 | `resolve_freeze_dir()` returns `$XDG_DATA_HOME/razorback/freeze/<sealed_hash>/` (default `~/.local/share/razorback/freeze/`) or `$RAZORBACK_FREEZE_DIR/<sealed_hash>/` when set; NOT a sub-path of the active worktree | T0 (RED resolver), T1 (GREEN resolver), T2 (wire agent) |
| AC-2 | Cross-worktree discovery by sealed_hash — freeze tree from worktree A is reachable from worktree B (or after A is removed) | T3 (cross-worktree integration smoke) |
| AC-3 | `tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py` + in-tree spacedock_solver_v2 lifecycle tests stay GREEN | T2 (update existing unit tests to read the CAS path), T6 (full regression run captured in stage report) |
| AC-4 | Migration helper (`razorback freeze migrate`) | **SKIPPED — deferred** per re-baseline above (Task 4 sketch retained for breakglass) |
| AC-5 | Goal 1 re-score from CAS without re-running the agent — second invocation against the same sealed_hash spec resumes from the freeze tree and writes only verifier+score outputs | T5 (CAS-resume mechanism integration test) |

**Riskiest contract first:** T0+T1 (resolver shape) → T2 (agent re-wiring, which breaks existing unit tests that asserted run-dir-relative freeze paths) → T3 (cross-worktree discovery — the entity's headline mechanism) → T5 (end-to-end no-agent-invocation re-score, AC-5 mechanism gate). T2 is the load-bearing internal-contract change; if it lands cleanly, AC-2/AC-5 fall out automatically.

---

## Surface map — what changes

| File | Change |
|---|---|
| `src/razorback/freeze_dir_default.py` *(new)* | Helper module: `resolve_default_freeze_dir() -> Path`. Reads `$RAZORBACK_FREEZE_DIR`, then `$XDG_DATA_HOME`, then defaults to `~/.local/share/razorback/freeze`. Always returns an absolute, expanded path. No side effects (no `mkdir`). Copy of `runs_dir_default.py` with `RUNS` → `FREEZE`, `runs` → `freeze`. |
| `tests/unit/test_freeze_dir_default.py` *(new)* | T0 RED, T1 GREEN. Six tests mirroring `test_runs_dir_default.py`: env-var precedence, XDG fallback, home fallback, tilde expansion, absoluteness, not-under-cwd. |
| `src/razorback/agents/spacedock_solver_v2.py:162-182` | `resolve_freeze_dir` no longer walks back from `logs_dir`. It returns `resolve_default_freeze_dir() / self.sealed_hash`. The `_resolve_run_dir_from_logs_dir` static method becomes dead code and is removed. The `logs_dir` parameter on `__init__` is still honored as-is for harbor's per-trial logs root — only freeze resolution changes. |
| `tests/unit/test_spacedock_solver_v2_freeze_on_host.py` | Update `_kw` and assertions: `logs_dir` no longer drives the freeze path. The four existing tests still assert "git ran on host" / "real .git dir / sealed_hash.txt" / "resume runs git checkout on host"; only the *location* assertion changes. Add a new test `test_freeze_dir_outside_active_worktree` that asserts the resolved freeze_dir is NOT under any directory containing a `.git` (the contract from AC-1). |
| `tests/integration/test_v2_freeze_dir_mechanism.py` | Update the two existing tests: `test_sealed_hash_txt_lands_at_keyed_external_path` and `test_harbor_jobs_resume_round_trip_with_new_trial_name`. The path assertion `<run-dir>/_razorback/freeze/<sealed_hash>/` becomes `<cas-root>/<sealed_hash>/`. The "NOT inside trials/" assertion stays trivially true (CAS root is outside `<run-dir>` entirely). |
| `tests/integration/test_freeze_cross_worktree_discovery.py` *(new)* | T3 mechanism gate for AC-2. Two throwaway worktrees + a shared `$RAZORBACK_FREEZE_DIR`. Agent A writes; remove worktree A; Agent B with same sealed_hash resolves to the SAME freeze dir and reads sealed_hash.txt. |
| `tests/integration/test_freeze_cas_resume_no_agent_invocation.py` *(new)* | T5 mechanism gate for AC-5. Two `rk run` invocations against the same spec with `_invoke_harbor` patched to record whether the agent was called. First invocation creates the freeze tree at the CAS path; second invocation finds it via sealed_hash and the resume branch in `setup()` (`sealed_file.exists() == True`) runs `git checkout -- .` instead of `git init`. We assert no NEW agent process is spawned for the freeze-init path. |

## Surface map — what stays

- `compute_sealed_hash` and the six-input contract — unchanged.
- `SpacedockSolverAgent.__init__` parameter list — unchanged. `logs_dir` is still the harbor per-trial logs dir; the *freeze tree* just no longer lives under it.
- `_host_git`, `_commit_stage`, `setup`, `_refuse_on_resume_mismatch` — internal logic unchanged. Only `resolve_freeze_dir` changes.
- `examples/drivers/dab-paper-matrix.sh` — unchanged. Driver passes `--runs-dir`; it does not touch the freeze layout.
- `cli/run.py` — unchanged for AC-1..AC-3+AC-5. (If AC-4 is later un-deferred, this is the file that gets the new Typer subcommand.)
- `_legacy/run.py:123` — `agent_freeze` reference is the v1 agent's container-side scratch dir, NOT the v2 sealed-hash freeze CAS. Different code path. Untouched.
- `src/razorback/spec/freeze.py` — spec-level freeze (canonical YAML pin, `sealed_hash` stamp). Distinct from the freeze TREE on disk. Untouched.
- `.gitignore` — `runs/`, `_runs/`, `.runs/` patterns are unrelated to the CAS path. The default CAS lives under `~/.local/share/razorback/freeze/`, never in the worktree. No change.

---

## Tasks

### Task 0 — RED: failing tests for the freeze-dir resolver

**Files:**
- Create: `tests/unit/test_freeze_dir_default.py`

Riskiest-contract-first: if the precedence ordering for `$RAZORBACK_FREEZE_DIR` → `$XDG_DATA_HOME` → `~/.local/share` is wrong, every downstream wiring is wrong.

- [ ] **Step 0.1: Write the failing test file**

```python
# ABOUTME: AC-1 unit tests for the default freeze-dir resolver (CAS root).
# ABOUTME: Asserts env-var precedence and that the default is never under cwd.

from pathlib import Path

import pytest


def test_env_var_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "explicit"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert resolve_default_freeze_dir() == (tmp_path / "explicit").resolve()


def test_xdg_fallback_when_no_razorback_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.delenv("RAZORBACK_FREEZE_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    expected = (tmp_path / "xdg" / "razorback" / "freeze").resolve()
    assert resolve_default_freeze_dir() == expected


def test_home_local_share_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.delenv("RAZORBACK_FREEZE_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    expected = (
        tmp_path / "home" / ".local" / "share" / "razorback" / "freeze"
    ).resolve()
    assert resolve_default_freeze_dir() == expected


def test_expands_tilde_in_razorback_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", "~/custom-freeze")
    expected = (tmp_path / "home" / "custom-freeze").resolve()
    assert resolve_default_freeze_dir() == expected


def test_default_is_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.delenv("RAZORBACK_FREEZE_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert resolve_default_freeze_dir().is_absolute()


def test_default_not_under_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-1 verification clause: resolved default is not a sub-path of cwd."""
    from razorback.freeze_dir_default import resolve_default_freeze_dir
    monkeypatch.delenv("RAZORBACK_FREEZE_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "fake_cwd_worktree").mkdir()
    monkeypatch.chdir(tmp_path / "fake_cwd_worktree")
    resolved = resolve_default_freeze_dir()
    cwd = Path.cwd().resolve()
    assert cwd not in resolved.parents, (
        f"default freeze_dir {resolved} is under cwd {cwd}; AC-1 violated"
    )
```

- [ ] **Step 0.2: Run the tests, verify they all fail**

Run: `uv run pytest tests/unit/test_freeze_dir_default.py -v`
Expected: 6 FAILs with `ModuleNotFoundError: No module named 'razorback.freeze_dir_default'`

- [ ] **Step 0.3: Commit RED**

```bash
git add tests/unit/test_freeze_dir_default.py
git commit -m "test: RED — default freeze-dir resolver (AC-1)"
```

---

### Task 1 — GREEN: implement the resolver

**Files:**
- Create: `src/razorback/freeze_dir_default.py`

- [ ] **Step 1.1: Write the minimal resolver**

```python
# ABOUTME: AC-1 resolver for the default freeze-tree CAS root.
# ABOUTME: Precedence: $RAZORBACK_FREEZE_DIR > $XDG_DATA_HOME/razorback/freeze > ~/.local/share/razorback/freeze.

import os
from pathlib import Path


def resolve_default_freeze_dir() -> Path:
    """Return the default freeze-tree CAS root as an absolute, expanded path.

    Precedence:
    1. `$RAZORBACK_FREEZE_DIR` if set and non-empty.
    2. `$XDG_DATA_HOME/razorback/freeze` if `$XDG_DATA_HOME` is set and non-empty.
    3. `~/.local/share/razorback/freeze`.

    The returned path is NOT created on disk; callers `mkdir(parents=True,
    exist_ok=True)` when they materialize a freeze tree at
    `<root>/<sealed_hash>/`.
    """
    explicit = os.environ.get("RAZORBACK_FREEZE_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return (Path(xdg).expanduser() / "razorback" / "freeze").resolve()
    return (Path.home() / ".local" / "share" / "razorback" / "freeze").resolve()
```

- [ ] **Step 1.2: Run the tests, verify GREEN**

Run: `uv run pytest tests/unit/test_freeze_dir_default.py -v`
Expected: 6 PASS

- [ ] **Step 1.3: Commit GREEN**

```bash
git add src/razorback/freeze_dir_default.py
git commit -m "feat: GREEN — default freeze-dir CAS root resolver (AC-1)"
```

---

### Task 2 — Re-wire `SpacedockSolverAgent.resolve_freeze_dir` to the CAS (AC-1, AC-3)

**Files:**
- Modify: `src/razorback/agents/spacedock_solver_v2.py` (`resolve_freeze_dir` + drop `_resolve_run_dir_from_logs_dir`)
- Modify: `tests/unit/test_spacedock_solver_v2_freeze_on_host.py` (update `_kw` fixture; update assertions)
- Modify: `tests/integration/test_v2_freeze_dir_mechanism.py` (path assertions point at CAS root)

**The riskiest internal-contract change.** If this lands wrong, AC-2 and AC-5 cannot pass and the lifecycle tests in AC-3 will go red.

- [ ] **Step 2.1: Edit `src/razorback/agents/spacedock_solver_v2.py`**

Add the import near the top, with the other razorback imports:

```python
from razorback.freeze_dir_default import resolve_default_freeze_dir
```

Replace lines 162-182 (`resolve_freeze_dir` + `_resolve_run_dir_from_logs_dir`) with:

```python
    def resolve_freeze_dir(self) -> Path:
        """Per spec §4.3.4 + AC-1: sealed_hash-keyed external freeze in a CAS.

        The freeze tree lives at `<cas-root>/<sealed_hash>/` where `<cas-root>`
        resolves via `$RAZORBACK_FREEZE_DIR` → `$XDG_DATA_HOME/razorback/freeze`
        → `~/.local/share/razorback/freeze`. This is independent of any
        worktree, so:
        - `git worktree remove --force` cannot destroy freeze trees.
        - Any worktree can discover any prior freeze by sealed_hash (AC-2).
        - Re-running the same spec resumes from the existing freeze without
          re-invoking the agent (AC-5).
        """
        return resolve_default_freeze_dir() / self.sealed_hash
```

Delete the entire `_resolve_run_dir_from_logs_dir` static method (lines 173-182). It is dead code after this change.

- [ ] **Step 2.2: Run the affected unit tests, expect failures**

Run: `uv run pytest tests/unit/test_spacedock_solver_v2_freeze_on_host.py tests/integration/test_v2_freeze_dir_mechanism.py -v`
Expected: Most tests will now resolve a freeze_dir under `~/.local/share/razorback/freeze/` (or wherever the test environment puts it). The `assert (expected / "sealed_hash.txt").exists()` etc still pass IF the assertion stops trying to compute the expected path from `tmp_path / "run" / "_razorback" / "freeze"`. Specifically `test_sealed_hash_txt_lands_at_keyed_external_path` will FAIL on its `expected = tmp_path / "run" / "_razorback" / "freeze" / agent.sealed_hash` line.

- [ ] **Step 2.3: Update `tests/unit/test_spacedock_solver_v2_freeze_on_host.py`**

At the top of `_kw`, add a `monkeypatch`-based redirect — but since `_kw` is plain (not a fixture), the simpler change is: have each test set `monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))` BEFORE constructing the agent. Update each of the 4 existing tests to accept `monkeypatch` and call:

```python
monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
```

as the first line of the test body (before `SpacedockSolverAgent(...)` is constructed).

No assertion changes are needed in these 4 tests — they call `agent.resolve_freeze_dir()` and use whatever it returns. They never hardcoded `tmp_path / "run" / "_razorback" / "freeze"`.

Add ONE new test at the end of the file:

```python
@pytest.mark.asyncio
async def test_freeze_dir_outside_active_worktree(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """AC-1: resolved freeze_dir is NOT under any directory containing .git."""
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    freeze_dir = agent.resolve_freeze_dir()
    # Walk up from freeze_dir and confirm no .git ancestor inside tmp_path.
    for parent in [freeze_dir, *freeze_dir.parents]:
        if not str(parent).startswith(str(tmp_path)):
            break
        assert not (parent / ".git").exists(), (
            f"freeze_dir {freeze_dir} is inside a git worktree at {parent}"
        )
```

- [ ] **Step 2.4: Update `tests/integration/test_v2_freeze_dir_mechanism.py`**

For `test_sealed_hash_txt_lands_at_keyed_external_path`:

Replace:
```python
expected = tmp_path / "run" / "_razorback" / "freeze" / agent.sealed_hash
```
with (after adding `monkeypatch` parameter):
```python
monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))
# … construct agent AFTER the env var is set …
expected = tmp_path / "freeze-cas" / agent.sealed_hash
```

Replace the "NOT inside trials/" final block with a stronger AC-2-precursor assertion:
```python
# AC-1 + AC-2 precursor: CAS root is outside the run-dir entirely.
assert "trials" not in str(expected)
assert (tmp_path / "run") not in expected.parents
```

For `test_harbor_jobs_resume_round_trip_with_new_trial_name`:

Same `monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))` at the top. The existing assertions (`agent_b.sealed_hash == agent_a.sealed_hash`, `agent_b.resolve_freeze_dir() == freeze_dir`, etc.) already test the CAS contract — same sealed_hash → same path. They will pass unchanged once the path is reachable.

- [ ] **Step 2.5: Re-run the affected unit tests, expect GREEN**

Run: `uv run pytest tests/unit/test_spacedock_solver_v2_freeze_on_host.py tests/integration/test_v2_freeze_dir_mechanism.py tests/unit/test_freeze_dir_default.py -v`
Expected: ALL PASS.

- [ ] **Step 2.6: Commit**

```bash
git add src/razorback/agents/spacedock_solver_v2.py \
        tests/unit/test_spacedock_solver_v2_freeze_on_host.py \
        tests/integration/test_v2_freeze_dir_mechanism.py
git commit -m "feat: spacedock_solver_v2 freeze trees live in CAS root (AC-1, AC-3)"
```

---

### Task 3 — Cross-worktree discovery integration test (AC-2)

**Files:**
- Create: `tests/integration/test_freeze_cross_worktree_discovery.py`

This is the entity's headline mechanism gate. The smallest end-to-end exercise that proves "freeze tree from worktree A is reachable from worktree B."

- [ ] **Step 3.1: Write the cross-worktree test**

```python
# ABOUTME: AC-2 mechanism gate — freeze tree written from worktree A is
# ABOUTME: discoverable from worktree B sharing the same $RAZORBACK_FREEZE_DIR.

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgent

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_worktree(repo_root: Path, base: Path, name: str) -> Path:
    wt = base / name
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "add",
         "--detach", str(wt), "HEAD"],
        check=True, capture_output=True,
    )
    return wt


def _force_remove(repo_root: Path, wt: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(wt)],
        check=True, capture_output=True,
    )


def _common_kwargs(workflow: Path) -> dict:
    return dict(
        runtime="claude",
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        solver_workflow=workflow,
        solver_workflow_content_hash="sha256:" + "a" * 64,
        prompt_content_hashes={"readme": "sha256:" + "b" * 64},
        spacedock_skill_version="1.0.0",
        harbor_agent_kwargs={"max_turns": 200},
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )


def _make_logs_dir(worktree_root: Path, trial_name: str) -> Path:
    logs = worktree_root / "runs" / "exp" / "job" / "trials" / trial_name / "logs" / "agent"
    logs.mkdir(parents=True, exist_ok=True)
    (worktree_root / "runs" / "exp" / "job" / "spec.frozen.yaml").write_text(
        "placeholder"
    )
    return logs


@pytest.mark.asyncio
async def test_freeze_survives_worktree_a_teardown_and_is_visible_from_worktree_b(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cas_root = tmp_path / "freeze-cas"
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(cas_root))

    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    wt_a = _make_worktree(REPO_ROOT, tmp_path, "wt-a")
    wt_b = _make_worktree(REPO_ROOT, tmp_path, "wt-b")
    try:
        # Construct + setup agent from inside worktree A's surface.
        logs_a = _make_logs_dir(wt_a, "task-0001__abc1234")
        agent_a = SpacedockSolverAgent(
            logs_dir=logs_a, **_common_kwargs(workflow)
        )
        fake_env = MagicMock()
        fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
        agent_a._inner = MagicMock()
        agent_a._inner.setup = AsyncMock()
        await agent_a.setup(fake_env)

        freeze_a = agent_a.resolve_freeze_dir()
        assert freeze_a.is_relative_to(cas_root), (
            f"freeze_a {freeze_a} is not under CAS root {cas_root}"
        )
        assert (freeze_a / "sealed_hash.txt").read_text().strip() == agent_a.sealed_hash
    finally:
        _force_remove(REPO_ROOT, wt_a)

    # Worktree A is gone. Build agent B from inside worktree B with the
    # SAME inputs (same sealed_hash) and confirm discovery.
    try:
        logs_b = _make_logs_dir(wt_b, "task-0001__deadbeef")
        agent_b = SpacedockSolverAgent(
            logs_dir=logs_b, **_common_kwargs(workflow)
        )
        assert agent_b.sealed_hash == agent_a.sealed_hash, (
            "sealed_hash must be input-derived, not worktree-derived"
        )
        freeze_b = agent_b.resolve_freeze_dir()
        assert freeze_b == freeze_a, (
            f"AC-2 violated: agent B resolved {freeze_b}, not the shared {freeze_a}"
        )
        # The pre-existing freeze tree is intact (worktree A teardown did not destroy it).
        assert (freeze_b / "sealed_hash.txt").exists()
        assert (freeze_b / ".git").is_dir()
    finally:
        _force_remove(REPO_ROOT, wt_b)
```

- [ ] **Step 3.2: Run the smoke**

Run: `uv run pytest tests/integration/test_freeze_cross_worktree_discovery.py -v`
Expected: PASS. If `git worktree add` fails because the test runs inside a worktree that already exists at `tmp_path`, switch the base directory to a temp dir outside the repo (the runs-outside-worktree T4 smoke handled this fine; tmp_path under `/private/var/folders` is fine on macOS and `/tmp/pytest-*` on Linux).

- [ ] **Step 3.3: Commit**

```bash
git add tests/integration/test_freeze_cross_worktree_discovery.py
git commit -m "test: freeze CAS survives worktree teardown + cross-worktree visible (AC-2)"
```

---

### Task 4 — AC-4 migration helper (**SKIPPED — DEFERRED**)

See the "AC-4 re-baseline" section above. **Do NOT implement this task.** Mark it SKIPPED in the stage report with the rationale "no migration target exists today; YAGNI deferred per captain's dispatch note".

Breakglass sketch (only execute if captain rejects the deferral recommendation):

- Create `src/razorback/cli/freeze.py` with a Typer subcommand `migrate(source_dir: Path, dry_run: bool = False)`.
- Walk `source_dir.rglob("_razorback/freeze/*/sealed_hash.txt")`.
- For each match, parse the sealed_hash from the file body; compute `dest = resolve_default_freeze_dir() / sealed_hash`.
- If `dest` exists with a matching `sealed_hash.txt`, skip (idempotent).
- If `dest` exists with a mismatched `sealed_hash.txt`, raise rc=1 (corruption).
- Else `shutil.move` the parent directory.
- Wire under `razorback.cli:app.add_typer(freeze_app, name="freeze")`.
- Unit test against a tmp_path fixture freeze tree at the old layout.

Estimated effort: 30 minutes if needed.

---

### Task 5 — CAS-resume mechanism gate (AC-5)

**Files:**
- Create: `tests/integration/test_freeze_cas_resume_no_agent_invocation.py`

The entity's whole-premise gate: prove that with a freeze tree in CAS, a second invocation of the same agent reads sealed_hash.txt from the SAME path and takes the resume branch (`git checkout -- .`) instead of re-init.

This test does NOT need to run a full `rk run` cycle; the contract under test is internal to `SpacedockSolverAgent.setup()`. The minimal exercise is two `agent.setup()` calls on freshly-constructed agents with the same sealed_hash, in a shared `$RAZORBACK_FREEZE_DIR`, asserting:
1. The first call writes sealed_hash.txt (init branch).
2. The second call does NOT re-init; it takes the resume branch.

We detect "resume branch taken" by counting host-git invocations. Init branch fires `init`, `config user.email`, `config user.name`, `config commit.gpgsign`, `add -A`, `commit ... seed` (6 calls). Resume branch fires `checkout -- .` (1 call). Different argv shapes — easy to assert.

- [ ] **Step 5.1: Write the AC-5 mechanism test**

```python
# ABOUTME: AC-5 mechanism gate — second agent invocation with the same
# ABOUTME: sealed_hash resumes from the CAS freeze tree without re-init.

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgent


def _kw(tmp_path: Path) -> dict:
    workflow = tmp_path / "solver"
    workflow.mkdir(exist_ok=True)
    (workflow / "README.md").write_text("## Stages\n- model\n")
    logs_dir = (
        tmp_path / "run" / "trials" / "task-0001__abc1234" / "logs" / "agent"
    )
    logs_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "run" / "spec.frozen.yaml").write_text("placeholder")
    return dict(
        logs_dir=logs_dir,
        runtime="claude",
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        solver_workflow=workflow,
        solver_workflow_content_hash="sha256:" + "a" * 64,
        prompt_content_hashes={"readme": "sha256:" + "b" * 64},
        spacedock_skill_version="1.0.0",
        harbor_agent_kwargs={"max_turns": 200},
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )


@pytest.mark.asyncio
async def test_second_setup_takes_resume_branch_without_reinit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAZORBACK_FREEZE_DIR", str(tmp_path / "freeze-cas"))

    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))

    # First setup: init branch — real git init on host so the .git exists.
    agent_a = SpacedockSolverAgent(**_kw(tmp_path))
    agent_a._inner = MagicMock()
    agent_a._inner.setup = AsyncMock()
    await agent_a.setup(fake_env)

    freeze_dir = agent_a.resolve_freeze_dir()
    assert (freeze_dir / "sealed_hash.txt").exists()
    assert (freeze_dir / ".git").is_dir()

    # Second setup with the SAME inputs — must take the resume branch.
    # We track host-git argv shapes by patching _host_git.
    agent_b = SpacedockSolverAgent(**_kw(tmp_path))
    agent_b._inner = MagicMock()
    agent_b._inner.setup = AsyncMock()
    assert agent_b.resolve_freeze_dir() == freeze_dir  # CAS hit.

    host_git_calls: list[tuple[str, ...]] = []
    original_host_git = agent_b._host_git

    async def recording_host_git(*args: str) -> None:
        host_git_calls.append(tuple(args))
        await original_host_git(*args)

    agent_b._host_git = recording_host_git  # type: ignore[assignment]
    await agent_b.setup(fake_env)

    # Resume branch fires `checkout -- .` exactly once and nothing else.
    assert host_git_calls == [("checkout", "--", ".")], (
        f"AC-5 violated: second setup did not take the resume branch. "
        f"host_git argv list: {host_git_calls}"
    )
    # And critically: no inner agent setup is skipped — the contract is that
    # the AGENT is still wired (so the freeze tree could be re-replayed) but
    # no re-init / re-seed git work happens. Inner setup was called once.
    assert agent_b._inner.setup.await_count == 1
```

- [ ] **Step 5.2: Run the AC-5 gate**

Run: `uv run pytest tests/integration/test_freeze_cas_resume_no_agent_invocation.py -v`
Expected: PASS. If the assertion on `host_git_calls` fails because the resume branch fires extra calls, STOP and re-read `spacedock_solver_v2.py:setup()` lines 229-256 — the resume branch is supposed to be `git checkout -- .` only. Adding fixes without understanding why will violate AC-5.

- [ ] **Step 5.3: Commit**

```bash
git add tests/integration/test_freeze_cas_resume_no_agent_invocation.py
git commit -m "test: second setup with same sealed_hash resumes from CAS (AC-5)"
```

---

### Task 6 — Full regression run + stage report capture (AC-3)

**Files:**
- No new files. Run existing tests and capture the result.

- [ ] **Step 6.1: Run the full halt/resume integration test**

Run: `uv run pytest tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py -v`
Expected: PASS or pre-existing FAIL (per the x9 validation report, this test had pre-existing failures on `main` unrelated to runs_dir; if it fails identically on this branch, it's not a regression).

- [ ] **Step 6.2: Run the spacedock-related test bundle**

Run:
```bash
uv run pytest \
  tests/unit/test_freeze_dir_default.py \
  tests/unit/test_spacedock_solver_v2_freeze_on_host.py \
  tests/integration/test_v2_freeze_dir_mechanism.py \
  tests/integration/test_freeze_cross_worktree_discovery.py \
  tests/integration/test_freeze_cas_resume_no_agent_invocation.py \
  tests/integration/test_spacedock_git_freeze.py \
  -v
```
Expected: ALL PASS for the new/updated tests; `test_spacedock_git_freeze.py` was already green; record any deviation.

- [ ] **Step 6.3: Run full-suite regression (excluding integration / docker-heavy)**

Run: `uv run pytest -m "not integration" --timeout=60 -q`
Expected: same baseline as x9's validation report (548 pass, 5 skipped, 4 deselected, 2 pre-existing fails). Any NEW failure must be investigated before reporting completion.

- [ ] **Step 6.4: No commit needed for Task 6** — it is the validation-stage prep.

---

## Sequencing

```
T0 (RED resolver) → T1 (GREEN resolver) → T2 (re-wire agent + update unit/integ tests)
  → T3 (cross-worktree mechanism) → T5 (CAS-resume mechanism) → T6 (regression capture)
```

T4 (AC-4) is **skipped — deferred**.

T0+T1 is riskiest-contract-first per the captain's foundational rule. T2 is the load-bearing internal change; if it lands cleanly, AC-2/AC-5 fall out automatically. T3 + T5 are the two mechanism-validation gates for the entity's premise — they prove cross-worktree discovery and re-score-without-re-running respectively. If either fails after T2, STOP and re-plan — do NOT pile fixes.

## Self-review

- **Spec coverage:** AC-1 (T0+T1+T2), AC-2 (T3), AC-3 (T2 updates existing tests, T6 captures full regression), AC-4 (SKIPPED — deferred with rationale), AC-5 (T5). Four of five ACs have a dedicated task; AC-4 is documented as skipped.
- **Placeholder scan:** no TBD / TODO / "fill in" strings; every test body and code change is fully written above.
- **Type consistency:** `resolve_default_freeze_dir() -> Path` mirrors `resolve_default_runs_dir() -> Path` exactly. The `SpacedockSolverAgent.resolve_freeze_dir() -> Path` signature is unchanged; only the implementation body is rewritten.
- **AC-2 mechanism risk:** cross-worktree discovery depends on (a) sealed_hash being input-derived (already true via `compute_sealed_hash`), and (b) the CAS path containing only the sealed_hash, not the run-dir. T3 asserts both. If T3 fails, the agent's __init__ is leaking worktree context into the freeze key — investigate `compute_sealed_hash` inputs.
- **AC-5 detection signal:** the test asserts `host_git_calls == [("checkout", "--", ".")]` — a strong contract check that uses the existing setup() branch shape verbatim. No assertion-on-mock-internals; this is real argv inspection.
- **No backwards-compat hacks:** the entity body's AC-2 line "or after worktree A is removed" is the EXPLICIT statement that the old `<run-dir>/_razorback/freeze/` layout must not be supported in parallel. Plan removes `_resolve_run_dir_from_logs_dir` outright rather than dual-path.

## Resume hook

After this plan ships:
- Goal 1 re-runs become free of agent-cost on the freeze-tree path. Re-running `goal1-resume` against a CAS-warm freeze tree skips the agent and only re-runs verifier + score (paper's `per_query_pass_at_1` metric is now reachable).
- The four ergonomics entities (`x9` shipped, this entity (`f1`), `commit-small-artifacts-by-default` (`jp`, SUPERSEDED), `fo-no-force-worktree-remove` (`z5`)) — three of four are closed structurally; the fourth (`z5`) is independent and orthogonal.
- Future entity opportunity: freeze tree GC / retention policy (already out-of-scope here per the entity body). Becomes load-bearing if the CAS grows past ~10 GB on the captain's machine.
