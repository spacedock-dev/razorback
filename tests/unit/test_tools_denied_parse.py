# ABOUTME: PKG-9 v2 AC-1 + AC-4: tools_denied parse/round-trip on v2 SpacedockSolverAgentBlock.
# ABOUTME: Spec §6.2 introduces tools_denied: list[str] on the spacedock_solver agent block.

from typing import Any

import pytest
import yaml

from razorback.errors import ExitCode, SpecError
from razorback.spec.freeze import freeze_spec
from razorback.spec.parse import parse_spec_text


FIVE_DENIALS = [
    "Bash(pip install datasets*)",
    "Bash(pip install dataagentbench*)",
    "Bash(huggingface-cli login*)",
    "Bash(curl https://huggingface.co/*)",
    "Bash(wget https://huggingface.co/*)",
]


def _spec_with(agent_extra: dict[str, Any]) -> str:
    spec: dict[str, Any] = {
        "version": 1,
        "experiment": "pkg9-v2-parse-test",
        "agent": {
            "kind": "spacedock_solver_v2",
            "runtime": "claude",
            "model": "claude-opus-4-5",
            "solver_workflow": ".",
            **agent_extra,
        },
        "benchmark": {"kind": "local", "task_paths": []},
        "trials": 1,
    }
    return yaml.safe_dump(spec, sort_keys=False)


def test_tools_denied_five_entry_list_parses_verbatim():
    """AC-1 (a): a five-entry tools_denied list parses and survives verbatim."""
    spec = parse_spec_text(_spec_with({"tools_denied": list(FIVE_DENIALS)}))
    assert spec.agent.tools_denied == FIVE_DENIALS


def test_tools_denied_wrong_type_raises_spec_error_exit_10():
    """AC-1 (b): tools_denied as a bare string raises SpecError (exit 10) naming the field."""
    with pytest.raises(SpecError) as excinfo:
        parse_spec_text(_spec_with({"tools_denied": "Bash(rm*)"}))
    assert excinfo.value.exit_code == int(ExitCode.SPEC_ERROR)
    assert "tools_denied" in str(excinfo.value)


def test_tools_denied_omitted_defaults_to_empty_list():
    """AC-1 (c): omitting tools_denied yields [] on the parsed block."""
    spec = parse_spec_text(_spec_with({}))
    assert spec.agent.tools_denied == []


def test_tools_denied_round_trip_through_freeze_preserves_order():
    """AC-4: freeze re-emits tools_denied with byte-identical contents and ordering."""
    spec = parse_spec_text(_spec_with({"tools_denied": list(FIVE_DENIALS)}))
    frozen_text = freeze_spec(spec)
    reloaded = yaml.safe_load(frozen_text)
    assert reloaded["agent"]["tools_denied"] == FIVE_DENIALS
