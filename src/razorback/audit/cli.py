# ABOUTME: `rk audit` Typer command (Layer 3 post-hoc trajectory scan over a run-dir).
# ABOUTME: Maps --policy strict + any non-clean trial to TaintFindingsError (exit 23).

import json
from pathlib import Path

import typer

from razorback.audit import claude_code
from razorback.audit import harbor_codex
from razorback.audit import taint
from razorback.errors import ExitCode


_TRIAL_SENTINELS = ("codex-output.jsonl", "claude-output.jsonl", "traces/manifest.json")


def _discover_trial_roots(run_dir: Path) -> list[Path]:
    """Walk run_dir; return subdirectories that look like trial roots.

    A trial root is any directory containing one of `codex-output.jsonl`,
    `claude-output.jsonl`, or `traces/manifest.json`. Mirrors the upstream
    discover_scan_inputs semantics but operates one level up, at the
    per-trial granularity that `rk audit` surfaces.
    """
    seen: set[Path] = set()
    roots: list[Path] = []
    for sentinel in _TRIAL_SENTINELS:
        for hit in sorted(run_dir.rglob(sentinel)):
            if sentinel == "traces/manifest.json":
                candidate = hit.parent.parent
            else:
                candidate = hit.parent
            if candidate in seen:
                continue
            seen.add(candidate)
            roots.append(candidate)
    for candidate in harbor_codex.discover_trial_roots(run_dir):
        if candidate in seen:
            continue
        seen.add(candidate)
        roots.append(candidate)
    claude_code_roots = claude_code.discover_trial_roots(run_dir)
    for candidate in claude_code_roots:
        if candidate in seen:
            continue
        seen.add(candidate)
        roots.append(candidate)
    # The claude-cli runtime symlinks ``claude-output.jsonl`` to
    # ``claude-code.txt`` under ``steps/main/agent/`` for PKG-26 audit-sentinel
    # parity. The sentinel rglob above therefore double-discovers that nested
    # agent directory as a ghost trial. Drop those ghosts when a strict ancestor
    # is already a claude_code trial root — the cell-level root carries the
    # findings; the nested ghost would be a redundant CLEAN row.
    if claude_code_roots:
        claude_set = set(claude_code_roots)
        roots = [
            r for r in roots
            if r in claude_set
            or not any(_is_strict_descendant(r, ancestor) for ancestor in claude_set)
        ]
    return roots


def _is_strict_descendant(path: Path, ancestor: Path) -> bool:
    try:
        rel = path.relative_to(ancestor)
    except ValueError:
        return False
    return rel != Path(".")


def _reduce_trial_status(findings: list[dict]) -> str:
    """Reduce a trial's findings list to one of clean / tainted / coverage_missing."""
    for finding in findings:
        if finding.get("category") == "forbidden_lookup":
            return "tainted"
    for finding in findings:
        category = finding.get("category")
        if category == "trace_coverage" and finding.get("status") in {"missing", "partial"}:
            return "coverage_missing"
        if category == "attempt_incomplete":
            return "coverage_missing"
        if category == "scanner_error":
            return "coverage_missing"
    return "clean"


def _trial_id(trial_root: Path, run_dir: Path) -> str:
    try:
        rel = trial_root.relative_to(run_dir).as_posix()
    except ValueError:
        rel = trial_root.as_posix()
    return rel or "."


def _audit_run_dir(run_dir: Path, policy: str) -> dict:
    trials = []
    summary = {"clean": 0, "tainted": 0, "coverage_missing": 0}
    for trial_root in _discover_trial_roots(run_dir):
        report = taint.scan_attempt(trial_root, taint_policy="audit")
        findings = [
            *report["findings"],
            *harbor_codex.scan_trial(trial_root),
            *claude_code.scan_trial(trial_root),
        ]
        status = _reduce_trial_status(findings)
        summary[status] += 1
        trials.append({
            "trial_id": _trial_id(trial_root, run_dir),
            "trial_path": str(trial_root),
            "taint_status": status,
            "findings": findings,
        })
    return {
        "schema_version": "rk-audit-v1",
        "run_dir": str(run_dir),
        "policy": policy,
        "trials": trials,
        "summary": summary,
    }


def audit_command(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True),
    policy: str = typer.Option(
        "audit",
        "--policy",
        help="Policy mode: `audit` (default, report only) or `strict` (exit 23 on non-clean).",
    ),
    format: str = typer.Option(
        "json",
        "--format",
        help="Output format: `json` (default) or `markdown`.",
    ),
) -> None:
    """Layer 3 post-hoc audit (spec §9.4): scan a run-dir for trajectory leak patterns."""
    if policy not in {"audit", "strict"}:
        typer.echo(f"unknown policy: {policy} (expected 'audit' or 'strict')", err=True)
        raise typer.Exit(ExitCode.USAGE)
    if format not in {"json", "markdown"}:
        typer.echo(f"unknown format: {format} (expected 'json' or 'markdown')", err=True)
        raise typer.Exit(ExitCode.USAGE)

    run_dir_resolved = Path(run_dir).expanduser().resolve()
    result = _audit_run_dir(run_dir_resolved, policy)

    if format == "json":
        typer.echo(json.dumps(result, indent=2, sort_keys=True))
    else:
        lines = [
            "# rk audit",
            "",
            f"Run dir: {result['run_dir']}",
            f"Policy: {result['policy']}",
            f"Summary: clean={result['summary']['clean']} "
            f"tainted={result['summary']['tainted']} "
            f"coverage_missing={result['summary']['coverage_missing']}",
            "",
        ]
        for trial in result["trials"]:
            lines.append(f"## {trial['trial_id']}: {trial['taint_status']}")
            if not trial["findings"]:
                lines.append("")
                lines.append("No findings.")
                lines.append("")
                continue
            for finding in trial["findings"]:
                lines.append(
                    f"- {finding.get('category')} in {finding.get('source_kind')} "
                    f"{finding.get('source_path')} "
                    f"({finding.get('status') or finding.get('pattern')})"
                )
            lines.append("")
        typer.echo("\n".join(lines))

    if policy == "strict":
        non_clean = result["summary"]["tainted"] + result["summary"]["coverage_missing"]
        if non_clean > 0:
            typer.echo(
                f"TaintFindingsError: rk audit --policy strict found "
                f"{non_clean} non-clean trial(s) "
                f"(tainted={result['summary']['tainted']}, "
                f"coverage_missing={result['summary']['coverage_missing']})",
                err=True,
            )
            raise typer.Exit(ExitCode.TAINT_FINDINGS)
