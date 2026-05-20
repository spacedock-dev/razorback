# ABOUTME: PKG-17 AC-5 — read harbor's lock.json + diff against provenance.yaml.
# ABOUTME: Surface drift records for rk runs show; harbor writes lock.json itself.

from __future__ import annotations

import json
from pathlib import Path

import yaml


def compute_drift(run_dir: Path) -> dict | None:
    """Return a drift record when the lock fingerprint disagrees with provenance.

    Today this checks `harbor.version` against `provenance.yaml::harbor_version`.
    Future fields (image_digest, agent_cli_hash, model_resolved_version) follow
    the same pattern; expand the comparison map below when freeze-time pinning
    lands runtime resolution.
    """
    lock_path = run_dir / "lock.json"
    prov_path = run_dir / "provenance.yaml"
    if not lock_path.exists() or not prov_path.exists():
        return None

    try:
        lock = json.loads(lock_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    try:
        prov = yaml.safe_load(prov_path.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return None

    lock_harbor = (lock.get("harbor") or {}).get("version")
    prov_harbor = prov.get("harbor_version")
    if prov_harbor is not None and lock_harbor is not None and prov_harbor != lock_harbor:
        return {
            "field": "harbor_version",
            "provenance": prov_harbor,
            "lock": lock_harbor,
        }
    return None
