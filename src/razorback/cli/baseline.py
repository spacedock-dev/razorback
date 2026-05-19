# ABOUTME: `rk baseline promote|verify` (§3.2).
# ABOUTME: promote copies 4 artifacts + constraints and verifies; verify re-runs the check.

from pathlib import Path

import typer

from razorback.constraints.baseline import promote, verify
from razorback.errors import RazorbackError

baseline_app = typer.Typer(help="Promote and verify baselines.", no_args_is_help=True)


@baseline_app.command("promote")
def promote_command(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
    target: Path = typer.Option(..., "--to"),
    constraints: Path = typer.Option(..., "--constraints", exists=True),
) -> None:
    """Copy frozen spec, summary, per-dataset scores, provenance into a baseline dir."""
    try:
        promote(run_dir=run_dir, target=target, constraints_path=constraints)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
    typer.echo(str(target))


@baseline_app.command("verify")
def verify_command(
    target: Path = typer.Argument(..., exists=True, file_okay=False),
) -> None:
    """Re-run the constraints check against the bound baseline directory."""
    try:
        verify(target)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
    typer.echo("OK")
