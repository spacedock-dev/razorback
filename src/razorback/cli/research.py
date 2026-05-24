# ABOUTME: `rk research new <slug> --from <ref>` — scaffolds a per-benchmark research repo.
# ABOUTME: Reads docs/templates/research-project/ + docs/templates/benchmark-defaults.toml.

from __future__ import annotations

import shutil
import string
import sys
import tomllib
from pathlib import Path

import typer


research_app = typer.Typer(
    help="Scaffold a per-benchmark research repo.",
    no_args_is_help=True,
)


_TEMPLATES_ROOT = Path(__file__).resolve().parents[3] / "docs" / "templates"
_PROJECT_TEMPLATE = _TEMPLATES_ROOT / "research-project"
_DEFAULTS_TOML = _TEMPLATES_ROOT / "benchmark-defaults.toml"


_FALLBACK_DEFAULTS = {
    "max_turns": 20,
    "max_budget_usd": 5.0,
    "reasoning_effort": "default",
    "paper_baseline_name": "paper",
    "paper_baseline_value": 0.0,
}
_TODO_MARKER = (
    "# TODO: tune for this benchmark (max_turns / max_budget_usd / "
    "reasoning_effort / paper_baseline). See "
    "docs/templates/benchmark-defaults.toml for the per-benchmark "
    "default table — add an entry there once you have ground truth."
)


def _parse_ref(ref: str) -> tuple[str, str]:
    """Return (org, short_name). Tolerates trailing @<rev>; ignores it for
    the defaults lookup."""
    if "/" not in ref:
        raise typer.BadParameter(
            f"--from must be '<org>/<name>[@<ref>]'; got {ref!r}"
        )
    base = ref.split("@", 1)[0]
    org, short = base.split("/", 1)
    return org, short


def _load_defaults(org: str, short: str) -> tuple[dict, bool]:
    """Returns (defaults_dict, found_in_table). When not found, defaults
    are the fallback set + the caller emits a TODO marker."""
    if not _DEFAULTS_TOML.is_file():
        return _FALLBACK_DEFAULTS, False
    with _DEFAULTS_TOML.open("rb") as fh:
        table = tomllib.load(fh)
    entry = table.get(org, {}).get(short)
    if entry is None:
        return _FALLBACK_DEFAULTS, False
    return entry, True


def _iter_template_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def _render(text: str, mapping: dict[str, str]) -> str:
    return string.Template(text).safe_substitute(mapping)


def _plan(root: Path, target: Path) -> list[Path]:
    rels: list[Path] = []
    for src in _iter_template_files(root):
        rels.append(target / src.relative_to(root))
    return rels


@research_app.command("new")
def new_command(
    slug: str = typer.Argument(..., help="Repo slug, e.g. 'dabstep'."),
    dataset_ref: str = typer.Option(
        ...,
        "--from",
        help="Harbor dataset reference, e.g. 'adyen/dabstep@latest'.",
    ),
    solver_runtime: str = typer.Option(
        "claude",
        "--solver-runtime",
        help="Inner-agent runtime: claude|codex|pi (default: claude).",
    ),
    target_model: str = typer.Option(
        "claude-opus-4-5",
        "--target-model",
        help="Inner-agent model alias (default: claude-opus-4-5).",
    ),
    into: Path | None = typer.Option(
        None,
        "--into",
        help="Target directory (default: ~/<slug>-research/).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the planned scaffold tree, do not write.",
    ),
) -> None:
    """Scaffold a per-benchmark research repo.

    Layout, template contents, and the benchmark-defaults table are
    documented at `docs/superpowers/specs/2026-05-23-generic-harbor-benchmark-surface.md`
    §2.3.
    """
    org, short = _parse_ref(dataset_ref)
    defaults, found = _load_defaults(org, short)

    target = into if into is not None else Path.home() / f"{slug}-research"
    target = target.expanduser()

    mapping = {
        "slug": slug,
        "dataset_ref": dataset_ref,
        "solver_runtime": solver_runtime,
        "target_model": target_model,
        "max_turns": str(defaults.get("max_turns", _FALLBACK_DEFAULTS["max_turns"])),
        "max_budget_usd": str(
            defaults.get("max_budget_usd", _FALLBACK_DEFAULTS["max_budget_usd"])
        ),
        "reasoning_effort": str(
            defaults.get("reasoning_effort", _FALLBACK_DEFAULTS["reasoning_effort"])
        ),
        "experiment_max_budget_usd": str(
            defaults.get("max_budget_usd", _FALLBACK_DEFAULTS["max_budget_usd"]) * 100
        ),
        "paper_baseline_name": str(
            defaults.get("paper_baseline_name", _FALLBACK_DEFAULTS["paper_baseline_name"])
        ),
        "paper_baseline_value": str(
            defaults.get("paper_baseline_value", _FALLBACK_DEFAULTS["paper_baseline_value"])
        ),
        "todo_marker": "" if found else _TODO_MARKER,
    }

    if dry_run:
        typer.echo(f"# would scaffold {target}/")
        for rel in _plan(_PROJECT_TEMPLATE, target):
            typer.echo(f"  {rel.relative_to(target)}")
        return

    if target.exists() and any(target.iterdir()):
        typer.echo(
            f"refusing to scaffold into non-empty directory: {target}",
            err=True,
        )
        raise typer.Exit(2)

    target.mkdir(parents=True, exist_ok=True)
    for src in _iter_template_files(_PROJECT_TEMPLATE):
        dst = target / src.relative_to(_PROJECT_TEMPLATE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if _is_binary(src):
            shutil.copy(src, dst)
        else:
            dst.write_text(_render(src.read_text(), mapping))

    # Preserve executable bit on shell scripts (Template render uses
    # write_text which doesn't carry mode bits from the source).
    for path in target.rglob("*.sh"):
        path.chmod(path.stat().st_mode | 0o111)

    if not found:
        typer.echo(
            f"note: no benchmark-defaults entry for {org}/{short} — "
            f"scaffolded conservative defaults with a TODO marker. "
            f"Add an entry to docs/templates/benchmark-defaults.toml "
            f"once you have ground truth."
        )
    typer.echo(f"scaffolded {target}/")


def _is_binary(path: Path) -> bool:
    """Cheap heuristic: try to decode as utf-8."""
    try:
        path.read_text(encoding="utf-8")
        return False
    except UnicodeDecodeError:
        return True
