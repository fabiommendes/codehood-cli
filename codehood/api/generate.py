"""
`python -m codehood_cli.api.generate`: writes `api/generated.py` from a
server's OpenAPI document.

See `dev/specs/to-do/api.md` for the design this follows -- in short: every
name in `ENDPOINTS` must exist in the spec as an `operationId`, and each one
becomes a typed function plus whatever request/response/error models it
needs, all folded into one generated module.
"""

from __future__ import annotations

import json
import keyword
import re
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Annotated, Any, NamedTuple

import httpx
import typer

from .openapi import Endpoint, JSONSchema, OpenAPISpec, Operation, load_openapi

type JSON = dict[str, Any]


def _crud(name: str) -> set[str]:
    """
    Expand a CRUD operation name to the five standard operations.
    """
    entity = name[:1].upper() + name[1:]
    return {
        f"{op}{entity}"
        for op in ("create", "read", "list", "update", "delete", "upsert")
    }


#: `operationId`s this CLI generates a typed function for. See the spec's
#: "`ENDPOINTS` is the one hand-maintained list" -- adding an id here that
#: the spec doesn't define is a generation-time error, not a silent no-op.
ENDPOINTS = {
    "health",
    "login",
    "logout",
    *_crud("course"),
    *_crud("discipline"),
    *_crud("edition"),
    *_crud("user"),
    *_crud("resource"),
    *_crud("question"),
    *_crud("timeslot"),
    *_crud("calendar-event"),
    *_crud("exam"),
    *_crud("grade-column"),
    "courseGrades",
    # `file` is absent: `/api/file` is not in the document while the
    # multipart upload is being written (see `ROADBLOCKS.md` item 1).
}

GENERATED_HEADER = "# This file is AUTO-GENERATED. DO NOT EDIT!\n"

_PRIMITIVE_TYPES = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
}


class UnsupportedSchemaError(NotImplementedError):
    """
    A schema needs JSON Schema features the type mapper doesn't cover yet.

    See `dev/specs/to-review/api-nested-schemas.md`, "What still raises
    `UnsupportedSchemaError`": `allOf`, `not`, list-valued `type`, and any
    node with no `type`, `$ref`, or `anyOf`/`oneOf`.
    """


#
# The generator
#
class Generator:
    def __init__(self, spec: JSON) -> None:
        self.spec = load_openapi(spec)
        self.endpoints = self.spec.operations()
        missing = ENDPOINTS - self.endpoints.keys()
        if missing:
            print("COMPLETE LIST OF ENDPOINTS IN SPEC:")
            for endpoint in sorted(self.endpoints.keys()):
                print(f"- {endpoint}")
            raise KeyError(
                f"ENDPOINTS names operations not in the spec: {sorted(missing)}"
            )

    def generate(self) -> str:
        """
        Generate `api/generated.py`'s full source from the spec.
        """
        needed: dict[str, JSONSchema] = {}
        exceptions_needed: dict[str, JSONSchema] = {}
        shapes = ShapeRegistry(self.spec, ENDPOINTS)

        functions = [
            render_function(
                operation_id,
                self.endpoints[operation_id],
                TypeCtx(self.spec, needed, shapes),
                TypeCtx(self.spec, exceptions_needed, shapes),
            )
            for operation_id in sorted(ENDPOINTS)
        ]
        needs_auth_headers = any(
            self.spec.requires_auth(self.endpoints[operation_id].operation)
            for operation_id in ENDPOINTS
        )

        # A schema used as a documented error is rendered only as an
        # exception -- see the spec's "one exception class per schema".
        for name in exceptions_needed:
            needed.pop(name, None)

        models = self._render_models(needed, shapes, exclude=exceptions_needed.keys())
        exceptions = [
            render_exception(name, schema, TypeCtx(self.spec, needed, shapes))
            for name, schema in sorted(exceptions_needed.items())
        ]

        body = models + exceptions + functions
        imports = self._render_imports(
            needs_literal=any("Literal[" in part for part in body),
            # `dict[str, Any]` is the only place `Any` appears in generated
            # source -- see the spec's "free-form object" rule.
            needs_any=any("dict[str, Any]" in part for part in body),
            pydantic_names={
                name
                for name, marker in [
                    ("ConfigDict", "ConfigDict("),
                    ("Field", "Field(alias="),
                    ("TypeAdapter", "TypeAdapter("),
                ]
                if any(marker in part for part in body)
            },
            needs_auth_headers=needs_auth_headers,
            needs_query_params=any("query_params(" in part for part in body),
        )
        parts = [GENERATED_HEADER, imports, *body]
        return "\n\n".join(part.rstrip() for part in parts) + "\n"

    def _render_models(
        self,
        needed: dict[str, JSONSchema],
        shapes: ShapeRegistry,
        *,
        exclude: Iterable[str],
    ) -> list[str]:
        """
        Render every schema `needed` transitively reaches, as plain models.

        A worklist rather than a single pass over `needed`, because
        rendering one model can discover another (a field referencing a
        schema nobody had reached yet).
        """
        rendered: dict[str, str] = {}
        dependencies: dict[str, set[str]] = {}
        pending = dict(needed)
        while pending:
            name, schema = pending.popitem()
            if name in rendered or name in exclude:
                continue
            discovered: dict[str, JSONSchema] = {}
            rendered[name] = render_model(
                name, schema, TypeCtx(self.spec, discovered, shapes)
            )
            dependencies[name] = set(discovered) - {name}
            for found_name, found_schema in discovered.items():
                if found_name not in rendered:
                    pending[found_name] = found_schema
        return [rendered[name] for name in _dependency_order(dependencies)]

    def _render_imports(
        self,
        *,
        needs_literal: bool,
        needs_any: bool,
        pydantic_names: set[str],
        needs_auth_headers: bool,
        needs_query_params: bool,
    ) -> str:
        lines = ["from __future__ import annotations", ""]
        typing_names = sorted(
            name
            for name, needed in [("Any", needs_any), ("Literal", needs_literal)]
            if needed
        )
        if typing_names:
            lines += [f"from typing import {', '.join(typing_names)}", ""]
        base_imports = ["CodehoodAPIError"]
        if needs_auth_headers:
            base_imports.append("auth_headers")
        base_imports.append("get_client")
        if needs_query_params:
            base_imports.append("query_params")
        lines.append("import httpx")
        if pydantic_names:
            lines.append(f"from pydantic import {', '.join(sorted(pydantic_names))}")
        lines += [
            "",
            "from ..models.base import Model",
            f"from .base import {', '.join(base_imports)}",
        ]
        return "\n".join(lines)


#
# UTILITIES
#
def _unique(items: Iterable[str]) -> list[str]:
    """
    `items` with repeats dropped, first-seen order kept.
    """
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)


def _dependency_order(dependencies: dict[str, set[str]]) -> list[str]:
    """
    Model names ordered so a model is defined after everything it names.

    `from __future__ import annotations` would let pydantic resolve a
    forward reference later, but only by rebuilding the model against its
    module at first use -- which fails outright for anyone who `exec`s the
    source without registering a module. Emitting definitions in
    dependency order costs nothing and makes the file work as plain
    Python. Alphabetical within each layer keeps output deterministic, and
    a `$ref` cycle (nothing in today's spec has one) falls back to
    alphabetical for whatever it can't order.
    """
    ordered: list[str] = []
    remaining = dict(dependencies)
    while remaining:
        ready = sorted(
            name for name, needs in remaining.items() if not needs & remaining.keys()
        ) or sorted(remaining)
        ordered += ready
        for name in ready:
            del remaining[name]
    return ordered


#
# JSON Schema -> Python type
#
def snake_case(identifier: str) -> str:
    """
    `getHealth` -> `get_health`; `instructorUsername` -> `instructor_username`.

    The second pattern keeps a run of capitals together (`userID` ->
    `user_id`, not `user_i_d`), splitting it only where the last capital
    starts a new word.
    """
    words = re.sub(r"[^0-9a-zA-Z]+", "_", identifier)
    return re.sub(
        r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", words
    ).lower()


#: `render_function` gives every generated function a `client` keyword, so a
#: parameter of that name would collide with it.
_RESERVED_ARG_NAMES = {"client", "body"}


def arg_name(parameter_name: str) -> str:
    """
    The Python argument name for a request parameter.

    The wire name stays whatever the server called it -- only the argument
    a caller types is converted, and only far enough to be a usable
    identifier that doesn't collide with the keywords `render_function`
    adds itself.
    """
    name = snake_case(parameter_name)
    if keyword.iskeyword(name) or name in _RESERVED_ARG_NAMES:
        return f"{name}_"
    if not name.isidentifier():
        return "arg_" + re.sub(r"\W", "_", name)
    return name


def pascal(identifier: str) -> str:
    """
    `readCourse` -> `ReadCourse`; `discipline` -> `Discipline`.

    Used both for an operation id (naming a top-level minted request/
    response/error model) and a property name (naming a nested one) --
    the server only ever hands us camelCase identifiers, so capitalizing
    the first letter is the whole job.
    """
    return identifier[:1].upper() + identifier[1:]


def py_class_name(name: str) -> str:
    """
    `Calendar Event` -> `CalendarEvent`; `upsertCalendar-event` ->
    `UpsertCalendarEvent`.

    A schema name and an `operationId` are the server's prose, not Python
    identifiers: the document spells some of them with spaces or hyphens.
    Splitting on anything that is not alphanumeric and capitalizing each
    word is the whole conversion, and it leaves a name that already is an
    identifier untouched.
    """
    words = [word for word in re.split(r"[^0-9a-zA-Z]+", name) if word]
    return "".join(pascal(word) for word in words)


def safe_field_name(property_name: str) -> str:
    """
    A property name pydantic will actually carry as a public field.

    The server emits `_count` on every list-bearing response, and pydantic
    treats a leading underscore as a *private* attribute -- declaring one
    silently drops the field, taking the server's data with it. Such names
    (and Python keywords) become a plain identifier here; the caller pairs
    the result with `Field(alias=...)` so the wire format is unchanged.
    """
    name = property_name.lstrip("_")
    if keyword.iskeyword(name):
        return f"{name}_"
    if not name.isidentifier():
        return "field_" + re.sub(r"\W", "_", property_name)
    return name


def field_name(property_name: str) -> str:
    """
    The Python attribute name for a JSON property.

    Snake_cased from the wire name -- the wire name itself is kept as
    `Field(alias=...)` whenever it differs, so the JSON payload is
    unaffected. Built on top of `safe_field_name` for the leading-
    underscore/keyword handling, then re-checked for a keyword collision
    `snake_case` itself can introduce (`Class` -> `class`).
    """
    name = snake_case(safe_field_name(property_name))
    if keyword.iskeyword(name):
        return f"{name}_"
    return name


#: Name-candidate tiers, best first -- see the spec's naming rules.
#: A tagged union member outranks every other candidate: `DataMd` says what
#: the shape *is*, where the container's own `Data` says only where it was
#: found, and all four members of a union are found in the same place. A
#: projection of a component schema (`_TIER_SUBTYPE`, see
#: `_projection_name`) comes next: it names the entity the shape is a
#: cut-down view of, which the property name alone cannot say.
_TIER_VARIANT = 0
_TIER_SUBTYPE = 1
_TIER_PROPERTY = 2
_TIER_ENTITY = 3
_TIER_SITE = 4

#: CRUD verbs `_crud` builds operation ids from. Stripping one off an
#: operation id leaves the entity the operation is about, which is the best
#: available name for the shape that operation returns (`readCourse` ->
#: `Course`).
_CRUD_VERBS = ("create", "read", "list", "update", "delete", "upsert")


def shape_id(schema: JSONSchema) -> str:
    """
    An inline object schema's identity for deduplication: its *structure*.

    The server is TypeScript/zod, i.e. structurally typed, so two inline
    schemas with the same shape are the same type and deserve one generated
    class. Raw JSON is the wrong identity for that: the exam's `duration`
    and the time slot's `duration` differ only by a `nullable` flag and a
    `description`, neither of which `render_model` emits, yet byte
    comparison calls them two types.

    So the identity is the reduction of a schema to what the generator
    actually renders -- see `_structure`. A node's own `nullable` is
    dropped here because it lands on the *field* that holds the object, not
    on the class.
    """
    structure = _structure(schema)
    if isinstance(structure, dict):
        structure.pop("nullable", None)
    return json.dumps(structure, sort_keys=True)


def _structure(schema: JSONSchema) -> object:
    """
    A schema reduced to the parts that reach generated source.

    `type`, `enum`, `nullable`, union members, array items, property names
    with their optionality, and `additionalProperties`. Everything else --
    `description`, `minimum`, `pattern`, `examples`, `format` -- is
    documentation the generator drops, so it must not split one class into
    two. A `$ref` reduces to the reference itself: it renders as the target
    class's name, which an inline copy of the same shape would not.

    Property *order* is kept, since it is the order fields are emitted in.
    """
    if not isinstance(schema, dict):
        return None
    if "$ref" in schema:
        return {"$ref": schema["$ref"]}

    node: dict[str, object] = {}
    for key in ("type", "enum", "nullable"):
        if key in schema:
            node[key] = schema[key]
    for key in ("anyOf", "oneOf", "allOf"):
        members = schema.get(key)
        if members is not None:
            node[key] = [_structure(member) for member in members]
    if schema.get("type") == "array":
        node["items"] = _structure(schema.get("items", {}))

    properties = schema.get("properties")
    if properties is not None:
        required = set(schema.get("required", []))
        node["properties"] = [
            [name, name in required, _structure(property_schema)]
            for name, property_schema in properties.items()
        ]

    additional = schema.get("additionalProperties")
    if isinstance(additional, dict):
        node["additionalProperties"] = _structure(additional)
    elif additional is not None:
        node["additionalProperties"] = bool(additional)
    return node


def _is_projection(schema: JSONSchema, component: JSONSchema) -> bool:
    """
    Whether `schema` is a strictly smaller view of `component`.

    Every property of `schema` is a property of `component` with the same
    shape, and `component` has at least one more. `required` is compared by
    neither: the same embedded thing is optional at one site and mandatory
    at another, and that says nothing about which type it is.
    """
    properties = schema.get("properties") or {}
    component_properties = component.get("properties") or {}
    if not set(properties) < set(component_properties):
        return False
    return all(
        _structure(property_schema) == _structure(component_properties[name])
        for name, property_schema in properties.items()
    )


class ShapeRegistry:
    """
    Names every inline `object` schema the spec reaches, before any of it
    is rendered.

    The name a shape deserves depends on every place it appears, not just
    the first one reached -- `discipline` is a better name for the shape
    behind `readDiscipline`'s response than `ReadDisciplineResponse` is,
    and only a whole-spec pass can know a property named `discipline`
    holds it. So collection and naming happen up front, and `py_type`
    later just looks a shape up.
    """

    def __init__(self, spec: OpenAPISpec, operation_ids: Iterable[str]) -> None:
        self.spec = spec
        #: shape -> {tier: {candidate names}}, filled by `_collect`.
        self._candidates: dict[str, dict[int, set[str]]] = {}
        #: shape -> shapes holding it as a property value, filled by
        #: `_collect`. A contested name is qualified by one of these.
        self._owners: dict[str, set[str]] = {}
        #: shape -> how deeply nested the shallowest occurrence of it is,
        #: counting one per property hop. Used only to pick which owner
        #: qualifies a contested name.
        self._depths: dict[str, int] = {}
        #: Every `$ref`able object schema, by class name and by shape. An
        #: inline shape that matches one *is* it (`_assign_names`) or is a
        #: projection of it (`_projection_name`).
        self._components = {
            py_class_name(name): schema
            for name, schema in spec.components.schemas.items()
            if isinstance(schema, dict) and schema.get("properties")
        }
        self._component_shapes: dict[str, str] = {}
        for class_name in sorted(self._components):
            self._component_shapes.setdefault(
                shape_id(self._components[class_name]), class_name
            )
        endpoints = spec.operations()
        for operation_id in sorted(operation_ids):
            self._collect_operation(operation_id, endpoints[operation_id].operation)
        self._names = self._assign_names()

    def name_for(self, schema: JSONSchema) -> str:
        return self._names[shape_id(schema)]

    #
    # Collection
    #
    def _collect_operation(self, operation_id: str, operation: Operation) -> None:
        op_pascal = py_class_name(operation_id)
        entity = _crud_entity(operation_id)

        request_body = operation.request_body
        if request_body is not None:
            media = request_body.content.get("application/json")
            if media is not None:
                self._collect(
                    media.content_schema,
                    [(_TIER_SITE, f"{op_pascal}Request")],
                    entity=entity,
                )

        for status, response in operation.responses.items():
            media = response.content.get("application/json")
            if media is None:
                continue
            if status.startswith("2"):
                candidates = [(_TIER_SITE, f"{op_pascal}Response")]
                if entity is not None:
                    candidates.append((_TIER_ENTITY, entity))
            else:
                candidates = [(_TIER_SITE, f"{op_pascal}Error{status}")]
            self._collect(media.content_schema, candidates, entity=entity)

    def _collect(
        self,
        schema: JSONSchema,
        candidates: list[tuple[int, str]],
        owner: str | None = None,
        depth: int = 0,
        entity: str | None = None,
    ) -> None:
        """
        Walk one schema, recording a name candidate for every inline
        object under it. `candidates` are `(tier, name)` for *this* node;
        a property's shape proposes `Pascal(property)` at `_TIER_PROPERTY`,
        and an array's items propose their container's names with `Item`
        appended.

        `owner` is the shape of the nearest enclosing object, used to
        qualify a name two shapes fight over. A union member or an array
        item is held by whatever holds its container, so it inherits the
        same owner. `entity` is what the whole operation is about, carried
        all the way down because a projection is named after it -- see
        `_projection_name`.
        """
        if not isinstance(schema, dict):
            return
        if "$ref" in schema:
            # A component that is a bare union has no class of its own (see
            # `py_type`), so its members are named as if it were inlined here.
            _, resolved = self.spec.resolve(schema)
            if _is_union_component(resolved):
                self._collect(resolved, candidates, owner, depth, entity)
            return

        for member in schema.get("anyOf") or schema.get("oneOf") or []:
            self._collect(
                member, _variant_candidates(member, candidates), owner, depth, entity
            )

        if schema.get("type") == "array":
            # A site name describes the whole response, so its item is that
            # plus `Item`. An entity name describes the thing itself, and
            # `listCourse` returns a list *of* those -- `Course` is already
            # the item's name, not the list's.
            item_candidates = [
                (tier, name if tier == _TIER_ENTITY else f"{name}Item")
                for tier, name in candidates
            ]
            self._collect(
                schema.get("items", {}), item_candidates, owner, depth, entity
            )
            return

        if schema.get("type") != "object":
            return

        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            self._collect(additional, [], owner, depth, entity)

        properties = schema.get("properties")
        if not properties:
            return

        shape = shape_id(schema)
        tiers = self._candidates.setdefault(shape, {})
        for tier, name in candidates:
            tiers.setdefault(tier, set()).add(name)
        projection = self._projection_name(schema, candidates, entity)
        if projection is not None:
            tiers.setdefault(_TIER_SUBTYPE, set()).add(projection)
        if owner is not None:
            self._owners.setdefault(shape, set()).add(owner)
        self._depths[shape] = min(self._depths.get(shape, depth), depth)

        for property_name, property_schema in properties.items():
            self._collect(
                property_schema,
                [(_TIER_PROPERTY, pascal(safe_field_name(property_name)))],
                shape,
                depth + 1,
                entity,
            )

    def _projection_name(
        self,
        schema: JSONSchema,
        candidates: list[tuple[int, str]],
        entity: str | None,
    ) -> str | None:
        """
        `{Component}At{Entity}` when `schema` is a cut-down view of a
        component schema, else `None`.

        `listCalendarEvent`'s items embed `{slug, day, start, duration}`:
        every property of the `TimeSlot` component except the title and the
        ids, with the same shape on each one. That is a *projection* of a
        time slot, and `TimeSlotAtCalendarEvent` says so. The qualifier is
        the entity the operation is about, never the operation id or the
        site, because being in a list response is noise -- the same
        projection reached from `readCalendarEvent` is the same class.

        A projection is only offered to a shape whose property is named
        after the component (`timeSlot` -> `TimeSlot`). Subset-of-a-
        component on its own is far too loose to name anything by: on this
        spec a bare `{id}` is a strict subset of eight components, and a
        request body is a strict subset of the entity it writes. The
        property name is what makes the match unambiguous -- exactly one
        component can answer to it -- and a shape the server did not name
        after the component is not being presented as one.

        Required-ness may differ between the two; that is a presentation
        detail of the site, not evidence of a different thing.
        """
        if entity is None:
            return None
        for tier, name in candidates:
            if tier != _TIER_PROPERTY:
                continue
            component = self._components.get(name)
            if component is not None and _is_projection(schema, component):
                return f"{name}At{entity}"
        return None

    #
    # Naming
    #
    def _assign_names(self) -> dict[str, str]:
        """
        Give each shape a name that depends only on that shape's own
        candidates and on which names the whole document contests.

        A shape structurally identical to a `$ref`able component schema is
        that schema: it takes the component's class name and renders once,
        however many inline copies of it the document carries. The server
        inlines the same entity on the read paths that it `$ref`s on the
        create path, so this is what keeps `readExam` and `listExam`
        returning `Exam` rather than a site-named twin of it.

        Otherwise a shape takes its best *uncontested* candidate: best tier
        first, alphabetical within a tier, skipping any name a `$ref`ed component
        schema already owns or that a second shape also proposes. A bare
        name therefore means "exactly one shape in the spec wants this",
        which is a property a reader can rely on and which no other shape's
        arrival can quietly take away.

        When every candidate is contested, the shape is named
        `{Owner}{Best}` -- the owner being the object that holds it as a
        property (`QuestionTrueFalseChoicesItem`). Qualifying by owner
        rather than by a counter is what makes the output stable: a counter
        numbers shapes in order of appearance, so adding one endpoint
        renumbers models belonging to another (this is exactly how the time
        slot's `Duration` silently became `Duration2`), while an owner is a
        fact about the shape itself.
        """
        reserved = {py_class_name(name) for name in self.spec.components.schemas}
        ordered = {
            shape: _unique(
                [name for tier in sorted(tiers) for name in sorted(tiers[tier])]
            )
            for shape, tiers in self._candidates.items()
        }
        proposals = Counter(name for names in ordered.values() for name in names)
        # Every name any shape proposes is off limits as a qualified name:
        # whether the proposer actually ends up using it is irrelevant, and
        # ignoring that keeps qualification order-independent too.
        blocked = reserved | set(proposals)

        names: dict[str, str] = {}
        resolving: set[str] = set()

        def resolve(shape: str) -> str:
            if shape in names:
                return names[shape]
            if shape in resolving:
                # A shape reachable from itself cannot qualify its own name.
                return ""
            resolving.add(shape)
            component = self._component_shapes.get(shape)
            if component is not None:
                names[shape] = component
                resolving.discard(shape)
                return component
            candidates = ordered[shape]
            free = next(
                (
                    name
                    for name in candidates
                    if name not in reserved and proposals[name] == 1
                ),
                None,
            )
            names[shape] = free or self._qualify(
                candidates, self._owners.get(shape, set()), resolve, blocked, names
            )
            resolving.discard(shape)
            return names[shape]

        for shape in sorted(ordered):
            resolve(shape)
        return names

    def _qualify(
        self,
        candidates: list[str],
        owners: set[str],
        resolve: Callable[[str], str],
        blocked: set[str],
        names: dict[str, str],
    ) -> str:
        """
        `{Owner}{Best}` for a shape whose every candidate is contested.

        A shape can be reached from several owners -- the multiple-choice
        choice appears both under a multiple-choice question and under a
        fill-in blank -- and then the *outermost* owner qualifies it, the
        one closest to the API surface, alphabetically first on a tie. The
        shallow owner is the one a reader meets first, so `Question...` is
        a better prefix than `BlanksItem...` for the same shape.
        """
        base = candidates[0] if candidates else "Shape"
        owner_names = [
            name
            for _depth, name in sorted(
                (self._depths.get(owner, 0), resolve(owner)) for owner in owners
            )
            if name
        ]
        taken = blocked | set(names.values())
        for owner_name in owner_names:
            qualified = f"{owner_name}{base}"
            if qualified not in taken:
                return qualified

        # Nothing left but a counter: the shape has no owner at all (a
        # response body is held by nothing), or its owner already qualifies
        # a sibling that wants the same name -- two untagged members of one
        # union, which share both owner and base and so cannot be told
        # apart by either. Nothing in today's spec reaches this. The counter
        # still counts onto the owner-qualified name, so at worst one shape
        # of a pair carries a digit rather than both names being positional.
        stem = f"{owner_names[0]}{base}" if owner_names else base
        suffix = 2
        while f"{stem}{suffix}" in taken:
            suffix += 1
        return f"{stem}{suffix}"


def _variant_candidates(
    member: JSONSchema, candidates: list[tuple[int, str]]
) -> list[tuple[int, str]]:
    """
    Name candidates for one member of an `anyOf`/`oneOf`.

    Every member of a union sits at the same site, so inheriting the
    container's candidates unchanged leaves them fighting over one name and
    resolving to `Data`, `Data2`, `Data3`. A member tagged by a
    single-valued `enum` -- the JSON Schema spelling of a discriminated
    union -- proposes `{container}{Tag}` instead, so `data`'s four members
    become `DataLink`, `DataFile`, `DataCode`, and `DataMd`.

    An untagged member has nothing better to offer and keeps the
    container's candidates as they are.
    """
    tag = _discriminator(member)
    if tag is None:
        return candidates
    suffix = tag_suffix(tag)
    return [(_TIER_VARIANT, f"{name}{suffix}") for _, name in candidates] + candidates


def tag_suffix(tag: str) -> str:
    """
    The class-name suffix a discriminator tag contributes.

    `FILE` is a tag, not an acronym the reader wants shouted back:
    `DataFile` reads as a class name where `DataFILE` does not. A tag the
    server spells with separators is a phrase, not an identifier, so each
    word is capitalized and the separators dropped -- `multiple-choice`
    gives `QuestionMultipleChoice`, which is a name Python will accept.
    """
    words = [word for word in re.split(r"[^a-zA-Z0-9]+", tag) if word]
    return "".join(word.title() if word.isupper() else pascal(word) for word in words)


def _discriminator(schema: JSONSchema) -> str | None:
    """
    The tag value of a discriminated-union member, if it has one.

    A property whose schema is a one-value string `enum` is the tag; a
    property literally named `type` wins over any other, since that is what
    the server's own unions use.
    """
    if not isinstance(schema, dict):
        return None
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None

    tags: dict[str, str] = {}
    for name, property_schema in properties.items():
        if not isinstance(property_schema, dict):
            continue
        values = property_schema.get("enum")
        if isinstance(values, list) and len(values) == 1 and isinstance(values[0], str):
            tags[name] = values[0]

    if "type" in tags:
        return tags["type"]
    return next(iter(tags.values()), None)


def _crud_entity(operation_id: str) -> str | None:
    """`readCourse` -> `Course`; `login` -> `None`."""
    for verb in _CRUD_VERBS:
        if operation_id.startswith(verb) and len(operation_id) > len(verb):
            return py_class_name(operation_id[len(verb) :])
    return None


class TypeCtx(NamedTuple):
    """
    What `py_type` needs besides the schema itself.

    `needed` accumulates every named schema reached along the way -- both
    `$ref` targets and inline objects the `ShapeRegistry` has minted a name
    for -- so the caller renders exactly the models actually used.
    """

    spec: OpenAPISpec
    needed: dict[str, JSONSchema]
    shapes: ShapeRegistry


def py_type(schema: JSONSchema, ctx: TypeCtx) -> str:
    """
    Map one JSON Schema node to a Python type annotation.
    """
    if "$ref" in schema:
        ref_name, resolved = ctx.spec.resolve(schema)
        if _is_union_component(resolved):
            return py_type(resolved, ctx)
        name = py_class_name(ref_name)
        ctx.needed[name] = resolved
        return name

    if "allOf" in schema or "not" in schema or isinstance(schema.get("type"), list):
        raise UnsupportedSchemaError(
            f"cannot map schema to a Python type yet:\n{json.dumps(schema, indent=2)}"
        )

    members = schema.get("anyOf") or schema.get("oneOf")
    if members is not None:
        parts = [py_type(member, ctx) for member in members]
    else:
        parts = [_resolve_shape(schema, ctx)]

    if schema.get("nullable"):
        parts.append("None")

    return dedupe_union(parts)


def _is_union_component(schema: JSONSchema) -> bool:
    """
    Whether a `$ref` target is a union with no properties of its own.

    Such a component cannot be a model class: it has no fields, only
    members. It maps to the union of its members, exactly as the same
    `anyOf` written inline would.
    """
    return not schema.get("properties") and bool(
        schema.get("anyOf") or schema.get("oneOf")
    )


def dedupe_union(parts: list[str]) -> str:
    """
    Join union members with `|`, dropping repeats but keeping first-seen
    order -- so `nullable` composed with an already-nullable `anyOf`, or an
    `anyOf` of two schemas that map to the same type, don't double up.
    """
    seen: list[str] = []
    for part in parts:
        if part not in seen:
            seen.append(part)
    return " | ".join(seen)


def _resolve_shape(schema: JSONSchema, ctx: TypeCtx) -> str:
    """
    `py_type` for a schema already known not to be a `$ref`, `anyOf`,
    `oneOf`, `allOf`, `not`, or `nullable` wrapper -- enums, primitives,
    arrays, and objects.
    """
    enum_values = schema.get("enum")
    if enum_values and all(
        value is None or isinstance(value, (str, int, bool)) for value in enum_values
    ):
        values = ", ".join(repr(value) for value in enum_values)
        return f"Literal[{values}]"

    schema_type = schema.get("type")
    if schema_type == "null":
        return "None"
    if schema_type in _PRIMITIVE_TYPES:
        return _PRIMITIVE_TYPES[schema_type]
    if schema_type == "array":
        return f"list[{py_type(schema.get('items', {}), ctx)}]"
    if schema_type == "object":
        return _resolve_object(schema, ctx)
    if schema_type is None:
        # An untyped node -- `{}`, or `{"nullable": true}` as the
        # `additionalProperties` of a free-form `meta` map -- constrains
        # nothing, so any JSON value satisfies it. `object` says that
        # without reaching for `Any`.
        return "object"

    raise UnsupportedSchemaError(
        f"cannot map schema to a Python type yet:\n{json.dumps(schema, indent=2)}"
    )


def _resolve_object(schema: JSONSchema, ctx: TypeCtx) -> str:
    """
    An inline `object`: the name the registry minted for its shape if it
    has `properties`, otherwise a `dict[...]` -- see the spec's
    "`additionalProperties`" section.
    """
    if schema.get("properties"):
        name = ctx.shapes.name_for(schema)
        ctx.needed[name] = schema
        return name

    additional = schema.get("additionalProperties")
    if isinstance(additional, dict):
        return f"dict[str, {py_type(additional, ctx)}]"
    return "dict[str, Any]"


def annotated(py_type: str, *, required: bool) -> str:
    """
    `py_type` if the field is required, else unioned with `None`.

    `py_type` may already include `None` (a `nullable` field, or a
    `format`-of-strings `anyOf` with a `{"type": "null"}` member) -- an
    optional nullable field must not come out `T | None | None`, so this
    dedupes the same way `py_type`'s own unions do.
    """
    if required:
        return py_type
    return dedupe_union([*py_type.split(" | "), "None"])


class ParamSpec(NamedTuple):
    """
    One request parameter: what the caller types (`name`) and what goes on
    the wire (`wire_name`) -- see `arg_name`.
    """

    name: str
    wire_name: str
    location: str
    required: bool
    py_type: str


class FieldSpec(NamedTuple):
    py_type: str
    required: bool
    #: The wire name, when it differs from the Python field name -- see
    #: `safe_field_name`. `None` when the two are the same.
    alias: str | None = None


def get_field_types(schema: JSONSchema, ctx: TypeCtx) -> dict[str, FieldSpec]:
    """
    `{field_name: (python_type, required, alias)}` for one object schema.
    """
    required = set(schema.get("required", []))
    fields: dict[str, FieldSpec] = {}
    for name, field_schema in schema.get("properties", {}).items():
        py_name = field_name(name)
        fields[py_name] = FieldSpec(
            py_type(field_schema, ctx),
            name in required,
            alias=None if py_name == name else name,
        )
    return fields


def render_field_lines(field_types: dict[str, FieldSpec]) -> list[str]:
    if not field_types:
        return ["    pass"]
    lines = []
    for name, (py_type, required, alias) in field_types.items():
        annotation = annotated(py_type, required=required)
        if alias is None:
            assignment = "" if required else " = None"
        else:
            default = "" if required else "default=None, "
            assignment = f" = Field({default}alias={alias!r})"
        lines.append(f"    {name}: {annotation}{assignment}")
    return lines


def render_config_lines(field_types: dict[str, FieldSpec]) -> list[str]:
    """
    `populate_by_name` for a class that aliases at least one field, so it
    can still be built from Python with the field's own name.
    """
    if not any(spec.alias for spec in field_types.values()):
        return []
    return ["    model_config = ConfigDict(populate_by_name=True)", ""]


#
# Rendering: plain data models
#
def render_model(name: str, schema: JSONSchema, ctx: TypeCtx) -> str:
    """
    Render one `class {name}(Model): ...`. Any inline object it holds is
    its own top-level model, referred to by the name the `ShapeRegistry`
    minted -- see the spec's "Inline objects become top-level models".
    """
    field_types = get_field_types(schema, ctx)
    lines = [f"class {name}(Model):"]
    lines += render_config_lines(field_types)
    lines += render_field_lines(field_types)
    return "\n".join(lines) + "\n"


#
# Rendering: typed exceptions
#
#: Names `CodehoodAPIError` itself defines. A payload field with one of
#: these names still lands in `.payload` normally, but gets no top-level
#: property -- one would silently shadow the base class's own attribute
#: (e.g. a payload's `status` field hiding the HTTP status code), which is
#: worse than the minor inconsistency of that one field needing
#: `.payload.status` instead of `.status`.
_RESERVED_EXCEPTION_ATTRS = {"status", "payload"}


def render_exception(name: str, schema: JSONSchema, ctx: TypeCtx) -> str:
    field_types = get_field_types(schema, ctx)
    payload_lines = [
        f"    {line}"
        for line in render_config_lines(field_types) + render_field_lines(field_types)
    ]
    payload_body = "\n".join(payload_lines)

    lines = [
        f"class {name}(CodehoodAPIError):",
        "    class Payload(Model):",
        payload_body,
        "",
        "    payload: Payload",
    ]
    properties = [
        "\n".join(
            [
                "    @property",
                f"    def {field_name}(self) -> {annotated(py_type, required=required)}:",
                f"        return self.payload.{field_name}",
            ]
        )
        for field_name, (py_type, required, _alias) in field_types.items()
        if field_name not in _RESERVED_EXCEPTION_ATTRS
    ]
    blocks = ["\n".join(lines), *properties]
    return "\n\n".join(blocks) + "\n"


#
# Rendering: one generated function per endpoint
#
def render_parse(py_type: str, expression: str, model_names: Iterable[str]) -> str:
    """
    Source that turns a decoded JSON body into `py_type`.

    A generated model validates itself, but a response is not always one:
    `list[Course]`, `dict[str, Any]` and `str` are all types
    `X.model_validate(...)` is simply not defined on -- `list[Course]` is a
    `types.GenericAlias`, so calling it would raise `AttributeError` on the
    first request. `TypeAdapter` covers every one of those uniformly.
    """
    if py_type in model_names:
        return f"{py_type}.model_validate({expression})"
    return f"TypeAdapter({py_type}).validate_python({expression})"


def render_function(
    operation_id: str,
    endpoint: Endpoint,
    ctx: TypeCtx,
    error_ctx: TypeCtx,
) -> str:
    """
    `error_ctx` differs from `ctx` only in where it accumulates schemas:
    one used as a documented error is rendered as an exception class, not
    a plain model.
    """
    operation = endpoint.operation
    spec = ctx.spec
    func_name = snake_case(operation_id)

    params = [
        ParamSpec(
            arg_name(parameter.name),
            parameter.name,
            parameter.location,
            parameter.required,
            py_type(parameter.content_schema, ctx),
        )
        for parameter in operation.parameters
    ]

    body_type = None
    if operation.request_body is not None:
        media = operation.request_body.content.get("application/json")
        if media is not None:
            body_type = py_type(media.content_schema, ctx)

    success_status = next(
        (status for status in operation.responses if status.startswith("2")), None
    )
    if success_status is None:
        raise UnsupportedSchemaError(f"{operation_id!r} has no documented 2xx response")
    success_media = operation.responses[success_status].content.get("application/json")
    success_type = (
        py_type(success_media.content_schema, ctx) if success_media else "None"
    )

    error_types: dict[str, str] = {
        status: py_type(media.content_schema, error_ctx)
        for status, response in operation.responses.items()
        if not status.startswith("2")
        for media in [response.content.get("application/json")]
        if media is not None
    }
    for status, error_type in error_types.items():
        if error_type not in error_ctx.needed:
            raise UnsupportedSchemaError(
                f"{operation_id!r}'s {status} response is {error_type}, which "
                "has no exception class to carry it -- a documented error "
                "must be an object schema"
            )

    signature_parts = [
        f"{param.name}: {annotated(param.py_type, required=param.required)}"
        + ("" if param.required else " = None")
        for param in params
    ]
    if body_type is not None:
        signature_parts.append(f"body: {body_type}")
    signature_parts.append("client: httpx.Client | None = None")

    path_params = [param for param in params if param.location == "path"]
    query_params = [param for param in params if param.location == "query"]

    path_expr = repr(endpoint.path)
    if path_params:
        # The placeholder in the path is the server's name for the
        # parameter, not the argument's.
        substitutions = ", ".join(
            f"{param.wire_name}={param.name}" for param in path_params
        )
        path_expr = f"{endpoint.path!r}.format({substitutions})"

    call_kwargs = []
    if query_params:
        pairs = ", ".join(
            f"{param.wire_name!r}: {param.name}" for param in query_params
        )
        # `query_params` drops the ones the caller left unset; `httpx`
        # would otherwise send them as `?name=`, which is not the same
        # thing as not sending them.
        call_kwargs.append(f"params=query_params({{{pairs}}})")
    if body_type is not None:
        call_kwargs.append('json=body.model_dump(mode="json", by_alias=True)')
    if spec.requires_auth(operation):
        call_kwargs.append("headers=auth_headers(client)")
    call_args = path_expr + ("" if not call_kwargs else ", " + ", ".join(call_kwargs))

    lines = [f"def {func_name}(*, {', '.join(signature_parts)}) -> {success_type}:"]
    doc = operation.summary or operation.description
    if doc:
        lines += ['    """', f"    {doc}", '    """']
    lines.append("    client = client if client is not None else get_client()")
    lines.append(f"    response = client.{endpoint.method.lower()}({call_args})")

    for status, exception_name in error_types.items():
        lines.append(f"    if response.status_code == {status}:")
        lines.append(
            f"        raise {exception_name}"
            f"(response.status_code, {exception_name}.Payload.model_validate(response.json()))"
        )

    lines.append(f"    if response.status_code == {success_status}:")
    lines.append(
        "        return None"
        if success_type == "None"
        else "        return "
        + render_parse(success_type, "response.json()", ctx.needed)
    )
    lines.append("    response.raise_for_status()")
    lines.append("    raise CodehoodAPIError(response.status_code, Model())")

    return "\n".join(lines) + "\n"


#
# CLI
#
def main() -> None:
    """
    Entry point for `python -m codehood_cli.api.generate`.
    """
    app = typer.Typer(
        name="api-codegen",
        help="Generate API client code from OpenAPI spec.",
    )

    @app.command()
    def codegen(
        path: Annotated[
            str | None,
            typer.Argument(
                help="Path to OpenAPI spec file or URL to a Codehood server."
            ),
        ] = None,
        output: Annotated[
            Path | None,
            typer.Argument(help="Path to write the generated module to."),
        ] = None,
    ) -> None:
        """
        Generate `api/generated.py` from an OpenAPI spec.
        """
        if path is None:
            path = (
                "openapi.json"
                if Path("openapi.json").exists()
                else "http://localhost:4321/openapi.json"
            )

        if path.startswith("http://") or path.startswith("https://"):
            response = httpx.get(path)
            response.raise_for_status()
            spec = response.json()
        else:
            spec = json.loads(Path(path).read_text(encoding="utf-8"))

        output = output or Path(__file__).parent / "generated.py"
        source = Generator(spec).generate()
        output.write_text(source, encoding="utf-8")
        typer.echo(f"wrote {output}")

    app()


if __name__ == "__main__":
    main()
