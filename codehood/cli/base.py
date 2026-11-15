from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .. import repo

app = typer.Typer(
    name="codehood",
    help="Codehood CLI",
)


@app.callback()
def configure(
    ctx: typer.Context,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            envvar="CODEHOOD_CONFIG",
            help=(
                "Read this file instead of codehood.toml in the repository root. "
                "Must come before the command."
            ),
        ),
    ] = None,
) -> None:
    """
    Codehood CLI

    Raises:
        typer.Exit: With code 1 when `config` does not exist and the command
            is not `init`, which creates it.
    """
    repo.set_config_override(config)
    if config is not None and ctx.invoked_subcommand != "init" and not config.is_file():
        typer.echo(f"error: could not find Codehood config at {config}", err=True)
        raise typer.Exit(code=1)
