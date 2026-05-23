# Validation Report: Historical wallclock ordering hints for job dispatch

Entity: `k05te9qfkv1at7qh3zay5naf`
Branch: `spacedock-ensign/job-ordering-from-run-wallclock-hints`
Validated commits: `db9e249`, `1212642`, `518a030`, `fbb8b09`, `97b375b`, `15e742e`, `57eba27`, `044da5e`, `fa0662e`

## Cycle 2 Validation

Gate decision: PASSED.

Cycle 1 was rejected because two branch-local unit test doubles did not accept
the additive `ordering_hint` keyword. Commit `044da5e` updated both test doubles,
and the required cycle-2 focused commands now pass. The optional full suite still
has unrelated environment/integration failures, but no ordering-hint or
branch-local unit regressions remain.

## Cycle 2 Commands Run

Previously failing branch-local tests:

```text
PYTHONPATH=packages/razorback-plugin-dab/src .venv/bin/python -m pytest --import-mode=importlib tests/unit/test_cli_run_aggregator_wiring.py::test_cli_run_invokes_aggregator_on_harbor_success tests/unit/test_run_plugin_drift_wired.py::test_run_with_allow_plugin_drift_records_in_provenance -q
..                                                                       [100%]
2 passed in 0.79s
```

Focused ordering/provenance/scoring suite:

```text
PYTHONPATH=packages/razorback-plugin-dab/src .venv/bin/python -m pytest --import-mode=importlib tests/unit/test_run_ordering.py tests/unit/test_rk_run_ordering_hint_cli.py tests/unit/test_rk_run_v2_provenance_artifacts.py tests/unit/test_task_identity_scoring.py tests/unit/test_score_load.py tests/unit/test_cli_run_aggregator_wiring.py tests/unit/test_run_plugin_drift_wired.py -q
..........................                                               [100%]
26 passed in 1.24s
```

Focused translator/harbor-view/aggregate suite:

```text
PYTHONPATH=packages/razorback-plugin-dab/src .venv/bin/python -m pytest --import-mode=importlib tests/unit/test_ade_bench_translator.py tests/unit/test_ade_bench_harbor_view.py tests/unit/test_runs_aggregate.py -q
................                                                         [100%]
16 passed in 0.86s
```

Focused pre-check suite:

```text
PYTHONPATH=packages/razorback-plugin-dab/src .venv/bin/python -m pytest --import-mode=importlib tests/unit/test_rk_run_v2_pre_checks.py -q
...                                                                      [100%]
3 passed in 0.84s
```

Optional full suite:

```text
uv run pytest
4 failed, 568 passed, 9 skipped, 16 warnings in 37.82s
```

Full-suite failures:

```text
FAILED tests/integration/test_budget_gate_two_invocations.py::test_two_sequential_invocations_second_refuses
FAILED tests/integration/test_budget_gate_two_invocations.py::test_without_flag_regression_against_smoke
FAILED tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end
FAILED tests/integration/test_rk_run_v2_deterministic_smoke.py::test_deterministic_smoke_runs_end_to_end
```

The first, second, and fourth failures require external DAB data at
`/Users/clkao/git/dataagentbench/data/query_bookreview`. The
`test_rk_run_nop_end_to_end` failure is the previously documented
`AssertionError: events.jsonl is empty`. The two branch-local unit failures
from cycle 1 are no longer present in either the required focused commands or
the optional full-suite run.

## Cycle 2 Acceptance Criteria

AC-1 - Optional ordering hint input: PASS.

Evidence: `test_rk_run_without_ordering_hint_preserves_input_order` and
`test_rk_run_order_from_run_serializes_longest_known_tasks_first` passed in the
required focused command. Code inspection confirmed `src/razorback/cli/run.py`
exposes `--order-from-run`, leaves no-hint task order unchanged, and applies
ordering only when a hint is provided.

AC-2 - Wallclock extraction is robust: PASS.

Evidence: `tests/unit/test_run_ordering.py` passed. Code inspection confirmed
`src/razorback/run_ordering.py` parses `started_at`/`finished_at`, handles run
directories and single result files, ignores missing/malformed/non-positive
timings, and records warning strings plus ignored counts.

AC-3 - Longest-known-first scheduling: PASS.

Evidence: `tests/unit/test_run_ordering.py` and
`tests/unit/test_rk_run_ordering_hint_cli.py` passed. Inspection confirmed
known durations sort descending, unknown tasks retain original relative order,
and the serialized Harbor `JobConfig` order is asserted under
`n_concurrent_trials == 2`.

AC-4 - Results semantics do not change: PASS.

Evidence: `tests/unit/test_task_identity_scoring.py` and
`tests/unit/test_score_load.py` passed in the focused suite. Inspection
confirmed the implementation only reorders `job_config.tasks`; aggregation and
scoring continue to resolve trial identity from task-view manifests and trial
names.

AC-5 - Provenance records the hint: PASS.

Evidence: `test_rk_run_records_ordering_hint_metadata_in_manifest_and_provenance`
and `tests/unit/test_rk_run_v2_provenance_artifacts.py` passed. Inspection
confirmed additive `ordering_hint` metadata is written through
`src/razorback/runs/aggregate.py` and
`src/razorback/provenance/provenance_yaml.py`.

## Cycle 2 Code Review Findings

Blocking: none.

Non-blocking:

- Optional `uv run pytest` still fails on unrelated environment/integration
  issues: missing external DAB bookreview data and empty `events.jsonl` in the
  nop integration test.

## Cycle 2 Gate Decision

PASSED.

The cycle-1 branch-local unit regressions are fixed, AC-1 through AC-5 are
covered by focused tests plus inspection, and the remaining full-suite failures
match previously documented external/integration blockers unrelated to this
ordering-hint change.

## Commands Run

Focused ordering/provenance/scoring suite:

```text
PYTHONPATH=packages/razorback-plugin-dab/src .venv/bin/python -m pytest --import-mode=importlib tests/unit/test_run_ordering.py tests/unit/test_rk_run_ordering_hint_cli.py tests/unit/test_rk_run_v2_provenance_artifacts.py tests/unit/test_task_identity_scoring.py tests/unit/test_score_load.py -q
18 passed in 1.01s
```

Focused translator/harbor-view/aggregate suite:

```text
PYTHONPATH=packages/razorback-plugin-dab/src .venv/bin/python -m pytest --import-mode=importlib tests/unit/test_ade_bench_translator.py tests/unit/test_ade_bench_harbor_view.py tests/unit/test_runs_aggregate.py -q
16 passed in 0.89s
```

Focused pre-check suite:

```text
PYTHONPATH=packages/razorback-plugin-dab/src .venv/bin/python -m pytest --import-mode=importlib tests/unit/test_rk_run_v2_pre_checks.py -q
3 passed in 0.89s
```

Full suite:

```text
uv run pytest
6 failed, 566 passed, 9 skipped, 16 warnings in 42.26s
```

Full-suite failures:

```text
FAILED tests/integration/test_budget_gate_two_invocations.py::test_two_sequential_invocations_second_refuses
FAILED tests/integration/test_budget_gate_two_invocations.py::test_without_flag_regression_against_smoke
FAILED tests/integration/test_rk_run_nop.py::test_rk_run_nop_end_to_end
FAILED tests/integration/test_rk_run_v2_deterministic_smoke.py::test_deterministic_smoke_runs_end_to_end
FAILED tests/unit/test_cli_run_aggregator_wiring.py::test_cli_run_invokes_aggregator_on_harbor_success
FAILED tests/unit/test_run_plugin_drift_wired.py::test_run_with_allow_plugin_drift_records_in_provenance
```

The first, second, and fourth failures require external DAB data at `/Users/clkao/git/dataagentbench/data/query_bookreview`. The `test_rk_run_nop_end_to_end` failure is `AssertionError: events.jsonl is empty`. The two unit failures are branch-local regression fallout from new optional keyword plumbing:

```text
tests/unit/test_cli_run_aggregator_wiring.py:58: KeyError: 'benchmark_kind'
```

`src/razorback/cli/run.py:368-375` now calls `safe_aggregate_run_dir(..., ordering_hint=ordering_hint_metadata)`. The existing test double at `tests/unit/test_cli_run_aggregator_wiring.py:43-44` does not accept `ordering_hint`, so `safe_aggregate_run_dir` catches the `TypeError` as a warning and the test's capture never runs.

```text
tests/unit/test_run_plugin_drift_wired.py:136: AssertionError
Result TypeError: _capture() got an unexpected keyword argument 'ordering_hint'
```

`src/razorback/cli/run.py:345-350` now calls `_write_provenance_artifacts(..., ordering_hint=ordering_hint_metadata)`. The patched capture function at `tests/unit/test_run_plugin_drift_wired.py:123` does not accept the new keyword.

## Acceptance Criteria

AC-1 - Optional ordering hint input: PASS.

Verified by:

```text
tests/unit/test_rk_run_ordering_hint_cli.py ... [100%]
```

Code inspection confirmed `rk run` exposes `--order-from-run` in `src/razorback/cli/run.py`, applies no ordering when the option is absent, and the CLI test asserts no-hint `_job_config.yaml` order `["short", "unknown", "long"]` versus hinted order `["long", "short", "unknown"]`.

AC-2 - Wallclock extraction is robust: PASS.

Verified by:

```text
tests/unit/test_run_ordering.py ..... [100%]
```

Code inspection confirmed `src/razorback/run_ordering.py` parses trial `started_at`/`finished_at`, ignores missing/malformed/non-positive records with warning strings, supports single result files and run directories, and uses max elapsed wallclock for repeated task keys.

AC-3 - Longest-known-first scheduling: PASS.

Verified by:

```text
tests/unit/test_run_ordering.py ..... [100%]
tests/unit/test_rk_run_ordering_hint_cli.py ... [100%]
```

The helper test asserts known durations sort descending with unknown tasks retaining original relative order. The CLI mechanism test asserts the serialized Harbor `JobConfig` task order is `["long", "short", "unknown"]` and `n_concurrent_trials == 2`.

AC-4 - Results semantics do not change: PASS for focused AC evidence; BLOCKED for branch gate because full suite has unrelated and branch-local failures.

Verified by:

```text
tests/unit/test_task_identity_scoring.py .. [100%]
tests/unit/test_score_load.py ....... [100%]
```

Code inspection confirmed ordering only permutes `job_config.tasks`; task identity resolution in `src/razorback/runs/aggregate.py` remains keyed through task-view manifests and trial names, and the scoring invariance test compares task-keyed outcomes across default and reordered fixtures.

AC-5 - Provenance records the hint: PASS for focused AC evidence; BLOCKED for branch gate because full suite has branch-local unit failures in existing provenance/aggregation tests.

Verified by:

```text
tests/unit/test_rk_run_ordering_hint_cli.py ... [100%]
tests/unit/test_rk_run_v2_provenance_artifacts.py . [100%]
```

Code inspection confirmed `ordering_hint` metadata is written additively to `manifest.json` through `src/razorback/runs/aggregate.py` and to `provenance.yaml` through `src/razorback/provenance/provenance_yaml.py`.

## Code Review Findings

Blocking:

- Full `uv run pytest` does not pass on the worktree branch. Two unit failures are direct fallout from the implementation's new `ordering_hint` keyword and should be fixed before merge by updating existing test doubles or call contracts:
  `tests/unit/test_cli_run_aggregator_wiring.py:43`, `tests/unit/test_run_plugin_drift_wired.py:123`.

Non-blocking:

- The requested `superpowers:requesting-code-review` asset is not installed in this Codex session. I searched available skills/plugins for `superpowers`, `requesting-code-review`, and `code-review`; only Spacedock docs paths were present, not an executable skill. I performed a manual review of the required files instead.
- The full suite also has integration/environment failures unrelated to ordering hints: missing external DAB data under `/Users/clkao/git/dataagentbench/data/query_bookreview` and an empty `events.jsonl` assertion in `test_rk_run_nop_end_to_end`.

## Gate Decision

REJECTED.

The AC-specific focused tests and code inspection support the feature behavior, but the validation stage requires `uv run pytest` from a clean checkout. The branch currently leaves branch-local unit regressions in existing tests, so it should return to implementation for concrete fixes before advancing to `done`.
