"""
Interactive Textual widgets for answering one MDQ question at a time.

Not wired into any `codehood` command yet -- see
`dev/specs/to-do/question-widgets.md`.
"""

from __future__ import annotations

from .base import QuestionDocument, QuestionWidget, question_document
from .fill_in import FillInQuestion
from .responses import (
    BlankResponse,
    EssayResponse,
    FillInResponse,
    MultipleChoiceResponse,
    MultipleSelectionResponse,
    NumericResponse,
    Response,
    ShortAnswerResponse,
    TrueFalseResponse,
)
from .simple import (
    EssayQuestion,
    MultipleChoiceQuestion,
    MultipleSelectionQuestion,
    NumericQuestion,
    ShortAnswerQuestion,
    TrueFalseQuestion,
)

__all__ = [
    "QuestionWidget",
    "QuestionDocument",
    "question_document",
    "MultipleChoiceQuestion",
    "MultipleSelectionQuestion",
    "TrueFalseQuestion",
    "NumericQuestion",
    "ShortAnswerQuestion",
    "EssayQuestion",
    "FillInQuestion",
    "Response",
    "BlankResponse",
    "MultipleChoiceResponse",
    "MultipleSelectionResponse",
    "TrueFalseResponse",
    "NumericResponse",
    "ShortAnswerResponse",
    "EssayResponse",
    "FillInResponse",
    "QUESTION_WIDGETS",
]

#: Dispatch a parsed document to its widget class by `document["type"]` --
#: `QUESTION_WIDGETS[document["type"]](document, on_response=...)`.
QUESTION_WIDGETS: dict[str, type[QuestionWidget]] = {
    "multiple-choice": MultipleChoiceQuestion,
    "multiple-selection": MultipleSelectionQuestion,
    "true-false": TrueFalseQuestion,
    "numeric": NumericQuestion,
    "short-answer": ShortAnswerQuestion,
    "essay": EssayQuestion,
    "fill-in": FillInQuestion,
}
