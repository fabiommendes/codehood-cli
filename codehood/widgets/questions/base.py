"""
`QuestionWidget`: the shared shape every question-type widget in this
package follows.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import mdq
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Button, Markdown

from .responses import Response

__all__ = ["QuestionWidget", "QuestionDocument", "question_document"]

#: A question as plain data, built by `question_document` -- this package
#: never parses MDQ source itself.
QuestionDocument = Mapping[str, Any]


def question_document(question: mdq.Question) -> QuestionDocument:
    """
    Return `question` as the mapping a widget reads, with an id on every
    choice.
    """
    return question.with_ids().model_dump(mode="json", exclude_none=True)


class QuestionWidget(Widget):
    """
    One interactive MDQ question.

    Renders `preamble`/`stem`/`epilogue` as Markdown around whatever
    `compose_body` contributes, and turns a submit press into a call to
    `on_response` with the `Response` `build_response` produces.
    `on_response` is a plain callback, not a Textual message -- see
    `dev/specs/to-do/question-widgets.md`.

    Never reads a choice's `score`/`answer`, a short-answer's `oneOf`, an
    essay's `answerKey`, or any other answer-key field, even though
    `self.document` carries them. Grading is the `on_response` callback's
    business entirely.
    """

    DEFAULT_CSS = """
    QuestionWidget {
        height: auto;
    }
    QuestionWidget .stem {
        margin: 1 0;
    }
    QuestionWidget #submit {
        margin-top: 1;
    }
    """

    def __init__(
        self,
        document: QuestionDocument,
        *,
        on_response: Callable[[Response], None] | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.document = document
        self.on_response = on_response

    def compose(self) -> ComposeResult:
        with Vertical():
            if preamble := self.document.get("preamble"):
                yield Markdown(preamble, classes="preamble")
            yield Markdown(self.render_stem(), classes="stem")
            yield from self.compose_body()
            if epilogue := self.document.get("epilogue"):
                yield Markdown(epilogue, classes="epilogue")
            yield Button("Submit", id="submit", variant="primary")

    def render_stem(self) -> str:
        """The stem's Markdown source. Overridden by `FillInQuestion`."""

        return self.document["stem"]

    def compose_body(self) -> ComposeResult:
        """Yield the control(s) the student answers through."""
        raise NotImplementedError
        yield  # pragma: no cover - makes this a generator function

    def build_response(self) -> Response:
        """Read the composed control(s) and produce this question's `Response`."""
        raise NotImplementedError

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self.submit()

    def submit(self) -> None:
        """Build a `Response` and hand it to `on_response`, if one was given."""

        response = self.build_response()
        if self.on_response is not None:
            self.on_response(response)
