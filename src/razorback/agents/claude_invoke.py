# ABOUTME: Shared `claude -p` argv builder + DISALLOWED_TOOLS list.
# ABOUTME: Used by ClaudeCliAgent (M3) and SpacedockSolverAgent (M4 per-stage runs).

import shlex


DEFAULT_ALLOWED_TOOLS = ("Bash", "Read", "Write", "Edit", "Glob", "Grep")

# Verbatim from run_experiment.py:1531-1549. Do NOT paraphrase.
DISALLOWED_TOOLS = (
    "WebFetch", "WebSearch",
    "Bash(curl *)", "Bash(wget *)", "Bash(git clone *)",
    "Bash(huggingface-cli *)", "Bash(hf *)",
    "Bash(pip install datasets*)", "Bash(pip install huggingface*)",
    "Bash(pip install transformers*)", "Bash(pip install evaluate*)",
    "Bash(pip3 install datasets*)", "Bash(pip3 install huggingface*)",
    "Bash(pip3 install transformers*)", "Bash(pip3 install evaluate*)",
)


def build_claude_argv(
    *,
    prompt: str,
    model: str | None,
    tools_allowed: list[str],
) -> str:
    """Return a shell-safe `claude -p <prompt> ...` command string for environment.exec."""
    allowed = list(tools_allowed) if tools_allowed else list(DEFAULT_ALLOWED_TOOLS)
    parts = [
        "claude", "-p", shlex.quote(prompt),
        "--allowedTools", ",".join(allowed),
    ]
    for d in DISALLOWED_TOOLS:
        parts.extend(["--disallowedTools", shlex.quote(d)])
    parts.extend(["--permission-mode", "bypassPermissions"])
    if model:
        parts.extend(["--model", model])
    return " ".join(parts)
