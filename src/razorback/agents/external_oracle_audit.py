# ABOUTME: Per-cell external-oracle audit. Scans claude-code.txt tool_use events
# ABOUTME: for forbidden patterns from DAB verify-stage contract; exits 0/2/3.

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = "razorback-external-oracle-audit-v1"
SIDECAR_FILENAME = "external-oracle-audit.json"

EXIT_OK = 0
EXIT_EXTERNAL_ORACLE = 2
EXIT_TRACE_MISSING = 3

_KNOWN_PUBLIC_HOSTS = (
    "raw.githubusercontent.com",
    "huggingface.co",
    "datasets-server.huggingface.co",
    "api.github.com",
    "kaggle.com",
    "drive.google.com",
)

_PUBLIC_HOST_ALTERNATION = "|".join(re.escape(h) for h in _KNOWN_PUBLIC_HOSTS)


def _compile(pattern: str, flags: int = 0) -> re.Pattern[str]:
    return re.compile(pattern, flags)


_BASH_READ_PATTERNS: list[tuple[str, str, re.Pattern[str], str]] = [
    (
        "huggingface",
        "huggingface (host or library reference)",
        _compile(r"huggingface", re.IGNORECASE),
        "confirmed",
    ),
    (
        "load_dataset",
        "datasets.load_dataset() call",
        _compile(r"\b(?:datasets\.)?load_dataset\s*\("),
        "confirmed",
    ),
    (
        "hf_uri",
        "hf:// URI scheme",
        _compile(r"\bhf://"),
        "confirmed",
    ),
    (
        "from_datasets_import",
        "from datasets import ...",
        _compile(r"\bfrom\s+datasets\s+import\b"),
        "confirmed",
    ),
    (
        "requests_get_public_host",
        "requests.get() to a known public data host",
        _compile(
            r"requests\.get\s*\(\s*['\"]https?://(?:" + _PUBLIC_HOST_ALTERNATION + ")",
        ),
        "confirmed",
    ),
    (
        "llm_oracle",
        "LLM-as-oracle pattern (asking another model for the answer)",
        _compile(r"\b(?:openai|anthropic\.messages\.create|google\.generativeai)\b"),
        "suspected",
    ),
]

_WEB_TOOL_NAMES = {"WebSearch", "WebFetch"}


def _find_claude_code_txt(cell_dir: Path) -> Path:
    direct = cell_dir / "steps" / "main" / "agent" / "claude-code.txt"
    if direct.is_file():
        return direct
    matches = list(cell_dir.rglob("claude-code.txt"))
    if not matches:
        raise FileNotFoundError(
            f"no claude-code.txt under {cell_dir}; cannot run external-oracle audit"
        )
    return matches[0]


def _parse_events(path: Path) -> Iterator[tuple[int, dict]]:
    """Yield (line_number, event_dict) for every parseable JSONL row."""
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw or not raw.startswith("{"):
                continue
            try:
                yield lineno, json.loads(raw)
            except json.JSONDecodeError:
                continue


def _iter_tool_uses(
    events: Iterator[tuple[int, dict]],
) -> Iterator[tuple[int, int, dict]]:
    """Yield (event_index, line_number, tool_use_block) for assistant tool_use blocks.

    event_index counts ALL events (not just assistant ones) so it lines up with
    the integer offset a human would compute from the JSONL file. line_number
    is the 1-based file line.
    """
    event_index = -1
    for lineno, ev in events:
        event_index += 1
        if ev.get("type") != "assistant":
            continue
        msg = ev.get("message") or {}
        for block in msg.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            yield event_index, lineno, block


def _scan_block(event_index: int, line_number: int, block: dict) -> list[dict[str, Any]]:
    name = block.get("name") or ""
    inp = block.get("input") or {}
    findings: list[dict[str, Any]] = []

    if name in _WEB_TOOL_NAMES:
        findings.append(
            {
                "event_index": event_index,
                "line_number": line_number,
                "pattern_id": "web_search_tool",
                "pattern_label": f"web tool invocation: {name}",
                "severity": "confirmed",
                "snippet": f"tool_use name={name}",
            }
        )
        return findings

    if name not in ("Bash", "Read"):
        return findings

    target = inp.get("command") if name == "Bash" else inp.get("file_path")
    if not isinstance(target, str) or not target:
        return findings

    for pid, label, rex, severity in _BASH_READ_PATTERNS:
        if rex.search(target):
            findings.append(
                {
                    "event_index": event_index,
                    "line_number": line_number,
                    "pattern_id": pid,
                    "pattern_label": label,
                    "severity": severity,
                    "snippet": target[:200],
                }
            )

    # Broad requests.get without a known public host → suspected.
    if (
        name == "Bash"
        and re.search(r"\brequests\.get\s*\(", target)
        and not any(f["pattern_id"] == "requests_get_public_host" for f in findings)
    ):
        findings.append(
            {
                "event_index": event_index,
                "line_number": line_number,
                "pattern_id": "requests_get_unknown_host",
                "pattern_label": "requests.get() to an un-classified host",
                "severity": "suspected",
                "snippet": target[:200],
            }
        )

    return findings


def scan_cell(cell_dir: Path) -> dict[str, Any]:
    """Scan a cell run-dir's claude-code.txt for forbidden patterns.

    Raises FileNotFoundError when no claude-code.txt is present under cell_dir.
    """
    cell_dir = Path(cell_dir)
    txt_path = _find_claude_code_txt(cell_dir)

    findings: list[dict[str, Any]] = []
    for event_index, line_number, block in _iter_tool_uses(_parse_events(txt_path)):
        findings.extend(_scan_block(event_index, line_number, block))

    confirmed = sum(1 for f in findings if f["severity"] == "confirmed")
    suspected = sum(1 for f in findings if f["severity"] == "suspected")
    return {
        "schema_version": SCHEMA_VERSION,
        "trace_path": str(txt_path),
        "findings": findings,
        "confirmed_count": confirmed,
        "suspected_count": suspected,
    }


def _write_sidecar(cell_dir: Path, payload: dict[str, Any]) -> Path:
    out = cell_dir / SIDECAR_FILENAME
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        print(
            "usage: python -m razorback.agents.external_oracle_audit <cell-dir>",
            file=sys.stderr,
        )
        return 64
    cell_dir = Path(args[0])
    try:
        payload = scan_cell(cell_dir)
    except FileNotFoundError as exc:
        print(f"trace-missing: {exc}", file=sys.stderr)
        # Still write a sidecar so the dispatcher can surface the error state.
        try:
            cell_dir.mkdir(parents=True, exist_ok=True)
            _write_sidecar(
                cell_dir,
                {
                    "schema_version": SCHEMA_VERSION,
                    "trace_path": None,
                    "findings": [],
                    "confirmed_count": 0,
                    "suspected_count": 0,
                    "error": "trace-missing",
                },
            )
        except OSError:
            pass
        return EXIT_TRACE_MISSING

    _write_sidecar(cell_dir, payload)

    for f in payload["findings"]:
        print(
            f"line={f['line_number']:>4} ev={f['event_index']:>3} "
            f"id={f['pattern_id']:<26} sev={f['severity']:<9} "
            f"snippet={f['snippet'][:160]!r}"
        )

    if payload["confirmed_count"] > 0:
        print(
            f"external-oracle-cheating: {payload['confirmed_count']} confirmed findings "
            f"in {payload['trace_path']}",
            file=sys.stderr,
        )
        return EXIT_EXTERNAL_ORACLE

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
