# swe-bench-pro on razorback — survey + mechanism-smoke design

Date: 2026-06-24
Status: design approved; entities filed to `docs/razorback-implementation/` backlog.

## Goal

Support the `swe-bench-pro` benchmark in razorback using harbor's
published `scale-ai/swe-bench-pro` dataset. First milestone is a
**mechanism smoke**: get one swe-bench-pro task running end-to-end and
scored, de-risking hydration, leakage, and solver fit before committing
to a full-dataset run. The full N=1 dataset score is a deferred
follow-up goal entity, filed once the smoke passes.

## Survey: what already exists vs what is missing

### Already supported (no code change)

- **Generic `kind: harbor` benchmark block.** `HarborBenchmarkBlock`
  (`src/razorback/spec/schema.py:169`) resolves any published harbor
  dataset through `PackageDatasetClient` with no per-benchmark code when
  `plugin:` is unset — the dabstep pass-through path, distinct from the
  spider2-dbt / ade-bench paths that need view materializers. Verified:
  `PackageReference.parse("scale-ai/swe-bench-pro@latest")` succeeds and
  harbor 0.6.6 is installed, so the spec schema accepts the dataset ref
  today.
- **Spec-side selectors.** `tasks` / `exclude_tasks` / `n_tasks` apply
  with the same semantics as harbor's `-i` / `-x` / `-l`. The schema
  docstring already names swe-bench-verified as the project-prefixed-slug
  example, so swe-bench-pro's slug shape is anticipated.
- **Scoring.** `rk score` computes pass@1 + Wilson intervals via the
  benchmark aggregator, reading harbor's per-task verdict — benchmark-
  agnostic as long as harbor emits a verdict per task.

### Missing or unknown (the real work)

1. **Harbor package hydration (top risk).** spider2-dbt hit a
   `git checkout exit-128` blocker (PKG-40) hydrating its harbor package.
   swe-bench-pro is git-repo-based (clone repo at a base commit), so the
   same hydration/checkout blocker is the #1 feasibility risk. Needs a
   live `harbor download scale-ai/swe-bench-pro` smoke.
2. **Leakage / audit (trust boundary).** SWE-bench tasks ship the **gold
   patch and the test patch** alongside the repo. The agent workspace
   must not expose them pre-solve. Needs swe-specific deny-globs + a
   negative leakage test, mirroring `SPIDER2_DBT_DENY_GLOBS`. If globs
   alone cannot strip the gold patch, swe-bench-pro escalates from the
   generic pass-through to a materialized-view family (like spider2/ade)
   — a captain-gated finding.
3. **Solver workflow fit.** Existing solvers are data-analysis-flavored
   ("produce the requested answer"). SWE needs a patch-producing loop
   (edit repo files → verifier runs FAIL_TO_PASS / PASS_TO_PASS). The
   generic `codex-benchmark-solver` is the chosen starting point; a
   swe-tuned prompt is a noted follow-up if the generic one underperforms.
4. **Resource budget.** Large repos + long test suites need bigger
   `max_turns`, `override_timeout_sec`, `max_timeout_sec`, and disk than
   the existing 1200s codex specs. Folded into the example-spec entity.
5. **Scoring strata / task identity.** Confirm the aggregator stratifies
   project-prefixed swe-bench-pro slugs sensibly (the recently-merged
   `harbor-view-task-identity-scored-runs` work is the relevant surface).
   Folded into the example-spec entity.

## Architecture decision

swe-bench-pro rides the **generic `kind: harbor` pass-through** (the
dabstep path: no plugin, no family branch, no view materializer) —
**unless** the leakage probe (E2) proves the workspace exposes gold
patches that deny-globs cannot strip, in which case it escalates to a
materialized-view family. The escalation is a captain decision surfaced
by E2, not a baked-in assumption.

Chosen runtime/solver: **`kind: codex` (gpt-5.5) + the existing
`codex-benchmark-solver`** — matches the current full-dataset direction
and adds the least new surface.

## Entity breakdown (filed to backlog)

Sequenced E1 → (E2 ∥ E3). All three carry `auto-approve: false` because
they touch the spec / translate / audit / score surfaces the workflow
gates.

### E1 — `swe-bench-pro-hydration-resolve-smoke` (riskiest contract first)

Prove `scale-ai/swe-bench-pro@<ref>` resolves through generic
`_build_harbor` to `TaskConfig` dirs. Deliverable: a minimal
swe-bench-pro-shaped harbor task fixture + an integration test that
`rk run --explain` lists the resolved tasks (regression guard that it
stays on the generic path, not a family branch). A **non-gating** live
`harbor download scale-ai/swe-bench-pro` smoke records exit code + task
count, re-checking the PKG-40-style checkout blocker.

### E2 — `swe-bench-pro-leakage-audit-deny-globs` (depends on E1)

Probe what a resolved swe-bench-pro workspace exposes (gold patch / test
patch / FAIL_TO_PASS contents). Add swe-specific deny-globs + a negative
leakage test (plant a gold-patch-shaped file, assert excluded), mirroring
the spider2 deny-glob work; may extend `rk audit` signatures. Surfaces
the view-materializer escalation as a captain decision if globs are
insufficient.

### E3 — `swe-bench-pro-example-spec-scoring-strata` (depends on E1, overlaps E2)

User-facing `examples/specs/swe-bench-pro-codex.yaml`: `kind: harbor`,
`scale-ai/swe-bench-pro@<ref>`, `kind: codex` / gpt-5.5, SWE-tuned
timeout/turn budget, hydration-prereq header note; freezes offline via
`rk freeze --allow-missing`. Confirms `rk score` stratifies the
project-prefixed swe-bench-pro slugs — a fixture-backed scoring test
producing `summary.json`.

## Deferred (not filed now)

`goal-swe-bench-pro-codex-full-dataset-1x-score` — a full-dataset pass@1
goal entity mirroring the DAB / ade-bench goal docs, filed once E1's
hydration smoke passes.
