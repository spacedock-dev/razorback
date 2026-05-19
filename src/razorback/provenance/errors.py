# ABOUTME: Provenance typed errors with documented exit codes (§3.2 rows 11, 21).
# ABOUTME: Subclassed from RazorbackError so the CLI maps them via exc.exit_code.

from razorback.errors import ExitCode, RazorbackError


class ProvenanceError(RazorbackError):
    """One or more provenance fields could not be resolved and --allow-missing was not passed."""

    exit_code: int = ExitCode.PROVENANCE_ERROR


class AliasDriftError(RazorbackError):
    """Provider's resolved model version differs from the frozen spec's pinned value."""

    exit_code: int = ExitCode.ALIAS_DRIFT

    def __init__(self, *, model_alias: str, frozen: str, resolved: str) -> None:
        super().__init__(
            f"model alias '{model_alias}' resolved to '{resolved}', "
            f"frozen spec pinned '{frozen}'. Pass --allow-alias-drift to override."
        )
        self.model_alias = model_alias
        self.frozen = frozen
        self.resolved = resolved


class HarborDriftError(RazorbackError):
    """Installed harbor major version differs from the frozen spec's pinned harbor version."""

    exit_code: int = ExitCode.GENERIC

    def __init__(self, *, frozen: str, installed: str) -> None:
        super().__init__(
            f"harbor major-version drift: frozen={frozen}, installed={installed}. "
            f"Refusing to run."
        )
        self.frozen = frozen
        self.installed = installed
