"""
The files a push leaves out because of `[push] exclude` in `codehood.toml`.

Excluded files are never read, so they cannot be pushed; what the server
already holds under their slugs is protected from pruning (see
`plan.plan_sync`). `questions/`, `resources/` and `exams/` are excludable: they
are the trees whose files are pushed one by one.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..repo.diff import FileType
from ..repo.file_tracker import scan_files
from .exam import peek_exam_slug
from .question import peek_id, question_slug
from .resource import INFO_FILE, resource_slug

__all__ = ["ExcludedFile", "scan_excluded"]


@dataclass(frozen=True)
class ExcludedFile:
    """
    A question, exam or resource file that matched an `exclude` pattern.
    """

    kind: Literal["question", "resource", "exam"]
    slug: str
    #: Relative to the repository root, `/`-separated.
    path: str


def scan_excluded(root: Path, exclude: Sequence[str]) -> Iterator[ExcludedFile]:
    """
    Yield every question and resource file the patterns exclude.

    A question's slug may come from the `id` in its front matter, so that
    much of an excluded question is read; an unreadable one falls back to
    its path. An excluded `info.yaml` is metadata, not a resource, and is
    not yielded.
    """
    for file in scan_files(root, exclude):
        if not file.excluded:
            continue
        rel_path = Path(file.name)
        if file.type is FileType.QUESTION:
            slug = question_slug(peek_id(root / file.path), rel_path)
            yield ExcludedFile("question", slug, file.path.as_posix())
        elif file.type is FileType.EXAM:
            slug = peek_exam_slug(root / file.path, rel_path)
            yield ExcludedFile("exam", slug, file.path.as_posix())
        elif file.type is FileType.RESOURCE and rel_path.name != INFO_FILE:
            yield ExcludedFile(
                "resource", resource_slug(rel_path), file.path.as_posix()
            )
