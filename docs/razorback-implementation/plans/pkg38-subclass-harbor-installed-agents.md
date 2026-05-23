# PKG-38 Subclass Harbor Installed Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Razorback's live Codex and Claude solver runtimes reuse Harbor's installed-agent implementations through explicit subclasses or thin Harbor-backed compatibility shims, while preserving v2 sealed-input, freeze-dir, and checkpoint contracts.

**Architecture:** Keep `SpacedockSolverAgent` as the lifecycle owner and make `_runtime/{codex,claude}.py` the only per-runtime Harbor glue. Codex stays a `Codex` subclass with documented benchmark-only overrides; Claude gets a `ClaudeCode` subclass so both live runtimes share the same subclass-first shape. Legacy `agent.kind: claude-cli` remains parseable as a compatibility spelling, but active translation and new benchmark spec generation route to Harbor `ClaudeCode`/`spacedock_solver_v2`, not the old parallel `ClaudeCliAgent` runtime.

**Tech Stack:** Python 3.12, `uv`, pytest, Pydantic, Harbor installed agents (`harbor.agents.installed.codex.Codex`, `harbor.agents.installed.claude_code.ClaudeCode`), Razorback v2 spec and translator.

---

## AC to Task Map

| AC | Governing spec cites | Tasks | Focused tests |
| --- | --- | --- | --- |
| AC-1 - Codex runtime stays subclass-first | v2 spec §4.3 runtime selection and sealed-hash inputs; §8.4 runtime adapter shape | T1, T2, T6 | `tests/unit/test_runtime_adapters.py`, `tests/integration/test_v2_freeze_dir_mechanism.py` |
| AC-2 - Claude runtime stops avoidable parallel CLI wrapping | v2 spec §4.3.1, §6.2, §8.4 | T1, T3, T4, T5 | `tests/unit/test_claude_cli_*.py`, `tests/unit/test_translate_spacedock_solver_import_path.py`, `tests/unit/test_runtime_adapters.py` |
| AC-3 - Solver lifecycle preserves sealed input and checkpoint contracts | v2 spec §4.3.4-6, §4.4, §7.1, §8.4, §9.6 | T6, T7 | `tests/unit/test_spacedock_solver_v2_class.py`, `tests/unit/test_spacedock_solver_v2_lifecycle.py`, `tests/unit/test_spec_freeze_cli_pkg8.py`, `tests/integration/test_v2_freeze_dir_mechanism.py` |
| AC-4 - Upstream divergence is documented where it remains | v2 spec §4.3.1, §8.4 | T2, T3, T7 | `tests/unit/test_runtime_adapters.py` plus reviewer inspection |

## Upstream Class Surface Analysis

**Harbor `Codex`:** Installed class at `.venv/lib/python3.12/site-packages/harbor/agents/installed/codex.py`. It subclasses `BaseInstalledAgent`, declares descriptor-backed kwargs `reasoning_effort` and `reasoning_summary`, implements `install()`, `run()`, version parsing, Codex auth handling, MCP/skills registration, and ATIF post-run parsing. Razorback should not duplicate `Codex.install()` or `Codex.run()`. The retained benchmark divergence is `build_cli_flags()` adding `-c web_search="disabled"` and an install-phase proxy-clearing shim so Harbor's own install commands can reach npm/curl even when Razorback's runtime proxy block is present.

**Harbor `ClaudeCode`:** Installed class at `.venv/lib/python3.12/site-packages/harbor/agents/installed/claude_code.py`. It subclasses `BaseInstalledAgent`, declares descriptor-backed kwargs for `max_turns`, `reasoning_effort`, `thinking`, `max_budget_usd`, `append_system_prompt`, `allowed_tools`, `disallowed_tools`, and `MAX_THINKING_TOKENS`, and owns install/run/session/ATIF behavior. Razorback should construct a subclass or thin adapter and never re-wrap `claude -p` for live benchmark solving.

**Existing `RazorbackCodex`:** `src/razorback/agents/_runtime/codex.py` already subclasses Harbor `Codex`, but currently reimplements upstream `install()` by copying Harbor's command body and only changing proxy env. T2 replaces that with a `super().install()` delegation wrapped by install-phase env handling, preserving subclass-first behavior without maintaining a parallel install script.

**`spacedock_solver_v2`:** `src/razorback/agents/spacedock_solver_v2.py` is the lifecycle boundary. It computes `sealed_hash`, resolves `_razorback/freeze/<sealed_hash>/`, writes named git checkpoint commits, composes the workflow instruction, and delegates to `_runtime` builders. PKG-38 should not move sealed-hash computation, freeze-dir resolution, checkpoint labels, or `setup()`/`run()` ordering into the runtime adapters.

**Legacy `claude_cli`:** `src/razorback/agents/claude_cli.py` is a standalone `BaseAgent` wrapper around `claude -p`. It validates CLI presence and builds commands through `claude_invoke.py`, duplicating behavior Harbor `ClaudeCode` now owns. PKG-38 keeps this module only as historical compatibility code; active translator and registry paths stop selecting it.

**Subclass-first direction:** After implementation, both live runtime builders return Razorback subclasses of Harbor installed agents: `RazorbackCodex(Codex)` and `RazorbackClaudeCode(ClaudeCode)`. The old `agent.kind: claude-cli` spelling maps to the Harbor-backed Claude subclass with narrowly supported legacy kwargs, while new benchmark specs use `agent.kind: spacedock_solver_v2` with `runtime: claude` or `runtime: codex`.

## File Structure

| File | Responsibility | Action |
| --- | --- | --- |
| `src/razorback/agents/_runtime/codex.py` | Codex subclass and kwarg filtering | Modify: keep `RazorbackCodex(Codex)`, remove copied install body, add documented `Codex.install` delegation/proxy shim |
| `src/razorback/agents/_runtime/claude.py` | Claude Harbor runtime adapter | Modify: add `RazorbackClaudeCode(ClaudeCode)`, descriptor-backed kwarg filtering, field-name mapping |
| `src/razorback/agents/spacedock_solver_v2.py` | v2 lifecycle owner | Inspect only unless a comment is needed; do not move sealed/freeze/checkpoint logic |
| `src/razorback/translate.py` | Spec to Harbor `AgentConfig` translation | Modify: legacy `claude-cli` compatibility maps to Harbor-backed Claude subclass; v2 translation unchanged except import constants if shared |
| `src/razorback/agents/registry.py` | Agent-kind validation/import-path registry | Modify: `claude-cli` registry entry points at the compatibility shim import path, not `ClaudeCliAgent` |
| `src/razorback/agents/claude_cli.py` | Legacy manual wrapper | Modify: add a legacy/not-active comment; do not change runtime behavior |
| `examples/drivers/generate-dab-paper-matrix-specs.py` | Goal 1 Claude benchmark spec generator | Modify: new generated specs use `spacedock_solver_v2` + `runtime: claude` |
| `examples/solver_workflows/claude-benchmark-solver/README.md` | Generic Claude benchmark solver workflow | Create |
| `tests/unit/test_runtime_adapters.py` | Runtime adapter contract tests | Modify |
| `tests/unit/test_claude_cli_registry.py` | Legacy kind registry compatibility tests | Modify |
| `tests/unit/test_claude_cli_translator_proxy.py` | Legacy kind translation/auth/proxy tests | Modify |
| `tests/unit/test_claude_cli_compat_shim.py` | New compatibility-shim tests | Create |
| `tests/unit/test_claude_benchmark_spec_generator.py` | New generated-spec tests for Claude benchmark matrix | Create |
| `tests/unit/test_translate_spacedock_solver_import_path.py` | v2 import path/environment tests | Modify only for assertions that guard Claude v2 routing |
| `tests/unit/test_spacedock_solver_v2_class.py` | Sealed hash contract tests | Modify only to add regression assertions |
| `tests/unit/test_spacedock_solver_v2_lifecycle.py` | Freeze/checkpoint lifecycle tests | Modify only to add regression assertions |
| `tests/unit/test_spec_freeze_cli_pkg8.py` | Freeze CLI sealed-field tests | Modify only to add exact hash preservation assertions |
| `tests/integration/test_v2_freeze_dir_mechanism.py` | Smallest end-to-end freeze-dir mechanism tests | Modify only to assert adapter refactor did not alter freeze root behavior |

## Task 1: Lock Down Current Upstream Shapes

**Spec cites:** §4.3.1 runtime selection, §8.4 runtime adapter sub-modules.

**Files:**
- Modify: `tests/unit/test_runtime_adapters.py`

- [ ] **Step 1: Add source-shape tests before editing runtime code.**
  Add tests that import Harbor `Codex`/`ClaudeCode` and assert the descriptors Razorback relies on:
  - `Codex.CLI_FLAGS` contains `reasoning_effort` and `reasoning_summary`.
  - `ClaudeCode.CLI_FLAGS` contains `max_turns`, `reasoning_effort`, `append_system_prompt`, `allowed_tools`, and `disallowed_tools`.
  - `ClaudeCode.ENV_VARS` contains `max_thinking_tokens`.

- [ ] **Step 2: Add subclass-first tests.**
  Add failing assertions that:
  - `codex_adapter.build_inner_agent(...).__class__.__name__ == "RazorbackCodex"` and `isinstance(inner, Codex)`.
  - `claude_adapter.build_inner_agent(...).__class__.__name__ == "RazorbackClaudeCode"` and `isinstance(inner, ClaudeCode)`.

- [ ] **Step 3: Add divergence-documentation tests.**
  Add source-inspection tests that retained overrides in `RazorbackCodex` include comments naming the upstream method:
  - `Codex.build_cli_flags` for web search disablement.
  - `Codex.install` for install-phase proxy env clearing.
  The test should fail if a retained override lacks both the upstream method name and a benchmark reason phrase.

- [ ] **Step 4: Run the focused red test.**
  Run: `uv run --frozen pytest tests/unit/test_runtime_adapters.py -q`
  Expected before implementation: fail on missing `RazorbackClaudeCode` and, if T2 has not run, fail on the copied Codex install implementation/comment guard.

- [ ] **Step 5: Commit after T2/T3 make these tests green.**
  Commit message: `pkg38: lock harbor installed-agent adapter contracts`

## Task 2: Keep Codex Subclass-First Without Copying Harbor Install

**Spec cites:** §4.3.1 runtime selection, §8.4 adapter construction. AC-1 and AC-4.

**Files:**
- Modify: `src/razorback/agents/_runtime/codex.py`
- Test: `tests/unit/test_runtime_adapters.py`

- [ ] **Step 1: Refactor `RazorbackCodex.install()` to delegate.**
  Replace the copied install command body with a small override that calls `await super().install(environment)`. Use a private install-phase flag plus `exec_as_root()` / `exec_as_agent()` overrides to merge `_without_proxy_env(...)` only while `Codex.install` is running. This preserves Harbor's install script and keeps Razorback's exe/benchmark proxy constraint localized.

- [ ] **Step 2: Preserve web-search disablement.**
  Keep `build_cli_flags()` as the only CLI behavior override. Its comment must name `Codex.build_cli_flags` and state the benchmark reason: Codex web search must be disabled for offline benchmark solving.

- [ ] **Step 3: Add an assertion that the install body does not contain Harbor command literals.**
  In `tests/unit/test_runtime_adapters.py`, inspect `RazorbackCodex.install` and assert it does not contain `npm install -g @openai/codex`, `apt-get update`, or `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm`. That directly enforces "no parallel upstream install behavior."

- [ ] **Step 4: Add install-phase env tests.**
  Monkeypatch `Codex.install` to call `self.exec_as_agent(environment, command="probe", env={"X": "1"})`, run `RazorbackCodex.install(fake_env)`, and assert the env passed to `fake_env.exec` contains `HTTP_PROXY == ""`, `HTTPS_PROXY == ""`, and `X == "1"`.

- [ ] **Step 5: Run Codex adapter tests.**
  Run: `uv run --frozen pytest tests/unit/test_runtime_adapters.py::test_codex_constructs_inner_agent_with_supported_kwargs tests/unit/test_runtime_adapters.py::test_codex_rejects_unsupported_contract_kwargs -q`
  Expected: pass.

- [ ] **Step 6: Run the AC-1 focused command.**
  Run: `uv run --frozen pytest tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q`
  Expected: pass.

- [ ] **Step 7: Commit.**
  Commit message: `pkg38: delegate codex install to harbor`

## Task 3: Add a Harbor-Backed Claude Runtime Subclass

**Spec cites:** §4.3.1 runtime selection, §6.2 agent block, §8.4 runtime adapter sub-modules. AC-2 and AC-4.

**Files:**
- Modify: `src/razorback/agents/_runtime/claude.py`
- Modify: `tests/unit/test_runtime_adapters.py`

- [ ] **Step 1: Extend the red adapter tests.**
  Add tests that:
  - `RazorbackClaudeCode` subclasses Harbor `ClaudeCode`.
  - `build_inner_agent()` forwards `max_turns`, `reasoning_effort`, `append_system_prompt`, `tools_allowed`, and `tools_denied` into Harbor descriptor kwargs.
  - `tools_allowed` maps to `allowed_tools`, and `tools_denied` maps to `disallowed_tools`.
  - unknown non-empty `harbor_agent_kwargs` raise `SpacedockSolverAgentError` instead of being dropped.

- [ ] **Step 2: Implement `RazorbackClaudeCode(ClaudeCode)`.**
  Add the subclass in `src/razorback/agents/_runtime/claude.py`. Do not override `install()`, `setup()`, `run()`, `populate_context_post_run()`, or `build_cli_flags()` unless a test in this task proves a benchmark constraint needs it. The subclass exists to make the live Claude path explicitly Harbor installed-agent backed and to host future documented benchmark-only overrides.

- [ ] **Step 3: Derive supported kwargs from Harbor descriptors.**
  Build `_CLAUDE_SUPPORTED_KWARGS` from `ClaudeCode.CLI_FLAGS` and `ClaudeCode.ENV_VARS`, plus `skills_dir` if the builder continues to pass that BaseAgent constructor kwarg. Reject unsupported active values. Treat `None`, empty `tools_allowed`, and empty `tools_denied` as no-ops; continue forwarding `max_turns=200` for Claude because the existing Claude adapter honors that cap.

- [ ] **Step 4: Preserve current field-name mapping.**
  Keep Razorback spec names in `build_v2_harbor_agent_kwargs()` and map only in the adapter:
  - `tools_allowed` -> comma-joined `allowed_tools`
  - `tools_denied` -> comma-joined `disallowed_tools`
  - `append_system_prompt` -> `append_system_prompt`
  - `reasoning_effort` -> `reasoning_effort`
  Do not add `max_budget_usd` to `harbor_agent_kwargs` in PKG-38; that would alter v2 sealed hashes outside this task's acceptance criteria.

- [ ] **Step 5: Run Claude adapter tests.**
  Run: `uv run --frozen pytest tests/unit/test_runtime_adapters.py -q`
  Expected: pass.

- [ ] **Step 6: Commit.**
  Commit message: `pkg38: route claude runtime through harbor subclass`

## Task 4: Reduce `agent.kind: claude-cli` to a Compatibility Shim

**Spec cites:** §6.2 agent block validation, §8.4 runtime adaptation. AC-2.

**Files:**
- Modify: `src/razorback/translate.py`
- Modify: `src/razorback/agents/registry.py`
- Modify: `src/razorback/agents/claude_cli.py` only for a legacy comment if retained
- Modify: `tests/unit/test_claude_cli_registry.py`
- Modify: `tests/unit/test_claude_cli_translator_proxy.py`
- Create: `tests/unit/test_claude_cli_compat_shim.py`

- [ ] **Step 1: Write failing compatibility tests.**
  Add tests proving:
  - `resolve_agent_kind("claude-cli").import_path` is the Harbor-backed Claude subclass import path, not `razorback.agents.claude_cli:ClaudeCliAgent`.
  - Translating a legacy `agent.kind: claude-cli` spec emits `AgentConfig.import_path` for `RazorbackClaudeCode`.
  - Auth still flows through `AgentConfig.env`, not kwargs.
  - Default `sampling.temperature: 0.0` is accepted for legacy compatibility.
  - Non-default `sampling.temperature` raises `SpecError` with a message naming that Harbor `ClaudeCode` has no temperature kwarg.

- [ ] **Step 2: Change the translator import path.**
  Replace the active `CLAUDE_CLI_IMPORT_PATH` target with a compatibility constant such as `RAZORBACK_CLAUDE_CODE_IMPORT_PATH = "razorback.agents._runtime.claude:RazorbackClaudeCode"`. Keep the legacy spec kind spelling `claude-cli` in `src/razorback/spec/schema.py` so old specs parse.

- [ ] **Step 3: Map legacy kwargs to Harbor Claude kwargs.**
  For `ClaudeCliAgentBlock` in `_build_agent_config()`:
  - Resolve Claude auth exactly as today.
  - Emit `model_name=spec.agent.model`.
  - Map non-empty `tools_allowed` to `allowed_tools="Read,Write"` style kwargs.
  - Do not emit `sampling_temperature`.
  - Refuse non-default sampling values that Harbor cannot honor.

- [ ] **Step 4: Update registry.**
  Point `"claude-cli"` at the same compatibility import path and keep the existing config schema strict. This proves registry-based validation does not select the legacy manual wrapper.

- [ ] **Step 5: Mark the old wrapper as inactive.**
  Add a top-of-file comment to `src/razorback/agents/claude_cli.py`: "Legacy manual wrapper retained for historical tests; active translation routes `agent.kind: claude-cli` to Harbor `ClaudeCode`." Do not alter its runtime behavior in PKG-38.

- [ ] **Step 6: Run the AC-2 focused command.**
  Run: `uv run --frozen pytest tests/unit/test_claude_cli_*.py tests/unit/test_translate_spacedock_solver_import_path.py -q`
  Expected: pass.

- [ ] **Step 7: Commit.**
  Commit message: `pkg38: make claude-cli a harbor-backed shim`

## Task 5: Ensure New Benchmark Specs Do Not Select Legacy `claude-cli`

**Spec cites:** §6.1 benchmark translation, §6.2 agent block, §8.4 runtime adaptation. AC-2 compatibility strategy.

**Files:**
- Modify: `examples/drivers/generate-dab-paper-matrix-specs.py`
- Create: `examples/solver_workflows/claude-benchmark-solver/README.md`
- Create: `tests/unit/test_claude_benchmark_spec_generator.py`

- [ ] **Step 1: Write generator tests first.**
  Add tests that load `examples/drivers/generate-dab-paper-matrix-specs.py` by path and assert `build_spec("direct-minimal", "bookreview")` emits:
  - `agent.kind == "spacedock_solver_v2"`
  - `agent.runtime == "claude"`
  - `agent.model == "claude-opus-4-7"`
  - `agent.solver_workflow == "./examples/solver_workflows/claude-benchmark-solver"`
  - `agent.spacedock_skill_version == "1.0.0"`
  - no `agent.kind: claude-cli`
  Keep the existing benchmark block (`harbor_dab`) unchanged.

- [ ] **Step 2: Add a Claude-named solver workflow.**
  Create `examples/solver_workflows/claude-benchmark-solver/README.md` with the same benchmark-offline discipline as the Codex workflow, phrased without Codex-specific naming. This keeps generated Claude specs readable without renaming the existing Codex workflow path.

- [ ] **Step 3: Update the generator.**
  Change `build_spec()` to emit `spacedock_solver_v2` with `runtime: claude`, `solver_workflow`, `spacedock_skill_version`, `max_turns`, `tools_allowed`, and `tools_denied`. Preserve the existing DAB data root, workspace variant, hints, observers, trials, and budget metadata.

- [ ] **Step 4: Run generator tests.**
  Run: `uv run --frozen pytest tests/unit/test_claude_benchmark_spec_generator.py tests/unit/test_codex_benchmark_spec_generator.py -q`
  Expected: pass. The Codex generator remains unchanged.

- [ ] **Step 5: Commit.**
  Commit message: `pkg38: emit claude benchmark specs through solver v2`

## Task 6: Guard Sealed Hash, Freeze Directory, and Checkpoint Behavior

**Spec cites:** §4.3.4-6, §4.4, §7.1, §8.4, §9.6. AC-3.

**Files:**
- Modify: `tests/unit/test_spacedock_solver_v2_class.py`
- Modify: `tests/unit/test_spacedock_solver_v2_lifecycle.py`
- Modify: `tests/unit/test_spec_freeze_cli_pkg8.py`
- Modify: `tests/integration/test_v2_freeze_dir_mechanism.py`

- [ ] **Step 1: Add a sealed-hash exact-value regression.**
  In `tests/unit/test_spacedock_solver_v2_class.py`, compute a known v2 hash with fixed `model`, `sampling`, `solver_workflow_content_hash`, `prompt_content_hashes`, `spacedock_skill_version`, and `harbor_agent_kwargs`, and assert the exact 32-character hex string. This catches accidental `harbor_agent_kwargs` shape changes.

- [ ] **Step 2: Add freeze CLI parity coverage.**
  In `tests/unit/test_spec_freeze_cli_pkg8.py`, assert freeze-time sealed hash equals `compute_sealed_hash(...)` using the existing helper and still includes Codex reasoning kwargs only when present. Do not add Claude-only fields to the sealed payload in PKG-38.

- [ ] **Step 3: Keep checkpoint labels exact.**
  Leave `CHECKPOINT_SETUP_READY`, `CHECKPOINT_RUN_BEFORE_AGENT`, and `CHECKPOINT_RUN_AFTER_AGENT` unchanged. In `tests/unit/test_spacedock_solver_v2_lifecycle.py`, keep asserting the exact commit-message order:
  - `stage: setup/ready`
  - `stage: run/before-agent`
  - `stage: run/after-agent`

- [ ] **Step 4: Keep freeze root outside trials.**
  In `tests/integration/test_v2_freeze_dir_mechanism.py`, keep asserting `<run-dir>/_razorback/freeze/<sealed_hash>` and that the path does not include `trials`.

- [ ] **Step 5: Run the AC-3 focused command.**
  Run: `uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_spacedock_solver_v2_lifecycle.py tests/unit/test_spec_freeze_cli_pkg8.py tests/integration/test_v2_freeze_dir_mechanism.py -q`
  Expected: pass.

- [ ] **Step 6: Commit.**
  Commit message: `pkg38: guard solver v2 sealed lifecycle contracts`

## Task 7: Final Inspection and Acceptance Sweep

**Spec cites:** §4.3, §4.4, §6.2, §7.1, §8.4. AC-1 through AC-4.

**Files:**
- Inspect: all files changed in T2-T6
- Modify: only comments/test names if an override lacks the AC-4 documentation

- [ ] **Step 1: Inspect retained overrides.**
  Search:
  `rg -n "class Razorback|def install|def setup|def run|def build_cli_flags" src/razorback/agents`
  Confirm every retained override of a Harbor installed-agent method names the upstream method and benchmark reason in nearby code comments or test names.

- [ ] **Step 2: Verify no active path selects the legacy wrapper.**
  Run:
  `rg -n "razorback\\.agents\\.claude_cli:ClaudeCliAgent|ClaudeCliAgent" src/razorback examples/drivers tests/unit/test_claude_cli_*.py`
  Expected: production translator/registry/generator paths do not point at `ClaudeCliAgent`. References under the legacy module and legacy behavior tests are allowed.

- [ ] **Step 3: Run the required AC commands.**
  Run:
  `uv run --frozen pytest tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q`

  Run:
  `uv run --frozen pytest tests/unit/test_claude_cli_*.py tests/unit/test_translate_spacedock_solver_import_path.py -q`

  Run:
  `uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_spacedock_solver_v2_lifecycle.py tests/unit/test_spec_freeze_cli_pkg8.py tests/integration/test_v2_freeze_dir_mechanism.py -q`

- [ ] **Step 4: Run a combined regression sweep for touched tests.**
  Run:
  `uv run --frozen pytest tests/unit/test_runtime_adapters.py tests/unit/test_claude_cli_*.py tests/unit/test_translate_spacedock_solver_import_path.py tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_spacedock_solver_v2_lifecycle.py tests/unit/test_spec_freeze_cli_pkg8.py tests/unit/test_claude_benchmark_spec_generator.py tests/unit/test_codex_benchmark_spec_generator.py tests/integration/test_v2_freeze_dir_mechanism.py -q`
  Expected: pass.

- [ ] **Step 5: Commit final comment/test cleanup.**
  Commit message: `pkg38: document harbor subclass divergences`

## Compatibility Strategy Summary

`agent.kind: claude-cli` remains a parseable legacy spelling for old specs, but it becomes a Harbor-backed compatibility shim:

- Active translation emits `RazorbackClaudeCode(ClaudeCode)`, not `ClaudeCliAgent`.
- Registry resolution points to the same Harbor-backed class.
- Default legacy sampling is accepted only when it is a no-op under Harbor `ClaudeCode`; unsupported active sampling values fail closed with `SpecError`.
- New benchmark spec generation emits `spacedock_solver_v2` with `runtime: claude`, making the compatibility spelling unnecessary for new matrices.
- Historical checked-in specs can be migrated separately when those examples are regenerated; PKG-38 only changes active code paths and the generator used for new specs.

## Risk-First Ordering

T1-T3 validate the riskiest contract first: the runtime adapters must use Harbor's live installed-agent shape and fail closed on unsupported kwargs. T4 then removes the active legacy Claude wrapper path while preserving old spec parsing. T5 prevents new benchmark specs from reintroducing `claude-cli`. T6 runs the lifecycle guardrail after adapter changes but before the final acceptance sweep, so sealed hash, freeze-dir, and checkpoint regressions are caught before comprehensive commands.

## Acceptance Commands

Use the exact commands from the entity after implementation:

```bash
uv run --frozen pytest tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q
uv run --frozen pytest tests/unit/test_claude_cli_*.py tests/unit/test_translate_spacedock_solver_import_path.py -q
uv run --frozen pytest tests/unit/test_spacedock_solver_v2_class.py tests/unit/test_spacedock_solver_v2_lifecycle.py tests/unit/test_spec_freeze_cli_pkg8.py tests/integration/test_v2_freeze_dir_mechanism.py -q
```
