"""
Translates a parsed `mdq` question into the JSON the server's `question`
union accepts.

The server stores questions in the format of the mdq spec, so the translation
is the document itself, with the omitted optional fields left out.
"""

from __future__ import annotations

from typing import Any

import mdq

__all__ = ["wire_question"]

#: Lists the mdq schema requires to be absent or non-empty.
_NON_EMPTY_LISTS = ("extra", "accept", "reject")


def wire_question(question: mdq.Question) -> dict[str, Any]:
    """
    Return `question` as the plain mapping the server's `question` union takes.

    Omitted optional fields stay omitted: the server rejects an explicit
    `null`, and an empty `extra`, `accept` or `reject` list, which `mdq`
    models default to but the mdq schema requires to have items.
    """
    payload = question.model_dump(mode="json", by_alias=True, exclude_none=True)
    for key in _NON_EMPTY_LISTS:
        if payload.get(key) == []:
            del payload[key]
    return payload
