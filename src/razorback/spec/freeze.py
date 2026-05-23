# ABOUTME: Spec freeze — pin canonical YAML and stamp v2 solver sealed fields (§6.2).

import hashlib
from pathlib import Path

import yaml

from razorback.agents.seal import compute_sealed_hash
from razorback.spec.schema import (
    SpacedockSolverV2AgentBlock,
    Spec,
)


def freeze_spec(spec: Spec) -> str:
    """Return the canonical YAML for a parsed spec.

    For canonical spacedock_solver agents, the solver workflow content hash and
    sealed_hash are pinned (§6.2, §6.4).
    """
    payload = spec.model_dump(mode="json")

    if isinstance(spec.agent, SpacedockSolverV2AgentBlock):
        _freeze_spacedock_v2(payload["agent"], spec.agent.solver_workflow)

    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False)


def _freeze_spacedock_v2(agent_block: dict, solver_workflow: Path) -> None:
    """Compute solver_workflow_content_hash + sealed_hash for v2 (spec §4.3.5 + §8.4).

    `solver_workflow` resolves relative to cwd when not absolute.
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

def derive_job_name(frozen_text: str) -> str:
    """Content-derived job_name per §6.7: sha256(frozen)[:16] hex."""
    return hashlib.sha256(frozen_text.encode("utf-8")).hexdigest()[:16]
