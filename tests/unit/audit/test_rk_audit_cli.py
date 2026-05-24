# ABOUTME: Integration tests for `rk audit` Typer command (AC-1 + AC-5 of phase4a).
# ABOUTME: Exercises per-trial reducer, JSON output shape, and --policy strict exit code.

import json

from typer.testing import CliRunner

from razorback.cli import app


runner = CliRunner()


def _parse_json_stdout(result):
    payload, _ = json.JSONDecoder().raw_decode(result.stdout)
    return payload


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


def test_rk_audit_discovers_harbor_codex_txt_trial(harbor_codex_clean_txt_run_dir):
    result = runner.invoke(app, ["audit", str(harbor_codex_clean_txt_run_dir)])
    assert result.exit_code == 0, result.stdout
    payload = _parse_json_stdout(result)
    assert len(payload["trials"]) == 1
    assert payload["trials"][0]["trial_id"] == "task-a/query-1/trial-0"
    assert payload["trials"][0]["taint_status"] == "clean"
    assert payload["summary"] == {"clean": 1, "tainted": 0, "coverage_missing": 0}


def test_rk_audit_strict_taints_harbor_codex_session_command(
    harbor_codex_tainted_session_run_dir,
):
    result = runner.invoke(
        app,
        ["audit", str(harbor_codex_tainted_session_run_dir), "--policy", "strict"],
    )
    assert result.exit_code == 23
    payload = _parse_json_stdout(result)
    assert payload["summary"] == {"clean": 0, "tainted": 1, "coverage_missing": 0}
    finding = payload["trials"][0]["findings"][0]
    assert finding["category"] == "forbidden_lookup"
    assert finding["source_kind"] == "harbor_codex_session"
    assert finding["source_path"] == (
        "steps/main/agent/sessions/2026/05/21/session.jsonl"
    )


def test_rk_audit_strict_taints_harbor_codex_txt_command(
    harbor_codex_tainted_txt_run_dir,
):
    result = runner.invoke(
        app,
        ["audit", str(harbor_codex_tainted_txt_run_dir), "--policy", "strict"],
    )
    assert result.exit_code == 23
    payload = _parse_json_stdout(result)
    finding = payload["trials"][0]["findings"][0]
    assert finding["category"] == "forbidden_lookup"
    assert finding["source_kind"] == "harbor_codex_text"
    assert finding["source_path"] == "steps/main/agent/codex.txt"


def test_rk_audit_strict_treats_guard_blocked_codex_txt_command_as_clean(
    harbor_codex_guard_blocked_txt_run_dir,
):
    result = runner.invoke(
        app,
        ["audit", str(harbor_codex_guard_blocked_txt_run_dir), "--policy", "strict"],
    )
    assert result.exit_code == 0, result.stdout
    payload = _parse_json_stdout(result)
    assert payload["summary"] == {"clean": 1, "tainted": 0, "coverage_missing": 0}
    assert payload["trials"][0]["findings"] == []


def test_rk_audit_strict_treats_guard_blocked_codex_session_command_as_clean(
    harbor_codex_guard_blocked_session_run_dir,
):
    result = runner.invoke(
        app,
        ["audit", str(harbor_codex_guard_blocked_session_run_dir), "--policy", "strict"],
    )
    assert result.exit_code == 0, result.stdout
    payload = _parse_json_stdout(result)
    assert payload["summary"] == {"clean": 1, "tainted": 0, "coverage_missing": 0}
    assert payload["trials"][0]["findings"] == []


def test_rk_audit_discovers_direct_harbor_codex_txt_trial(
    harbor_codex_direct_txt_run_dir,
):
    result = runner.invoke(app, ["audit", str(harbor_codex_direct_txt_run_dir)])
    assert result.exit_code == 0, result.stdout
    payload = _parse_json_stdout(result)
    assert len(payload["trials"]) == 1
    assert payload["trials"][0]["trial_id"] == "ade-bench-airbnb001__R5gM9eD"
    assert payload["trials"][0]["taint_status"] == "clean"
    assert payload["summary"] == {"clean": 1, "tainted": 0, "coverage_missing": 0}


def test_rk_audit_strict_ignores_job_log_setup_install(
    harbor_codex_setup_install_only_run_dir,
):
    result = runner.invoke(
        app,
        ["audit", str(harbor_codex_setup_install_only_run_dir), "--policy", "strict"],
    )
    assert result.exit_code == 0, result.stdout
    payload = _parse_json_stdout(result)
    assert payload["summary"] == {"clean": 1, "tainted": 0, "coverage_missing": 0}
    assert payload["trials"][0]["findings"] == []


def test_rk_audit_strict_fails_on_missing_spacedock_trial_manifest(
    spacedock_dispatch_gap_run_dir,
):
    result = runner.invoke(
        app,
        ["audit", str(spacedock_dispatch_gap_run_dir), "--policy", "strict"],
    )
    assert result.exit_code == 23
    payload = _parse_json_stdout(result)
    assert payload["summary"]["coverage_missing"] == 1
    missing = [
        trial
        for trial in payload["trials"]
        if trial["taint_status"] == "coverage_missing"
    ][0]
    assert missing["trial_id"] == "trial-b__bbbb"
    assert missing["findings"][0]["missing_reason"] == (
        "spacedock_dispatch_manifest_absent"
    )


def test_rk_audit_strict_passes_when_spacedock_trial_manifests_present(
    spacedock_dispatch_complete_run_dir,
):
    result = runner.invoke(
        app,
        ["audit", str(spacedock_dispatch_complete_run_dir), "--policy", "strict"],
    )
    assert result.exit_code == 0, result.stdout
    payload = _parse_json_stdout(result)
    assert payload["summary"] == {"clean": 2, "tainted": 0, "coverage_missing": 0}
    assert [trial["trial_id"] for trial in payload["trials"]] == [
        "trial-a__aaaa",
        "trial-b__bbbb",
    ]


def test_rk_audit_strict_accepts_legacy_single_spacedock_root_manifest(
    spacedock_dispatch_legacy_single_run_dir,
):
    result = runner.invoke(
        app,
        ["audit", str(spacedock_dispatch_legacy_single_run_dir), "--policy", "strict"],
    )
    assert result.exit_code == 0, result.stdout
    payload = _parse_json_stdout(result)
    assert payload["summary"] == {"clean": 1, "tainted": 0, "coverage_missing": 0}
    assert payload["trials"][0]["trial_id"] == "trial-a__aaaa"
