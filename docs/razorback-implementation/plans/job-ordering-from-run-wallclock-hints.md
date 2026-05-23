# Historical Wallclock Ordering Hints for Job Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for implementation tracking.

**Goal:** `rk run` can optionally use a previous run artifact or run directory as a scheduling hint, extracting per-task wallclock durations and dispatching longest-known tasks first while preserving default behavior, task identity, scoring, and provenance semantics.

**Architecture:** Add a small ordering module that parses historical Harbor/Razorback run artifacts into `{task_key: seconds}` and applies a stable longest-known-first sort to `JobConfig.tasks` after `spec_to_job_config()` returns and before `_job_config.yaml` is written. The CLI owns the user-facing option and run metadata. The translator remains responsible for constructing benchmark task lists and task-view manifests; ordering is a post-translation list permutation so Harbor receives ordinary `TaskConfig(path=...)` entries. This matches the installed Harbor constraint: no wallclock or priority scheduling hook is available, so Razorback must reorder tasks before passing them to Harbor.

**Tech Stack:** Python 3.12, Typer, Pydantic/Harbor model objects already in use, pytest, JSON/YAML standard parsing. No new runtime dependencies.

---

## AC to Task Map

| AC | Governing spec cites | Tasks | Focused verification |
| --- | --- | --- | --- |
| AC-1 - Optional ordering hint input | v2 spec §3.1 CLI stability/path canonicalization; §3.2 `rk run`; §8.1 run wrapper | T3, T4, T5 | CLI/spec tests cover no hint preserving order and `--order-from-run <path>` changing order only when timing exists. |
| AC-2 - Wallclock extraction is robust | v2 spec §7.1 run-dir contract; §8.1 post-harbor run-dir artifacts; entity fixture path | T1, T2 | Parser fixture tests cover complete timings, missing fields, malformed timestamps, and partial coverage with warnings. |
| AC-3 - Longest-known-first scheduling | v2 spec §6.1 benchmark-block translation to `JobConfig.tasks`; §8.1 `rk run` before Harbor invocation | T3, T5 | Unit and smallest CLI mechanism tests assert `JobConfig.tasks` order is known-duration descending, unknowns in original relative order. |
| AC-4 - Results semantics do not change | v2 spec §6.3 trial semantics; §8.3a score loader; §7.1 run-dir artifacts | T6, T8 | Scoring and aggregation fixture tests prove `benchmark_task_id`, task ids, and task-keyed output shape are invariant under reordering. |
| AC-5 - Provenance records the hint | v2 spec §3.3 provenance freeze stability; §7.3 additive stability; §8.1 provenance artifacts | T4, T7 | Run manifest/provenance test asserts hint path, ordering mode, usable timing count, total tasks, and ignored timing count are recorded. |

---

## Planned Code Surfaces

| File | Responsibility | Planned action |
| --- | --- | --- |
| `src/razorback/run_ordering.py` | Historical timing parser and stable task reorder helper | Create. Parse run dirs or explicit result files, derive task keys from per-trial `result.json`, compute elapsed seconds, warn on unusable data, and reorder `TaskConfig` lists. |
| `src/razorback/cli/run.py` | CLI option, call site before Harbor `_job_config.yaml`, run metadata | Modify. Add `--order-from-run PATH`; after `spec_to_job_config(...)`, call ordering helper before `job_config_yaml.write_text(...)`; pass ordering summary into provenance/aggregation metadata. |
| `src/razorback/runs/aggregate.py` | Manifest writer | Modify. Add optional `ordering_hint` block to `manifest.json` without changing existing required fields. |
| `src/razorback/provenance/provenance_yaml.py` | Run provenance writer | Modify to allow an additive `ordering_hint` block in run-dir `provenance.yaml`, or write it via `cli/run.py` by extending the provenance payload before calling `write_provenance_yaml`. |
| `src/razorback/translate.py` | Task identity source, not the ordering owner | No direct sort here unless implementation needs a helper to compute task keys from task-view manifests. Keep benchmark-specific task construction unchanged. |
| `tests/unit/test_run_ordering.py` | Parser and sort unit tests | Create. |
| `tests/unit/test_rk_run_ordering_hint_cli.py` | CLI wiring and `_job_config.yaml` order tests | Create. |
| `tests/unit/test_task_identity_scoring.py` | Existing task identity invariance tests | Extend if needed for reordered task-view manifests and per-trial outcomes. |
| `tests/unit/test_runs_aggregate.py` or `tests/unit/test_rk_run_v2_provenance_artifacts.py` | Manifest/provenance shape tests | Extend with ordering metadata assertions. |
| `tests/fixtures/run_ordering/` | Minimal historical timing fixtures | Create small synthetic fixtures; optionally add a script/comment for sampling from the ADE full run root. |

**Real fixture/example input:** `/home/exedev/.local/share/razorback/runs/ade-haiku-full-20260523T0005Z/run/ade-haiku-direct-full/ca04e5e7155ef10b` has a top-level `result.json` with `started_at`/`finished_at` and 48 per-trial result files with `task_id`, `task_name`, `trial_name`, `started_at`, and `finished_at`. Use it during implementation as a manual compatibility check; keep committed tests synthetic and small.

---

## Ordering Contract

- Default `rk run` behavior stays unchanged when `--order-from-run` is absent.
- The hint source accepts either a run directory or a JSON result artifact path. Directory mode walks immediate child trial dirs containing `result.json`; result-file mode parses a single JSON file if it contains trial-like records, otherwise reports no usable per-task timings.
- Per-trial elapsed wallclock is `finished_at - started_at` from ISO timestamps. Timestamp parse failures, missing fields, negative/zero elapsed durations, and records without a stable task key are ignored with `typer.echo("warning: ...", err=True)`.
- Task key matching should prefer benchmark-stable identity from Razorback task-view manifests: `benchmark_task_id` when available, then Harbor `task_name`, then local task path basename. Do not key on the random trial suffix after `__`.
- Sorting policy: tasks with known timing sort before unknown tasks by descending elapsed seconds. Ties preserve original relative order. Unknown tasks preserve original relative order after all known tasks.
- If a prior run has repeated trials for the same task, use the maximum elapsed duration for scheduling. This is conservative for tail reduction and deterministic.

---

## Mechanism Validation First

**Riskiest contract:** matching historical timing data back to the new run's `TaskConfig` objects without changing task identity or relying on Harbor internals. A bad key would silently reorder the wrong tasks and corrupt tail scheduling claims.

**Smallest end-to-end mechanism:** T5 uses `CliRunner`, patches `_invoke_harbor`, and inspects the serialized `_job_config.yaml` from a tiny local spec with three task dirs and a historical fixture. This validates the actual `rk run -> spec_to_job_config -> ordering -> _job_config.yaml` path before any live Harbor or comprehensive benchmark run.

---

## Tasks

### Task 1: Historical Result Parser RED Tests

**ACs:** AC-2  
**Spec cites:** §7.1 run-dir contract; §8.1 run wrapper artifacts.

**Files:**
- Create: `tests/unit/test_run_ordering.py`
- Create: `tests/fixtures/run_ordering/complete_run/`
- Create: `tests/fixtures/run_ordering/partial_run/`

- [ ] **Step 1: Add fixture builders or committed minimal JSON fixtures.**
  Include per-trial result files with:
  - `task_id: {"path": ".../_razorback/task_views/task-a"}`
  - `task_name`
  - `trial_name: "task-a__abc123"`
  - `started_at` and `finished_at`
  Add one fixture with missing `finished_at`, one with malformed `started_at`, and one unknown task not present in the current run.

- [ ] **Step 2: Write red tests for parser output.**
  Test a future `load_wallclock_hints(path)` returns a summary containing:
  - `durations_by_task_key["task-a"] == 120.0`
  - repeated task rows use the max elapsed duration;
  - invalid/missing rows are ignored;
  - warnings include clear text naming the skipped file and missing/malformed field.

- [ ] **Step 3: Run red tests.**
  ```bash
  uv run pytest tests/unit/test_run_ordering.py -v
  ```
  Expected: import failure for `razorback.run_ordering`.

### Task 2: Implement Historical Wallclock Extraction

**ACs:** AC-2  
**Spec cites:** §7.1 run-dir contract; §8.1 run wrapper artifacts.

**Files:**
- Create: `src/razorback/run_ordering.py`

- [ ] **Step 1: Implement parser dataclasses.**
  Add `OrderingHintSummary` with fields: `source_path`, `mode`, `durations_by_task_key`, `usable_timing_count`, `ignored_timing_count`, `warnings`.

- [ ] **Step 2: Implement result discovery.**
  Directory mode should ignore top-level non-trial artifacts (`result.json`, `manifest.json`, `summary.json`, `_razorback`, `tasks`, etc.) and read only child `result.json` files. Single-file mode should parse that file and, if no per-trial rows are discoverable, return zero usable timings with a warning.

- [ ] **Step 3: Implement task-key extraction.**
  Prefer `task_name`; else derive from `task_id.path` basename; else strip `trial_name` at `__`. Keep this helper private but covered through tests.

- [ ] **Step 4: Run parser tests.**
  ```bash
  uv run pytest tests/unit/test_run_ordering.py -v
  ```
  Expected: parser tests pass.

- [ ] **Step 5: Manual compatibility probe against the ADE full run.**
  ```bash
  uv run python - <<'PY'
  from pathlib import Path
  from razorback.run_ordering import load_wallclock_hints
  root = Path("/home/exedev/.local/share/razorback/runs/ade-haiku-full-20260523T0005Z/run/ade-haiku-direct-full/ca04e5e7155ef10b")
  summary = load_wallclock_hints(root)
  print(summary.usable_timing_count, summary.ignored_timing_count)
  print(sorted(summary.durations_by_task_key.items(), key=lambda kv: kv[1], reverse=True)[:5])
  PY
  ```
  Expected: nonzero usable timings, ideally 48 usable rows for the provided fixture root.

### Task 3: Stable Longest-Known-First Sort

**ACs:** AC-1, AC-3, AC-4  
**Spec cites:** §6.1 benchmark-block translation to `JobConfig.tasks`; §6.3 trial/task semantics.

**Files:**
- Modify: `src/razorback/run_ordering.py`
- Extend: `tests/unit/test_run_ordering.py`

- [ ] **Step 1: Write red unit tests for ordering.**
  Build fake `TaskConfig(path=...)` objects for tasks `a`, `b`, `c`, `d`. Assert durations `b=30`, `d=90` produce order `d, b, a, c`; unknown `a,c` retain their original relative order.

- [ ] **Step 2: Add tie-policy tests.**
  Equal known durations preserve original relative order. With an empty summary, output order is byte-for-byte unchanged.

- [ ] **Step 3: Implement `apply_wallclock_ordering(tasks, summary)`.**
  Return `(ordered_tasks, metadata)` rather than mutating hidden state. Metadata should include `mode: "longest-known-first"`, `source_path`, `usable_timing_count`, `matched_task_count`, `unmatched_task_count`, and `ignored_timing_count`.

- [ ] **Step 4: Run unit tests.**
  ```bash
  uv run pytest tests/unit/test_run_ordering.py -v
  ```

### Task 4: CLI Option and Run Metadata Plumbing

**ACs:** AC-1, AC-5  
**Spec cites:** §3.1 CLI stability/path canonicalization; §3.2 `rk run`; §3.3/§7.3 additive provenance stability; §8.1 run wrapper.

**Files:**
- Modify: `src/razorback/cli/run.py`
- Modify: `src/razorback/runs/aggregate.py`
- Modify: `src/razorback/provenance/provenance_yaml.py` if needed
- Create: `tests/unit/test_rk_run_ordering_hint_cli.py`

- [ ] **Step 1: Write red CLI tests.**
  Patch `_run_canary`, `_resolve_model_version`, and `_invoke_harbor`. Run a tiny local spec with no hint and assert `_job_config.yaml` task order matches input. Run again with `--order-from-run <fixture>` and assert the serialized task order changes.

- [ ] **Step 2: Add Typer option.**
  In `run_command`, add:
  ```python
  order_from_run: Optional[Path] = typer.Option(
      None,
      "--order-from-run",
      help="Previous run directory or result artifact used as wallclock ordering hint.",
  )
  ```

- [ ] **Step 3: Apply ordering before Harbor serialization.**
  After `spec_to_job_config(...)` and before the env templating loop / `_job_config.yaml` write, load hints if present and replace `job_config.tasks` with the ordered list using the existing Harbor model API.

- [ ] **Step 4: Emit warnings.**
  Print parser warnings to stderr. If the hint path exists but yields zero usable timings, continue with default order and warn clearly.

- [ ] **Step 5: Thread metadata.**
  Keep an `ordering_hint_metadata` dict set to `None` by default. When a hint is provided, include source path, mode, usable timing count, matched task count, unmatched task count, and ignored timing count.

### Task 5: Smallest End-to-End Queue Mechanism Test

**ACs:** AC-1, AC-3  
**Spec cites:** §8.1 `rk run` before Harbor invocation; §6.1 task translation.

**Files:**
- Extend: `tests/unit/test_rk_run_ordering_hint_cli.py`

- [ ] **Step 1: Add a three-task local spec fixture.**
  Create task dirs under `tmp_path` and write a frozen local spec with `benchmark.kind: local`, `task_paths: [short, unknown, long]`, and `concurrency.trials: 2`.

- [ ] **Step 2: Add a historical run fixture.**
  Historical per-trial timings should make `long` slower than `short`; omit timing for `unknown`.

- [ ] **Step 3: Assert Harbor receives the sorted order.**
  Patch `_invoke_harbor` and inspect `run_dir / "_job_config.yaml"` after CLI completion. Assert task paths are `[long, short, unknown]` and `n_concurrent_trials == 2`.

- [ ] **Step 4: Run targeted tests.**
  ```bash
  uv run pytest tests/unit/test_rk_run_ordering_hint_cli.py tests/unit/test_run_ordering.py -v
  ```

### Task 6: Task Identity and Scoring Invariance

**ACs:** AC-4  
**Spec cites:** §6.3 trial semantics; §8.3a `rk score`; §7.1 run-dir contract.

**Files:**
- Extend: `tests/unit/test_task_identity_scoring.py`
- Possibly extend: `tests/unit/test_score_load.py`

- [ ] **Step 1: Write a reordered-run fixture test.**
  Build two synthetic run dirs with the same trial result rows and task-view manifests but different directory creation/order. Assert `aggregate_summary`, `write_per_trial_outcomes`, and `load_run_dir` produce the same task-keyed identities and score shape.

- [ ] **Step 2: Assert no scoring dependency on dispatch order.**
  Compare the sets of `(benchmark_kind, benchmark_task_id, reward)` from `per_trial_outcomes.json`. They must match exactly across ordered and default fixtures.

- [ ] **Step 3: Run scoring/identity tests.**
  ```bash
  uv run pytest tests/unit/test_task_identity_scoring.py tests/unit/test_score_load.py -v
  ```

### Task 7: Provenance and Manifest Recording

**ACs:** AC-5  
**Spec cites:** §3.3 provenance freeze format stability; §7.3 additive stability; §8.1 run-dir artifacts.

**Files:**
- Modify: `src/razorback/cli/run.py`
- Modify: `src/razorback/runs/aggregate.py`
- Modify: `src/razorback/provenance/provenance_yaml.py` if T4 did not already cover it
- Extend: `tests/unit/test_rk_run_ordering_hint_cli.py`
- Extend: `tests/unit/test_rk_run_v2_provenance_artifacts.py`

- [ ] **Step 1: Add red metadata assertions.**
  A hinted run should write `manifest.json` and `provenance.yaml` fields like:
  ```yaml
  ordering_hint:
    mode: longest-known-first
    source_path: /abs/or/user/path
    usable_timing_count: 2
    matched_task_count: 2
    unmatched_task_count: 1
    ignored_timing_count: 0
  ```
  No-hint runs should either omit `ordering_hint` or set it to `null`; choose one and document it in the test.

- [ ] **Step 2: Implement additive manifest support.**
  Add an optional `ordering_hint` argument to `write_manifest(...)` / `aggregate_run_dir(...)` / `safe_aggregate_run_dir(...)` and include it in `manifest.json`.

- [ ] **Step 3: Implement additive provenance support.**
  Extend `_write_provenance_artifacts(...)` to merge ordering metadata into the run-dir `provenance.yaml` payload. Do not change frozen spec bytes; `spec.frozen.yaml` must remain byte-for-byte equal to input.

- [ ] **Step 4: Run provenance tests.**
  ```bash
  uv run pytest tests/unit/test_rk_run_v2_provenance_artifacts.py tests/unit/test_rk_run_ordering_hint_cli.py -v
  ```

### Task 8: Regression and Acceptance Verification

**ACs:** AC-1 through AC-5  
**Spec cites:** §3.2 command surface; §6.1 task translation; §7.1 run-dir contract; §8.1 run wrapper; §8.3a score.

**Files:** No new planned implementation files.

- [ ] **Step 1: Run focused unit suite.**
  ```bash
  uv run pytest \
    tests/unit/test_run_ordering.py \
    tests/unit/test_rk_run_ordering_hint_cli.py \
    tests/unit/test_rk_run_v2_provenance_artifacts.py \
    tests/unit/test_task_identity_scoring.py \
    tests/unit/test_score_load.py \
    -v
  ```

- [ ] **Step 2: Run related translator and aggregator tests.**
  ```bash
  uv run pytest \
    tests/unit/test_ade_bench_translator.py \
    tests/unit/test_ade_bench_harbor_view.py \
    tests/unit/test_translate_harbor_task_batches.py \
    tests/unit/test_runs_aggregate.py \
    -v
  ```

- [ ] **Step 3: Optional manual ADE fixture validation.**
  Use the ADE full run root from the assignment as `--order-from-run` against a dry/paused CLI test or helper script to print top matched tasks. Do not run a full cost-bearing benchmark unless explicitly approved.

- [ ] **Step 4: Final default-order compatibility check.**
  ```bash
  uv run pytest tests/unit/test_rk_run_v2_provenance_artifacts.py tests/unit/test_rk_run_v2_pre_checks.py -v
  ```

---

## Risks and Guardrails

- **Default-order compatibility:** The hint option must be opt-in. No-hint runs must preserve current `spec_to_job_config` task order and existing `_job_config.yaml` shape.
- **Task identity/scoring invariance:** Reordering must only permute `JobConfig.tasks`; it must not rename task directories, alter task-view manifests, rewrite `benchmark_task_id`, change `trial_name` parsing expectations, or affect `rk score` grouping.
- **Partial or missing historical timing data:** Missing and malformed rows are expected. The deterministic policy is known tasks first by descending max duration, unknown tasks after them in original order, with warnings and metadata counts.
- **Path and privacy:** Provenance should record the hint path needed for reproducibility. Preserve the user-provided path or normalized absolute path consistently; do not copy historical result contents into provenance.
- **Harbor compatibility:** Do not patch Harbor internals or depend on undocumented scheduler hooks. The only Harbor-facing change is the order of the already-supported `tasks` list.
