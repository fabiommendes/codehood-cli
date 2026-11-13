"""
Typed responses produced by the question widgets in this package.

A `Response` captures only what a student marked -- never a score, a
correctness judgement, or anything read from a question's answer key. See
`dev/specs/to-do/question-widgets.md` ("The widget never reads a question's
answer key"): grading is entirely the `on_response` callback's job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "BlankResponse",
    "EssayResponse",
    "FillInResponse",
    "MultipleChoiceResponse",
    "MultipleSelectionResponse",
    "NumericResponse",
    "Response",
    "ShortAnswerResponse",
    "TrueFalseResponse",
    "parse_numeric_text",
]


@dataclass(frozen=True, slots=True)
class MultipleChoiceResponse:
    """The single choice a student picked, or `None` if they skipped it."""

    choice_id: str | None


@dataclass(frozen=True, slots=True)
class MultipleSelectionResponse:
    """The choices a student ticked. Empty is a valid response, not a skip."""

    choice_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class TrueFalseResponse:
    """
    One judgement per statement a student actually judged.

    A statement id missing from `answers` is an abstention
    (`mdq.spec/CONTEXT.md`: "leaving one individual true-false statement
    unjudged"), distinct from a `False` entry.
    """

    answers: dict[str, bool]


@dataclass(frozen=True, slots=True)
class NumericResponse:
    """
    `text` is exactly what the student typed; `value` is `None` when `text`
    doesn't parse as a number -- a malformed response, never a wrong one
    (`mdq.spec/CONTEXT.md`).
    """

    text: str
    value: float | None


@dataclass(frozen=True, slots=True)
class ShortAnswerResponse:
    text: str


@dataclass(frozen=True, slots=True)
class EssayResponse:
    text: str


#: What a single fill-in blank can produce, reusing the response type of
#: whichever question type the blank is graded like.
BlankResponse = MultipleChoiceResponse | ShortAnswerResponse | NumericResponse


@dataclass(frozen=True, slots=True)
class FillInResponse:
    """One typed response per blank id, keyed exactly like `document["blanks"]`."""

    blanks: dict[str, BlankResponse]


Response = (
    MultipleChoiceResponse
    | MultipleSelectionResponse
    | TrueFalseResponse
    | NumericResponse
    | ShortAnswerResponse
    | EssayResponse
    | FillInResponse
)


_FRACTION_RE = re.compile(r"^(?P<sign>[+-])?(?P<num>\d+)/(?P<den>\d+)$")


def parse_numeric_text(text: str) -> float | None:
    """
    Parse `text` as the numeric domain mdq accepts: a plain float, or an
    `a/b` fraction. Returns `None` for anything else -- a malformed
    response, not a wrong one.

    Args:
        text: Exactly what the student typed.

    Returns:
        The parsed value, or `None` if `text` doesn't parse.

    Example:
        >>> parse_numeric_text("3.5")
        3.5
        >>> parse_numeric_text("3/4")
        0.75
        >>> parse_numeric_text("abc") is None
        True
    """

    text = text.strip()
    if not text:
        return None
    if m := _FRACTION_RE.match(text):
        den = int(m.group("den"))
        if den == 0:
            return None
        value = int(m.group("num")) / den
        return -value if m.group("sign") == "-" else value
    try:
        return float(text)
    except ValueError:
        return None
