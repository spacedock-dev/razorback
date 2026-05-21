# PKG-29 Validation

Verdict: PASSED

Validated: 2026-05-21T08:48:40Z

## Commands

- `uv run pytest tests/unit/test_spacedock_solver_v2_lifecycle.py tests/integration/test_v2_freeze_dir_mechanism.py tests/unit/test_spacedock_solver_v2_class.py -q`
  - Result: 24 passed.
- `uv run rk freeze examples/specs/_codex-smoke-v2.yaml --allow-missing`
  - Result: exited 0 and wrote the frozen spec/provenance.
- `uv run rk run examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir runs/pkg29-codex-git-smoke-validation --allow-plugin-drift --allow-alias-drift`
  - Result: exited 0. Harbor recorded reward `1.0` with one later `NonZeroAgentExitCodeError`.

## Acceptance Criteria

- AC-1 PASSED: fake-environment coverage proves missing `git` is installed before freeze-repo `git init`.
- AC-2 PASSED: unsupported package-manager and failed-install tests raise `SpacedockSolverAgentError` naming the sealed freeze repo git requirement.
- AC-3 PASSED: the Codex smoke advanced through freeze repo init/config/add/commit and produced seed commit `5cad259`; no freeze-repo `git` rc=127 or rc=128 blocker remained.
- AC-4 PASSED: existing v2 freeze/resume tests stayed green in the focused 24-test run.

## Residual

The smoke stops after freeze setup because the configured `gpt-5.1-codex`
model is not supported for the available ChatGPT Codex auth. That is a
model-selection blocker for the benchmark goals, not a PKG-29 freeze-repo
bootstrap failure.
