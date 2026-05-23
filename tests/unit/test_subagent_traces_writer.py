# ABOUTME: T7/T8 — subagent_traces.write_subagent_trace_manifest parses
# ABOUTME: claude-code.txt JSONL, counts Task/Agent tool_use events, emits manifest.

import json
from pathlib import Path

import pytest

from razorback.agents.subagent_traces import write_subagent_trace_manifest


def _assistant_tool_use(tool_use_id, name, subagent_type, prompt, model):
    return {
        "type": "assistant",
        "message": {
            "model": model,
            "id": "msg_x",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": name,
                    "input": {"subagent_type": subagent_type, "prompt": prompt},
                }
            ],
        },
    }


def _write_claude_code_txt(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")


def test_writer_counts_two_task_events(tmp_path):
    cell_dir = tmp_path / "cell"
    agent_dir = cell_dir / "steps" / "main" / "agent"
    events = [
        {"type": "system", "subtype": "init", "tools": ["Task", "Bash"]},
        _assistant_tool_use("toolu_1", "Task", "spacedock:ensign", "do A", "claude-opus-4-7"),
        _assistant_tool_use("toolu_2", "Task", "spacedock:ensign", "do B", "claude-opus-4-7"),
    ]
    _write_claude_code_txt(agent_dir / "claude-code.txt", events)
    manifest = write_subagent_trace_manifest(cell_dir)
    assert manifest["schema_version"] == "razorback-subagent-traces-v1"
    assert manifest["captured"] == 2
    assert manifest["expected"] is None
    assert len(manifest["dispatches"]) == 2
    for idx, dispatch in enumerate(manifest["dispatches"]):
        assert set(dispatch.keys()) == {
            "tool_use_id",
            "subagent_type",
            "prompt_sha256",
            "spawn_index",
        }
        assert dispatch["spawn_index"] == idx
        assert dispatch["subagent_type"] == "spacedock:ensign"
        assert len(dispatch["prompt_sha256"]) == 64
    assert manifest["parent_agent"]["model"] == "claude-opus-4-7"
    assert manifest["capture_source"] == "razorback-claude-cli-trace"
    # Manifest written to disk.
    out = json.loads((cell_dir / "subagent-trace-manifest.json").read_text())
    assert out == manifest


def test_writer_handles_zero_task_events(tmp_path):
    cell_dir = tmp_path / "cell"
    agent_dir = cell_dir / "steps" / "main" / "agent"
    events = [
        {"type": "system", "subtype": "init", "tools": ["Task", "Bash"]},
        {
            "type": "assistant",
            "message": {
                "model": "claude-opus-4-7",
                "id": "msg_y",
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_b",
                        "name": "Bash",
                        "input": {"command": "ls"},
                    }
                ],
            },
        },
    ]
    _write_claude_code_txt(agent_dir / "claude-code.txt", events)
    manifest = write_subagent_trace_manifest(cell_dir)
    assert manifest["captured"] == 0
    assert manifest["dispatches"] == []


def test_writer_counts_agent_tool_use_too(tmp_path):
    """Claude CLI >= 2.1.148 emits the dispatch primitive as 'Agent' on the wire
    even when session-init advertises it as 'Task'. The writer counts both.
    """
    cell_dir = tmp_path / "cell"
    agent_dir = cell_dir / "steps" / "main" / "agent"
    events = [
        {"type": "system", "subtype": "init", "tools": ["Task"]},
        _assistant_tool_use("toolu_a", "Agent", "spacedock:ensign", "do X", "claude-opus-4-7"),
    ]
    _write_claude_code_txt(agent_dir / "claude-code.txt", events)
    manifest = write_subagent_trace_manifest(cell_dir)
    assert manifest["captured"] == 1
    assert manifest["dispatches"][0]["subagent_type"] == "spacedock:ensign"


def test_writer_raises_on_missing_claude_code_txt(tmp_path):
    cell_dir = tmp_path / "empty-cell"
    cell_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        write_subagent_trace_manifest(cell_dir)
