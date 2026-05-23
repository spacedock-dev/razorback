---
id: p35e5xqtr9yrcz37e4p06rvq
title: Avoid global os.environ mutation during Harbor run env templating
status: backlog
source: 2026-05-23 staff audit - run env templating mutates global process environment
started:
completed:
verdict:
score: 0.55
worktree:
issue:
pr:
mod-block:
---

## Problem

`rk run` mirrors selected auth variables into `os.environ` while preparing
Harbor serialization. The mutation is not restored. That is brittle in tests
and long-lived processes because one run can leak environment state into later
operations.

## Acceptance criteria

**AC-1 - Run env templating avoids persistent global mutation.**
The Harbor serialization path either passes an explicit env mapping or uses a
save/restore context manager around any temporary `os.environ` writes.
Verified by: a unit test asserts environment variables are restored after the
run-preparation helper exits.

**AC-2 - Auth propagation still works.**
The Harbor task config still receives the intended provider auth variables when
they are configured.
Verified by: an existing or new test checks the serialized env template.

**AC-3 - Failure paths restore environment too.**
Exceptions during serialization do not leave mirrored auth variables in
`os.environ`.
Verified by: a test forces an exception and checks environment restoration.
