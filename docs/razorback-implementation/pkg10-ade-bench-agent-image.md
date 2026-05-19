---
id: m914zq0kkpjcs4119wbzyssz
title: PKG-10 — ade-bench-agent image (Dockerfile layering ade-bench's task-specific tools onto dab-agent)
status: backlog
source: FU-2 validation report (2026-05-19) — real ade-bench tasks reach agent.run() under dab-agent:latest but score 0.0 because dbt/gdown/tmux/asciinema/nodejs/yq/pyyaml are absent
score: 1.0
started:
completed:
verdict:
worktree:
issue:
pr:
mod-block:
---

## Problem

FU-2 shipped the `--image` override mechanism so razorback's
ade-bench adapter can route ade-bench tasks at a non-default
container image. The live airbnb001 probe confirmed the mechanism
works: the agent reaches `agent.run()` without a setup-time crash,
and `summary.json` carries a numeric (not null) score. But the
score is 0.0 across the board because real ade-bench tasks need
task-specific tooling — `dbt`, `gdown`, `tmux`, `asciinema`,
`nodejs`, `yq`, `pyyaml`, plus likely `python-dotenv` and other
deps surfaced by ade-bench's `setup.sh` files per task — and
`dab-agent:latest` lacks them. The agent runs, the setup.sh
fails, the task ends with a graceful-degradation 0.0 (correctly
caught by AC-4's typed missing-tool error).

Without an `ade-bench-agent:latest` image that layers these tools
onto `dab-agent:latest`, the planned ade-bench haiku baseline run
(deliverable 2 from CL 2026-05-19; ~$20-40 at Haiku rates for 48
tasks × N=1) produces the same 0.0 shape FU-2 hit. No baseline
signal, no real number to compare against.

## Unlocks

- **The ade-bench haiku baseline run** becomes meaningful: agents
  have the tools they need; scores reflect agent behavior, not
  missing-binary failures.
- Future ade-bench/opus runs reuse the same image with no
  additional work.
- Establishes the layering pattern (`benchmark-specific-agent`
  FROM `dab-agent`) that future benchmarks (τ-bench, HAL,
  terminal-bench-2) can crib from.
- Decouples razorback's `dab-agent` (minimal, fast to rebuild)
  from per-benchmark tooling sprawl.

## Depends on

- **FU-2** (done, merged) — provides the `--image` override
  mechanism that PKG-10 produces an image for.
- **No PKG-2 / PKG-3 dependency.** Different benchmark adapter,
  different surface. PKG-10 can run fully parallel to the
  PKG-2/PKG-3 wave.
- **Survey input**: `~/git/ade-bench/` (or wherever the ade-bench
  source lives) — the worker needs to inventory `setup.sh` files
  across the 48-task corpus to derive the full tool list. The
  handoff's list (`dbt/gdown/tmux/asciinema/nodejs/yq/pyyaml`) is
  the FU-2-observed subset; the survey should produce the union.

## Acceptance criteria

**AC-1 — Dockerfile at `images/ade-bench-agent/Dockerfile` FROMs
`dab-agent:latest` and installs the ade-bench task-tool set.**
Verified by: the file exists; `FROM dab-agent:latest` is line 1
(or one of the first 3 non-comment lines); `RUN apt-get install`
+ `RUN pip install` blocks cover the surveyed tool union (at
minimum: `dbt-core`, `gdown`, `tmux`, `asciinema`, `nodejs`,
`yq`, `pyyaml`, `python-dotenv`). The worker's survey output is
committed as a sibling artifact at `images/ade-bench-agent/
tool-survey.md` citing each tool's source `setup.sh`.

**AC-2 — Image builds cleanly.**
Verified by: `docker build -t ade-bench-agent:latest images/
ade-bench-agent/` exits 0 from a clean `dab-agent:latest` base.
Build log shows no installer errors (warnings tolerated). Final
image size noted in the validation report (heads-up for the
cost-bearing run).

**AC-3 — A single ade-bench task runs end-to-end with the new
image and produces a non-degraded score.**
Verified by: live invocation `uv run rk run examples/specs/
airbnb001-haiku.yaml --image ade-bench-agent:latest` (or the
adapter's default once AC-4 lands) on a Haiku-budget task. The
run-dir's `events.jsonl` shows `setup.sh` exits 0 (no
tool-not-found errors); `summary.json` carries a real score
(non-zero, non-degraded, non-typed-error). The score itself
doesn't need to be high — it needs to be a real number that
reflects agent behavior.

**AC-4 — Razorback's ade-bench adapter defaults to
`ade-bench-agent:latest` when running ade-bench tasks, with the
existing `--image` override still functional for advanced use.**
Verified by: a unit test asserts the adapter's effective image
for an ade-bench spec without explicit `--image` is
`ade-bench-agent:latest`; a second test asserts an explicit
`--image foo:bar` override still wins. dab tasks still default
to `dab-agent:latest`.

**AC-5 — Carry-forward tests stay green.**
Verified by: `uv run pytest` from a clean checkout exits 0 with
all prior tests passing alongside new PKG-10 tests. The ade-bench
fixture tests from FU-1 + FU-2 continue to pass against the new
default image.

**AC-6 — Tool-survey methodology documented.**
Verified by: `images/ade-bench-agent/tool-survey.md` documents
how the tool list was derived (e.g., "grep `apt-get install`
across all 48 setup.sh files; union the package list; cite each
package's first-occurrence task"). Future ade-bench-agent rebuilds
can re-run the survey when ade-bench adds tasks.

## Test plan

- **Unit tests:** image-selection default for ade-bench vs dab
  specs; `--image` override precedence; carry-forward fixture
  tests stay green.
- **Build test:** `docker build` exits 0 (CI-runnable if a docker
  daemon is available; otherwise validator-runnable locally).
- **Integration test:** one airbnb001-haiku task end-to-end with
  the new image. Cost: ~$0.10-0.50 at Haiku rates for one task.
- **Tool-survey artifact**: a worker reads every ade-bench
  `setup.sh` and produces the union; committed alongside the
  Dockerfile.
- **Acceptance command:** `uv run rk run examples/specs/
  airbnb001-haiku.yaml` exits 0 with `summary.json` carrying a
  real (non-zero, non-degraded) score.

## Out of scope

- **The full 48-task ade-bench haiku baseline run.** That's a
  separate captain-gated experiment after PKG-10 merges. Cost:
  ~$20-40 at Haiku rates.
- Pinning tool versions for full determinism. PKG-8 handles
  plugin/skill version pinning more generally; the ade-bench-agent
  Dockerfile pins where ade-bench's own setup.sh files do, and
  otherwise tracks latest.
- Multi-stage Dockerfile optimization (slimmer final image). The
  first version is correctness-first; size-optimization later.
- Per-task images. The deliverable is one shared image with the
  union of tools, matching ade-bench's own design assumption.
- Mirroring the image to a registry. Locally-built is fine for the
  haiku baseline; registry-push is a separate ops decision.
- Image-override mechanism itself (FU-2 already shipped it).
