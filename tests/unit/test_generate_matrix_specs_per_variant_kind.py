# ABOUTME: PKG-26 AC-3 — generate-dab-paper-matrix-specs.py emits per-variant agent.kind:
# ABOUTME: spacedock → spacedock_solver (runtime: claude); direct-* → claude-cli (subclassed).

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    REPO_ROOT / "examples" / "drivers" / "generate-dab-paper-matrix-specs.py"
)


def _import_generator():
    """Load the dash-named script as a module so we can call build_spec()."""
    spec = importlib.util.spec_from_file_location(
        "_gen_dab_paper_matrix_specs", SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_spacedock_variant_emits_spacedock_solver_kind():
    """AC-3: spacedock cell → kind=spacedock_solver with runtime=claude."""
    gen = _import_generator()
    spec = gen.build_spec("spacedock", "bookreview")
    assert spec["agent"]["kind"] == "spacedock_solver"
    assert spec["agent"]["runtime"] == "claude"
    assert "solver_workflow" in spec["agent"]
    assert Path(spec["agent"]["solver_workflow"]).name == "dab_paper_matrix"


def test_direct_minimal_variant_emits_claude_cli_kind():
    """AC-3: direct-minimal cell → kind=claude-cli (now the ClaudeCode subclass)."""
    gen = _import_generator()
    spec = gen.build_spec("direct-minimal", "bookreview")
    assert spec["agent"]["kind"] == "claude-cli"


def test_direct_structured_variant_emits_claude_cli_kind():
    """AC-3: direct-structured cell → kind=claude-cli."""
    gen = _import_generator()
    spec = gen.build_spec("direct-structured", "agnews")
    assert spec["agent"]["kind"] == "claude-cli"


def test_spacedock_solver_workflow_path_exists():
    """The pinned solver_workflow path resolves to a real directory under the repo."""
    gen = _import_generator()
    spec = gen.build_spec("spacedock", "bookreview")
    raw = spec["agent"]["solver_workflow"]
    workflow_path = Path(raw)
    if not workflow_path.is_absolute():
        workflow_path = (REPO_ROOT / raw.lstrip("./")).resolve()
    assert workflow_path.is_dir(), f"solver_workflow path missing: {workflow_path}"
    assert (workflow_path / "README.md").is_file()


def test_spacedock_block_does_not_carry_tools_allowed_default_csv():
    """spacedock_solver's tools_allowed defaults to []; tools should be empty
    list (passes through to harbor agent kwargs) rather than the direct variants'
    explicit list. We assert it's a list so the schema accepts it.
    """
    gen = _import_generator()
    spec = gen.build_spec("spacedock", "bookreview")
    assert isinstance(spec["agent"].get("tools_allowed", []), list)


def test_workspace_variants_set_includes_all_three_kinds():
    """All three variants get generated. Ordering inherited from WORKSPACE_VARIANTS."""
    from razorback_plugin_dab.generate.workspace_readme import WORKSPACE_VARIANTS

    assert set(WORKSPACE_VARIANTS) == {
        "direct-minimal",
        "direct-structured",
        "spacedock",
    }
