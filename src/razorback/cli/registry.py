# ABOUTME: `rk registry list|resolve|add|remove` (§3.2).
# ABOUTME: Named-reference registry; `@name` -> path lookup.

import typer

from razorback.registry import store

registry_app = typer.Typer(help="Named-reference registry.", no_args_is_help=True)


@registry_app.command("list")
def list_cmd() -> None:
    """List every registered (kind, name) -> path entry."""
    for entry in store.list_entries():
        typer.echo(f"{entry['kind']}\t@{entry['name']}\t{entry['path']}")


@registry_app.command("resolve")
def resolve_cmd(
    kind: str = typer.Argument(...),
    name: str = typer.Argument(...),
) -> None:
    """Print the path bound to `@name` for the given kind."""
    target = store.resolve(kind, name)
    if target is None:
        typer.echo(f"unknown {kind} {name}", err=True)
        raise typer.Exit(1)
    typer.echo(target)


@registry_app.command("add")
def add_cmd(
    kind: str = typer.Argument(...),
    name: str = typer.Argument(...),
    target: str = typer.Argument(...),
) -> None:
    """Bind `@name` -> path for the given kind."""
    store.add(kind, name, target)
    typer.echo("OK")


@registry_app.command("remove")
def remove_cmd(
    kind: str = typer.Argument(...),
    name: str = typer.Argument(...),
) -> None:
    """Remove `@name` from the registry."""
    store.remove(kind, name)
    typer.echo("OK")
