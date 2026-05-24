# ABOUTME: `rk score <run-dir>` Typer subcommand — single-run statistical readout.
# ABOUTME: Spec §3.2 surface; delegates to runs/aggregate.py for the headline number.

from __future__ import annotations

import json
from pathlib import Path

import typer

from razorback.errors import ExitCode, RazorbackError
from razorback.runs.aggregate import (
    count_trials,
    read_trial_outcomes,
    reduce_per_query_stratified,
)
from razorback.score.render import render_json, render_markdown
from razorback.score.verdict import AgainstConstantReport, against_constant


def _load_audit_status(run_dir: Path) -> dict | None:
    """Read `<run-dir>/audit.json` summary; return None if absent (soft-fail)."""
    audit_path = run_dir / "audit.json"
    if not audit_path.is_file():
        return None
    try:
        payload = json.loads(audit_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return None
    return {
        "clean": int(summary.get("clean", 0)),
        "tainted": int(summary.get("tainted", 0)),
        "coverage_missing": int(summary.get("coverage_missing", 0)),
    }


def _load_paper_baseline(run_dir: Path) -> tuple[str, float] | None:
    """Read `<run-dir>/spec.frozen.yaml` and return (name, value) when
    `experiment_meta.paper_baseline` is present; None otherwise (soft-fail
    on parse errors or missing file)."""
    spec_path = run_dir / "spec.frozen.yaml"
    if not spec_path.is_file():
        return None
    try:
        import yaml

        payload = yaml.safe_load(spec_path.read_text())
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(payload, dict):
        return None
    meta = payload.get("experiment_meta")
    if not isinstance(meta, dict):
        return None
    pb = meta.get("paper_baseline")
    if not isinstance(pb, dict):
        return None
    name = pb.get("name")
    value = pb.get("value")
    if not isinstance(name, str) or not isinstance(value, (int, float)):
        return None
    return name, float(value)


def score_command(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    alpha: float = typer.Option(0.05, "--alpha", min=0.0001, max=0.5),
    fmt: str = typer.Option("json", "--format", help="json (canonical) | markdown"),
    against: str | None = typer.Option(
        None,
        "--against-constant",
        help="name=value paper-reproduction comparison (e.g. paper=0.577)",
    ),
) -> None:
    """rk score <run-dir>: per-query Wilson CIs + stratified pass@1 mean. §3.2."""
    if fmt not in {"json", "markdown"}:
        raise typer.BadParameter(
            f"--format must be 'json' or 'markdown', got '{fmt}'"
        )

    constant_name: str | None = None
    constant_value: float | None = None
    constant_source: str | None = None
    if against is not None:
        if "=" not in against:
            raise typer.BadParameter(
                f"--against-constant must be name=value, got '{against}'"
            )
        constant_name, raw_value = against.split("=", 1)
        try:
            constant_value = float(raw_value)
        except ValueError as exc:
            raise typer.BadParameter(
                f"--against-constant value must be a float, got '{raw_value}'"
            ) from exc
        constant_source = "cli"
    else:
        # Auto-pull from spec.frozen.yaml's experiment_meta.paper_baseline.
        baseline = _load_paper_baseline(run_dir)
        if baseline is not None:
            constant_name, constant_value = baseline
            constant_source = "spec.frontmatter"

    try:
        outcomes = read_trial_outcomes(run_dir)
        report = reduce_per_query_stratified(
            outcomes, alpha=alpha, trial_counts=count_trials(run_dir)
        )
    except RazorbackError as exc:
        typer.echo(f"score error: {exc}", err=True)
        raise typer.Exit(int(exc.exit_code))

    verdict: AgainstConstantReport | None = None
    if constant_name is not None and constant_value is not None:
        verdict = against_constant(report, name=constant_name, value=constant_value)

    taint_status = _load_audit_status(run_dir)

    output = render_json(
        report, verdict, taint_status=taint_status, constant_source=constant_source
    ) if fmt == "json" else render_markdown(report, verdict)
    typer.echo(output)
    raise typer.Exit(ExitCode.OK)
