---
id: 46k3jhr4xy3qz83x6406jv2g
title: M5 — Provenance freeze + full DAB scoring (first DAB result)
status: implementation
source: design §8
started: 2026-05-19T08:23:23Z
completed:
verdict:
score: 0.95
worktree: .worktrees/spacedock-ensign-m5-provenance-full-dab
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

## Plan

Implementation plan: [`plans/m5-provenance-full-dab.md`](plans/m5-provenance-full-dab.md).
Tasks 1-3 land the riskiest contracts (alias drift, missing-provenance refusal, harbor drift) before any resolver code. Tasks 4-10 add the resolver stack, freeze CLI, drift wiring, and 12-dataset aggregator generalization. Tasks 11-13 are the AC-6 acceptance run — cost-bounded, one trial per query across all 12 DAB datasets.

## Stage Report: plan

- DONE: Plan steps map 1:1 to the 7 ACs in the M5 entity body, each with the §-cite that governs it (§6.4 provenance freeze + AliasDriftError + harbor version drift, §6.5 12-dataset stratified macro-average, §3.2 exit codes 11/21). AC↔task map at the top of the plan.
  See "AC ↔ Task Map" table in `plans/m5-provenance-full-dab.md` (7 rows, each cites §6.4 / §6.5 / §3.2 and names the implementing Task).
- DONE: The riskiest contract for M5 — that the model-alias-drift check (AC-3) actually fires when the provider returns a different version than the frozen `model_resolved_version` — is plan Task 1 as a unit test with a mocked provider, BEFORE any provider-API resolver code lands. Same for harbor version drift (AC-4) and missing-provenance refusal (AC-1). Math-heavy aggregator extension (AC-5: 12-dataset stratified average) comes AFTER the freeze/refusal machinery.
  Task 1 (AC-3 alias-drift unit test against mocked Anthropic SDK) → Task 2 (AC-1 refusal unit tests) → Task 3 (AC-4 harbor-drift unit test) → Tasks 4-7 (resolvers, retry, freeze CLI, run wiring) → Tasks 8-10 (aggregator + translator widening for AC-5). AC-6 integration test is Task 12.
- DONE: The plan extends M2's aggregator surface from docs/razorback-implementation/plans/m2-dab-bookreview.md to the full 12 DAB datasets, citing M2's `aggregate.py` module path. The plan does NOT re-derive the bookreview math — it generalizes M2's pass@1 + per-dataset mean code to a cross-dataset macro-average. Cite which lines of M2's plan are extended.
  "M2 reuse" subsection cites `_build_summary` at M2 plan lines 317-337 and `pass_at_k` at lines 287-297. Task 8 adds the 12-dataset fixture; Task 9 verifies translator iteration over `spec.benchmark.datasets`. No math changes to `src/razorback/benchmarks/dab/aggregate.py`.

### Summary

Plan written at `docs/razorback-implementation/plans/m5-provenance-full-dab.md` (14 tasks). Risk-first ordering: AC-3 alias drift, AC-1 missing-provenance refusal, and AC-4 harbor drift land as mocked unit tests in Tasks 1-3 before any resolver/CLI code. Resolver stack (Anthropic SDK `client.models.retrieve()` + docker/git/hash/harbor/prompt), `rk spec freeze` Typer command, and `rk run` drift wiring follow in Tasks 4-7. AC-5 is verified via a 12-dataset synthetic fixture + golden (hand-computed stratified pass@1 = 6.5/12 = 0.5417) against M2's untouched aggregator. AC-6 integration test (Task 12) drives all 12 DAB datasets through Claude end-to-end, gated by `RAZORBACK_RUN_FULL_DAB_TEST=1` to keep CI cheap; the headline "first DAB result" lands when the implementer runs it. Provider-API resolver concretized as `anthropic.Anthropic().models.retrieve(alias)` returning `model.id` + `model.created_at` — no divergence from §6.4's design shape; Codex/OpenAI deferred to M6/M7 per design doc.
