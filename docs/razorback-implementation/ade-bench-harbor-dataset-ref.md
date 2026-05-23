---
id: gbejh94n05b1096a6fhqeq0h
title: ADE-Bench uses Harbor published dataset references
status: validation
source: 2026-05-23 captain directive — consume canonical Harbor dataset refs instead of local ADE task roots
started: 2026-05-23T04:58:35Z
completed:
verdict:
score: 0.85
worktree: .worktrees/spacedock-ensign-ade-bench-harbor-dataset-ref
issue:
pr:
mod-block: 
---

## Problem

Razorback's current ADE path consumes local Harbor-shaped task directories
(`tasks_root + tasks`) or explicit git-task entries. That is Harbor-compatible,
but it is not Harbor registry-native: users still need to know where the ADE
tasks live and how they were materialized. Harbor already exposes canonical
published datasets such as `ade-bench@1.0`; Razorback should consume that
dataset reference and let Harbor resolve/materialize the task package set.

The local Harbor-shaped task-root path may stay as a development/debug escape
hatch, but the public score path for ADE should be a dataset ref.

## Acceptance criteria

**AC-1 — ADE specs accept a Harbor dataset reference.**
`benchmark.kind: ade-bench` can name a published Harbor dataset ref such as
`ade-bench@1.0` without requiring `tasks_root`. Specs can still select a subset
of task ids for smoke runs.
Verified by: schema/parser tests cover dataset-ref-only, dataset-ref + subset,
and old local-task-root compatibility.

**AC-2 — Dataset resolution uses Harbor's public resolver.**
Razorback resolves the dataset through Harbor's dataset/task client, materializes
tasks into a cache or run-owned staging area, and records the resolved dataset
version/content hash when Harbor exposes it.
Verified by: unit tests patch Harbor's resolver/client and assert package task
ids become local task directories without invoking the old ADE-specific root
loader.

**AC-3 — ADE task views still provide Razorback controls.**
Resolved Harbor tasks pass through the generic task-view materializer so
Razorback can still apply solution-file exclusion, image overrides, runtime
tooling layers, scoring metadata, and future batching/freeze wrappers.
Verified by: translator tests assert resolved dataset tasks produce task views
with `RAZORBACK_BENCHMARK_KIND=ade-bench` and per-task ids.

**AC-4 — Examples stop teaching local ADE roots as the canonical path.**
The primary ADE Codex/Claude smoke specs and generator use the published
dataset ref by default. Local fixture/root examples are marked as test fixtures
or dev-only.
Verified by: `rg "tasks_root: .*ade" examples/specs examples/drivers` returns
only fixture/dev examples, and a new smoke spec names `ade-bench@1.0`.

**AC-5 — No submodule requirement.**
The implementation does not require adding ade-bench or harbor-datasets as a
git submodule. Network/materialization failures surface as clear setup errors.
Verified by: validation report includes a clean checkout run without any new
git submodules and an error-path test for resolver failure.

## Notes

This should layer under the existing task-view abstraction rather than replacing
it. The new boundary is source selection: registry dataset ref -> Harbor
materialized tasks -> Razorback task views -> Harbor run.

## Stage Report: plan

- DONE: Separate plan doc at docs/razorback-implementation/plans/ade-bench-harbor-dataset-ref.md per the README's 4+-AC rule. AC↔task map for AC-1..AC-5.
  Written at docs/razorback-implementation/plans/ade-bench-harbor-dataset-ref.md with the AC-to-task table covering AC-1..AC-5; eight tasks (T0 probe through T8 acceptance sweep).
- DONE: Probe Harbor's published-dataset resolver surface — name the exact import path razorback should call, the package format Harbor exposes for `ade-bench@1.0`, and how the result is materialized into local task directories that the existing task-view materializer (pkg40) consumes. If Harbor's surface is unclear, plan a Phase-0 probe task before writing code.
  Surface named: `harbor.tasks.client.TaskClient.download_tasks(task_ids=[PackageTaskId(org="harbor", name="ade-bench", ref="1.0")], output_dir=..., export=True)` returning `BatchDownloadResult.results[*].path` + `content_hash` (harbor/tasks/client.py:457, harbor/models/task/id.py:35). T0 is a 6-step bounded probe that validates the export layout BEFORE schema/translator code lands — `TaskConfig(name=..., ref=...)` natively was rejected because it bypasses the PKG-40 materializer.
- DONE: AC-3 task-view interaction: Specify how resolved Harbor tasks flow into the task-view materializer at packages/.../harbor_view.py without bypassing the solution-file exclusion + image override + runtime tooling layers. Cite the integration point.
  Integration point cited at src/razorback/benchmarks/ade_bench/harbor_view.py:22 (`materialize_ade_harbor_task_view`) and src/razorback/translate.py:311 (translator call site). T3 has an explicit guardrail test (`test_translator_preserves_docker_image_override_through_dataset_path`) asserting the dataset-ref path passes `docker_image` into the same materializer; T4 step 4 extends only the kwargs surface, not the call shape — so ADE_BENCH_DENY_GLOBS, dbt-deps Dockerfile layer, and RAZORBACK_BENCHMARK_* env injection apply unchanged.

### Summary

Wrote a separate plan doc with eight tasks. Riskiest-first: T0 probes Harbor's `TaskClient.download_tasks([PackageTaskId])` export layout in 6 bounded steps before any schema/translator code lands. The dataset-ref path is wired as a sibling source-resolver under the existing PKG-40 materializer (not a replacement); `dataset_ref` + `dataset_content_hash` ride into `view_manifest.json` (schema_version bump to 2) and freeze `provenance.yaml` to satisfy AC-2's pinning requirement. AC-5's no-submodule clause is enforced as an in-test `git submodule status` assertion in T7, not just a docs claim.

## Stage Report: implementation

- DONE: Execute the plan at docs/razorback-implementation/plans/ade-bench-harbor-dataset-ref.md TDD-first, riskiest-first. T0 (Harbor TaskClient.download_tasks probe, 6 bounded steps) lands BEFORE T1+ code. If T0 surfaces that Harbor's export layout differs from the plan's assumption, stop and ask before writing schema/translator code.
  T0 ran first and surfaced 4 contract deviations from the plan (org name `dbt-labs/ade-bench` not `harbor/ade-bench`; only `@latest` tag exists, not `@1.0`; API entry is `PackageDatasetClient.download_dataset` not `TaskClient.download_tasks` directly; task package names carry the `ade-bench-` prefix). Escalated to captain via SendMessage; captain approved resolutions A-D + E1; T1+ executed against the adjusted contracts. Probe note at docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md (commits 9008eac, 440b2cf).
- DONE: All 5 ACs proven from this stage: AC-1 schema tests; AC-2 patch-Harbor-resolver unit test + content_hash in view_manifest.json + provenance.yaml; AC-3 task-view guardrail test (dataset-ref path passes docker_image to same materializer); AC-4 examples + smoke spec; AC-5 in-test `git submodule status` assertion.
  AC-1: 8 schema tests at tests/unit/test_ade_bench_dataset_ref_schema.py (bare-name rejection cites canonical example + rule per captain guardrail). AC-2: 9 resolver + translator manifest tests + freeze smoke pin both `dataset_content_hash` and per-task `task_content_hash` in `view_manifest.json` schema_v2. AC-3: `test_translator_preserves_docker_image_override_through_dataset_path` asserts dataset-ref path passes `docker_image` through `materialize_ade_harbor_task_view` (call shape unchanged from PKG-40). AC-4: `examples/specs/ade-bench-harbor-dataset-codex.yaml` ships `dataset: dbt-labs/ade-bench@latest`; `rg "tasks_root: .*ade" examples/specs examples/drivers` returns only 3 fixture/dev paths (all under `./tests/fixtures/`); generator gains `--ade-dataset-ref` flag with 5 new tests. AC-5: `tests/integration/test_ade_bench_dataset_ref_freeze_smoke.py::test_no_new_submodule_required_by_dataset_ref_path` asserts `git submodule status` carries no forbidden marker.
- DONE: Stage report enumerates test counts + uv run pytest excerpts. Any plan deviation called out with the AC cite (especially if T0 surfaces an unexpected Harbor surface).
  See below. 93/93 focused tests pass; 553/553 unit tests pass (one pre-existing unrelated collection failure in test_task_identity_scoring.py confirmed against baseline, unchanged by this work).

### Summary

Layered a dataset-ref source-resolver under the existing PKG-40 materializer
(no replacement). The riskiest contract (Harbor's published-dataset export
layout) was probed live in T0 BEFORE any schema/translator code landed, and
that probe surfaced 4 plan deviations (org `dbt-labs` not `harbor`; ref `@latest`
not `@1.0`; entry `PackageDatasetClient.download_dataset` not `TaskClient.download_tasks`;
task slugs prefixed `ade-bench-`). The captain confirmed the adjusted contracts
and the implementation shipped against them. `view_manifest.json` schema bumped
to v2 with `dataset_ref`, `dataset_content_hash` (dataset-level sha256), and
`task_content_hash` (per-task sha256 from `PackageTaskId.ref`) — both hashes
are the load-bearing reproducibility pin; the human-readable `@latest` is
documentation. Plan deviations called out per AC: AC-1 (canonical example
shifted from `ade-bench@1.0` to `dbt-labs/ade-bench@latest`); AC-2 (manifest
gained a third `task_content_hash` field beyond the plan's two); AC-4 (generator
adds `--ade-dataset-ref` as a sibling to `--ade-bench-root` rather than
replacing it, since existing tests + dev workflows still use the local-root
path as the fixture/dev escape hatch — `--ade-bench-root` is now documented
as dev/fixture only and is mutually exclusive with `--ade-dataset-ref`).

### Modules added / harbor surfaces touched

- New: `src/razorback/benchmarks/ade_bench/dataset_ref.py` (`parse_dataset_ref`,
  `resolve_dataset_tasks`, `ResolvedDatasetTask`).
- Modified: `src/razorback/spec/schema.py` (added `AdeBenchBenchmarkBlock.dataset`
  field + `_validate_source_selection` model validator; `tasks_root` + `tasks`
  became optional; bare-name rejection cites the canonical example).
- Modified: `src/razorback/translate.py` (`_build_ade_bench` grew a sibling
  dataset-ref branch under the existing PKG-40 materializer; image-override,
  leakage deny-globs, and `RAZORBACK_BENCHMARK_*` env-var injection all apply
  unchanged).
- Modified: `src/razorback/benchmarks/ade_bench/harbor_view.py` and
  `src/razorback/harbor_tasks/materialize.py` (accept and forward
  `dataset_ref`, `dataset_content_hash`, `task_content_hash` kwargs).
- Modified: `src/razorback/harbor_tasks/manifest.py` (schema v2;
  `TaskViewManifest` carries the three new optional fields).
- Harbor surfaces consumed: `harbor.registry.client.PackageDatasetClient`
  (`get_dataset_metadata`, `download_dataset`),
  `harbor.registry.client.base.DatasetMetadata` + `DownloadedDatasetItem`,
  `harbor.models.task.id.PackageTaskId`.

### Test counts and excerpts

`uv run --frozen pytest tests/unit/test_ade_bench_dataset_ref_schema.py tests/unit/test_ade_bench_dataset_ref_resolver.py tests/unit/test_ade_bench_dataset_ref_translator.py tests/unit/test_ade_bench_harbor_view.py tests/unit/test_harbor_task_view_materializer.py tests/unit/test_translate_harbor_task_batches.py tests/unit/test_ade_bench_translator.py tests/unit/test_ade_bench_translator_docker_image_override.py tests/unit/test_ade_bench_translator_git_task.py tests/unit/test_ade_bench_translator_local_root.py tests/unit/test_ade_bench_translator_test_sh_gating.py tests/unit/test_ade_bench_schema.py tests/unit/test_ade_bench_schema_docker_image_override.py tests/unit/test_ade_bench_schema_git_tasks.py tests/unit/test_codex_benchmark_spec_generator.py tests/unit/test_claude_benchmark_spec_generator.py tests/integration/test_ade_bench_dataset_ref_freeze_smoke.py`
→ `93 passed in 1.53s`

`uv run --frozen pytest tests/unit/ -q --ignore=tests/unit/test_task_identity_scoring.py`
→ `553 passed, 16 warnings in 9.37s` (pre-existing unrelated collection
failure in `test_task_identity_scoring.py::razorback.score.load` deselected;
confirmed unchanged against baseline before any gb work).

`rg "tasks_root: .*ade" examples/specs examples/drivers` → 3 matches, all
under `./tests/fixtures/ade_bench/tasks` (fixture/dev only per AC-4); the
three legacy specs now carry `FIXTURE/DEV` ABOUTME headers naming the
canonical replacement.

`git submodule status` → empty (AC-5 baseline preserved; in-test assertion
codifies the invariant for CI).

### Plan deviations called out

- AC-1: canonical dataset-ref example shifted from the plan's `ade-bench@1.0`
  to `dbt-labs/ade-bench@latest`. The plan's bare `ade-bench@1.0` form is
  explicitly rejected by the new validator with an error naming both the
  required shape (`<org>/<name>@<ref>`) and the canonical example (captain's
  AC-1 guardrail). T0 probe note records the registry evidence (only
  `dbt-labs/ade-bench@latest`, rev=1, exists in Harbor 0.6.6's registry).
- AC-2: manifest schema v2 carries THREE hashes, not two — `dataset_ref`,
  `dataset_content_hash` (dataset-level), and `task_content_hash` (per-task,
  from `PackageTaskId.ref`). Captain decision D pinned both layers so a frozen
  spec reproduces the exact task body, not just the dataset version that
  contained it.
- AC-4: the generator gains `--ade-dataset-ref` as a sibling to
  `--ade-bench-root` rather than replacing it (the plan said "Keep an opt-in
  `--legacy-tasks-root` switch" — same intent, different flag name to match
  the existing CLI surface; the existing 7 generator tests using
  `--ade-bench-root` continue to pass).

## Stage Report: validation

- DONE: Re-run the focused 93-test bundle from the impl report independently. Report exit code + N/N. Then full unit suite: `uv run --frozen pytest tests/unit/ -q --ignore=tests/unit/test_task_identity_scoring.py` and report (impl claimed 553/553 passing).
  Focused bundle: 93/93 passed in 1.47s, exit 0. Full unit suite (clean HEAD after stashing in-progress gb-T9 work): 559 passed in 8.46s, exit 0 (+6 vs impl's 553 due to uncommitted gb-T9 test additions reset for the clean run). Pre-existing `test_task_identity_scoring` collection failure confirmed unchanged.
- DONE: Verify AC-1..AC-5 directly. AC-1: schema rejects bare names with an error citing the canonical example AND the rule; schema accepts all three Harbor ref forms (tag/revision/digest) per a `PackageReference.parse` round-trip. AC-2: view_manifest.json v2 carries `dataset_ref`, `dataset_content_hash`, `task_content_hash` — open a manifest from a real test run and confirm. AC-3: dataset-ref path passes `docker_image` through `materialize_ade_harbor_task_view` (cite the guardrail test). AC-4: `rg "tasks_root: .*ade" examples/specs examples/drivers` returns only fixture/dev paths. AC-5: in-test `git submodule status` assertion exists.
  AC-1 PARTIAL FAIL — bare-name rejection passes (error cites both rule + canonical example) but the schema regex `[A-Za-z0-9_.+-]*` at `src/razorback/spec/schema.py:178-180` and `dataset_ref.py:18` rejects the digest form `@sha256:...` because `:` is not in the class; AC-1 explicitly requires tri-acceptance via `PackageReference.parse` round-trip. AC-2 PASS — manifest v2 carries all three fields (`harbor_tasks/manifest.py:45,59-61`); resolver + freeze-smoke tests confirm both hashes ride into the manifest and `provenance.yaml`. AC-3 PASS — guardrail test `test_translator_preserves_docker_image_override_through_dataset_path` asserts the dataset-ref path passes `docker_image=spec.benchmark.docker_image_override` into `materialize_ade_harbor_task_view` (`translate.py:312-323`). AC-4 PASS — `rg` returns 3 hits all under `./tests/fixtures/ade_bench/tasks`; canonical example file exists at `examples/specs/ade-bench-harbor-dataset-codex.yaml`. AC-5 PASS — `tests/integration/test_ade_bench_dataset_ref_freeze_smoke.py::test_no_new_submodule_required_by_dataset_ref_path` runs `git submodule status` and asserts no forbidden marker.
- DONE: **REQUIRED CHECK** — the canonical example file at `examples/specs/ade-bench-harbor-dataset-codex.yaml` currently ships `dataset: dbt-labs/ade-bench@latest`. Two valid resolutions: (a) Accept as-is and file a tiny follow-up. (b) Reject back to implementation with a precise feedback note. Recommend (a) or (b) based on whether the schema's tri-acceptance is sufficient. Run `superpowers:requesting-code-review` and write the validation report.
  Chose (b) — reject back to implementation. The AC-1 gap is functional, not just UX: the committed schema regex rejects the digest tier even though `PackageReference.parse` round-trips it cleanly. The gb-T9 in-progress override (uncommitted in the worktree) is exactly the right fix. Validation report at `docs/razorback-implementation/validation/ade-bench-harbor-dataset-ref.md` enumerates the 5 concrete fixes required to reach `done`. Code review synthesized inline in the validation report (no sub-agent dispatch available in ensign/team mode); 2 blocking issues, 3 non-blocking, gate REJECT.

### Summary

Independent re-run of the focused 93-bundle + full unit suite passes cleanly on a HEAD checkout (after resetting the in-progress gb-T9 override work that was uncommitted in the worktree). AC-2/AC-3/AC-4/AC-5 are solid PASSes against the team-lead's stated criteria; AC-1 is PARTIAL — bare-name rejection guardrail is in place, but the schema regex rejects the captain-designated paper-grade digest tier. Gate decision: REJECT (option b). Five concrete fixes enumerated in the validation report; the gb-T9 override work that's already in the worktree carries most of them.

### Feedback Cycles

**Cycle 1 (2026-05-23, validation REJECT cited at bf32ae1):**

Validator chose option (b) reject-to-implementation on AC-1 PARTIAL FAIL.
The schema regex `[A-Za-z0-9_.+-]*` at `src/razorback/spec/schema.py:178-180`
and `dataset_ref.py:18` does not accept the `@sha256:` digest tier (colon
not in the character class), but AC-1 explicitly requires tri-acceptance
(tag / revision / digest) per `PackageReference.parse` round-trip. The
canonical example file also still uses `@latest` rather than the
captain-designated digest form. Concrete fixes routed to the next
implementation dispatch:

1. Replace regex with `PackageReference.parse` round-trip in
   `src/razorback/spec/schema.py:AdeBenchBenchmarkBlock._validate_source_selection`;
   require `parsed.org` + `parsed.short_name` + `parsed.ref` non-empty.
   Preserve the bare-name rejection error message naming both rule and
   canonical example (AC-1 guardrail).
2. Same swap in `src/razorback/benchmarks/ade_bench/dataset_ref.py:parse_dataset_ref`.
   Return `(parsed.org, parsed.short_name, parsed.ref)`.
3. Update `examples/specs/ade-bench-harbor-dataset-codex.yaml` line 20 from
   `dataset: dbt-labs/ade-bench@latest` to
   `dataset: dbt-labs/ade-bench@sha256:2c1f9e6966d01b0a5de2235d1a0b64089c7eead42c85c3b7b61d0929405c2bd5`.
   Update ABOUTME comments to reflect the digest tier as canonical.
4. Update `docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md`
   lines 87-94 to lead with the digest tier; keep `@latest` documented as
   valid for daily smoke.
5. Add (or restore — Circle K race may have reverted some) 4 tri-acceptance
   tests in `tests/unit/test_ade_bench_dataset_ref_schema.py`:
   `test_schema_accepts_tag_ref`, `test_schema_accepts_revision_ref`,
   `test_schema_accepts_digest_ref_canonical_pin`,
   `test_schema_validation_uses_harbor_package_reference_parser`. With the
   schema fix in place, the 12-test schema suite passes green.

Cycle 1 also covers a captain-flagged context: the prior cycle's
implementation worker (terminated mid-flight) had applied roughly the
correct fix to `dataset_ref.py` + `schema.py` but suffered file-revert
race conditions with the concurrent validator worker; those uncommitted
changes are still present in the worktree at start of cycle 2 and are a
reasonable starting point. Validator's report at
`docs/razorback-implementation/validation/ade-bench-harbor-dataset-ref.md`
(commit `bf32ae1`) is the authoritative source for the required fixes.

## Stage Report: implementation (cycle 2)

- DONE: Apply the 5 concrete fixes from the validation report (`docs/razorback-implementation/validation/ade-bench-harbor-dataset-ref.md`, committed at bf32ae1). The current worktree HAS uncommitted partial work in `src/razorback/spec/schema.py` and `src/razorback/benchmarks/ade_bench/dataset_ref.py` from the prior cycle — inspect with `git diff` first, then either complete or replace as needed. Required end-state: `PackageReference.parse` round-trip in both files; bare-name rejection error preserves the rule + canonical-example clauses; AC-1 schema accepts all three Harbor ref tiers (tag/revision/digest).
  Finished the prior-cycle uncommitted work as-is (correct end-state): both `AdeBenchBenchmarkBlock._validate_source_selection` and `parse_dataset_ref` now delegate to `PackageReference.parse` and require `parsed.org`/`parsed.short_name`/`parsed.ref` non-empty. Bare-name rejection error message preserved verbatim (rule + canonical example). Committed at 1cd97e7.
- DONE: Update `examples/specs/ade-bench-harbor-dataset-codex.yaml` line 20 to `dataset: dbt-labs/ade-bench@sha256:2c1f9e6966d01b0a5de2235d1a0b64089c7eead42c85c3b7b61d0929405c2bd5`. Update ABOUTME comments to reflect digest-tier-as-canonical. Update `docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md` lines 87-94 to lead with the digest tier; keep `@latest` documented as valid for daily smoke.
  Spec line 20 now ships the digest tier; ABOUTME lines reframed to "paper-grade digest pin" with the manifest hashes codifying the same hash for freeze provenance. Probe-note closing paragraph leads with the digest tier; `@latest` remains documented as valid for daily smoke. Downstream test assertions in `test_canonical_dataset_ref_spec_is_checked_in`, `test_canonical_dataset_ref_spec_translates_with_pinned_hashes`, and `test_freeze_command_writes_provenance_for_dataset_ref_spec` updated to match. Committed at f18618f.
- DONE: Land the 4 tri-acceptance tests in `tests/unit/test_ade_bench_dataset_ref_schema.py` (`test_schema_accepts_tag_ref`, `test_schema_accepts_revision_ref`, `test_schema_accepts_digest_ref_canonical_pin`, `test_schema_validation_uses_harbor_package_reference_parser`). Run `uv run pytest tests/unit/test_ade_bench_dataset_ref_schema.py` and report 12/12 passing. Run the focused 93-test bundle from the validator's report and ensure no regression. Append a cycle-2 Stage Report at the end of the entity body documenting each fix landed + commit SHAs.
  4 tri-acceptance tests landed; `uv run --frozen pytest tests/unit/test_ade_bench_dataset_ref_schema.py` -> 12 passed in 0.10s. Focused 17-file bundle (prior 93 + 4 new schema tests): `uv run --frozen pytest <17 files>` -> 97 passed in 1.61s. Full unit suite (minus pre-existing unrelated `test_task_identity_scoring` collection failure): `uv run --frozen pytest tests/unit/ -q --ignore=tests/unit/test_task_identity_scoring.py` -> 563 passed in 9.17s. Commit SHAs: 1cd97e7 (parser-backed validator + 4 tri-acceptance tests), f18618f (digest-tier canonical example + 3 downstream test updates).

### Summary

Cycle-2 implementation finished the prior cycle's uncommitted parser-backed
validator work (correct as-written) and landed the digest-tier canonical
example with matching downstream test updates. Schema's `PackageReference.parse`
round-trip now accepts all three Harbor ref tiers (tag / revision / digest);
bare-name rejection guardrail preserved. The `@sha256:` digest tier is now
the canonical example (paper-grade pin: resolver refuses mismatched content,
not just a downstream manifest check). 97/97 focused tests pass; 563/563
full unit suite passes (no regressions).

### Commit SHAs

- 1cd97e7 — fix(ade-bench): parser-backed Harbor dataset-ref validator (AC-1 tri-acceptance)
- f18618f — fix(ade-bench): canonical example uses @sha256: digest pin (AC-4 paper-grade)

## Stage Report: validation (cycle 2)

- DONE: Independently verify cycle-2's 5 fixes against the cycle-1 validation report at `docs/razorback-implementation/validation/ade-bench-harbor-dataset-ref.md` (committed at bf32ae1). For each of the 5 concrete fixes named there: confirm the change landed (cite the commit SHA and file:line). Run `uv run pytest tests/unit/test_ade_bench_dataset_ref_schema.py` and confirm 12/12. Run the original focused 93-test bundle + the 4 new tri-acceptance tests; confirm 97/97.
  All 5 fixes landed and cited per-fix in the validation report's `## Cycle 2 re-validation` section. Fix 1 + Fix 2 at `1cd97e7` (`src/razorback/spec/schema.py:230-255` and `src/razorback/benchmarks/ade_bench/dataset_ref.py:40-75`); Fix 3 + Fix 4 at `f18618f` (`examples/specs/ade-bench-harbor-dataset-codex.yaml:20` and `docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md:88-94`); Fix 5 at `1cd97e7` (`tests/unit/test_ade_bench_dataset_ref_schema.py:108,117,126,144`). Test runs: schema suite 12/12; focused 97-bundle 97/97; full unit suite 563/563 (exit 0 on all).
- DONE: Verify AC-1's tri-acceptance directly: open a `uv run python -c` and confirm `AdeBenchBenchmarkBlock(kind='ade-bench', dataset=<each of the three forms>)` accepts each one. Each form: `dbt-labs/ade-bench@latest`, `dbt-labs/ade-bench@1`, `dbt-labs/ade-bench@sha256:2c1f9e6966d01b0a5de2235d1a0b64089c7eead42c85c3b7b61d0929405c2bd5`. Confirm bare-name rejection still cites both rule + canonical example. AC-2/AC-3/AC-4/AC-5 from cycle 1 still hold (re-verify briefly; they passed at cycle 1 and no code in those AC paths changed).
  Direct `uv run python -c` accepts all three Harbor ref tiers (tag/revision/digest); bare-name `ade-bench@1.0` rejected with error containing both `<org>/<name>@<ref>` rule AND `dbt-labs/ade-bench@latest` canonical example. AC-2/AC-3/AC-4/AC-5 source paths untouched in cycle 2 (`git diff bf32ae1..HEAD --name-only` shows only schema.py + dataset_ref.py outside tests/docs/examples); AC-4 `rg "tasks_root: .*ade"` still returns 3 fixture-only paths; AC-5 `git submodule status` still empty.
- DONE: Append (or amend) the validation report at `docs/razorback-implementation/validation/ade-bench-harbor-dataset-ref.md` with a `## Cycle 2 re-validation` section documenting the verdict. Run code review against `bf32ae1..HEAD` (the cycle-2 commits 1cd97e7 + f18618f + fef3dfc). Gate decision: APPROVE → done, or REJECT back to implementation with concrete follow-ups.
  `## Cycle 2 re-validation` section appended. Code review of `bf32ae1..HEAD` inline in the report: no blocking issues; 2 non-blocking style/factoring notes (lazy-vs-eager import inconsistency; duplicated belt-and-suspenders block — both acceptable to defer). Gate decision: **APPROVE → done**.

### Summary

Cycle-2 closes the AC-1 PARTIAL FAIL cleanly. All 5 concrete fixes from the cycle-1 REJECT landed at the cited commits/lines; the schema now accepts all three Harbor ref tiers via `PackageReference.parse` round-trip and the canonical example demonstrates the paper-grade digest pin. 12/12 schema, 97/97 focused, 563/563 full unit on clean HEAD. AC-2..AC-5 unchanged from cycle-1 PASS. Gate: APPROVE → done.
