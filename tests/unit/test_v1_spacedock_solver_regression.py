# ABOUTME: AC-8, v1 SpacedockSolverAgent still functional under kind: spacedock-solver.
# ABOUTME: v1 sealed_hash computation + class construction routing unchanged by Phase 3.

import yaml

from razorback.agents.seal import compute_sealed_hash
from razorback.spec.schema import Spec, SpacedockSolverAgentBlock
from razorback.translate import SPACEDOCK_SOLVER_IMPORT_PATH, spec_to_job_config


def test_v1_sealed_hash_four_input_shape_unchanged():
    """AC-8: v1 sealed_hash via stages + prompt_hashes still produces a deterministic value."""
    sealed = compute_sealed_hash(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        prompt_hashes={
            "model": "sha256:" + "a" * 64,
            "analyze": "sha256:" + "b" * 64,
            "verify": "sha256:" + "c" * 64,
        },
    )
    assert len(sealed) == 32
    assert all(c in "0123456789abcdef" for c in sealed)


def test_v1_spec_routes_to_v1_class_import_path(tmp_path):
    """AC-8: spec.agent.kind: spacedock-solver routes to v1's SpacedockSolverAgent."""
    spec_yaml = """
version: 1
experiment: v1-regression
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  stages: [model, analyze, verify]
  tools_allowed: [Bash, Read]
  prompts:
    model: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    analyze: "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    verify: "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
  prompt_contents:
    model: "stage1 body"
    analyze: "stage2 body"
    verify: "stage3 body"
  sealed_hash: "deadbeefcafebabe0123456789abcdef"
benchmark:
  kind: local
  task_paths: []
trials: 1
"""
    spec = Spec.model_validate(yaml.safe_load(spec_yaml))
    assert isinstance(spec.agent, SpacedockSolverAgentBlock)
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".env").write_text("ANTHROPIC_API_KEY=sk-fake\n")
    home = tmp_path / "home"
    home.mkdir()
    cfg, _ = spec_to_job_config(
        spec=spec,
        job_name="v1-regression",
        jobs_dir=tmp_path / "_runs",
        project_root=project_root,
        home=home,
    )
    assert cfg.agents[0].import_path == SPACEDOCK_SOLVER_IMPORT_PATH


def test_v1_class_constructs_with_v1_kwargs(tmp_path):
    """AC-8: v1 class still constructs from v1 kwargs without invoking v2 code paths."""
    from razorback.agents.spacedock_solver import SpacedockSolverAgent

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    agent = SpacedockSolverAgent(
        logs_dir=logs_dir,
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=[],
        prompts={
            "model": "sha256:" + "a" * 64,
            "analyze": "sha256:" + "b" * 64,
            "verify": "sha256:" + "c" * 64,
        },
        prompt_contents={"model": "x", "analyze": "y", "verify": "z"},
        sealed_hash="deadbeef" * 4,
        extra_env={"ANTHROPIC_API_KEY": "sk-fake"},
    )
    assert agent.sealed_hash == "deadbeef" * 4
    assert agent.name() == "spacedock-solver"
