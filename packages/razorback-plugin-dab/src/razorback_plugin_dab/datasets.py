# ABOUTME: Catalog of the 12 upstream DAB datasets — name, backend kinds, query count.
# ABOUTME: Source of truth: /Users/clkao/git/dataagentbench/data/query_<name>/db_config.yaml.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DabDataset:
    name: str
    backends: tuple[str, ...]
    query_count: int


DAB_DATASETS: tuple[DabDataset, ...] = (
    DabDataset(name="agnews", backends=("mongo", "sqlite"), query_count=4),
    DabDataset(name="bookreview", backends=("postgres", "sqlite"), query_count=3),
    DabDataset(name="crmarenapro", backends=("duckdb", "postgres", "sqlite"), query_count=13),
    DabDataset(name="DEPS_DEV_V1", backends=("duckdb", "sqlite"), query_count=2),
    DabDataset(name="GITHUB_REPOS", backends=("duckdb", "sqlite"), query_count=4),
    DabDataset(name="googlelocal", backends=("postgres", "sqlite"), query_count=4),
    DabDataset(name="music_brainz_20k", backends=("duckdb", "sqlite"), query_count=3),
    DabDataset(name="PANCANCER_ATLAS", backends=("duckdb", "postgres"), query_count=3),
    DabDataset(name="PATENTS", backends=("postgres", "sqlite"), query_count=3),
    DabDataset(name="stockindex", backends=("duckdb", "sqlite"), query_count=3),
    DabDataset(name="stockmarket", backends=("duckdb", "sqlite"), query_count=5),
    DabDataset(name="yelp", backends=("duckdb", "mongo"), query_count=7),
)


def by_name(name: str) -> DabDataset:
    for d in DAB_DATASETS:
        if d.name == name:
            return d
    raise KeyError(f"unknown DAB dataset: {name!r}")
