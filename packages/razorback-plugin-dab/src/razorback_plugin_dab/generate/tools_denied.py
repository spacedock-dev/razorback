# ABOUTME: PreToolUse denylist sourced verbatim from upstream DAB.
# ABOUTME: Source: /Users/clkao/git/dataagentbench/benchmark/lib/run_experiment.py:1531-1549.

from __future__ import annotations

import json
from pathlib import Path

# Sourced verbatim from upstream DAB benchmark/lib/run_experiment.py
# lines 1531-1549 (DISALLOWED_TOOLS array). Do not reorder or edit.
DISALLOWED_TOOLS: tuple[str, ...] = (
    "WebFetch", "WebSearch",
    "Bash(curl *)", "Bash(wget *)", "Bash(git clone *)",
    "Bash(huggingface-cli *)", "Bash(hf *)",
    "Bash(pip install datasets*)", "Bash(pip install huggingface*)",
    "Bash(pip install transformers*)", "Bash(pip install evaluate*)",
    "Bash(pip3 install datasets*)", "Bash(pip3 install huggingface*)",
    "Bash(pip3 install transformers*)", "Bash(pip3 install evaluate*)",
    "Bash(uv pip install datasets*)", "Bash(uv pip install huggingface*)",
    "Bash(uv pip install transformers*)", "Bash(uv pip install evaluate*)",
    "Bash(uv add datasets*)", "Bash(uv add huggingface*)",
    "Bash(uv add transformers*)", "Bash(uv add evaluate*)",
    "Bash(python -m pip install datasets*)",
    "Bash(python -m pip install huggingface*)",
    "Bash(python -m pip install transformers*)",
    "Bash(python3 -m pip install datasets*)",
    "Bash(python3 -m pip install huggingface*)",
    "Bash(python3 -m pip install transformers*)",
)


def generate_settings_json(task_name: str) -> dict:
    """Return the per-task settings.json payload (PreToolUse denylist)."""
    return {
        "permissions": {
            "deny": list(DISALLOWED_TOOLS),
        },
        "_provenance": {
            "task": task_name,
            "source": "dataagentbench/benchmark/lib/run_experiment.py:1531-1549",
        },
    }


def write_settings_json(settings_path: Path, task_name: str) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(generate_settings_json(task_name), indent=2) + "\n")
