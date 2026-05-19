# ABOUTME: AC-3 — AliasDriftError fires when provider's resolved model version
# ABOUTME: differs from the frozen spec's pinned model_resolved_version.

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from razorback.errors import ExitCode
from razorback.provenance.drift import check_alias_drift
from razorback.provenance.errors import AliasDriftError


def _fake_model_retrieve(resolved_id: str, created_at: str = "2025-10-22T00:00:00Z"):
    """Build a MagicMock client whose .models.retrieve returns a frozen response."""
    client = MagicMock()
    client.models.retrieve.return_value = MagicMock(
        id=resolved_id,
        created_at=created_at,
        display_name="Claude Opus 4.5",
    )
    return client


def test_alias_drift_raises_when_provider_version_differs():
    """Frozen: claude-opus-4-5-20251022. Provider now returns -20260101. AliasDriftError."""
    client = _fake_model_retrieve("claude-opus-4-5-20260101")
    with pytest.raises(AliasDriftError) as exc_info:
        check_alias_drift(
            model_alias="claude-opus-4-5",
            frozen_resolved_version="claude-opus-4-5-20251022",
            client=client,
            allow=False,
        )
    assert exc_info.value.exit_code == ExitCode.ALIAS_DRIFT
    assert exc_info.value.exit_code == 21
    assert "claude-opus-4-5-20251022" in str(exc_info.value)
    assert "claude-opus-4-5-20260101" in str(exc_info.value)


def test_alias_drift_no_raise_when_versions_match():
    client = _fake_model_retrieve("claude-opus-4-5-20251022")
    resolved_id, resolved_at = check_alias_drift(
        model_alias="claude-opus-4-5",
        frozen_resolved_version="claude-opus-4-5-20251022",
        client=client,
        allow=False,
    )
    assert resolved_id == "claude-opus-4-5-20251022"
    assert resolved_at == "2025-10-22T00:00:00Z"


def test_alias_drift_allow_returns_both_versions_for_provenance_recording():
    """--allow-alias-drift: do not raise; return both versions so provenance.yaml records them."""
    client = _fake_model_retrieve(
        "claude-opus-4-5-20260101", created_at="2026-01-01T00:00:00Z"
    )
    resolved_id, resolved_at = check_alias_drift(
        model_alias="claude-opus-4-5",
        frozen_resolved_version="claude-opus-4-5-20251022",
        client=client,
        allow=True,
    )
    assert resolved_id == "claude-opus-4-5-20260101"
    assert resolved_at == "2026-01-01T00:00:00Z"


def test_alias_drift_error_carries_both_versions_on_exc():
    """AliasDriftError exposes .frozen and .resolved for the run-dir's provenance.yaml writer."""
    client = _fake_model_retrieve("claude-opus-4-5-20260101")
    with pytest.raises(AliasDriftError) as exc_info:
        check_alias_drift(
            model_alias="claude-opus-4-5",
            frozen_resolved_version="claude-opus-4-5-20251022",
            client=client,
            allow=False,
        )
    assert exc_info.value.frozen == "claude-opus-4-5-20251022"
    assert exc_info.value.resolved == "claude-opus-4-5-20260101"
    assert exc_info.value.model_alias == "claude-opus-4-5"
