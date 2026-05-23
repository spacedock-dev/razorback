# ABOUTME: T13 (unit-level integration) — SpacedockSolverAgent.cleanup writes
# ABOUTME: subagent-trace-manifest.json at logs_dir.parents[3] from real claude-code.txt.

import json
from pathlib import Path

import pytest

from razorback.agents.spacedock_solver import SpacedockSolverAgent


T0_FIXTURE = """\
{"type":"system","subtype":"init","tools":["Task","Bash","Agent"]}
{"type":"assistant","message":{"model":"claude-opus-4-7","id":"msg_1","role":"assistant","content":[{"type":"tool_use","id":"toolu_a","name":"Agent","input":{"subagent_type":"spacedock:ensign","prompt":"do the probe stage"}}]}}
{"type":"result","subtype":"success","is_error":false,"total_cost_usd":0.26}
"""


def _common_kwargs(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- probe\n")
    return dict(
        runtime="claude",
        model="claude-opus-4-7",
        sampling={"temperature": 0.0, "top_p": None, "seed": None},
        solver_workflow=workflow,
        solver_workflow_content_hash="sha256:" + "a" * 64,
        prompt_content_hashes={"readme": "sha256:" + "b" * 64},
        spacedock_skill_version="1.0.0",
        harbor_agent_kwargs={"max_turns": 200},
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )


@pytest.mark.asyncio
async def test_cleanup_writes_manifest_adjacent_to_provenance(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """End-to-end of the AC-2 post-run hook: cleanup parses claude-code.txt at
    logs_dir and writes subagent-trace-manifest.json at logs_dir.parents[3]
    (the cell-run-dir adjacent to provenance.yaml)."""
    monkeypatch.setenv("RAZORBACK_SPACEDOCK_PLUGIN_DIR", str(tmp_path))

    cell_run_dir = tmp_path / "cell-run"
    logs_dir = cell_run_dir / "trial-001__aaaa1234" / "steps" / "main" / "agent"
    logs_dir.mkdir(parents=True)
    (logs_dir / "claude-code.txt").write_text(T0_FIXTURE)
    (cell_run_dir / "provenance.yaml").write_text("placeholder")

    kw = _common_kwargs(tmp_path)
    agent = SpacedockSolverAgent(logs_dir=logs_dir, **kw)

    await agent.cleanup(environment=None)

    manifest_path = cell_run_dir / "subagent-trace-manifest.json"
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text())
    assert payload["captured"] == 1
    assert payload["dispatches"][0]["subagent_type"] == "spacedock:ensign"
    assert payload["parent_agent"]["model"] == "claude-opus-4-7"
    assert payload["schema_version"] == "razorback-subagent-traces-v1"


@pytest.mark.asyncio
async def test_cleanup_for_codex_runtime_does_not_write_manifest(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """The manifest write is gated to runtime=claude; codex cells must not get
    a stray manifest (per plan §Risk register)."""
    cell_run_dir = tmp_path / "cell-run"
    logs_dir = cell_run_dir / "trial-001__aaaa1234" / "steps" / "main" / "agent"
    logs_dir.mkdir(parents=True)
    (logs_dir / "claude-code.txt").write_text(T0_FIXTURE)

    kw = _common_kwargs(tmp_path)
    kw["runtime"] = "codex"
    kw["harbor_agent_kwargs"] = {
        "max_turns": 200,
        "tools_allowed": [],
        "tools_denied": [],
        "reasoning_effort": "high",
    }
    kw["model"] = "gpt-5.1-codex"
    kw["extra_env"] = {"OPENAI_API_KEY": "x"}
    agent = SpacedockSolverAgent(logs_dir=logs_dir, **kw)

    await agent.cleanup(environment=None)

    assert not (cell_run_dir / "subagent-trace-manifest.json").exists()
