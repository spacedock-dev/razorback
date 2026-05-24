# ABOUTME: Explain-only planner for `rk run --explain`.
# ABOUTME: Builds the resolved solver/runtime/preparation/prompt report without invoking Harbor.

import hashlib
import json
from pathlib import Path

import typer

from razorback.errors import ExitCode


def _redacted_env_keys(env: dict | None) -> list[str]:
    return sorted(str(k) for k in (env or {}).keys())


def _task_path(task) -> Path | None:
    raw = getattr(task, "path", None)
    if raw is None:
        return None
    return Path(raw)


def _task_instruction_path(task_path: Path | None) -> Path | None:
    if task_path is None:
        return None
    candidate = task_path / "instruction.md"
    return candidate if candidate.is_file() else None


def _read_if_file(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return path.read_text(errors="replace")


def _sample_task_prompt_inputs(job_config) -> dict:
    tasks = list(getattr(job_config, "tasks", []) or [])
    if not tasks:
        return {
            "task_count": 0,
            "task_paths": [],
            "sample_task_path": None,
            "sample_instruction_path": None,
            "sample_instruction": None,
        }
    task_paths = [_task_path(task) for task in tasks]
    sample_path = task_paths[0]
    instruction_path = _task_instruction_path(sample_path)
    return {
        "task_count": len(tasks),
        "task_paths": [str(p) for p in task_paths if p is not None],
        "sample_task_path": str(sample_path) if sample_path is not None else None,
        "sample_instruction_path": (
            str(instruction_path) if instruction_path is not None else None
        ),
        "sample_instruction": _read_if_file(instruction_path),
    }


def _prompt_plan(spec, job_config) -> dict:
    agent = spec.agent
    task_inputs = _sample_task_prompt_inputs(job_config)
    sample_instruction = task_inputs.get("sample_instruction")
    kind = getattr(agent, "kind", None)

    if kind == "spacedock_solver":
        from razorback.agents.spacedock_solver import (
            CODEX_SPACEDOCK_FIRST_OFFICER_SKILL_PATH,
            CODEX_SPACEDOCK_PROMPT_PREFIX_TEMPLATE,
            SPACEDOCK_PROMPT_PREFIX_TEMPLATE,
        )

        workflow_readme = Path(agent.solver_workflow) / "README.md"
        workflow_text = _read_if_file(workflow_readme)
        workspace_dir = "/app" if agent.runtime == "codex" else "/workspace"
        if agent.runtime == "codex":
            prefix = CODEX_SPACEDOCK_PROMPT_PREFIX_TEMPLATE.format(
                workspace_dir=workspace_dir,
                first_officer_skill_path=CODEX_SPACEDOCK_FIRST_OFFICER_SKILL_PATH,
            )
            prompt_mode = "spacedock-codex-first-officer"
        else:
            prefix = SPACEDOCK_PROMPT_PREFIX_TEMPLATE.format(
                workspace_dir=workspace_dir
            )
            prompt_mode = "spacedock-claude-first-officer"
        sample_composed_prompt = None
        if workflow_text is not None and sample_instruction is not None:
            sample_composed_prompt = (
                f"{prefix}"
                "# Solver workflow instructions\n\n"
                f"{workflow_text.strip()}\n\n"
                "# Task instruction\n\n"
                f"{sample_instruction}"
            )
        return {
            **task_inputs,
            "mode": prompt_mode,
            "workspace_dir": workspace_dir,
            "solver_workflow": str(agent.solver_workflow),
            "solver_workflow_readme": str(workflow_readme),
            "solver_workflow_readme_found": workflow_text is not None,
            "prompt_prefix": prefix,
            "workflow_readme": workflow_text,
            "sample_composed_prompt": sample_composed_prompt,
            "task_instruction_application": (
                "The benchmark task instruction is appended after the solver "
                "workflow for each trial."
            ),
        }

    return {
        **task_inputs,
        "mode": "direct-task-instruction",
        "prompt_prefix": "",
        "workflow_readme": None,
        "sample_composed_prompt": sample_instruction,
        "task_instruction_application": (
            "The benchmark task instruction is passed directly to the runtime "
            "adapter for each trial."
        ),
    }


def _agent_plan(spec, job_config) -> dict:
    agent_cfg = job_config.agents[0]
    spec_agent = spec.agent
    kwargs = dict(getattr(agent_cfg, "kwargs", None) or {})
    return {
        "spec_kind": getattr(spec_agent, "kind", None),
        "runtime": getattr(spec_agent, "runtime", None),
        "model": getattr(spec_agent, "model", getattr(agent_cfg, "model_name", None)),
        "harbor_import_path": getattr(agent_cfg, "import_path", None),
        "harbor_builtin_name": getattr(agent_cfg, "name", None),
        "override_timeout_sec": getattr(agent_cfg, "override_timeout_sec", None),
        "override_setup_timeout_sec": getattr(
            agent_cfg, "override_setup_timeout_sec", None
        ),
        "max_timeout_sec": getattr(agent_cfg, "max_timeout_sec", None),
        "env_keys": _redacted_env_keys(getattr(agent_cfg, "env", None)),
        "kwargs": kwargs,
    }


def _preparation_plan(spec, job_config, *, run_dir: Path, job_config_yaml: Path) -> list[str]:
    steps = [
        "Parse frozen spec and validate schema.",
        "Resolve runs-dir, job name, and run directory.",
        "Run runs-dir Docker mount visibility canary.",
        "Check frozen Harbor/model/plugin provenance drift when present.",
        "Translate Razorback spec to Harbor JobConfig.",
    ]
    benchmark_kind = getattr(spec.benchmark, "kind", None)
    if benchmark_kind == "ade-bench":
        steps.append(
            "Resolve/materialize ADE Harbor task views, including environment, "
            "tests, instruction.md, and view_manifest.json."
        )
    elif benchmark_kind == "harbor_dab":
        steps.append(
            "Invoke razorback-plugin-dab generate to materialize Harbor task "
            "directories for the requested datasets/query mode."
        )
    elif benchmark_kind == "spider2-dbt":
        steps.append("Materialize Spider2-DBT Harbor task views.")
    else:
        steps.append("Use local task paths directly.")

    if getattr(spec.agent, "kind", None) == "spacedock_solver":
        steps.extend([
            "Create/mount the run-local freeze root at /razorback-freeze.",
            "At agent setup, create or validate the sealed-hash freeze CAS.",
            "For ADE tasks, run Razorback ADE workspace preflight before model invocation.",
        ])
        runtime = getattr(spec.agent, "runtime", None)
        if runtime == "codex":
            steps.extend([
                "Build RazorbackCodex as the inner runtime adapter.",
                "Install Codex with proxy variables cleared only for install.",
                "Stage the Spacedock plugin into Codex skills and enable multi_agent.",
                "Install Codex public-lookup guards and shell wrappers.",
                "Invoke codex exec with the first-officer bootstrap prompt.",
            ])
        elif runtime == "claude":
            steps.extend([
                "Build RazorbackClaudeCode as the inner runtime adapter.",
                "Stage the Spacedock plugin into the trial container.",
                "Invoke Claude with --agent spacedock:first-officer.",
            ])
    elif getattr(spec.agent, "kind", None) == "codex":
        steps.extend([
            "Build RazorbackCodex directly.",
            "Install Codex with proxy variables cleared only for install.",
            "Install Codex public-lookup guards and shell wrappers.",
            "Invoke codex exec with each task instruction directly.",
        ])
    elif getattr(spec.agent, "kind", None) == "claude-cli":
        steps.extend([
            "Build RazorbackClaudeCode directly.",
            "Apply Claude auth/tool policy.",
            "Invoke Claude with each task instruction directly.",
        ])

    steps.extend([
        f"Write Harbor job config to {job_config_yaml}.",
        f"Invoke `uv run harbor run -c {job_config_yaml}`.",
        f"After Harbor returns, write spec/provenance/aggregate artifacts under {run_dir}.",
    ])
    return steps


def explain_run(
    *,
    spec_path: Path,
    spec_bytes: bytes,
    spec,
    job_name: str,
    run_dir: Path,
    job_config,
    ordering_hint_metadata: dict | None,
) -> dict:
    job_config_yaml = run_dir / "_job_config.yaml"
    environment = getattr(job_config, "environment", None)
    return {
        "schema_version": "rk-run-explain-v1",
        "explain_only": True,
        "explain_side_effects": [
            "runs normal preflight checks before the explain branch",
            "translates the spec and may materialize task views to report exact task paths",
            "does not write _job_config.yaml",
            "does not invoke Harbor",
            "does not run the model",
        ],
        "spec_path": str(spec_path),
        "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
        "experiment": spec.experiment,
        "job_name": job_name,
        "run_dir": str(run_dir),
        "job_config_yaml": str(job_config_yaml),
        "benchmark": spec.benchmark.model_dump(mode="json"),
        "concurrency": {
            "trials": spec.concurrency.trials,
            "attempts": spec.trials,
        },
        "agent": _agent_plan(spec, job_config),
        "environment": (
            environment.model_dump(mode="json") if environment is not None else None
        ),
        "ordering_hint": ordering_hint_metadata,
        "prompt": _prompt_plan(spec, job_config),
        "preparation": _preparation_plan(
            spec,
            job_config,
            run_dir=run_dir,
            job_config_yaml=job_config_yaml,
        ),
    }


def format_explain_markdown(plan: dict) -> str:
    agent = plan["agent"]
    prompt = plan["prompt"]
    lines = [
        "# rk run --explain",
        "",
        "Explain-only: Harbor will not be invoked and no model will run.",
        "Spec translation may materialize task views so paths and sample "
        "prompts match the real run.",
        "",
        "## Run",
        "",
        f"- Spec: `{plan['spec_path']}`",
        f"- Experiment: `{plan['experiment']}`",
        f"- Job name: `{plan['job_name']}`",
        f"- Run dir: `{plan['run_dir']}`",
        f"- Job config path: `{plan['job_config_yaml']}`",
        f"- Benchmark: `{plan['benchmark'].get('kind')}`",
        f"- Tasks: `{prompt['task_count']}`",
        f"- Concurrency: `{plan['concurrency']['trials']}`",
        "",
        "## Agent",
        "",
        f"- Spec kind: `{agent.get('spec_kind')}`",
        f"- Runtime: `{agent.get('runtime')}`",
        f"- Model: `{agent.get('model')}`",
        f"- Harbor import path: `{agent.get('harbor_import_path')}`",
        f"- Env keys: `{', '.join(agent.get('env_keys') or []) or '(none)'}`",
        f"- Kwargs: `{json.dumps(agent.get('kwargs') or {}, sort_keys=True)}`",
        "",
        "## Prompt",
        "",
        f"- Mode: `{prompt.get('mode')}`",
        f"- Task instruction application: {prompt.get('task_instruction_application')}",
    ]
    if prompt.get("solver_workflow"):
        lines.extend([
            f"- Solver workflow: `{prompt.get('solver_workflow')}`",
            f"- Workflow README: `{prompt.get('solver_workflow_readme')}`",
            f"- Workflow README found: `{prompt.get('solver_workflow_readme_found')}`",
        ])
    if prompt.get("sample_task_path"):
        lines.extend([
            f"- Sample task: `{prompt.get('sample_task_path')}`",
            f"- Sample instruction: `{prompt.get('sample_instruction_path')}`",
        ])
    lines.extend(["", "## Preparation", ""])
    lines.extend(
        f"{idx}. {step}" for idx, step in enumerate(plan["preparation"], start=1)
    )
    sample_prompt = prompt.get("sample_composed_prompt")
    if sample_prompt is not None:
        lines.extend([
            "",
            "## Sample Composed Prompt",
            "",
            "This is the exact prompt shape for the first task after task "
            "materialization and ordering. Other tasks substitute their own "
            "`instruction.md` content at the same `# Task instruction` boundary.",
            "",
            "```text",
            sample_prompt,
            "```",
        ])
    return "\n".join(lines)


def emit_run_explain(plan: dict, explain_format: str) -> None:
    if explain_format == "json":
        typer.echo(json.dumps(plan, indent=2, sort_keys=True))
        return
    if explain_format != "markdown":
        typer.echo(
            "ConfigInvalidError: --explain-format must be 'markdown' or 'json'",
            err=True,
        )
        raise typer.Exit(ExitCode.CONFIG_INVALID)
    typer.echo(format_explain_markdown(plan))
