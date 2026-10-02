"""
Field validators and their `Annotated` types for `codehood.toml`'s models.

The patterns and the reserved-slug set are copied from the server's
published rules for a valid course URL segment -- see `repo.py`'s
docstring and `dev/specs/to-do/init.md`, "Slugs are validated locally,
existence is not".
"""

from __future__ import annotations

import re
from functools import wraps
from typing import Annotated, Any, Callable

from pydantic import AfterValidator

__all__ = [
    #: Types
    "DisciplineSlug",
    "InstructorUsername",
    "EditionSlug",
    "GradeColumnSlug",
    "ServerUrl",
    #: Validator composition
    "string_validator",
    #: Validators
    "validate_discipline",
    "validate_instructor",
    "validate_edition",
    "validate_slug",
    "url_validator",
]

type Validator[T] = Callable[[Any], T]

# Patterns copied from `codehood-server/src/utils/course-url.ts`
# (`DISCIPLINE_SLUG_RE`, `USERNAME_RE`, `EDITION_RE`), the server's
# published rules for what makes a valid course URL segment. `init` checks
# these locally so a typo like `2026_1` or `CS101` is a fast local error;
# whether the slug actually names something is left to the server.
DISCIPLINE_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")
INSTRUCTOR_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")
EDITION_RE = re.compile(r"^[0-9]{4}(-([1-9][0-9]*|0))?$")

# The server's rule for a flat slug (`slug` in `src/core/schemas/base.ts`):
# exactly one URL segment.
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

# Copied from `codehood-server/src/utils/course-url.ts`'s `RESERVED_SLUGS`.
# Top-level names a discipline slug must not equal, because the root
# namespace is shared with every system route. This copy will drift from
# the server's list over time; that is accepted (see the spec) and the fix
# when it does is a paste from that file.
RESERVED_SLUGS: frozenset[str] = frozenset(
    {
        "403",
        "404",
        "500",
        "_actions",
        "_astro",
        "_image",
        "admin",
        "api",
        "calendar",
        "courses",
        "design",
        "favicon",
        "files",
        "getting-started",
        "img",
        "invite",
        "login",
        "logo",
        "manifest",
        "profile",
        "sw",
        "about",
        "docs",
        "help",
        "logout",
        "me",
        "new",
        "search",
        "settings",
        "signup",
        "static",
        "users",
    }
)


#
# Validator composition
#
def string_validator(fn: Callable[[str], str], /) -> Validator[str]:
    """
    Wrap a string validator to accept any value and convert it to a string.
    """

    @wraps(fn)
    def wrapper(value: Any) -> str:
        return fn(str(value))

    return wrapper


#
# Validator functions
#
@string_validator
def validate_discipline(value: str) -> str:
    if not DISCIPLINE_RE.fullmatch(value):
        raise ValueError(f"discipline {value!r} must match {DISCIPLINE_RE.pattern!r}")
    if value in RESERVED_SLUGS:
        raise ValueError(f"discipline {value!r} is a reserved name")
    return value


@string_validator
def validate_instructor(value: str) -> str:
    if not INSTRUCTOR_RE.fullmatch(value):
        raise ValueError(f"instructor {value!r} must match {INSTRUCTOR_RE.pattern!r}")
    return value


@string_validator
def validate_edition(value: str) -> str:
    if not EDITION_RE.fullmatch(value):
        raise ValueError(f"edition {value!r} must match {EDITION_RE.pattern!r}")
    return value


@string_validator
def validate_slug(value: str) -> str:
    if not SLUG_RE.fullmatch(value):
        raise ValueError(f"slug {value!r} must match {SLUG_RE.pattern!r}")
    return value


@string_validator
def url_validator(value: str) -> str:
    # TODO: validate that the URL has a valid structure.
    return value.removesuffix("/")


#
# Annotated type aliases
#
DisciplineSlug = Annotated[str, AfterValidator(validate_discipline)]
InstructorUsername = Annotated[str, AfterValidator(validate_instructor)]
EditionSlug = Annotated[str, AfterValidator(validate_edition)]
GradeColumnSlug = Annotated[str, AfterValidator(validate_slug)]
ServerUrl = Annotated[str, AfterValidator(url_validator)]
