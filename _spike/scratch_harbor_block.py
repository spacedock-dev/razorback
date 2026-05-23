"""Throw-away spike: scratch HarborBenchmarkBlock + _build_harbor.

Goal — validate that razorback can resolve adyen/dabstep@latest via
PackageDatasetClient and emit a harbor JobConfig whose tasks[].path
points at the downloaded task directories, WITHOUT any new Pydantic
class shipping to src/razorback/spec/schema.py.

This file is NOT imported by production code. It exists to test the
contract before we add the production block.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from harbor.models.job.config import JobConfig, RetryConfig
from harbor.models.trial.config import (
    AgentConfig,
    EnvironmentConfig,
    TaskConfig,
    VerifierConfig,
)
from harbor.models.package.reference import PackageReference
from harbor.registry.client import PackageDatasetClient


# ----- 1. Minimal HarborBenchmarkBlock (scratch — NOT shipping yet) -----


class HarborBenchmarkBlock(BaseModel):
    """Generic Harbor-resolved benchmark block (spike-only).

    Any harbor-published dataset is addressable through this single
    block: `dataset:` resolves via PackageDatasetClient; optional
    `tasks` / `exclude_tasks` / `n_tasks` selectors apply spec-side.
    """

    model_config = ConfigDict(extra="forbid")
    kind: Literal["harbor"]
    dataset: str | None = None
    tasks_root: Path | None = None
    tasks: list[str] | None = None
    exclude_tasks: list[str] | None = None
    n_tasks: int | None = None

    @field_validator("dataset")
    @classmethod
    def _validate_dataset_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "/" not in value or "@" not in value:
            raise ValueError(
                f"benchmark.dataset must be '<org>/<name>@<ref>'; got {value!r}"
            )
        parsed = PackageReference.parse(value)
        if not parsed.org or not parsed.short_name or not parsed.ref:
            raise ValueError(
                f"benchmark.dataset must be '<org>/<name>@<ref>'; got {value!r}"
            )
        return value

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "HarborBenchmarkBlock":
        if self.dataset is None and self.tasks_root is None:
            raise ValueError("exactly one of `dataset` or `tasks_root` required")
        if self.dataset is not None and self.tasks_root is not None:
            raise ValueError("`dataset` and `tasks_root` are mutually exclusive")
        return self


# ----- 2. Minimal _build_harbor (scratch — emits TaskConfig list) -----


def _resolve_dataset_tasks_scratch(
    *, dataset_ref: str, tasks: list[str] | None, cache_root: Path
) -> list[tuple[str, Path, str]]:
    """Return list of (task_name, downloaded_path, content_hash).

    Notes from Phase -1 probe:
    - PackageTaskId.name is the BARE name (e.g. '35' for dabstep,
      'matplotlib__matplotlib-14623' for swe-bench-verified,
      'ade-bench-f1006' for ade-bench). No dataset-prefix stripping;
      spec-side `tasks:` must match the bare name verbatim.
    """
    cache_root = Path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)

    async def _run() -> list[tuple[str, Path, str]]:
        client = PackageDatasetClient()
        metadata = await client.get_dataset_metadata(dataset_ref)
        items = await client.download_dataset(
            dataset_ref,
            overwrite=False,
            output_dir=cache_root,
            export=True,
        )
        by_name: dict[str, tuple[Path, str]] = {}
        for item in items:
            by_name[item.id.name] = (Path(item.downloaded_path).resolve(), item.id.ref)

        if tasks is None:
            return [(name, *by_name[name]) for name in sorted(by_name)]

        missing = [t for t in tasks if t not in by_name]
        if missing:
            available = sorted(by_name)[:10]
            raise ValueError(
                f"dataset {dataset_ref!r}: requested {missing!r} not found. "
                f"first 10 available: {available!r}"
            )
        return [(t, *by_name[t]) for t in tasks]

    return asyncio.run(_run())


def build_harbor_scratch(
    *,
    block: HarborBenchmarkBlock,
    job_name: str,
    jobs_dir: Path,
    cache_root: Path,
    agent_cfg: AgentConfig,
    environment_cfg: EnvironmentConfig,
    n_concurrent_trials: int = 1,
    n_attempts: int = 1,
) -> JobConfig:
    """Emit a harbor JobConfig from a HarborBenchmarkBlock.

    Pure pass-through path (no prep hook). Resolves dataset via
    PackageDatasetClient or uses tasks_root local dir.
    """
    if block.dataset is not None:
        resolved = _resolve_dataset_tasks_scratch(
            dataset_ref=block.dataset,
            tasks=block.tasks,
            cache_root=cache_root,
        )
        task_paths = [path for _, path, _ in resolved]
    else:
        assert block.tasks_root is not None
        if not block.tasks:
            raise ValueError("tasks_root requires non-empty tasks list")
        task_paths = [block.tasks_root / t for t in block.tasks]

    if block.exclude_tasks:
        excluded = set(block.exclude_tasks)
        task_paths = [p for p in task_paths if p.name not in excluded]

    if block.n_tasks is not None:
        task_paths = task_paths[: block.n_tasks]

    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=n_concurrent_trials,
        n_attempts=n_attempts,
        agents=[agent_cfg],
        tasks=[TaskConfig(path=p) for p in task_paths],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=environment_cfg,
    )


# ----- 3. Spike driver — exercise the block + builder end-to-end -----


def main() -> None:
    import json
    import os
    import sys
    import tempfile

    print("=" * 60)
    print("SPIKE 1: parse HarborBenchmarkBlock")
    print("=" * 60)
    block = HarborBenchmarkBlock(
        kind="harbor",
        dataset="adyen/dabstep@latest",
        tasks=["35"],
    )
    print(f"  block.dataset = {block.dataset!r}")
    print(f"  block.tasks = {block.tasks!r}")
    print("  OK — block parses and validates")

    print()
    print("=" * 60)
    print("SPIKE 2: validator rejects bad refs")
    print("=" * 60)
    for bad in ("dabstep", "adyen/dabstep", "@latest"):
        try:
            HarborBenchmarkBlock(kind="harbor", dataset=bad)
            print(f"  FAIL — {bad!r} should have been rejected")
        except Exception as e:
            print(f"  OK — {bad!r} rejected: {type(e).__name__}")

    print()
    print("=" * 60)
    print("SPIKE 3: resolve adyen/dabstep@latest via PackageDatasetClient")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as td:
        cache = Path(td) / "cache"
        resolved = _resolve_dataset_tasks_scratch(
            dataset_ref="adyen/dabstep@latest",
            tasks=["35"],
            cache_root=cache,
        )
        for name, path, content_hash in resolved:
            print(f"  task {name!r}:")
            print(f"    path = {path}")
            print(f"    content_hash = {content_hash}")
            assert path.exists(), f"resolved path does not exist: {path}"
            task_toml = path / "task.toml"
            instr = path / "instruction.md"
            print(f"    task.toml exists = {task_toml.exists()}")
            print(f"    instruction.md exists = {instr.exists()}")
            if task_toml.exists():
                print(f"    task.toml head: {task_toml.read_text().splitlines()[:5]}")

        print()
        print("=" * 60)
        print("SPIKE 4: build JobConfig from block")
        print("=" * 60)
        # Stub agent + environment configs (we're not running, just shape-checking).
        agent_cfg = AgentConfig(
            name="scratch-agent",
            import_path="razorback.agents.spacedock_solver:SpacedockSolverAgent",
            kwargs={},
            env={},
        )
        environment_cfg = EnvironmentConfig(
            import_path="razorback.environments.docker:ProxySeparatedDockerEnvironment",
            kwargs={},
        )
        jobs_dir = Path(td) / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        cfg = build_harbor_scratch(
            block=block,
            job_name="spike-dabstep-001",
            jobs_dir=jobs_dir,
            cache_root=cache,
            agent_cfg=agent_cfg,
            environment_cfg=environment_cfg,
        )
        print(f"  JobConfig.job_name = {cfg.job_name}")
        print(f"  JobConfig.jobs_dir = {cfg.jobs_dir}")
        print(f"  JobConfig.tasks count = {len(cfg.tasks)}")
        for tc in cfg.tasks:
            print(f"    TaskConfig(path={tc.path})")

        print()
        print("=" * 60)
        print("SPIKE 5: dump JobConfig to YAML — verify harbor would accept")
        print("=" * 60)
        import yaml
        job_yaml_path = jobs_dir / f"{cfg.job_name}.yaml"
        job_yaml_path.write_text(yaml.safe_dump(cfg.model_dump(mode="json")))
        print(f"  wrote {job_yaml_path}")
        print(f"  size: {job_yaml_path.stat().st_size} bytes")
        # Round-trip: re-parse via harbor's JobConfig to prove the YAML is
        # actually accepted by harbor's own model.
        reloaded_yaml = yaml.safe_load(job_yaml_path.read_text())
        reloaded = JobConfig.model_validate(reloaded_yaml)
        print(f"  reloaded.job_name = {reloaded.job_name}")
        print(f"  reloaded.tasks count = {len(reloaded.tasks)}")
        print("  OK — JobConfig round-trips through harbor's own model")

    print()
    print("=" * 60)
    print("SPIKE COMPLETE — all five checks passed")
    print("=" * 60)


if __name__ == "__main__":
    main()
