# Validation — M5 — Provenance freeze + full DAB scoring (first DAB result)

Worktree branch: `spacedock-ensign/m5-provenance-full-dab`
Tip commit at validation start: `0111928` (`m5: implementation stage report — 13/13 tasks, first DAB result = 0.6746 (6-dataset subset)`)
Validator: fresh agent, did not write the implementation
Authoritative inputs: M5 entity body (7 ACs), plan at `docs/razorback-implementation/plans/m5-provenance-full-dab.md`, design doc §6.4 / §6.5 / §3.2.

## Reproduction summary

From a clean checkout of the worktree branch tip:

- `uv run pytest` → **`118 passed, 1 skipped` in `382.48s` (6:22)** (rerun: `118 passed, 1 skipped in 477.16s` confirms stability).
- The single skip is `tests/integration/test_dab_dev_claude_full.py::test_dab_dev_claude_full_writes_complete_summary`, gated by `RAZORBACK_RUN_FULL_DAB_TEST=1` (intentionally not rerun — the AC-6 live run already cost real money; the deliverable summary.json snapshot is committed at `docs/razorback-implementation/m5-first-dab-result-summary.json` per FO authorization).
- 119 tests collected. Decomposition: **17 M1 + 27 M2 + 28 M3 + 46 M5 unit + 1 M5 integration (gated) = 119**. M4 has not landed on this worktree (it forked from M3-done). Carry-forward intact.

M5's 46 new unit tests:
- `tests/unit/test_provenance_alias_drift.py` (4) — AC-3 mocked Anthropic SDK
- `tests/unit/test_provenance_harbor_drift.py` (4) — AC-4 major-version drift
- `tests/unit/test_provenance_refuses_missing.py` (9) — AC-1 per-field refusal + ExitCode.PROVENANCE_ERROR == 11
- `tests/unit/test_provenance_resolvers.py` (12) — six resolver coverage including 503-retry-then-succeed and 404-hard-error
- `tests/unit/test_provenance_retry.py` (3) — AC-7 retry harness
- `tests/unit/test_provenance_yaml.py` (4) — provenance.yaml shape, alias_drift record
- `tests/unit/test_run_drift_wired.py` (2) — AC-3/AC-4 wired into `execute_run` BEFORE `Job.create`
- `tests/unit/test_spec_freeze_cli.py` (3) — AC-1, AC-2 CLI surface
- `tests/unit/test_dab_aggregate_twelve_datasets.py` (2) — AC-5 stratified macro-average across 12 datasets
- `tests/unit/test_dab_translator_twelve.py` (2) — translator fan-out widened from 1 to 12 datasets

## AC verification

Each AC reproduced against the worktree-branch tip.

### AC-1 — `rk spec freeze` resolves all six provenance fields and refuses on any unresolved field absent `--allow-missing` — PASS

`Verified by:` "unit tests feed a spec missing each provenance field in turn and assert the freeze command exits with `ProvenanceError` (exit code 11) and writes neither the frozen spec nor `provenance.yaml`."

Tests:
- `tests/unit/test_provenance_refuses_missing.py::test_refuses_when_any_single_field_missing[model_resolved_version|image_digest|agent_cli_hash|harness_git_sha|harbor_version|prompt_file_hashes]` — 6 parametrized PASSED. Each asserts `exc.exit_code == ExitCode.PROVENANCE_ERROR == 11`.
- `tests/unit/test_provenance_refuses_missing.py::test_refusal_lists_all_missing_fields_not_just_first` — PASSED.
- `tests/unit/test_spec_freeze_cli.py::test_freeze_refuses_when_field_missing` — PASSED. Invokes `rk spec freeze` via `CliRunner`; asserts `exit_code == 11`, neither `*.frozen.yaml` nor `provenance.yaml` exists after the failure (lines 89-91 of the test file).

Refusal predicate at `src/razorback/provenance/provenance_yaml.py:24-33`. CLI wiring at `src/razorback/provenance/freeze_cmd.py:74-78` (`refuse_if_any_unresolved` is called BEFORE the freeze body is written at line 80-92, so the "writes neither" clause holds by control flow). AC-1 met verbatim.

### AC-2 — `--allow-missing` writes frozen spec but records unresolved fields in `provenance.yaml` — PASS

`Verified by:` "a unit test runs freeze with `--allow-missing` against a spec whose model API is mocked to return 503; the frozen spec lands and `provenance.yaml` contains the unresolved field marker."

Tests:
- `tests/unit/test_spec_freeze_cli.py::test_freeze_allow_missing_writes_with_unresolved_marker` — PASSED. Invokes `rk spec freeze <spec> --allow-missing` with `resolve_model_version` stubbed to return `(None, None)`; asserts `exit_code == 0` and `prov["unresolved"]` contains `"model_resolved_version"`.
- `tests/unit/test_provenance_refuses_missing.py::test_allow_missing_does_not_raise_even_when_fields_missing` — PASSED.
- `tests/unit/test_provenance_yaml.py::test_unresolved_field_appears_in_unresolved_list_not_in_body` — PASSED.

The literal "503 mock" path is exercised at the resolver layer via `test_provenance_resolvers.py::test_resolve_model_version_retries_503_then_succeeds` and the freeze-CLI path via the stubbed `(None, None)` return. AC-2 met by direct exercise of `--allow-missing` + unresolved marker.

### AC-3 — `AliasDriftError` (exit code 21) fires when the provider returns a different version — PASS

`Verified by:` "a unit test mocks the provider API to return a different version than the frozen value; `rk run` exits 21 and the resulting `provenance.yaml` (when `--allow-alias-drift` is passed) records both versions."

Tests:
- `tests/unit/test_provenance_alias_drift.py::test_alias_drift_raises_when_provider_version_differs` — PASSED. Asserts `exc.exit_code == ExitCode.ALIAS_DRIFT == 21` and the message contains both `claude-opus-4-5-20251022` (frozen) and `claude-opus-4-5-20260101` (resolved).
- `tests/unit/test_provenance_alias_drift.py::test_alias_drift_allow_returns_both_versions_for_provenance_recording` — PASSED. With `allow=True`, both versions are returned (for downstream provenance.yaml recording).
- `tests/unit/test_provenance_alias_drift.py::test_alias_drift_error_carries_both_versions_on_exc` — PASSED. `exc.frozen` and `exc.resolved` exposed for the provenance.yaml writer.
- `tests/unit/test_provenance_yaml.py::test_drift_record_appears_under_alias_drift` — PASSED. `provenance.yaml` records both versions under `alias_drift.frozen` and `alias_drift.resolved`.
- `tests/unit/test_run_drift_wired.py::test_run_refuses_on_alias_drift_by_default` — PASSED. `execute_run(allow_alias_drift=False)` raises `AliasDriftError` before reaching `Job.create`.

Code path verified at `src/razorback/run.py:53-70`: `check_alias_drift` fires at line 58, BEFORE `Job.create` at line 102. Drift record builds at lines 64-70 when `allow_alias_drift=True`. AC-3 met verbatim.

### AC-4 — Harbor major-version drift between freeze and run is a hard error — PASS

`Verified by:` "a unit test patches `harbor.__version__` to a different major than the frozen value; `rk run` refuses with a typed error before reaching `Job.create`."

Tests:
- `tests/unit/test_provenance_harbor_drift.py::test_major_drift_raises` — PASSED. 0.6.6 → 1.0.0 raises `HarborDriftError`.
- `tests/unit/test_provenance_harbor_drift.py::test_major_drift_raises_2_to_1` — PASSED. Symmetric direction.
- `tests/unit/test_provenance_harbor_drift.py::test_check_harbor_drift_reads_installed_version_when_not_passed` — PASSED. Patches `_installed_harbor_version()` (the `harbor.__version__` wrapper) and asserts the drift fires.
- `tests/unit/test_provenance_harbor_drift.py::test_no_drift_when_major_matches` — PASSED. 0.6.6 ↔ 0.6.6, 0.6.6 ↔ 0.7.0, 0.6.6 ↔ 0.6.99 all pass through.
- `tests/unit/test_run_drift_wired.py::test_run_refuses_on_harbor_drift` — PASSED. `execute_run` raises `HarborDriftError` before `Job.create`.

Code path: `src/razorback/run.py:50-51` — `check_harbor_drift` fires at line 51, BEFORE `Job.create` at line 102. AC-4 met verbatim.

### AC-5 — DAB aggregator produces a stratified macro-average across the 12 datasets per §6.5 — PASS

`Verified by:` "a unit test feeds a fixture covering all 12 DAB datasets to the aggregator and asserts the resulting `summary.json` has a stratified pass@1 line whose value matches the cross-dataset macro-average computed by hand on the fixture."

Tests:
- `tests/unit/test_dab_aggregate_twelve_datasets.py::test_aggregator_stratifies_across_twelve_datasets` — PASSED. Fixture at `tests/fixtures/provenance/twelve_dataset_trial_results.json` (120 rows across all 12 dataset slugs: agnews, bookreview, crmarenapro, DEPS_DEV_V1, GITHUB_REPOS, googlelocal, music_brainz_20k, PANCANCER_ATLAS, PATENTS, stockindex, stockmarket, yelp). Golden at `twelve_dataset_golden_summary.json` matches the aggregator output exactly.
- `tests/unit/test_dab_aggregate_twelve_datasets.py::test_stratified_pass_at_1_is_hand_computed_macro_average` — PASSED. **Independent re-derivation**: `got["stratified_pass_at_1"] - sum(per_ds) / 12 < 1e-9` AND `got["stratified_pass_at_1"] - 6.5 / 12 < 1e-9`. The hand-computed 6.5/12 = 0.5417 macro-average is reached without reading the golden.

Independent reproduction: validator loaded the fixture directly and confirmed (a) 12 distinct datasets, (b) golden `stratified_pass_at_1 = 0.5416666...`, (c) `6.5/12 = 0.5416666...` matches. The aggregator math (`_build_summary` + `pass_at_k` in `src/razorback/benchmarks/dab/aggregate.py`) is M2's untouched code path; M5 widened only the input. AC-5 met verbatim — the math correctness AC is independent of the AC-6 subset deferral.

### AC-6 — End-to-end full DAB dev-tier run writes complete `summary.json` — PASSED-WITH-NOTE

`Verified by:` "`uv run rk run examples/specs/dab-dev-claude.yaml` exits 0 against the full DAB dev tier and the run-dir's `summary.json` contains: a per-query block for each of the 12 datasets, a per-dataset mean for each, and a single stratified macro-average line."

**FO-authorized subset deferral.** The implementer attempted the full 12-dataset live run and hit a host-disk constraint (M2's `prepare.py` deep-copies `query_dataset/` trees per task — `shutil.copytree` at `src/razorback/benchmarks/dab/prepare.py:152-167`; PATENTS alone is ~5.2 GB; total deep-copy footprint estimated 30-60 GB; host had ~16 GB free). The FO authorized a 6-dataset subset run as the M5 deliverable; the committed snapshot is at `docs/razorback-implementation/m5-first-dab-result-summary.json`. The canonical 12-dataset spec `examples/specs/dab-dev-claude.yaml` remains in the tree for a future operator with disk headroom and is exercised by the gated `tests/integration/test_dab_dev_claude_full.py` (skipped without `RAZORBACK_RUN_FULL_DAB_TEST=1`).

Snapshot inspection (validator-direct):

- **Per-query block:** present for each of 24 queries across 6 datasets (each with `query_id`, `n_trials`, `n_correct`, `pass_at_1`). Counts: agnews 4, bookreview 3, googlelocal 4, music_brainz_20k 3, stockindex 3, yelp 7.
- **Per-dataset mean:** `dataset_pass_at_1` present for all 6 datasets — `bookreview 1.000`, `stockindex 1.000`, `googlelocal 0.750`, `yelp 0.714`, `music_brainz_20k 0.333`, `agnews 0.250`.
- **Single stratified macro-average:** `stratified_pass_at_1: 0.6746031746031745`.

Math re-derived by validator: `(0.25 + 1.0 + 0.75 + 0.3333 + 1.0 + 0.7143) / 6 = 0.67460317460...` — matches the recorded value to floating-point precision. The aggregator produced the deliverable shape correctly through a real Claude agent run (claude-opus-4-5-20251101, image sha256:018978c8...).

**Assessment.** The deliverable is materially what M5 set out to produce: per-query / per-dataset / stratified pass@1 across N datasets through a real Claude agent — the math correctness for the full 12 is independently proven by AC-5's golden, and the live mechanism (freeze → run → summary.json) is proven end-to-end on a subset. The subset-deferral was authorized by the FO BEFORE the run started; per dispatch instructions, "the subset-deferral on AC-6 is NOT itself a blocker". PASSED-WITH-NOTE: the M6+ prepare.py symlink follow-up (avoid the deep-copy and unlock the full 12) is tracked in the M5 implementation stage report.

### AC-7 — Provenance retries with exponential backoff on transient 503s — PASS

`Verified by:` "a unit test mocks the provider API to return 503 twice then 200; the freeze succeeds and the resolved version lands in `provenance.yaml`."

Tests:
- `tests/unit/test_provenance_retry.py::test_retries_twice_then_succeeds` — PASSED. Harness-level: 503, 503, 200 → returns `"ok"`; `sleeps == [0.1, 0.2]` (exponential).
- `tests/unit/test_provenance_retry.py::test_gives_up_after_max_attempts` — PASSED.
- `tests/unit/test_provenance_retry.py::test_non_transient_raises_immediately` — PASSED.
- `tests/unit/test_provenance_resolvers.py::test_resolve_model_version_retries_503_then_succeeds` — PASSED. Resolver-level: mocked `client.models.retrieve` raises 503 twice then returns `(claude-opus-4-5-20251022, 2025-10-22T00:00:00Z)`; resolver returns the resolved value with 2 sleeps recorded.

Composition into the freeze command is via `test_freeze_allow_missing_writes_with_unresolved_marker` (when the resolver returns None due to non-transient failure) and `test_freeze_all_resolved_writes_frozen_and_provenance` (when the resolver succeeds, `provenance.yaml.model_resolved_version` lands). The 503-then-200 → provenance.yaml lands path is the composition of `test_resolve_model_version_retries_503_then_succeeds` + `test_freeze_all_resolved_writes_frozen_and_provenance`. AC-7 met by the resolver-level exercise + freeze-CLI composition.

## Code review

Independent review of the M5 diff (33 files, +2777/-10 LoC since `c45bed3` `merge: m3-claude-cli-agent`):

**Strengths.**
- Risk-first commit ordering — AC-3 (`2be3ea6`), AC-1 (`6e3e977`), AC-4 (`e0e7a2a`) all land as mocked unit tests BEFORE resolver code (`769d1a8`) and freeze CLI (`d4ea553`).
- Every resolver dependency-injects its externals (Anthropic client factory, docker shell, `which`, git runner, sleep) — unit tests run in zero wallclock.
- Drift checks fire BEFORE `Job.create` (run.py:51, 58 vs. line 102). The "before harbor" invariant is enforced by control flow, not just by docstring.
- AC-5's golden is hand-derivable (6.5/12) and the test independently re-derives it without trusting the golden — strong evidence.
- ABOUTME headers consistent across all 7 new `src/razorback/provenance/` files.
- Exit codes registered through the `ExitCode` IntEnum (PROVENANCE_ERROR=11, ALIAS_DRIFT=21) — design §3.2 wire surface preserved.

**Minor (non-blocking).**
1. `src/razorback/provenance/freeze_cmd.py:44-47` swallows all exceptions from `resolve_model_version` and converts them to `(None, None)`. A 404 typo'd model name therefore surfaces as `ProvenanceError: unresolved provenance fields: model_resolved_version` (exit 11) instead of the more actionable "404 not found" — the exit code is still correct per §6.4, but the diagnostic is less precise. Track-forward for M6 polish.
2. `src/razorback/provenance/errors.py:31` — `HarborDriftError.exit_code = ExitCode.GENERIC` (1). Design §3.2 reserves 11 and 21 for ProvenanceError and AliasDriftError respectively but doesn't assign a code for HarborDriftError. AC-4's Verified by clause only requires "a typed error before reaching Job.create"; the typed-error requirement is met. Reserving a dedicated exit code is a future cleanup.
3. `examples/specs/dab-dev-claude.yaml:13` (and `-subset.yaml:13`) hardcodes `data_root: /Users/clkao/git/dataagentbench/data` — a developer-machine absolute path. Matches M2's pattern; portability concern is tracked-forward.
4. `freeze_cmd.py:53` hardcodes `cli_bin = "claude"` for `kind == "claude-cli"`. Codex/OpenAI explicitly deferred to M6/M7 per plan and design doc; intentional and documented.

**Blocking.** None.

**Cross-cut check — M1+M2+M3 tests stay green:** all 17 M1 + 27 M2 + 28 M3 tests pass on the M5 worktree tip (verified by full pytest run above). No regressions.

## Gate decision

**PASSED.** All 7 ACs reproduce against the worktree branch tip. AC-6 is PASSED-WITH-NOTE per the FO-authorized subset deferral — the deliverable shape (per-query / per-dataset / stratified pass@1 through a real Claude agent) is materially achieved on 6 datasets, the math for the full 12 is independently proven by AC-5's hand-derivable golden, and the M2 prepare.py symlink follow-up to unlock the full 12-dataset run is tracked forward. No blocking code-review findings. M1/M2/M3 carry-forward green. Approve to `done`.

## Stage Report

(See the entity file at `docs/razorback-implementation/m5-provenance-full-dab.md` for the canonical Stage Report: validation entry.)
