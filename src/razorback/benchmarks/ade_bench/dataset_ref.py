# ABOUTME: Parses ade-bench dataset refs and resolves them via Harbor's PackageDatasetClient.
# ABOUTME: Returns ResolvedDatasetTask records feeding the PKG-40 materializer; no API replacement.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harbor.models.package.reference import PackageReference
from harbor.registry.client import PackageDatasetClient

from razorback.benchmarks.ade_bench.tasks import _run_async
from razorback.errors import SpecError


_CANONICAL_EXAMPLE = "dbt-labs/ade-bench@latest"
_REF_SHAPE = "<org>/<name>@<ref>"


@dataclass(frozen=True)
class ResolvedDatasetTask:
    """A single task resolved out of a Harbor dataset version.

    `path` is the local directory Harbor exported (the materializer source).
    `task_slug` is the per-task Harbor package name (e.g. `ade-bench-airbnb001`).
    `requested_slug` is the spec-side identifier the operator wrote
    (e.g. `airbnb001`) — when the spec asks for all tasks, this matches
    `task_slug` with the dataset prefix stripped.
    `content_hash` is the per-task sha256 from `PackageTaskId.ref`.
    `dataset_content_hash` is the dataset-version sha256 shared by all tasks.
    """

    path: Path
    task_slug: str
    requested_slug: str
    content_hash: str | None
    dataset_content_hash: str | None


def parse_dataset_ref(ref: str) -> tuple[str, str, str]:
    """Parse a Harbor dataset ref `<org>/<name>@<ref>` into its components.

    Validation delegates to `harbor.models.package.reference.PackageReference.parse`,
    accepting all three ref tiers Harbor supports:

    - `@<tag>` (mutable label, e.g. `latest`)
    - `@<rev_number>` (immutable revision, e.g. `1`)
    - `@sha256:<digest>` (content-addressed paper-grade pin)

    Bare names (no `<org>/` or no `@<ref>`), or anything `PackageReference.parse`
    rejects, raise `SpecError` whose message names BOTH the required shape AND
    a working canonical example (captain's AC-1 guardrail: bad input -> good guidance).
    """
    if not isinstance(ref, str) or "/" not in ref or "@" not in ref:
        raise SpecError(
            f"invalid Harbor dataset ref {ref!r}: "
            f"required shape is {_REF_SHAPE} "
            f"(e.g. {_CANONICAL_EXAMPLE!r})"
        )
    try:
        parsed = PackageReference.parse(ref)
    except Exception as exc:
        raise SpecError(
            f"invalid Harbor dataset ref {ref!r}: "
            f"required shape is {_REF_SHAPE} "
            f"(e.g. {_CANONICAL_EXAMPLE!r}); "
            f"Harbor parser rejected it: {exc}"
        ) from exc
    if not parsed.org or not parsed.short_name or not parsed.ref:
        raise SpecError(
            f"invalid Harbor dataset ref {ref!r}: "
            f"required shape is {_REF_SHAPE} "
            f"(e.g. {_CANONICAL_EXAMPLE!r})"
        )
    return parsed.org, parsed.short_name, parsed.ref


def _strip_dataset_prefix(task_slug: str, dataset_name: str) -> str:
    """Strip the `<dataset_name>-` prefix from a per-task package name.

    Harbor names per-task packages like `ade-bench-airbnb001` inside the
    `ade-bench` dataset. The spec-side identifier `airbnb001` is the suffix.
    Falls back to the package name itself when the prefix is absent.
    """
    prefix = f"{dataset_name}-"
    return task_slug[len(prefix):] if task_slug.startswith(prefix) else task_slug


def resolve_dataset_tasks(
    *,
    dataset_ref: str,
    tasks: list[str] | None,
    cache_root: Path,
) -> list[ResolvedDatasetTask]:
    """Resolve a Harbor dataset ref into local task directories.

    Calls `PackageDatasetClient.download_dataset` (the dataset-package entry
    point), which internally resolves the dataset version, enumerates its
    member task packages, and fans them through `TaskClient.download_tasks`.
    Each returned task carries its own per-task `content_hash` (from
    `PackageTaskId.ref`); the dataset-level hash is fetched from
    `get_dataset_metadata` so both hashes can be pinned in `view_manifest.json`.

    If `tasks` is `None`, all dataset members are returned. Otherwise, each
    spec-side slug is matched against a unique per-task package whose name
    ends with `-<slug>` (after stripping the dataset prefix). Misses raise
    `SpecError` listing what IS available so the operator can self-correct.

    Resolver exceptions (network, registry, postgrest) are wrapped in
    `SpecError` naming both the dataset ref and the underlying cause so
    `rk freeze`'s SPEC_ERROR exit code is correct (AC-5 — clear setup errors).
    """
    _, dataset_name, _ = parse_dataset_ref(dataset_ref)

    cache_root = Path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)

    client = PackageDatasetClient()
    try:
        metadata = _run_async(client.get_dataset_metadata(dataset_ref))
        items = _run_async(
            client.download_dataset(
                dataset_ref,
                overwrite=False,
                output_dir=cache_root,
                export=True,
            )
        )
    except SpecError:
        raise
    except BaseException as exc:
        raise SpecError(
            f"failed to resolve dataset {dataset_ref!r}: {exc}"
        ) from exc

    dataset_content_hash = metadata.dataset_version_content_hash

    by_slug: dict[str, ResolvedDatasetTask] = {}
    for item in items:
        per_task_hash = item.id.ref  # already shape "sha256:..."
        task_slug = item.id.name
        requested_slug = _strip_dataset_prefix(task_slug, dataset_name)
        by_slug[requested_slug] = ResolvedDatasetTask(
            path=Path(item.downloaded_path).resolve(),
            task_slug=task_slug,
            requested_slug=requested_slug,
            content_hash=per_task_hash,
            dataset_content_hash=dataset_content_hash,
        )

    if tasks is None:
        return list(by_slug.values())

    selected: list[ResolvedDatasetTask] = []
    missing: list[str] = []
    for requested in tasks:
        if requested in by_slug:
            selected.append(by_slug[requested])
        else:
            missing.append(requested)

    if missing:
        available = sorted(by_slug.keys())
        raise SpecError(
            f"dataset {dataset_ref!r}: requested task(s) {missing!r} not found. "
            f"Available task slugs ({len(available)}): {available!r}"
        )

    return selected
