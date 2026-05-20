# ABOUTME: Integration tests for `rk audit` Typer command (AC-1 + AC-5 of phase4a).
# ABOUTME: Exercises per-trial reducer, JSON output shape, and --policy strict exit code.

import json

from typer.testing import CliRunner

from razorback.cli import app


runner = CliRunner()


def _parse_json_stdout(result):
    return json.loads(result.stdout)


def test_rk_audit_emits_per_trial_status(three_trial_run_dir):
    result = runner.invoke(app, ["audit", str(three_trial_run_dir)])
    assert result.exit_code == 0, result.stdout
    payload = _parse_json_stdout(result)
    assert payload["schema_version"] == "rk-audit-v1"
    assert payload["policy"] == "audit"
    statuses = [trial["taint_status"] for trial in payload["trials"]]
    assert sorted(statuses) == ["clean", "coverage_missing", "tainted"]
    assert payload["summary"] == {"clean": 1, "tainted": 1, "coverage_missing": 1}


def test_rk_audit_policy_strict_exits_23(three_trial_run_dir):
    result = runner.invoke(app, ["audit", str(three_trial_run_dir), "--policy", "strict"])
    assert result.exit_code == 23
    assert "TaintFindingsError" in result.output


def test_rk_audit_policy_audit_exits_0(three_trial_run_dir):
    result = runner.invoke(app, ["audit", str(three_trial_run_dir), "--policy", "audit"])
    assert result.exit_code == 0
    payload = _parse_json_stdout(result)
    assert payload["summary"]["tainted"] == 1
    assert payload["summary"]["coverage_missing"] == 1


def test_rk_audit_all_clean_exits_0_under_strict(clean_only_run_dir):
    result = runner.invoke(app, ["audit", str(clean_only_run_dir), "--policy", "strict"])
    assert result.exit_code == 0, result.stdout
    payload = _parse_json_stdout(result)
    assert payload["summary"] == {"clean": 1, "tainted": 0, "coverage_missing": 0}


def test_rk_audit_markdown_format(clean_only_run_dir):
    result = runner.invoke(app, ["audit", str(clean_only_run_dir), "--format", "markdown"])
    assert result.exit_code == 0, result.stdout
    assert "# rk audit" in result.stdout
    assert "clean=1" in result.stdout


def test_rk_audit_rejects_unknown_policy(clean_only_run_dir):
    result = runner.invoke(app, ["audit", str(clean_only_run_dir), "--policy", "nope"])
    assert result.exit_code == 2
    assert "unknown policy" in result.output
