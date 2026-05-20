# ABOUTME: `rk run` Typer command (Phase 1 v2). Parse, pre-check, translate, delegate to harbor.
# ABOUTME: Maps razorback typed errors to documented exit codes (§3.4).

import os
import subprocess
from pathlib import Path
from typing import Optional

import typer

from razorback.errors import (
    BudgetExceededError,
    ConfigInvalidError,
    ExitCode,
    RazorbackError,
    SpecError,
)
from razorback.provenance.drift import check_alias_drift, check_harbor_drift
from razorback.provenance.errors import AliasDriftError
from razorback.runs_dir_canary import (
    check_runs_dir_visible,
    default_container_probe_factory,
)
from razorback.spec.freeze import derive_job_name
from razorback.spec.parse import parse_spec_file
from razorback.translate import spec_to_job_config


def _resolve_model_version(model_alias: str, frozen_resolved: str, allow_drift: bool):
    """Re-resolve via Anthropic SDK; wrapped for test patching."""
    import anthropic

    client = anthropic.Anthropic()
    return check_alias_drift(
        model_alias=model_alias,
        frozen_resolved_version=frozen_resolved,
        client=client,
        allow=allow_drift,
    )


def _run_canary(runs_dir: Path) -> None:
    """Runs-dir mount-visibility probe (AC-8); wrapped for test patching."""
    probe = default_container_probe_factory()
    check_runs_dir_visible(runs_dir, container_probe=probe)


def _invoke_harbor(job_config_yaml: Path, env: dict[str, str]) -> int:
    """Subprocess-invoke `harbor run -c <yaml>`; wrapped for test patching.

    `env` is the full environment for the harbor subprocess. Callers stage
    HOME under the runs-dir so harbor's hardcoded `~/.cache/harbor` and
    `~/.harbor` resolve to writable paths in sandboxed environments
    (CI, agent sandboxes, Colima). Returns harbor's exit code; razorback
    surfaces non-zero as exit 30.
    """
    proc = subprocess.run(
        ["uv", "run", "harbor", "run", "-c", str(job_config_yaml)],
        env=env,
        capture_output=False,
    )
    return proc.returncode


def _stage_harbor_home(runs_dir_resolved: Path) -> Path:
    """Create a sandbox-safe HOME for harbor under the user's runs-dir.

    Harbor hardcodes `~/.cache/harbor` and `~/.harbor` via Path.expanduser.
    Pointing HOME under the runs-dir keeps both inside the user-chosen,
    canary-checked runs-dir tree. The user's real `~/.docker/` (cli-plugins,
    config, contexts) is symlinked in so harbor's subprocess docker calls
    still find `docker compose` and the active context.
    """
    harbor_home = runs_dir_resolved / ".harbor-home"
    (harbor_home / ".cache" / "harbor").mkdir(parents=True, exist_ok=True)
    (harbor_home / ".harbor").mkdir(parents=True, exist_ok=True)
    real_docker = Path(os.environ.get("HOME", str(Path.home()))) / ".docker"
    synthetic_docker = harbor_home / ".docker"
    if real_docker.exists() and not synthetic_docker.exists():
        synthetic_docker.symlink_to(real_docker)
    return harbor_home


def _resolve_docker_host() -> str | None:
    """Return the user's active docker host so the harbor subprocess can reach docker.

    Redirecting HOME (so harbor's hardcoded ~/.cache/harbor works) hides the
    user's `~/.docker/config.json` from docker's context resolver, which then
    falls back to the default socket and fails on Colima/Docker-Desktop hosts.
    Pre-resolve the current context's Host so the subprocess gets DOCKER_HOST
    set explicitly.
    """
    if "DOCKER_HOST" in os.environ:
        return os.environ["DOCKER_HOST"]
    try:
        proc = subprocess.run(
            ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return None


def _write_provenance_artifacts(spec_bytes: bytes, spec, run_dir: Path) -> None:
    """AC-3: byte-for-byte echo of the input frozen spec + provenance.yaml writer.

    `spec_bytes` is the raw bytes of the input frozen spec; `spec` is its
    parsed form (used to extract the provenance block for provenance.yaml).
    """
    from razorback.provenance.provenance_yaml import write_provenance_yaml

    (run_dir / "spec.frozen.yaml").write_bytes(spec_bytes)
    frozen_provenance = spec.model_dump(mode="json").get("provenance") or {}
    if frozen_provenance:
        write_provenance_yaml(
            run_dir / "provenance.yaml", frozen_provenance, drift_record=None
        )


def run_command(
    spec_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    runs_dir: Path = typer.Option(Path("_runs"), "--runs-dir", help="Base directory for run-dirs."),
    allow_alias_drift: bool = typer.Option(
        False,
        "--allow-alias-drift",
        help="Run even when provider model version differs from frozen.",
    ),
    max_budget_usd_running: Optional[Path] = typer.Option(
        None,
        "--max-budget-usd-running",
        help="Path to running-total JSON file; the gate refuses on overage and "
             "appends actual cost on completion (per spec §3.2 + §3.4 exit 22).",
    ),
) -> None:
    """Execute a frozen spec against harbor and write the v2 run-dir artifacts."""
    try:
        spec = parse_spec_file(spec_path)
    except SpecError as exc:
        typer.echo(f"SpecError: {exc}", err=True)
        raise typer.Exit(ExitCode.SPEC_ERROR)

    # AC-8: runs-dir mount-visibility canary BEFORE any agent invocation.
    runs_dir_resolved = Path(runs_dir).expanduser().resolve()
    try:
        _run_canary(runs_dir_resolved)
    except ConfigInvalidError as exc:
        typer.echo(f"ConfigInvalidError: {exc}", err=True)
        raise typer.Exit(ExitCode.CONFIG_INVALID)

    # AC-2: harbor + alias-drift pre-checks.
    frozen_provenance = spec.model_dump(mode="json").get("provenance") or {}
    frozen_model = frozen_provenance.get("model_resolved_version")
    frozen_harbor = frozen_provenance.get("harbor_version")

    if frozen_harbor is not None:
        try:
            check_harbor_drift(frozen=frozen_harbor, installed=None)
        except RazorbackError as exc:
            typer.echo(f"{type(exc).__name__}: {exc}", err=True)
            raise typer.Exit(exc.exit_code)

    if frozen_model is not None:
        model_alias = getattr(spec.agent, "model", None) or "claude-opus-4-5"
        try:
            _resolve_model_version(model_alias, frozen_model, allow_alias_drift)
        except AliasDriftError as exc:
            typer.echo(f"AliasDriftError: {exc}", err=True)
            raise typer.Exit(ExitCode.ALIAS_DRIFT)

    # AC-6 + §3.1 canonicalization: jobs_dir is the absolute, symlink-resolved path.
    spec_bytes = spec_path.read_bytes()
    job_name = derive_job_name(spec_bytes.decode("utf-8"))
    run_dir = runs_dir_resolved / spec.experiment / job_name
    run_dir.mkdir(parents=True, exist_ok=True)

    # Phase 4a: pre-launch budget gate. Opt-in via --max-budget-usd-running.
    # Refuses with exit 22 before spending harbor compute when the running
    # total plus this invocation's estimate would exceed the cap.
    if max_budget_usd_running is not None:
        from razorback.budget import (
            decide_budget,
            read_estimate_from_spec,
            read_running_total,
            stamp_started,
        )

        meta = getattr(spec, "experiment_meta", None)
        max_budget = getattr(meta, "max_budget_usd", None) if meta else None
        if max_budget is None:
            typer.echo(
                "ConfigInvalidError: --max-budget-usd-running requires "
                "spec.experiment_meta.max_budget_usd",
                err=True,
            )
            raise typer.Exit(ExitCode.CONFIG_INVALID)
        try:
            estimate = read_estimate_from_spec(spec)
            rt = read_running_total(
                max_budget_usd_running,
                experiment=spec.experiment,
                max_budget_usd=max_budget,
            )
            decide_budget(rt, estimate_usd=estimate)
        except BudgetExceededError as exc:
            typer.echo(f"BudgetExceededError: {exc}", err=True)
            raise typer.Exit(ExitCode.BUDGET_EXCEEDED)
        except ConfigInvalidError as exc:
            typer.echo(f"ConfigInvalidError: {exc}", err=True)
            raise typer.Exit(ExitCode.CONFIG_INVALID)
        # Gate decided "proceed": stamp the in-flight record.
        stamp_started(
            path=max_budget_usd_running,
            experiment=spec.experiment,
            max_budget_usd=max_budget,
            estimate_usd=estimate,
            run_dir=str(run_dir),
        )

    try:
        job_config, _ = spec_to_job_config(
            spec,
            job_name=job_name,
            jobs_dir=run_dir.parent,
            tasks_root=run_dir / "tasks",
            project_root=Path.cwd(),
        )
    except RazorbackError as exc:
        typer.echo(f"{type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(exc.exit_code)

    # Harbor's AgentConfig._serialize_env templatizes sensitive env values that
    # match os.environ ("FOO" -> "${FOO}"); values that don't match are redacted
    # irrecoverably (sk-a****gAA). razorback resolves OAuth from
    # ~/.claude/benchmark-token, which never lives in os.environ — so mirror
    # AgentConfig.env into os.environ before serializing so the on-disk
    # _job_config.yaml carries templates that the harbor subprocess can
    # resolve via the inherited harbor_env below.
    for agent_cfg in job_config.agents:
        for env_key, env_val in (agent_cfg.env or {}).items():
            os.environ[env_key] = env_val

    job_config_yaml = run_dir / "_job_config.yaml"
    job_config_yaml.write_text(job_config.model_dump_json(indent=2))

    harbor_home = _stage_harbor_home(runs_dir_resolved)
    harbor_env = {**os.environ, "HOME": str(harbor_home)}
    docker_host = _resolve_docker_host()
    if docker_host is not None:
        harbor_env["DOCKER_HOST"] = docker_host
    rc = _invoke_harbor(job_config_yaml, harbor_env)
    if rc != 0:
        typer.echo(f"harbor run failed (exit {rc}); surfacing as exit 30", err=True)
        raise typer.Exit(ExitCode.HARBOR_RUNTIME)

    # Phase 4a: post-completion budget stamp. Read the harbor-produced cost
    # field from the run-dir and append it to the running-total file. When
    # cost telemetry is null (subscription auth per Phase 0 baseline), the
    # record is stamped with cost_known=False so the gate's next decision
    # falls back to the pre-launch estimate.
    if max_budget_usd_running is not None:
        from razorback.budget import (
            read_actual_cost_from_run_dir,
            stamp_completed,
        )

        actual_cost, cost_known = read_actual_cost_from_run_dir(run_dir)
        stamp_completed(
            path=max_budget_usd_running,
            run_dir=str(run_dir),
            actual_usd=actual_cost,
            cost_known=cost_known,
        )

    # AC-3 (Task 8 finishes the writer): write spec.frozen.yaml + provenance.yaml.
    _write_provenance_artifacts(spec_bytes, spec, run_dir)
