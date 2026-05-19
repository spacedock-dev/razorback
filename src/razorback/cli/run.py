# ABOUTME: `rk run` Typer command. M1: parse spec, freeze, run harbor, write run-dir.
# ABOUTME: Maps razorback typed errors to documented exit codes (§3.2).

from pathlib import Path

import typer

from razorback.errors import ExitCode, RazorbackError, SpecError
from razorback.spec.parse import parse_spec_file


def run_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    runs_dir: Path = typer.Option(Path("_runs"), "--runs-dir", help="Base directory for run-dirs."),
) -> None:
    """Execute a frozen spec against harbor and write a run-dir."""
    try:
        spec = parse_spec_file(spec_path)
    except SpecError as exc:
        typer.echo(f"SpecError: {exc}", err=True)
        raise typer.Exit(ExitCode.SPEC_ERROR)

    from razorback.run import execute_run

    try:
        execute_run(spec=spec, runs_dir=runs_dir)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
