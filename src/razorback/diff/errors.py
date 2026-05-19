# ABOUTME: Razorback diff package typed errors. Currently: BenchmarkMismatchError (AC-6).

from razorback.errors import ExitCode, RazorbackError


class BenchmarkMismatchError(RazorbackError):
    """`rk runs diff` was asked to pair runs from different benchmarks. §3.2 row 12."""

    exit_code: int = ExitCode.CONSTRAINT_VIOLATION

    def __init__(self, *, run_a_kind: str, run_b_kind: str) -> None:
        super().__init__(
            f"cross-benchmark diff refused: run A is benchmark.kind={run_a_kind!r}, "
            f"run B is benchmark.kind={run_b_kind!r}. Pairing requires the same benchmark surface."
        )
        self.run_a_kind = run_a_kind
        self.run_b_kind = run_b_kind
