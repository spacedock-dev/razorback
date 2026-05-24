---
id: 8qnj22s6a93akscdg1sxej8c
title: ade-bench task images — bake claude CLI via harbor_view image-layer extension
status: backlog
source: 2026-05-25 jj cycle-5 + cycle-6 findings (worktree `.worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline`, commits `4ff32ea` cycle-5, `66eb811` cycle-6). Both cycles stopped at `RazorbackClaudeCode.setup` (`src/razorback/_runtime/claude.py:118`) raising `RazorbackClaudeCodeError: "claude CLI not available in the container (exit=127)"`. ade-bench task images are built from upstream Dockerfiles (`FROM python:3.11-slim`) and do not include claude; razorback's setup override bypasses Harbor's `BaseInstalledAgent.setup` auto-install (`npm install -g @anthropic-ai/claude-code`). Cycle-6 also confirmed switching the agent kind from `claude-cli` to `spacedock_solver+claude` does NOT route around the blocker — the failure is in razorback's runtime adapter regardless of outer agent kind. The image-layer extension (mirroring the existing `_ensure_dbt_deps_image_layer` pattern in `harbor_view.py`, analog of PKG-23 / PKG-27 bridge work) is the lowest-impedance fix per ensign + captain decision 2026-05-25.
score: 0.85
auto-approve: false
worktree:
issue:
pr:
mod-block:
started:
completed:
verdict:
---

## Problem

Any claude-runtime agent (whether `agent.kind: claude-cli` or
`agent.kind: spacedock_solver` with `runtime: claude`) dispatched against
ade-bench fails at `_inner.setup()` because the materialized task
image does not carry the claude CLI. `RazorbackClaudeCode.setup`
at `src/razorback/_runtime/claude.py:118` raises
`RazorbackClaudeCodeError: claude CLI not available in the container
(exit=127)`. Two consecutive jj cycles (5 + 6) confirmed this is
the binding blocker for the entire Goal 2 matrix — no matter what
agent kind the spec selects, the runtime adapter cannot run claude.

Harbor's `BaseInstalledAgent.setup` would auto-install
`@anthropic-ai/claude-code` via npm, but razorback's setup override
bypasses that path (likely deliberate — egress / determinism /
provenance concerns; the override predates this entity and its
rationale should be confirmed from the original commit history
before re-introducing auto-install behavior).

The cleanest fix is to extend `harbor_view.py`'s `_ensure_..._image_layer`
family with `_ensure_claude_cli_image_layer`. That family already
mirrors the pattern: `_ensure_dbt_deps_image_layer` (PKG-23 era)
appends dbt deps on top of upstream Dockerfile FROM base; the
claude analog appends claude CLI install on top of any
upstream FROM base. The layer is added at image-build time, not
runtime setup time, so the runtime adapter's existing assertion
("claude must already be present") remains correct.

Once this entity ships:
- jj `goal2-ade-bench-haiku-baseline` cycle-7 can re-run T0 phases
  2-5 against the post-layer ade-bench task views and (if green)
  proceed with the 48×1 matrix dispatch.
- Any future razorback claude-runtime dispatch against an ade-bench
  task view (or any other dataset-ref benchmark with a non-claude
  upstream base) works without further bridge work.

## Acceptance criteria

**AC-1 — `_ensure_claude_cli_image_layer` exists and mirrors the
dbt-deps pattern.** Function lives in `src/razorback/harbor_view.py`
(or the matching module where `_ensure_dbt_deps_image_layer` lives —
locate it). Signature matches the family convention. Behavior:
given a materialized task-view directory whose Dockerfile FROM
base does not carry claude, append a layer that installs claude
via `npm install -g @anthropic-ai/claude-code` (or whichever
mechanism harbor's `BaseInstalledAgent` would normally use); the
post-layer image, when run, has `claude --version` exit 0.

Verified by:
- `grep -n "_ensure_claude_cli_image_layer" src/razorback/harbor_view.py` returns ≥1 match (function definition).
- `uv run pytest tests/unit/test_ade_bench_image_layer.py -v` includes a RED→GREEN unit test asserting the layer is invoked on the dataset-ref materialization path when the FROM base lacks claude.

**AC-2 — Layer-built image carries claude CLI at runtime.** Using
the same test fixture as the dbt-deps layer test (or the closest
analog), build an image FROM `python:3.11-slim` + the new layer,
start it, and assert `claude --version` exits 0 inside the
container. This is the mechanism gate before any jj live re-run.

Verified by: a unit or integration test that builds the layered
image and asserts `subprocess.run(["docker", "run", "--rm", "{image}",
"claude", "--version"]).returncode == 0`. Test file path noted in
stage report.

**AC-3 — `RazorbackClaudeCode.setup` no longer raises on
ade-bench task views.** With the layer wired into the dataset-ref
dispatch path, the cycle-5/cycle-6 failure mode (raising
`RazorbackClaudeCodeError` at `_runtime/claude.py:118`) does not
reproduce on a jj T0 single-task probe against the post-layer image.

Verified by: jj worktree (`.worktrees/spacedock-ensign-goal2-ade-bench-haiku-baseline`)
runs T0 phases 2-5 against the same canonical pin
(`dbt-labs/ade-bench@sha256:2c1f9e69...`) used in cycle-5/6 and
exits clean. The trace path + the absence of the cycle-5/6
exception in the trace are cited in jj's cycle-7 stage report
when this entity unblocks jj's resumption.

**AC-4 — Non-ade-bench dispatch paths are not regressed.** The
layer extension MUST be scoped to dataset-ref materialization
paths whose FROM base lacks claude — not unconditionally applied.
Existing DAB dispatch paths (dab-agent:latest already carries
claude) and any spec whose `docker_image_override` resolves to
an already-claude-carrying image must NOT pay the layer cost.

Verified by:
- `uv run pytest tests/` exits 0 (full suite); pre-existing
  failures (LFS-hydration etc.) reproduce on baseline `main`
  with no new failures introduced.
- A unit test asserts the layer is NOT applied when the resolved
  image already carries claude.

## Test plan

- **Locate dbt-deps layer analog** as the reference implementation
  before any code change. `grep -n "_ensure_dbt_deps_image_layer\|_ensure_.*_image_layer" src/razorback/` locates the family.
- **Investigate the setup override's original rationale** before
  changing it — `git log -p --follow src/razorback/_runtime/claude.py` and the original commit message of the override. Document
  the rationale in the impl stage report so the layer approach
  is shown to respect whatever the override was guarding against.
- **TDD:** RED unit test for AC-1 → GREEN layer implementation →
  RED unit test for AC-4 (no-op when claude present) → GREEN
  scoping → integration test for AC-2 (docker build + run) →
  manual cross-check against jj's cycle-7 probe for AC-3.
- **Mechanism-first per CLAUDE.md:** the AC-2 integration test
  (smallest end-to-end build+run of the layered image) goes
  BEFORE any AC-3 integration with jj's worktree.

## Out of scope

- **Restoring `BaseInstalledAgent.setup` auto-install in
  `RazorbackClaudeCode.setup`.** Shape (2) from cycle-6's
  three-option decision tree. Captain chose shape (1) for this
  entity; if the layer approach exposes new failure modes,
  shape (2) is the fallback as a sibling entity.
- **Extending `docker_image_override` to patch FROM lines.**
  Shape (3) from cycle-6's decision tree. Wider razorback surface
  change; not pursued here.
- **Goal 2 matrix dispatch itself.** That stays with jj
  `goal2-ade-bench-haiku-baseline`. This entity unblocks jj; jj
  ships the baseline number.
- **PKG-23 / PKG-27 bridge work generalization.** This entity
  adds one more layer to the existing pattern; it does not
  refactor the family into a registry or generic mechanism.
  If a third or fourth bridge layer arrives, then refactor.
- **Other dataset-ref benchmarks (spider2-dbt, livecodebench,
  etc.).** This entity is scoped to ade-bench because that's
  the demonstrated blocker. If another benchmark hits the same
  failure mode, file a sibling or widen this entity's scope at
  that time.

## Depends on

- (none — pure infrastructure work; mechanism-validated by the
  AC-2 integration test before live use)

## Resume hook

When this lands:
- jj `goal2-ade-bench-haiku-baseline` worktree resumes at cycle-7.
  The cycle-7 dispatch starts from the same probe spec
  (spacedock_solver+claude+Haiku on the canonical ade-bench pin)
  and runs T0 phases 2-5 against the post-layer image. If T0
  green, jj proceeds with T1-T6 matrix dispatch at N=1.
- Any future claude-runtime dispatch against ade-bench (or other
  dataset-ref benchmarks with non-claude FROM bases) works without
  the cycle-5/6 setup-time failure.

The `auto-approve: false` flag is set because the image-layer
mechanism affects every claude-runtime ade-bench dispatch — a
captain-facing infrastructure surface — and the captain should
explicitly approve the layer's wire-in before it lands.
