"""
Exceptions `codehood/push/` raises before it touches the network.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

__all__ = [
    "CalendarError",
    "QuestionParseError",
    "QuestionSourceError",
    "RepositoryError",
    "ResourceFileError",
    "ResourceLinkError",
    "SlugCollisionError",
]


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

    Raised by `question.read_question`; `scan_questions` turns it into an
    `InvalidQuestion`, so one bad file fails alone.
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


class QuestionSourceError(Exception):
    """
    A file linked by a question or an exam (a test source or an attachment)
    cannot be read, or is over the upload limit.

    Raised by `question.resolve_test_sources` and `question.read_attachments`
    before any network call, refusing the whole push: the document cannot be
    sent without the files it links, and the server must not keep a version
    that lacks them.
    """

    def __init__(self, path: Path, origin: str, cause: Exception) -> None:
        """
        Args:
            path: The test file the link resolves to.
            origin: The link target, as written in the question.
            cause: The `OSError` or `UnicodeDecodeError` reading it raised,
                or the `ValueError` saying it is too large.
        """
        self.path = path
        self.origin = origin
        self.cause = cause
        reason = "file not found" if isinstance(cause, FileNotFoundError) else cause
        super().__init__(f"cannot read linked file {origin!r} ({path}): {reason}")


class CalendarError(Exception):
    """
    `calendar.md` does not parse, or asks for something impossible.

    Raised by `calendar.parse_calendar` and `calendar.allocate` before any
    network call, refusing the whole push: the calendar sets the course's
    own dates, so there is no partial push that still makes sense.
    """


class ResourceLinkError(Exception):
    """
    A `calendar.md` lesson links to `resources/` in a way that cannot be
    pushed.

    Raised by `links.attach_resources` before any network call, in two
    cases: a link targets a path under `resources/` that no scanned
    resource has, or one resource is linked from two different lessons.
    The message names the offending path and, for the second case, both
    lessons.
    """


class RepositoryError(Exception):
    """
    A folder under `repositories/` cannot be pushed as it is.

    Raised by `repository.scan_repositories` before any network call: a loose
    file in `repositories/`, a folder whose name is not a slug, a symlink,
    a file over the upload limit, or a folder with nothing to publish. The
    message names the offending path.
    """


class ResourceFileError(Exception):
    """
    A file under `resources/` cannot be read as its kind says it should.

    Raised by `resource.scan_resources` before any network call: an
    `info.yaml` that is not a mapping of existing file names to known keys,
    or a `.url` file with no `http(s)` URI. The message names the file.
    """

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")
