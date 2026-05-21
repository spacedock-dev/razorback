---
id: 258p4x6h49czym2mafm7s5dg
title: PKG-24 — vendor dab-agent Dockerfile into razorback (close external repo dependency)
status: backlog
source: Captain directive 2026-05-20 ("dab-agent:latest is built from ~/git/dataagentbench, but we should consider have a copy here")
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

`dab-agent:latest` is razorback's canonical agent container for
harbor-DAB matrix runs (the `main` service in DAB tasks; the
default `PREBUILT_IMAGE_NAME` in `compose.py` and `prepare.py`).
But its Dockerfile and build context live in a SIBLING repository
at `~/git/dataagentbench/benchmark/Dockerfile.agent`, with the
build orchestrated by `~/git/dataagentbench/benchmark/setup.sh`
lines 143-146.

Razorback's source tree has no Dockerfile, no build command, no
documentation referencing how dab-agent gets built. The string
`dab-agent:latest` appears only as a constant in
`packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/compose.py:14`
(DEFAULT_AGENT_IMAGE).

Two failure modes this causes:
1. **Recovery dependency on external state.** When the Colima VM
   was reset 2026-05-20 (disk-recovery prune), `dab-agent:latest`
   was wiped from the image cache. Goal 1's matrix resume + any
   future harbor-DAB run is now blocked on someone re-running
   `~/git/dataagentbench/benchmark/setup.sh`. The captain had to
   provide the build path; razorback couldn't surface it from its
   own tree.
2. **Cross-repo coupling.** Razorback's CI / docs / contributor
   experience all implicitly assume `~/git/dataagentbench` is
   present and healthy. Onboarding requires "clone dataagentbench
   too; run setup.sh". This makes razorback non-portable.

The fix is to vendor the dab-agent build context into razorback:
copy `Dockerfile.agent` (renamed appropriately) into razorback,
expose a build command (e.g., `razorback dab build-agent` or
`packages/razorback-plugin-dab/scripts/build-agent.sh`), and update
documentation so razorback is self-sufficient for its own agent
images.

## Acceptance criteria

**AC-1 — Dockerfile committed under razorback.** The
dab-agent Dockerfile (currently
`~/git/dataagentbench/benchmark/Dockerfile.agent`) lives at a
razorback-internal path, e.g.,
`packages/razorback-plugin-dab/agent-image/Dockerfile`. The
content is byte-identical to upstream OR cite-explicit if any
adjustment was made.
Verified by: file exists at the expected path; `diff` against
upstream Dockerfile.agent shows zero or documented-only changes.

**AC-2 — Build command exposed.**
A scripted build command in the razorback tree (e.g.,
`packages/razorback-plugin-dab/agent-image/build.sh` or a CLI
subcommand `razorback dab build-agent`) builds `dab-agent:latest`
without requiring `~/git/dataagentbench` to be present.
Verified by: running the build command from a clean checkout
produces `dab-agent:latest` in the local docker daemon.

**AC-3 — Documentation updates.**
The repo README + harbor-DAB plugin README reference the build
step. Onboarding instructions no longer say "clone dataagentbench"
for the purpose of the agent image.
Verified by: README updates committed; grep for
`~/git/dataagentbench` in razorback's docs returns only references
to DATA bind-mount paths, not agent-image paths.

**AC-4 — Dataagentbench dependency narrowed.**
Razorback's hard dependency on `~/git/dataagentbench` is reduced
to: dataset bind-mount (PKG-14's `data_root` parameter — already
isolated). The agent-image build is no longer a coupling point.
Verified by: a clean razorback checkout can build the agent image
and run any harbor-DAB task that doesn't require live dataset data
(unit tests against fixtures); live runs still need the data bind-
mount but that's the only remaining external dependency.

## Test plan

- **Unit:** A trivial assertion test that the Dockerfile is
  present at the expected path.
- **Integration:** A build smoke (CI-friendly — skip-if-no-docker)
  that runs the build command and asserts `docker images
  dab-agent:latest` is non-empty.
- **Acceptance:** A clean razorback checkout (with
  ~/git/dataagentbench moved or removed) can build the agent
  image and run a harbor-DAB unit test.

## Out of scope

- ade-bench-agent image (different agent for ade-bench
  matrices) — separate follow-up after PKG-23 + the ade-bench
  runtime contract lands.
- Multi-arch / cross-platform builds. Vendor as-is initially.
- Registry publication (push to ghcr.io etc.) — local-only is fine
  for now.

## Depends on

- None blocking; can ship independently of Goal 1/Goal 2 work.

## Resume hook

After PKG-24 ships, future Colima/docker resets do not block
goal1 resume on external repo state. The razorback maintainer
runs the in-tree build command and continues.
