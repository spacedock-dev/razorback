# ABOUTME: Razorback typed errors and the documented CLI exit code map.
# ABOUTME: Stable wire surface; see design §3.2.

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    GENERIC = 1
    USAGE = 2
    SPEC_ERROR = 10
    PROVENANCE_ERROR = 11
    CONSTRAINT_VIOLATION = 12
    SEED_MISMATCH = 20
    ALIAS_DRIFT = 21
    HARBOR_RUNTIME = 30


class RazorbackError(Exception):
    """Base for razorback typed errors."""
    exit_code: int = ExitCode.GENERIC


class SpecError(RazorbackError):
    exit_code: int = ExitCode.SPEC_ERROR
