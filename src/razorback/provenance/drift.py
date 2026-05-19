# ABOUTME: Run-time provenance drift checks (§6.4): re-resolve model alias, compare to frozen.
# ABOUTME: Also exposes harbor major-version drift; both fire BEFORE harbor's Job.create.

from __future__ import annotations

from typing import Any

from razorback.provenance.errors import AliasDriftError, HarborDriftError


def check_alias_drift(
    *,
    model_alias: str,
    frozen_resolved_version: str,
    client: Any,
    allow: bool,
) -> tuple[str, str]:
    """Re-resolve the model alias and compare to the frozen value.

    Returns (resolved_id, resolved_at) on no-drift or allow=True. Raises
    AliasDriftError when the resolved version differs and allow=False.
    """
    model = client.models.retrieve(model_alias)
    resolved_id = model.id
    resolved_at = (
        model.created_at if isinstance(model.created_at, str) else str(model.created_at)
    )
    if resolved_id != frozen_resolved_version:
        if not allow:
            raise AliasDriftError(
                model_alias=model_alias,
                frozen=frozen_resolved_version,
                resolved=resolved_id,
            )
    return resolved_id, resolved_at


def _installed_harbor_version() -> str:
    """Return harbor.__version__ at run-time. Wrapped for test patching."""
    import harbor

    return harbor.__version__


def check_harbor_drift(*, frozen: str, installed: str | None) -> None:
    """Refuse on harbor major-version drift between freeze and run (§6.4)."""
    if installed is None:
        installed = _installed_harbor_version()
    if _major(frozen) != _major(installed):
        raise HarborDriftError(frozen=frozen, installed=installed)


def _major(version: str) -> int:
    return int(version.split(".", 1)[0])
