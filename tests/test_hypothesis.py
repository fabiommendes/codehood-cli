"""
Tests for `codehood.hypothesis`. See
`dev/specs/to-review/api-hypothesis-strategies.md`, "Proving it works".
"""

from __future__ import annotations

import json
import re
import typing
from pathlib import Path

import pytest
from hypothesis import find as find_any
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import TypeAdapter

from codehood.api import generated
from codehood.api.generate import ENDPOINTS, UnsupportedSchemaError, snake_case
from codehood.api.openapi import load_openapi
from codehood.hypothesis import (
    JSON,
    json_schema_documents,
    openapi_endpoint_documents,
    openapi_response_documents,
)

REAL_SPEC_PATH = (
    Path(__file__).parent.parent / "resources" / "openapi" / "codehood.json"
)
REAL_SPEC = load_openapi(json.loads(REAL_SPEC_PATH.read_text()))

#: `operationId`s with a `requestBody` -- the only ones
#: `openapi_endpoint_documents` accepts.
_ENDPOINTS_WITH_BODY = sorted(
    operation_id
    for operation_id in ENDPOINTS
    if REAL_SPEC.operations()[operation_id].operation.request_body is not None
)


def _assert_keys_survive(document: JSON, dumped: JSON, path: str = "") -> None:
    """
    Every key the spec put in `document` is still there after the model
    round trip.

    `validate_python` alone proves almost nothing about field coverage:
    pydantic ignores keys it has no field for, so a model that silently
    dropped `_count` validates every document just as happily as the
    correct one. Dumping back and comparing keys is what actually pins the
    mapping down -- it is the check that would have caught the `_count`
    data loss on its own.
    """
    if isinstance(document, dict):
        assert isinstance(dumped, dict), path
        dropped = set(document) - set(dumped)
        assert not dropped, f"{path or '<root>'}: model dropped {sorted(dropped)}"
        for key, value in document.items():
            _assert_keys_survive(value, dumped[key], f"{path}.{key}")
    elif isinstance(document, list):
        assert isinstance(dumped, list) and len(dumped) == len(document), path
        for index, (value, dumped_value) in enumerate(zip(document, dumped)):
            _assert_keys_survive(value, dumped_value, f"{path}[{index}]")


def _round_trip(model_type: object, document: JSON) -> JSON:
    """
    Validate `document` as `model_type`, then dump it back on the wire.
    """
    adapter = TypeAdapter(model_type)
    return adapter.dump_python(adapter.validate_python(document), by_alias=True)


#
# 1. The invariant, against the real snapshot.
#
@pytest.mark.parametrize("operation_id", _ENDPOINTS_WITH_BODY)
@settings(max_examples=5)
@given(data=st.data())
def test_every_request_body_the_spec_permits_validates(operation_id, data):
    """
    For an operation with a request body, a document the spec permits must
    validate against the generated function's `body` annotation, and
    survive the round trip back out with every key intact.

    One case per operation: drawing a document for every operation in a
    single case outgrows what Hypothesis lets one input hold.
    """
    func = getattr(generated, snake_case(operation_id))
    body_type = typing.get_type_hints(func)["body"]
    document = data.draw(
        openapi_endpoint_documents(operation_id, REAL_SPEC), label=operation_id
    )
    _assert_keys_survive(document, _round_trip(body_type, document))


@pytest.mark.parametrize("operation_id", sorted(ENDPOINTS))
@settings(max_examples=5)
@given(data=st.data())
def test_every_response_body_the_spec_permits_validates(operation_id, data):
    """
    Same as above, but for the operation's 200 response against the
    generated function's return annotation.
    """
    func = getattr(generated, snake_case(operation_id))
    return_type = typing.get_type_hints(func)["return"]
    if return_type is type(None):
        return
    document = data.draw(
        openapi_response_documents(operation_id, REAL_SPEC), label=operation_id
    )
    _assert_keys_survive(document, _round_trip(return_type, document))


#
# 2. JSON round trip.
#
@settings(max_examples=5)
@given(data=st.data())
def test_generated_documents_survive_a_json_round_trip(data):
    """
    Guards against `datetime`, `Decimal`, NaN, or bytes leaking out of the
    strategy -- anything that doesn't come back unchanged from
    `json.loads(json.dumps(doc))` isn't a JSON document at all.
    """
    for operation_id in _ENDPOINTS_WITH_BODY:
        document = data.draw(
            openapi_endpoint_documents(operation_id, REAL_SPEC), label=operation_id
        )
        assert json.loads(json.dumps(document)) == document


#
# 3. Per-keyword unit tests, each on a small inline schema.
#
@given(value=json_schema_documents({"type": "string", "enum": ["a", "b", "c"]}))
def test_enum_draws_from_the_enum(value):
    assert value in {"a", "b", "c"}


def test_nullable_produces_both_none_and_non_none():
    """
    Checked across the whole Hypothesis run rather than within one example:
    a manual loop drawing many values *inside* a single example lets the
    shrinker collapse every draw to the same trivial value (`None`), which
    is a valid single draw but not what "across a run" means.
    """
    seen_none = False
    seen_value = False

    @given(value=json_schema_documents({"type": "string", "nullable": True}))
    @settings(max_examples=200)
    def check(value):
        nonlocal seen_none, seen_value
        if value is None:
            seen_none = True
        else:
            seen_value = True

    check()
    assert seen_none
    assert seen_value


@given(
    value=json_schema_documents(
        {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{1,30}$"}
    )
)
def test_pattern_output_fullmatches_the_regex(value):
    assert re.fullmatch("^[a-z0-9][a-z0-9-]{1,30}$", value)


@given(value=json_schema_documents({"type": "string", "minLength": 5}))
def test_min_length_is_respected(value):
    assert len(value) >= 5


@given(value=json_schema_documents({"type": "integer", "minimum": 10}))
def test_minimum_bound_holds(value):
    assert value >= 10


@given(
    value=json_schema_documents(
        {"type": "integer", "minimum": 10, "exclusiveMinimum": True}
    )
)
def test_exclusive_minimum_bound_holds(value):
    assert value > 10


_REQUIRED_OPTIONAL_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "nickname": {"type": "string"},
    },
    "required": ["id"],
}


@given(value=json_schema_documents(_REQUIRED_OPTIONAL_SCHEMA))
def test_required_keys_always_present_and_no_extra_keys(value):
    assert "id" in value
    assert set(value) <= {"id", "nickname"}


def test_ref_resolves():
    spec = load_openapi(
        {
            "openapi": "3.0.0",
            "info": {"title": "Fixture", "version": "0.0.1"},
            "components": {
                "schemas": {
                    "Widget": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    }
                }
            },
            "paths": {},
        }
    )
    strategy = json_schema_documents({"$ref": "#/components/schemas/Widget"}, spec)

    @given(value=strategy)
    @settings(max_examples=10)
    def check(value):
        assert set(value) == {"name"}
        assert isinstance(value["name"], str)

    check()


def test_ref_without_spec_raises_value_error():
    with pytest.raises(ValueError):
        json_schema_documents({"$ref": "#/components/schemas/Widget"})


def test_anyof_yields_values_from_more_than_one_branch():
    seen_email = False
    seen_username = False

    @given(
        value=json_schema_documents(
            {
                "anyOf": [
                    {"type": "string", "format": "email"},
                    {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{1,30}$"},
                ]
            }
        )
    )
    @settings(max_examples=200)
    def check(value):
        nonlocal seen_email, seen_username
        if re.fullmatch("^[a-z0-9][a-z0-9-]{1,30}$", value):
            seen_username = True
        if "@" in value:
            seen_email = True

    check()
    assert seen_email
    assert seen_username


#
# 4. Unsupported keywords raise.
#
def test_allof_raises():
    with pytest.raises(UnsupportedSchemaError):
        json_schema_documents(
            {
                "allOf": [
                    {"type": "object", "properties": {"a": {"type": "string"}}},
                    {"type": "object", "properties": {"b": {"type": "string"}}},
                ]
            }
        )


def test_oneof_draws_from_every_member():
    strategy = json_schema_documents(
        {
            "oneOf": [
                {"type": "string"},
                {"type": "integer"},
            ]
        }
    )
    drawn = {
        type(find_any(strategy, lambda value: isinstance(value, str))),
        type(find_any(strategy, lambda value: isinstance(value, int))),
    }
    assert drawn == {str, int}


#
# `openapi_endpoint_documents` / `openapi_response_documents` error paths.
#
def test_endpoint_with_no_request_body_raises_value_error():
    """
    `getHealth` (`health` here) documents no `requestBody` -- returning
    `st.none()` would let a test loop silently cover nothing, which is the
    failure mode this whole module exists to prevent.
    """
    with pytest.raises(ValueError):
        openapi_endpoint_documents("health", REAL_SPEC)


def test_accepts_raw_dict_spec_too():
    raw_spec = json.loads(REAL_SPEC_PATH.read_text())
    strategy = openapi_endpoint_documents("login", raw_spec)

    @given(value=strategy)
    @settings(max_examples=5)
    def check(value):
        assert "login" in value and "password" in value

    check()
