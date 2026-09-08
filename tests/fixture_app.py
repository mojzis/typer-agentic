"""The fixture CLI from the spec (§10). Importable, and runnable as a module."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from typer_agentic import AgentErrorsConfig, agent_errors

app = typer.Typer(help="Demo tool for tests.")


@app.command()
def sync(
    path: Annotated[Path, typer.Argument(help="Where to sync.")],
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose output.")
    ] = False,
    count: Annotated[int, typer.Option(help="How many.")] = 1,
    env: Annotated[
        Literal["dev", "prod"], typer.Option(help="Target environment.")
    ] = "dev",
    secret: Annotated[str, typer.Option(hidden=True)] = "x",
) -> None:
    """Sync a path."""
    typer.echo(f"synced {path} {verbose} {count} {env} {secret}")


@app.command(no_args_is_help=True)
def push(
    target: str,
    tags: Annotated[list[str], typer.Option(help="Tags.")] = [],
    retries: Annotated[int, typer.Option(min=0, max=5, help="Retry budget.")] = 0,
) -> None:
    """Push to a target."""
    typer.echo(f"pushed {target} {tags} {retries}")


@app.command()
def fail(code: int = 3) -> None:
    """Exit with a code, or abort."""
    if code < 0:
        raise typer.Abort()
    raise typer.Exit(code)


@app.command(name="returns-int")
def returns_int() -> int:
    """Return an int (stock Typer still exits 0)."""
    return 5


@app.command()
def interrupt() -> None:
    """Simulate Ctrl-C."""
    raise KeyboardInterrupt


@app.command()
def boom() -> None:
    """Raise a runtime error."""
    raise RuntimeError("boom")


def build_main(config: AgentErrorsConfig | None = None):
    return agent_errors(app, config=config)


if __name__ == "__main__":
    build_main()()
