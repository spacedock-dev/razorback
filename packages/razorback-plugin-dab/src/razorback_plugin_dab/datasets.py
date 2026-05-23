# ABOUTME: DAB dataset catalog — thin loader over dataset.toml (the Harbor-style def).
# ABOUTME: Preserves DabDataset dataclass + by_name() for legacy callers.

from __future__ import annotations

from dataclasses import dataclass

from razorback_plugin_dab.dataset_def import load_default_definition


@dataclass(frozen=True)
class DabDataset:
    name: str
    backends: tuple[str, ...]
    query_count: int
    schema_version: str = "v1"


def _build_catalog() -> tuple[DabDataset, ...]:
    definition = load_default_definition()
    return tuple(
        DabDataset(
            name=d.name,
            backends=d.backends,
            query_count=d.query_count,
            schema_version=d.schema_version,
        )
        for d in definition.datasets
    )


DAB_DATASETS: tuple[DabDataset, ...] = _build_catalog()


def by_name(name: str) -> DabDataset:
    for d in DAB_DATASETS:
        if d.name == name:
            return d
    raise KeyError(f"unknown DAB dataset: {name!r}")
