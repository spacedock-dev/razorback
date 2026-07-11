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
    assert manifest["trial"]["trial_id"] == "cell"
    assert manifest["prompt_mode"] is None
    assert manifest["trace_artifacts"] == [
        {
            "kind": "parent_log",
            "runtime": "claude",
            "path": "steps/main/agent/claude-code.txt",
        }
    ]
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


def test_writer_counts_codex_spawn_agent_events(tmp_path):
    cell_dir = tmp_path / "cell"
    agent_dir = cell_dir / "steps" / "main" / "agent"
    events = [
        {
            "type": "item.completed",
            "item": {
                "id": "spawn-model",
                "type": "collab_tool_call",
                "tool": "spawn_agent",
                "prompt": (
                    "stage_name: model\n"
                    "dispatch_agent_id: spacedock:ensign\n"
                    "worker_key: spacedock-ensign\n"
                ),
                "receiver_thread_ids": ["thread-1"],
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "wait-model",
                "type": "collab_tool_call",
                "tool": "wait_agent",
                "receiver_thread_ids": ["thread-1"],
                "status": "completed",
            },
        },
    ]
    _write_claude_code_txt(agent_dir / "codex.txt", events)

    manifest = write_subagent_trace_manifest(cell_dir)

    assert manifest["captured"] == 1
    assert manifest["capture_source"] == "razorback-codex-cli-trace"
    assert manifest["trial"]["trial_id"] == "cell"
    assert manifest["prompt_mode"] is None
    assert manifest["trace_artifacts"] == [
        {
            "kind": "parent_log",
            "runtime": "codex",
            "path": "steps/main/agent/codex.txt",
        }
    ]
    assert manifest["dispatches"][0]["tool_use_id"] == "spawn-model"
    assert manifest["dispatches"][0]["subagent_type"] == "spacedock:ensign"
    assert manifest["dispatches"][0]["spawn_index"] == 0


def test_writer_counts_codex_subagent_rollouts_when_stdout_has_no_spawn(tmp_path):
    """codex `exec --json` stdout is parent-thread-only: native spawn_agent
    dispatches never appear in codex.txt (only e.g. `wait` collab calls do).
    The writer must fall back to the sessions/ rollout mirror, where every
    thread — including subagent threads — has a rollout jsonl.
    """
    cell_dir = tmp_path / "cell"
    agent_dir = cell_dir / "steps" / "main" / "agent"
    stdout_events = [
        {"type": "thread.started", "thread_id": "thread-fo"},
        {
            "type": "item.completed",
            "item": {
                "id": "item_12",
                "type": "collab_tool_call",
                "tool": "wait",
                "sender_thread_id": "thread-fo",
                "receiver_thread_ids": [],
                "status": "completed",
            },
        },
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
    ]
    _write_claude_code_txt(agent_dir / "codex.txt", stdout_events)

    sessions_day = agent_dir / "sessions" / "2026" / "07" / "10"
    sessions_day.mkdir(parents=True)
    fo_rollout = [
        {
            "type": "session_meta",
            "payload": {"id": "thread-fo", "thread_source": "user", "source": "exec"},
        },
        {"type": "turn_context", "payload": {"model": "gpt-5.6-sol"}},
    ]
    (sessions_day / "rollout-fo.jsonl").write_text(
        "\n".join(json.dumps(e) for e in fo_rollout) + "\n"
    )
    ensign_rollout = [
        {
            "type": "session_meta",
            "payload": {
                "id": "thread-ensign",
                "session_id": "thread-fo",
                "parent_thread_id": "thread-fo",
                "thread_source": "subagent",
                "agent_nickname": "Arendt",
                "agent_path": "/root/dataset_solver",
            },
        },
        {
            "type": "event_msg",
            "payload": {
                "type": "user_message",
                "message": "dispatch_agent_id: spacedock:ensign\nworker_key: spacedock-ensign\n",
            },
        },
    ]
    (sessions_day / "rollout-ensign.jsonl").write_text(
        "\n".join(json.dumps(e) for e in ensign_rollout) + "\n"
    )

    manifest = write_subagent_trace_manifest(cell_dir)

    assert manifest["capture_source"] == "razorback-codex-cli-trace"
    assert manifest["captured"] == 1
    dispatch = manifest["dispatches"][0]
    assert dispatch["tool_use_id"] == "thread-ensign"
    assert dispatch["subagent_type"] == "spacedock:ensign"
    assert dispatch["spawn_index"] == 0
    assert len(dispatch["prompt_sha256"]) == 64
    # The subagent rollout is listed as a trace artifact next to the parent log.
    kinds = {(a["kind"], a["path"]) for a in manifest["trace_artifacts"]}
    assert ("parent_log", "steps/main/agent/codex.txt") in kinds
    assert (
        "subagent_rollout",
        "steps/main/agent/sessions/2026/07/10/rollout-ensign.jsonl",
    ) in kinds
    # Parent model recovered from the FO rollout (stdout has no turn_context).
    assert manifest["parent_agent"]["model"] == "gpt-5.6-sol"


def test_writer_raises_on_missing_claude_code_txt(tmp_path):
    cell_dir = tmp_path / "empty-cell"
    cell_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        write_subagent_trace_manifest(cell_dir)
