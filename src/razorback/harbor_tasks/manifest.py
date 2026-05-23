from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


TASK_VIEW_MANIFEST = "view_manifest.json"
TASK_VIEW_MANIFEST_SCHEMA_VERSION = 2


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def directory_checksums(root: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            checksums[path.relative_to(root).as_posix()] = file_sha256(path)
    return checksums


def directory_size_bytes(root: Path) -> int:
    total = 0
    for path in Path(root).rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total


@dataclass(frozen=True)
class TaskViewManifest:
    schema_version: int
    source_task_dir: str
    source_checksums: dict[str, str]
    benchmark_kind: str
    benchmark_task_id: str
    transform_name: str
    view_mode: Literal["copy", "link", "shared-context"]
    excluded_globs: list[str]
    environment_overrides: dict[str, Any]
    created_at: str = field(default_factory=utcnow_iso)
    harbor_version: str | None = None
    source_size_bytes: int | None = None
    view_size_bytes: int | None = None
    child_task_ids: list[str] = field(default_factory=list)
    dataset_ref: str | None = None
    dataset_content_hash: str | None = None
    task_content_hash: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    def write(self, path: Path) -> None:
        path.write_text(self.to_json())
