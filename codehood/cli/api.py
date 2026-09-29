"""
`codehood api`: browse the endpoints the CLI knows about, and call the ones
that don't require auth, straight from a server's OpenAPI document. See
`dev/specs/to-review/api.md`.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

import httpx
import typer
from rich import markup
from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.syntax import Syntax
from rich.style import Style
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from ..api import generated
from ..api.base import CodehoodAPIError, get_client
from ..api.generate import ENDPOINTS, arg_name, snake_case
from ..api.openapi import Endpoint, JSONSchema, OpenAPISpec, Operation, load_openapi
from ..theme import CodehoodApp, role_style
from .base import app

__all__ = ["api"]

#: (field name, required, mask input) triples, in schema order.
FieldSpec = tuple[str, bool, bool]

METHOD_ROLE = {
    "GET": "success",
    "POST": "primary",
    "PUT": "warning",
    "PATCH": "accent",
    "DELETE": "error",
}


@app.command()
def api(
    server: Annotated[
        str | None,
        typer.Option(
            "--server",
            help="Codehood server URL. Defaults to the current repository's codehood.toml.",
        ),
    ] = None,
) -> None:
    """
    Browse the REST API endpoints `codehood` knows about.
    """
    try:
        spec_data = fetch_spec(server)
    except httpx.HTTPError as exc:
        typer.echo(f"error: could not fetch the OpenAPI spec: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    spec = load_openapi(spec_data)
    all_endpoints = spec.operations()
    missing = ENDPOINTS - all_endpoints.keys()
    if missing:
        typer.echo(
            f"error: server spec is missing registered endpoints: {sorted(missing)}",
            err=True,
        )
        raise typer.Exit(code=1)

    endpoints = {
        operation_id: all_endpoints[operation_id] for operation_id in ENDPOINTS
    }
    # Same `server` the spec was just fetched from, so a call from the
    # browser targets that server too -- `--server` shouldn't stop applying
    # once you press enter on a row.
    ApiBrowser(endpoints, spec, get_client(server)).run()


class ApiBrowser(CodehoodApp[None]):
    """
    Lists the endpoints in `ENDPOINTS`; every detail shown is read live from
    the parsed spec, never hardcoded.

    Pressing enter on a row calls that endpoint, unless the spec says it
    needs auth we don't have.
    """

    CSS = """
    #detail {
        height: 1fr;
        border: solid $accent;
        padding: 1 2;
    }
    """
    BINDINGS = [("q", "quit", "Quit")]
    TITLE = "codehood api"

    def __init__(
        self,
        endpoints: dict[str, Endpoint],
        spec: OpenAPISpec,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__()
        self.endpoints = endpoints
        self.spec = spec
        #: Reused for every call so it targets the same server browsing did
        #: -- `--server` shouldn't stop applying once you press enter.
        self.client = client if client is not None else get_client()

    def compose(self) -> ComposeResult:
        yield Header()
        table: DataTable[str] = DataTable(id="endpoints")
        table.cursor_type = "row"
        table.add_columns("operationId", "method", "path", "summary")
        for operation_id, endpoint in sorted(self.endpoints.items()):
            table.add_row(
                operation_id,
                endpoint.method,
                endpoint.path,
                endpoint.operation.summary,
                key=operation_id,
            )
        yield table
        yield Static(id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(DataTable).focus()
        if self.endpoints:
            self.show_detail(sorted(self.endpoints)[0])

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key.value is not None:
            self.show_detail(event.row_key.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is not None:
            self._call_endpoint(event.row_key.value)

    def show_detail(self, operation_id: str) -> None:
        endpoint = self.endpoints[operation_id]
        operation = endpoint.operation
        renderables: list[RenderableType] = []

        def render_schema(
            schema: JSONSchema, title: str | None = None
        ) -> RenderableType:
            if "$ref" in schema:
                name, schema = self.spec.resolve(schema)
            source = dump_schema_as_yaml(schema)
            group: list[RenderableType] = [Padding(Syntax(source, "yaml"), (0, 2))]

            if title is not None:
                group = [markup.render(title), *group]
            return Padding(Group(*group), (1, 0, 0, 2))

        # Head
        renderables.append(
            Text.assemble(
                (
                    endpoint.method,
                    role_style(METHOD_ROLE.get(endpoint.method, "muted")) + Style(bold=True),
                ),
                (f" {endpoint.path}", "bold"),
            )
        )

        title_style = "bold underline"
        if operation.parameters:
            renderables.append(Text("\nPARAMETERS", style=title_style))
            for parameter in operation.parameters:
                mark = "*" if parameter.required else ""
                schema = render_schema(parameter.content_schema)
                renderables.append(
                    f"  {parameter.name} ({parameter.location}){mark}: {schema}"
                )

        if operation.request_body is not None:
            renderables.append(Text("\nBODY", style=title_style))
            for media_type, media in operation.request_body.content.items():
                data = render_schema(
                    media.content_schema, title=f"Request Body ({media_type})"
                )
                renderables.append(data)

        renderables.append(Text("\nRESPONSES", style=title_style))
        for status, response in sorted(operation.responses.items()):
            response_media = response.content.get("application/json")
            if response_media is not None:
                renderables.append(
                    render_schema(
                        response_media.content_schema,
                        title=f"[b]{status}:[/b] {response.description}",
                    )
                )

        self.query_one("#detail", Static).update(Group(*renderables))

    @work
    async def _call_endpoint(self, operation_id: str) -> None:
        """
        Runs as a Textual worker: `push_screen_wait` below requires one, and
        it keeps a slow call from blocking the row-selected handler.
        """
        endpoint = self.endpoints[operation_id]
        operation = endpoint.operation

        if self.spec.requires_auth(operation):
            self._show_result(
                f"{operation_id} requires authentication, which `codehood login` "
                "doesn't support yet -- refusing rather than sending a request "
                "that would just fail server-side.",
                is_error=True,
            )
            return

        field_specs = self._field_specs(operation)
        values: dict[str, str] = {}
        if field_specs:
            result = await self.push_screen_wait(CallForm(field_specs))
            if result is None:
                return
            values = result

        function = getattr(generated, snake_case(operation_id))
        kwargs = self._build_kwargs(operation, values)
        try:
            outcome = await asyncio.to_thread(function, client=self.client, **kwargs)
        except CodehoodAPIError as exc:
            self._show_result(
                f"{type(exc).__name__} (HTTP {exc.status}): {exc.payload}",
                is_error=True,
            )
        except httpx.HTTPError as exc:
            self._show_result(f"request failed: {exc}", is_error=True)
        else:
            self._show_result(str(outcome), is_error=False)

    def _field_specs(self, operation: Operation) -> list[FieldSpec]:
        specs = [
            (parameter.name, parameter.required, "password" in parameter.name.lower())
            for parameter in operation.parameters
        ]
        body_schema = self._body_schema(operation)
        if body_schema is not None:
            required = set(body_schema.get("required", []))
            for field_name in body_schema.get("properties", {}):
                specs.append(
                    (
                        field_name,
                        field_name in required,
                        "password" in field_name.lower(),
                    )
                )
        return specs

    def _body_schema(self, operation: Operation) -> JSONSchema | None:
        if operation.request_body is None:
            return None
        media = operation.request_body.content.get("application/json")
        if media is None or "$ref" not in media.content_schema:
            return None
        _name, schema = self.spec.resolve(media.content_schema)
        return schema

    def _build_kwargs(
        self, operation: Operation, values: dict[str, str]
    ) -> dict[str, Any]:
        # The form collects values under each parameter's wire name (what
        # the detail pane shows); the generated function takes them under
        # the snake_cased argument name.
        kwargs: dict[str, Any] = {
            arg_name(parameter.name): values[parameter.name]
            for parameter in operation.parameters
            if parameter.name in values
        }
        if operation.request_body is not None:
            media = operation.request_body.content.get("application/json")
            if media is not None and "$ref" in media.content_schema:
                model_name, schema = self.spec.resolve(media.content_schema)
                body_values = {
                    name: values[name]
                    for name in schema.get("properties", {})
                    if name in values
                }
                body_model = getattr(generated, model_name)
                kwargs["body"] = body_model(**body_values)
        return kwargs

    def _show_result(self, text: str, *, is_error: bool) -> None:
        style = role_style("error" if is_error else "success") + Style(bold=True)
        self.query_one("#detail", Static).update(Text(text, style=style))


class CallForm(ModalScreen[dict[str, str] | None]):
    """
    One text `Input` per field an operation's call needs (its request body's
    fields, plus any path/query parameters). Dismisses with `None` on
    cancel, or `{field_name: value}` on submit.
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    CSS = """
    CallForm {
        align: center middle;
    }
    #form {
        width: 60;
        height: auto;
        border: solid $accent;
        padding: 1 2;
        background: $surface;
    }
    """

    def __init__(self, fields: list[FieldSpec]) -> None:
        super().__init__()
        self.fields = fields

    def compose(self) -> ComposeResult:
        with Vertical(id="form"):
            for name, required, secret in self.fields:
                yield Label(f"{name}{'*' if required else ''}")
                yield Input(password=secret, id=f"field-{name}")
            yield Button("Submit", id="submit", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        values: dict[str, str] = {}
        for name, required, _secret in self.fields:
            value = self.query_one(f"#field-{name}", Input).value
            if required and not value:
                self.notify(f"{name} is required", severity="error")
                return
            values[name] = value
        self.dismiss(values)

    def action_cancel(self) -> None:
        self.dismiss(None)


#
#  Utilities
#
def dump_schema_as_yaml(schema: JSONSchema, inline_threshold: int = 40) -> str:
    """
    Render a JSON schema as YAML, for display in the API browser.

    The spec's OpenAPI document is JSON, but YAML is more readable for
    humans. This is only used for display, so it doesn't need to be
    round-trippable.
    """

    def quote(v: Any) -> str:
        if isinstance(v, str):
            return f'"{v}"'
        return str(v)

    def label(value: str) -> str:
        # A parameter's own schema (e.g. a query param typed `boolean`) has
        # no `properties` -- it's rendered as its bare type, with no `key:`
        # prefix, rather than assuming every schema describes an object.
        return value if key is None else f"{key}: {value}"

    properties = schema.get("properties")
    items = properties.items() if properties is not None else [(None, schema)]

    lines = []
    for key, prop in items:
        prop = prop.copy()
        line = label(prop["type"])
        comments = []

        if "enum" in prop and len(prop["enum"]) == 1:
            # A single-value enum is a constant, so show it as such.
            line = label(quote(prop["enum"][0]))
            del prop["enum"]

        if "description" in prop:
            comments.append(prop["description"].removesuffix("."))
        if "enum" in prop:
            cases = " | ".join(quote(case) for case in prop["enum"])
            comments.append(f"enum: {cases}")
        if "minLength" in prop:
            comments.append(f"length >= {prop['minLength']}")
        if "maxLength" in prop:
            comments.append(f"length <= {prop['maxLength']}")

        if comments:
            comments_data = "; ".join(comments)
            if len(comments_data) > inline_threshold:
                # If the comments are long, put them on a separate line so they
                # don't wrap in the middle of a sentence.
                line = f"# {comments_data}\n{line}"
            else:
                line += "  # " + "; ".join(comments)

        lines.append(line)

    return "\n".join(lines)


def fetch_spec(server: str | None) -> dict[str, Any]:
    client = get_client(server)
    response = client.get("/openapi.json")
    response.raise_for_status()
    return response.json()
