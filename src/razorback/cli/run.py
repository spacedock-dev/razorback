# ABOUTME: `rk run` Typer command (Phase 1 v2). Parse, pre-check, translate, delegate to harbor.
# ABOUTME: Maps razorback typed errors to documented exit codes (§3.4).

import subprocess
from pathlib import Path

import typer

from razorback.errors import (
    ConfigInvalidError,
    ExitCode,
    RazorbackError,
    SpecError,
)
from razorback.provenance.drift import check_alias_drift, check_harbor_drift
from razorback.provenance.errors import AliasDriftError
from razorback.runs_dir_canary import (
    check_runs_dir_visible,
    default_container_probe_factory,
)
from razorback.spec.freeze import derive_job_name
from razorback.spec.parse import parse_spec_file
from razorback.translate import spec_to_job_config


def _resolve_model_version(model_alias: str, frozen_resolved: str, allow_drift: bool):
    """Re-resolve via Anthropic SDK; wrapped for test patching."""
    import anthropic

    client = anthropic.Anthropic()
    return check_alias_drift(
        model_alias=model_alias,
        frozen_resolved_version=frozen_resolved,
        client=client,
        allow=allow_drift,
    )


def _run_canary(runs_dir: Path) -> None:
    """Runs-dir mount-visibility probe (AC-8); wrapped for test patching."""
    probe = default_container_probe_factory()
    check_runs_dir_visible(runs_dir, container_probe=probe)


def _invoke_harbor(job_config_yaml: Path) -> int:
    """Subprocess-invoke `harbor run -c <yaml>`; wrapped for test patching.

    Returns harbor's exit code. Razorback surfaces this as exit 30 if non-zero.
    """
    proc = subprocess.run(
        ["uv", "run", "harbor", "run", "-c", str(job_config_yaml)],
        capture_output=False,
    )
    return proc.returncode


def _write_provenance_artifacts(spec_bytes: bytes, spec, run_dir: Path) -> None:
    """AC-3: byte-for-byte echo of the input frozen spec + provenance.yaml writer.

    `spec_bytes` is the raw bytes of the input frozen spec; `spec` is its
    parsed form (used to extract the provenance block for provenance.yaml).
    """
    from razorback.provenance.provenance_yaml import write_provenance_yaml

    (run_dir / "spec.frozen.yaml").write_bytes(spec_bytes)
    frozen_provenance = spec.model_dump(mode="json").get("provenance") or {}
    if frozen_provenance:
        write_provenance_yaml(
            run_dir / "provenance.yaml", frozen_provenance, drift_record=None
        )


def run_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    runs_dir: Path = typer.Option(Path("_runs"), "--runs-dir", help="Base directory for run-dirs."),
    allow_alias_drift: bool = typer.Option(
        False,
        "--allow-alias-drift",
        help="Run even when provider model version differs from frozen.",
    ),
) -> None:
    """Execute a frozen spec against harbor and write the v2 run-dir artifacts."""
    try:
        spec = parse_spec_file(spec_path)
    except SpecError as exc:
        typer.echo(f"SpecError: {exc}", err=True)
        raise typer.Exit(ExitCode.SPEC_ERROR)

    # AC-8: runs-dir mount-visibility canary BEFORE any agent invocation.
    runs_dir_resolved = Path(runs_dir).expanduser().resolve()
    try:
        _run_canary(runs_dir_resolved)
    except ConfigInvalidError as exc:
        typer.echo(f"ConfigInvalidError: {exc}", err=True)
        raise typer.Exit(ExitCode.CONFIG_INVALID)

    # AC-2: harbor + alias-drift pre-checks.
    frozen_provenance = spec.model_dump(mode="json").get("provenance") or {}
    frozen_model = frozen_provenance.get("model_resolved_version")
    frozen_harbor = frozen_provenance.get("harbor_version")

    if frozen_harbor is not None:
        try:
            check_harbor_drift(frozen=frozen_harbor, installed=None)
        except RazorbackError as exc:
            typer.echo(f"{type(exc).__name__}: {exc}", err=True)
            raise typer.Exit(exc.exit_code)

    if frozen_model is not None:
        model_alias = getattr(spec.agent, "model", None) or "claude-opus-4-5"
        try:
            _resolve_model_version(model_alias, frozen_model, allow_alias_drift)
        except AliasDriftError as exc:
            typer.echo(f"AliasDriftError: {exc}", err=True)
            raise typer.Exit(ExitCode.ALIAS_DRIFT)

    # AC-6 + §3.1 canonicalization: jobs_dir is the absolute, symlink-resolved path.
    spec_bytes = spec_path.read_bytes()
    job_name = derive_job_name(spec_bytes.decode("utf-8"))
    run_dir = runs_dir_resolved / spec.experiment / job_name
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        job_config, _ = spec_to_job_config(
            spec,
            job_name=job_name,
            jobs_dir=run_dir.parent,
            tasks_root=run_dir / "tasks",
            project_root=Path.cwd(),
        )
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)

    job_config_yaml = run_dir / "_job_config.yaml"
    job_config_yaml.write_text(job_config.model_dump_json(indent=2))

    rc = _invoke_harbor(job_config_yaml)
    if rc != 0:
        typer.echo(f"harbor run failed (exit {rc}); surfacing as exit 30", err=True)
        raise typer.Exit(ExitCode.HARBOR_RUNTIME)

    # AC-3 (Task 8 finishes the writer): write spec.frozen.yaml + provenance.yaml.
    _write_provenance_artifacts(spec_bytes, spec, run_dir)
