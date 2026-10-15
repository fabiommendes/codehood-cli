"""
The six question types whose answer shape is exactly one control:
`multiple-choice`, `multiple-selection`, `true-false`, `numeric`,
`short-answer`, `essay`. `fill-in` composes several of the same controls per
blank -- see `fill_in.py`.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import TextArea

from .base import QuestionWidget
from .controls import (
    ChoiceControl,
    MultiChoiceControl,
    NumericControl,
    ShortAnswerControl,
    TrueFalseControl,
)
from .responses import (
    EssayResponse,
    MultipleChoiceResponse,
    MultipleSelectionResponse,
    NumericResponse,
    ShortAnswerResponse,
    TrueFalseResponse,
)

__all__ = [
    "MultipleChoiceQuestion",
    "MultipleSelectionQuestion",
    "TrueFalseQuestion",
    "NumericQuestion",
    "ShortAnswerQuestion",
    "EssayQuestion",
]


class MultipleChoiceQuestion(QuestionWidget):
    def compose_body(self) -> ComposeResult:
        yield ChoiceControl(
            self.document["choices"],
            shuffle=self.shuffle,
            id="control",
        )

    def build_response(self) -> MultipleChoiceResponse:
        control = self.query_one("#control", ChoiceControl)
        return MultipleChoiceResponse(control.result)


class MultipleSelectionQuestion(QuestionWidget):
    def compose_body(self) -> ComposeResult:
        yield MultiChoiceControl(
            self.document["choices"],
            shuffle=self.shuffle,
            id="control",
        )

    def build_response(self) -> MultipleSelectionResponse:
        control = self.query_one("#control", MultiChoiceControl)
        return MultipleSelectionResponse(control.result)


class TrueFalseQuestion(QuestionWidget):
    def compose_body(self) -> ComposeResult:
        yield TrueFalseControl(
            self.document["choices"],
            shuffle=self.shuffle,
            id="control",
        )

    def build_response(self) -> TrueFalseResponse:
        control = self.query_one("#control", TrueFalseControl)
        return TrueFalseResponse(control.result)


class NumericQuestion(QuestionWidget):
    def compose_body(self) -> ComposeResult:
        yield NumericControl(unit=self.document.get("unit"), id="control")

    def build_response(self) -> NumericResponse:
        control = self.query_one("#control", NumericControl)
        text, value = control.result
        return NumericResponse(text, value)


class ShortAnswerQuestion(QuestionWidget):
    def compose_body(self) -> ComposeResult:
        yield ShortAnswerControl(id="control")

    def build_response(self) -> ShortAnswerResponse:
        control = self.query_one("#control", ShortAnswerControl)
        return ShortAnswerResponse(control.result)


class EssayQuestion(QuestionWidget):
    """
    `input: code` gets a syntax-highlighted `TextArea` when `highlight`
    names a language Textual ships with; anything else -- `text`, `plain`,
    or an unrecognized `highlight` -- gets a plain one.
    """

    def compose_body(self) -> ComposeResult:
        text_area = TextArea(id="control")
        language = self.document.get("highlight")
        if (
            self.document.get("input") == "code"
            and language in text_area.available_languages
        ):
            text_area.language = language
        yield text_area

    def build_response(self) -> EssayResponse:
        control = self.query_one("#control", TextArea)
        return EssayResponse(control.text)
