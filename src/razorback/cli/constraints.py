# ABOUTME: `rk constraints *` Typer commands.
# ABOUTME: Exit code 12 (ConstraintViolation) on a pinned mismatch or undeclared surface.

from pathlib import Path

import typer
import yaml

from razorback.constraints.check import check_spec_against_constraints
from razorback.errors import RazorbackError

constraints_app = typer.Typer(help="Constraints file checks.", no_args_is_help=True)


@constraints_app.command("check")
def check_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    constraints_path: Path = typer.Option(
        ..., "--constraints", exists=True, dir_okay=False,
    ),
    baseline_path: Path = typer.Option(
        None,
        "--baseline",
        exists=True,
        dir_okay=False,
        help="Optional baseline spec for mutation-surface coverage.",
    ),
) -> None:
    """Verify a spec against a constraints file. Exit code 12 on violation (§3.2)."""
    spec = yaml.safe_load(spec_path.read_text())
    constraints = yaml.safe_load(constraints_path.read_text())
    baseline = yaml.safe_load(baseline_path.read_text()) if baseline_path else None
    try:
        check_spec_against_constraints(spec, constraints, baseline=baseline)
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
    typer.echo("OK")
