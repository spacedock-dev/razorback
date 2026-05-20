# ABOUTME: `rk run` Typer command. Phase 1: parse spec, run pre-checks, delegate to harbor run.
# ABOUTME: Maps razorback typed errors to documented exit codes (§3.4).

from pathlib import Path

import typer

from razorback.errors import ExitCode, SpecError
from razorback.spec.parse import parse_spec_file


def run_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    runs_dir: Path = typer.Option(Path("_runs"), "--runs-dir", help="Base directory for run-dirs."),
    allow_alias_drift: bool = typer.Option(
        False,
        "--allow-alias-drift",
        help="Run even when provider model version differs from frozen.",
    ),
) -> None:
    """Execute a frozen spec against harbor and write a run-dir."""
    try:
        parse_spec_file(spec_path)
    except SpecError as exc:
        typer.echo(f"SpecError: {exc}", err=True)
        raise typer.Exit(ExitCode.SPEC_ERROR)

    raise RuntimeError("rk run v2 wrapper not yet implemented — Phase 1 Task 7")
