# ABOUTME: T1/T2 — external_oracle_audit scans claude-code.txt JSONL for
# ABOUTME: forbidden external-oracle patterns; exits 0 clean / 2 cheating / 3 trace-missing.

import json
import subprocess
import sys
from pathlib import Path


def _run_audit(cell_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "razorback.agents.external_oracle_audit", str(cell_dir)],
        capture_output=True,
        text=True,
    )


def _write_trace(cell_dir: Path, events: list[dict]) -> Path:
    agent_dir = cell_dir / "steps" / "main" / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    path = agent_dir / "claude-code.txt"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


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


def _web_search_event(query: str = "anything") -> dict:
    return {
        "type": "assistant",
        "message": {
            "model": "claude-opus-4-7",
            "id": "msg_w",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_ws",
                    "name": "WebSearch",
                    "input": {"query": query},
                }
            ],
        },
    }


def _sidecar(cell_dir: Path) -> dict:
    return json.loads((cell_dir / "external-oracle-audit.json").read_text())


def test_a_load_dataset_fancyzhx_rejects(tmp_path):
    cell = tmp_path / "cell"
    _write_trace(
        cell,
        [
            {"type": "system", "subtype": "init", "tools": ["Bash"]},
            _bash_event(
                "python3 << 'EOF'\nfrom datasets import load_dataset\n"
                "ds = load_dataset('fancyzhx/ag_news')\nEOF"
            ),
        ],
    )
    result = _run_audit(cell)
    assert result.returncode == 2, result.stderr
    payload = _sidecar(cell)
    assert payload["schema_version"] == "razorback-external-oracle-audit-v1"
    assert payload["confirmed_count"] >= 1
    pattern_ids = {f["pattern_id"] for f in payload["findings"]}
    assert "load_dataset" in pattern_ids
    snippets = " ".join(f["snippet"] for f in payload["findings"])
    assert "fancyzhx/ag_news" in snippets
    assert all(isinstance(f["event_index"], int) for f in payload["findings"])


def test_b_clean_bash_only_passes(tmp_path):
    cell = tmp_path / "cell"
    _write_trace(
        cell,
        [
            {"type": "system", "subtype": "init", "tools": ["Bash"]},
            _bash_event("psql -c 'SELECT 1'"),
            _bash_event("mongosh --eval 'db.runCommand({ping:1})'"),
        ],
    )
    result = _run_audit(cell)
    assert result.returncode == 0, result.stderr
    payload = _sidecar(cell)
    assert payload["findings"] == []
    assert payload["confirmed_count"] == 0


def test_c_requests_get_public_host_rejects(tmp_path):
    cell = tmp_path / "cell"
    _write_trace(
        cell,
        [
            {"type": "system", "subtype": "init", "tools": ["Bash"]},
            _bash_event(
                "python3 -c \"import requests; "
                "requests.get('https://raw.githubusercontent.com/owner/repo/main/file.csv')\""
            ),
        ],
    )
    result = _run_audit(cell)
    assert result.returncode == 2, result.stderr
    payload = _sidecar(cell)
    pids = {f["pattern_id"] for f in payload["findings"]}
    assert "requests_get_public_host" in pids
    confirmed = [f for f in payload["findings"] if f["pattern_id"] == "requests_get_public_host"]
    assert all(f["severity"] == "confirmed" for f in confirmed)


def test_d_python_heredoc_from_datasets_import_rejects(tmp_path):
    cell = tmp_path / "cell"
    _write_trace(
        cell,
        [
            {"type": "system", "subtype": "init", "tools": ["Bash"]},
            _bash_event("python3 << 'EOF'\nfrom datasets import load_dataset\nEOF"),
        ],
    )
    result = _run_audit(cell)
    assert result.returncode == 2, result.stderr
    payload = _sidecar(cell)
    pids = {f["pattern_id"] for f in payload["findings"]}
    assert "from_datasets_import" in pids


def test_e_websearch_tool_use_rejects(tmp_path):
    cell = tmp_path / "cell"
    _write_trace(
        cell,
        [
            {"type": "system", "subtype": "init", "tools": ["Bash", "WebSearch"]},
            _web_search_event("ag_news label distribution"),
        ],
    )
    result = _run_audit(cell)
    assert result.returncode == 2, result.stderr
    payload = _sidecar(cell)
    pids = {f["pattern_id"] for f in payload["findings"]}
    assert "web_search_tool" in pids


def test_f_missing_trace_exits_three(tmp_path):
    cell = tmp_path / "empty-cell"
    cell.mkdir()
    result = _run_audit(cell)
    assert result.returncode == 3
    assert "trace-missing" in result.stderr


def test_tool_result_echo_not_flagged(tmp_path):
    """Defense-in-depth: a forbidden pattern appearing only in a user-role
    tool_result echo (not in an assistant-role tool_use input) must not fire.
    """
    cell = tmp_path / "cell"
    _write_trace(
        cell,
        [
            {"type": "system", "subtype": "init", "tools": ["Bash"]},
            _bash_event("ls /workspace"),
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_x",
                            "content": "echo: load_dataset('fake')",
                        }
                    ],
                },
            },
        ],
    )
    result = _run_audit(cell)
    assert result.returncode == 0, result.stderr
    payload = _sidecar(cell)
    assert payload["findings"] == []
