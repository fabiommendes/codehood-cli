"""
`codehood login` / `codehood logout`. See `dev/specs/to-review/login.md`.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import typer

from .. import repo
from ..api import generated
from ..api.base import (
    CodehoodAPIError,
    delete_token,
    get_client,
    load_login,
    load_token,
    save_token,
)
from ..models.repo import RepoConfig
from .base import app

__all__ = ["login", "logout"]


@app.command()
def login() -> None:
    """
    Exchange a login and password for a CLI API key, and store it.

    The login prompt defaults to the course's instructor in `codehood.toml`.
    There is one stored login per server, so logging in as someone else
    replaces the previous one, and says so.
    """
    config = _repo_config()
    server_url = config.server.url
    login_name = typer.prompt("Login", default=config.course.instructor)
    password = typer.prompt("Password", hide_input=True)

    client = get_client(server_url)
    try:
        result = generated.login(
            body=generated.LoginRequest(login=login_name, password=password),
            client=client,
        )
    except CodehoodAPIError as exc:
        typer.echo(f"error: {exc.payload}", err=True)
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        typer.echo(f"error: could not reach {server_url}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    key = str(client.base_url)
    if load_token(key) is not None and load_login(key) != login_name:
        previous = load_login(key)
        was = f" (was {previous})" if previous else ""
        typer.echo(f"replacing the stored login for {server_url}{was}")
    save_token(key, result.token, login=login_name)
    typer.echo(f"logged in to {server_url} as {login_name}")


@app.command()
def logout() -> None:
    """
    Forget the locally stored CLI API key for the current repository's server.
    """
    server_url = _repo_config().server.url
    client = get_client(server_url)
    key = str(client.base_url)
    previous = load_login(key)
    if delete_token(key):
        was = f" (forgot the login of {previous})" if previous else ""
        typer.echo(f"logged out of {server_url}{was}")
    else:
        typer.echo(f"not logged in to {server_url}")
    typer.echo(
        "note: this only forgets the key locally -- the server has no way "
        "yet to revoke it remotely; use /profile for that."
    )


def _repo_config() -> RepoConfig:
    """
    The current repository's `codehood.toml`, or a clean exit if there isn't
    one.

    Neither command takes a `--server` flag -- see the spec's "Login and
    logout take no flags".
    """
    config = repo.read_config(Path(repo.CONFIG_FILE))
    if config is None:
        typer.echo("error: not a codehood repository (no codehood.toml here)", err=True)
        raise typer.Exit(code=1)
    return config
