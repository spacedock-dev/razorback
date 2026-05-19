---
id: 46k3jhr4xy3qz83x6406jv2g
title: M5 — Provenance freeze + full DAB scoring (first DAB result)
status: backlog
source: design §8
started:
completed:
verdict:
score: 0.95
worktree:
issue:
pr:
mod-block:
---

## Problem

The "first DAB result" milestone CL named explicitly in the
implementation brief. Two layers come together: `rk spec freeze`
resolves every dynamic input (model version, image digest, git
SHA, agent CLI hash, harbor version, prompt content hashes) and
refuses on any unresolved field unless `--allow-missing`; and the
DAB aggregator runs the §6.5 stratified pass@1 across the 12 DAB
datasets, producing a real cross-dataset score from a full dev
tier run. See §6.4, §6.5, §8.M5.

`rk run` re-resolves the model version at run start and refuses
with `AliasDriftError` (exit code 21) when the provider's
resolved version disagrees with the frozen spec, per §6.4.

## Acceptance criteria

**AC-1 — `rk spec freeze` resolves all six provenance fields
listed in §6.4 and refuses on any unresolved field absent
`--allow-missing`.**
Verified by: unit tests feed a spec missing each provenance
field in turn and assert the freeze command exits with
`ProvenanceError` (exit code 11) and writes neither the frozen
spec nor `provenance.yaml`.

**AC-2 — `--allow-missing` flag writes the frozen spec but
records the unresolved fields in `provenance.yaml`.**
Verified by: a unit test runs freeze with `--allow-missing`
against a spec whose model API is mocked to return 503; the
frozen spec lands and `provenance.yaml` contains the unresolved
field marker.

**AC-3 — `AliasDriftError` (exit code 21) fires when the
provider returns a model version different from the frozen
spec's pinned `model_resolved_version`.**
Verified by: a unit test mocks the provider API to return a
different version than the frozen value; `rk run` exits 21 and
the resulting `provenance.yaml` (when `--allow-alias-drift` is
passed) records both versions.

**AC-4 — Major-version drift in installed harbor between freeze
and run is a hard error.**
Verified by: a unit test patches `harbor.__version__` to a
different major than the frozen value; `rk run` refuses with a
typed error before reaching `Job.create`.

**AC-5 — The DAB aggregator produces a stratified macro-average
across the 12 datasets per §6.5.**
Verified by: a unit test feeds a fixture covering all 12 DAB
datasets to the aggregator and asserts the resulting
`summary.json` has a stratified pass@1 line whose value matches
the cross-dataset macro-average computed by hand on the fixture.

**AC-6 — End-to-end full DAB dev-tier run with a real agent
(Claude or Codex) writes a complete `summary.json` with per-
dataset and stratified scores.**
Verified by: `uv run rk run examples/specs/dab-dev-claude.yaml`
exits 0 against the full DAB dev tier and the run-dir's
`summary.json` contains: a per-query block for each of the 12
datasets, a per-dataset mean for each, and a single stratified
macro-average line. Cost-bounded; one trial per query
(`trials: 1`).

**AC-7 — Provenance retries with exponential backoff on
transient 503s.**
Verified by: a unit test mocks the provider API to return 503
twice then 200; the freeze succeeds and the resolved version
lands in `provenance.yaml`.

## Test plan

- **Unit tests:** each provenance resolver field (model, image,
  CLI, git SHA, harbor version, prompt hash); `--allow-missing`
  behavior; alias drift detection; harbor version drift;
  aggregator against the 12-dataset fixture; retry/backoff on
  transient errors.
- **Integration test:** full DAB dev tier through Claude via
  harbor's docker environment. This is the cost-bearing test;
  estimate one dev-tier run is the budget.
- **Acceptance command:** `uv run rk spec freeze examples/specs/
  dab-dev-claude.yaml` followed by `uv run rk run examples/specs/
  dab-dev-claude.frozen.yaml` — the freeze command produces a
  fully-pinned frozen spec and provenance.yaml; the run produces
  a stratified score across the 12 DAB datasets.

## Out of scope

- `runs diff`, paired statistics — §M6.
- Constraints check, baseline promote/verify, registry — §M6.
- ade-bench or any other harbor-shipped benchmark — §M7.
- Per-stage cost attribution for non-staged agents (claude /
  codex emit one phase, not three) — already handled by §6.8's
  schema; no additional work here.
