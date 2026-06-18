from __future__ import annotations

import importlib.metadata
import os
import re
import shutil
from pathlib import Path
from typing import Literal

from harbor.models.task.config import TaskConfig as HarborTaskConfig

from razorback.harbor_tasks.leakage import (
    DEFAULT_SOLUTION_DENY_GLOBS,
    assert_no_denied_paths,
    matches_denied_path,
)
from razorback.harbor_tasks.manifest import (
    TASK_VIEW_MANIFEST,
    TASK_VIEW_MANIFEST_SCHEMA_VERSION,
    TaskViewManifest,
    directory_checksums,
    directory_size_bytes,
)


def materialize_harbor_task_view(
    *,
    source_task_dir: Path,
    view_root: Path,
    benchmark_kind: str,
    benchmark_task_id: str,
    transform_name: str,
    docker_image: str | None = None,
    environment_env: dict[str, str] | None = None,
    resource_overrides: dict[str, int] | None = None,
    exclude_globs: tuple[str, ...] = DEFAULT_SOLUTION_DENY_GLOBS,
    view_mode: Literal["copy", "link"] = "copy",
    dataset_ref: str | None = None,
    dataset_content_hash: str | None = None,
    task_content_hash: str | None = None,
) -> Path:
    """Create a Razorback-owned Harbor task view and return its local path."""
    source = Path(source_task_dir).resolve()
    if not (source / "task.toml").is_file():
        raise FileNotFoundError(f"Harbor task source missing task.toml: {source}")
    if view_mode not in {"copy", "link"}:
        raise ValueError(f"unsupported view_mode: {view_mode}")

    root = Path(view_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    view_dir = root / _view_name(benchmark_kind, benchmark_task_id)
    if view_dir.exists() or view_dir.is_symlink():
        if view_dir.is_dir() and not view_dir.is_symlink():
            shutil.rmtree(view_dir)
        else:
            view_dir.unlink()
    view_dir.mkdir(parents=True)

    _reflect_allowed_files(
        source=source,
        destination=view_dir,
        exclude_globs=exclude_globs,
        view_mode=view_mode,
    )
    _patch_task_toml(
        view_dir / "task.toml",
        docker_image=docker_image,
        environment_env=environment_env or {},
        resource_overrides=resource_overrides or {},
    )
    assert_no_denied_paths(view_dir, deny_globs=exclude_globs)

    manifest = TaskViewManifest(
        schema_version=TASK_VIEW_MANIFEST_SCHEMA_VERSION,
        source_task_dir=str(source),
        source_checksums=directory_checksums(source),
        benchmark_kind=benchmark_kind,
        benchmark_task_id=benchmark_task_id,
        transform_name=transform_name,
        view_mode=view_mode,
        excluded_globs=list(exclude_globs),
        environment_overrides={
            "docker_image_tag": docker_image,
            "docker_image_digest": None,
            "env": dict(environment_env or {}),
            "resources": dict(resource_overrides or {}),
        },
        harbor_version=_harbor_version(),
        source_size_bytes=directory_size_bytes(source),
        view_size_bytes=directory_size_bytes(view_dir),
        dataset_ref=dataset_ref,
        dataset_content_hash=dataset_content_hash,
        task_content_hash=task_content_hash,
    )
    manifest.write(view_dir / TASK_VIEW_MANIFEST)
    return view_dir


def _reflect_allowed_files(
    *,
    source: Path,
    destination: Path,
    exclude_globs: tuple[str, ...],
    view_mode: Literal["copy", "link"],
) -> None:
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        rel_posix = rel.as_posix()
        if matches_denied_path(rel_posix, exclude_globs):
            continue
        target = destination / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if view_mode == "copy":
            shutil.copy2(path, target)
        else:
            os.symlink(path, target)


def _patch_task_toml(
    task_toml: Path,
    *,
    docker_image: str | None,
    environment_env: dict[str, str],
    resource_overrides: dict[str, int],
) -> None:
    task_config = HarborTaskConfig.model_validate_toml(task_toml.read_text())
    if docker_image is not None:
        task_config.environment.docker_image = docker_image
    if environment_env:
        merged = dict(task_config.environment.env)
        merged.update(environment_env)
        task_config.environment.env = merged
    for key, value in resource_overrides.items():
        if not hasattr(task_config.environment, key):
            raise ValueError(f"unsupported environment resource override: {key}")
        setattr(task_config.environment, key, value)
    # In `view_mode="link"` the reflected task.toml is a symlink back into the
    # shared source tree; writing through it would follow the link and corrupt
    # the source (leaking the injected benchmark env onto disk). Replace the
    # symlink with a real, view-owned file so the patch stays inside the view.
    if task_toml.is_symlink():
        task_toml.unlink()
    task_toml.write_text(task_config.model_dump_toml())


def _view_name(benchmark_kind: str, benchmark_task_id: str) -> str:
    raw = f"{benchmark_kind}-{benchmark_task_id}"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-._")
    return safe[:160] or "task-view"


def _harbor_version() -> str | None:
    try:
        return importlib.metadata.version("harbor")
    except importlib.metadata.PackageNotFoundError:
        return None
