"""
Translates a parsed `mdq` question into the JSON the server's `question`
union accepts.

`mdq` moves faster than the server's copy of the format, so the question
`mdq.parse` returns can carry fields the server rejects as unknown keys
(`Unrecognized key: "diacritics"`) or values it types more narrowly
(`shuffle: "inherit"` where the server wants a boolean). The translation lives
here, apart from the HTTP plumbing in `run.py`, so each gap is one line in a
table. What the translation drops is lost on the server side: it grades with
the fields it knows.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import mdq

__all__ = ["DROPPED_QUESTION_KEYS", "wire_question"]

#: Question fields the server has no place for, whatever their value.
DROPPED_QUESTION_KEYS = (
    "weight",
    "grading",
    "diacritics",
    "unmatched",
    "incorrectFeedback",
)

#: Short-answer blank fields the server has no place for.
DROPPED_SHORT_ANSWER_BLANK_KEYS = ("reject", "preAccept", "preReject")


def wire_question(question: mdq.Question) -> dict[str, Any]:
    """
    Return `question` as the plain mapping the server's `question` union takes.

    Omitted optional fields stay omitted: the server rejects an explicit
    `null`. Fields it does not know are dropped, `shuffle: "inherit"` is
    omitted (outside an exam it means `false`, which is also the server's
    reading of an absent value) and a fill-in's short-answer blank
    has its `accept` patterns flattened into the `oneOf` strings the server
    stores.
    """
    payload = question.model_dump(mode="json", by_alias=True, exclude_none=True)
    for key in DROPPED_QUESTION_KEYS:
        payload.pop(key, None)
    if payload.get("shuffle") == "inherit":
        del payload["shuffle"]
    if "blanks" in payload:
        payload["blanks"] = [_wire_blank(blank) for blank in payload["blanks"]]
    return payload


#
# Utilities
#
def _wire_blank(blank: Mapping[str, Any]) -> dict[str, Any]:
    """One fill-in blank, in the shape the server stores."""
    wire = dict(blank)
    if wire["type"] != "short-answer":
        return wire
    for key in DROPPED_SHORT_ANSWER_BLANK_KEYS:
        wire.pop(key, None)
    if "accept" in wire:
        wire["oneOf"] = [entry["pattern"] for entry in wire.pop("accept")]
    return wire
