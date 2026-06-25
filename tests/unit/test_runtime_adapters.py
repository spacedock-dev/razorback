# ABOUTME: AC-3, per-runtime adapter sub-modules exist; pi raises NotImplementedError.
# ABOUTME: claude.py and codex.py construct installed agents with expected kwargs.

import importlib
import inspect
import json
import shlex
import subprocess
import sys
import tomllib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.codex import Codex

from razorback.agents._runtime import claude as claude_adapter
from razorback.agents._runtime import codex as codex_adapter
from razorback.agents._runtime import pi as pi_adapter
from razorback.agents.public_lookup_guard import (
    codex_pretooluse_guard_script,
    codex_shell_wrapper_script,
)
from razorback.agents.spacedock_solver import SpacedockSolverAgentError


def _descriptor_kwargs(descriptors):
    return {descriptor.kwarg for descriptor in descriptors}


def _appended_codex_config_toml(command: str) -> str:
    marker = 'cat >>"$CODEX_HOME/config.toml" <<TOML\n'
    return command.split(marker, 1)[1].rsplit("\nTOML", 1)[0]


def shlex_quote_path(path) -> str:
    return shlex.quote(str(path))


def _spacedock_plugin_fixture(tmp_path):
    plugin = tmp_path / "spacedock-plugin"
    for rel in (
        ".codex-plugin/plugin.json",
        "skills/first-officer/SKILL.md",
        "skills/ensign/SKILL.md",
        "agents/first-officer.md",
        "agents/ensign.md",
    ):
        path = plugin / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n")
    return plugin


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
    assert "--dangerously-bypass-hook-trust" in inner.build_cli_flags()


def test_codex_spacedock_inner_agent_enables_multi_agent(tmp_path):
    plugin = _spacedock_plugin_fixture(tmp_path)
    inner = codex_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="gpt-5.5",
        harbor_agent_kwargs={"reasoning_effort": "xhigh"},
        extra_env={"OPENAI_API_KEY": "sk-fake"},
        enable_multi_agent=True,
        spacedock_plugin_dirs=[plugin],
    )

    flags = inner.build_cli_flags()
    assert "--enable multi_agent" in flags
    assert inner._spacedock_plugin_dirs == [plugin]


@pytest.mark.asyncio
async def test_codex_spacedock_setup_stages_plugin_and_registers_skills(
    tmp_path, monkeypatch
):
    async def fake_setup(self, environment):
        return None

    monkeypatch.setattr(Codex, "setup", fake_setup)
    plugin = _spacedock_plugin_fixture(tmp_path)
    fake_env = SimpleNamespace(
        exec=AsyncMock(return_value=SimpleNamespace(return_code=0, stdout="", stderr="")),
        upload_dir=AsyncMock(),
    )
    inner = codex_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="gpt-5.5",
        harbor_agent_kwargs={},
        extra_env={"OPENAI_API_KEY": "sk-fake"},
        enable_multi_agent=True,
        spacedock_plugin_dirs=[plugin],
    )

    await inner.setup(fake_env)

    assert inner.skills_dir == codex_adapter.CODEX_SPACEDOCK_REMOTE_SKILLS_DIR
    fake_env.upload_dir.assert_awaited_once_with(
        str(plugin), "/tmp/razorback-agents/skills/spacedock"
    )


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
            command="curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/install.sh",
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command",
    [
        "curl https://github.com/dbt-labs/dbt-core",
        "wget https://raw.githubusercontent.com/f1db/f1db/master/f1db.sql",
        "git ls-remote https://github.com/dbt-labs/dbt-core",
        (
            "python -c \"import urllib.request; "
            "urllib.request.urlopen('https://hub.getdbt.com/api/v1/index.json')\""
        ),
    ],
)
async def test_codex_blocks_public_lookup_commands_before_delegating(
    tmp_path, monkeypatch, command
):
    calls = []

    async def fake_exec_as_agent(self, environment, command, **kwargs):
        calls.append(command)
        return SimpleNamespace(return_code=0, stdout="", stderr="")

    monkeypatch.setattr(Codex, "exec_as_agent", fake_exec_as_agent)
    inner = codex_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="gpt-5.1-codex",
        harbor_agent_kwargs={},
        extra_env={"OPENAI_API_KEY": "sk-fake"},
    )

    with pytest.raises(SpacedockSolverAgentError, match="public lookup"):
        await inner.exec_as_agent(SimpleNamespace(), command=command)

    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command",
    [
        "rg 'https://github.com' models/ tests/",
        "sed -n '1,80p' models/staging/example.sql",
        "dbt run --select customers",
        "python -c \"import duckdb; duckdb.sql('select 1').fetchall()\"",
        "find . -maxdepth 2 -type f -name '*.sql'",
    ],
)
async def test_codex_allows_local_commands_to_delegate(tmp_path, monkeypatch, command):
    calls = []

    async def fake_exec_as_agent(self, environment, command, **kwargs):
        calls.append(command)
        return SimpleNamespace(return_code=0, stdout="", stderr="")

    monkeypatch.setattr(Codex, "exec_as_agent", fake_exec_as_agent)
    inner = codex_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="gpt-5.1-codex",
        harbor_agent_kwargs={},
        extra_env={"OPENAI_API_KEY": "sk-fake"},
    )

    await inner.exec_as_agent(SimpleNamespace(), command=command)

    assert calls == [command]


@pytest.mark.asyncio
async def test_codex_runtime_setup_installs_pretooluse_lookup_guard(
    tmp_path, monkeypatch
):
    calls = []

    async def fake_exec_as_agent(self, environment, command, **kwargs):
        calls.append(command)
        return SimpleNamespace(return_code=0, stdout="", stderr="")

    monkeypatch.setattr(Codex, "exec_as_agent", fake_exec_as_agent)
    inner = codex_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="gpt-5.1-codex",
        harbor_agent_kwargs={},
        extra_env={"OPENAI_API_KEY": "sk-fake"},
    )
    setup_command = (
        "cat >/tmp/auth.json <<EOF\n{}\nEOF\n"
        'ln -sf /tmp/auth.json "$CODEX_HOME/auth.json"\n'
    )

    await inner.exec_as_agent(SimpleNamespace(), command=setup_command)

    assert len(calls) == 1
    delegated = calls[0]
    assert setup_command in delegated
    assert "razorback-public-lookup-guard.py" in delegated
    assert "razorback-shell-guard.sh" in delegated
    assert "razorback-bin" in delegated
    for tool in ("curl", "wget", "git", "pip", "pip3", "npm", "python", "python3"):
        assert tool in delegated
    appended_config = tomllib.loads(_appended_codex_config_toml(delegated))
    pre_tool_use = appended_config["hooks"]["PreToolUse"]
    assert len(pre_tool_use) == 1
    matcher_group = pre_tool_use[0]
    assert matcher_group["matcher"] == "*"
    assert "command" not in matcher_group
    assert len(matcher_group["hooks"]) == 1
    hook = matcher_group["hooks"][0]
    assert hook == {
        "type": "command",
        "command": "python3 $CODEX_HOME/razorback-public-lookup-guard.py",
        "timeout": 10,
    }
    assert "_RAZORBACK_LOOKUP_GUARD" not in hook["command"]
    assert "[[hooks.PreToolUse.hooks]]" in delegated
    assert "blocked benchmark public lookup command before execution" in delegated


@pytest.mark.asyncio
async def test_codex_outer_exec_launches_with_shell_lookup_guard(tmp_path, monkeypatch):
    calls = []

    async def fake_exec_as_agent(self, environment, command, **kwargs):
        calls.append(command)
        return SimpleNamespace(return_code=0, stdout="", stderr="")

    monkeypatch.setattr(Codex, "exec_as_agent", fake_exec_as_agent)
    inner = codex_adapter.build_inner_agent(
        logs_dir=tmp_path,
        model="gpt-5.1-codex",
        harbor_agent_kwargs={},
        extra_env={"OPENAI_API_KEY": "sk-fake"},
    )
    outer_command = (
        "if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; "
        "codex exec --enable unified_exec --json 'solve it'"
    )

    await inner.exec_as_agent(SimpleNamespace(), command=outer_command)

    delegated = calls[0]
    assert delegated.startswith("if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; ")
    assert (
        'BASH_ENV="$CODEX_HOME/razorback-shell-guard.sh" '
        'RAZORBACK_ORIGINAL_PATH="$PATH" '
        'PATH="$CODEX_HOME/razorback-bin:$PATH" '
        "codex exec --enable unified_exec"
    ) in delegated
    assert "fi; BASH_ENV=" in delegated
    assert delegated.count("BASH_ENV=") == 1


def test_codex_pretooluse_lookup_guard_script_blocks_public_lookup_payload(tmp_path):
    guard_path = tmp_path / "guard.py"
    guard_path.write_text(codex_pretooluse_guard_script())
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "curl https://example.com"},
    }

    result = subprocess.run(
        [sys.executable, str(guard_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "blocked benchmark public lookup command" in result.stderr


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("wget", ["https://example.com/data.csv"]),
        ("git", ["clone", "https://github.com/example/project"]),
        ("git", ["ls-remote", "https://github.com/example/project"]),
        ("pip", ["install", "datasets"]),
        ("pip3", ["install", "datasets"]),
        ("npm", ["install", "left-pad"]),
        ("python", ["-m", "pip", "install", "datasets"]),
        (
            "python3",
            [
                "-c",
                "import requests; requests.get('https://example.com/data.json')",
            ],
        ),
    ],
)
def test_codex_shell_guard_blocks_public_lookup_patterns(tmp_path, tool, args):
    guard_path = tmp_path / "guard.py"
    guard_path.write_text(codex_pretooluse_guard_script())

    result = subprocess.run(
        [sys.executable, str(guard_path), "--shell-guard", tool, *args],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "blocked benchmark public lookup command" in result.stderr


def _install_shell_wrapper_fixture(tmp_path, tool, real_command):
    codex_home = tmp_path / "codex-home"
    bin_dir = codex_home / "razorback-bin"
    bin_dir.mkdir(parents=True)
    guard_path = codex_home / "razorback-public-lookup-guard.py"
    guard_path.write_text(codex_pretooluse_guard_script())
    guard_path.chmod(0o700)
    wrapper_path = bin_dir / tool
    wrapper_path.write_text(codex_shell_wrapper_script())
    wrapper_path.chmod(0o700)
    env = {
        "CODEX_HOME": str(codex_home),
        "RAZORBACK_GUARD_PYTHON": sys.executable,
        f"RAZORBACK_REAL_{tool.upper()}": str(real_command),
    }
    return wrapper_path, env


def test_codex_shell_wrapper_blocks_curl_before_real_command(tmp_path):
    marker = tmp_path / "curl-called"
    real_curl = tmp_path / "real-curl"
    real_curl.write_text(f"#!/bin/sh\n: > {shlex_quote_path(marker)}\n")
    real_curl.chmod(0o700)
    wrapper_path, env = _install_shell_wrapper_fixture(tmp_path, "curl", real_curl)

    result = subprocess.run(
        [str(wrapper_path), "https://example.com"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "blocked benchmark public lookup command" in result.stderr
    assert not marker.exists()


def test_codex_shell_wrapper_allows_local_python_source(tmp_path):
    marker = tmp_path / "python-called"
    real_python = tmp_path / "real-python"
    real_python.write_text(f"#!/bin/sh\n: > {shlex_quote_path(marker)}\n")
    real_python.chmod(0o700)
    wrapper_path, env = _install_shell_wrapper_fixture(tmp_path, "python", real_python)

    result = subprocess.run(
        [
            str(wrapper_path),
            "-c",
            "import duckdb; duckdb.sql('select 1').fetchall()",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert marker.exists()


def test_codex_shell_wrapper_blocks_python_stdin_public_lookup(tmp_path):
    marker = tmp_path / "python-called"
    real_python = tmp_path / "real-python"
    real_python.write_text(f"#!/bin/sh\n: > {shlex_quote_path(marker)}\n")
    real_python.chmod(0o700)
    wrapper_path, env = _install_shell_wrapper_fixture(tmp_path, "python3", real_python)

    result = subprocess.run(
        [str(wrapper_path)],
        input=(
            "import urllib.request\n"
            "urllib.request.urlopen('https://example.com').read()\n"
        ),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "blocked benchmark public lookup command" in result.stderr
    assert not marker.exists()


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


def test_codex_max_turns_rejection_is_actionable(tmp_path):
    """A custom max_turns is the most common codex trip (claude honors it, codex
    does not). The error must tell the user the fix: keep the default (200) and
    budget wall-clock via timeouts — not leave them to reverse-engineer it.
    """
    with pytest.raises(SpacedockSolverAgentError) as excinfo:
        codex_adapter.build_inner_agent(
            logs_dir=tmp_path,
            model="gpt-5.1-codex",
            harbor_agent_kwargs={"max_turns": 400},
            extra_env={"OPENAI_API_KEY": "sk-fake"},
        )
    message = str(excinfo.value)
    assert "200" in message
    assert "timeout" in message.lower()


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
    """v4-pkg9 owns the PreToolUse hook plumbing; Phase 3 just passes the kwarg through.

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
