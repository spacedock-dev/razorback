# ABOUTME: Typer application root for the `rk` binary.
# ABOUTME: Subcommands attach here; M1 wires up `rk run` only.

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

from razorback.cli.spec import app as spec_app

app.add_typer(spec_app, name="spec")

from razorback.cli.runs import runs_app

app.add_typer(runs_app, name="runs")
