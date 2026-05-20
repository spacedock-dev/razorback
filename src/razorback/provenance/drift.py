# ABOUTME: Run-time provenance drift checks (§6.4 + §8.2): re-resolve model alias and plugin
# ABOUTME: inventory, compare to frozen; harbor major-version drift; all fire pre-Job.create.

from __future__ import annotations

from typing import Any, Callable

from razorback.provenance.errors import (
    AliasDriftError,
    HarborDriftError,
    ProvenanceError,
)
from razorback.provenance.resolvers import resolve_plugin_inventory


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


# PKG-8 v2 §3.2 + AC-3: refuse with exit 11 on plugin drift between freeze and run.
def check_plugin_drift(
    *,
    frozen: list[dict[str, Any]] | None,
    resolver: Callable[[], dict[str, Any]] | None = None,
    allow: bool = False,
) -> dict[str, Any] | None:
    """Compare the frozen plugins list against the live entry-point inventory.

    `frozen` is `spec.frozen.yaml.provenance.plugins`. When `frozen` is None
    (pre-PKG-8 frozen specs), the check is a no-op. When the resolved inventory
    differs from `frozen` by any (group, name, distribution, version) row,
    raises ProvenanceError(exit 11) unless `allow=True`, in which case returns
    a `{"frozen": ..., "resolved": ...}` record for provenance.yaml to write
    under `plugin_drift:`.
    """
    if frozen is None:
        return None
    if resolver is None:
        resolver = resolve_plugin_inventory
    resolved_block = resolver()
    resolved_rows = (resolved_block or {}).get("plugins", [])
    drifted_keys = _diff_plugin_rows(frozen, resolved_rows)
    if not drifted_keys:
        return None
    if not allow:
        names = ", ".join(f"{group}/{name}" for group, name in drifted_keys)
        raise ProvenanceError(
            f"plugin drift: {names}; pass --allow-plugin-drift to override."
        )
    return {"frozen": frozen, "resolved": resolved_rows}


def _diff_plugin_rows(
    frozen: list[dict[str, Any]], resolved: list[dict[str, Any]]
) -> list[tuple[str, str]]:
    """Return sorted (group, name) keys for rows that differ between frozen and resolved."""

    def _key(row: dict[str, Any]) -> tuple[str, str]:
        return (row.get("group", ""), row.get("name", ""))

    def _value(row: dict[str, Any]) -> tuple[str, str]:
        return (row.get("distribution", ""), row.get("version", ""))

    frozen_by_key = {_key(r): _value(r) for r in frozen}
    resolved_by_key = {_key(r): _value(r) for r in resolved}
    keys = set(frozen_by_key) | set(resolved_by_key)
    drifted: list[tuple[str, str]] = []
    for k in keys:
        if frozen_by_key.get(k) != resolved_by_key.get(k):
            drifted.append(k)
    return sorted(drifted)
