# ABOUTME: YAML-backed registry: (kind, name) -> path.
# ABOUTME: Default location ~/.config/razorback/registry.yaml; overridable via RAZORBACK_REGISTRY.

import os
from pathlib import Path

import yaml


def registry_path(override: Path | None = None) -> Path:
    """Resolve the registry file path. Override > env > default."""
    if override is not None:
        return Path(override)
    env = os.environ.get("RAZORBACK_REGISTRY")
    if env:
        return Path(env)
    return Path.home() / ".config" / "razorback" / "registry.yaml"


def _load(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "entries": []}
    payload = yaml.safe_load(path.read_text())
    if not payload:
        return {"version": 1, "entries": []}
    payload.setdefault("entries", [])
    return payload


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload))


def _strip_at(name: str) -> str:
    return name[1:] if name.startswith("@") else name


def add(kind: str, name: str, target: str, *, override: Path | None = None) -> None:
    path = registry_path(override)
    payload = _load(path)
    n = _strip_at(name)
    payload["entries"] = [
        e for e in payload["entries"] if not (e["kind"] == kind and e["name"] == n)
    ]
    payload["entries"].append({"kind": kind, "name": n, "path": target})
    _save(path, payload)


def resolve(kind: str, name: str, *, override: Path | None = None) -> str | None:
    payload = _load(registry_path(override))
    n = _strip_at(name)
    for e in payload["entries"]:
        if e["kind"] == kind and e["name"] == n:
            return e["path"]
    return None


def list_entries(*, override: Path | None = None) -> list[dict]:
    return _load(registry_path(override))["entries"]


def remove(kind: str, name: str, *, override: Path | None = None) -> None:
    path = registry_path(override)
    payload = _load(path)
    n = _strip_at(name)
    payload["entries"] = [
        e for e in payload["entries"] if not (e["kind"] == kind and e["name"] == n)
    ]
    _save(path, payload)
