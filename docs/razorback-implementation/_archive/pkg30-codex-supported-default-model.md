---
id: p5g5bk2dh0pg4xkszbrgv84v
title: PKG-30 — use a supported Codex model for benchmark specs
status: done
source: PKG-29 validation — freeze setup passes, but `gpt-5.1-codex` is rejected by the available Codex auth
started: 2026-05-21T08:50:00Z
completed: 2026-05-21T08:53:00Z
verdict: PASSED
score: 1.00
worktree:
issue:
pr:
mod-block:
---

## Problem

The Codex benchmark generator and smoke specs default to
`gpt-5.1-codex`. Local Codex auth rejects that model after PKG-29
successfully reaches the agent layer. A direct Codex CLI probe with
`gpt-5.5` succeeds, so the benchmark specs need a supported default
before DAB or ade-bench full runs.

## Acceptance criteria

**AC-1 — Checked-in Codex smoke specs use a supported model.**
The in-tree Codex smoke specs use `gpt-5.5`.
Verified by: grep and freeze/smoke execution of `_codex-smoke-v2`.

**AC-2 — Matrix generation remains configurable.**
The Codex benchmark spec generator defaults to `gpt-5.5` but exposes
a `--model` override for future score runs.
Verified by: focused generator unit tests.

**AC-3 — Supported-model smoke reaches task completion.**
`_codex-smoke-v2` no longer stops at model rejection.
Verified by: `rk run` on the frozen smoke spec exits 0 without
`NonZeroAgentExitCodeError`.

## Depends on

- `pkg29-spacedock-solver-git-bootstrap`

## Stage Report: implementation

- DONE: Checked-in Codex smoke specs now use `gpt-5.5`.
  `_codex-smoke-v2`, `codex-dab-smoke`, and `codex-ade-bench-smoke` were updated from the rejected model to the verified supported model.
- DONE: Matrix generation remains configurable.
  `examples/drivers/generate-codex-benchmark-specs.py` defaults to `gpt-5.5` and adds `--model` for explicit score-run overrides.
- DONE: Supported-model smoke reaches task completion.
  `uv run rk run examples/specs/_codex-smoke-v2.frozen.yaml --runs-dir runs/pkg30-codex-gpt55-smoke --allow-plugin-drift --allow-alias-drift` exited 0 with one trial, zero exceptions, and reward `1.0`.

### Validation

- `codex exec --ephemeral --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --model gpt-5.5 --json -c model_reasoning_effort=low 'Return exactly OK.'` exited 0.
- `uv run pytest tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_runtime_adapters.py tests/integration/test_v2_freeze_dir_mechanism.py -q` passed: 22 tests.
- `uv run python examples/drivers/generate-codex-benchmark-specs.py --benchmark dab --dab-data-root <local-dab-data-root>` printed all 12 DAB cells.
- `uv run rk freeze examples/specs/_codex-smoke-v2.yaml --allow-missing` exited 0.
