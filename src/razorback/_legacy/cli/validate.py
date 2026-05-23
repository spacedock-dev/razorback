# ABOUTME: `rk validate` command (§3.2). Parses spec, emits warnings JSON, exits 0 on warnings.
# ABOUTME: AC-4 (compose_services=False) + AC-5 (tools_allowed on ade-bench) live here.

import json
from pathlib import Path
from typing import Any

import typer

from razorback.errors import ExitCode, SpecError
from razorback.spec.parse import parse_spec_file
from razorback.spec.schema import AdeBenchBenchmarkBlock


def validate_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
) -> None:
    """Validate a razorback spec; emit warnings on stdout as JSON."""
    try:
        spec = parse_spec_file(spec_path)
    except SpecError as exc:
        typer.echo(f"SpecError: {exc}", err=True)
        raise typer.Exit(ExitCode.SPEC_ERROR)

    warnings: list[dict[str, Any]] = []

    if isinstance(spec.benchmark, AdeBenchBenchmarkBlock):
        ade_reset = {
            "agent_container": True,
            "compose_services": False,
            "host_workspace": True,
        }

        # AC-4 — warn whenever any reset surface is False.
        for surface, ok in ade_reset.items():
            if ok:
                continue
            if surface == "compose_services":
                warnings.append(
                    {
                        "code": "ADE_BENCH_COMPOSE_NOT_RESET",
                        "kind": "per_trial_state_reset",
                        "message": (
                            "ade-bench declares `compose_services: False`: state in "
                            "compose-managed services may leak across trials (the §6.5 "
                            'example: "postgres state leaks across trials"). The '
                            "trial-isolation contract for compose-managed services is "
                            "the user's responsibility."
                        ),
                    }
                )
            else:
                warnings.append(
                    {
                        "code": f"ADE_BENCH_{surface.upper()}_NOT_RESET",
                        "kind": "per_trial_state_reset",
                        "message": f"ade-bench declares `{surface}: False`: see §6.5.",
                    }
                )

        # AC-5 — tools_allowed is not enforced for ade-bench's agent path (§9.2).
        tools_allowed = getattr(spec.agent, "tools_allowed", []) or []
        if tools_allowed:
            warnings.append(
                {
                    "code": "ADE_BENCH_TOOLS_ALLOWED_NOT_ENFORCED",
                    "kind": "tools_allowed",
                    "message": (
                        f"`tools_allowed: {tools_allowed!r}` is declared but "
                        "ade-bench's compose-managed environment does not route through "
                        "razorback's allowlist enforcement; see §9.2."
                    ),
                }
            )

    typer.echo(json.dumps({"warnings": warnings}))
