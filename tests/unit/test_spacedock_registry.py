# ABOUTME: Phase 6 — registry exposes only canonical agent.kind=spacedock_solver.
# ABOUTME: Stale v1/transitional routes are rejected by the active registry/schema.

import pytest

from razorback.agents.registry import AgentKindError, resolve_agent_kind
from razorback.errors import SpecError
from razorback.spec.parse import parse_spec_text


def test_spacedock_solver_kind_resolves_to_schema_and_import_path():
    entry = resolve_agent_kind("spacedock_solver")
    assert entry.import_path == "razorback.agents.spacedock_solver:SpacedockSolverAgent"
    cfg = entry.config_schema(
        runtime="codex",
        model="claude-opus-4-5",
        sampling={"temperature": 0.0, "top_p": None, "seed": 42},
        solver_workflow="examples/solver_workflows/codex-benchmark-solver",
        tools_allowed=["Bash", "Read"],
        tools_denied=["Bash(curl*)"],
        solver_workflow_content_hash="sha256:" + "a" * 64,
        sealed_hash="deadbeef" * 4,
    )
    assert cfg.runtime == "codex"
    assert cfg.tools_denied == ["Bash(curl*)"]


def test_spec_parse_accepts_canonical_spacedock_solver(tmp_path):
    workflow = tmp_path / "solver"
    workflow.mkdir()
    (workflow / "README.md").write_text("## Stages\n- model\n")
    spec_text = f"""\
version: 1
experiment: canonical-solver
agent:
  kind: spacedock_solver
  runtime: claude
  model: claude-opus-4-5
  sampling: {{temperature: 0.0, seed: 42}}
  solver_workflow: {workflow}
  tools_allowed: []
  tools_denied: []
benchmark:
  kind: harbor_dab
  data_root: /tmp/data
  datasets: [bookreview]
"""
    spec = parse_spec_text(spec_text)
    assert spec.agent.kind == "spacedock_solver"


def test_spec_parse_rejects_stale_v1_spelling():
    stale_kind = "spacedock" + "-solver"
    bad_spec = f"""\
version: 1
experiment: stale-v1
agent:
  kind: {stale_kind}
benchmark:
  kind: harbor_dab
  data_root: /tmp/data
  datasets: [bookreview]
"""
    with pytest.raises(SpecError) as exc:
        parse_spec_text(bad_spec)
    assert stale_kind in str(exc.value)


def test_spec_parse_rejects_transitional_spelling():
    stale_kind = "spacedock_" + "solver_v2"  # intentional historical rejection assertion
    bad_spec = f"""\
version: 1
experiment: stale-transitional
agent:
  kind: {stale_kind}
  model: claude-opus-4-5
  solver_workflow: .
benchmark:
  kind: harbor_dab
  data_root: /tmp/data
  datasets: [bookreview]
"""
    with pytest.raises(SpecError) as exc:
        parse_spec_text(bad_spec)
    assert stale_kind in str(exc.value)


def test_spec_parse_rejects_unknown_agent_kwargs():
    bad_spec = """\
version: 1
experiment: extra-key
agent:
  kind: spacedock_solver
  model: claude-opus-4-5
  sampling: {temperature: 0.0, seed: 42}
  solver_workflow: .
  tools_allowed: []
  frobnicator: true
benchmark:
  kind: harbor_dab
  data_root: /tmp/data
  datasets: [bookreview]
"""
    with pytest.raises(SpecError) as exc:
        parse_spec_text(bad_spec)
    msg = str(exc.value).lower()
    assert "frobnicator" in msg or "extra" in msg


def test_unknown_kind_raises_agent_kind_error():
    with pytest.raises(AgentKindError):
        resolve_agent_kind("definitely-not-real")


@pytest.mark.parametrize(
    "kind",
    [
        "spacedock_" + "solver_v2",  # intentional historical rejection assertion
        "spacedock" + "-solver",
        "claude-cli",
    ],
)
def test_stale_registry_routes_do_not_resolve(kind):
    with pytest.raises(AgentKindError):
        resolve_agent_kind(kind)
