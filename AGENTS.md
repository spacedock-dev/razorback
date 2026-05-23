# Agent Notes

## Project

Razorback is a Python CLI (`rk`) built on Harbor for reproducible
agentic benchmark runs. It freezes specs, runs Harbor jobs, scores
results, audits traces for leakage, and writes run-dir artifacts.

Primary code paths:

- `src/razorback/` — core CLI, spec parsing/freezing, translation,
  scoring, auditing, provenance, agents.
- `packages/razorback-plugin-dab/` — DAB Harbor task generator.
- `examples/specs/` — runnable benchmark specs.
- `examples/drivers/` — matrix drivers and aggregators.
- `docs/razorback-implementation/` — Spacedock workflow state.

## Workflow

Use `docs/razorback-implementation` as the active workflow. Check
state with the Spacedock status tool for that workflow directory.

Do not touch tasks already marked in implementation unless assigned.

## Commands

Use `uv run` for project commands:

```bash
uv run pytest
uv run rk freeze <spec.yaml>
uv run rk run <spec.frozen.yaml> --runs-dir <runs-dir>
uv run rk score <run-dir> --format json
uv run rk audit <run-dir> --policy strict --format json
```

DAB data is external to this repo. Pass it through specs as a
machine-local path, typically via a `data_root` value or generated
specs.

## Editing

Keep changes scoped. Prefer `rg` for search. Do not rewrite workflow
history or revert user/other-agent changes. Use worktrees for
workflow implementation stages. Commit meaningful workflow state and
stage work when operating as first officer or ensign.
