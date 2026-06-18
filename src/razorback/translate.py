# ABOUTME: Spec to harbor JobConfig translator (Phase 1 AC-6: emits AgentConfig.import_path).
# ABOUTME: Replaces the v1 compat translator. Auth flows via AgentConfig.env per FU-1 AC-1.

from pathlib import Path
from typing import Any, Literal

from harbor.models.agent.name import AgentName
from harbor.models.job.config import JobConfig, RetryConfig
from harbor.models.trial.config import (
    AgentConfig,
    EnvironmentConfig,
    TaskConfig,
    VerifierConfig,
)

from razorback.agents.auth import resolve_claude_auth, resolve_codex_auth
from razorback.benchmarks.spider2_dbt.harbor_view import (
    materialize_spider2_harbor_task_view,
)
from razorback.agents.proxy import PROXY_BLOCK_ENV
from razorback.errors import SpecError
from razorback.spec.agent_kwargs import build_spacedock_harbor_agent_kwargs
from razorback.spec.schema import (
    CodexAgentBlock,
    HarborBenchmarkBlock,
    HarborLocalBenchmarkBlock,
    LocalBenchmarkBlock,
    NopAgentBlock,
    SpacedockSolverAgentBlock,
    Spec,
)


SPACEDOCK_SOLVER_IMPORT_PATH = (
    "razorback.agents.spacedock_solver:SpacedockSolverAgent"
)
SPACEDOCK_SOLVER_ENVIRONMENT_IMPORT_PATH = (
    "razorback.environments.docker:ProxySeparatedDockerEnvironment"
)
RAZORBACK_CLAUDE_CODE_IMPORT_PATH = (
    "razorback.agents._runtime.claude:RazorbackClaudeCode"
)
RAZORBACK_CODEX_IMPORT_PATH = (
    "razorback.agents._runtime.codex:RazorbackCodex"
)
SPACEDOCK_SOLVER_CONTAINER_FREEZE_ROOT = "/razorback-freeze"

SPIDER2_DBT_SHORT_NAME = "spider2-dbt"


def _is_spider2_dbt_dataset(dataset_ref: str) -> bool:
    """True when a `kind: harbor` dataset ref names the spider2-dbt family.

    Mirrors the ade-bench dataset-ref flow: the dataset ref is the family
    signal. The fully-qualified `<org>/spider2-dbt@<ref>` form resolves to
    short_name == "spider2-dbt"; the bare `spider2-dbt@1.0` form is the
    `harbor download` CLI concept (not a valid spec dataset) and raises on
    parse, so the helper swallows the error and returns False.
    """
    from harbor.models.package.reference import PackageReference

    try:
        parsed = PackageReference.parse(dataset_ref)
    except Exception:
        return False
    return parsed.short_name == SPIDER2_DBT_SHORT_NAME


def _apply_task_selectors(
    paths: list[Path], *, exclude_tasks: list[str] | None, n_tasks: int | None
) -> list[Path]:
    """Filter task dirs by name, then cap. Operates on whatever `.name` the
    caller passes — for spider2-dbt this MUST be source-slug paths, applied
    BEFORE materialization (view names are `spider2-dbt-<slug>`)."""
    result = paths
    if exclude_tasks:
        excluded = set(exclude_tasks)
        result = [p for p in result if p.name not in excluded]
    if n_tasks is not None:
        result = result[:n_tasks]
    return result


def spec_to_job_config(
    spec: Spec,
    *,
    job_name: str,
    jobs_dir: Path,
    tasks_root: Path | None = None,
    project_root: Path | None = None,
    home: Path | None = None,
    prior_frozen_spec_path: Path | None = None,
    materialize_mode: Literal["bind", "copy"] = "bind",
) -> tuple[JobConfig, dict[str, tuple[str, int]]]:
    """Translate a parsed (frozen) spec into a harbor JobConfig.

    Returns (JobConfig, trial_name_map). The map is empty for non-DAB benchmarks.
    Phase 1 emits `AgentConfig.import_path` for spacedock_solver per AC-6.
    """
    agent_cfg, _task_env = _build_agent_config(
        spec,
        project_root=project_root,
        home=home,
        prior_frozen_spec_path=prior_frozen_spec_path,
    )

    if isinstance(spec.benchmark, LocalBenchmarkBlock):
        return _build_local(
            spec=spec, job_name=job_name, jobs_dir=jobs_dir, agent_cfg=agent_cfg
        ), {}
    if isinstance(spec.benchmark, HarborBenchmarkBlock):
        return _build_harbor(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            tasks_root=Path(tasks_root) if tasks_root else None,
            agent_cfg=agent_cfg,
            home=home,
            materialize_mode=materialize_mode,
        )
    if isinstance(spec.benchmark, HarborLocalBenchmarkBlock):
        return _build_harbor_local(
            spec=spec,
            job_name=job_name,
            jobs_dir=jobs_dir,
            agent_cfg=agent_cfg,
        ), {}
    raise SpecError(f"unsupported benchmark block: {type(spec.benchmark).__name__}")


def _build_agent_config(
    spec: Spec,
    *,
    project_root: Path | None,
    home: Path | None,
    prior_frozen_spec_path: Path | None = None,
) -> tuple[AgentConfig, dict[str, str]]:
    if isinstance(spec.agent, NopAgentBlock):
        return AgentConfig(name=AgentName.NOP.value), {}

    if isinstance(spec.agent, CodexAgentBlock):
        if project_root is None:
            raise SpecError("codex agent requires project_root for .env auth discovery.")
        resolution = resolve_codex_auth(project_root=project_root, home=home)
        kwargs: dict[str, Any] = {}
        if spec.agent.reasoning_effort is not None:
            kwargs["reasoning_effort"] = spec.agent.reasoning_effort
        if spec.agent.reasoning_summary is not None:
            kwargs["reasoning_summary"] = spec.agent.reasoning_summary
        agent_cfg = AgentConfig(
            import_path=RAZORBACK_CODEX_IMPORT_PATH,
            model_name=spec.agent.model,
            override_timeout_sec=spec.agent.override_timeout_sec,
            override_setup_timeout_sec=spec.agent.override_setup_timeout_sec,
            max_timeout_sec=spec.agent.max_timeout_sec,
            kwargs=kwargs,
            env=dict(resolution.env),
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env

    if isinstance(spec.agent, SpacedockSolverAgentBlock):
        if project_root is None:
            raise SpecError(
                "spacedock_solver requires project_root for .env auth discovery."
            )
        if spec.agent.sealed_hash is None:
            raise SpecError(
                "spacedock_solver spec must be frozen (agent.sealed_hash missing)."
            )
        if spec.agent.runtime == "codex":
            resolution = resolve_codex_auth(project_root=project_root, home=home)
        else:
            resolution = resolve_claude_auth(project_root=project_root, home=home)
        harbor_agent_kwargs = build_spacedock_harbor_agent_kwargs(
            max_turns=spec.agent.max_turns,
            tools_allowed=spec.agent.tools_allowed,
            tools_denied=spec.agent.tools_denied,
            append_system_prompt=spec.agent.append_system_prompt,
            reasoning_effort=spec.agent.reasoning_effort,
            reasoning_summary=spec.agent.reasoning_summary,
        )
        kwargs: dict[str, Any] = {
            "runtime": spec.agent.runtime,
            "model": spec.agent.model,
            "sampling": {
                "temperature": spec.agent.sampling.temperature,
                "top_p": spec.agent.sampling.top_p,
                "seed": spec.agent.sampling.seed,
            },
            "solver_workflow": str(spec.agent.solver_workflow),
            "solver_workflow_content_hash": spec.agent.solver_workflow_content_hash,
            "prompt_content_hashes": dict(spec.agent.prompt_content_hashes),
            "spacedock_skill_version": spec.agent.spacedock_skill_version,
            "harbor_agent_kwargs": harbor_agent_kwargs,
            "max_turns": spec.agent.max_turns,
            "tools_allowed": list(spec.agent.tools_allowed),
            "tools_denied": list(spec.agent.tools_denied),
            "resume_from_freeze": (
                str(spec.agent.resume_from_freeze)
                if spec.agent.resume_from_freeze
                else None
            ),
        }
        agent_cfg = AgentConfig(
            import_path=SPACEDOCK_SOLVER_IMPORT_PATH,
            model_name=spec.agent.model,
            override_timeout_sec=spec.agent.override_timeout_sec,
            override_setup_timeout_sec=spec.agent.override_setup_timeout_sec,
            max_timeout_sec=spec.agent.max_timeout_sec,
            kwargs=kwargs,
            env=dict(resolution.env),
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env

    if getattr(spec.agent, "kind", None) == "claude-cli":
        if project_root is None:
            raise SpecError(
                "claude-cli agent requires project_root for .env auth discovery."
            )
        if spec.agent.sampling.temperature not in (None, 0.0):
            raise SpecError(
                "legacy agent.kind: claude-cli now routes to Harbor ClaudeCode, "
                "which has no temperature kwarg; keep sampling.temperature at "
                "its default no-op value."
            )
        resolution = resolve_claude_auth(project_root=project_root, home=home)
        kwargs: dict[str, Any] = {}
        if spec.agent.tools_allowed:
            kwargs["allowed_tools"] = ",".join(spec.agent.tools_allowed)
        if spec.agent.reasoning_effort is not None:
            kwargs["reasoning_effort"] = spec.agent.reasoning_effort
        agent_cfg = AgentConfig(
            import_path=RAZORBACK_CLAUDE_CODE_IMPORT_PATH,
            model_name=spec.agent.model,
            kwargs=kwargs,
            env=dict(resolution.env),
        )
        task_env = dict(PROXY_BLOCK_ENV)
        return agent_cfg, task_env

    raise SpecError(f"unsupported agent block: {type(spec.agent).__name__}")


def _build_local(
    *, spec: Spec, job_name: str, jobs_dir: Path, agent_cfg: AgentConfig
) -> JobConfig:
    assert isinstance(spec.benchmark, LocalBenchmarkBlock)
    run_dir = jobs_dir / job_name
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=spec.concurrency.trials,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=[TaskConfig(path=Path(p).resolve()) for p in spec.benchmark.task_paths],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=_environment_config(agent_cfg, run_dir),
    )


def _build_harbor_local(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    agent_cfg: AgentConfig,
) -> JobConfig:
    """Translate `kind: harbor-local` — local Harbor-shaped task directory dev escape."""
    assert isinstance(spec.benchmark, HarborLocalBenchmarkBlock)
    block = spec.benchmark
    source_root = Path(block.tasks_root).resolve()
    task_paths: list[Path] = []
    for slug in block.tasks:
        source_task_dir = source_root / slug
        if not (source_task_dir / "task.toml").is_file():
            raise SpecError(
                f"harbor-local task {slug!r} not found at {source_task_dir} "
                f"(missing task.toml); tasks_root={source_root}"
            )
        task_paths.append(source_task_dir)

    run_dir = jobs_dir / job_name
    return JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=spec.concurrency.trials,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=[TaskConfig(path=p) for p in task_paths],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=_environment_config(agent_cfg, run_dir),
    )


def _build_harbor(
    *,
    spec: Spec,
    job_name: str,
    jobs_dir: Path,
    agent_cfg: AgentConfig,
    home: Path | None = None,
    tasks_root: Path | None = None,
    materialize_mode: Literal["bind", "copy"] = "bind",
) -> tuple[JobConfig, dict[str, tuple[str, int] | tuple[str, list[int]]]]:
    """Translate `kind: harbor` block into a Harbor JobConfig.

    Two modes:

    - **Pure pass-through** (no `plugin:`): resolves `dataset:` via
      `PackageDatasetClient`, applies spec-side `tasks` / `exclude_tasks`
      / `n_tasks` selectors verbatim against `PackageTaskId.name`, emits
      one `TaskConfig(path=...)` per resolved task. Returns an empty
      trial_name_map.

    - **Plugin route** (`plugin:` set): dispatches to the named plugin
      via the `razorback.plugin_args` entry-point registry. The plugin's
      `generate` CLI emits per-task directories under `tasks_root`; if
      the plugin emits a `trial_name_map_v2.json` extension, the map is
      reconstructed and returned for aggregator consumption (DAB
      batch-mode + per-query semantics).
    """
    assert isinstance(spec.benchmark, HarborBenchmarkBlock)
    block = spec.benchmark
    run_dir = jobs_dir / job_name

    if block.plugin is not None:
        if tasks_root is None:
            raise SpecError(
                f"`kind: harbor` with `plugin: {block.plugin}` requires "
                "tasks_root (the run orchestrator passes it)."
            )
        task_paths, trial_name_map = _invoke_plugin_generate(
            plugin=block.plugin,
            plugin_args=block.plugin_args or {},
            spec_tasks=block.tasks,
            tasks_root=Path(tasks_root),
        )
    else:
        # Fail fast on the spider2-dbt tasks_root contract BEFORE the network
        # resolve: `_is_spider2_dbt_dataset` is a cheap ref-parse, while
        # `_resolve_harbor_dataset_tasks` can trigger a dataset download. A
        # spider2-dbt dataset with `tasks_root is None` is mis-wired regardless
        # of resolution, so reject it without touching the network.
        is_spider2_dbt = _is_spider2_dbt_dataset(block.dataset)
        if is_spider2_dbt and tasks_root is None:
            raise SpecError(
                "`kind: harbor` spider2-dbt dataset requires tasks_root "
                "(the run orchestrator passes it)."
            )
        home_dir = Path(home) if home is not None else Path.home()
        cache_root = home_dir / ".cache" / "razorback" / "harbor" / "datasets"
        source_paths = _resolve_harbor_dataset_tasks(
            dataset_ref=block.dataset,
            tasks=block.tasks,
            cache_root=cache_root,
        )
        if is_spider2_dbt:
            # Filter on SOURCE slugs BEFORE materialization so selectors bind
            # to Harbor task names, not the `spider2-dbt-<slug>` view names.
            selected_sources = _apply_task_selectors(
                source_paths,
                exclude_tasks=block.exclude_tasks,
                n_tasks=block.n_tasks,
            )
            view_root = Path(tasks_root)
            # Map the spec-level materialize mode onto the view-materializer's
            # vocabulary: `bind` -> symlink the (large) task trees in place,
            # `copy` -> eagerly duplicate. Mirrors how ade-bench threads the
            # mode (cli/run.py:313). Defaulting to "bind" matches
            # `spec_to_job_config`, so an un-threaded call no longer silently
            # forces copy.
            view_mode: Literal["copy", "link"] = (
                "link" if materialize_mode == "bind" else "copy"
            )
            task_paths = [
                materialize_spider2_harbor_task_view(
                    source_task_dir=src,
                    view_root=view_root,
                    task_slug=src.name,
                    view_mode=view_mode,
                )
                for src in selected_sources
            ]
            trial_name_map = {}

            cfg = JobConfig(
                job_name=job_name,
                jobs_dir=jobs_dir,
                n_concurrent_trials=spec.concurrency.trials,
                n_attempts=spec.trials,
                agents=[agent_cfg],
                tasks=[TaskConfig(path=p) for p in task_paths],
                verifier=VerifierConfig(disable=False),
                retry=RetryConfig(max_retries=0),
                environment=_environment_config(agent_cfg, run_dir),
            )
            return cfg, trial_name_map

        task_paths = source_paths
        trial_name_map = {}

    if block.exclude_tasks:
        excluded = set(block.exclude_tasks)
        task_paths = [p for p in task_paths if p.name not in excluded]

    if block.n_tasks is not None:
        task_paths = task_paths[: block.n_tasks]

    cfg = JobConfig(
        job_name=job_name,
        jobs_dir=jobs_dir,
        n_concurrent_trials=spec.concurrency.trials,
        n_attempts=spec.trials,
        agents=[agent_cfg],
        tasks=[TaskConfig(path=p) for p in task_paths],
        verifier=VerifierConfig(disable=False),
        retry=RetryConfig(max_retries=0),
        environment=_environment_config(agent_cfg, run_dir),
    )
    return cfg, trial_name_map


def _invoke_plugin_generate(
    *,
    plugin: str,
    plugin_args: dict[str, object],
    spec_tasks: list[str] | None,
    tasks_root: Path,
) -> tuple[list[Path], dict[str, tuple[str, int] | tuple[str, list[int]]]]:
    """Run the named plugin's `generate` CLI; collect task paths + trial-name map.

    The plugin is discovered by name via the `razorback.plugin_args`
    entry-point group (typed args validation already happened at spec
    parse time). The CLI command is invoked via
    `uv run razorback-plugin-<name> generate` matching today's contract.

    The plugin SHOULD emit `<tasks_root>/trial_name_map_v2.json` carrying
    `{tasks: [{slug, query_ids: list[int]}]}`. When present, the map is
    reconstructed for the aggregator's `reward_per_query.json` fan-out.
    When absent, every emitted task directory becomes a `(slug, int)`
    entry derived from its name.
    """
    import json
    import subprocess

    tasks_root.mkdir(parents=True, exist_ok=True)
    cmd = [
        "uv", "run", f"razorback-plugin-{plugin}", "generate",
        "--out", str(tasks_root.resolve()),
    ]
    # Note: `dataset` (the spec-level ref like "dab@1.0") is NOT passed to the
    # plugin CLI — it's a spec-level identity concept used by the freeze
    # provenance, not a plugin invocation parameter. The plugin's task-set
    # selector is `--datasets` (plural), populated from spec_tasks below.
    if spec_tasks:
        cmd.extend(["--datasets", ",".join(spec_tasks)])
    for key, value in plugin_args.items():
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            cmd.append(flag if value else f"--no-{key.replace('_', '-')}")
        elif value is None:
            continue
        else:
            cmd.extend([flag, str(value)])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SpecError(
            f"razorback-plugin-{plugin} generate failed "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )

    task_dirs = sorted(
        p for p in tasks_root.rglob("task.toml")
    )
    task_paths = sorted({p.parent for p in task_dirs})

    map_path = tasks_root / "trial_name_map_v2.json"
    trial_name_map: dict[str, tuple[str, int] | tuple[str, list[int]]] = {}
    if map_path.is_file():
        payload = json.loads(map_path.read_text())
        for entry in payload.get("tasks", []):
            slug = entry["slug"]
            query_ids = entry.get("query_ids")
            if isinstance(query_ids, list) and len(query_ids) > 1:
                # batch mode: one task carries N query_ids
                trial_name_map[slug] = (_split_dataset_from_slug(slug)[0], list(query_ids))
            elif isinstance(query_ids, list) and len(query_ids) == 1:
                trial_name_map[slug] = (_split_dataset_from_slug(slug)[0], int(query_ids[0]))
    else:
        # Fallback: derive (dataset, int) from `<dataset>-q<n>` naming.
        for task_dir in task_paths:
            slug = task_dir.name
            if "-q" in slug:
                ds, qpart = slug.rsplit("-q", 1)
                try:
                    trial_name_map[slug] = (ds, int(qpart))
                except ValueError:
                    pass

    return task_paths, trial_name_map


def _split_dataset_from_slug(slug: str) -> tuple[str, str | None]:
    """Split `<dataset>-q<n>` → (dataset, '<n>'). Bare `<dataset>` → (dataset, None)."""
    if "-q" in slug:
        ds, qpart = slug.rsplit("-q", 1)
        return ds, qpart if qpart.isdigit() else None
    return slug, None


def _resolve_harbor_dataset_tasks(
    *, dataset_ref: str, tasks: list[str] | None, cache_root: Path
) -> list[Path]:
    """Resolve a Harbor dataset ref into local task directories.

    Wraps `PackageDatasetClient.download_dataset` (the same entry point
    ade-bench's dataset-ref path uses). Returns paths in spec-order when
    `tasks` is provided, alphabetical order otherwise.

    Errors are wrapped in `SpecError` so `rk freeze`/`rk run` surface
    SPEC_ERROR exit code rather than raw network/registry exceptions.
    """
    import asyncio

    from harbor.registry.client import PackageDatasetClient

    cache_root = Path(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)

    async def _resolve() -> list[Path]:
        client = PackageDatasetClient()
        items = await client.download_dataset(
            dataset_ref,
            overwrite=False,
            output_dir=cache_root,
            export=True,
        )
        return items

    try:
        items = asyncio.run(_resolve())
    except SpecError:
        raise
    except BaseException as exc:
        raise SpecError(
            f"failed to resolve harbor dataset {dataset_ref!r}: {exc}"
        ) from exc

    by_name: dict[str, Path] = {
        item.id.name: Path(item.downloaded_path).resolve() for item in items
    }

    if tasks is None:
        return [by_name[name] for name in sorted(by_name)]

    missing = [t for t in tasks if t not in by_name]
    if missing:
        available = sorted(by_name)
        sample = available[:10]
        raise SpecError(
            f"harbor dataset {dataset_ref!r}: requested task(s) {missing!r} "
            f"not found. available ({len(available)}, first 10): {sample!r}"
        )
    return [by_name[t] for t in tasks]


def _environment_config(agent_cfg: AgentConfig, run_dir: Path) -> EnvironmentConfig:
    if agent_cfg.import_path == RAZORBACK_CODEX_IMPORT_PATH:
        return EnvironmentConfig(
            import_path=SPACEDOCK_SOLVER_ENVIRONMENT_IMPORT_PATH,
            delete=False,
            env=dict(PROXY_BLOCK_ENV),
        )

    if agent_cfg.import_path != SPACEDOCK_SOLVER_IMPORT_PATH:
        return EnvironmentConfig(delete=False)

    host_freeze_root = run_dir / "_razorback" / "freeze"
    host_freeze_root.mkdir(parents=True, exist_ok=True)
    return EnvironmentConfig(
        import_path=SPACEDOCK_SOLVER_ENVIRONMENT_IMPORT_PATH,
        delete=False,
        env=dict(PROXY_BLOCK_ENV),
        mounts_json=[
            {
                "type": "bind",
                "source": str(host_freeze_root.resolve()),
                "target": SPACEDOCK_SOLVER_CONTAINER_FREEZE_ROOT,
            }
        ],
    )
