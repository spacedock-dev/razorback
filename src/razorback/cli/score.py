# ABOUTME: `rk score <run-dir>` Typer subcommand — single-run statistical readout.
# ABOUTME: Spec §3.2 surface; delegates to runs/aggregate.py for the headline number.

from __future__ import annotations

from pathlib import Path

import typer

from razorback.errors import ExitCode, RazorbackError
from razorback.runs.aggregate import read_trial_outcomes, reduce_per_query_stratified
from razorback.score.render import render_json, render_markdown
from razorback.score.verdict import AgainstConstantReport, against_constant


def score_command(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    alpha: float = typer.Option(0.05, "--alpha", min=0.0001, max=0.5),
    fmt: str = typer.Option("json", "--format", help="json (canonical) | markdown"),
    against: str | None = typer.Option(
        None,
        "--against-constant",
        help="name=value paper-reproduction comparison (e.g. paper=0.577)",
    ),
) -> None:
    """rk score <run-dir>: per-query Wilson CIs + stratified pass@1 mean. §3.2."""
    if fmt not in {"json", "markdown"}:
        raise typer.BadParameter(
            f"--format must be 'json' or 'markdown', got '{fmt}'"
        )

    constant_name: str | None = None
    constant_value: float | None = None
    if against is not None:
        if "=" not in against:
            raise typer.BadParameter(
                f"--against-constant must be name=value, got '{against}'"
            )
        constant_name, raw_value = against.split("=", 1)
        try:
            constant_value = float(raw_value)
        except ValueError as exc:
            raise typer.BadParameter(
                f"--against-constant value must be a float, got '{raw_value}'"
            ) from exc

    try:
        outcomes = read_trial_outcomes(run_dir)
        report = reduce_per_query_stratified(outcomes, alpha=alpha)
    except RazorbackError as exc:
        typer.echo(f"score error: {exc}", err=True)
        raise typer.Exit(int(exc.exit_code))

    verdict: AgainstConstantReport | None = None
    if constant_name is not None and constant_value is not None:
        verdict = against_constant(report, name=constant_name, value=constant_value)

    output = render_json(report, verdict) if fmt == "json" else render_markdown(report, verdict)
    typer.echo(output)
    raise typer.Exit(ExitCode.OK)
