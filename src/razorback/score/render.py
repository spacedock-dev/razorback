# ABOUTME: rk score renderers — canonical JSON (§3.3) + human-readable markdown (§3.2).
# ABOUTME: JSON key set is the §3.3 semver-stable surface; Task 9 pins it via snapshot.

"""Canonical JSON shape for `rk score` output (semver-stable within major version):

    {
      "score_version": 1,
      "alpha": 0.05,
      "strata": {
        "<stratum>": {
          "n_total": int,
          "n_completed": int,
          "n_errored": int,
          "n_pass": int,
          "pass_at_1": float | null,
          "wilson_ci": [float, float] | null,
          "error_reason": str | null
        }, ...
      },
      "stratified_pass_at_1": float | null,
      "stratified_n_completed": int,
      "stratified_n_errored": int,
      "error_reason": str | null,
      "against_constant": {  # present only when --against-constant supplied
        "name": str,
        "value": float,
        "per_stratum": {
          "<stratum>": {"verdict": str|null, "ci": [float, float]|null, "side": str|null}
        },
        "stratified": {"mean": float|null, "verdict": str|null}
      }
    }
"""

from __future__ import annotations

import json
from typing import Any

from razorback.score.reduce import ScoreReport
from razorback.score.verdict import AgainstConstantReport


def render_json(
    report: ScoreReport, verdict: AgainstConstantReport | None
) -> str:
    payload: dict[str, Any] = _report_to_jsonable(report)
    if verdict is not None:
        payload["against_constant"] = _verdict_to_jsonable(verdict)
    return json.dumps(payload, indent=2, sort_keys=False)


def render_markdown(
    report: ScoreReport, verdict: AgainstConstantReport | None
) -> str:
    lines: list[str] = []
    has_verdict = verdict is not None
    if has_verdict:
        verdict_col = f"vs {verdict['name']}={verdict['value']}"
        header = (
            f"| stratum | n_completed | n_errored | pass@1 | "
            f"{int((1 - report['alpha']) * 100)}% CI | {verdict_col} |"
        )
        separator = "|---|---|---|---|---|---|"
    else:
        header = (
            f"| stratum | n_completed | n_errored | pass@1 | "
            f"{int((1 - report['alpha']) * 100)}% CI |"
        )
        separator = "|---|---|---|---|---|"
    lines.append(header)
    lines.append(separator)

    for stratum_name in sorted(report["strata"].keys()):
        stats = report["strata"][stratum_name]
        pass_at_1 = _fmt_float(stats["pass_at_1"])
        ci = _fmt_ci(stats["wilson_ci"])
        row = (
            f"| {stratum_name} | {stats['n_completed']} | {stats['n_errored']} | "
            f"{pass_at_1} | {ci} |"
        )
        if has_verdict:
            v = verdict["per_stratum"].get(stratum_name, {})
            verdict_text = _verdict_text(v)
            row += f" {verdict_text} |"
        lines.append(row)

    mean = report["stratified_pass_at_1"]
    mean_text = _fmt_float(mean)
    if has_verdict:
        s = verdict["stratified"]
        lines.append(
            f"\nstratified pass@1: {mean_text}  "
            f"(vs {verdict['name']}={verdict['value']}: {s['verdict']})"
        )
    else:
        lines.append(f"\nstratified pass@1: {mean_text}")
    return "\n".join(lines)


def _report_to_jsonable(report: ScoreReport) -> dict[str, Any]:
    strata: dict[str, Any] = {}
    for name, stats in report["strata"].items():
        ci = stats["wilson_ci"]
        strata[name] = {
            **{
                key: stats[key]
                for key in (
                    "dataset",
                    "query_id",
                    "benchmark_kind",
                    "benchmark_task_id",
                )
                if key in stats
            },
            "n_total": stats["n_total"],
            "n_completed": stats["n_completed"],
            "n_errored": stats["n_errored"],
            "n_pass": stats["n_pass"],
            "pass_at_1": stats["pass_at_1"],
            "wilson_ci": list(ci) if ci is not None else None,
            "error_reason": stats["error_reason"],
        }
    return {
        "score_version": report["score_version"],
        "alpha": report["alpha"],
        "strata": strata,
        "stratified_pass_at_1": report["stratified_pass_at_1"],
        "stratified_n_completed": report["stratified_n_completed"],
        "stratified_n_errored": report["stratified_n_errored"],
        "error_reason": report["error_reason"],
    }


def _verdict_to_jsonable(verdict: AgainstConstantReport) -> dict[str, Any]:
    per_stratum: dict[str, Any] = {}
    for name, v in verdict["per_stratum"].items():
        ci = v.get("ci")
        per_stratum[name] = {
            "verdict": v.get("verdict"),
            "ci": list(ci) if ci is not None else None,
            "side": v.get("side"),
        }
    return {
        "name": verdict["name"],
        "value": verdict["value"],
        "per_stratum": per_stratum,
        "stratified": {
            "mean": verdict["stratified"]["mean"],
            "verdict": verdict["stratified"]["verdict"],
        },
    }


def _fmt_float(value: float | None) -> str:
    return "null" if value is None else f"{value:.3f}"


def _fmt_ci(ci: tuple[float, float] | None) -> str:
    if ci is None:
        return "null"
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def _verdict_text(v: dict[str, Any]) -> str:
    verdict = v.get("verdict")
    if verdict is None:
        return "null"
    if verdict == "outside-CI":
        side = v.get("side") or ""
        return f"outside-CI ({side})" if side else "outside-CI"
    return verdict
