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
)


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
) -> None:
    """Serialize the resolved-field dict to provenance.yaml.

    Unresolved fields (value=None) are written as a list under `unresolved:`.
    `drift_record` records alias-drift overrides (§6.4) recorded by `rk run`.
    """
    document: dict[str, Any] = {}
    unresolved: list[str] = []
    for name in REQUIRED_FIELDS:
        val = resolved.get(name)
        if val is None:
            unresolved.append(name)
        else:
            document[name] = val
    if "model_resolved_at" in resolved and resolved["model_resolved_at"] is not None:
        document["model_resolved_at"] = resolved["model_resolved_at"]
    if unresolved:
        document["unresolved"] = sorted(unresolved)
    if drift_record is not None:
        document["alias_drift"] = drift_record
    out_path.write_text(yaml.safe_dump(document, sort_keys=False, default_flow_style=False))
