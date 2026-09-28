"""
The pure core that turns files under `questions/` into `QuestionFile`s.

Nothing here touches the network or the server's idea of what it holds --
see `plan.py` for that half. `mdq` is the parser of record: the server's
`QuestionCreate.question` is a structured, discriminated union, not
Markdown, so `mdq.parse` turns a file's text into the shape the
server wants and `run.py` translates it into the generated request model.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import mdq

from ..repo.diff import FileType
from ..repo.file_tracker import scan_files
from .errors import QuestionParseError, SlugCollisionError
from .resource import slugify

__all__ = ["AnyQuestion", "QuestionFile", "question_version", "scan_questions"]

#: The discriminated union `mdq.parse` returns for a question.
type AnyQuestion = mdq.Question


@dataclass(frozen=True)
class QuestionFile:
    """
    One file under `questions/`, already parsed, slugged, and hashed.
    """

    slug: str
    version: str
    question: AnyQuestion
    path: Path


def question_version(raw: bytes) -> str:
    """
    Digest a question file's raw bytes into the `version` the server
    stores.

    Unlike a resource's `ref`, which digests the parsed fields, a
    question's `version` digests the file itself -- see
    `dev/specs/to-do/push-questions.md`, "The hash rides in `version`,
    not `contentHash`". The `md5:` prefix names the recipe, so changing it
    later invalidates old versions loudly instead of colliding with them.
    """
    return f"md5:{hashlib.md5(raw).hexdigest()}"


def scan_questions(root: Path) -> Iterator[QuestionFile]:
    """
    Walk `questions/` and yield one `QuestionFile` per file.

    Reuses the (fixed) `repo.file_tracker.scan_files` for the walk, so a
    subdirectory never becomes a question of its own.

    Raises:
        SlugCollisionError: two or more files flatten to the same slug.
            Raised eagerly, before any file is parsed or any network call
            is made.
        QuestionParseError: the first file `mdq.parse` refuses.
    """
    base = root / "questions"
    by_slug: dict[str, list[Path]] = defaultdict(list)
    entries: list[tuple[str, Path]] = []

    for file in scan_files(root):
        if file.type is not FileType.QUESTION:
            continue
        rel_path = Path(file.name)
        slug = slugify(rel_path)
        by_slug[slug].append(rel_path)
        entries.append((slug, rel_path))

    collisions = {slug: paths for slug, paths in by_slug.items() if len(paths) > 1}
    if collisions:
        raise SlugCollisionError(collisions)

    for slug, rel_path in entries:
        yield _read_question(base, slug, rel_path)


#
# Utilities
#
def _read_question(base: Path, slug: str, rel_path: Path) -> QuestionFile:
    """
    Read, parse, and hash one question file off disk.
    """
    path = base / rel_path
    raw = path.read_bytes()
    try:
        question = mdq.parse(raw.decode("utf-8"), kind="question", ids="fill")
    except mdq.InvalidDocument as exc:
        raise QuestionParseError(path, exc) from exc
    return QuestionFile(
        slug=slug,
        version=question_version(raw),
        question=question,
        path=path,
    )
