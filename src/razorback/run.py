# ABOUTME: Run orchestrator — wires spec → freeze → harbor → drainer → run-dir.
# ABOUTME: Stubbed in Task 6; the live harbor call lands in Task 10.

from pathlib import Path

from razorback.errors import RazorbackError
from razorback.spec.schema import Spec


def execute_run(*, spec: Spec, runs_dir: Path) -> None:
    raise RazorbackError("execute_run not implemented yet — see Task 10")
