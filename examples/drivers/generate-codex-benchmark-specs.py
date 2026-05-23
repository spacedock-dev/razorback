#!/usr/bin/env python3
# ABOUTME: PKG-27 Codex benchmark spec generator for DAB and ade-bench N=1 cells.
# ABOUTME: Dry-runs portable data roots before any full score matrix execution.

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import yaml

from razorback_plugin_dab.datasets import DAB_DATASETS


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOLVER_WORKFLOW = "./examples/solver_workflows/codex-benchmark-solver"
CODEX_MODEL = "gpt-5.5"
WORKSPACE_VARIANTS = ("direct-minimal", "direct-structured", "spacedock")


class DabSpecRow(NamedTuple):
    dataset: str
    data_root: Path
    trials: int = 1


class AdeBenchSpecRow(NamedTuple):
    task_slug: str
    tasks_root: Path
    input_shape: str = "harbor_task_root"
    trials: int = 1


class AdeBenchDatasetSpecRow(NamedTuple):
    """Canonical ADE-Bench source: a Harbor published dataset ref.

    `dataset_ref` is the fully-qualified `<org>/<name>@<ref>` string fed to
    `PackageDatasetClient.download_dataset`. `task_slug` is the spec-side
    identifier (post dataset-prefix strip, e.g. `airbnb001`).
    """
    task_slug: str
    dataset_ref: str
    trials: int = 1


def plan_ade_bench_dataset_specs(
    *, dataset_ref: str, task_slugs: list[str]
) -> list[AdeBenchDatasetSpecRow]:
    """Plan one Codex N=1 cell per requested task slug against a Harbor dataset.

    Caller passes the spec-side slugs (e.g. `airbnb001`). The resolver in the
    translator strips the `<dataset_name>-` prefix when matching against
    per-task package names like `ade-bench-airbnb001` at run time.
    """
    if not task_slugs:
        raise ValueError(
            "plan_ade_bench_dataset_specs requires at least one task slug; "
            "pass `--ade-task-slug airbnb001` (repeatable) on the CLI"
        )
    return [
        AdeBenchDatasetSpecRow(task_slug=slug, dataset_ref=dataset_ref, trials=1)
        for slug in task_slugs
    ]


def emit_ade_bench_dataset_spec(
    row: AdeBenchDatasetSpecRow,
    *,
    out_dir: Path,
    model: str = CODEX_MODEL,
    reasoning_effort: str | None = None,
    solver_workflow: str = DEFAULT_SOLVER_WORKFLOW,
    docker_image_override: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / f"{_slug_for_filename(row.task_slug)}.yaml"
    benchmark = {
        "kind": "ade-bench",
        "dataset": row.dataset_ref,
        "tasks": [row.task_slug],
        "batch_mode": "per-task",
    }
    if docker_image_override is not None:
        benchmark["docker_image_override"] = docker_image_override
    payload = _base_spec(
        experiment=(
            f"codex-ade-bench-dataset-{_slug_for_filename(row.task_slug)}"
        ),
        benchmark=benchmark,
        trials=row.trials,
        model=model,
        reasoning_effort=reasoning_effort,
        solver_workflow=solver_workflow,
    )
    _write_yaml(
        spec_path,
        payload,
        about=(
            f"Codex ade-bench N=1 cell for task={row.task_slug} via "
            f"dataset={row.dataset_ref}."
        ),
    )
    return spec_path


def plan_dab_specs(*, data_root: Path) -> list[DabSpecRow]:
    return [DabSpecRow(dataset=d.name, data_root=data_root, trials=1) for d in DAB_DATASETS]


def plan_ade_bench_specs(*, ade_bench_root: Path) -> list[AdeBenchSpecRow]:
    slugs = (
        sorted(p.name for p in ade_bench_root.iterdir() if (p / "task.toml").is_file())
        if ade_bench_root.is_dir()
        else []
    )
    if slugs:
        return [
            AdeBenchSpecRow(
                task_slug=slug,
                tasks_root=ade_bench_root,
                trials=1,
            )
            for slug in slugs
        ]
    raise FileNotFoundError(
        "ade-bench score specs require a Harbor-shaped task root containing "
        f"*/task.toml entries; upstream tasks/*/task.yaml roots are retired: {ade_bench_root}"
    )


def emit_dab_spec(
    row: DabSpecRow,
    *,
    out_dir: Path,
    model: str = CODEX_MODEL,
    reasoning_effort: str | None = None,
    solver_workflow: str = DEFAULT_SOLVER_WORKFLOW,
    workspace_variant: str = "direct-structured",
    hints: bool = False,
) -> Path:
    if workspace_variant not in WORKSPACE_VARIANTS:
        raise ValueError(f"workspace_variant must be one of {', '.join(WORKSPACE_VARIANTS)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / f"{row.dataset}.yaml"
    payload = _base_spec(
        experiment=f"codex-dab-{_slug_for_filename(row.dataset)}",
        benchmark={
            "kind": "harbor_dab",
            "data_root": str(row.data_root),
            "datasets": [row.dataset],
            "workspace_variant": workspace_variant,
            "hints": hints,
        },
        trials=row.trials,
        model=model,
        reasoning_effort=reasoning_effort,
        solver_workflow=solver_workflow,
    )
    _write_yaml(spec_path, payload, about=f"Codex DAB N=1 cell for dataset={row.dataset}.")
    return spec_path


def emit_ade_bench_spec(
    row: AdeBenchSpecRow,
    *,
    out_dir: Path,
    model: str = CODEX_MODEL,
    reasoning_effort: str | None = None,
    solver_workflow: str = DEFAULT_SOLVER_WORKFLOW,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    spec_path = out_dir / f"{_slug_for_filename(row.task_slug)}.yaml"
    benchmark = {
        "kind": "ade-bench",
        "tasks_root": str(row.tasks_root),
        "tasks": [row.task_slug],
        "batch_mode": "per-task",
    }
    payload = _base_spec(
        experiment=f"codex-ade-bench-{_slug_for_filename(row.task_slug)}",
        benchmark=benchmark,
        trials=row.trials,
        model=model,
        reasoning_effort=reasoning_effort,
        solver_workflow=solver_workflow,
    )
    _write_yaml(spec_path, payload, about=f"Codex ade-bench N=1 cell for task={row.task_slug}.")
    return spec_path


def _base_spec(
    *,
    experiment: str,
    benchmark: dict,
    trials: int,
    model: str,
    reasoning_effort: str | None = None,
    solver_workflow: str = DEFAULT_SOLVER_WORKFLOW,
) -> dict:
    agent = {
        "kind": "spacedock_solver",
        "runtime": "codex",
        "model": model,
        "sampling": {"temperature": 0.0, "top_p": None, "seed": 1},
        "solver_workflow": solver_workflow,
        "spacedock_skill_version": "1.0.0",
        "max_turns": 200,
        "tools_allowed": [],
        "tools_denied": [],
    }
    if reasoning_effort is not None:
        agent["reasoning_effort"] = reasoning_effort
    return {
        "version": 1,
        "experiment": experiment,
        "agent": agent,
        "benchmark": benchmark,
        "trials": trials,
        "observers": [
            {"kind": "jsonl", "path": "events.jsonl"},
            {"kind": "stdout"},
        ],
    }


def _write_yaml(path: Path, payload: dict, *, about: str) -> None:
    header = (
        f"# ABOUTME: {about}\n"
        "# ABOUTME: Generated by examples/drivers/generate-codex-benchmark-specs.py.\n"
    )
    path.write_text(header + yaml.safe_dump(payload, sort_keys=False))


def _slug_for_filename(value: str) -> str:
    return value.lower().replace("_", "-")


def _freeze(spec_path: Path) -> None:
    subprocess.run(
        ["uv", "run", "rk", "freeze", str(spec_path), "--allow-missing"],
        cwd=REPO_ROOT,
        check=True,
    )


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _print_dab_dry_run(rows: list[DabSpecRow]) -> None:
    print(f"DAB Codex dry-run: N=1, datasets={len(rows)}, data_root={rows[0].data_root if rows else ''}")
    for row in rows:
        print(f"- dataset={row.dataset} trials={row.trials} data_root={row.data_root}")


def _print_ade_bench_dry_run(rows: list[AdeBenchSpecRow], *, ade_bench_root: Path) -> None:
    print(f"ade-bench Codex dry-run: N=1, tasks={len(rows)}, tasks_root={ade_bench_root}")
    for row in rows:
        print(f"- task={row.task_slug} trials={row.trials} tasks_root={row.tasks_root}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", choices=("dab", "ade-bench"), required=True)
    parser.add_argument("--dab-data-root", type=Path, help="Local DataAgentBench data root.")
    parser.add_argument(
        "--ade-bench-root",
        type=Path,
        help=(
            "Local ade-bench checkout root (dev/fixture path). "
            "Prefer --ade-dataset-ref for canonical Harbor-published-dataset runs."
        ),
    )
    parser.add_argument(
        "--ade-dataset-ref",
        type=str,
        help=(
            "Harbor published dataset ref (e.g. 'dbt-labs/ade-bench@latest'). "
            "Canonical ade-bench source per AC-4."
        ),
    )
    parser.add_argument(
        "--ade-task-slug",
        action="append",
        default=[],
        help=(
            "Spec-side task slug (e.g. 'airbnb001'). Repeat to emit multiple "
            "cells. Used only with --ade-dataset-ref."
        ),
    )
    parser.add_argument(
        "--ade-docker-image-override",
        type=str,
        help="docker_image_override for emitted ade-bench dataset-ref specs.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=REPO_ROOT / "examples" / "specs" / "codex",
        help="Output root for generated specs.",
    )
    parser.add_argument("--write", action="store_true", help="Write specs instead of dry-run only.")
    parser.add_argument("--freeze", action="store_true", help="Freeze emitted specs with --allow-missing.")
    parser.add_argument(
        "--model",
        default=CODEX_MODEL,
        help=f"Codex model for emitted specs. Default: {CODEX_MODEL}.",
    )
    parser.add_argument(
        "--reasoning-effort",
        help="Optional Codex reasoning effort to emit under the agent block.",
    )
    parser.add_argument(
        "--solver-workflow",
        default=DEFAULT_SOLVER_WORKFLOW,
        help=f"Solver workflow directory for emitted specs. Default: {DEFAULT_SOLVER_WORKFLOW}.",
    )
    parser.add_argument(
        "--workspace-variant",
        choices=WORKSPACE_VARIANTS,
        default="direct-structured",
        help="DAB workspace variant for emitted harbor_dab specs.",
    )
    parser.add_argument(
        "--hints",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Emit DAB specs with benchmark.hints enabled.",
    )
    args = parser.parse_args()

    emitted: list[Path] = []
    if args.benchmark == "dab":
        if args.dab_data_root is None:
            parser.error("--dab-data-root is required for --benchmark dab")
        rows = plan_dab_specs(data_root=args.dab_data_root)
        _print_dab_dry_run(rows)
        if args.write:
            for row in rows:
                emitted.append(
                    emit_dab_spec(
                        row,
                        out_dir=args.out_root / "dab",
                        model=args.model,
                        reasoning_effort=args.reasoning_effort,
                        solver_workflow=args.solver_workflow,
                        workspace_variant=args.workspace_variant,
                        hints=args.hints,
                    )
                )
    else:
        if args.ade_dataset_ref is not None and args.ade_bench_root is not None:
            parser.error(
                "pass exactly one of --ade-dataset-ref (canonical Harbor "
                "dataset ref) or --ade-bench-root (dev/fixture local root)"
            )
        if args.ade_dataset_ref is not None:
            dataset_rows = plan_ade_bench_dataset_specs(
                dataset_ref=args.ade_dataset_ref,
                task_slugs=list(args.ade_task_slug),
            )
            print(
                f"ade-bench Codex dry-run: N=1, tasks={len(dataset_rows)}, "
                f"dataset_ref={args.ade_dataset_ref}"
            )
            for row in dataset_rows:
                print(
                    f"- task={row.task_slug} trials={row.trials} "
                    f"dataset_ref={row.dataset_ref}"
                )
            if args.write:
                for row in dataset_rows:
                    emitted.append(
                        emit_ade_bench_dataset_spec(
                            row,
                            out_dir=args.out_root / "ade-bench",
                            model=args.model,
                            reasoning_effort=args.reasoning_effort,
                            solver_workflow=args.solver_workflow,
                            docker_image_override=args.ade_docker_image_override,
                        )
                    )
        else:
            if args.ade_bench_root is None:
                parser.error(
                    "pass either --ade-dataset-ref (canonical Harbor dataset "
                    "ref) or --ade-bench-root (dev/fixture local root) for "
                    "--benchmark ade-bench"
                )
            rows = plan_ade_bench_specs(ade_bench_root=args.ade_bench_root)
            _print_ade_bench_dry_run(rows, ade_bench_root=args.ade_bench_root)
            if args.write:
                for row in rows:
                    emitted.append(
                        emit_ade_bench_spec(
                            row,
                            out_dir=args.out_root / "ade-bench",
                            model=args.model,
                            reasoning_effort=args.reasoning_effort,
                            solver_workflow=args.solver_workflow,
                        )
                    )

    for spec_path in emitted:
        print(f"wrote {_display_path(spec_path)}")
        if args.freeze:
            _freeze(spec_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
