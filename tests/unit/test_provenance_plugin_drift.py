# ABOUTME: AC-3 — check_plugin_drift refuses with ProvenanceError (exit 11) on plugin
# ABOUTME: version drift between freeze and run; --allow-plugin-drift records the drift.

from __future__ import annotations

import pytest

from razorback.errors import ExitCode
from razorback.provenance.drift import check_plugin_drift
from razorback.provenance.errors import ProvenanceError


FROZEN_PLUGINS = [
    {
        "group": "harbor.agents",
        "name": "claude_code",
        "distribution": "harbor",
        "version": "0.6.6",
    },
    {
        "group": "harbor.benchmarks",
        "name": "dab",
        "distribution": "razorback-plugin-dab",
        "version": "0.1.0",
    },
]


def _resolver(rows):
    return lambda: {"plugins": rows}


def test_no_drift_returns_none() -> None:
    out = check_plugin_drift(
        frozen=list(FROZEN_PLUGINS),
        resolver=_resolver(list(FROZEN_PLUGINS)),
        allow=False,
    )
    assert out is None


def test_drift_raises_provenance_error_default() -> None:
    drifted = [dict(row) for row in FROZEN_PLUGINS]
    drifted[1]["version"] = "0.2.0"
    with pytest.raises(ProvenanceError) as exc_info:
        check_plugin_drift(
            frozen=list(FROZEN_PLUGINS), resolver=_resolver(drifted), allow=False
        )
    assert exc_info.value.exit_code == ExitCode.PROVENANCE_ERROR
    assert exc_info.value.exit_code == 11
    msg = str(exc_info.value)
    assert "dab" in msg
    assert "--allow-plugin-drift" in msg


def test_allow_flag_returns_drift_record() -> None:
    drifted = [dict(row) for row in FROZEN_PLUGINS]
    drifted[1]["version"] = "0.2.0"
    record = check_plugin_drift(
        frozen=list(FROZEN_PLUGINS), resolver=_resolver(drifted), allow=True
    )
    assert record is not None
    assert record["frozen"] == FROZEN_PLUGINS
    assert record["resolved"] == drifted


def test_frozen_none_is_noop() -> None:
    """Pre-PKG-8 frozen specs lack the plugins block; check is a no-op."""
    out = check_plugin_drift(
        frozen=None, resolver=_resolver(list(FROZEN_PLUGINS)), allow=False
    )
    assert out is None


def test_drift_when_plugin_removed() -> None:
    """A plugin frozen but no longer installed counts as drift."""
    resolved = [FROZEN_PLUGINS[0]]
    with pytest.raises(ProvenanceError) as exc_info:
        check_plugin_drift(
            frozen=list(FROZEN_PLUGINS), resolver=_resolver(resolved), allow=False
        )
    assert "dab" in str(exc_info.value)


def test_drift_when_plugin_added() -> None:
    """A newly-installed plugin not in the frozen list counts as drift."""
    resolved = list(FROZEN_PLUGINS) + [
        {
            "group": "harbor.agents",
            "name": "codex",
            "distribution": "harbor",
            "version": "0.6.6",
        }
    ]
    with pytest.raises(ProvenanceError) as exc_info:
        check_plugin_drift(
            frozen=list(FROZEN_PLUGINS), resolver=_resolver(resolved), allow=False
        )
    assert "codex" in str(exc_info.value)
