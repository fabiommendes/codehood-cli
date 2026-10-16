"""
Shared plumbing for `codehood_cli.api.generated`: the HTTP client every
generated function calls through, the exception hierarchy it raises, and the
credentials store `codehood login`/`codehood logout` and the auth-gated
generated functions all read and write.

None of this is itself generated -- see `dev/specs/to-review/api.md`, "A
shared client, threaded through as an optional parameter" and "One exception
class per schema, not per (operation, status)", and `dev/specs/to-review/
login.md`, "The bearer token is attached inside generated code, gated per
operation" -- so this is the one file in `api/` codegen never touches.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path

import httpx
import tomlkit

from .. import repo
from ..models.base import Model

DEFAULT_BASE_URL = "http://localhost:4321"

#: Sent on every request, including the ones with no body.
#:
#: Astro's cross-site guard refuses any mutating request whose
#: `Content-Type` looks like an HTML form's -- and it counts a *missing*
#: one, which is what a bodyless `DELETE` would otherwise send, giving
#: `403 Cross-site DELETE form submissions are forbidden`. Saying what we
#: actually speak is enough to clear it, and is true of every other
#: request here anyway. See `ROADBLOCKS.md`.
DEFAULT_HEADERS = {"Content-Type": "application/json"}

#: Global, not per-repo -- see `dev/specs/to-review/login.md`, "Credentials
#: are global, not per-repo".
CREDENTIALS_PATH = Path.home() / ".codehood" / "credentials.toml"


def get_client(base_url: str | None = None) -> httpx.Client:
    """
    Build the client generated functions call through.

    `base_url` defaults to `[server].url` in `codehood.toml` in the current
    directory, falling back to `DEFAULT_BASE_URL` when there is no
    repository here -- generated functions stay usable from a plain
    checkout, a test, or a REPL with nothing scaffolded.
    """
    return httpx.Client(
        base_url=base_url or _default_base_url(), headers=DEFAULT_HEADERS
    )


def _default_base_url() -> str:
    config = repo.read_config(Path(repo.CONFIG_FILE))
    return config.server.url if config is not None else DEFAULT_BASE_URL


#: What `httpx` accepts as one query parameter's value: a scalar, or a
#: sequence of them for a repeated parameter such as `slugs`.
type QueryValue = (
    str | int | float | bool | None | Sequence[str | int | float | bool | None]
)


def query_params(params: Mapping[str, QueryValue]) -> dict[str, QueryValue]:
    """
    Drop the query parameters a caller left unset.

    `httpx` renders a `None` value as an empty string, so passing every
    optional parameter through would send `?types=&slugs=` on a call that
    named neither -- which the server reads as two present-but-empty
    filters and rejects. An omitted parameter has to be omitted.
    """
    return {name: value for name, value in params.items() if value is not None}


class CodehoodAPIError(Exception):
    """
    Base class for every exception `codehood_cli.api.generated` raises.

    Each subclass corresponds to one OpenAPI component schema used in a
    documented error response. `status` is the HTTP status code the server
    actually sent for this call; `payload` is that response's body, parsed
    into the subclass's nested `Payload` model. Subclasses add one
    `@property` per payload field so `err.field` works without the
    `.payload` indirection.
    """

    def __init__(self, status: int, payload: Model) -> None:
        super().__init__(f"{type(self).__name__} ({status}): {payload}")
        self.status = status
        self.payload = payload


class NotLoggedInError(Exception):
    """
    Raised by a generated function for an operation whose effective
    `security` is non-empty, when `CREDENTIALS_PATH` has no token for its
    client's `base_url`. Raised before the request is sent -- see
    `dev/specs/to-review/login.md`, "The bearer token is attached inside
    generated code, gated per operation".
    """

    def __init__(self, base_url: str) -> None:
        super().__init__(f"not logged in to {base_url} -- run `codehood login`")
        self.base_url = base_url


def stored_servers() -> list[str]:
    """
    Every server URL with a stored token, in the order `codehood login`
    added them. Used by `cli/init.py`'s `_default_server` to default
    `--server` when there's exactly one -- see `dev/specs/to-review/
    login.md`.
    """
    if not CREDENTIALS_PATH.exists():
        return []
    servers = tomllib.loads(CREDENTIALS_PATH.read_text(encoding="utf-8")).get(
        "servers", {}
    )
    return list(servers)


def load_token(base_url: str) -> str | None:
    """
    The stored CLI API key for `base_url`, or `None` if `codehood login`
    was never run for it (or `codehood logout` cleared it).
    """
    if not CREDENTIALS_PATH.exists():
        return None
    servers = tomllib.loads(CREDENTIALS_PATH.read_text(encoding="utf-8")).get(
        "servers", {}
    )
    return servers.get(base_url)


def load_login(base_url: str) -> str | None:
    """
    The login name `base_url`'s stored token was issued to, or `None` when
    unknown (no token, or one stored before logins were recorded).
    """
    if not CREDENTIALS_PATH.exists():
        return None
    logins = tomllib.loads(CREDENTIALS_PATH.read_text(encoding="utf-8")).get(
        "logins", {}
    )
    return logins.get(base_url)


def save_token(base_url: str, token: str, login: str | None = None) -> None:
    """
    Store `token` for `base_url`, overwriting whatever was there.

    There is one credential per server: the CLI acts as one person on each.
    `login` goes in a separate `[logins]` table, so `[servers]` keeps plain
    token strings that older CLI versions read. A token saved without a
    `login` forgets the previous one, which belonged to the old token.

    `CREDENTIALS_PATH` is `chmod 600` after every write -- it holds a raw
    bearer token, unlike `codehood.toml`, which is committed and never
    holds a secret.
    """
    doc = read_credentials_doc()
    servers = doc.setdefault("servers", tomlkit.table())
    servers[base_url] = token
    logins = doc.setdefault("logins", tomlkit.table())
    if login is None:
        logins.pop(base_url, None)
    else:
        logins[base_url] = login
    write_credentials_doc(doc)


def delete_token(base_url: str) -> bool:
    """
    Forget the stored token for `base_url`, if any.

    Returns whether there was one to forget, so `codehood logout` can say
    which happened.
    """
    if not CREDENTIALS_PATH.exists():
        return False
    doc = read_credentials_doc()
    servers = doc.get("servers", {})
    if base_url not in servers:
        return False
    del servers[base_url]
    doc.get("logins", {}).pop(base_url, None)
    write_credentials_doc(doc)
    return True


def auth_headers(client: httpx.Client) -> dict[str, str]:
    """
    The `Authorization` header a generated function attaches for an
    operation that requires auth.

    Raises `NotLoggedInError` rather than returning an empty mapping, so a
    call with no stored token fails locally instead of reaching the server
    and getting an unauthenticated 401 back.
    """
    base_url = str(client.base_url)
    token = load_token(base_url)
    if token is None:
        raise NotLoggedInError(base_url)
    return {"Authorization": f"Bearer {token}"}


def read_credentials_doc() -> tomlkit.TOMLDocument:
    if not CREDENTIALS_PATH.exists():
        return tomlkit.document()
    return tomlkit.parse(CREDENTIALS_PATH.read_text(encoding="utf-8"))


def write_credentials_doc(doc: tomlkit.TOMLDocument) -> None:
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_PATH.write_text(tomlkit.dumps(doc), encoding="utf-8")
    CREDENTIALS_PATH.chmod(0o600)
