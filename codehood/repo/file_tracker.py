from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, NamedTuple, Protocol

from ..functional import curry
from ..globs import is_excluded
from .diff import AddFile, Diff, FileType

MDQ_SUFFIXES = (".md", ".mdq")
EXAM_TYPES = {
    "draft": FileType.EXAM_DRAFT,
    "practice": FileType.EXAM_PRACTICE,
    "published": FileType.EXAM_PUBLISHED,
}


#
# File scanners
#
class ScanFiles(Protocol):
    def __call__(self) -> Iterable[File]: ...


@curry(1)
def scan_files(root: Path, exclude: Sequence[str] = ()) -> Iterable[File]:
    """
    Yield all files codehood tracks in the repository.

    Files outside a Codehood tree are ignored. Files under `resources/` and
    `questions/` that match an `exclude` pattern (see `codehood.globs`) are
    still yielded, flagged `excluded`, so a caller can report them and
    protect what the server holds for them.
    """

    def skipped(path: Path) -> bool:
        return is_excluded(path.relative_to(root).as_posix(), exclude)

    def if_exists(path: str | Path, typ: FileType):
        if (path := root / path).exists():
            yield File(str(path.relative_to(root)), typ)

    # Basic common files
    yield from if_exists("codehood.toml", FileType.CONFIG)
    yield from if_exists("README.md", FileType.README)
    yield from if_exists("calendar.md", FileType.CALENDAR)
    yield from if_exists("roster.csv", FileType.ROSTER)

    # Resources -- recurses, and only files become resources (see
    # `dev/specs/to-do/push.md`, "A resource's slug is its flattened path
    # under `resources/`": a subdirectory is not itself a resource).
    base = root / "resources"
    for resource in base.rglob("*"):
        if resource.is_dir():
            continue
        name = str(resource.relative_to(base))
        yield File(name, FileType.RESOURCE, excluded=skipped(resource))

    # Questions -- recurses, and only files become questions (same fix as
    # `resources/`, see `dev/specs/to-do/push-questions.md`).
    base = root / "questions"
    for question in base.rglob("*"):
        if question.is_dir():
            continue
        name = str(question.relative_to(base))
        excluded = skipped(question)
        if question.suffix in MDQ_SUFFIXES:
            yield File(name, FileType.QUESTION, excluded=excluded)
        else:
            yield File(
                name,
                FileType.WARNING,
                f"not a question file: {question.name}",
                excluded=excluded,
            )

    # Exams
    for kind, typ in EXAM_TYPES.items():
        for exam in (root / "exams" / kind).glob("*"):
            name = str(exam.relative_to(root / "exams"))
            if exam.suffix in MDQ_SUFFIXES:
                yield File(name, typ)
            else:
                yield File(
                    name,
                    FileType.WARNING,
                    f"not an exam file: {kind}/{exam.name}",
                )


#
# Differs
#
class ScanDiffs(Protocol):
    def __call__(self, files: Iterable[File]) -> Iterable[Diff]: ...


@curry(1)
def find_diffs(
    root: Path,
    files: Iterable[File],
    mode: Literal["quick", "strict"] = "quick",
) -> Iterable[Diff]:
    """
    Track files in the repo and flag which ones were changed since the last commit.

    There is no local state to diff against -- see `dev/specs/to-do/
    push.md`, "There is no local state" -- so every file currently reads
    as added. A caller wanting an actual diff compares against the
    server's state instead, the way `codehood.push.plan.plan_push` does
    for resources.
    """

    for file in files:
        yield AddFile(file.name, file.type)


class File(NamedTuple):
    name: str
    type: FileType
    message: str | None = None
    excluded: bool = False

    @property
    def path(self) -> Path:
        return self.type.path(self.name)
