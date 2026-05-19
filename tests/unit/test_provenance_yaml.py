# ABOUTME: provenance.yaml writer — shape stability test (§6.4 sidecar).

import yaml

from razorback.provenance.provenance_yaml import write_provenance_yaml


ALL_RESOLVED = {
    "model_resolved_version": "claude-opus-4-5-20251022",
    "model_resolved_at": "2025-10-22T00:00:00Z",
    "image_digest": "sha256:abc",
    "agent_cli_hash": "sha256:def",
    "harness_git_sha": "0123456789abcdef",
    "harbor_version": "0.6.6",
    "prompt_file_hashes": {"p.md": "sha256:fed"},
}


def test_writes_six_resolved_fields_plus_timestamp(tmp_path):
    out = tmp_path / "provenance.yaml"
    write_provenance_yaml(out, ALL_RESOLVED)
    doc = yaml.safe_load(out.read_text())
    assert doc["model_resolved_version"] == "claude-opus-4-5-20251022"
    assert doc["model_resolved_at"] == "2025-10-22T00:00:00Z"
    assert doc["harbor_version"] == "0.6.6"
    assert "unresolved" not in doc
    assert "alias_drift" not in doc


def test_unresolved_field_appears_in_unresolved_list_not_in_body(tmp_path):
    resolved = dict(ALL_RESOLVED)
    resolved["image_digest"] = None
    out = tmp_path / "provenance.yaml"
    write_provenance_yaml(out, resolved)
    doc = yaml.safe_load(out.read_text())
    assert "image_digest" not in doc
    assert "image_digest" in doc["unresolved"]


def test_drift_record_appears_under_alias_drift(tmp_path):
    """AC-3 — when --allow-alias-drift is passed, provenance.yaml records both versions."""
    out = tmp_path / "provenance.yaml"
    write_provenance_yaml(
        out,
        ALL_RESOLVED,
        drift_record={
            "model_alias": "claude-opus-4-5",
            "frozen": "claude-opus-4-5-20251022",
            "resolved": "claude-opus-4-5-20260101",
        },
    )
    doc = yaml.safe_load(out.read_text())
    assert doc["alias_drift"]["frozen"] == "claude-opus-4-5-20251022"
    assert doc["alias_drift"]["resolved"] == "claude-opus-4-5-20260101"


def test_multiple_unresolved_sorted(tmp_path):
    resolved = dict(ALL_RESOLVED)
    resolved["image_digest"] = None
    resolved["harbor_version"] = None
    out = tmp_path / "provenance.yaml"
    write_provenance_yaml(out, resolved)
    doc = yaml.safe_load(out.read_text())
    assert doc["unresolved"] == ["harbor_version", "image_digest"]
