# ABOUTME: AC-5 — phase_stats.json has the §6.8 schema exactly.

import json
from pathlib import Path

import pytest

from razorback.agents.spacedock_solver import assert_phase_stats_schema


def test_phase_stats_schema(tmp_path):
    fixture = tmp_path / "phase_stats.json"
    fixture.write_text(json.dumps({
        "model":   {"tokens_in": 100, "tokens_out": 50, "cost_usd": 0.001, "wallclock_s": 2.0},
        "analyze": {"tokens_in":  80, "tokens_out": 40, "cost_usd": 0.0008, "wallclock_s": 1.5},
        "verify":  {"tokens_in":  60, "tokens_out": 30, "cost_usd": 0.0006, "wallclock_s": 1.0},
    }))
    assert_phase_stats_schema(fixture)


def test_phase_stats_rejects_missing_stage(tmp_path):
    fixture = tmp_path / "phase_stats.json"
    fixture.write_text(json.dumps({
        "model":   {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "wallclock_s": 0.0},
        "analyze": {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "wallclock_s": 0.0},
    }))
    with pytest.raises(AssertionError):
        assert_phase_stats_schema(fixture)


def test_phase_stats_rejects_missing_key(tmp_path):
    fixture = tmp_path / "phase_stats.json"
    fixture.write_text(json.dumps({
        "model":   {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0},
        "analyze": {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "wallclock_s": 0.0},
        "verify":  {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "wallclock_s": 0.0},
    }))
    with pytest.raises(AssertionError):
        assert_phase_stats_schema(fixture)


def test_phase_stats_schema_helper_is_importable_from_aggregator():
    """The M5 aggregator imports this helper. Lock the import path now."""
    from razorback.agents.spacedock_solver import assert_phase_stats_schema as f
    assert callable(f)
