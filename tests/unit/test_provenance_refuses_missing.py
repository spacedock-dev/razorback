# ABOUTME: AC-1 — rk spec freeze refuses on any unresolved provenance field absent --allow-missing.
# ABOUTME: ProvenanceError (exit 11) and neither spec.frozen.yaml nor provenance.yaml gets written.

import pytest

from razorback.errors import ExitCode
from razorback.provenance.errors import ProvenanceError
from razorback.provenance.provenance_yaml import refuse_if_any_unresolved


FIELDS = [
    "model_resolved_version",
    "image_digest",
    "agent_cli_hash",
    "harness_git_sha",
    "harbor_version",
    "prompt_file_hashes",
    "plugins",
]


def _all_resolved() -> dict:
    return {
        "model_resolved_version": "claude-opus-4-5-20251022",
        "model_resolved_at": "2025-10-22T00:00:00Z",
        "image_digest": "sha256:abc123",
        "agent_cli_hash": "sha256:def456",
        "harness_git_sha": "0123456789abcdef",
        "harbor_version": "0.6.6",
        "prompt_file_hashes": {"agent-prompts/p.md": "sha256:fedcba"},
        "plugins": [],
    }


@pytest.mark.parametrize("missing_field", FIELDS)
def test_refuses_when_any_single_field_missing(missing_field):
    resolved = _all_resolved()
    resolved[missing_field] = None
    with pytest.raises(ProvenanceError) as exc_info:
        refuse_if_any_unresolved(resolved, allow_missing=False)
    assert exc_info.value.exit_code == ExitCode.PROVENANCE_ERROR
    assert exc_info.value.exit_code == 11
    assert missing_field in str(exc_info.value)


def test_no_raise_when_all_resolved():
    resolved = _all_resolved()
    refuse_if_any_unresolved(resolved, allow_missing=False)


def test_allow_missing_does_not_raise_even_when_fields_missing():
    resolved = _all_resolved()
    resolved["image_digest"] = None
    resolved["agent_cli_hash"] = None
    refuse_if_any_unresolved(resolved, allow_missing=True)


def test_refusal_lists_all_missing_fields_not_just_first():
    resolved = _all_resolved()
    resolved["image_digest"] = None
    resolved["harbor_version"] = None
    with pytest.raises(ProvenanceError) as exc_info:
        refuse_if_any_unresolved(resolved, allow_missing=False)
    msg = str(exc_info.value)
    assert "image_digest" in msg
    assert "harbor_version" in msg
