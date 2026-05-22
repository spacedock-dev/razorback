# Razorback

A benchmark runner for agentic research workflows. See
`docs/razorback-implementation/README.md` for the implementation workflow.

## Where do runs go?

`rk run` writes one run-dir per `(spec, job)` under a base "runs-dir":

- **Default**: `$RAZORBACK_RUNS_DIR` if set; else `$XDG_DATA_HOME/razorback/runs`
  if set; else `~/.local/share/razorback/runs`.
- **Override**: pass `--runs-dir <path>` to `rk run`.

The default lives OUTSIDE your git worktree on purpose: `git worktree remove
--force` cannot destroy experiment outputs written there. If you pin a
worktree-relative path (`--runs-dir _runs`, `--runs-dir runs/`) the outputs
share the worktree's fate.

## Quickstart

```
uv sync
uv run rk run examples/specs/_deterministic-smoke.yaml
ls ~/.local/share/razorback/runs/
```
