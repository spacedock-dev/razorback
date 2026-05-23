# ADE-Bench Harbor Dataset-Ref Probe (T0 evidence)

Probe performed 2026-05-22 against Harbor 0.6.6 against the live registry
(no API keys configured beyond what `harbor.db.client.create_authenticated_client`
picks up from the environment). The riskiest contract for the dataset-ref
implementation is "does Harbor expose `ade-bench` as a published dataset whose
export layout PKG-40's materializer accepts unchanged?" This note records the
T0 answer and the deviations from the plan that the implementation must absorb.

## Confirmed surfaces

- `harbor.tasks.client.TaskClient.download_tasks` exists with signature
  `(self, task_ids: list[GitTaskId | LocalTaskId | PackageTaskId], overwrite=False, output_dir=None, export=False, on_task_download_start=None, on_task_download_complete=None) -> BatchDownloadResult`.
- `harbor.models.task.id.PackageTaskId` has `(org: str, name: str, ref: str | None = None)`.
- `BatchDownloadResult.results: list[TaskDownloadResult]` where
  `TaskDownloadResult(path: Path, download_time_sec: float, cached: bool, content_hash: str | None = None, resolved_git_commit_id: str | None = None)`.
- `harbor.registry.client.PackageDatasetClient.download_dataset(name, overwrite=False, output_dir=None, export=False, ...) -> list[DownloadedDatasetItem]` where each item is `(id: PackageTaskId, downloaded_path: Path)`.
- `PackageDatasetClient.get_dataset_metadata(name) -> DatasetMetadata` carries
  `task_ids: list[PackageTaskId]`, `dataset_version_content_hash: str | None`,
  `dataset_version_id: str | None`, `files: list[DatasetFileInfo]`.

## Live invocation (2026-05-22)

`PackageDatasetClient().download_dataset("dbt-labs/ade-bench@latest", output_dir=..., export=True)` returned 48 items in roughly the time it takes to fan 48 task downloads through `TaskClient`. Each `downloaded_path` resolves to `<output_dir>/<task-package-name>/` and contains a Harbor-shaped task layout:

```
<output_dir>/ade-bench-airbnb001/
  task.toml
  instruction.md
  environment/{Dockerfile, setup.sh, AGENTS.md, ...}
  tests/{test.sh, test-setup.sh, AUTO_*.sql, ...}
  solution/{setup.sh, solve.sh, solution.sh}
```

`solution/**` IS exported into the task directory, so the existing
`ADE_BENCH_DENY_GLOBS` exclusion path in `materialize_ade_harbor_task_view`
must continue to apply on the dataset-ref path (no behavior change).

Total dataset size: ~49 MB.

## Deviations from the plan

The plan in `docs/razorback-implementation/plans/ade-bench-harbor-dataset-ref.md`
encoded assumptions that the live probe contradicts. These are the contract
surprises T0 was designed to catch before T1+ committed code to them.

1. **Org name.** Plan assumed `harbor/ade-bench`. Actual: published under `dbt-labs/ade-bench`. Calling `TaskClient.download_tasks([PackageTaskId(org="harbor", name="ade-bench", ref="1.0")])` directly fails with `postgrest APIError PGRST116 - 0 rows` because `ade-bench` is a **dataset** package (`package.type = "dataset"`), not a task package.

2. **Available refs.** Plan assumed `@1.0`. Actual: the only published version of `dbt-labs/ade-bench` is revision 1, tagged `latest`. There is no `1.0` tag. Refs that resolve today: `latest`, `1` (revision number), and the digest `sha256:2c1f9e6966d01b0a5de2235d1a0b64089c7eead42c85c3b7b61d0929405c2bd5`.

3. **API entry point.** Plan called `TaskClient.download_tasks([PackageTaskId(...)])` directly. Actual entry point for a published dataset is `PackageDatasetClient.download_dataset(name, output_dir=..., export=True)`, which internally resolves the dataset to a list of per-task `PackageTaskId(ref="sha256:...")` entries and then calls `TaskClient.download_tasks(...)` on them. Razorback's resolver should call the dataset client, not the task client, when consuming a dataset ref.

4. **Task slug shape.** Plan assumed bare task slugs (`airbnb001`, `airbnb002`). Actual: each task package carries the dataset prefix in its name — the 48 packages are named `ade-bench-airbnb001`, `ade-bench-airbnb002`, ..., `ade-bench-quickbooks003`, ..., `ade-bench-f1006-hard`, etc. The exported subdirectory under `output_dir` is named after the task package, not a stripped slug. The spec convention for `tasks: [airbnb001]` therefore needs a documented suffix-match (strip the `ade-bench-` prefix from the per-task package name when comparing to spec entries), and a clear error when the suffix isn't unique.

5. **Export layout.** Plan assumed `<output_dir>/ade-bench/<task-slug>/task.toml`. Actual: `<output_dir>/<task-package-name>/task.toml` — a flat directory directly under `output_dir`, with no intermediate dataset-name folder. The dataset client does not nest by package org or dataset name; the per-task package name is the directory.

## Content-hash shape

Both per-task and dataset-level hashes are available:

- **Per-task:** `PackageTaskId.ref` (and `TaskDownloadResult.content_hash`) is `"sha256:<64-hex>"` for each of the 48 tasks. Distinct per task.
- **Dataset-level:** `DatasetMetadata.dataset_version_content_hash = "2c1f9e6966d01b0a5de2235d1a0b64089c7eead42c85c3b7b61d0929405c2bd5"` (one value per dataset version; same value across all tasks). This is the AC-2 "dataset version" pin.

A manifest that records `dataset_ref` + `dataset_content_hash` satisfies the entity's AC-2 phrasing. Recording the per-task `task_content_hash` as well lets a frozen spec reproduce the exact same task body, not just the dataset version that contained it. The implementation captures both.

## Files written by T0

The downloaded probe data lives at `runs/ade-bench-dataset-ref-probe/` (gitignored under `runs/`). Clean up with `rm -rf runs/ade-bench-dataset-ref-probe`. `git submodule status` is empty before and after the probe — no new submodule was added (AC-5 baseline holds).

## Implications for T1+

The plan needs adjustment before T1+ implementation lands:

- Schema: `dataset:` accepts `<org>/<name>@<ref>` only (no default org), and the canonical example spec uses `dataset: dbt-labs/ade-bench@latest`.
- Resolver: calls `PackageDatasetClient.download_dataset(...)` (not `TaskClient.download_tasks([PackageTaskId(...)])`); each result's `.downloaded_path` becomes the resolved task source dir; `.id.ref` becomes the per-task `content_hash`.
- Resolver subset matching: spec `tasks: [airbnb001]` matches the unique resolved task whose package name ends with `-airbnb001`. Reject ambiguous suffixes; reject misses with a SpecError naming the dataset ref and the unmatched suffix.
- Manifest: bump `TASK_VIEW_MANIFEST_SCHEMA_VERSION` to 2; add `dataset_ref`, `dataset_content_hash`, and `task_content_hash` (per-task) as optional fields.
- Examples: ship `dataset: dbt-labs/ade-bench@latest` in `examples/specs/ade-bench-harbor-dataset-codex.yaml`. Mark every `tasks_root: .../ade-bench` example as fixture/dev only.

These adjustments preserve AC-1..AC-5 — only the specific dataset-ref string and the API entry point change. The PKG-40 materializer call shape is untouched.
