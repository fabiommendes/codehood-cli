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
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import mdq
from mdq.models import Attachment, CodeQuestion
from pydantic import ValidationError

from ..repo.diff import FileType
from ..repo.file_tracker import scan_files
from .errors import QuestionParseError, QuestionSourceError, SlugCollisionError
from .resource import front_matter_str, slugify, slugify_text, split_front_matter

__all__ = [
    "DRAFT_MARK",
    "MAX_UPLOAD_BYTES",
    "AnyQuestion",
    "InvalidQuestion",
    "LinkedFile",
    "LocalQuestionStatus",
    "QuestionFile",
    "QuestionStatus",
    "peek_id",
    "question_slug",
    "question_status",
    "question_version",
    "read_attachments",
    "resolve_exam_sources",
    "resolve_test_sources",
    "scan_questions",
    "test_source_paths",
]

#: The discriminated union `mdq.parse` returns for a question.
type AnyQuestion = mdq.Question

#: The statuses a push reads from the server, in the order a push only moves
#: forward through: `HIDDEN` is set on the web and no file can undo it.
type QuestionStatus = Literal["DRAFT", "PUBLISHED", "HIDDEN"]

#: The statuses a file can declare, through `DRAFT_MARK`.
type LocalQuestionStatus = Literal["DRAFT", "PUBLISHED"]

#: A leading `_` on the file or on any directory above it marks a draft, and
#: is left out of the slug.
DRAFT_MARK = "_"

#: The largest file the server takes in one upload, in bytes.
MAX_UPLOAD_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class QuestionFile:
    """
    One file under `questions/`, already parsed, slugged, and hashed.
    """

    slug: str
    version: str
    question: AnyQuestion
    path: Path
    status: LocalQuestionStatus = "PUBLISHED"
    #: The files its linked test sources and attachments were read from.
    sources: tuple[Path, ...] = ()
    #: Attachment name -> sha-256 of the linked attachments' bytes.
    files: Mapping[str, str] = field(default_factory=dict)
    #: Sha-256 -> the file the bytes of that attachment are read from.
    blobs: Mapping[str, Path] = field(default_factory=dict)


@dataclass(frozen=True)
class LinkedFile:
    """
    A file a question or an exam links from its `## [attachments]` section,
    read off disk.
    """

    name: str
    path: Path
    data: bytes

    @property
    def sha256(self) -> str:
        """
        The hex sha-256 of the file's bytes, the name the server stores it under.
        """
        return hashlib.sha256(self.data).hexdigest()


@dataclass(frozen=True)
class InvalidQuestion:
    """
    A file under `questions/` that `mdq` refused, kept so the push reports it
    as a failure and leaves what the server holds under its slug alone.
    """

    slug: str
    path: Path
    reason: str


def question_version(raw: bytes) -> str:
    """
    Digest a question file's raw bytes into the `version` the server
    stores. For a `code` question, the bytes of its linked test files
    follow the file's.

    Unlike a resource's `ref`, which digests the parsed fields, a
    question's `version` digests the file itself -- see
    `dev/specs/to-do/push-questions.md`, "The hash rides in `version`,
    not `contentHash`". The `md5:` prefix names the recipe, so changing it
    later invalidates old versions loudly instead of colliding with them.
    """
    return f"md5:{hashlib.md5(raw).hexdigest()}"


def scan_questions(
    root: Path, exclude: Sequence[str] = ()
) -> Iterator[QuestionFile | InvalidQuestion]:
    """
    Walk `questions/` and yield one `QuestionFile` per file, or an
    `InvalidQuestion` for a file `mdq` refuses.

    Reuses the (fixed) `repo.file_tracker.scan_files` for the walk, so a
    subdirectory never becomes a question of its own. Files matching an
    `exclude` pattern are skipped without being read. The `id` in a
    question's front matter is its slug; without one, the slug is the
    flattened path, without the `_` that marks a draft.

    Raises:
        SlugCollisionError: two or more files want the same slug. Raised
            eagerly, after reading front matter but before any file is
            parsed or any network call is made.
    """
    base = root / "questions"
    by_slug: dict[str, list[Path]] = defaultdict(list)
    entries: list[tuple[str, Path]] = []

    for file in scan_files(root, exclude):
        if file.type is not FileType.QUESTION or file.excluded:
            continue
        rel_path = Path(file.name)
        slug = question_slug(peek_id(base / rel_path), rel_path)
        by_slug[slug].append(rel_path)
        entries.append((slug, rel_path))

    collisions = {slug: paths for slug, paths in by_slug.items() if len(paths) > 1}
    if collisions:
        raise SlugCollisionError(collisions)

    for slug, rel_path in entries:
        try:
            yield read_question(base, slug, rel_path)
        except QuestionParseError as exc:
            yield InvalidQuestion(slug=slug, path=exc.path, reason=str(exc.cause))


def question_slug(question_id: str | None, rel_path: Path) -> str:
    """
    The slug a question file pushes under: its `id`, slugified, or else its
    flattened path under `questions/` without draft marks.

    `_rascunhos/_laco.md` and `rascunhos/laco.md` share the slug
    `rascunhos-laco`, so publishing by renaming keeps the question.
    """
    if question_id:
        return slugify_text(question_id)
    return slugify(Path(*(part.removeprefix(DRAFT_MARK) for part in rel_path.parts)))


def question_status(rel_path: Path) -> LocalQuestionStatus:
    """
    `DRAFT` when the file or a directory under `questions/` starts with `_`,
    `PUBLISHED` otherwise.
    """
    if any(part.startswith(DRAFT_MARK) for part in rel_path.parts):
        return "DRAFT"
    return "PUBLISHED"


def peek_id(path: Path) -> str | None:
    """
    The `id` in a question file's front matter, read without `mdq`; `None`
    when absent or the file cannot be read as text.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    front_matter, _ = split_front_matter(text)
    return front_matter_str(front_matter, "id")


#
# Utilities
#
def read_question(base: Path, slug: str, rel_path: Path) -> QuestionFile:
    """
    Read, parse, and hash one question file off disk.

    A linked test source of a `code` question is read and resolved here.

    Raises:
        QuestionParseError: `mdq.parse` refuses the file, or a test file
            breaks the rules of the annotations.
        QuestionSourceError: a linked test file cannot be read.
    """
    path = base / rel_path
    raw = path.read_bytes()
    try:
        question = mdq.parse(raw.decode("utf-8"), kind="question", ids="fill")
        question = resolve_test_sources(question, path.parent)
    except (mdq.InvalidDocument, ValidationError) as exc:
        raise QuestionParseError(path, exc) from exc
    sources = test_source_paths(question, path.parent)
    linked = read_attachments(question.attachments, path.parent)
    # A linked test or attachment file is part of the question: editing it
    # alone must change the version, or the push would skip the question.
    content = raw + b"".join(
        b"\0" + data
        for data in (
            *(source.read_bytes() for source in sources),
            *(item.data for item in linked),
        )
    )
    return QuestionFile(
        slug=slug,
        version=question_version(content),
        question=question,
        path=path,
        status=question_status(rel_path),
        sources=(*sources, *(item.path for item in linked)),
        files={item.name: item.sha256 for item in linked},
        blobs={item.sha256: item.path for item in linked},
    )


def read_attachments(
    attachments: Sequence[Attachment] | None, base: Path
) -> tuple[LinkedFile, ...]:
    """
    Read the files the linked attachments point to, in the order of the
    document; fenced attachments carry their own text and are skipped.

    Links are relative to `base`, the directory of the file that holds them.

    Raises:
        QuestionSourceError: a linked file is missing, cannot be read, or is
            over `MAX_UPLOAD_BYTES`.
    """
    found: list[LinkedFile] = []
    for attachment in attachments or ():
        if attachment.origin is None:
            continue
        path = base / attachment.origin
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise QuestionSourceError(path, attachment.origin, exc) from exc
        if len(data) > MAX_UPLOAD_BYTES:
            limit = MAX_UPLOAD_BYTES // (1024 * 1024)
            reason = ValueError(f"{len(data)} bytes, over the {limit} MiB limit")
            raise QuestionSourceError(path, attachment.origin, reason)
        found.append(LinkedFile(attachment.name, path, data))
    return tuple(found)


def test_source_paths(question: AnyQuestion, base: Path) -> tuple[Path, ...]:
    """
    The files a `code` question links as test sources, relative to `base`
    and without repeats; empty for any other question.
    """
    if not isinstance(question, CodeQuestion):
        return ()
    origins = dict.fromkeys(
        source.origin for source in question.tests or [] if source.origin
    )
    return tuple(base / origin for origin in origins)


def resolve_test_sources(question: AnyQuestion, base: Path) -> AnyQuestion:
    """
    Read the linked test sources of a `code` question and resolve them with
    `CodeQuestion.resolve`; any other question comes back unchanged.

    Links are relative to `base`, the directory of the file that holds the
    question. A source with a fenced `text` is not touched.

    Raises:
        QuestionSourceError: a linked file is missing or is not UTF-8 text.
        pydantic.ValidationError: a file breaks the rules of the annotations.
    """
    if not isinstance(question, CodeQuestion):
        return question
    texts: dict[str, str] = {}
    for source in question.tests or []:
        if source.origin is None or source.text is not None:
            continue
        path = base / source.origin
        try:
            texts[source.origin] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise QuestionSourceError(path, source.origin, exc) from exc
    return question.resolve(texts)


def resolve_exam_sources(exam: mdq.Exam, base: Path) -> mdq.Exam:
    """
    Resolve the test sources of every inline question of an exam, with links
    relative to `base`, the directory of the exam file.

    Included questions are left alone: they come from a bank, which resolves
    them against their own files.

    Raises:
        QuestionSourceError: a linked file is missing or is not UTF-8 text.
        pydantic.ValidationError: a file breaks the rules of the annotations.
    """
    entries = [
        resolve_test_sources(entry, base) if isinstance(entry, CodeQuestion) else entry
        for entry in exam.questions
    ]
    return exam.model_copy(update={"questions": entries})
