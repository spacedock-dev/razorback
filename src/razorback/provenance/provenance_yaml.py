# ABOUTME: provenance.yaml writer + refusal predicate (§6.4).
# ABOUTME: A field with value None is the sentinel for unresolved.

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from razorback.provenance.errors import ProvenanceError


REQUIRED_FIELDS = (
    "model_resolved_version",
    "image_digest",
    "agent_cli_hash",
    "harness_git_sha",
    "harbor_version",
    "prompt_file_hashes",
    "plugins",
)

# Optional fields: written when non-None, never appear in REQUIRED_FIELDS or in
# the `unresolved:` list. solver_workflow_hash is conditional on the spec
# carrying an agent.solver_workflow path (spec §8.2; only spacedock_solver
# specs do today).
OPTIONAL_FIELDS = ("solver_workflow_hash",)


def refuse_if_any_unresolved(resolved: dict[str, Any], *, allow_missing: bool) -> None:
    """Raise ProvenanceError if any required field's value is None."""
    if allow_missing:
        return
    missing: list[str] = [name for name in REQUIRED_FIELDS if resolved.get(name) is None]
    if missing:
        raise ProvenanceError(
            f"unresolved provenance fields: {', '.join(missing)}. "
            f"Pass --allow-missing to write anyway (will be tagged in provenance.yaml)."
        )


def write_provenance_yaml(
    out_path: Path,
    resolved: dict[str, Any],
    *,
    drift_record: dict[str, Any] | None = None,
    plugin_drift_record: dict[str, Any] | None = None,
    ordering_hint: dict[str, Any] | None = None,
) -> None:
    """Serialize the resolved-field dict to provenance.yaml.

    Unresolved REQUIRED_FIELDS (value=None) are written as a list under
    `unresolved:`. OPTIONAL_FIELDS (solver_workflow_hash) are written only when
    non-None and never appear under `unresolved:`. `drift_record` records
    alias-drift overrides (§6.4); `plugin_drift_record` records plugin-drift
    overrides (PKG-8 §3.2).
    """
    document: dict[str, Any] = {}
    unresolved: list[str] = []
    for name in REQUIRED_FIELDS:
        val = resolved.get(name)
        if val is None:
            unresolved.append(name)
        else:
            document[name] = val
    for name in OPTIONAL_FIELDS:
        val = resolved.get(name)
        if val is not None:
            document[name] = val
    if "model_resolved_at" in resolved and resolved["model_resolved_at"] is not None:
        document["model_resolved_at"] = resolved["model_resolved_at"]
    if unresolved:
        document["unresolved"] = sorted(unresolved)
    if drift_record is not None:
        document["alias_drift"] = drift_record
    if plugin_drift_record is not None:
        document["plugin_drift"] = plugin_drift_record
    if ordering_hint is not None:
        document["ordering_hint"] = ordering_hint
    out_path.write_text(yaml.safe_dump(document, sort_keys=False, default_flow_style=False))
