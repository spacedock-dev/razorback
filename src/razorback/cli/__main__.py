# ABOUTME: Allows `python -m razorback.cli ...` to invoke the Typer app.
# ABOUTME: Used by the integration test harness.

from razorback.cli import app

if __name__ == "__main__":
    app()
