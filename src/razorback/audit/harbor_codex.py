# ABOUTME: Harbor Codex trace discovery/scanning for `rk audit`.
# ABOUTME: Adapts Codex JSON event shapes while keeping the DAB taint port stable.

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from razorback.audit import taint


_SHELL_TOOL_NAMES = {
    "Bash",
    "Shell",
    "exec",
    "exec_command",
    "unified_exec.exec_command",
    "functions.exec_command",
}
_COMMAND_KEYS = {"cmd", "command", "shell", "script"}
_EXTRA_SHELL_PATTERNS = {
    "forbidden_lookup": [
        re.compile(r"(?m)(?:^|[;&|]\s*)git\s+clone\b"),
        re.compile(
            r"(?m)(?:^|[;&|]\s*)docker\s+"
            r"(?:ps|inspect|exec|cp|run|compose|container|image|network|volume|pull)\b"
        ),
        re.compile(r"/var/run/docker\.sock"),
    ],
}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _trial_root_for_source(path: Path) -> Path | None:
    for parent in path.parents:
        if parent.name == "steps":
            return parent.parent
    return None


def discover_trial_roots(run_dir: Path) -> list[Path]:
    """Return Harbor trial roots with Codex traces under steps/*/agent."""
    run_dir = Path(run_dir)
    seen: set[Path] = set()
    roots: list[Path] = []
    for pattern in (
        "**/steps/*/agent/codex.txt",
        "**/steps/*/agent/sessions/**/*.jsonl",
    ):
        for hit in sorted(run_dir.glob(pattern)):
            trial_root = _trial_root_for_source(hit)
            if trial_root is None or trial_root in seen:
                continue
            seen.add(trial_root)
            roots.append(trial_root)
    return roots


def _trace_sources(trial_root: Path) -> list[tuple[str, Path]]:
    sources: list[tuple[str, Path]] = []
    for agent_dir in sorted(trial_root.glob("steps/*/agent")):
        codex_txt = agent_dir / "codex.txt"
        if codex_txt.is_file():
            sources.append(("harbor_codex_text", codex_txt))
        for session in sorted((agent_dir / "sessions").glob("**/*.jsonl")):
            sources.append(("harbor_codex_session", session))
    return sources


def _loads_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _walk_command_values(value: Any) -> list[str]:
    commands: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in _COMMAND_KEYS and isinstance(nested, str):
                commands.append(nested)
            else:
                commands.extend(_walk_command_values(nested))
    elif isinstance(value, list):
        for item in value:
            commands.extend(_walk_command_values(item))
    return commands


def _scan_command(command: str, base: dict[str, Any]) -> list[dict[str, Any]]:
    findings = taint._scan_command(command, base)
    if findings:
        return findings
    for script in taint._shell_scripts(command):
        shell_script = taint._mask_shell_quoted_strings(
            taint._mask_python_heredoc_bodies(script)
        )
        findings.extend(
            taint._scan_text(
                shell_script,
                {**base, "scanned_field": "command.shell"},
                _EXTRA_SHELL_PATTERNS,
            )
        )
        if findings:
            return findings
    return findings


def _scan_tool_name(tool_name: str, base: dict[str, Any]) -> list[dict[str, Any]]:
    return taint._scan_text(
        tool_name,
        {**base, "scanned_field": "tool_name"},
        taint.FORBIDDEN_TOOL_PATTERNS,
    )


def _shell_tool_name(tool_name: str) -> bool:
    name = Path(tool_name).name
    return name in _SHELL_TOOL_NAMES or name.lower() in {"bash", "shell", "sh"}


def _scan_response_item_event(event: dict[str, Any], base: dict[str, Any]) -> list[dict[str, Any]]:
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return []

    payload_type = payload.get("type")
    event_base = {
        **base,
        "event_id": payload.get("call_id") or payload.get("id"),
        "event_type": event.get("type"),
        "tool_type": payload_type,
    }

    if payload_type == "web_search_call":
        return _scan_tool_name("web_search_call", event_base)

    if payload_type not in {"function_call", "custom_tool_call"}:
        return []

    findings: list[dict[str, Any]] = []
    tool_name = payload.get("name")
    if isinstance(tool_name, str):
        findings.extend(_scan_tool_name(tool_name, event_base))

    raw_arguments = payload.get("arguments")
    if payload_type == "custom_tool_call":
        raw_arguments = payload.get("input")
    parsed_arguments = _loads_json(raw_arguments)

    for command in _walk_command_values(parsed_arguments):
        findings.extend(_scan_command(command, event_base))

    if (
        not findings
        and isinstance(raw_arguments, str)
        and isinstance(tool_name, str)
        and Path(tool_name).name in _SHELL_TOOL_NAMES
    ):
        findings.extend(_scan_command(raw_arguments, event_base))

    return findings


def _scan_item_completed_event(event: dict[str, Any], base: dict[str, Any]) -> list[dict[str, Any]]:
    item = event.get("item")
    if not isinstance(item, dict):
        return []

    item_type = item.get("type")
    event_base = {
        **base,
        "event_id": item.get("id"),
        "event_type": event.get("type"),
        "tool_type": item_type,
    }

    findings = taint._scan_event(event, event_base)
    if item_type != "tool_execution":
        return findings

    tool_name = item.get("tool_name") or item.get("tool") or item.get("name")
    raw_input = item.get("tool_input")
    if raw_input is None:
        raw_input = item.get("input")
    if raw_input is None:
        raw_input = item.get("arguments")
    parsed_input = _loads_json(raw_input)

    for command in _walk_command_values(parsed_input):
        findings.extend(_scan_command(command, event_base))

    if (
        not findings
        and isinstance(raw_input, str)
        and isinstance(tool_name, str)
        and _shell_tool_name(tool_name)
    ):
        findings.extend(_scan_command(raw_input, event_base))

    return findings


def _scan_codex_event(event: Any, base: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(event, dict):
        return []
    if event.get("type") == "response_item":
        return _scan_response_item_event(event, base)
    if event.get("type") == "item.completed":
        return _scan_item_completed_event(event, base)
    return []


def _scan_jsonl(path: Path, trial_root: Path, source_kind: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_no, line in enumerate(
        path.read_text(errors="ignore").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        base = {
            "source_kind": source_kind,
            "source_path": _rel(path, trial_root),
            "trace_id": None,
            "subagent_thread_id": None,
            "stage_name": None,
            "event_id": None,
            "event_type": None,
            "tool_type": None,
            "line": line_no,
        }
        findings.extend(_scan_codex_event(event, base))
    return findings


def scan_trial(trial_root: Path) -> list[dict[str, Any]]:
    """Scan Harbor Codex solver traces for forbidden lookup attempts."""
    trial_root = Path(trial_root)
    findings: list[dict[str, Any]] = []
    try:
        for source_kind, path in _trace_sources(trial_root):
            findings.extend(_scan_jsonl(path, trial_root, source_kind))
    except Exception as exc:
        findings.append({
            "source_kind": "harbor_codex_scanner",
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
