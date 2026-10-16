from __future__ import annotations

import httpx
import typer

from ..api.base import NotLoggedInError
from .api import api
from .attendance import attendance
from .auth import login, logout
from .base import app as _app
from .chill import chill
from .grades import grades
from .init import init
from .push import push
from .show import show

__all__ = [
    #: Main entry point
    "main",
    #: Subcommands
    "api",
    "attendance",
    "chill",
    "grades",
    "init",
    "login",
    "logout",
    "push",
    "show",
]


def main() -> None:
    """
    Run the Codehood CLI, turning failures every command shares into one error line.

    Raises:
        SystemExit: With code 1 when no login is stored for the server or the
            server cannot be reached.
    """
    try:
        _app()
    except NotLoggedInError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise SystemExit(1) from exc
    except httpx.TransportError as exc:
        typer.echo(f"error: could not reach {server_of(exc)}: {exc}", err=True)
        raise SystemExit(1) from exc


#
# Utilities
#
def server_of(exc: httpx.TransportError) -> str:
    """
    The scheme and host `exc`'s request was sent to, or "the server" if unknown.
    """
    try:
        url = exc.request.url
    except RuntimeError:
        return "the server"
    return f"{url.scheme}://{url.netloc.decode()}"
