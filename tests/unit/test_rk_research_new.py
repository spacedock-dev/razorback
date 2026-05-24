# ABOUTME: TDD for `rk research new <slug> --from <ref>` scaffold command.
# ABOUTME: Covers idempotence, dry-run, benchmark-defaults lookup, default fallback, dabstep + swe-bench-verified scenarios.

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


def _runner_and_app():
    """Import the CLI lazily so test collection survives early failures."""
    from razorback.cli import app

    return CliRunner(), app


def test_rk_research_new_creates_scaffold_tree(tmp_path):
    """Scaffolds the canonical layout: README, specs/, solver_workflows/,
    hypotheses/, runs/.gitignore, drivers/, razorback-research.toml."""
    runner, app = _runner_and_app()
    target = tmp_path / "dabstep-research"
    result = runner.invoke(
        app,
        [
            "research",
            "new",
            "dabstep",
            "--from",
            "adyen/dabstep@latest",
            "--into",
            str(target),
        ],
    )
    assert result.exit_code == 0, result.output
    assert target.exists()
    assert (target / "README.md").is_file()
    assert (target / "specs" / "baseline.yaml").is_file()
    assert (target / "specs" / "README.md").is_file()
    assert (target / "solver_workflows" / "baseline" / "README.md").is_file()
    assert (target / "solver_workflows" / "README.md").is_file()
    assert (target / "hypotheses" / "README.md").is_file()
    assert (target / "runs" / ".gitignore").is_file()
    assert (target / "drivers" / "matrix.sh").is_file()
    assert (target / "razorback-research.toml").is_file()


def test_rk_research_new_dabstep_baseline_spec_validates(tmp_path):
    """The scaffolded baseline.yaml parses through razorback's Spec model
    and carries kind: harbor + dataset: adyen/dabstep@latest."""
    from razorback.spec.parse import parse_spec_file

    runner, app = _runner_and_app()
    target = tmp_path / "dabstep-research"
    result = runner.invoke(
        app,
        [
            "research",
            "new",
            "dabstep",
            "--from",
            "adyen/dabstep@latest",
            "--into",
            str(target),
        ],
    )
    assert result.exit_code == 0, result.output
    spec_path = target / "specs" / "baseline.yaml"
    spec = parse_spec_file(spec_path)
    # benchmark block
    assert type(spec.benchmark).__name__ == "HarborBenchmarkBlock"
    assert spec.benchmark.dataset == "adyen/dabstep@latest"
    # agent defaults pulled from benchmark-defaults.toml
    assert spec.agent.kind == "spacedock_solver"
    assert spec.agent.max_turns == 16
    assert float(spec.agent.max_budget_usd or 0) == 2.0


def test_rk_research_new_swe_bench_verified_baseline_spec_validates(tmp_path):
    """The scaffolded baseline.yaml parses for swe-bench-verified with the
    larger per-task defaults (max_turns: 40, max_budget_usd: 12)."""
    from razorback.spec.parse import parse_spec_file

    runner, app = _runner_and_app()
    target = tmp_path / "swe-bench-verified-research"
    result = runner.invoke(
        app,
        [
            "research",
            "new",
            "swe-bench-verified",
            "--from",
            "swe-bench/swe-bench-verified@latest",
            "--target-model",
            "claude-opus-4-7",
            "--into",
            str(target),
        ],
    )
    assert result.exit_code == 0, result.output
    spec = parse_spec_file(target / "specs" / "baseline.yaml")
    assert spec.benchmark.dataset == "swe-bench/swe-bench-verified@latest"
    assert spec.agent.model == "claude-opus-4-7"
    assert spec.agent.max_turns == 40
    assert float(spec.agent.max_budget_usd or 0) == 12.0
    assert spec.agent.reasoning_effort == "xhigh"


def test_rk_research_new_unknown_benchmark_uses_conservative_defaults(tmp_path):
    """For an org/name not in benchmark-defaults.toml, the scaffold falls back
    to conservative defaults and embeds a TODO comment so researchers can
    tune."""
    runner, app = _runner_and_app()
    target = tmp_path / "exotic-research"
    result = runner.invoke(
        app,
        [
            "research",
            "new",
            "exotic",
            "--from",
            "org/exotic@latest",
            "--into",
            str(target),
        ],
    )
    assert result.exit_code == 0, result.output
    body = (target / "specs" / "baseline.yaml").read_text()
    assert "TODO: tune for this benchmark" in body
    # Spec still parses with conservative defaults
    from razorback.spec.parse import parse_spec_file

    spec = parse_spec_file(target / "specs" / "baseline.yaml")
    assert spec.benchmark.dataset == "org/exotic@latest"


def test_rk_research_new_refuses_existing_non_empty_dir(tmp_path):
    """Refuses to scaffold into an existing non-empty directory (no
    accidental overwrite)."""
    runner, app = _runner_and_app()
    target = tmp_path / "exists"
    target.mkdir()
    (target / "junk").write_text("hi")
    result = runner.invoke(
        app,
        [
            "research",
            "new",
            "dabstep",
            "--from",
            "adyen/dabstep@latest",
            "--into",
            str(target),
        ],
    )
    assert result.exit_code != 0
    assert "exists" in result.output.lower() or "non-empty" in result.output.lower()


def test_rk_research_new_dry_run_prints_plan_writes_nothing(tmp_path):
    """--dry-run prints the planned scaffold tree and exits 0 without writing
    files."""
    runner, app = _runner_and_app()
    target = tmp_path / "would-create"
    result = runner.invoke(
        app,
        [
            "research",
            "new",
            "dabstep",
            "--from",
            "adyen/dabstep@latest",
            "--into",
            str(target),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert not target.exists(), "dry-run must not write the scaffold"
    assert "specs/baseline.yaml" in result.output
    assert "solver_workflows/baseline/README.md" in result.output


def test_rk_research_new_default_into_targets_home_slug(tmp_path, monkeypatch):
    """When --into is omitted, the default target is ~/<slug>-research/."""
    monkeypatch.setenv("HOME", str(tmp_path))
    runner, app = _runner_and_app()
    result = runner.invoke(
        app,
        [
            "research",
            "new",
            "myresearch",
            "--from",
            "org/myresearch@latest",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "myresearch-research" / "specs" / "baseline.yaml").is_file()


def test_rk_research_new_solver_workflow_readme_required_sections(tmp_path):
    """The scaffolded solver_workflows/baseline/README.md carries the four
    required sections per design doc §2.3 + the External-oracle audit prose
    aligned with wp."""
    runner, app = _runner_and_app()
    target = tmp_path / "dabstep-research"
    runner.invoke(
        app,
        [
            "research",
            "new",
            "dabstep",
            "--from",
            "adyen/dabstep@latest",
            "--into",
            str(target),
        ],
    )
    body = (target / "solver_workflows" / "baseline" / "README.md").read_text()
    assert "## Stages" in body
    assert "## Reset declaration" in body
    assert "## External-oracle audit" in body
    # External-oracle audit prose names the forbidden libs / patterns
    assert "datasets.load_dataset" in body or "load_dataset" in body
    assert "huggingface" in body.lower()


def test_rk_research_new_matrix_sh_chains_run_audit_score(tmp_path):
    """The scaffolded drivers/matrix.sh chains rk run -> rk audit --policy
    strict -> rk score, mirroring examples/drivers/dab-paper-matrix.sh's
    pattern."""
    runner, app = _runner_and_app()
    target = tmp_path / "dabstep-research"
    runner.invoke(
        app,
        [
            "research",
            "new",
            "dabstep",
            "--from",
            "adyen/dabstep@latest",
            "--into",
            str(target),
        ],
    )
    body = (target / "drivers" / "matrix.sh").read_text()
    assert "rk freeze" in body
    assert "rk run" in body
    assert "rk audit" in body and "--policy strict" in body
    assert "rk score" in body
    # Smoke gate hint for spacedock variants
    assert "subagent-trace-manifest.json" in body
