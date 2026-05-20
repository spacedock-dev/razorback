# ABOUTME: PKG-9 v2 AC-3 — live runtime probe asserts PreToolUse denial event.
# ABOUTME: Cost-bearing; gated by RAZORBACK_RUN_TOOLS_DENIED_LIVE=1 + valid auth.

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
FIXTURE_SPEC = REPO / "tests" / "fixtures" / "specs" / "tools_denied_live.yaml"

_GATE = os.environ.get("RAZORBACK_RUN_TOOLS_DENIED_LIVE") == "1"
_HAS_AUTH = bool(
    os.environ.get("ANTHROPIC_API_KEY")
    or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    or (Path.home() / ".claude" / "benchmark-token").exists()
)


def _iter_session_jsonl_records(run_dir: Path):
    """Walk every harbor-written session JSONL under the run-dir.

    Claude Code records its transcript under
    `<harbor-logs-dir>/sessions/.../*.jsonl`; harbor stages those per-trial.
    PreToolUse denials surface in two places: (1) the system stream's
    tool_use_error event, (2) the tool_result block whose content names the
    `--disallowedTools` rule. Either is acceptable evidence.
    """
    for jsonl in run_dir.rglob("*.jsonl"):
        try:
            for line in jsonl.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    yield jsonl, json.loads(line)
                except json.JSONDecodeError:
                    continue
        except OSError:
            continue


def _record_mentions_denial(rec: dict) -> bool:
    """A denial event references the disallowed-tools rule for pip install datasets."""
    text = json.dumps(rec)
    if "pip install datasets" not in text:
        return False
    # Match the markers Claude Code emits when a tool call is refused via the
    # --disallowedTools flag. Either phrase is sufficient evidence.
    markers = (
        "disallowed",
        "Tool ",  # e.g., "Tool ... is not allowed"
        "permission",
        "not allowed",
        "denied",
    )
    return any(m in text for m in markers)


@pytest.mark.integration
@pytest.mark.skipif(
    not _GATE,
    reason=(
        "AC-3 live runtime probe is cost-bearing; set "
        "RAZORBACK_RUN_TOOLS_DENIED_LIVE=1 to run."
    ),
)
@pytest.mark.skipif(
    not _HAS_AUTH,
    reason="AC-3 needs ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN or benchmark-token.",
)
@pytest.mark.skipif(
    shutil.which("claude") is None,
    reason="AC-3 needs the host `claude` CLI on PATH.",
)
@pytest.mark.timeout(900)
def test_tools_denied_live_pip_install_datasets_is_blocked(tmp_path: Path):
    """A fixture spec whose agent attempts `pip install datasets` runs to
    completion, but the run-dir's transcripts carry a PreToolUse denial
    event citing the hook rule, and the install never executes.
    """
    runs_root = tmp_path / "_runs"
    runs_root.mkdir()

    # Freeze the fixture spec so rk run sees a v2 frozen spec (sealed_hash pinned).
    # The CLI surface for `rk spec freeze` is not wired; call the freeze_cmd
    # Typer command directly via typer.testing to materialize the frozen spec.
    frozen_path = tmp_path / "tools_denied_live.frozen.yaml"
    from typer.testing import CliRunner
    import typer
    from razorback.provenance.freeze_cmd import freeze_command

    freeze_app = typer.Typer()
    freeze_app.command()(freeze_command)
    result = CliRunner().invoke(
        freeze_app,
        [str(FIXTURE_SPEC), "--out", str(frozen_path)],
    )
    assert result.exit_code == 0, f"freeze failed: {result.output}"
    assert frozen_path.exists(), f"freeze did not write {frozen_path}"

    run = subprocess.run(
        [
            sys.executable, "-m", "razorback.cli", "run",
            str(frozen_path), "--runs-dir", str(runs_root),
        ],
        cwd=REPO,
        env={**os.environ},
        capture_output=True,
        text=True,
        timeout=900,
    )
    # The agent's denied pip install does not by itself fail the run; harbor
    # surfaces the trial as completed with the agent's last message. Exit 0
    # is the expected path under the local nop-task benchmark.
    assert run.returncode == 0, (
        f"rk run failed (exit {run.returncode}):\n"
        f"stdout={run.stdout}\nstderr={run.stderr}"
    )

    experiment_dir = runs_root / "pkg9-v2-tools-denied-live"
    run_dirs = [p for p in experiment_dir.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1, run_dirs
    run_dir = run_dirs[0]

    # AC-3 evidence: at least one transcript record mentions a denial event
    # referencing `pip install datasets`. The harbor publisher's event stream
    # (events.jsonl, per spec §6.3 observer translation) is the canonical
    # surface; until that lands in v2, scan harbor's session transcripts which
    # carry the same payload.
    denial_records = [
        (path, rec)
        for path, rec in _iter_session_jsonl_records(run_dir)
        if _record_mentions_denial(rec)
    ]
    assert denial_records, (
        f"no PreToolUse denial event for `pip install datasets` recorded "
        f"under {run_dir}; harbor transcripts: "
        f"{[p.relative_to(run_dir) for p in run_dir.rglob('*.jsonl')]}"
    )

    # The denied install must not have executed: search the transcripts for a
    # successful `pip install datasets` tool_result (return_code 0 + stdout
    # mentioning the package being installed). If any such record exists, the
    # hook did not block.
    successful_installs = [
        (path, rec)
        for path, rec in _iter_session_jsonl_records(run_dir)
        if "Successfully installed datasets" in json.dumps(rec)
    ]
    assert not successful_installs, (
        f"PreToolUse hook did not block `pip install datasets`; "
        f"successful-install records: {successful_installs}"
    )
