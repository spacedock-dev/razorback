# ABOUTME: Typer application root for the `rk` binary.
# ABOUTME: Subcommands attach here; M1 wires up `rk run` only.

import typer

app = typer.Typer(help="Razorback: a benchmark runner for agentic research workflows.")
