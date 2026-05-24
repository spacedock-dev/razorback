# ABOUTME: cycle-2 — claude_code adapter scans assistant.tool_use events in
# ABOUTME: claude-code.txt and reuses taint patterns + cli passthrough.

import json
from pathlib import Path

from typer.testing import CliRunner

from razorback.audit import claude_code
from razorback.cli import app


runner = CliRunner()


def _bash_event(command: str, tool_use_id: str = "toolu_x") -> dict:
    return {
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-7",
            "id": "msg_x",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": "Bash",
                    "input": {"command": command},
                }
            ],
        },
    }


def _websearch_event() -> dict:
    return {
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-7",
            "id": "msg_ws",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_ws",
                    "name": "WebSearch",
                    "input": {"query": "ag_news"},
                }
            ],
        },
    }


def _user_tool_result_event(text: str) -> dict:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "toolu_x", "content": text}],
        },
    }


def _write_trial(trial_dir: Path, events: list[dict]) -> Path:
    agent_dir = trial_dir / "steps" / "main" / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    path = agent_dir / "claude-code.txt"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


def test_load_dataset_python_heredoc_flagged(tmp_path: Path) -> None:
    trial = tmp_path / "trial-0"
    _write_trial(trial, [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event(
            "python3 << 'EOF'\nfrom datasets import load_dataset\n"
            "ds = load_dataset('fancyzhx/ag_news')\nEOF"
        ),
    ])
    findings = claude_code.scan_trial(trial)
    assert findings, "expected load_dataset to be flagged"
    assert any(f["category"] == "forbidden_lookup" for f in findings)
    assert any(f["source_kind"] == "claude_code_trace" for f in findings)


def test_clean_bash_passes(tmp_path: Path) -> None:
    trial = tmp_path / "trial-0"
    _write_trial(trial, [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event("psql -c 'SELECT 1'"),
        _bash_event("mongosh --eval 'db.runCommand({ping:1})'"),
    ])
    assert claude_code.scan_trial(trial) == []


def test_pip_install_generic_lib_stays_clean(tmp_path: Path) -> None:
    """Captain principle: pip install rapidfuzz is CLEAN."""
    trial = tmp_path / "trial-0"
    _write_trial(trial, [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event("pip install rapidfuzz"),
        _bash_event("pip install --user duckdb"),
        _bash_event("pip3 install scikit-learn"),
    ])
    findings = claude_code.scan_trial(trial)
    assert findings == [], findings


def test_pip_install_named_lib_flagged(tmp_path: Path) -> None:
    trial = tmp_path / "trial-0"
    _write_trial(trial, [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event("pip install datasets"),
    ])
    findings = claude_code.scan_trial(trial)
    assert findings
    assert any(f["category"] == "forbidden_lookup" for f in findings)


def test_websearch_tool_use_flagged(tmp_path: Path) -> None:
    trial = tmp_path / "trial-0"
    _write_trial(trial, [
        {"type": "system", "subtype": "init", "tools": ["WebSearch"]},
        _websearch_event(),
    ])
    findings = claude_code.scan_trial(trial)
    assert findings
    assert findings[0]["category"] == "forbidden_lookup"
    assert findings[0]["scanned_field"] == "tool_name"


def test_curl_to_huggingface_flagged(tmp_path: Path) -> None:
    trial = tmp_path / "trial-0"
    _write_trial(trial, [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event("curl -sI https://huggingface.co"),
    ])
    findings = claude_code.scan_trial(trial)
    assert findings
    assert findings[0]["category"] == "forbidden_lookup"


def test_tool_result_echo_not_flagged(tmp_path: Path) -> None:
    """The OFFENSE lives in the assistant's tool_use, not in the user-role
    tool_result echo. A forbidden pattern appearing only in a tool_result must
    not fire (matches cycle-1 module's defense-in-depth behavior).
    """
    trial = tmp_path / "trial-0"
    _write_trial(trial, [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event("ls /workspace"),
        _user_tool_result_event("echo: load_dataset('fake')"),
    ])
    assert claude_code.scan_trial(trial) == []


def test_missing_claude_code_txt_returns_empty(tmp_path: Path) -> None:
    """No claude-code.txt → no findings (the per-cell dispatcher hook treats
    that case as a coverage concern via taint-side machinery, not here)."""
    trial = tmp_path / "trial-0"
    trial.mkdir()
    assert claude_code.scan_trial(trial) == []


def test_discover_trial_roots_finds_claude_code_txt(tmp_path: Path) -> None:
    trial_a = tmp_path / "task-a" / "query-1" / "trial-0"
    _write_trial(trial_a, [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event("pwd"),
    ])
    trial_b = tmp_path / "task-b" / "query-1" / "trial-0"
    _write_trial(trial_b, [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event("pip install rapidfuzz"),
    ])
    roots = claude_code.discover_trial_roots(tmp_path)
    assert set(roots) == {trial_a, trial_b}


def test_rk_audit_strict_taints_claude_code_load_dataset(tmp_path: Path) -> None:
    """End-to-end: `rk audit --policy strict` over a run-dir with a
    claude-code.txt load_dataset event exits 23.
    """
    _write_trial(tmp_path / "task-a" / "query-1" / "trial-0", [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event(
            "python3 -c \"from datasets import load_dataset; "
            "load_dataset('fancyzhx/ag_news')\""
        ),
    ])
    result = runner.invoke(app, ["audit", str(tmp_path), "--policy", "strict"])
    assert result.exit_code == 23, result.stdout
    assert "TaintFindingsError" in result.output


def test_rk_audit_strict_treats_pip_install_rapidfuzz_as_clean(tmp_path: Path) -> None:
    """End-to-end captain-principle gate: pip install rapidfuzz CLEAN."""
    _write_trial(tmp_path / "task-a" / "query-1" / "trial-0", [
        {"type": "system", "subtype": "init", "tools": ["Bash"]},
        _bash_event("pip install rapidfuzz"),
        _bash_event("pip install duckdb"),
    ])
    result = runner.invoke(app, ["audit", str(tmp_path), "--policy", "strict"])
    assert result.exit_code == 0, result.stdout
