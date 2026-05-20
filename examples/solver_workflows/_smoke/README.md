# Smoke solver workflow (Phase 3 v2 reference)

Minimal solver_workflow for the `_deterministic-smoke-v2.frozen.yaml` reference
spec. One stage, claude-only. The body of this README drives stage names per
spec §4.3.2.

## Stages

- model

## Stage: model

Read the task instruction and produce the requested output. No multi-stage
orchestration in the smoke; the real workflow mods land in phase 4a+.
