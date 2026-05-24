# ABOUTME: Port of dataagentbench/benchmark/tests/test_taint.py with razorback divergence.
# ABOUTME: pip-install rule rebalanced per captain principle (cycle-2 of wp entity).
import json

from razorback.audit import taint


def parent_spawn_wait_jsonl(child_id="thread-1"):
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


def child_command_jsonl(thread_id, command):
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


def codex_event_jsonl(item):
    return json.dumps({
        "type": "item.completed",
        "thread_id": "parent-thread",
        "item": item,
    }) + "\n"


def make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1):
    attempt = tmp_path / "attempt"
    trace = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
    trace.parent.mkdir(parents=True)
    (attempt / "codex-output.jsonl").write_text(parent_spawn_wait_jsonl("thread-1"))
    trace.write_text(child_command_jsonl("thread-1", "pwd"))
    (attempt / "traces" / "manifest.json").write_text(json.dumps({
        "schema_version": "dab-subagent-traces-v1",
        "capture_source": "codex-hooks",
        "capture_status": "complete" if expected == captured else "partial",
        "expected_subagent_count": expected,
        "captured_subagent_count": captured,
        "traces": [{
            "trace_id": "trace-model",
            "trace_path": "traces/subagents/model-thread-1.jsonl",
            "stage_name": "model",
            "parent_event_id": "spawn-model",
            "subagent_thread_id": "thread-1",
            "coverage_status": "complete",
        }],
    }) + "\n")
    return attempt


def test_prompt_and_command_output_mentions_do_not_taint_attempt(tmp_path):
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    (attempt / "codex-output.jsonl").write_text("\n".join([
        codex_event_jsonl({
            "id": "spawn-model",
            "type": "collab_tool_call",
            "tool": "spawn_agent",
            "prompt": "Do not use datasets.load_dataset, web_search, curl, or pip install.",
            "status": "completed",
        }).strip(),
        codex_event_jsonl({
            "id": "cmd-readme",
            "type": "command_execution",
            "command": "sed -n '1,260p' README.md",
            "aggregated_output": "Forbidden examples: datasets.load_dataset and web_search.",
            "status": "completed",
        }).strip(),
    ]) + "\n")

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "clean"
    assert report["findings"] == []


def test_audit_regex_literals_do_not_taint_attempt(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    child = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
    child.write_text(child_command_jsonl(
        "thread-1",
        "python - <<'PY'\n"
        "patterns = [r'datasets\\.load_dataset', r'load_dataset\\(', 'web_search', 'pip install', r'curl .*api', 'wget url']\n"
        "print('\\n'.join(patterns))\n"
        "PY",
    ))

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "clean"
    assert report["findings"] == []


def test_malformed_python_heredoc_does_not_abort_scan(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    child = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
    child.write_text(child_command_jsonl(
        "thread-1",
        "python - <<'PY'\n"
        "if True:\n"
        "    print('ok')\n"
        "  print('bad indent')\n"
        "PY",
    ))

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "clean"
    assert report["findings"] == []


def test_local_rg_audit_pattern_terms_do_not_taint_attempt(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    child = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
    child.write_text(child_command_jsonl(
        "thread-1",
        'bash -lc \'rg -n "huggingface|datasets\\.load_dataset|curl|wget" '
        "/home/exedev/.codex/dab-subagent-hooks.jsonl'",
    ))

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "clean"
    assert report["findings"] == []


def test_subagent_only_forbidden_lookup_taints_attempt(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    child = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
    child.write_text(child_command_jsonl(
        "thread-1",
        "python - <<'PY'\nfrom datasets import load_dataset\nload_dataset('ag_news')\nPY",
    ))

    report = taint.scan_attempt(attempt, taint_policy="taint")

    assert report["status"] == "tainted"
    assert report["findings"][0]["source_kind"] == "subagent_trace"
    assert report["findings"][0]["source_path"] == "traces/subagents/model-thread-1.jsonl"
    assert report["findings"][0]["subagent_thread_id"] == "thread-1"
    assert report["findings"][0]["scanned_field"] == "command.python"


def test_shell_install_or_download_commands_taint_attempt(tmp_path):
    """pip install of a named canonical-data lib is forbidden (razorback divergence)."""
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    child = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
    child.write_text(child_command_jsonl("thread-1", "/bin/bash -lc 'pip install datasets'"))

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    pattern = report["findings"][0]["pattern"]
    assert r"datasets|huggingface|huggingface_hub|transformers|evaluate" in pattern, (
        f"expected new captain-principle regex, got: {pattern!r}"
    )
    assert report["findings"][0]["scanned_field"] == "command.shell"


def test_shell_pip_install_generic_lib_stays_clean(tmp_path):
    """Captain principle: generic compute libraries (rapidfuzz, scikit-learn,
    duckdb, numpy, pandas) are CLEAN. Only the four canonical-data libraries
    are forbidden by name. Mirrors razorback.agents.claude_invoke.DISALLOWED_TOOLS.
    """
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    child = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
    child.write_text(
        child_command_jsonl("thread-1", "/bin/bash -lc 'pip install rapidfuzz'")
        + child_command_jsonl("thread-1", "/bin/bash -lc 'pip install scikit-learn'")
        + child_command_jsonl("thread-1", "/bin/bash -lc 'pip install --user duckdb'")
        + child_command_jsonl("thread-1", "/bin/bash -lc 'pip3 install numpy pandas'")
    )

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "clean", report["findings"]
    assert report["findings"] == []


def test_shell_pip_install_each_named_lib_taints_attempt(tmp_path):
    """All four canonical-data libs in the named list MUST flag."""
    for lib in ("datasets", "huggingface", "huggingface_hub", "transformers", "evaluate"):
        attempt = make_clean_parent_with_trace_manifest(
            tmp_path / lib, expected=1, captured=1,
        )
        child = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
        child.write_text(child_command_jsonl("thread-1", f"/bin/bash -lc 'pip install {lib}'"))
        report = taint.scan_attempt(attempt, taint_policy="fail")
        assert report["status"] == "failed", f"{lib} should taint: {report}"


def test_shell_pip_install_named_lib_with_version_pin_taints_attempt(tmp_path):
    """Version pins (datasets==2.18.0, huggingface_hub>=0.20, transformers~=4.40)
    must still flag — the captain principle is the lib name, not the spec form.
    """
    for spec in ("datasets==2.18.0", "huggingface_hub>=0.20", "transformers~=4.40", "evaluate<0.5"):
        attempt = make_clean_parent_with_trace_manifest(
            tmp_path / spec.replace("=", "_").replace(">", "_").replace("<", "_").replace("~", "_"),
            expected=1, captured=1,
        )
        child = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
        child.write_text(child_command_jsonl("thread-1", f"/bin/bash -lc 'pip install {spec}'"))
        report = taint.scan_attempt(attempt, taint_policy="fail")
        assert report["status"] == "failed", f"{spec} should taint: {report}"


def test_shell_huggingface_cli_taints_attempt(tmp_path):
    """huggingface-cli / hf binaries are forbidden (mirror claude_invoke list)."""
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    child = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
    child.write_text(child_command_jsonl(
        "thread-1", "/bin/bash -lc 'huggingface-cli download fancyzhx/ag_news'",
    ))
    report = taint.scan_attempt(attempt, taint_policy="fail")
    assert report["status"] == "failed"


def test_shell_download_command_still_taints_attempt(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    child = attempt / "traces" / "subagents" / "model-thread-1.jsonl"
    child.write_text(child_command_jsonl("thread-1", "/bin/bash -lc 'curl https://example.com/data.csv'"))

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    assert report["findings"][0]["pattern"] == r"(?m)(?:^|[;&|]\s*)(?:curl|wget)\b"
    assert report["findings"][0]["scanned_field"] == "command.shell"


def test_web_search_tool_execution_taints_attempt(tmp_path):
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    (attempt / "codex-output.jsonl").write_text(codex_event_jsonl({
        "id": "tool-1",
        "type": "tool_execution",
        "tool_name": "web_search",
        "tool_input": {"query": "agnews label"},
        "status": "completed",
    }))

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    assert report["findings"][0]["scanned_field"] == "tool_name"


def test_missing_subagent_trace_coverage_fails_under_fail_policy(tmp_path):
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    (attempt / "codex-output.jsonl").write_text(parent_spawn_wait_jsonl("thread-1"))

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    assert report["findings"][0]["source_kind"] == "trace_manifest"
    assert report["findings"][0]["category"] == "trace_coverage"
    assert report["findings"][0]["status"] == "missing"


def test_partial_subagent_trace_coverage_is_reported_but_clean_under_audit(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=2, captured=1)
    manifest = json.loads((attempt / "traces" / "manifest.json").read_text())
    manifest["capture_status"] = "partial"
    manifest["missing_reason"] = "unmatched_spawn"
    (attempt / "traces" / "manifest.json").write_text(json.dumps(manifest) + "\n")

    report = taint.scan_attempt(attempt, taint_policy="audit")

    assert report["status"] == "clean"
    assert report["findings"][0]["category"] == "trace_coverage"


def test_stale_manifest_with_extra_hook_session_fails_under_fail_policy(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    codex_home = attempt / "_codex_home" / ".codex"
    codex_home.mkdir(parents=True)
    (codex_home / "dab-subagent-hooks.jsonl").write_text("\n".join([
        json.dumps({"hook_event_name": "SessionStart", "session_id": "parent-thread"}),
        json.dumps({"hook_event_name": "PreToolUse", "session_id": "thread-1",
                    "tool_name": "Bash", "tool_input": {"command": "pwd"}}),
        json.dumps({"hook_event_name": "PostToolUse", "session_id": "thread-1",
                    "tool_name": "Bash", "tool_input": {"command": "pwd"}}),
        json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "thread-2",
                    "prompt": "- stage_name: verify\n"}),
    ]) + "\n")

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    finding = report["findings"][0]
    assert finding["category"] == "trace_coverage"
    assert finding["missing_reason"] == "hook_reconciliation_failed"


def test_timed_out_nonterminal_spacedock_attempt_fails_under_fail_policy(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    workspace = attempt / "workspace"
    workspace.mkdir()
    (workspace / "agnews.md").write_text("---\nstatus: analyze\n---\n")
    (attempt / "codex-meta.json").write_text(json.dumps({"timed_out": True, "duration_s": 1800}))

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    assert report["findings"][-1]["category"] == "attempt_incomplete"
    assert report["findings"][-1]["status"] == "timed_out_non_terminal"
    assert report["findings"][-1]["timeout_roots"] == ["."]


def test_timed_out_spacedock_attempt_without_nonterminal_entity_fails_under_fail_policy(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    workspace = attempt / "workspace"
    workspace.mkdir()
    (workspace / "agnews.md").write_text("---\nstatus: done\n---\n")
    (attempt / "codex-meta.json").write_text(json.dumps({"timed_out": True, "duration_s": 1800}))

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    finding = report["findings"][-1]
    assert finding["category"] == "attempt_incomplete"
    assert finding["status"] == "timed_out"
    assert finding["timed_out"] is True
    assert finding["timeout_roots"] == ["."]
    assert "incomplete_entities" not in finding


def test_nested_timed_out_spacedock_attempt_fails_top_level_scan(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    nested = attempt / "fresh" / "query1"
    nested.mkdir(parents=True)
    (nested / "codex-meta.json").write_text(json.dumps({"timed_out": True, "duration_s": 1800}))
    workspace = nested / "workspace"
    workspace.mkdir()
    (workspace / "agnews.md").write_text("---\nstatus: done\n---\n")

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    finding = report["findings"][-1]
    assert finding["category"] == "attempt_incomplete"
    assert finding["status"] == "timed_out"
    assert finding["timeout_roots"] == ["fresh/query1"]


def test_nonterminal_spacedock_attempt_without_timeout_fails_under_fail_policy(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    workspace = attempt / "workspace"
    workspace.mkdir()
    (workspace / "agnews.md").write_text("---\nstatus: verify\n---\n")

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    finding = report["findings"][-1]
    assert finding["category"] == "attempt_incomplete"
    assert finding["status"] == "non_terminal"
    assert finding["timed_out"] is False
    assert finding["incomplete_entities"] == [{
        "path": "workspace/agnews.md",
        "status": "verify",
    }]


def test_nested_nonterminal_spacedock_attempt_fails_under_fail_policy(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    workspace = attempt / "fresh" / "query1" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "agnews.md").write_text("---\nstatus: analyze\n---\n")

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    finding = report["findings"][-1]
    assert finding["category"] == "attempt_incomplete"
    assert finding["incomplete_entities"] == [{
        "path": "fresh/query1/workspace/agnews.md",
        "status": "analyze",
    }]


def test_fresh_nested_subagent_trace_forbidden_lookup_fails_top_level_attempt(tmp_path):
    attempt = tmp_path / "attempt"
    nested = attempt / "fresh" / "query1"
    trace = nested / "traces" / "subagents" / "model-thread-1.jsonl"
    trace.parent.mkdir(parents=True)
    (nested / "codex-output.jsonl").write_text(parent_spawn_wait_jsonl("thread-1"))
    trace.write_text(child_command_jsonl(
        "thread-1",
        "python - <<'PY'\nfrom datasets import load_dataset\nload_dataset('ag_news')\nPY",
    ))
    (nested / "traces" / "manifest.json").write_text(json.dumps({
        "schema_version": "dab-subagent-traces-v1",
        "capture_source": "codex-hooks",
        "capture_status": "complete",
        "expected_subagent_count": 1,
        "captured_subagent_count": 1,
        "traces": [{
            "trace_id": "trace-model",
            "trace_path": "traces/subagents/model-thread-1.jsonl",
            "stage_name": "model",
            "subagent_thread_id": "thread-1",
            "coverage_status": "complete",
        }],
    }) + "\n")

    report = taint.scan_attempt(attempt, taint_policy="fail")

    assert report["status"] == "failed"
    finding = report["findings"][0]
    assert finding["source_kind"] == "subagent_trace"
    assert finding["source_path"] == "fresh/query1/traces/subagents/model-thread-1.jsonl"
    assert finding["subagent_thread_id"] == "thread-1"


def test_nested_subagent_trace_forbidden_lookup_taints_attempt(tmp_path):
    attempt = make_clean_parent_with_trace_manifest(tmp_path, expected=1, captured=1)
    nested_trace = attempt / "traces" / "subagents" / "model-thread-2.jsonl"
    nested_trace.write_text(child_command_jsonl(
        "thread-2",
        "python - <<'PY'\nfrom datasets import load_dataset\nload_dataset('ag_news')\nPY",
    ))
    manifest = json.loads((attempt / "traces" / "manifest.json").read_text())
    manifest["nested_subagent_count"] = 1
    manifest["traces"].append({
        "trace_id": "trace-nested",
        "trace_path": "traces/subagents/model-thread-2.jsonl",
        "stage_name": "model",
        "parent_event_id": None,
        "parent_subagent_thread_id": "thread-1",
        "subagent_thread_id": "thread-2",
        "coverage_status": "complete",
    })
    (attempt / "traces" / "manifest.json").write_text(json.dumps(manifest) + "\n")

    report = taint.scan_attempt(attempt, taint_policy="taint")

    assert report["status"] == "tainted"
    finding = report["findings"][0]
    assert finding["source_path"] == "traces/subagents/model-thread-2.jsonl"
    assert finding["subagent_thread_id"] == "thread-2"
    assert finding["trace_id"] == "trace-nested"
