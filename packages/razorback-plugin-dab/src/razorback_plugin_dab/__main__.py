# ABOUTME: Module entry-point so `python -m razorback_plugin_dab …` works.
# ABOUTME: Delegates to the Typer app in cli.py.

from razorback_plugin_dab.cli import app

if __name__ == "__main__":
    app()
