# ABOUTME: `rk runs *` Typer commands (M6 lands `diff`; list/show land in M7).
# ABOUTME: Maps razorback typed errors to documented exit codes (§3.2).

import json
from pathlib import Path

import typer

from razorback.diff.diff import (
    check_paired_benchmark_kind,
    check_paired_seed_compatibility,
    compute_diff,
)
from razorback.diff.pairing import load_run_outcomes
from razorback.errors import ExitCode, RazorbackError
from razorback.runs.inspect import list_run_dirs, read_run_dir

runs_app = typer.Typer(help="Inspect and diff razorback run-dirs.", no_args_is_help=True)


@runs_app.command("list")
def list_command(
    root: Path = typer.Option(
        Path(".runs"), "--root", exists=True, file_okay=False, dir_okay=True
    ),
    experiment: str | None = typer.Option(None, "--experiment"),
) -> None:
    """List razorback run-dirs under <root>. §3.2."""
    entries = list_run_dirs(root, experiment=experiment)
    typer.echo(json.dumps(entries, indent=2))


@runs_app.command("show")
def show_command(
    run_dir: Path = typer.Argument(...),
) -> None:
    """Show one run-dir's manifest envelope + summary. §3.2."""
    try:
        payload = read_run_dir(run_dir)
    except FileNotFoundError as exc:
        typer.echo(f"run-dir missing required input: {exc}", err=True)
        raise typer.Exit(ExitCode.USAGE)
    typer.echo(json.dumps(payload, indent=2))


@runs_app.command("diff")
def diff_command(
    run_a: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    run_b: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    alpha: float = typer.Option(0.05, "--alpha", min=0.0001, max=0.5),
    bootstrap_iters: int = typer.Option(10000, "--bootstrap-iters", min=100),
    seed: int = typer.Option(0, "--seed", help="numpy RNG seed for the bootstrap"),
    fmt: str = typer.Option(
        "json",
        "--format",
        help="json (canonical) | markdown (deferred; falls back to json)",
    ),
) -> None:
    """Paired diff between two run-dirs. JSON to stdout. §6.5."""
    try:
        check_paired_benchmark_kind(run_a, run_b)
        check_paired_seed_compatibility(run_a, run_b)
        a = load_run_outcomes(run_a)
        b = load_run_outcomes(run_b)
        result = compute_diff(
            a, b, alpha=alpha, bootstrap_iters=bootstrap_iters, seed=seed,
        )
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)
    typer.echo(json.dumps(result, indent=2))
