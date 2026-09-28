"""
Drives each question widget through Textual's `App.run_test()`/`Pilot`
harness and asserts the exact `Response` it hands to `on_response`. See
`dev/specs/to-do/question-widgets.md` for what's being proven and why.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
import mdq
from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import Input, RadioButton, RadioSet, SelectionList, TextArea

from codehood.widgets.questions import (
    EssayQuestion,
    EssayResponse,
    FillInQuestion,
    FillInResponse,
    MultipleChoiceQuestion,
    MultipleChoiceResponse,
    MultipleSelectionQuestion,
    MultipleSelectionResponse,
    NumericQuestion,
    NumericResponse,
    QuestionDocument,
    QuestionWidget,
    ShortAnswerQuestion,
    ShortAnswerResponse,
    TrueFalseQuestion,
    TrueFalseResponse,
    question_document,
)
from codehood.widgets.questions.controls import _ordered
from codehood.widgets.questions.responses import parse_numeric_text

#: A screen tall enough that no widget in this suite pushes its submit
#: button out of the visible region (`Vertical`/`Horizontal` default to
#: `height: 1fr`, so anything short of "auto" everywhere would silently
#: overflow -- see `docs/adr/0001-fill-in-blanks-render-below-the-stem.md`
#: for the sibling layout issue this suite caught).
SCREEN_SIZE = (80, 50)


def parse_question(text: str) -> QuestionDocument:
    """Parse MDQ source into the mapping a widget reads."""
    return question_document(mdq.parse(text, kind="question"))


class _Harness(App[None]):
    """Mounts exactly one `QuestionWidget` for a test to drive."""

    def __init__(self, widget: QuestionWidget) -> None:
        super().__init__()
        self.widget = widget

    def compose(self) -> ComposeResult:
        yield self.widget


def drive(
    widget: QuestionWidget,
    body: Callable[[Pilot[None], QuestionWidget], Awaitable[None]],
) -> None:
    """Mount `widget` in a headless app and run `body(pilot, widget)` against it."""

    async def main() -> None:
        app = _Harness(widget)
        async with app.run_test(size=SCREEN_SIZE) as pilot:
            await body(pilot, widget)

    asyncio.run(main())


async def submit(pilot: Pilot[None]) -> None:
    await pilot.click("#submit")
    await pilot.pause()


async def type_into(pilot: Pilot[None], control: Input, text: str) -> None:
    await pilot.click(control)
    for char in text:
        await pilot.press(char)


#
# multiple-choice
#


def test_multiple_choice_records_the_picked_id() -> None:
    document = parse_question("What is 2 + 2?\n\n* [ ] 3\n* [*] 4\n* [ ] 5\n")
    responses: list[MultipleChoiceResponse] = []
    widget = MultipleChoiceQuestion(document, on_response=responses.append)

    async def body(pilot: Pilot[None], widget: QuestionWidget) -> None:
        buttons = list(widget.query(RadioButton))
        await pilot.click(buttons[1])  # "4"
        await pilot.pause()
        await submit(pilot)

    drive(widget, body)
    assert responses == [MultipleChoiceResponse("four")]


def test_multiple_choice_skip_is_a_none_choice_id() -> None:
    document = parse_question("What is 2 + 2?\n\n* [ ] 3\n* [*] 4\n* [ ] 5\n")
    responses: list[MultipleChoiceResponse] = []
    widget = MultipleChoiceQuestion(document, on_response=responses.append)

    drive(widget, lambda pilot, widget: submit(pilot))
    assert responses == [MultipleChoiceResponse(None)]


#
# multiple-selection
#


def test_multiple_selection_records_every_ticked_id() -> None:
    document = parse_question(
        "Which of these are primary colors?\n\n* [x] Red\n* [ ] Green\n* [x] Blue\n"
    )
    responses: list[MultipleSelectionResponse] = []
    widget = MultipleSelectionQuestion(document, on_response=responses.append)

    async def body(pilot: Pilot[None], widget: QuestionWidget) -> None:
        selection_list = widget.query_one(SelectionList)
        selection_list.focus()
        await pilot.pause()
        await pilot.press("space")  # Red
        await pilot.press("down", "down")
        await pilot.press("space")  # Blue
        await pilot.pause()
        await submit(pilot)

    drive(widget, body)
    assert responses == [MultipleSelectionResponse(frozenset({"red", "blue"}))]


#
# true-false
#


def test_true_false_leaves_an_unjudged_statement_out_of_answers() -> None:
    document = parse_question(
        "Judge each statement.\n\n* [T] The sky is blue.\n* [F] Fish can fly.\n"
    )
    responses: list[TrueFalseResponse] = []
    widget = TrueFalseQuestion(document, on_response=responses.append)

    async def body(pilot: Pilot[None], widget: QuestionWidget) -> None:
        first_set = widget.query(RadioSet)[0]
        await pilot.click(list(first_set.query(RadioButton))[0])  # judge it True
        await pilot.pause()
        await submit(pilot)

    drive(widget, body)
    assert responses == [TrueFalseResponse({"the-sky-is-blue": True})]


#
# numeric
#


def test_numeric_parses_a_well_formed_value() -> None:
    document = parse_question("Compute 2 + 2.\n\n[numeric]: 4\n")
    responses: list[NumericResponse] = []
    widget = NumericQuestion(document, on_response=responses.append)

    async def body(pilot: Pilot[None], widget: QuestionWidget) -> None:
        await type_into(pilot, widget.query_one(Input), "4")
        await submit(pilot)

    drive(widget, body)
    assert responses == [NumericResponse("4", 4.0)]


def test_numeric_malformed_input_keeps_text_but_value_is_none() -> None:
    document = parse_question("Compute 2 + 2.\n\n[numeric]: 4\n")
    responses: list[NumericResponse] = []
    widget = NumericQuestion(document, on_response=responses.append)

    async def body(pilot: Pilot[None], widget: QuestionWidget) -> None:
        await type_into(pilot, widget.query_one(Input), "abc")
        await submit(pilot)

    drive(widget, body)
    assert responses == [NumericResponse("abc", None)]


#
# short-answer
#


def test_short_answer_records_typed_text() -> None:
    document = parse_question(
        "What is the capital of Brazil?\n\n[short-answer]: Brasília\n"
    )
    responses: list[ShortAnswerResponse] = []
    widget = ShortAnswerQuestion(document, on_response=responses.append)

    async def body(pilot: Pilot[None], widget: QuestionWidget) -> None:
        await type_into(pilot, widget.query_one(Input), "Brasilia")
        await submit(pilot)

    drive(widget, body)
    assert responses == [ShortAnswerResponse("Brasilia")]


#
# essay
#


def test_essay_records_typed_text() -> None:
    document = parse_question("Explain your reasoning.\n\n[essay]\n")
    responses: list[EssayResponse] = []
    widget = EssayQuestion(document, on_response=responses.append)

    async def body(pilot: Pilot[None], widget: QuestionWidget) -> None:
        text_area = widget.query_one(TextArea)
        text_area.focus()
        await pilot.pause()
        for char in "because":
            await pilot.press(char)
        await submit(pilot)

    drive(widget, body)
    assert responses == [EssayResponse("because")]


#
# fill-in
#


def test_fill_in_produces_one_typed_response_per_blank() -> None:
    document = parse_question(
        "The capital of Brazil is [^capital/short-answer] and 2 + 2 is [^sum/numeric].\n\n"
        "[^capital/short-answer]: Brasília\n\n[^sum/numeric]: 4\n"
    )
    responses: list[FillInResponse] = []
    widget = FillInQuestion(document, on_response=responses.append)

    async def body(pilot: Pilot[None], widget: QuestionWidget) -> None:
        inputs = list(widget.query(Input))
        await type_into(pilot, inputs[0], "Brasilia")
        await type_into(pilot, inputs[1], "4")
        await submit(pilot)

    drive(widget, body)
    assert responses == [
        FillInResponse(
            {
                "capital": ShortAnswerResponse("Brasilia"),
                "sum": NumericResponse("4", 4.0),
            }
        )
    ]


#
# parse_numeric_text
#


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("4", 4.0),
        ("3.5", 3.5),
        ("-2", -2.0),
        ("3/4", 0.75),
        ("-1/4", -0.25),
        ("", None),
        ("   ", None),
        ("abc", None),
        ("1/0", None),
    ],
)
def test_parse_numeric_text(text: str, expected: float | None) -> None:
    assert parse_numeric_text(text) == expected


#
# shuffle
#


def test_shuffle_varies_the_rendered_order() -> None:
    """
    Not a one-shot flaky check: `random.sample` over 6 items has a
    1/720 chance of landing back on the original order, so asserting at
    least one of 50 draws differs is effectively certain to pass and still
    proves shuffling is wired in, not a no-op.
    """

    choices = [{"id": str(i), "text": str(i)} for i in range(6)]
    orders = {
        tuple(c["id"] for c in _ordered(choices, shuffle=True)) for _ in range(50)
    }
    assert len(orders) > 1


def test_shuffle_false_keeps_document_order() -> None:
    choices = [{"id": str(i), "text": str(i)} for i in range(6)]
    for _ in range(10):
        assert _ordered(choices, shuffle=False) == choices
