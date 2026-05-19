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
    stages: list[str],
    prompt_hashes: dict[str, str],
) -> str:
    """Compute the M4 sealed_hash from the four sealed fields.

    Deterministic over a canonical JSON encoding:
    - keys sorted alphabetically at every level,
    - prompt_hashes keys sorted,
    - stages list order preserved (the order IS part of the seal).

    Returns the first 32 hex chars of the sha256 digest.
    """
    payload = {
        "model": model,
        "sampling": _canonicalize_sampling(sampling),
        "stages": list(stages),
        "prompt_hashes": {k: prompt_hashes[k] for k in sorted(prompt_hashes)},
    }
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()[:32]


def _canonicalize_sampling(sampling: dict[str, Any]) -> dict[str, Any]:
    """Coerce sampling to a canonical JSON shape.

    null/None values are pinned (not dropped): "seed is unset" is part of the seal.
    """
    return {
        "temperature": sampling.get("temperature"),
        "top_p": sampling.get("top_p"),
        "seed": sampling.get("seed"),
    }
