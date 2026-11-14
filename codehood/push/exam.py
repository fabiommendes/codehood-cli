"""
The pure core that turns files under `exams/` into `ExamFile`s.

Nothing here touches the network or the server's idea of what it holds --
see `plan.py` for that half. `mdq.parse` keeps `include:` and `includeAll:`
blocks unresolved, so this module resolves them against the questions the
repository holds, and sends each question of the exam as a reference by
slug. Questions written inline are returned as `QuestionFile`s of their own.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Collection, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import mdq
from mdq.errors import IncludeNotFound
from mdq.models import Attachment, Include, IncludeAll
from mdq.models._query import QuerySyntaxError, parse_query
from pydantic import JsonValue, ValidationError

from .errors import SlugCollisionError
from .question import (
    DRAFT_MARK,
    InvalidQuestion,
    QuestionFile,
    question_status,
    question_version,
    read_attachments,
    resolve_exam_sources,
    test_source_paths,
)
from .resource import (
    REF_PREFIX,
    front_matter_str,
    slugify_text,
    split_front_matter,
    title_from_filename,
)
from .wire import canonical_question, exam_payload

if TYPE_CHECKING:
    from .exclude import ExcludedFile

__all__ = [
    "EXAM_SUFFIXES",
    "LIVE_STATUSES",
    "ExamFile",
    "ExamStatus",
    "ExamType",
    "IgnoredExamPolicy",
    "InvalidExam",
    "LocalBank",
    "LocalExamStatus",
    "exam_duration",
    "exam_rev",
    "exam_scheduled_at",
    "exam_slug",
    "exam_status",
    "exam_type",
    "inline_questions",
    "peek_exam_slug",
    "scan_exams",
]

#: The types the server knows.
type ExamType = Literal["EXAM", "QUIZ", "PRACTICE"]

#: Every status the server reads an exam with, in the order an exam moves
#: through: `ONGOING` and `COMPLETED` are set on the server and no file can
#: undo them.
type ExamStatus = Literal["DRAFT", "SCHEDULED", "ONGOING", "COMPLETED"]

#: The statuses a file can declare.
type LocalExamStatus = Literal["DRAFT", "SCHEDULED"]

#: The statuses a push never moves an exam out of.
LIVE_STATUSES: frozenset[str] = frozenset({"ONGOING", "COMPLETED"})

#: Suffixes of an exam file, longest first so `x.mdq.md` is `x`.
EXAM_SUFFIXES = (".mdq.md", ".mdq", ".md")

#: The words that set the type of an exam, from a path.
_TYPE_WORDS: dict[str, ExamType] = {"quiz": "QUIZ", "practice": "PRACTICE"}

#: Separators of the words of a path component.
_WORD_BREAK = re.compile(r"[-_.]")

#: The inline id of an H1 such as `# [midterm] Midterm Exam`.
_H1_ID = re.compile(r"^#[ \t]+\[(?P<id>[^\]\n]+)\]", re.MULTILINE)


@dataclass(frozen=True)
class ExamFile:
    """
    One file under `exams/`, already parsed and slugged.

    `questions` are the slugs the exam holds, in order, includes resolved.
    `inline` are the questions the file writes itself, each of them among
    `questions` too.
    """

    slug: str
    path: Path
    type: ExamType
    status: LocalExamStatus
    title: str
    description: str | None
    preamble: str | None
    tags: tuple[str, ...]
    allow_code_run: bool | None
    questions: tuple[str, ...]
    #: `{"hours", "minutes"}` or `None` when the file declares none.
    duration: dict[str, JsonValue] | None = None
    #: The start as the server spells it, or `None` when the file declares none.
    scheduled_at: str | None = None
    inline: tuple[QuestionFile, ...] = ()
    #: The names of the `mdq` fields set to a value the server cannot hold.
    ignored: tuple[str, ...] = ()
    #: The attachments of the exam itself, fenced and linked.
    attachments: tuple[Attachment, ...] = ()
    #: Attachment name -> sha-256 of the linked attachments' bytes.
    files: Mapping[str, str] = field(default_factory=dict)
    #: Sha-256 -> the file the bytes of that attachment are read from.
    blobs: Mapping[str, Path] = field(default_factory=dict)
    #: The files its linked attachments were read from.
    sources: tuple[Path, ...] = ()

    @property
    def rev(self) -> str:
        """
        The `rev` of the exam's payload.
        """
        return exam_rev(exam_payload(self))


@dataclass(frozen=True)
class InvalidExam:
    """
    A file under `exams/` that `mdq` refused or whose includes do not
    resolve, kept so the push reports a failure and leaves what the server
    holds under its slug alone.
    """

    slug: str
    path: Path
    reason: str


@dataclass(frozen=True)
class IgnoredExamPolicy:
    """
    Fields of an exam file that the server has no column for: they are not
    sent.
    """

    slug: str
    path: Path
    fields: tuple[str, ...]


class LocalBank:
    """
    A `mdq.QuestionBank` over the questions the repository holds, by slug.
    """

    def __init__(self, questions: Mapping[str, mdq.Question]) -> None:
        self.questions = questions

    def load(self, question_id: str) -> Mapping[str, object]:
        try:
            question = self.questions[question_id]
        except KeyError:
            raise IncludeNotFound(question_id, "not a local question") from None
        return question.model_dump(mode="json", by_alias=True, exclude_none=True)

    def tagged(self, tag: str) -> Collection[str]:
        return {
            slug for slug, question in self.questions.items() if tag in question.tags
        }

    def ids(self) -> Collection[str]:
        return set(self.questions)


def exam_slug(exam_id: str | None, rel_path: Path) -> str:
    """
    The slug an exam file pushes under: its `id`, slugified, or else its
    flattened path under `exams/` without suffix and draft marks.

    `part1/exam.md` is `part1-exam` and `_drafts/_a.mdq.md` is `drafts-a`.
    """
    if exam_id:
        return slugify_text(exam_id)
    return slugify_text("-".join(_strip_suffix(_unmark(rel_path).parts)))


def exam_type(rel_path: Path) -> ExamType:
    """
    The type an exam file declares: the first `quiz` or `practice` word in
    its path, directories before the filename, and `EXAM` when there is none.

    A word is a run of characters between `-`, `_` or `.`, so
    `quizzical.md` is an `EXAM`.
    """
    for part in rel_path.parts:
        for word in _WORD_BREAK.split(part.lower()):
            if word in _TYPE_WORDS:
                return _TYPE_WORDS[word]
    return "EXAM"


def exam_status(rel_path: Path, *, scheduled: bool) -> LocalExamStatus:
    """
    `DRAFT` when the file or a directory under `exams/` starts with `_`;
    otherwise `SCHEDULED` if the exam declares a start, `DRAFT` if not.
    """
    if any(part.startswith(DRAFT_MARK) for part in rel_path.parts) or not scheduled:
        return "DRAFT"
    return "SCHEDULED"


def exam_duration(value: timedelta) -> dict[str, JsonValue]:
    """
    A duration as the `{hours, minutes}` the server takes: a plain total,
    with no 24 hour wrap and the seconds dropped.
    """
    minutes = int(value.total_seconds()) // 60
    return {"hours": minutes // 60, "minutes": minutes % 60}


def exam_scheduled_at(start: date | datetime) -> str:
    """
    A start as the UTC timestamp the server spells back: a date is midnight
    and a naive datetime is UTC.
    """
    if isinstance(start, datetime):
        moment = start.replace(tzinfo=UTC) if start.tzinfo is None else start
        moment = moment.astimezone(UTC)
    else:
        moment = datetime(start.year, start.month, start.day, tzinfo=UTC)
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{moment.microsecond // 1000:03d}Z"


def exam_rev(payload: Mapping[str, JsonValue]) -> str:
    """
    Digest an exam payload into the `rev` the server stores, the way
    `resource.content_ref` digests a resource.

    `attachments` and `files` count only when the exam has an attachment, so
    the `rev` of an exam without one is the same as before they existed.
    """
    if not payload.get("attachments"):
        payload = {
            key: value
            for key, value in payload.items()
            if key not in ("attachments", "files")
        }
    canonical = json.dumps(
        {"v": REF_PREFIX, **payload},
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{REF_PREFIX}:{digest}"


def inline_questions(
    exams: Sequence[ExamFile | InvalidExam],
) -> tuple[QuestionFile, ...]:
    """
    The questions the exams write inline, which a push sends as questions
    of their own.
    """
    return tuple(
        question
        for exam in exams
        if isinstance(exam, ExamFile)
        for question in exam.inline
    )


def scan_exams(
    root: Path,
    questions: Sequence[QuestionFile | InvalidQuestion],
    excluded: Sequence[ExcludedFile] = (),
) -> Iterator[ExamFile | InvalidExam]:
    """
    Walk `exams/` and yield an `ExamFile` per MDQ file, or an `InvalidExam`
    for one `mdq` refuses or whose includes do not resolve.

    `questions` are the ones scanned from `questions/` and `excluded` those
    `[push] exclude` leaves out: an include may name either, but only the
    first kind is sent, so naming the second is an error.

    Raises:
        SlugCollisionError: two exam files want the same slug, or an inline
            question wants the slug of another question. Raised before any
            exam is yielded.
        QuestionSourceError: a test file linked by an inline `code`
            question cannot be read.
    """
    base = root / "exams"
    index = _QuestionIndex.build(root, questions, excluded)
    left_out = {file.path for file in excluded if file.kind == "exam"}
    found = [
        _read_exam(base, path, index)
        for path in _exam_paths(base)
        if path.relative_to(root).as_posix() not in left_out
    ]

    exams: dict[str, list[Path]] = defaultdict(list)
    inline: dict[str, list[Path]] = defaultdict(list)
    for exam in found:
        exams[exam.slug].append(exam.path)
        if isinstance(exam, ExamFile):
            for question in exam.inline:
                inline[question.slug].append(question.path)
    collisions = {slug: paths for slug, paths in exams.items() if len(paths) > 1}
    for slug, paths in inline.items():
        taken = [index.paths_by_slug[slug]] if slug in index.paths_by_slug else []
        if len(paths) + len(taken) > 1:
            collisions[slug] = [*taken, *paths]
    if collisions:
        raise SlugCollisionError(collisions)
    yield from found


#
# Utilities
#
@dataclass(frozen=True)
class _QuestionIndex:
    """
    What an include can name: every question of `questions/` by slug, by
    filename stem and by path.
    """

    root: Path
    #: Slug -> why it cannot be included, `None` when it can.
    state: Mapping[str, str | None]
    by_stem: Mapping[str, tuple[str, ...]]
    by_path: Mapping[Path, str]
    paths_by_slug: Mapping[str, Path]
    bank: LocalBank

    @classmethod
    def build(
        cls,
        root: Path,
        questions: Sequence[QuestionFile | InvalidQuestion],
        excluded: Sequence[ExcludedFile],
    ) -> _QuestionIndex:
        entries: list[tuple[str, Path, str | None]] = []
        valid: dict[str, mdq.Question] = {}
        for item in questions:
            if isinstance(item, QuestionFile):
                entries.append((item.slug, item.path, None))
                valid[item.slug] = item.question
            else:
                entries.append((item.slug, item.path, f"is invalid: {item.reason}"))
        for file in excluded:
            if file.kind == "question":
                entries.append(
                    (file.slug, root / file.path, "is left out by [push] exclude")
                )
        state: dict[str, str | None] = {}
        paths: dict[str, Path] = {}
        by_path: dict[Path, str] = {}
        stems: dict[str, list[str]] = defaultdict(list)
        for slug, path, problem in entries:
            state.setdefault(slug, problem)
            paths.setdefault(slug, path)
            by_path[path.resolve()] = slug
            stem = _strip_suffix((path.name,))[0].removeprefix(DRAFT_MARK)
            stems[stem].append(slug)
        return cls(
            root=root,
            state=state,
            by_stem={s: tuple(dict.fromkeys(slugs)) for s, slugs in stems.items()},
            by_path=by_path,
            paths_by_slug=paths,
            bank=LocalBank(valid),
        )

    def resolve(self, include: str, exam_path: Path) -> str:
        """
        The slug `include` names, by the ladder of the mapping: an exact
        slug, then a unique filename stem, then a relative path.

        Raises:
            LookupError: nothing matches, or the match cannot be sent.
        """
        slug = self._find(include, exam_path)
        if slug is None:
            raise LookupError(f"include {include!r} matches no question")
        problem = self.state[slug]
        if problem is not None:
            raise LookupError(
                f"include {include!r} names question {slug!r}, which {problem}"
            )
        return slug

    def _find(self, include: str, exam_path: Path) -> str | None:
        if include in self.state:
            return include
        stems = self.by_stem.get(include.removeprefix(DRAFT_MARK), ())
        if len(stems) == 1:
            return stems[0]
        if "/" in include or include.endswith(EXAM_SUFFIXES):
            for directory in (exam_path.parent, self.root / "questions", self.root):
                for candidate in _candidates(directory / include):
                    found = self.by_path.get(candidate.resolve())
                    if found is not None:
                        return found
        return None


def _candidates(path: Path) -> Iterator[Path]:
    yield path
    for suffix in EXAM_SUFFIXES:
        yield path.with_name(path.name + suffix)


def _strip_suffix(parts: Sequence[str]) -> tuple[str, ...]:
    """
    `parts` with the suffix of the last one dropped, `.mdq.md` as one.
    """
    *head, last = parts
    for suffix in EXAM_SUFFIXES:
        if last.endswith(suffix):
            return (*head, last.removesuffix(suffix))
    return (*head, last)


def _unmark(rel_path: Path) -> Path:
    return Path(*(part.removeprefix(DRAFT_MARK) for part in rel_path.parts))


def _exam_paths(base: Path) -> list[Path]:
    if not base.is_dir():
        return []
    return sorted(
        path
        for path in base.rglob("*")
        if path.is_file() and path.name.endswith(EXAM_SUFFIXES)
    )


def peek_exam_slug(path: Path, rel_path: Path) -> str:
    """
    The slug of an exam file read without `mdq`: its `id` in the front matter
    or the H1, else its path under `exams/`.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return exam_slug(None, rel_path)
    return _peek_slug(text, rel_path)


def _peek_slug(text: str, rel_path: Path) -> str:
    """
    The slug of a file `mdq` refused: its `id` in the front matter or the
    H1, else its path.
    """
    front_matter, body = split_front_matter(text)
    exam_id = front_matter_str(front_matter, "id")
    if exam_id is None and (found := _H1_ID.search(body)):
        exam_id = found["id"].strip()
    return exam_slug(exam_id, rel_path)


def _read_exam(base: Path, path: Path, index: _QuestionIndex) -> ExamFile | InvalidExam:
    """
    Read and parse one exam file.

    Raises:
        QuestionSourceError: a test file of an inline question is missing.
    """
    rel_path = path.relative_to(base)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return InvalidExam(exam_slug(None, rel_path), path, str(exc))
    try:
        exam = mdq.parse(text, kind="exam")
        exam = resolve_exam_sources(exam, path.parent)
    except (mdq.InvalidDocument, ValidationError) as exc:
        return InvalidExam(_peek_slug(text, rel_path), path, str(exc))
    slug = exam_slug(exam.id, rel_path)
    try:
        return _build(slug, rel_path, path, exam, index)
    except (LookupError, ValueError) as exc:
        return InvalidExam(slug, path, str(exc))


def _build(
    slug: str, rel_path: Path, path: Path, exam: mdq.Exam, index: _QuestionIndex
) -> ExamFile:
    """
    Raises:
        LookupError: an include matches no question or one that is not sent.
        ValueError: `includeAll` has a `max`, a query cannot be read, the
            exam holds a question twice, or `meta.codeRun` is not a boolean.
    """
    code_run = (exam.meta or {}).get("codeRun")
    if code_run is not None and not isinstance(code_run, bool):
        raise ValueError(f"meta.codeRun must be true or false, not {code_run!r}")

    # Every include and inline slug first: an `includeAll` skips what the
    # exam already holds, wherever in the exam that is.
    slugs: dict[int, str] = {}
    inline: list[QuestionFile] = []
    for position, entry in enumerate(exam.questions, start=1):
        if isinstance(entry, Include):
            slugs[position] = index.resolve(entry.include, path)
        elif not isinstance(entry, IncludeAll):
            question_slug = _inline_slug(slug, entry.id, position)
            slugs[position] = question_slug
            inline.append(_inline_file(question_slug, entry, rel_path, path))
    held = set(slugs.values())

    questions: list[str] = []
    for position, entry in enumerate(exam.questions, start=1):
        if isinstance(entry, IncludeAll):
            added = _include_all(entry, index, held)
            held.update(added)
            questions.extend(added)
        else:
            questions.append(slugs[position])
    duplicates = sorted({s for s in questions if questions.count(s) > 1})
    if duplicates:
        raise ValueError(f"the exam holds {', '.join(map(repr, duplicates))} twice")

    ignored = tuple(
        name
        for name, set_ in (
            ("penalty", exam.penalty != "none"),
            ("grading", exam.grading != "symmetric"),
            ("shuffle", exam.shuffle),
        )
        if set_
    )
    if exam.duration is not None and exam_duration(exam.duration) == {
        "hours": 0,
        "minutes": 0,
    }:
        raise ValueError(f"duration {exam.duration} is under a minute")
    linked = read_attachments(exam.attachments, path.parent)
    stem = _strip_suffix((path.name,))[0]
    return ExamFile(
        slug=slug,
        path=path,
        type=exam_type(rel_path),
        status=exam_status(rel_path, scheduled=exam.start is not None),
        title=exam.title or title_from_filename(stem.removeprefix(DRAFT_MARK)),
        description=exam.description,
        preamble=exam.instructions,
        tags=tuple(exam.tags or ()),
        allow_code_run=code_run,
        questions=tuple(questions),
        duration=exam_duration(exam.duration) if exam.duration is not None else None,
        scheduled_at=exam_scheduled_at(exam.start) if exam.start is not None else None,
        inline=tuple(inline),
        ignored=ignored,
        attachments=tuple(exam.attachments or ()),
        files={item.name: item.sha256 for item in linked},
        blobs={item.sha256: item.path for item in linked},
        sources=tuple(item.path for item in linked),
    )


def _include_all(entry: IncludeAll, index: _QuestionIndex, held: set[str]) -> list[str]:
    """
    The slugs `entry`'s query selects that the exam does not hold yet, sorted.

    Raises:
        ValueError: the block has a `max` or a query that cannot be read.
    """
    if entry.max is not None:
        raise ValueError(
            f"includeAll {entry.include_all!r} has a max: a random pick "
            "never converges, so it is not supported"
        )
    try:
        chosen = parse_query(entry.include_all).select(index.bank)
    except QuerySyntaxError as exc:
        raise ValueError(f"includeAll {entry.include_all!r}: {exc}") from exc
    return sorted(chosen - held)


def _inline_slug(exam: str, question_id: str | None, position: int) -> str:
    part = slugify_text(question_id) if question_id else ""
    return f"{exam}-{part or f'q{position}'}"


def _inline_file(
    slug: str, question: mdq.Question, rel_path: Path, path: Path
) -> QuestionFile:
    """
    An inline question as a `QuestionFile`, versioned by its own content so
    editing one question does not change its siblings'.

    Linked attachments are relative to the exam file and, when there are any,
    their hashes join the canonical JSON as `files`.
    """
    linked = read_attachments(question.attachments, path.parent)
    files = {item.name: item.sha256 for item in linked}
    document = canonical_question(question)
    if files:
        document["files"] = {**files}
    canonical = json.dumps(
        document,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    )
    return QuestionFile(
        slug=slug,
        version=question_version(canonical.encode("utf-8")),
        question=question,
        path=path,
        status=question_status(rel_path),
        sources=(*test_source_paths(question, path.parent), *(i.path for i in linked)),
        files=files,
        blobs={item.sha256: item.path for item in linked},
    )
