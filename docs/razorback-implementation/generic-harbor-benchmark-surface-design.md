---
id: hmh8cq1mjkzbhpt6vnga8a03
title: Design doc + spec amendment — generic harbor benchmark surface (collapse per-benchmark kinds)
status: plan
source: Captain directive 2026-05-23 — "let's say we have a consumer repo, targeting dabstep (another harbor-listed dataset), would this work today? or does it need more wiring in razorback?" → captain pushed back on the "needs new BenchmarkBlock class" answer with "no this is too complicated. i'd assume if dabstep is already on harbor, there should be just simple config, no additional classes/plugin needed." Captain then provided concrete URL `https://hub.harborframework.com/datasets/adyen/dabstep/latest` and asked for a design doc + grounded research + spec amendment if material.
started: 2026-05-23T22:25:35Z
completed:
verdict:
score: 0.92
worktree:
issue:
pr:
mod-block:
---

## Problem

Razorback's `spec.benchmark` discriminator is per-benchmark today:
`HarborDabBenchmarkBlock` / `AdeBenchBenchmarkBlock` /
`Spider2DbtBenchmarkBlock` / `LocalBenchmarkBlock` /
legacy `DabBenchmarkBlock` (`src/razorback/spec/schema.py:101-310`).
`translate.py` has matching per-benchmark builders
(`_build_harbor_dab` / `_build_ade_bench` / `_build_spider2_dbt` at
lines 312-453). Every new harbor-published benchmark requires:

1. A new `BenchmarkBlock` Pydantic class with `kind: Literal["..."]`
2. A new `_build_<benchmark>` method in `translate.py` that emits a
   benchmark-specific Harbor job-config YAML
3. (Often) a sibling `razorback-plugin-<benchmark>` pip package

This contradicts spec §1.3 explicitly:

> Razorback is not a benchmark library. Benchmarks live in harbor's
> catalog as adapters publishable via `harbor publish`. **Razorback
> ships no benchmark adapters.**

The captain's framing — "if dabstep is on harbor, there should be
just simple config" — IS the spec's actual intent. The implementation
has accumulated per-benchmark special-casing that the spec disclaims.

## Grounded research (already performed by FO)

### Harbor already exposes a generic published-dataset entrypoint

`harbor run -d <org>/<name>@<version>` (from
`.venv/lib/python3.12/site-packages/harbor/cli/jobs.py:825-844`)
resolves any Harbor-published dataset via `PackageDatasetClient`
(`.../registry/client/package.py`) → returns `DatasetMetadata` with
`task_ids` + `files`. Harbor's CLI ALREADY accepts:

- `-d / --dataset <org/name@version>` — published dataset reference
  (the dabstep case)
- `-p / --path <path>` — local task/dataset directory
- `--task-git-url` + `--task-git-commit` — git-based task
- `-t / --task <org/name[@ref]>` — single task from registry
- `-i / --include-task-name <glob>` — task subset selector
- `-x / --exclude-task-name <glob>` — task exclusion selector
- `-n / --n-tasks <int>` — task-count cap

So the entire benchmark-selector surface razorback needs to expose IS
already in harbor's CLI. Razorback's job is to emit a YAML or pass
the relevant flags.

### Dataset.toml schema is canonical at the harbor layer

Harbor's `DatasetManifest` model
(`.../harbor/models/dataset/manifest.py:152-218`) defines the
canonical TOML schema:

```toml
schema_version = "1.0"

[dataset]
name = "org/name"           # required, org/name format
description = "..."
authors = [{name = "...", email = "..."}]
keywords = ["..."]

[[tasks]]
name = "org/task-name"      # required, org/name format
digest = "sha256:<64hex>"   # required, pins exact task version

[[files]]                   # optional dataset-level files (e.g., metric.py)
path = "metric.py"
digest = "sha256:<64hex>"   # auto-computed at publish time if omitted
```

Content hash = SHA-256 over sorted task digests (+ optional file
path:digest pairs). `harbor publish` produces this manifest from a
local source; `PackageDatasetClient` resolves a `<org>/<name>@<ref>`
back into the materialized task tree.

### dabstep — confirmed published

`https://hub.harborframework.com/datasets/adyen/dabstep/latest` shows:
- Owner: `adyen`
- Name: `dabstep`
- 450 tasks across 5+ pages of task IDs (`adyen/6` through `adyen/2770`)
- Command surfaced verbatim: `harbor run -d adyen/dabstep`
- Hub does NOT expose the dataset.toml/README server-side; the manifest
  lives inside the published package itself, retrievable via `harbor
  download` or `PackageDatasetClient`.

### Comparison benchmark — `swe-bench/swe-bench-verified`

Also confirmed at `https://hub.harborframework.com/datasets/swe-bench/swe-bench-verified`:
- Owner: `swe-bench`
- Name: `swe-bench-verified`
- 500 manually validated tasks (subset of the 2294-issue
  SWE-bench corpus)
- Harbor maintains a "parity table" comparing the official SWE-bench
  baseline vs. Harbor's adapter: `mini-swe-agent` + GPT-5-mini scored
  `official 0.563 +/- 0.000 vs. Harbor 0.545 +/- 0.007` across 499
  comparable tasks. So harbor's adapter is already calibrated and
  in-use; the dataset is mature.
- Source: 2024 ICLR paper (Jimenez et al., OpenReview).

Other harbor-hub datasets visible: `terminal-bench/terminal-bench-2`
(89), `lawbench/lawbench` (1000), `replicationbench/replicationbench`
(90), `stanford/medagentbench` (300), `scale-ai/swe-bench-pro` (731).
Each follows the same `<org>/<name>` pattern. None of them are wired
into razorback today.

### Razorback's current handoff to harbor

`src/razorback/cli/run.py:55-65` `_invoke_harbor()`:

```python
proc = subprocess.run(
    ["uv", "run", "harbor", "run", "-c", str(job_config_yaml)],
    env=env, capture_output=False,
)
```

Razorback emits a job-config YAML (per-benchmark via translate.py)
and passes it through `-c`. The benchmark-specific knowledge is
ENCODED in the YAML razorback constructs. If razorback emitted a
generic YAML that passed dataset+task selectors through, the
per-benchmark builders become unnecessary.

## Acceptance criteria

**AC-1 — Design doc shipped.**
A design doc lives at `docs/superpowers/specs/2026-05-23-generic-harbor-benchmark-surface.md`
(or a captain-renamed slug) covering:
- the current per-benchmark pattern + costs (per-new-benchmark wiring
  burden, divergence from spec §1.3)
- harbor's generic surface (DatasetManifest TOML + `harbor run -d`
  CLI + PackageDatasetClient) with verbatim schema snippets
- the proposed `HarborBenchmarkBlock(kind: harbor, dataset: <ref>,
  ...)` collapse and the migration shape for `HarborDabBenchmarkBlock`
  + `AdeBenchBenchmarkBlock` + `Spider2DbtBenchmarkBlock`
- a per-cell-spec example for **dabstep** and **swe-bench-verified**
  showing the YAML before/after
- the backwards-compat story (kept-as-aliases? deprecation window?
  hard cutover?) and what breaks
- the legitimate razorback-side prep that DOESN'T collapse (e.g.,
  DAB's `workspace_variant: spacedock|direct-minimal|direct-structured`
  — that's a solver-side detail, not benchmark-specific) and how it
  threads through the generic block
- explicit recommendation: "do this refactor" / "don't do it because
  X" / "do a partial — collapse harbor_dab+spider2+ade but keep local"
Verified by: `test -f docs/superpowers/specs/2026-05-23-generic-harbor-benchmark-surface.md`;
doc cites the harbor source files + spec sections + URLs above
verbatim.

**AC-2 — Grounded research recorded.**
The design doc cites real evidence: the harbor CLI flag block
(`jobs.py:800-895`), the DatasetManifest model
(`models/dataset/manifest.py:152-218`), the PackageDatasetClient
(`registry/client/package.py`), the dabstep hub URL with task count
(450), the swe-bench-verified hub URL with task count (500), the
SWE-bench parity table. No invented file paths or fabricated schema
snippets.
Verified by: every code-path citation in the doc resolves to a real
line in `.venv/lib/python3.12/site-packages/harbor/...` at the
current pinned harbor==0.6.6; every URL is fetchable.

**AC-3 — Spec amendment evaluated.**
The doc explicitly answers: "does the v2 spec at
`docs/superpowers/specs/2026-05-19-razorback-on-harbor.md` need an
update?" If yes, the doc proposes the diff (which §6.1 / §6.2 / §2
sections change, what the new spec text reads). If the answer is "no
spec change — the spec is already correct and the implementation
just needs to follow it," the doc cites the spec sections that
already prescribe the generic surface.
Verified by: doc has a `## Spec amendment` section that either
includes a diff or explicitly explains "no change required, the spec
already says this at §X."

**AC-4 — Decision-ready output for captain.**
The doc ends with a `## Recommendation` section that the captain can
respond to as YES/NO/MODIFY without re-reading the body. The
recommendation is concrete: file follow-on entity X to refactor
(estimated effort), or kill the refactor (with reason), or partial
(with scope).
Verified by: section exists and is one decision point.

## Test plan

- **Mechanism check first:** confirm via `uv run python -c "from
  harbor.cli.jobs import start; import inspect;
  print(inspect.signature(start))"` (or equivalent) that
  `--dataset` flag actually accepts `<org>/<name>@<version>` against
  the live PackageDatasetClient. Cite the exit code + output in the
  doc.
- **Dabstep dry-test:** run `uv run harbor download -d adyen/dabstep`
  (or `harbor datasets download adyen/dabstep@latest`) and observe
  whether the dataset.toml + task files materialize successfully
  without any razorback involvement. Cite output (success or specific
  error) in the doc. (~Network only; no API spend.)
- **Spec amendment review:** if the doc proposes a v2 spec change,
  validate the diff renders cleanly (`git apply --check`) and is
  internally consistent (no §-ref broken).
- **No pytest required** — this is a doc/design entity. Existing
  pytest must remain green (no code changes).

## Out of scope

- **Actually implementing the refactor.** This entity ships the
  design doc + spec amendment proposal only. The implementation
  entity is sibling work the captain greenlights based on this doc's
  recommendation.
- **Building a `razorback-plugin-dabstep` package.** If the design
  recommends "no plugin needed, just config," this is a no-op. If it
  recommends "minimal plugin for dabstep-specific verifier hooks,"
  that's a sibling entity.
- **Refactoring `LocalBenchmarkBlock`.** Local-path benchmarks have
  a genuinely different invocation shape (no Harbor registry). They
  may legitimately stay separate.
- **Codex/Pi runtime adapters.** Same as `ne`'s scope discipline.

## Depends on

- (none — pure research + doc)
- Aware-of: `qh dab-harbor-dataset-definition` (DONE; established
  the `dataset: dab@1.0` precedent), `gb ade-bench-harbor-dataset-ref`
  (DONE; established `dataset: <org>/<name>@<ref>` for ADE). Both
  partially toward the generic surface; the captain's pushback +
  this design doc would finish the journey.

## Resume hook

When this lands, the captain has a decision-ready doc that says
either "yes, file the refactor entity, scoped as X" or "no, here's
why the current pattern is correct." If the refactor proceeds, every
future harbor-published benchmark (dabstep, swe-bench-verified,
terminal-bench-2, lawbench, replicationbench, medagentbench,
swe-bench-pro, anything published next year) becomes a one-spec
addition with zero razorback code change. That's a meaningful
multiplier on razorback's surface coverage.
