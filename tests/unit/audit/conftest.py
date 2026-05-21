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


def _codex_response_item(payload):
    return json.dumps({
        "type": "response_item",
        "timestamp": "2026-05-21T00:00:00Z",
        "payload": payload,
    }) + "\n"


def _codex_custom_tool_call(command, call_id="call-1"):
    return _codex_response_item({
        "type": "custom_tool_call",
        "call_id": call_id,
        "name": "unified_exec.exec_command",
        "input": json.dumps({"cmd": command}),
        "status": "completed",
    })


def _codex_item_completed_command(command):
    return json.dumps({
        "type": "item.completed",
        "thread_id": "parent-thread",
        "item": {
            "id": "cmd-1",
            "type": "command_execution",
            "command": command,
            "status": "completed",
        },
    }) + "\n"


def _write_harbor_codex_trial(
    trial_dir,
    *,
    codex_txt="",
    session_jsonl="",
    job_log=None,
):
    agent_dir = trial_dir / "steps" / "main" / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    if codex_txt is not None:
        (agent_dir / "codex.txt").write_text(codex_txt)
    if session_jsonl:
        session_dir = agent_dir / "sessions" / "2026" / "05" / "21"
        session_dir.mkdir(parents=True)
        (session_dir / "session.jsonl").write_text(session_jsonl)
    if job_log is not None:
        (trial_dir / "job.log").write_text(job_log)


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


@pytest.fixture
def harbor_codex_clean_txt_run_dir(tmp_path):
    """Harbor-shaped Codex run-dir with one clean codex.txt trace."""
    run_dir = tmp_path / "run"
    _write_harbor_codex_trial(
        run_dir / "task-a" / "query-1" / "trial-0",
        codex_txt=_codex_response_item({
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "done"}],
        }),
    )
    return run_dir


@pytest.fixture
def harbor_codex_tainted_session_run_dir(tmp_path):
    """Harbor-shaped Codex run-dir with a forbidden solver command in session JSONL."""
    run_dir = tmp_path / "run"
    _write_harbor_codex_trial(
        run_dir / "task-a" / "query-1" / "trial-0",
        codex_txt="",
        session_jsonl=_codex_custom_tool_call("curl https://example.com/data.csv"),
    )
    return run_dir


@pytest.fixture
def harbor_codex_tainted_txt_run_dir(tmp_path):
    """Harbor-shaped Codex run-dir with a forbidden solver command in codex.txt."""
    run_dir = tmp_path / "run"
    _write_harbor_codex_trial(
        run_dir / "task-a" / "query-1" / "trial-0",
        codex_txt=_codex_item_completed_command("curl https://example.com/data.csv"),
    )
    return run_dir


@pytest.fixture
def harbor_codex_setup_install_only_run_dir(tmp_path):
    """Harbor-shaped Codex run-dir where install text is outside the solver trace."""
    run_dir = tmp_path / "run"
    _write_harbor_codex_trial(
        run_dir / "task-a" / "query-1" / "trial-0",
        codex_txt=_codex_custom_tool_call("pwd"),
        job_log=(
            "setup: npm install -g @openai/codex\n"
            "setup: pip install harbor\n"
        ),
    )
    return run_dir
