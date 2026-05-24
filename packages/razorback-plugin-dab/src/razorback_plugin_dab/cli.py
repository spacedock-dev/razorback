# ABOUTME: razorback-plugin-dab CLI — generate / list / validate.
# ABOUTME: `generate` emits harbor task dirs; `list` prints the 12-dataset catalog as JSON.

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from razorback_plugin_dab import datasets as catalog
from razorback_plugin_dab.generate.prepare import prepare_dataset_tasks
from razorback_plugin_dab.hydration import DatasetNotHydratedError, check_hydrated

app = typer.Typer(no_args_is_help=True, add_completion=False, help="razorback-plugin-dab")


WORKSPACE_VARIANTS = ("direct-minimal", "direct-structured", "spacedock")
QUERY_MODES = ("batch", "per-query")


def _resolve_default_data_root() -> Path | None:
    """Resolve a default DAB data root when `--data-root` is absent on CLI.

    Resolution chain (returns the first hit):
      1. `$DATAAGENTBENCH_DATA_ROOT` if set + non-empty → that path.
      2. `~/dataagentbench/data` if it exists as a directory → that path.
      3. None — caller must surface a named-env-var error to the operator.

    Evaluated at command invocation time (not at typer.Option declaration
    time) so the resolution stays per-process and respects $HOME overrides
    in test environments.
    """
    import os

    env_value = os.environ.get("DATAAGENTBENCH_DATA_ROOT")
    if env_value:
        return Path(env_value).expanduser()
    home_default = Path("~/dataagentbench/data").expanduser()
    if home_default.is_dir():
        return home_default
    return None


@app.command()
def generate(
    datasets: str = typer.Option(
        ..., "--datasets", help="Comma-separated dataset names, or 'hello-fixture' for the smoke fixture."
    ),
    data_root: Optional[Path] = typer.Option(
        None, "--data-root", help="DAB data root (e.g. /path/to/dataagentbench/data)."
    ),
    out: Path = typer.Option(..., "--out", help="Output directory for emitted task tree."),
    workspace_variant: str = typer.Option(
        "direct-minimal", "--workspace-variant", help="One of: direct-minimal, direct-structured, spacedock."
    ),
    hints: bool = typer.Option(False, "--hints/--no-hints", help="Include db_description_withhint in workspace."),
    materialize: str = typer.Option(
        "bind",
        "--materialize",
        help="Dataset materialization mode: bind (default — bind-mount dumps from data_root) or copy (per-task workdir copy).",
    ),
    postgres_volume_mode: str = typer.Option(
        "reuse",
        "--postgres-volume-mode",
        help="postgres data volume strategy: reuse (default — dataset-keyed shared volume) or fresh (per-task unique volume).",
    ),
    query_mode: str = typer.Option(
        "per-query",
        "--query-mode",
        help="One of: batch, per-query (default: per-query). "
             "batch emits one task per dataset; per-query emits one per (dataset, query).",
    ),
) -> None:
    """Emit harbor task directories under <out>/<dataset>-q<n>/ for each requested dataset."""
    if workspace_variant not in WORKSPACE_VARIANTS:
        typer.echo(
            f"razorback-plugin-dab: unknown workspace_variant {workspace_variant!r}; "
            f"expected one of {WORKSPACE_VARIANTS}",
            err=True,
        )
        raise typer.Exit(code=2)

    if materialize not in ("bind", "copy"):
        typer.echo(
            f"razorback-plugin-dab: --materialize must be one of bind|copy; got {materialize!r}",
            err=True,
        )
        raise typer.Exit(code=2)

    if postgres_volume_mode not in ("reuse", "fresh"):
        typer.echo(
            f"razorback-plugin-dab: --postgres-volume-mode must be one of reuse|fresh; "
            f"got {postgres_volume_mode!r}",
            err=True,
        )
        raise typer.Exit(code=2)

    if query_mode not in QUERY_MODES:
        typer.echo(
            f"razorback-plugin-dab: --query-mode must be one of {QUERY_MODES}; got {query_mode!r}",
            err=True,
        )
        raise typer.Exit(code=2)

    out.mkdir(parents=True, exist_ok=True)
    requested = [d.strip() for d in datasets.split(",") if d.strip()]

    if requested == ["hello-fixture"]:
        _emit_hello_fixture(out)
        return

    if data_root is None:
        data_root = _resolve_default_data_root()
        if data_root is None:
            typer.echo(
                "razorback-plugin-dab: --data-root is required. Pass --data-root "
                "or set $DATAAGENTBENCH_DATA_ROOT to the DAB data directory "
                "(or ensure ~/dataagentbench/data exists).",
                err=True,
            )
            raise typer.Exit(code=2)

    known = {d.name for d in catalog.DAB_DATASETS}
    unknown = [d for d in requested if d not in known]
    if unknown:
        typer.echo(
            f"razorback-plugin-dab: unknown dataset(s) {unknown!r}; expected one of {sorted(known)}",
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        for name in requested:
            check_hydrated(data_root=data_root, dataset_name=name)
    except DatasetNotHydratedError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2)

    for name in requested:
        prepare_dataset_tasks(
            data_root=data_root,
            dataset=name,
            tasks_root=out,
            workspace_variant=workspace_variant,
            hints=hints,
            materialize_mode=materialize,
            postgres_volume_mode=postgres_volume_mode,
            query_mode=query_mode,
        )


@app.command("list")
def list_cmd() -> None:
    """Print the 12-dataset catalog as JSON (machine-readable)."""
    payload = [
        {"name": d.name, "backends": list(d.backends), "query_count": d.query_count}
        for d in catalog.DAB_DATASETS
    ]
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def validate(tasks_root: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True)) -> None:
    """Schema-check an emitted task tree by listing per-task directories."""
    tasks = sorted(p for p in tasks_root.iterdir() if p.is_dir())
    failures: list[str] = []
    for task_dir in tasks:
        toml = task_dir / "task.toml"
        if not toml.exists():
            failures.append(f"{task_dir}: missing task.toml")
            continue
        if not (task_dir / "instruction.md").exists():
            failures.append(f"{task_dir}: missing instruction.md")
        if not (task_dir / "tests").is_dir():
            failures.append(f"{task_dir}: missing tests/ dir")
    if failures:
        for line in failures:
            typer.echo(line, err=True)
        raise typer.Exit(code=1)
    typer.echo(f"OK: {len(tasks)} tasks validated")


def _emit_hello_fixture(out: Path) -> None:
    """Smallest harbor-shaped task tree: one task with name='main', echoes ok."""
    task_dir = out / "hello-fixture"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.toml").write_text(
        'schema_version = "1.2"\n\n'
        '[task]\n'
        'name = "razorback-plugin-dab/hello-fixture"\n'
        'description = "smoke fixture emitted by razorback-plugin-dab."\n\n'
        '[environment]\n'
        'docker_image = "alpine:3.20"\n'
        'workdir = "/workspace"\n\n'
        '[[steps]]\n'
        'name = "main"\n'
    )
    (task_dir / "instruction.md").write_text("Touch /workspace/done. The verifier checks for it.\n")
    env = task_dir / "environment"
    env.mkdir(exist_ok=True)
    (env / "Dockerfile").write_text("# Unused — [environment].docker_image selects the image.\n")
    tests = task_dir / "tests"
    tests.mkdir(exist_ok=True)
    test_sh = tests / "test.sh"
    test_sh.write_text(
        '#!/bin/sh\nset -eu\nmkdir -p /logs/verifier\n'
        'if [ -e /workspace/done ]; then\n'
        '  printf \'{"reward": 1.0}\\n\' > /logs/verifier/reward.json\n'
        'else\n'
        '  printf \'{"reward": 0.0}\\n\' > /logs/verifier/reward.json\n'
        'fi\n'
    )
    test_sh.chmod(0o755)
    steps_main = task_dir / "steps" / "main"
    steps_main.mkdir(parents=True, exist_ok=True)
    (steps_main / "instruction.md").write_text("Touch /workspace/done. The verifier checks for it.\n")
    (steps_main / "workdir").mkdir(exist_ok=True)


if __name__ == "__main__":
    app()
