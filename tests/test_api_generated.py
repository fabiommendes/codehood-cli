"""
Round-trips the committed `codehood_cli.api.generated` against a fake
transport, so a regeneration that silently breaks a function's contract
fails here rather than at `codehood push` time. See `dev/specs/to-review/api.md`,
"Proving it works".
"""

from __future__ import annotations

import httpx
import pytest

from codehood.api import generated
from codehood.api.base import save_token


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/health":
        return httpx.Response(200, json={"status": "ok", "database": "ok"})
    if request.url.path == "/api/auth/login":
        import json

        data = json.loads(request.read())
        if data["password"] == "wrong":
            return httpx.Response(401, json={"error": "bad credentials"})
        return httpx.Response(200, json={"token": "abc123"})
    raise AssertionError(f"unexpected path: {request.url.path}")


@pytest.fixture
def client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(_handler), base_url="http://test")


def test_health_ok(client):
    result = generated.health(client=client)
    assert result == generated.HealthResponse(status="ok", database="ok")


def test_login_ok(client):
    result = generated.login(
        body=generated.LoginRequest(login="a@b.com", password="right"), client=client
    )
    assert result.token == "abc123"


def test_health_error_is_typed_and_catchable_by_base(client):
    """
    `health` is the only operation whose spec documents an error response,
    so it is what proves the typed-exception path end to end.
    """

    def _unhealthy(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"status": "error", "database": "unreachable"})

    unhealthy_client = httpx.Client(
        transport=httpx.MockTransport(_unhealthy), base_url="http://test"
    )
    with pytest.raises(generated.CodehoodAPIError) as excinfo:
        generated.health(client=unhealthy_client)
    assert isinstance(excinfo.value, generated.HealthError)
    assert excinfo.value.status == 503


def test_health_error_is_typed_with_no_shadowed_status():
    def _unhealthy(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"status": "error", "database": "unreachable"})

    unhealthy_client = httpx.Client(
        transport=httpx.MockTransport(_unhealthy), base_url="http://test"
    )

    with pytest.raises(generated.HealthError) as excinfo:
        generated.health(client=unhealthy_client)
    error = excinfo.value
    # `.status` is always the HTTP status code, even though the payload
    # itself also has a field named `status` -- see `_RESERVED_EXCEPTION_ATTRS`.
    assert error.status == 503
    assert error.payload.status == "error"
    assert error.database == "unreachable"


#
# Query parameters
#
@pytest.fixture
def logged_in() -> None:
    save_token("http://localhost:4321", "test-token")


def test_list_resource_with_no_filters_sends_no_query_string(logged_in):
    """
    Regression: `httpx` renders a `None` parameter as `?types=`, and the
    server reads that as a present-but-empty filter and answers 400. A
    call that filters by nothing must ask for nothing.
    """
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.query.decode())
        return httpx.Response(200, json=[])

    client = httpx.Client(
        base_url="http://localhost:4321", transport=httpx.MockTransport(handler)
    )
    generated.list_resource(discipline="cs101", course="ada_2026-1", client=client)
    assert seen == [""]


def test_list_resource_sends_the_filters_it_was_given(logged_in):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.query.decode())
        return httpx.Response(200, json=[])

    client = httpx.Client(
        base_url="http://localhost:4321", transport=httpx.MockTransport(handler)
    )
    generated.list_resource(
        discipline="cs101", course="ada_2026-1", types=["MD"], client=client
    )
    assert seen == ["types=MD"]


#
# The `Resource.data` union
#
# `push/run.py` constructs these by name, so a regeneration that renamed
# or reshaped one would otherwise fail at push time against a real server
# rather than here.
def test_resource_data_request_members_keep_their_names_and_fields():
    assert set(generated.DataMd.model_fields) == {"type", "content"}
    assert set(generated.DataCode.model_fields) == {"type", "content", "language"}
    assert set(generated.ResourceCreateDataFile.model_fields) == {
        "type",
        "filename",
        "buffer",
    }


def test_upsert_resource_request_carries_slug_ref_and_the_union():
    # `upsertResource`'s inline body is structurally the `ResourceCreate`
    # component, so it is that class rather than an `UpsertResourceRequest`
    # twin of it.
    fields = generated.ResourceCreate.model_fields
    assert {"slug", "title", "ref", "description", "data"} == set(fields)
