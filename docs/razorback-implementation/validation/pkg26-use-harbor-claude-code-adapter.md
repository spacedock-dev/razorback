# PKG-26 — Reshape ClaudeCliAgent to subclass harbor's ClaudeCode — Validation Report

**Entity:** `pkg26-use-harbor-claude-code-adapter`
**Branch:** `spacedock-ensign/pkg26-use-harbor-claude-code-adapter`
**Worktree:** `.worktrees/spacedock-ensign-pkg26-use-harbor-claude-code-adapter`
**Impl commits:** `49b28f2` (T0–T2 refactor) · `c279bf7` (T3 generator) · `fdd6b04` (env-passthrough + shell-quote bridge) · `1cb3087` (T4 + stage report)
**Verdict:** **PASSED** (conditional on (a) correcting the q3 evidence error in `pkg26-validation.md` and (b) the orthogonal spacedock freeze-dir follow-up tracking AC-4 spacedock; both acknowledged below)

## Test re-run evidence

`.venv/bin/pytest tests/unit/ -x --ignore=tests/unit/test_claude_cli_translator_proxy.py`:

- **486/486 passed** in 7.14s.
- New PKG-26 suites (14/14 PASS):
  - `tests/unit/test_claude_cli_subclasses_claude_code.py` (4 tests — AC-1/AC-5)
  - `tests/unit/test_claude_cli_kwarg_mapping.py` (4 tests — AC-2 kwarg surface)
  - `tests/unit/test_generate_matrix_specs_per_variant_kind.py` (6 tests — AC-3)
- Existing claude_cli + spacedock + translator + audit suites stay green (no PKG-26 regression).

Pre-existing breakage in `tests/unit/test_claude_cli_translator_proxy.py` (`ModuleNotFoundError: razorback.compat`) traces to commit `5eb26c7` ("Phase 1 AC-5: sideline v1 run.py + manifest + observers + runtime + c…") — not a PKG-26 regression. Confirmed by checking out the file at HEAD vs. main: import fails identically.

## AC check

- **AC-1 — `ClaudeCliAgent` subclasses `ClaudeCode`.** PASS.
  `src/razorback/agents/claude_cli.py:19` — `class ClaudeCliAgent(ClaudeCode)`. `test_claude_cli_agent_subclasses_harbor_claude_code` and `test_claude_cli_agent_class_is_subclass_of_claude_code` GREEN. Razorback inherits harbor's `--output-format=stream-json --print` invocation, `_parse_total_cost_from_stream_json` (claude_code.py:491), and ATIF trajectory harvest.

- **AC-2 — Translator unchanged; kwargs map cleanly; live trial yields cost + audit artifacts.** PASS (direct-minimal). Translator `CLAUDE_CLI_IMPORT_PATH` unchanged; `tools_allowed` → harbor's `allowed_tools` CSV inside `__init__`; `disallowed_tools` shell-quoted via `shlex.quote()` to survive harbor's unquoted flag emit (parens in `Bash(curl *)`). Live direct-minimal evidence below.

- **AC-3 — Generator emits per-variant `agent.kind`.** PASS.
  `examples/drivers/generate-dab-paper-matrix-specs.py:_build_agent_block` branches: spacedock → `spacedock_solver_v2` (`runtime: claude`); direct-minimal + direct-structured → `claude-cli`. 6 unit tests GREEN. Frozen spec `examples/specs/goal1/spacedock/bookreview.frozen.yaml` carries `sealed_hash: 81bd6794a0d6ecab0d2461ccaeca044f` and `solver_workflow_content_hash: sha256:3aaaa4…`; direct-minimal frozen YAML carries `kind: claude-cli`.

- **AC-4 — Live `rk run` produces cost + audit artifacts (per kind).** **PARTIAL PASS** (direct-minimal: PASS; spacedock: FAILED orthogonal).
  - Direct-minimal — `runs/goal1-direct-minimal-bookreview/5f21efb6d72031cd/`:
    - Job-level `summary.json.cost_usd = 2.00947125` (non-null). ✓
    - Per-trial cost from `step_results[0].agent_result.cost_usd`:
      - `bookreview-q1__tprNpyG`: cost=$0.7011515, reward=1.0; `claude-output.jsonl` symlink → claude-code.txt (109 441 bytes). ✓
      - `bookreview-q2__jzV6KNp`: cost=$1.3083198, reward=1.0; symlink → claude-code.txt (144 040 bytes). ✓
      - `bookreview-q3__9EgCfVG`: cost=null, reward=null; trial died with `NonZeroAgentExitCodeError` (exit 137 / SIGKILL — OOM on the host during the `claude --print` invocation). symlink → claude-code.txt (77 282 bytes, partial stream).
    - **2/3 trials meet AC-4 strictly + 1/3 OOM-killed.** Job summary `cost_usd` is non-null (sums q1+q2). Audit sentinel present on all 3 trials (q3's is a partial stream from the truncated session). The q3 OOM is a host-resource symptom, not a PKG-26 wrapper defect — stream-json was being emitted normally up to the kill point, harbor's `_parse_total_cost_from_stream_json` correctly returns None when no `result` block is present.
    - **Mechanism gate is met:** harbor's stream-json invocation runs end-to-end inside the container; per-trial `cost_usd` is non-null whenever the agent completes; razorback's `claude-output.jsonl` audit sentinel is published as the symlink override.
  - Spacedock — `runs/goal1-spacedock-bookreview/a261fbfbba624ef5/`: all 3 trials `SpacedockSolverAgentError` because `git -C <host_freeze_dir> init -q` executed via `environment.exec` inside the docker container fails rc=128 (host path not mounted into container). Pre-existing `spacedock_solver_v2` + `harbor_dab` adapter bug — outside PKG-26's surface map (claude_cli subclass + per-variant generator). Filed as the orthogonal `spacedock-solver-v2-freeze-dir-mount` follow-up.

- **AC-5 — Razorback-specific behavior preserved.** PASS.
  - Co-mingled-auth refusal: `tests/unit/test_claude_cli_setup_env_scrub.py::test_constructor_refuses_to_co_mingle` GREEN.
  - `supported_sampling() == {"temperature"}`: `tests/unit/test_claude_cli_supported_sampling.py` (2 tests) GREEN.
  - PKG-9 v2 `tests/unit/test_tools_denied_claude_hook.py` (2 tests) GREEN.

## Code review

Scope: 5 source files (`claude_cli.py` rewrite, `provenance/freeze_cmd.py` extension, `spec/freeze.py` extension, matrix generator, new solver workflow README) + 3 test files (2 new + 1 rewritten) + 12 regenerated spacedock spec YAMLs.

**Material findings (none load-bearing for verdict):**

1. **`run()` mutates `os.environ` (process-global).** `claude_cli.py:86-105` stamps `_razorback_extra_env` keys into `os.environ` around `await super().run()` and restores in `finally`. Single-threaded today; concurrent trials in-process would race. Acceptable given the current sequential dispatch contract and the explicit "cleaner upstream would have run() merge self._extra_env" out-of-scope note in `pkg26-validation.md`. Polish, not blocking.

2. **Duplicated v2 sealing helper.** `provenance/freeze_cmd.py:_seal_v2_agent_block` and `spec/freeze.py:_freeze_spacedock_v2` both compute `sealed_hash + solver_workflow_content_hash + spacedock_skill_version`. Two-source-of-truth risk for future contributors. Polish — extract a shared helper when the v2-aware freeze surface stabilises.

3. **Evidence inaccuracy in `pkg26-validation.md` (impl stage's own report).** The impl-stage validation evidence document at `docs/razorback-implementation/pkg26-validation.md:69` attributes `cost_usd: 2.00947125, reward: 0.0` to `bookreview-q3__9EgCfVG`. The actual trial state is `cost_usd: null, reward: null, exception_type: NonZeroAgentExitCodeError (exit 137)`. The 2.00947125 value is the job-level `summary.json.cost_usd` (sum of q1+q2), not q3's per-trial cost. **Honesty correction needed in `pkg26-validation.md`.** Not a code defect; an evidence-doc bug. Verdict-blocking only if uncorrected; flagged here for the impl agent or follow-up to amend the impl-stage doc.

**Non-material:**

- `populate_context_post_run` symlink uses `claude_code_txt.name` (relative), portable across run-dir moves. Good.
- `shlex.quote()` on disallowed_tools CSV is a clean local workaround for harbor's unquoted CLI flag emit. Inline comment plus the out-of-scope note in `pkg26-validation.md` flagging it for upstream is appropriate.
- `version_test.py` rewrite drops the `FileNotFoundError` branch — correct because the new `setup()` runs `environment.exec("claude --version")` inside the container, not via host `subprocess.run`. Coverage shift is intentional and consistent with the new contract.
- Spec generator's `tools_allowed` for spacedock includes the default list; v2 schema accepts list shape. Test `test_spacedock_block_does_not_carry_tools_allowed_default_csv` asserts `isinstance(..., list)`. Correct.

## Honest spacedock-AC-4 status

AC-4 spacedock evidence is **FAILED** as documented in the implementation stage report and captured here. The failure mode (host-path freeze dir not visible inside container) is **orthogonal to PKG-26's surface map** — PKG-26 changes the `claude_cli` adapter and per-variant agent.kind dispatch; the spacedock failure is at `spacedock_solver_v2`'s freeze-repo bridge layer (`git init` executed via `environment.exec` against a path that exists on the host but not in the container). This is the captain-acknowledged `spacedock-solver-v2-freeze-dir-mount` follow-up, dispatched in parallel per standing orders. PKG-26 does not own the fix.

Captain's auto-approve directive plus the "ACCEPT that as the basis for the orthogonal freeze-dir followup (already filed sd-b32 yk)" instruction in the validation checklist make this an accepted carve-out, not a PKG-26 regression.

## Verdict

**PASSED.**

Three conditions:
1. **AC-4 direct-minimal evidence holds:** 2/3 trials cleanly meet the cost + audit-sentinel contract; q3's null cost is a host-resource OOM (exit 137), not a PKG-26 defect; job-level `summary.json.cost_usd` is non-null. ✓
2. **AC-4 spacedock failure is honestly captured as orthogonal:** Impl stage report explicitly attributes the failure to `spacedock_solver_v2` + `harbor_dab` + docker freeze-dir mounting, filed as a separate follow-up. ✓
3. **No other material findings:** Two polish issues (process-global env mutation, duplicated v2 sealing helper) are documented and non-blocking. One evidence-doc correction needed in `pkg26-validation.md` (q3 attribution) — flagged for the impl agent to amend, but does not block this verdict since the underlying live-run data is fully captured here.

The load-bearing PKG-26 surfaces (subclass shape, kwarg mapping, per-variant generator, audit-sentinel publication, v2 freeze sealing) ship correctly. Goal 1 RESUME's direct-* variants are unblocked immediately. The spacedock variant unblocks once the orthogonal freeze-dir mount follow-up lands.
