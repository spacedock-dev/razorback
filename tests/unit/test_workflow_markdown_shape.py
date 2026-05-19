# ABOUTME: AC-2 surface check — the dab-claude example workflow markdown exists and references rk commands.

from pathlib import Path

WORKFLOW_ROOT = (
    Path(__file__).resolve().parents[2] / "examples" / "workflows" / "dab-claude"
)


def test_workflow_directory_exists():
    assert WORKFLOW_ROOT.is_dir()


def test_readme_documents_lifecycle():
    readme = (WORKFLOW_ROOT / "README.md").read_text()
    for stage in ("propose", "smoke", "full", "analyze", "conclude"):
        assert stage in readme.lower(), f"README must document stage '{stage}'"


def test_stages_markdown_names_rk_subcommands():
    stages = (WORKFLOW_ROOT / "stages.md").read_text()
    for cmd in (
        "rk validate",
        "rk spec freeze",
        "rk run",
        "rk registry resolve",
        "rk runs diff",
        "rk baseline promote",
    ):
        assert cmd in stages, f"stages.md must reference '{cmd}'"


def test_run_workflow_markdown_names_reconciling_stages():
    run_wf = (WORKFLOW_ROOT / "run-workflow.md").read_text()
    for stage in ("pending", "reconciling", "completed", "failed"):
        assert stage in run_wf.lower(), f"run-workflow.md must name stage '{stage}'"
    assert "reconcile_run_workflow" in run_wf


def test_workflow_references_dab_dev_claude_spec():
    stages = (WORKFLOW_ROOT / "stages.md").read_text()
    assert "examples/specs/dab-dev-claude.yaml" in stages or "dab-dev-claude" in stages
