# ABOUTME: PKG-38 generator checks for Goal 1 Claude DAB matrix specs.
# ABOUTME: New generated Claude benchmark specs use solver v2 instead of claude-cli.

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


def test_goal1_claude_specs_use_solver_v2_runtime_claude():
    generator = _load_generator()

    payload = generator.build_spec("direct-minimal", "bookreview")

    assert payload["agent"]["kind"] == "spacedock_solver_v2"
    assert payload["agent"]["runtime"] == "claude"
    assert payload["agent"]["model"] == "claude-opus-4-7"
    assert (
        payload["agent"]["solver_workflow"]
        == "./examples/solver_workflows/claude-benchmark-solver"
    )
    assert payload["agent"]["spacedock_skill_version"] == "1.0.0"
    assert payload["benchmark"]["kind"] == "harbor_dab"
    assert payload["benchmark"]["datasets"] == ["bookreview"]
    assert payload["benchmark"]["workspace_variant"] == "direct-minimal"
    assert payload["benchmark"]["hints"] is True
    assert "claude-cli" not in repr(payload["agent"])
