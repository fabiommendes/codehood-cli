"""
`fill-in`: a stem with named blanks, each graded like a smaller
multiple-choice, short-answer, or numeric question.

Blanks render below the stem rather than inside it -- see
`docs/adr/0001-fill-in-blanks-render-below-the-stem.md`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label

from .base import QuestionWidget
from .controls import ChoiceControl, Control, NumericControl, ShortAnswerControl
from .responses import (
    BlankResponse,
    FillInResponse,
    MultipleChoiceResponse,
    NumericResponse,
    ShortAnswerResponse,
)

__all__ = ["FillInQuestion"]

#: Matches an inline blank reference in a fill-in stem, e.g. `[^capital]`.
_BLANK_REF_RE = re.compile(r"\[\^([a-zA-Z0-9](?:[-_][a-zA-Z0-9]+)*)\]")


class FillInQuestion(QuestionWidget):
    DEFAULT_CSS = """
    FillInQuestion #control {
        height: auto;
    }
    """

    def render_stem(self) -> str:
        return _BLANK_REF_RE.sub(
            lambda m: f"**[[{m.group(1)}]]**", self.document["stem"]
        )

    def compose_body(self) -> ComposeResult:
        shuffle = self.shuffle
        with Vertical(id="control"):
            for blank in self.document["blanks"]:
                yield Label(f"[[{blank['id']}]]")
                yield _blank_control(blank, shuffle=shuffle)

    def build_response(self) -> FillInResponse:
        blanks: dict[str, BlankResponse] = {}
        for blank in self.document["blanks"]:
            control = self.query_one(f"#{_control_id(blank['id'])}", Control)
            blanks[blank["id"]] = _blank_response(blank, control)
        return FillInResponse(blanks)


def _control_id(blank_id: str) -> str:
    return f"blank-{blank_id}"


def _blank_control(blank: Mapping[str, Any], *, shuffle: bool) -> Control:
    control_id = _control_id(blank["id"])
    if blank["type"] == "multiple-choice":
        return ChoiceControl(blank["choices"], shuffle=shuffle, id=control_id)
    if blank["type"] == "numeric":
        return NumericControl(unit=blank.get("unit"), id=control_id)
    return ShortAnswerControl(id=control_id)


def _blank_response(blank: Mapping[str, Any], control: Control) -> BlankResponse:
    if blank["type"] == "multiple-choice":
        return MultipleChoiceResponse(control.result)
    if blank["type"] == "numeric":
        text, value = control.result
        return NumericResponse(text, value)
    return ShortAnswerResponse(control.result)
