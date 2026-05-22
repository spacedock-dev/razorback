# harbor-DAB batch query_mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to drive this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Entity:** `docs/razorback-implementation/harbor-dab-batch-query-mode.md`
(id `65edwgd257aem15f4fheazjv`).

**Goal.** Add `query_mode: {batch, per-query}` to the
`HarborDabBenchmarkBlock`. Under `batch`, harbor-DAB materializes ONE
task per dataset (`task_name = dataset`) whose workdir holds all
`queryN/query.json` siblings; the agent solves every query in a single
turn and writes a merged `answers.json` keyed by `qN`. The verifier runs
each upstream `validate.py` and emits a per-query verdict map; the
aggregator stratifies pass@1 per (dataset, query_id). `per-query`
(default) preserves today's shape.

## Upstream contract (DAB verbatim)

**run.sh:33** (`benchmark/run.sh`):

    --query-mode <mode>          Query dispatch shape: batch, per-query (default: batch)

**lib/benchctl.py:4322-4326** (interactive picker source-of-truth):

    elif key == "query_mode":
        options = ["batch", "per-query"]
        cur = state.get("query_mode", "batch")
        state["query_mode"] = pick_option(
            "Query mode", options,
            default_idx=options.index(cur) if cur in options else 0,
        )

**lib/run_experiment.py:651-657** (validator):

    def validate_query_mode(resolved):
        mode = getattr(resolved, "query_mode", None)
        if mode not in ("batch", "per-query"):
            raise ValueError(
                f"query_mode invalid choice: {mode!r} "
                ...
            )

**Workspace layout under batch** (verbatim from
`/Users/clkao/git/dataagentbench/benchmark/workspace-readmes/workspace-readme-direct-entity-output.md`
lines 41-45 and 84-85):

    |-- query1/query.json
    |-- query2/query.json
    |-- query3/query.json
    `-- answers.json

> "Write `answers.json` in the workspace root. Use each query directory
> name as the key. For a query in `query2/query.json`, write
> `{"q2": "answer"}`."

**Tests around 2713+** (`benchmark/tests/test_run_experiment.py:2713-2720`):

    def test_validate_query_mode_accepts_batch_and_per_query():
        run_experiment.validate_query_mode(argparse.Namespace(query_mode="batch"))
        run_experiment.validate_query_mode(argparse.Namespace(query_mode="per-query"))

    def test_validate_query_mode_rejects_legacy_fresh():
        with pytest.raises(ValueError, match="invalid choice"):
            run_experiment.validate_query_mode(argparse.Namespace(query_mode="fresh"))

We mirror the same `{batch, per-query}` literal set and the same
upstream-rejection shape (no `fresh` legacy in razorback; harbor-DAB has
never had a `fresh` mode to deprecate).

**Razorback default differs from DAB upstream.** Upstream defaults
`query_mode` to `batch`; razorback today materializes one harbor task
per (dataset, query) and that shape is shipped in PKG-13 / 14 / 15 / 16
/ 17 / 21 / 25. Per the entity's AC-1, this plan defaults `query_mode`
to `per-query` to preserve back-compat. The matrix-spec generator
(AC-5) opts into `batch` explicitly for Goal 1 RESUME.

## Code change points

### Schema — `src/razorback/spec/schema.py`

`HarborDabBenchmarkBlock` (lines 117-130) gets one new field:

    query_mode: Literal["batch", "per-query"] = "per-query"

It lands on the harbor-DAB block ONLY, not on `AdeBenchBenchmarkBlock`
(entity scope §"Out of scope") and not on `DabBenchmarkBlock` (legacy
in-tree path; PKG-22 marks it for retirement). The pydantic
`extra="forbid"` config already rejects anything off the literal set;
no separate `field_validator` is needed.

### Plugin generator — `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/prepare.py`

`prepare_dataset_tasks` (line 53) gains one kwarg with the same default:

    def prepare_dataset_tasks(
        ...,
        query_mode: str = "per-query",
        ...
    ) -> list[TaskManifestEntry]:

Under `query_mode == "per-query"` the existing per-query loop at line
107-137 stays verbatim — closes AC-3 by construction (no diff to the
running path).

Under `query_mode == "batch"` the loop is replaced by a single call to
a new sibling `_materialize_batch_task_dir`:

    def _materialize_batch_task_dir(
        *,
        task_name: str,                 # equals `dataset`
        dataset_dir: Path,
        query_dirs: list[Path],         # all queryN/ from dataset_dir
        task_dir: Path,
        workspace_variant: str,
        hints: bool,
        docker_image: str,
        container_workdir: str,
        db_config: dict,
        dataset_meta: catalog.DabDataset,
        materialize_mode: str,
        postgres_volume_mode: str,
    ) -> None: ...

Structural deltas vs per-query:

1. `task_name = dataset` (no `-q<id>` suffix). Manifest entry exposes a
   new field `query_ids: list[int]` (sorted, all queries for the
   dataset) instead of the single `query_id`. `query_id` is set to
   `None` for batch entries; the per-query `query_id: int` field stays
   for back-compat with `_legacy/compat/harbor_0_6_6.py`'s consumers.
   The TypedDict gains `total=False` and a new key.
2. **Instruction (workdir)** — `_instruction()` is replaced under batch
   by `_batch_instruction()`, which enumerates `query1`, `query2`, ...
   and references the merged answers.json shape. Verbatim contract per
   upstream's `workspace-readme-direct-entity-output.md` (the same
   source of truth our three variants already match).
3. **Workdir tree** — instead of copying `query_dir/query.json` to
   `workdir/query.json` (single file), the batch path creates
   `workdir/query1/query.json`, `workdir/query2/query.json`, etc.,
   mirroring upstream `prep_workspace`'s siblings layout
   (`benchmark/lib/run_experiment.py:1037-1045`):

       for qdir in sorted(dataset_dir.glob("query[0-9]*")):
           ...
           q_workspace = workspace / qname

4. **Tests dir** — `tests/validate.py` is replaced by
   `tests/validate_batch.py`, an aggregator that imports each upstream
   `query{N}/validate.py` (one per query) and exposes a single
   `validate(answers_json_text) -> tuple[bool, str]` plus a structured
   `validate_per_query(answers) -> dict[str, tuple[bool, str]]`. The
   per-query `validate.py` files are copied as `validate_q1.py`,
   `validate_q2.py`, etc., or — to keep the q1/q2/q3 substring-leak
   hardening from PKG-13 T14 — the existing `_hardened_template`
   selector runs per query and writes `validate_qN.py` with the
   hardened body wherever bookreview hits.
5. **stratum.json** — currently one stratum per (dataset, query). Under
   batch, the file holds `{"stratum": {"dataset": ..., "query_ids":
   [...], "backends": [...]}}` (list-shape `query_ids`, no scalar
   `query_id`). The stratum reader in
   `packages/razorback-plugin-dab/src/razorback_plugin_dab/generate/stratum.py`
   gains a `write_batch_stratum_file` sibling; consumers in
   `tests/unit/test_stratum_tagging.py` get a new fixture.
6. **test.sh** — currently calls `verify.py` against `answers.json`
   producing one reward (0.0 or 1.0). Under batch, the new `test.sh`
   calls a new `verify_batch.py` which:
   - reads `answers.json` from workdir
   - for each `query{N}` dir, invokes its `validate_q{N}.py` (or
     `_hardened_*.py`) against `answers[f"q{N}"]`
   - writes `/logs/verifier/reward.json` as the harbor-required scalar
     `{"reward": <mean>}` (mean of per-query rewards, in [0.0, 1.0])
   - writes `/logs/verifier/reward_per_query.json` as
     `{"q1": {"reward": 1.0, "reason": "..."}, "q2": {...}, ...}` — the
     batch sidecar consumed by the razorback-side aggregator.

   Mean-of-per-query for the scalar reward is the minimum viable
   summary; razorback's `aggregate_job_result` reads the sidecar map,
   not the scalar, so the scalar is informational only (and matches
   harbor's existing rewards shape).

### Plugin CLI — `packages/razorback-plugin-dab/src/razorback_plugin_dab/cli.py`

`generate` (line 23) gains one flag:

    query_mode: str = typer.Option(
        "per-query", "--query-mode",
        help="One of: batch, per-query (default: per-query). "
             "batch emits one task per dataset; per-query emits one per (dataset, query).",
    ),

Validated against `("batch", "per-query")` with the same exit-2 + stderr
shape as `--workspace-variant`. Forwarded into `prepare_dataset_tasks`.

### Razorback translator — `src/razorback/translate.py`

`_build_harbor_dab` (line 350) extends the subprocess invocation:

    cmd = [
        "uv", "run", "razorback-plugin-dab", "generate",
        ...,
        "--query-mode", spec.benchmark.query_mode,
    ]

The trial-name → (dataset, query_id) map handling (lines 391-401) needs
the batch branch:

- Per-query mode: unchanged. `bookreview-q1` → `("bookreview", 1)`.
- Batch mode: the emitted dir is `bookreview` (no `-q` suffix), and the
  single TaskConfig produces a single harbor trial. The aggregator
  needs to fan that trial out into N per-query outcomes.

  The translator emits `trial_name_map[task_name] = ("bookreview", [1,
  2, 3])` — i.e. the second element becomes `list[int]` under batch.
  Downstream (`aggregate_job_result`) is taught to handle the
  list-shape: for a batch trial, read
  `reward_per_query.json` from the trial's verifier outputs, map each
  `qN` to `(dataset, N)`, emit one outcome per query.

  Alternative considered: re-use the existing `tuple[str, int]` shape
  by emitting N entries, all keyed on the same `task_name`. Rejected
  because the existing `_resolve_key()` (aggregate.py:128-133) does a
  dict lookup and would collide. The list-shape is cleaner.

  `trial_name_map` type becomes `dict[str, tuple[str, int] | tuple[str,
  list[int]]]`. The legacy compat layer
  (`_legacy/compat/harbor_0_6_6.py`) is NOT changed — it serves DAB
  (kind=dab), not harbor_dab.

### Razorback aggregator — `src/razorback/benchmarks/dab/aggregate.py`

`aggregate_job_result` (line 83) is extended:

- Branch on `_resolve_key()` result shape.
- `tuple[str, int]` → unchanged single-outcome path.
- `tuple[str, list[int]]` → read the batch sidecar
  `reward_per_query.json` from the trial's verifier directory; emit
  one outcome per query_id with the matching reward.

The sidecar path is `JobResult.trial_results[i].verifier_result` →
`rewards` is the harbor scalar dict; the per-query map is exposed via a
new `VerifierResult.rewards_per_query` field if harbor's model supports
it, otherwise read from
`<trial_dir>/logs/verifier/reward_per_query.json` (the path
test_sh writes in §"Plugin generator" §6).

Reading from disk avoids a harbor-model change and is the same shape
harbor already uses for its own per-step reward.json — concrete path
verified during T5.

### Matrix-spec generator — `examples/drivers/generate-dab-paper-matrix-specs.py`

`build_spec()` (line 22) adds:

    "benchmark": {
        ...,
        "query_mode": "batch",
    },

Goal 1 RESUME's T1 re-runs this generator to regenerate the 36 frozen
specs.

## Test plan (TDD-ordered)

The captain's checklist names 5 ACs. The test-order below is the
"smallest end-to-end exercise of the riskiest path first" framing — the
RED tests go in the order their failures would invalidate downstream
work.

- [ ] **T0 — RED schema test (AC-1).** Add
  `tests/unit/test_spec_harbor_dab_block.py::test_harbor_dab_accepts_query_mode_batch_and_per_query`
  and `::test_harbor_dab_default_query_mode_is_per_query` and
  `::test_harbor_dab_rejects_unknown_query_mode`. The first two should
  GREEN once the literal field is added; the third should produce a
  `SpecError` (mirrors the existing
  `test_harbor_dab_rejects_unknown_workspace_variant` shape).

- [ ] **T1 — GREEN schema (AC-1).** Add `query_mode: Literal["batch",
  "per-query"] = "per-query"` to `HarborDabBenchmarkBlock`. Run the
  full `pytest tests/unit/test_spec_harbor_dab_block.py` suite.

- [ ] **T2 — RED batch materialize (AC-2).** Add
  `packages/razorback-plugin-dab/tests/unit/test_prepare_batch_query_mode.py`
  containing at minimum:

  - `test_batch_mode_emits_one_task_dir_per_dataset` — invokes
    `prepare_dataset_tasks(..., query_mode="batch")` against the
    synthetic 3-query bookreview fixture from
    `test_prepare_per_query.py::_build_synthetic_data_root` (extended
    to seed q1, q2, q3); asserts manifest has length 1, `task_name ==
    "bookreview"`, no `-q` suffix.
  - `test_batch_mode_workdir_has_three_query_subdirs` — asserts
    `workdir/query1/query.json`, `query2/query.json`, `query3/query.json`
    exist and that the **flat** `workdir/query.json` does NOT exist.
  - `test_batch_mode_instruction_enumerates_queries` — asserts the
    instruction.md and `steps/main/instruction.md` mention all three
    queries and the merged-answers contract (`"q1"`, `"q2"`, `"q3"`
    keys).
  - `test_batch_mode_tests_dir_has_per_query_validators` — asserts
    `tests/validate_q1.py`, `validate_q2.py`, `validate_q3.py` exist
    (bookreview's three hardened bodies) and `tests/verify_batch.py`
    is present.
  - `test_batch_mode_stratum_payload_uses_query_ids_list` — asserts
    `stratum.json` carries `"query_ids": [1, 2, 3]`, no scalar
    `query_id`.

- [ ] **T3 — GREEN batch materialize.** Implement
  `_materialize_batch_task_dir`, `_batch_instruction`,
  `write_batch_stratum_file`, plus the verifier sidecar files as
  described above. Pass T2.

- [ ] **T4 — RED verifier aggregation (AC-4).** Add
  `tests/unit/test_dab_aggregate_batch_query_mode.py`:

  - `test_aggregate_batch_trial_emits_per_query_outcomes` — synthetic
    fake `JobResult.trial_results` with one trial named `bookreview`
    and a fake `verifier_result` that points to a tmp_path containing
    `reward_per_query.json` = `{"q1": {"reward": 1.0}, "q2": {"reward":
    0.0}, "q3": {"reward": 1.0}}`. With `trial_name_map = {"bookreview":
    ("bookreview", [1, 2, 3])}`, asserts that the written
    `per_trial_outcomes.json` has THREE outcomes (q1=1.0, q2=0.0,
    q3=1.0), summary's `dataset_pass_at_1` = 2/3 = 0.667.
  - `test_aggregate_per_query_trial_unchanged` — keeps the existing
    `aggregate_job_result` regression green when the map carries
    `tuple[str, int]` entries.
  - `test_aggregate_batch_missing_sidecar_yields_zero_per_query` —
    when the sidecar file is absent, all per-query rewards default to
    0.0 with a reason; closes a regression class where the scalar
    `rewards` is honest 0.0 (verifier crashed) but the per-query map
    would otherwise be silently empty.

- [ ] **T5 — GREEN verifier aggregation.** Extend `aggregate_job_result`
  per §"Razorback aggregator". Pass T4.

  Also: extend `_build_harbor_dab` to emit list-shape map entries
  under batch (small RED-then-GREEN cycle inside T5 — add a unit
  `test_translator_harbor_dab_batch_emits_list_keyed_map` first; then
  ship). Confirms the translator-aggregator handshake.

- [ ] **T6 — Regenerate matrix specs (AC-5).** Add `query_mode: batch`
  to `build_spec()` in
  `examples/drivers/generate-dab-paper-matrix-specs.py`. Add a
  matching unit
  `tests/unit/test_generate_matrix_specs.py::test_matrix_specs_carry_query_mode_batch`
  that loads one emitted spec and asserts
  `spec["benchmark"]["query_mode"] == "batch"`. Re-run the generator
  to regenerate the 36 specs under `examples/specs/goal1/`.

  Per-query regression invariant (AC-3): all PKG-13/14/15/16/17/21/25
  test files keep their existing `prepare_dataset_tasks(...)` calls
  (default `query_mode="per-query"`) and stay GREEN. `uv run pytest
  packages/razorback-plugin-dab/` and `uv run pytest tests/unit/` are
  the gate; the suite must pass before T7.

- [ ] **T7 — Live `rk run` against bookreview batch-mode (AC-5
  acceptance).** Freeze one regenerated spec
  (`examples/specs/goal1/spacedock/bookreview.yaml`), run `rk run`
  with `--max-budget-usd-running` ≤ $0.50, and inspect the trial:

  - exactly ONE agent invocation (one `claude-cli` subprocess, one
    `events.jsonl`-recorded `agent_started` event)
  - workdir contains `query1/`, `query2/`, `query3/` plus a single
    `answers.json` with three keys
  - `reward_per_query.json` materializes with three entries
  - `per_trial_outcomes.json` has three rows, all keyed
    `("bookreview", 1|2|3)`
  - `rk score` against this run reports stratified per-query pass@1

  If the live run shows a different shape (e.g., the agent only
  answered one question), revisit T3's instruction template — that's
  the agent-facing contract.

## Out of scope (entity §"Out of scope" verbatim)

- Per-query mode deprecation. Stay supported indefinitely.
- ade-bench / Goal 2. Different adapter; sibling entity if needed.
- Spacedock workflow variants. Already covered by the workspace-
  readme variant selector.
- Verifier aggregation strategy beyond per-query reduction. AC-4
  intentionally keeps the per-query verdict map; downstream
  stratification is `rk score`'s job.

## Risks and mitigations

- **R1 — Verifier sidecar contract drift.** harbor's `VerifierResult`
  schema doesn't expose a `rewards_per_query` field today. Mitigation:
  read the sidecar from disk via the trial dir path. This is the same
  pattern PKG-15 uses for `.compose-services.json` (sidecar at a
  well-known path under the trial's verifier outputs).

  Cross-check during T3: confirm the harbor copy/mount step puts
  `/logs/verifier/reward_per_query.json` somewhere the razorback
  aggregator can find from the trial result's verifier directory.
  PKG-15's reachability gate has the same shape; the gate's sidecar
  lives at `environment/.compose-services.json` and is read by the
  validator successfully (see `test_prepare_bind_materialize.py`).

- **R2 — Stratum file shape break.** PKG-13's stratum tagger reads
  `query_id` (scalar). Mitigation: keep the per-query stratum
  generator unchanged; write a NEW `write_batch_stratum_file` that
  emits `query_ids: list[int]` and let downstream readers branch on
  the key. T2 has the regression assertion.

- **R3 — Bookreview q1/q2/q3 substring-leak hardening regresses.**
  PKG-13 T14 installed `_hardened_template` for bookreview-q1 (q1.py)
  and bookreview-q2/q3 (shared q2_q3.py). Under batch the hardening
  needs to fire once per query, not once for the dataset. Mitigation:
  T3 generates `validate_q{N}.py` from `_hardened_template(dataset,
  query_id)` per query, preserving the existing hardened bodies. T2
  asserts each `validate_qN.py` either matches the hardened template
  body byte-for-byte (for bookreview) or matches the upstream body
  (for all other datasets).

- **R4 — Spec-kind drift.** The entity scope says "Schema extension
  lands on the harbor-DAB benchmark block (not the generic ade_bench
  one)." Mitigation: the schema diff is explicitly local to
  `HarborDabBenchmarkBlock`. The pydantic `extra="forbid"` on
  `AdeBenchBenchmarkBlock` rejects any `query_mode` accidentally
  carried into an ade-bench spec; add an explicit negative test
  `tests/unit/test_ade_bench_translator_local_root.py::test_ade_bench_rejects_query_mode`
  in T1 alongside the schema GREEN.

## Resume hook (from entity §"Resume hook")

After this entity merges, Goal 1 RESUME's T1 regenerates frozen specs
with `query_mode: batch`. The matrix dispatches as 36 cells of
batch-mode (vs the prior 36×3 per-query invocations). Per-variant
comparison becomes load-bearing — variants now differ by agent
ARCHITECTURE (spacedock_solver_v2 vs claude-cli-as-ClaudeCode-subclass
per the per-variant-kinds entity) AND by task SHAPE (batch agent turn
per dataset).
