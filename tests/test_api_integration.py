"""
Integration tests: real HTTP calls to a running Codehood server, not a
`MockTransport`. `tests/test_api_generated.py` proves the generated client
matches the *committed* spec; this file proves it still matches *reality*.

Skipped by default -- run with `task test-integration`, or
`pytest --run-integration -m integration`. Targets `CODEHOOD_SERVER`
(default `http://localhost:4321`), and skips at runtime if nothing answers
there rather than failing with a wall of connection errors.

See `dev/specs/to-do/api.md`, "Proving it works".
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from codehood.api import generated
from codehood.api.generate import Generator, format_source

pytestmark = pytest.mark.integration

SERVER_URL = os.environ.get("CODEHOOD_SERVER", "http://localhost:4321")

_ROOT = Path(__file__).parent.parent
COMMITTED_SPEC_PATH = _ROOT / "resources" / "openapi" / "codehood.json"
GENERATED_CLIENT_PATH = _ROOT / "codehood" / "api" / "generated.py"


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    live_client = httpx.Client(base_url=SERVER_URL, timeout=5.0)
    try:
        live_client.get("/openapi.json")
    except httpx.TransportError as exc:
        pytest.skip(f"no Codehood server reachable at {SERVER_URL} ({exc})")
    return live_client


def test_health_matches_a_generated_shape(client: httpx.Client) -> None:
    """
    The real response parses into one of the two shapes `generated.py`
    knows about. Proof the generated types haven't drifted from what the
    server actually sends -- not a claim about the server's health, which
    might legitimately be down.
    """
    try:
        result = generated.health(client=client)
    except generated.HealthError as exc:
        assert exc.status == 503
        assert exc.database == "unreachable"
    else:
        assert result.status == "ok"
        assert result.database == "ok"


def test_login_with_bad_credentials_returns_typed_error(
    client: httpx.Client,
) -> None:
    """
    Needs no real account: a nonexistent email deterministically exercises
    the error path, and only a wire-format match with the real server would
    let this parse into `InvalidCredentials` at all.
    """
    with pytest.raises(generated.InvalidCredentials) as excinfo:
        generated.login(
            body=generated.LoginRequest(
                login="does-not-exist@example.invalid", password="wrong"
            ),
            client=client,
        )
    assert excinfo.value.status == 401
    assert excinfo.value.code == "not-allowed"
    assert excinfo.value.message


def test_live_spec_matches_committed_snapshot(client: httpx.Client) -> None:
    """
    `resources/openapi/codehood.json` is what the real-spec regression
    test in `test_api_generate.py` runs against offline. If this fails, the
    server changed and nobody refreshed the snapshot.
    """
    response = client.get("/openapi.json")
    response.raise_for_status()
    live_spec = response.json()
    committed_spec = json.loads(COMMITTED_SPEC_PATH.read_text())
    assert live_spec == committed_spec, (
        f"{COMMITTED_SPEC_PATH.relative_to(_ROOT)} is stale -- refresh it from "
        f"{SERVER_URL}/openapi.json"
    )


def test_generated_client_matches_what_codegen_would_produce_now(
    client: httpx.Client,
) -> None:
    """
    Resolves the spec's open question about a CI drift check between
    `generated.py` and the live spec: if this fails, someone changed an
    `ENDPOINTS` operation server-side without regenerating the client.
    """
    response = client.get("/openapi.json")
    response.raise_for_status()
    fresh_source = format_source(Generator(response.json()).generate())
    committed_source = GENERATED_CLIENT_PATH.read_text()
    assert fresh_source == committed_source, (
        f"{GENERATED_CLIENT_PATH.relative_to(_ROOT)} is stale -- run "
        f"`uv run python -m codehood.api.generate` against {SERVER_URL} and commit the result"
    )
