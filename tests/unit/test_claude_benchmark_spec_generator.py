# ABOUTME: PKG-38 generator checks for Goal 1 Claude DAB matrix specs.
# ABOUTME: Direct variants use claude-cli; spacedock variant uses canonical solver.

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "examples" / "drivers" / "generate-dab-paper-matrix-specs.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("claude_goal1_specs", GENERATOR)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_goal1_claude_specs_use_per_variant_agent_kind():
    generator = _load_generator()

    direct = generator.build_spec("direct-minimal", "bookreview")
    spacedock = generator.build_spec("spacedock", "bookreview")

    assert direct["agent"]["kind"] == "claude-cli"
    assert direct["agent"]["model"] == "claude-opus-4-7"
    assert direct["benchmark"]["kind"] == "harbor_dab"
    assert direct["benchmark"]["datasets"] == ["bookreview"]
    assert direct["benchmark"]["workspace_variant"] == "direct-minimal"
    assert direct["benchmark"]["hints"] is True
    assert direct["benchmark"]["query_mode"] == "batch"

    assert spacedock["agent"]["kind"] == "spacedock_solver"
    assert spacedock["agent"]["runtime"] == "claude"
    assert spacedock["agent"]["model"] == "claude-opus-4-7"
    assert spacedock["agent"]["solver_workflow"] == (
        "./examples/solver_workflows/dab_paper_matrix"
    )
