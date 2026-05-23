# Phase 6 Follow-Up: Clean Canonical Spacedock Names Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove active internal `V2` / `v2` / `spacedock_solver_v2` naming from the canonical Spacedock solver surface while preserving behavior.

**Architecture:** This is a naming cleanup, not a routing change. Keep the canonical API as `agent.kind: spacedock_solver` and `razorback.agents.spacedock_solver:SpacedockSolverAgent`; rename internal schema/helper/test/example names around that surface, and leave only explicitly historical rejection assertions.

**Tech Stack:** Python 3, Pydantic discriminated unions, Harbor `AgentConfig.import_path`, Typer CLI, pytest, ripgrep validation.

---

## Plan Size Decision

Use this separate plan doc. The entity has only three ACs, but the inventory crosses multiple active subsystems: spec schema, freeze/provenance stamping, translation, agent/runtime comments, unit and integration test names, example smoke specs, root README prose, and active workflow backlog docs.

## Source of Truth

- v2 spec: `docs/superpowers/specs/2026-05-19-razorback-on-harbor.md`
- Relevant cites: spec §4.1-§4.5 for the single `SpacedockSolverAgent` runtime adapter and Harbor import-path dispatch; spec §6.2 for `agent.kind: spacedock_solver`; spec §8.1 for translation; spec §8.2 for freeze/provenance; spec §8.4 for runtime adaptation.
- Predecessor validation: `docs/razorback-implementation/validation/phase6-promote-v2-canonical.md`

## AC to Task Map

| AC | Tasks | Validation |
|---|---|---|
| AC-1 - Active code uses canonical Spacedock solver names | Tasks 1-5 | `rg -n "V2|v2|spacedock_solver_v2" src/razorback tests examples --glob '!**/_legacy/**'` shows only the intentionally historical stale-discriminator assertions |
| AC-2 - Behavior is unchanged | Tasks 1-4, 6 | Required focused suite plus renamed helper/example-generator tests pass |
| AC-3 - Docs distinguish history from active API | Tasks 5-6 | Root README/AGENTS are canonical; validation report lists any remaining historical doc hits with rationale |

## Inventory Classification

Current active-code grep command:

```bash
rg -n "V2|v2|spacedock_solver_v2" src/razorback tests examples --glob '!**/_legacy/**'
```

Cleanup targets:

- `src/razorback/spec/schema.py`: `SpacedockSolverV2AgentBlock` is now the canonical schema class and should become `SpacedockSolverAgentBlock`.
- `src/razorback/spec/freeze.py`: `SpacedockSolverV2AgentBlock`, `_freeze_spacedock_v2`, and v2 docstrings/comments should use canonical solver wording.
- `src/razorback/spec/agent_kwargs.py`: `build_v2_harbor_agent_kwargs` should become `build_spacedock_harbor_agent_kwargs`.
- `src/razorback/translate.py`: imports and `isinstance` checks should use `SpacedockSolverAgentBlock`; helper import should use `build_spacedock_harbor_agent_kwargs`.
- `src/razorback/provenance/freeze_cmd.py`: `_stamp_v2_sealed_fields` and v2 comments should become canonical Spacedock sealed-field wording.
- `src/razorback/agents/spacedock_solver.py`, `src/razorback/agents/seal.py`, and `src/razorback/agents/_runtime/*.py`: comments/docstrings/local variables should stop describing the current route as v2.
- Tests whose assertions remain active should be renamed from v2 language to canonical language, including `test_seal_v2_six_inputs.py`, `test_rk_run_v2_*`, `test_v2_deterministic_smoke_runs_end_to_end`, and function names such as `test_known_v2_sealed_hash_value_is_stable`.
- Example smoke specs `_codex-smoke-v2.*` and `_deterministic-smoke-v2.frozen.yaml` should be renamed to canonical smoke names or removed if superseded.
- Root `README.md` currently names `spacedock_solver_v2` as the active wrapper and should name `spacedock_solver`.
- Active backlog docs with actionable stale `spacedock_solver_v2` instructions, especially Goal 3, Goal 4, PKG-22, and `spacedock-v2-freeze-cas-container-visibility`, should be updated to canonical `spacedock_solver` if they are not already implementation-owned.

Intentional historical assertions:

- `tests/unit/test_spec_schema_spacedock_solver.py` and `tests/unit/test_spacedock_registry.py` must keep one stale-discriminator check for `"spacedock_" + "solver_v2"` because Phase 6 requires the historical route to reject. Rename the test names/comments to "transitional" or "stale discriminator" and add a one-line rationale beside the constructed string.
- `_legacy/` hits are outside AC-1's grep by design.
- Historical docs under `docs/razorback-implementation/_archive/`, `docs/razorback-implementation/validation/`, `docs/razorback-implementation/_debriefs/`, `docs/razorback-implementation/_evidence/`, and older plan docs may keep `v2` / `spacedock_solver_v2` when recounting pre-Phase-6 state. The validation report must list the remaining classes of hits and why they are historical, not active API.
- Generic references to the "v2 spec" or "v2 release" in workflow docs are release/spec labels, not Spacedock solver API names. Leave them with validation rationale unless the local sentence claims `spacedock_solver_v2` is current.

## Task 1: Rename the Canonical Schema Class

**Spec cites:** spec §4.2, §6.2, §8.1.

**Files:**
- Modify: `tests/unit/test_spec_schema_spacedock_solver.py`
- Modify: `src/razorback/spec/schema.py`
- Modify: `src/razorback/spec/freeze.py`
- Modify: `src/razorback/translate.py`

- [ ] **Step 1: Make the schema test expect the canonical class name**

Change the import and surviving assertions in `tests/unit/test_spec_schema_spacedock_solver.py`:

```python
from razorback.spec.schema import SpacedockSolverAgentBlock


def test_spacedock_solver_block_parses(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")
    block = SpacedockSolverAgentBlock(
        kind="spacedock_solver",
        runtime="claude",
        model="claude-opus-4-5",
        solver_workflow=workflow,
        max_turns=200,
        max_budget_usd=10,
        tools_allowed=[],
        tools_denied=[],
    )
    assert block.runtime == "claude"
    assert block.kind == "spacedock_solver"
```

Also update the final type assertion:

```python
assert isinstance(spec.agent, SpacedockSolverAgentBlock)
```

- [ ] **Step 2: Run the focused schema test and confirm RED**

Run:

```bash
uv run pytest tests/unit/test_spec_schema_spacedock_solver.py -q
```

Expected before production rename: import failure for `SpacedockSolverAgentBlock`.

- [ ] **Step 3: Rename the production schema class**

In `src/razorback/spec/schema.py`, rename the class and union member:

```python
class SpacedockSolverAgentBlock(BaseModel):
    """Spec-level agent block for canonical spacedock_solver (spec §6.2 + §4)."""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["spacedock_solver"]
    runtime: Literal["claude", "codex", "pi"] = "claude"
    model: str = "claude-opus-4-5"
    sampling: SamplingBlock = Field(default_factory=SamplingBlock)
    solver_workflow: Path
    solver_workflow_content_hash: str | None = None
    max_turns: int = 200
    max_budget_usd: float | None = None
    tools_allowed: list[str] = Field(default_factory=list)
    tools_denied: list[str] = Field(default_factory=list)
    append_system_prompt: str | None = None
    reasoning_effort: str | None = None
    reasoning_summary: str | None = None
    resume_from_freeze: Path | None = None
    sealed_hash: str | None = None
    spacedock_skill_version: str | None = None
    prompt_content_hashes: dict[str, str] = Field(default_factory=dict)
```

Update the union:

```python
AgentBlock = Annotated[
    Union[
        NopAgentBlock,
        ClaudeCliAgentBlock,
        SpacedockSolverAgentBlock,
    ],
    Field(discriminator="kind"),
]
```

- [ ] **Step 4: Update imports/type checks**

In `src/razorback/spec/freeze.py` and `src/razorback/translate.py`, replace `SpacedockSolverV2AgentBlock` with `SpacedockSolverAgentBlock`. The route and literal `kind: "spacedock_solver"` stay unchanged.

- [ ] **Step 5: Run the schema/routing checkpoint**

Run:

```bash
uv run pytest tests/unit/test_spec_schema_spacedock_solver.py tests/unit/test_translate_spacedock_solver_import_path.py -q
```

Expected: all selected tests pass.

## Task 2: Rename Freeze, Provenance, and Harbor-Kwarg Helpers

**Spec cites:** spec §4.3 sealed inputs, §4.5 Harbor kwargs dispatch, §8.2 freeze/provenance, §8.4 runtime adaptation.

**Files:**
- Modify: `src/razorback/spec/agent_kwargs.py`
- Modify: `src/razorback/spec/freeze.py`
- Modify: `src/razorback/provenance/freeze_cmd.py`
- Modify: `src/razorback/translate.py`
- Modify: `tests/unit/test_spec_freeze_cli_pkg8.py` only if it imports renamed helpers directly

- [ ] **Step 1: Rename the kwarg helper**

In `src/razorback/spec/agent_kwargs.py`:

```python
def build_spacedock_harbor_agent_kwargs(
    *,
    max_turns: int | None,
    tools_allowed: list[str] | None,
    tools_denied: list[str] | None,
    append_system_prompt: str | None = None,
    reasoning_effort: str | None = None,
    reasoning_summary: str | None = None,
) -> dict[str, Any]:
```

Update imports and call sites in `src/razorback/translate.py`, `src/razorback/spec/freeze.py`, and `src/razorback/provenance/freeze_cmd.py`.

- [ ] **Step 2: Rename freeze helpers**

In `src/razorback/spec/freeze.py`, use canonical names:

```python
if isinstance(spec.agent, SpacedockSolverAgentBlock):
    _freeze_spacedock_solver(payload["agent"], spec.agent.solver_workflow)


def _freeze_spacedock_solver(agent_block: dict, solver_workflow: Path) -> None:
    """Compute solver_workflow_content_hash + sealed_hash for spacedock_solver."""
```

- [ ] **Step 3: Rename provenance stamping helpers**

In `src/razorback/provenance/freeze_cmd.py`, use:

```python
_stamp_spacedock_solver_sealed_fields(
    frozen_body,
    solver_workflow_hash=solver_workflow_hash,
)


def _stamp_spacedock_solver_sealed_fields(
    frozen_body: dict[str, Any],
    *,
    solver_workflow_hash: str | None,
) -> None:
```

- [ ] **Step 4: Run the freeze/provenance checkpoint**

Run:

```bash
uv run pytest tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_translate_spacedock_solver_import_path.py -q
```

Expected: all selected tests pass and frozen specs still carry the same sealed fields.

## Task 3: Rename Agent, Seal, and Runtime Current-Contract Language

**Spec cites:** spec §4.1, §4.3, §8.4.

**Files:**
- Modify: `src/razorback/agents/spacedock_solver.py`
- Modify: `src/razorback/agents/seal.py`
- Modify: `src/razorback/agents/_runtime/__init__.py`
- Modify: `src/razorback/agents/_runtime/claude.py`
- Modify: `src/razorback/agents/_runtime/codex.py`
- Modify: `tests/unit/test_spacedock_solver_class.py`
- Rename: `tests/unit/test_seal_v2_six_inputs.py` -> `tests/unit/test_seal_canonical_six_inputs.py`

- [ ] **Step 1: Update the public comments without changing executable code**

Replace active "v2" wording with canonical wording. Examples:

```python
# ABOUTME: SpacedockSolverAgent canonical runtime adapter for claude|codex|pi.
```

```python
class SpacedockSolverAgentError(RazorbackError):
    """Raised on SpacedockSolverAgent contract violations."""
```

- [ ] **Step 2: Rename seal-shape locals**

In `src/razorback/agents/seal.py`, keep behavior unchanged but rename local concepts:

```python
legacy_shape = stages is not None or prompt_hashes is not None
canonical_shape = (
    solver_workflow_content_hash is not None
    or prompt_content_hashes is not None
    or spacedock_skill_version is not None
    or harbor_agent_kwargs is not None
)
if legacy_shape and canonical_shape:
    raise TypeError(
        "compute_sealed_hash: legacy (stages/prompt_hashes) and canonical "
        "(solver_workflow_content_hash/prompt_content_hashes/"
        "spacedock_skill_version/harbor_agent_kwargs) inputs are exclusive."
    )
if canonical_shape:
```

- [ ] **Step 3: Rename the sealed-hash test file and test names**

Use `git mv`:

```bash
git mv tests/unit/test_seal_v2_six_inputs.py tests/unit/test_seal_canonical_six_inputs.py
```

In that file, change ABOUTME prose to "canonical six sealed inputs" and keep the same assertions. In `tests/unit/test_spacedock_solver_class.py`, rename:

```python
def test_known_canonical_sealed_hash_value_is_stable(tmp_path):
```

- [ ] **Step 4: Run the agent/seal checkpoint**

Run:

```bash
uv run pytest tests/unit/test_seal_canonical_six_inputs.py tests/unit/test_spacedock_solver_class.py tests/unit/test_spacedock_solver_lifecycle.py tests/unit/test_runtime_adapters.py -q
```

Expected: all selected tests pass.

## Task 4: Rename Active Smoke Examples and Example Tests

**Spec cites:** spec §6.2, §8.1.

**Files:**
- Rename: `examples/specs/_codex-smoke-v2.yaml` -> `examples/specs/_codex-smoke.yaml`
- Rename: `examples/specs/_codex-smoke-v2.frozen.yaml` -> `examples/specs/_codex-smoke.frozen.yaml`
- Rename or regenerate: `examples/specs/_deterministic-smoke-v2.frozen.yaml` -> `examples/specs/_deterministic-smoke.frozen.yaml`
- Modify: `tests/integration/test_spacedock_solver_deterministic_smoke.py`
- Modify: `tests/unit/test_codex_benchmark_spec_generator.py`
- Modify: `tests/integration/test_spacedock_solver_freeze_dir_mechanism.py`

- [ ] **Step 1: Rename smoke spec files**

Use `git mv` for checked-in files. Update `experiment:` values and comments from `_codex-smoke-v2` / `_deterministic-smoke-v2` to `_codex-smoke` / `_deterministic-smoke` while keeping `agent.kind: spacedock_solver`.

- [ ] **Step 2: Refresh frozen specs through the public freeze path**

Run:

```bash
uv run rk freeze examples/specs/_codex-smoke.yaml --out examples/specs/_codex-smoke.frozen.yaml --allow-missing
uv run rk freeze examples/specs/_deterministic-smoke.yaml --out examples/specs/_deterministic-smoke.frozen.yaml --allow-missing
```

Expected: both commands exit 0 and the frozen files still contain `agent.kind: spacedock_solver`.

- [ ] **Step 3: Update integration smoke references**

In `tests/integration/test_spacedock_solver_deterministic_smoke.py`, update:

```python
SPEC = REPO / "examples" / "specs" / "_deterministic-smoke.frozen.yaml"
```

Rename the test:

```python
def test_canonical_deterministic_smoke_runs_end_to_end(tmp_path: Path):
```

Update the expected experiment dir:

```python
experiment_dir = runs_root / "_deterministic-smoke"
```

- [ ] **Step 4: Update example-generator test names/comments**

In `tests/unit/test_codex_benchmark_spec_generator.py`, rename:

```python
def test_emit_dab_codex_spec_uses_canonical_codex_solver_and_harbor_dab(tmp_path: Path) -> None:
```

Keep the assertion:

```python
assert payload["agent"]["kind"] == "spacedock_solver"
```

In `tests/integration/test_spacedock_solver_freeze_dir_mechanism.py`, rename functions that mention v2 in the current path, for example:

```python
def test_translator_mounts_canonical_freeze_root_into_container(tmp_path):
def test_translator_includes_codex_reasoning_kwargs_for_canonical_agent(tmp_path):
```

- [ ] **Step 5: Run the example checkpoint**

Run:

```bash
uv run pytest tests/unit/test_codex_benchmark_spec_generator.py tests/integration/test_spacedock_solver_deterministic_smoke.py tests/integration/test_spacedock_solver_freeze_dir_mechanism.py -q
```

Expected: unit/mechanism tests pass; live-gated smoke may skip unless Docker/API env is set.

## Task 5: Clean Active Docs and Preserve Historical Assertions

**Spec cites:** spec §4.2, §4.5, §6.2.

**Files:**
- Modify: `README.md`
- Modify only if still backlog/plan and not owned by another worker: `docs/razorback-implementation/goal3-dab-codex-full-dataset-1x-score.md`
- Modify only if still backlog/plan and not owned by another worker: `docs/razorback-implementation/goal4-ade-bench-codex-full-dataset-1x-score.md`
- Modify only if still backlog/plan and not owned by another worker: `docs/razorback-implementation/pkg22-provenance-writer-claude-cli-kind.md`
- Modify only if still backlog/plan and not owned by another worker: `docs/razorback-implementation/spacedock-v2-freeze-cas-container-visibility.md`
- Modify: `tests/unit/test_spec_schema_spacedock_solver.py`
- Modify: `tests/unit/test_spacedock_registry.py`

- [ ] **Step 1: Root README names only the canonical active API**

Replace active prose with:

```markdown
- `spacedock_solver` is the README-driven solver agent wrapper for
  runtime adapters such as Claude and Codex.
```

Replace current-direction prose with:

```markdown
The active goal is to produce N=1 full-dataset benchmark numbers for
DAB and ade-bench using Codex. The first dependency is the Codex
runtime adapter for `spacedock_solver`; DAB and ade-bench score
matrices build on that surface.
```

- [ ] **Step 2: Update active backlog ACs that instruct future agents to use stale names**

For Goal 3 and Goal 4 AC-1, replace `agent.kind: spacedock_solver_v2` with `agent.kind: spacedock_solver`.

For PKG-22, replace stale "kind != spacedock_solver_v2" and cross-kind examples with canonical `spacedock_solver`; if a sentence is specifically recounting the 2026-05-20 observation, append "(historical spelling at the time; canonical now `spacedock_solver`)".

For `spacedock-v2-freeze-cas-container-visibility`, update the problem and AC text to say `spacedock_solver`. The title may keep "v2" only if the entity is about release-era freeze CAS, not the agent kind.

- [ ] **Step 3: Make stale-discriminator tests self-identifying**

In `tests/unit/test_spec_schema_spacedock_solver.py` and `tests/unit/test_spacedock_registry.py`, keep the constructed stale kind but add a rationale:

```python
stale_kind = "spacedock_" + "solver_v2"  # intentional historical rejection assertion
```

Rename test functions from "v2 spelling" to "transitional spelling" so the only remaining `v2` grep hit in tests is the intentional stale string.

- [ ] **Step 4: Run doc and historical-assertion greps**

Run:

```bash
rg -n "spacedock_solver_v2" README.md AGENTS.md docs/razorback-implementation \
  --glob '!docs/razorback-implementation/_archive/**' \
  --glob '!docs/razorback-implementation/validation/**' \
  --glob '!docs/razorback-implementation/plans/**' \
  --glob '!docs/razorback-implementation/_debriefs/**' \
  --glob '!docs/razorback-implementation/_evidence/**'
```

Expected: no active API hits. If any done/backlog historical hit remains, record the exact file and rationale in the validation report.

## Task 6: Final Focused Validation and Report

**Spec cites:** spec §4.5, §6.2, §8.1, §8.2, §8.4.

**Files:**
- Modify/create: `docs/razorback-implementation/validation/phase6-followup-clean-canonical-spacedock-names.md`

- [ ] **Step 1: Run the required AC-1 grep**

Run:

```bash
rg -n "V2|v2|spacedock_solver_v2" src/razorback tests examples --glob '!**/_legacy/**'
```

Expected: only intentional historical assertions. The report must list each remaining line and classify it as either stale-discriminator rejection or a failure to fix.

- [ ] **Step 2: Run the required AC-2 focused suite**

Run exactly:

```bash
uv run pytest tests/unit/test_spec_schema_spacedock_solver.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_spacedock_solver_class.py tests/unit/test_spacedock_solver_lifecycle.py tests/unit/test_runtime_adapters.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run the renamed/supporting focused suite**

Run:

```bash
uv run pytest tests/unit/test_seal_canonical_six_inputs.py tests/unit/test_spacedock_registry.py tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_codex_benchmark_spec_generator.py tests/integration/test_spacedock_solver_freeze_dir_mechanism.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run active-doc grep and write rationale**

Run:

```bash
rg -n "V2|v2|spacedock_solver_v2" README.md AGENTS.md docs/razorback-implementation \
  --glob '!docs/razorback-implementation/_archive/**' \
  --glob '!docs/razorback-implementation/validation/**' \
  --glob '!docs/razorback-implementation/plans/**'
```

Expected: `README.md` and `AGENTS.md` have no stale `spacedock_solver_v2`; remaining workflow `v2` hits are either generic "v2 spec/release" references or explicitly historical stage records. The validation report must include the rationale for each remaining class of hit.

- [ ] **Step 5: Commit implementation**

Run `git status --short` and add only files changed for this entity. The expected
path set is:

```bash
git add \
  README.md \
  docs/razorback-implementation/goal3-dab-codex-full-dataset-1x-score.md \
  docs/razorback-implementation/goal4-ade-bench-codex-full-dataset-1x-score.md \
  docs/razorback-implementation/pkg22-provenance-writer-claude-cli-kind.md \
  docs/razorback-implementation/spacedock-v2-freeze-cas-container-visibility.md \
  docs/razorback-implementation/validation/phase6-followup-clean-canonical-spacedock-names.md \
  src/razorback/spec/schema.py \
  src/razorback/spec/freeze.py \
  src/razorback/spec/agent_kwargs.py \
  src/razorback/translate.py \
  src/razorback/provenance/freeze_cmd.py \
  src/razorback/agents/spacedock_solver.py \
  src/razorback/agents/seal.py \
  src/razorback/agents/_runtime/__init__.py \
  src/razorback/agents/_runtime/claude.py \
  src/razorback/agents/_runtime/codex.py \
  tests/unit/test_spec_schema_spacedock_solver.py \
  tests/unit/test_translate_spacedock_solver_import_path.py \
  tests/unit/test_spacedock_solver_class.py \
  tests/unit/test_spacedock_solver_lifecycle.py \
  tests/unit/test_runtime_adapters.py \
  tests/unit/test_spacedock_registry.py \
  tests/unit/test_spec_freeze_cli_pkg8.py \
  tests/unit/test_codex_benchmark_spec_generator.py \
  tests/unit/test_seal_canonical_six_inputs.py \
  tests/integration/test_spacedock_solver_deterministic_smoke.py \
  tests/integration/test_spacedock_solver_freeze_dir_mechanism.py \
  examples/specs/_codex-smoke.yaml \
  examples/specs/_codex-smoke.frozen.yaml \
  examples/specs/_deterministic-smoke.frozen.yaml
git add -u \
  examples/specs/_codex-smoke-v2.yaml \
  examples/specs/_codex-smoke-v2.frozen.yaml \
  examples/specs/_deterministic-smoke-v2.frozen.yaml \
  tests/unit/test_seal_v2_six_inputs.py
git commit -m "phase6 followup: clean canonical spacedock names"
```

## Final Acceptance Checklist for Implementer

- [ ] `SpacedockSolverV2AgentBlock`, `build_v2_harbor_agent_kwargs`, `_freeze_spacedock_v2`, and `_stamp_v2_sealed_fields` no longer exist in active code.
- [ ] Active tests and examples avoid `v2` naming except the explicit stale-discriminator rejection string.
- [ ] `README.md` and `AGENTS.md` name `spacedock_solver`, not `spacedock_solver_v2`.
- [ ] Required AC-2 pytest command passes exactly as written.
- [ ] Validation report includes the AC-1 grep output and a rationale for all remaining historical/documentation hits.
