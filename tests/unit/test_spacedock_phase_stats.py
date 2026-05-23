# ABOUTME: AC-5 — phase_stats.json has the §6.8 schema exactly.

import json
from pathlib import Path

import pytest

from razorback.agents.spacedock_solver import assert_phase_stats_schema


def test_phase_stats_schema(tmp_path):
    fixture = tmp_path / "phase_stats.json"
    fixture.write_text(json.dumps({
        "setup/ready": _stats(),
        "run/before-agent": _stats(),
        "run/after-agent": _stats(),
    }))
    assert_phase_stats_schema(
        fixture,
        stages=["setup/ready", "run/before-agent", "run/after-agent"],
    )


def test_phase_stats_rejects_missing_stage(tmp_path):
    fixture = tmp_path / "phase_stats.json"
    fixture.write_text(json.dumps({
        "setup/ready": _stats(),
        "run/before-agent": _stats(),
    }))
    with pytest.raises(AssertionError):
        assert_phase_stats_schema(
            fixture,
            stages=["setup/ready", "run/before-agent", "run/after-agent"],
        )


def test_phase_stats_rejects_missing_key(tmp_path):
    fixture = tmp_path / "phase_stats.json"
    fixture.write_text(json.dumps({
        "setup/ready": {
            "tokens_in": 0,
            "tokens_out": 0,
            "tokens_reasoning": 0,
            "tokens_cache_read": 0,
            "tokens_cache_write": 0,
            "cost_usd": 0.0,
        },
        "run/before-agent": _stats(),
        "run/after-agent": _stats(),
    }))
    with pytest.raises(AssertionError):
        assert_phase_stats_schema(
            fixture,
            stages=["setup/ready", "run/before-agent", "run/after-agent"],
        )


def test_phase_stats_schema_helper_is_importable_from_aggregator():
    """The M5 aggregator imports this helper. Lock the import path now."""
    from razorback.agents.spacedock_solver import assert_phase_stats_schema as f
    assert callable(f)


def _stats() -> dict:
    return {
        "tokens_in": 0,
        "tokens_out": 0,
        "tokens_reasoning": 0,
        "tokens_cache_read": 0,
        "tokens_cache_write": 0,
        "cost_usd": 0.0,
        "wallclock_s": 0.0,
    }
