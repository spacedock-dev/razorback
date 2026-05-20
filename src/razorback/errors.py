# ABOUTME: Razorback typed errors and the documented CLI exit code map.
# ABOUTME: Stable wire surface; see design §3.2 + §3.4.

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
    BUDGET_EXCEEDED = 22
    TAINT_FINDINGS = 23
    CONFIG_INVALID = 24
    HARBOR_RUNTIME = 30


class RazorbackError(Exception):
    """Base for razorback typed errors."""
    exit_code: int = ExitCode.GENERIC


class SpecError(RazorbackError):
    exit_code: int = ExitCode.SPEC_ERROR


class SeedMismatchError(RazorbackError):
    """Halt-resume sealed-input hashes do not match the seed's frozen spec (§3.2)."""
    exit_code: int = ExitCode.SEED_MISMATCH


class ConstraintViolation(RazorbackError):
    """A spec violates a pinned field or a not-declared mutation surface (§3.2)."""
    exit_code: int = ExitCode.CONSTRAINT_VIOLATION


class BudgetExceededError(RazorbackError):
    """`--max-budget-usd-running` running-total + estimate exceeds `experiment.max_budget_usd` (§3.4)."""
    exit_code: int = ExitCode.BUDGET_EXCEEDED


class TaintFindingsError(RazorbackError):
    """`rk audit --policy strict` found at least one non-`clean` trial (§3.4)."""
    exit_code: int = ExitCode.TAINT_FINDINGS


class ConfigInvalidError(RazorbackError):
    """Configuration is structurally valid but operationally unusable (§3.4 row 24, AC-8)."""
    exit_code: int = ExitCode.CONFIG_INVALID
