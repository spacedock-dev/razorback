# ABOUTME: Phase 5 / AC-2 + AC-5 — per-stage prompt-content lints.
# ABOUTME: Asserts named guidance phrases appear verbatim in the experiment-workflow template's stage prompts.

from __future__ import annotations

import importlib.resources


def _read_template_text() -> str:
    """Return the experiment-workflow README text from the installed package."""
    return (
        importlib.resources.files("razorback")
        .joinpath("templates", "experiment-workflow", "README.md")
        .read_text(encoding="utf-8")
    )


def _read_run_template_text() -> str:
    return (
        importlib.resources.files("razorback")
        .joinpath("templates", "run-workflow", "README.md")
        .read_text(encoding="utf-8")
    )


# --- AC-2: stage frontmatter / skeleton ---------------------------------


def test_experiment_workflow_has_six_stages_in_order():
    """AC-2: pending, propose, smoke, full, analyze, conclude — in order."""
    text = _read_template_text()
    expected = ["pending", "propose", "smoke", "full", "analyze", "conclude"]
    positions = []
    for name in expected:
        marker = f"## Stage: {name}"
        idx = text.find(marker)
        assert idx >= 0, f"missing '{marker}' in experiment-workflow README"
        positions.append(idx)
    assert positions == sorted(positions), (
        f"stage sections out of order; positions={positions}"
    )


def test_experiment_workflow_declares_id_style_sd_b32():
    """AC-2: sd-b32 ID style."""
    assert "id-style: sd-b32" in _read_template_text()


def test_experiment_workflow_declares_max_budget_usd():
    """AC-2: experiment.max_budget_usd declared in template spec."""
    assert "experiment.max_budget_usd" in _read_template_text()


# --- AC-2: propose-stage leak-guard prose (k3 scope) ---------------------


def test_propose_stage_lists_internal_leak_surfaces():
    text = _read_template_text()
    for phrase in ("answer keys", "ground-truth columns", "per-task hints"):
        assert phrase in text, f"propose stage missing internal-leak phrase: {phrase!r}"


def test_propose_stage_lists_external_oracle_surfaces():
    text = _read_template_text()
    for phrase in (
        "datasets.load_dataset",
        "hf://",
        "public CSV",
        "web-search",
        "cached prior answers",
    ):
        assert phrase in text, (
            f"propose stage missing external-oracle phrase: {phrase!r}"
        )


def test_propose_stage_cites_workspace_readme_canonical_prose():
    text = _read_template_text()
    assert "workspace_readme.py" in text, (
        "propose stage must cite packages/.../workspace_readme.py as canonical "
        "leak-guard prose"
    )


def test_propose_stage_states_unable_to_determine_sentinel():
    """AC-5 verifier: propose prompt mentions UNABLE TO DETERMINE."""
    assert "UNABLE TO DETERMINE" in _read_template_text()


# --- AC-2: smoke / full stage prompts -----------------------------------


def test_smoke_stage_mandates_rk_run_explain_preflight():
    text = _read_template_text()
    assert "rk run --explain" in text
    assert "reasoning_effort" in text


def test_smoke_stage_mandates_rk_runs_cost_budget_check():
    text = _read_template_text()
    assert "rk runs cost" in text
    assert "--max-budget-usd-running" in text


def test_smoke_stage_mandates_rk_audit_policy_strict_sandwich():
    text = _read_template_text()
    assert "rk audit --policy strict" in text
    assert "rk score" in text
    # canonical sandwich pattern cite
    assert "dab-paper-matrix.sh" in text


# --- AC-2: analyze stage prompt (single-benchmark path, T-5a/T-5b) -------


def test_analyze_stage_cites_paper_baseline_auto_pull():
    text = _read_template_text()
    assert "experiment_meta.paper_baseline" in text


def test_analyze_stage_uses_stratified_pass_at_1_headline():
    text = _read_template_text()
    assert "stratified_pass_at_1" in text


def test_analyze_stage_cites_against_constant_stratified_verdict():
    text = _read_template_text()
    assert "against_constant.stratified.verdict" in text


def test_analyze_stage_does_not_invoke_against_constant_cli_flag():
    """M2 / AC-5 lint: post-hm shape uses auto-pull; no `--against-constant` CLI invocation."""
    text = _read_template_text()
    # The phrase may appear in instructional context ("do NOT pass --against-constant"),
    # so we lint that it does NOT appear as a CLI INVOCATION pattern.
    # An invocation looks like `rk score ... --against-constant <value>`.
    # We check that the literal string "rk score --against-constant" is absent.
    assert "rk score --against-constant" not in text, (
        "analyze stage must use paper_baseline auto-pull, not `rk score "
        "--against-constant` CLI invocation (M2 / AC-5)"
    )


def test_analyze_stage_documents_stratified_only_headline_directive():
    text = _read_template_text()
    assert "stratified-only headline" in text.lower() or (
        "stratified" in text.lower() and "headline" in text.lower()
    )


def test_analyze_stage_surfaces_spacedock_audit_coverage_caveat():
    """Phase5 entity body amendment: analyze prompt surfaces gv audit-coverage gap."""
    text = _read_template_text()
    assert "audit-scanner-subagent-jsonl-coverage" in text or "spacedock_solver" in text


# --- AC-3: run-workflow template ----------------------------------------


def test_run_workflow_has_four_stages_in_order():
    text = _read_run_template_text()
    expected = ["pending", "reconciling", "completed", "failed"]
    positions = []
    for name in expected:
        marker = f"## Stage: {name}"
        idx = text.find(marker)
        assert idx >= 0, f"missing '{marker}' in run-workflow README"
        positions.append(idx)
    assert positions == sorted(positions), (
        f"run-workflow stage sections out of order; positions={positions}"
    )


def test_run_workflow_declares_id_style_sd_b32():
    assert "id-style: sd-b32" in _read_run_template_text()


# --- AC-5: reachability (dry-run, no harbor / no API spend) -------------


def test_experiment_workflow_template_instantiates_to_tmp(tmp_path):
    """AC-5: a fresh `tmp_path/.razorback-workflow` instantiation exposes the six
    stage README sections (reachability stub — no harbor, no API spend)."""
    import shutil

    templates_root = importlib.resources.files("razorback").joinpath("templates")
    src_dir = templates_root.joinpath("experiment-workflow")
    # importlib.resources.files() may return a MultiplexedPath; convert to real fs path
    # via as_file for shutil.copytree.
    with importlib.resources.as_file(src_dir) as resolved_src:
        target = tmp_path / ".razorback-workflow"
        shutil.copytree(resolved_src, target)
        assert target.is_dir()
        readme = target / "README.md"
        assert readme.is_file()
        text = readme.read_text(encoding="utf-8")
        for name in ("pending", "propose", "smoke", "full", "analyze", "conclude"):
            assert f"## Stage: {name}" in text, (
                f"instantiated template missing stage section: {name}"
            )


def test_run_workflow_template_instantiates_to_tmp(tmp_path):
    """AC-3 + AC-5: run-workflow template instantiates with four stage sections."""
    import shutil

    templates_root = importlib.resources.files("razorback").joinpath("templates")
    src_dir = templates_root.joinpath("run-workflow")
    with importlib.resources.as_file(src_dir) as resolved_src:
        target = tmp_path / ".razorback-runs"
        shutil.copytree(resolved_src, target)
        readme = target / "README.md"
        assert readme.is_file()
        text = readme.read_text(encoding="utf-8")
        for name in ("pending", "reconciling", "completed", "failed"):
            assert f"## Stage: {name}" in text, (
                f"instantiated run-workflow template missing stage section: {name}"
            )
