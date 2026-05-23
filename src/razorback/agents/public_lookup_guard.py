# ABOUTME: Shared public-lookup command guard for benchmark agent runtimes.
# ABOUTME: Mirrors audit taint command patterns before solver shell execution.

from __future__ import annotations

import re
import textwrap

from razorback.audit import taint


_EXTRA_PUBLIC_LOOKUP_PATTERNS = {
    "forbidden_lookup": [
        re.compile(r"(?m)(?:^|[;&|]\s*)git\s+ls-remote\b.*\bhttps?://"),
        re.compile(r"(?m)(?:^|[;&|]\s*)git\s+clone\b.*\bhttps?://"),
    ],
}

_PYTHON_PUBLIC_LOOKUP_PATTERNS = [
    re.compile(r"\burllib\.request\.(?:urlopen|urlretrieve)\s*\("),
    re.compile(r"\brequests\.(?:get|post|put|patch|head|request)\s*\("),
    re.compile(r"\bhttpx\.(?:get|post|put|patch|head|request)\s*\("),
    re.compile(r"\baiohttp\.ClientSession\s*\("),
]
_PUBLIC_URL = re.compile(r"\bhttps?://")
CODEX_SHELL_GUARD_COMMANDS = (
    "curl",
    "wget",
    "git",
    "pip",
    "pip3",
    "npm",
    "python",
    "python3",
)


def is_forbidden_public_lookup_command(command: str) -> bool:
    """Return True when a shell command would taint strict benchmark audit."""
    base = {
        "source_kind": "runtime_guard",
        "source_path": None,
        "trace_id": None,
        "subagent_thread_id": None,
        "stage_name": None,
        "event_id": None,
        "event_type": None,
        "tool_type": "command_execution",
        "line": None,
    }
    if taint._scan_command(command, base):
        return True
    for script in taint._shell_scripts(command):
        shell_script = taint._mask_shell_quoted_strings(
            taint._mask_python_heredoc_bodies(script)
        )
        if taint._scan_text(shell_script, base, _EXTRA_PUBLIC_LOOKUP_PATTERNS):
            return True
    for source in taint._python_sources(command):
        if _PUBLIC_URL.search(source) and any(
            pattern.search(source) for pattern in _PYTHON_PUBLIC_LOOKUP_PATTERNS
        ):
            return True
    return False


def codex_pretooluse_guard_script() -> str:
    """Return a self-contained Codex hook script for remote benchmark containers."""
    return textwrap.dedent(
        r'''
        #!/usr/bin/env python3
        import json
        import os
        import re
        import shlex
        import sys

        COMMAND_KEYS = {"cmd", "command", "shell", "script"}
        SHELL_TOOL_NAMES = {
            "Bash",
            "Shell",
            "exec",
            "exec_command",
            "unified_exec.exec_command",
            "functions.exec_command",
        }
        SHELL_PATTERNS = [
            re.compile(r"(?m)(?:^|[;&|]\s*)(?:curl|wget)\b"),
            re.compile(r"(?m)(?:^|[;&|]\s*)(?:python(?:3)?\s+-m\s+pip|pip(?:3)?)\s+install\b"),
            re.compile(r"(?m)(?:^|[;&|]\s*)npm\s+install\b"),
            re.compile(r"(?m)(?:^|[;&|]\s*)git\s+(?:clone|ls-remote)\b.*\bhttps?://"),
        ]
        PYTHON_PATTERNS = [
            re.compile(r"\burllib\.request\.(?:urlopen|urlretrieve)\s*\("),
            re.compile(r"\brequests\.(?:get|post|put|patch|head|request)\s*\("),
            re.compile(r"\bhttpx\.(?:get|post|put|patch|head|request)\s*\("),
            re.compile(r"\baiohttp\.ClientSession\s*\("),
            re.compile(r"\b(?:from\s+datasets\s+import|datasets\.load_dataset|load_dataset)\b"),
        ]
        PUBLIC_URL = re.compile(r"\bhttps?://")

        def shell_words(command):
            try:
                return shlex.split(command, posix=True)
            except ValueError:
                return []

        def shell_scripts(command):
            yield command
            words = shell_words(command)
            for index, word in enumerate(words[:-1]):
                name = os.path.basename(word)
                if name in {"bash", "sh", "zsh"} and word.endswith(name):
                    for opt_index in range(index + 1, len(words) - 1):
                        option = words[opt_index]
                        if option.startswith("-") and "c" in option:
                            yield words[opt_index + 1]
                            break

        def python_c_sources(script):
            words = shell_words(script)
            for index, word in enumerate(words[:-1]):
                if os.path.basename(word) not in {"python", "python3"}:
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

        def heredoc_sources(command):
            lines = command.splitlines()
            index = 0
            while index < len(lines):
                match = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][\w.-]*)\1", lines[index])
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

        def python_sources(command):
            seen = set()
            for script in shell_scripts(command):
                for source in heredoc_sources(script):
                    if source not in seen:
                        seen.add(source)
                        yield source
                for source in python_c_sources(script):
                    if source not in seen:
                        seen.add(source)
                        yield source

        def command_blocked(command):
            for script in shell_scripts(command):
                for pattern in SHELL_PATTERNS:
                    if pattern.search(script):
                        return True
            for source in python_sources(command):
                if any(pattern.search(source) for pattern in PYTHON_PATTERNS):
                    if PUBLIC_URL.search(source) or "load_dataset" in source or "datasets" in source:
                        return True
            return False

        def shell_command_blocked(tool_name, args, stdin_source):
            tool = os.path.basename(tool_name)
            if tool in {"curl", "wget"}:
                return True
            if tool == "git":
                return len(args) >= 2 and args[0] in {"clone", "ls-remote"} and any(PUBLIC_URL.search(arg) for arg in args[1:])
            if tool in {"pip", "pip3"}:
                return bool(args) and args[0] == "install"
            if tool == "npm":
                return bool(args) and args[0] == "install"
            if tool in {"python", "python3"}:
                if len(args) >= 3 and args[0] == "-m" and args[1] == "pip" and args[2] == "install":
                    return True
                sources = []
                for index, arg in enumerate(args):
                    if arg == "-c" and index + 1 < len(args):
                        sources.append(args[index + 1])
                        break
                    if arg.startswith("-c") and len(arg) > 2:
                        sources.append(arg[2:])
                        break
                    if not arg.startswith("-"):
                        break
                if stdin_source:
                    sources.append(stdin_source)
                for source in sources:
                    if any(pattern.search(source) for pattern in PYTHON_PATTERNS):
                        if PUBLIC_URL.search(source) or "load_dataset" in source or "datasets" in source:
                            return True
            return False

        def walk_commands(value):
            if isinstance(value, dict):
                for key, nested in value.items():
                    if key in COMMAND_KEYS and isinstance(nested, str):
                        yield nested
                    else:
                        yield from walk_commands(nested)
            elif isinstance(value, list):
                for item in value:
                    yield from walk_commands(item)

        def loads_json(value):
            if not isinstance(value, str):
                return value
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        def run_hook_guard():
            payload = json.load(sys.stdin)
            tool_name = payload.get("tool_name") or payload.get("tool") or payload.get("name") or ""
            tool_input = loads_json(payload.get("tool_input") or payload.get("input") or payload.get("arguments") or {})
            commands = list(walk_commands(tool_input))
            if not commands and isinstance(tool_input, str) and os.path.basename(tool_name) in SHELL_TOOL_NAMES:
                commands = [tool_input]

            if any(command_blocked(command) for command in commands):
                print(
                    "blocked benchmark public lookup command before execution",
                    file=sys.stderr,
                )
                sys.exit(2)

        def run_shell_guard(argv):
            if len(argv) < 3:
                print("razorback shell guard wrapper invoked without a tool name", file=sys.stderr)
                sys.exit(127)
            tool_name = argv[2]
            args = argv[3:]
            stdin_source = sys.stdin.read()
            if shell_command_blocked(tool_name, args, stdin_source):
                print(
                    "blocked benchmark public lookup command before execution",
                    file=sys.stderr,
                )
                sys.exit(2)

        if len(sys.argv) >= 2 and sys.argv[1] == "--shell-guard":
            run_shell_guard(sys.argv)
        else:
            run_hook_guard()
        '''
    ).strip() + "\n"


def codex_shell_guard_script() -> str:
    """Return a Bash startup script that exposes real command paths to wrappers."""
    exports = "\n".join(
        f': "${{RAZORBACK_REAL_{tool.upper()}:=$(PATH="$RAZORBACK_ORIGINAL_PATH" command -v {tool} 2>/dev/null || true)}}"\n'
        f"export RAZORBACK_REAL_{tool.upper()}"
        for tool in CODEX_SHELL_GUARD_COMMANDS
    )
    return textwrap.dedent(
        f'''
        # Razorback Codex shell guard. Sourced by bash through BASH_ENV.
        : "${{CODEX_HOME:?}}"
        : "${{RAZORBACK_ORIGINAL_PATH:=$PATH}}"
        export RAZORBACK_ORIGINAL_PATH
        : "${{RAZORBACK_GUARD_PYTHON:=$(PATH="$RAZORBACK_ORIGINAL_PATH" command -v python3 2>/dev/null || PATH="$RAZORBACK_ORIGINAL_PATH" command -v python 2>/dev/null || true)}}"
        export RAZORBACK_GUARD_PYTHON
        {exports}
        case ":$PATH:" in
            *":$CODEX_HOME/razorback-bin:"*) ;;
            *) export PATH="$CODEX_HOME/razorback-bin:$PATH" ;;
        esac
        '''
    ).strip() + "\n"


def codex_shell_wrapper_script() -> str:
    """Return the common shell wrapper installed under guarded command names."""
    return textwrap.dedent(
        r'''
        #!/bin/sh
        tool=$(basename "$0")
        var="RAZORBACK_REAL_$(printf '%s' "$tool" | tr '[:lower:]' '[:upper:]')"
        eval "real=\${$var:-}"
        guard="$CODEX_HOME/razorback-public-lookup-guard.py"
        guard_python="${RAZORBACK_GUARD_PYTHON:-}"

        if [ -z "$guard_python" ] || [ ! -x "$guard_python" ]; then
            echo "$tool: command not found" >&2
            exit 127
        fi

        if [ -z "$real" ] || [ ! -x "$real" ]; then
            "$guard_python" "$guard" --shell-guard "$tool" "$@" </dev/null
            rc=$?
            if [ "$rc" -ne 0 ]; then
                exit "$rc"
            fi
            echo "$tool: command not found" >&2
            exit 127
        fi

        if { [ "$tool" = "python" ] || [ "$tool" = "python3" ]; } && { [ "$#" -eq 0 ] || [ "${1:-}" = "-" ]; }; then
            tmp=$(mktemp "${TMPDIR:-/tmp}/razorback-python-stdin.XXXXXX") || exit 1
            cat >"$tmp"
            "$guard_python" "$guard" --shell-guard "$tool" "$@" <"$tmp"
            rc=$?
            if [ "$rc" -ne 0 ]; then
                rm -f "$tmp"
                exit "$rc"
            fi
            "$real" "$@" <"$tmp"
            rc=$?
            rm -f "$tmp"
            exit "$rc"
        fi

        "$guard_python" "$guard" --shell-guard "$tool" "$@" </dev/null
        rc=$?
        if [ "$rc" -ne 0 ]; then
            exit "$rc"
        fi
        exec "$real" "$@"
        '''
    ).strip() + "\n"
