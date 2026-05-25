# ABOUTME: AC-4 — phase5 workflow README templates ship as in-package data.
# ABOUTME: Asserts importlib.resources can read both template dirs from the installed razorback package.

from __future__ import annotations

import importlib.resources


def test_razorback_templates_dir_is_packaged():
    """Phase 5 / AC-4: `razorback/templates/` ships as package data."""
    templates_root = importlib.resources.files("razorback").joinpath("templates")
    assert templates_root.is_dir(), (
        f"razorback.templates package-data root missing: {templates_root}"
    )


def test_experiment_workflow_template_packaged():
    """Phase 5 / AC-2 + AC-4: experiment-workflow/README.md ships from installed wheel."""
    templates_root = importlib.resources.files("razorback").joinpath("templates")
    readme = templates_root.joinpath("experiment-workflow", "README.md")
    assert readme.is_file(), f"experiment-workflow README missing at {readme}"
    text = readme.read_text(encoding="utf-8")
    assert len(text) > 0, "experiment-workflow README is empty"


def test_run_workflow_template_packaged():
    """Phase 5 / AC-3 + AC-4: run-workflow/README.md ships from installed wheel."""
    templates_root = importlib.resources.files("razorback").joinpath("templates")
    readme = templates_root.joinpath("run-workflow", "README.md")
    assert readme.is_file(), f"run-workflow README missing at {readme}"
    text = readme.read_text(encoding="utf-8")
    assert len(text) > 0, "run-workflow README is empty"


def test_template_dirs_enumerable_from_installed_package():
    """Phase 5 / AC-4 verifier: the AC's exact command works.

    Mirrors the entity body's verifier:
        python -c "import importlib.resources; print(list(
        importlib.resources.files('razorback').joinpath('templates').iterdir()))"
    """
    templates_root = importlib.resources.files("razorback").joinpath("templates")
    names = {entry.name for entry in templates_root.iterdir()}
    assert "experiment-workflow" in names, f"missing experiment-workflow in {names}"
    assert "run-workflow" in names, f"missing run-workflow in {names}"
