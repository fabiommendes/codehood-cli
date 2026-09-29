"""
`codehood show`: open one MDQ question file in the interactive widget for its
type, for manually exercising `src/codehood_cli/widgets/questions/`.
Provisional -- see `dev/specs/to-do/question-widgets.md`'s "Out of scope".
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import mdq
from mdq.errors import MdqError
from mdq.parser import is_exam
from textual.app import ComposeResult
from textual.widgets import Footer

from ..theme import CodehoodApp
from ..widgets.questions import (
    QUESTION_WIDGETS,
    question_document,
    QuestionDocument,
    QuestionWidget,
    Response,
)
from .base import app

__all__ = ["show"]


@app.command()
def show(
    file: Annotated[Path, typer.Argument(help="Path to a single-question MDQ file.")],
) -> None:
    """
    Open a question file in its interactive widget and print what you submit.
    """
    text = file.read_text(encoding="utf-8")
    if is_exam(text):
        typer.echo(
            "error: `codehood show` only handles a single question, not an exam",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        document = question_document(mdq.parse(text, kind="question"))
    except MdqError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    widget_class = QUESTION_WIDGETS.get(document["type"])
    if widget_class is None:
        typer.echo(f"error: no widget for question type {document['type']!r}", err=True)
        raise typer.Exit(code=1)

    response = ShowApp(document, widget_class).run()
    if response is not None:
        typer.echo(response)


class ShowApp(CodehoodApp[Response]):
    """Mounts the widget for `document`'s type; exits with the `Response` it submits."""

    BINDINGS = [("q", "quit", "Quit")]
    TITLE = "codehood show"

    def __init__(
        self, document: QuestionDocument, widget_class: type[QuestionWidget]
    ) -> None:
        super().__init__()
        self.document = document
        self.widget_class = widget_class

    def compose(self) -> ComposeResult:
        yield self.widget_class(self.document, on_response=self.exit)
        yield Footer()
