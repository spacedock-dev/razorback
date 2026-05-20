# ABOUTME: Typer application root for the `rk` binary.
# ABOUTME: Subcommands attach here; v2 wires up `rk run` only at Phase 1.

import typer

from razorback.cli.run import run_command

app = typer.Typer(
    help="Razorback: a benchmark runner for agentic research workflows.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Anchor the Typer app so single-command apps still expose `rk run`."""


app.command("run")(run_command)

from razorback.audit.cli import audit_command

app.command("audit")(audit_command)

from razorback.cli.runs import runs_app

app.add_typer(runs_app, name="runs")

from razorback.cli.constraints import constraints_app

app.add_typer(constraints_app, name="constraints")

from razorback.cli.baseline import baseline_app

app.add_typer(baseline_app, name="baseline")

from razorback.cli.registry import registry_app

app.add_typer(registry_app, name="registry")
