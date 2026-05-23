# ABOUTME: DAB dataset definition loader — pydantic shape for dataset.toml.
# ABOUTME: Used by Razorback core (translator + generator) as the source of truth for AC-1..AC-5.

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DabDatasetEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    backends: tuple[str, ...]
    query_count: int = Field(ge=1)
    query_ids: tuple[int, ...]
    schema_version: str = "v1"


class DabDatasetDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    version: str
    description: str = ""
    workspace_variants: tuple[str, ...]
    datasets: tuple[DabDatasetEntry, ...]

    def get_dataset(self, name: str) -> DabDatasetEntry:
        for d in self.datasets:
            if d.name == name:
                return d
        raise KeyError(f"unknown DAB dataset: {name!r}")

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"


def load_definition_from(path: Path) -> DabDatasetDefinition:
    raw = tomllib.loads(Path(path).read_text())
    return DabDatasetDefinition.model_validate(raw)


def load_default_definition() -> DabDatasetDefinition:
    pkg_files = resources.files("razorback_plugin_dab")
    toml_path = pkg_files / "dataset.toml"
    with resources.as_file(toml_path) as concrete:
        return load_definition_from(Path(concrete))
