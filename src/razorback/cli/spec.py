# ABOUTME: `rk spec *` Typer subcommand group. M5 adds `freeze`.

import typer

from razorback.provenance.freeze_cmd import freeze_command

app = typer.Typer(help="Spec inspection and freeze commands.")
app.command("freeze")(freeze_command)
