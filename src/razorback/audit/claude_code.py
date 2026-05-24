# ABOUTME: Claude-cli (claude-code.txt) trace discovery/scanning for rk audit.
# ABOUTME: Adapts the assistant.tool_use event shape while keeping taint.py stable.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from razorback.audit import taint


_BASH_READ_NAMES = {"Bash", "Read"}
_WEB_TOOL_NAMES = {"WebSearch", "WebFetch"}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _trial_root_for_source(path: Path) -> Path | None:
    for parent in path.parents:
        if parent.name == "steps":
            return parent.parent
    for parent in path.parents:
        if parent.name == "agent":
            return parent.parent
    return None


def discover_trial_roots(run_dir: Path) -> list[Path]:
    """Return trial roots that contain a claude-cli ``claude-code.txt`` trace."""
    run_dir = Path(run_dir)
    seen: set[Path] = set()
    roots: list[Path] = []
    for pattern in (
        "**/agent/claude-code.txt",
        "**/steps/*/agent/claude-code.txt",
    ):
        for hit in sorted(run_dir.glob(pattern)):
            trial_root = _trial_root_for_source(hit)
            if trial_root is None or trial_root in seen:
                continue
            seen.add(trial_root)
            roots.append(trial_root)
    return roots


def _trace_sources(trial_root: Path) -> list[Path]:
    sources: list[Path] = []
    agent_dirs: list[Path] = []
    direct_agent_dir = trial_root / "agent"
    if direct_agent_dir.is_dir():
        agent_dirs.append(direct_agent_dir)
    agent_dirs.extend(sorted(trial_root.glob("steps/*/agent")))
    for agent_dir in agent_dirs:
        candidate = agent_dir / "claude-code.txt"
        if candidate.is_file():
            sources.append(candidate)
    return sources


def _iter_assistant_tool_uses(events: list[tuple[int, dict]]):
    """Yield ``(line_no, event_id, block)`` for each assistant tool_use block."""
    for line_no, event in events:
        if not isinstance(event, dict) or event.get("type") != "assistant":
            continue
        msg = event.get("message") or {}
        msg_id = msg.get("id") if isinstance(msg, dict) else None
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            yield line_no, block.get("id") or msg_id, block


def _scan_tool_use(line_no: int, event_id: Any, block: dict, base_template: dict) -> list[dict[str, Any]]:
    name = block.get("name") or ""
    inp = block.get("input") if isinstance(block.get("input"), dict) else {}

    event_base = {
        **base_template,
        "event_id": event_id,
        "event_type": "assistant",
        "tool_type": "tool_use",
        "line": line_no,
    }

    if name in _WEB_TOOL_NAMES:
        return taint._scan_text(
            name,
            {**event_base, "scanned_field": "tool_name"},
            taint.FORBIDDEN_TOOL_PATTERNS,
        ) or [{
            **event_base,
            "scanned_field": "tool_name",
            "category": "forbidden_lookup",
            "confidence": "high",
            "pattern": rf"\b{name}\b",
        }]

    if name not in _BASH_READ_NAMES:
        return []

    if name == "Bash":
        command = inp.get("command")
    else:
        command = inp.get("file_path")
    if not isinstance(command, str) or not command:
        return []
    return taint._scan_command(command, event_base)


def _scan_jsonl(path: Path, trial_root: Path) -> list[dict[str, Any]]:
    parsed_events: list[tuple[int, dict]] = []
    for line_no, line in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed_events.append((line_no, event))

    base_template = {
        "source_kind": "claude_code_trace",
        "source_path": _rel(path, trial_root),
        "trace_id": None,
        "subagent_thread_id": None,
        "stage_name": None,
        "event_id": None,
        "event_type": None,
        "tool_type": None,
    }

    findings: list[dict[str, Any]] = []
    for line_no, event_id, block in _iter_assistant_tool_uses(parsed_events):
        findings.extend(_scan_tool_use(line_no, event_id, block, base_template))
    return findings


def scan_trial(trial_root: Path) -> list[dict[str, Any]]:
    """Scan a trial root's claude-cli traces for forbidden lookups."""
    trial_root = Path(trial_root)
    findings: list[dict[str, Any]] = []
    try:
        for path in _trace_sources(trial_root):
            findings.extend(_scan_jsonl(path, trial_root))
    except Exception as exc:
        findings.append({
            "source_kind": "claude_code_scanner",
            "source_path": _rel(trial_root, trial_root),
            "trace_id": None,
            "subagent_thread_id": None,
            "stage_name": None,
            "event_id": None,
            "event_type": None,
            "tool_type": None,
            "category": "scanner_error",
            "confidence": "high",
            "status": type(exc).__name__,
            "message": str(exc),
        })
    return findings
