# ABOUTME: Port of dataagentbench/benchmark/lib/taint.py with razorback divergence.
# ABOUTME: Layer 3 of the leak-protection stack (spec §9.4); driven by rk audit (§3.2).

"""Port of dataagentbench/benchmark/lib/taint.py.

Source: /Users/clkao/git/dataagentbench/benchmark/lib/taint.py (561 LoC, ported 2026-05-20).

Razorback divergence from upstream:
- FORBIDDEN_SHELL_PATTERNS narrows the pip-install rule to the four named
  canonical-data libraries (datasets/huggingface/transformers/evaluate) plus
  the huggingface-cli/hf binaries. Upstream flags ANY ``pip install X`` as
  cheating; the razorback principle is that generic compute libraries
  (rapidfuzz, scikit-learn, duckdb, etc.) are CLEAN — only the named
  canonical-data libs are forbidden. The list mirrors
  razorback.agents.claude_invoke.DISALLOWED_TOOLS so audit and runtime agree.
"""
import json
from pathlib import Path
import re
import shlex
import tokenize
from io import StringIO

from razorback.audit import subagent_traces


# Named canonical-data libraries that razorback forbids by name. Mirrors
# ``Bash(pip install datasets*)`` etc. in razorback.agents.claude_invoke.
_FORBIDDEN_LIB_NAMES = ("datasets", "huggingface", "huggingface_hub", "transformers", "evaluate")
_FORBIDDEN_LIB_ALTERNATION = "|".join(re.escape(name) for name in _FORBIDDEN_LIB_NAMES)

FORBIDDEN_SHELL_PATTERNS = {
    "forbidden_lookup": [
        re.compile(r"(?m)(?:^|[;&|]\s*)(?:curl|wget)\b"),
        re.compile(
            r"(?m)(?:^|[;&|]\s*)(?:python(?:3)?\s+-m\s+pip|pip(?:3)?)\s+install\b"
            r"(?:\s+-[^\s;&|]+)*"  # consume any flag args before the package name
            rf"\s+(?:{_FORBIDDEN_LIB_ALTERNATION})(?:\b|[*=<>~])"
        ),
        re.compile(r"(?m)(?:^|[;&|]\s*)npm\s+install\b"),
        re.compile(r"(?m)(?:^|[;&|]\s*)(?:huggingface-cli|hf)\b"),
    ],
}

FORBIDDEN_TOOL_PATTERNS = {
    "forbidden_lookup": [
        re.compile(r"\bweb_search\b"),
        re.compile(r"\bweb\.run\b"),
    ],
}


def _rel(path, root):
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return Path(path).as_posix()


def discover_scan_inputs(attempt_root):
    attempt_root = Path(attempt_root)
    inputs = []
    for root in subagent_traces.iter_trace_roots(attempt_root):
        for name in ("codex-output.jsonl", "claude-output.jsonl"):
            path = root / name
            if path.exists():
                inputs.append({"source_kind": "parent_log", "path": path})
        manifest_path = root / "traces" / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
            except json.JSONDecodeError:
                manifest = {"capture_status": "partial", "missing_reason": "invalid_manifest", "traces": []}
            inputs.append({"source_kind": "trace_manifest", "path": manifest_path, "manifest": manifest})
            for entry in manifest.get("traces") or []:
                trace_path = root / (entry.get("trace_path") or "")
                if trace_path.exists():
                    inputs.append({"source_kind": "subagent_trace", "path": trace_path, "trace": entry})
        elif subagent_traces.parent_has_completed_spawns(root / "codex-output.jsonl"):
            inputs.append({
                "source_kind": "trace_manifest",
                "path": manifest_path,
                "coverage_status": "missing",
                "missing_reason": "manifest_absent",
            })
    return inputs


def _scan_text(text, base, patterns):
    findings = []
    for category, regexes in patterns.items():
        for regex in regexes:
            if regex.search(text):
                finding = dict(base)
                finding.update({
                    "category": category,
                    "confidence": "high",
                    "pattern": regex.pattern,
                })
                findings.append(finding)
                return findings
    return findings


def _shell_words(command):
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return []


def _shell_scripts(command):
    yield command
    words = _shell_words(command)
    for index, word in enumerate(words[:-1]):
        name = Path(word).name
        if name in {"bash", "sh", "zsh"} and word.endswith(name):
            for opt_index in range(index + 1, len(words) - 1):
                option = words[opt_index]
                if option.startswith("-") and "c" in option:
                    yield words[opt_index + 1]
                    break


def _heredoc_sources(command):
    lines = command.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][\w.-]*)\1", line)
        if not match:
            index += 1
            continue
        terminator = match.group(2)
        body = []
        index += 1
        while index < len(lines):
            if lines[index].strip() == terminator:
                break
            body.append(lines[index])
            index += 1
        if body:
            yield "\n".join(body)
        index += 1


def _line_invokes_python_before_heredoc(line, match):
    prefix = line[:match.start()]
    words = _shell_words(prefix)
    if any(Path(word).name in {"python", "python3"} for word in words):
        return True
    return re.search(r"(?:^|[\s;&|'\"])(?:\S*/)?python(?:3)?\b", prefix) is not None


def _mask_python_heredoc_bodies(script):
    lines = script.splitlines()
    masked = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][\w.-]*)\1", line)
        masked.append(line)
        if not match:
            index += 1
            continue
        terminator = match.group(2)
        is_python_heredoc = _line_invokes_python_before_heredoc(line, match)
        index += 1
        while index < len(lines):
            if lines[index].strip() == terminator:
                masked.append(lines[index])
                index += 1
                break
            if not is_python_heredoc:
                masked.append(lines[index])
            index += 1
    return "\n".join(masked)


def _mask_shell_quoted_strings(script):
    masked = []
    quote = None
    escaped = False
    for char in script:
        if quote is None:
            if char in {"'", '"'}:
                quote = char
                masked.append(char)
            else:
                masked.append(char)
            continue

        if quote == '"' and escaped:
            masked.append(" ")
            escaped = False
            continue
        if quote == '"' and char == "\\":
            masked.append(" ")
            escaped = True
            continue
        if char == quote:
            masked.append(char)
            quote = None
            continue
        if char == "\n":
            masked.append("\n")
            continue
        masked.append(" ")
    return "".join(masked)


def _python_c_sources(script):
    words = _shell_words(script)
    for index, word in enumerate(words[:-1]):
        name = Path(word).name
        if name not in {"python", "python3"}:
            continue
        for opt_index in range(index + 1, len(words)):
            option = words[opt_index]
            if option == "-c" and opt_index + 1 < len(words):
                yield words[opt_index + 1]
                break
            if option.startswith("-c") and len(option) > 2:
                yield option[2:]
                break
            if not option.startswith("-"):
                break


def _python_sources(command):
    seen = set()
    for script in _shell_scripts(command):
        for source in _heredoc_sources(script):
            if source not in seen:
                seen.add(source)
                yield source
        for source in _python_c_sources(script):
            if source not in seen:
                seen.add(source)
                yield source


def _python_tokens(source):
    try:
        tokens = tokenize.generate_tokens(StringIO(source).readline)
        return [
            token
            for token in tokens
            if token.type not in {
                tokenize.ENCODING,
                tokenize.ENDMARKER,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.NEWLINE,
                tokenize.NL,
                tokenize.COMMENT,
                tokenize.STRING,
            }
        ]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []


def _finding(base, category, pattern, line=None):
    finding = dict(base)
    finding.update({
        "category": category,
        "confidence": "high",
        "pattern": pattern,
    })
    if line is not None:
        finding["source_line"] = line
    return finding


def _scan_python_source(source, base):
    tokens = _python_tokens(source)
    strings = [token.string for token in tokens]
    for index, token in enumerate(tokens):
        if strings[index:index + 3] == ["from", "datasets", "import"]:
            return [_finding(base, "forbidden_lookup", "from datasets import", token.start[0])]
        if strings[index] == "load_dataset" and index + 1 < len(strings) and strings[index + 1] == "(":
            return [_finding(base, "forbidden_lookup", "load_dataset(", token.start[0])]
        if (
            strings[index:index + 3] == ["datasets", ".", "load_dataset"]
            and index + 3 < len(strings)
            and strings[index + 3] == "("
        ):
            return [_finding(base, "forbidden_lookup", "datasets.load_dataset(", token.start[0])]
    return []


def _scan_command(command, base):
    findings = []
    for script in _shell_scripts(command):
        shell_script = _mask_shell_quoted_strings(_mask_python_heredoc_bodies(script))
        findings.extend(_scan_text(shell_script, {**base, "scanned_field": "command.shell"}, FORBIDDEN_SHELL_PATTERNS))
    if findings:
        return findings
    for source in _python_sources(command):
        findings.extend(_scan_python_source(source, {**base, "scanned_field": "command.python"}))
        if findings:
            return findings
    return findings


def _scan_event(event, base):
    item = event.get("item") if isinstance(event, dict) else {}
    if not isinstance(item, dict):
        return []
    item_type = item.get("type")
    findings = []
    if item_type == "command_execution":
        command = item.get("command")
        if isinstance(command, str):
            findings.extend(_scan_command(command, base))
    elif item_type == "tool_execution":
        tool_name = item.get("tool_name")
        if isinstance(tool_name, str):
            findings.extend(_scan_text(tool_name, {**base, "scanned_field": "tool_name"}, FORBIDDEN_TOOL_PATTERNS))
        tool_input = item.get("tool_input")
        if isinstance(tool_input, dict):
            findings.extend(_scan_text(
                json.dumps(tool_input, sort_keys=True),
                {**base, "scanned_field": "tool_input"},
                FORBIDDEN_TOOL_PATTERNS,
            ))
    return findings


def _scan_jsonl(path, attempt_root, source_kind, trace=None):
    findings = []
    for line_no, line in enumerate(Path(path).read_text().splitlines(), start=1):
        if not line.strip():
            continue
        event = None
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            pass
        item = event.get("item") if isinstance(event, dict) else {}
        base = {
            "source_kind": source_kind,
            "source_path": _rel(path, attempt_root),
            "trace_id": (trace or {}).get("trace_id"),
            "subagent_thread_id": (trace or {}).get("subagent_thread_id"),
            "stage_name": (trace or {}).get("stage_name"),
            "event_id": item.get("id") if isinstance(item, dict) else None,
            "event_type": event.get("type") if isinstance(event, dict) else None,
            "tool_type": item.get("type") if isinstance(item, dict) else None,
            "line": line_no,
        }
        findings.extend(_scan_event(event, base))
    return findings


def _coverage_findings(scan_input, attempt_root):
    if "manifest" not in scan_input:
        return [{
            "source_kind": "trace_manifest",
            "source_path": _rel(scan_input["path"], attempt_root),
            "trace_id": None,
            "subagent_thread_id": None,
            "stage_name": None,
            "event_id": None,
            "event_type": None,
            "tool_type": None,
            "category": "trace_coverage",
            "confidence": "high",
            "status": scan_input.get("coverage_status", "missing"),
            "missing_reason": scan_input.get("missing_reason", "manifest_absent"),
        }]
    manifest = scan_input["manifest"]
    status = manifest.get("capture_status")
    if status in (None, "complete", "not_applicable"):
        hook_issues = subagent_traces.hook_reconciliation_issues(attempt_root, manifest)
        if not hook_issues:
            return []
        return [{
            "source_kind": "trace_manifest",
            "source_path": _rel(scan_input["path"], attempt_root),
            "trace_id": None,
            "subagent_thread_id": None,
            "stage_name": manifest.get("stage_name"),
            "event_id": None,
            "event_type": None,
            "tool_type": None,
            "category": "trace_coverage",
            "confidence": "high",
            "status": "partial",
            "missing_reason": "hook_reconciliation_failed",
            "hook_reconciliation_issues": hook_issues,
        }]
    return [{
        "source_kind": "trace_manifest",
        "source_path": _rel(scan_input["path"], attempt_root),
        "trace_id": None,
        "subagent_thread_id": None,
        "stage_name": manifest.get("stage_name"),
        "event_id": None,
        "event_type": None,
        "tool_type": None,
        "category": "trace_coverage",
        "confidence": "high",
        "status": status,
        "missing_reason": manifest.get("missing_reason"),
    }]


def _root_timed_out(root):
    root = Path(root)
    for name in ("codex-meta.json", "claude-meta.json"):
        path = root / name
        if not path.exists():
            continue
        try:
            meta = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if meta.get("timed_out") is True:
            return True
    for name in ("codex-stderr.log", "claude-stderr.log"):
        path = root / name
        if path.exists() and "Process timed out after" in path.read_text(errors="ignore"):
            return True
    return False


def _attempt_timeout_roots(attempt_root):
    attempt_root = Path(attempt_root)
    return [root for root in subagent_traces.iter_trace_roots(attempt_root) if _root_timed_out(root)]


def _attempt_timed_out(attempt_root):
    return bool(_attempt_timeout_roots(attempt_root))


def _frontmatter_status(path):
    try:
        lines = Path(path).read_text(errors="ignore").splitlines()
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            return None
        if stripped.startswith("status:"):
            return stripped.split(":", 1)[1].strip().strip("'\"")
    return None


def _attempt_completion_findings(attempt_root):
    attempt_root = Path(attempt_root)
    timeout_roots = _attempt_timeout_roots(attempt_root)
    timed_out = bool(timeout_roots)

    active_statuses = []
    workspace_roots = [attempt_root / "workspace"]
    workspace_roots.extend(sorted(attempt_root.glob("fresh/query*/workspace")))
    workspace_roots.extend(sorted(attempt_root.glob("context/workspace")))
    workspace_roots.extend(sorted(attempt_root.glob("context-fresh/query*/workspace")))
    for workspace in workspace_roots:
        if not workspace.is_dir():
            continue
        for path in sorted(workspace.glob("*.md")):
            if path.name == "README.md":
                continue
            status = _frontmatter_status(path)
            if status:
                active_statuses.append((path, status))

    if not active_statuses:
        if not timed_out:
            return []
        incomplete = []
    else:
        incomplete = [(path, status) for path, status in active_statuses if status != "done"]

    if not timed_out and not incomplete:
        return []

    if timed_out and incomplete:
        status = "timed_out_non_terminal"
    elif timed_out:
        status = "timed_out"
    else:
        status = "non_terminal"

    finding = {
        "source_kind": "attempt_metadata",
        "source_path": _rel(attempt_root, attempt_root),
        "trace_id": None,
        "subagent_thread_id": None,
        "stage_name": None,
        "event_id": None,
        "event_type": None,
        "tool_type": None,
        "category": "attempt_incomplete",
        "confidence": "high",
        "status": status,
        "timed_out": timed_out,
    }
    if timed_out:
        finding["timeout_roots"] = [_rel(root, attempt_root) for root in timeout_roots]
    if incomplete:
        finding["incomplete_entities"] = [
            {
                "path": _rel(path, attempt_root),
                "status": status,
            }
            for path, status in incomplete
        ]
    return [finding]


def decide_status(findings, taint_policy):
    if taint_policy == "audit":
        return "clean"
    if taint_policy == "taint":
        return "tainted" if findings else "clean"
    if taint_policy == "fail":
        return "failed" if findings else "clean"
    raise ValueError(f"unknown taint policy: {taint_policy}")


def scan_attempt(attempt_root, taint_policy="audit"):
    attempt_root = Path(attempt_root)
    findings = []
    try:
        for scan_input in discover_scan_inputs(attempt_root):
            kind = scan_input["source_kind"]
            if kind == "trace_manifest":
                findings.extend(_coverage_findings(scan_input, attempt_root))
            elif kind == "subagent_trace":
                findings.extend(_scan_jsonl(
                    scan_input["path"],
                    attempt_root,
                    kind,
                    trace=scan_input.get("trace"),
                ))
            elif kind == "parent_log":
                findings.extend(_scan_jsonl(scan_input["path"], attempt_root, kind))
        findings.extend(_attempt_completion_findings(attempt_root))
    except Exception as exc:
        findings.append({
            "source_kind": "taint_scanner",
            "source_path": _rel(attempt_root, attempt_root),
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
    return {
        "schema_version": "dab-taint-v1",
        "taint_policy": taint_policy,
        "status": decide_status(findings, taint_policy),
        "findings": findings,
    }


def render_markdown(report):
    lines = [
        "# Taint Report",
        "",
        f"Status: {report.get('status', 'unknown')}",
        f"Policy: {report.get('taint_policy', 'audit')}",
        "",
    ]
    findings = report.get("findings") or []
    if not findings:
        lines.append("No taint findings.")
    else:
        for finding in findings:
            lines.append(
                f"- {finding.get('category')} in {finding.get('source_kind')} "
                f"{finding.get('source_path')} ({finding.get('status') or finding.get('pattern')})"
            )
    lines.append("")
    return "\n".join(lines)
