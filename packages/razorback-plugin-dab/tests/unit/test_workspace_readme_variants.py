# ABOUTME: PKG-9 carry-forward — three workspace-README variants render variant-specific text.
# ABOUTME: Each variant declares the answers.json output contract.

import pytest

from razorback_plugin_dab.generate.workspace_readme import (
    WORKSPACE_VARIANTS,
    render_workspace_readme,
)


def test_three_variants_exist():
    assert WORKSPACE_VARIANTS == ("spacedock", "direct-structured", "direct-minimal")


def test_direct_minimal_is_terse():
    text = render_workspace_readme(variant="direct-minimal", container_workdir="/workspace")
    assert "answers.json" in text
    assert "Workspace layout" not in text  # the structured variant has this
    assert "first officer" not in text


def test_direct_minimal_carries_database_access_block():
    """Paper-canonical alignment: direct-minimal must tell the agent how to
    reach the workspace databases. Mirrors direct-structured's lines 47-52
    (host/port creds for postgres+mongo, sqlite/duckdb under query_dataset/).
    Without this section, the agent in direct-minimal cannot connect to the
    workspace DBs without trial-and-error discovery — explains the archived
    `an` run's 100% UTD smoke + 0.4279 stratified-per-query headline."""
    text = render_workspace_readme(variant="direct-minimal", container_workdir="/workspace")
    assert "## Database access" in text
    assert "dab-postgres" in text
    assert "5432" in text
    assert "dab-mongo" in text
    assert "27017" in text
    assert "query_dataset/" in text


def test_direct_structured_has_layout_block():
    text = render_workspace_readme(variant="direct-structured", container_workdir="/workspace")
    assert "Workspace layout" in text
    assert "db_config.yaml" in text
    assert "dab-postgres" in text
    assert "first officer" not in text


def test_spacedock_has_solver_framing():
    text = render_workspace_readme(variant="spacedock", container_workdir="/workspace")
    assert "first officer" in text
    assert "model -> analyze -> verify" in text
    assert "answers.json" in text


def test_unknown_variant_raises():
    with pytest.raises(ValueError):
        render_workspace_readme(variant="nope", container_workdir="/workspace")


def test_workdir_threaded_into_template():
    text = render_workspace_readme(variant="direct-structured", container_workdir="/work")
    assert "/work/answers.json" in text
