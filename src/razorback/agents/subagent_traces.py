# ABOUTME: Per-cell subagent trace-manifest writer. Parses claude-code.txt JSONL,
# ABOUTME: counts Task/Agent tool_use events, emits subagent-trace-manifest.json.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "razorback-subagent-traces-v1"
CAPTURE_SOURCE = "razorback-claude-cli-trace"

# Claude CLI 2.1.148 emits the dispatch primitive as `Agent` on the wire even
# when session-init advertises it as `Task`. Older CLIs emit `Task`. Count both.
_DISPATCH_NAMES = ("Task", "Agent")


def _find_claude_code_txt(cell_dir: Path) -> Path:
    direct = cell_dir / "steps" / "main" / "agent" / "claude-code.txt"
    if direct.is_file():
        return direct
    matches = list(cell_dir.rglob("claude-code.txt"))
    if not matches:
        raise FileNotFoundError(
            f"no claude-code.txt under {cell_dir}; cannot write trace manifest"
        )
    return matches[0]


def _parse_events(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _extract_parent_model(events: list[dict]) -> str | None:
    for ev in events:
        if ev.get("type") == "assistant":
            msg = ev.get("message") or {}
            model = msg.get("model")
            if isinstance(model, str) and model:
                return model
    return None


def _extract_dispatches(events: list[dict]) -> list[dict[str, Any]]:
    dispatches: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("type") != "assistant":
            continue
        msg = ev.get("message") or {}
        for block in msg.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            name = block.get("name")
            if name not in _DISPATCH_NAMES:
                continue
            tool_use_id = block.get("id") or ""
            inp = block.get("input") or {}
            subagent_type = inp.get("subagent_type") or ""
            prompt = inp.get("prompt") or ""
            prompt_sha256 = hashlib.sha256(
                prompt.encode("utf-8") if isinstance(prompt, str) else b""
            ).hexdigest()
            dispatches.append(
                {
                    "tool_use_id": tool_use_id,
                    "subagent_type": subagent_type,
                    "prompt_sha256": prompt_sha256,
                    "spawn_index": len(dispatches),
                }
            )
    return dispatches


def write_subagent_trace_manifest(cell_dir: Path) -> dict[str, Any]:
    """Parse the cell's claude-code.txt and write subagent-trace-manifest.json.

    Returns the in-memory manifest dict. Raises FileNotFoundError when no
    claude-code.txt is present under cell_dir.
    """
    cell_dir = Path(cell_dir)
    txt_path = _find_claude_code_txt(cell_dir)
    events = list(_parse_events(txt_path))
    dispatches = _extract_dispatches(events)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "expected": None,
        "captured": len(dispatches),
        "dispatches": dispatches,
        "parent_agent": {"model": _extract_parent_model(events)},
        "capture_source": CAPTURE_SOURCE,
    }
    out_path = cell_dir / "subagent-trace-manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
