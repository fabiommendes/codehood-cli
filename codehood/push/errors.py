"""
Exceptions `codehood/push/` raises before it touches the network.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

__all__ = ["CalendarError", "QuestionParseError", "SlugCollisionError"]


class SlugCollisionError(Exception):
    """
    Two or more files under `resources/` or `questions/` flatten to the
    same slug.

    Raised by `scan_resources`/`scan_questions` before any network call,
    refusing the whole push: it does not guess which file was meant, and
    does not push a partial repository on the way to an error.
    """

    def __init__(self, collisions: Mapping[str, list[Path]]) -> None:
        """
        Args:
            collisions: Every contested slug mapped to every file that
                wants it.
        """
        self.collisions = dict(collisions)
        detail = "; ".join(
            f"{slug!r} wanted by {', '.join(str(path) for path in paths)}"
            for slug, paths in self.collisions.items()
        )
        super().__init__(f"colliding slugs: {detail}")


class QuestionParseError(Exception):
    """
    `mdq` refused to parse a file under `questions/`.

    Raised by `scan_questions` on the first file `mdq.parse`
    refuses, refusing the whole push for the same reason a slug collision
    does: push does not upload half a question bank on the way to an
    error.
    """

    def __init__(self, path: Path, cause: Exception) -> None:
        """
        Args:
            path: The question file `mdq` refused.
            cause: The `mdq.InvalidDocument` it raised.
        """
        self.path = path
        self.cause = cause
        super().__init__(f"{path}: {cause}")


class CalendarError(Exception):
    """
    `calendar.md` does not parse, or asks for something impossible.

    Raised by `calendar.parse_calendar` and `calendar.allocate` before any
    network call, refusing the whole push: the calendar sets the course's
    own dates, so there is no partial push that still makes sense.
    """
