"""
Fetch the Codehood OpenAPI document from wherever this machine keeps it.

Tries four locations, in order, and uses the first that yields a valid
document:

1. `$CODEHOOD_OPENAPI_JSON`, a URL or a file path.
2. The local dev server, `http://localhost:4321/openapi.json`.
3. The server checkout: the parent repository when this CLI lives in its
   `cli/` directory, else a sibling `../codehood-server/` or `../codehood/`.
   Reads `public/openapi.json` from it.
4. The generator in that checkout, `scripts/generate-openapi.ts`, run
   through `pnpm exec tsx`. It writes `public/openapi.json`, which is then
   read as in rule 3.

The result is written to the given path, or to
`resources/openapi/codehood-latest.json`.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from pydantic import ValidationError

from codehood.api.openapi import load_openapi

#: Repository root, the parent of the `scripts/` directory this file is in.
ROOT = Path(__file__).resolve().parent.parent

DEFAULT_OUTPUT = ROOT / "resources" / "openapi" / "codehood-latest.json"
ENV_VAR = "CODEHOOD_OPENAPI_JSON"
LOCAL_SERVER_URL = "http://localhost:4321/openapi.json"
#: The parent comes first: in the server repository this CLI lives in `cli/`.
SIBLING_REPOS = (ROOT.parent, ROOT.parent / "codehood-server", ROOT.parent / "codehood")
SPEC_IN_REPO = Path("public") / "openapi.json"
GENERATOR_IN_REPO = Path("scripts") / "generate-openapi.ts"

#: The dev server is either up or it isn't; waiting longer won't change that.
HTTP_TIMEOUT = 5.0
#: `tsx` compiles the server's whole type graph on a cold start.
GENERATOR_TIMEOUT = 180.0

app = typer.Typer()


@app.command()
def copy_openapi(
    output: Annotated[
        Path | None, typer.Argument(help="Path to write the OpenAPI spec to")
    ] = None,
) -> None:
    """Copy the Codehood OpenAPI spec from one of the known locations."""
    destination = output or DEFAULT_OUTPUT

    for source in _sources():
        found = source()
        if found is None:
            continue
        origin, document = found
        _write(document, destination, origin)
        return

    typer.secho(
        "no OpenAPI document found. Start the dev server on "
        f"{LOCAL_SERVER_URL}, check out the server next to this repo, or point "
        f"${ENV_VAR} at a copy.",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(1)


#
# SOURCES
#
# Each returns `(origin, document)` when it can produce a document and `None`
# when this machine simply doesn't have that source. A source that exists but
# is broken (unreachable host, malformed JSON) warns and returns `None`, so
# the search moves on -- except `$CODEHOOD_OPENAPI_JSON`, where the human has
# said exactly where to look and silently reading somewhere else would hide
# the mistake.
#
type Source = Callable[[], tuple[str, dict[str, Any]] | None]


def _sources() -> Iterator[Source]:
    yield _from_env
    yield _from_local_server
    yield _from_sibling_file
    yield _from_sibling_generator


def _from_env() -> tuple[str, dict[str, Any]] | None:
    location = os.environ.get(ENV_VAR)
    if not location:
        return None

    if location.startswith(("http://", "https://")):
        document = _fetch(location)
    else:
        path = Path(location).expanduser()
        if not path.is_file():
            _fail(f"${ENV_VAR} is {location!r}, which is not a file or a URL")
        document = _parse(path.read_text(), location)

    if document is None:
        _fail(f"${ENV_VAR} is set to {location!r} but no document could be read")
    return location, document or {}


def _from_local_server() -> tuple[str, dict[str, Any]] | None:
    document = _fetch(LOCAL_SERVER_URL)
    return None if document is None else (LOCAL_SERVER_URL, document)


def _from_sibling_file() -> tuple[str, dict[str, Any]] | None:
    for repo in SIBLING_REPOS:
        path = repo / SPEC_IN_REPO
        if not path.is_file():
            continue
        document = _parse(path.read_text(), str(path))
        if document is not None:
            return str(path), document
    return None


def _from_sibling_generator() -> tuple[str, dict[str, Any]] | None:
    for repo in SIBLING_REPOS:
        generator = repo / GENERATOR_IN_REPO
        if not generator.is_file():
            continue

        command = ["pnpm", "exec", "tsx", str(GENERATOR_IN_REPO)]
        typer.echo(f"running {' '.join(command)} in {repo}")
        try:
            result = subprocess.run(
                command,
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=GENERATOR_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            _warn(f"could not run the generator in {repo}: {error}")
            continue
        if result.returncode != 0:
            _warn(f"the generator in {repo} failed:\n{result.stderr.strip()}")
            continue

        # The generator writes `public/openapi.json` rather than printing the
        # document, so read what it just wrote.
        path = repo / SPEC_IN_REPO
        if not path.is_file():
            _warn(f"the generator ran but {path} still doesn't exist")
            continue
        document = _parse(path.read_text(), str(path))
        if document is not None:
            return f"{generator} -> {path}", document
    return None


#
# INTERNAL
#
def _fetch(url: str) -> dict[str, Any] | None:
    try:
        response = httpx.get(url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPError as error:
        _warn(f"could not fetch {url}: {error}")
        return None
    return _parse(response.text, url)


def _parse(text: str, origin: str) -> dict[str, Any] | None:
    """
    Parse and validate one candidate document.

    Validating here, rather than trusting whatever the source returned, is
    what stops a dev server's HTML error page or a half-written file from
    being copied over a good snapshot.
    """
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        _warn(f"{origin} is not JSON: {error}")
        return None
    try:
        load_openapi(document)
    except ValidationError as error:
        _warn(f"{origin} is not an OpenAPI document: {error.error_count()} errors")
        return None
    return document


def _write(document: dict[str, Any], destination: Path, origin: str) -> None:
    """
    Write `document` in the server's own formatting.

    Two-space indent, non-ASCII left alone, trailing newline: byte-identical
    to what `generate-openapi.ts` writes, so a refresh from any of the four
    sources produces the same file and `git diff` shows only real changes.
    """
    serialized = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    previous = destination.read_text() if destination.is_file() else None

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(serialized)

    typer.echo(f"copied {origin}")
    if previous is None:
        typer.secho(f"wrote {destination} (new)", fg=typer.colors.GREEN)
    elif previous == serialized:
        typer.echo(f"wrote {destination} (unchanged)")
    else:
        typer.secho(f"wrote {destination} (changed)", fg=typer.colors.YELLOW)


def _warn(message: str) -> None:
    typer.secho(f"skipped: {message}", fg=typer.colors.YELLOW, err=True)


def _fail(message: str) -> None:
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
