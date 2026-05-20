# ABOUTME: Fixture helpers for `rk audit` CLI integration tests.
# ABOUTME: Reuse the same JSONL builders as test_taint_keep_verbatim for fixture parity.

import json

import pytest


def _parent_spawn_wait_jsonl(child_id="thread-1"):
    return "\n".join([
        json.dumps({
            "type": "item.completed",
            "thread_id": "parent-thread",
            "item": {
                "id": "spawn-model",
                "type": "collab_tool_call",
                "tool": "spawn_agent",
                "prompt": "stage_name: model\n",
                "receiver_thread_ids": [child_id],
                "status": "completed",
            },
        }),
        json.dumps({
            "type": "item.completed",
            "thread_id": "parent-thread",
            "item": {
                "id": "wait-model",
                "type": "collab_tool_call",
                "tool": "wait",
                "receiver_thread_ids": [child_id],
                "agents_states": {child_id: {"status": "completed", "message": "done"}},
                "status": "completed",
            },
        }),
    ]) + "\n"


def _child_command_jsonl(thread_id, command):
    return json.dumps({
        "type": "item.completed",
        "thread_id": thread_id,
        "item": {
            "id": "cmd-1",
            "type": "command_execution",
            "command": command,
            "status": "completed",
        },
    }) + "\n"


def _write_trial(trial_dir, child_command="pwd", include_manifest=True):
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "codex-output.jsonl").write_text(_parent_spawn_wait_jsonl("thread-1"))
    trace = trial_dir / "traces" / "subagents" / "model-thread-1.jsonl"
    trace.parent.mkdir(parents=True)
    trace.write_text(_child_command_jsonl("thread-1", child_command))
    if include_manifest:
        (trial_dir / "traces" / "manifest.json").write_text(json.dumps({
            "schema_version": "dab-subagent-traces-v1",
            "capture_source": "codex-hooks",
            "capture_status": "complete",
            "expected_subagent_count": 1,
            "captured_subagent_count": 1,
            "traces": [{
                "trace_id": "trace-model",
                "trace_path": "traces/subagents/model-thread-1.jsonl",
                "stage_name": "model",
                "parent_event_id": "spawn-model",
                "subagent_thread_id": "thread-1",
                "coverage_status": "complete",
            }],
        }) + "\n")


@pytest.fixture
def three_trial_run_dir(tmp_path):
    """Run-dir with three trials: clean, tainted (pip install datasets), coverage_missing."""
    run_dir = tmp_path / "run"
    _write_trial(run_dir / "task-a" / "query-1" / "trial-0", child_command="pwd")
    _write_trial(
        run_dir / "task-a" / "query-1" / "trial-1",
        child_command="/bin/bash -lc 'pip install datasets'",
    )
    _write_trial(
        run_dir / "task-a" / "query-1" / "trial-2",
        child_command="pwd",
        include_manifest=False,
    )
    return run_dir


@pytest.fixture
def clean_only_run_dir(tmp_path):
    """Run-dir with a single clean trial."""
    run_dir = tmp_path / "run"
    _write_trial(run_dir / "task-a" / "query-1" / "trial-0", child_command="pwd")
    return run_dir
