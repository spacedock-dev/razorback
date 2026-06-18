---
id: h1cxe6x9zcyfq0zrs0rejsp7
title: spider2-dbt — user-facing example spec
status: backlog
source: follow-up from spider2-dbt-source-resolution-and-run-wiring (no example exercises the new kind:harbor + qualified-ref path)
started:
completed:
verdict:
score:
worktree:
issue:
pr:
mod-block:
---

## Problem

After `spider2-dbt-source-resolution-and-run-wiring` ships, no
user-facing example spec demonstrates the new capability:
`kind: harbor` + `dataset: spider2-dbt/spider2-dbt@1.0`. The only
existing spec, `examples/specs/pkg40-spider2-dbt-harbor-task-view-codex.yaml`,
uses `kind: harbor-local` pointing straight at a fixture dir, which
bypasses the dataset-resolution path; the qualified-ref form lives only
in an internal `nop`-agent test fixture. This task adds a real example
spec under `examples/specs/` so a user can see how to run the
spider2-dbt benchmark. A full run is gated on the PKG-40 harbor-package
checkout blocker, so the example documents that prerequisite and the AC
verifies what is checkable offline (schema-valid + freezes).

## Acceptance criteria

**AC-1 — A `kind: harbor` spider2-dbt example spec exists and freezes cleanly.**
Verified by: `uv run rk freeze examples/specs/<name>.yaml` exits 0 and
writes `examples/specs/<name>.frozen.yaml` with
`benchmark.dataset == "spider2-dbt/spider2-dbt@1.0"`.

**AC-2 — The example records the `spider2-dbt@1.0` hydration prerequisite for a full run.**
Verified by: `grep -F 'spider2-dbt@1.0' examples/specs/<name>.yaml` returns
the header note naming the harbor-package hydration step (the PKG-40
blocker), so the user knows what a live run requires.

## Test plan

A unit/integration check that the example freezes (AC-1); confirm the
frozen dataset ref is the qualified form. No live run is attempted while
the PKG-40 blocker stands.

## Out of scope

Unblocking the `spider2-dbt@1.0` harbor-package checkout (PKG-40,
externally owned). The dbt-deps/preflight parity, the verifier, and the
scored-run task-identity reconciliation (their own entities).
