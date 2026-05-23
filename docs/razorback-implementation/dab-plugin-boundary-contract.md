---
id: 9gzbfzk0a878k8nqkk9ffjg8
title: Clarify and enforce the DAB plugin boundary contract
status: backlog
source: 2026-05-23 staff audit - core DAB plugin boundary is porous
started:
completed:
verdict:
score: 0.82
worktree:
issue:
pr:
mod-block:
---

## Problem

Core translation code says it does not import the DAB plugin and treats the
plugin as a subprocess boundary, but the implementation also imports
`razorback_plugin_dab.dataset_def` directly. The mixed boundary is hard to
reason about and makes it unclear whether external plugins should expose a typed
Python API, a CLI-only API, or both.

## Acceptance criteria

**AC-1 - Boundary choice is explicit.**
Razorback documents whether sibling benchmark plugins are consumed through a
typed Python entry point, a CLI subprocess contract, or a fallback sequence.
Verified by: the v2 spec or developer docs state the contract in one place.

**AC-2 - Code matches the documented boundary.**
Translation code no longer has comments that contradict its imports or
subprocess calls.
Verified by: tests and code review find no "never imports plugin" comment next
to direct plugin imports.

**AC-3 - DAB dataset definition consumption is covered.**
The DAB path continues to consume the packaged dataset definition without an
in-tree DAB adapter.
Verified by: DAB freeze/translate tests run from the installed plugin surface.

**AC-4 - Future plugin drift is guarded.**
A test or narrow contract fixture fails if the DAB plugin boundary changes
without updating core expectations.
Verified by: the fixture exercises the chosen public plugin API.
