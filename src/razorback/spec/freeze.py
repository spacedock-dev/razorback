# ABOUTME: Spec freeze — pin canonical YAML; for spacedock-solver content-hash prompt
# ABOUTME: files (§6.4) and stamp sealed_hash (§6.2).

import hashlib
from pathlib import Path

import yaml

from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.spec.schema import SpacedockSolverAgentBlock, Spec


def freeze_spec(spec: Spec) -> str:
    """Return the canonical YAML for a parsed spec.

    For spacedock-solver agents, prompt file paths are read and replaced with
    `sha256:` strings; bodies are embedded under `prompt_contents`; `sealed_hash`
    is pinned (§6.2, §6.4).
    """
    payload = spec.model_dump(mode="json")

    if isinstance(spec.agent, SpacedockSolverAgentBlock):
        _freeze_spacedock_prompts(payload["agent"])
        payload["agent"]["sealed_hash"] = compute_sealed_hash(
            model=payload["agent"]["model"],
            sampling=payload["agent"]["sampling"],
            stages=payload["agent"]["stages"],
            prompt_hashes=payload["agent"]["prompts"],
        )

    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)


def _freeze_spacedock_prompts(agent_block: dict) -> None:
    """Replace prompts.<stage> file paths with sha256: strings; embed bodies under prompt_contents."""
    prompts = agent_block.get("prompts") or {}
    contents: dict[str, str] = {}
    resolved: dict[str, str] = {}
    for stage, value in prompts.items():
        if isinstance(value, str) and value.startswith("sha256:"):
            existing = (agent_block.get("prompt_contents") or {}).get(stage)
            if existing is None:
                raise ValueError(
                    f"agent.prompts.{stage} is pre-hashed but prompt_contents.{stage} is missing"
                )
            resolved[stage] = value
            contents[stage] = existing
            continue
        path = Path(value)
        if not path.is_absolute():
            path = Path.cwd() / path
        body = path.read_bytes()
        resolved[stage] = prompt_sha256(body)
        contents[stage] = body.decode("utf-8")
    agent_block["prompts"] = resolved
    agent_block["prompt_contents"] = contents


def derive_job_name(frozen_text: str) -> str:
    """Content-derived job_name per §6.7: sha256(frozen)[:16] hex."""
    return hashlib.sha256(frozen_text.encode("utf-8")).hexdigest()[:16]
