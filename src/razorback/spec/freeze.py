# ABOUTME: Spec freeze — pin canonical YAML; for spacedock-solver content-hash prompt
# ABOUTME: files (§6.4) and stamp sealed_hash (§6.2).

import hashlib
from pathlib import Path

import yaml

from razorback.agents.seal import compute_sealed_hash, prompt_sha256
from razorback.spec.schema import (
    SpacedockSolverAgentBlock,
    SpacedockSolverV2AgentBlock,
    Spec,
)


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

    if isinstance(spec.agent, SpacedockSolverV2AgentBlock):
        _freeze_spacedock_v2(payload["agent"], spec.agent.solver_workflow)

    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)


def _freeze_spacedock_v2(agent_block: dict, solver_workflow: Path) -> None:
    """Compute solver_workflow_content_hash + sealed_hash for v2 (spec §4.3.5 + §8.4).

    `solver_workflow` resolves relative to cwd when not absolute (mirrors the
    v1 prompt-path resolution at _freeze_spacedock_prompts:50).
    """
    workflow_path = solver_workflow
    if not workflow_path.is_absolute():
        workflow_path = Path.cwd() / workflow_path

    if agent_block.get("solver_workflow_content_hash") is None:
        agent_block["solver_workflow_content_hash"] = _dir_content_hash(workflow_path)

    if agent_block.get("spacedock_skill_version") is None:
        agent_block["spacedock_skill_version"] = "1.0.0"

    harbor_agent_kwargs = {
        "max_turns": agent_block.get("max_turns"),
        "tools_allowed": list(agent_block.get("tools_allowed") or []),
        "tools_denied": list(agent_block.get("tools_denied") or []),
    }
    if agent_block.get("append_system_prompt") is not None:
        harbor_agent_kwargs["append_system_prompt"] = agent_block["append_system_prompt"]

    agent_block["sealed_hash"] = compute_sealed_hash(
        model=agent_block["model"],
        sampling=agent_block["sampling"],
        solver_workflow_content_hash=agent_block["solver_workflow_content_hash"],
        prompt_content_hashes=dict(agent_block.get("prompt_content_hashes") or {}),
        spacedock_skill_version=agent_block["spacedock_skill_version"],
        harbor_agent_kwargs=harbor_agent_kwargs,
    )


def _dir_content_hash(path: Path) -> str:
    """sha256 hash over (relative-path, file-bytes) tuples in sorted order."""
    h = hashlib.sha256()
    if not path.is_dir():
        raise ValueError(f"solver_workflow path is not a directory: {path}")
    for entry in sorted(path.rglob("*")):
        if not entry.is_file():
            continue
        rel = entry.relative_to(path).as_posix().encode("utf-8")
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        body = entry.read_bytes()
        h.update(len(body).to_bytes(8, "big"))
        h.update(body)
    return "sha256:" + h.hexdigest()


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
