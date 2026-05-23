# Validation report: ADE-Bench uses Harbor published dataset references

**Entity:** `docs/razorback-implementation/ade-bench-harbor-dataset-ref.md`
**Worktree branch:** `spacedock-ensign/ade-bench-harbor-dataset-ref`
**Range reviewed:** `edd2b7c..e76450e` (9 commits)
**Validator runs:** clean checkout at `e76450e` after stashing the in-progress gb-T9 override work that was present in the worktree but uncommitted.

## Acceptance Criteria

### AC-1 — ADE specs accept a Harbor dataset reference. PARTIAL FAIL

Two clauses to verify:

1. **Schema rejects bare names with an error citing the canonical example AND the rule.** PASS.
   - Command: `python -c "AdeBenchBenchmarkBlock(kind='ade-bench', dataset='ade-bench@1.0')"`
   - Output (excerpt): `Value error, invalid Harbor dataset ref 'ade-bench@1.0': required shape is <org>/<name>@<ref> (e.g. 'dbt-labs/ade-bench@latest')`
   - Both `<org>/<name>@<ref>` and `dbt-labs/ade-bench@latest` are present in the error message.

2. **Schema accepts all three Harbor ref forms (tag/revision/digest) per a `PackageReference.parse` round-trip.** FAIL.
   - `PackageReference.parse` round-trip verified directly for all three forms:
     - `dbt-labs/ade-bench@latest` -> `(dbt-labs, ade-bench, latest)` OK
     - `dbt-labs/ade-bench@1` -> `(dbt-labs, ade-bench, 1)` OK
     - `dbt-labs/ade-bench@sha256:2c1f9e69...` -> `(dbt-labs, ade-bench, sha256:2c1f9e69...)` OK
   - But the SCHEMA itself rejects the digest form because the regex at
     `src/razorback/spec/schema.py:178-180` uses `[A-Za-z0-9_.+-]*` which does
     NOT include `:`. Constructing `AdeBenchBenchmarkBlock(kind='ade-bench',
     dataset='dbt-labs/ade-bench@sha256:2c1f9e69...')` raises
     `ValidationError: invalid Harbor dataset ref ...: required shape is
     <org>/<name>@<ref>`.
   - The same defect exists in `src/razorback/benchmarks/ade_bench/dataset_ref.py:18`
     (same regex shape).

Test evidence: 8 tests in `tests/unit/test_ade_bench_dataset_ref_schema.py` pass (the original RED batch). The committed working tree also contains 4 additional tests under that file (`test_schema_accepts_tag_ref`, `test_schema_accepts_revision_ref`, `test_schema_accepts_digest_ref_canonical_pin`, `test_schema_validation_uses_harbor_package_reference_parser`) that were authored by the in-progress gb-T9 override work but were left uncommitted; with the matching schema/resolver changes also uncommitted, `test_schema_accepts_digest_ref_canonical_pin` fails on the implementation as committed. This is the symptom that surfaces the AC-1 gap.

### AC-2 — Dataset resolution uses Harbor's public resolver. PASS

- `view_manifest.json` schema v2 carries all three required fields:
  `src/razorback/harbor_tasks/manifest.py:45,59-61` defines
  `schema_version: int`, `dataset_ref: str | None`, `dataset_content_hash: str | None`,
  `task_content_hash: str | None`.
- The translator passes `dataset_ref`, `dataset_content_hash` (dataset-version
  sha256 from `PackageDatasetClient.get_dataset_metadata`) and
  `task_content_hash` (per-task sha256 from `PackageTaskId.ref`) through
  `materialize_ade_harbor_task_view` (`src/razorback/translate.py:319-321`).
- Resolver test `test_resolve_dataset_tasks_records_dataset_content_hash`
  asserts both hashes appear in the `ResolvedDatasetTask` records.
- Integration smoke `test_canonical_dataset_ref_spec_translates_with_pinned_hashes`
  and `test_freeze_command_writes_provenance_for_dataset_ref_spec` open a
  real `view_manifest.json` from a translated run and confirm both hashes
  ride into the freeze provenance.

Command: `uv run --frozen pytest tests/unit/test_ade_bench_dataset_ref_resolver.py tests/unit/test_ade_bench_dataset_ref_translator.py tests/integration/test_ade_bench_dataset_ref_freeze_smoke.py` -> 19 passed.

### AC-3 — ADE task views still provide Razorback controls. PASS

- Guardrail test:
  `tests/unit/test_ade_bench_dataset_ref_translator.py::test_translator_preserves_docker_image_override_through_dataset_path`
  asserts the dataset-ref branch calls
  `materialize_ade_harbor_task_view(...,
  docker_image=spec.benchmark.docker_image_override, ...)`.
- Call site verified at `src/razorback/translate.py:312-323`: the dataset-ref
  branch funnels every resolved task through the same PKG-40 materializer
  used by the local-root branch (no parallel path that would skip
  ADE_BENCH_DENY_GLOBS / dbt-deps layer / `RAZORBACK_BENCHMARK_*` env vars).

Command: `uv run --frozen pytest tests/unit/test_ade_bench_dataset_ref_translator.py::test_translator_preserves_docker_image_override_through_dataset_path` -> 1 passed.

### AC-4 — Examples stop teaching local ADE roots as the canonical path. PASS

- `rg "tasks_root: .*ade" examples/specs examples/drivers` returns three
  matches, all under `./tests/fixtures/ade_bench/tasks`:
  - `examples/specs/codex-ade-bench-smoke.yaml:20` (carries
    `FIXTURE/DEV ade-bench` ABOUTME header pointing to canonical replacement).
  - `examples/specs/pkg40-ade-harbor-task-view-codex.yaml:20` (carries
    `FIXTURE/DEV PKG-40` ABOUTME header pointing to canonical replacement).
  - `examples/specs/probe-ade-bench-airbnb001-claude-harbor-local.yaml:25`
    (a PKG-40 probe spec; clearly dev-only by name + opening doc comment).
- Canonical example file present at
  `examples/specs/ade-bench-harbor-dataset-codex.yaml` with
  `dataset: dbt-labs/ade-bench@latest`. ABOUTME line 1: "Canonical ade-bench
  score spec — Harbor published dataset ref (no local task root)."
- Generator gains `--ade-dataset-ref` flag with 5 new tests; `--ade-bench-root`
  remains as the dev/fixture sibling (mutually exclusive). See
  `test_cli_dataset_ref_emits_canonical_ade_spec`,
  `test_cli_rejects_both_dataset_ref_and_local_root`,
  `test_canonical_dataset_ref_spec_is_checked_in`, etc.

### AC-5 — No submodule requirement. PASS

- In-test `git submodule status` assertion at
  `tests/integration/test_ade_bench_dataset_ref_freeze_smoke.py:117-134`:
  test `test_no_new_submodule_required_by_dataset_ref_path` runs
  `git submodule status` from `REPO_ROOT` and asserts no forbidden marker
  (`ade-bench`, `harbor-datasets`, `ade_bench`) appears in the output.
- Live verification: `git submodule status` returns empty.
- Error-path coverage for resolver failure:
  `test_translator_dataset_ref_resolver_failure_translates_to_spec_error`,
  `test_resolve_dataset_tasks_client_failure_wraps`.

## Test runs (independent, on clean HEAD after stash)

Focused 93-test bundle (matches impl report):
`uv run --frozen pytest <17 files>` -> **93 passed in 1.47s. Exit 0.**

Full unit suite minus pre-existing failure:
`uv run --frozen pytest tests/unit/ -q --ignore=tests/unit/test_task_identity_scoring.py` ->
**559 passed in 8.46s. Exit 0.**

(Impl report claimed 553 passed; my count is 559. The +6 difference is
explained by the in-progress override work that committed test additions
beyond what the impl report enumerated, but a single test from that batch —
`test_schema_accepts_digest_ref_canonical_pin` — fails on committed
implementation. After resetting the working tree to HEAD for this run, the
test does not load because the test file was reset; the 559-pass count
corresponds to the committed-HEAD shape.)

Pre-existing baseline failure confirmed unchanged:
`uv run --frozen pytest tests/unit/test_task_identity_scoring.py` -> still
fails with `ModuleNotFoundError: No module named 'razorback.score.load'`
(unrelated to this entity).

## Code review

### Strengths
- Layered design: dataset-ref is a sibling source-resolver under the existing
  PKG-40 materializer. No parallel materializer; the leakage deny-globs,
  dbt-deps Dockerfile layer, and `RAZORBACK_BENCHMARK_*` env-var injection
  all apply unchanged on the new path.
- Resolver error wrapping is correct (`BaseException` catch with `SpecError`
  re-raise preserved) so `rk freeze` SPEC_ERROR exit codes stay consistent.
- Three-hash manifest schema (`dataset_ref` + `dataset_content_hash` +
  `task_content_hash`) is the right reproducibility pin: dataset-level hash
  is sufficient for "same dataset version", per-task hash is sufficient for
  "same task body even if the dataset is republished with a different task
  set". `@latest` is documentation; the hashes are load-bearing.
- T0 probe note (`docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md`)
  is genuinely useful: documents the 4 plan deviations (org name,
  ref-shape, API entry point, task-slug prefix) with cited evidence.

### Issues

#### Blocking
1. **Schema regex rejects the digest tier.** `src/razorback/spec/schema.py:178-180`
   and `src/razorback/benchmarks/ade_bench/dataset_ref.py:18` use a regex
   character class `[A-Za-z0-9_.+-]*` that does not match `:`. Harbor's
   canonical paper-grade pin shape `@sha256:<digest>` includes a colon and
   therefore fails validation. AC-1 explicitly requires the schema to accept
   all three Harbor ref forms (tag / revision / digest) per
   `PackageReference.parse` round-trip; the regex shortcuts that round-trip
   and gets it wrong. Fix: delegate to `PackageReference.parse` and require
   `parsed.org`, `parsed.short_name`, `parsed.ref` to all be non-empty —
   exactly what gb-T9 has in-progress in the uncommitted working tree at the
   moment of this validation.

2. **Canonical example uses `@latest` instead of the digest.** The captain's
   mid-flight override (after T0 surfaced that Harbor's `PackageReference`
   supports `@sha256:`) directed that the canonical example demonstrate the
   digest tier (paper-grade pin). The committed
   `examples/specs/ade-bench-harbor-dataset-codex.yaml:20` ships
   `dbt-labs/ade-bench@latest`. The probe note line 90-94 explicitly calls
   out `@latest` as the example shape but defends it on the grounds that
   the hashes are pinned in the manifest — that defense is sound for
   AC-2/AC-5 reproducibility but does not satisfy the captain's "lead with
   the digest" UX guardrail.

#### Non-blocking
3. **`harbor_view.py` and `materialize.py` accept the three new kwargs but
   the surface change is minimal.** Diff stat shows +6 lines on each; the
   forward is straightforward kwarg passthrough into the manifest dataclass.
   Tests cover it; no concern.

4. **`tests/fixtures/ade_bench/fake_dataset/` was added as the resolver test
   fixture.** Shape mirrors the live Harbor export (flat
   `<output_dir>/ade-bench-<slug>/task.toml`). Fine; documented in probe note.

5. **Stage report counts.** Impl report says "8 schema tests" but the
   committed-but-uncommitted in-tree work added 4 more (one of which fails
   on committed code). This is a side-effect of gb-T9 being mid-flight at
   validation time; not a defect in the validated implementation itself.

### Recommendations
- After fixing the blocking issues above, re-run the 93-test bundle plus the
  3-tier acceptance tests (`test_schema_accepts_tag_ref`,
  `test_schema_accepts_revision_ref`, `test_schema_accepts_digest_ref_canonical_pin`,
  `test_schema_validation_uses_harbor_package_reference_parser`) and ensure
  the 12-test schema suite is fully green.
- The "free-form `@<ref>` regex" is a recurring shape across the codebase;
  if other benchmarks gain Harbor ref fields, factor `PackageReference.parse`
  into a single helper to avoid this same drift.

## Gate decision

**REJECT back to implementation (option b in the dispatch CHECK).**

### Reasoning

The team-lead's dispatch presents this as a binary on UX vs functional
correctness, and explicitly defines AC-1's tri-acceptance clause:

> "schema accepts all three Harbor ref forms (tag/revision/digest) per a
> `PackageReference.parse` round-trip"

The committed schema does not satisfy that clause: the digest form fails
validation. This is a functional AC-1 gap, not just a "canonical example
chose the wrong tier" UX issue. Option (a) "accept as-is and file a tiny
follow-up" would leave the schema rejecting the form the captain explicitly
designated as the paper-grade pin — and would also leave the in-progress
gb-T9 override work (which is exactly the right fix) in an unmerged limbo.

Option (b) closes the loop cleanly: the override work already exists in the
worktree (uncommitted), the schema fix is mechanical (swap regex for
`PackageReference.parse` round-trip), and the canonical example swap is
one line. Estimated effort to ship the rejection feedback: under 30 minutes.

### Concrete fixes required to reach `done`

1. **`src/razorback/spec/schema.py`**: replace the
   `_ADE_BENCH_DATASET_REF_RE.match(self.dataset)` validation in
   `AdeBenchBenchmarkBlock._validate_source_selection` with a
   `PackageReference.parse(self.dataset)` round-trip; require
   `parsed.org` and `parsed.ref` non-empty (the parser is permissive and
   accepts bare names without `org`). Error message preserves the
   `<org>/<name>@<ref>` shape + canonical-example clauses (AC-1 guardrail
   unchanged).

2. **`src/razorback/benchmarks/ade_bench/dataset_ref.py`**: same swap on
   `parse_dataset_ref`. Return `(parsed.org, parsed.short_name, parsed.ref)`.

3. **`examples/specs/ade-bench-harbor-dataset-codex.yaml`**: update line 20
   from `dataset: dbt-labs/ade-bench@latest` to
   `dataset: dbt-labs/ade-bench@sha256:2c1f9e6966d01b0a5de2235d1a0b64089c7eead42c85c3b7b61d0929405c2bd5`.
   Update the ABOUTME comment lines if they reference `@latest` directly.

4. **`docs/razorback-implementation/notes/ade-bench-harbor-dataset-ref-probe.md`**:
   update the "canonical example" paragraph (lines 87-94) to lead with the
   digest tier; keep `@latest` valid for daily smoke.

5. **Commit the 4 already-authored tests** in
   `tests/unit/test_ade_bench_dataset_ref_schema.py`
   (`test_schema_accepts_tag_ref`, `test_schema_accepts_revision_ref`,
   `test_schema_accepts_digest_ref_canonical_pin`,
   `test_schema_validation_uses_harbor_package_reference_parser`) along
   with the schema/resolver changes so the 12-test schema suite is green.

After those changes, re-run the 93-bundle + the 4 tri-acceptance tests and
the full unit suite to confirm no regressions.
