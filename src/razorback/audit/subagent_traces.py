# ABOUTME: Port of dataagentbench/benchmark/lib/subagent_traces.py (read-side closure, 2026-05-20).
# ABOUTME: Read-side surface used by razorback.audit.taint; capture-side helpers stay un-ported.

"""Port of dataagentbench/benchmark/lib/subagent_traces.py (read-side closure only).

Source: /Users/clkao/git/dataagentbench/benchmark/lib/subagent_traces.py (870 LoC, ported 2026-05-20).

## Ported (read-side)
- IGNORED_TRACE_ROOT_PARTS, SCHEMA_VERSION
- _codex_trace_paths (used by _hook_event_counts to locate the host hook log)
- _read_jsonl
- _collab_item
- _stage_from_prompt
- parse_parent_lifecycle
- parent_has_completed_spawns (used by taint.discover_scan_inputs)
- _under_ignored_trace_root, iter_trace_roots (used by taint.discover_scan_inputs + taint._attempt_timeout_roots)
- _hook_event_counts (used by hook_reconciliation_issues)
- hook_reconciliation_issues (used by taint._coverage_findings)

## Dropped (capture-side, lives in the runtime, not razorback's audit)
- TraceCaptureConfig, TRACE_HOOK_SCRIPT
- prepare_codex_spacedock_trace_capture
- _hook_event_to_trace_events, _hook_tool_item
- materialize_hook_traces
- sha256_file (capture-side; no read-side caller in the closure)
- _trace_stats, _trace_files_by_thread, _hook_stage_by_thread, first_thread_id
- _entry_for_trace, reconcile_traces
- coverage_missing_reason, write_trace_manifest
- read_trace_coverage, combine_coverage_statuses, read_trace_coverage_recursive
"""
import json
from pathlib import Path


SCHEMA_VERSION = "dab-subagent-traces-v1"
IGNORED_TRACE_ROOT_PARTS = {
    "_codex_home",
    "_claude_home",
    ".codex",
    ".tmp",
    ".git",
    "workspace",
}


def _codex_trace_paths(attempt_root, isolated):
    attempt_root = Path(attempt_root)
    codex_home = attempt_root / "_codex_home" / ".codex"
    host_hook_log = codex_home / "dab-subagent-hooks.jsonl"
    host_script = codex_home / "dab-subagent-trace-hook.py"
    if isolated:
        runtime_hook_log = "/home/exedev/.codex/dab-subagent-hooks.jsonl"
        runtime_script = "/home/exedev/.codex/dab-subagent-trace-hook.py"
    else:
        runtime_hook_log = str(host_hook_log.resolve())
        runtime_script = str(host_script.resolve())
    return codex_home, host_hook_log, host_script, runtime_hook_log, runtime_script


def _read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    events = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _collab_item(event):
    item = event.get("item") if isinstance(event, dict) else None
    if not isinstance(item, dict):
        return None
    if item.get("type") != "collab_tool_call":
        return None
    return item


def _stage_from_prompt(prompt):
    for line in (prompt or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        if stripped.startswith("stage_name:"):
            return stripped.split(":", 1)[1].strip()
    return None


def parse_parent_lifecycle(parent_log):
    spawns = []
    waits = {}
    parent_thread_id = None
    for event in _read_jsonl(parent_log):
        parent_thread_id = parent_thread_id or event.get("thread_id")
        item = _collab_item(event)
        if item is None:
            continue
        tool = item.get("tool")
        if tool == "spawn_agent":
            for worker in item.get("receiver_thread_ids") or []:
                spawns.append({
                    "parent_event_id": item.get("id"),
                    "stage_name": _stage_from_prompt(item.get("prompt")) or "subagent",
                    "subagent_thread_id": worker,
                    "parent_thread_id": event.get("thread_id") or parent_thread_id,
                    "worker_key": "spacedock-ensign" if "spacedock-ensign" in (item.get("prompt") or "") else None,
                })
        elif tool in {"wait", "wait_agent"}:
            states = item.get("agents_states") or {}
            for worker in item.get("receiver_thread_ids") or states.keys():
                state = states.get(worker) if isinstance(states, dict) else None
                if event.get("type") == "item.started":
                    status = item.get("status") or "in_progress"
                elif event.get("type") == "item.completed":
                    status = item.get("status") or "completed"
                else:
                    status = item.get("status") or "unknown"
                message = None
                if isinstance(state, dict):
                    status = state.get("status") or status
                    message = state.get("message")
                waits[worker] = {
                    "wait_event_id": item.get("id"),
                    "status": status,
                    "message": message,
                }
    return spawns, waits, parent_thread_id


def parent_has_completed_spawns(parent_log):
    spawns, waits, _ = parse_parent_lifecycle(parent_log)
    if not spawns:
        return False
    if not waits:
        return bool(spawns)
    return any(spawn["subagent_thread_id"] in waits for spawn in spawns)


def _under_ignored_trace_root(path, attempt_root):
    try:
        parts = Path(path).relative_to(attempt_root).parts
    except ValueError:
        parts = Path(path).parts
    return any(part in IGNORED_TRACE_ROOT_PARTS for part in parts)


def iter_trace_roots(attempt_root):
    attempt_root = Path(attempt_root)
    roots = []

    def add(root):
        root = Path(root)
        if root in roots or _under_ignored_trace_root(root, attempt_root):
            return
        roots.append(root)

    add(attempt_root)
    for mode in ("fresh", "context-fresh"):
        mode_dir = attempt_root / mode
        if mode_dir.is_dir():
            for child in sorted(mode_dir.iterdir()):
                if child.is_dir():
                    add(child)
    context_dir = attempt_root / "context"
    if context_dir.is_dir():
        add(context_dir)

    for marker in ("traces/manifest.json", "codex-output.jsonl", "claude-output.jsonl"):
        for path in sorted(attempt_root.rglob(marker)):
            add(path.parent.parent if marker == "traces/manifest.json" else path.parent)
    return roots


def _hook_event_counts(attempt_root, parent_thread_id=None):
    attempt_root = Path(attempt_root)
    _, hook_log, _, _, _ = _codex_trace_paths(attempt_root, isolated=False)
    counts = {}
    if not hook_log.exists():
        return counts
    for event in _read_jsonl(hook_log):
        session_id = event.get("session_id")
        if not session_id or session_id == parent_thread_id:
            continue
        counts[session_id] = counts.get(session_id, 0) + 1
    return counts


def hook_reconciliation_issues(attempt_root, manifest):
    """Return hook/trace mismatches not represented by the manifest.

    Codex can leave the parent JSONL truncated while workers continue
    writing hook events. The raw hook log is therefore the upper bound on
    preserved subagent activity for an attempt.
    """
    attempt_root = Path(attempt_root)
    parent_thread_id = (manifest or {}).get("parent_thread_id")
    if not parent_thread_id:
        _, _, parent_thread_id = parse_parent_lifecycle(attempt_root / "codex-output.jsonl")
    hook_counts = _hook_event_counts(attempt_root, parent_thread_id)
    if not hook_counts:
        return []

    entries = (manifest or {}).get("traces") or []
    by_thread = {
        entry.get("subagent_thread_id"): entry
        for entry in entries
        if entry.get("subagent_thread_id")
    }
    issues = []
    for thread_id, hook_count in sorted(hook_counts.items()):
        entry = by_thread.get(thread_id)
        if entry is None:
            issues.append({
                "reason": "orphan_hook_session",
                "subagent_thread_id": thread_id,
                "hook_event_count": hook_count,
                "trace_event_count": 0,
            })
            continue
        trace_path = entry.get("trace_path")
        if not trace_path:
            trace_count = 0
        else:
            trace_count = len(_read_jsonl(attempt_root / trace_path))
        if trace_count < hook_count:
            issues.append({
                "reason": "truncated_hook_trace",
                "subagent_thread_id": thread_id,
                "hook_event_count": hook_count,
                "trace_event_count": trace_count,
            })
    return issues
