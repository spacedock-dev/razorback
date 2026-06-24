# swe-bench-pro on razorback — survey + mechanism-smoke design

Date: 2026-06-24
Status: design approved (rev 2, post Codex adversarial review); entities filed
to `docs/razorback-implementation/` backlog.

## Goal

Support the `swe-bench-pro` benchmark in razorback using harbor's
published `scale-ai/swe-bench-pro` dataset. First milestone is a
**mechanism smoke**: get one swe-bench-pro task running end-to-end and
scored, de-risking hydration, leakage, and solver fit before committing
to a full-dataset run. The full N=1 dataset score is a deferred
follow-up goal entity, filed once the smoke passes.

## Revision note (rev 2)

A Codex adversarial review of rev 1 found a load-bearing inconsistency:
rev 1 put swe-bench-pro on the **generic `kind: harbor` pass-through**
(the dabstep path) yet still assumed leakage stripping, per-task strata,
and a benchmark env. Those capabilities exist **only on the task-view
materializer path** (`harbor_tasks/materialize.py`), not on generic
pass-through (`translate.py` hands source dirs straight to `TaskConfig`).
Rev 2 flips the architecture: swe-bench-pro uses the **task-view
materializer family** (the spider2/ade pattern) from the start. Rev 2
also fixes a schema-invalid spec shape and corrects every AC's
verification surface (see each entity).

## Survey: what already exists vs what is missing

### Already supported (no code change)

- **Spec schema accepts the dataset ref.** `HarborBenchmarkBlock`
  (`src/razorback/spec/schema.py:169`) accepts `kind: harbor` +
  `dataset: scale-ai/swe-bench-pro@<ref>`; `PackageReference.parse`
  validates the qualified `<org>/<name>@<ref>` form at parse time
  (verified live, harbor 0.6.6 installed).
- **The task-view materializer exists and is generic.**
  `materialize_harbor_task_view` (`src/razorback/harbor_tasks/materialize.py:26`)
  reflects a source Harbor task into a Razorback-owned view, applying
  path deny-globs (`harbor_tasks/leakage.py:DEFAULT_SOLUTION_DENY_GLOBS`),
  injecting `RAZORBACK_BENCHMARK_KIND` / `RAZORBACK_BENCHMARK_TASK_ID`
  via the task.toml env, and writing a `view_manifest.json`. spider2/ade
  wire it in via a per-benchmark branch in `_build_harbor`.
- **Scoring stratifies off the view manifest.** The aggregator
  (`src/razorback/runs/aggregate.py:_resolve_stratum_from_task_view_manifest`)
  reads each view's `view_manifest.json` to recover
  `(dataset=benchmark_kind, query_id=benchmark_task_id)` strata — so a
  view-materialized benchmark scores per-task without extra work. Scoring
  reads the per-trial **reward** (`rewards["reward"]`,
  `aggregate.py:259-266`), not a free-form "verdict".

### Missing or unknown (the real work)

1. **Harbor package hydration (top risk).** spider2-dbt hit a
   `git checkout exit-128` blocker (PKG-40) hydrating its harbor package.
   swe-bench-pro is git-repo-based (clone repo at a base commit), so the
   same hydration/checkout blocker is the #1 feasibility risk. Needs a
   live `harbor download` smoke (exact CLI shape confirmed against
   `harbor download --help` at filing time).
2. **No `_build_harbor` wiring for swe-bench-pro.** The generic
   pass-through gives no leakage stripping, no env, no strata. swe-bench-pro
   must be wired through `materialize_harbor_task_view` in `_build_harbor`
   (the spider2/ade family pattern) — this is E1's deliverable.
3. **Leakage deny-globs (trust boundary).** SWE-bench tasks ship the
   **gold patch and test patch**. `DEFAULT_SOLUTION_DENY_GLOBS` covers
   `solution*/answer*/tests/expected` but **not** `*.patch` / `test_patch`
   / `gold`. E2 extends the deny-glob set and proves exclusion is
   fail-closed via `assert_no_denied_paths` + a negative test.
4. **Solver workflow + resource budget.** Codex with a solver workflow is
   `kind: spacedock_solver` / `runtime: codex` (the dabstep smoke shape) —
   **not** `kind: codex`, which has no `solver_workflow` / `max_turns`
   fields (`schema.py:49-89`). Large repos + long test suites need bigger
   `max_turns` / `override_timeout_sec` / `max_timeout_sec` than the 1200s
   codex specs. Folded into the example-spec entity.
5. **Scoring strata confirmation.** Confirm the view-manifest-driven
   aggregator emits one query cell per swe-bench-pro task slug. Folded
   into the example-spec entity.

## Architecture decision

swe-bench-pro uses the **task-view materializer family** (the spider2/ade
pattern): `_build_harbor` detects the swe-bench-pro dataset and routes each
resolved source task through the **generic** `materialize_harbor_task_view`
(no benchmark-specific view logic needed, unlike spider2's dbt wrapper),
with swe-specific deny-globs. This one path supplies all three
capabilities the generic pass-through lacks — leakage stripping, the
`RAZORBACK_BENCHMARK_KIND`/`TASK_ID` env, and per-task strata via the view
manifest.

Chosen runtime/solver: **`kind: spacedock_solver` / `runtime: codex`
(gpt-5.5) + the existing `codex-benchmark-solver` workflow** — the valid
schema shape for codex-with-solver, mirroring the dabstep smoke spec.

## Entity breakdown (filed to backlog)

Sequenced E1 → (E2 ∥ E3). All three carry `auto-approve: false` because
they touch the translate / leakage / score surfaces the workflow gates.

### E1 — `swe-bench-pro-hydration-resolve-smoke` (riskiest contract first)

Wire swe-bench-pro into `_build_harbor` through the generic task-view
materializer (the spider2/ade family pattern). Deliverable: a minimal
swe-bench-pro-shaped harbor task fixture + an integration test that the
resolved spec emits view dirs carrying `task.toml` +
`RAZORBACK_BENCHMARK_KIND=swe-bench-pro` + `RAZORBACK_BENCHMARK_TASK_ID`,
and that `rk run --explain --explain-format json` lists one `task_paths`
entry per fixture instance. A **non-gating** live `harbor download` smoke
records exit code + task count, re-checking the PKG-40-style checkout
blocker.

### E2 — `swe-bench-pro-leakage-audit-deny-globs` (depends on E1)

Probe what a resolved swe-bench-pro task exposes (gold patch / test patch
/ FAIL_TO_PASS contents). Extend the deny-glob set
(`harbor_tasks/leakage.py`) with swe-specific globs and prove exclusion is
fail-closed: a negative leakage test plants gold/test-patch files, asserts
the materialized view excludes them, and FAILS when the new globs are
reverted (load-bearing), mirroring the spider2 deny-glob work. The defense
is the materializer's path-based exclusion (`assert_no_denied_paths`), not
`rk audit` — `rk audit`'s strict reducer only taints
`category == "forbidden_lookup"` (`audit/cli.py:79-92`) and has no SWE
signatures, so a trace-level audit AC would exit clean and is out of scope.

### E3 — `swe-bench-pro-example-spec-scoring-strata` (depends on E1, overlaps E2)

User-facing `examples/specs/swe-bench-pro-spacedock-codex.yaml`:
`kind: harbor`, `scale-ai/swe-bench-pro@<ref>`, `kind: spacedock_solver` /
`runtime: codex` / gpt-5.5 / `solver_workflow: codex-benchmark-solver`,
SWE-tuned `max_turns` + timeout budget, hydration-prereq header note;
freezes offline via `rk freeze --allow-missing`. Confirms the aggregator
stratifies swe-bench-pro task slugs — a fixture-backed test over a
synthetic run dir with `view_manifest.json` sidecars asserting the
`swe-bench-pro` stratum carries one query cell per task slug (the
`aggregate_summary` `summary.json` surface; `rk score` echoes a separate
`score_version`/`strata` JSON — kept distinct in the AC).

## Deferred (not filed now)

`goal-swe-bench-pro-codex-full-dataset-1x-score` — a full-dataset pass@1
goal entity mirroring the DAB / ade-bench goal docs, filed once E1's
hydration smoke passes.
