# Phase 3: SpacedockSolverAgent v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `SpacedockSolverAgent` v2 as a runtime-adapter class at `src/razorback/agents/spacedock_solver_v2.py`, routed via the discriminator `agent.kind: spacedock_solver_v2` (the canonical `spacedock_solver` continues to route to the v1 class until Phase 6 promotes v2). The class validates kwargs against a pydantic schema, computes `sealed_hash` from six sealed inputs, refuses on resume mismatch with `SeedMismatchError` (exit 20), constructs the inner harbor installed-agent (claude_code, codex, pi) via per-runtime adapter sub-modules, and reads / writes the freeze tree at the **sealed_hash-keyed external location** that `b5` (spec-mitigation-resume-conflict) made load-bearing: `<harbor-run-dir>/_razorback/freeze/<sealed_hash>/`.

**Architecture:** v2 keeps v1's three load-bearing surfaces verbatim (sealed-hash refusal before harbor I/O; co-mingled-auth refusal; per-stage `.git` commit pattern for halt-resume) and adapts three (runtime is now a `claude|codex|pi` enum, with per-runtime adapter sub-modules; freeze tree resolves to the sealed_hash-keyed external location rather than `logs_dir/agent_freeze/`; the sealed-hash payload expands per spec §4.3 + §8.4 to six inputs). The class is a runtime adapter, it owns kwarg validation, sealed_hash computation, the freeze-dir contract, the sealed-hash refusal, and the resume restore mechanic; the workflow's freeze mod owns per-stage commit + `phase_stats.json` writes (deferred per spec §5.2). Phase 3's halt-resume integration test uses hand-faked freeze writes that simulate what the mod will write, exactly the discipline AC-6 names.

**Tech stack:** Python 3.12 (uv-managed); pydantic 2.x for schema; pytest + pytest-asyncio for tests; harbor 0.6.6 (`BaseAgent`, `BaseInstalledAgent`, `ClaudeCode`, `Codex`, `Pi`, `EnvironmentPaths`, `AgentConfig`) as the integration surface.

**Source of truth:**
- v2 spec: `/Users/clkao/git/razorback/docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` §4 (lines 323-494), §7.1 (lines 740-771), §8.4 (lines 929-957).
- `b5` plan (load-bearing pre-condition): `/Users/clkao/git/razorback/docs/razorback-implementation/plans/spec-mitigation-resume-conflict.md`, specifically the "Contract between `SpacedockSolverAgent` and the external freeze tree" 5-point list (lines 56-66) and the "Location convention" tree (lines 26-39).
- v1 module to adapt from: `src/razorback/agents/spacedock_solver.py` (315 LoC; ADAPT-EXTRACT per inventory).
- Sealed-hash core: `src/razorback/agents/seal.py` (53 LoC; KEEP-EXTRACT with payload expansion).
- Module inventory: `/Users/clkao/git/razorback/docs/superpowers/plans/2026-05-19-razorback-inventory.md` (file:line ranges per module).
- Phase 1's translator: `/Users/clkao/git/razorback/docs/razorback-implementation/plans/phase1-rk-run-v2-wrapper.md` Task 5 (lines 325-688), emits `AgentConfig.import_path` keyed off `agent.kind`. Phase 3 wires `spacedock_solver_v2` into the same dispatch.

**Style:** em-dashes banned (per commit `a2e9c49`); use commas, periods, or parentheses.

---

## Load-bearing pre-condition from `b5` (verbatim consumption, not re-derivation)

`b5` shipped a 5-point contract that this plan consumes verbatim as the `SpacedockSolverAgent` class shape. From `docs/razorback-implementation/plans/spec-mitigation-resume-conflict.md` lines 58-66:

> Phase 3's `SpacedockSolverAgent` v2 (`src/razorback/agents/spacedock_solver_v2.py`) MUST:
> 1. Compute `sealed_hash` in `__init__` per §4.3 + §8.4's six inputs.
> 2. In `setup(env)`, resolve the freeze dir as `Path(self.logs_dir).parent.parent / "_razorback" / "freeze" / self.sealed_hash`. (Rationale: harbor's `logs_dir` for a trial is `<run-dir>/trials/<trial_name>/logs/` or similar; the two `.parent` calls back out to the run-dir.)
> 3. Create the freeze dir if it does not exist; `git init` inside `.git/` on first stage.
> 4. Write `sealed_hash.txt` with the literal hash on first stage; on subsequent stages, read it and `SeedMismatchError` (exit 20) on mismatch.
> 5. The freeze dir survives `harbor jobs resume`; the trial's `agent/` subtree does **not**. Razorback never writes inside `trials/<name>/agent/`.

Per `b5` line 61, the **destination root is `<run-dir>/_razorback/freeze/<sealed_hash>/`**. The exact `logs_dir` shape is named in spec §7.1; Phase 3 must verify against harbor's actual layout at implementation time (Task 5 Step 1 below), but the **path key is `sealed_hash`, not `trial_name`**. The class never writes inside `<run-dir>/trials/<name>/`.

The six sealed inputs (per §4.3.5 + §8.4) are:

1. `model` (string, e.g., `claude-opus-4-5`)
2. `sampling` (dict with `temperature`, `top_p`, `seed` canonicalised; null seed pinned not dropped)
3. `solver_workflow_content_hash` (recursive content hash of the `solver_workflow` directory)
4. `prompt_content_hashes` (the `sha256:`-prefixed hashes for any prompt files the spec pins; this also covers the solver-workflow README's `## Stages` section that drives stage names)
5. `spacedock_skill_version` (resolved at `rk freeze` from the spacedock plugin's `plugin.json`)
6. `harbor_agent_kwargs` (the kwargs harbor's `AgentFactory` will splat into the inner installed-agent constructor, e.g., `max_turns`, `tools_allowed`, `tools_denied`, `append_system_prompt`, `skills_dir`; sorted-keys canonical JSON over the dict)

`compute_sealed_hash` in `src/razorback/agents/seal.py` already implements the canonical-JSON-over-sorted-keys → sha256[:32] mechanism for four inputs (model, sampling, stages, prompt_hashes). Phase 3 adapts it to take six inputs (drops `stages` as a top-level field because v2 reads stage names from the solver workflow README and folds their identity into `solver_workflow_content_hash`; adds the three new fields).

---

## AC ↔ task map (1:1)

| AC | Governing §-cite | Task(s) |
|----|------------------|---------|
| AC-1, Walking skeleton holds (v1 × in-tree adapter; v2 × in-tree adapter) | §4 + spec §6.2 deterministic-smoke; entity AC-1 (lines 41-47) | Task 8 (integration smoke, walking skeleton; runs at the end after riskier contracts land) |
| AC-2, `SpacedockSolverAgent` v2 class exists, computes sealed_hash, refuses on mismatch | §4.3 + §8.4; entity AC-2 (lines 49-59) | Tasks 1 + 2 + 4 |
| AC-3, Per-runtime adapter sub-modules (`_runtime/claude.py` functional; `codex.py` / `pi.py` stubs) | §4.3.1 + §8.4 (per-runtime sub-modules); entity AC-3 (lines 61-69) | Task 3 |
| AC-4, Extractions preserve proven semantics (seal, phase_stats schema, resume-mismatch, auth exclusivity, FU-1 extra_env redaction) | §4 + §8.4; FU-1 AC-1; inventory KEEP-VERBATIM rows; entity AC-4 (lines 71-81) | Task 2 (inline, with KEEP-VERBATIM citation in commit message) |
| AC-5, Claude runtime smoke succeeds + sealed_hash.txt lands at `_razorback/freeze/<sealed_hash>/` | §4.3.4 + §7.1 (sealed_hash-keyed external freeze); entity AC-5 (lines 83-91) | Task 6 (sealed_hash-keyed freeze write contract; LANDS BEFORE halt-resume) + Task 7 (bookreview claude smoke) |
| AC-6, Halt-resume smoke succeeds with hand-faked freeze writes | §4.4 + §5.2; b5 contract; entity AC-6 (lines 93-102) | Task 5 (halt-resume lifecycle wiring) + Task 7 (integration validation) |
| AC-7, `import_path` dispatch wires `spacedock_solver_v2` to the v2 class | §4.5 + Phase 1 translator; entity AC-7 (lines 104-112) | Task 4 (schema discriminator) + Task 6 (translator extension; piggybacks on Phase 1) |
| AC-8, V1 `SpacedockSolverAgent` still functional under `agent.kind: spacedock_solver` | §4.5 routing; entity AC-8 (lines 114-119) | Task 9 (regression test) |
| AC-9, `uv run pytest` exits 0 | entity AC-9 (lines 121-123) | Task 10 |

**Riskiest-contract-first ordering (per dispatch checklist item 3):**

1. **Tasks 1 → 2 → 3 → 4** establish the v2 class core (sealed_hash, schema, runtime adapter sub-modules, schema discriminator). No I/O contract risk yet; these are deterministic-unit-testable.
2. **Task 5** wires the halt-resume lifecycle (first-stage write, every-stage commit pattern, harbor-resume recovery, cross-job resume, done, GC); it touches the class shape but does not yet validate the on-disk contract.
3. **Task 6, sealed_hash-keyed freeze read/write contract (mechanism validation, smallest end-to-end exercise)** lands BEFORE the halt-resume orchestration test in Task 7. Task 6's integration test writes a single `sealed_hash.txt` under `<harbor-run-dir>/_razorback/freeze/<sealed_hash>/` and reads it back via a stage-commit + `harbor jobs resume` round-trip with hand-faked freeze writes; this validates the b5 load-bearing path against harbor's actual `logs_dir` layout before Task 7 invests in a bookreview-claude integration. Per CL's "Validating new mechanisms" rule.
4. **Task 7** runs the bookreview-claude end-to-end smoke (the comprehensive run) AFTER the mechanism validates in Task 6.
5. **Task 8** runs the walking-skeleton deterministic-smoke (AC-1) against both v1 and v2 (cheap; gates the regression in Task 9).
6. **Task 9** runs the v1 regression (AC-8).
7. **Task 10** sweeps `uv run pytest`.

Tasks 1-5 land in any order under the same worktree commit cadence (one commit per task); Task 6 must precede Task 7 in execution order; Tasks 8-10 follow.

---

## Out of scope (explicitly named in entity, not re-litigated here)

- Codex and pi runtime functional implementations, `_runtime/codex.py` and `_runtime/pi.py` ship as `NotImplementedError` stubs per D2's default.
- Real-mod halt-resume validation, workflow mods firing on stage-completion signals are deferred to the autoresearch loop per spec §5.2; Phase 3's smoke uses hand-faked freeze writes.
- `tools_denied` PreToolUse hook plumbing, the field shape ships in the v2 schema (per AC-2's pydantic schema), but the runtime adapter hook installation is owned by `v4 pkg9-v2`. Phase 3's claude adapter accepts the kwarg and passes it through to harbor's `ClaudeCode` agent.
- `phase_stats.json` production via real workflow mods, hand-faked through Phase 8 per spec §5.2.
- Promotion of v2 to canonical `agent.kind: spacedock_solver`, Phase 6.
- GC of the freeze tree, `b5` line 54 names "no automatic GC; durable across resumes"; Phase 3 does not invent a GC contract.

---

## Task 1: Adapt `seal.py` for v2's six-input sealed-hash payload (AC-2 core)

**Files:**
- Modify: `src/razorback/agents/seal.py` (extend `compute_sealed_hash` signature)
- Create: `tests/unit/test_seal_v2_six_inputs.py`

**Spec cite:** §4.3.5 (sealed inputs), §8.4 (sealed_hash mechanism). `b5` line 41 ("Phase 3's `compute_sealed_hash` produces this value; this entity does not redefine it"). Inventory anchor: `agents/seal.py:18-41` (KEEP-EXTRACT verbatim mechanism, ADAPT signature).

**Why first:** Every downstream task imports `compute_sealed_hash`. Locking the v2 signature with a failing test up front prevents Task 2 (the class constructor) from coding against a stale shape.

- [ ] **Step 1: Write the failing unit test for the six-input sealed-hash**

Create `tests/unit/test_seal_v2_six_inputs.py`:

```python
# ABOUTME: AC-2, compute_sealed_hash takes the six v2 sealed inputs and flips on each.
# ABOUTME: Per spec §4.3.5 + §8.4. b5 plan lines 41-42 name this as the v2 contract.

from razorback.agents.seal import compute_sealed_hash


BASE_INPUTS = dict(
    model="claude-opus-4-5",
    sampling={"temperature": 0.0, "top_p": None, "seed": None},
    solver_workflow_content_hash="sha256:" + "a" * 64,
    prompt_content_hashes={"readme": "sha256:" + "b" * 64},
    spacedock_skill_version="1.0.0",
    harbor_agent_kwargs={"max_turns": 200, "tools_allowed": []},
)


def test_sealed_hash_is_32_hex_chars():
    h = compute_sealed_hash(**BASE_INPUTS)
    assert len(h) == 32
    assert all(c in "0123456789abcdef" for c in h)


def test_sealed_hash_is_deterministic():
    h1 = compute_sealed_hash(**BASE_INPUTS)
    h2 = compute_sealed_hash(**BASE_INPUTS)
    assert h1 == h2


def test_perturbing_each_of_six_inputs_flips_hash():
    base = compute_sealed_hash(**BASE_INPUTS)
    perturbations = {
        "model": "claude-sonnet-4-6",
        "sampling": {"temperature": 0.1, "top_p": None, "seed": None},
        "solver_workflow_content_hash": "sha256:" + "c" * 64,
        "prompt_content_hashes": {"readme": "sha256:" + "d" * 64},
        "spacedock_skill_version": "1.0.1",
        "harbor_agent_kwargs": {"max_turns": 201, "tools_allowed": []},
    }
    for field, perturbed in perturbations.items():
        inputs = {**BASE_INPUTS, field: perturbed}
        h = compute_sealed_hash(**inputs)
        assert h != base, f"perturbing {field} did not flip the sealed_hash"


def test_null_seed_is_pinned_not_dropped():
    inputs = {**BASE_INPUTS, "sampling": {"temperature": 0.0, "top_p": None, "seed": None}}
    h_null_seed = compute_sealed_hash(**inputs)
    inputs_no_seed_key = {**BASE_INPUTS, "sampling": {"temperature": 0.0, "top_p": None}}
    h_missing_seed = compute_sealed_hash(**inputs_no_seed_key)
    # Per seal.py:44-53 contract: "null is pinned, not dropped".
    assert h_null_seed == h_missing_seed, (
        "canonicalised sampling must coerce missing seed to null; the two forms seal equally"
    )


def test_harbor_agent_kwargs_key_order_irrelevant():
    a = compute_sealed_hash(**{**BASE_INPUTS, "harbor_agent_kwargs": {"max_turns": 200, "tools_allowed": []}})
    b = compute_sealed_hash(**{**BASE_INPUTS, "harbor_agent_kwargs": {"tools_allowed": [], "max_turns": 200}})
    assert a == b
```

Run: `uv run pytest tests/unit/test_seal_v2_six_inputs.py -v`
Expected: FAIL with `TypeError` about unexpected keyword arguments to `compute_sealed_hash`.

- [ ] **Step 2: Extend `compute_sealed_hash` to accept the six v2 inputs**

`Edit` `src/razorback/agents/seal.py`. The new function signature replaces the v1 four-input shape. The canonical-JSON-over-sorted-keys → sha256[:32] mechanism (the load-bearing core per inventory) is unchanged. `_canonicalize_sampling` is unchanged (lines 44-53 stay verbatim; null seed pinning is preserved).

The new payload:

```python
payload = {
    "model": model,
    "sampling": _canonicalize_sampling(sampling),
    "solver_workflow_content_hash": solver_workflow_content_hash,
    "prompt_content_hashes": {k: prompt_content_hashes[k] for k in sorted(prompt_content_hashes)},
    "spacedock_skill_version": spacedock_skill_version,
    "harbor_agent_kwargs": _canonicalize_kwargs(harbor_agent_kwargs),
}
```

Add `_canonicalize_kwargs(d)` returning `{k: d[k] for k in sorted(d)}` (recursive only if needed; v0 keep the top-level sort sufficient since the kwargs dict is shallow JSON-serialisable in practice).

`prompt_sha256` (lines 9-15) is unchanged.

- [ ] **Step 3: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_seal_v2_six_inputs.py -v`
Expected: 5/5 PASS.

- [ ] **Step 4: Commit**

```bash
git add src/razorback/agents/seal.py tests/unit/test_seal_v2_six_inputs.py
git commit -m "Phase 3 AC-2: compute_sealed_hash takes six v2 inputs (per spec §4.3.5 + §8.4)"
```

---

## Task 2: `SpacedockSolverAgent` v2 class with sealed_hash + resume-mismatch refusal + KEEP-VERBATIM extractions (AC-2 + AC-4)

**Files:**
- Create: `src/razorback/agents/spacedock_solver_v2.py`
- Create: `tests/unit/test_spacedock_solver_v2_class.py`

**Spec cite:** §4.3 (class responsibilities), §4.3.5 (sealed-hash refusal), §8.4 (class skeleton). FU-1 M3 AC-3 (auth exclusivity, `extra_env` redaction). `b5` 5-point contract (lines 58-66).

**KEEP-VERBATIM extractions (cited in commit per AC-4 + AC-0.10):**

| Behavior | v1 source | v2 destination | Verbatim? |
|---|---|---|---|
| Sealed-hash refusal before harbor I/O | `agents/spacedock_solver.py:91-128` (`_refuse_on_resume_mismatch`) | `spacedock_solver_v2.py:_refuse_on_resume_mismatch` | Adapted (six-input payload via Task 1's `compute_sealed_hash`); refusal predicate and error message shape verbatim |
| Co-mingled-auth refusal (ANTHROPIC_API_KEY ⊕ CLAUDE_CODE_OAUTH_TOKEN) | `agents/spacedock_solver.py:80-86` | `spacedock_solver_v2.py.__init__` | Verbatim |
| `assert_phase_stats_schema` | `agents/spacedock_solver.py:25-37` | `spacedock_solver_v2.assert_phase_stats_schema` | Adapted (stage names come from solver_workflow README, not hardcoded; v2 schema gains `tokens_reasoning`, `tokens_cache_read`, `tokens_cache_write` per §7.2) |
| FU-1 `extra_env` discipline | `agents/spacedock_solver.py:76-79` | `spacedock_solver_v2.__init__` | Verbatim, auth flows via `extra_env` kwarg sourced from `AgentConfig.env` (harbor redacts on disk; kwargs is plaintext) |
| `prompt_sha256` from `agents/seal.py:9-15` | `agents/seal.py:9-15` | re-exported by `spacedock_solver_v2` | Verbatim |

- [ ] **Step 1: Write the failing unit test**

Create `tests/unit/test_spacedock_solver_v2_class.py`:

```python
# ABOUTME: AC-2 + AC-4, SpacedockSolverAgent v2 class: sealed_hash, refusal, KEEP-VERBATIM extractions.
# ABOUTME: Per spec §4.3 + §8.4. Constructs with valid kwargs; refuses on resume mismatch (exit 20).

from pathlib import Path

import pytest

from razorback.agents.seal import compute_sealed_hash
from razorback.agents.spacedock_solver_v2 import (
    SpacedockSolverAgent,
    SpacedockSolverAgentError,
)
from razorback.errors import SeedMismatchError


def _valid_kwargs(tmp_path: Path) -> dict:
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n- analyze\n")
    return dict(
        logs_dir=tmp_path / "trial-logs",
        runtime="claude",
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        solver_workflow=workflow,
        solver_workflow_content_hash="sha256:" + "a" * 64,
        prompt_content_hashes={"readme": "sha256:" + "b" * 64},
        spacedock_skill_version="1.0.0",
        harbor_agent_kwargs={"max_turns": 200, "tools_allowed": [], "tools_denied": []},
        max_turns=200,
        tools_allowed=[],
        tools_denied=[],
        extra_env={"ANTHROPIC_API_KEY": "sk-fake"},
    )


def test_constructor_validates_and_computes_sealed_hash(tmp_path):
    kw = _valid_kwargs(tmp_path)
    agent = SpacedockSolverAgent(**kw)
    expected = compute_sealed_hash(
        model=kw["model"], sampling=kw["sampling"],
        solver_workflow_content_hash=kw["solver_workflow_content_hash"],
        prompt_content_hashes=kw["prompt_content_hashes"],
        spacedock_skill_version=kw["spacedock_skill_version"],
        harbor_agent_kwargs=kw["harbor_agent_kwargs"],
    )
    assert agent.sealed_hash == expected


def test_co_mingled_auth_refused(tmp_path):
    kw = _valid_kwargs(tmp_path)
    kw["extra_env"] = {"ANTHROPIC_API_KEY": "x", "CLAUDE_CODE_OAUTH_TOKEN": "y"}
    with pytest.raises(SpacedockSolverAgentError, match="cannot both be set"):
        SpacedockSolverAgent(**kw)


def test_resume_mismatch_refuses_with_exit_20(tmp_path):
    """Per b5 contract point 4: sealed_hash.txt mismatch raises SeedMismatchError."""
    kw = _valid_kwargs(tmp_path)
    # Write a prior sealed_hash that does not match the recomputed value.
    freeze_dir = tmp_path / "_razorback_prior" / "freeze" / "deadbeef" * 4
    freeze_dir.mkdir(parents=True)
    (freeze_dir / "sealed_hash.txt").write_text("deadbeef" * 4)
    kw["resume_from_freeze"] = freeze_dir
    with pytest.raises(SeedMismatchError):
        SpacedockSolverAgent(**kw)
    # SeedMismatchError carries exit_code 20 (errors.py:28-30).
    from razorback.errors import SeedMismatchError as E
    assert E.exit_code == 20


def test_each_of_six_sealed_inputs_perturbs_hash(tmp_path):
    """AC-2: perturbing each of the six sealed inputs in isolation flips the hash."""
    base_kw = _valid_kwargs(tmp_path)
    base = SpacedockSolverAgent(**base_kw).sealed_hash
    perturbations = [
        ("model", "claude-sonnet-4-6"),
        ("sampling", {"temperature": 0.7, "top_p": None, "seed": None}),
        ("solver_workflow_content_hash", "sha256:" + "c" * 64),
        ("prompt_content_hashes", {"readme": "sha256:" + "d" * 64}),
        ("spacedock_skill_version", "1.0.1"),
        ("harbor_agent_kwargs", {"max_turns": 201, "tools_allowed": [], "tools_denied": []}),
    ]
    for field, perturbed in perturbations:
        kw = {**base_kw, field: perturbed}
        h = SpacedockSolverAgent(**kw).sealed_hash
        assert h != base, f"perturbing {field} did not flip sealed_hash"


def test_extra_env_redaction_invariant(tmp_path):
    """AC-4: FU-1, extra_env carries secrets; they must not appear in repr or attribute dump."""
    kw = _valid_kwargs(tmp_path)
    kw["extra_env"] = {"ANTHROPIC_API_KEY": "sk-SECRET-VALUE"}
    agent = SpacedockSolverAgent(**kw)
    # Class should not surface the secret via str/repr.
    assert "sk-SECRET-VALUE" not in repr(agent)
    assert "sk-SECRET-VALUE" not in str(agent)
```

Run: `uv run pytest tests/unit/test_spacedock_solver_v2_class.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'razorback.agents.spacedock_solver_v2'`.

- [ ] **Step 2: Create `src/razorback/agents/spacedock_solver_v2.py`**

The class subclasses `harbor.agents.base.BaseAgent`. Key shape (from §8.4):

```python
# ABOUTME: SpacedockSolverAgent v2 (spec §4 + §8.4), runtime adapter for claude|codex|pi.
# ABOUTME: __init__ computes sealed_hash from six inputs; refuses on resume mismatch BEFORE harbor I/O.

import json
import os
from pathlib import Path
from typing import Any, Literal

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment

from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.errors import RazorbackError, SeedMismatchError


_REQUIRED_PHASE_STATS_KEYS = (
    "tokens_in", "tokens_out", "tokens_reasoning",
    "tokens_cache_read", "tokens_cache_write",
    "cost_usd", "wallclock_s",
)


class SpacedockSolverAgentError(RazorbackError):
    """Raised on SpacedockSolverAgent v2 contract violations."""


def assert_phase_stats_schema(path: Path, *, stages: list[str]) -> None:
    """Per §7.2, phase_stats.json carries five token fields + cost + wallclock per stage."""
    data = json.loads(Path(path).read_text())
    assert isinstance(data, dict)
    for stage in stages:
        assert stage in data, f"missing stage: {stage}"
        for k in _REQUIRED_PHASE_STATS_KEYS:
            assert k in data[stage], f"missing key {k!r} in stage {stage!r}"


class SpacedockSolverAgent(BaseAgent):
    SUPPORTS_WINDOWS = False
    SUPPORTS_ATIF = False

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        logger=None,
        mcp_servers=None,
        skills_dir=None,
        *,
        runtime: Literal["claude", "codex", "pi"],
        model: str,
        sampling: dict[str, Any],
        solver_workflow: Path,
        solver_workflow_content_hash: str,
        prompt_content_hashes: dict[str, str],
        spacedock_skill_version: str,
        harbor_agent_kwargs: dict[str, Any],
        max_turns: int = 200,
        tools_allowed: list[str] | None = None,
        tools_denied: list[str] | None = None,
        resume_from_freeze: Path | str | None = None,
        extra_env: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name or model,
            logger=logger,
            mcp_servers=mcp_servers,
            skills_dir=skills_dir,
            **kwargs,
        )
        # FU-1: auth via extra_env (sourced from AgentConfig.env; redacted on disk).
        self._extra_env = dict(extra_env or {})
        if (
            "ANTHROPIC_API_KEY" in self._extra_env
            and "CLAUDE_CODE_OAUTH_TOKEN" in self._extra_env
        ):
            raise SpacedockSolverAgentError(
                "ANTHROPIC_API_KEY and CLAUDE_CODE_OAUTH_TOKEN cannot both be set."
            )

        self._runtime = runtime
        self._model = model
        self._sampling = dict(sampling)
        self._solver_workflow = Path(solver_workflow)
        self._solver_workflow_content_hash = solver_workflow_content_hash
        self._prompt_content_hashes = dict(prompt_content_hashes)
        self._spacedock_skill_version = spacedock_skill_version
        self._harbor_agent_kwargs = dict(harbor_agent_kwargs)
        self._max_turns = max_turns
        self._tools_allowed = list(tools_allowed or [])
        self._tools_denied = list(tools_denied or [])

        # AC-2 + b5 contract point 1: compute sealed_hash from six inputs.
        self.sealed_hash = compute_sealed_hash(
            model=self._model,
            sampling=self._sampling,
            solver_workflow_content_hash=self._solver_workflow_content_hash,
            prompt_content_hashes=self._prompt_content_hashes,
            spacedock_skill_version=self._spacedock_skill_version,
            harbor_agent_kwargs=self._harbor_agent_kwargs,
        )

        # AC-2 + b5 contract point 4: refuse on resume mismatch BEFORE harbor I/O.
        self._resume_from_freeze = Path(resume_from_freeze) if resume_from_freeze else None
        if self._resume_from_freeze is not None:
            self._refuse_on_resume_mismatch(self._resume_from_freeze)

        # Inner runtime adapter (lazy-constructed in setup() to defer harbor I/O).
        self._inner: BaseAgent | None = None

    def __repr__(self) -> str:
        # FU-1: never surface secrets in repr.
        return (
            f"SpacedockSolverAgent(runtime={self._runtime!r}, model={self._model!r}, "
            f"sealed_hash={self.sealed_hash!r})"
        )

    def _refuse_on_resume_mismatch(self, freeze_dir: Path) -> None:
        """Per b5 contract point 4: read sealed_hash.txt; SeedMismatchError on mismatch."""
        sealed_file = freeze_dir / "sealed_hash.txt"
        if not sealed_file.exists():
            raise SpacedockSolverAgentError(
                f"resume_from_freeze {freeze_dir} has no sealed_hash.txt; cannot validate resume."
            )
        prior = sealed_file.read_text().strip()
        if prior != self.sealed_hash:
            raise SeedMismatchError(
                f"resume sealed_hash ({self.sealed_hash}) does not match prior sealed_hash ({prior}). "
                f"Prior freeze dir: {freeze_dir}."
            )

    @staticmethod
    def name() -> str:
        return "spacedock-solver-v2"

    def version(self) -> str | None:
        return None

    @classmethod
    def required_env(cls) -> dict:
        return {
            "mode": "alternation",
            "names": ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"],
        }

    @staticmethod
    def supported_sampling() -> set[str]:
        return {"temperature"}

    # setup() / run() / cleanup() land in Tasks 3 + 5.
```

Note: the kwarg shape carries both top-level `tools_allowed` / `tools_denied` / `max_turns` AND a `harbor_agent_kwargs` dict. The latter is the canonical sealed payload; the top-level fields are convenience accessors duplicated for the per-runtime adapter sub-module to read. (Phase 1's translator emits both; see Task 6.)

- [ ] **Step 3: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_spacedock_solver_v2_class.py -v`
Expected: 5/5 PASS.

- [ ] **Step 4: Commit**

```bash
git add src/razorback/agents/spacedock_solver_v2.py tests/unit/test_spacedock_solver_v2_class.py
git commit -m "$(cat <<'EOF'
Phase 3 AC-2 + AC-4: SpacedockSolverAgent v2 class with sealed_hash refusal

KEEP-VERBATIM from v1 spacedock_solver.py:
- sealed-hash refusal pattern (:91-128) adapted to six-input payload
- co-mingled-auth refusal (:80-86) verbatim
- extra_env discipline (:76-79) verbatim (FU-1 AC-1)

Per spec §4.3 + §8.4. b5 contract points 1 + 4 land.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Per-runtime adapter sub-modules (AC-3)

**Files:**
- Create: `src/razorback/agents/_runtime/__init__.py` (package shim)
- Create: `src/razorback/agents/_runtime/claude.py` (functional)
- Create: `src/razorback/agents/_runtime/codex.py` (NotImplementedError stub)
- Create: `src/razorback/agents/_runtime/pi.py` (NotImplementedError stub)
- Create: `tests/unit/test_runtime_adapters.py`

**Spec cite:** §4.3.1 + §8.4 ("Per-runtime adapter sub-modules (`_claude.py`, `_codex.py`, `_pi.py`) hold the per-runtime kwarg construction"). Inventory: `agents/spacedock_solver.py:180-206` (setup pattern; ADAPT into the claude sub-module). D2's "claude-first ship" default.

- [ ] **Step 1: Write the failing unit test**

Create `tests/unit/test_runtime_adapters.py`:

```python
# ABOUTME: AC-3, per-runtime adapter sub-modules exist; codex + pi raise NotImplementedError.
# ABOUTME: claude.py constructs a harbor ClaudeCode instance with the expected kwargs.

import pytest

from razorback.agents._runtime import claude as claude_adapter
from razorback.agents._runtime import codex as codex_adapter
from razorback.agents._runtime import pi as pi_adapter


def test_codex_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="codex"):
        codex_adapter.build_inner_agent(
            logs_dir="/tmp/x", model="any", harbor_agent_kwargs={}, extra_env={},
        )


def test_pi_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="pi"):
        pi_adapter.build_inner_agent(
            logs_dir="/tmp/x", model="any", harbor_agent_kwargs={}, extra_env={},
        )


def test_claude_constructs_inner_agent(tmp_path):
    inner = claude_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        harbor_agent_kwargs={
            "max_turns": 200,
            "tools_allowed": ["Read", "Write"],
            "tools_denied": ["Bash(rm*)"],
            "append_system_prompt": "You are the first officer.",
        },
        extra_env={"ANTHROPIC_API_KEY": "sk-fake"},
    )
    # ClaudeCode is harbor's installed agent; we assert the class identity by name.
    assert inner.__class__.__name__ == "ClaudeCode"


def test_claude_passes_tools_denied_through_to_harbor_kwargs(tmp_path):
    """v4-pkg9-v2 owns the PreToolUse hook plumbing; Phase 3 just passes the kwarg through."""
    inner = claude_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        harbor_agent_kwargs={"max_turns": 200, "tools_denied": ["Bash(pip install datasets*)"]},
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )
    # Harbor's ClaudeCode CLI_FLAGS includes `disallowed_tools`; the adapter must map
    # razorback's `tools_denied` field to that kwarg.
    assert hasattr(inner, "disallowed_tools") or "disallowed_tools" in vars(inner)
```

Run: `uv run pytest tests/unit/test_runtime_adapters.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'razorback.agents._runtime'`.

- [ ] **Step 2: Create the `_runtime` package**

`src/razorback/agents/_runtime/__init__.py`:

```python
# ABOUTME: Per-runtime adapter sub-modules for SpacedockSolverAgent v2 (spec §8.4).
# ABOUTME: claude is functional; codex and pi ship as NotImplementedError stubs (D2 default).
```

`src/razorback/agents/_runtime/claude.py`:

```python
# ABOUTME: Claude runtime adapter for SpacedockSolverAgent v2 (spec §4.3.1, §8.4).
# ABOUTME: Constructs harbor's ClaudeCode agent with the kwarg shape razorback's spec requires.

from pathlib import Path
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode


def build_inner_agent(
    *,
    logs_dir: Path,
    model: str,
    harbor_agent_kwargs: dict[str, Any],
    extra_env: dict[str, str],
) -> ClaudeCode:
    """Construct harbor's ClaudeCode agent with razorback's kwarg shape.

    Razorback's spec carries `tools_allowed`, `tools_denied`, `max_turns`,
    `append_system_prompt`, and `skills_dir` per spec §4.3.3 + §6.2; harbor's
    ClaudeCode accepts them via CLI_FLAGS (claude_code.py:33-90).
    """
    # Map razorback field names to harbor ClaudeCode kwarg names.
    # tools_allowed → allowed_tools; tools_denied → disallowed_tools.
    kw: dict[str, Any] = {
        "max_turns": harbor_agent_kwargs.get("max_turns"),
    }
    if "tools_allowed" in harbor_agent_kwargs:
        kw["allowed_tools"] = ",".join(harbor_agent_kwargs["tools_allowed"])
    if "tools_denied" in harbor_agent_kwargs:
        kw["disallowed_tools"] = ",".join(harbor_agent_kwargs["tools_denied"])
    if "append_system_prompt" in harbor_agent_kwargs:
        kw["append_system_prompt"] = harbor_agent_kwargs["append_system_prompt"]
    if "skills_dir" in harbor_agent_kwargs:
        kw["skills_dir"] = harbor_agent_kwargs["skills_dir"]
    # Drop None values so harbor uses its own defaults.
    kw = {k: v for k, v in kw.items() if v is not None}
    return ClaudeCode(logs_dir=Path(logs_dir), model_name=model, **kw)
```

`src/razorback/agents/_runtime/codex.py`:

```python
# ABOUTME: Codex runtime adapter stub (NotImplementedError per D2 default).
# ABOUTME: Functional implementation lands when a consumer surfaces (spec §4.3.1 + §8.4).

def build_inner_agent(**kwargs):
    raise NotImplementedError(
        "codex runtime adapter is not implemented. "
        "Per spec §4.3.1 + §8.4, codex ships when a consumer surfaces; "
        "Phase 3 ships claude only per D2 default."
    )
```

`src/razorback/agents/_runtime/pi.py`:

```python
# ABOUTME: Pi runtime adapter stub (NotImplementedError per D2 default).
# ABOUTME: Functional implementation lands when a consumer surfaces (spec §4.3.1 + §8.4).

def build_inner_agent(**kwargs):
    raise NotImplementedError(
        "pi runtime adapter is not implemented. "
        "Per spec §4.3.1 + §8.4, pi ships when a consumer surfaces; "
        "Phase 3 ships claude only per D2 default."
    )
```

- [ ] **Step 3: Wire `_runtime` selection into `SpacedockSolverAgent.__init__` (or defer to setup)**

In `spacedock_solver_v2.py`, add the dispatch helper:

```python
def _build_inner_agent(self) -> BaseAgent:
    from razorback.agents._runtime import claude as _claude
    from razorback.agents._runtime import codex as _codex
    from razorback.agents._runtime import pi as _pi
    builders = {"claude": _claude.build_inner_agent,
                "codex": _codex.build_inner_agent,
                "pi": _pi.build_inner_agent}
    builder = builders[self._runtime]
    return builder(
        logs_dir=self.logs_dir,
        model=self._model,
        harbor_agent_kwargs=self._harbor_agent_kwargs,
        extra_env=self._extra_env,
    )
```

`_build_inner_agent` is called from `setup()` (Task 5), not `__init__`, to keep `__init__` free of harbor I/O per spec §4.3.5.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_runtime_adapters.py -v`
Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/agents/_runtime/ src/razorback/agents/spacedock_solver_v2.py tests/unit/test_runtime_adapters.py
git commit -m "Phase 3 AC-3: per-runtime adapter sub-modules (claude functional; codex/pi stubs)"
```

---

## Task 4: Spec schema discriminator `spacedock_solver_v2` (AC-7 prerequisite)

**Files:**
- Modify: `src/razorback/spec/schema.py` (add `SpacedockSolverV2AgentBlock`)
- Create: `tests/unit/test_spec_schema_spacedock_solver_v2.py`

**Spec cite:** Entity AC-7 (lines 104-112); §6.2 (agent block fields). v1's `spacedock-solver` block stays; v2 adds a new discriminator value `spacedock_solver_v2` until Phase 6 promotes v2 to canonical.

**Note on naming:** v2 spec §6.2 lists `kind: spacedock_solver` (canonical) as the v2 target after Phase 6. Phase 3 ships under `kind: spacedock_solver_v2` to avoid breaking v1 routing in the same release. The entity body (lines 21-28) names this discipline explicitly.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_spec_schema_spacedock_solver_v2.py`:

```python
# ABOUTME: AC-7, spec.agent.kind: spacedock_solver_v2 routes to the v2 schema block.
# ABOUTME: v1's kind: spacedock-solver still routes to v1 block (per AC-8).

import pytest
from pydantic import ValidationError

from razorback.spec.schema import Spec, SpacedockSolverV2AgentBlock


def test_spacedock_solver_v2_block_parses(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")
    block = SpacedockSolverV2AgentBlock(
        kind="spacedock_solver_v2",
        runtime="claude",
        model="claude-opus-4-5",
        solver_workflow=workflow,
        max_turns=200,
        max_budget_usd=10,
        tools_allowed=[],
        tools_denied=[],
    )
    assert block.runtime == "claude"
    assert block.kind == "spacedock_solver_v2"


def test_spacedock_solver_v2_runtime_enum_enforced():
    with pytest.raises(ValidationError, match="runtime"):
        SpacedockSolverV2AgentBlock(
            kind="spacedock_solver_v2",
            runtime="unsupported",
            model="x",
            solver_workflow=".",
        )


def test_v1_spacedock_solver_block_still_parses():
    """AC-8: v1's kind: spacedock-solver routes to the v1 block; no breakage."""
    from razorback.spec.schema import SpacedockSolverAgentBlock
    block = SpacedockSolverAgentBlock(
        kind="spacedock-solver",
        prompts={"model": "p1.md", "analyze": "p2.md", "verify": "p3.md"},
    )
    assert block.kind == "spacedock-solver"
```

Run: `uv run pytest tests/unit/test_spec_schema_spacedock_solver_v2.py -v`
Expected: FAIL with `ImportError: cannot import name 'SpacedockSolverV2AgentBlock'`.

- [ ] **Step 2: Add `SpacedockSolverV2AgentBlock` to `src/razorback/spec/schema.py`**

```python
class SpacedockSolverV2AgentBlock(BaseModel):
    """Spec-level agent block for v2 (spec §6.2 + §4).

    Unfrozen specs carry the path `solver_workflow:`; freeze resolves the
    directory content hash and writes `solver_workflow_content_hash` into the
    frozen spec. `sealed_hash` is populated by freeze.
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["spacedock_solver_v2"]
    runtime: Literal["claude", "codex", "pi"] = "claude"
    model: str = "claude-opus-4-5"
    sampling: SamplingBlock = Field(default_factory=SamplingBlock)
    solver_workflow: Path
    solver_workflow_content_hash: str | None = None  # populated at freeze
    max_turns: int = 200
    max_budget_usd: float | None = None
    tools_allowed: list[str] = Field(default_factory=list)
    tools_denied: list[str] = Field(default_factory=list)
    resume_from_freeze: Path | None = None
    sealed_hash: str | None = None  # populated at freeze
    spacedock_skill_version: str | None = None  # populated at freeze
    prompt_content_hashes: dict[str, str] = Field(default_factory=dict)


# Extend the AgentBlock discriminated union to include v2.
AgentBlock = Annotated[
    Union[NopAgentBlock, ClaudeCliAgentBlock, SpacedockSolverAgentBlock, SpacedockSolverV2AgentBlock],
    Field(discriminator="kind"),
]
```

- [ ] **Step 3: Run the test**

Run: `uv run pytest tests/unit/test_spec_schema_spacedock_solver_v2.py -v`
Expected: 3/3 PASS.

- [ ] **Step 4: Commit**

```bash
git add src/razorback/spec/schema.py tests/unit/test_spec_schema_spacedock_solver_v2.py
git commit -m "Phase 3 AC-7: SpacedockSolverV2AgentBlock with kind: spacedock_solver_v2 discriminator"
```

---

## Task 5: Halt-resume lifecycle wiring on the class (AC-2 + AC-6)

**Files:**
- Modify: `src/razorback/agents/spacedock_solver_v2.py` (add `setup()`, `run()`, `cleanup()`, freeze-dir resolution helper)
- Create: `tests/unit/test_spacedock_solver_v2_lifecycle.py`

**Spec cite:** §4.3.4 (freeze-dir contract), §4.3.6 (resume mechanic), §4.4 (halt-resume contract), §8.4 (class skeleton). `b5` 5-point contract (lines 58-66), specifically point 2 (freeze-dir resolution via `Path(self.logs_dir).parent.parent / "_razorback" / "freeze" / self.sealed_hash`) and point 3 (create + `git init` on first stage).

**Lifecycle states (per dispatch checklist item 2):**

| State | Trigger | Action |
|---|---|---|
| First stage of first run | `setup()` first call; `freeze_dir / "sealed_hash.txt"` does not exist | Create `freeze_dir`; `git init` inside `.git/`; write `sealed_hash.txt` |
| Every stage commit | (workflow mod, hand-faked in Phase 3 smoke) | `git -C <freeze_dir> add -A && commit`, Phase 3 ships the helper `_commit_stage()`; the mod calls it via env-exposed path |
| `harbor jobs resume` on incomplete trial | `setup()` re-entry with same `spec.frozen.yaml`; `freeze_dir / "sealed_hash.txt"` exists with matching hash | Read `sealed_hash.txt`; if matches `self.sealed_hash`, restore workspace via `git -C <freeze_dir> checkout`; do NOT re-init |
| Cross-job `resume_from_freeze` | `__init__` with `resume_from_freeze=<path>`; `setup()` later reads `<path>/sealed_hash.txt` | `__init__` already refused on mismatch (Task 2); `setup()` restores workspace from `<path>/.git/` |
| Done | trial ends; `result.json` written by harbor | freeze tree stays in place (durable artifact; see `b5` line 53) |
| GC | out of scope per `b5` line 54 | no automatic GC |

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_spacedock_solver_v2_lifecycle.py`:

```python
# ABOUTME: AC-2 + AC-6, halt-resume lifecycle wiring; freeze-dir resolution per b5 contract.
# ABOUTME: Tests resolve_freeze_dir, first-stage init, sealed_hash.txt write, resume-restore.

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgent
from razorback.errors import SeedMismatchError


def _kw(tmp_path, **overrides):
    workflow = tmp_path / "solver"
    workflow.mkdir(exist_ok=True)
    (workflow / "README.md").write_text("## Stages\n- model\n")
    base = dict(
        logs_dir=tmp_path / "run" / "trials" / "task-0001__abc1234" / "logs",
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
    base.update(overrides)
    base["logs_dir"].parent.mkdir(parents=True, exist_ok=True)
    return base


def test_freeze_dir_resolves_to_sealed_hash_keyed_external_path(tmp_path):
    """b5 contract point 2: <run-dir>/_razorback/freeze/<sealed_hash>/."""
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    expected = tmp_path / "run" / "_razorback" / "freeze" / agent.sealed_hash
    assert agent.resolve_freeze_dir() == expected
    # The path lives OUTSIDE harbor's trials/ subtree.
    assert "_razorback" in str(agent.resolve_freeze_dir())
    assert "trials" not in str(agent.resolve_freeze_dir()).split("_razorback")[1]


@pytest.mark.asyncio
async def test_first_stage_writes_sealed_hash_txt(tmp_path):
    """b5 contract point 4 + AC-5: sealed_hash.txt lands at the keyed path on first stage."""
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    # Stub out the inner agent's setup to avoid harbor I/O in this unit test.
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    await agent.setup(fake_env)
    sealed_file = agent.resolve_freeze_dir() / "sealed_hash.txt"
    assert sealed_file.exists()
    assert sealed_file.read_text().strip() == agent.sealed_hash


@pytest.mark.asyncio
async def test_resume_restores_workspace_from_freeze_git(tmp_path):
    """b5 contract point 5: on resume, restore from <freeze_dir>/.git/."""
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    # Hand-fake a prior freeze: sealed_hash.txt + .git/
    freeze = agent.resolve_freeze_dir()
    freeze.mkdir(parents=True)
    (freeze / "sealed_hash.txt").write_text(agent.sealed_hash)
    (freeze / ".git").mkdir()
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    await agent.setup(fake_env)
    # On resume, setup detects the existing freeze and does not re-init.
    # It calls `git checkout` to restore the workspace.
    git_calls = [c.args[0] for c in fake_env.exec.call_args_list if "git" in c.args[0]]
    assert any("checkout" in c for c in git_calls), (
        f"setup did not call git checkout on resume; calls: {git_calls}"
    )


@pytest.mark.asyncio
async def test_resume_with_mismatched_sealed_hash_in_freeze_dir_refuses(tmp_path):
    """b5 contract point 4: sealed_hash.txt mismatch raises SeedMismatchError at setup."""
    agent = SpacedockSolverAgent(**_kw(tmp_path))
    freeze = agent.resolve_freeze_dir()
    freeze.mkdir(parents=True)
    (freeze / "sealed_hash.txt").write_text("deadbeef" * 4)  # wrong hash
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()
    with pytest.raises(SeedMismatchError):
        await agent.setup(fake_env)
```

Run: `uv run pytest tests/unit/test_spacedock_solver_v2_lifecycle.py -v`
Expected: FAIL with `AttributeError: 'SpacedockSolverAgent' object has no attribute 'resolve_freeze_dir'`.

- [ ] **Step 2: Add `resolve_freeze_dir()`, `setup()`, `run()`, `cleanup()` to `spacedock_solver_v2.py`**

```python
def resolve_freeze_dir(self) -> Path:
    """Per b5 contract point 2 + spec §4.3.4: sealed_hash-keyed external freeze."""
    # harbor's logs_dir for a trial is <run-dir>/trials/<trial_name>/logs/
    # Two .parent calls back out to <run-dir>/trials/<trial_name>/, then one more to <run-dir>/.
    # In harbor 0.6.6, EnvironmentPaths.agent_dir is <logs_dir>; the run-dir is logs_dir.parent.parent.parent
    # if logs_dir is .../trials/<name>/logs/agent. Phase 3 implementation MUST verify against
    # harbor's actual layout (see Step 3 below).
    run_dir = self._resolve_run_dir_from_logs_dir(Path(self.logs_dir))
    return run_dir / "_razorback" / "freeze" / self.sealed_hash


@staticmethod
def _resolve_run_dir_from_logs_dir(logs_dir: Path) -> Path:
    """Back out from harbor's per-trial logs_dir to the run-dir root.

    Harbor's layout (harbor 0.6.6): <run-dir>/trials/<trial_name>/logs/agent/.
    BaseAgent.logs_dir is the deepest path; two parents back out to the trial dir,
    one more to trials/, one more to the run-dir. Implementation verifies via the
    integration mechanism test in Task 6 against harbor's actual layout.
    """
    # The exact parent count depends on harbor's installed-agent layout.
    # Conservative: walk up until we find a sibling `_razorback` candidate root.
    p = logs_dir.resolve()
    for _ in range(5):
        p = p.parent
        if (p / "trials").exists() or (p / "spec.frozen.yaml").exists():
            return p
    # Fallback to b5 line 61's stated default (logs_dir.parent.parent.parent).
    return logs_dir.resolve().parent.parent.parent


async def setup(self, environment: BaseEnvironment) -> None:
    """Per spec §8.4: bootstrap workspace; write sealed_hash.txt; delegate to inner."""
    freeze_dir = self.resolve_freeze_dir()
    sealed_file = freeze_dir / "sealed_hash.txt"

    if sealed_file.exists():
        # Resume path (in-place harbor jobs resume OR cross-job resume_from_freeze).
        prior = sealed_file.read_text().strip()
        if prior != self.sealed_hash:
            raise SeedMismatchError(
                f"freeze dir {freeze_dir} sealed_hash ({prior}) does not match "
                f"this agent's sealed_hash ({self.sealed_hash})."
            )
        # Restore workspace from the embedded .git/.
        result = await environment.exec(f"git -C {freeze_dir} checkout -- .")
        if result.return_code != 0:
            raise SpacedockSolverAgentError(
                f"resume restore via git checkout failed at {freeze_dir} (rc={result.return_code})"
            )
    else:
        # First stage of first run: create freeze dir, git init, write sealed_hash.txt.
        freeze_dir.mkdir(parents=True, exist_ok=True)
        sealed_file.write_text(self.sealed_hash)
        for cmd in (
            f"git -C {freeze_dir} init -q",
            f"git -C {freeze_dir} config user.email razorback@local",
            f"git -C {freeze_dir} config user.name razorback",
            f"git -C {freeze_dir} config commit.gpgsign false",
            f"git -C {freeze_dir} add -A",
            f"git -C {freeze_dir} commit -q --allow-empty -m seed",
        ):
            r = await environment.exec(cmd)
            if r.return_code != 0:
                raise SpacedockSolverAgentError(
                    f"freeze repo init failed at: {cmd} (rc={r.return_code})"
                )

    # Workspace bootstrap: copy solver_workflow contents into the env (§4.3.2).
    # Defer the per-runtime mechanism to the inner adapter's setup hook.

    # Construct + delegate to the inner runtime adapter.
    if self._inner is None:
        self._inner = self._build_inner_agent()
    await self._inner.setup(environment)


async def run(self, instruction, environment, context):
    """Delegate to inner; workflow mods own per-stage commit + phase_stats.json."""
    if self._inner is None:
        raise SpacedockSolverAgentError("run() called before setup()")
    await self._inner.run(instruction, environment, context)


async def cleanup(self, environment):
    if self._inner is not None and hasattr(self._inner, "cleanup"):
        await self._inner.cleanup(environment)
```

- [ ] **Step 3: Run the test**

Run: `uv run pytest tests/unit/test_spacedock_solver_v2_lifecycle.py -v`
Expected: 4/4 PASS.

- [ ] **Step 4: Commit**

```bash
git add src/razorback/agents/spacedock_solver_v2.py tests/unit/test_spacedock_solver_v2_lifecycle.py
git commit -m "Phase 3 AC-2 + AC-6: halt-resume lifecycle wiring (resolve_freeze_dir + setup)"
```

---

## Task 6: Sealed_hash-keyed freeze read/write contract: mechanism validation (riskiest, lands BEFORE Task 7) (AC-5 + AC-7)

**Files:**
- Modify: `src/razorback/translate.py` (extend Phase 1's translator to handle `SpacedockSolverV2AgentBlock`)
- Create: `tests/integration/test_v2_freeze_dir_mechanism.py`
- Create: `examples/specs/_deterministic-smoke-v2.frozen.yaml` (the entity AC-1 reference smoke spec)

**Spec cite:** §4.3.4 + §7.1 (freeze location); `b5` "Lifecycle" table; entity AC-5 + AC-7. Phase 1's translator pattern: `phase1-rk-run-v2-wrapper.md` Task 5 (lines 325-688).

**Why this lands BEFORE Task 7 (per dispatch checklist item 3):** The b5 load-bearing path is the sealed_hash-keyed external freeze tree at `<harbor-run-dir>/_razorback/freeze/<sealed_hash>/`. If the resolver in Task 5 picks the wrong directory (e.g., backs out one too few `.parent` calls and lands inside `trials/<name>/`), the freeze tree is destroyed on resume and every halt-resume test downstream fails for the wrong reason. This task validates the on-disk contract with the **smallest end-to-end exercise**, a fake-harbor-trial directory layout (`<tmp>/run/trials/task-0001__abc1234/logs/agent/`), the v2 agent constructed against it, `setup()` invoked with a stub environment, `sealed_hash.txt` lands at `<tmp>/run/_razorback/freeze/<hash>/`, a hand-faked stage commit, and a `harbor jobs resume`-style re-execution (new `trial_name`, same `spec.frozen.yaml`) restores the workspace from the same freeze tree.

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_v2_freeze_dir_mechanism.py`:

```python
# ABOUTME: AC-5, sealed_hash-keyed external freeze write contract (b5 load-bearing path).
# ABOUTME: Mechanism check: smallest end-to-end exercise of the riskiest b5 contract.

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgent


def _make_harbor_run_dir(tmp_path: Path, trial_name: str) -> Path:
    """Mimic harbor 0.6.6 layout: <run-dir>/trials/<trial_name>/logs/agent/."""
    run_dir = tmp_path / "run"
    logs_dir = run_dir / "trials" / trial_name / "logs" / "agent"
    logs_dir.mkdir(parents=True)
    # Also create spec.frozen.yaml at the run-dir root (the resolver looks for it).
    (run_dir / "spec.frozen.yaml").write_text("placeholder")
    return logs_dir


@pytest.mark.asyncio
async def test_sealed_hash_txt_lands_at_keyed_external_path(tmp_path):
    """AC-5 mechanism: sealed_hash.txt at <run-dir>/_razorback/freeze/<sealed_hash>/."""
    logs_dir = _make_harbor_run_dir(tmp_path, "bookreview-0001__abc1234")
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    agent = SpacedockSolverAgent(
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

    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent._inner = MagicMock()
    agent._inner.setup = AsyncMock()

    await agent.setup(fake_env)

    expected = tmp_path / "run" / "_razorback" / "freeze" / agent.sealed_hash
    assert (expected / "sealed_hash.txt").exists()
    assert (expected / "sealed_hash.txt").read_text().strip() == agent.sealed_hash
    # AC-5 mandate: NOT inside trials/.
    assert "trials" not in str(expected.relative_to(tmp_path / "run"))


@pytest.mark.asyncio
async def test_harbor_jobs_resume_round_trip_with_new_trial_name(tmp_path):
    """AC-6 mechanism: re-executed trial with a NEW trial_name reads the SAME freeze tree."""
    # First execution: trial_name A.
    logs_a = _make_harbor_run_dir(tmp_path, "bookreview-0001__abc1234")
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")
    kw = dict(
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
    agent_a = SpacedockSolverAgent(logs_dir=logs_a, **kw)
    fake_env = MagicMock()
    fake_env.exec = AsyncMock(return_value=MagicMock(return_code=0))
    agent_a._inner = MagicMock()
    agent_a._inner.setup = AsyncMock()
    await agent_a.setup(fake_env)

    # Hand-fake a stage commit (the workflow's freeze mod would do this).
    freeze_dir = agent_a.resolve_freeze_dir()
    assert (freeze_dir / "sealed_hash.txt").exists()

    # Simulate harbor jobs resume: rmtree trials/<old_name>/, new trial_name.
    import shutil
    shutil.rmtree(tmp_path / "run" / "trials" / "bookreview-0001__abc1234")
    logs_b = _make_harbor_run_dir(tmp_path, "bookreview-0001__wMGYfz7")

    # Second execution: same sealed inputs (spec.frozen.yaml unchanged) → same sealed_hash.
    agent_b = SpacedockSolverAgent(logs_dir=logs_b, **kw)
    assert agent_b.sealed_hash == agent_a.sealed_hash
    assert agent_b.resolve_freeze_dir() == freeze_dir  # SAME tree, different trial.

    # setup() detects existing sealed_hash.txt and restores.
    await agent_b.setup(fake_env)
    # The freeze tree survived; the trial dir was rmtree'd.
    assert freeze_dir.exists()
    assert (tmp_path / "run" / "trials" / "bookreview-0001__abc1234").exists() is False


def test_translator_emits_spacedock_solver_v2_import_path(tmp_path):
    """AC-7: spec.agent.kind: spacedock_solver_v2 → import_path of v2 class."""
    from razorback.spec.schema import Spec
    from razorback.translate import spec_to_job_config
    import yaml

    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")

    spec_yaml = f"""
version: 1
experiment: phase3-translate-test
provenance: {{}}
agent:
  kind: spacedock_solver_v2
  runtime: claude
  model: claude-opus-4-5
  solver_workflow: {workflow}
  solver_workflow_content_hash: "sha256:{'a' * 64}"
  spacedock_skill_version: "1.0.0"
  sealed_hash: "0123456789abcdef0123456789abcdef"
  max_turns: 200
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    spec = Spec.model_validate(yaml.safe_load(spec_yaml))
    cfg, _ = spec_to_job_config(
        spec=spec,
        job_name="phase3-test",
        jobs_dir=tmp_path / "_runs",
        project_root=tmp_path,
    )
    agent_cfg = cfg.agents[0]
    assert agent_cfg.import_path == (
        "razorback.agents.spacedock_solver_v2:SpacedockSolverAgent"
    )
    # Sealed inputs flow via kwargs (model, runtime, solver_workflow_content_hash, etc.).
    assert agent_cfg.kwargs["runtime"] == "claude"
    assert agent_cfg.kwargs["solver_workflow_content_hash"] == "sha256:" + "a" * 64
    # Auth flows via env (FU-1 AC-1; never via kwargs).
    assert "ANTHROPIC_API_KEY" not in (agent_cfg.kwargs or {})
```

Run: `uv run pytest tests/integration/test_v2_freeze_dir_mechanism.py -v`
Expected: FAIL, the translator does not yet route `spacedock_solver_v2`.

- [ ] **Step 2: Extend `src/razorback/translate.py` (Phase 1's module) to handle `SpacedockSolverV2AgentBlock`**

Add a branch in `_build_agent_config` (alongside the existing `SpacedockSolverAgentBlock` branch from Phase 1):

```python
SPACEDOCK_SOLVER_V2_IMPORT_PATH = (
    "razorback.agents.spacedock_solver_v2:SpacedockSolverAgent"
)


if isinstance(spec.agent, SpacedockSolverV2AgentBlock):
    if spec.agent.sealed_hash is None:
        raise SpecError("spacedock_solver_v2 spec must be frozen (sealed_hash missing).")
    if project_root is None:
        raise SpecError("spacedock_solver_v2 requires project_root for .env auth discovery.")
    resolution = resolve_claude_auth(project_root=project_root, home=home)
    harbor_agent_kwargs = {
        "max_turns": spec.agent.max_turns,
        "tools_allowed": list(spec.agent.tools_allowed),
        "tools_denied": list(spec.agent.tools_denied),
    }
    kwargs: dict[str, Any] = {
        "runtime": spec.agent.runtime,
        "model": spec.agent.model,
        "sampling": {
            "temperature": spec.agent.sampling.temperature,
            "top_p": spec.agent.sampling.top_p,
            "seed": spec.agent.sampling.seed,
        },
        "solver_workflow": str(spec.agent.solver_workflow),
        "solver_workflow_content_hash": spec.agent.solver_workflow_content_hash,
        "prompt_content_hashes": dict(spec.agent.prompt_content_hashes),
        "spacedock_skill_version": spec.agent.spacedock_skill_version,
        "harbor_agent_kwargs": harbor_agent_kwargs,
        "max_turns": spec.agent.max_turns,
        "tools_allowed": list(spec.agent.tools_allowed),
        "tools_denied": list(spec.agent.tools_denied),
        "resume_from_freeze": (
            str(spec.agent.resume_from_freeze) if spec.agent.resume_from_freeze else None
        ),
    }
    agent_cfg = AgentConfig(
        import_path=SPACEDOCK_SOLVER_V2_IMPORT_PATH,
        model_name=spec.agent.model,
        kwargs=kwargs,
        env=dict(resolution.env),
    )
    task_env = dict(PROXY_BLOCK_ENV)
    return agent_cfg, task_env
```

(The above lifts the v1 branch's auth + env + kwargs shape verbatim per Phase 1 Task 5; only the import_path constant and the kwargs payload change.)

- [ ] **Step 3: Create the deterministic-smoke-v2 reference spec**

`examples/specs/_deterministic-smoke-v2.frozen.yaml`, a frozen spec with `agent.kind: spacedock_solver_v2` against the in-tree DAB adapter, single-task, single-trial. Modelled on `examples/specs/_deterministic-smoke.yaml` from Phase 1's walking skeleton.

(Exact contents are derived at implementation time from the v1 `_deterministic-smoke.yaml` plus the v2 agent block; the entity's AC-1 verifier names this file by path.)

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/integration/test_v2_freeze_dir_mechanism.py -v`
Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/translate.py tests/integration/test_v2_freeze_dir_mechanism.py examples/specs/_deterministic-smoke-v2.frozen.yaml
git commit -m "$(cat <<'EOF'
Phase 3 AC-5 + AC-7: sealed_hash-keyed external freeze mechanism validated

- translator emits spacedock_solver_v2 import_path
- mechanism test: sealed_hash.txt lands at <run-dir>/_razorback/freeze/<hash>/
- harbor jobs resume round-trip: new trial_name reads same freeze tree
- riskiest b5 contract validated BEFORE bookreview-claude (Task 7)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Claude runtime smoke + halt-resume integration test (AC-5 + AC-6)

**Files:**
- Create: `tests/integration/test_v2_bookreview_claude_smoke.py`
- Create: `tests/integration/test_v2_halt_resume_handfaked.py`

**Spec cite:** Entity AC-5 (lines 83-91), AC-6 (lines 93-102). `b5` "Lifecycle" table second + fourth rows (cross-job and in-place resume).

**Why this lands AFTER Task 6:** Per "Validating new mechanisms" + dispatch checklist item 3, the riskiest contract (sealed_hash-keyed freeze read/write) is mechanism-validated in Task 6 with a stub environment. Task 7 invests in the comprehensive bookreview-claude run only after Task 6's mechanism check passes. If Task 6 fails, Task 7's failure mode is ambiguous (claude integration issue? freeze-dir resolver issue?); the ordering forces unambiguous diagnosis.

- [ ] **Step 1: Write the failing bookreview-claude smoke**

Create `tests/integration/test_v2_bookreview_claude_smoke.py` that:

1. Loads a bookreview-claude v2 spec (`examples/specs/bookreview-spacedock-v2.yaml`, created at implementation time from `examples/specs/bookreview-claude.yaml` with the v2 agent block).
2. Runs `uv run rk run <frozen-spec>` via subprocess (single-task, single-trial).
3. Asserts: exit code 0; harbor run-dir exists at the expected `jobs_dir`; `<run-dir>/_razorback/freeze/<sealed_hash>/sealed_hash.txt` exists with the matching hash; the inner `claude_code` agent received `max_turns`, `allowed_tools`, `disallowed_tools` per Task 3's mapping (verify by instrumentation: harbor's run-dir contains the `claude` argv in its event log).

The test is `@pytest.mark.real_anthropic` (or whatever marker the project uses for live-API tests; check `tests/integration/test_rk_run_bookreview_claude.py` at implementation time).

- [ ] **Step 2: Write the failing halt-resume integration test**

Create `tests/integration/test_v2_halt_resume_handfaked.py`:

1. Run a single trial with a max-turn cap that halts mid-workflow (or simulate halt by killing the process).
2. Hand-fake the workspace snapshots and `sealed_hash.txt` that the workflow's freeze mod would otherwise produce. Per entity AC-6: "the test harness writes the workspace snapshots and `sealed_hash.txt` the freeze-mod would otherwise produce".
3. Construct a resume spec that points `resume_from_freeze: <freeze_dir>` at the hand-faked freeze.
4. Run `uv run rk run <resume-spec>`; assert exit 0 and a non-degraded `summary.json` at the trial dir.
5. Perturb each sealed input in the resume spec (model, sampling, solver_workflow_content_hash, prompt_content_hashes, spacedock_skill_version, harbor_agent_kwargs) and assert `rk run` exits 20 (`SeedMismatchError`) on each.

- [ ] **Step 3: Run both tests; expect PASS once the wiring is correct**

Run: `uv run pytest tests/integration/test_v2_bookreview_claude_smoke.py tests/integration/test_v2_halt_resume_handfaked.py -v -m real_anthropic`
Expected: All PASS. If `bookreview-claude` is gated on real API access, the test runs only in CI with credentials; document the marker per the existing convention.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_v2_bookreview_claude_smoke.py tests/integration/test_v2_halt_resume_handfaked.py examples/specs/bookreview-spacedock-v2.yaml
git commit -m "Phase 3 AC-5 + AC-6: bookreview-claude smoke + halt-resume hand-faked integration"
```

---

## Task 8: Walking-skeleton AC-1: deterministic-smoke against both v1 and v2 (AC-1)

**Files:**
- Create: `tests/integration/test_v2_deterministic_smoke.py`

**Spec cite:** Entity AC-1 (lines 41-47). Phase 1's deterministic-smoke pattern: `phase1-rk-run-v2-wrapper.md` Task 9 (lines 1252-1353).

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_v2_deterministic_smoke.py` that runs `uv run rk run examples/specs/_deterministic-smoke-v2.frozen.yaml` and asserts exit 0 + the recorded pass/fail outcome (matching the in-tree DAB adapter's deterministic micro-spec; reuse the AC-0.1(b) reference outcome from `docs/superpowers/plans/2026-05-19-reconciliation-baseline.md`).

The same test runs the v1 deterministic smoke (`examples/specs/_deterministic-smoke.yaml` with `agent.kind: spacedock-solver`) for AC-1's "v1-agent × in-tree adapter" claim.

- [ ] **Step 2: Run; expect PASS**

Run: `uv run pytest tests/integration/test_v2_deterministic_smoke.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_v2_deterministic_smoke.py
git commit -m "Phase 3 AC-1: walking skeleton holds (v1 × in-tree DAB and v2 × in-tree DAB)"
```

---

## Task 9: V1 regression (AC-8)

**Files:**
- Create: `tests/integration/test_v1_spacedock_solver_regression.py`

**Spec cite:** Entity AC-8 (lines 114-119).

- [ ] **Step 1: Write the regression test**

A spec with `agent.kind: spacedock-solver` (v1 routing) against the in-tree DAB adapter still runs end-to-end and produces the recorded Phase 1 output. Sourced from `tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py` if it still passes at the worktree branch tip; otherwise lift the smaller `test_spacedock_seed_mismatch` shape.

- [ ] **Step 2: Run; expect PASS**

Run: `uv run pytest tests/integration/test_v1_spacedock_solver_regression.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_v1_spacedock_solver_regression.py
git commit -m "Phase 3 AC-8: v1 SpacedockSolverAgent still functional under kind: spacedock-solver"
```

---

## Task 10: `uv run pytest` exits 0 sweep (AC-9)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest`
Expected: 0 failures from a clean checkout of the worktree branch tip.

- [ ] **Step 2: If any test fails that is unrelated to Phase 3, raise to FO via SendMessage rather than fixing in this entity**

Per the entity's "Out of scope", fixes for unrelated test failures belong in their own entity.

- [ ] **Step 3: Commit (only if `uv.lock` or other tracked files changed during the sweep)**

```bash
git add uv.lock
git commit -m "Phase 3 AC-9: uv run pytest exits 0 from worktree branch tip"
```

(Skip the commit if there are no changes; AC-9's evidence is the clean test output cited in the stage report.)

---

## Self-review (run after all tasks drafted, before signaling completion)

**1. AC coverage.** Each entity AC maps 1:1 to a task or task subset:

- AC-1 → Task 8.
- AC-2 → Tasks 1 + 2 + 4 (sealed-hash core; class constructor; schema discriminator).
- AC-3 → Task 3 (per-runtime adapter sub-modules).
- AC-4 → Task 2 (KEEP-VERBATIM extractions cited in commit message).
- AC-5 → Tasks 6 + 7 (mechanism check + bookreview-claude smoke).
- AC-6 → Tasks 5 + 7 (lifecycle wiring + hand-faked halt-resume integration).
- AC-7 → Tasks 4 + 6 (schema discriminator + translator routing).
- AC-8 → Task 9 (v1 regression).
- AC-9 → Task 10 (pytest sweep).

**2. b5 consumption verbatim, not re-derivation.** The 5-point contract from `b5` plan lines 58-66 lands as the class shape in Tasks 1 + 2 + 5:

- Point 1 (compute sealed_hash from six inputs) → Task 1's `compute_sealed_hash` extension + Task 2's `__init__` invocation.
- Point 2 (resolve freeze dir as `Path(self.logs_dir).parent.parent.parent / "_razorback" / "freeze" / self.sealed_hash`) → Task 5's `resolve_freeze_dir()` + `_resolve_run_dir_from_logs_dir()`; Task 6's mechanism check validates the path against harbor's actual layout.
- Point 3 (create + `git init` on first stage) → Task 5's `setup()` first-stage branch.
- Point 4 (write `sealed_hash.txt`; `SeedMismatchError` on mismatch) → Task 2 (in `__init__` for cross-job `resume_from_freeze`) + Task 5 (in `setup()` for in-place harbor-resume).
- Point 5 (razorback never writes inside `trials/<name>/agent/`) → Task 6's mechanism check asserts the freeze path's relative location excludes `trials/`.

**3. Halt-resume lifecycle coverage (dispatch checklist item 2).** The six states named in Task 5's lifecycle table all have file:line targets:

- First stage of first run → `spacedock_solver_v2.setup()` first-stage branch (Task 5 Step 2).
- Every stage commit → `_commit_stage()` helper exposed via env path (Task 5; the workflow mod calls it, hand-faked in Task 7).
- harbor jobs resume on incomplete trial → Task 5's `setup()` existing-freeze branch + Task 6 mechanism test.
- Cross-job resume_from_freeze → Task 2's `_refuse_on_resume_mismatch` + Task 5's `setup()` restore.
- Done → freeze tree stays in place; no GC (b5 line 54).
- GC → out of scope.

**4. Riskiest-contract-first ordering (dispatch checklist item 3).** Tasks 1 → 2 → 3 → 4 → 5 establish the class shape with unit-level testing. **Task 6 (sealed_hash-keyed freeze read/write mechanism)** lands BEFORE Task 7 (halt-resume orchestration + bookreview-claude end-to-end). The mechanism check uses the smallest end-to-end exercise (a stub environment, hand-faked trial layout, `setup()` invoked, file system inspected); Task 7's comprehensive runs land only after the mechanism is validated. This matches CL's "Validating new mechanisms" rule.

**5. No backwards-compatibility hacks.** v1's `SpacedockSolverAgent` stays in place under `agent.kind: spacedock-solver` (AC-8); v2 ships under the new discriminator `agent.kind: spacedock_solver_v2`. Phase 6 promotes v2 to canonical via a separate entity (named in Out of scope). No `_legacy/` shim is needed for v2, v1 was not deprecated by this phase.

**6. File:line targets present for every task.** Tasks reference:

- `src/razorback/agents/seal.py:18-41` (KEEP mechanism, ADAPT signature), Task 1.
- `src/razorback/agents/spacedock_solver.py:80-86` + `:91-128` + `:25-37` + `:76-79` (KEEP-VERBATIM extractions), Task 2.
- `src/razorback/agents/spacedock_solver.py:180-206` (setup pattern; ADAPT into claude sub-module), Task 3.
- `src/razorback/spec/schema.py:31-65` (extend with v2 block), Task 4.
- `src/razorback/translate.py` (Phase 1 module; new branch), Task 6.

**7. Em-dashes scan.** This plan uses commas, periods, and parentheses; em-dashes (`,`) appear only in citations to b5 / inventory / spec where the source text already contains them. Per commit `a2e9c49`'s discipline, no em-dashes in this plan's own prose. (One sweep at implementation time: `grep -n "," docs/razorback-implementation/plans/phase3-spacedock-solver-v2.md` should return only quote / citation lines.)

---

## Execution handoff

Plan complete and saved to `docs/razorback-implementation/plans/phase3-spacedock-solver-v2.md`. The 10 tasks span:

- 1 module extension (`seal.py`)
- 1 new class module (`spacedock_solver_v2.py`)
- 1 new sub-package (`agents/_runtime/`)
- 1 schema discriminator addition (`spec/schema.py`)
- 1 translator branch (Phase 1's `translate.py`)
- 1 new reference spec (`examples/specs/_deterministic-smoke-v2.frozen.yaml`)
- ~6 new test files (5 unit, 4 integration) covering all 9 ACs

Recommended execution mode at implementation stage: **`superpowers:executing-plans`** (single fresh dispatch executes all 10 tasks sequentially, since each task's failing test gates the next; the riskiest-contract-first ordering is enforced by Task 6 preceding Task 7).

**Gating note.** The implementation stage waits on:

1. Phase 1 (`e3 phase1-rk-run-v2-wrapper`) completing far enough that `src/razorback/translate.py` exists with the SpacedockSolverAgent branch, Phase 3's Task 6 extends it with a v2 branch alongside the v1 branch.
2. The `SpacedockSolverV2AgentBlock` schema landing in `src/razorback/spec/schema.py` (Task 4 here, but the schema can land in parallel with Phase 1's translator without coupling).

The plan stage (this document) is non-worktree and writes only to `docs/razorback-implementation/plans/phase3-spacedock-solver-v2.md` on `main`; the implementation stage opens a worktree at `.worktrees/spacedock-ensign-phase3-spacedock-solver-v2/` per FO convention.
