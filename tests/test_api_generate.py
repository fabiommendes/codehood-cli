"""
Tests for `codehood.api.generate`. See
`dev/specs/to-review/api-nested-schemas.md`, "Proving it works".
"""

from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

import httpx
import pytest

from codehood.api.generate import Generator, UnsupportedSchemaError

REAL_SPEC_PATH = (
    Path(__file__).parent.parent / "resources" / "openapi" / "codehood.json"
)

_module_counter = 0


def _exec_generated(source: str) -> dict[str, object]:
    """
    `exec`s generated source as if it were the real `api/generated.py`.

    A plain `exec(..., {"__name__": ..., "__package__": ...})` is enough for
    `callable(...)`/`issubclass(...)` checks (what the pre-existing tests
    did), but pydantic resolves `from __future__ import annotations`
    forward refs (e.g. `Literal[...]`, nested classes) by looking the
    module up in `sys.modules` -- a namespace dict that was never
    registered there leaves the model "not fully defined". Registering a
    real (temporary) module object under a unique name fixes that, so
    tests can actually `model_validate(...)` the generated models, not
    just import them.
    """
    global _module_counter
    _module_counter += 1
    name = f"codehood.api._generated_test_{_module_counter}"
    module = types.ModuleType(name)
    module.__package__ = "codehood.api"
    sys.modules[name] = module
    try:
        exec(compile(source, "<generated>", "exec"), module.__dict__)
    finally:
        del sys.modules[name]
    return module.__dict__


FIXTURE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Fixture", "version": "0.0.1"},
    "components": {
        "schemas": {
            "ApiError": {
                "type": "object",
                "properties": {"error": {"type": "string"}},
                "required": ["error"],
            },
            "HealthOk": {
                "type": "object",
                "properties": {"status": {"type": "string", "enum": ["ok"]}},
                "required": ["status"],
            },
            "HealthError": {
                "type": "object",
                "properties": {"status": {"type": "string", "enum": ["error"]}},
                "required": ["status"],
            },
            "CliLoginRequest": {
                "type": "object",
                "properties": {
                    "email": {"type": "string"},
                    "password": {"type": "string"},
                },
                "required": ["email", "password"],
            },
            "CliLoginResponse": {
                "type": "object",
                "properties": {"token": {"type": "string"}},
                "required": ["token"],
            },
        }
    },
    "paths": {
        "/api/health": {
            "get": {
                "operationId": "getHealth",
                "summary": "Liveness probe",
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthOk"}
                            }
                        },
                    },
                    "503": {
                        "description": "down",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthError"}
                            }
                        },
                    },
                },
            }
        },
        "/api/auth/cli-login": {
            "post": {
                "operationId": "cliLogin",
                "summary": "Exchange credentials for a key",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CliLoginRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/CliLoginResponse"
                                }
                            }
                        },
                    },
                    "400": {
                        "description": "bad request",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ApiError"}
                            }
                        },
                    },
                    "401": {
                        "description": "unauthorized",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ApiError"}
                            }
                        },
                    },
                },
            }
        },
    },
}

#: `FIXTURE_SPEC`'s operation ids -- `ENDPOINTS` grew far past these two (see
#: `_crud`-generated CRUD ids), so every test that generates from
#: `FIXTURE_SPEC` scopes `ENDPOINTS` down to just what the fixture declares.
FIXTURE_ENDPOINTS = {"getHealth", "cliLogin"}


def test_real_spec_generates_without_error():
    """
    Regenerates against a committed snapshot of the server's actual
    `openapi.json` (`resources/openapi/codehood.json`). Catches the
    server renaming a path or dropping an operation `ENDPOINTS` still
    names, and is the regression the whole nested-schemas spec exists for:
    the snapshot is full of inline objects, `nullable`, and one `anyOf`.
    """
    spec = json.loads(REAL_SPEC_PATH.read_text())
    source = Generator(spec).generate()
    namespace = _exec_generated(source)
    assert callable(namespace["health"])
    assert callable(namespace["login"])
    assert callable(namespace["read_course"])
    assert callable(namespace["list_course"])
    assert callable(namespace["create_course"])


def test_unknown_endpoint_fails_loudly(monkeypatch):
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", FIXTURE_ENDPOINTS)
    spec = {**FIXTURE_SPEC, "paths": {}}
    with pytest.raises(KeyError, match="getHealth"):
        Generator(spec)


def test_generated_source_is_importable_and_shaped_right(monkeypatch):
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", FIXTURE_ENDPOINTS)
    source = Generator(FIXTURE_SPEC).generate()
    namespace = _exec_generated(source)

    assert callable(namespace["get_health"])
    assert callable(namespace["cli_login"])
    assert issubclass(namespace["ApiError"], namespace["CodehoodAPIError"])
    # `ApiError` backs two statuses on the same operation -- one class, not two.
    assert source.count("class ApiError(") == 1


#: `FIXTURE_SPEC` plus a synthetic `getMe` that inherits the document's
#: default `security`, and the default itself -- proving the header gets
#: attached from either source, not just an operation's own override.
FIXTURE_SPEC_WITH_AUTH = {
    **FIXTURE_SPEC,
    "security": [{"BearerAuth": []}],
    "paths": {
        **FIXTURE_SPEC["paths"],
        "/api/health": {
            "get": {**FIXTURE_SPEC["paths"]["/api/health"]["get"], "security": []},
        },
        "/api/auth/cli-login": {
            "post": {
                **FIXTURE_SPEC["paths"]["/api/auth/cli-login"]["post"],
                "security": [],
            },
        },
        "/api/me": {
            "get": {
                "operationId": "getMe",
                "summary": "Current user",
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthOk"}
                            }
                        },
                    }
                },
            }
        },
    },
}


def test_auth_required_operation_attaches_bearer_header(monkeypatch):
    """
    An operation whose effective `security` is non-empty (`getMe`, via the
    document's default) gets `headers=auth_headers(client)` on its request
    call; ones that override it to `[]` (`getHealth`, `cliLogin`) don't.
    """
    monkeypatch.setattr(
        "codehood.api.generate.ENDPOINTS", {"getHealth", "cliLogin", "getMe"}
    )
    source = Generator(FIXTURE_SPEC_WITH_AUTH).generate()
    assert "from .base import CodehoodAPIError, auth_headers, get_client" in source
    get_me_source = source.split("def get_me(")[1]
    assert "headers=auth_headers(client)" in get_me_source
    get_health_source = source.split("def get_health(")[1].split("def get_me(")[0]
    assert "headers=auth_headers(client)" not in get_health_source
    cli_login_source = source.split("def cli_login(")[1].split("def get_health(")[0]
    assert "headers=auth_headers(client)" not in cli_login_source


def test_no_auth_required_endpoint_omits_auth_headers_import(monkeypatch):
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", FIXTURE_ENDPOINTS)
    source = Generator(FIXTURE_SPEC).generate()
    assert "auth_headers" not in source


def test_allof_still_raises(monkeypatch):
    """
    `allOf` is deliberately out of scope (merging subschemas is a real
    design question the spec explicitly declines to answer) -- it must
    keep raising, the same way an inline object used to before this
    feature existed.
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", FIXTURE_ENDPOINTS)
    spec = {
        **FIXTURE_SPEC,
        "paths": {
            **FIXTURE_SPEC["paths"],
            "/api/health": {
                "get": {
                    "operationId": "getHealth",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {
                                                "type": "object",
                                                "properties": {"x": {"type": "string"}},
                                            },
                                            {
                                                "type": "object",
                                                "properties": {"y": {"type": "string"}},
                                            },
                                        ]
                                    }
                                }
                            },
                        }
                    },
                }
            },
        },
    }
    with pytest.raises(UnsupportedSchemaError):
        Generator(spec).generate()


#
# Inline objects (top-level and nested), inline arrays, inline request
# bodies -- shapes copied out of `resources/openapi/codehood.json`'s
# `readCourse`/`listCourse`/`createCourse` (trimmed to what each test
# needs).
#
_DISCIPLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "slug": {"type": "string"},
        "name": {"type": "string"},
    },
    "required": ["slug", "name"],
}

_ENROLLMENT_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "userId": {"type": "number"},
        "createdAt": {"type": "string"},
    },
    "required": ["userId", "createdAt"],
}

_COURSE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "number"},
        "discipline": _DISCIPLINE_SCHEMA,
        "enrollments": {"type": "array", "items": _ENROLLMENT_ITEM_SCHEMA},
    },
    "required": ["id", "discipline", "enrollments"],
}

NESTED_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Fixture", "version": "0.0.1"},
    "components": {"schemas": {}},
    "paths": {
        "/api/course/{id}": {
            "get": {
                "operationId": "readCourse",
                "summary": "Find a single Course by id.",
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {"schema": _COURSE_RESPONSE_SCHEMA}
                        },
                    }
                },
            }
        },
        "/api/course": {
            "get": {
                "operationId": "listCourse",
                "summary": "Find multiple Courses.",
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": _COURSE_RESPONSE_SCHEMA,
                                }
                            }
                        },
                    }
                },
            },
            "post": {
                "operationId": "createCourse",
                "summary": "Creates a new Course.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "disciplineSlug": {"type": "string"},
                                    "startAt": {"type": "string", "nullable": True},
                                },
                                "required": ["disciplineSlug", "startAt"],
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"id": {"type": "number"}},
                                    "required": ["id"],
                                }
                            }
                        },
                    }
                },
            },
        },
    },
}


def test_inline_response_object_becomes_named_model(monkeypatch):
    """
    `readCourse`'s inline 2xx response is a real class -- named `Course`,
    since a CRUD operation's entity name beats the site name
    `ReadCourseResponse` (see the spec's naming tiers).
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"readCourse"})
    source = Generator(NESTED_SPEC).generate()
    assert "class Course(Model):" in source
    read_course_source = source.split("def read_course(")[1]
    assert "-> Course:" in read_course_source

    namespace = _exec_generated(source)
    assert set(namespace["Course"].model_fields) == {"id", "discipline", "enrollments"}


def test_nested_inline_object_becomes_a_top_level_model_and_round_trips(monkeypatch):
    """
    `discipline` and `enrollments[]` are inline objects nested inside
    `readCourse`'s response. Each becomes its own module-level class --
    named for the property that holds it -- and validating a realistic
    payload gives attribute access, not dicts.
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"readCourse"})
    source = Generator(NESTED_SPEC).generate()
    namespace = _exec_generated(source)
    course_cls = namespace["Course"]
    discipline_cls = namespace["Discipline"]
    enrollment_cls = namespace["EnrollmentsItem"]

    payload = {
        "id": 1,
        "discipline": {"slug": "algorithms", "name": "Algorithms"},
        "enrollments": [
            {"userId": 7, "createdAt": "2024-01-01T00:00:00Z"},
            {"userId": 8, "createdAt": "2024-01-02T00:00:00Z"},
        ],
    }
    result = course_cls.model_validate(payload)

    assert result.discipline.slug == "algorithms"
    assert result.discipline.name == "Algorithms"
    assert result.enrollments[0].user_id == 7
    assert result.enrollments[1].user_id == 8
    assert isinstance(result.discipline, discipline_cls)
    assert isinstance(result.enrollments[0], enrollment_cls)


def test_identical_shapes_collapse_into_one_class(monkeypatch):
    """
    `listCourse`'s array item is the same schema as `readCourse`'s whole
    response, so both functions must speak in the same `Course` class --
    a caller that fetches a list and a single course has one type, not two
    identical ones (see the spec's structural deduplication).
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"readCourse", "listCourse"})
    source = Generator(NESTED_SPEC).generate()
    assert source.count("class Course(Model):") == 1
    assert "class ListCourseResponseItem(Model):" not in source
    assert "-> Course:" in source.split("def read_course(")[1]
    assert "-> list[Course]:" in source.split("def list_course(")[1]

    namespace = _exec_generated(source)
    course_cls = namespace["Course"]
    payload = [
        {
            "id": index,
            "discipline": {"slug": "algorithms", "name": "Algorithms"},
            "enrollments": [],
        }
        for index in (1, 2)
    ]
    assert [course_cls.model_validate(item).id for item in payload] == [1, 2]


def test_inline_request_body_becomes_named_model(monkeypatch):
    """
    `createCourse`'s inline request body gets minted a name and shows up
    as `body: CreateCourseRequest` in the generated signature.
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"createCourse"})
    source = Generator(NESTED_SPEC).generate()
    assert "class CreateCourseRequest(Model):" in source
    create_course_source = source.split("def create_course(")[1]
    signature = create_course_source.split(") ->")[0]
    assert "body: CreateCourseRequest" in signature


#
# `nullable`
#
NULLABLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Fixture", "version": "0.0.1"},
    "components": {"schemas": {}},
    "paths": {
        "/api/user/{id}": {
            "patch": {
                "operationId": "updateUser",
                "summary": "Update a single User by id.",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    # optional + nullable
                                    "bio": {"type": "string", "nullable": True},
                                    # required + nullable
                                    "age": {"type": "integer", "nullable": True},
                                },
                                "required": ["age"],
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"id": {"type": "number"}},
                                    "required": ["id"],
                                }
                            }
                        },
                    }
                },
            }
        }
    },
}


def test_nullable_required_and_optional_fields(monkeypatch):
    """
    `nullable: true` maps to `T | None`, independent of `required`: a
    required nullable field has no default, an optional one defaults to
    `None`. Neither should ever double up into `T | None | None`.
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"updateUser"})
    source = Generator(NULLABLE_SPEC).generate()

    assert "bio: str | None = None" in source
    # Required, so no default -- the annotation is the whole line.
    assert re.search(r"^\s+age: int \| None$", source, re.MULTILINE)
    assert "None | None" not in source

    namespace = _exec_generated(source)
    request_cls = namespace["UpdateUserRequest"]
    with_bio = request_cls.model_validate({"bio": "hello", "age": None})
    without_bio = request_cls.model_validate({"age": 30})
    assert with_bio.bio == "hello"
    assert with_bio.age is None
    assert without_bio.bio is None
    assert without_bio.age == 30


#
# `anyOf` of two strings collapses to `str` -- `login`'s body field in the
# real spec.
#
LOGIN_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Fixture", "version": "0.0.1"},
    "components": {
        "schemas": {
            "LoginRequest": {
                "type": "object",
                "properties": {
                    "login": {
                        "anyOf": [
                            {"type": "string", "format": "email"},
                            {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{1,30}$"},
                        ]
                    },
                    "password": {"type": "string"},
                },
                "required": ["login", "password"],
            },
            "LoginResponse": {
                "type": "object",
                "properties": {"token": {"type": "string"}},
                "required": ["token"],
            },
        }
    },
    "paths": {
        "/api/login": {
            "post": {
                "operationId": "login",
                "security": [],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LoginRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/LoginResponse"}
                            }
                        },
                    }
                },
            }
        }
    },
}


def test_anyof_of_two_strings_collapses_to_str(monkeypatch):
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"login"})
    source = Generator(LOGIN_SPEC).generate()

    login_request_source = source.split("class LoginRequest(Model):")[1].split(
        "class "
    )[0]
    assert "login: str" in login_request_source
    assert "str | str" not in source

    namespace = _exec_generated(source)
    request_cls = namespace["LoginRequest"]
    validated = request_cls.model_validate({"login": "a@b.com", "password": "secret"})
    assert validated.login == "a@b.com"


#
# `additionalProperties`
#
def _spec_with_response_schema(schema: dict) -> dict:
    return {
        "openapi": "3.0.0",
        "info": {"title": "Fixture", "version": "0.0.1"},
        "components": {"schemas": {}},
        "paths": {
            "/api/health": {
                "get": {
                    "operationId": "health",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": schema}},
                        }
                    },
                }
            }
        },
    }


def test_free_form_object_becomes_a_dict(monkeypatch):
    """
    An object with no `properties` has no fields to mint a model from, so
    it maps to a mapping type -- typed by `additionalProperties` when that
    names a schema, `Any`-valued when it doesn't.
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"health"})

    typed = Generator(
        _spec_with_response_schema(
            {"type": "object", "additionalProperties": {"type": "string"}}
        )
    ).generate()
    assert "-> dict[str, str]:" in typed

    free = Generator(_spec_with_response_schema({"type": "object"})).generate()
    assert "-> dict[str, Any]:" in free
    namespace = _exec_generated(free)
    assert callable(namespace["health"])


#
# Parameter naming
#
PARAMS_SPEC = _spec_with_response_schema(
    {"type": "object", "properties": {"id": {"type": "number"}}, "required": ["id"]}
)
PARAMS_SPEC["paths"]["/api/health"]["get"]["parameters"] = [
    {"name": "instructorUsername", "in": "query", "schema": {"type": "string"}},
    {
        "name": "disciplineSlug",
        "in": "query",
        "required": True,
        "schema": {"type": "string"},
    },
]


def test_query_parameters_are_snake_cased_but_keep_their_wire_names(monkeypatch):
    """
    A caller types `instructor_username=`; the server still receives
    `instructorUsername`. Converting the query key too would silently ask
    the server for a parameter it doesn't have.
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"health"})
    source = Generator(PARAMS_SPEC).generate()
    signature = source.split("def health(")[1].split(") ->")[0]

    assert "discipline_slug: str" in signature
    assert "instructor_username: str | None = None" in signature
    assert "instructorUsername:" not in signature
    assert (
        "params=query_params({'instructorUsername': instructor_username, "
        "'disciplineSlug': discipline_slug})" in source
    )


def test_path_parameters_are_snake_cased_and_still_substitute(monkeypatch):
    """
    The `{...}` placeholder in the path is the server's name for the
    parameter, so `.format()` must keep using it as the keyword.
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"health"})
    spec = json.loads(json.dumps(PARAMS_SPEC))
    spec["paths"]["/api/health/{courseId}"] = spec["paths"].pop("/api/health")
    spec["paths"]["/api/health/{courseId}"]["get"]["parameters"] = [
        {
            "name": "courseId",
            "in": "path",
            "required": True,
            "schema": {"type": "number"},
        }
    ]
    source = Generator(spec).generate()

    assert "def health(*, course_id: float," in source
    assert "'/api/health/{courseId}'.format(courseId=course_id)" in source


#
# Parsing a response body
#
def test_list_response_is_parsed_at_runtime(monkeypatch):
    """
    Calls the generated function against a fake transport, rather than
    only `exec`ing it.

    `list[Course].model_validate(...)` is what a naive "the response type
    validates itself" rule emits, and it raises `AttributeError` on the
    first request -- a `types.GenericAlias` has no such method. Only
    actually calling the function catches that.
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"listCourse"})
    source = Generator(NESTED_SPEC).generate()
    namespace = _exec_generated(source)

    payload = [
        {
            "id": index,
            "discipline": {"slug": "algorithms", "name": "Algorithms"},
            "enrollments": [{"userId": 7, "createdAt": "2024-01-01T00:00:00Z"}],
        }
        for index in (1, 2)
    ]
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        ),
        base_url="http://test",
    )

    result = namespace["list_course"](client=client)
    assert [course.id for course in result] == [1, 2]
    assert result[0].discipline.slug == "algorithms"
    assert isinstance(result[0], namespace["Course"])


def test_free_form_response_is_parsed_at_runtime(monkeypatch):
    """
    Same for a response that isn't a model at all -- `dict[str, Any]` has
    no `model_validate` either.
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"health"})
    source = Generator(_spec_with_response_schema({"type": "object"})).generate()
    namespace = _exec_generated(source)

    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"anything": [1, 2]})
        ),
        base_url="http://test",
    )
    assert namespace["health"](client=client) == {"anything": [1, 2]}


#
# Discriminated unions
#
def _tagged_union_schema() -> dict:
    """
    The shape `Resource.data` has: an `anyOf` whose members are told apart
    by a one-value `type` enum.
    """
    return {
        "type": "object",
        "properties": {
            "data": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["MD"]},
                            "content": {"type": "string"},
                        },
                        "required": ["type", "content"],
                    },
                    {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["CODE"]},
                            "content": {"type": "string"},
                            "language": {"type": "string"},
                        },
                        "required": ["type", "content", "language"],
                    },
                ]
            }
        },
        "required": ["data"],
    }


def test_tagged_union_members_are_named_after_their_tag(monkeypatch):
    """
    Every member of a union sits at the same site, so naming them after
    the site alone leaves them fighting over one name and resolving to
    `Data`, `Data2`, `Data3` -- which tells a reader nothing and silently
    renumbers when the server reorders the union. The tag is the one thing
    that distinguishes them.
    """
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"health"})
    source = Generator(_spec_with_response_schema(_tagged_union_schema())).generate()

    assert "class DataMd(Model):" in source
    assert "class DataCode(Model):" in source
    assert "class Data2(Model):" not in source

    namespace = _exec_generated(source)
    assert set(namespace["DataMd"].model_fields) == {"type", "content"}
    assert set(namespace["DataCode"].model_fields) == {"type", "content", "language"}


def test_untagged_union_members_fall_back_to_the_owner_then_a_counter(monkeypatch):
    """
    Nothing distinguishes members with no tag, so they fall back to the
    schema that owns them and only then to a counter.

    The counter is the last resort, not the scheme: two siblings sharing
    one owner and one base name are the only thing left that it can tell
    apart. Both names still carry the owner, so adding an unrelated
    endpoint cannot renumber either of them.
    """
    schema = {
        "type": "object",
        "properties": {
            "data": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {"a": {"type": "string"}},
                        "required": ["a"],
                    },
                    {
                        "type": "object",
                        "properties": {"b": {"type": "string"}},
                        "required": ["b"],
                    },
                ]
            }
        },
        "required": ["data"],
    }
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"health"})
    source = Generator(_spec_with_response_schema(schema)).generate()
    assert "class HealthResponseData(Model):" in source
    assert "class HealthResponseData2(Model):" in source


#
# Component schemas: identity and projections
#
def _spec_with_component_and_inline(component: dict, inline: dict) -> dict:
    """
    A spec where `readTimeslot` `$ref`s `TimeSlot` and `listTimeslot`
    returns `inline` -- the shape the server actually inlines.
    """
    return {
        "openapi": "3.0.0",
        "info": {"title": "Fixture", "version": "0.0.1"},
        "components": {"schemas": {"TimeSlot": component}},
        "paths": {
            "/api/time-slot/{slug}": {
                "get": {
                    "operationId": "readTimeslot",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/TimeSlot"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/calendar-event": {
                "get": {
                    "operationId": "listCalendar-event",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "array", "items": inline}
                                }
                            },
                        }
                    },
                }
            },
        },
    }


_TIME_SLOT_COMPONENT = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "slug": {"type": "string"},
        "title": {"type": "string", "nullable": True},
        "day": {"type": "string", "enum": ["MONDAY", "TUESDAY"]},
    },
    "required": ["id", "slug", "title", "day"],
}


def test_an_inline_shape_identical_to_a_component_is_that_component(monkeypatch):
    """
    The server inlines on the read paths what it `$ref`s on the create
    path. An inline copy of a component schema is the same type, so it
    takes the component's name and is rendered once -- otherwise `listX`
    hands back a site-named twin of `X` that no caller can pass where an
    `X` is wanted.
    """
    inline = {
        "type": "object",
        "properties": {
            # Same properties, same order, but documented differently --
            # identity is structural, not textual.
            "id": {"type": "integer", "description": "the row id"},
            "slug": {"type": "string", "examples": ["mon-08"]},
            "title": {"type": "string", "nullable": True},
            "day": {"type": "string", "enum": ["MONDAY", "TUESDAY"]},
        },
        "required": ["id", "slug", "title", "day"],
    }
    monkeypatch.setattr(
        "codehood.api.generate.ENDPOINTS", {"readTimeslot", "listCalendar-event"}
    )
    source = Generator(
        _spec_with_component_and_inline(_TIME_SLOT_COMPONENT, inline)
    ).generate()

    assert source.count("class TimeSlot(Model):") == 1
    assert "ListCalendarEventResponseItem" not in source
    assert "-> TimeSlot:" in source.split("def read_timeslot(")[1]
    assert "-> list[TimeSlot]:" in source.split("def list_calendar_event(")[1]


def test_an_inline_subset_of_a_component_is_named_a_projection(monkeypatch):
    """
    `listCalendarEvent` embeds a cut-down time slot: every property of
    `TimeSlot` except the title and the id. That is a projection, named
    after the component it projects and the *entity* the operation is
    about -- `TimeSlotAtCalendarEvent`. The CRUD verb and the fact that it
    arrived in a list response are noise: the same shape reached from
    `readCalendarEvent` is the same class.
    """
    inline = {
        "type": "object",
        "properties": {
            "week": {"type": "integer"},
            "timeSlot": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "day": {"type": "string", "enum": ["MONDAY", "TUESDAY"]},
                },
                # Required-ness differs from the component's; that is a
                # presentation detail of the site, not a different type.
                "required": ["slug"],
            },
        },
        "required": ["week", "timeSlot"],
    }
    monkeypatch.setattr(
        "codehood.api.generate.ENDPOINTS", {"readTimeslot", "listCalendar-event"}
    )
    source = Generator(
        _spec_with_component_and_inline(_TIME_SLOT_COMPONENT, inline)
    ).generate()

    assert "class TimeSlotAtCalendarEvent(Model):" in source
    assert "ListCalendarEventResponseItemTimeSlot" not in source
    assert "time_slot: TimeSlotAtCalendarEvent" in source

    namespace = _exec_generated(source)
    event = namespace["CalendarEvent"].model_validate(
        {"week": 3, "timeSlot": {"slug": "mon-08", "day": "MONDAY"}}
    )
    assert event.time_slot.slug == "mon-08"
    assert isinstance(event.time_slot, namespace["TimeSlotAtCalendarEvent"])


def test_a_subset_of_a_component_it_is_not_named_after_is_not_a_projection(monkeypatch):
    """
    Subset-of-a-component alone names nothing: on the real spec a bare
    `{id}` is a strict subset of eight of them. The property has to be
    named after the component for the match to mean anything, and
    `pinnedAt` is not.
    """
    inline = {
        "type": "object",
        "properties": {
            "week": {"type": "integer"},
            "pinnedAt": {
                "type": "object",
                "properties": {"slug": {"type": "string"}},
                "required": ["slug"],
            },
        },
        "required": ["week", "pinnedAt"],
    }
    monkeypatch.setattr(
        "codehood.api.generate.ENDPOINTS", {"readTimeslot", "listCalendar-event"}
    )
    source = Generator(
        _spec_with_component_and_inline(_TIME_SLOT_COMPONENT, inline)
    ).generate()

    assert "AtCalendarEvent" not in source
    assert "class PinnedAt(Model):" in source
    assert "pinned_at: PinnedAt" in source


def test_a_union_component_is_the_union_of_its_members(monkeypatch):
    """
    A component that is a bare `anyOf` has no fields to make a class of.
    A `$ref` to it maps to the union of its members, the same as that
    `anyOf` written inline, and never to an empty model that would drop
    every key of the response.
    """
    full = {
        "type": "object",
        "properties": {"slug": {"type": "string"}, "answer": {"type": "string"}},
        "required": ["slug", "answer"],
    }
    public = {
        "type": "object",
        "properties": {"slug": {"type": "string"}},
        "required": ["slug"],
    }
    spec = _spec_with_component_and_inline({"anyOf": [full, public]}, public)
    monkeypatch.setattr("codehood.api.generate.ENDPOINTS", {"readTimeslot"})
    source = Generator(spec).generate()

    assert "class TimeSlot(Model):" not in source
    signature = source.split("def read_timeslot(")[1].split(":\n")[0]
    members = signature.split("-> ")[1].split(" | ")
    assert len(members) == 2

    namespace = _exec_generated(source)
    for name in members:
        assert name in namespace
    fields = {
        frozenset(namespace[name].model_fields)  # type: ignore[attr-defined]
        for name in members
    }
    assert fields == {frozenset({"slug", "answer"}), frozenset({"slug"})}
