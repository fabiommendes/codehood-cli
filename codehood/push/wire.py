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


def wire_question(question: mdq.Question) -> dict[str, Any]:
    """
    Return `question` as the plain mapping the server's `question` union takes.

    Omitted optional fields stay omitted: the server rejects an explicit
    `null`.
    """
    return question.model_dump(mode="json", by_alias=True, exclude_none=True)
