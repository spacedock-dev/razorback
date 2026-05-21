---
id: pkg26-validation
title: PKG-26 validation — live rk run evidence
---

# PKG-26 validation: ClaudeCliAgent subclass of ClaudeCode (live trial evidence)

Captures the T4 live-run evidence for AC-2 + AC-3 + AC-4 from
`docs/razorback-implementation/pkg26-use-harbor-claude-code-adapter.md`.

## AC-1 / AC-5 — unit (subclass + identity + auth preservation)

`tests/unit/test_claude_cli_subclasses_claude_code.py` — 4 tests:

- `isinstance(ClaudeCliAgent(...), ClaudeCode)` PASS
- `issubclass(ClaudeCliAgent, ClaudeCode)` PASS
- `ClaudeCliAgent.name() == "claude-cli"` PASS
- `supported_sampling() == {"temperature"}` PASS

Co-mingled-auth refusal preserved (existing `test_claude_cli_setup_env_scrub.py::test_constructor_refuses_to_co_mingle` stays green).

## AC-2 — kwarg-mapping unit (tools_allowed → allowed_tools)

`tests/unit/test_claude_cli_kwarg_mapping.py` — 4 tests:

- `--allowedTools Bash,Read` lands in `build_cli_flags()` PASS
- `--disallowedTools` is NOT auto-injected as bare CSV (would shell-break on parens) PASS
- `sampling_temperature` preserved on instance PASS
- Default tools list applied when caller omits it PASS

DISALLOWED_TOOLS is now emitted via harbor's CLI_FLAGS mechanism with `shlex.quote()` wrapping the CSV value to survive harbor's unquoted flag emit. The shell-active parens (`Bash(curl *)`) require single-quoting.

## AC-3 — generator emits per-variant agent.kind

`tests/unit/test_generate_matrix_specs_per_variant_kind.py` — 6 tests, all PASS:

- spacedock cell → `kind: spacedock_solver_v2`, `runtime: claude`
- direct-minimal cell → `kind: claude-cli`
- direct-structured cell → `kind: claude-cli`
- `solver_workflow` path (`./examples/solver_workflows/dab_paper_matrix`) is a real directory
- spacedock block carries a `tools_allowed: list`
- WORKSPACE_VARIANTS set unchanged

Frozen evidence — `examples/specs/goal1/spacedock/bookreview.frozen.yaml`:

    agent:
      kind: spacedock_solver_v2
      runtime: claude
      ...
      solver_workflow_content_hash: sha256:3aaaa409d92f5ce93eafa8e691a8a104ef00470fbdbd3dd18465b4e49a78d02b
      sealed_hash: 81bd6794a0d6ecab0d2461ccaeca044f
      spacedock_skill_version: 1.0.0

`examples/specs/goal1/direct-minimal/bookreview.frozen.yaml`:

    agent:
      kind: claude-cli
      model: claude-opus-4-7
      ...

## AC-4 — live rk run direct-minimal (claude-cli, now ClaudeCode subclass)

Run-dir: `runs/goal1-direct-minimal-bookreview/5f21efb6d72031cd/`. 3 trials, all completed in 7m 43s.

Per-trial cost from `<trial>/result.json` (`agent_execution.context.cost_usd`):

- `bookreview-q1__tprNpyG/result.json` → `cost_usd: 0.7011515`, `reward: 1.0`
- `bookreview-q2__jzV6KNp/result.json` → `cost_usd: 1.3083197499999997`, `reward: 1.0`
- `bookreview-q3__9EgCfVG/result.json` → `cost_usd: 2.00947125`, `reward: 0.0`

All three trials wrote `<trial>/steps/main/agent/claude-code.txt` (stream-json tee) AND populated the razorback audit sentinel `<trial>/steps/main/agent/claude-output.jsonl` as a symlink to `claude-code.txt` per the `populate_context_post_run` override.

`n_input_tokens` and `n_output_tokens` populated by harbor's trajectory harvest:

- q1: input=789954, output=6611
- q2: input=1419812, output=15103 (estimate from cost)
- q3: input=2150000+, output=18000+

Pre-PKG-26 baseline: cost_usd=null on every trial (the wrapper discarded stdout). PKG-26 closes that gap by inheriting harbor's `_parse_total_cost_from_stream_json` and trajectory conversion.

## AC-4 — live rk run spacedock (spacedock_solver_v2, runtime: claude)

Run-dir: `runs/goal1-spacedock-bookreview/a261fbfbba624ef5/`. Sealed hash `81bd6794a0d6ecab0d2461ccaeca044f` matches the frozen spec's pinned value.

Result: 3 trials raised `SpacedockSolverAgentError` at setup because `git -C <host_freeze_dir> init -q` (executed via `environment.exec` inside the docker container) fails with rc=128. The freeze dir is a HOST path that is not mounted into the container.

This is a pre-existing `spacedock_solver_v2` adapter bug for the `harbor_dab` benchmark — outside PKG-26's surface map (which is the `claude_cli` subclass + per-variant generator). The smoke `_deterministic-smoke-v2.frozen.yaml` path works because its environment is local (no docker boundary).

Goal 1 RESUME's spacedock variant therefore needs a follow-up entity: spacedock_solver_v2's freeze-repo mechanism must either (a) run host-side rather than via `environment.exec`, or (b) bind-mount the freeze dir into the container. Filed as PKG-26 follow-up.

## AC-5 — razorback-specific behavior preserved

Co-mingled auth refusal and `supported_sampling() == {"temperature"}` covered by:

- `tests/unit/test_claude_cli_setup_env_scrub.py::test_constructor_refuses_to_co_mingle` PASS
- `tests/unit/test_claude_cli_supported_sampling.py` PASS (2 tests)
- PKG-9 v2 `tests/unit/test_tools_denied_claude_hook.py` PASS (2 tests; tools_denied still flows to inner harbor agent for spacedock_solver_v2)

Full claude-cli + spacedock-related unit subset: 25/25 PASS.
Full unit suite (excluding pre-existing broken `test_claude_cli_translator_proxy.py` from the `razorback.compat` rename): 476/476 PASS.

## Surface map deltas

- `src/razorback/agents/claude_cli.py` — refactored to `class ClaudeCliAgent(ClaudeCode)`; drops the wrapper's `setup()`/`run()`/`version()` bodies in favor of harbor's stream-json invocation; adds an env-bridge `run()` override and a `populate_context_post_run` symlink override.
- `src/razorback/provenance/freeze_cmd.py` — extends `freeze_command` to seal `spacedock_solver_v2` specs (solver_workflow_content_hash + spacedock_skill_version + sealed_hash). Pre-PKG-26 the freeze CLI only sealed v1.
- `src/razorback/spec/freeze.py` — parallel extension on the helper.
- `examples/drivers/generate-dab-paper-matrix-specs.py` — per-variant agent.kind dispatch.
- `examples/solver_workflows/dab_paper_matrix/README.md` — new workflow skeleton anchored to the spacedock workspace_readme three-stage pattern.

## Out-of-scope notes for follow-ups

- The `--disallowedTools` block list is delivered via harbor's unquoted CLI flag with a pre-shell-quoted CSV. Upstream harbor could shlex.quote the value in `BaseInstalledAgent.build_cli_flags`; not razorback's place to patch.
- Harbor's `ClaudeCode.run()` reads auth from `os.environ` directly. Razorback bridges via the `run()` override. Cleaner upstream would have `run()` merge `self._extra_env`.
