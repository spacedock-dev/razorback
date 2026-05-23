# ABOUTME: AC-3, per-runtime adapter sub-modules exist; pi raises NotImplementedError.
# ABOUTME: claude.py and codex.py construct installed agents with expected kwargs.

import importlib
import inspect
from types import SimpleNamespace

import pytest
from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.codex import Codex

from razorback.agents._runtime import claude as claude_adapter
from razorback.agents._runtime import codex as codex_adapter
from razorback.agents._runtime import pi as pi_adapter
from razorback.agents.spacedock_solver import SpacedockSolverAgentError


def _descriptor_kwargs(descriptors):
    return {descriptor.kwarg for descriptor in descriptors}


def test_harbor_installed_agent_descriptor_shapes_are_available():
    assert {"reasoning_effort", "reasoning_summary"} <= _descriptor_kwargs(
        Codex.CLI_FLAGS
    )
    assert {
        "max_turns",
        "reasoning_effort",
        "append_system_prompt",
        "allowed_tools",
        "disallowed_tools",
    } <= _descriptor_kwargs(ClaudeCode.CLI_FLAGS)
    assert "max_thinking_tokens" in _descriptor_kwargs(ClaudeCode.ENV_VARS)


def test_claude_runtime_helper_import_path_remains_loadable():
    module = importlib.import_module("razorback.agents._runtime.claude")

    assert getattr(module, "RazorbackClaudeCode").__name__ == "RazorbackClaudeCode"


def test_codex_constructs_inner_agent_with_supported_kwargs(tmp_path):
    inner = codex_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="gpt-5.1-codex",
        harbor_agent_kwargs={"reasoning_effort": "high", "reasoning_summary": "auto"},
        extra_env={"OPENAI_API_KEY": "sk-fake"},
    )
    assert inner.__class__.__name__ == "RazorbackCodex"
    assert isinstance(inner, Codex)
    assert inner.model_name == "gpt-5.1-codex"
    assert getattr(inner, "_extra_env", {}) == {"OPENAI_API_KEY": "sk-fake"}
    flag_kwargs = getattr(inner, "_flag_kwargs", {})
    assert flag_kwargs["reasoning_effort"] == "high"
    assert flag_kwargs["reasoning_summary"] == "auto"
    assert '-c \'web_search="disabled"\'' in inner.build_cli_flags()


def test_codex_retained_overrides_document_upstream_method_and_benchmark_reason():
    build_cli_flags_source = inspect.getsource(codex_adapter.RazorbackCodex.build_cli_flags)
    assert "Codex.build_cli_flags" in build_cli_flags_source
    assert "offline benchmark solving" in build_cli_flags_source

    install_source = inspect.getsource(codex_adapter.RazorbackCodex.install)
    assert "Codex.install" in install_source
    assert "benchmark proxy" in install_source


def test_codex_install_delegates_without_copying_harbor_command_literals():
    install_source = inspect.getsource(codex_adapter.RazorbackCodex.install)
    assert "npm install -g @openai/codex" not in install_source
    assert "apt-get update" not in install_source
    assert "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm" not in install_source


@pytest.mark.asyncio
async def test_codex_install_phase_clears_proxy_env_while_delegating(
    tmp_path, monkeypatch
):
    async def fake_harbor_install(self, environment):
        await self.exec_as_agent(
            environment,
            command="probe",
            env={"X": "1"},
        )

    monkeypatch.setattr(Codex, "install", fake_harbor_install)
    fake_env = SimpleNamespace()

    async def fake_exec(*_args, **_kwargs):
        return SimpleNamespace(return_code=0, stdout="", stderr="")

    from unittest.mock import AsyncMock

    fake_env.exec = AsyncMock(side_effect=fake_exec)
    inner = codex_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="gpt-5.1-codex",
        harbor_agent_kwargs={},
        extra_env={"OPENAI_API_KEY": "sk-fake"},
    )

    await inner.install(fake_env)

    exec_env = fake_env.exec.await_args.kwargs["env"]
    assert exec_env["HTTP_PROXY"] == ""
    assert exec_env["HTTPS_PROXY"] == ""
    assert exec_env["X"] == "1"
    assert exec_env["OPENAI_API_KEY"] == "sk-fake"


@pytest.mark.parametrize(
    "kwarg",
    [
        {"max_turns": 3},
        {"tools_allowed": ["Read"]},
        {"tools_denied": ["Bash(rm*)"]},
        {"append_system_prompt": "extra system text"},
    ],
)
def test_codex_rejects_unsupported_contract_kwargs(tmp_path, kwarg):
    name = next(iter(kwarg))
    with pytest.raises(SpacedockSolverAgentError, match=name):
        codex_adapter.build_inner_agent(
            logs_dir=tmp_path,
            model="gpt-5.1-codex",
            harbor_agent_kwargs=kwarg,
            extra_env={"OPENAI_API_KEY": "sk-fake"},
        )


def test_pi_raises_not_implemented(tmp_path):
    with pytest.raises(NotImplementedError, match="pi"):
        pi_adapter.build_inner_agent(
            logs_dir=tmp_path,
            model="any",
            harbor_agent_kwargs={},
            extra_env={},
        )


def test_claude_constructs_inner_agent_as_runtime_helper_subclass(tmp_path):
    """Inner must be razorback's runtime helper, not harbor's ClaudeCode directly.

    Routing through RazorbackClaudeCode inherits PKG-26's cost-emit + claude-output.jsonl
    audit sentinel. Returning harbor.ClaudeCode directly (the earlier shape) silently
    dropped cost_usd telemetry even under paid-API auth — surfaced live during
    Goal 1 RESUME cell 1 (spacedock/agnews) where cost was null on disk despite
    a 3m54s opus-4.7 run, with raw tokens reconstructible only from session jsonl.
    """
    inner = claude_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        harbor_agent_kwargs={
            "max_turns": 200,
            "reasoning_effort": "medium",
            "tools_allowed": ["Read", "Write"],
            "tools_denied": ["Bash(rm*)"],
            "append_system_prompt": "You are the first officer.",
        },
        extra_env={"ANTHROPIC_API_KEY": "sk-fake"},
    )
    assert isinstance(inner, claude_adapter.RazorbackClaudeCode)
    # Defense-in-depth: RazorbackClaudeCode IS a ClaudeCode subclass; the harbor base
    # contract still holds.
    assert isinstance(inner, ClaudeCode)
    assert getattr(inner, "_extra_env", {}) == {"ANTHROPIC_API_KEY": "sk-fake"}
    flag_kwargs = getattr(inner, "_flag_kwargs", {})
    assert flag_kwargs["max_turns"] == 200
    assert flag_kwargs["reasoning_effort"] == "medium"
    assert flag_kwargs["allowed_tools"] == "Read,Write"
    assert flag_kwargs["disallowed_tools"] == "Bash(rm*)"
    assert flag_kwargs["append_system_prompt"] == "You are the first officer."


def test_claude_runtime_helper_publishes_audit_sentinel(tmp_path, monkeypatch):
    calls = []

    def fake_populate_context_post_run(self, context):
        calls.append(context)

    monkeypatch.setattr(ClaudeCode, "populate_context_post_run", fake_populate_context_post_run)
    (tmp_path / "claude-code.txt").write_text('{"type":"result"}\n')
    context = SimpleNamespace()
    agent = claude_adapter.RazorbackClaudeCode(
        logs_dir=tmp_path,
        model_name="claude-opus-4-5",
        extra_env={"ANTHROPIC_API_KEY": "sk-fake"},
    )

    agent.populate_context_post_run(context)

    sentinel = tmp_path / "claude-output.jsonl"
    assert calls == [context]
    assert sentinel.exists()
    assert sentinel.is_symlink() or sentinel.read_text() == '{"type":"result"}\n'


def test_claude_passes_tools_denied_through_to_harbor_kwargs(tmp_path):
    """v4-pkg9-v2 owns the PreToolUse hook plumbing; Phase 3 just passes the kwarg through.

    Harbor's ClaudeCode stashes CLI flag kwargs in `_flag_kwargs`. The adapter
    must map razorback's `tools_denied` field to harbor's `disallowed_tools`.
    """
    inner = claude_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        harbor_agent_kwargs={
            "max_turns": 200,
            "tools_denied": ["Bash(pip install datasets*)"],
        },
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )
    flag_kwargs = getattr(inner, "_flag_kwargs", {})
    assert "disallowed_tools" in flag_kwargs, (
        f"adapter did not forward tools_denied → disallowed_tools; flag_kwargs={flag_kwargs}"
    )
    assert "Bash(pip install datasets*)" in flag_kwargs["disallowed_tools"]


def test_claude_passes_tools_allowed_through(tmp_path):
    inner = claude_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="claude-opus-4-5",
        harbor_agent_kwargs={"max_turns": 200, "tools_allowed": ["Read", "Edit"]},
        extra_env={"ANTHROPIC_API_KEY": "x"},
    )
    flag_kwargs = getattr(inner, "_flag_kwargs", {})
    assert "allowed_tools" in flag_kwargs
    assert "Read" in flag_kwargs["allowed_tools"]
    assert "Edit" in flag_kwargs["allowed_tools"]


def test_claude_rejects_unknown_active_harbor_kwargs(tmp_path):
    with pytest.raises(SpacedockSolverAgentError, match="unsupported"):
        claude_adapter.build_inner_agent(
            logs_dir=tmp_path,
            model="claude-opus-4-5",
            harbor_agent_kwargs={"not_a_harbor_kwarg": "active"},
            extra_env={"ANTHROPIC_API_KEY": "x"},
        )
