# ABOUTME: AC-2 — agent.kind=spacedock-solver registry entry validates kwargs BEFORE
# ABOUTME: harbor.AgentConfig is constructed. SpecError on bad stages, bad prompts, unknown fields.

import pytest

from razorback.agents.registry import AgentKindError, resolve_agent_kind
from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text


def test_spacedock_solver_kind_resolves_to_schema_and_import_path():
    entry = resolve_agent_kind("spacedock-solver")
    assert entry.import_path == "razorback.agents.spacedock_solver:SpacedockSolverAgent"
    cfg = entry.config_schema(
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        stages=["model", "analyze", "verify"],
        tools_allowed=["Bash", "Read"],
        prompts={"model": "sha256:aa", "analyze": "sha256:bb", "verify": "sha256:cc"},
        sealed_hash="deadbeef" * 4,
    )
    assert cfg.stages == ["model", "analyze", "verify"]


def test_spec_parse_rejects_unknown_stages():
    bad_spec = """\
version: 1
experiment: bad-stages
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling: {temperature: 0.0, seed: 42}
  stages: [model, verify]
  tools_allowed: []
  prompts:
    model: ./prompts/m.md
    verify: ./prompts/v.md
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
"""
    with pytest.raises(SpecError) as exc:
        parse_spec_text(bad_spec)
    assert "stages" in str(exc.value)


def test_spec_parse_rejects_prompts_missing_a_stage():
    bad_spec = """\
version: 1
experiment: missing-prompt
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling: {temperature: 0.0, seed: 42}
  stages: [model, analyze, verify]
  tools_allowed: []
  prompts:
    model: ./prompts/m.md
    analyze: ./prompts/a.md
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
"""
    with pytest.raises(SpecError) as exc:
        parse_spec_text(bad_spec)
    assert "prompts" in str(exc.value) and "verify" in str(exc.value)


def test_spec_parse_rejects_unknown_agent_kwargs():
    bad_spec = """\
version: 1
experiment: extra-key
agent:
  kind: spacedock-solver
  model: claude-opus-4-5
  sampling: {temperature: 0.0, seed: 42}
  stages: [model, analyze, verify]
  tools_allowed: []
  prompts:
    model: ./prompts/m.md
    analyze: ./prompts/a.md
    verify: ./prompts/v.md
  frobnicator: true
benchmark:
  kind: dab
  data_root: /Users/clkao/git/dataagentbench/data
  datasets: [bookreview]
"""
    with pytest.raises(SpecError) as exc:
        parse_spec_text(bad_spec)
    msg = str(exc.value).lower()
    assert "frobnicator" in msg or "extra" in msg


def test_unknown_kind_raises_agent_kind_error():
    with pytest.raises(AgentKindError):
        resolve_agent_kind("definitely-not-real")


def test_existing_kinds_still_resolve():
    """M3's nop + claude-cli kinds keep resolving — M4 only adds, never removes."""
    assert resolve_agent_kind("nop").import_path is None
    assert resolve_agent_kind("claude-cli").import_path == "razorback.agents.claude_cli:ClaudeCliAgent"
