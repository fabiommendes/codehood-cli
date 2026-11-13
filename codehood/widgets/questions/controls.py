"""
Reusable input controls shared across question widgets.

Each control renders one answer-input shape and exposes what the student
entered as `.result` -- nothing here knows what a "correct" answer looks
like, only what shape a response takes. `base.QuestionWidget` composes one
control per question; `fill_in.py` composes one per blank.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Input, Label, RadioButton, RadioSet, SelectionList, Static
from textual.widgets.selection_list import Selection

from .responses import parse_numeric_text

__all__ = [
    "ChoiceControl",
    "Control",
    "MultiChoiceControl",
    "NumericControl",
    "ShortAnswerControl",
    "TrueFalseControl",
]


def _ordered(
    items: Sequence[Mapping[str, Any]], *, shuffle: bool
) -> list[Mapping[str, Any]]:
    """Return `items` in the order a control should render them."""

    return random.sample(list(items), len(items)) if shuffle else list(items)


class Control(Widget):
    """Base for a control that exposes what the student entered as `.result`."""

    DEFAULT_CSS = """
    Control {
        height: auto;
    }
    """

    @property
    def result(self) -> Any:
        """What the student entered, in whatever shape this control produces."""
        raise NotImplementedError


class ChoiceControl(Control):
    """
    Exactly one choice, out of `choices`, picked via a `RadioSet`.

    Backs `multiple-choice` questions and `fill-in`'s choice blanks.
    """

    def __init__(
        self,
        choices: Sequence[Mapping[str, Any]],
        *,
        shuffle: bool = False,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._choices = _ordered(choices, shuffle=shuffle)

    def compose(self) -> ComposeResult:
        with RadioSet():
            for choice in self._choices:
                yield RadioButton(choice["text"])

    @property
    def result(self) -> str | None:
        """The picked choice's `id`, or `None` if nothing was picked."""

        index = self.query_one(RadioSet).pressed_index
        return self._choices[index]["id"] if index >= 0 else None


class MultiChoiceControl(Control):
    """Any number of `choices`, picked via a `SelectionList`."""

    def __init__(
        self,
        choices: Sequence[Mapping[str, Any]],
        *,
        shuffle: bool = False,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._choices = _ordered(choices, shuffle=shuffle)

    def compose(self) -> ComposeResult:
        yield SelectionList(
            *(Selection(choice["text"], choice["id"]) for choice in self._choices)
        )

    @property
    def result(self) -> frozenset[str]:
        return frozenset(self.query_one(SelectionList).selected)


class TrueFalseControl(Control):
    """
    One statement per row, each judged independently via its own two-option
    `RadioSet`. A row never clicked stays out of `.result` -- an abstention,
    not a `False`.
    """

    DEFAULT_CSS = """
    TrueFalseControl .statement {
        height: auto;
    }
    """

    def __init__(
        self,
        statements: Sequence[Mapping[str, Any]],
        *,
        shuffle: bool = False,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._statements = _ordered(statements, shuffle=shuffle)

    def compose(self) -> ComposeResult:
        for statement in self._statements:
            with Vertical(classes="statement"):
                yield Static(statement["text"])
                with RadioSet(id=self._set_id(statement["id"])):
                    yield RadioButton("True")
                    yield RadioButton("False")

    @staticmethod
    def _set_id(statement_id: str) -> str:
        return f"statement-{statement_id}"

    @property
    def result(self) -> dict[str, bool]:
        answers: dict[str, bool] = {}
        for statement in self._statements:
            index = self.query_one(
                f"#{self._set_id(statement['id'])}", RadioSet
            ).pressed_index
            if index == 0:
                answers[statement["id"]] = True
            elif index == 1:
                answers[statement["id"]] = False
        return answers


class NumericControl(Control):
    """A single numeric entry, parsed on read rather than as-you-type."""

    DEFAULT_CSS = """
    NumericControl Horizontal {
        height: auto;
    }
    """

    def __init__(self, *, unit: str | None = None, id: str | None = None) -> None:
        super().__init__(id=id)
        self._unit = unit

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Input(placeholder="answer", id="value")
            if self._unit:
                yield Label(self._unit)

    @property
    def result(self) -> tuple[str, float | None]:
        """`(text, value)` -- `value` is `None` for a malformed response."""

        text = self.query_one("#value", Input).value
        return text, parse_numeric_text(text)


class ShortAnswerControl(Control):
    """A single line of free text."""

    def compose(self) -> ComposeResult:
        yield Input(placeholder="answer", id="value")

    @property
    def result(self) -> str:
        return self.query_one("#value", Input).value
