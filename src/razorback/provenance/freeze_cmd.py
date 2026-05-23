# ABOUTME: `rk spec freeze` Typer command — orchestrates the per-field resolvers (§6.4, §8.2).
# ABOUTME: Writes spec.frozen.yaml (pinned spec body) + provenance.yaml (sidecar).
# Pass-through-only: experiment_meta block (incl. estimated_cost_usd) is a static
# operator field, not a rk freeze-computed dynamic input; r4 phase4a-rk-run-budget-gate
# owns the schema. PKG-8 carries it through verbatim via spec.model_dump.

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
import yaml

from razorback.agents.seal import compute_sealed_hash
from razorback.errors import RazorbackError
from razorback.provenance.provenance_yaml import (
    refuse_if_any_unresolved,
    write_provenance_yaml,
)
from razorback.provenance.resolvers import (
    resolve_agent_cli_hash,
    resolve_harbor_version,
    resolve_harness_git_sha,
    resolve_image_digest,
    resolve_model_version,
    resolve_plugin_inventory,
    resolve_prompt_hashes,
    resolve_solver_workflow_hash,
)
from razorback.spec.agent_kwargs import build_v2_harbor_agent_kwargs
from razorback.spec.parse import parse_spec_file


def freeze_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    out: Path | None = typer.Option(
        None, "--out", help="Frozen spec path. Default: <spec>.frozen.yaml."
    ),
    allow_missing: bool = typer.Option(
        False, "--allow-missing", help="Write even with unresolved fields."
    ),
) -> None:
    """Resolve every dynamic input in the spec and write spec.frozen.yaml + provenance.yaml."""
    try:
        spec = parse_spec_file(spec_path)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)

    model_alias = getattr(spec.agent, "model", None) or "claude-opus-4-5"
    try:
        model_id, model_at = resolve_model_version(model_alias)
    except Exception:
        model_id, model_at = None, None

    image_ref = getattr(spec.benchmark, "image", None) or "dab-agent"
    image_digest = (
        resolve_image_digest(image_ref) if spec.provenance.pin_image_digest else None
    )
    cli_bin = _agent_cli_bin(spec)
    agent_cli_hash = (
        resolve_agent_cli_hash(cli_bin) if spec.provenance.pin_agent_cli_hash else None
    )
    git_sha = (
        resolve_harness_git_sha(Path.cwd()) if spec.provenance.pin_git_sha else None
    )
    harbor_version = resolve_harbor_version()
    prompt_paths = _collect_prompt_paths(spec)
    prompt_hashes = resolve_prompt_hashes(prompt_paths)
    # PKG-8 v2 (§3.2 + §8.2): plugin inventory + solver_workflow content hash.
    plugin_inventory = resolve_plugin_inventory()
    plugins = plugin_inventory["plugins"] if plugin_inventory is not None else None
    sw_path = _solver_workflow_path(spec)
    solver_workflow_hash = (
        resolve_solver_workflow_hash(sw_path) if sw_path is not None else None
    )

    resolved = {
        "model_resolved_version": model_id,
        "model_resolved_at": model_at,
        "image_digest": image_digest,
        "agent_cli_hash": agent_cli_hash,
        "harness_git_sha": git_sha,
        "harbor_version": harbor_version,
        "prompt_file_hashes": prompt_hashes,
        "plugins": plugins,
        "solver_workflow_hash": solver_workflow_hash,
    }

    try:
        refuse_if_any_unresolved(resolved, allow_missing=allow_missing)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)

    frozen_path = out or spec_path.with_suffix(".frozen.yaml")
    frozen_body = spec.model_dump(mode="json")
    _stamp_v2_sealed_fields(
        frozen_body,
        solver_workflow_hash=solver_workflow_hash,
    )
    frozen_provenance_block: dict[str, Any] = {
        **frozen_body.get("provenance", {}),
        "model_resolved_version": model_id,
        "model_resolved_at": model_at,
        "image_digest": image_digest,
        "agent_cli_hash": agent_cli_hash,
        "harness_git_sha": git_sha,
        "harbor_version": harbor_version,
        "prompt_file_hashes": prompt_hashes,
        "plugins": plugins,
    }
    if solver_workflow_hash is not None:
        frozen_provenance_block["solver_workflow_hash"] = solver_workflow_hash
    frozen_body["provenance"] = frozen_provenance_block

    frozen_path.write_text(yaml.safe_dump(frozen_body, sort_keys=False))

    write_provenance_yaml(spec_path.parent / "provenance.yaml", resolved)
    typer.echo(f"wrote {frozen_path}")
    typer.echo(f"wrote {spec_path.parent / 'provenance.yaml'}")


def _collect_prompt_paths(spec) -> list[Path]:
    """Walk the spec for prompt_file references. M5 covers the agent block only."""
    paths: list[Path] = []
    pf = getattr(spec.agent, "prompt_file", None)
    if pf:
        paths.append(Path(pf))
    return paths


def _solver_workflow_path(spec) -> Path | None:
    """Return the spec's solver_workflow directory path, or None when not set.

    Only spec.agent kinds that opt into a solver_workflow surface set this
    attribute (spec §8.2). Non-spacedock agents return None and the
    solver_workflow_hash field stays absent from provenance.yaml.
    """
    raw = getattr(spec.agent, "solver_workflow", None)
    return Path(raw) if raw else None


def _agent_cli_bin(spec) -> str:
    if spec.agent.kind == "claude-cli":
        return "claude"
    if spec.agent.kind == "spacedock_solver_v2":
        return "codex" if spec.agent.runtime == "codex" else spec.agent.runtime
    return spec.agent.kind


def _stamp_v2_sealed_fields(
    frozen_body: dict[str, Any],
    *,
    solver_workflow_hash: str | None,
) -> None:
    agent = frozen_body.get("agent") or {}
    if agent.get("kind") != "spacedock_solver_v2":
        return
    if solver_workflow_hash is not None:
        agent["solver_workflow_content_hash"] = solver_workflow_hash
    if agent.get("spacedock_skill_version") is None:
        agent["spacedock_skill_version"] = "1.0.0"
    harbor_agent_kwargs = build_v2_harbor_agent_kwargs(
        max_turns=agent.get("max_turns"),
        tools_allowed=agent.get("tools_allowed"),
        tools_denied=agent.get("tools_denied"),
        append_system_prompt=agent.get("append_system_prompt"),
        reasoning_effort=agent.get("reasoning_effort"),
        reasoning_summary=agent.get("reasoning_summary"),
    )
    agent["sealed_hash"] = compute_sealed_hash(
        model=agent["model"],
        sampling=agent["sampling"],
        solver_workflow_content_hash=agent.get("solver_workflow_content_hash"),
        prompt_content_hashes=dict(agent.get("prompt_content_hashes") or {}),
        spacedock_skill_version=agent.get("spacedock_skill_version"),
        harbor_agent_kwargs=harbor_agent_kwargs,
    )
