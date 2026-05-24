# ABOUTME: Per-cell subagent trace-manifest writer. Parses runtime JSONL logs,
# ABOUTME: counts dispatch events, emits subagent-trace-manifest.json.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "razorback-subagent-traces-v1"
CLAUDE_CAPTURE_SOURCE = "razorback-claude-cli-trace"
CODEX_CAPTURE_SOURCE = "razorback-codex-cli-trace"

# Claude CLI 2.1.148 emits the dispatch primitive as `Agent` on the wire even
# when session-init advertises it as `Task`. Older CLIs emit `Task`. Count both.
_DISPATCH_NAMES = ("Task", "Agent")
_CODEX_DISPATCH_TOOLS = ("spawn_agent", "spawn")


def _find_runtime_log(cell_dir: Path) -> tuple[Path, str]:
    direct = cell_dir / "steps" / "main" / "agent" / "claude-code.txt"
    if direct.is_file():
        return direct, "claude"
    matches = list(cell_dir.rglob("claude-code.txt"))
    if matches:
        return matches[0], "claude"

    direct = cell_dir / "steps" / "main" / "agent" / "codex.txt"
    if direct.is_file():
        return direct, "codex"
    matches = list(cell_dir.rglob("codex.txt"))
    if matches:
        return matches[0], "codex"

    raise FileNotFoundError(
        f"no claude-code.txt or codex.txt under {cell_dir}; cannot write trace manifest"
    )


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


def _prompt_field(prompt: str, field: str) -> str | None:
    prefix = f"{field}:"
    for raw_line in prompt.splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def _codex_dispatch_type(item: dict[str, Any], prompt: str) -> str:
    for key in ("subagent_type", "agent_type", "dispatch_agent_id"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    nested = item.get("input")
    if isinstance(nested, dict):
        for key in ("subagent_type", "agent_type", "dispatch_agent_id"):
            value = nested.get(key)
            if isinstance(value, str) and value:
                return value
    parsed = _prompt_field(prompt, "dispatch_agent_id")
    if parsed:
        return parsed
    if "spacedock:ensign" in prompt:
        return "spacedock:ensign"
    return ""


def _extract_codex_dispatches(events: list[dict]) -> list[dict[str, Any]]:
    dispatches: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("type") != "item.completed":
            continue
        item = ev.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("type") != "collab_tool_call":
            continue
        if item.get("tool") not in _CODEX_DISPATCH_TOOLS:
            continue
        prompt = item.get("prompt") or ""
        if not isinstance(prompt, str):
            prompt = ""
        prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        dispatches.append(
            {
                "tool_use_id": item.get("id") or "",
                "subagent_type": _codex_dispatch_type(item, prompt),
                "prompt_sha256": prompt_sha256,
                "spawn_index": len(dispatches),
            }
        )
    return dispatches


def _extract_codex_parent_model(events: list[dict]) -> str | None:
    for ev in events:
        if ev.get("type") != "turn_context":
            continue
        payload = ev.get("payload") or {}
        model = payload.get("model")
        if isinstance(model, str) and model:
            return model
    return None


def _relative_trace_artifact(path: Path, trial_dir: Path, runtime: str) -> dict[str, str]:
    return {
        "kind": "parent_log",
        "runtime": runtime,
        "path": path.relative_to(trial_dir).as_posix(),
    }


def write_subagent_trace_manifest(
    trial_dir: Path,
    *,
    prompt_mode: str | None = None,
) -> dict[str, Any]:
    """Parse the trial's runtime JSONL and write subagent-trace-manifest.json.

    Returns the in-memory manifest dict. Raises FileNotFoundError when no
    supported runtime JSONL is present under trial_dir.
    """
    trial_dir = Path(trial_dir)
    txt_path, runtime = _find_runtime_log(trial_dir)
    events = list(_parse_events(txt_path))
    if runtime == "claude":
        dispatches = _extract_dispatches(events)
        parent_model = _extract_parent_model(events)
        capture_source = CLAUDE_CAPTURE_SOURCE
    else:
        dispatches = _extract_codex_dispatches(events)
        parent_model = _extract_codex_parent_model(events)
        capture_source = CODEX_CAPTURE_SOURCE
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "trial": {"trial_id": trial_dir.name},
        "prompt_mode": prompt_mode,
        "trace_artifacts": [
            _relative_trace_artifact(txt_path, trial_dir, runtime),
        ],
        "expected": None,
        "captured": len(dispatches),
        "dispatches": dispatches,
        "parent_agent": {"model": parent_model},
        "capture_source": capture_source,
    }
    out_path = trial_dir / "subagent-trace-manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
