# ABOUTME: `rk spec freeze` Typer command — orchestrates the six resolvers (§6.4).
# ABOUTME: Writes spec.frozen.yaml (pinned spec body) + provenance.yaml (sidecar).

from __future__ import annotations

from pathlib import Path

import typer
import yaml

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
    resolve_prompt_hashes,
)
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
    cli_bin = "claude" if spec.agent.kind == "claude-cli" else spec.agent.kind
    agent_cli_hash = (
        resolve_agent_cli_hash(cli_bin) if spec.provenance.pin_agent_cli_hash else None
    )
    git_sha = (
        resolve_harness_git_sha(Path.cwd()) if spec.provenance.pin_git_sha else None
    )
    harbor_version = resolve_harbor_version()
    prompt_paths = _collect_prompt_paths(spec)
    prompt_hashes = resolve_prompt_hashes(prompt_paths)

    resolved = {
        "model_resolved_version": model_id,
        "model_resolved_at": model_at,
        "image_digest": image_digest,
        "agent_cli_hash": agent_cli_hash,
        "harness_git_sha": git_sha,
        "harbor_version": harbor_version,
        "prompt_file_hashes": prompt_hashes,
    }

    try:
        refuse_if_any_unresolved(resolved, allow_missing=allow_missing)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)

    frozen_path = out or spec_path.with_suffix(".frozen.yaml")
    frozen_body = spec.model_dump(mode="json")
    frozen_body["provenance"] = {
        **frozen_body.get("provenance", {}),
        "model_resolved_version": model_id,
        "model_resolved_at": model_at,
        "image_digest": image_digest,
        "agent_cli_hash": agent_cli_hash,
        "harness_git_sha": git_sha,
        "harbor_version": harbor_version,
        "prompt_file_hashes": prompt_hashes,
    }
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
