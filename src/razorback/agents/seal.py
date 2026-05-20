# ABOUTME: Sealed-input hashing for SpacedockSolverAgent halt-resume (§6.2, §6.4).
# ABOUTME: compute_sealed_hash returns the single hex string pinned into spec.frozen.yaml.

import hashlib
import json
from typing import Any


def prompt_sha256(content_bytes: bytes) -> str:
    """Return the sha256 hex of prompt file bytes, prefixed `sha256:`.

    The prefix is part of the wire format pinned into spec.frozen.yaml — readers
    can distinguish hash algorithms in future versions without breaking the field shape.
    """
    return "sha256:" + hashlib.sha256(content_bytes).hexdigest()


def compute_sealed_hash(
    *,
    model: str,
    sampling: dict[str, Any],
    stages: list[str] | None = None,
    prompt_hashes: dict[str, str] | None = None,
    solver_workflow_content_hash: str | None = None,
    prompt_content_hashes: dict[str, str] | None = None,
    spacedock_skill_version: str | None = None,
    harbor_agent_kwargs: dict[str, Any] | None = None,
) -> str:
    """Compute the sealed_hash from the v1 four-input or v2 six-input shape.

    Deterministic over a canonical JSON encoding (keys sorted at every level,
    null seed pinned not dropped). Returns the first 32 hex chars of sha256.

    v1 payload (stages + prompt_hashes) keeps the v1 SpacedockSolverAgent
    routing intact (AC-8); v2 payload (solver_workflow_content_hash +
    prompt_content_hashes + spacedock_skill_version + harbor_agent_kwargs)
    is the v2 contract from spec §4.3.5 + §8.4.
    """
    v1_shape = stages is not None or prompt_hashes is not None
    v2_shape = (
        solver_workflow_content_hash is not None
        or prompt_content_hashes is not None
        or spacedock_skill_version is not None
        or harbor_agent_kwargs is not None
    )
    if v1_shape and v2_shape:
        raise TypeError(
            "compute_sealed_hash: v1 (stages/prompt_hashes) and v2 "
            "(solver_workflow_content_hash/prompt_content_hashes/"
            "spacedock_skill_version/harbor_agent_kwargs) inputs are exclusive."
        )
    if v2_shape:
        payload = {
            "model": model,
            "sampling": _canonicalize_sampling(sampling),
            "solver_workflow_content_hash": solver_workflow_content_hash,
            "prompt_content_hashes": {
                k: (prompt_content_hashes or {})[k]
                for k in sorted(prompt_content_hashes or {})
            },
            "spacedock_skill_version": spacedock_skill_version,
            "harbor_agent_kwargs": _canonicalize_kwargs(harbor_agent_kwargs or {}),
        }
    else:
        payload = {
            "model": model,
            "sampling": _canonicalize_sampling(sampling),
            "stages": list(stages or []),
            "prompt_hashes": {
                k: (prompt_hashes or {})[k] for k in sorted(prompt_hashes or {})
            },
        }
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()[:32]


def _canonicalize_kwargs(d: dict[str, Any]) -> dict[str, Any]:
    """Return d with top-level keys sorted; values are JSON-serialisable as-is."""
    return {k: d[k] for k in sorted(d)}


def _canonicalize_sampling(sampling: dict[str, Any]) -> dict[str, Any]:
    """Coerce sampling to a canonical JSON shape.

    null/None values are pinned (not dropped): "seed is unset" is part of the seal.
    """
    return {
        "temperature": sampling.get("temperature"),
        "top_p": sampling.get("top_p"),
        "seed": sampling.get("seed"),
    }
