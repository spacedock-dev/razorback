# ABOUTME: Spacedock dispatch-manifest audit coverage helpers.
# ABOUTME: Enumerates run manifest trials and fails closed on missing dispatch evidence.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


MANIFEST_NAME = "subagent-trace-manifest.json"


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_spacedock_run(run_dir: Path) -> bool:
    spec_path = run_dir / "spec.frozen.yaml"
    if not spec_path.is_file():
        return False
    try:
        payload = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return False
    agent = payload.get("agent") if isinstance(payload, dict) else None
    return isinstance(agent, dict) and agent.get("kind") == "spacedock_solver"


def listed_spacedock_trial_roots(run_dir: Path) -> list[Path]:
    if not is_spacedock_run(run_dir):
        return []
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    names = payload.get("per_trial_paths") if isinstance(payload, dict) else None
    if not isinstance(names, list):
        return []
    return [
        trial_root
        for trial_root in (run_dir / str(name) for name in names)
        if trial_root.is_dir()
    ]


def _coverage(
    status: str,
    missing_reason: str,
    source_path: Path,
    trial_root: Path,
) -> dict[str, Any]:
    return {
        "source_kind": "spacedock_dispatch_manifest",
        "source_path": _rel(source_path, trial_root),
        "trace_id": None,
        "subagent_thread_id": None,
        "stage_name": None,
        "event_id": None,
        "event_type": None,
        "tool_type": None,
        "category": "trace_coverage",
        "confidence": "high",
        "status": status,
        "missing_reason": missing_reason,
    }


def _captured_count(payload: dict[str, Any]) -> int:
    try:
        return int(payload.get("captured") or 0)
    except (TypeError, ValueError):
        return 0


def scan_trial(run_dir: Path, trial_root: Path) -> list[dict[str, Any]]:
    listed_roots = listed_spacedock_trial_roots(run_dir)
    if not listed_roots or trial_root not in listed_roots:
        return []
    per_trial = trial_root / MANIFEST_NAME
    manifest_path = per_trial
    if not per_trial.is_file() and len(listed_roots) == 1:
        manifest_path = run_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        return [
            _coverage(
                "missing",
                "spacedock_dispatch_manifest_absent",
                per_trial,
                trial_root,
            )
        ]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [
            _coverage(
                "missing",
                "spacedock_dispatch_manifest_invalid",
                manifest_path,
                trial_root,
            )
        ]
    if not isinstance(payload, dict) or _captured_count(payload) < 1:
        return [
            _coverage(
                "partial",
                "spacedock_dispatch_events_absent",
                manifest_path,
                trial_root,
            )
        ]
    return []
