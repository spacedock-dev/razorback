# Retire v1 SpacedockSolverAgent + rename v2 to spacedock — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the dormant v1 `SpacedockSolverAgent` surface (zero production callers) and rename the v2 canonical agent — class, file, kind name, schema literal, pydantic block — to plain `spacedock`, eliminating the `_v2` suffix everywhere and consolidating dispatch into one `_REGISTRY` entry.

**Architecture:** Clean cut, no rollback alias, no kind aliasing (captain decision). The cut is sequenced so the test suite stays green at every commit boundary, not just at the end. Pivot point is the schema `Literal` rename — that single change forces every downstream artifact (parser, specs, freeze cmd, translate) to be consistent on the new name within the same commit. v1 deletion happens first (it has no production callers and its only integration test is already failing on main, so deleting it strictly reduces noise). The v2→spacedock rename then proceeds as a single coherent commit because partial rename leaves the schema in an inconsistent state.

**Tech Stack:** Python 3.12, pydantic v2 discriminated unions, `uv` for venv, `pytest -m 'not integration'` for the AC-4 gate, `git mv` for history-preserving renames.

---

## AC ↔ Task map

| AC | Tasks |
|---|---|
| AC-1 — v1 surface deleted | T1 |
| AC-2 — v2 renamed to spacedock (file, class, kind, block, literal, runtime docstrings) | T2, T3, T4, T5, T6 |
| AC-3 — dual dispatch eliminated (translate.py constants gone, `_REGISTRY["spacedock"]` added) | T4, T7 |
| AC-4 — green main (`pytest -m 'not integration'` exit 0) | T8 |

Supersession housekeeping (phase6 + phase7 archive moves) handled in T9.

---

## Grep set the implementation worker must verify

The entity spec lists verification greps. Run each before starting (baseline) and after T1 / after T7 (must match expected post-state). Counts below are from the pre-implementation main HEAD.

**AC-1 verification greps (must return 0 after T1):**

```bash
# v1 kind name in active code
grep -rn "kind: spacedock-solver" src/ tests/ examples/ packages/
# baseline: 15 hits

# v1 import path (space-or-EOL boundary so spacedock_solver_v2 doesn't match)
grep -rEn "from razorback.agents.spacedock_solver( |$)" src/ tests/ examples/ packages/
# baseline: 9 hits

# _legacy holding tank
grep -rn "razorback._legacy" src/ tests/ examples/ packages/
# baseline: 1 hit
```

**AC-2 verification greps (must return 0 after T7):**

```bash
# v2 kind literal across production code (excludes docs/ which carry historical refs)
grep -rn "spacedock_solver_v2" src/ tests/ examples/ packages/ \
  --include='*.py' --include='*.yaml' --include='*.yml' --include='*.md'
# baseline: 72 hits across 41 files

# v2 class / pydantic block name
grep -rn "SpacedockSolverV2" src/ tests/ examples/ packages/ \
  --include='*.py' --include='*.yaml' --include='*.yml' --include='*.md'
# baseline: 10 hits
```

**AC-3 verification greps (must return 0 / 1 after T7):**

```bash
grep -n "SPACEDOCK_SOLVER" src/razorback/translate.py            # → 0 hits
grep -n '"spacedock"' src/razorback/agents/registry.py            # → ≥1 hit (the new entry)
```

**The 41 production files that touch the v2 kind name** (must all be touched by the rename pass — pre-computed so the worker can sanity-check completeness):

- `src/razorback/translate.py`
- `src/razorback/spec/schema.py`
- `src/razorback/spec/freeze.py`
- `src/razorback/provenance/freeze_cmd.py`
- `src/razorback/agents/_runtime/claude.py`
- `src/razorback/agents/_runtime/codex.py`
- `src/razorback/agents/_runtime/__init__.py` (docstring only)
- `examples/drivers/generate-codex-benchmark-specs.py`
- `examples/drivers/generate-dab-paper-matrix-specs.py`
- `examples/specs/_codex-smoke-v2.yaml`
- `examples/specs/_deterministic-smoke-v2.frozen.yaml`
- `examples/specs/codex-ade-bench-smoke.yaml`
- `examples/specs/codex-dab-smoke.yaml`
- `examples/specs/pkg40-ade-harbor-task-view-codex.yaml`
- `examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml`
- `examples/specs/goal1/spacedock/*.yaml` × 12
- `tests/fixtures/specs/tools_denied_live.yaml`
- `tests/integration/test_freeze_cas_resume_no_agent_invocation.py`
- `tests/integration/test_freeze_cross_worktree_discovery.py`
- `tests/integration/test_v2_deterministic_smoke.py` (also renamed)
- `tests/integration/test_v2_freeze_dir_mechanism.py` (also renamed)
- `tests/unit/test_claude_benchmark_spec_generator.py`
- `tests/unit/test_codex_benchmark_spec_generator.py`
- `tests/unit/test_generate_matrix_specs_per_variant_kind.py`
- `tests/unit/test_runtime_adapters.py`
- `tests/unit/test_spacedock_solver_v2_class.py` (also renamed)
- `tests/unit/test_spacedock_solver_v2_freeze_on_host.py` (also renamed)
- `tests/unit/test_spacedock_solver_v2_lifecycle.py` (also renamed)
- `tests/unit/test_spec_freeze_cli_pkg8.py`
- `tests/unit/test_spec_schema_spacedock_solver_v2.py` (also renamed)
- `tests/unit/test_tools_denied_claude_hook.py`
- `tests/unit/test_tools_denied_parse.py`
- `tests/unit/test_translate_spacedock_solver_import_path.py` (deleted by T1 — v1-specific)

`packages/` returns zero hits today; nothing to rename there. The `docs/` tree carries historical mentions (~50 files); those are deliberately out of scope per AC-2's "production code" wording and the entity body's "this entity's body + validation report may still cite the old names as historical reference" carveout.

---

## Ordering principle (READ THIS BEFORE STARTING)

The TL;DR for the implementer: **the test suite cannot stay green during a half-finished rename**, so the rename is a single atomic commit (T7) rather than a sequence. We CAN keep the suite green across T1 (v1 deletion), and we CAN keep it green again from T7 onward. The window between T1 and T7 is a "single rename commit" — no intermediate checkpoints inside it.

Order rationale:

1. **T1 first (v1 deletion).** v1 has zero production callers, its halt/resume integration test is already failing on main, and deleting it strictly shrinks the diff surface for the rename. After T1, the codebase has exactly one solver agent — but it's still called `spacedock_solver_v2`.
2. **T2 (registry consolidation prep).** Remove the v1 `"spacedock-solver"` entry from `_REGISTRY` and remove the `SpacedockSolverAgentConfig` class it referenced. This is a no-op for runtime behavior (nobody used it) but is mechanically a separate commit because it touches `registry.py` which is otherwise untouched by T7.
3. **T3 (delete v1 import path constants in translate.py).** Same rationale as T2: separable, mechanically distinct, simplifies the T7 diff. After T3, translate.py has only `SPACEDOCK_SOLVER_V2_IMPORT_PATH` + the v2 dispatch branch.
4. **T4 — T6 (preparation steps that don't break anything).** Add the new `_REGISTRY["spacedock"]` entry while the schema literal is still `"spacedock_solver_v2"` (the entry exists but is unreached — no spec yet declares `kind: spacedock`).
5. **T7 (atomic rename commit).** The big one. Inside ONE commit:
    - `git mv src/razorback/agents/spacedock_solver_v2.py → src/razorback/agents/spacedock.py`
    - rename the class `SpacedockSolverAgent` (the v2 one) → `SpacedockAgent` everywhere in the moved file
    - rename pydantic block `SpacedockSolverV2AgentBlock` → `SpacedockAgentBlock` in `src/razorback/spec/schema.py`
    - rename schema literal `Literal["spacedock_solver_v2"]` → `Literal["spacedock"]` in the same file
    - swap import paths in `translate.py`, `spec/freeze.py`, `provenance/freeze_cmd.py`, runtime adapters
    - swap `_REGISTRY` import_path string to `razorback.agents.spacedock:SpacedockAgent`
    - update every `kind: spacedock_solver_v2` in YAML to `kind: spacedock` (specs, fixtures, smoke files, driver scripts that emit specs)
    - `git mv` v2-named test files to spacedock-named test files
    - update runtime adapter docstrings (the 3 `_runtime/*.py` files cite "v2" in ABOUTME comments and class docstrings)
6. **T8 (re-freeze the sealed spec).** Only one production frozen spec exists today — `examples/specs/_deterministic-smoke-v2.frozen.yaml`. Inside T7 we update its `kind:` field, which invalidates its `sealed_hash`. Re-freeze it in T8 using `rk freeze` so the sealed hash matches the new content. (The 12 goal1 specs are NOT sealed today — verified by `grep -l "sealed_hash:" examples/specs/goal1/spacedock/*.yaml` returning empty — so they need only the literal text swap inside T7, no separate freeze step.)
7. **T9 (supersession housekeeping + green-main verification).** Move `phase6-promote-v2-canonical.md` and `phase7-delete-legacy.md` to `_archive/` with a one-line supersession note, then run the AC-4 gate.

This ordering means commits T1, T2, T3 are individually bisect-clean (tests still pass), the T7 commit will be the only one where you must run the suite carefully because it's the rename atomicity point, and T9 is bisect-clean trivially.

---

## File Structure

**Files deleted (T1):**

```
src/razorback/agents/spacedock_solver.py
src/razorback/_legacy/                                              # entire dir
tests/unit/test_v1_spacedock_solver_regression.py
tests/unit/test_spacedock_registry.py
tests/unit/test_translate_spacedock_solver_import_path.py
tests/unit/test_spacedock_prompt_drift.py
tests/unit/test_spacedock_tools_allowed.py
tests/unit/test_spacedock_seed_mismatch.py
tests/integration/test_spacedock_git_freeze.py
tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py
tests/fixtures/spacedock/seed-frozen-spec.yaml
tests/fixtures/spacedock/resume-mismatch-frozen-spec.yaml
examples/specs/bookreview-spacedock-seed.yaml
examples/specs/bookreview-spacedock-resume.yaml
```

**Files renamed (T7, via `git mv`):**

```
src/razorback/agents/spacedock_solver_v2.py      → src/razorback/agents/spacedock.py
tests/unit/test_spacedock_solver_v2_class.py     → tests/unit/test_spacedock_class.py
tests/unit/test_spacedock_solver_v2_lifecycle.py → tests/unit/test_spacedock_lifecycle.py
tests/unit/test_spacedock_solver_v2_freeze_on_host.py → tests/unit/test_spacedock_freeze_on_host.py
tests/unit/test_spec_schema_spacedock_solver_v2.py → tests/unit/test_spec_schema_spacedock.py
tests/integration/test_v2_deterministic_smoke.py → tests/integration/test_deterministic_smoke.py
tests/integration/test_v2_freeze_dir_mechanism.py → tests/integration/test_freeze_dir_mechanism.py
examples/specs/_codex-smoke-v2.yaml              → examples/specs/_codex-smoke.yaml
examples/specs/_deterministic-smoke-v2.frozen.yaml → examples/specs/_deterministic-smoke.frozen.yaml
```

**Files modified (in-place):** All 41 production files in the grep set above whose names do NOT change. Plus:

- `src/razorback/agents/registry.py` — remove v1 entry + config class (T2), add `"spacedock"` entry pointing at the new import path (T6, then updated in T7)
- `src/razorback/translate.py` — remove v1 dispatch branch + v1 constant (T3), remove v2 constant + flip v2 dispatch to use the new import path string (T7)

**Files supersession-moved (T9):**

```
docs/razorback-implementation/phase6-promote-v2-canonical.md → docs/razorback-implementation/_archive/
docs/razorback-implementation/phase7-delete-legacy.md         → docs/razorback-implementation/_archive/
```

---

## Task 1: Delete v1 SpacedockSolverAgent surface

**Files:**
- Delete: 13 paths listed above + `src/razorback/_legacy/` directory

This task removes a dormant agent surface. It must NOT touch any v2 code. After this commit, the `_REGISTRY` still has the `"spacedock-solver"` entry pointing at a now-missing file — that's fine because no test or production spec invokes that kind anymore (the only callers were the v1-only tests deleted in this same commit). T2 cleans up the dangling registry entry.

- [ ] **Step 1: Baseline grep**

```bash
grep -rn "kind: spacedock-solver" src/ tests/ examples/ packages/ | wc -l    # expect 15
grep -rEn "from razorback.agents.spacedock_solver( |$)" src/ tests/ examples/ packages/ | wc -l   # expect 9
grep -rn "razorback._legacy" src/ tests/ examples/ packages/ | wc -l   # expect 1
```

- [ ] **Step 2: Delete via `git rm`**

```bash
git rm src/razorback/agents/spacedock_solver.py
git rm -r src/razorback/_legacy
git rm tests/unit/test_v1_spacedock_solver_regression.py
git rm tests/unit/test_spacedock_registry.py
git rm tests/unit/test_translate_spacedock_solver_import_path.py
git rm tests/unit/test_spacedock_prompt_drift.py
git rm tests/unit/test_spacedock_tools_allowed.py
git rm tests/unit/test_spacedock_seed_mismatch.py
git rm tests/integration/test_spacedock_git_freeze.py
git rm tests/integration/test_rk_run_bookreview_spacedock_halt_resume.py
git rm tests/fixtures/spacedock/seed-frozen-spec.yaml
git rm tests/fixtures/spacedock/resume-mismatch-frozen-spec.yaml
git rm examples/specs/bookreview-spacedock-seed.yaml
git rm examples/specs/bookreview-spacedock-resume.yaml
```

If any of these files do not exist, investigate before deleting more — the entity body enumerated them off a known-good snapshot; an unexpected absence might mean a teammate already started this work.

- [ ] **Step 3: Verify the AC-1 greps return 0**

```bash
grep -rn "kind: spacedock-solver" src/ tests/ examples/ packages/      # expect: no output
grep -rEn "from razorback.agents.spacedock_solver( |$)" src/ tests/ examples/ packages/   # expect: no output
grep -rn "razorback._legacy" src/ tests/ examples/ packages/           # expect: no output
```

If any return hits, do NOT proceed — investigate. The most likely cause is a leftover reference in a file you didn't expect (e.g., a doc that lives in `_evidence/` or a generated artifact). Cite the hits and ask the FO.

- [ ] **Step 4: Run the non-integration test suite**

```bash
uv run pytest -m 'not integration' --timeout=60 -q
```

Expected: the previously-failing `test_rk_run_bookreview_spacedock_halt_resume` is now gone (it was an `-m integration` test anyway, so this gate doesn't observe it). Other tests should be unchanged in pass/fail count. The two pre-existing failures listed in AC-4 — `test_rk_run_bookreview_spacedock_halt_resume` and `test_rk_run_nop` — should both be either gone or unaffected. Pass count must not regress below pre-T1 baseline.

If a test fails that wasn't failing on main before T1, STOP. Most likely cause: a stray import of v1 in a v2 test you didn't expect. Fix the import in T1's diff scope, not as a new task.

- [ ] **Step 5: Commit**

```bash
git add -u
git commit -m "remove: v1 SpacedockSolverAgent surface (zero production callers; clean cut, no rollback alias)

Per entity retire-v1-rename-v2-to-spacedock AC-1. Deletes the v1 agent class,
its 8 tests, 4 fixture/example specs, and the _legacy/ holding tank. The v1
halt/resume integration test was already failing on main with SpecError
'spec must be frozen' (AC-3.8 contract drift). Captain decision: don't
preserve a rollback alias for v1; new repo, no old runs to migrate."
```

---

## Task 2: Drop v1 from `_REGISTRY` + remove `SpacedockSolverAgentConfig`

**Files:**
- Modify: `src/razorback/agents/registry.py`

The `_REGISTRY` still has the entry `"spacedock-solver": AgentKindEntry(SpacedockSolverAgentConfig, "razorback.agents.spacedock_solver:SpacedockSolverAgent")` which now points at a deleted module. Remove the entry AND the `SpacedockSolverAgentConfig` pydantic class above it. The config class has no remaining importers (its only user was the deleted `test_spacedock_registry.py`).

- [ ] **Step 1: Remove the registry entry and the config class**

In `src/razorback/agents/registry.py`:

- Delete the entire `SpacedockSolverAgentConfig` class (the `class SpacedockSolverAgentConfig(BaseModel): ...` block including its two validators) — currently lines ~37–64.
- Delete the `"spacedock-solver"` entry from the `_REGISTRY` dict — currently lines ~81–84.
- Delete the now-unused `_VALID_STAGES` tuple at the top of the file (only the deleted config class referenced it).

After the edit, `_REGISTRY` has exactly two entries: `"nop"` and `"claude-cli"`.

- [ ] **Step 2: Verify no other code imports `SpacedockSolverAgentConfig`**

```bash
grep -rn "SpacedockSolverAgentConfig" src/ tests/ examples/ packages/
```

Expected: no output. If anything matches, STOP and re-examine T1's deletion list — it should have caught everything.

- [ ] **Step 3: Run the test suite**

```bash
uv run pytest -m 'not integration' --timeout=60 -q
```

Expected: same pass count as end of T1. The only test that imported `SpacedockSolverAgentConfig` was `test_spacedock_registry.py`, deleted in T1.

- [ ] **Step 4: Commit**

```bash
git add src/razorback/agents/registry.py
git commit -m "registry: drop v1 spacedock-solver entry + SpacedockSolverAgentConfig

Per entity retire-v1-rename-v2-to-spacedock AC-3 prep. The entry pointed at
a module deleted in the previous commit. The pydantic config class had no
remaining importers after the v1 test bundle was removed."
```

---

## Task 3: Delete v1 dispatch path in `translate.py`

**Files:**
- Modify: `src/razorback/translate.py`

Remove the v1 hardcoded constant + the v1 dispatch branch in `_build_agent_config`. The v2 branch and the v2 constant `SPACEDOCK_SOLVER_V2_IMPORT_PATH` stay for now — those flip in T7.

- [ ] **Step 1: Edit translate.py**

In `src/razorback/translate.py`:

- Delete the constant `SPACEDOCK_SOLVER_IMPORT_PATH = (...)` at lines ~34–36.
- Delete the `if isinstance(spec.agent, SpacedockSolverAgentBlock):` branch at lines ~128–165 (the entire v1 block, ending right before the `if isinstance(spec.agent, SpacedockSolverV2AgentBlock):` line).
- Remove `SpacedockSolverAgentBlock` from the import statement at lines ~20–31 (currently imported from `razorback.spec.schema` alongside the other agent blocks).

After this edit, `translate.py` dispatches `NopAgentBlock`, `SpacedockSolverV2AgentBlock`, and `ClaudeCliAgentBlock` only.

- [ ] **Step 2: Verify v1 grep returns 0 in translate.py**

```bash
grep -n "SPACEDOCK_SOLVER_IMPORT_PATH\|SpacedockSolverAgentBlock" src/razorback/translate.py
```

Expected: no output. (`SPACEDOCK_SOLVER_V2_IMPORT_PATH` and `SpacedockSolverV2AgentBlock` still match other patterns in this file — that's fine and T7 cleans them up.)

- [ ] **Step 3: Check spec/schema.py — is `SpacedockSolverAgentBlock` still defined there?**

```bash
grep -n "class SpacedockSolverAgentBlock" src/razorback/spec/schema.py
```

If it's defined, the schema still has a v1 pydantic block. Inspect: is it still in the discriminated union, and is there a test or fixture that exercises the `kind: spacedock-solver` path through the parser? If yes, delete the class AND remove it from the union — but verify via `grep -rn "SpacedockSolverAgentBlock" src/ tests/` first to make sure nothing else imports it. (Note: `spec/freeze.py` imports `SpacedockSolverV2AgentBlock` — that's the v2 one and stays for now.)

If the class is gone or has no callers, skip the edit in this step.

- [ ] **Step 4: Run the test suite**

```bash
uv run pytest -m 'not integration' --timeout=60 -q
```

Expected: same pass count as end of T2.

- [ ] **Step 5: Commit**

```bash
git add src/razorback/translate.py src/razorback/spec/schema.py
git commit -m "translate: drop v1 SPACEDOCK_SOLVER_IMPORT_PATH + dispatch branch

Per entity retire-v1-rename-v2-to-spacedock AC-3 prep. The v1 import path
constant and the SpacedockSolverAgentBlock dispatch branch had no remaining
callers after the v1 surface deletion. The v2 dispatch path is untouched
and flips to the renamed spacedock module in the rename commit."
```

(If `spec/schema.py` wasn't modified, drop it from the `git add` list and the commit message's `spec/schema.py` reference.)

---

## Task 4: Add `_REGISTRY["spacedock"]` placeholder entry

**Files:**
- Modify: `src/razorback/agents/registry.py`

Pre-stage the new `_REGISTRY` entry so it exists with the future import path BEFORE the v2 → spacedock rename lands. This is purely additive — no spec declares `kind: spacedock` yet, so the entry is unreached. The benefit: T7 doesn't have to also modify `registry.py`, which keeps T7's diff narrower (rename + literal flip only).

Note: the runtime ConfigSchema for the v2 agent's kwargs isn't currently validated through `_REGISTRY` (translate.py builds kwargs directly), so this entry serves discovery/listing purposes only. Use `NopAgentConfig` as the placeholder schema — it's the existing "no config" pydantic model. The implementer should NOT introduce a new config-schema class in this entity unless they discover one is needed for tests in T7.

- [ ] **Step 1: Edit registry.py**

Add to `_REGISTRY`:

```python
    "spacedock": AgentKindEntry(
        NopAgentConfig,
        "razorback.agents.spacedock:SpacedockAgent",
    ),
```

The import path points at the post-T7 module location. Until T7 lands, attempting `resolve_agent_kind("spacedock")` returns a working `AgentKindEntry` but actually importing `razorback.agents.spacedock` fails — that's fine because no test does so.

- [ ] **Step 2: Run the test suite**

```bash
uv run pytest -m 'not integration' --timeout=60 -q
```

Expected: same pass count as end of T3. A test that asserts the `_REGISTRY` keys may now report a stale snapshot — if so, update that test to include `"spacedock"`. (Most likely candidate: anything matching `grep -rln "_REGISTRY\|resolve_agent_kind" tests/`.)

- [ ] **Step 3: Commit**

```bash
git add src/razorback/agents/registry.py
# Plus any registry-snapshot test you had to update:
# git add tests/unit/test_<that_one>.py
git commit -m "registry: add 'spacedock' entry pointing at future module path

Per entity retire-v1-rename-v2-to-spacedock AC-3. Stages the canonical entry
before the v2→spacedock rename so the rename commit (T7) is purely a rename
without registry edits. The entry is unreached until the rename lands."
```

---

## Task 5: (intentionally folded into T7)

No separate task. Schema literal change + block rename + class rename are all in T7 because partial application leaves the discriminated union inconsistent.

---

## Task 6: (intentionally folded into T7)

No separate task. Runtime adapter docstring + import updates are all in T7 because the imports must follow the file rename in lockstep.

---

## Task 7: Atomic v2 → spacedock rename

**Files (move via `git mv`):**
- `src/razorback/agents/spacedock_solver_v2.py` → `src/razorback/agents/spacedock.py`
- `tests/unit/test_spacedock_solver_v2_class.py` → `tests/unit/test_spacedock_class.py`
- `tests/unit/test_spacedock_solver_v2_lifecycle.py` → `tests/unit/test_spacedock_lifecycle.py`
- `tests/unit/test_spacedock_solver_v2_freeze_on_host.py` → `tests/unit/test_spacedock_freeze_on_host.py`
- `tests/unit/test_spec_schema_spacedock_solver_v2.py` → `tests/unit/test_spec_schema_spacedock.py`
- `tests/integration/test_v2_deterministic_smoke.py` → `tests/integration/test_deterministic_smoke.py`
- `tests/integration/test_v2_freeze_dir_mechanism.py` → `tests/integration/test_freeze_dir_mechanism.py`
- `examples/specs/_codex-smoke-v2.yaml` → `examples/specs/_codex-smoke.yaml`
- `examples/specs/_deterministic-smoke-v2.frozen.yaml` → `examples/specs/_deterministic-smoke.frozen.yaml`

**Files (modify in place):** the remaining 32 files in the grep set above whose names don't change.

This is the big one. It must land as a single commit because the discriminated union, the schema literal, the kind name in YAML, and the import paths must all flip together — otherwise the spec parser rejects every spacedock spec mid-rename.

- [ ] **Step 1: `git mv` the renamed files**

```bash
git mv src/razorback/agents/spacedock_solver_v2.py src/razorback/agents/spacedock.py
git mv tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_spacedock_class.py
git mv tests/unit/test_spacedock_solver_v2_lifecycle.py tests/unit/test_spacedock_lifecycle.py
git mv tests/unit/test_spacedock_solver_v2_freeze_on_host.py tests/unit/test_spacedock_freeze_on_host.py
git mv tests/unit/test_spec_schema_spacedock_solver_v2.py tests/unit/test_spec_schema_spacedock.py
git mv tests/integration/test_v2_deterministic_smoke.py tests/integration/test_deterministic_smoke.py
git mv tests/integration/test_v2_freeze_dir_mechanism.py tests/integration/test_freeze_dir_mechanism.py
git mv examples/specs/_codex-smoke-v2.yaml examples/specs/_codex-smoke.yaml
git mv examples/specs/_deterministic-smoke-v2.frozen.yaml examples/specs/_deterministic-smoke.frozen.yaml
```

Don't commit yet. Stage only — the next steps modify these files' contents.

- [ ] **Step 2: Rename the class inside the moved agent module**

In `src/razorback/agents/spacedock.py`:

- `class SpacedockSolverAgent(...)` → `class SpacedockAgent(...)`
- `class SpacedockSolverAgentError(...)` → `class SpacedockAgentError(...)` (keep the existing exception class; just renamed)
- Any module-level constants whose names mention `SOLVER` or `V2` — rename to drop those tokens. Inspect the file's full text; the spec/v2 history may have leaked names like `SPACEDOCK_SOLVER_V2_*`.
- Any docstring or comment that says "v2", "Phase 3 v2", "SpacedockSolverAgent v2" — rewrite as "SpacedockAgent" without temporal qualifiers (per CLAUDE.md: no "v2", "new", "improved", "promoted" in names or comments). Comments should describe the code as it is, not its history.

- [ ] **Step 3: Update the pydantic schema (the discriminator pivot)**

In `src/razorback/spec/schema.py`:

- `class SpacedockSolverV2AgentBlock(BaseModel):` → `class SpacedockAgentBlock(BaseModel):`
- The `kind: Literal["spacedock_solver_v2"]` field → `kind: Literal["spacedock"]`
- The discriminated union (currently around line 100) — update the entry from `SpacedockSolverV2AgentBlock` to `SpacedockAgentBlock`.
- Any docstrings or model_config comments mentioning "v2" — rewrite (same rule as Step 2).

- [ ] **Step 4: Propagate the block rename through every importer**

```bash
grep -rln "SpacedockSolverV2AgentBlock" src/ tests/
```

Touch each file in the result. Replace `SpacedockSolverV2AgentBlock` → `SpacedockAgentBlock` everywhere. Known importers as of pre-implementation:

- `src/razorback/translate.py` — imports it from `razorback.spec.schema` and dispatches on `isinstance(spec.agent, SpacedockSolverV2AgentBlock)`.
- `src/razorback/spec/freeze.py` — imports it.

- [ ] **Step 5: Propagate the class + module rename through every importer**

```bash
grep -rln "from razorback.agents.spacedock_solver_v2\|razorback.agents.spacedock_solver_v2" src/ tests/
```

For each hit:
- `from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgent` → `from razorback.agents.spacedock import SpacedockAgent`
- `from razorback.agents.spacedock_solver_v2 import SpacedockSolverAgentError` → `from razorback.agents.spacedock import SpacedockAgentError`
- The import-path string in `translate.py` (`SPACEDOCK_SOLVER_V2_IMPORT_PATH = "razorback.agents.spacedock_solver_v2:SpacedockSolverAgent"`) — delete the constant and inline the new value `"razorback.agents.spacedock:SpacedockAgent"` at the single call site (the `AgentConfig(import_path=...)` argument in the v2 dispatch branch).
- Similarly delete `SPACEDOCK_SOLVER_V2_CONTAINER_FREEZE_ROOT` if it's no longer referenced after the rename, or rename it to drop the `_V2_` infix if it's still used. (Check with `grep -n "SPACEDOCK_SOLVER_V2_CONTAINER_FREEZE_ROOT" src/`.)
- `SPACEDOCK_SOLVER_V2_ENVIRONMENT_IMPORT_PATH` — same treatment. Rename to drop `_V2_`, or leave the value but rename the symbol to `SPACEDOCK_ENVIRONMENT_IMPORT_PATH`.

- [ ] **Step 6: Update `provenance/freeze_cmd.py`**

Currently has two lines checking `spec.agent.kind == "spacedock_solver_v2"` (around lines 148, 159). Change both to `"spacedock"`.

- [ ] **Step 7: Update runtime adapter docstrings**

Three files: `src/razorback/agents/_runtime/{claude,codex,__init__}.py`. Each carries an ABOUTME header or docstring citing "v2" or "SpacedockSolverAgent v2". Rewrite to "SpacedockAgent" without the v2 token. Also update the import lines (already covered by Step 5).

Concretely:
- `_runtime/__init__.py`: `# ABOUTME: Per-runtime adapter sub-modules for SpacedockSolverAgent v2 (spec §8.4).` → `# ABOUTME: Per-runtime adapter sub-modules for SpacedockAgent (spec §8.4).`
- `_runtime/claude.py`: ABOUTME header + the docstring at the `def build_inner_agent` function (currently mentions "spacedock v2") + the inline comment at ~line 52 ("v2 callers"). Strip the v2 qualifier.
- `_runtime/codex.py`: ABOUTME header + the comment at ~line 130 ("Razorback's v2 schema default"). Strip the v2 qualifier.

- [ ] **Step 8: Update every YAML spec's `kind:` field**

```bash
# Verification: list every YAML still carrying the v2 kind
grep -rln "kind: spacedock_solver_v2" examples/ tests/
```

Expected files (from baseline):

```
examples/specs/_codex-smoke.yaml                                     # just renamed in Step 1
examples/specs/_deterministic-smoke.frozen.yaml                      # just renamed
examples/specs/codex-ade-bench-smoke.yaml
examples/specs/codex-dab-smoke.yaml
examples/specs/pkg40-ade-harbor-task-view-codex.yaml
examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml
examples/specs/goal1/spacedock/*.yaml                                # 12 files
tests/fixtures/specs/tools_denied_live.yaml
```

For each: replace the single line `  kind: spacedock_solver_v2` with `  kind: spacedock`. No other content changes.

- [ ] **Step 9: Update the driver scripts that emit specs**

In `examples/drivers/generate-dab-paper-matrix-specs.py` and `examples/drivers/generate-codex-benchmark-specs.py`:

- Every Python string literal `"spacedock_solver_v2"` → `"spacedock"` (these are the kind values written into the emitted specs).
- Every docstring or comment that says "v2" referring to the agent kind — strip the v2 token (same rule as Step 2).

- [ ] **Step 10: Update the v2 tests that we just renamed**

The body of each renamed test file still references `spacedock_solver_v2` strings and `SpacedockSolverAgent` / `SpacedockSolverV2AgentBlock` class names. Walk through each:

- `tests/unit/test_spacedock_class.py` — class name references, import lines
- `tests/unit/test_spacedock_lifecycle.py` — same
- `tests/unit/test_spacedock_freeze_on_host.py` — same
- `tests/unit/test_spec_schema_spacedock.py` — schema literal assertions
- `tests/integration/test_deterministic_smoke.py` — kind name in inline-yaml fixtures
- `tests/integration/test_freeze_dir_mechanism.py` — same

Plus the other v2-referencing tests that we DIDN'T rename:

- `tests/integration/test_freeze_cas_resume_no_agent_invocation.py`
- `tests/integration/test_freeze_cross_worktree_discovery.py`
- `tests/unit/test_claude_benchmark_spec_generator.py`
- `tests/unit/test_codex_benchmark_spec_generator.py`
- `tests/unit/test_generate_matrix_specs_per_variant_kind.py`
- `tests/unit/test_runtime_adapters.py`
- `tests/unit/test_spec_freeze_cli_pkg8.py`
- `tests/unit/test_tools_denied_claude_hook.py`
- `tests/unit/test_tools_denied_parse.py`

In each, replace string literals and class references. After this step:

```bash
grep -rn "spacedock_solver_v2\|SpacedockSolverV2\|SpacedockSolverAgent " \
  src/ tests/ examples/ packages/ \
  --include='*.py' --include='*.yaml' --include='*.yml'
```

Expected: zero hits. (The trailing space on `SpacedockSolverAgent ` keeps `SpacedockAgent` from matching; if some grep tool ignores the space, also check `grep -wn "SpacedockSolverAgent"`.)

- [ ] **Step 11: Re-stage and check the diff is coherent**

```bash
git status
git diff --cached --stat
```

Sanity-check: every file in the 41-file production list (above) should appear in the staged diff. If a known file is missing, you missed a substitution.

- [ ] **Step 12: Run the test suite**

```bash
uv run pytest -m 'not integration' --timeout=60 -q
```

Expected: pass count equal to or greater than end of T4. The pre-existing `test_rk_run_nop` failure (per AC-4 — "the two pre-existing failures ... disappear with v1's deletion in AC-1") should be gone. If a NEW failure appears, it's almost certainly a missed reference somewhere in Steps 2–10; do not patch a symptom, instead grep for the failing test's error message and find the v2-named identifier that didn't get renamed.

The frozen smoke spec `examples/specs/_deterministic-smoke.frozen.yaml` now has a `kind: spacedock` value but an OLD `sealed_hash` computed against `kind: spacedock_solver_v2`. Tests that load that frozen spec will fail with a hash mismatch. T8 fixes this. For T7's test gate, EXPECT a failure in any test that consumes this specific frozen spec — note which tests they are, and verify T8 unblocks them.

- [ ] **Step 13: Commit**

```bash
git add -A   # justified — every modified file is part of this single rename
# (Verify with git status that no surprise files are present before adding.)
git commit -m "rename: spacedock_solver_v2 → spacedock (file, class, kind, schema literal)

Per entity retire-v1-rename-v2-to-spacedock AC-2 + AC-3. Single coherent
commit because the schema discriminated union, the Literal, and the kind
in every YAML must flip together — partial application leaves the parser
unable to load any spacedock spec. The frozen smoke spec's sealed_hash
is re-computed in the following commit."
```

---

## Task 8: Re-freeze the sealed smoke spec

**Files:**
- Modify: `examples/specs/_deterministic-smoke.frozen.yaml`

The only sealed (`sealed_hash:`-bearing) spec in the codebase that referenced `kind: spacedock_solver_v2`. T7 changed its `kind:` to `spacedock`, which invalidates the sealed hash. Re-freeze using the `rk freeze` CLI.

The 12 goal1 specs at `examples/specs/goal1/spacedock/*.yaml` are NOT sealed (no `sealed_hash:` field) — verified via `grep -l "sealed_hash:" examples/specs/goal1/spacedock/*.yaml` returning empty. They needed only the kind-name text swap in T7 Step 8; no freeze action.

- [ ] **Step 1: Inspect the current state of the frozen spec**

```bash
grep -n "kind:\|sealed_hash:" examples/specs/_deterministic-smoke.frozen.yaml
```

Expected: `kind: spacedock` (from T7) and a `sealed_hash:` line whose value is now stale.

- [ ] **Step 2: Re-freeze**

```bash
uv run rk freeze examples/specs/_deterministic-smoke.frozen.yaml --in-place
```

(If `--in-place` isn't the actual flag name, check `uv run rk freeze --help`. The intent is: rewrite the file with a sealed_hash that matches the post-rename content. If the CLI doesn't support an in-place flag, freeze to a temp path and overwrite.)

- [ ] **Step 3: Verify the re-freeze**

```bash
grep -n "kind:\|sealed_hash:" examples/specs/_deterministic-smoke.frozen.yaml
```

`kind: spacedock` is unchanged; `sealed_hash:` has a new value.

- [ ] **Step 4: Run the test suite**

```bash
uv run pytest -m 'not integration' --timeout=60 -q
```

Expected: the tests that failed at end of T7 (specifically anything loading the frozen smoke spec) now pass. Overall pass count is now equal to or greater than end of T6.

- [ ] **Step 5: Commit**

```bash
git add examples/specs/_deterministic-smoke.frozen.yaml
git commit -m "re-freeze: deterministic-smoke spec under new kind=spacedock

Per entity retire-v1-rename-v2-to-spacedock test plan 'spec freeze pass'.
The kind-name rename in the previous commit invalidated the sealed_hash;
this commit recomputes it. The goal1 specs are unsealed and needed no
freeze action."
```

---

## Task 9: Archive superseded entities + green-main verification (AC-4 gate)

**Files:**
- Move: `docs/razorback-implementation/phase6-promote-v2-canonical.md` → `docs/razorback-implementation/_archive/`
- Move: `docs/razorback-implementation/phase7-delete-legacy.md` → `docs/razorback-implementation/_archive/`

**Recommendation for the supersession move:** do it INSIDE this entity's implementation stage, not post-merge by the FO. Rationale: the entity body's "Supersedes" section explicitly says "moved to `_archive/` ... as part of this entity's implementation stage." Doing it as a separate FO post-merge action splits the historical record (the entity reference says "superseded by retire-v1-rename-v2-to-spacedock", but the linked entity has already merged and the supersession isn't visible in its history). One coherent commit keeps the supersession audit-traceable.

- [ ] **Step 1: Move the superseded entities**

```bash
git mv docs/razorback-implementation/phase6-promote-v2-canonical.md docs/razorback-implementation/_archive/
git mv docs/razorback-implementation/phase7-delete-legacy.md docs/razorback-implementation/_archive/
```

- [ ] **Step 2: Add a supersession note to each**

To both files, append a short markdown section:

```markdown

---

## Superseded

Superseded by `retire-v1-rename-v2-to-spacedock` (entity id `5f192b62951w0v5wx45fw8qm`).
Captain decision 2026-05-23: skip the `_legacy/` rollback alias; clean cut
folding promote + delete into a single ship. See entity body for rationale.
```

- [ ] **Step 3: Run the AC-4 gate**

```bash
uv run pytest -m 'not integration' --timeout=60 -q
```

Expected output: exit code 0. Record the pass count (the AC-4 verification asks for "exit code + N/N pass count" — paste both into the stage report at validation time).

If anything fails at this point, STOP and surface the failure. The most likely root cause is a missed v2 reference from T7; resist the urge to "just fix it" — investigate via `grep -n` first and trace the failing test back to the dangling identifier.

- [ ] **Step 4: Commit**

```bash
git add docs/razorback-implementation/_archive/phase6-promote-v2-canonical.md \
        docs/razorback-implementation/_archive/phase7-delete-legacy.md
git commit -m "archive: phase6-promote-v2-canonical + phase7-delete-legacy (superseded)

Both folded into retire-v1-rename-v2-to-spacedock per captain decision
2026-05-23 (no _legacy rollback alias; clean cut). Adds a 'Superseded'
note to each archived entity for audit traceability."
```

---

## Self-Review

**1. Spec coverage:**

- AC-1 (v1 surface deleted) — T1
- AC-2 (v2 renamed to spacedock everywhere) — T7 + T8
- AC-3 (dual dispatch eliminated; registry has `"spacedock"`; translate.py constants gone) — T3 (v1 constant) + T7 (v2 constant) + T4 (registry entry pre-staged) + T2 (registry v1 entry gone)
- AC-4 (`pytest -m 'not integration'` exit 0) — gated at end of T9
- Test plan "spec freeze pass" — T8
- Test plan "mechanical: git mv for history" — T1 (`git rm`), T7 (`git mv`)
- Test plan "renamed test files continue to pass" — implicit in T7's gate
- Out-of-scope: backward-compat aliases, prior frozen specs, runtime sub-module functional implementation, cross-repo edits — none in the plan, as required
- Supersedes: phase6 + phase7 archive moves — T9

**2. Placeholder scan:** plan has no TBD / "implement later" / "add appropriate" / "similar to Task N" phrases. Each step's commands are concrete. The one ambiguity I flag explicitly is T8 Step 2's `--in-place` flag — the implementer is instructed to check `rk freeze --help` because I don't have evidence of the exact flag name from main HEAD.

**3. Type consistency:** the new class is `SpacedockAgent` everywhere (T7 Step 2, registry entry in T4, import path strings, docstrings). The new pydantic block is `SpacedockAgentBlock`. The new schema literal is `"spacedock"`. The new module path is `razorback.agents.spacedock`. These four identifiers appear consistently across T4, T7 Steps 2–5, the registry entry literal, and the translate.py import-path string. The exception class is `SpacedockAgentError` (T7 Step 2) and gets imported under that name everywhere.

**4. AC-3 wording carveout:** the entity's AC-3 says translate.py should route "through `resolve_agent_kind()` exactly like it routes `claude-cli` today." This is mildly misleading — `claude-cli` is currently dispatched via a hardcoded `RAZORBACK_CLAUDE_CODE_IMPORT_PATH` constant in translate.py, not through `resolve_agent_kind()`. The plan honors AC-3's NORMATIVE checks (`_REGISTRY` entry exists for `"spacedock"`; no `SPACEDOCK_SOLVER*` constants remain in translate.py) but does NOT introduce a `resolve_agent_kind()` dispatch refactor inside this entity — that would be a wider cleanup also touching `claude-cli` and is correctly out of scope per the entity's narrow "v1 retire + v2 rename" framing. Flagging this for FO/captain review at validation time.

---

## Execution Handoff

Plan complete and saved to `docs/razorback-implementation/plans/retire-v1-rename-v2-to-spacedock.md`. Two execution options:

1. **Subagent-Driven (recommended)** — FO dispatches a fresh implementation-stage ensign per task (T1, T2, T3, T4, T7, T8, T9), with the captain reviewing between tasks. T7 is the heavy one and benefits from an isolated worktree.

2. **Inline Execution** — implementation-stage ensign executes the full plan in one session inside the entity's worktree, with checkpoints at the end of T1, T4, and T7.

Captain to choose. Default for this entity (multi-file rename touching ~40 files) is option 1.
