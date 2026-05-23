---
id: 9sq4r4tf6whgga5zzx3zfept
title: Make Codex install environment proxy scrubbing deterministic
status: backlog
source: 2026-05-23 staff audit - Codex install proxy stripping can reintroduce proxy variables
started:
completed:
verdict:
score: 0.76
worktree:
issue:
pr:
mod-block:
---

## Problem

The Codex runtime strips proxy variables for install commands, but one helper
initializes those keys to empty strings and then overlays caller-provided
environment values. A caller env containing `HTTPS_PROXY` can therefore
reintroduce the proxy variable that the helper intended to scrub.

## Acceptance criteria

**AC-1 - Proxy scrub wins after env merge.**
Codex install-command environment construction merges caller env first and then
overwrites proxy variables with the intended scrubbed values.
Verified by: a unit test passes `HTTPS_PROXY`, `HTTP_PROXY`, and lowercase
variants in the caller env and asserts the command env has the scrubbed values.

**AC-2 - Runtime proxy behavior is unchanged where required.**
Build/runtime paths that intentionally need proxy settings still receive them
through the documented path.
Verified by: existing proxy separation tests stay green.

**AC-3 - Helper behavior is documented in code.**
The env helper name or a short comment makes clear whether it removes, blanks,
or preserves proxy keys.
Verified by: code review can infer the contract without reading call-site
history.
